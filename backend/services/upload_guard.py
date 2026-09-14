"""업로드 크기 제한.

`await file.read()` 로 전부 읽은 뒤 길이를 재면, 우리가 만드는 버퍼에 파일이
통째로 올라온 뒤에야 거절한다. 청크로 읽으면서 넘는 순간 끊으면 그 버퍼는
제한 크기 언저리에서 멈춘다.

**이것이 막는 것은 우리 버퍼뿐이다.** FastAPI 는 엔드포인트를 부르기 전에
multipart 파서가 본문을 다 받아 `SpooledTemporaryFile`(1MB 를 넘으면 디스크)에
이미 써 둔다. 그래서 아주 큰 업로드는 핸들러에 닿기 전에 전량 수신된다.
그쪽까지 막으려면 `Content-Length` 선검사나 ASGI 본문 크기 미들웨어가 따로 필요하다.
"""
from fastapi import HTTPException

#: 한 번에 읽는 크기. 1MB.
DEFAULT_CHUNK = 1024 * 1024


async def read_limited(file, max_bytes: int, chunk_size: int = DEFAULT_CHUNK) -> bytes:
    """`max_bytes` 까지만 읽는다. 넘으면 413 을 내고 더 읽지 않는다."""
    buf = bytearray()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {max_bytes // (1024 * 1024)}MB",
            )
    return bytes(buf)


def read_limited_sync(fileobj, max_bytes: int, chunk_size: int = DEFAULT_CHUNK) -> bytes:
    """동기 파일 객체용. `UploadFile.file` 처럼 read(n) 을 주는 것에 쓴다."""
    buf = bytearray()
    while True:
        chunk = fileobj.read(chunk_size)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {max_bytes // (1024 * 1024)}MB",
            )
    return bytes(buf)
