"""대시보드 TC 안정성

- 회차를 시간 순으로 늘어놓고 PASS 와 그 밖(FAIL · BLOCK)을 오간 횟수를 센다
- 매번 실패한 TC 는 불안정이 아니라 계속 실패로 센다
- NA · NS 는 실행이 아니라 빼고, min_runs 보다 적게 실행된 TC 는 보지 않는다
- 버전 묶음과 삭제된 TC 를 거른다

실행: cd backend && python -m pytest tests_unit/test_dashboard_stability.py -q
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestResult, TestResultValue, TestRun, User
from routes.dashboard import tc_stability

R = TestResultValue
P, F, B, NA, NS = R.PASS, R.FAIL, R.BLOCK, R.NA, R.NS

# TC 별 회차 결과 (R1 -> R4). R4 만 버전 1.6, 나머지는 1.5
PLAN = {
    "A": [P, F, P, F],     # 3번 뒤집힘
    "B": [F, F, F, F],     # 계속 실패
    "C": [P, P, P, P],     # 안정
    "D": [P, NS, NA, NS],  # 실행 1회뿐
    "E": [P, B, P, NS],    # BLOCK 도 PASS 가 아닌 쪽
    "X": [P, F, P, F],     # 삭제된 TC
}


@pytest.fixture
def env(pg_engine, tmp_path):
    engine = pg_engine

    db = sessionmaker(bind=engine)()
    u = User(username="u", password_hash="x", display_name="U", role="admin")
    db.add(u)
    db.flush()
    project = Project(name="P", created_by=u.id)
    db.add(project)
    db.flush()
    tcs = {}
    for n, key in enumerate(PLAN, start=1):
        tc = TestCase(project_id=project.id, no=n, tc_id=f"TC-{key}", category="cat", sheet_name="S", created_by=u.id,
                      deleted_at=datetime(2026, 9, 1) if key == "X" else None)
        db.add(tc)
        tcs[key] = tc
    db.flush()
    base = datetime(2026, 9, 1)
    for i in range(4):
        run = TestRun(project_id=project.id, name="수행", round=i + 1, version="1.6" if i == 3 else "1.5",
                      created_by=u.id, created_at=base + timedelta(days=i))
        db.add(run)
        db.flush()
        for key, seq in PLAN.items():
            db.add(TestResult(test_run_id=run.id, test_case_id=tcs[key].id, result=seq[i], executed_by=u.id))
    db.commit()
    yield db, project, u
    db.close()
    engine.dispose()


def _call(env, **kw):
    db, project, u = env
    args = dict(date_from=None, date_to=None, version=None, min_runs=2, limit=20)
    args.update(kw)
    return tc_stability(project.id, db=db, current_user=u, **args)


def test_뒤집힘_횟수와_계속_실패를_가른다(env):
    res = _call(env)
    assert res["analyzed"] == 4, "A · B · C · E. D 는 실행 1회, X 는 삭제"
    assert res["unstable_count"] == 2 and res["always_fail_count"] == 1
    a, e = res["unstable"]
    assert a["tc_id"] == "TC-A" and a["flips"] == 3 and a["flip_rate"] == 100.0
    assert a["fail"] == 2 and a["fail_rate"] == 50.0 and a["recent"] == ["PASS", "FAIL", "PASS", "FAIL"]
    assert a["last_run"] == "수행 R4"
    assert e["tc_id"] == "TC-E" and e["flips"] == 2 and e["block"] == 1 and e["fail"] == 0


def test_버전_묶음으로_좁힌다(env):
    res = _call(env, version="v1.5")
    a = next(x for x in res["unstable"] if x["tc_id"] == "TC-A")
    assert a["executed"] == 3 and a["flips"] == 2 and a["last_run"] == "수행 R3"


def test_min_runs_와_limit(env):
    res = _call(env, min_runs=4)
    assert [x["tc_id"] for x in res["unstable"]] == ["TC-A"], "E 는 실행 3회"
    assert len(_call(env, limit=1)["unstable"]) == 1


def test_기간으로_거른다(env):
    res = _call(env, date_from="2026-09-03")
    # R3 · R4 만 본다. A(P F) · B(F F) · C(P P) 가 2회씩, E 는 1회라 빠진다
    assert res["analyzed"] == 3 and res["unstable_count"] == 1 and res["always_fail_count"] == 1
