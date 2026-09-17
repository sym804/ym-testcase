"""토큰 폐기 - 비밀번호를 바꿔도 옛 토큰이 살아 있던 자리

JWT 는 발급하면 만료까지 서버가 막을 수 없다. 그래서 만료를 길게 잡으면
유출된 토큰을 되돌릴 방법이 사라진다. 로그인 유지가 3650일이었고 로그아웃은
쿠키만 지웠으므로, 본문으로 받은 access_token 하나로 10년을 쓸 수 있었다.

사용자 행에 버전을 두고 토큰에 그 값을 실으면, 비밀번호를 바꾸는 것만으로
그 사용자의 토큰이 전부 한 번에 막힌다.

실행: cd backend && python -m pytest test_token_revocation.py -v
"""
import os
import secrets

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

import dev_db_guard

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(username, password, remember_me=False):
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": username, "password": password, "remember_me": remember_me},
    )
    return r


@pytest.fixture
def victim():
    """비밀번호를 바꿔도 되는 일회용 계정.

    사용자 삭제 API 가 없으므로 테스트마다 새 이름을 쓴다. 같은 이름을 재사용하면
    앞 테스트가 바꾼 비밀번호 때문에 다음 테스트의 로그인이 어긋난다.
    """
    admin = login("admin", ADMIN_PW)
    assert admin.status_code == 200, admin.text
    admin_token = admin.json()["access_token"]

    username = f"__revoke_{secrets.token_hex(4)}__"
    first_pw = "revoke1234"
    r = requests.post(
        f"{BASE}/api/auth/register",
        json={"username": username, "password": first_pw, "display_name": "Revoke Target"},
    )
    assert r.status_code == 201, r.text

    yield {"id": r.json()["id"], "username": username, "password": first_pw, "admin": admin_token}


def test_비밀번호를_바꾸면_그_전_토큰이_막힌다(victim):
    old = login(victim["username"], victim["password"]).json()["access_token"]
    assert requests.get(f"{BASE}/api/auth/me", headers=auth(old)).status_code == 200

    r = requests.put(
        f"{BASE}/api/auth/change-password",
        headers=auth(old),
        json={"current_password": victim["password"], "new_password": "changed1234"},
    )
    assert r.status_code == 200, r.text

    after = requests.get(f"{BASE}/api/auth/me", headers=auth(old))
    assert after.status_code == 401, (
        f"비밀번호를 바꿨는데 옛 토큰이 아직 통한다: {after.status_code}"
    )


def test_비밀번호를_바꾸면_새_토큰은_통한다(victim):
    old = login(victim["username"], victim["password"]).json()["access_token"]
    requests.put(
        f"{BASE}/api/auth/change-password",
        headers=auth(old),
        json={"current_password": victim["password"], "new_password": "changed1234"},
    )

    fresh = login(victim["username"], "changed1234")
    assert fresh.status_code == 200, fresh.text
    token = fresh.json()["access_token"]
    assert requests.get(f"{BASE}/api/auth/me", headers=auth(token)).status_code == 200


def test_관리자가_비밀번호를_초기화하면_그_사용자_토큰이_막힌다(victim):
    old = login(victim["username"], victim["password"]).json()["access_token"]
    assert requests.get(f"{BASE}/api/auth/me", headers=auth(old)).status_code == 200

    r = requests.put(
        f"{BASE}/api/auth/users/{victim['id']}/reset-password",
        headers=auth(victim["admin"]),
    )
    assert r.status_code == 200, r.text

    after = requests.get(f"{BASE}/api/auth/me", headers=auth(old))
    assert after.status_code == 401, (
        f"관리자가 초기화했는데 옛 토큰이 아직 통한다: {after.status_code}"
    )


def test_로그아웃하면_그_토큰이_막힌다(victim):
    """쿠키만 지우면 Bearer 로 들고 있던 같은 토큰이 그대로 통한다.

    이 제품은 헤더 인증도 받으므로(`_extract_token`), 로그아웃이 쿠키만 지우는 한
    "폐기할 수단이 없다"는 문제가 로그아웃 자리에 그대로 남는다.
    """
    token = login(victim["username"], victim["password"]).json()["access_token"]
    assert requests.get(f"{BASE}/api/auth/me", headers=auth(token)).status_code == 200

    out = requests.post(f"{BASE}/api/auth/logout", headers=auth(token))
    assert out.status_code == 200, out.text

    after = requests.get(f"{BASE}/api/auth/me", headers=auth(token))
    assert after.status_code == 401, f"로그아웃했는데 토큰이 아직 통한다: {after.status_code}"


def test_남의_비밀번호_변경은_내_토큰을_건드리지_않는다(victim):
    """버전을 사용자별로 두지 않고 전역으로 두면 여기서 걸린다."""
    mine = login("admin", ADMIN_PW).json()["access_token"]
    other = login(victim["username"], victim["password"]).json()["access_token"]

    requests.put(
        f"{BASE}/api/auth/change-password",
        headers=auth(other),
        json={"current_password": victim["password"], "new_password": "changed1234"},
    )

    assert requests.get(f"{BASE}/api/auth/me", headers=auth(mine)).status_code == 200


def test_로그인_유지의_만료가_31일을_넘지_않는다():
    """무기한에 가까운 토큰은 유출되면 되돌릴 수 없다."""
    from datetime import datetime, timezone

    from jose import jwt

    r = login("admin", ADMIN_PW, remember_me=True)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    claims = jwt.get_unverified_claims(token)
    exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    days = (exp - datetime.now(timezone.utc)).days
    assert days <= 31, f"로그인 유지 토큰이 {days}일 유효하다"


def test_토큰에_버전_클레임이_실린다():
    r = login("admin", ADMIN_PW)
    from jose import jwt

    claims = jwt.get_unverified_claims(r.json()["access_token"])
    assert "ver" in claims, f"버전 클레임이 없다: {sorted(claims)}"


def test_버전_클레임이_없는_옛_토큰은_막힌다():
    """배포 전에 발급된 토큰도 서명은 유효하다. 그것까지 막아야 폐기가 성립한다."""
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from datetime import datetime, timedelta

    from jose import jwt

    import auth as auth_mod

    users = requests.get(
        f"{BASE}/api/auth/users", headers=auth(login("admin", ADMIN_PW).json()["access_token"])
    ).json()
    admin_id = next(u["id"] for u in users if u["username"] == "admin")

    legacy = jwt.encode(
        {"sub": str(admin_id), "role": "admin", "exp": datetime.utcnow() + timedelta(hours=1)},
        auth_mod.SECRET_KEY,
        algorithm=auth_mod.ALGORITHM,
    )
    r = requests.get(f"{BASE}/api/auth/me", headers=auth(legacy))
    assert r.status_code == 401, f"버전 없는 토큰이 통한다: {r.status_code}"
