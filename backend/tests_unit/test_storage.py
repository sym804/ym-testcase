"""파일 저장소. 로컬은 디스크, 배포는 Supabase Storage REST.

Supabase 구현은 실제 서비스 대신 표준 라이브러리 HTTP 서버로 요청 모양(경로, 메서드,
헤더, 본문)을 단언한다. 실제 Supabase 와의 왕복은 스테이징 스모크에서 확인한다.
"""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi import HTTPException

from services import storage as storage_mod

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 로컬 ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    return storage_mod.get_storage()


def test_로컬_왕복(local):
    local.put("attachments/a.png", b"abc", "image/png")
    assert local.read("attachments/a.png", 10) == b"abc"
    assert local.size("attachments/a.png") == 3
    local.delete(["attachments/a.png", "attachments/none.png"])
    assert local.size("attachments/a.png") is None


def test_로컬_상한을_넘으면_413(local):
    local.put("k/x.bin", b"x" * 11, None)
    with pytest.raises(HTTPException) as e:
        local.read("k/x.bin", 10)
    assert e.value.status_code == 413


@pytest.mark.parametrize("key", ["../x", "/abs", "a/../b", "한글.png", "a b.png", ""])
def test_키_규칙을_어기면_거부(local, key):
    with pytest.raises(ValueError):
        local.put(key, b"x", None)


def test_로컬은_직접_업로드와_서명_다운로드가_없다(local):
    assert local.upload_target("k/x.bin", None) is None
    assert local.download_url("k/x.bin", "x.bin") is None


def test_모듈_임포트만으로_폴더를_만들지_않는다(tmp_path):
    target = tmp_path / "never"
    env = dict(os.environ, UPLOAD_DIR=str(target), STORAGE_BACKEND="local",
               DATABASE_URL="postgresql+psycopg2://u:p@127.0.0.1:1/x")
    r = subprocess.run([sys.executable, "-c", "import services.storage, routes.attachments"],
                       cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    assert not target.exists()


# ── Supabase ─────────────────────────────────────────────────────────────────

class _Fake(BaseHTTPRequestHandler):
    calls = []
    objects = {}

    def log_message(self, *a):
        pass

    def _body(self):
        n = int(self.headers.get("content-length") or 0)
        return self.rfile.read(n) if n else b""

    def _send(self, code, payload=None, raw=None, headers=None):
        data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else b"")
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _record(self, body):
        _Fake.calls.append({"method": self.command, "path": self.path, "headers": dict(self.headers), "body": body})

    def do_POST(self):
        body = self._body()
        self._record(body)
        if self.path.startswith("/storage/v1/object/upload/sign/"):
            key = self.path[len("/storage/v1/object/upload/sign/"):]
            return self._send(200, {"url": f"/object/upload/sign/{key}?token=TOK"})
        if self.path.startswith("/storage/v1/object/sign/"):
            key = self.path[len("/storage/v1/object/sign/"):]
            return self._send(200, {"signedURL": f"/object/sign/{key}?token=DL"})
        if self.path.startswith("/storage/v1/object/"):
            _Fake.objects[self.path[len("/storage/v1/object/"):]] = body
            return self._send(200, {"Key": self.path})
        self._send(404)

    def do_GET(self):
        self._record(b"")
        key = self.path[len("/storage/v1/object/"):]
        if key in _Fake.objects:
            return self._send(200, raw=_Fake.objects[key])
        self._send(400, {"error": "not_found"})

    def do_HEAD(self):
        self._record(b"")
        key = self.path[len("/storage/v1/object/"):]
        if key in _Fake.objects:
            return self._head_ok(key)
        self._send(400)

    def _head_ok(self, key):
        self.send_response(200)
        self.send_header("content-length", str(len(_Fake.objects[key])))
        self.end_headers()

    def do_DELETE(self):
        body = self._body()
        self._record(body)
        for p in json.loads(body or b"{}").get("prefixes", []):
            _Fake.objects.pop("bkt/" + p, None)
        self._send(200, [])


@pytest.fixture
def supa(monkeypatch):
    _Fake.calls, _Fake.objects = [], {}
    srv = HTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", base)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "SERVICE-KEY")
    monkeypatch.setenv("STORAGE_BUCKET", "bkt")
    yield storage_mod.get_storage(), base
    srv.shutdown()


def test_서비스_키로_인증한다(supa):
    st, _ = supa
    st.put("attachments/a.png", b"abc", "image/png")
    h = {k.lower(): v for k, v in _Fake.calls[-1]["headers"].items()}
    assert h["authorization"] == "Bearer SERVICE-KEY"
    assert h["apikey"] == "SERVICE-KEY"
    assert h["content-type"] == "image/png"
    assert _Fake.calls[-1]["path"] == "/storage/v1/object/bkt/attachments/a.png"


def test_supabase_왕복과_크기(supa):
    st, _ = supa
    st.put("k/x.bin", b"hello", None)
    assert st.read("k/x.bin", 10) == b"hello"
    assert st.size("k/x.bin") == 5
    assert st.size("k/none.bin") is None
    st.delete(["k/x.bin"])
    assert json.loads(_Fake.calls[-1]["body"]) == {"prefixes": ["k/x.bin"]}
    assert _Fake.calls[-1]["path"] == "/storage/v1/object/bkt"


def test_supabase_상한을_넘으면_413(supa):
    st, _ = supa
    st.put("k/big.bin", b"x" * 11, None)
    with pytest.raises(HTTPException) as e:
        st.read("k/big.bin", 10)
    assert e.value.status_code == 413


def test_직접_업로드_주소는_절대_주소와_PUT(supa):
    st, base = supa
    t = st.upload_target("staging/u1/a.xlsx", "application/vnd.ms-excel")
    assert t == {
        "method": "PUT",
        "url": f"{base}/storage/v1/object/upload/sign/bkt/staging/u1/a.xlsx?token=TOK",
        "headers": {"content-type": "application/vnd.ms-excel"},
    }
    assert "SERVICE-KEY" not in json.dumps(t)


def test_서명_다운로드_주소는_파일명을_붙인다(supa):
    st, base = supa
    url = st.download_url("attachments/a.png", "결과 화면.png", expires_sec=60)
    assert url.startswith(f"{base}/storage/v1/object/sign/bkt/attachments/a.png?token=DL&download=")
    assert json.loads(_Fake.calls[-1]["body"]) == {"expiresIn": 60}
    assert "SERVICE-KEY" not in url
