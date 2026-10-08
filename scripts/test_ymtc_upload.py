"""CI 결과 업로드 CLI(ymtc-upload.mjs)의 업로드 경로.

서버가 스테이징 업로드(/api/uploads)를 지원하면 발급 -> 직접 PUT -> upload_id 로 처리하고,
지원하지 않는 옛 서버(404)면 예전처럼 multipart 로 보낸다. 배포의 요청 본문 4.5MB 한도 때문에
큰 결과 파일은 스테이징으로만 올라간다.
"""
import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, "ymtc-upload.mjs")
SUMMARY = {"format": "junit-xml", "dry_run": False, "run_id": 7, "total_tests": 1, "matched_tests": 1,
           "recorded": 1, "counts": {"PASS": 1, "FAIL": 0, "NS": 0}, "known_failures": 0,
           "unexpected_failures": [], "fixed_candidates": [], "kept_executed": [], "out_of_run": [],
           "unmatched_count": 0, "unmatched": []}

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 가 없다")


def _server(staging: bool):
    calls = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _body(self):
            n = int(self.headers.get("content-length") or 0)
            return self.rfile.read(n) if n else b""

        def _json(self, code, payload):
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            body = self._body()
            calls.append(("POST", self.path, self.headers.get("content-type", ""), body, self.headers.get("authorization")))
            if self.path == "/api/uploads":
                if not staging:
                    return self._json(404, {"detail": "Not Found"})
                return self._json(201, {"upload_id": "U1", "method": "PUT",
                                        "url": "/api/uploads/U1/content?token=T",
                                        "headers": {"content-type": "application/octet-stream"}})
            return self._json(200, SUMMARY)

        def do_PUT(self):
            body = self._body()
            calls.append(("PUT", self.path, self.headers.get("content-type", ""), body, self.headers.get("authorization")))
            self._json(200, {"upload_id": "U1", "size": len(body)})

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, calls


def _run(base, report):
    env = dict(os.environ, YMTC_API_KEY="ymtc_key", YMTC_URL=base)
    return subprocess.run(["node", CLI, "--project", "3", "--run-id", "7", str(report)],
                          env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)


@pytest.fixture
def report(tmp_path):
    p = tmp_path / "junit.xml"
    p.write_bytes(b'<testsuites><testsuite name="a"><testcase name="T-1 ok"/></testsuite></testsuites>')
    return p


def test_스테이징을_지원하면_발급_PUT_upload_id(report):
    srv, calls = _server(staging=True)
    try:
        r = _run(f"http://127.0.0.1:{srv.server_address[1]}", report)
    finally:
        srv.shutdown()
    assert r.returncode == 0, r.stderr
    methods = [(c[0], c[1].split("?")[0]) for c in calls]
    assert methods == [("POST", "/api/uploads"), ("PUT", "/api/uploads/U1/content"),
                       ("POST", "/api/projects/3/testruns/7/results/import")]
    stage = json.loads(calls[0][3])
    assert stage["purpose"] == "result_import" and stage["filename"] == "junit.xml"
    assert stage["size"] == report.stat().st_size
    assert calls[1][3] == report.read_bytes()
    assert calls[1][4] is None, "저장소 주소에 API 키를 싣지 않는다"
    assert "upload_id=U1" in calls[2][1]
    assert calls[2][3] == b"", "처리 요청에는 파일을 다시 싣지 않는다"


def test_옛_서버면_multipart(report):
    srv, calls = _server(staging=False)
    try:
        r = _run(f"http://127.0.0.1:{srv.server_address[1]}", report)
    finally:
        srv.shutdown()
    assert r.returncode == 0, r.stderr
    assert [c[1].split("?")[0] for c in calls] == ["/api/uploads", "/api/projects/3/testruns/7/results/import"]
    assert calls[1][2].startswith("multipart/form-data")
    assert report.read_bytes() in calls[1][3]
