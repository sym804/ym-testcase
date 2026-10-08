"""Supabase Storage 버킷의 객체를 zip 하나로 내려받는다. 백업 워크플로가 부른다.

Supabase 의 DB 백업에는 Storage 객체가 들어가지 않는다. 그래서 따로 받는다.
스테이징(staging/)은 하루 안에 지워지는 임시 업로드라 담지 않는다.

    (환경변수 STORAGE_BACKEND=supabase, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, STORAGE_BUCKET)
    python scripts/backup_storage.py storage-backup.zip

zip 안의 _manifest.txt 에 담은 수, 백업 도중 지워진 객체, 실패한 객체를 적는다.
실패가 하나라도 있으면 나머지를 다 담은 뒤 종료코드 1 을 낸다.
"""
import os
import re
import sys
import time
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from services.storage import StorageUnavailable, get_storage  # noqa: E402

#: 객체 하나의 상한. 첨부 상한(50MB)보다 넉넉하게
MAX_OBJECT = 100 * 1024 * 1024
SKIP_PREFIXES = ("staging/",)
RETRIES = 3
_SAFE_KEY = re.compile(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*")


def _wanted(keys, done):
    return [k for k in keys if k not in done and not k.startswith(SKIP_PREFIXES)]


def main(out_path: str, *, storage=None, sleep=time.sleep) -> int:
    st = storage or get_storage()
    done: set[str] = set()
    deleted: list[str] = []
    failed: list[str] = []

    def backup_one(zf, key):
        # zip 경로로 쓰는 키라 저장소 키 규칙(상대 경로, .. 없음)을 다시 확인한다.
        if not _SAFE_KEY.fullmatch(key) or ".." in key.split("/"):
            failed.append(key)
            return
        for attempt in range(RETRIES):
            try:
                zf.writestr(key, st.read(key, MAX_OBJECT))
                done.add(key)
                return
            except StorageUnavailable:
                if st.size(key) is None:  # 목록을 뽑은 뒤 지워졌다
                    deleted.append(key)
                    return
                if attempt < RETRIES - 1:
                    sleep(2 ** attempt)
        failed.append(key)

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key in _wanted(st.list_keys(), done):
            backup_one(zf, key)
        # 목록은 offset 페이지라, 도중에 앞쪽 객체가 지워지면 뒤 객체가 앞 페이지로 밀려 빠진다.
        # 한 번 더 뽑아 처음 목록에 없던 것을 담는다.
        seen = done | set(deleted) | set(failed)
        for key in _wanted(st.list_keys(), seen):
            backup_one(zf, key)
        lines = [f"objects: {len(done)}"]
        lines += [f"deleted during backup: {k}" for k in deleted]
        lines += [f"failed: {k}" for k in failed]
        zf.writestr("_manifest.txt", "\n".join(lines) + "\n")

    print(f"objects: {len(done)}, deleted during backup: {len(deleted)}, failed: {len(failed)}")
    print(f"zip bytes: {os.path.getsize(out_path)}")
    for k in failed:
        print(f"failed: {k}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "storage-backup.zip"))
