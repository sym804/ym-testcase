"""단위 테스트 전용 설정.

backend/conftest.py 의 `_server` 픽스처는 8008 포트에 서버가 이미 떠 있으면
그 서버를 그대로 쓰고 admin 계정을 시드한다. 즉 개발 서버를 켠 채로 pytest 를
돌리면 실 DB 에 쓰기가 들어간다.

이 디렉터리의 테스트는 서버가 필요 없다. 같은 이름으로 다시 정의해 그 픽스처를
무력화한다(가까운 conftest 가 이긴다). 여기 테스트는 각자 임시 DB 만 쓴다.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def _server():
    yield
