# .env 로딩 - 아래 os.getenv 호출보다 먼저 실행되어야 한다
import env_setup  # noqa: F401

import hashlib
import hmac
import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, List

import bcrypt

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole, UserStatus, Project, ProjectMember, ProjectRole

logger = logging.getLogger(__name__)

_ENV = os.getenv("ENV", "development")
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if _ENV == "production":
        raise RuntimeError("SECRET_KEY environment variable must be set in production")
    # 개발 환경: 프로세스마다 랜덤 키 생성 (재시작 시 기존 토큰 무효화)
    SECRET_KEY = secrets.token_urlsafe(64)
    logger.warning("SECRET_KEY not set - using random key (dev only)")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "72"))
#: 로그인 유지를 켰을 때의 만료. 예전 값 3650일은 유출을 되돌릴 수 없다는 뜻이었다.
REMEMBER_ME_DAYS = int(os.getenv("REMEMBER_ME_DAYS", "30"))

# Cookie 설정
COOKIE_SECURE = _ENV == "production"
COOKIE_SAMESITE = "lax"
COOKIE_MAX_AGE = ACCESS_TOKEN_EXPIRE_HOURS * 3600

# Swagger UI용 (OpenAPI docs에서 Authorization 버튼 표시)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# System role hierarchy - higher index = more privileged
SYSTEM_ROLE_HIERARCHY: List[str] = ["user", "qa_manager", "admin"]

# Project role hierarchy - higher index = more privileged
PROJECT_ROLE_HIERARCHY: List[str] = ["viewer", "tester", "admin"]


#: bcrypt 가 받는 비밀번호 최대 바이트. bcrypt 5.0 부터 넘으면 hashpw · checkpw 가 ValueError 를 낸다.
BCRYPT_MAX_BYTES = 72
PASSWORD_TOO_LONG_DETAIL = "비밀번호는 72바이트 이하로 입력해 주세요(영문 72자, 한글 24자까지)."


def password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > BCRYPT_MAX_BYTES


def ensure_password_fits(password: str) -> None:
    """새 비밀번호(가입 · 변경 · 초기화)가 bcrypt 상한을 넘으면 400.

    ★글자 수가 아니라 바이트로 잰다. 한글은 한 글자가 3바이트라 25자면 넘는다. 예전에는
      hashpw 의 ValueError 가 그대로 500 이 됐다. 잘라서 해시하지 않는다. 자르면 73바이트째
      부터는 무엇을 쳐도 같은 비밀번호가 되어, 사용자가 정한 것보다 약해진다.
    """
    if password_too_long(password):
        raise HTTPException(status_code=400, detail=PASSWORD_TOO_LONG_DETAIL)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


_DUMMY_HASH: Optional[str] = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
    return _DUMMY_HASH


def verify_password(plain: str, hashed: Optional[str]) -> bool:
    # ★해시가 없으면(계정 없음, Google 전용 계정) 더미 해시로 한 번 대조하고 거짓을 낸다.
    #   bcrypt 를 건너뛰면 응답 시간으로 계정 유무가 새고, None.encode() 는 500 이 된다.
    # ★72바이트를 넘는 입력은 어떤 해시와도 맞을 수 없다(넘는 값은 저장되지 않는다). 틀린
    #   비밀번호와 같게 거짓을 내고, 응답 시간도 같게 더미 대조를 한 번 지불한다. 예전에는
    #   checkpw 의 ValueError 로 500 이 났고 실패 횟수도 세지 않았다.
    pw = plain.encode("utf-8")
    if len(pw) > BCRYPT_MAX_BYTES:
        bcrypt.checkpw(pw[:BCRYPT_MAX_BYTES], _dummy_hash().encode("utf-8"))
        return False
    if not hashed:
        bcrypt.checkpw(pw, _dummy_hash().encode("utf-8"))
        return False
    return bcrypt.checkpw(pw, hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _extract_token(request: Request, bearer_token: Optional[str] = None) -> tuple[str, str]:
    """쿠키 또는 Authorization 헤더에서 JWT 추출. (token, source) 반환."""
    # 1) Authorization 헤더 (Swagger UI, API 클라이언트)
    if bearer_token:
        return bearer_token, "header"
    # 2) httpOnly 쿠키
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token, "cookie"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _check_csrf(request: Request, auth_source: str):
    """쿠키 인증 시 상태 변경 요청에 CSRF 검증."""
    if auth_source != "cookie":
        return  # Authorization 헤더 인증은 CSRF 면역
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    csrf_cookie = request.cookies.get("csrf_token")
    csrf_header = request.headers.get("X-CSRF-Token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=403, detail="CSRF 토큰이 유효하지 않습니다.")


#: API 키 원문의 머리. JWT 는 "eyJ" 로 시작하므로 겹치지 않는다.
API_KEY_PREFIX = "ymtc_"
#: last_used_at 을 이보다 자주 쓰지 않는다. 읽기 요청이 전부 쓰기가 되지 않게.
API_KEY_TOUCH_INTERVAL = timedelta(minutes=1)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """(원문, key_id). 원문은 `ymtc_<key_id 8자>_<비밀 43자>` 이다."""
    key_id = secrets.token_hex(4)
    return f"{API_KEY_PREFIX}{key_id}_{secrets.token_urlsafe(32)}", key_id


def _user_from_api_key(raw: str, db: Session) -> User:
    """API 키로 사용자를 찾는다. 어느 단계에서 실패했는지는 응답에 드러내지 않는다."""
    from models import ApiKey, now_kst

    denied = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 API 키입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    parts = raw.split("_", 2)
    if len(parts) != 3 or not parts[1]:
        raise denied
    key = db.query(ApiKey).filter(ApiKey.key_id == parts[1]).first()
    # ★해시는 상수 시간으로 비교한다. 행이 없을 때도 같은 비교를 한 번 해서
    #   key_id 의 존재 여부가 응답 시간으로 새지 않게 한다.
    expected = key.key_hash if key else "0" * 64
    if not hmac.compare_digest(hash_api_key(raw), expected) or key is None:
        raise denied
    now = now_kst()
    if key.revoked_at is not None or (key.expires_at is not None and key.expires_at <= now):
        raise denied
    user = db.query(User).filter(User.id == key.user_id).first()
    # ★중지·대기 계정의 키도 막는다. 이 경로는 get_current_user 의 상태 검사보다 먼저 반환한다.
    if user is None or user.status != UserStatus.active:
        raise denied
    if key.last_used_at is None or now - key.last_used_at >= API_KEY_TOUCH_INTERVAL:
        key.last_used_at = now
        db.commit()
    return user


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    jwt_token, auth_source = _extract_token(request, token)

    # API 키는 Authorization 헤더로만 받는다. 헤더 인증이라 CSRF 대상이 아니다.
    if auth_source == "header" and jwt_token.startswith(API_KEY_PREFIX):
        request.state.auth_method = "api_key"
        return _user_from_api_key(jwt_token, db)
    request.state.auth_method = "session"

    # CSRF 검증 (쿠키 인증 + 상태 변경 요청)
    _check_csrf(request, auth_source)

    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    # ★토큰 버전 대조. 이 줄이 유일한 폐기 경로다.
    #   `ver` 가 없는 토큰은 이 기능 이전에 발급된 것이다. 서명은 유효하므로
    #   여기서 막지 않으면 10년짜리 옛 토큰이 그대로 통한다.
    #   DB 값을 0 으로 정규화한다. NULL 인 행이 있으면 `None != None` 이 거짓이 되어
    #   `ver` 없는 토큰이 통과한다. 마이그레이션상 NULL 은 없어야 하지만, 이 비교가
    #   폐기의 유일한 관문이라 열려 있는 쪽으로 틀리게 두지 않는다.
    if payload.get("ver") != (user.token_version or 0):
        raise credentials_exception
    if user.status != UserStatus.active:
        raise credentials_exception
    # ★임시 비밀번호(관리자 초기화) 상태면 변경 창이 쓰는 경로만 연다. 화면만 막으면 임시
    #   비밀번호를 본 사람이 API 로 바로 쓸 수 있다. API 키는 초기화 때 모두 폐기되고, 새 키는
    #   세션으로만 만들므로 이 경로(세션)만 보면 된다.
    route_path = getattr(request.scope.get("route"), "path", None) or request.url.path
    if user.must_change_password and route_path not in _PASSWORD_CHANGE_PATHS:
        raise HTTPException(status_code=403, detail=MUST_CHANGE_PASSWORD_DETAIL)

    return user


#: 임시 비밀번호 상태에서도 열어 두는 경로. 변경 창은 사용자 확인, 변경, 로그아웃만 쓴다.
_PASSWORD_CHANGE_PATHS = frozenset({"/api/auth/me", "/api/auth/change-password", "/api/auth/logout"})
MUST_CHANGE_PASSWORD_DETAIL = "비밀번호를 먼저 변경해 주세요."


def revoke_user_api_keys(user_id: int, db: Session) -> int:
    """그 사용자의 살아 있는 키를 모두 폐기한다. 커밋은 부른 쪽이 한다.

    비밀번호가 바뀌는 자리(본인 변경 · 관리자 초기화 · 계정 복구)에서 부른다. 계정을 되찾는
    국면인데 탈취한 쪽이 만들어 둔 키가 살아 있으면 비밀번호를 바꾼 의미가 없다.
    """
    from models import ApiKey, now_kst

    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
        .update({ApiKey.revoked_at: now_kst()}, synchronize_session=False)
    )


def get_session_user(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """로그인 세션으로만 허용하는 작업. API 키로 부르면 403.

    키 발급 · 폐기, 비밀번호 변경, 로그아웃이 여기에 걸린다. 키 하나가 새 키를 찍어 내거나,
    로그아웃으로 그 사용자의 웹 세션을 전부 끊을 수 있으면 유출된 키의 피해가 키 밖으로 번진다.
    """
    if getattr(request.state, "auth_method", None) == "api_key":
        raise HTTPException(status_code=403, detail="API 키로는 할 수 없는 작업입니다. 로그인해서 진행해 주세요.")
    return current_user


def role_required(minimum_role: str):
    """Dependency factory that enforces a minimum system role level."""
    min_index = SYSTEM_ROLE_HIERARCHY.index(minimum_role)

    def _check(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.value if isinstance(current_user.role, UserRole) else current_user.role
        user_index = SYSTEM_ROLE_HIERARCHY.index(user_role)
        if user_index < min_index:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum_role}' or higher required",
            )
        return current_user

    return _check


def admin_session_required(
    request: Request,
    current_user: User = Depends(role_required("admin")),
) -> User:
    """계정 관리(승인, 역할, 중지, 삭제 등)는 관리자 로그인 세션으로만 한다.

    API 키는 사용자 권한을 통째로 갖는다. 관리자 키가 새면 자기 계정을 승인하고 관리자로 올려,
    키를 폐기해도 관리자 계정이 남는다. 그래서 계정을 바꾸는 작업은 키로 받지 않는다.
    """
    return get_session_user(request, current_user)


def get_project_role(
    project_id: int, user: User, db: Session
) -> Optional[str]:
    """사용자의 프로젝트 내 역할 반환. 접근 불가시 None."""
    user_role = user.role.value if isinstance(user.role, UserRole) else user.role

    # 시스템 admin / qa_manager는 모든 프로젝트에 admin 접근
    if user_role in ("admin", "qa_manager"):
        return "admin"

    # ★생성자라는 이유로 admin 을 주지 않는다. 생성자는 만들 때 admin 멤버로 등록되므로 멤버 표가
    #   정본이다. 따로 보면 강등된 뒤 관리자가 멤버 역할을 낮추거나 빼도 계속 admin 이었다.
    #   목록(projects.py), 개요(overview.py), 검색(search.py)도 같은 규칙이다.
    project = db.query(Project).filter(Project.id == project_id).first()

    # 멤버 테이블 조회
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id,
    ).first()
    if member:
        return member.role.value if isinstance(member.role, ProjectRole) else member.role

    # 공개 프로젝트는 비멤버도 viewer 접근 허용
    if project and not project.is_private:
        return "viewer"

    return None


def check_project_access(minimum_role: str = "viewer"):
    """프로젝트 접근 권한 체크 dependency factory.

    minimum_role 값:
      - "viewer": 읽기 전용 접근 (admin/qa_manager → 전체, 멤버 → 모두, 비멤버 → 거부)
      - "tester": 테스트 수행 권한 (프로젝트 역할 tester 이상)
      - "admin": 프로젝트 관리 권한 (프로젝트 역할 admin)
    """

    def _check(
        project_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        proj_role = get_project_role(project_id, current_user, db)

        # 프로젝트에 접근 권한이 없으면 거부
        if proj_role is None:
            raise HTTPException(status_code=403, detail="이 프로젝트에 접근 권한이 없습니다.")

        # viewer(읽기)는 멤버이기만 하면 허용
        if minimum_role == "viewer":
            return current_user

        # tester/admin 권한 체크: 프로젝트 역할 계층으로 비교
        min_index = PROJECT_ROLE_HIERARCHY.index(minimum_role)
        role_index = PROJECT_ROLE_HIERARCHY.index(proj_role)
        if role_index >= min_index:
            return current_user

        raise HTTPException(status_code=403, detail="이 작업을 수행할 권한이 없습니다.")

    return _check
