# 조직 계정 인증 백엔드 Implementation Plan (계획 4a)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 환경변수로 가입 정책을 고르는 이메일 가입, 계정 상태(사용/대기/중지), 관리자 계정 관리, Google 로그인(서버 측 인가 코드 흐름)을 백엔드에 넣는다.

**Architecture:** 설정 읽기(`services/auth_config.py`)와 판정(`services/account_policy.py`)은 순수 함수로 두고, 계정을 바꾸는 모든 경로는 `services/accounts.py` 의 전역 advisory 잠금(`LockNs.ACCOUNTS`) 안에서 사용자 수와 활성 관리자 수를 센다. Google 연동은 `services/google_oauth.py`(URL, 서명 쿠키, 토큰 교환과 검증)와 `routes/google_auth.py`(시작, 콜백, 해제)로 나누고, 테스트는 `google_oauth.exchange_and_verify` 하나만 가짜로 바꾼다.

**Tech Stack:** FastAPI 0.135, SQLAlchemy 2.0, Alembic, PostgreSQL 17, python-jose(서명 쿠키), google-auth 2.61.0 + requests 2.34.2(ID 토큰 검증), pytest

**Spec:** `docs/superpowers/specs/2026-10-09-org-account-auth-design.md`

## Global Constraints

- 작업 위치: 워크트리 `C:\Users\ymseo\Documents\tc_manager-pg`, 브랜치 `feat/auth`. 원본 폴더 `tc_manager`(사용자 실사용)는 건드리지 않는다.
- 커밋은 태스크마다 로컬에만 한다. **푸시는 계획 4a 끝의 QA 2인 대조 뒤에** 한다(지난 계획에서 QA 전 푸시를 지적받았다).
- 테스트는 실 DB 를 건드리지 않는다. 새 테스트는 전부 `backend/tests_unit` 안에서 `pg_engine` + 앱 직접 기동으로 돈다. 실사용 서버(8008)가 떠 있으면 서버 테스트(`backend/test_*.py`)는 `TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018` 로 돌린다.
- 전체 백엔드 테스트: `cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 TEST_ADMIN_PASSWORD=test1234 python -m pytest -q -k "not test_dompurify_installed"`
- 엠대시(U+2014), 엔대시(U+2013) 금지. 코드 주석은 주변처럼 한국어 `★` 주석 관행을 따른다.
- 의존성 고정: `google-auth==2.61.0`, `requests==2.34.2` 를 `backend/requirements.txt` 에 넣는다.
- 오류 문구(사용자에게 보이는 detail)는 아래 표의 글자 그대로 쓴다. 계획 4b 의 i18n 이 이 문구로 대조한다.
  - 승인 대기 로그인: `관리자 승인을 기다리는 중입니다.`
  - 중지 계정 로그인: `사용이 중지된 계정입니다.`
  - 사용자가 있는데 이메일 없이 가입: `이메일로 가입해 주세요.`
  - 이메일 중복: `이미 가입된 이메일입니다.`
  - 회사 이메일만: `회사 이메일로만 가입할 수 있습니다.`
  - 가입 횟수 제한: `가입 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.`
  - 첫 관리자 토큰 불일치: `첫 관리자 토큰이 올바르지 않습니다.`
  - 비밀번호 없는 계정의 비밀번호 변경: `비밀번호가 없는 계정입니다.`
- **Ruling(설계 보완):** 설계는 `GOOGLE_CLIENT_ID` 가 있으면 `GOOGLE_REDIRECT_URI` 도 필수라고 했다. 개발 환경(`ENV` 가 production 이 아님)에서는 비어 있으면 `http://localhost:5173/api/auth/google/callback` 을 쓰고, production 에서만 필수로 한다. 사용자 실사용 `.env` 에 이미 클라이언트 ID 와 비밀만 들어 있어 머지 뒤 기동이 멈추지 않게 하기 위해서다. 틀리면 드는 비용: 운영에서 주소를 빠뜨린 실수는 여전히 기동 때 잡힌다.

## Review Focus

- 앞뒤 공백과 대문자가 섞인 이메일(`  Ym@Example.COM `)로 가입한 뒤 소문자로 로그인하면 된다(Task 4 테스트).
- 승인 대기 계정이 비밀번호 찾기 코드 확인을 하면 일반 실패(401)와 같은 응답이 나온다(Task 5 테스트).
- 프로젝트 멤버로 추가된 승인 대기 계정도 거절(삭제)된다. 멤버 행은 CASCADE 로 지워진다(Task 5 테스트).
- 실사용 `.env` 처럼 클라이언트 ID 와 비밀만 있고 리디렉션 주소가 없어도 개발 환경에서는 기동한다(Task 1 테스트).
- 중지된 사용자가 남은 쿠키로 계정 연결을 시작하면 401 이다(Task 6 테스트).

---

### Task 1: 인증 설정과 판정 함수

**Files:**
- Create: `backend/services/auth_config.py`
- Create: `backend/services/account_policy.py`
- Modify: `backend/main.py` (임포트 시점 검사 한 줄)
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Test: `backend/tests_unit/test_auth_config.py`, `backend/tests_unit/test_account_policy.py`

**Interfaces:**
- Produces:
  - `auth_config.AuthConfig` (frozen dataclass: `google_client_id: str`, `google_client_secret: str`, `google_redirect_uri: str`, `company_domains: frozenset[str]`, `allow_personal: bool`, `approval: str`, `bootstrap_token: str`, `production: bool`, 속성 `google_enabled -> bool`)
  - `auth_config.load_auth_config(env: Mapping[str, str]) -> AuthConfig` (잘못된 값이면 `RuntimeError`)
  - `auth_config.get_auth_config() -> AuthConfig` (`os.environ` 을 매번 읽는다)
  - `account_policy.AccountRejected(code: str)` 예외, 속성 `code`
  - `account_policy.normalize_email(raw: str) -> str` (형식 오류나 100자 초과면 `ValueError`)
  - `account_policy.normalize_identifier(raw: str) -> str`
  - `account_policy.initial_status(cfg: AuthConfig, *, source: str, email: str, hd: str | None = None) -> UserStatus` (`source` 는 `"google"` 또는 `"email"`)
  - `account_policy.safe_next(raw: str | None, default: str = "/projects") -> str`
- Consumes: `models.UserStatus` (Task 2 에서 만든다. 이 태스크에서 먼저 `models.py` 에 enum 만 추가한다. Step 3 참고)

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests_unit/test_auth_config.py`

```python
"""인증 환경변수 읽기와 검사. 잘못된 값이면 임포트 때 멈춘다."""
import pytest

from services.auth_config import load_auth_config


def test_기본값은_개인허용_승인없음_구글꺼짐():
    cfg = load_auth_config({})
    assert cfg.allow_personal is True
    assert cfg.approval == "none"
    assert cfg.google_enabled is False
    assert cfg.company_domains == frozenset()


def test_회사_도메인은_소문자_공백제거_쉼표구분():
    cfg = load_auth_config({"AUTH_COMPANY_DOMAINS": " Corp.COM , sub.corp.com ,"})
    assert cfg.company_domains == frozenset({"corp.com", "sub.corp.com"})


@pytest.mark.parametrize("env", [
    {"AUTH_APPROVAL": "maybe"},
    {"AUTH_ALLOW_PERSONAL": "yes"},
    {"AUTH_ALLOW_PERSONAL": "0"},
    {"GOOGLE_CLIENT_ID": "cid"},
    {"ENV": "production", "GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "s"},
])
def test_잘못된_설정은_멈춘다(env):
    with pytest.raises(RuntimeError):
        load_auth_config(env)


def test_개발환경은_리디렉션_주소가_없으면_로컬_기본값():
    cfg = load_auth_config({"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "s"})
    assert cfg.google_enabled is True
    assert cfg.google_redirect_uri == "http://localhost:5173/api/auth/google/callback"


def test_production_표시와_부트스트랩_토큰():
    cfg = load_auth_config({"ENV": "production", "BOOTSTRAP_TOKEN": " t0k "})
    assert cfg.production is True
    assert cfg.bootstrap_token == "t0k"
```

`backend/tests_unit/test_account_policy.py`

```python
"""새 계정 상태 판정, 식별자 정규화, 이동 경로 검사."""
import pytest

from models import UserStatus
from services.account_policy import (
    AccountRejected, initial_status, normalize_email, normalize_identifier, safe_next,
)
from services.auth_config import load_auth_config

A, P = UserStatus.active, UserStatus.pending
REJ = "company_only"

# (approval, allow_personal) -> (회사 Google, 개인 Google, 회사 도메인 이메일, 기타 이메일)
TABLE = {
    ("none", "1"): (A, A, A, A),
    ("personal", "1"): (A, P, P, P),
    ("all", "1"): (P, P, P, P),
    ("none", "0"): (A, REJ, P, REJ),
    ("personal", "0"): (A, REJ, P, REJ),
    ("all", "0"): (P, REJ, P, REJ),
}


def _status(cfg, **kw):
    try:
        return initial_status(cfg, **kw)
    except AccountRejected as e:
        return e.code


@pytest.mark.parametrize("key", list(TABLE))
def test_판정표(key):
    approval, allow = key
    cfg = load_auth_config({"AUTH_APPROVAL": approval, "AUTH_ALLOW_PERSONAL": allow,
                            "AUTH_COMPANY_DOMAINS": "corp.com"})
    got = (
        _status(cfg, source="google", email="a@corp.com", hd="corp.com"),
        _status(cfg, source="google", email="a@gmail.com", hd=None),
        _status(cfg, source="email", email="a@corp.com"),
        _status(cfg, source="email", email="a@gmail.com"),
    )
    assert got == TABLE[key]


def test_회사_주소의_개인_Google_계정은_회사_계정이_아니다():
    cfg = load_auth_config({"AUTH_ALLOW_PERSONAL": "0", "AUTH_COMPANY_DOMAINS": "corp.com"})
    assert _status(cfg, source="google", email="a@corp.com", hd=None) == REJ


def test_이메일_정규화():
    assert normalize_email("  Ym@Example.COM ") == "ym@example.com"
    for bad in ["", "no-at", "a@b", "a b@c.com", "x" * 95 + "@c.com"]:
        with pytest.raises(ValueError):
            normalize_email(bad)


def test_식별자_정규화는_이메일만_소문자():
    assert normalize_identifier(" Admin ") == "Admin"
    assert normalize_identifier(" Ym@Example.com ") == "ym@example.com"


@pytest.mark.parametrize("raw,expected", [
    ("/projects/3?tab=tc", "/projects/3?tab=tc"),
    (None, "/projects"),
    ("", "/projects"),
    ("projects", "/projects"),
    ("//evil.com", "/projects"),
    ("/\\evil.com", "/projects"),
    ("/\tevil", "/projects"),
    ("https://evil.com", "/projects"),
    ("/a b", "/projects"),
])
def test_이동_경로는_사이트_안_경로만(raw, expected):
    assert safe_next(raw) == expected
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_config.py tests_unit/test_account_policy.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'services.auth_config'`

- [ ] **Step 3: 구현**

`backend/models.py` 의 `UserRole` 아래에 enum 을 추가한다(칸은 Task 2 에서 붙인다).

```python
class UserStatus(str, enum.Enum):
    active = "active"
    pending = "pending"
    disabled = "disabled"
```

`backend/services/auth_config.py`

```python
"""인증 설정(환경변수). 설계: docs/superpowers/specs/2026-10-09-org-account-auth-design.md

★main.py 가 임포트 때 load_auth_config(os.environ) 를 불러 잘못된 값이면 멈춘다. 서버리스는
  lifespan 을 부르지 않을 수 있어 임포트 시점에 검사한다(runtime_env 검사와 같은 자리).
★요청마다 get_auth_config() 로 다시 읽는다. 값이 작고, 테스트가 환경변수를 바꿔 끼울 수 있다.
"""
import os
from dataclasses import dataclass
from typing import Mapping

APPROVAL_VALUES = ("none", "personal", "all")
DEV_REDIRECT_URI = "http://localhost:5173/api/auth/google/callback"


@dataclass(frozen=True)
class AuthConfig:
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    company_domains: frozenset
    allow_personal: bool
    approval: str
    bootstrap_token: str
    production: bool

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id)


def _get(env: Mapping[str, str], name: str, default: str = "") -> str:
    value = env.get(name)
    return default if value is None else value.strip()


def load_auth_config(env: Mapping[str, str]) -> AuthConfig:
    production = _get(env, "ENV", "development") == "production"
    domains = frozenset(d.strip().lower() for d in _get(env, "AUTH_COMPANY_DOMAINS").split(",") if d.strip())

    allow = _get(env, "AUTH_ALLOW_PERSONAL") or "1"
    if allow not in ("0", "1"):
        raise RuntimeError(f"AUTH_ALLOW_PERSONAL 은 0 또는 1 이어야 합니다: {allow!r}")
    approval = (_get(env, "AUTH_APPROVAL") or "none").lower()
    if approval not in APPROVAL_VALUES:
        raise RuntimeError(f"AUTH_APPROVAL 은 none / personal / all 중 하나여야 합니다: {approval!r}")
    if allow == "0" and not domains:
        raise RuntimeError("AUTH_ALLOW_PERSONAL=0 이면 AUTH_COMPANY_DOMAINS 가 있어야 합니다(아무도 가입할 수 없습니다)")

    client_id = _get(env, "GOOGLE_CLIENT_ID")
    secret = _get(env, "GOOGLE_CLIENT_SECRET")
    redirect = _get(env, "GOOGLE_REDIRECT_URI")
    if client_id:
        if not secret:
            raise RuntimeError("GOOGLE_CLIENT_ID 를 쓰면 GOOGLE_CLIENT_SECRET 도 있어야 합니다")
        if not redirect:
            # ★개발 환경만 로컬 기본값을 준다. 운영은 Google 콘솔에 등록한 주소를 반드시 적게 한다.
            if production:
                raise RuntimeError("운영(ENV=production)에서는 GOOGLE_REDIRECT_URI 를 지정해야 합니다")
            redirect = DEV_REDIRECT_URI

    return AuthConfig(
        google_client_id=client_id,
        google_client_secret=secret,
        google_redirect_uri=redirect,
        company_domains=domains,
        allow_personal=allow == "1",
        approval=approval,
        bootstrap_token=_get(env, "BOOTSTRAP_TOKEN"),
        production=production,
    )


def get_auth_config() -> AuthConfig:
    return load_auth_config(os.environ)
```

`backend/services/account_policy.py`

```python
"""새 계정의 상태 판정과 입력 정규화. 설정을 인자로 받는 순수 함수다(표 테스트용).

회사 계정은 Google 이 준 Workspace 도메인(hd)으로만 판정한다. 회사 주소로 만든 개인 Google
계정은 hd 가 없다. 이메일 가입은 주소 소유를 확인할 수 없어 따로 다룬다.
"""
import re
from typing import Optional
from urllib.parse import urlsplit

from models import UserStatus

EMAIL_MAX = 100  # users.username 이 100자다. 이메일 가입은 username 에 이메일을 넣는다
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_BAD_PATH_CHARS = re.compile(r"[\\\x00-\x20\x7f]")


class AccountRejected(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalize_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if len(email) > EMAIL_MAX or not _EMAIL_RE.match(email):
        raise ValueError("이메일 형식이 올바르지 않습니다.")
    return email


def normalize_identifier(raw: str) -> str:
    """로그인 칸 입력. 이메일이면 소문자로 바꾼다. 횟수 제한 키도 이 값으로 만든다."""
    value = (raw or "").strip()
    return value.lower() if "@" in value else value


def initial_status(cfg, *, source: str, email: str, hd: Optional[str] = None) -> UserStatus:
    if source == "google":
        company = bool(hd) and hd.lower() in cfg.company_domains
        if not company and not cfg.allow_personal:
            raise AccountRejected("company_only")
        if cfg.approval == "none":
            return UserStatus.active
        if cfg.approval == "personal":
            return UserStatus.active if company else UserStatus.pending
        return UserStatus.pending
    if source == "email":
        if not cfg.allow_personal:
            if email.rsplit("@", 1)[-1] not in cfg.company_domains:
                raise AccountRejected("company_only")
            # ★회사 계정만 받는 설정에서 이메일 가입은 승인 설정과 상관없이 대기다.
            #   주소 소유를 확인하지 않으므로 회사 주소를 적기만 하면 통과하는 구멍이 된다.
            return UserStatus.pending
        return UserStatus.active if cfg.approval == "none" else UserStatus.pending
    raise ValueError(f"알 수 없는 가입 경로: {source}")


def safe_next(raw: Optional[str], default: str = "/projects") -> str:
    """로그인 뒤 이동할 경로. 사이트 안 경로만 받는다(열린 리디렉션 차단)."""
    if not raw or not raw.startswith("/") or raw.startswith("//") or _BAD_PATH_CHARS.search(raw):
        return default
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc:
        return default
    return raw
```

`backend/main.py` 의 `check_serverless_config()` 줄 바로 아래에 추가한다.

```python
from services.auth_config import load_auth_config  # noqa: E402

load_auth_config(os.environ)
```

`backend/requirements.txt` 끝에 추가한다.

```
google-auth==2.61.0  # Google ID 토큰 검증(서명, aud, iss, 만료)
requests==2.34.2  # google-auth 의 HTTP 전송. 개발 의존성에만 있으면 운영에서 ImportError
```

`backend/.env.example` 끝에 추가한다.

```
# ── 로그인 정책 ────────────────────────────────────────────────

# Google 로그인. 클라이언트 ID 가 비어 있으면 Google 로그인 버튼을 숨긴다
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
# Google 콘솔에 등록한 리디렉션 URI 와 글자까지 같아야 한다. 개발 환경은 비워 두면 아래 값을 쓴다
GOOGLE_REDIRECT_URI=http://localhost:5173/api/auth/google/callback

# 회사 도메인(쉼표로 여러 개). Google Workspace 도메인으로 회사 계정을 판정한다
AUTH_COMPANY_DOMAINS=
# AUTH_COMPANY_DOMAINS=company.com

# 회사 도메인 밖 계정(개인 메일)을 받을지. 1 = 받는다, 0 = 회사 계정만
AUTH_ALLOW_PERSONAL=1
# AUTH_ALLOW_PERSONAL=0

# 관리자 승인이 필요한 대상. none = 모두 바로 사용(누구나 가입해 바로 씀),
# personal = 회사 Google 계정만 바로, 나머지는 승인 후, all = 모두 승인 후
AUTH_APPROVAL=none
# AUTH_APPROVAL=personal
# AUTH_APPROVAL=all

# 운영(ENV=production)의 빈 DB 에서 첫 관리자를 만들 때만 쓴다. 가입 화면에 이 값을 넣어야 한다
BOOTSTRAP_TOKEN=

# IP 하나가 1시간에 보낼 수 있는 가입 요청 수
REGISTER_MAX_PER_HOUR=10
```

그리고 의존성을 설치한다: `pip install google-auth==2.61.0 requests==2.34.2`

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_config.py tests_unit/test_account_policy.py`
Expected: PASS (전부)

- [ ] **Step 5: 커밋(로컬)**

```bash
git add backend/services/auth_config.py backend/services/account_policy.py backend/models.py backend/main.py backend/requirements.txt backend/.env.example backend/tests_unit/test_auth_config.py backend/tests_unit/test_account_policy.py
git commit -m "feat(auth): 로그인 정책 환경변수와 새 계정 판정 함수"
```

---

### Task 2: 계정 칸 마이그레이션(0007)과 모델

**Files:**
- Create: `backend/alembic/versions/0007_account_identity.py`
- Modify: `backend/models.py` (`User`, `AccountRequest`)
- Modify: `backend/services/locks.py` (`FIRST_ADMIN` -> `ACCOUNTS`, 값 2 유지)
- Modify: `backend/routes/auth.py:82` (`LockNs.FIRST_ADMIN` -> `LockNs.ACCOUNTS`)
- Test: `backend/tests_unit/test_auth_migration.py`

**Interfaces:**
- Produces:
  - `User.email: str | None`(100자, 유일), `User.email_verified: bool`(server_default false), `User.google_sub: str | None`(유일), `User.status: UserStatus`(server_default 'active'), `User.password_hash: str | None`
  - `User.has_password` 속성(bool), `User.google_linked` 속성(bool)
  - `LockNs.ACCOUNTS = 2`
  - `account_requests.user_id`, `resolved_by_id` 외래키 `ON DELETE SET NULL`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests_unit/test_auth_migration.py`

```python
"""0007: 기존 사용자는 active, 비밀번호 칸은 비어도 됨, 복구 이력은 사용자 삭제를 막지 않는다."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import testing_db


def _alembic(url, *args):
    env = dict(os.environ, DATABASE_URL=url, DATABASE_URL_DIRECT="")
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr


@pytest.fixture
def url():
    u = testing_db.create_database(prefix="ymtc_0007")
    yield u
    testing_db.drop_database(u)


def test_기존_행이_active_로_채워지고_새_칸이_생긴다(url):
    _alembic(url, "upgrade", "0006_storage_deletions")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (username, password_hash, display_name, role, must_change_password, token_version) "
                       "VALUES ('old', 'h', 'Old', 'admin', false, 0)"))
    _alembic(url, "upgrade", "head")
    with eng.begin() as c:
        row = c.execute(text("SELECT status::text, email, email_verified, google_sub FROM users WHERE username='old'")).one()
        assert row == ("active", None, False, None)
        c.execute(text("INSERT INTO users (username, display_name, role, must_change_password, token_version) "
                       "VALUES ('google-only', 'G', 'user', false, 0)"))
    eng.dispose()


def test_복구_이력이_있어도_사용자를_지울_수_있다(url):
    _alembic(url, "upgrade", "head")
    eng = create_engine(url)
    with eng.begin() as c:
        uid = c.execute(text("INSERT INTO users (username, password_hash, display_name, role, must_change_password, token_version) "
                             "VALUES ('p', 'h', 'P', 'user', false, 0) RETURNING id")).scalar()
        c.execute(text("INSERT INTO account_requests (request_type, status, contact, user_id, resolved_by_id) "
                       "VALUES ('reset_password', 'approved', 'x', :u, :u)"), {"u": uid})
        c.execute(text("DELETE FROM users WHERE id = :u"), {"u": uid})
        assert c.execute(text("SELECT user_id, resolved_by_id FROM account_requests")).one() == (None, None)
    eng.dispose()


def test_내렸다_올려도_된다(url):
    _alembic(url, "upgrade", "head")
    _alembic(url, "downgrade", "0006_storage_deletions")
    _alembic(url, "upgrade", "head")
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_migration.py`
Expected: FAIL, 첫 테스트가 `column "status" does not exist`

- [ ] **Step 3: 구현**

`backend/alembic/versions/0007_account_identity.py`

```python
"""계정 신원 칸: email, email_verified, google_sub, status. password_hash 를 비어도 되게.

account_requests 의 사용자 외래키를 SET NULL 로 바꾼다. 승인 대기 계정을 거절(삭제)할 때
복구 이력 때문에 삭제가 막히지 않게 한다.
★status 와 email_verified 는 서버 기본값이 있어야 한다. SQLite 이관 스크립트가 원본에 없는
  칸을 빼고 INSERT 한다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_account_identity"
down_revision = "0006_storage_deletions"
branch_labels = None
depends_on = None

_STATUS = sa.Enum("active", "pending", "disabled", name="userstatus")


def upgrade() -> None:
    _STATUS.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column("email", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("status", _STATUS, nullable=False, server_default="active"))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)
    for col in ("user_id", "resolved_by_id"):
        name = f"account_requests_{col}_fkey"
        op.drop_constraint(name, "account_requests", type_="foreignkey")
        op.create_foreign_key(name, "account_requests", "users", [col], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    for col in ("user_id", "resolved_by_id"):
        name = f"account_requests_{col}_fkey"
        op.drop_constraint(name, "account_requests", type_="foreignkey")
        op.create_foreign_key(name, "account_requests", "users", [col], ["id"])
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_index(op.f("ix_users_google_sub"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "status")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "email")
    _STATUS.drop(op.get_bind(), checkfirst=True)
```

`backend/models.py` 의 `User` 를 바꾼다. `password_hash` 줄을 아래로 바꾸고, `token_version` 아래에 칸 넷과 속성 둘을 넣는다.

```python
    # Google 로만 가입한 계정에는 비밀번호가 없다. 비어 있으면 비밀번호 로그인은 항상 실패한다
    password_hash = Column(String(255), nullable=True)
```

```python
    #: 이메일 가입과 Google 계정의 주소. 소문자로 저장한다. 기존 아이디 계정은 비어 있다.
    email = Column(String(100), unique=True, nullable=True, index=True)
    #: Google 이 확인해 준 이메일이면 참. 이메일 가입은 거짓(주소 소유를 확인하지 않는다).
    email_verified = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    #: Google 이 계정마다 주는 고유 번호. Google 로그인은 이메일이 아니라 이 칸으로 찾는다.
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    status = Column(SAEnum(UserStatus), nullable=False, default=UserStatus.active, server_default=UserStatus.active.value)
```

```python
    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def google_linked(self) -> bool:
        return bool(self.google_sub)
```

`AccountRequest` 의 두 외래키를 바꾼다.

```python
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
```

```python
    resolved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
```

`backend/services/locks.py` 의 `LockNs` 에서 `FIRST_ADMIN = 2` 를 아래로 바꾼다.

```python
    #: 계정 생성과 신원·상태·역할 변경을 한 줄로 세운다(옛 이름 FIRST_ADMIN, 값은 그대로).
    ACCOUNTS = 2
```

`backend/routes/auth.py:82` 의 `advisory_xact_lock(db, LockNs.FIRST_ADMIN)` 을 `advisory_xact_lock(db, LockNs.ACCOUNTS)` 로 바꾼다.

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_migration.py tests_unit/test_baseline_schema.py tests_unit/test_schema_version.py tests_unit/test_rls_migration.py`
Expected: PASS. `test_모델과_차이가_없다` 가 실패하면 모델과 마이그레이션의 server_default 표기를 맞춘다(마이그레이션 쪽을 정본으로 본다).

Run: `cd .. && python -m pytest -q scripts/test_migrate_sqlite_to_pg.py`
Expected: PASS (이관 스크립트가 새 칸을 서버 기본값으로 채운다)

- [ ] **Step 5: 커밋(로컬)**

```bash
git add backend/alembic/versions/0007_account_identity.py backend/models.py backend/services/locks.py backend/routes/auth.py backend/tests_unit/test_auth_migration.py
git commit -m "feat(auth): 계정 신원 칸 마이그레이션 0007 (email, google_sub, status)"
```

---

### Task 3: 로그인과 계정 상태의 효력

**Files:**
- Create: `backend/services/accounts.py`
- Modify: `backend/auth.py` (`verify_password`, `_user_from_api_key`, `get_current_user`)
- Modify: `backend/routes/auth.py` (`issue_session` 분리, `login`, `change_password`)
- Modify: `backend/schemas.py` (`UserResponse`)
- Modify: `backend/tests_unit/conftest.py` (공용 픽스처)
- Create: `backend/tests_unit/auth_helpers.py`
- Test: `backend/tests_unit/test_auth_login.py`

**Interfaces:**
- Consumes: `account_policy.normalize_identifier`, `UserStatus`, `LockNs.ACCOUNTS`
- Produces:
  - `accounts.lock_accounts(db: Session) -> None`
  - `accounts.find_user_by_identifier(db: Session, raw: str) -> User | None` (email 먼저, 없으면 username)
  - `accounts.active_admin_count(db: Session, exclude_id: int | None = None) -> int`
  - `accounts.email_taken(db: Session, email: str, exclude_id: int | None = None) -> bool` (email 칸과 username 칸 모두)
  - `accounts.google_username(db: Session, email: str) -> str`
  - `accounts.disable(db: Session, user: User) -> None` (상태 disabled, token_version+1, API 키 폐기. 커밋 안 함)
  - `routes.auth.issue_session(response: Response, user: User, remember_me: bool = False) -> str` (쿠키 둘을 심고 토큰을 돌려준다)
  - `auth.verify_password(plain: str, hashed: str | None) -> bool`
  - 테스트 픽스처 `live_app`(모듈, base URL 문자열), `auth_env`(함수, `SimpleNamespace(base, Session, engine)`)
  - `auth_helpers.PW`, `make_user(Session, **kw) -> int`, `login(base, ident, password=PW)`, `bearer(resp) -> dict`

- [ ] **Step 1: 공용 픽스처와 도우미, 실패하는 테스트 작성**

`backend/tests_unit/conftest.py` 끝에 추가한다.

```python
import socket
import threading
import time
from types import SimpleNamespace

import uvicorn
from sqlalchemy.orm import sessionmaker

_AUTH_ENV_KEYS = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "AUTH_COMPANY_DOMAINS",
                  "AUTH_ALLOW_PERSONAL", "AUTH_APPROVAL", "BOOTSTRAP_TOKEN", "REGISTER_MAX_PER_HOUR")


@pytest.fixture(scope="module")
def live_app():
    """앱을 빈 포트에 띄운다(lifespan 끔). DB 는 auth_env 가 get_db 를 갈아 끼운다."""
    from main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, lifespan="off", log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    deadline = time.time() + 15
    while not srv.started and time.time() < deadline:
        time.sleep(0.05)
    assert srv.started, "테스트 서버가 뜨지 않았다"
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    th.join(timeout=10)


@pytest.fixture
def auth_env(pg_engine, live_app, monkeypatch):
    """임시 스키마 DB + 인증 환경변수 초기화. 테스트가 monkeypatch.setenv 로 정책을 바꾼다."""
    from database import get_db
    from main import app
    from services import rate_limit

    Session = sessionmaker(bind=pg_engine)

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    for key in _AUTH_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENV", "development")
    app.dependency_overrides[get_db] = _db
    rate_limit.clear_all(engine=pg_engine)
    yield SimpleNamespace(base=live_app, Session=Session, engine=pg_engine)
    app.dependency_overrides.clear()
```

`backend/tests_unit/auth_helpers.py`

```python
"""인증 테스트 도우미. 사용자는 ORM 으로 바로 만들고 요청은 실제 HTTP 로 보낸다."""
import requests

from auth import hash_password
from models import User, UserRole, UserStatus

PW = "Passw0rd!long"


def make_user(Session, *, username, email=None, role=UserRole.user, status=UserStatus.active,
              password=PW, google_sub=None, email_verified=False, display_name=None) -> int:
    s = Session()
    try:
        u = User(username=username, email=email, role=role, status=status,
                 password_hash=hash_password(password) if password else None,
                 google_sub=google_sub, email_verified=email_verified,
                 display_name=display_name or username)
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


def login(base, ident, password=PW):
    return requests.post(base + "/api/auth/login", json={"username": ident, "password": password})


def bearer(resp) -> dict:
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}
```

`backend/tests_unit/test_auth_login.py`

```python
"""이메일 로그인, 횟수 제한 키 정규화, 상태 사유, 비밀번호 없는 계정, 중지의 효력."""
import requests

from auth_helpers import PW, bearer, login, make_user
from models import User, UserStatus


def test_이메일로_대소문자_무관하게_로그인(auth_env):
    make_user(auth_env.Session, username="ym@example.com", email="ym@example.com")
    assert login(auth_env.base, "  YM@Example.com ").status_code == 200


def test_골뱅이가_든_옛_아이디도_로그인된다(auth_env):
    make_user(auth_env.Session, username="old@name")
    assert login(auth_env.base, "old@name").status_code == 200


def test_대소문자를_바꿔도_같은_횟수_제한에_묶인다(auth_env):
    make_user(auth_env.Session, username="ym@example.com", email="ym@example.com")
    variants = ["ym@example.com", "YM@example.com", "Ym@Example.com", "yM@EXAMPLE.COM"]
    codes = [login(auth_env.base, variants[i % 4], "wrong-password").status_code for i in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_대기와_중지_사유는_비밀번호가_맞을_때만(auth_env):
    make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    make_user(auth_env.Session, username="d@example.com", email="d@example.com", status=UserStatus.disabled)
    assert login(auth_env.base, "p@example.com", "wrong-password").status_code == 401
    assert login(auth_env.base, "d@example.com", "wrong-password").status_code == 401
    r = login(auth_env.base, "p@example.com")
    assert (r.status_code, r.json()["detail"]) == (403, "관리자 승인을 기다리는 중입니다.")
    r = login(auth_env.base, "d@example.com")
    assert (r.status_code, r.json()["detail"]) == (403, "사용이 중지된 계정입니다.")


def test_비밀번호_없는_계정은_401_이고_변경은_400(auth_env):
    make_user(auth_env.Session, username="g@example.com", email="g@example.com", password=None, google_sub="sub-1")
    assert login(auth_env.base, "g@example.com", "anything-at-all").status_code == 401
    uid = make_user(auth_env.Session, username="has-pw")
    h = bearer(login(auth_env.base, "has-pw"))
    s = auth_env.Session()
    s.get(User, uid).password_hash = None
    s.commit()
    s.close()
    r = requests.put(auth_env.base + "/api/auth/change-password", headers=h,
                     json={"current_password": PW, "new_password": "NewPassw0rd!"})
    # 세션 토큰은 비밀번호를 지우기 전에 받았다. 비밀번호가 없으면 400
    assert (r.status_code, r.json()["detail"]) == (400, "비밀번호가 없는 계정입니다.")


def test_중지하면_JWT_와_API_키가_바로_막힌다(auth_env):
    uid = make_user(auth_env.Session, username="victim")
    h = bearer(login(auth_env.base, "victim"))
    key = requests.post(auth_env.base + "/api/auth/api-keys", headers=h,
                        json={"name": "k", "expires_days": 30}).json()["key"]
    assert requests.get(auth_env.base + "/api/auth/me", headers={"Authorization": "Bearer " + key}).status_code == 200
    s = auth_env.Session()
    s.get(User, uid).status = UserStatus.disabled
    s.commit()
    s.close()
    assert requests.get(auth_env.base + "/api/auth/me", headers=h).status_code == 401
    assert requests.get(auth_env.base + "/api/auth/me", headers={"Authorization": "Bearer " + key}).status_code == 401


def test_me_응답에_새_칸이_있다(auth_env):
    make_user(auth_env.Session, username="ym@example.com", email="ym@example.com")
    body = requests.get(auth_env.base + "/api/auth/me", headers=bearer(login(auth_env.base, "ym@example.com"))).json()
    assert body["email"] == "ym@example.com"
    assert body["status"] == "active"
    assert body["has_password"] is True and body["google_linked"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_login.py`
Expected: FAIL. 이메일 로그인 401, `/me` 응답에 `email` 없음, 비밀번호 없는 계정 로그인에서 500 등

- [ ] **Step 3: 구현**

`backend/auth.py`: `import` 줄에 `UserStatus` 를 더한다(`from models import User, UserRole, UserStatus, Project, ProjectMember, ProjectRole`). `verify_password` 를 바꾼다.

```python
_DUMMY_HASH: Optional[str] = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
    return _DUMMY_HASH


def verify_password(plain: str, hashed: Optional[str]) -> bool:
    # ★해시가 없으면(계정 없음, Google 전용 계정) 더미 해시로 한 번 대조하고 거짓을 낸다.
    #   bcrypt 를 건너뛰면 응답 시간으로 계정 유무가 새고, None.encode() 는 500 이 된다.
    if not hashed:
        bcrypt.checkpw(plain.encode("utf-8"), _dummy_hash().encode("utf-8"))
        return False
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

`_user_from_api_key` 의 `if user is None:` 을 아래로 바꾼다.

```python
    # ★중지·대기 계정의 키도 막는다. 이 경로는 get_current_user 의 상태 검사보다 먼저 반환한다.
    if user is None or user.status != UserStatus.active:
        raise denied
```

`get_current_user` 의 `ver` 대조 바로 아래에 넣는다.

```python
    if user.status != UserStatus.active:
        raise credentials_exception
```

`backend/services/accounts.py`

```python
"""계정 변경 공통 도구. 생성, 연결, 승인, 중지, 역할 변경은 모두 lock_accounts 안에서 한다.

★행 잠금만으로는 부족하다. 관리자 둘이 서로를 동시에 중지하면 서로 다른 행을 잠가 둘 다
  '활성 관리자 2명' 을 보고 통과한다. 전역 잠금 하나로 줄 세우고 그 안에서 센다.
"""
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from auth import revoke_user_api_keys
from models import User, UserRole, UserStatus
from services.account_policy import normalize_identifier
from services.locks import LockNs, advisory_xact_lock


def lock_accounts(db: Session) -> None:
    advisory_xact_lock(db, LockNs.ACCOUNTS)


def find_user_by_identifier(db: Session, raw: str) -> Optional[User]:
    ident = normalize_identifier(raw)
    if not ident:
        return None
    if "@" in ident:
        user = db.query(User).filter(User.email == ident).first()
        if user:
            return user
    return db.query(User).filter(User.username == ident).first()


def active_admin_count(db: Session, exclude_id: Optional[int] = None) -> int:
    q = db.query(func.count(User.id)).filter(User.role == UserRole.admin, User.status == UserStatus.active)
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.scalar() or 0


def email_taken(db: Session, email: str, exclude_id: Optional[int] = None) -> bool:
    q = db.query(User.id).filter(or_(User.email == email, User.username == email))
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.first() is not None


def google_username(db: Session, email: str) -> str:
    """Google 신규 계정의 아이디. 같은 문자열의 아이디가 있으면 #숫자로 비켜 만든다."""
    base = email[:95]
    if not db.query(User.id).filter(User.username == base).first():
        return base
    n = 2
    while db.query(User.id).filter(User.username == f"{base}#{n}").first():
        n += 1
    return f"{base}#{n}"


def disable(db: Session, user: User) -> None:
    user.status = UserStatus.disabled
    user.token_version = (user.token_version or 0) + 1
    revoke_user_api_keys(user.id, db)
```

`backend/schemas.py` 의 `UserResponse` 를 바꾼다.

```python
class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    must_change_password: bool = False
    created_at: datetime
    email: Optional[str] = None
    status: str = "active"
    has_password: bool = True
    google_linked: bool = False

    model_config = ConfigDict(from_attributes=True)
```

(`Optional` 이 `schemas.py` 상단에 임포트돼 있지 않으면 `from typing import Optional` 을 더한다.)

`backend/routes/auth.py`

- 임포트에 `from models import User, UserRole, UserStatus` 와 `from services.accounts import find_user_by_identifier` 와 `from services.account_policy import normalize_identifier` 를 더한다.
- `login` 의 쿠키 설정 부분을 함수로 떼고 `login` 을 아래로 바꾼다.

```python
def issue_session(response: Response, user: User, remember_me: bool = False) -> str:
    """로그인 쿠키(access_token, csrf_token)를 심는다. 비밀번호 로그인과 Google 로그인이 같이 쓴다."""
    # remember_me: 30일, 일반: 기본 만료
    # ★예전에는 3650일이었다. JWT 는 발급 후 만료까지 서버가 막을 수 없으므로
    #   그 값은 유출된 토큰을 10년간 되돌릴 수 없다는 뜻이었다. 기간을 줄이고
    #   token_version 으로 폐기 경로를 따로 뒀다.
    if remember_me:
        expire_delta = timedelta(days=REMEMBER_ME_DAYS)
        cookie_max_age = REMEMBER_ME_DAYS * 24 * 3600
    else:
        expire_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        cookie_max_age = COOKIE_MAX_AGE
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "ver": user.token_version or 0},
        expires_delta=expire_delta,
    )
    response.set_cookie(key="access_token", value=token, httponly=True, secure=COOKIE_SECURE,
                        samesite=COOKIE_SAMESITE, max_age=cookie_max_age, path="/")
    # CSRF 토큰 (JS에서 읽을 수 있도록 httpOnly=False)
    response.set_cookie(key="csrf_token", value=secrets.token_urlsafe(32), httponly=False, secure=COOKIE_SECURE,
                        samesite=COOKIE_SAMESITE, max_age=cookie_max_age, path="/")
    return token


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    # ★제한 키를 정규화한 값으로 만든다. 원문을 쓰면 대소문자를 바꿔 한도를 비켜 간다.
    ident = normalize_identifier(payload.username)
    _check_rate_limit(request, ident, db)

    user = find_user_by_identifier(db, ident)
    ok = verify_password(payload.password, user.password_hash if user else None)
    if not user or not ok:
        logger.warning("Failed login attempt: user=%s ip=%s", ident, client_ip(request))
        _record_failure(request, ident, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    _clear_failures(request, ident, db)
    # ★상태는 비밀번호가 맞은 뒤에만 알려 준다. 틀렸을 때 알려 주면 남의 계정 상태를 떠볼 수 있다.
    if user.status == UserStatus.pending:
        raise HTTPException(status_code=403, detail="관리자 승인을 기다리는 중입니다.")
    if user.status == UserStatus.disabled:
        raise HTTPException(status_code=403, detail="사용이 중지된 계정입니다.")

    logger.info("User logged in: %s (remember_me=%s)", user.username, payload.remember_me)
    token = issue_session(response, user, payload.remember_me)
    # ★횟수 제한 키 잠금을 응답 전에 푼다. get_db 정리는 응답 뒤에 돈다(SYM-145).
    db.commit()
    return Token(access_token=token, must_change_password=user.must_change_password)
```

- `change_password` 의 첫 줄에 넣는다.

```python
    if not current_user.password_hash:
        raise HTTPException(status_code=400, detail="비밀번호가 없는 계정입니다.")
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_login.py tests_unit/test_api_keys.py tests_unit/test_rate_limit.py`
Expected: PASS

- [ ] **Step 5: 커밋(로컬)**

```bash
git add backend/auth.py backend/services/accounts.py backend/routes/auth.py backend/schemas.py backend/tests_unit/conftest.py backend/tests_unit/auth_helpers.py backend/tests_unit/test_auth_login.py
git commit -m "feat(auth): 이메일 로그인, 계정 상태 효력, 비밀번호 없는 계정 처리"
```

---

### Task 4: 가입(첫 관리자, 이메일 가입), 설정 조회, 기존 테스트 전환

**Files:**
- Modify: `backend/routes/auth.py` (`register`, `check_username`, 새 `GET /config`)
- Modify: `backend/schemas.py` (`UserCreate`)
- Modify: `backend/conftest.py` (`REGISTER_MAX_PER_HOUR` 기본값)
- Modify: `backend/tests_unit/test_first_admin_concurrent.py`
- Modify: `backend/test_account_requests.py`, `backend/test_run_tc_sync.py`, `backend/test_security.py`, `backend/test_staged_upload.py`, `backend/test_token_revocation.py`
- Test: `backend/tests_unit/test_auth_register.py`

**Interfaces:**
- Consumes: `get_auth_config`, `initial_status`, `normalize_email`, `AccountRejected`, `lock_accounts`, `email_taken`
- Produces:
  - `POST /api/auth/register` 요청 `{username?, email?, password, display_name, bootstrap_token?}`, 응답 `UserResponse`(201)
  - `GET /api/auth/config` 응답 `{"google_enabled": bool, "signup_mode": "bootstrap" | "email"}`
  - `GET /api/auth/check-username` 은 사용자가 있으면 404
  - `routes.auth.register(payload: UserCreate, request: Request, db: Session)` (테스트가 직접 부른다)

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests_unit/test_auth_register.py`

```python
"""첫 관리자, 이메일 가입 정책, 가입 횟수 제한, 설정 조회."""
import requests

from auth_helpers import PW, make_user
from models import User, UserRole, UserStatus


def _reg(base, **body):
    body.setdefault("password", PW)
    body.setdefault("display_name", "N")
    return requests.post(base + "/api/auth/register", json=body)


def test_빈_DB_는_첫_관리자_화면이고_아이디로_만든다(auth_env):
    assert requests.get(auth_env.base + "/api/auth/config").json() == {"google_enabled": False, "signup_mode": "bootstrap"}
    r = _reg(auth_env.base, username="boss")
    assert r.status_code == 201, r.text
    assert (r.json()["role"], r.json()["status"]) == ("admin", "active")
    assert requests.get(auth_env.base + "/api/auth/config").json()["signup_mode"] == "email"
    assert requests.get(auth_env.base + "/api/auth/check-username", params={"username": "x"}).status_code == 404


def test_운영의_첫_관리자는_토큰이_맞아야(auth_env, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("BOOTSTRAP_TOKEN", "t0k")
    r = _reg(auth_env.base, username="boss", bootstrap_token="nope")
    assert (r.status_code, r.json()["detail"]) == (403, "첫 관리자 토큰이 올바르지 않습니다.")
    assert _reg(auth_env.base, username="boss", bootstrap_token="t0k").status_code == 201


def test_운영인데_토큰이_설정돼_있지_않으면_첫_관리자를_못_만든다(auth_env, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    assert _reg(auth_env.base, username="boss").status_code == 403


def test_사용자가_있으면_이메일이_필요하다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    r = _reg(auth_env.base, username="someone")
    assert (r.status_code, r.json()["detail"]) == (400, "이메일로 가입해 주세요.")


def test_이메일_가입은_정규화되고_그_이메일로_로그인된다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    r = _reg(auth_env.base, email="  Ym@Example.COM ")
    assert r.status_code == 201, r.text
    assert (r.json()["username"], r.json()["email"], r.json()["status"]) == ("ym@example.com", "ym@example.com", "active")
    assert requests.post(auth_env.base + "/api/auth/login", json={"username": "ym@example.com", "password": PW}).status_code == 200


def test_중복_이메일은_400(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin, email="ym@example.com")
    r = _reg(auth_env.base, email="YM@example.com")
    assert (r.status_code, r.json()["detail"]) == (400, "이미 가입된 이메일입니다.")


def test_personal_이면_이메일_가입은_대기(auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_APPROVAL", "personal")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    assert _reg(auth_env.base, email="a@corp.com").json()["status"] == "pending"


def test_회사_계정만이면_다른_도메인은_403_회사_도메인도_대기(auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_PERSONAL", "0")
    monkeypatch.setenv("AUTH_COMPANY_DOMAINS", "corp.com")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    r = _reg(auth_env.base, email="a@gmail.com")
    assert (r.status_code, r.json()["detail"]) == (403, "회사 이메일로만 가입할 수 있습니다.")
    assert _reg(auth_env.base, email="b@corp.com").json()["status"] == "pending"


def test_가입_횟수_제한(auth_env, monkeypatch):
    monkeypatch.setenv("REGISTER_MAX_PER_HOUR", "3")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    codes = [_reg(auth_env.base, email=f"u{i}@example.com").status_code for i in range(4)]
    assert codes == [201, 201, 201, 429]


def test_구글_설정이_있으면_config_가_알린다(auth_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "s")
    assert requests.get(auth_env.base + "/api/auth/config").json()["google_enabled"] is True
```

`backend/tests_unit/test_first_admin_concurrent.py` 전체를 바꾼다.

```python
"""빈 DB 에 동시에 가입해도 관리자는 한 명이다.

라우트 함수를 독립 세션(독립 연결)으로 동시에 부른다. SQLite 에서는 쓰기 잠금이
줄을 세워 줬지만 PostgreSQL 의 READ COMMITTED 에서는 서로의 미커밋 행을 못 본다.
첫 계정 뒤로는 아이디 가입이 막히므로(이메일로 가입해 주세요) 한 명만 성공한다.
"""
import threading

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from models import User, UserRole
from routes.auth import register
from schemas import UserCreate

N = 8


def _req():
    return Request({"type": "http", "method": "POST", "path": "/api/auth/register", "headers": [],
                    "client": ("127.0.0.1", 0), "query_string": b""})


def test_빈_DB_에_동시에_가입해도_관리자는_한_명(pg_engine, monkeypatch):
    monkeypatch.setenv("REGISTER_MAX_PER_HOUR", "1000")
    Session = sessionmaker(bind=pg_engine)
    barrier = threading.Barrier(N)
    ok, rejected, errors = [], [], []

    def go(i):
        s = Session()
        try:
            barrier.wait()
            register(UserCreate(username=f"user{i}", password="Passw0rd!x", display_name=f"u{i}"), request=_req(), db=s)
            ok.append(i)
        except HTTPException as e:
            rejected.append(e.status_code)
        except Exception as e:  # noqa: BLE001  실패도 결과로 모은다
            errors.append(repr(e))
        finally:
            s.close()

    threads = [threading.Thread(target=go, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    s = Session()
    roles = [u.role for u in s.query(User).all()]
    s.close()
    assert errors == []
    assert len(ok) == 1 and rejected == [400] * (N - 1)
    assert roles == [UserRole.admin]
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_register.py tests_unit/test_first_admin_concurrent.py`
Expected: FAIL. `/api/auth/config` 404, `register()` 에 `request` 인자 없음 등

- [ ] **Step 3: 구현**

`backend/schemas.py` 의 `UserCreate` 를 바꾼다.

```python
class UserCreate(BaseModel):
    # 사용자가 0명일 때(첫 관리자)만 username 을 받는다. 그 뒤로는 email 이 필수다.
    username: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=254)
    password: str = Field(..., min_length=8)
    display_name: str = Field(..., min_length=1, max_length=100)
    bootstrap_token: Optional[str] = None
```

`backend/routes/auth.py`

- 임포트에 더한다: `import hmac`, `import os`, `from sqlalchemy.exc import IntegrityError`, `from services.auth_config import get_auth_config`, `from services.account_policy import AccountRejected, initial_status, normalize_email`, `from services.accounts import lock_accounts, email_taken`.
- `check_username` 과 `register` 를 아래로 바꾸고 `config` 를 더한다.

```python
BUCKET_REGISTER = "register"
REGISTER_WINDOW_SEC = 3600


def _check_register_limit(request: Request, db: Session) -> None:
    """IP 하나의 가입 시도를 센다(성공·실패 무관). 인터넷에 열린 진입점이라 bcrypt 비용과
    승인 대기 목록 스팸을 막는다. 비밀번호 찾기 접수 제한과 같은 방식이다."""
    key = client_ip(request)
    keyed_xact_lock(db, LockNs.RATE_LIMIT, f"{BUCKET_REGISTER}:{key}")
    engine = db.get_bind()
    limit = int(os.getenv("REGISTER_MAX_PER_HOUR", "10"))
    if rate_limit.count_recent(BUCKET_REGISTER, key, REGISTER_WINDOW_SEC, engine=engine) >= limit:
        raise HTTPException(status_code=429, detail="가입 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
    rate_limit.record(BUCKET_REGISTER, key, engine=engine)


def _has_users(db: Session) -> bool:
    return db.query(User.id).first() is not None


@router.get("/config")
def auth_config_info(db: Session = Depends(get_db)):
    """화면이 켜진 로그인 기능을 묻는다. 사용자가 0명이면 첫 관리자 화면을 보여 준다."""
    cfg = get_auth_config()
    has_users = _has_users(db)
    db.rollback()
    return {"google_enabled": cfg.google_enabled, "signup_mode": "email" if has_users else "bootstrap"}


@router.get("/check-username")
def check_username(username: str, db: Session = Depends(get_db)):
    # 첫 관리자 화면에서만 쓴다. 사용자가 생긴 뒤로는 아이디 존재를 묻는 경로를 닫는다.
    if _has_users(db):
        raise HTTPException(status_code=404, detail="Not Found")
    return {"available": True}


def _bootstrap_admin(payload: UserCreate, cfg, password_hash: str, db: Session) -> User:
    if cfg.production:
        # ★인터넷에 열린 빈 DB 에서 먼저 들어온 사람이 관리자가 되는 것을 막는다.
        if not cfg.bootstrap_token or not hmac.compare_digest(payload.bootstrap_token or "", cfg.bootstrap_token):
            raise HTTPException(status_code=403, detail="첫 관리자 토큰이 올바르지 않습니다.")
    email = None
    if payload.username and payload.username.strip():
        username = payload.username.strip()
    elif payload.email:
        try:
            email = normalize_email(payload.email)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        username = email
    else:
        raise HTTPException(status_code=422, detail="아이디를 입력해 주세요.")
    user = User(username=username, email=email, email_verified=False, password_hash=password_hash,
                display_name=payload.display_name.strip()[:100], role=UserRole.admin,
                status=UserStatus.active, must_change_password=False)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    cfg = get_auth_config()
    # bcrypt 는 잠금 밖에서 한다. 잠금 구간이 길면 가입 연타에 모든 가입이 줄을 선다.
    password_hash = hash_password(payload.password)
    _check_register_limit(request, db)
    # ★계정 생성은 전역 잠금으로 줄 세운다. 잠금은 커밋까지 유지되므로 다음 가입은 앞선
    #   가입이 커밋된 뒤에 사용자 수와 이메일 중복을 본다(SYM-136).
    lock_accounts(db)
    if not _has_users(db):
        return _bootstrap_admin(payload, cfg, password_hash, db)

    if not payload.email:
        raise HTTPException(status_code=400, detail="이메일로 가입해 주세요.")
    try:
        email = normalize_email(payload.email)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        initial = initial_status(cfg, source="email", email=email)
    except AccountRejected:
        raise HTTPException(status_code=403, detail="회사 이메일로만 가입할 수 있습니다.")
    if email_taken(db, email):
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")

    user = User(username=email, email=email, email_verified=False, password_hash=password_hash,
                display_name=payload.display_name.strip()[:100], role=UserRole.user,
                status=initial, must_change_password=False)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")
    db.refresh(user)
    return user
```

`backend/conftest.py` 상단(다른 `os.environ` 설정이 있는 곳)에 넣는다. 서버 테스트는 한 IP 에서 여러 계정을 만든다.

```python
# 서버 테스트는 127.0.0.1 하나에서 계정을 여러 개 만든다. 운영 기본값(시간당 10회)이면 429 가 난다.
os.environ.setdefault("REGISTER_MAX_PER_HOUR", "1000")
```

기존 서버 테스트 전환. 이메일 가입은 아이디가 이메일이므로, 각 파일에서 테스트 계정 이름을 이메일로 바꾸고 가입 JSON 의 `"username"` 키를 `"email"` 로 바꾼다.

- `backend/test_account_requests.py`: 파일 전체에서 `"__recover_user__"` 를 `"__recover_user__@example.com"` 으로, `"__rl_target__"` 를 `"__rl_target__@example.com"` 으로 바꾼다. 114행과 395행 가입 JSON 의 `"username":` 을 `"email":` 로 바꾼다.
- `backend/test_run_tc_sync.py`: `"__sync_viewer__"` -> `"__sync_viewer__@example.com"`, 50행 가입 JSON 키를 `"email":` 로.
- `backend/test_staged_upload.py`: `"__staged_other__"` -> `"__staged_other__@example.com"`, 36행 가입 JSON 키를 `"email":` 로.
- `backend/test_token_revocation.py`: 50행을 `username = f"__revoke_{secrets.token_hex(4)}__@example.com"` 로, 54행 JSON 을 `{"email": username, "password": first_pw, "display_name": "Revoke Target"}` 로.
- `backend/test_security.py`:
  - `"__sec_viewer__"` -> `"__sec_viewer__@example.com"`, 52행 가입 JSON 키를 `"email":` 로.
  - 376행을 `username = f"__outsider_{uniq}__@example.com"` 로, 377행 가입 JSON 키를 `"email":` 로.
  - `test_check_username_exists` 와 `test_check_username_available` 두 함수를 아래 하나로 바꾼다.

```python
    def test_check_username_closed_after_bootstrap(self):
        """사용자가 생긴 뒤로는 아이디 존재를 묻는 경로가 닫힌다 → 404"""
        r = requests.get(f"{BASE}/api/auth/check-username?username=admin")
        assert r.status_code == 404
```

  - `test_register_duplicate` 를 아래로 바꾼다.

```python
    def test_register_duplicate(self):
        """같은 이메일 두 번 → 400"""
        body = {"email": "__sec_dup__@example.com", "password": "somepassword123", "display_name": "Dup"}
        requests.post(f"{BASE}/api/auth/register", json=body)
        r = requests.post(f"{BASE}/api/auth/register", json=body)
        assert r.status_code == 400
```

  - `test_register_short_password` 의 JSON 을 `{"email": "__sec_short_pw__@example.com", "password": "short", "display_name": "Short PW"}` 로 바꾼다.

남은 아이디 가입이 없는지 확인한다.

Run: `cd backend && grep -n "auth/register" -A3 test_*.py | grep '"username"'`
Expected: 출력 없음

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_register.py tests_unit/test_first_admin_concurrent.py`
Expected: PASS

Run: (전체 백엔드 테스트, Global Constraints 의 명령)
Expected: PASS(1 skipped). 실패하면 그 파일에 남은 옛 아이디를 찾아 바꾼다.

- [ ] **Step 5: 커밋(로컬)**

```bash
git add backend/routes/auth.py backend/schemas.py backend/conftest.py backend/tests_unit/test_auth_register.py backend/tests_unit/test_first_admin_concurrent.py backend/test_account_requests.py backend/test_run_tc_sync.py backend/test_security.py backend/test_staged_upload.py backend/test_token_revocation.py
git commit -m "feat(auth): 첫 관리자와 이메일 가입 정책, 가입 횟수 제한, 설정 조회"
```

---

### Task 5: 관리자 계정 관리와 복구 경로 정리

**Files:**
- Modify: `backend/routes/auth.py` (승인, 거절, 중지, 다시 사용, 이메일 해제, 역할 변경 가드, 관리자 초기화)
- Modify: `backend/routes/account_requests.py` (승인 대상 상태, 코드 확인 정규화, Google 연결 끊기)
- Test: `backend/tests_unit/test_auth_admin.py`

**Interfaces:**
- Consumes: `lock_accounts`, `active_admin_count`, `disable`, `find_user_by_identifier`, `normalize_identifier`
- Produces:
  - `POST /api/auth/users/{id}/approve|reject|disable|enable|release-email` (관리자, 응답 `UserResponse`, reject 는 204)
  - `routes.auth.disable_user(user_id: int, db: Session, current_user: User) -> User` (테스트가 직접 부른다)

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests_unit/test_auth_admin.py`

```python
"""승인, 거절, 중지, 다시 사용, 이메일 해제, 마지막 관리자 보호, 복구 경로."""
import threading

import requests
from fastapi import HTTPException

from auth_helpers import PW, bearer, login, make_user
from models import AccountRequest, AccountRequestStatus, AccountRequestType, Project, ProjectMember, ProjectRole, User, UserRole, UserStatus


def _admin(env, name="boss"):
    make_user(env.Session, username=name, role=UserRole.admin)
    return bearer(login(env.base, name))


def _post(env, h, path):
    return requests.post(env.base + path, headers=h)


def test_승인하면_로그인된다(auth_env):
    h = _admin(auth_env)
    uid = make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    assert _post(auth_env, h, f"/api/auth/users/{uid}/approve").json()["status"] == "active"
    assert login(auth_env.base, "p@example.com").status_code == 200
    assert _post(auth_env, h, f"/api/auth/users/{uid}/approve").status_code == 409


def test_거절은_대기만_지우고_멤버와_복구_이력이_있어도_된다(auth_env):
    h = _admin(auth_env)
    uid = make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    s = auth_env.Session()
    p = Project(name="P", created_by=s.query(User).filter_by(username="boss").one().id)
    s.add(p)
    s.flush()
    s.add(ProjectMember(project_id=p.id, user_id=uid, role=ProjectRole.tester))
    s.add(AccountRequest(request_type=AccountRequestType.reset_password, status=AccountRequestStatus.approved,
                         contact="x", user_id=uid))
    s.commit()
    s.close()
    assert _post(auth_env, h, f"/api/auth/users/{uid}/reject").status_code == 204
    s = auth_env.Session()
    assert s.get(User, uid) is None
    assert s.query(AccountRequest).one().user_id is None
    s.close()
    active = make_user(auth_env.Session, username="a2")
    assert _post(auth_env, h, f"/api/auth/users/{active}/reject").status_code == 409


def test_중지는_키를_폐기하고_다시_사용해도_옛_키는_죽어_있다(auth_env):
    h = _admin(auth_env)
    uid = make_user(auth_env.Session, username="u1")
    uh = bearer(login(auth_env.base, "u1"))
    key = requests.post(auth_env.base + "/api/auth/api-keys", headers=uh, json={"name": "k", "expires_days": 30}).json()["key"]
    assert _post(auth_env, h, f"/api/auth/users/{uid}/disable").json()["status"] == "disabled"
    assert _post(auth_env, h, f"/api/auth/users/{uid}/enable").json()["status"] == "active"
    assert requests.get(auth_env.base + "/api/auth/me", headers={"Authorization": "Bearer " + key}).status_code == 401
    assert requests.get(auth_env.base + "/api/auth/me", headers=uh).status_code == 401  # token_version 이 올랐다


def test_자기_자신과_마지막_관리자는_중지_못하고_강등도_못한다(auth_env):
    h = _admin(auth_env)
    s = auth_env.Session()
    boss_id = s.query(User).filter_by(username="boss").one().id
    s.close()
    assert _post(auth_env, h, f"/api/auth/users/{boss_id}/disable").status_code == 409
    r = requests.put(auth_env.base + f"/api/auth/users/{boss_id}/role", headers=h, json={"role": "user"})
    assert r.status_code == 409
    other = make_user(auth_env.Session, username="boss2", role=UserRole.admin)
    assert requests.put(auth_env.base + f"/api/auth/users/{other}/role", headers=h, json={"role": "user"}).status_code == 200


def test_관리자_둘이_서로를_동시에_중지해도_한_명은_남는다(auth_env):
    from routes.auth import disable_user

    a = make_user(auth_env.Session, username="a", role=UserRole.admin)
    b = make_user(auth_env.Session, username="b", role=UserRole.admin)
    barrier = threading.Barrier(2)
    results = []

    def go(actor, target):
        s = auth_env.Session()
        try:
            me = s.get(User, actor)
            barrier.wait()
            disable_user(target, db=s, current_user=me)
            results.append("ok")
        except HTTPException as e:
            results.append(e.status_code)
        finally:
            s.close()

    ts = [threading.Thread(target=go, args=(a, b)), threading.Thread(target=go, args=(b, a))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    s = auth_env.Session()
    active_admins = s.query(User).filter_by(role=UserRole.admin, status=UserStatus.active).count()
    s.close()
    assert active_admins == 1, results
    assert sorted(map(str, results)) == ["409", "ok"]


def test_이메일_해제는_확인_안_된_이메일만(auth_env):
    h = _admin(auth_env)
    squat = make_user(auth_env.Session, username="v@corp.com", email="v@corp.com")
    google = make_user(auth_env.Session, username="g@corp.com", email="g@corp.com", email_verified=True, google_sub="s1")
    r = _post(auth_env, h, f"/api/auth/users/{squat}/release-email")
    assert (r.json()["email"], r.json()["username"]) == (None, f"released-{squat}")
    assert _post(auth_env, h, f"/api/auth/users/{google}/release-email").status_code == 409


def test_목록에_새_칸이_있다(auth_env):
    h = _admin(auth_env)
    make_user(auth_env.Session, username="g@x.com", email="g@x.com", password=None, google_sub="s2")
    rows = {u["username"]: u for u in requests.get(auth_env.base + "/api/auth/users", headers=h).json()}
    assert rows["g@x.com"]["has_password"] is False and rows["g@x.com"]["google_linked"] is True


def test_관리자_초기화는_Google_연결을_끊는다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    uid = make_user(auth_env.Session, username="u", google_sub="attacker-sub")
    sess = requests.Session()
    r = sess.post(auth_env.base + "/api/auth/login", json={"username": "boss", "password": PW})
    assert r.status_code == 200
    r = sess.put(auth_env.base + f"/api/auth/users/{uid}/reset-password",
                 headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 200, r.text
    s = auth_env.Session()
    assert s.get(User, uid).google_sub is None
    s.close()


def test_대기_계정의_복구는_승인도_코드도_막힌다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    uid = make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    s = auth_env.Session()
    req = AccountRequest(request_type=AccountRequestType.reset_password, status=AccountRequestStatus.pending,
                         claimed_username="p@example.com", contact="x")
    s.add(req)
    s.commit()
    rid = req.id
    s.close()
    sess = requests.Session()
    sess.post(auth_env.base + "/api/auth/login", json={"username": "boss", "password": PW})
    r = sess.post(auth_env.base + f"/api/auth/account-requests/{rid}/approve", json={"user_id": uid},
                  headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 409
    r = requests.post(auth_env.base + "/api/auth/reset-password/verify",
                      json={"username": "P@example.com", "code": "whatever-code", "new_password": "NewPassw0rd!"})
    assert r.status_code == 401
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_admin.py`
Expected: FAIL. `/approve` 404 등

- [ ] **Step 3: 구현**

`backend/routes/auth.py` 임포트에 `from services.accounts import active_admin_count, disable` 를 더한다(기존 `lock_accounts, email_taken, find_user_by_identifier` 와 합친다). 아래를 더하고 `update_user_role`, `reset_password` 를 바꾼다.

```python
def _locked_target(db: Session, user_id: int) -> User:
    lock_accounts(db)
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user


def _saved(db: Session, user: User) -> User:
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/approve", response_model=UserResponse)
def approve_user(user_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(role_required("admin"))):
    user = _locked_target(db, user_id)
    if user.status != UserStatus.pending:
        raise HTTPException(status_code=409, detail="승인 대기 중인 계정이 아닙니다.")
    user.status = UserStatus.active
    logger.info("User approved: %s by=%s", user.username, current_user.username)
    return _saved(db, user)


@router.post("/users/{user_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_user(user_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(role_required("admin"))):
    user = _locked_target(db, user_id)
    if user.status != UserStatus.pending:
        raise HTTPException(status_code=409, detail="승인 대기 중인 계정만 거절할 수 있습니다.")
    username = user.username
    db.delete(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="다른 기록에 연결된 계정이라 거절할 수 없습니다. 사용 중지를 쓰세요.")
    logger.info("User rejected (deleted): %s by=%s", username, current_user.username)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/disable", response_model=UserResponse)
def disable_user(user_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(role_required("admin"))):
    user = _locked_target(db, user_id)
    if user.id == current_user.id:
        raise HTTPException(status_code=409, detail="자기 자신은 사용 중지할 수 없습니다.")
    if user.status == UserStatus.disabled:
        raise HTTPException(status_code=409, detail="이미 사용 중지된 계정입니다.")
    if user.role == UserRole.admin and user.status == UserStatus.active and active_admin_count(db, exclude_id=user.id) == 0:
        raise HTTPException(status_code=409, detail="마지막 관리자는 사용 중지할 수 없습니다.")
    disable(db, user)
    logger.info("User disabled: %s by=%s", user.username, current_user.username)
    return _saved(db, user)


@router.post("/users/{user_id}/enable", response_model=UserResponse)
def enable_user(user_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(role_required("admin"))):
    user = _locked_target(db, user_id)
    if user.status != UserStatus.disabled:
        raise HTTPException(status_code=409, detail="사용 중지된 계정이 아닙니다.")
    user.status = UserStatus.active
    logger.info("User enabled: %s by=%s", user.username, current_user.username)
    return _saved(db, user)


@router.post("/users/{user_id}/release-email", response_model=UserResponse)
def release_email(user_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(role_required("admin"))):
    """남의 주소로 먼저 가입해 이메일을 차지한 계정에서 이메일을 뗀다. 진짜 주인이 Google 로 들어올 수 있게."""
    user = _locked_target(db, user_id)
    if user.email_verified:
        raise HTTPException(status_code=409, detail="Google 이 확인한 이메일은 해제할 수 없습니다.")
    released = user.email or (user.username if "@" in user.username else None)
    if not released:
        raise HTTPException(status_code=409, detail="해제할 이메일이 없습니다.")
    user.email = None
    if user.username == released:
        user.username = f"released-{user.id}"
    logger.info("Email released: user_id=%s by=%s", user.id, current_user.username)
    return _saved(db, user)
```

`update_user_role` 의 사용자 조회부터 끝까지를 바꾼다.

```python
    user = _locked_target(db, user_id)
    new_role = UserRole(payload.role)
    # ★마지막 활성 관리자를 강등하면 아무도 관리할 수 없다. 중지 쪽 검사도 이 길로 우회된다.
    if (user.role == UserRole.admin and new_role != UserRole.admin and user.status == UserStatus.active
            and active_admin_count(db, exclude_id=user.id) == 0):
        raise HTTPException(status_code=409, detail="마지막 관리자의 역할은 바꿀 수 없습니다.")
    user.role = new_role
    return _saved(db, user)
```

`reset_password`(관리자 초기화)의 `revoke_user_api_keys(user.id, db)` 아래에 넣는다.

```python
    # 탈취한 쪽이 자기 Google 계정을 연결해 두었으면 그 길이 남는다. 되찾는 국면이라 끊는다.
    user.google_sub = None
```

`backend/routes/account_requests.py`

- 임포트에 `from models import ... UserStatus` 를 더하고(기존 `from models import (...)` 묶음에), `from services.account_policy import normalize_identifier`, `from services.accounts import find_user_by_identifier` 를 더한다.
- `approve_account_request` 의 `if not target:` 블록 아래에 넣는다.

```python
    if target.status != UserStatus.active:
        raise HTTPException(status_code=409, detail="사용 중인 계정만 처리할 수 있습니다.")
```

- `reset_password_with_code` 의 첫 부분과 사용자 조회를 바꾼다. 함수 안의 `payload.username` 을 전부 `ident` 로 바꾼다(제한 확인, 실패 기록, 성공 후 초기화 세 곳).

```python
    ident = normalize_identifier(payload.username)
    _check_rate_limit(request, ident, db)
    fail = HTTPException(status_code=401, detail="코드가 올바르지 않거나 만료되었습니다.")

    user = find_user_by_identifier(db, ident)
    # 대기·중지 계정은 복구 대상이 아니다. 실패 응답은 다른 실패와 같게 둔다.
    if not user or user.status != UserStatus.active:
        verify_password(payload.code, _DUMMY_HASH)  # 타이밍 균일화. 위 _DUMMY_HASH 주석 참고
        _record_failure(request, ident, db)
        raise fail
```

- 성공 경로의 `revoke_user_api_keys(user.id, db)` 아래에 넣는다.

```python
    user.google_sub = None  # 관리자 초기화와 같은 이유
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_auth_admin.py tests_unit/test_auth_login.py tests_unit/test_auth_register.py`
Expected: PASS

Run: (전체 백엔드 테스트)
Expected: PASS(1 skipped)

- [ ] **Step 5: 커밋(로컬)**

```bash
git add backend/routes/auth.py backend/routes/account_requests.py backend/tests_unit/test_auth_admin.py
git commit -m "feat(auth): 관리자 계정 관리(승인, 거절, 중지, 이메일 해제)와 마지막 관리자 보호"
```

---

### Task 6: Google 로그인(시작, 콜백, 연결, 해제)

**Files:**
- Create: `backend/services/google_oauth.py`
- Create: `backend/routes/google_auth.py`
- Modify: `backend/main.py` (라우터 등록)
- Test: `backend/tests_unit/test_google_oauth.py`, `backend/tests_unit/test_google_login.py`

**Interfaces:**
- Consumes: `get_auth_config`, `initial_status`, `AccountRejected`, `safe_next`, `lock_accounts`, `email_taken`, `google_username`, `issue_session`, `get_current_user`, `get_session_user`
- Produces:
  - `google_oauth.Flow(state, nonce, verifier, mode, next, uid=None)`, `GoogleIdentity(sub, email, email_verified, hd, name)`
  - `google_oauth.new_flow(mode, next_path, uid=None) -> Flow`, `code_challenge(verifier) -> str`, `authorize_url(cfg, flow) -> str`, `encode_flow(flow) -> str`, `decode_flow(token) -> Flow`(실패 시 `FlowError`)
  - `google_oauth.exchange_and_verify(cfg, code, verifier, nonce) -> GoogleIdentity`(실패 시 `GoogleAuthError`). 테스트는 이 함수 하나를 바꿔 끼운다.
  - `GET /api/auth/google/start?mode=login|link&next=`, `GET /api/auth/google/callback`, `POST /api/auth/google/unlink`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests_unit/test_google_oauth.py`

```python
"""Google 흐름 도구: PKCE, 인가 URL, 서명 쿠키, 토큰 교환과 검증."""
import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest

from services import google_oauth as g
from services.auth_config import load_auth_config

CFG = load_auth_config({"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "sec",
                        "GOOGLE_REDIRECT_URI": "http://localhost:5173/api/auth/google/callback"})


def test_인가_URL_에_state_nonce_S256_이_실린다():
    flow = g.new_flow("login", "/projects")
    q = parse_qs(urlsplit(g.authorize_url(CFG, flow)).query)
    expected = base64.urlsafe_b64encode(hashlib.sha256(flow.verifier.encode()).digest()).rstrip(b"=").decode()
    assert q["state"] == [flow.state] and q["nonce"] == [flow.nonce]
    assert q["code_challenge"] == [expected] and q["code_challenge_method"] == ["S256"]
    assert q["scope"] == ["openid email profile"] and q["redirect_uri"] == [CFG.google_redirect_uri]


def test_서명_쿠키는_왕복되고_로그인_JWT_와_섞이지_않는다():
    flow = g.new_flow("link", "/projects", uid=7)
    back = g.decode_flow(g.encode_flow(flow))
    assert back == flow
    from auth import create_access_token
    with pytest.raises(g.FlowError):
        g.decode_flow(create_access_token({"sub": "1", "ver": 0}))
    with pytest.raises(g.FlowError):
        g.decode_flow("garbage")


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def test_교환과_검증(monkeypatch):
    seen = {}

    def fake_post(url, data, timeout):
        seen.update(url=url, data=data, timeout=timeout)
        return _Resp(200, {"id_token": "IDT"})

    def fake_verify(token, request, audience, clock_skew_in_seconds):
        seen.update(token=token, audience=audience, skew=clock_skew_in_seconds)
        return {"sub": "123", "email": "A@Corp.com", "email_verified": True, "hd": "corp.com", "name": "A", "nonce": "N"}

    monkeypatch.setattr(g.requests, "post", fake_post)
    import google.oauth2.id_token as idt
    monkeypatch.setattr(idt, "verify_oauth2_token", fake_verify)
    ident = g.exchange_and_verify(CFG, "CODE", "VERIFIER", "N")
    assert ident == g.GoogleIdentity(sub="123", email="a@corp.com", email_verified=True, hd="corp.com", name="A")
    assert seen["data"]["code_verifier"] == "VERIFIER" and seen["timeout"] == g.HTTP_TIMEOUT_SEC
    assert seen["audience"] == "cid" and seen["skew"] == g.CLOCK_SKEW_SEC
    with pytest.raises(g.GoogleAuthError):
        g.exchange_and_verify(CFG, "CODE", "VERIFIER", "OTHER-NONCE")


def test_토큰_주소가_실패하면_GoogleAuthError(monkeypatch):
    monkeypatch.setattr(g.requests, "post", lambda url, data, timeout: _Resp(400, {}))
    with pytest.raises(g.GoogleAuthError):
        g.exchange_and_verify(CFG, "CODE", "V", "N")
```

`backend/tests_unit/test_google_login.py`

```python
"""Google 콜백: 로그인, 신규, 대기, 회사 계정만, 이메일 선점, 상태, 연결, 해제, 동시성."""
import threading
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from auth_helpers import PW, make_user
from models import User, UserRole, UserStatus
from services import google_oauth as g


@pytest.fixture
def gcfg(auth_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    return auth_env


def _identity(monkeypatch, **kw):
    ident = g.GoogleIdentity(sub=kw.get("sub", "sub-1"), email=kw.get("email", "a@gmail.com"),
                             email_verified=kw.get("email_verified", True), hd=kw.get("hd"), name=kw.get("name", "A"))
    monkeypatch.setattr(g, "exchange_and_verify", lambda cfg, code, verifier, nonce: ident)
    return ident


def _start(env, sess=None, **params):
    sess = sess or requests.Session()
    r = sess.get(env.base + "/api/auth/google/start", params=params, allow_redirects=False)
    assert r.status_code == 302, r.text
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    return sess, state


def _callback(env, sess, state, **extra):
    params = {"code": "C", "state": state, **extra}
    return sess.get(env.base + "/api/auth/google/callback", params=params, allow_redirects=False)


def test_시작은_Google_로_보내고_쿠키를_심는다(gcfg):
    r = requests.get(gcfg.base + "/api/auth/google/start", allow_redirects=False)
    assert r.headers["location"].startswith(g.AUTH_URI)
    cookie = r.headers["set-cookie"]
    assert "oauth_flow=" in cookie and "Path=/api/auth/google" in cookie and "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()


def test_Google_이_꺼져_있으면_안내(auth_env):
    r = requests.get(auth_env.base + "/api/auth/google/start", allow_redirects=False)
    assert r.headers["location"] == "/login?error=google_disabled"


def test_새_계정이_만들어지고_로그인된다(gcfg, monkeypatch):
    _identity(monkeypatch, email="new@gmail.com")
    sess, state = _start(gcfg, next="/projects/3")
    r = _callback(gcfg, sess, state)
    assert r.headers["location"] == "/projects/3"
    assert "access_token" in sess.cookies
    s = gcfg.Session()
    u = s.query(User).filter_by(google_sub="sub-1").one()
    assert (u.username, u.email, u.email_verified, u.password_hash, u.status) == (
        "new@gmail.com", "new@gmail.com", True, None, UserStatus.active)
    s.close()


def test_개인_계정은_personal_에서_대기(gcfg, monkeypatch):
    monkeypatch.setenv("AUTH_APPROVAL", "personal")
    _identity(monkeypatch)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=pending"
    assert "access_token" not in sess.cookies


def test_회사_계정은_personal_에서_바로(gcfg, monkeypatch):
    monkeypatch.setenv("AUTH_APPROVAL", "personal")
    monkeypatch.setenv("AUTH_COMPANY_DOMAINS", "corp.com")
    _identity(monkeypatch, email="a@corp.com", hd="corp.com")
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/projects"


def test_회사_계정만이면_개인은_거절(gcfg, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_PERSONAL", "0")
    monkeypatch.setenv("AUTH_COMPANY_DOMAINS", "corp.com")
    _identity(monkeypatch, email="a@corp.com", hd=None)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=company_only"


def test_같은_이메일의_계정이_있으면_만들지_않는다(gcfg, monkeypatch):
    make_user(gcfg.Session, username="a@gmail.com", email="a@gmail.com")
    _identity(monkeypatch)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=email_taken"
    s = gcfg.Session()
    assert s.query(User).filter_by(google_sub="sub-1").first() is None
    s.close()


@pytest.mark.parametrize("st,code", [(UserStatus.pending, "pending"), (UserStatus.disabled, "disabled")])
def test_연결된_계정의_상태(gcfg, monkeypatch, st, code):
    make_user(gcfg.Session, username="x", google_sub="sub-1", status=st)
    _identity(monkeypatch)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == f"/login?error={code}"


def test_확인값이_없거나_다르면_거절(gcfg, monkeypatch):
    _identity(monkeypatch)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, "other-state").headers["location"] == "/login?error=google_state"
    r = requests.get(gcfg.base + "/api/auth/google/callback", params={"code": "C", "state": state}, allow_redirects=False)
    assert r.headers["location"] == "/login?error=google_state"


def test_검증_실패와_이메일_미확인(gcfg, monkeypatch):
    def boom(cfg, code, verifier, nonce):
        raise g.GoogleAuthError("x")
    monkeypatch.setattr(g, "exchange_and_verify", boom)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=google_verify"
    _identity(monkeypatch, email_verified=False)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=google_email_unverified"


def test_취소하면_메시지_없이_로그인_화면(gcfg):
    sess, state = _start(gcfg)
    r = sess.get(gcfg.base + "/api/auth/google/callback", params={"error": "access_denied", "state": state},
                 allow_redirects=False)
    assert r.headers["location"] == "/login"


def test_빈_DB_는_첫_관리자부터(auth_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    _identity(monkeypatch)
    sess, state = _start(auth_env)
    assert _callback(auth_env, sess, state).headers["location"] == "/login?error=bootstrap_required"


def test_사이트_밖_이동_경로는_버린다(gcfg, monkeypatch):
    _identity(monkeypatch)
    sess, state = _start(gcfg, next="/\\evil.com")
    assert _callback(gcfg, sess, state).headers["location"] == "/projects"


def _cookie_login(env, ident):
    sess = requests.Session()
    assert sess.post(env.base + "/api/auth/login", json={"username": ident, "password": PW}).status_code == 200
    return sess


def test_연결과_해제(gcfg, monkeypatch):
    uid = make_user(gcfg.Session, username="me")
    _identity(monkeypatch, email="me@gmail.com")
    sess = _cookie_login(gcfg, "me")
    sess, state = _start(gcfg, sess, mode="link")
    assert _callback(gcfg, sess, state).headers["location"] == "/projects?account=linked"
    s = gcfg.Session()
    u = s.get(User, uid)
    assert (u.google_sub, u.email, u.email_verified) == ("sub-1", "me@gmail.com", True)
    s.close()
    r = sess.post(gcfg.base + "/api/auth/google/unlink", headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 200 and r.json()["google_linked"] is False


def test_비밀번호_없는_계정은_해제_못한다(gcfg, monkeypatch):
    make_user(gcfg.Session, username="g@gmail.com", email="g@gmail.com", password=None, google_sub="sub-1")
    _identity(monkeypatch, email="g@gmail.com")
    sess, state = _start(gcfg)
    _callback(gcfg, sess, state)
    r = sess.post(gcfg.base + "/api/auth/google/unlink", headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 400


def test_연결은_시작한_사람과_세션이_같아야(gcfg, monkeypatch):
    make_user(gcfg.Session, username="alice")
    make_user(gcfg.Session, username="mallory")
    _identity(monkeypatch)
    victim = _cookie_login(gcfg, "alice")
    attacker = _cookie_login(gcfg, "mallory")
    attacker, state = _start(gcfg, attacker, mode="link")
    flow_cookie = attacker.cookies.get("oauth_flow")
    victim.cookies.set("oauth_flow", flow_cookie, domain="127.0.0.1", path="/api/auth/google")
    assert _callback(gcfg, victim, state).headers["location"] == "/projects?account=google_state"


def test_이미_다른_계정에_연결된_Google_계정(gcfg, monkeypatch):
    make_user(gcfg.Session, username="owner", google_sub="sub-1")
    make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    sess, state = _start(gcfg, _cookie_login(gcfg, "me"), mode="link")
    assert _callback(gcfg, sess, state).headers["location"] == "/projects?account=already_linked"


def test_로그인_안_했으면_연결_시작은_401_중지된_세션도(gcfg):
    assert requests.get(gcfg.base + "/api/auth/google/start", params={"mode": "link"},
                        allow_redirects=False).status_code == 401
    uid = make_user(gcfg.Session, username="soon-disabled")
    sess = _cookie_login(gcfg, "soon-disabled")
    s = gcfg.Session()
    s.get(User, uid).status = UserStatus.disabled
    s.commit()
    s.close()
    assert sess.get(gcfg.base + "/api/auth/google/start", params={"mode": "link"},
                    allow_redirects=False).status_code == 401


def test_같은_Google_계정의_동시_첫_로그인은_계정_하나(gcfg, monkeypatch):
    _identity(monkeypatch)
    pairs = [_start(gcfg) for _ in range(2)]
    barrier = threading.Barrier(2)
    out = []

    def go(sess, state):
        barrier.wait()
        out.append(_callback(gcfg, sess, state).headers["location"])

    ts = [threading.Thread(target=go, args=p) for p in pairs]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    s = gcfg.Session()
    assert s.query(User).filter_by(google_sub="sub-1").count() == 1
    s.close()
    assert out == ["/projects", "/projects"]
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_google_oauth.py tests_unit/test_google_login.py`
Expected: FAIL, `ImportError: cannot import name 'google_oauth'`

- [ ] **Step 3: 구현**

`backend/services/google_oauth.py`

```python
"""Google 로그인(OpenID Connect 인가 코드 흐름) 도구.

★확인값(state, nonce, PKCE verifier)은 서버 메모리가 아니라 서명한 쿠키에 담는다. 서버리스는
  요청마다 다른 인스턴스가 받을 수 있다. 쿠키 JWT 에는 use 칸을 넣고 sub 칸을 쓰지 않아
  로그인 JWT 와 섞이지 않는다(get_current_user 는 sub 가 없으면 거절한다).
★테스트는 exchange_and_verify 하나만 바꿔 끼운다. 라우트는 이 모듈을 통해 부른다.
"""
import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import requests
from jose import JWTError, jwt

from auth import ALGORITHM, SECRET_KEY

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
FLOW_COOKIE = "oauth_flow"
FLOW_COOKIE_PATH = "/api/auth/google"
FLOW_TTL_SEC = 600
HTTP_TIMEOUT_SEC = 10
CLOCK_SKEW_SEC = 10
_FLOW_USE = "oauth_flow"


class GoogleAuthError(Exception):
    pass


class FlowError(Exception):
    pass


@dataclass
class Flow:
    state: str
    nonce: str
    verifier: str
    mode: str
    next: str
    uid: Optional[int] = None


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    hd: Optional[str]
    name: str


def new_flow(mode: str, next_path: str, uid: Optional[int] = None) -> Flow:
    return Flow(secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48), mode, next_path, uid)


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorize_url(cfg, flow: Flow) -> str:
    query = {
        "client_id": cfg.google_client_id,
        "redirect_uri": cfg.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": flow.state,
        "nonce": flow.nonce,
        "code_challenge": code_challenge(flow.verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return AUTH_URI + "?" + urlencode(query)


def encode_flow(flow: Flow) -> str:
    claims = {
        "use": _FLOW_USE, "st": flow.state, "nn": flow.nonce, "cv": flow.verifier,
        "md": flow.mode, "nx": flow.next,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=FLOW_TTL_SEC),
    }
    if flow.uid is not None:
        claims["uid"] = flow.uid
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_flow(token: str) -> Flow:
    try:
        c = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise FlowError("서명 또는 만료") from None
    if c.get("use") != _FLOW_USE:
        raise FlowError("용도가 다른 토큰")
    try:
        return Flow(c["st"], c["nn"], c["cv"], c["md"], c["nx"], c.get("uid"))
    except KeyError:
        raise FlowError("칸 누락") from None


def exchange_and_verify(cfg, code: str, verifier: str, nonce: str) -> GoogleIdentity:
    """인가 코드를 교환하고 ID 토큰을 검증한다. 실패는 모두 GoogleAuthError 다.

    ★토큰, 인가 코드, 클라이언트 비밀은 예외 메시지와 로그에 넣지 않는다.
    """
    import google.oauth2.id_token as google_id_token
    from google.auth.transport import requests as google_requests

    try:
        resp = requests.post(TOKEN_URI, data={
            "code": code,
            "client_id": cfg.google_client_id,
            "client_secret": cfg.google_client_secret,
            "redirect_uri": cfg.google_redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }, timeout=HTTP_TIMEOUT_SEC)
    except requests.RequestException:
        raise GoogleAuthError("token_exchange_network") from None
    if resp.status_code != 200:
        raise GoogleAuthError(f"token_exchange_{resp.status_code}")
    raw = (resp.json() or {}).get("id_token")
    if not raw:
        raise GoogleAuthError("no_id_token")

    class _TimeoutRequest(google_requests.Request):
        # ★인증서 조회에 기본 시간 제한(120초)이 걸린다. 서버리스 함수가 그동안 묶이지 않게 줄인다.
        def __call__(self, *args, timeout=None, **kwargs):
            return super().__call__(*args, timeout=timeout or HTTP_TIMEOUT_SEC, **kwargs)

    try:
        claims = google_id_token.verify_oauth2_token(
            raw, _TimeoutRequest(), audience=cfg.google_client_id, clock_skew_in_seconds=CLOCK_SKEW_SEC)
    except Exception:  # noqa: BLE001  google-auth 는 실패를 여러 예외로 낸다. 전부 검증 실패다
        raise GoogleAuthError("id_token_invalid") from None
    if claims.get("nonce") != nonce:
        raise GoogleAuthError("nonce_mismatch")
    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=(claims.get("email") or "").strip().lower(),
        email_verified=bool(claims.get("email_verified")),
        hd=claims.get("hd"),
        name=(claims.get("name") or "")[:100],
    )
```

`backend/routes/google_auth.py`

```python
"""Google 로그인 라우트. 설계: docs/superpowers/specs/2026-10-09-org-account-auth-design.md

★콜백 순서를 고정한다. 쿠키 검증과 토큰 교환(DB 없음) 뒤에 짧은 DB 트랜잭션을 연다. 세션은
  처음 쿼리할 때 연결을 잡으므로, 그 전까지는 외부 호출 동안 DB 연결을 쥐지 않는다.
★모든 리디렉션은 정상 반환이라 get_db 정리가 응답 뒤에 돈다. 잠금을 잡은 경로는 반환 전에
  커밋하거나 되돌린다(SYM-145).
"""
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import COOKIE_SECURE, get_current_user, get_session_user
from database import get_db
from models import User, UserRole, UserStatus
from routes.auth import issue_session
from schemas import UserResponse
from services import google_oauth
from services.account_policy import AccountRejected, initial_status, safe_next
from services.accounts import email_taken, google_username, lock_accounts
from services.auth_config import get_auth_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/google", tags=["auth"])


def _redirect(url: str) -> RedirectResponse:
    resp = RedirectResponse(url, status_code=302)
    resp.delete_cookie(google_oauth.FLOW_COOKIE, path=google_oauth.FLOW_COOKIE_PATH)
    return resp


def _fail(code: str, mode: str = "login") -> RedirectResponse:
    return _redirect(f"/projects?account={code}" if mode == "link" else f"/login?error={code}")


def _session_user(request: Request, db: Session) -> Optional[User]:
    """쿠키 세션의 사용자. 헤더 토큰과 API 키는 받지 않는다(token=None 이면 쿠키만 본다)."""
    try:
        user = get_current_user(request, None, db)
    except HTTPException:
        return None
    if getattr(request.state, "auth_method", None) != "session":
        return None
    return user


@router.get("/start")
def google_start(request: Request, mode: str = "login", next: str = "/projects", db: Session = Depends(get_db)):
    cfg = get_auth_config()
    if mode not in ("login", "link"):
        mode = "login"
    if not cfg.google_enabled:
        return _fail("google_disabled", mode)
    uid = None
    if mode == "link":
        user = _session_user(request, db)
        db.rollback()
        if user is None:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
        uid = user.id
    flow = google_oauth.new_flow(mode, safe_next(next), uid)
    resp = RedirectResponse(google_oauth.authorize_url(cfg, flow), status_code=302)
    resp.set_cookie(google_oauth.FLOW_COOKIE, google_oauth.encode_flow(flow), max_age=google_oauth.FLOW_TTL_SEC,
                    httponly=True, secure=COOKIE_SECURE, samesite="lax", path=google_oauth.FLOW_COOKIE_PATH)
    return resp


@router.get("/callback")
def google_callback(request: Request, code: str = "", state: str = "", error: str = "",
                    db: Session = Depends(get_db)):
    cfg = get_auth_config()
    raw = request.cookies.get(google_oauth.FLOW_COOKIE)
    try:
        flow = google_oauth.decode_flow(raw) if raw else None
    except google_oauth.FlowError:
        flow = None
    mode = flow.mode if flow else "login"

    if error:  # 사용자가 Google 화면에서 취소했다. 메시지 없이 돌려보낸다
        return _redirect("/projects" if mode == "link" else "/login")
    if not cfg.google_enabled:
        return _fail("google_disabled", mode)
    if flow is None or not state or not hmac.compare_digest(state, flow.state):
        return _fail("google_state", mode)
    try:
        ident = google_oauth.exchange_and_verify(cfg, code, flow.verifier, flow.nonce)
    except google_oauth.GoogleAuthError as e:
        logger.warning("Google login verification failed: %s", e)
        return _fail("google_verify", mode)
    if not ident.email_verified:
        return _fail("google_email_unverified", mode)

    try:
        if mode == "link":
            return _link(request, db, cfg, flow, ident)
        return _login(db, cfg, flow, ident)
    finally:
        # 커밋한 경로는 이미 커밋됐다. 남은 트랜잭션과 잠금을 응답 전에 푼다.
        db.rollback()


def _login(db: Session, cfg, flow, ident) -> RedirectResponse:
    lock_accounts(db)
    if db.query(User.id).first() is None:
        return _fail("bootstrap_required")
    try:
        status_for_new = initial_status(cfg, source="google", email=ident.email, hd=ident.hd)
    except AccountRejected as e:
        return _fail(e.code)

    user = db.query(User).filter(User.google_sub == ident.sub).with_for_update().first()
    if user is None:
        if email_taken(db, ident.email):
            return _fail("email_taken")
        user = User(
            username=google_username(db, ident.email), email=ident.email, email_verified=True,
            google_sub=ident.sub, password_hash=None,
            display_name=(ident.name or ident.email.split("@")[0])[:100],
            role=UserRole.user, status=status_for_new, must_change_password=False,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return _fail("email_taken")
        logger.info("Google account created: user_id=%s status=%s", user.id, user.status.value)

    if user.status == UserStatus.pending:
        return _fail("pending")
    if user.status == UserStatus.disabled:
        return _fail("disabled")
    resp = _redirect(flow.next)
    issue_session(resp, user)
    db.commit()
    return resp


def _link(request: Request, db: Session, cfg, flow, ident) -> RedirectResponse:
    current = _session_user(request, db)
    # ★시작한 사람과 지금 세션이 같아야 한다. 남이 시작한 연결 콜백을 피해자에게 열게 해
    #   공격자의 Google 계정을 피해자 계정에 붙이는 공격을 막는다.
    if current is None or flow.uid is None or current.id != flow.uid:
        return _fail("google_state", "link")
    try:
        initial_status(cfg, source="google", email=ident.email, hd=ident.hd)
    except AccountRejected as e:
        return _fail(e.code, "link")

    lock_accounts(db)
    user = db.query(User).filter(User.id == flow.uid).with_for_update().first()
    if user.google_sub == ident.sub:
        return _redirect("/projects?account=linked")
    other = db.query(User.id).filter(User.google_sub == ident.sub, User.id != user.id).first()
    if other or user.google_sub:
        return _fail("already_linked", "link")
    user.google_sub = ident.sub
    if not user.email and not email_taken(db, ident.email, exclude_id=user.id):
        user.email = ident.email
        user.email_verified = True
    db.commit()
    logger.info("Google account linked: user_id=%s", user.id)
    return _redirect("/projects?account=linked")


@router.post("/unlink", response_model=UserResponse)
def google_unlink(db: Session = Depends(get_db), current_user: User = Depends(get_session_user)):
    lock_accounts(db)
    user = db.query(User).filter(User.id == current_user.id).with_for_update().first()
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="비밀번호가 없는 계정은 Google 연결을 해제할 수 없습니다.")
    user.google_sub = None
    db.commit()
    db.refresh(user)
    logger.info("Google account unlinked: user_id=%s", user.id)
    return user
```

`backend/main.py`: 라우트 임포트 묶음에 `from routes import google_auth as google_auth_routes` 를 더하고, `app.include_router(auth_routes.router)` 바로 아래에 `app.include_router(google_auth_routes.router)` 를 더한다.

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest -q tests_unit/test_google_oauth.py tests_unit/test_google_login.py`
Expected: PASS

- [ ] **Step 5: 커밋(로컬)**

```bash
git add backend/services/google_oauth.py backend/routes/google_auth.py backend/main.py backend/tests_unit/test_google_oauth.py backend/tests_unit/test_google_login.py
git commit -m "feat(auth): Google 로그인(시작, 콜백, 연결, 해제)"
```

---

### Task 7: 전체 게이트

**Files:** 없음(검증만)

- [ ] **Step 1: 백엔드 전체**

Run: (Global Constraints 의 전체 백엔드 테스트)
Expected: PASS(1 skipped). 이전 755건보다 늘어난 수를 원장에 적는다.

- [ ] **Step 2: 스크립트 테스트**

Run: `TEST_DATABASE_ADMIN_URL=postgresql+psycopg2://ymtc:ymtc@127.0.0.1:54329/ymtc python -m pytest -q scripts/test_migrate_sqlite_to_pg.py scripts/test_compare_api.py scripts/test_backup_storage.py`
Expected: PASS

- [ ] **Step 3: 의존성 설치 확인(깨끗한 환경 흉내)**

Run: `cd backend && python -c "import google.oauth2.id_token, google.auth.transport.requests, requests; print('ok')"`
Expected: `ok`

- [ ] **Step 4: 원장 기록**

`.superpowers/sdd/2026-10-09-plan4a-auth-backend/progress.md` 에 태스크별 완료 줄과 Ruling 을 남긴다. 푸시는 하지 않는다. 다음은 QA 2인(백엔드 범위) -> 대조 -> 수정 -> 계획 4b.
