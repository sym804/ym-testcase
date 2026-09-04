# 계정 복구 (아이디 찾기 / 비밀번호 재설정) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계정을 잃은 사용자가 관리자 승인을 거쳐 아이디를 찾고 비밀번호를 스스로 재설정할 수 있게 한다.

**Architecture:** 새 테이블 `account_requests` 하나에 요청과 1회용 코드를 함께 담는다. 비로그인 사용자가 요청을 넣으면 `pending` 으로 쌓이고, 관리자가 대상 계정을 확정해 승인하면 아이디 찾기는 바로 `completed` 가 되고 비밀번호 재설정은 12자 코드가 발급된다. 사용자는 그 코드로 새 비밀번호를 직접 정한다. 비밀번호 자체는 관리자 손을 거치지 않는다.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, SQLite, bcrypt, React 18, TypeScript, react-i18next, pytest + requests, Vitest

**Spec:** `docs/superpowers/specs/2026-09-04-account-recovery-design.md`

## Global Constraints

- 심각도 표기는 `Blocker / Critical / Major / Minor / Trivial` 이다. `Block` 을 쓰지 않는다.
- 엠대시(U+2014)와 엔대시(U+2013)를 어떤 산출물에도 쓰지 않는다. 하이픈, 쉼표, 콜론, 괄호로 대체한다.
- 백엔드 포트는 **8008** 이다. 8000 은 다른 프로젝트가 쓴다. 프론트엔드는 **5173**.
- 버전 체계는 `system.feature.fix.patch` (`rules/versioning.md`). 이번 릴리즈 목표는 System 1.3.0.0, Frontend 1.3.0.0, Backend 1.3.0.0, Database 0.7.0.0.
- 관리자 화면의 액션 버튼은 해당 표 **바로 위**에 둔다. 페이지 최상단에 두지 않는다.
- 테스트 중 바꾼 비밀번호와 DB 데이터는 수행 후 원복한다.
- 로그인 실패가 5분에 10회 쌓이면 잠기고 서버 재시작으로만 풀린다. 코드 오입력 테스트는 계정과 IP 키를 나눠 쓴다.
- 새 비밀번호 최소 길이는 8자다 (기존 `PasswordChange` 와 동일).
- 코드 평문은 승인 응답에 딱 한 번만 싣는다. DB 와 로그에는 남기지 않는다.

## File Structure

**Backend**
- Modify: `backend/models.py` - `AccountRequestType`, `AccountRequestStatus` enum 과 `AccountRequest` 모델
- Create: `backend/alembic/versions/<rev>_add_account_requests.py` - 테이블 생성
- Modify: `backend/schemas.py` - 요청/응답 스키마 6개
- Create: `backend/routes/account_requests.py` - 엔드포인트 5개와 전용 rate limit
- Modify: `backend/main.py` - 라우터 등록, `version=`
- Create: `backend/test_account_requests.py` - pytest 통합 테스트

라우터를 `auth.py` 에 넣지 않고 새 파일로 분리한다. `auth.py` 는 이미 260줄이고 로그인, 회원가입, 권한, 관리자 기능이 한 파일에 있다. 계정 복구는 수명주기가 다른 별개 흐름이라 같이 두면 더 읽기 어려워진다.

**Frontend**
- Modify: `frontend/src/api/index.ts` - `accountRequestsApi`
- Create: `frontend/src/pages/AccountHelpPage.tsx` - 요청 접수 (비로그인)
- Create: `frontend/src/pages/ResetPasswordPage.tsx` - 코드로 재설정 (비로그인)
- Create: `frontend/src/components/AccountRequestSection.tsx` - 관리자 화면 섹션
- Modify: `frontend/src/App.tsx` - 라우트 2개
- Modify: `frontend/src/pages/LoginPage.tsx` - 안내 문구를 링크로
- Modify: `frontend/src/pages/AdminPage.tsx` - 섹션 삽입
- Create: `frontend/src/i18n/ko/accountHelp.json`, `frontend/src/i18n/en/accountHelp.json`
- Modify: `frontend/src/i18n/index.ts` - 네임스페이스 등록
- Modify: `frontend/src/i18n/{ko,en}/login.json`, `{ko,en}/admin.json`, `{ko,en}/common.json`
- Modify: `frontend/package.json` - version
- Modify: `frontend/src/test/api-index.test.ts` - API 호출 검증

관리자 섹션을 `AdminPage.tsx` 에 직접 넣지 않고 컴포넌트로 뺀다. `AdminPage.tsx` 는 이미 사용자 표와 프로젝트 배정 표를 들고 있어 섹션을 하나 더 인라인으로 넣으면 커진다.

**문서**
- Modify: `frontend/src/pages/UserManualPage.tsx`, `frontend/src/pages/AdminManualPage.tsx`
- Modify: `rules/versioning.md`, `Release_note.md`
- Modify: `TC_Manager_Full_Regression_Checklist.xlsx`, `Issue_list.xlsx`

---

## Task 1: 데이터 모델과 마이그레이션

**Files:**
- Modify: `backend/models.py`
- Create: `backend/alembic/versions/<rev>_add_account_requests.py`
- Test: `backend/test_account_requests.py`

**Interfaces:**
- Consumes: `Base`, `now_kst` (`backend/models.py`), `User` 모델
- Produces: `AccountRequestType.find_id` / `.reset_password`, `AccountRequestStatus.pending` / `.approved` / `.rejected` / `.completed`, `AccountRequest` 모델 (`__tablename__ = "account_requests"`)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/test_account_requests.py` 를 새로 만든다.

```python
"""계정 복구 (아이디 찾기 / 비밀번호 재설정) 통합 테스트

실행: cd backend && python -m pytest test_account_requests.py -v
"""
import os

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://localhost:8008")


def test_account_request_model_exists():
    from models import AccountRequest, AccountRequestStatus, AccountRequestType

    assert AccountRequest.__tablename__ == "account_requests"
    assert AccountRequestType.find_id.value == "find_id"
    assert AccountRequestType.reset_password.value == "reset_password"
    assert AccountRequestStatus.pending.value == "pending"
    assert AccountRequestStatus.approved.value == "approved"
    assert AccountRequestStatus.rejected.value == "rejected"
    assert AccountRequestStatus.completed.value == "completed"


def test_account_request_columns():
    from models import AccountRequest

    cols = {c.name for c in AccountRequest.__table__.columns}
    assert cols == {
        "id", "request_type", "status",
        "claimed_username", "claimed_display_name", "contact", "note",
        "user_id", "code_hash", "code_expires_at",
        "created_at", "resolved_at", "resolved_by_id",
    }
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && python -m pytest test_account_requests.py -v`
Expected: FAIL. `ImportError: cannot import name 'AccountRequest' from 'models'`

- [ ] **Step 3: 모델을 추가한다**

`backend/models.py` 의 `TestResultValue` enum 바로 아래에 enum 두 개를 넣는다.

```python
class AccountRequestType(str, enum.Enum):
    find_id = "find_id"
    reset_password = "reset_password"


class AccountRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"
```

파일 맨 끝에 모델을 붙인다.

```python
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
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && python -m pytest test_account_requests.py -v`
Expected: PASS 2건

- [ ] **Step 5: 마이그레이션을 만든다**

Run: `cd backend && python -m alembic revision -m "add account_requests"`

생성된 파일의 `upgrade` / `downgrade` 를 아래로 채운다. `down_revision` 이 `'06933fddb519'` 인지 확인한다.

```python
def upgrade() -> None:
    """계정 복구 요청 테이블 추가"""
    op.create_table(
        'account_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_type', sa.Enum('find_id', 'reset_password', name='accountrequesttype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'completed', name='accountrequeststatus'), nullable=False),
        sa.Column('claimed_username', sa.String(length=100), nullable=True),
        sa.Column('claimed_display_name', sa.String(length=100), nullable=True),
        sa.Column('contact', sa.String(length=200), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('code_hash', sa.String(length=255), nullable=True),
        sa.Column('code_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_account_requests_id', 'account_requests', ['id'])
    op.create_index('ix_account_requests_status_created', 'account_requests', ['status', 'created_at'])


def downgrade() -> None:
    """계정 복구 요청 테이블 제거"""
    op.drop_index('ix_account_requests_status_created', table_name='account_requests')
    op.drop_index('ix_account_requests_id', table_name='account_requests')
    op.drop_table('account_requests')
```

- [ ] **Step 6: 마이그레이션이 올라가고 내려가는지 확인한다**

Run: `cd backend && python -m alembic upgrade head && python -m alembic downgrade -1 && python -m alembic upgrade head`
Expected: 세 번 모두 에러 없이 완료. 마지막에 head 로 돌아와 있어야 한다.

- [ ] **Step 7: 커밋**

```bash
git add backend/models.py backend/alembic/versions backend/test_account_requests.py
git commit -m "feat(db): 계정 복구 요청 테이블 추가"
```

---

## Task 2: 스키마와 요청 접수 엔드포인트

**Files:**
- Modify: `backend/schemas.py`
- Create: `backend/routes/account_requests.py`
- Modify: `backend/main.py:126` 부근 (라우터 등록)
- Test: `backend/test_account_requests.py`

**Interfaces:**
- Consumes: Task 1 의 `AccountRequest`, `AccountRequestType`, `AccountRequestStatus`
- Produces: `POST /api/auth/account-requests`. 스키마 `AccountRequestCreate`, `AccountRequestResponse`, `AccountRequestListItem`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/test_account_requests.py` 끝에 붙인다.

```python
def _submit(payload):
    return requests.post(f"{BASE}/api/auth/account-requests", json=payload)


def test_submit_reset_request_for_existing_user():
    r = _submit({
        "request_type": "reset_password",
        "claimed_username": "admin",
        "contact": "사내 메신저 admin",
    })
    assert r.status_code == 201, r.text
    assert r.json() == {"message": "요청이 접수되었습니다. 관리자 확인 후 연락드립니다."}


def test_submit_reset_request_for_missing_user_is_indistinguishable():
    """계정 열거 방지: 없는 아이디로 요청해도 응답이 동일해야 한다."""
    r = _submit({
        "request_type": "reset_password",
        "claimed_username": "__no_such_user__",
        "contact": "사내 메신저 nobody",
    })
    assert r.status_code == 201, r.text
    assert r.json() == {"message": "요청이 접수되었습니다. 관리자 확인 후 연락드립니다."}


def test_submit_find_id_request():
    r = _submit({
        "request_type": "find_id",
        "claimed_display_name": "Admin",
        "contact": "사내 메신저 admin",
    })
    assert r.status_code == 201, r.text


def test_reset_request_without_username_is_rejected():
    r = _submit({"request_type": "reset_password", "contact": "x"})
    assert r.status_code == 422, r.text


def test_find_id_request_without_display_name_is_rejected():
    r = _submit({"request_type": "find_id", "contact": "x"})
    assert r.status_code == 422, r.text
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && python -m pytest test_account_requests.py -v -k submit or reject`
Expected: FAIL. 404 (라우트 없음)

- [ ] **Step 3: 스키마를 추가한다**

`backend/schemas.py` 의 `Token` 클래스 바로 아래에 넣는다.

```python
# ── Account Recovery ──────────────────────────────────────────────────────────

class AccountRequestCreate(BaseModel):
    request_type: str  # find_id | reset_password
    claimed_username: Optional[str] = None
    claimed_display_name: Optional[str] = None
    contact: str = Field(..., min_length=1, max_length=200)
    note: Optional[str] = None


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
```

- [ ] **Step 4: 라우터를 만든다**

`backend/routes/account_requests.py` 를 새로 만든다.

```python
"""계정 복구 (아이디 찾기 / 비밀번호 재설정).

메일 발송 경로가 없어 셀프 서비스가 불가능하므로 관리자 승인 큐로 처리한다.
관리자와 사용자 사이에 오가는 것은 1회용 코드이며 비밀번호 자체는 전달되지 않는다.
"""
import logging
import secrets
import time
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import (
    AccountRequest, AccountRequestStatus, AccountRequestType, User, now_kst,
)
from schemas import (
    AccountRequestAck, AccountRequestApprove, AccountRequestApproveResult,
    AccountRequestCreate, AccountRequestListItem, AccountRequestReject,
    ResetPasswordWithCode,
)
from auth import hash_password, verify_password, role_required

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["account-recovery"])

ACK_MESSAGE = "요청이 접수되었습니다. 관리자 확인 후 연락드립니다."
CODE_TTL_HOURS = 24

# 접수 남용 방어. auth.py 의 _login_failures 는 실패만 세므로 여기에 쓸 수 없다.
_submit_hits: dict[str, list[float]] = defaultdict(list)
SUBMIT_MAX_PER_WINDOW = 10
SUBMIT_WINDOW_SEC = 3600
_MAX_SUBMIT_KEYS = 10000
_last_submit_purge: float = 0.0


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _purge_submit_keys():
    global _last_submit_purge
    now = time.time()
    if now - _last_submit_purge < 60:
        return
    _last_submit_purge = now
    expired = [
        k for k, hits in _submit_hits.items()
        if not hits or now - max(hits) >= SUBMIT_WINDOW_SEC
    ]
    for k in expired:
        del _submit_hits[k]


def _check_submit_limit(request: Request):
    """성공/실패 무관하게 접수 시도를 센다. 1시간 10회."""
    _purge_submit_keys()
    if len(_submit_hits) >= _MAX_SUBMIT_KEYS:
        oldest = min(_submit_hits, key=lambda k: _submit_hits[k][-1] if _submit_hits[k] else 0)
        del _submit_hits[oldest]
    key = _client_ip(request)
    now = time.time()
    _submit_hits[key] = [t for t in _submit_hits[key] if now - t < SUBMIT_WINDOW_SEC]
    if len(_submit_hits[key]) >= SUBMIT_MAX_PER_WINDOW:
        logger.warning("Account request rate limit exceeded: %s", key)
        raise HTTPException(status_code=429, detail="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
    _submit_hits[key].append(now)


@router.post("/account-requests", response_model=AccountRequestAck,
             status_code=status.HTTP_201_CREATED)
def submit_account_request(
    payload: AccountRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _check_submit_limit(request)

    try:
        req_type = AccountRequestType(payload.request_type)
    except ValueError:
        raise HTTPException(status_code=422, detail="요청 종류가 올바르지 않습니다.")

    if req_type is AccountRequestType.reset_password and not payload.claimed_username:
        raise HTTPException(status_code=422, detail="아이디를 입력해 주세요.")
    if req_type is AccountRequestType.find_id and not payload.claimed_display_name:
        raise HTTPException(status_code=422, detail="표시 이름을 입력해 주세요.")

    # 중복 pending 이 있으면 새로 만들지 않는다. 응답은 동일하다.
    q = db.query(AccountRequest).filter(
        AccountRequest.request_type == req_type,
        AccountRequest.status == AccountRequestStatus.pending,
    )
    if req_type is AccountRequestType.reset_password:
        q = q.filter(AccountRequest.claimed_username == payload.claimed_username)
    else:
        q = q.filter(AccountRequest.claimed_display_name == payload.claimed_display_name)

    if q.first() is None:
        db.add(AccountRequest(
            request_type=req_type,
            status=AccountRequestStatus.pending,
            claimed_username=payload.claimed_username,
            claimed_display_name=payload.claimed_display_name,
            contact=payload.contact,
            note=payload.note,
        ))
        db.commit()
        logger.info("Account request submitted: type=%s ip=%s", req_type.value, _client_ip(request))

    return AccountRequestAck(message=ACK_MESSAGE)
```

- [ ] **Step 5: 라우터를 등록한다**

`backend/main.py` 의 import 블록에서 다른 라우터와 같은 자리에 추가하고, `app.include_router(tc_result_history_routes.router)` 다음 줄에 등록한다.

```python
from routes import account_requests as account_request_routes
```

```python
app.include_router(account_request_routes.router)
```

- [ ] **Step 6: 통과를 확인한다**

Run: `cd backend && python -m pytest test_account_requests.py -v`
Expected: PASS 7건

- [ ] **Step 7: 커밋**

```bash
git add backend/schemas.py backend/routes/account_requests.py backend/main.py backend/test_account_requests.py
git commit -m "feat(api): 계정 복구 요청 접수 엔드포인트"
```

---

## Task 3: 관리자 목록, 승인, 반려

**Files:**
- Modify: `backend/routes/account_requests.py`
- Test: `backend/test_account_requests.py`

**Interfaces:**
- Consumes: Task 2 의 `router`, `ACK_MESSAGE`, `CODE_TTL_HOURS`
- Produces: `GET /api/auth/account-requests`, `POST /api/auth/account-requests/{id}/approve`, `POST /api/auth/account-requests/{id}/reject`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/test_account_requests.py` 끝에 붙인다.

```python
def _login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin_headers():
    return _login("admin", os.getenv("TEST_ADMIN_PASSWORD", "test1234"))


@pytest.fixture(scope="module")
def normal_user(admin_headers):
    """일반 사용자 하나를 만들어 둔다. 비밀번호를 바꾸는 테스트의 대상이 된다."""
    requests.post(f"{BASE}/api/auth/register", json={
        "username": "__recover_user__", "password": "origin1234", "display_name": "Recover User",
    })
    r = requests.get(f"{BASE}/api/auth/users", headers=admin_headers)
    uid = next(u["id"] for u in r.json() if u["username"] == "__recover_user__")
    return {"username": "__recover_user__", "id": uid}


def test_list_requires_admin(normal_user):
    h = _login("__recover_user__", "origin1234")
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=h)
    assert r.status_code == 403, r.text


def test_admin_can_list_pending(admin_headers):
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert all("code_hash" not in item for item in body)


def test_approve_find_id_returns_username_and_no_code(admin_headers, normal_user):
    _submit({
        "request_type": "find_id",
        "claimed_display_name": "Recover User",
        "contact": "메신저 recover",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json()
               if x["request_type"] == "find_id" and x["claimed_display_name"] == "Recover User")

    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/approve",
        json={"user_id": normal_user["id"]}, headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "__recover_user__"
    assert body["code"] is None


def test_approve_reset_returns_plaintext_code_once(admin_headers, normal_user):
    _submit({
        "request_type": "reset_password",
        "claimed_username": "__recover_user__",
        "contact": "메신저 recover",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json()
               if x["request_type"] == "reset_password"
               and x["claimed_username"] == "__recover_user__")

    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/approve",
        json={"user_id": normal_user["id"]}, headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] and len(body["code"]) >= 12
    assert body["code_expires_at"]

    # 목록에는 코드가 다시 나오지 않는다
    r2 = requests.get(f"{BASE}/api/auth/account-requests",
                      params={"status": "approved"}, headers=admin_headers)
    item = next(x for x in r2.json() if x["id"] == req["id"])
    assert "code" not in item and "code_hash" not in item


def test_approve_twice_conflicts(admin_headers, normal_user):
    _submit({
        "request_type": "find_id",
        "claimed_display_name": "Dup Target",
        "contact": "메신저 dup",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json() if x["claimed_display_name"] == "Dup Target")
    url = f"{BASE}/api/auth/account-requests/{req['id']}/approve"
    assert requests.post(url, json={"user_id": normal_user["id"]}, headers=admin_headers).status_code == 200
    assert requests.post(url, json={"user_id": normal_user["id"]}, headers=admin_headers).status_code == 409


def test_duplicate_pending_is_not_created(admin_headers):
    """같은 대상으로 두 번 요청해도 큐에는 하나만 쌓인다."""
    target = "__dup_pending__"
    for _ in range(2):
        r = _submit({
            "request_type": "reset_password",
            "claimed_username": target,
            "contact": "메신저 dup-pending",
        })
        assert r.status_code == 201, r.text

    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    same = [x for x in r.json()
            if x["request_type"] == "reset_password" and x["claimed_username"] == target]
    assert len(same) == 1, f"pending 이 {len(same)}건 쌓였다"


def test_approve_requires_admin(normal_user):
    """승인도 관리자 전용이다. 목록만 막고 승인을 열어두면 의미가 없다."""
    _submit({
        "request_type": "find_id",
        "claimed_display_name": "Forbidden Target",
        "contact": "메신저 forbidden",
    })
    h = _login("__recover_user__", "origin1234")
    r = requests.post(
        f"{BASE}/api/auth/account-requests/1/approve",
        json={"user_id": normal_user["id"]}, headers=h,
    )
    assert r.status_code == 403, r.text


def test_code_is_stored_hashed_not_plaintext(admin_headers, normal_user):
    """승인 응답의 평문 코드가 DB 에 그대로 들어가면 안 된다."""
    from database import SessionLocal
    from models import AccountRequest

    _submit({
        "request_type": "reset_password",
        "claimed_username": "__hash_check__",
        "contact": "메신저 hash",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json() if x["claimed_username"] == "__hash_check__")
    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/approve",
        json={"user_id": normal_user["id"]}, headers=admin_headers,
    )
    code = r.json()["code"]

    db = SessionLocal()
    try:
        row = db.query(AccountRequest).filter(AccountRequest.id == req["id"]).first()
        assert row.code_hash, "코드 해시가 비어 있다"
        assert row.code_hash != code, "평문 코드가 그대로 저장되었다"
        assert row.code_hash.startswith("$2"), "bcrypt 해시가 아니다"
    finally:
        db.close()


def test_reject_moves_to_rejected(admin_headers):
    _submit({
        "request_type": "reset_password",
        "claimed_username": "__no_such_user__",
        "contact": "메신저 nobody",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json() if x["claimed_username"] == "__no_such_user__")

    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/reject",
        json={"note": "존재하지 않는 계정"}, headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    r = requests.get(f"{BASE}/api/auth/account-requests",
                     params={"status": "rejected"}, headers=admin_headers)
    item = next(x for x in r.json() if x["id"] == req["id"])
    assert item["status"] == "rejected"
    assert item["note"] == "존재하지 않는 계정"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && python -m pytest test_account_requests.py -v -k "list or approve or reject"`
Expected: FAIL. 404 (라우트 없음)

- [ ] **Step 3: 엔드포인트를 추가한다**

`backend/routes/account_requests.py` 끝에 붙인다.

```python
@router.get("/account-requests", response_model=list[AccountRequestListItem])
def list_account_requests(
    status_filter: str = Query("pending", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    try:
        st = AccountRequestStatus(status_filter)
    except ValueError:
        raise HTTPException(status_code=422, detail="상태 값이 올바르지 않습니다.")

    return (
        db.query(AccountRequest)
        .filter(AccountRequest.status == st)
        .order_by(AccountRequest.created_at.desc())
        .all()
    )


@router.post("/account-requests/{request_id}/approve", response_model=AccountRequestApproveResult)
def approve_account_request(
    request_id: int,
    payload: AccountRequestApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    req = db.query(AccountRequest).filter(AccountRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if req.status is not AccountRequestStatus.pending:
        raise HTTPException(status_code=409, detail="이미 처리된 요청입니다.")

    target = db.query(User).filter(User.id == payload.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="대상 사용자를 찾을 수 없습니다.")

    req.user_id = target.id
    req.resolved_by_id = current_user.id
    req.resolved_at = now_kst()

    if req.request_type is AccountRequestType.find_id:
        req.status = AccountRequestStatus.completed
        db.commit()
        logger.info("Find-id approved: request=%s target=%s by=%s",
                    req.id, target.username, current_user.username)
        return AccountRequestApproveResult(
            request_type=req.request_type.value, username=target.username,
        )

    code = secrets.token_urlsafe(9)
    req.code_hash = hash_password(code)
    req.code_expires_at = now_kst() + timedelta(hours=CODE_TTL_HOURS)
    req.status = AccountRequestStatus.approved
    db.commit()
    logger.info("Reset code issued: request=%s target=%s by=%s",
                req.id, target.username, current_user.username)
    return AccountRequestApproveResult(
        request_type=req.request_type.value,
        code=code,
        code_expires_at=req.code_expires_at,
    )


@router.post("/account-requests/{request_id}/reject", response_model=AccountRequestListItem)
def reject_account_request(
    request_id: int,
    payload: AccountRequestReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    req = db.query(AccountRequest).filter(AccountRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if req.status is not AccountRequestStatus.pending:
        raise HTTPException(status_code=409, detail="이미 처리된 요청입니다.")

    req.status = AccountRequestStatus.rejected
    req.note = payload.note
    req.resolved_by_id = current_user.id
    req.resolved_at = now_kst()
    db.commit()
    db.refresh(req)
    logger.info("Account request rejected: request=%s by=%s", req.id, current_user.username)
    return req
```

파일 상단의 fastapi import 에 `Query` 를 더한다. 쿼리 파라미터는 밖으로 `status` 로
노출되어야 하는데, 파이썬 쪽 이름을 `status` 로 두면 같은 모듈에서 쓰는 `status` 모듈
(`status.HTTP_201_CREATED`)과 부딪히므로 별칭을 쓴다.

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && python -m pytest test_account_requests.py -v`
Expected: PASS 16건

- [ ] **Step 5: 커밋**

```bash
git add backend/routes/account_requests.py backend/test_account_requests.py
git commit -m "feat(api): 계정 복구 요청 목록, 승인, 반려"
```

---

## Task 4: 코드로 비밀번호 재설정

**Files:**
- Modify: `backend/routes/account_requests.py`
- Test: `backend/test_account_requests.py`

**Interfaces:**
- Consumes: Task 3 의 승인 흐름, `auth.py` 의 `_check_rate_limit`, `_record_failure`
- Produces: `POST /api/auth/reset-password/verify`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/test_account_requests.py` 끝에 붙인다. 이 테스트는 비밀번호를 바꾸므로 마지막에 원복한다.

```python
def _issue_code(admin_headers, username, user_id, contact="메신저 code"):
    """대상 계정에 대해 재설정 코드를 발급받는다."""
    _submit({"request_type": "reset_password", "claimed_username": username, "contact": contact})
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json()
               if x["request_type"] == "reset_password" and x["claimed_username"] == username)
    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/approve",
        json={"user_id": user_id}, headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    return req["id"], r.json()["code"]


def test_reset_with_code_changes_password(admin_headers, normal_user):
    _, code = _issue_code(admin_headers, normal_user["username"], normal_user["id"])

    r = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code, "new_password": "changed1234",
    })
    assert r.status_code == 200, r.text

    # 새 비밀번호로 로그인된다
    ok = requests.post(f"{BASE}/api/auth/login", json={
        "username": normal_user["username"], "password": "changed1234",
    })
    assert ok.status_code == 200, ok.text

    # 옛 비밀번호는 실패한다
    ng = requests.post(f"{BASE}/api/auth/login", json={
        "username": normal_user["username"], "password": "origin1234",
    })
    assert ng.status_code == 401

    # 원복: 코드를 새로 발급받아 원래 비밀번호로 되돌린다
    _, code2 = _issue_code(admin_headers, normal_user["username"], normal_user["id"])
    back = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code2, "new_password": "origin1234",
    })
    assert back.status_code == 200, back.text


def test_code_cannot_be_reused(admin_headers, normal_user):
    _, code = _issue_code(admin_headers, normal_user["username"], normal_user["id"])
    first = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code, "new_password": "origin1234",
    })
    assert first.status_code == 200, first.text

    again = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code, "new_password": "origin1234",
    })
    assert again.status_code == 401


def test_expired_code_fails(admin_headers, normal_user):
    """만료 시각을 과거로 돌려 검증한다."""
    from datetime import timedelta

    from database import SessionLocal
    from models import AccountRequest, now_kst

    req_id, code = _issue_code(admin_headers, normal_user["username"], normal_user["id"])

    db = SessionLocal()
    try:
        req = db.query(AccountRequest).filter(AccountRequest.id == req_id).first()
        req.code_expires_at = now_kst() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    r = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code, "new_password": "origin1234",
    })
    assert r.status_code == 401


def test_wrong_code_is_rate_limited(admin_headers):
    """틀린 코드를 반복하면 429. 다른 테스트의 계정과 키가 겹치지 않도록 전용 계정을 쓴다."""
    requests.post(f"{BASE}/api/auth/register", json={
        "username": "__rl_target__", "password": "origin1234", "display_name": "RL Target",
    })
    saw_429 = False
    for _ in range(12):
        r = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
            "username": "__rl_target__", "code": "wrongwrongwrong", "new_password": "origin1234",
        })
        if r.status_code == 429:
            saw_429 = True
            break
        assert r.status_code == 401
    assert saw_429
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && python -m pytest test_account_requests.py -v -k "reset_with_code or reused or expired or rate_limited"`
Expected: FAIL. 404 (라우트 없음)

- [ ] **Step 3: 엔드포인트를 추가한다**

`backend/routes/account_requests.py` 끝에 붙인다. import 에 `from routes.auth import _check_rate_limit, _record_failure` 를 더한다.

```python
@router.post("/reset-password/verify")
def reset_password_with_code(
    payload: ResetPasswordWithCode,
    request: Request,
    db: Session = Depends(get_db),
):
    """코드로 새 비밀번호를 정한다.

    실패는 단계를 구분하지 않고 모두 같은 401 을 낸다. 어디서 틀렸는지 알려주면
    계정 존재 여부와 승인 여부가 새어 나간다.
    """
    _check_rate_limit(request, payload.username)
    fail = HTTPException(status_code=401, detail="코드가 올바르지 않거나 만료되었습니다.")

    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        _record_failure(request, payload.username)
        raise fail

    req = (
        db.query(AccountRequest)
        .filter(
            AccountRequest.user_id == user.id,
            AccountRequest.request_type == AccountRequestType.reset_password,
            AccountRequest.status == AccountRequestStatus.approved,
        )
        .order_by(AccountRequest.created_at.desc())
        .first()
    )
    if not req or not req.code_hash:
        _record_failure(request, payload.username)
        raise fail

    if req.code_expires_at is None or req.code_expires_at < now_kst():
        _record_failure(request, payload.username)
        raise fail

    if not verify_password(payload.code, req.code_hash):
        _record_failure(request, payload.username)
        raise fail

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    req.status = AccountRequestStatus.completed
    req.code_hash = None
    req.resolved_at = now_kst()
    db.commit()
    logger.info("Password reset via code: user=%s request=%s", user.username, req.id)
    return {"message": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요."}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && python -m pytest test_account_requests.py -v`
Expected: PASS 20건

- [ ] **Step 5: 기존 테스트가 깨지지 않았는지 본다**

Run: `cd backend && python -m pytest -v`
Expected: 기존 테스트 전부 통과. rate limit 테스트 때문에 `admin` 로그인이 막히면 서버를 재시작하고 다시 돌린다.

- [ ] **Step 6: 커밋**

```bash
git add backend/routes/account_requests.py backend/test_account_requests.py
git commit -m "feat(api): 1회용 코드로 비밀번호 재설정"
```

---

## Task 5: 프론트엔드 API 클라이언트

**Files:**
- Modify: `frontend/src/api/index.ts`
- Test: `frontend/src/test/api-index.test.ts`

**Interfaces:**
- Consumes: Task 2~4 의 엔드포인트
- Produces: `accountRequestsApi.submit`, `.list`, `.approve`, `.reject`, `.resetWithCode`. 타입 `AccountRequestItem`, `ApproveResult`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/src/test/api-index.test.ts` 의 import 목록에 `accountRequestsApi` 를 더하고, 파일 끝에 붙인다.

```typescript
describe("accountRequestsApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submit 은 POST /api/auth/account-requests 를 호출한다", async () => {
    mockPost.mockResolvedValue({ data: { message: "ok" } });
    await accountRequestsApi.submit({
      request_type: "reset_password",
      claimed_username: "kim",
      contact: "메신저",
    });
    expect(mockPost).toHaveBeenCalledWith("/api/auth/account-requests", {
      request_type: "reset_password",
      claimed_username: "kim",
      contact: "메신저",
    });
  });

  it("list 는 status 파라미터를 실어 GET 한다", async () => {
    mockGet.mockResolvedValue({ data: [] });
    await accountRequestsApi.list("approved");
    expect(mockGet).toHaveBeenCalledWith("/api/auth/account-requests", {
      params: { status: "approved" },
    });
  });

  it("approve 는 user_id 를 실어 POST 한다", async () => {
    mockPost.mockResolvedValue({ data: { request_type: "find_id", username: "kim" } });
    await accountRequestsApi.approve(7, 3);
    expect(mockPost).toHaveBeenCalledWith("/api/auth/account-requests/7/approve", { user_id: 3 });
  });

  it("reject 는 사유를 실어 POST 한다", async () => {
    mockPost.mockResolvedValue({ data: {} });
    await accountRequestsApi.reject(7, "없는 계정");
    expect(mockPost).toHaveBeenCalledWith("/api/auth/account-requests/7/reject", {
      note: "없는 계정",
    });
  });

  it("resetWithCode 는 POST /api/auth/reset-password/verify 를 호출한다", async () => {
    mockPost.mockResolvedValue({ data: { message: "ok" } });
    await accountRequestsApi.resetWithCode("kim", "abc123", "newpass1234");
    expect(mockPost).toHaveBeenCalledWith("/api/auth/reset-password/verify", {
      username: "kim",
      code: "abc123",
      new_password: "newpass1234",
    });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd frontend && npx vitest run src/test/api-index.test.ts`
Expected: FAIL. `accountRequestsApi` 를 export 하지 않음

- [ ] **Step 3: API 를 추가한다**

`frontend/src/api/index.ts` 의 `usersApi` 블록 바로 아래에 넣는다.

```typescript
// ─── Account Recovery ─────────────────────────────────
export interface AccountRequestItem {
  id: number;
  request_type: "find_id" | "reset_password";
  status: "pending" | "approved" | "rejected" | "completed";
  claimed_username: string | null;
  claimed_display_name: string | null;
  contact: string;
  note: string | null;
  user_id: number | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AccountRequestSubmit {
  request_type: "find_id" | "reset_password";
  claimed_username?: string;
  claimed_display_name?: string;
  contact: string;
  note?: string;
}

export interface ApproveResult {
  request_type: "find_id" | "reset_password";
  username: string | null;
  code: string | null;
  code_expires_at: string | null;
}

export const accountRequestsApi = {
  submit: async (data: AccountRequestSubmit) => {
    const res = await client.post<{ message: string }>("/api/auth/account-requests", data);
    return res.data;
  },

  list: async (status: string) => {
    const res = await client.get<AccountRequestItem[]>("/api/auth/account-requests", {
      params: { status },
    });
    return res.data;
  },

  approve: async (requestId: number, userId: number) => {
    const res = await client.post<ApproveResult>(
      `/api/auth/account-requests/${requestId}/approve`,
      { user_id: userId }
    );
    return res.data;
  },

  reject: async (requestId: number, note: string) => {
    const res = await client.post<AccountRequestItem>(
      `/api/auth/account-requests/${requestId}/reject`,
      { note }
    );
    return res.data;
  },

  resetWithCode: async (username: string, code: string, newPassword: string) => {
    const res = await client.post<{ message: string }>("/api/auth/reset-password/verify", {
      username,
      code,
      new_password: newPassword,
    });
    return res.data;
  },
};
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd frontend && npx vitest run src/test/api-index.test.ts`
Expected: PASS

- [ ] **Step 5: 타입 체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/api/index.ts frontend/src/test/api-index.test.ts
git commit -m "feat(fe): 계정 복구 API 클라이언트"
```

---

## Task 6: i18n 문구

**Files:**
- Create: `frontend/src/i18n/ko/accountHelp.json`, `frontend/src/i18n/en/accountHelp.json`
- Modify: `frontend/src/i18n/index.ts`
- Modify: `frontend/src/i18n/{ko,en}/login.json`, `frontend/src/i18n/{ko,en}/admin.json`

**Interfaces:**
- Produces: `accountHelp` 네임스페이스. `login:forgotPasswordLink`, `admin:accountRequests.*`

- [ ] **Step 1: 한국어 문구 파일을 만든다**

`frontend/src/i18n/ko/accountHelp.json`

```json
{
  "title": "계정 도움 요청",
  "tabFindId": "아이디 찾기",
  "tabResetPassword": "비밀번호 재설정",
  "displayName": "표시 이름",
  "displayNamePlaceholder": "가입할 때 쓴 이름",
  "username": "아이디",
  "usernamePlaceholder": "아이디를 입력하세요",
  "contact": "연락 받을 곳",
  "contactPlaceholder": "사내 메신저 ID 또는 내선번호",
  "note": "메모",
  "notePlaceholder": "관리자가 본인 확인에 참고할 내용 (선택)",
  "submit": "요청 보내기",
  "submitting": "보내는 중...",
  "submitted": "요청이 접수되었습니다. 관리자 확인 후 연락드립니다.",
  "emptyFields": "필수 항목을 입력해 주세요.",
  "failed": "요청을 보내지 못했습니다.",
  "backToLogin": "로그인으로 돌아가기",
  "resetTitle": "비밀번호 재설정",
  "resetIntro": "관리자에게 받은 코드를 입력하고 새 비밀번호를 정하세요.",
  "code": "재설정 코드",
  "codePlaceholder": "관리자에게 받은 코드",
  "newPassword": "새 비밀번호",
  "newPasswordPlaceholder": "8자 이상",
  "confirmPassword": "새 비밀번호 확인",
  "passwordMismatch": "새 비밀번호가 서로 다릅니다.",
  "passwordTooShort": "비밀번호는 8자 이상이어야 합니다.",
  "resetSubmit": "비밀번호 변경",
  "resetDone": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.",
  "resetFailed": "코드가 올바르지 않거나 만료되었습니다."
}
```

- [ ] **Step 2: 영어 문구 파일을 만든다**

`frontend/src/i18n/en/accountHelp.json`

```json
{
  "title": "Account Help",
  "tabFindId": "Find ID",
  "tabResetPassword": "Reset Password",
  "displayName": "Display name",
  "displayNamePlaceholder": "The name you signed up with",
  "username": "Username",
  "usernamePlaceholder": "Enter your username",
  "contact": "How to reach you",
  "contactPlaceholder": "Chat ID or extension number",
  "note": "Note",
  "notePlaceholder": "Anything that helps the admin verify you (optional)",
  "submit": "Send request",
  "submitting": "Sending...",
  "submitted": "Your request has been received. An administrator will contact you.",
  "emptyFields": "Please fill in the required fields.",
  "failed": "Could not send the request.",
  "backToLogin": "Back to login",
  "resetTitle": "Reset Password",
  "resetIntro": "Enter the code you received from the administrator and choose a new password.",
  "code": "Reset code",
  "codePlaceholder": "Code from the administrator",
  "newPassword": "New password",
  "newPasswordPlaceholder": "At least 8 characters",
  "confirmPassword": "Confirm new password",
  "passwordMismatch": "The new passwords do not match.",
  "passwordTooShort": "Password must be at least 8 characters.",
  "resetSubmit": "Change password",
  "resetDone": "Your password has been changed. Please sign in with the new password.",
  "resetFailed": "The code is invalid or has expired."
}
```

- [ ] **Step 3: 네임스페이스를 등록한다**

`frontend/src/i18n/index.ts` 에서 `adminManualKo` import 다음 줄에 추가한다.

```typescript
import accountHelpKo from "./ko/accountHelp.json";
```

`adminManualEn` import 다음 줄에 추가한다.

```typescript
import accountHelpEn from "./en/accountHelp.json";
```

`resources.ko` 의 `adminManual: adminManualKo,` 다음 줄과 `resources.en` 의 `adminManual: adminManualEn,` 다음 줄에 각각 추가한다.

```typescript
      accountHelp: accountHelpKo,
```

```typescript
      accountHelp: accountHelpEn,
```

- [ ] **Step 4: 로그인 화면 문구를 바꾼다**

`frontend/src/i18n/ko/login.json` 의 `forgotPassword` 값을 바꾸고 링크 문구를 더한다.

```json
  "forgotPassword": "아이디나 비밀번호를 잊으셨나요?",
  "forgotPasswordLink": "계정 도움 요청"
```

`frontend/src/i18n/en/login.json` 도 같이 바꾼다.

```json
  "forgotPassword": "Forgot your username or password?",
  "forgotPasswordLink": "Get account help"
```

- [ ] **Step 5: 관리자 화면 문구를 더한다**

`frontend/src/i18n/ko/admin.json` 의 최상위에 키를 더한다.

```json
  "accountRequests": {
    "title": "계정 요청",
    "empty": "대기 중인 요청이 없습니다.",
    "refresh": "새로고침",
    "colType": "종류",
    "colClaimed": "요청 내용",
    "colContact": "연락처",
    "colNote": "메모",
    "colCreated": "접수일",
    "colActions": "처리",
    "typeFindId": "아이디 찾기",
    "typeResetPassword": "비밀번호 재설정",
    "selectUser": "대상 계정 선택",
    "approve": "승인",
    "reject": "반려",
    "rejectReason": "반려 사유",
    "codeIssued": "재설정 코드가 발급되었습니다. 지금 복사해서 전달하세요. 다시 볼 수 없습니다.",
    "usernameFound": "대상 아이디입니다. 요청자에게 전달하세요.",
    "copy": "복사",
    "copied": "복사됨",
    "expiresAt": "만료",
    "needUser": "대상 계정을 먼저 선택해 주세요.",
    "failed": "처리에 실패했습니다."
  }
```

`frontend/src/i18n/en/admin.json` 에도 같은 구조로 더한다.

```json
  "accountRequests": {
    "title": "Account Requests",
    "empty": "No pending requests.",
    "refresh": "Refresh",
    "colType": "Type",
    "colClaimed": "Request",
    "colContact": "Contact",
    "colNote": "Note",
    "colCreated": "Submitted",
    "colActions": "Actions",
    "typeFindId": "Find ID",
    "typeResetPassword": "Reset Password",
    "selectUser": "Select target account",
    "approve": "Approve",
    "reject": "Reject",
    "rejectReason": "Reason",
    "codeIssued": "A reset code has been issued. Copy it now and pass it on. You cannot see it again.",
    "usernameFound": "This is the target username. Pass it on to the requester.",
    "copy": "Copy",
    "copied": "Copied",
    "expiresAt": "Expires",
    "needUser": "Select the target account first.",
    "failed": "The action failed."
  }
```

- [ ] **Step 6: 키가 양쪽에 다 있는지 확인한다**

Run:
```bash
cd frontend && node -e "
const ko=require('./src/i18n/ko/accountHelp.json'), en=require('./src/i18n/en/accountHelp.json');
const a=Object.keys(ko).sort().join(','), b=Object.keys(en).sort().join(',');
if(a!==b){console.error('키 불일치'); process.exit(1);}
console.log('accountHelp 키 일치', Object.keys(ko).length);
"
```
Expected: `accountHelp 키 일치 29`

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/i18n
git commit -m "feat(i18n): 계정 복구 문구 추가"
```

---

## Task 7: 요청 접수 페이지

**Files:**
- Create: `frontend/src/pages/AccountHelpPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx:84-87`

**Interfaces:**
- Consumes: Task 5 의 `accountRequestsApi.submit`, Task 6 의 `accountHelp` 네임스페이스
- Produces: 라우트 `/account-help`

- [ ] **Step 1: 페이지를 만든다**

`frontend/src/pages/AccountHelpPage.tsx`

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { accountRequestsApi } from "../api/index";

type Tab = "find_id" | "reset_password";

export default function AccountHelpPage() {
  const { t } = useTranslation("accountHelp");
  const [tab, setTab] = useState<Tab>("find_id");
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [contact, setContact] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const identifier = tab === "find_id" ? displayName : username;
    if (!identifier || !contact) {
      setError(t("emptyFields"));
      return;
    }
    setLoading(true);
    try {
      await accountRequestsApi.submit({
        request_type: tab,
        claimed_display_name: tab === "find_id" ? displayName : undefined,
        claimed_username: tab === "reset_password" ? username : undefined,
        contact,
        note: note || undefined,
      });
      setDone(true);
    } catch {
      setError(t("failed"));
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.card}>
          <h2 style={styles.title}>{t("title")}</h2>
          <p style={styles.doneText}>{t("submitted")}</p>
          <Link to="/login" style={styles.link}>{t("backToLogin")}</Link>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>
        <h2 style={styles.title}>{t("title")}</h2>

        <div style={styles.tabs}>
          <button type="button" onClick={() => setTab("find_id")}
                  style={tab === "find_id" ? styles.tabOn : styles.tab}>
            {t("tabFindId")}
          </button>
          <button type="button" onClick={() => setTab("reset_password")}
                  style={tab === "reset_password" ? styles.tabOn : styles.tab}>
            {t("tabResetPassword")}
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {tab === "find_id" ? (
            <label style={styles.label}>
              {t("displayName")}
              <input style={styles.input} value={displayName}
                     onChange={(e) => setDisplayName(e.target.value)}
                     placeholder={t("displayNamePlaceholder")} />
            </label>
          ) : (
            <label style={styles.label}>
              {t("username")}
              <input style={styles.input} value={username}
                     onChange={(e) => setUsername(e.target.value)}
                     placeholder={t("usernamePlaceholder")} />
            </label>
          )}

          <label style={styles.label}>
            {t("contact")}
            <input style={styles.input} value={contact}
                   onChange={(e) => setContact(e.target.value)}
                   placeholder={t("contactPlaceholder")} />
          </label>

          <label style={styles.label}>
            {t("note")}
            <textarea style={{ ...styles.input, height: 72 }} value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder={t("notePlaceholder")} />
          </label>

          {error && <div style={styles.error}>{error}</div>}

          <button type="submit" disabled={loading} style={styles.submit}>
            {loading ? t("submitting") : t("submit")}
          </button>
        </form>

        <div style={styles.footer}>
          <Link to="/login" style={styles.link}>{t("backToLogin")}</Link>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    minHeight: "100vh", backgroundColor: "var(--bg-page)",
    display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
  },
  card: {
    width: "100%", maxWidth: 420, backgroundColor: "var(--bg-card, #fff)",
    borderRadius: 10, padding: 28, border: "1px solid var(--border-color, #E2E8F0)",
  },
  title: { margin: "0 0 20px", fontSize: 20 },
  tabs: { display: "flex", gap: 8, marginBottom: 20 },
  tab: {
    flex: 1, padding: "8px 0", cursor: "pointer", fontSize: 13,
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 6,
    backgroundColor: "transparent", color: "var(--text-secondary, #64748B)",
  },
  tabOn: {
    flex: 1, padding: "8px 0", cursor: "pointer", fontSize: 13, fontWeight: 600,
    border: "1px solid var(--accent, #2563EB)", borderRadius: 6,
    backgroundColor: "var(--accent, #2563EB)", color: "#fff",
  },
  label: { display: "block", fontSize: 13, marginBottom: 14 },
  input: {
    width: "100%", marginTop: 6, padding: "9px 10px", fontSize: 13, boxSizing: "border-box",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 6,
  },
  error: { color: "var(--danger, #DC2626)", fontSize: 12, marginBottom: 12 },
  submit: {
    width: "100%", padding: "10px 0", fontSize: 14, cursor: "pointer",
    border: "none", borderRadius: 6, backgroundColor: "var(--accent, #2563EB)", color: "#fff",
  },
  doneText: { fontSize: 13, lineHeight: 1.6, marginBottom: 20 },
  footer: { marginTop: 18, textAlign: "center", fontSize: 12 },
  link: { color: "var(--accent, #2563EB)", textDecoration: "none" },
};
```

- [ ] **Step 2: 라우트를 등록한다**

`frontend/src/App.tsx` 의 import 에 추가한다.

```tsx
import AccountHelpPage from "./pages/AccountHelpPage";
```

`<Route path="/register" element={<RegisterPage />} />` 다음 줄에 추가한다.

```tsx
      <Route path="/account-help" element={<AccountHelpPage />} />
```

- [ ] **Step 3: 로그인 화면의 안내를 링크로 바꾼다**

`frontend/src/pages/LoginPage.tsx` 의 `styles.hint` 블록을 바꾼다.

```tsx
          <div style={styles.hint}>
            {t("forgotPassword")}{" "}
            <Link to="/account-help" style={styles.link}>
              {t("forgotPasswordLink")}
            </Link>
          </div>
```

- [ ] **Step 4: 타입 체크와 빌드**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 에러 없음

- [ ] **Step 5: 화면을 눈으로 확인한다**

백엔드를 8008, 프론트엔드를 5173 으로 띄우고 `http://localhost:5173/account-help` 를 연다.

확인 항목:
- 탭을 바꾸면 입력란이 표시 이름과 아이디로 바뀐다
- 필수 항목을 비우고 제출하면 경고가 뜬다
- 제출하면 접수 안내가 뜬다
- 없는 아이디로 제출해도 같은 안내가 뜬다

스크린샷을 남긴다. Task 10 의 매뉴얼에 쓴다.

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/pages/AccountHelpPage.tsx frontend/src/App.tsx frontend/src/pages/LoginPage.tsx
git commit -m "feat(fe): 계정 도움 요청 페이지"
```

---

## Task 8: 코드 입력 재설정 페이지

**Files:**
- Create: `frontend/src/pages/ResetPasswordPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: Task 5 의 `accountRequestsApi.resetWithCode`, Task 6 의 문구
- Produces: 라우트 `/reset-password`

- [ ] **Step 1: 페이지를 만든다**

`frontend/src/pages/ResetPasswordPage.tsx`

```tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PasswordInput from "../components/PasswordInput";
import { accountRequestsApi } from "../api/index";

export default function ResetPasswordPage() {
  const { t } = useTranslation("accountHelp");
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!username || !code || !password) {
      setError(t("emptyFields"));
      return;
    }
    if (password.length < 8) {
      setError(t("passwordTooShort"));
      return;
    }
    if (password !== confirm) {
      setError(t("passwordMismatch"));
      return;
    }
    setLoading(true);
    try {
      await accountRequestsApi.resetWithCode(username, code, password);
      setDone(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch {
      setError(t("resetFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>
        <h2 style={styles.title}>{t("resetTitle")}</h2>
        {done ? (
          <>
            <p style={styles.doneText}>{t("resetDone")}</p>
            <Link to="/login" style={styles.link}>{t("backToLogin")}</Link>
          </>
        ) : (
          <>
            <p style={styles.intro}>{t("resetIntro")}</p>
            <form onSubmit={handleSubmit}>
              <label style={styles.label}>
                {t("username")}
                <input style={styles.input} value={username}
                       onChange={(e) => setUsername(e.target.value)}
                       placeholder={t("usernamePlaceholder")} />
              </label>
              <label style={styles.label}>
                {t("code")}
                <input style={styles.input} value={code}
                       onChange={(e) => setCode(e.target.value)}
                       placeholder={t("codePlaceholder")} />
              </label>
              <label style={styles.label}>
                {t("newPassword")}
                <PasswordInput style={styles.input} value={password}
                               onChange={(e) => setPassword(e.target.value)}
                               placeholder={t("newPasswordPlaceholder")} />
              </label>
              <label style={styles.label}>
                {t("confirmPassword")}
                <PasswordInput style={styles.input} value={confirm}
                               onChange={(e) => setConfirm(e.target.value)}
                               placeholder={t("newPasswordPlaceholder")} />
              </label>

              {error && <div style={styles.error}>{error}</div>}

              <button type="submit" disabled={loading} style={styles.submit}>
                {loading ? t("submitting") : t("resetSubmit")}
              </button>
            </form>
            <div style={styles.footer}>
              <Link to="/login" style={styles.link}>{t("backToLogin")}</Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    minHeight: "100vh", backgroundColor: "var(--bg-page)",
    display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
  },
  card: {
    width: "100%", maxWidth: 420, backgroundColor: "var(--bg-card, #fff)",
    borderRadius: 10, padding: 28, border: "1px solid var(--border-color, #E2E8F0)",
  },
  title: { margin: "0 0 12px", fontSize: 20 },
  intro: { fontSize: 13, lineHeight: 1.6, marginBottom: 20, color: "var(--text-secondary, #64748B)" },
  label: { display: "block", fontSize: 13, marginBottom: 14 },
  input: {
    width: "100%", marginTop: 6, padding: "9px 10px", fontSize: 13, boxSizing: "border-box",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 6,
  },
  error: { color: "var(--danger, #DC2626)", fontSize: 12, marginBottom: 12 },
  submit: {
    width: "100%", padding: "10px 0", fontSize: 14, cursor: "pointer",
    border: "none", borderRadius: 6, backgroundColor: "var(--accent, #2563EB)", color: "#fff",
  },
  doneText: { fontSize: 13, lineHeight: 1.6, marginBottom: 20 },
  footer: { marginTop: 18, textAlign: "center", fontSize: 12 },
  link: { color: "var(--accent, #2563EB)", textDecoration: "none" },
};
```

`PasswordInput` 은 `React.InputHTMLAttributes<HTMLInputElement>` 를 그대로 받는다.
따라서 `onChange` 는 문자열 콜백이 아니라 이벤트 핸들러이며 `style` 도 그대로 넘어간다.
`marginTop: 6` 때문에 라벨 아래 간격이 다른 입력란과 맞는다.

- [ ] **Step 2: 라우트를 등록한다**

`frontend/src/App.tsx` 의 import 에 추가한다.

```tsx
import ResetPasswordPage from "./pages/ResetPasswordPage";
```

`/account-help` 라우트 다음 줄에 추가한다.

```tsx
      <Route path="/reset-password" element={<ResetPasswordPage />} />
```

- [ ] **Step 3: 타입 체크와 빌드**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/pages/ResetPasswordPage.tsx frontend/src/App.tsx
git commit -m "feat(fe): 코드 입력 비밀번호 재설정 페이지"
```

---

## Task 9: 관리자 계정 요청 섹션

**Files:**
- Create: `frontend/src/components/AccountRequestSection.tsx`
- Modify: `frontend/src/pages/AdminPage.tsx`

**Interfaces:**
- Consumes: Task 5 의 `accountRequestsApi.list` / `.approve` / `.reject`, `usersApi.list`, Task 6 의 `admin:accountRequests.*`
- Produces: `<AccountRequestSection />`

- [ ] **Step 1: 컴포넌트를 만든다**

`frontend/src/components/AccountRequestSection.tsx`

```tsx
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { accountRequestsApi, usersApi, type AccountRequestItem } from "../api/index";
import type { User } from "../types";

export default function AccountRequestSection() {
  const { t } = useTranslation("admin");
  const [items, setItems] = useState<AccountRequestItem[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [result, setResult] = useState<{ id: number; text: string; note: string } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [reqs, us] = await Promise.all([
        accountRequestsApi.list("pending"),
        usersApi.list(),
      ]);
      setItems(reqs);
      setUsers(us);
    } catch {
      setError(t("accountRequests.failed"));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const approve = async (item: AccountRequestItem) => {
    const userId = picked[item.id];
    if (!userId) {
      setError(t("accountRequests.needUser"));
      return;
    }
    setError("");
    try {
      const res = await accountRequestsApi.approve(item.id, userId);
      if (res.request_type === "find_id") {
        setResult({
          id: item.id,
          text: res.username ?? "",
          note: t("accountRequests.usernameFound"),
        });
      } else {
        const until = res.code_expires_at
          ? ` (${t("accountRequests.expiresAt")}: ${new Date(res.code_expires_at).toLocaleString()})`
          : "";
        setResult({
          id: item.id,
          text: res.code ?? "",
          note: t("accountRequests.codeIssued") + until,
        });
      }
      await load();
    } catch {
      setError(t("accountRequests.failed"));
    }
  };

  const reject = async (item: AccountRequestItem) => {
    const reason = window.prompt(t("accountRequests.rejectReason")) ?? "";
    setError("");
    try {
      await accountRequestsApi.reject(item.id, reason);
      await load();
    } catch {
      setError(t("accountRequests.failed"));
    }
  };

  const label = (item: AccountRequestItem) =>
    item.request_type === "find_id"
      ? t("accountRequests.typeFindId")
      : t("accountRequests.typeResetPassword");

  const claimed = (item: AccountRequestItem) =>
    item.claimed_username ?? item.claimed_display_name ?? "";

  return (
    <section style={s.section}>
      <h3 style={s.title}>{t("accountRequests.title")}</h3>

      {result && (
        <div style={s.result}>
          <div style={s.resultNote}>{result.note}</div>
          <div style={s.resultRow}>
            <code style={s.code}>{result.text}</code>
            <button style={s.copyBtn}
                    onClick={() => void navigator.clipboard.writeText(result.text)}>
              {t("accountRequests.copy")}
            </button>
          </div>
        </div>
      )}

      {error && <div style={s.error}>{error}</div>}

      <div style={s.actions}>
        <button style={s.refreshBtn} onClick={() => void load()}>
          {t("accountRequests.refresh")}
        </button>
      </div>

      {items.length === 0 ? (
        <p style={s.empty}>{t("accountRequests.empty")}</p>
      ) : (
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>{t("accountRequests.colType")}</th>
              <th style={s.th}>{t("accountRequests.colClaimed")}</th>
              <th style={s.th}>{t("accountRequests.colContact")}</th>
              <th style={s.th}>{t("accountRequests.colNote")}</th>
              <th style={s.th}>{t("accountRequests.colCreated")}</th>
              <th style={s.th}>{t("accountRequests.colActions")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td style={s.td}>{label(item)}</td>
                <td style={s.td}>{claimed(item)}</td>
                <td style={s.td}>{item.contact}</td>
                <td style={s.td}>{item.note ?? ""}</td>
                <td style={s.td}>{new Date(item.created_at).toLocaleDateString()}</td>
                <td style={s.td}>
                  <select
                    style={s.select}
                    value={picked[item.id] ?? ""}
                    onChange={(e) =>
                      setPicked((p) => ({ ...p, [item.id]: Number(e.target.value) }))
                    }
                  >
                    <option value="">{t("accountRequests.selectUser")}</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.username} ({u.display_name})
                      </option>
                    ))}
                  </select>
                  <button style={s.approveBtn} onClick={() => void approve(item)}>
                    {t("accountRequests.approve")}
                  </button>
                  <button style={s.rejectBtn} onClick={() => void reject(item)}>
                    {t("accountRequests.reject")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

const s: Record<string, React.CSSProperties> = {
  section: { marginTop: 32 },
  title: { fontSize: 16, margin: "0 0 12px" },
  actions: { marginBottom: 8 },
  refreshBtn: {
    padding: "6px 12px", fontSize: 12, cursor: "pointer",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 6,
    backgroundColor: "transparent",
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: {
    textAlign: "left", padding: "8px 10px", fontWeight: 600,
    borderBottom: "1px solid var(--border-color, #E2E8F0)",
  },
  td: {
    padding: "8px 10px", verticalAlign: "top",
    borderBottom: "1px solid var(--border-color, #E2E8F0)",
  },
  select: { marginRight: 6, fontSize: 12, padding: "4px 6px" },
  approveBtn: {
    marginRight: 4, padding: "4px 10px", fontSize: 12, cursor: "pointer",
    border: "none", borderRadius: 4, backgroundColor: "var(--accent, #2563EB)", color: "#fff",
  },
  rejectBtn: {
    padding: "4px 10px", fontSize: 12, cursor: "pointer",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 4,
    backgroundColor: "transparent",
  },
  empty: { fontSize: 13, color: "var(--text-secondary, #64748B)" },
  error: { color: "var(--danger, #DC2626)", fontSize: 12, marginBottom: 8 },
  result: {
    padding: 12, marginBottom: 12, borderRadius: 6,
    border: "1px solid var(--accent, #2563EB)",
  },
  resultNote: { fontSize: 12, marginBottom: 8 },
  resultRow: { display: "flex", alignItems: "center", gap: 8 },
  code: { fontSize: 14, fontFamily: "monospace", letterSpacing: 1 },
  copyBtn: {
    padding: "4px 10px", fontSize: 12, cursor: "pointer",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 4,
    backgroundColor: "transparent",
  },
};
```

`User` 타입은 `frontend/src/types` 에 있다. `AdminPage.tsx:5` 가 같은 곳에서 가져온다.

액션 버튼(새로고침)은 프로젝트 규칙대로 표 바로 위에 둔다. 승인과 반려 버튼은 각 행 안에 있다.

- [ ] **Step 2: AdminPage 에 넣는다**

`frontend/src/pages/AdminPage.tsx` 의 import 에 추가한다.

```tsx
import AccountRequestSection from "../components/AccountRequestSection";
```

기존 마지막 섹션이 끝나는 자리, 즉 페이지 컨테이너의 닫는 태그 바로 앞에 넣는다.

```tsx
        <AccountRequestSection />
```

- [ ] **Step 3: 타입 체크와 빌드**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 에러 없음

- [ ] **Step 4: 전체 흐름을 눈으로 확인한다**

백엔드 8008, 프론트엔드 5173 을 띄운다.

1. 로그아웃 상태로 `/account-help` 에서 비밀번호 재설정을 요청한다
2. 관리자로 로그인해 `/admin` 의 계정 요청 섹션에 요청이 보이는지 본다
3. 대상 계정을 고르고 승인한다. 코드가 뜨고 복사 버튼이 동작하는지 본다
4. 로그아웃하고 `/reset-password` 에서 그 코드로 새 비밀번호를 정한다
5. 새 비밀번호로 로그인된다
6. 같은 코드를 다시 쓰면 실패한다
7. 아이디 찾기 요청을 넣고 승인하면 아이디가 표시된다

확인 후 테스트에 쓴 계정의 비밀번호를 원복한다.

스크린샷을 남긴다. Task 10 의 매뉴얼에 쓴다.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/components/AccountRequestSection.tsx frontend/src/pages/AdminPage.tsx
git commit -m "feat(fe): 관리자 계정 요청 처리 섹션"
```

---

## Task 10: 매뉴얼, 회귀 TC, 버전, 릴리즈 기록

**Files:**
- Modify: `frontend/src/pages/UserManualPage.tsx`
- Modify: `frontend/src/pages/AdminManualPage.tsx`
- Modify: `frontend/package.json:4`
- Modify: `backend/main.py:63`
- Modify: `frontend/src/i18n/ko/common.json:31`, `frontend/src/i18n/en/common.json:31`
- Modify: `rules/versioning.md`
- Modify: `Release_note.md`
- Modify: `TC_Manager_Full_Regression_Checklist.xlsx`
- Modify: `Issue_list.xlsx`

**Interfaces:**
- Consumes: Task 1~9 의 완성된 기능

- [ ] **Step 1: 사용자 매뉴얼에 절을 넣는다**

`frontend/src/pages/UserManualPage.tsx` 에서 로그인 관련 절을 찾아 그 뒤에 계정 복구 절을 넣는다. 기존 절의 마크업 패턴을 그대로 따른다. 내용은 다음을 담는다.

- 아이디를 잊었을 때: 로그인 화면의 '계정 도움 요청' 링크에서 표시 이름과 연락처를 적어 요청하면 관리자가 확인 후 아이디를 알려준다
- 비밀번호를 잊었을 때: 같은 화면에서 아이디와 연락처를 적어 요청하면 관리자가 재설정 코드를 준다. 그 코드를 `/reset-password` 에 넣고 새 비밀번호를 직접 정한다
- 코드는 24시간 안에 한 번만 쓸 수 있다
- Task 7 과 Task 9 에서 남긴 스크린샷을 넣는다

- [ ] **Step 2: 관리자 매뉴얼에 절을 넣는다**

`frontend/src/pages/AdminManualPage.tsx` 의 API 목록 표(`:353` 부근에 `PUT /api/auth/users/{user_id}/reset-password` 가 있는 그 표)에 다섯 줄을 더한다.

```tsx
                ["POST", "/api/auth/account-requests", t("apiRef.auth.submitAccountRequest")],
                ["GET", "/api/auth/account-requests", t("apiRef.auth.listAccountRequests")],
                ["POST", "/api/auth/account-requests/{id}/approve", t("apiRef.auth.approveAccountRequest")],
                ["POST", "/api/auth/account-requests/{id}/reject", t("apiRef.auth.rejectAccountRequest")],
                ["POST", "/api/auth/reset-password/verify", t("apiRef.auth.resetPasswordWithCode")],
```

`frontend/src/i18n/{ko,en}/adminManual.json` 의 `apiRef.auth` 아래에 대응 키 5개를 더한다. 한국어 값은 각각 "계정 복구 요청 접수", "계정 복구 요청 목록", "계정 복구 요청 승인", "계정 복구 요청 반려", "코드로 비밀번호 재설정" 이다. 영어는 "Submit account recovery request", "List account recovery requests", "Approve account recovery request", "Reject account recovery request", "Reset password with code" 이다.

승인 절차 설명도 함께 넣는다. 요청자에게 본인 확인을 한 뒤 대상 계정을 고르고 승인하며, 코드는 다시 볼 수 없으므로 그 자리에서 복사해 전달해야 한다는 점을 명시한다.

- [ ] **Step 3: 버전을 올린다**

`frontend/package.json` 의 `"version": "1.2.2.0"` 을 `"1.3.0.0"` 으로 바꾼다.

`backend/main.py` 의 `version="1.2.3.0",` 을 `version="1.3.0.0",` 으로 바꾼다.

`frontend/src/i18n/ko/common.json` 과 `en/common.json` 의 `"version"` 값을 `"YM TestCase v1.3.0.0 | AGPL-3.0"` 으로 바꾼다. 지금 v1.0.0.0 에 멈춰 있어 화면 하단에 실제와 다른 버전이 보이던 것을 같이 고치는 것이다.

- [ ] **Step 4: 버전 이력 표에 줄을 더한다**

`rules/versioning.md` 의 '현재 버전 이력' 표 마지막에 추가한다.

```
| **v1.3.0.0** | **1.3.0.0** | **1.3.0.0** | **1.3.0.0** | **0.7.0.0** | **계정 복구 (아이디 찾기, 코드 기반 비밀번호 재설정)** |
```

- [ ] **Step 5: 릴리즈 노트를 쓴다**

`Release_note.md` 의 `## v1.2.3.0` 바로 위에 새 섹션을 넣는다. 기존 섹션의 형식을 그대로 따른다.

```markdown
## v1.3.0.0 (2026-09-04) - 계정 복구 (아이디 찾기, 비밀번호 재설정)

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.2.3.0 | **1.3.0.0** | feature +1 |
| Frontend | 1.2.2.0 | **1.3.0.0** | feature +1 |
| Backend | 1.2.3.0 | **1.3.0.0** | feature +1 |
| Database | 0.6.0.0 | **0.7.0.0** | feature +1 |

### 배경

여러 사람이 쓰기 시작하면서 계정을 잃은 사용자를 되돌릴 경로가 필요해졌다.
아이디 찾기는 아예 없었고 비밀번호는 관리자만 초기화할 수 있었다.
User 모델에 연락 수단이 없고 SMTP 설정도 없어 메일 기반 셀프 서비스는 불가능했다.

### 변경

- 계정 복구 요청 큐 신설. 아이디 찾기와 비밀번호 재설정을 같은 큐에서 관리한다
- 관리자가 대상 계정을 확정해 승인한다. 아이디 찾기는 아이디를 돌려주고,
  비밀번호 재설정은 24시간 유효한 1회용 코드를 발급한다
- 사용자가 그 코드로 새 비밀번호를 직접 정한다. 비밀번호는 관리자 손을 거치지 않는다
- 로그인 화면의 안내 문구를 '계정 도움 요청' 링크로 바꿨다
- 화면 하단 버전 표기가 v1.0.0.0 에 멈춰 있던 것을 실제 버전으로 맞췄다

### 보안

- 계정 열거 방지: 없는 아이디로 요청해도 응답이 동일하다
- 코드는 해시로만 저장하고 평문은 승인 응답 1회로 끝난다
- 코드는 한 번 쓰면 죽는다. 사용 즉시 code_hash 를 지운다
- 코드 대입은 기존 로그인 rate limit(5분 10회)으로, 요청 접수는 IP 기준 1시간 10회로 막는다

### 테스트

backend/test_account_requests.py 20건 신규. 기존 테스트 회귀 확인.
```

- [ ] **Step 6: 회귀 체크리스트에 TC 를 넣는다**

`TC_Manager_Full_Regression_Checklist.xlsx` 의 '체크리스트' 시트에 행을 추가한다. 컬럼은 `No`, `TC ID`, `대분류`, `Depth 1`, `Depth 2`, `Depth 3` 순이며 기존 마지막 행 다음부터 채운다. TC ID 는 `rules/tc_writing_guide.md` 의 `TC-[모듈약어]-[번호]` 형식을 따라 `TC-AUTH-` 대역에서 기존 마지막 번호 다음부터 쓴다.

추가할 TC 는 다음 8건이다.

1. 아이디 찾기 요청 접수 성공
2. 비밀번호 재설정 요청 접수 성공
3. 없는 아이디로 요청해도 같은 안내가 표시됨 (계정 열거 방지)
4. 같은 대상으로 중복 요청 시 큐에 하나만 쌓임
5. 관리자 승인 시 아이디 찾기는 아이디, 비밀번호 재설정은 코드 표시
6. 발급된 코드로 비밀번호 재설정 후 새 비밀번호 로그인 성공
7. 같은 코드 재사용 시 실패
8. 비관리자가 계정 요청 목록 접근 시 차단

openpyxl 로 append 한다. 기존 행의 서식을 참고해 맞춘다.

- [ ] **Step 7: 이슈 로그와 GitHub 이슈를 남긴다**

`Issue_list.xlsx` 에 enhancement 한 건을 추가한다. 심각도는 Major 다. 신규 기능 추가이며 인증 흐름이 걸린다. 발생 버전은 BE 1.2.3.0, 수정 버전은 BE 1.3.0.0 이다.

GitHub 이슈도 같이 만든다.

```bash
gh issue create -R sym804/ym-testcase --label "enhancement,major,backend" \
  --title "계정 복구 (아이디 찾기 / 비밀번호 재설정) 추가"
```

본문은 `rules/issue_management.md` 의 개선 템플릿을 따른다. 등록 후 close 한다.

- [ ] **Step 8: 전체 검증**

Run:
```bash
cd backend && python -m pytest -v
cd ../frontend && npx tsc --noEmit && npx vitest run && npm run build
```
Expected: 전부 통과

- [ ] **Step 9: 커밋**

```bash
git add frontend/src/pages/UserManualPage.tsx frontend/src/pages/AdminManualPage.tsx \
  frontend/src/i18n frontend/package.json backend/main.py \
  rules/versioning.md Release_note.md \
  TC_Manager_Full_Regression_Checklist.xlsx Issue_list.xlsx
git commit -m "docs: v1.3.0.0 매뉴얼, 회귀 TC, 버전, 릴리즈 노트"
```

---

## Task 11: QA 2인 교차 검증

**Files:** 없음 (검증 전용)

**Interfaces:**
- Consumes: Task 1~10 의 전체 변경

- [ ] **Step 1: QA 2인을 한 메시지에서 동시에 디스패치한다**

전역 CLAUDE.md 의 QA 2인 체제를 따른다. 런타임 동작이 바뀌었으므로 생략할 수 없다.

QA1 은 Codex 읽기 전용이다. 프롬프트는 파일로 만들어 stdin 으로 파이프한다. 인자로 넘기면 매달린다.

```bash
cat prompt.txt | codex exec -s read-only
```

프롬프트에 실행 금지 항목을 이름으로 명시한다. `pytest`, `alembic upgrade`, `alembic downgrade`, `npm run build`, `gh issue`, `pnpm install` 을 실행하지 말라고 적는다. 특히 alembic downgrade 는 방금 만든 테이블을 지운다.

QA2 는 자체 리뷰 에이전트다. 이 프로젝트의 과거 사고와 규칙을 아는 시각으로 본다. 프롬프트에 다음을 넣는다.

- `rules/` 11개 규칙 위반 여부, 특히 versioning 과 issue_management
- 계정 열거 방지가 모든 경로에서 실제로 성립하는가
- 새로 쓴 테스트가 진짜 결함을 잡는가, 구현을 베낀 동어반복인가
- rate limit 이 테스트 사이에 서로 간섭하지 않는가

- [ ] **Step 2: 두 보고를 대조한다**

둘 다 지적한 것은 우선순위 최상이다. 한쪽만 지적한 것은 반드시 재현한 뒤 수용 여부를 정한다. 판정이 갈리면 데이터로 결론낸다.

- [ ] **Step 3: 화면을 눈으로 본다**

두 QA 모두 화면을 못 본다. Task 7 과 Task 9 에서 남긴 스크린샷을 다시 확인한다. 특히 코드 표시 영역이 다크 모드에서도 읽히는지 본다.

- [ ] **Step 4: 지적 사항을 반영하고 다시 테스트한다**

Run:
```bash
cd backend && python -m pytest -v
cd ../frontend && npx tsc --noEmit && npx vitest run && npm run build
```

- [ ] **Step 5: 푸시하고 CI 를 확인한다**

```bash
git push origin main
gh run list -R sym804/ym-testcase --limit 3
```

CI 가 완료될 때까지 기다렸다가 결론을 낸다. 실패하면 내 커밋이 깨뜨린 것인지 원래 깨져 있었는지 headSha 로 구분한다.
