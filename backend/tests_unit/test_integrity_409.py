"""TC ID 중복은 409 와 안내 문구로 돌려준다.

판정은 PostgreSQL 오류 메시지에 들어 있는 제약 이름으로 한다. SQLite 시절의
`test_cases.project_id, test_cases.tc_id` 형식 문자열 판정은 지웠다.
"""
import asyncio
import json
import os
import sys

import pytest
from sqlalchemy.exc import IntegrityError

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from models import Project, TestCase, User


def _dup_tc_id_error(s):
    u = User(username="u", password_hash="x", display_name="u")
    s.add(u)
    s.flush()
    p = Project(name="P", created_by=u.id)
    s.add(p)
    s.flush()
    s.add(TestCase(project_id=p.id, sheet_name="S", no=1, tc_id="TC-1", created_by=u.id))
    s.flush()
    s.add(TestCase(project_id=p.id, sheet_name="S", no=2, tc_id="TC-1", created_by=u.id))
    with pytest.raises(IntegrityError) as e:
        s.flush()
    s.rollback()
    return e.value


def test_TC_ID_중복은_409_와_안내_문구(pg_session):
    from starlette.requests import Request
    from main import integrity_error_handler

    exc = _dup_tc_id_error(pg_session)
    req = Request({"type": "http", "method": "PUT", "path": "/api/x", "headers": []})
    resp = asyncio.run(integrity_error_handler(req, exc))
    assert resp.status_code == 409
    assert "TC ID" in json.loads(resp.body)["detail"]
