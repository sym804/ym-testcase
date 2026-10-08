"""운영 보조 엔드포인트: /api/config, Cron 일일 정리.

실행: cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_internal.py -q
"""
import os
import threading
from datetime import timedelta

import pytest
import requests

import dev_db_guard

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
CRON = f"{BASE}/api/internal/cron/daily"

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)


def test_config_는_로그인_없이_업로드_상한을_준다():
    r = requests.get(f"{BASE}/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["upload_limits"] == {"attachment": 50 * 1024 * 1024, "tc_import": 10 * 1024 * 1024,
                                     "result_import": 20 * 1024 * 1024}
    assert body["direct_upload"] is False  # 로컬 저장소


def test_cron_비밀값이_설정되지_않았으면_503(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    assert requests.get(CRON, headers={"Authorization": "Bearer x"}).status_code == 503


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "s3cret"}])
def test_cron_인증이_없거나_틀리면_401(monkeypatch, headers):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    assert requests.get(CRON, headers=headers).status_code == 401


def test_cron_은_오래된_미처리_업로드를_지운다(monkeypatch):
    from database import SessionLocal
    from models import StagedUpload, User, now_kst
    from services.storage import get_storage

    monkeypatch.setenv("CRON_SECRET", "s3cret")
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").one()
    old = StagedUpload(id="a" * 32, user_id=admin.id, purpose="tc_import", filename="old.csv",
                       declared_size=3, storage_key="staging/" + "a" * 32 + "/old.csv",
                       created_at=now_kst() - timedelta(days=2))
    fresh = StagedUpload(id="b" * 32, user_id=admin.id, purpose="tc_import", filename="new.csv",
                         declared_size=3, storage_key="staging/" + "b" * 32 + "/new.csv")
    db.add_all([old, fresh])
    db.commit()
    get_storage().put(old.storage_key, b"old", None)
    get_storage().put(fresh.storage_key, b"new", None)
    db.close()

    r = requests.get(CRON, headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200, r.text
    assert r.json()["staged_uploads"] >= 1
    assert get_storage().size("staging/" + "a" * 32 + "/old.csv") is None
    assert get_storage().size("staging/" + "b" * 32 + "/new.csv") == 3

    db = SessionLocal()
    ids = {row.id for row in db.query(StagedUpload).filter(StagedUpload.id.in_(["a" * 32, "b" * 32]))}
    db.query(StagedUpload).filter(StagedUpload.id == "b" * 32).delete()
    db.commit()
    db.close()
    assert ids == {"b" * 32}


def test_cron_이_이미_돌고_있으면_건너뛴다(monkeypatch):
    from sqlalchemy import create_engine, text

    monkeypatch.setenv("CRON_SECRET", "s3cret")
    eng = create_engine(os.environ["DATABASE_URL"])
    conn = eng.connect()
    tx = conn.begin()
    conn.execute(text("SELECT pg_advisory_xact_lock(3, 0)"))
    try:
        r = requests.get(CRON, headers={"Authorization": "Bearer s3cret"}, timeout=10)
    finally:
        tx.rollback()
        conn.close()
        eng.dispose()
    assert r.status_code == 200, r.text
    assert r.json() == {"skipped": "running"}
