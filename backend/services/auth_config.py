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
