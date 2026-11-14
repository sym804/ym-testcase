"""xlsx 가져오기는 압축을 풀기 전에 풀린 크기를 확인한다(SYM-218).

업로드 상한(10MB)은 압축된 크기다. xlsx 는 zip 이라 같은 문자가 반복되는 시트는 수백 배로
풀린다. 목차(file_size)만 보면 안 된다. 목차를 작게 속인 항목을 zipfile.read() 로 읽으면 압축을
통째로 푼 뒤에야 자른다. 그래서 조금씩 풀며 실제 크기를 재고, 잰 내용으로 다시 묶어 파서에 넘긴다.
"""
import io
import zipfile

import openpyxl
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from services import import_service
from services.import_service import XLSX_TOO_LARGE, _load_workbook_from_upload

MB = 1024 * 1024


def _upload(data: bytes, name="tcs.xlsx") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=name)


def _bomb(unpacked_mb: int) -> bytes:
    """같은 바이트만 든 시트 하나. 압축하면 수 KB 다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/worksheets/sheet1.xml", b"\x20" * (unpacked_mb * MB))
    return buf.getvalue()


def _real_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    wb.active["A1"] = "TC ID"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_풀린_크기가_상한을_넘으면_열지_않고_400(monkeypatch):
    monkeypatch.setenv("XLSX_MAX_UNCOMPRESSED_MB", "2")
    data = _bomb(3)
    assert len(data) < 100 * 1024  # 압축 크기는 업로드 상한 한참 아래다
    called = []
    monkeypatch.setattr("openpyxl.load_workbook", lambda *a, **k: called.append(1))
    with pytest.raises(HTTPException) as e:
        _load_workbook_from_upload(_upload(data))
    assert (e.value.status_code, e.value.detail) == (400, XLSX_TOO_LARGE)
    assert called == []


def test_상한_안이면_그대로_읽는다(monkeypatch):
    monkeypatch.setenv("XLSX_MAX_UNCOMPRESSED_MB", "2")
    wb = _load_workbook_from_upload(_upload(_real_xlsx()))
    assert wb.active["A1"].value == "TC ID"


def test_항목_수가_너무_많아도_거절한다(monkeypatch):
    monkeypatch.setattr(import_service, "XLSX_MAX_ENTRIES", 5)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(6):
            z.writestr(f"x{i}.xml", "a")
    with pytest.raises(HTTPException) as e:
        _load_workbook_from_upload(_upload(buf.getvalue()))
    assert (e.value.status_code, e.value.detail) == (400, XLSX_TOO_LARGE)


def test_zip_이_아니면_기존과_같은_읽기_실패():
    with pytest.raises(HTTPException) as e:
        _load_workbook_from_upload(_upload(b"not a zip at all"))
    assert (e.value.status_code, e.value.detail) == (400, "Failed to read Excel file")


def test_기본_상한은_실제_TC_파일의_최대_압축률을_담는다(monkeypatch):
    """로컬 xlsx 73개 실측 최대 압축률 13.7배. 10MB 파일이 그 비율이면 137MB 다."""
    monkeypatch.delenv("XLSX_MAX_UNCOMPRESSED_MB", raising=False)
    assert import_service._xlsx_max_uncompressed() == 200 * MB


def _lying_zip(real_mb: int, fake: int = 1000) -> bytes:
    """xl/styles.xml 의 풀린 크기를 목차와 로컬 헤더 모두 fake 로 속이고, CRC 도 앞 fake 바이트에 맞춘 zip."""
    import struct
    import zlib

    name = b"xl/styles.xml"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(name.decode(), b"\x20" * (real_mb * MB))
    data = bytearray(buf.getvalue())
    crc = zlib.crc32(b"\x20" * fake)

    def find(sig, name_len_at, name_at):
        pos = 0
        while True:
            pos = data.find(sig, pos)
            n = struct.unpack_from("<H", data, pos + name_len_at)[0]
            if bytes(data[pos + name_at:pos + name_at + n]) == name:
                return pos
            pos += 4

    lh = find(b"PK\x03\x04", 26, 30)
    struct.pack_into("<I", data, lh + 14, crc)
    struct.pack_into("<I", data, lh + 22, fake)
    cd = find(b"PK\x01\x02", 28, 46)
    struct.pack_into("<I", data, cd + 16, crc)
    struct.pack_into("<I", data, cd + 24, fake)
    return bytes(data)


def test_목차를_속인_항목도_메모리를_키우지_않는다(monkeypatch):
    """목차 file_size 만 보면 통과하고 openpyxl 의 read() 가 압축을 통째로 푼다(QA1 지적, 재현 601MB)."""
    import tracemalloc

    data = _lying_zip(real_mb=200)
    assert zipfile.ZipFile(io.BytesIO(data)).getinfo("xl/styles.xml").file_size == 1000
    seen = []

    def fake_load(filename, **_kw):
        seen.append(filename.getvalue())
        return object()

    monkeypatch.setattr("openpyxl.load_workbook", fake_load)
    tracemalloc.start()
    try:
        try:
            _load_workbook_from_upload(_upload(data))
        except HTTPException as e:
            assert e.status_code == 400
        _cur, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 30 * MB, peak
    # 파서까지 갔다면, 넘긴 묶음의 목차는 실제로 담긴 크기다
    for repacked in seen:
        with zipfile.ZipFile(io.BytesIO(repacked)) as z:
            for info in z.infolist():
                assert info.compress_type == zipfile.ZIP_STORED
                assert info.file_size == len(z.read(info))


def test_지원하지_않는_zip_버전은_500_이_아니라_400():
    import struct

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.xml", "a")
    data = bytearray(buf.getvalue())
    cd = data.find(b"PK\x01\x02")
    struct.pack_into("<H", data, cd + 6, 99)  # version needed to extract
    with pytest.raises(HTTPException) as e:
        _load_workbook_from_upload(_upload(bytes(data)))
    assert e.value.status_code == 400


def test_다시_묶은_파일도_openpyxl_이_그대로_읽는다():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "로그인"
    for i in range(1, 200):
        ws.cell(row=i, column=1, value=f"TC-{i:03d}")
        ws.cell(row=i, column=2, value="반복 " * 20)
    buf = io.BytesIO()
    wb.save(buf)
    got = _load_workbook_from_upload(_upload(buf.getvalue()))
    assert got.sheetnames == ["로그인"]
    assert got["로그인"]["A199"].value == "TC-199"


def test_상한_근처_정상_항목도_한_벌만_메모리에_든다(monkeypatch):
    """목차가 정직해도 풀린 조각을 모았다 이어 붙이면 항목 하나가 세 벌이 된다(QA 2인 지적)."""
    import tracemalloc

    monkeypatch.setenv("XLSX_MAX_UNCOMPRESSED_MB", "40")
    data = _bomb(35)
    monkeypatch.setattr("openpyxl.load_workbook", lambda filename, **_kw: object())
    tracemalloc.start()
    try:
        _load_workbook_from_upload(_upload(data))
        _cur, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 35 * MB * 1.4, peak / MB
