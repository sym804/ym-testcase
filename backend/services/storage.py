"""파일 저장소. 로컬은 디스크, 배포는 Supabase Storage.

서버리스 함수의 디스크는 꺼지면 사라지므로 배포에서는 Supabase Storage 비공개 버킷을 쓴다.
`STORAGE_BACKEND=supabase` 면 Supabase, 아니면 로컬 디스크(`UPLOAD_DIR`, 기본 backend/uploads).

★Supabase 는 표준 라이브러리 urllib 로 REST 를 직접 부른다. 쓰는 경로가 여섯 개라 클라이언트
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
    if not key or not _KEY_RE.fullmatch(key) or any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError(f"잘못된 저장소 키: {key!r}")
    return key


class StorageConflict(Exception):
    """put_new: 같은 키에 이미 객체가 있다. 덮어쓰지 않았다."""


class StorageUnavailable(Exception):
    """저장소에 닿지 못했거나 저장소가 오류를 냈다. 앱은 503 으로 바꿔 응답한다.

    메시지에 서비스 키나 서명 주소를 넣지 않는다(로그에 남는다).
    """


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

    def put_new(self, key: str, data: bytes, content_type: str | None) -> None:
        """없을 때만 쓴다. 있으면 StorageConflict. 존재 확인과 쓰기가 한 번의 open 이다."""
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "xb") as f:
                f.write(data)
        except FileExistsError:
            raise StorageConflict(key) from None

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

    def list_keys(self, prefix: str = "") -> list[str]:
        """백업용. 모든 객체 키."""
        base = self.root
        out = []
        for dirpath, _dirs, files in os.walk(base):
            for f in files:
                rel = os.path.relpath(os.path.join(dirpath, f), base).replace(os.sep, "/")
                if rel.startswith(prefix):
                    out.append(rel)
        return out

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
        try:
            return urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (400, 404):
                raise
            raise StorageUnavailable(f"storage {method} failed: HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise StorageUnavailable(f"storage {method} failed: {type(e).__name__}") from None

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

    def put_new(self, key: str, data: bytes, content_type: str | None) -> None:
        """없을 때만 쓴다(x-upsert false). 있으면 StorageConflict.

        ★존재 확인을 HEAD(size) 로 하지 않는다. size() 는 HEAD 400 과 Content-Length 없음도
          None 으로 돌려줘서, 그걸 '없음' 으로 읽고 올리면 남의 객체를 덮어쓸 수 있다(QA 지적).
          Supabase 는 버전에 따라 중복을 409 또는 400 + statusCode "409" 로 알린다.
        """
        headers = {"content-type": content_type or "application/octet-stream", "x-upsert": "false"}
        h = {"Authorization": f"Bearer {self.key}", "apikey": self.key, **headers}
        req = urllib.request.Request(self.base + self._obj(key), data=data, method="POST", headers=h)
        try:
            with urllib.request.urlopen(req, timeout=30):
                return
        except urllib.error.HTTPError as e:
            body = e.read() or b""
            try:
                status = str(json.loads(body).get("statusCode", ""))
            except (ValueError, AttributeError):
                status = ""
            if e.code == 409 or (e.code == 400 and status == "409"):
                raise StorageConflict(key) from None
            raise StorageUnavailable(f"storage POST failed: HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise StorageUnavailable(f"storage POST failed: {type(e).__name__}") from None

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

    def list_keys(self, prefix: str = "") -> list[str]:
        """백업용. 폴더(id 가 없는 항목)를 따라 내려가며 모든 객체 키를 모은다."""
        out: list[str] = []
        stack = [prefix.strip("/")]
        while stack:
            folder = stack.pop()
            offset = 0
            while True:
                items = self._json("POST", f"/object/list/{self.bucket}",
                                   {"prefix": folder, "limit": 1000, "offset": offset})
                for it in items:
                    path = f"{folder}/{it['name']}" if folder else it["name"]
                    (stack.append if it.get("id") is None else out.append)(path)
                if len(items) < 1000:
                    break
                offset += 1000
        return out

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
