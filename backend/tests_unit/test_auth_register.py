"""첫 관리자, 이메일 가입 정책, 가입 횟수 제한, 설정 조회."""
import requests

from auth_helpers import PW, make_user
from models import UserRole


def _reg(base, **body):
    body.setdefault("password", PW)
    body.setdefault("display_name", "N")
    return requests.post(base + "/api/auth/register", json=body)


def test_빈_DB_는_첫_관리자_화면이고_아이디로_만든다(auth_env):
    assert requests.get(auth_env.base + "/api/auth/config").json() == {"google_enabled": False, "signup_mode": "bootstrap"}
    r = _reg(auth_env.base, username="boss")
    assert r.status_code == 201, r.text
    assert (r.json()["role"], r.json()["status"]) == ("admin", "active")
    assert requests.get(auth_env.base + "/api/auth/config").json()["signup_mode"] == "email"
    assert requests.get(auth_env.base + "/api/auth/check-username", params={"username": "x"}).status_code == 404


def test_운영의_첫_관리자는_토큰이_맞아야(auth_env, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("BOOTSTRAP_TOKEN", "t0k")
    r = _reg(auth_env.base, username="boss", bootstrap_token="nope")
    assert (r.status_code, r.json()["detail"]) == (403, "첫 관리자 토큰이 올바르지 않습니다.")
    assert _reg(auth_env.base, username="boss", bootstrap_token="t0k").status_code == 201


def test_운영인데_토큰이_설정돼_있지_않으면_첫_관리자를_못_만든다(auth_env, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    assert _reg(auth_env.base, username="boss").status_code == 403


def test_사용자가_있으면_이메일이_필요하다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    r = _reg(auth_env.base, username="someone")
    assert (r.status_code, r.json()["detail"]) == (400, "이메일로 가입해 주세요.")


def test_이메일_가입은_정규화되고_그_이메일로_로그인된다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    r = _reg(auth_env.base, email="  Ym@Example.COM ")
    assert r.status_code == 201, r.text
    assert (r.json()["username"], r.json()["email"], r.json()["status"]) == ("ym@example.com", "ym@example.com", "active")
    assert requests.post(auth_env.base + "/api/auth/login", json={"username": "ym@example.com", "password": PW}).status_code == 200


def test_중복_이메일은_400(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin, email="ym@example.com")
    r = _reg(auth_env.base, email="YM@example.com")
    assert (r.status_code, r.json()["detail"]) == (400, "이미 가입된 이메일입니다.")


def test_personal_이면_이메일_가입은_대기(auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_APPROVAL", "personal")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    assert _reg(auth_env.base, email="a@corp.com").json()["status"] == "pending"


def test_회사_계정만이면_다른_도메인은_403_회사_도메인도_대기(auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_PERSONAL", "0")
    monkeypatch.setenv("AUTH_COMPANY_DOMAINS", "corp.com")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    r = _reg(auth_env.base, email="a@gmail.com")
    assert (r.status_code, r.json()["detail"]) == (403, "회사 이메일로만 가입할 수 있습니다.")
    assert _reg(auth_env.base, email="b@corp.com").json()["status"] == "pending"


def test_가입_횟수_제한(auth_env, monkeypatch):
    monkeypatch.setenv("REGISTER_MAX_PER_HOUR", "3")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    codes = [_reg(auth_env.base, email=f"u{i}@example.com").status_code for i in range(4)]
    assert codes == [201, 201, 201, 429]


def test_가입_횟수_기본_상한은_IP_당_시간당_30건(auth_env):
    """사무실 하나(NAT 하나)에서 팀이 한꺼번에 이메일로 가입해도 막히지 않게 10건에서 30건으로 올렸다."""
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    codes = [_reg(auth_env.base, email=f"d{i}@example.com").status_code for i in range(31)]
    assert codes[:30] == [201] * 30
    assert codes[30] == 429


def test_구글_설정이_있으면_config_가_알린다(auth_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "s")
    assert requests.get(auth_env.base + "/api/auth/config").json()["google_enabled"] is True
