"""테스트용: ASGI 앱에 요청을 직접 보낸다.

starlette 의 TestClient 는 버전에 따라 httpx 또는 httpx2 를 요구해, 개발 PC 와 CI 의 설치
결과가 갈렸다(2026-10-09 CI 실패). lifespan 을 부르지 않는 서버리스 런타임을 흉내 내는
테스트에는 오히려 이 방식이 맞다. lifespan 을 거치는 기동은 asgi_get_many(lifespan=True) 로 본다.
"""
import asyncio
import json


async def _request(app, path: str) -> tuple[int, dict]:
    status, _headers, body = await _raw(app, path)
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        data = {}
    return status, data


async def _raw(app, path: str) -> tuple[int, dict, bytes]:
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
    start = next(m for m in messages if m["type"] == "http.response.start")
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in start.get("headers", [])}
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], headers, body


async def _with_lifespan(app, paths: list[str]) -> list[tuple[int, dict]]:
    """lifespan startup 을 끝낸 뒤 요청을 보내고 shutdown 한다. startup 이 실패하면 RuntimeError."""
    inbox: asyncio.Queue = asyncio.Queue()
    outbox: asyncio.Queue = asyncio.Queue()
    task = asyncio.ensure_future(app({"type": "lifespan", "asgi": {"version": "3.0"}, "state": {}},
                                     inbox.get, outbox.put))
    await inbox.put({"type": "lifespan.startup"})
    started = await outbox.get()
    if started["type"] != "lifespan.startup.complete":
        await task
        raise RuntimeError(f"lifespan startup failed: {started.get('message', '')}")
    try:
        return [await _request(app, p) for p in paths]
    finally:
        await inbox.put({"type": "lifespan.shutdown"})
        await outbox.get()
        await task


def asgi_get(app, path: str) -> tuple[int, dict]:
    """GET 요청 하나를 보내고 (상태 코드, JSON 본문 또는 {}) 를 돌려준다. lifespan 은 부르지 않는다."""
    return asyncio.run(_request(app, path))


def asgi_get_raw(app, path: str) -> tuple[int, dict, bytes]:
    """GET 하나를 보내 (상태 코드, 소문자 헤더, 본문 바이트) 를 돌려준다. lifespan 은 부르지 않는다."""
    return asyncio.run(_raw(app, path))


def asgi_get_many(app, paths: list[str], *, lifespan: bool = False) -> list[tuple[int, dict]]:
    """여러 GET 을 한 이벤트 루프에서 차례로 보낸다. lifespan=True 면 기동·종료 이벤트를 앞뒤로 보낸다."""
    async def run():
        if lifespan:
            return await _with_lifespan(app, paths)
        return [await _request(app, p) for p in paths]

    return asyncio.run(run())
