"""같은 결과 행을 같은 기준값(expected_executed_at)으로 동시에 저장하면 하나만 성공한다.

낙관적 잠금은 "읽어서 비교한 뒤 UPDATE" 라, 두 요청이 같은 값을 읽으면 둘 다 통과해
늦게 끝난 쪽이 앞의 저장을 덮는다. 행을 잠그고 읽어야 기다린 쪽이 바뀐 값을 본다.
"""
import threading

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, User
from routes.testruns import submit_results
from schemas import TestResultCreate

N = 6


def _seed(engine):
    s = sessionmaker(bind=engine)()
    users = [User(username=f"u{i}", password_hash="x", display_name=f"U{i}", role="admin") for i in range(N)]
    s.add_all(users)
    s.flush()
    p = Project(name="P", created_by=users[0].id)
    s.add(p)
    s.flush()
    s.add(TestCaseSheet(project_id=p.id, name="S", sort_order=0, is_folder=False))
    tc = TestCase(project_id=p.id, no=1, tc_id="T-1", test_steps="1", expected_result="2",
                  sheet_name="S", created_by=users[0].id)
    s.add(tc)
    run = TestRun(project_id=p.id, name="R", round=1, created_by=users[0].id)
    s.add(run)
    s.flush()
    row = TestResult(test_run_id=run.id, test_case_id=tc.id, result=TestResultValue.NS,
                     executed_by=users[0].id)
    s.add(row)
    s.commit()
    seen = row.executed_at.isoformat()
    ids = (p.id, run.id, tc.id, [u.id for u in users])
    s.close()
    return ids, seen


def test_같은_기준값으로_동시에_저장하면_하나만_성공한다(pg_engine):
    (pid, run_id, tc_id, user_ids), seen = _seed(pg_engine)
    Session = sessionmaker(bind=pg_engine)
    barrier = threading.Barrier(N)
    outcomes = []

    def save(i):
        s = Session()
        try:
            user = s.get(User, user_ids[i])
            barrier.wait()
            submit_results(pid, run_id, [TestResultCreate(
                test_case_id=tc_id, result="PASS" if i % 2 else "FAIL", expected_executed_at=seen,
            )], db=s, current_user=user)
            outcomes.append(200)
        except HTTPException as e:
            outcomes.append(e.status_code)
        finally:
            s.close()

    threads = [threading.Thread(target=save, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == [200] + [409] * (N - 1), outcomes
