"""이메일 로그인, 횟수 제한 키 정규화, 상태 사유, 비밀번호 없는 계정, 중지의 효력."""
import requests

from auth_helpers import PW, bearer, login, make_user
from models import User, UserStatus


def test_이메일로_대소문자_무관하게_로그인(auth_env):
    make_user(auth_env.Session, username="ym@example.com", email="ym@example.com")
    assert login(auth_env.base, "  YM@Example.com ").status_code == 200


def test_골뱅이가_든_옛_아이디도_로그인된다(auth_env):
    make_user(auth_env.Session, username="old@name")
    assert login(auth_env.base, "old@name").status_code == 200


def test_대소문자를_바꿔도_같은_횟수_제한에_묶인다(auth_env):
    make_user(auth_env.Session, username="ym@example.com", email="ym@example.com")
    variants = ["ym@example.com", "YM@example.com", "Ym@Example.com", "yM@EXAMPLE.COM"]
    codes = [login(auth_env.base, variants[i % 4], "wrong-password").status_code for i in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_대기와_중지_사유는_비밀번호가_맞을_때만(auth_env):
    make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    make_user(auth_env.Session, username="d@example.com", email="d@example.com", status=UserStatus.disabled)
    assert login(auth_env.base, "p@example.com", "wrong-password").status_code == 401
    assert login(auth_env.base, "d@example.com", "wrong-password").status_code == 401
    r = login(auth_env.base, "p@example.com")
    assert (r.status_code, r.json()["detail"]) == (403, "관리자 승인을 기다리는 중입니다.")
    r = login(auth_env.base, "d@example.com")
    assert (r.status_code, r.json()["detail"]) == (403, "사용이 중지된 계정입니다.")


def test_비밀번호_없는_계정은_401_이고_변경은_400(auth_env):
    make_user(auth_env.Session, username="g@example.com", email="g@example.com", password=None, google_sub="sub-1")
    assert login(auth_env.base, "g@example.com", "anything-at-all").status_code == 401
    uid = make_user(auth_env.Session, username="has-pw")
    h = bearer(login(auth_env.base, "has-pw"))
    s = auth_env.Session()
    s.get(User, uid).password_hash = None
    s.commit()
    s.close()
    r = requests.put(auth_env.base + "/api/auth/change-password", headers=h,
                     json={"current_password": PW, "new_password": "NewPassw0rd!"})
    # 세션 토큰은 비밀번호를 지우기 전에 받았다. 비밀번호가 없으면 400
    assert (r.status_code, r.json()["detail"]) == (400, "비밀번호가 없는 계정입니다.")


def test_중지하면_JWT_와_API_키가_바로_막힌다(auth_env):
    uid = make_user(auth_env.Session, username="victim")
    h = bearer(login(auth_env.base, "victim"))
    key = requests.post(auth_env.base + "/api/auth/api-keys", headers=h,
                        json={"name": "k", "expires_days": 30}).json()["key"]
    assert requests.get(auth_env.base + "/api/auth/me", headers={"Authorization": "Bearer " + key}).status_code == 200
    s = auth_env.Session()
    s.get(User, uid).status = UserStatus.disabled
    s.commit()
    s.close()
    assert requests.get(auth_env.base + "/api/auth/me", headers=h).status_code == 401
    assert requests.get(auth_env.base + "/api/auth/me", headers={"Authorization": "Bearer " + key}).status_code == 401


def test_me_응답에_새_칸이_있다(auth_env):
    make_user(auth_env.Session, username="ym@example.com", email="ym@example.com")
    body = requests.get(auth_env.base + "/api/auth/me", headers=bearer(login(auth_env.base, "ym@example.com"))).json()
    assert body["email"] == "ym@example.com"
    assert body["status"] == "active"
    assert body["has_password"] is True and body["google_linked"] is False
