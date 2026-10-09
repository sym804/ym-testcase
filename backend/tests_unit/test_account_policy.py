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
