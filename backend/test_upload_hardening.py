"""업로드·첨부 경로의 경계 조건 (QA 2인 지적 반영).

실행: cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_upload_hardening.py -q
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
import requests

import dev_db_guard

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)

CSV = ("No,TC ID,Test Script (Step-by-Step) - Step,Expected Result\r\n"
       "1,HD-1,1. 실행,성공\r\n").encode("utf-8-sig")
JUNIT = b'<testsuites><testsuite name="a"><testcase name="HD-1 ok" time="1"/></testsuite></testsuites>'
PNG = b"\x89PNG\r\n\x1a\n" + b"1" * 16


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def project(h):
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": f"__hard_{uuid.uuid4().hex[:6]}"})
    pid = r.json()["id"]
    yield pid
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _issue(h, purpose, filename, size):
    r = requests.post(f"{BASE}/api/uploads", headers=h, json={
        "purpose": purpose, "filename": filename, "size": size, "content_type": "application/octet-stream"})
    assert r.status_code == 201, r.text
    return r.json()


def _put(t, data):
    url = t["url"] if t["url"].startswith("http") else BASE + t["url"]
    return requests.request(t["method"], url, data=data, headers=t["headers"])


def _staged(h, purpose, filename, data):
    t = _issue(h, purpose, filename, len(data))
    assert _put(t, data).status_code == 200
    return t["upload_id"]


def _result_id(h, pid):
    requests.post(f"{BASE}/api/projects/{pid}/testcases/import", headers=h,
                  files={"file": ("t.csv", CSV, "text/csv")})
    run = requests.post(f"{BASE}/api/projects/{pid}/testruns", headers=h, json={"name": "R"}).json()
    detail = requests.get(f"{BASE}/api/projects/{pid}/testruns/{run['id']}", headers=h).json()
    return run["id"], detail["results"][0]["id"]


# ── 로컬 PUT ─────────────────────────────────────────────────────────────────

def test_같은_주소로_동시에_올리면_하나만_성공하고_내용이_섞이지_않는다(h):
    from database import SessionLocal
    from models import StagedUpload
    from services.storage import get_storage

    # 1MB 씩 올려 스트리밍 시간을 늘린다. 둘 다 "아직 없음" 확인을 지난 뒤 겹치게 한다.
    size = 1024 * 1024
    t = _issue(h, "tc_import", "a.csv", size)
    barrier = threading.Barrier(2)

    def go(data):
        barrier.wait()
        return _put(t, data).status_code

    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(go, [b"A" * size, b"B" * size]))
    assert codes == [200, 409], codes
    db = SessionLocal()
    key = db.query(StagedUpload).filter(StagedUpload.id == t["upload_id"]).one().storage_key
    db.close()
    stored = get_storage().read(key, size)
    assert stored in (b"A" * size, b"B" * size), "두 업로드가 섞였다"


def test_첨부로_쓴_업로드에는_다시_올릴_수_없다(h, project):
    _, rid = _result_id(h, project)
    t = _issue(h, "attachment", "a.png", len(PNG))
    assert _put(t, PNG).status_code == 200
    assert requests.post(f"{BASE}/api/attachments/{rid}", headers=h,
                         params={"upload_id": t["upload_id"]}).status_code == 200
    assert _put(t, b"evil").status_code in (404, 409)


def test_만료된_업로드_주소는_401(h, monkeypatch):
    from services import staged_upload

    monkeypatch.setattr(staged_upload, "TOKEN_TTL", timedelta(seconds=-1))
    t = _issue(h, "tc_import", "a.csv", 3)
    assert _put(t, b"abc").status_code == 401


# ── 꺼내 쓰기 ────────────────────────────────────────────────────────────────

def test_저장소에_상한보다_큰_객체가_있으면_첨부는_413(h, project, monkeypatch):
    """배포에서는 클라이언트가 저장소에 직접 올려 PUT 상한을 거치지 않는다. claim 이 유일한 가드다."""
    from database import SessionLocal
    from models import StagedUpload
    from services import staged_upload
    from services.storage import get_storage

    _, rid = _result_id(h, project)
    t = _issue(h, "attachment", "big.png", 10)
    db = SessionLocal()
    key = db.query(StagedUpload).filter(StagedUpload.id == t["upload_id"]).one().storage_key
    db.close()
    get_storage().put(key, b"x" * 100, None)
    monkeypatch.setitem(staged_upload.PURPOSE_LIMITS, "attachment", 50)
    r = requests.post(f"{BASE}/api/attachments/{rid}", headers=h, params={"upload_id": t["upload_id"]})
    assert r.status_code == 413, r.text


def test_미리보기와_가져오기에_같은_upload_id_를_쓴다(h, project):
    uid = _staged(h, "tc_import", "t.csv", CSV)
    p = requests.post(f"{BASE}/api/projects/{project}/testcases/import/preview", headers=h,
                      params={"upload_id": uid})
    assert p.status_code == 200, p.text
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import", headers=h, params={"upload_id": uid})
    assert r.status_code == 201, r.text


def test_dry_run_뒤_같은_upload_id_로_실제_반영(h, project):
    run_id, _ = _result_id(h, project)
    uid = _staged(h, "result_import", "j.xml", JUNIT)
    url = f"{BASE}/api/projects/{project}/testruns/{run_id}/results/import"
    assert requests.post(url, headers=h, params={"upload_id": uid, "dry_run": "true"}).status_code == 200
    r = requests.post(url, headers=h, params={"upload_id": uid})
    assert r.status_code == 200, r.text
    assert requests.post(url, headers=h, params={"upload_id": uid}).status_code == 409


# ── 다운로드 ─────────────────────────────────────────────────────────────────

def _attachment_row(h, pid, filepath):
    from database import SessionLocal
    from models import Attachment, User

    _, rid = _result_id(h, pid)
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").one()
    att = Attachment(test_result_id=rid, filename="old.png", filepath=filepath,
                     content_type="image/png", file_size=len(PNG), uploaded_by=admin.id)
    db.add(att)
    db.commit()
    att_id = att.id
    db.close()
    return att_id


def test_옛_형식_첨부_키도_내려받는다(h, project):
    """SQLite 시절 첨부는 업로드 폴더 바로 아래 `<hex>.ext` 였다."""
    key = f"{uuid.uuid4().hex}.png"
    with open(os.path.join(os.environ["UPLOAD_DIR"], key), "wb") as f:
        f.write(PNG)
    att_id = _attachment_row(h, project, key)
    d = requests.get(f"{BASE}/api/attachments/download/{att_id}", headers=h)
    assert d.status_code == 200 and d.content == PNG


def test_경로_이탈_키는_403(h, project):
    att_id = _attachment_row(h, project, "../outside.png")
    assert requests.get(f"{BASE}/api/attachments/download/{att_id}", headers=h).status_code == 403


def test_저장소_장애면_503(h, project, monkeypatch):
    from routes import attachments
    from services.storage import StorageUnavailable

    class Down:
        def download_url(self, *a, **k):
            raise StorageUnavailable("down")

    att_id = _attachment_row(h, project, f"{uuid.uuid4().hex}.png")
    monkeypatch.setattr(attachments, "get_storage", lambda: Down())
    r = requests.get(f"{BASE}/api/attachments/download/{att_id}", headers=h)
    assert r.status_code == 503, r.text
    assert "저장소" in r.json()["detail"]
