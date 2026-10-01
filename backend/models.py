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
    #: 발급한 JWT 를 되돌리는 수단. 토큰에 이 값을 실어 두고 요청마다 대조한다.
    #: 비밀번호가 변경되면 1 올려서 그 사용자의 옛 토큰을 한 번에 막는다.
    #: JWT 는 발급하면 서버가 손댈 수 없으므로 이 대조가 유일한 폐기 경로다.
    token_version = Column(Integer, default=0, nullable=False, server_default="0")
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
    # 이슈 관리 도구 종류. "jira" / "linear" 이고 NULL 이면 주소 모양으로 짐작한다
    # (이 컬럼이 생기기 전 프로젝트와 같다).
    issue_tracker = Column(String(20), nullable=True)
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
        # ★이름이 겹치면 rename/delete 가 `.first()` 로 한쪽만 건드리고, TC 의
        #   sheet_name 은 이름으로 잇기 때문에 어느 시트의 것인지 정해지지 않는다.
        #   조회 후 삽입만으로는 동시 요청과 임포트를 막지 못한다.
        Index("uq_test_case_sheets_project_name", "project_id", "name", unique=True),
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
    # 리포트의 비교 대상. NULL 이면 같은 이름의 이전 회차를 쓰고, 그것도 없으면 비교하지 않는다.
    compare_run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_kst)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="test_runs")
    creator = relationship("User", back_populates="test_runs")
    test_plan = relationship("TestPlan", back_populates="test_runs")
    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")
    issues = relationship(
        "RunIssue", back_populates="test_run", cascade="all, delete-orphan",
        order_by="RunIssue.id", foreign_keys="RunIssue.test_run_id",
    )

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


# ── RunIssue ─────────────────────────────────────────────────────────────────

#: 이슈의 QA 확인 결과. 해결 · 유지 · 부분 해결 · 미확인.
ISSUE_VERDICTS = ("resolved", "open", "partial", "unverified")


def issue_group(origin_round, verdict) -> str:
    """리포트가 이슈를 나누는 묶음. 둘뿐이다(09-30 사용자 결정).

    - resolved: 판정이 해결.
    - open: 그 밖의 전부. 유지 · 부분 해결 · 미확인 · 판정 없음, 그리고 이번 수행에서
      새로 발견한 이슈. 확인하지 않았거나 새로 났어도 해결된 것은 아니므로 미해결이다.
      신규인지는 발견 열("이번 수행")로 안다. 예전에는 신규 · 미확인을 따로 묶어 넷이었다.
    """
    return "resolved" if verdict == "resolved" else "open"


#: 리포트에 싣는 차례. 미해결부터, 처리 완료는 뒤.
ISSUE_GROUP_ORDER = ("open", "resolved")


class RunIssue(Base):
    """수행 하나에 딸린 이슈. 리포트의 이슈 섹션이 이것을 싣는다.

    결과 행의 issue_link 칸과는 따로 둔다. 그 칸은 자유 문구라 키를 뽑을 수 없는
    값이 많고, TC 에 묶이지 않은 이슈(탐색 중 발견 등)는 적을 자리가 없었다.
    이슈 관리 도구와 연동하지 않고 사람이나 MCP 가 제목과 주소를 넣는다.
    """
    __tablename__ = "run_issues"

    id = Column(Integer, primary_key=True, index=True)
    test_run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    #: SF-1081 같은 키. 비우면 주소에서 뽑고, 못 뽑으면 NULL 로 둔다.
    issue_key = Column(String(50), nullable=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False)
    #: 도구의 상태 이름을 그대로 적는다(Todo, In Progress 등). 도구마다 달라 열거하지 않는다.
    status = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)
    #: 처음 발견한 수행. NULL 이면 이번 수행에서 처음 발견한 것(신규)이다. 이전 회차에서
    #: 가져온 이슈는 그 회차를 가리킨다. 수행이 지워져도 origin_round 는 남는다.
    origin_run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True)
    origin_round = Column(Integer, nullable=True)
    #: 이번 수행에서 QA 가 확인한 결과(ISSUE_VERDICTS). 도구의 상태(status)와 따로 둔다.
    #: 개발이 배포했다고 처리된 것이 아니라 QA 가 재현해 봐야 처리 완료다.
    verdict = Column(String(20), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_kst)
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)

    test_run = relationship("TestRun", back_populates="issues", foreign_keys=[test_run_id])
    origin_run = relationship("TestRun", foreign_keys=[origin_run_id])
    creator = relationship("User")
    #: 연관 TC. 없을 수도 여럿일 수도 있다. TC 가 지워지면 연결만 풀린다(FK CASCADE).
    test_cases = relationship(
        "TestCase", secondary="run_issue_test_cases", order_by="TestCase.no", lazy="selectin",
    )

    @property
    def tc_ids(self) -> list:
        return [tc.tc_id for tc in self.test_cases]

    __table_args__ = (
        # 같은 이슈를 두 번 넣지 않는다. MCP 가 같은 목록을 다시 채워도 중복이 쌓이지 않게 한다.
        Index("uq_run_issues_run_url", "test_run_id", "url", unique=True),
    )


class RunIssueTestCase(Base):
    """이슈와 연관 TC 의 연결. 순서는 TC 번호를 따르므로 따로 두지 않는다."""
    __tablename__ = "run_issue_test_cases"

    run_issue_id = Column(Integer, ForeignKey("run_issues.id", ondelete="CASCADE"), primary_key=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (
        Index("ix_run_issue_test_cases_case_id", "test_case_id"),
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
        # ★유일해야 한다. 멤버가 둘이면 권한 조회의 `.first()` 가 아무 역할이나
        #   돌려주어 판정이 비결정적이 되고, 삭제는 한 행만 지워 권한이 남는다.
        Index("ix_project_members_project_user", "project_id", "user_id", unique=True),
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


# ── ApiKey ────────────────────────────────────────────────────────────────────

class ApiKey(Base):
    """스크립트 · CI 가 비밀번호 없이 API 를 부르는 수단.

    원문은 발급 응답에서 한 번만 보여 주고 저장하지 않는다. 원문이 충분히 무작위라
    (256비트) bcrypt 같은 느린 해시가 필요 없고, SHA-256 으로 대조한다.
    key_id 는 원문 안에 그대로 들어 있는 짧은 식별자다. 해시 대조 전에 행을 찾는 데 쓰고,
    화면에서 어느 키인지 알아보는 데도 쓴다.
    """
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    key_id = Column(String(16), nullable=False, unique=True)
    key_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=now_kst)
    #: 요청마다 쓰면 읽기 요청도 전부 쓰기가 된다. 1분 넘게 지났을 때만 갱신한다.
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_api_keys_user_id", "user_id"),
    )
