"""저장소가 직접 받는 배포에서 로컬 전용 PUT 라우트는 저장소를 부르지 않고 400 이다(SYM-161).

전에는 배포 모드 판정에 서명 업로드 주소 발급을 썼다. 그 호출이 행 잠금을 쥔 채 최대
30초 걸리고, 쓰지도 않을 서명 주소를 하나 만든다.
"""
import requests

from auth_helpers import make_user
from models import StagedUpload, User
from routes import uploads as uploads_route
from services import staged_upload, storage as storage_mod


class _DirectStorage:
    direct_upload = True

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*a, **kw):
            self.calls.append(name)
            raise AssertionError(f"저장소 {name} 를 부르면 안 된다")
        return record


def test_직접_업로드_저장소면_네트워크_호출_없이_400(auth_env, monkeypatch):
    uid = make_user(auth_env.Session, username="up")
    with auth_env.Session() as s:
        row = staged_upload.new_upload(s, s.get(User, uid), "tc_import", "a.xlsx", 3, None)
        s.commit()
        token = staged_upload.upload_token(row)
        upload_id = row.id
    fake = _DirectStorage()
    monkeypatch.setattr(uploads_route, "get_storage", lambda: fake)

    r = requests.put(auth_env.base + f"/api/uploads/{upload_id}/content?token={token}", data=b"abc")

    assert r.status_code == 400, r.text
    assert fake.calls == []


def test_저장소_종류마다_직접_업로드_여부가_있다():
    assert storage_mod.LocalStorage("x").direct_upload is False
    assert storage_mod.SupabaseStorage("https://e.supabase.co", "k", "b").direct_upload is True


def test_상한을_넘겨_413_이면_행_잠금을_바로_푼다(auth_env, monkeypatch):
    """413 뒤 곧바로 다시 올리면 잠금이 남아 409 를 받던 경로."""
    uid = make_user(auth_env.Session, username="up2")
    with auth_env.Session() as s:
        row = staged_upload.new_upload(s, s.get(User, uid), "tc_import", "a.xlsx", 3, None)
        s.commit()
        token = staged_upload.upload_token(row)
        upload_id = row.id
    monkeypatch.setitem(staged_upload.PURPOSE_LIMITS, "tc_import", 4)
    seen = []
    orig = uploads_route.HTTPException

    def spy(*a, **kw):
        exc = orig(*a, **kw)
        if exc.status_code == 413:
            # 예외를 만드는 시점에 다른 연결이 그 행을 잠글 수 있어야 한다
            with auth_env.engine.connect() as c:
                got = c.exec_driver_sql(
                    "SELECT id FROM staged_uploads WHERE id = %s FOR UPDATE SKIP LOCKED", (upload_id,)
                ).first()
                seen.append(got is not None)
        return exc

    monkeypatch.setattr(uploads_route, "HTTPException", spy)
    r = requests.put(auth_env.base + f"/api/uploads/{upload_id}/content?token={token}", data=b"x" * 10)

    assert r.status_code == 413, r.text
    assert seen == [True]
    with auth_env.Session() as s:
        assert s.get(StagedUpload, upload_id) is not None
