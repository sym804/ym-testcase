"""클라이언트 IP 는 배포 플랫폼이 덮어쓰는 신뢰 헤더 하나만 믿는다."""
from starlette.requests import Request

from services.client_ip import client_ip


def _req(headers=None, host="10.0.0.1"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234)})


def test_설정이_없으면_소켓_주소를_쓰고_XFF_는_무시한다(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HEADER", raising=False)
    assert client_ip(_req({"x-forwarded-for": "6.6.6.6"})) == "10.0.0.1"


def test_신뢰_헤더가_있으면_그_값의_첫_항목(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HEADER", "X-Real-IP")
    assert client_ip(_req({"x-real-ip": " 1.2.3.4 , 5.6.7.8"})) == "1.2.3.4"


def test_신뢰_헤더가_비어_있으면_소켓_주소(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HEADER", "x-real-ip")
    assert client_ip(_req()) == "10.0.0.1"


def test_소켓_주소도_없으면_unknown(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HEADER", raising=False)
    req = Request({"type": "http", "headers": [], "client": None})
    assert client_ip(req) == "unknown"
