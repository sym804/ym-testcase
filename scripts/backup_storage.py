"""Supabase Storage 버킷의 객체를 zip 하나로 내려받는다. 백업 워크플로가 부른다.

Supabase 의 DB 백업에는 Storage 객체가 들어가지 않는다. 그래서 따로 받는다.

    (환경변수 STORAGE_BACKEND=supabase, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, STORAGE_BUCKET)
    python scripts/backup_storage.py storage-backup.zip
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from services.storage import get_storage  # noqa: E402

#: 객체 하나의 상한. 첨부 상한(50MB)보다 넉넉하게
MAX_OBJECT = 100 * 1024 * 1024


def main(out_path: str) -> int:
    st = get_storage()
    keys = st.list_keys()
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key in keys:
            zf.writestr(key, st.read(key, MAX_OBJECT))
    print(f"objects: {len(keys)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "storage-backup.zip"))
