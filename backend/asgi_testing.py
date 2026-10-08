"""테스트용: ASGI 앱에 요청 하나를 직접 보낸다.

starlette 의 TestClient 는 버전에 따라 httpx 또는 httpx2 를 요구해, 개발 PC 와 CI 의 설치
결과가 갈렸다(2026-10-09 CI 실패). lifespan 을 부르지 않는 서버리스 런타임을 흉내 내는
테스트에는 오히려 이 방식이 맞다.
"""
import asyncio
import json


def asgi_get(app, path: str) -> tuple[int, dict]:
    """GET 요청 하나를 보내고 (상태 코드, JSON 본문 또는 {}) 를 돌려준다. lifespan 은 부르지 않는다."""
    async def run():
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
            "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "",
            "query_string": b"", "headers": [(b"host", b"testserver")],
            "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
        }
        await app(scope, receive, send)
        status = next(m["status"] for m in messages if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        try:
            data = json.loads(body) if body else {}
        except ValueError:
            data = {}
        return status, data

    return asyncio.run(run())
