"""실행 환경(로컬 / 서버리스)에 따른 기본값과 설정 검사.

Vercel 은 함수 환경에 `VERCEL=1` 을 넣는다. 그 값이 있으면 서버리스로 본다.

서버리스 기본값
- DB_POOL=null: 실행 환경이 수시로 생기고 사라져 풀을 들 이유가 없다(Supabase 풀러가 맡는다)
- RUN_MIGRATIONS_ON_STARTUP=0: 실행 환경마다 동시에 돌기 때문. 배포 워크플로가 한다
- RUN_MAINTENANCE_ON_STARTUP=0: 정리는 Cron 이 한다

명시한 환경변수가 있으면 그 값이 이긴다.
"""
import logging
import os

logger = logging.getLogger(__name__)

_SERVERLESS_DEFAULTS = {
    "RUN_MIGRATIONS_ON_STARTUP": "0",
    "RUN_MAINTENANCE_ON_STARTUP": "0",
    "DB_POOL": "null",
}


def is_serverless() -> bool:
    return bool(os.getenv("VERCEL"))


def env_value(name: str, local_default: str = "") -> str:
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    if is_serverless() and name in _SERVERLESS_DEFAULTS:
        return _SERVERLESS_DEFAULTS[name]
    return local_default


def env_flag(name: str) -> bool:
    """켜고 끄는 설정. 로컬 기본은 켬, 서버리스 기본은 위 표."""
    return env_value(name, "1") == "1"


def check_serverless_config() -> None:
    """서버리스에서 동작할 수 없는 설정이면 기동을 멈추고, 위험한 설정은 크게 남긴다."""
    if not is_serverless():
        return
    if os.getenv("STORAGE_BACKEND") != "supabase":
        raise RuntimeError(
            "서버리스에서는 STORAGE_BACKEND=supabase 가 필요하다. 함수의 디스크는 꺼지면 사라진다."
        )
    if not os.getenv("TRUSTED_PROXY_HEADER"):
        logger.error(
            "TRUSTED_PROXY_HEADER 가 비어 있다. 서버리스에서는 소켓 주소가 프록시라 조직 전체가 "
            "한 IP 로 묶여 로그인 잠금과 접수 제한을 함께 받을 수 있다. 스테이징에서 플랫폼이 "
            "덮어쓰는 헤더를 확인해 지정한다."
        )
