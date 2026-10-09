import logging
import secrets
import string
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from database import get_db
from services import rate_limit
from services.client_ip import client_ip
from services.locks import LockNs, advisory_xact_lock, keyed_xact_lock
from models import User, UserRole, UserStatus
from services.account_policy import normalize_identifier
from services.accounts import find_user_by_identifier
from schemas import UserCreate, UserLogin, UserResponse, UserRoleUpdate, Token, PasswordChange
from auth import (
    hash_password, verify_password, create_access_token, get_current_user, role_required,
    get_session_user, revoke_user_api_keys,
    COOKIE_SECURE, COOKIE_SAMESITE, COOKIE_MAX_AGE, ACCESS_TOKEN_EXPIRE_HOURS,
    REMEMBER_ME_DAYS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Rate Limiting (실패한 로그인만 누적, IP+username 기준)
# ★DB 에 센다(services/rate_limit). 프로세스 메모리에 세면 서버리스 인스턴스마다
#   따로 세서 잠금이 사실상 걸리지 않고, 인스턴스가 꺼지면 기록도 사라진다.
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SEC = 300  # 5분
BUCKET_LOGIN = "login"


def _rate_limit_key(request: Request, username: str = "") -> str:
    """IP + username 조합 키"""
    ip = client_ip(request)
    return f"{ip}:{username}" if username else ip


def _check_rate_limit(request: Request, username: str, db: Session):
    """5분간 실패 10회 이상이면 차단

    ★요청 세션이 붙은 DB 에서 센다. 기본 엔진을 쓰면 테스트나 다른 연결 설정에서
      엉뚱한 DB(개발 DB)를 본다.
    ★같은 키를 요청 트랜잭션 동안 잠근다. 잠그지 않으면 9회일 때 동시에 온 요청이
      모두 9 를 보고 통과해 한도를 넘는다. 잠금은 요청이 끝날 때(커밋·롤백) 풀린다.
    """
    key = _rate_limit_key(request, username)
    keyed_xact_lock(db, LockNs.RATE_LIMIT, f"{BUCKET_LOGIN}:{key}")
    if rate_limit.count_recent(BUCKET_LOGIN, key, LOGIN_WINDOW_SEC, engine=db.get_bind()) >= LOGIN_MAX_FAILURES:
        logger.warning("Rate limit exceeded: %s", key)
        raise HTTPException(
            status_code=429,
            detail="로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.",
        )


def _record_failure(request: Request, username: str, db: Session):
    """실패한 로그인만 기록"""
    rate_limit.record(BUCKET_LOGIN, _rate_limit_key(request, username), engine=db.get_bind())


def _clear_failures(request: Request, username: str, db: Session):
    """로그인 성공 시 해당 키의 실패 기록 초기화"""
    rate_limit.clear(BUCKET_LOGIN, _rate_limit_key(request, username), engine=db.get_bind())


@router.get("/check-username")
def check_username(username: str, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.username == username).first() is not None
    return {"available": not exists}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    # ★가입을 전역 잠금으로 줄 세운다. 잠금은 커밋까지 유지되므로 다음 가입은 앞선
    #   가입이 커밋된 뒤에 아이디 중복과 사용자 수를 본다. 삽입 뒤 강등하던 방식은
    #   SQLite 의 쓰기 잠금에 기대고 있어서 PostgreSQL 에서는 서로의 미커밋 행을 못 봤다.
    # bcrypt 는 잠금 밖에서 한다. 잠금 구간이 길면 가입 연타에 모든 가입이 줄을 선다.
    password_hash = hash_password(payload.password)
    advisory_xact_lock(db, LockNs.ACCOUNTS)
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
        password_hash=password_hash,
        display_name=payload.display_name,
        role=initial_role,
        must_change_password=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    # ★API 키로 부르면 아래 버전 올림이 그 사용자의 웹 세션을 전부 끊는다. 세션으로만 받는다.
    current_user: User = Depends(get_session_user),
):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    # ★쿠키만 지우면 같은 토큰을 Authorization 헤더에 실어 계속 쓸 수 있다.
    #   이 제품은 헤더 인증도 받으므로(`_extract_token`) 그쪽이 그대로 열린다.
    #   버전을 올려 실제로 끊는다. 그 계정의 다른 기기 세션도 함께 끊긴다.
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    logger.info("User logged out: %s", current_user.username)
    return {"message": "로그아웃 되었습니다."}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/change-password", response_model=UserResponse)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_session_user),
):
    if not current_user.password_hash:
        raise HTTPException(status_code=400, detail="비밀번호가 없는 계정입니다.")
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="새 비밀번호가 현재와 동일합니다.")

    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    # 비밀번호를 바꾼 이유가 유출이면, 옛 토큰이 살아 있는 한 바꾼 의미가 없다
    current_user.token_version = (current_user.token_version or 0) + 1
    revoke_user_api_keys(current_user.id, db)
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    # ★임시 비밀번호를 응답으로 돌려준다. 유출된 관리자 키로 남의 계정을 가져갈 수 없게 세션으로만 받는다.
    get_session_user(request, current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    alphabet = string.ascii_letters + string.digits
    temp_pw = "".join(secrets.choice(alphabet) for _ in range(12))

    user.password_hash = hash_password(temp_pw)
    user.must_change_password = True
    # 관리자가 초기화하는 상황은 계정을 되찾는 국면이다. 옛 토큰을 같이 끊는다
    user.token_version = (user.token_version or 0) + 1
    revoke_user_api_keys(user.id, db)
    db.commit()
    logger.info("Password reset by admin for user: %s", user.username)
    return {"temp_password": temp_pw}
