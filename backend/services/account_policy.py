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
