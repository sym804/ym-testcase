"""파일 저장소. 로컬은 디스크, 배포는 Supabase Storage.

서버리스 함수의 디스크는 꺼지면 사라지므로 배포에서는 Supabase Storage 비공개 버킷을 쓴다.
`STORAGE_BACKEND=supabase` 면 Supabase, 아니면 로컬 디스크(`UPLOAD_DIR`, 기본 backend/uploads).

★Supabase 는 표준 라이브러리 urllib 로 REST 를 직접 부른다. 쓰는 경로가 다섯 개라 클라이언트
  라이브러리를 들일 이유가 없다. 경로는 공식 Python 클라이언트(storage3)와 같다.
★서비스 키는 서버에서만 쓴다. 클라이언트에 주는 주소(직접 업로드, 서명 다운로드)는
  Supabase 가 발급한 토큰만 담고 서비스 키는 담지 않는다.
★모듈을 임포트한다고 폴더를 만들지 않는다. 서버리스 파일시스템은 쓰기가 막혀 있을 수 있다.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import HTTPException

_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)*$")


def check_key(key: str) -> str:
    """키는 ASCII 영숫자와 `_ . -` 와 `/` 만. 경로 이탈(`..`)과 절대 경로를 막는다."""
    if not key or not _KEY_RE.match(key) or any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError(f"잘못된 저장소 키: {key!r}")
    return key


def _too_large(max_bytes: int) -> HTTPException:
    return HTTPException(status_code=413, detail=f"File too large. Maximum size is {max_bytes // (1024 * 1024)}MB")


class LocalStorage:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def _path(self, key: str) -> str:
        path = os.path.abspath(os.path.join(self.root, *check_key(key).split("/")))
        if not path.startswith(self.root + os.sep):
            raise ValueError(f"잘못된 저장소 키: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str | None) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def read(self, key: str, max_bytes: int) -> bytes:
        with open(self._path(key), "rb") as f:
            data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise _too_large(max_bytes)
        return data

    def size(self, key: str) -> int | None:
        path = self._path(key)
        return os.path.getsize(path) if os.path.isfile(path) else None

    def delete(self, keys: list[str]) -> None:
        for key in keys:
            path = self._path(key)
            if os.path.isfile(path):
                os.remove(path)

    def local_path(self, key: str) -> str:
        """로컬 다운로드 스트리밍용 실제 경로."""
        return self._path(key)

    def upload_target(self, key: str, content_type: str | None) -> dict | None:
        return None

    def download_url(self, key: str, filename: str, expires_sec: int = 60) -> str | None:
        return None


class SupabaseStorage:
    def __init__(self, base_url: str, service_key: str, bucket: str):
        self.base = base_url.rstrip("/") + "/storage/v1"
        self.key = service_key
        self.bucket = bucket

    def _req(self, method: str, path: str, data: bytes | None = None, headers: dict | None = None):
        h = {"Authorization": f"Bearer {self.key}", "apikey": self.key}
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        return urllib.request.urlopen(req, timeout=30)

    def _json(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        with self._req(method, path, data, {"content-type": "application/json"}) as r:
            return json.loads(r.read() or b"null")

    def _obj(self, key: str) -> str:
        return f"/object/{self.bucket}/{urllib.parse.quote(check_key(key))}"

    def put(self, key: str, data: bytes, content_type: str | None) -> None:
        headers = {"content-type": content_type or "application/octet-stream", "x-upsert": "true"}
        with self._req("POST", self._obj(key), data, headers):
            pass

    def read(self, key: str, max_bytes: int) -> bytes:
        with self._req("GET", self._obj(key)) as r:
            data = r.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise _too_large(max_bytes)
        return data

    def size(self, key: str) -> int | None:
        try:
            with self._req("HEAD", self._obj(key)) as r:
                length = r.headers.get("content-length")
                return int(length) if length is not None else None
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            raise

    def delete(self, keys: list[str]) -> None:
        if keys:
            self._json("DELETE", f"/object/{self.bucket}", {"prefixes": [check_key(k) for k in keys]})

    def upload_target(self, key: str, content_type: str | None) -> dict | None:
        res = self._json("POST", f"/object/upload/sign/{self.bucket}/{urllib.parse.quote(check_key(key))}")
        return {
            "method": "PUT",
            "url": self.base + res["url"],
            "headers": {"content-type": content_type or "application/octet-stream"},
        }

    def download_url(self, key: str, filename: str, expires_sec: int = 60) -> str | None:
        res = self._json("POST", f"/object/sign/{self.bucket}/{urllib.parse.quote(check_key(key))}",
                         {"expiresIn": expires_sec})
        return self.base + res["signedURL"] + "&download=" + urllib.parse.quote(filename)


def get_storage():
    if os.getenv("STORAGE_BACKEND", "local") == "supabase":
        return SupabaseStorage(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            os.getenv("STORAGE_BUCKET", "attachments"),
        )
    root = os.getenv("UPLOAD_DIR") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    return LocalStorage(root)
