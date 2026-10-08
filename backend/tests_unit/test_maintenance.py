"""일일 정리(Cron, 로컬 기동 정리 공통)."""
from datetime import timedelta

from sqlalchemy.orm import sessionmaker

from models import StagedUpload, StorageDeletion, User, now_kst
from services import maintenance


class _FlakyStorage:
    def __init__(self):
        self.objects = {"a/1.png": b"x", "a/2.png": b"y"}
        self.fail = True

    def delete(self, keys):
        if self.fail:
            raise OSError("storage down")
        for k in keys:
            self.objects.pop(k, None)


def test_삭제에_실패한_객체는_기록해_두고_다음_정리에서_지운다(pg_engine, monkeypatch):
    from routes import attachments

    st = _FlakyStorage()
    monkeypatch.setattr(attachments, "get_storage", lambda: st)
    monkeypatch.setattr(maintenance, "get_storage", lambda: st)
    s = sessionmaker(bind=pg_engine)()
    attachments.delete_attachment_objects(["a/1.png", "a/2.png"], s)
    s.commit()
    assert sorted(k for (k,) in s.query(StorageDeletion.storage_key)) == ["a/1.png", "a/2.png"]

    st.fail = False
    maintenance.retry_storage_deletions(s)
    s.commit()
    assert st.objects == {}
    assert s.query(StorageDeletion).count() == 0
    s.close()


def test_정리_중_저장소가_죽어도_나머지_정리는_한다(pg_engine, monkeypatch):
    st = _FlakyStorage()
    monkeypatch.setattr(maintenance, "get_storage", lambda: st)
    import services.staged_upload as su
    monkeypatch.setattr(su, "get_storage", lambda: st)
    s = sessionmaker(bind=pg_engine)()
    u = User(username="u", password_hash="x", display_name="u")
    s.add(u)
    s.flush()
    s.add(StagedUpload(id="c" * 32, user_id=u.id, purpose="tc_import", filename="x.csv",
                       declared_size=1, storage_key="staging/c/x.csv",
                       created_at=now_kst() - timedelta(days=3)))
    s.commit()
    result = maintenance.run_daily(s, engine=pg_engine)
    assert result["staged_uploads"] == 0  # 저장소 장애로 이번엔 못 지움
    assert s.query(StagedUpload).count() == 1  # 기록은 남아 다음에 다시 시도
    assert "testcases" in result and "rate_limit_events" in result
    s.close()
