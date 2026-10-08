"""레포 루트 vercel.json (Vercel Services: 프론트 정적 + FastAPI 백엔드, 한 도메인).

공개 레포라 회사 정보(도메인, Supabase 프로젝트 주소)가 들어가면 안 된다.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cfg():
    with open(os.path.join(ROOT, "vercel.json"), encoding="utf-8") as f:
        return json.load(f)


def test_서비스는_프론트와_백엔드():
    s = _cfg()["services"]
    assert s["frontend"]["root"] == "frontend/"
    assert s["frontend"]["outputDirectory"] == "dist"
    assert s["backend"]["root"] == "backend/"
    assert s["backend"]["entrypoint"] == "main:app"


def test_api_는_백엔드로_나머지는_프론트로_이_순서():
    rw = _cfg()["rewrites"]
    assert rw[0] == {"source": "/api/(.*)", "destination": {"service": "backend"}}
    assert rw[-1] == {"source": "/(.*)", "destination": {"service": "frontend"}}


def test_프론트는_SPA_로_index_html_을_돌려준다():
    rw = _cfg()["services"]["frontend"]["rewrites"]
    assert {"source": "/(.*)", "destination": "/index.html"} in rw


def test_매일_정리_Cron():
    crons = _cfg()["crons"]
    assert any(c["path"] == "/api/internal/cron/daily" for c in crons)


def test_정적_응답에도_보안_헤더와_Supabase_출처만_허용하는_CSP():
    headers = _cfg()["services"]["frontend"]["headers"]
    flat = {h["key"]: h["value"] for rule in headers for h in rule["headers"]}
    assert flat["X-Frame-Options"] == "DENY"
    csp = flat["Content-Security-Policy"]
    assert "connect-src 'self' https://*.supabase.co" in csp
    assert "img-src 'self' data: blob: https://*.supabase.co" in csp
    assert "frame-ancestors 'none'" in csp


def test_백엔드_함수_설정():
    fns = _cfg()["services"]["backend"]["functions"]
    (conf,) = fns.values()
    assert conf["maxDuration"] == 60
    assert "test_*.py" in conf["excludeFiles"]


def test_회사_정보가_없다():
    text = open(os.path.join(ROOT, "vercel.json"), encoding="utf-8").read()
    # 와일드카드 외의 구체적인 supabase 프로젝트 주소나 vercel.app 도메인이 없어야 한다
    assert not re.search(r"https://[a-z0-9]{10,}\.supabase\.co", text)
    assert ".vercel.app" not in text


def test_Swagger_는_api_아래():
    from main import app
    assert app.docs_url == "/api/docs"
    assert app.openapi_url == "/api/openapi.json"


def _csp_directives():
    headers = _cfg()["services"]["frontend"]["headers"]
    flat = {h["key"]: h["value"] for rule in headers for h in rule["headers"]}
    out = {}
    for part in flat["Content-Security-Policy"].split(";"):
        words = part.split()
        if words:
            out[words[0]] = words[1:]
    return out


def test_index_html_이_부르는_외부_출처를_CSP_가_허용한다():
    """index.html 의 외부 스타일·스크립트가 CSP 에 막히면 배포에서만 깨진다(로컬은 CSP 가 없다)."""
    html = open(os.path.join(ROOT, "frontend", "index.html"), encoding="utf-8").read()
    csp = _csp_directives()

    def origin(url):
        m = re.match(r"(https://[^/]+)", url)
        return m.group(1)

    for tag in re.findall(r"<link\b[^>]*>", html):
        href = re.search(r'href="(https://[^"]+)"', tag)
        if href and 'rel="stylesheet"' in tag:
            assert origin(href.group(1)) in csp["style-src"], tag
        # crossorigin preconnect 는 글꼴 파일 출처다(Google Fonts 의 CSS 가 그 출처의 woff2 를 부른다).
        if href and 'rel="preconnect"' in tag and "crossorigin" in tag:
            assert origin(href.group(1)) in csp["font-src"], tag
    for src in re.findall(r'<script\b[^>]*src="(https://[^"]+)"', html):
        assert origin(src) in csp["script-src"], src
