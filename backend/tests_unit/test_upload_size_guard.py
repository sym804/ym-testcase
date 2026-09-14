"""업로드 크기 제한은 다 읽기 전에 걸린다

`await file.read()` 로 전부 읽은 뒤 길이를 재면, 우리 버퍼에 파일이 통째로
올라온 뒤에야 거절한다. 청크로 읽으면서 넘는 순간 끊으면 그 버퍼는 제한 크기
언저리에서 멈춘다.

여기서 재는 것은 그 버퍼뿐이다. FastAPI 의 multipart 파서는 엔드포인트를 부르기
전에 본문을 이미 다 받아 두므로, 이 가드가 전체 수신량을 줄이지는 않는다.
"""
import asyncio
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from fastapi import HTTPException

from services.upload_guard import read_limited


class _FakeUpload:
    """읽은 총량을 기록하는 UploadFile 흉내."""

    def __init__(self, total: int):
        self._left = total
        self.read_total = 0

    async def read(self, size: int = -1) -> bytes:
        if self._left <= 0:
            return b""
        n = self._left if size is None or size < 0 else min(size, self._left)
        self._left -= n
        self.read_total += n
        return b"x" * n


def test_제한을_넘으면_413이다():
    up = _FakeUpload(5_000)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_limited(up, max_bytes=1_000))
    assert exc.value.status_code == 413


def test_제한을_넘으면_파일_전체를_읽지_않는다():
    up = _FakeUpload(5_000_000)
    with pytest.raises(HTTPException):
        asyncio.run(read_limited(up, max_bytes=1_000, chunk_size=256))
    assert up.read_total < 10_000, (
        f"제한을 넘고도 {up.read_total} 바이트를 읽었다. 다 읽은 뒤 재고 있다"
    )


def test_제한_안이면_그대로_돌려준다():
    up = _FakeUpload(900)
    got = asyncio.run(read_limited(up, max_bytes=1_000))
    assert len(got) == 900


def test_제한과_같은_크기는_통과한다():
    up = _FakeUpload(1_000)
    got = asyncio.run(read_limited(up, max_bytes=1_000))
    assert len(got) == 1_000
