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
