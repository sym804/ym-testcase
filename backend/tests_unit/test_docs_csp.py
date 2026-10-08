"""API 문서(Swagger UI) 페이지가 백엔드 CSP 에 막히지 않는다. 다른 경로의 CSP 는 그대로 엄격하다.

Swagger UI 는 CDN 스크립트와 인라인 스크립트를 쓴다. 전역 CSP(script-src 'self')를 그대로 받으면
빈 화면이 된다(v1.10.3.1 의 /docs 부터 있던 결함).
"""
import re

from asgi_testing import asgi_get_raw


def _directives(csp: str) -> dict:
    out = {}
    for part in csp.split(";"):
        words = part.split()
        if words:
            out[words[0]] = words[1:]
    return out


def _origin(url: str) -> str:
    return re.match(r"(https://[^/]+)", url).group(1)


def test_문서_페이지가_부르는_스크립트와_스타일을_CSP_가_허용한다():
    from main import app

    status, headers, body = asgi_get_raw(app, "/api/docs")
    assert status == 200
    html = body.decode("utf-8")
    csp = _directives(headers["content-security-policy"])

    srcs = re.findall(r'<script[^>]*src="([^"]+)"', html)
    assert srcs, "Swagger 스크립트를 찾지 못했다(페이지 형태가 바뀜)"
    for src in srcs:
        if src.startswith("https://"):
            assert _origin(src) in csp["script-src"], src
    if re.search(r"<script>(?!\s*</script>)", html):
        assert "'unsafe-inline'" in csp["script-src"]
    for href in re.findall(r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"|<link[^>]*href="([^"]+)"[^>]*rel="stylesheet"', html):
        url = href[0] or href[1]
        if url.startswith("https://"):
            assert _origin(url) in csp["style-src"], url
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


def test_다른_경로의_CSP_는_완화되지_않는다():
    from main import app

    _, headers, _ = asgi_get_raw(app, "/api/config")
    csp = _directives(headers["content-security-policy"])
    assert csp["script-src"] == ["'self'"]
