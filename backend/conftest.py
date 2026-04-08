"""pytest 전역 설정 — 테스트 세션 동안 uvicorn 서버를 자동으로 시작/종료"""
import threading
import time

# 독립 실행 스크립트를 pytest 수집에서 제외
collect_ignore = ["test_v060_full.py", "test_v060_edge_cases.py", "test_v103_features.py", "test_v110_features.py"]

import pytest
import requests
import uvicorn


def _server_already_running(port: int) -> bool:
    """이미 서버가 해당 포트에서 실행 중인지 확인"""
    try:
        r = requests.get(f"http://localhost:{port}/", timeout=2)
        return r.status_code < 500
    except requests.ConnectionError:
        return False


def _wait_for_server(url: str, timeout: float = 15):
    """서버가 응답할 때까지 대기"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"Server did not start within {timeout}s at {url}")


@pytest.fixture(scope="session", autouse=True)
def _server():
    """세션 시작 시 uvicorn 서버를 백그라운드 스레드로 실행 (이미 실행 중이면 스킵)"""
    port = int(__import__("os").getenv("TEST_PORT", "8008"))

    if _server_already_running(port):
        yield
        return

    from main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    _wait_for_server(f"http://localhost:{port}/docs")
    yield
    server.should_exit = True
    thread.join(timeout=5)
