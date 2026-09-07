"""테스트가 개발용 DB 에 붙지 않는지 확인한다.

과거 사고(2026-09-07): `tests_unit/test_tc_id_dedup.py` 가 모듈 수준에서
`from models import ...` 를 한다. pytest 는 수집 단계에서 테스트 모듈을 전부
임포트하므로, 그 시점에 `database.py` 가 함께 임포트되며 `engine` 이 기본값인
개발용 `./tc_manager.db` 에 묶였다. `conftest.py::_server` 가
`os.environ["DATABASE_URL"]` 을 임시 DB 로 바꾸는 것은 수집이 끝난 뒤라 늦었다.

그 결과 `main.py` 의 lifespan(실행 시점에 `os.getenv` 를 읽는다)은 임시 DB 로
마이그레이션하고, 앱 세션은 개발 DB 를 봤다. CI 에서는 테이블이 없는 빈 DB 를
보고 `_purge_old_deleted_testcases()` 가 터져 서버가 아예 뜨지 못했다(223 errors).
로컬에서는 개발 DB 의 admin 비밀번호가 테스트 값과 달라 401 이 났다(184 errors).

앞의 두 건은 서브프로세스로 임포트 순서를 직접 재현한다. 스위트 안에서만 도는
단언은 수집 순서에 기대므로 이 파일만 실행하면 결함을 놓친다(실측 확인).
"""
import os
import subprocess
import sys

import pytest
import requests

BACKEND = os.path.dirname(os.path.abspath(__file__))

#: `import conftest` 를 하지 않는다. `tests_unit/conftest.py` 가 같은 모듈 이름을
#: 갖기 때문에, 전체 수집에서는 그쪽이 sys.modules 를 차지해 AttributeError 가 난다
#: (실측 2026-09-07). 필요한 값은 여기서 다시 정한다.
DEV_DB_SUFFIX = "/tc_manager.db"


def _dev_server_running() -> bool:
    port = int(os.getenv("TEST_PORT", "8008"))
    try:
        return requests.get("http://127.0.0.1:%d/" % port, timeout=2).status_code < 500
    except requests.exceptions.RequestException:
        return False

#: conftest 를 임포트한 직후의 DATABASE_URL 을 찍는다. 픽스처는 돌지 않는다.
_PROBE = (
    "import os, conftest; "
    "print(os.environ.get('DATABASE_URL', ''))"
)


def _probe(**overrides) -> str:
    env = dict(os.environ)
    for key in ("DATABASE_URL", "ALLOW_DEV_DB"):
        env.pop(key, None)
    #: 닫혀 있는 포트를 준다. 개발 서버가 8008 에 떠 있으면 conftest 가 일부러
    #: DATABASE_URL 을 건드리지 않으므로, 그 분기를 타지 않게 고정한다.
    env["TEST_PORT"] = "1"
    env.update(overrides)
    r = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=BACKEND, env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_conftest_sets_temp_db_at_import_time():
    """conftest 를 임포트하는 것만으로 DATABASE_URL 이 정해져야 한다.

    픽스처 실행 시점에 정하면 수집 단계의 모듈 임포트에 진다.
    """
    url = _probe()

    assert url.startswith("sqlite:///"), url
    assert not url.endswith(DEV_DB_SUFFIX), (
        "테스트가 개발용 DB 를 쓰고 있다: %s" % url
    )


def test_preset_dev_database_url_is_overridden():
    """셸에 개발 DB 가 박혀 있어도 임시 DB 로 돌린다.

    일부러 쓰려면 ALLOW_DEV_DB=1 을 준다.
    """
    dev = "sqlite:///." + DEV_DB_SUFFIX

    assert not _probe(DATABASE_URL=dev).endswith(DEV_DB_SUFFIX)
    assert _probe(DATABASE_URL=dev, ALLOW_DEV_DB="1") == dev


def test_non_dev_database_url_is_respected():
    """개발 DB 가 아닌 값을 일부러 준 경우는 그대로 둔다."""
    given = "sqlite:///./some_other.db"

    assert _probe(DATABASE_URL=given) == given


def test_running_dev_server_keeps_database_url():
    """서버가 이미 떠 있으면 DATABASE_URL 을 건드리지 않는다.

    HTTP 는 그 서버의 DB 로 가는데 in-process engine 만 임시 DB 로 돌리면
    한 테스트가 두 DB 를 본다. `test_account_requests.py` 는 HTTP 로 만든 행을
    같은 테스트 안에서 `SessionLocal` 로 읽으므로 그 순간 None 이 된다.
    """
    import http.server
    import socketserver
    import threading

    given = "sqlite:///." + DEV_DB_SUFFIX
    with socketserver.TCPServer(
        ("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler
    ) as srv:
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            assert _probe(DATABASE_URL=given, TEST_PORT=str(port)) == given
        finally:
            srv.shutdown()


@pytest.mark.skipif(
    _dev_server_running(),
    reason="8008 에 개발 서버가 떠 있으면 conftest 가 일부러 개발 DB 를 유지한다",
)
def test_engine_url_matches_environment():
    """앱 engine 과 마이그레이션 대상이 같은 DB 여야 한다.

    `database.py` 는 임포트 시점 값을, `main.py` 의 lifespan 은 실행 시점
    `os.environ` 을 쓴다. 둘이 갈라지면 마이그레이션과 앱이 다른 파일에 붙는다.
    """
    import database

    assert database.DATABASE_URL == os.environ["DATABASE_URL"], (
        "engine 이 수집 시점 값에 묶였다"
    )
    assert not database.DATABASE_URL.endswith(DEV_DB_SUFFIX), (
        "테스트가 개발용 DB 를 쓰고 있다: %s" % database.DATABASE_URL
    )
