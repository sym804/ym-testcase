"""세 업로드 경로(TC 가져오기, 자동화 결과 가져오기, 첨부)가 upload_id 도 받는다.

기존 multipart 는 그대로 받는다(작은 파일, 외부 스크립트). 둘 중 정확히 하나를 보내야 한다.
첨부는 저장소 서비스로 저장·다운로드·삭제한다.

실행: cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_upload_paths.py -q
"""
import os

import pytest
import requests

import dev_db_guard

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)

CSV = ("No,TC ID,Test Script (Step-by-Step) - Step,Expected Result\r\n"
       "1,UP-1,1. 실행,성공\r\n2,UP-2,1. 실행,성공\r\n").encode("utf-8-sig")
JUNIT = b"""<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="a"><testcase name="UP-1 ok" time="1"></testcase>
<testcase name="UP-2 bad" time="1"><failure message="x"/></testcase></testsuite></testsuites>"""
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def project(h):
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__upload_paths__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    yield pid
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _staged(h, purpose, filename, data):
    r = requests.post(f"{BASE}/api/uploads", headers=h, json={
        "purpose": purpose, "filename": filename, "size": len(data), "content_type": "application/octet-stream"})
    assert r.status_code == 201, r.text
    t = r.json()
    url = t["url"] if t["url"].startswith("http") else BASE + t["url"]
    assert requests.request(t["method"], url, data=data, headers=t["headers"]).status_code == 200
    return t["upload_id"]


def _import_tcs(h, pid, **kw):
    return requests.post(f"{BASE}/api/projects/{pid}/testcases/import", headers=h, **kw)


def test_TC_가져오기는_upload_id_로도_된다(h, project):
    uid = _staged(h, "tc_import", "tcs.csv", CSV)
    r = _import_tcs(h, project, params={"upload_id": uid})
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 2


def test_TC_가져오기는_multipart_도_그대로(h, project):
    r = _import_tcs(h, project, files={"file": ("tcs.csv", CSV, "text/csv")})
    assert r.status_code == 201, r.text


def test_파일과_upload_id_를_둘_다_보내거나_둘_다_없으면_400(h, project):
    uid = _staged(h, "tc_import", "tcs.csv", CSV)
    both = _import_tcs(h, project, params={"upload_id": uid}, files={"file": ("tcs.csv", CSV, "text/csv")})
    assert both.status_code == 400, both.text
    assert _import_tcs(h, project).status_code == 400


def test_가져오기_미리보기도_upload_id_로(h, project):
    uid = _staged(h, "tc_import", "tcs.csv", CSV)
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import/preview", headers=h,
                      params={"upload_id": uid})
    assert r.status_code == 200, r.text


def _run_with_results(h, pid):
    assert _import_tcs(h, pid, files={"file": ("tcs.csv", CSV, "text/csv")}).status_code == 201
    r = requests.post(f"{BASE}/api/projects/{pid}/testruns", headers=h, json={"name": "R"})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]
    detail = requests.get(f"{BASE}/api/projects/{pid}/testruns/{run_id}", headers=h).json()
    return run_id, detail["results"][0]["id"]


def test_자동화_결과_가져오기는_upload_id_로도_된다(h, project):
    run_id, _ = _run_with_results(h, project)
    uid = _staged(h, "result_import", "junit.xml", JUNIT)
    r = requests.post(f"{BASE}/api/projects/{project}/testruns/{run_id}/results/import",
                      headers=h, params={"upload_id": uid})
    assert r.status_code == 200, r.text
    assert r.json()["counts"]["PASS"] == 1


def test_이름으로_결과_올리기도_upload_id_로(h, project):
    _run_with_results(h, project)
    uid = _staged(h, "result_import", "junit.xml", JUNIT)
    r = requests.post(f"{BASE}/api/projects/{project}/testruns/import", headers=h,
                      params={"upload_id": uid, "run_name": "R"})
    assert r.status_code in (200, 201), r.text


def test_첨부를_upload_id_로_붙이고_내려받고_지운다(h, project):
    _, result_id = _run_with_results(h, project)
    uid = _staged(h, "attachment", "shot.png", PNG)
    r = requests.post(f"{BASE}/api/attachments/{result_id}", headers=h, params={"upload_id": uid})
    assert r.status_code == 200, r.text
    att = r.json()
    assert att["file_size"] == len(PNG)
    d = requests.get(f"{BASE}/api/attachments/download/{att['id']}", headers=h)
    assert d.status_code == 200 and d.content == PNG

    from database import SessionLocal
    from models import Attachment
    from services.storage import get_storage
    db = SessionLocal()
    key = db.query(Attachment).filter(Attachment.id == att["id"]).one().filepath
    db.close()
    assert get_storage().size(key) == len(PNG)
    assert requests.delete(f"{BASE}/api/attachments/{att['id']}", headers=h).status_code == 204
    assert get_storage().size(key) is None


def test_첨부_multipart_도_저장소로(h, project):
    _, result_id = _run_with_results(h, project)
    r = requests.post(f"{BASE}/api/attachments/{result_id}", headers=h,
                      files={"file": ("shot.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    d = requests.get(f"{BASE}/api/attachments/download/{r.json()['id']}", headers=h)
    assert d.content == PNG


def test_upload_id_경로에도_확장자_검사가_걸린다(h, project):
    _, result_id = _run_with_results(h, project)
    uid = _staged(h, "attachment", "evil.exe", b"MZ")
    r = requests.post(f"{BASE}/api/attachments/{result_id}", headers=h, params={"upload_id": uid})
    assert r.status_code == 400, r.text


def test_프로젝트를_지우면_첨부_객체도_지운다(h):
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__upload_paths_del__"})
    pid = r.json()["id"]
    _, result_id = _run_with_results(h, pid)
    att = requests.post(f"{BASE}/api/attachments/{result_id}", headers=h,
                        files={"file": ("shot.png", PNG, "image/png")}).json()
    from database import SessionLocal
    from models import Attachment
    from services.storage import get_storage
    db = SessionLocal()
    key = db.query(Attachment).filter(Attachment.id == att["id"]).one().filepath
    db.close()
    assert requests.delete(f"{BASE}/api/projects/{pid}", headers=h).status_code in (200, 204)
    assert get_storage().size(key) is None
