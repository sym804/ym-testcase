"""임시 비밀번호(관리자 초기화) 상태에서는 비밀번호 변경 전까지 다른 API 를 막는다.

전에는 화면만 변경 창을 띄우고 서버는 검사하지 않았다. 전달 과정에서 임시 비밀번호를 본
사람이 화면을 거치지 않고 API 로 데이터를 읽거나 쓸 수 있었다.
"""
import requests

from auth_helpers import PW, bearer, login, make_user
from models import User


def _temp_user(env):
    uid = make_user(env.Session, username="tmp")
    with env.Session() as s:
        s.get(User, uid).must_change_password = True
        s.commit()
    return uid


def test_임시_비밀번호_상태는_변경_전까지_다른_API_가_403(auth_env):
    _temp_user(auth_env)
    h = bearer(login(auth_env.base, "tmp"))

    r = requests.get(auth_env.base + "/api/projects", headers=h)
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "비밀번호를 먼저 변경해 주세요."
    # 변경 창이 쓰는 것은 열려 있다
    assert requests.get(auth_env.base + "/api/auth/me", headers=h).status_code == 200


def test_비밀번호를_바꾸면_다시_로그인해_쓸_수_있다(auth_env):
    _temp_user(auth_env)
    h = bearer(login(auth_env.base, "tmp"))
    r = requests.put(auth_env.base + "/api/auth/change-password", headers=h,
                     json={"current_password": PW, "new_password": "Changed1!pw"})
    assert r.status_code == 200, r.text

    h2 = bearer(login(auth_env.base, "tmp", "Changed1!pw"))
    assert requests.get(auth_env.base + "/api/projects", headers=h2).status_code == 200


def test_임시_비밀번호_상태에서도_로그아웃은_된다(auth_env):
    _temp_user(auth_env)
    h = bearer(login(auth_env.base, "tmp"))
    assert requests.post(auth_env.base + "/api/auth/logout", headers=h).status_code == 200
