import hmac
import logging
import os
import secrets
import string
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from services import rate_limit
from services.client_ip import client_ip
from services.locks import LockNs, keyed_xact_lock
from models import User, UserRole, UserStatus
from services.account_policy import AccountRejected, initial_status, normalize_email, normalize_identifier
from services.accounts import (
    active_admin_count, activity_refs, clear_google, disable, email_taken, find_user_by_identifier, lock_accounts,
)
from services.auth_config import get_auth_config
from schemas import UserCreate, UserLogin, UserResponse, UserRoleUpdate, Token, PasswordChange
from auth import (
    hash_password, verify_password, ensure_password_fits, create_access_token, get_current_user, role_required,
    get_session_user, revoke_user_api_keys, admin_session_required,
    COOKIE_SECURE, COOKIE_SAMESITE, COOKIE_MAX_AGE, ACCESS_TOKEN_EXPIRE_HOURS,
    REMEMBER_ME_DAYS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Rate Limiting (실패한 로그인만 누적)
# ★DB 에 센다(services/rate_limit). 프로세스 메모리에 세면 서버리스 인스턴스마다
#   따로 세서 잠금이 사실상 걸리지 않고, 인스턴스가 꺼지면 기록도 사라진다.
# ★키 축이 셋이다(SYM-216). IP+아이디 하나만 두면 IP 를 바꿔 같은 계정을 다시 노리거나,
#   한 IP 에서 아이디만 바꿔 같은 비밀번호를 돌리는 스프레이가 아이디마다 새로 허용된다.
#   - IP+아이디: 5분 10회. 오타 낸 사용자를 짧게 막는 기존 제한
#   - 계정: 1시간 LOGIN_ACCOUNT_MAX_PER_HOUR(기본 50). IP 를 바꿔도 같은 계정이면 같이 센다
#   - IP: 1시간 LOGIN_IP_MAX_FAILURES_PER_HOUR(기본 100). 아이디를 바꿔도 같은 IP 면 같이 센다
# ★계정 상한은 공격자가 일부러 채워 그 계정의 비밀번호 로그인을 최대 한 시간 막을 수 있다.
#   감수한다. Google 로그인은 이 경로를 타지 않으므로 그쪽으로는 들어올 수 있다. 관리자 비밀번호
#   초기화도 이 잠금을 풀지만, 기존 세션·API 키·Google 연결을 함께 끊는다.
# ★TOO_MANY_LOGINS 는 "잠시 후" 로 둔다. 어느 축에 걸렸는지 알려 주면 어떤 상한을 채웠는지가
#   드러나고, 5분 축에 걸린 대부분의 사용자에게는 이 문구가 맞다.
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SEC = 300  # 5분
LOGIN_LONG_WINDOW_SEC = 3600  # 계정·IP 상한의 창
BUCKET_LOGIN = "login"
BUCKET_LOGIN_ACCOUNT = "login_account"
BUCKET_LOGIN_IP = "login_ip"
TOO_MANY_LOGINS = "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요."
TOO_MANY_PASSWORD_CHECKS = "비밀번호 확인 시도가 너무 많습니다. 최대 1시간 뒤 다시 시도해 주세요."


def _account_limit() -> int:
    return int(os.getenv("LOGIN_ACCOUNT_MAX_PER_HOUR", "50"))


def _ip_limit() -> int:
    return int(os.getenv("LOGIN_IP_MAX_FAILURES_PER_HOUR", "100"))


def _rate_limit_key(request: Request, username: str = "") -> str:
    """IP + username 조합 키"""
    ip = client_ip(request)
    return f"{ip}:{username}" if username else ip


def _account_key(db: Session, ident: str) -> str:
    """계정 상한 키. 있는 계정은 id 로 센다. 아이디와 이메일 중 무엇으로 시도해도 같은 키다.
    없는 아이디는 정규화한 입력으로 센다."""
    user = find_user_by_identifier(db, ident)
    return f"user:{user.id}" if user else f"ident:{ident}"


def _limits(request: Request, ident: str, db: Session):
    """요청 트랜잭션에서 잠그고 세는 키 (버킷, 키, 창, 상한). 잠그는 순서가 늘 같아야 교착이 없다.
    IP 상한은 여기 없다. 아래 _reserve_ip 가 따로 다룬다."""
    return [
        (BUCKET_LOGIN_ACCOUNT, _account_key(db, ident), LOGIN_LONG_WINDOW_SEC, _account_limit()),
        (BUCKET_LOGIN, _rate_limit_key(request, ident), LOGIN_WINDOW_SEC, LOGIN_MAX_FAILURES),
    ]


def _enforce(db: Session, limits, detail: str = TOO_MANY_LOGINS) -> None:
    engine = db.get_bind()
    for bucket, key, window, limit in limits:
        keyed_xact_lock(db, LockNs.RATE_LIMIT, f"{bucket}:{key}")
        if rate_limit.count_recent(bucket, key, window, engine=engine) >= limit:
            logger.warning("Rate limit exceeded: %s %s", bucket, key)
            raise HTTPException(status_code=429, detail=detail)


def _record(db: Session, limits) -> None:
    engine = db.get_bind()
    for bucket, key, _window, _limit in limits:
        rate_limit.record(bucket, key, engine=engine)


def _reserve_ip(request: Request, db: Session) -> None:
    """IP 상한. 시도를 먼저 기록하고(확인과 기록이 한 번에) 성공하면 지운다.

    ★요청 트랜잭션에서 이 키를 잠그면 한 사무실(NAT 하나)의 로그인이 bcrypt 한 번씩 줄을 서서
      출근 시간에 잠금 대기 시간을 넘긴다. 잠그지 않고 세기만 하면 동시 요청이 모두 같은 수를 보고
      통과해 상한을 넘긴다(QA1 지적). 그래서 확인과 기록만 짧은 별도 트랜잭션으로 묶는다.
    """
    event_id = rate_limit.reserve(BUCKET_LOGIN_IP, client_ip(request), LOGIN_LONG_WINDOW_SEC, _ip_limit(),
                                  engine=db.get_bind())
    if event_id is None:
        logger.warning("Rate limit exceeded: %s %s", BUCKET_LOGIN_IP, client_ip(request))
        raise HTTPException(status_code=429, detail=TOO_MANY_LOGINS)
    request.state.login_ip_event = event_id


def _check_rate_limit(request: Request, username: str, db: Session):
    """IP+아이디 5분 10회, 계정 1시간, IP 1시간 상한 중 하나라도 넘으면 차단

    ★요청 세션이 붙은 DB 에서 센다. 기본 엔진을 쓰면 테스트나 다른 연결 설정에서
      엉뚱한 DB(개발 DB)를 본다.
    ★계정·IP+아이디 키는 요청 트랜잭션 동안 잠근다. 잠그지 않으면 9회일 때 동시에 온 요청이
      모두 9 를 보고 통과해 한도를 넘는다. 잠금은 요청이 끝날 때(커밋·롤백) 풀린다.
      IP 키는 잠그지 않고 _reserve_ip 가 별도 짧은 트랜잭션에서 확인과 기록을 한 번에 한다.
    """
    _enforce(db, _limits(request, username, db))
    _reserve_ip(request, db)


def _record_failure(request: Request, username: str, db: Session):
    """실패한 로그인만 기록. IP 축은 _reserve_ip 가 이미 남겼다."""
    _record(db, _limits(request, username, db))


def _clear_failures(request: Request, username: str, db: Session):
    """로그인 성공 시 IP+아이디 키의 실패 기록만 초기화

    ★IP 상한은 지우지 않는다. 지우면 스프레이하는 쪽이 자기 계정으로 한 번씩 로그인해 상한을
      계속 비운다. 계정 상한도 지우지 않는다. 한 시간 50회는 본인 오타로 닿는 수가 아니다.
    """
    rate_limit.clear(BUCKET_LOGIN, _rate_limit_key(request, username), engine=db.get_bind())
    # 이 요청이 _reserve_ip 로 남긴 시도 한 건만 지운다. 맞혔으니 실패가 아니다.
    event_id = getattr(request.state, "login_ip_event", None)
    if event_id is not None:
        rate_limit.release(event_id, engine=db.get_bind())
        request.state.login_ip_event = None


def _password_change_limits(user: User) -> list:
    """비밀번호 변경의 현재 비밀번호 대조는 로그인과 같은 계정 상한에 센다.
    세션을 손에 넣은 쪽이 이 경로로 비밀번호를 맞혀 보는 것을 막는다."""
    return [(BUCKET_LOGIN_ACCOUNT, f"user:{user.id}", LOGIN_LONG_WINDOW_SEC, _account_limit())]


BUCKET_REGISTER = "register"
REGISTER_WINDOW_SEC = 3600


def _check_register_limit(request: Request, db: Session) -> None:
    """IP 하나의 가입 시도를 센다(성공·실패 무관). 인터넷에 열린 진입점이라 bcrypt 비용과
    승인 대기 목록 스팸을 막는다. 비밀번호 찾기 접수 제한과 같은 방식이다."""
    key = client_ip(request)
    keyed_xact_lock(db, LockNs.RATE_LIMIT, f"{BUCKET_REGISTER}:{key}")
    engine = db.get_bind()
    # 기본 30. 사무실 하나(NAT 하나)에서 팀이 한꺼번에 이메일로 가입하면 10건으로는 막혔다.
    limit = int(os.getenv("REGISTER_MAX_PER_HOUR", "30"))
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
        # bytes 로 비교한다. str 끼리는 ASCII 가 아닌 문자가 오면 TypeError(500) 다.
        given = (payload.bootstrap_token or "").encode("utf-8")
        if not cfg.bootstrap_token or not hmac.compare_digest(given, cfg.bootstrap_token.encode("utf-8")):
            raise HTTPException(status_code=403, detail="첫 관리자 토큰이 올바르지 않습니다.")
    email = None
    if payload.username and payload.username.strip():
        # 로그인은 '@' 가 든 입력을 소문자로 찾는다. 저장도 같은 규칙으로 해야 들어올 수 있다.
        username = normalize_identifier(payload.username)
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
    if not payload.display_name.strip():
        raise HTTPException(status_code=422, detail="표시 이름을 입력해 주세요.")
    ensure_password_fits(payload.password)  # bcrypt 72바이트 상한. 넘으면 400
    # ★횟수 제한을 bcrypt 보다 먼저 본다. 한도를 넘긴 요청이 bcrypt 비용을 쓰지 않게 한다.
    #   제한 잠금은 같은 IP 끼리만 줄을 세우므로 그 안에서 bcrypt 를 해도 다른 가입을 막지 않는다.
    _check_register_limit(request, db)
    # bcrypt 는 계정 잠금 밖에서 한다. 잠금 구간이 길면 가입 연타에 모든 가입이 줄을 선다.
    password_hash = hash_password(payload.password)
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
    ensure_password_fits(payload.new_password)  # bcrypt 72바이트 상한. 넘으면 400
    limits = _password_change_limits(current_user)
    _enforce(db, limits, TOO_MANY_PASSWORD_CHECKS)
    if not verify_password(payload.current_password, current_user.password_hash):
        _record(db, limits)
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="새 비밀번호가 현재와 동일합니다.")

    new_hash = hash_password(payload.new_password)
    checked_hash = current_user.password_hash
    version_seen = current_user.token_version or 0
    # ★사용 중지·초기화와 같은 계정 잠금으로 줄 세운다. 잠금 없이 API 키부터 바꾸면 사용 중지
    #   (사용자 행 -> 키 행)와 반대 순서로 행을 잡아 교착된다. bcrypt 는 잠금 밖에서 끝냈다.
    lock_accounts(db)
    current_user = _fresh(db, current_user.id)
    # 잠금을 기다리는 사이 중지·초기화·로그아웃으로 세션이 끊겼으면 진행하지 않는다.
    if (current_user is None or current_user.status != UserStatus.active
            or (current_user.token_version or 0) != version_seen):
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    if current_user.password_hash != checked_hash:
        raise HTTPException(status_code=409, detail="다른 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요.")
    current_user.password_hash = new_hash
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


def _fresh(db: Session, user_id: int) -> Optional[User]:
    """행을 잠그고 DB 의 최신 값으로 다시 읽는다.

    ★populate_existing 이 없으면 세션에 이미 있는 객체(인증에서 읽은 사용자 등)의 옛 값을 그대로
      돌려준다. 잠금을 기다리는 사이 다른 요청이 커밋한 변경을 못 보고 덮어쓰게 된다.
    """
    return db.query(User).filter(User.id == user_id).with_for_update().populate_existing().first()


def _locked_target(db: Session, user_id: int, actor: User) -> User:
    actor_id = actor.id
    lock_accounts(db)
    # 잠금을 기다리는 사이 행위자가 강등·중지됐을 수 있다. 잠금 안에서 다시 확인한다.
    fresh_actor = _fresh(db, actor_id)
    if fresh_actor is None or fresh_actor.role != UserRole.admin or fresh_actor.status != UserStatus.active:
        raise HTTPException(status_code=403, detail="Role 'admin' or higher required")
    user = _fresh(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user


def _saved(db: Session, user: User) -> User:
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/approve", response_model=UserResponse)
def approve_user(user_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(admin_session_required)):
    user = _locked_target(db, user_id, current_user)
    if user.status != UserStatus.pending:
        raise HTTPException(status_code=409, detail="승인 대기 중인 계정이 아닙니다.")
    user.status = UserStatus.active
    logger.info("User approved: %s by=%s", user.username, current_user.username)
    return _saved(db, user)


@router.post("/users/{user_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_user(user_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(admin_session_required)):
    user = _locked_target(db, user_id, current_user)
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
                 current_user: User = Depends(admin_session_required)):
    user = _locked_target(db, user_id, current_user)
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
                current_user: User = Depends(admin_session_required)):
    user = _locked_target(db, user_id, current_user)
    if user.status != UserStatus.disabled:
        raise HTTPException(status_code=409, detail="사용 중지된 계정이 아닙니다.")
    user.status = UserStatus.active
    logger.info("User enabled: %s by=%s", user.username, current_user.username)
    return _saved(db, user)


@router.post("/users/{user_id}/release-email", response_model=UserResponse)
def release_email(user_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(admin_session_required)):
    """남의 주소로 먼저 가입해 이메일을 차지한 계정에서 이메일을 뗀다. 진짜 주인이 Google 로 들어올 수 있게."""
    user = _locked_target(db, user_id, current_user)
    if user.id == current_user.id:
        raise HTTPException(status_code=409, detail="자기 자신의 이메일은 해제할 수 없습니다.")
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


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(admin_session_required)):
    """작업 기록이 하나도 없는 계정만 지운다. 실수로 생긴 빈 계정 정리용. 기록이 있으면 사용 중지를 쓴다."""
    user = _locked_target(db, user_id, current_user)
    if user.id == current_user.id:
        raise HTTPException(status_code=409, detail="자기 자신은 삭제할 수 없습니다.")
    if user.role == UserRole.admin and user.status == UserStatus.active and active_admin_count(db, exclude_id=user.id) == 0:
        raise HTTPException(status_code=409, detail="마지막 관리자는 삭제할 수 없습니다.")
    refs = activity_refs(db, user.id)
    if refs:
        logger.info("User delete refused: %s refs=%s", user.username, refs)
        raise HTTPException(status_code=409, detail="작업 기록이 있는 계정은 삭제할 수 없습니다. 사용 중지를 쓰세요.")
    username = user.username
    db.delete(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="작업 기록이 있는 계정은 삭제할 수 없습니다. 사용 중지를 쓰세요.")
    logger.info("User deleted: %s by=%s", username, current_user.username)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_session_required),
):
    valid_roles = [r.value for r in UserRole]
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {valid_roles}",
        )

    user = _locked_target(db, user_id, current_user)
    new_role = UserRole(payload.role)
    # ★마지막 활성 관리자를 강등하면 아무도 관리할 수 없다. 중지 쪽 검사도 이 길로 우회된다.
    if (user.role == UserRole.admin and new_role != UserRole.admin and user.status == UserStatus.active
            and active_admin_count(db, exclude_id=user.id) == 0):
        raise HTTPException(status_code=409, detail="마지막 관리자의 역할은 바꿀 수 없습니다.")
    user.role = new_role
    return _saved(db, user)


@router.put("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    # ★임시 비밀번호를 응답으로 돌려준다. 유출된 관리자 키로 남의 계정을 가져갈 수 없게 세션으로만 받는다.
    get_session_user(request, current_user)
    alphabet = string.ascii_letters + string.digits
    temp_pw = "".join(secrets.choice(alphabet) for _ in range(12))
    temp_hash = hash_password(temp_pw)
    user = _locked_target(db, user_id, current_user)

    user.password_hash = temp_hash
    user.must_change_password = True
    # 관리자가 초기화하는 상황은 계정을 되찾는 국면이다. 옛 토큰을 같이 끊는다
    user.token_version = (user.token_version or 0) + 1
    revoke_user_api_keys(user.id, db)
    # 탈취한 쪽이 자기 Google 계정을 연결해 두었으면 그 길이 남는다. 되찾는 국면이라 끊는다.
    clear_google(user)
    db.commit()
    # 공격자가 계정 상한을 채워 둔 계정이면 임시 비밀번호로도 한 시간 동안 못 들어온다.
    # 관리자 초기화가 그 잠금을 푸는 수단이다.
    rate_limit.clear(BUCKET_LOGIN_ACCOUNT, f"user:{user.id}", engine=db.get_bind())
    logger.info("Password reset by admin for user: %s", user.username)
    return {"temp_password": temp_pw}
