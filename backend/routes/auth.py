import logging
import secrets
import string
import time
from collections import defaultdict
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole
from schemas import UserCreate, UserLogin, UserResponse, UserRoleUpdate, Token, PasswordChange
from auth import hash_password, verify_password, create_access_token, get_current_user, role_required

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Rate Limiting (실패한 로그인만 누적, IP+username 기준)
_login_failures: dict[str, list[float]] = defaultdict(list)
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SEC = 300  # 5분
_MAX_RATE_LIMIT_KEYS = 10000  # 메모리 보호: 최대 키 수
_last_purge_time: float = 0.0


def _rate_limit_key(request: Request, username: str = "") -> str:
    """IP + username 조합 키"""
    client_ip = request.client.host if request.client else "unknown"
    return f"{client_ip}:{username}" if username else client_ip


def _purge_expired_keys():
    """만료된 키를 주기적으로 정리 (60초마다)"""
    global _last_purge_time
    now = time.time()
    if now - _last_purge_time < 60:
        return
    _last_purge_time = now
    expired = [
        k for k, timestamps in _login_failures.items()
        if not timestamps or now - max(timestamps) >= LOGIN_WINDOW_SEC
    ]
    for k in expired:
        del _login_failures[k]


def _check_rate_limit(request: Request, username: str = ""):
    """5분간 실패 10회 이상이면 차단"""
    _purge_expired_keys()
    key = _rate_limit_key(request, username)
    now = time.time()
    # 윈도우 밖의 기록 제거
    _login_failures[key] = [t for t in _login_failures[key] if now - t < LOGIN_WINDOW_SEC]
    if len(_login_failures[key]) >= LOGIN_MAX_FAILURES:
        logger.warning("Rate limit exceeded: %s", key)
        raise HTTPException(
            status_code=429,
            detail="로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.",
        )


def _record_failure(request: Request, username: str = ""):
    """실패한 로그인만 기록"""
    # 키 수 제한: 초과 시 가장 오래된 키부터 제거
    # TODO: 현재 O(n) min() 탐색이지만, _MAX_RATE_LIMIT_KEYS=10000 수준에서는 문제 없음.
    #       대규모 환경에서는 OrderedDict 또는 TTL 캐시로 교체 검토.
    if len(_login_failures) >= _MAX_RATE_LIMIT_KEYS:
        oldest_key = min(_login_failures, key=lambda k: _login_failures[k][-1] if _login_failures[k] else 0)
        del _login_failures[oldest_key]
    key = _rate_limit_key(request, username)
    _login_failures[key].append(time.time())


def _clear_failures(request: Request, username: str = ""):
    """로그인 성공 시 해당 키의 실패 기록 초기화"""
    key = _rate_limit_key(request, username)
    _login_failures.pop(key, None)


@router.get("/check-username")
def check_username(username: str, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.username == username).first() is not None
    return {"available": not exists}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 아이디입니다.",
        )

    # First user becomes admin automatically
    user_count = db.query(User).count()
    is_first_user = user_count == 0
    initial_role = UserRole.admin if is_first_user else UserRole.user

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=initial_role,
        must_change_password=is_first_user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(request, payload.username)

    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        client_ip = request.client.host if request.client else "unknown"
        logger.warning("Failed login attempt: user=%s ip=%s", payload.username, client_ip)
        _record_failure(request, payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    # 성공 시 실패 카운트 초기화
    _clear_failures(request, payload.username)
    logger.info("User logged in: %s", user.username)
    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return Token(access_token=token, must_change_password=user.must_change_password)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/change-password", response_model=UserResponse)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="새 비밀번호가 현재와 동일합니다.")

    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    db.commit()
    db.refresh(current_user)
    logger.info("Password changed: %s", current_user.username)
    return current_user


@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("qa_manager")),
):
    return db.query(User).order_by(User.id).all()


@router.put("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    valid_roles = [r.value for r in UserRole]
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {valid_roles}",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    user.role = UserRole(payload.role)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    alphabet = string.ascii_letters + string.digits
    temp_pw = "".join(secrets.choice(alphabet) for _ in range(12))

    user.password_hash = hash_password(temp_pw)
    user.must_change_password = True
    db.commit()
    logger.info("Password reset by admin for user: %s", user.username)
    return {"temp_password": temp_pw}
