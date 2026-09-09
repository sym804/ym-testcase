"""개발 DB 를 건드릴 위험이 있는지 알려 주는 자리.

값은 `conftest.py` 가 채운다. 테스트 파일은 이것만 보고 건너뛸지 정한다.

★`from conftest import ...` 로 가져오지 않는다. `tests_unit/conftest.py` 가 같은
  이름을 먼저 차지해서 루트 conftest 를 가린다(실측: 전체 수집에서 ImportError 8건).
"""

#: 이미 떠 있는 개발 서버를 그대로 쓰고 있는가. conftest 가 실제 값을 넣는다.
#: 기본값을 False 로 둬야, conftest 가 아직 안 돌았을 때 테스트를 건너뛰지 않는다.
DEV_DB_AT_RISK = False

SKIP_REASON = (
    "이미 떠 있는 개발 서버를 쓰고 있어 실 DB 가 오염된다. "
    "격리해서 돌리려면 개발 서버를 내리거나 TEST_PORT 를 비어 있는 포트로 지정한다."
)

#: 테스트 모듈이 TEST_BASE_URL 없이 쓰는 기본 주소의 포트.
#: ★conftest 의 TEST_PORT 로 떨어지면 안 된다. TEST_PORT=8009 만 주고
#:   TEST_BASE_URL 을 안 주면 판정은 8009(비어 있음)를 보고 안전하다고 하는데,
#:   테스트의 요청은 자기 기본값인 8008 로 간다. 개발 서버가 거기 떠 있으면 실 DB 에
#:   쓰기가 들어간다. test_dev_db_guard.py 가 이 값과 테스트 모듈을 대조한다.
DEFAULT_REQUEST_PORT = 8008

#: pytest 수집에서 빠지는 독립 실행 스크립트. conftest 의 collect_ignore 와 같아야 한다.
STANDALONE_SCRIPTS = (
    "test_v060_full.py", "test_v060_edge_cases.py",
    "test_v103_features.py", "test_v110_features.py",
)
