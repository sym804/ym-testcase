from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: TC ID 길이 상한. 컬럼이 String(50) 인데 SQLite 는 길이를 강제하지 않아서,
#: 검증이 없으면 긴 값이 그대로 쌓이고 PostgreSQL 로 옮길 때 그 데이터를 못 옮긴다.
#: 값은 채번 쪽(tc_id_service)이 원본이다. 두 벌로 두면 컬럼을 늘릴 때 한쪽만 변경된다.
from services.tc_id_service import TC_ID_MAX_LEN  # noqa: E402


# ── Auth / User ───────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str = Field(..., min_length=8)
    display_name: str


class UserLogin(BaseModel):
    # users.username 은 100자. 넘는 입력은 존재할 수 없는 계정이라 422 로 막는다
    # (횟수 제한 기록 키 칸 255자를 넘겨 500 이 나던 경로).
    username: str = Field(..., max_length=100)
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
    username: str = Field(..., max_length=100)
    code: str
    new_password: str = Field(..., min_length=8)


# ── Project ───────────────────────────────────────────────────────────────────

#: 고를 수 있는 이슈 관리 도구. 빈 값은 "지정 안 함" 으로 읽어 NULL 로 저장한다.
ISSUE_TRACKERS = ("jira", "linear")


def _normalize_tracker(v):
    if v is None:
        return None
    v = str(v).strip().lower()
    if not v:
        return None
    if v not in ISSUE_TRACKERS:
        raise ValueError(f"issue_tracker must be one of {', '.join(ISSUE_TRACKERS)}")
    return v


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    jira_base_url: Optional[str] = None
    issue_tracker: Optional[str] = None
    is_private: bool = False

    @field_validator("issue_tracker", mode="before")
    @classmethod
    def _tracker(cls, v):
        return _normalize_tracker(v)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    jira_base_url: Optional[str] = None
    issue_tracker: Optional[str] = None
    is_private: Optional[bool] = None
    field_config: Optional[dict] = None

    @field_validator("issue_tracker", mode="before")
    @classmethod
    def _tracker(cls, v):
        return _normalize_tracker(v)


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    jira_base_url: Optional[str] = None
    issue_tracker: Optional[str] = None
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
    tc_id: str = Field(..., min_length=1, max_length=TC_ID_MAX_LEN)
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
    tc_id: Optional[str] = Field(None, min_length=1, max_length=TC_ID_MAX_LEN)
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
    #: 리포트의 비교 대상 수행. null 이면 자동(같은 이름의 이전 회차)으로 되돌린다.
    compare_run_id: Optional[int] = None


class TestResultCreate(BaseModel):
    test_case_id: int
    result: str  # PASS/FAIL/BLOCK/NA/NS
    actual_result: Optional[str] = None
    issue_link: Optional[str] = None
    remarks: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_sec: Optional[float] = None
    #: 화면이 읽어 둔 행의 executed_at. 보내면 서버가 그 뒤에 다른 저장이 있었는지 확인해
    #: 있으면 409 로 거절한다(낙관적 잠금). 비우면 예전처럼 검사하지 않는다(스크립트 · MCP).
    expected_executed_at: Optional[str] = None


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
    compare_run_id: Optional[int] = None
    created_by: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    @field_validator("round", mode="before")
    @classmethod
    def _round_default(cls, v):
        """비어 있으면 1 라운드로 읽는다.

        ★컬럼은 NOT NULL 이다(SQLite 시절 e5a83f21c760 에서 바꿨고 기준점도 같다).
          SQLite 에서 옮겨 온 옛 행에 NULL 이 섞여 있을 수 있어 읽는 쪽도 견디게 둔다.
          목록 응답 하나가 못 만들어지면 그 프로젝트의 수행 목록 전체가 500 이 된다.
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
    compare_run_id: Optional[int] = None
    created_by: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    #: 목록 화면의 진행률. 담은 TC 수와 수행한(NS 아닌) 수. 목록 조회에서만 채우고 그 밖은 0 이다.
    tc_total: int = 0
    tc_executed: int = 0

    @field_validator("round", mode="before")
    @classmethod
    def _round_default(cls, v):
        """비어 있으면 1 라운드로 읽는다.

        ★컬럼은 NOT NULL 이다(SQLite 시절 e5a83f21c760 에서 바꿨고 기준점도 같다).
          SQLite 에서 옮겨 온 옛 행에 NULL 이 섞여 있을 수 있어 읽는 쪽도 견디게 둔다.
          목록 응답 하나가 못 만들어지면 그 프로젝트의 수행 목록 전체가 500 이 된다.
        """
        return 1 if v is None else v

    model_config = ConfigDict(from_attributes=True)


# ── Dashboard ─────────────────────────────────────────────────────────────────
#
# 대시보드 응답 스키마는 두지 않는다. 라우트가 dict 로 "pass" 키를 직접 내는데,
# 예전에 있던 모델들은 `pass_` 로 선언하고 파이썬 `model_dump` 오버라이드로 이름을
# 변경해 내는 구조였다. 아무 데서도 쓰이지 않았지만, 누가 `response_model=` 로 붙이는
# 순간 FastAPI 직렬화가 pydantic-core 를 타서 그 오버라이드를 건너뛴다. 응답 키가
# `pass_` 가 되고 화면의 카드와 도넛이 조용히 빈다. 고치려고 손대면 터지는 모양이라
# 지운다. 스키마를 다시 두려면 필드 이름부터 `pass` 로 낼 수 있는 방법을 정해야 한다.


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


# ── Run Issue ────────────────────────────────────────────────────────────────

def _http_url(v):
    v = (v or "").strip()
    # javascript: 같은 주소가 리포트에서 링크가 되지 않도록 http(s) 만 받는다.
    if not (v.lower().startswith("http://") or v.lower().startswith("https://")):
        raise ValueError("url must start with http:// or https://")
    return v


def _blank_to_none(v):
    if v is None:
        return None
    v = str(v).strip()
    return v or None


def _tc_id_list(v):
    """연관 TC-ID 목록. 공백과 빈 값을 버리고 순서를 지키며 중복을 없앤다.

    화면 입력칸이 쉼표로 이은 문자열을 보내도 받는다.
    """
    if v is None:
        return None
    if isinstance(v, str):
        v = v.split(",")
    return list(dict.fromkeys(s for s in (str(x).strip() for x in v) if s))


ISSUE_VERDICTS = ("resolved", "open", "partial", "unverified")


def _verdict(v):
    """QA 확인 결과. 비우면 NULL, 모르는 값은 422."""
    v = _blank_to_none(v)
    if v is None:
        return None
    v = v.lower()
    if v not in ISSUE_VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(ISSUE_VERDICTS)}")
    return v


class RunIssueCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., max_length=1000)
    issue_key: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)
    note: Optional[str] = None
    #: 연관 TC 의 TC-ID. 이 수행에 담긴 TC 만 받는다. 없어도 된다.
    tc_ids: List[str] = []
    #: 처음 발견한 수행(같은 프로젝트의 다른 수행). 비우면 이번 수행에서 발견한 신규 이슈다.
    origin_run_id: Optional[int] = None
    #: 이번 수행에서 확인한 결과. resolved / open / partial / unverified.
    verdict: Optional[str] = Field(None, max_length=20)

    @field_validator("verdict", mode="before")
    @classmethod
    def _verdict_value(cls, v):
        return _verdict(v)

    @field_validator("tc_ids", mode="before")
    @classmethod
    def _tcs(cls, v):
        return _tc_id_list(v) or []

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v):
        return (v or "").strip()

    @field_validator("url", mode="before")
    @classmethod
    def _url(cls, v):
        return _http_url(v)

    @field_validator("issue_key", "status", "note", mode="before")
    @classmethod
    def _blank(cls, v):
        return _blank_to_none(v)


class RunIssueUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    url: Optional[str] = Field(None, max_length=1000)
    issue_key: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)
    note: Optional[str] = None
    #: 보내면 통째로 변경한다. 빈 목록은 연결을 모두 푼다.
    tc_ids: Optional[List[str]] = None
    #: null 을 보내면 신규 이슈로 돌린다(발견 수행을 비운다).
    origin_run_id: Optional[int] = None
    verdict: Optional[str] = Field(None, max_length=20)

    @field_validator("tc_ids", mode="before")
    @classmethod
    def _tcs(cls, v):
        return [] if v is None else _tc_id_list(v)

    @field_validator("verdict", mode="before")
    @classmethod
    def _verdict_value(cls, v):
        return _verdict(v)

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v):
        return None if v is None else str(v).strip()

    @field_validator("url", mode="before")
    @classmethod
    def _url(cls, v):
        return None if v is None else _http_url(v)

    @field_validator("issue_key", "status", "note", mode="before")
    @classmethod
    def _blank(cls, v):
        # ★None 과 "" 을 구분하지 않는다. 둘 다 "비운다" 다. 안 보낸 필드는
        #   exclude_unset 으로 걸러지므로 여기까지 오지 않는다.
        return _blank_to_none(v)


class RunIssueResponse(BaseModel):
    id: int
    test_run_id: int
    issue_key: Optional[str] = None
    title: str
    url: str
    status: Optional[str] = None
    note: Optional[str] = None
    tc_ids: List[str] = []
    origin_run_id: Optional[int] = None
    origin_round: Optional[int] = None
    verdict: Optional[str] = None
    created_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RunIssueCarryOver(BaseModel):
    """이전 회차 이슈 가져오기. 비우면 리포트의 비교 대상(compare_run_id 또는 같은 이름의 이전 회차)."""
    from_run_id: Optional[int] = None


class RunIssueCarryOverResult(BaseModel):
    from_run_id: int
    from_run_name: str
    from_run_round: int
    #: 새로 넣은 수. 이미 같은 주소가 있던 이슈는 skipped 로 센다.
    added: int
    skipped: int
    issues: List[RunIssueResponse] = []
