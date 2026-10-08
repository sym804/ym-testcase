"""Storage 백업 스크립트: 스테이징 제외, 도중에 지워진 객체, 일시 장애, 목록 도중 변경.

실행: python -m pytest -q scripts/test_backup_storage.py
"""
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://unused@127.0.0.1:1/unused")

import backup_storage  # noqa: E402
from services.storage import StorageUnavailable  # noqa: E402


class FakeStorage:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = dict(objects)
        self.fail_reads: dict[str, int] = {}  # key -> 남은 실패 횟수
        self.on_list = None  # 목록을 뽑은 직후 부를 함수(목록 도중 변경 흉내)
        self.lists = 0

    def list_keys(self, prefix=""):
        self.lists += 1
        keys = sorted(self.objects)
        if self.on_list:
            hook, self.on_list = self.on_list, None
            hook(self)
        return keys

    def read(self, key, max_bytes):
        left = self.fail_reads.get(key, 0)
        if left:
            self.fail_reads[key] = left - 1
            raise StorageUnavailable("storage GET failed: HTTP 503")
        if key not in self.objects:
            raise StorageUnavailable("storage GET failed: HTTP 400")
        return self.objects[key]

    def size(self, key):
        return len(self.objects[key]) if key in self.objects else None


def _run(tmp_path, st):
    out = tmp_path / "b.zip"
    code = backup_storage.main(str(out), storage=st, sleep=lambda _s: None)
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        manifest = zf.read("_manifest.txt").decode("utf-8")
    return code, names, manifest


def test_스테이징은_빼고_첨부는_담는다(tmp_path):
    st = FakeStorage({"attachments/a.png": b"A", "staging/u1/x.csv": b"S"})
    code, names, manifest = _run(tmp_path, st)
    assert code == 0
    assert "attachments/a.png" in names
    assert "staging/u1/x.csv" not in names
    assert "objects: 1" in manifest


def test_목록_뒤에_지워진_객체는_실패가_아니라_누락으로_적는다(tmp_path):
    st = FakeStorage({"attachments/a.png": b"A", "attachments/b.png": b"B"})
    st.on_list = lambda s: s.objects.pop("attachments/a.png")
    code, names, manifest = _run(tmp_path, st)
    assert code == 0
    assert "attachments/b.png" in names and "attachments/a.png" not in names
    assert "deleted during backup: attachments/a.png" in manifest


def test_일시_장애는_다시_시도한다(tmp_path):
    st = FakeStorage({"attachments/a.png": b"A"})
    st.fail_reads["attachments/a.png"] = 2
    code, names, _ = _run(tmp_path, st)
    assert code == 0 and "attachments/a.png" in names


def test_계속_실패하면_나머지는_담고_종료코드_1(tmp_path):
    st = FakeStorage({"attachments/a.png": b"A", "attachments/b.png": b"B"})
    st.fail_reads["attachments/a.png"] = 99
    code, names, manifest = _run(tmp_path, st)
    assert code == 1
    assert "attachments/b.png" in names
    assert "failed: attachments/a.png" in manifest


def test_첫_목록_뒤에_생긴_객체는_두_번째_목록에서_담는다(tmp_path):
    # offset 페이지 사이에 앞쪽 객체가 지워지면 뒤 객체가 앞 페이지로 밀려 첫 목록에서 빠질 수 있다.
    st = FakeStorage({"attachments/a.png": b"A"})
    st.on_list = lambda s: s.objects.__setitem__("attachments/z.png", b"Z")
    code, names, _ = _run(tmp_path, st)
    assert code == 0
    assert {"attachments/a.png", "attachments/z.png"} <= names
    assert st.lists == 2


@pytest.mark.parametrize("bad", ["../x", "/abs"])
def test_이상한_키는_zip_경로로_쓰지_않는다(tmp_path, bad):
    st = FakeStorage({bad: b"X", "attachments/a.png": b"A"})
    code, names, manifest = _run(tmp_path, st)
    assert bad not in names
    assert code == 1 and f"failed: {bad}" in manifest
