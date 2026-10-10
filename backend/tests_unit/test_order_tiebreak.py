"""정렬 동점 깨기

시트 순서와 no 가 같은 행(지운 시트의 TC 들은 모두 맨 뒤 같은 자리이고, no 는 시트마다
1 부터라 겹친다)은 들어온 차례대로 남아, 같은 수행을 내보낼 때마다 순서가 바뀔 수 있었다.
마지막 키로 TC id 를 둔다. TC 목록 조회의 ORDER BY 도 같다.

실행: cd backend && python -m pytest tests_unit/test_order_tiebreak.py -q
"""
import os
import sys
from types import SimpleNamespace

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseSheet, User
from routes.testcases import list_testcases
from services.sheet_order import sort_results_for_export


def _row(tc_id, sheet, no):
    return SimpleNamespace(test_case_id=tc_id, test_case=SimpleNamespace(id=tc_id, sheet_name=sheet, no=no))


def test_내보내기_정렬은_들어온_차례와_무관하다():
    order = {"S": 0}
    # 지운 시트 X, Y 의 TC 는 둘 다 order 밖(맨 뒤)이고 no 가 1 로 같다
    rows = [_row(7, "Y", 1), _row(3, "X", 1), _row(1, "S", 1), _row(5, "X", 2)]
    a = [r.test_case_id for r in sort_results_for_export(rows, order)]
    b = [r.test_case_id for r in sort_results_for_export(list(reversed(rows)), order)]
    assert a == b == [1, 3, 7, 5]


@pytest.fixture
def env(pg_engine):
    db = sessionmaker(bind=pg_engine)()
    user = User(username="a", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.flush()
    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.flush()
    for i, name in enumerate(("S", "T")):
        db.add(TestCaseSheet(project_id=project.id, name=name, sort_order=i, is_folder=False))
    a = TestCase(project_id=project.id, no=1, tc_id="A", sheet_name="S", created_by=user.id)
    db.add(a)
    db.flush()
    b = TestCase(project_id=project.id, no=1, tc_id="B", sheet_name="T", created_by=user.id)
    db.add(b)
    db.commit()
    # A 를 고쳐 힙에서 B 뒤로 보낸다(UPDATE 는 새 행 버전을 뒤에 쓴다). 순서 키가 no 하나면
    # 동점인 A, B 가 저장된 차례로 나온다.
    db.execute(text("UPDATE test_cases SET remarks = 'x' WHERE id = :i"), {"i": a.id})
    db.commit()
    yield db, project, user, a, b
    db.close()


def test_TC_목록은_no_가_같으면_id_순이다(env):
    db, project, user, a, b = env
    rows = list_testcases(project.id, category=None, priority=None, search=None, sheet_name=None,
                          limit=None, offset=None, db=db, current_user=user)
    assert [r.tc_id for r in rows] == ["A", "B"]


def test_TC_목록_페이지는_no_동점에서도_id_순으로_끊긴다(pg_engine):
    """no 가 같은 TC 가 많을 때 LIMIT 이 붙으면 PostgreSQL 은 동점 사이 차례를 보장하지 않는다.

    페이지를 나눠 받는 쪽(MCP · 스크립트)이 같은 TC 를 두 번 받거나 빠뜨린다.
    """
    db = sessionmaker(bind=pg_engine)()
    try:
        user = User(username="a", password_hash="x", display_name="관리자", role="admin")
        db.add(user)
        db.flush()
        project = Project(name="P", created_by=user.id)
        db.add(project)
        db.flush()
        ids = []
        for i in range(40):
            db.add(TestCaseSheet(project_id=project.id, name=f"S{i}", sort_order=i, is_folder=False))
            tc = TestCase(project_id=project.id, no=1, tc_id=f"T{i:02d}", sheet_name=f"S{i}", created_by=user.id)
            db.add(tc)
            db.flush()
            ids.append(tc.id)
        db.commit()
        # 짝수 번째를 고쳐 힙 차례를 섞는다
        db.execute(text("UPDATE test_cases SET remarks = 'x' WHERE id = ANY(:ids)"), {"ids": ids[::2]})
        db.commit()
        got = []
        for off in range(0, 40, 7):
            got += [r.id for r in list_testcases(project.id, category=None, priority=None, search=None,
                                                 sheet_name=None, limit=7, offset=off, db=db, current_user=user)]
        assert got == sorted(ids)
    finally:
        db.close()
