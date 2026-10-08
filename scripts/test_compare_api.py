"""이관 전후 API 비교 도구. 가짜 서버 두 개로 같음/다름 판정을 본다.

실행: python -m pytest -q scripts/test_compare_api.py
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import compare_api  # noqa: E402


def _server(report_value):
    class H(BaseHTTPRequestHandler):
        seen = []

        def log_message(self, *a):
            pass

        def _send(self, code, payload):
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            if self.path == "/api/auth/login" and body == {"username": "admin", "password": "pw"}:
                return self._send(200, {"access_token": "TOK"})
            self._send(401, {"detail": "no"})

        def do_GET(self):
            H.seen.append(self.path)
            if self.headers.get("authorization") != "Bearer TOK":
                return self._send(401, {"detail": "no"})
            if self.path == "/api/projects":
                return self._send(200, [{"id": 7, "name": "P"}])
            if self.path == "/api/projects/7/testruns":
                return self._send(200, [{"id": 3}])
            if self.path.startswith("/api/projects/7/reports"):
                return self._send(200, {"summary": {"pass": report_value}})
            self._send(200, {"path": self.path})

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}", H


@pytest.fixture
def servers():
    made = []

    def make(value):
        srv, url, h = _server(value)
        made.append(srv)
        return url, h

    yield make
    for s in made:
        s.shutdown()


def test_같은_응답이면_종료코드_0(servers, tmp_path, monkeypatch):
    a, ha = servers(5)
    b, _ = servers(5)
    monkeypatch.setenv("CMP_PASSWORD", "pw")
    assert compare_api.main(["--a", a, "--b", b, "--username", "admin", "--out", str(tmp_path / "d.json")]) == 0
    assert "/api/projects/7/dashboard/summary" in ha.seen
    assert "/api/projects/7/reports?run_id=3" in ha.seen


def test_다른_응답은_경로와_함께_남기고_종료코드_1(servers, tmp_path, monkeypatch):
    a, _ = servers(5)
    b, _ = servers(6)
    monkeypatch.setenv("CMP_PASSWORD", "pw")
    out = tmp_path / "d.json"
    assert compare_api.main(["--a", a, "--b", b, "--username", "admin", "--out", str(out)]) == 1
    diffs = json.loads(out.read_text(encoding="utf-8"))
    assert [d["path"] for d in diffs] == ["/api/projects/7/reports?run_id=3"]


def test_로그인이_안_되면_종료코드_2(servers, tmp_path, monkeypatch):
    a, _ = servers(5)
    b, _ = servers(5)
    monkeypatch.setenv("CMP_PASSWORD", "wrong")
    assert compare_api.main(["--a", a, "--b", b, "--username", "admin", "--out", str(tmp_path / "d.json")]) == 2
