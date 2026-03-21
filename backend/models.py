import enum
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST).replace(tzinfo=None)

from sqlalchemy import (
    Boolean, Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum as SAEnum, JSON
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
    created_at = Column(DateTime, default=now_kst)

    project = relationship("Project")
    parent = relationship("TestCaseSheet", remote_side="TestCaseSheet.id", backref="children")


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
    issue_link = Column(String(500), nullable=True)
    assignee = Column(String(100), nullable=True)
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


# ── TestRun ───────────────────────────────────────────────────────────────────

class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    version = Column(String(50), nullable=True)
    environment = Column(String(100), nullable=True)
    round = Column(Integer, default=1)
    status = Column(SAEnum(TestRunStatus), default=TestRunStatus.in_progress)
    test_plan_id = Column(Integer, ForeignKey("test_plans.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_kst)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="test_runs")
    creator = relationship("User", back_populates="test_runs")
    test_plan = relationship("TestPlan", back_populates="test_runs")
    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")


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


# ── Attachment ───────────────────────────────────────────────────────────────

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    test_result_id = Column(Integer, ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False)
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
