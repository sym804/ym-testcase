"""로그인 실패 상한은 IP+아이디 조합 하나가 아니다(SYM-216).

- 계정 상한: IP 를 바꿔 가며 같은 계정에 시도해도 계정 하나에 1시간 상한이 걸린다.
  아이디와 이메일 중 무엇으로 시도해도 같은 계정으로 센다.
- IP 상한: 한 IP 에서 아이디만 바꿔 가며 시도하는 비밀번호 스프레이를 막는다.
- 비밀번호 변경의 현재 비밀번호 대조도 계정 상한에 같이 센다.

IP 는 TRUSTED_PROXY_HEADER 로 지정한 헤더에서 읽는다(services/client_ip). 테스트는 그 헤더로
요청마다 IP 를 바꾼다.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

from auth_helpers import PW, bearer, make_user
from models import UserRole

IP_HEADER = "x-test-ip"


def _login(base, ident, password, ip):
    return requests.post(base + "/api/auth/login", json={"username": ident, "password": password},
                         headers={IP_HEADER: ip})


def _env(monkeypatch, account=None, ip=None):
    monkeypatch.setenv("TRUSTED_PROXY_HEADER", IP_HEADER)
    if account is not None:
        monkeypatch.setenv("LOGIN_ACCOUNT_MAX_PER_HOUR", str(account))
    if ip is not None:
        monkeypatch.setenv("LOGIN_IP_MAX_FAILURES_PER_HOUR", str(ip))


def test_IP_를_바꿔도_계정_상한에_걸린다(auth_env, monkeypatch):
    _env(monkeypatch, account=4, ip=1000)
    make_user(auth_env.Session, username="victim")
    codes = [_login(auth_env.base, "victim", "wrong-password", f"10.0.0.{i}").status_code for i in range(4)]
    assert codes == [401] * 4
    # 처음 보는 IP 에서 맞는 비밀번호로 와도 막힌다. 맞혔을 때만 열어 주면 상한이 의미가 없다.
    r = _login(auth_env.base, "victim", PW, "10.0.0.99")
    assert r.status_code == 429
    assert r.json()["detail"] == "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요."


def test_아이디와_이메일을_번갈아도_같은_계정으로_센다(auth_env, monkeypatch):
    _env(monkeypatch, account=4, ip=1000)
    make_user(auth_env.Session, username="dual", email="dual@example.com")
    idents = ["dual", "dual@example.com"]
    codes = [_login(auth_env.base, idents[i % 2], "wrong-password", f"10.1.0.{i}").status_code for i in range(5)]
    assert codes == [401, 401, 401, 401, 429]


def test_한_IP_에서_아이디만_바꾸는_스프레이는_IP_상한에_걸린다(auth_env, monkeypatch):
    _env(monkeypatch, account=1000, ip=5)
    codes = [_login(auth_env.base, f"nobody{i}", "Spring2026!", "10.2.0.1").status_code for i in range(6)]
    assert codes == [401] * 5 + [429]
    # 다른 IP 는 영향이 없다
    assert _login(auth_env.base, "nobody-x", "Spring2026!", "10.2.0.2").status_code == 401


def test_자기_계정_로그인_성공으로_IP_실패_기록을_지울_수_없다(auth_env, monkeypatch):
    """IP 상한을 성공 때 지우면, 스프레이하는 쪽이 자기 계정으로 한 번씩 로그인해 상한을 계속 비운다."""
    _env(monkeypatch, account=1000, ip=3)
    make_user(auth_env.Session, username="attacker")
    assert _login(auth_env.base, "target1", "guess", "10.3.0.1").status_code == 401
    assert _login(auth_env.base, "target2", "guess", "10.3.0.1").status_code == 401
    assert _login(auth_env.base, "attacker", PW, "10.3.0.1").status_code == 200
    assert _login(auth_env.base, "target3", "guess", "10.3.0.1").status_code == 401
    assert _login(auth_env.base, "target4", "guess", "10.3.0.1").status_code == 429


def test_계정이_막혀도_다른_계정은_로그인된다(auth_env, monkeypatch):
    _env(monkeypatch, account=2, ip=1000)
    make_user(auth_env.Session, username="locked")
    make_user(auth_env.Session, username="bystander")
    for i in range(2):
        _login(auth_env.base, "locked", "wrong-password", f"10.4.0.{i}")
    assert _login(auth_env.base, "locked", PW, "10.4.0.9").status_code == 429
    assert _login(auth_env.base, "bystander", PW, "10.4.0.9").status_code == 200


def test_비밀번호_변경의_현재_비밀번호_대조도_계정_상한에_센다(auth_env, monkeypatch):
    _env(monkeypatch, account=3, ip=1000)
    make_user(auth_env.Session, username="changer")
    h = bearer(_login(auth_env.base, "changer", PW, "10.5.0.1"))

    def change(current):
        return requests.put(auth_env.base + "/api/auth/change-password", headers={**h, IP_HEADER: "10.5.0.1"},
                            json={"current_password": current, "new_password": "NewPassw0rd!"})

    assert [change("wrong-password").status_code for _ in range(3)] == [400] * 3
    # 맞는 현재 비밀번호도 상한을 넘으면 막힌다
    r = change(PW)
    assert (r.status_code, r.json()["detail"]) == (429, "비밀번호 확인 시도가 너무 많습니다. 최대 1시간 뒤 다시 시도해 주세요.")
    # 같은 계정 상한이라 로그인도 막힌다
    assert _login(auth_env.base, "changer", PW, "10.5.0.2").status_code == 429


def _burst(n, fn):
    """n 개 요청을 barrier 로 맞춰 한꺼번에 보낸다.

    ★n 은 10 이하로 둔다. 요청 하나가 세션 연결과 횟수 기록 연결을 같이 쓰므로, 테스트 엔진 풀
      (기본 5+10) 보다 동시 요청이 많으면 모두 두 번째 연결을 기다리며 멈춘다(풀 고갈).
    """
    barrier = threading.Barrier(n)

    def run(i):
        barrier.wait()
        return fn(i)

    with ThreadPoolExecutor(max_workers=n) as ex:
        return list(ex.map(run, range(n)))


def test_동시에_보낸_스프레이도_IP_상한을_넘지_못한다(auth_env, monkeypatch):
    """확인 뒤에 기록하면 동시 요청이 모두 같은 수를 보고 통과한다(QA1 지적)."""
    _env(monkeypatch, account=1000, ip=3)
    codes = _burst(10, lambda i: _login(auth_env.base, f"spray{i}", "Spring2026!", "10.6.0.1").status_code)
    assert sorted(codes) == [401] * 3 + [429] * 7, codes


def test_IP_를_바꿔_동시에_보내도_계정_상한을_넘지_못한다(auth_env, monkeypatch):
    _env(monkeypatch, account=3, ip=1000)
    make_user(auth_env.Session, username="burst-victim")
    codes = _burst(10, lambda i: _login(auth_env.base, "burst-victim", "wrong-password", f"10.8.0.{i}").status_code)
    assert sorted(codes) == [401] * 3 + [429] * 7, codes


def test_로그인에_성공해도_계정_실패_기록은_남는다(auth_env, monkeypatch):
    """계정 상한을 성공 때 지우면, 비밀번호를 아는 쪽(본인)과 맞히려는 쪽이 같은 계정을 두고
    번갈아 시도할 때 상한이 계속 비워진다."""
    _env(monkeypatch, account=3, ip=1000)
    make_user(auth_env.Session, username="keeps")
    assert _login(auth_env.base, "keeps", "wrong-password", "10.9.0.1").status_code == 401
    assert _login(auth_env.base, "keeps", "wrong-password", "10.9.0.2").status_code == 401
    assert _login(auth_env.base, "keeps", PW, "10.9.0.3").status_code == 200
    assert _login(auth_env.base, "keeps", "wrong-password", "10.9.0.4").status_code == 401
    assert _login(auth_env.base, "keeps", PW, "10.9.0.5").status_code == 429


def test_코드_재설정_실패도_같은_계정_상한에_센다(auth_env, monkeypatch):
    """코드 재설정은 로그인 없이 부를 수 있다. 여기서 비밀번호 대신 코드를 맞혀 보는 시도도 계정 단위로 센다."""
    _env(monkeypatch, account=3, ip=1000)
    make_user(auth_env.Session, username="resetter")
    for i in range(3):
        r = requests.post(auth_env.base + "/api/auth/reset-password/verify", headers={IP_HEADER: f"10.10.0.{i}"},
                          json={"username": "resetter", "code": "000000", "new_password": "NewPassw0rd!"})
        assert r.status_code == 401
    assert _login(auth_env.base, "resetter", PW, "10.10.0.9").status_code == 429


def test_관리자가_비밀번호를_초기화하면_계정_잠금이_풀린다(auth_env, monkeypatch):
    _env(monkeypatch, account=2, ip=1000)
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    uid = make_user(auth_env.Session, username="locked-out")
    for i in range(2):
        _login(auth_env.base, "locked-out", "wrong-password", f"10.11.0.{i}")
    assert _login(auth_env.base, "locked-out", PW, "10.11.0.9").status_code == 429
    h = bearer(_login(auth_env.base, "boss", PW, "10.11.1.1"))
    r = requests.put(auth_env.base + f"/api/auth/users/{uid}/reset-password", headers=h)
    assert r.status_code == 200, r.text
    assert _login(auth_env.base, "locked-out", r.json()["temp_password"], "10.11.0.9").status_code == 200


def test_성공한_시도는_IP_실패로_남지_않는다(auth_env, monkeypatch):
    """IP 축은 시도를 먼저 기록하고 성공하면 지운다. 정상 로그인이 쌓여 사무실 전체가 막히면 안 된다."""
    _env(monkeypatch, account=1000, ip=3)
    make_user(auth_env.Session, username="office")
    for _ in range(6):
        assert _login(auth_env.base, "office", PW, "10.7.0.1").status_code == 200


def test_상한_기본값(monkeypatch):
    from routes.auth import _account_limit, _ip_limit
    monkeypatch.delenv("LOGIN_ACCOUNT_MAX_PER_HOUR", raising=False)
    monkeypatch.delenv("LOGIN_IP_MAX_FAILURES_PER_HOUR", raising=False)
    assert _account_limit() == 50
    assert _ip_limit() == 100
