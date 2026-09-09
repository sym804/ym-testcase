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
