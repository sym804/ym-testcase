"""개발 DB 를 지키는 가드가 실제로 요청이 가는 곳을 보는지 확인한다.

가드는 "이미 떠 있는 개발 서버를 쓰고 있으면 건너뛴다" 로 판정한다. 그 판정이
테스트가 실제로 요청을 보내는 주소와 갈라지면, 안전하다고 말하면서 실 DB 를 친다.

두 값이 각자 기본값을 들고 있어서 조용히 어긋날 수 있다. 여기서 묶어 둔다.

실행: cd backend && python -m pytest test_dev_db_guard.py -v
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = Path(__file__).resolve().parent

#: HTTP 로 요청을 보내는 테스트 파일이 쓰는 기본 주소 패턴.
#: 따옴표 종류와 os.environ.get 표기까지 받는다. 표기를 조금 바꿔 쓴 파일이
#: 검사에서 조용히 빠지면, 그 파일만 실 DB 를 치게 된다.
_BASE_RE = re.compile(
    r"""os\.(?:getenv|environ\.get)\(\s*["']TEST_BASE_URL["']\s*,\s*["']https?://[^"':]+:(\d+)["']"""
)


def _files_with_default_base():
    """기본 주소를 쓰는 테스트 파일. 수집에서 빠지는 독립 스크립트는 뺀다."""
    import dev_db_guard

    ignored = set(dev_db_guard.STANDALONE_SCRIPTS)
    out = {}
    for path in HERE.rglob("test_*.py"):
        if path.name in ignored:
            continue
        m = _BASE_RE.search(path.read_text(encoding="utf-8"))
        if m:
            out[path.name] = int(m.group(1))
    return out


def test_default_base_port_matches_conftest():
    """테스트가 쓰는 기본 포트와 가드가 보는 기본 포트가 같아야 한다.

    ★conftest 를 임포트해 확인하지 않는다. tests_unit/conftest.py 가 같은 이름을
      선점해서, 전체 수집에서는 그쪽이 잡힌다.
    """
    import dev_db_guard

    files = _files_with_default_base()
    assert files, "기본 주소를 쓰는 테스트 파일을 하나도 못 찾았다. 패턴이 낡았는지 보라"

    mismatched = {n: p for n, p in files.items() if p != dev_db_guard.DEFAULT_REQUEST_PORT}
    assert not mismatched, (
        f"가드는 {dev_db_guard.DEFAULT_REQUEST_PORT} 를 보는데 이 파일들은 다른 곳으로 요청한다: {mismatched}"
    )


def test_http_test_files_carry_the_guard():
    """HTTP 를 쓰는 파일은 모두 가드를 달아야 한다.

    하나라도 빠지면 개발 서버가 떠 있을 때 그 파일만 실 DB 를 친다.
    """
    missing = []
    for name in _files_with_default_base():
        body = (HERE / name).read_text(encoding="utf-8")
        # 임포트만 하고 skip 을 빠뜨린 파일도 잡는다. 문자열이 있다는 것만으로는
        # 그 파일이 실제로 건너뛴다는 뜻이 아니다.
        if "DEV_DB_AT_RISK" not in body or "allow_module_level" not in body:
            missing.append(name)

    assert not missing, f"가드가 없거나 건너뛰지 않는 HTTP 테스트: {missing}"


def test_guard_is_off_in_ci():
    """CI 에서는 가드가 꺼져 있어야 한다.

    켜지면 HTTP 테스트가 통째로 건너뛰어진 채 초록이 나오고, 그것을 통과로 읽게
    된다. 실제로 그런 적이 있다(40건이 한 줄도 안 돌았다).
    """
    import pytest

    import dev_db_guard

    if not os.getenv("CI"):
        pytest.skip("로컬은 개발 서버가 떠 있을 수 있다. 이 확인은 CI 에서만 뜻이 있다")
    assert not dev_db_guard.DEV_DB_AT_RISK, "CI 인데 개발 서버가 떠 있다고 판정했다"


def test_conftest_falls_back_to_the_guard_default():
    """conftest 의 폴백이 가드 상수를 봐야 한다.

    ★소스를 문자열로 본다. conftest 를 임포트하면 requests 몽키패치와 임시 DB
      생성이 다시 돈다. 그리고 tests_unit/conftest.py 가 이름을 선점해 엉뚱한
      모듈이 잡힌다.
    """
    src = (HERE / "conftest.py").read_text(encoding="utf-8")

    assert "DEFAULT_REQUEST_PORT" in src, "conftest 가 가드 상수를 보지 않는다"
    assert not re.search(r'TEST_BASE_URL"\s*,\s*"http', src), (
        "conftest 가 자기 리터럴 기본 주소를 들고 있다. 테스트 모듈과 갈라진다"
    )
