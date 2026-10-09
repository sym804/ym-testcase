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
from services.account_policy import EMAIL_MAX, AccountRejected, initial_status, safe_next
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
            # 페이지 이동으로 여는 주소라 JSON 401 대신 로그인 화면으로 보낸다.
            return _redirect("/login")
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
    # bytes 로 비교한다. str 끼리는 ASCII 가 아닌 문자가 오면 TypeError(500) 다.
    if flow is None or not state or not hmac.compare_digest(state.encode("utf-8"), flow.state.encode("utf-8")):
        return _fail("google_state", mode)
    try:
        ident = google_oauth.exchange_and_verify(cfg, code, flow.verifier, flow.nonce)
    except google_oauth.GoogleAuthError as e:
        logger.warning("Google login verification failed: %s", e)
        return _fail("google_verify", mode)
    if not ident.email_verified:
        return _fail("google_email_unverified", mode)
    if not ident.email or len(ident.email) > EMAIL_MAX:
        # users.email 이 100자다. 넘는 주소는 저장하다 500 이 나므로 검증 실패로 돌려보낸다.
        logger.warning("Google login rejected: email length %s", len(ident.email or ""))
        return _fail("google_verify", mode)

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

    user = db.query(User).filter(User.google_sub == ident.sub).with_for_update().populate_existing().first()
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

    version_seen = current.token_version or 0
    lock_accounts(db)
    user = db.query(User).filter(User.id == flow.uid).with_for_update().populate_existing().first()
    # ★잠금을 기다리는 사이 비밀번호 초기화·복구·중지가 끝났을 수 있다. 세션을 다시 확인한다.
    if user is None or user.status != UserStatus.active or (user.token_version or 0) != version_seen:
        return _fail("google_state", "link")
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
    user = db.query(User).filter(User.id == current_user.id).with_for_update().populate_existing().first()
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="비밀번호가 없는 계정은 Google 연결을 해제할 수 없습니다.")
    user.google_sub = None
    db.commit()
    db.refresh(user)
    logger.info("Google account unlinked: user_id=%s", user.id)
    return user
