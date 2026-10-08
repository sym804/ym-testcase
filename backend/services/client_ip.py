"""요청을 보낸 클라이언트의 IP.

★헤더를 아무거나 믿지 않는다. X-Forwarded-For 는 클라이언트가 마음대로 넣을 수 있다.
  배포 플랫폼이 덮어써서 위조할 수 없는 헤더 하나만 TRUSTED_PROXY_HEADER 로 지정한다.
  어떤 헤더가 그런지는 플랫폼마다 다르고, 스테이징에서 실측해 정한다.
  비워 두면(로컬) 소켓 주소를 쓴다.
"""
import os


def client_ip(request) -> str:
    header = os.getenv("TRUSTED_PROXY_HEADER", "").strip().lower()
    if header:
        first = request.headers.get(header, "").split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"
