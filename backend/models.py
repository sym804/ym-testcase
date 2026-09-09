import enum
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST).replace(tzinfo=None)

from sqlalchemy import (
    Boolean, Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum as SAEnum, JSON, Index, text
)
from sqlalchemy.orm import relationship

from database import Base


class UserRole(str, enum.Enum):
    user = "user"
    qa_manager = "qa_manager"
    admin = "admin"


class ProjectRole(str, enum.Enum):
    tester = "tester"
    admin = "admin"


class TestRunStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


class TestResultValue(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCK = "BLOCK"
    NA = "NA"
    NS = "NS"


class AccountRequestType(str, enum.Enum):
    find_id = "find_id"
    reset_password = "reset_password"


class AccountRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.user, nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now_kst)

    projects = relationship("Project", back_populates="creator")
    test_cases = relationship("TestCase", back_populates="creator")
    test_runs = relationship("TestRun", back_populates="creator")
    test_results = relationship("TestResult", back_populates="executor")


# ── Project ───────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    jira_base_url = Column(String(500), nullable=True)
    is_private = Column(Boolean, default=False, nullable=False)
    field_config = Column(Text, nullable=True, default=None)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_kst)
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)

    creator = relationship("User", back_populates="projects")
    test_cases = relationship("TestCase", back_populates="project", cascade="all, delete-orphan")
    test_runs = relationship("TestRun", back_populates="project", cascade="all, delete-orphan")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")


# ── TestCaseSheet ─────────────────────────────────────────────────────────────

class TestCaseSheet(Base):
    __tablename__ = "test_case_sheets"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    parent_id = Column(Integer, ForeignKey("test_case_sheets.id", ondelete="CASCADE"), nullable=True)
    is_folder = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now_kst)

    project = relationship("Project")
    parent = relationship("TestCaseSheet", remote_side="TestCaseSheet.id", backref="children")

    __table_args__ = (
        Index("ix_test_case_sheets_project_id", "project_id"),
        Index("ix_test_case_sheets_parent_id", "parent_id"),
    )


# ── TestCase ──────────────────────────────────────────────────────────────────

class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    no = Column(Integer, nullable=False)
    tc_id = Column(String(50), nullable=False)
    type = Column(String(50), nullable=True)          # Func./UI/UX etc.
    category = Column(String(200), nullable=True)
    depth1 = Column(String(200), nullable=True)
    depth2 = Column(String(200), nullable=True)
    priority = Column(String(20), nullable=True)       # High/Medium/Low
    test_type = Column(String(50), nullable=True)
    precondition = Column(Text, nullable=True)
    test_steps = Column(Text, nullable=True)
    expected_result = Column(Text, nullable=True)
    r1 = Column(String(10), nullable=True)
    r2 = Column(String(10), nullable=True)
    r3 = Column(String(10), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_kst)
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    sheet_name = Column(String(100), default="기본", nullable=False)
    custom_fields = Column(JSON, nullable=True, default=None)
    deleted_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="test_cases")
    creator = relationship("User", back_populates="test_cases")
    test_results = relationship("TestResult", back_populates="test_case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_cases_project_id_deleted", "project_id", "deleted_at"),
        Index("ix_test_cases_sheet_name", "project_id", "sheet_name"),
        # TC ID 는 프로젝트 안에서 유일하다. 사전조건 참조 색인이 프로젝트 전체
        # TC 로 만들어져서, 중복이면 참조가 어느 쪽을 가리키는지 정해지지 않는다.
        # 소프트 삭제된 행은 제외해야 지운 번호를 다시 쓸 수 있다.
        Index(
            "uq_test_cases_project_tc_id", "project_id", "tc_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # no 는 시트 안 순번이라 겹치면 안 된다. 규칙만 두면 어긋난다. 신규 생성,
        # 복제, 임포트, 드래그 정렬 넷이 번호를 넣는데 그중 하나만 새도 무너진다.
        # 지운 행은 뺀다. 되살릴 때 번호가 겹치면 restore 가 다시 매긴다.
        Index(
            "uq_test_cases_sheet_no", "project_id", "sheet_name", "no",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


# ── TestRun ───────────────────────────────────────────────────────────────────

class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    version = Column(String(50), nullable=True)
    environment = Column(String(100), nullable=True)
    # ★NULL 을 받지 않는다. 응답 스키마가 필수 정수로 읽어서, NULL 이 하나라도
    #   섞이면 그 프로젝트의 수행 목록 전체가 500 이 됐다(실 DB 에 2건 있었다).
    round = Column(Integer, nullable=False, server_default="1", default=1)
    status = Column(SAEnum(TestRunStatus), default=TestRunStatus.in_progress)
    # 이 런이 담는 시트. NULL 이면 프로젝트 전체다(이 컬럼이 생기기 전 런과 같다).
    # 생성 시점의 필터가 아니라 런의 범위다. 진행 중 런이 새 TC 를 흡수할 때도
    # 이 범위를 지켜야 제외한 시트가 나중에 슬그머니 들어오지 않는다.
    sheet_names = Column(JSON, nullable=True, default=None)
    test_plan_id = Column(Integer, ForeignKey("test_plans.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_kst)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="test_runs")
    creator = relationship("User", back_populates="test_runs")
    test_plan = relationship("TestPlan", back_populates="test_runs")
    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_runs_project_id", "project_id"),
        Index("ix_test_runs_status", "project_id", "status"),
    )


# ── TestResult ────────────────────────────────────────────────────────────────

class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    test_run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    result = Column(SAEnum(TestResultValue), nullable=False)
    actual_result = Column(Text, nullable=True)
    issue_link = Column(String(500), nullable=True)
    remarks = Column(Text, nullable=True)
    executed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    executed_at = Column(DateTime, default=now_kst)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_sec = Column(Float, nullable=True)

    test_run = relationship("TestRun", back_populates="results")
    test_case = relationship("TestCase", back_populates="test_results")
    executor = relationship("User", back_populates="test_results")
    attachments = relationship("Attachment", back_populates="test_result", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_results_run_id", "test_run_id"),
        Index("ix_test_results_run_result", "test_run_id", "result"),
        Index("ix_test_results_case_id", "test_case_id"),
        # 한 런에서 한 TC 의 결과 행은 하나다. 결과 행을 만드는 경로가 셋이고
        # (런 생성 / 런 동기화 / 결과 제출) 셋 다 "없는 것을 조회한 뒤 넣는" 모양이라
        # 동시 요청에서 같은 쌍이 두 번 들어갈 수 있다. 실제로 운영 DB 에 있었다.
        Index("uq_test_results_run_case", "test_run_id", "test_case_id", unique=True),
    )


# ── Attachment ───────────────────────────────────────────────────────────────

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    test_result_id = Column(
        Integer, ForeignKey("test_results.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename = Column(String(500), nullable=False)
    filepath = Column(String(1000), nullable=False)
    content_type = Column(String(200), nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=now_kst)

    test_result = relationship("TestResult", back_populates="attachments")
    uploader = relationship("User")


# ── ProjectMember ────────────────────────────────────────────────────────────

class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(SAEnum(ProjectRole), default=ProjectRole.tester, nullable=False)
    added_at = Column(DateTime, default=now_kst)

    project = relationship("Project", back_populates="members")
    user = relationship("User")

    __table_args__ = (
        Index("ix_project_members_project_user", "project_id", "user_id"),
    )


# ── CustomFieldDef ───────────────────────────────────────────────────────────

class CustomFieldDef(Base):
    __tablename__ = "custom_field_defs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(100), nullable=False)
    field_type = Column(String(20), nullable=False, default="text")  # text, number, select, multiselect, checkbox, date
    options = Column(JSON, nullable=True)  # select/multiselect 용 옵션 리스트
    sort_order = Column(Integer, default=0, nullable=False)
    is_required = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now_kst)

    project = relationship("Project")


# ── TestPlan ────────────────────────────────────────────────────────────────

class TestPlan(Base):
    __tablename__ = "test_plans"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    milestone = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_kst)
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)

    project = relationship("Project")
    creator = relationship("User")
    test_runs = relationship("TestRun", back_populates="test_plan")


# ── SavedFilter ─────────────────────────────────────────────────────────────

class SavedFilter(Base):
    __tablename__ = "saved_filters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    conditions = Column(JSON, nullable=False)  # [{field, operator, value}]
    logic = Column(String(3), default="AND", nullable=False)  # AND / OR
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_kst)

    project = relationship("Project")
    creator = relationship("User")


# ── TestCaseHistory ──────────────────────────────────────────────────────────

class TestCaseHistory(Base):
    __tablename__ = "test_case_history"

    id = Column(Integer, primary_key=True, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, default=now_kst)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    test_case = relationship("TestCase")
    changer = relationship("User")

    __table_args__ = (
        Index("ix_test_case_history_tc_id", "test_case_id"),
    )


# ── AccountRequest ────────────────────────────────────────────────────────────

class AccountRequest(Base):
    """계정 복구 요청. 비로그인 사용자가 넣고 관리자가 처리한다.

    claimed_* 는 사용자가 적은 값을 검증 없이 담는 자리다. 승인 전까지는
    실재하는 계정을 가리킨다는 보장이 없다. 관리자가 확정한 대상만 user_id 로 들어간다.
    """
    __tablename__ = "account_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_type = Column(SAEnum(AccountRequestType), nullable=False)
    status = Column(SAEnum(AccountRequestStatus), default=AccountRequestStatus.pending, nullable=False)

    claimed_username = Column(String(100), nullable=True)
    claimed_display_name = Column(String(100), nullable=True)
    contact = Column(String(200), nullable=False)
    note = Column(Text, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    code_hash = Column(String(255), nullable=True)
    code_expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=now_kst)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_account_requests_status_created", "status", "created_at"),
    )
