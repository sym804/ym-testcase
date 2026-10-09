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
