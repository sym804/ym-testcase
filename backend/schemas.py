from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Auth / User ───────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str = Field(..., min_length=8)
    display_name: str


class UserLogin(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    must_change_password: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRoleUpdate(BaseModel):
    role: str  # user, qa_manager, admin


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


# ── Account Recovery ──────────────────────────────────────────────────────────

class AccountRequestCreate(BaseModel):
    request_type: str  # find_id | reset_password
    claimed_username: Optional[str] = Field(None, max_length=100)
    claimed_display_name: Optional[str] = Field(None, max_length=100)
    contact: str = Field(..., min_length=1, max_length=200)
    note: Optional[str] = Field(None, max_length=1000)

    @field_validator("claimed_username", "claimed_display_name", "contact", mode="before")
    @classmethod
    def _strip(cls, v):
        """앞뒤 공백을 서버에서 없앤다.

        중복 판정이 이 값들을 그대로 비교하므로, 뒤에 공백 하나가 붙은 값은 다른
        요청으로 취급되어 큐에 같은 건이 두 번 쌓인다. 길이 제한은 공백을 없앤
        뒤에 적용된다.
        """
        return v.strip() if isinstance(v, str) else v


class AccountRequestAck(BaseModel):
    """접수 응답. 대상 존재 여부를 드러내지 않도록 항상 같은 값을 낸다."""
    message: str


class AccountRequestListItem(BaseModel):
    id: int
    request_type: str
    status: str
    claimed_username: Optional[str] = None
    claimed_display_name: Optional[str] = None
    contact: str
    note: Optional[str] = None
    user_id: Optional[int] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AccountRequestApprove(BaseModel):
    user_id: int


class AccountRequestReject(BaseModel):
    note: Optional[str] = None


class AccountRequestApproveResult(BaseModel):
    """find_id 는 username 만, reset_password 는 code 와 만료 시각만 채워진다."""
    request_type: str
    username: Optional[str] = None
    code: Optional[str] = None
    code_expires_at: Optional[datetime] = None


class ResetPasswordWithCode(BaseModel):
    username: str
    code: str
    new_password: str = Field(..., min_length=8)


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    jira_base_url: Optional[str] = None
    is_private: bool = False


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    jira_base_url: Optional[str] = None
    is_private: Optional[bool] = None
    field_config: Optional[dict] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    jira_base_url: Optional[str] = None
    is_private: bool = False
    field_config: Optional[dict] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    my_role: Optional[str] = None  # 현재 사용자의 프로젝트 역할

    model_config = ConfigDict(from_attributes=True)


# ── Project Members ──────────────────────────────────────────────────────────

class ProjectMemberCreate(BaseModel):
    user_id: int
    role: str = "tester"  # tester, admin


class ProjectMemberUpdate(BaseModel):
    role: str


class ProjectMemberResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    role: str
    added_at: datetime
    username: Optional[str] = None
    display_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── TestCase ──────────────────────────────────────────────────────────────────

class TestCaseCreate(BaseModel):
    #: 보내지 않아도 된다. `no` 는 시트 안 순번이라 서버가 정한다.
    #: 보낸 값은 참고하지 않는다. 클라이언트가 정하면 같은 시트에 같은 번호가
    #: 들어오거나 구멍이 생겨 규약이 다시 깨진다.
    no: Optional[int] = None
    tc_id: str
    type: Optional[str] = None
    category: Optional[str] = None
    depth1: Optional[str] = None
    depth2: Optional[str] = None
    priority: Optional[str] = None
    test_type: Optional[str] = None
    precondition: Optional[str] = None
    test_steps: Optional[str] = None
    expected_result: Optional[str] = None
    r1: Optional[str] = None
    r2: Optional[str] = None
    r3: Optional[str] = None
    remarks: Optional[str] = None
    sheet_name: Optional[str] = "기본"
    custom_fields: Optional[dict[str, Any]] = None


class TestCaseUpdate(BaseModel):
    no: Optional[int] = None
    tc_id: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    depth1: Optional[str] = None
    depth2: Optional[str] = None
    priority: Optional[str] = None
    test_type: Optional[str] = None
    precondition: Optional[str] = None
    test_steps: Optional[str] = None
    expected_result: Optional[str] = None
    r1: Optional[str] = None
    r2: Optional[str] = None
    r3: Optional[str] = None
    remarks: Optional[str] = None
    sheet_name: Optional[str] = None
    custom_fields: Optional[dict[str, Any]] = None


class TestCaseResponse(BaseModel):
    id: int
    project_id: int
    no: int
    tc_id: str
    type: Optional[str] = None
    category: Optional[str] = None
    depth1: Optional[str] = None
    depth2: Optional[str] = None
    priority: Optional[str] = None
    test_type: Optional[str] = None
    precondition: Optional[str] = None
    test_steps: Optional[str] = None
    expected_result: Optional[str] = None
    r1: Optional[str] = None
    r2: Optional[str] = None
    r3: Optional[str] = None
    remarks: Optional[str] = None
    sheet_name: str = "기본"
    custom_fields: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    created_by: int

    model_config = ConfigDict(from_attributes=True)


class TestCaseBulkItem(BaseModel):
    id: int
    no: Optional[int] = None
    tc_id: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    depth1: Optional[str] = None
    depth2: Optional[str] = None
    priority: Optional[str] = None
    test_type: Optional[str] = None
    precondition: Optional[str] = None
    test_steps: Optional[str] = None
    expected_result: Optional[str] = None
    r1: Optional[str] = None
    r2: Optional[str] = None
    r3: Optional[str] = None
    remarks: Optional[str] = None
    sheet_name: Optional[str] = None
    custom_fields: Optional[dict[str, Any]] = None


class TestCaseBulkUpdate(BaseModel):
    items: List[TestCaseBulkItem]


# ── TestRun ───────────────────────────────────────────────────────────────────

class TestRunCreate(BaseModel):
    name: str
    version: Optional[str] = None
    environment: Optional[str] = None
    round: int = 1
    test_plan_id: Optional[int] = None
    #: 이 런에 담을 시트. 생략하거나 None 이면 프로젝트 전체를 담는다.
    sheet_names: Optional[List[str]] = None


class TestRunUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    environment: Optional[str] = None
    round: Optional[int] = None


class TestResultCreate(BaseModel):
    test_case_id: int
    result: str  # PASS/FAIL/BLOCK/NA/NS
    actual_result: Optional[str] = None
    issue_link: Optional[str] = None
    remarks: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_sec: Optional[float] = None


class TestResultUpdate(BaseModel):
    result: Optional[str] = None
    actual_result: Optional[str] = None
    issue_link: Optional[str] = None
    remarks: Optional[str] = None


class TestResultResponse(BaseModel):
    id: int
    test_run_id: int
    test_case_id: int
    result: str
    actual_result: Optional[str] = None
    issue_link: Optional[str] = None
    remarks: Optional[str] = None
    executed_by: int
    executed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_sec: Optional[float] = None
    test_case: Optional[TestCaseResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ── Attachment ───────────────────────────────────────────────────────────────

class AttachmentResponse(BaseModel):
    id: int
    test_result_id: int
    filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_by: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── TestCase History ─────────────────────────────────────────────────────────

class TestCaseHistoryResponse(BaseModel):
    id: int
    test_case_id: int
    changed_by: int
    changer_name: Optional[str] = None
    changed_at: datetime
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    tc_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TestRunResponse(BaseModel):
    id: int
    project_id: int
    name: str
    version: Optional[str] = None
    environment: Optional[str] = None
    round: int
    status: str
    sheet_names: Optional[List[str]] = None
    test_plan_id: Optional[int] = None
    created_by: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    @field_validator("round", mode="before")
    @classmethod
    def _round_default(cls, v):
        """비어 있으면 1 라운드로 읽는다.

        ★컬럼은 NOT NULL 로 바꿨지만(e5a83f21c760) 마이그레이션 전 DB 를 보는
          서버가 있으면 여기서 다시 터진다. 목록 응답 하나가 못 만들어지면 그
          프로젝트의 수행 목록 전체가 500 이 되므로 읽는 쪽도 견디게 둔다.
        """
        return 1 if v is None else v
    results: List[TestResultResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TestRunListResponse(BaseModel):
    id: int
    project_id: int
    name: str
    version: Optional[str] = None
    environment: Optional[str] = None
    round: int
    status: str
    sheet_names: Optional[List[str]] = None
    test_plan_id: Optional[int] = None
    created_by: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    @field_validator("round", mode="before")
    @classmethod
    def _round_default(cls, v):
        """비어 있으면 1 라운드로 읽는다.

        ★컬럼은 NOT NULL 로 바꿨지만(e5a83f21c760) 마이그레이션 전 DB 를 보는
          서버가 있으면 여기서 다시 터진다. 목록 응답 하나가 못 만들어지면 그
          프로젝트의 수행 목록 전체가 500 이 되므로 읽는 쪽도 견디게 둔다.
        """
        return 1 if v is None else v

    model_config = ConfigDict(from_attributes=True)


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total: int
    pass_: int = 0
    fail: int = 0
    block: int = 0
    na: int = 0
    not_started: int = 0
    pass_rate: float = 0.0
    fail_rate: float = 0.0
    block_rate: float = 0.0
    na_rate: float = 0.0
    not_started_rate: float = 0.0

    model_config = ConfigDict(populate_by_name=True)

    def model_dump(self, **kwargs):
        d = super().model_dump(**kwargs)
        d["pass"] = d.pop("pass_", 0)
        return d


class PriorityDistribution(BaseModel):
    priority: str
    total: int
    pass_: int = 0
    fail: int = 0
    block: int = 0
    na: int = 0
    not_started: int = 0

    def model_dump(self, **kwargs):
        d = super().model_dump(**kwargs)
        d["pass"] = d.pop("pass_", 0)
        return d


class CategoryBreakdown(BaseModel):
    category: str
    total: int
    pass_: int = 0
    fail: int = 0
    block: int = 0
    na: int = 0
    not_started: int = 0

    def model_dump(self, **kwargs):
        d = super().model_dump(**kwargs)
        d["pass"] = d.pop("pass_", 0)
        return d


class RoundComparison(BaseModel):
    round: int
    total: int
    pass_: int = 0
    fail: int = 0
    block: int = 0
    na: int = 0
    pass_rate: float = 0.0

    def model_dump(self, **kwargs):
        d = super().model_dump(**kwargs)
        d["pass"] = d.pop("pass_", 0)
        return d


class AssigneeSummary(BaseModel):
    assignee: str
    total: int
    pass_: int = 0
    fail: int = 0
    block: int = 0
    na: int = 0
    not_started: int = 0
    completion_rate: float = 0.0

    def model_dump(self, **kwargs):
        d = super().model_dump(**kwargs)
        d["pass"] = d.pop("pass_", 0)
        return d


# ── Custom Field ─────────────────────────────────────────────────────────────

class CustomFieldDefCreate(BaseModel):
    field_name: str
    field_type: str = "text"  # text, number, select, multiselect, checkbox, date
    options: Optional[List[str]] = None
    is_required: bool = False


class CustomFieldDefUpdate(BaseModel):
    field_name: Optional[str] = None
    field_type: Optional[str] = None
    options: Optional[List[str]] = None
    is_required: Optional[bool] = None
    sort_order: Optional[int] = None


class CustomFieldDefResponse(BaseModel):
    id: int
    project_id: int
    field_name: str
    field_type: str
    options: Optional[List[str]] = None
    sort_order: int
    is_required: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Test Plan ────────────────────────────────────────────────────────────────

class TestPlanCreate(BaseModel):
    name: str
    milestone: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TestPlanUpdate(BaseModel):
    name: Optional[str] = None
    milestone: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TestPlanResponse(BaseModel):
    id: int
    project_id: int
    name: str
    milestone: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    run_count: int = 0
    progress: Optional[dict] = None  # {total, pass, fail, ...}

    model_config = ConfigDict(from_attributes=True)


# ── Saved Filter ─────────────────────────────────────────────────────────────

class FilterCondition(BaseModel):
    field: str
    operator: str  # eq, neq, contains, not_contains, gt, lt, gte, lte, in, empty, not_empty
    value: Optional[Any] = None


class SavedFilterCreate(BaseModel):
    name: str
    conditions: List[FilterCondition]
    logic: str = "AND"  # AND / OR


class SavedFilterUpdate(BaseModel):
    name: Optional[str] = None
    conditions: Optional[List[FilterCondition]] = None
    logic: Optional[str] = None


class SavedFilterResponse(BaseModel):
    id: int
    project_id: int
    name: str
    conditions: List[dict]
    logic: str
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
