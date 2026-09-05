"""한 런에서 한 TC 의 결과 행은 하나다 (SYM-5).

결과 행을 만드는 경로가 셋이다(런 생성 / 런 동기화 / 결과 제출). 셋 다 "없는 것을
조회한 뒤 넣는" 모양이라 동시 요청에서 같은 쌍이 두 번 들어갈 수 있었다.
실제로 운영 DB 에 하나 있었다(run=25, case=5345).

이 파일은 HTTP 를 타지 않는다. 제약과 삽입 헬퍼, 그리고 마이그레이션의 병합 규칙만 본다.
다만 conftest 의 세션 autouse 픽스처가 여전히 uvicorn 을 띄운다. 이 파일이 서버를
쓰지 않을 뿐이지, 이 파일만 돌려도 서버는 뜬다(QA 지적).
"""
import importlib.util
import os
import sys

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _app_models():
    """models 를 **함수 안에서** 들인다.

    ★모듈 최상단에서 import 하면 안 된다. models -> database 인데 database 는
      import 시점에 DATABASE_URL 을 읽어 엔진을 만든다. pytest 는 수집 단계에서
      테스트 모듈을 import 하므로, 최상단 import 는 conftest 의 세션 픽스처가
      DATABASE_URL 을 임시 DB 로 바꾸기 **전에** 엔진을 운영 DB 로 굳혀 버린다.
      그러면 다른 테스트 파일이 운영 admin 비밀번호로 로그인하려다 전부 죽는다
      (2026-09-05 실측: 이 파일을 추가하자 test_security.py 169건이 에러).
    """
    import models
    return models


def _sync_service():
    from services import run_sync_service
    return run_sync_service

MIGRATION = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "alembic", "versions", "a1c4e7b9d2f0_unique_test_results_run_case.py",
)


@pytest.fixture
def db():
    m = _app_models()
    Base, User, Project = m.Base, m.User, m.Project
    TestRun, TestRunStatus, TestCase = m.TestRun, m.TestRunStatus, m.TestCase
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    user = User(username="u", password_hash="x", display_name="U", role="admin")
    s.add(user)
    s.flush()
    proj = Project(name="P", created_by=user.id)
    s.add(proj)
    s.flush()
    run = TestRun(project_id=proj.id, name="R", status=TestRunStatus.in_progress,
                  created_by=user.id)
    s.add(run)
    s.flush()
    cases = [TestCase(project_id=proj.id, no=i, tc_id=f"TC-{i:03d}", created_by=user.id)
             for i in (1, 2, 3)]
    s.add_all(cases)
    s.commit()
    s.info["user"], s.info["project"], s.info["run"] = user, proj, run
    s.info["cases"] = cases
    yield s
    s.close()


def _row(run, case, user, result=None):
    if result is None:
        result = _app_models().TestResultValue.NS
    return {"test_run_id": run.id, "test_case_id": case.id,
            "result": result, "executed_by": user.id}


# ── 제약 자체 ─────────────────────────────────────────────────────────────────

def test_유니크_인덱스가_스키마에_있다(db):
    """★제약이 실제로 걸렸는지 먼저 단언한다. 안 걸렸으면 아래 테스트는 무의미하다."""
    names = {i["name"] for i in inspect(db.get_bind()).get_indexes("test_results")}
    assert "uq_test_results_run_case" in names


def test_같은_런과_TC_로_두_번_넣으면_거부된다(db):
    run, user, case = db.info["run"], db.info["user"], db.info["cases"][0]
    TestResult = _app_models().TestResult
    db.add(TestResult(**_row(run, case, user)))
    db.commit()
    db.add(TestResult(**_row(run, case, user, _app_models().TestResultValue.PASS)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_다른_런이면_같은_TC_라도_들어간다(db):
    run, user, case = db.info["run"], db.info["user"], db.info["cases"][0]
    m = _app_models()
    TestRun, TestRunStatus, TestResult = m.TestRun, m.TestRunStatus, m.TestResult
    other = TestRun(project_id=db.info["project"].id, name="R2",
                    status=TestRunStatus.in_progress, created_by=user.id)
    db.add(other)
    db.flush()
    TestResult = _app_models().TestResult
    db.add(TestResult(**_row(run, case, user)))
    db.add(TestResult(**_row(other, case, user)))
    db.commit()
    assert db.query(_app_models().TestResult).count() == 2


# ── 삽입 헬퍼 ─────────────────────────────────────────────────────────────────

def test_충돌_행은_건너뛰고_나머지는_들어간다(db):
    """★예외로 처리하면 세션이 죽어 나머지 행까지 못 넣는다. 그것을 막는지 본다."""
    run, user, cases = db.info["run"], db.info["user"], db.info["cases"]
    TestResult = _app_models().TestResult
    db.add(TestResult(**_row(run, cases[0], user)))
    db.commit()

    inserted = _sync_service().insert_results_ignoring_duplicates(
        db, [_row(run, c, user) for c in cases]      # 3개 중 1개는 이미 있다
    )
    db.commit()
    assert inserted == 2, "이미 있는 하나만 빠지고 둘은 들어가야 한다"
    assert db.query(_app_models().TestResult).count() == 3


def test_빈_목록은_아무_일도_안_한다(db):
    assert _sync_service().insert_results_ignoring_duplicates(db, []) == 0


# ── 동기화 멱등성 ─────────────────────────────────────────────────────────────

def test_동기화를_두_번_돌려도_행이_안_늘어난다(db):
    run = db.info["run"]
    first = _sync_service().sync_run_results(run, db)
    assert first == 3
    second = _sync_service().sync_run_results(run, db)
    assert second == 0, "두 번째 호출은 새로 넣을 것이 없어야 한다"
    assert db.query(_app_models().TestResult).count() == 3


def test_완료된_런은_동기화하지_않는다(db):
    run = db.info["run"]
    run.status = _app_models().TestRunStatus.completed
    db.commit()
    assert _sync_service().sync_run_results(run, db) == 0
    assert db.query(_app_models().TestResult).count() == 0


# ── 마이그레이션의 병합 규칙 ──────────────────────────────────────────────────

def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_a1c4e7b9d2f0", MIGRATION)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_병합은_텍스트를_버리지_않는다():
    """★중복 두 행이 서로 다른 측정값을 갖고 있었다. 지우면 기록이 사라진다."""
    merge = _load_migration()._merge_text
    assert merge(["홈 0.24초", "종목상세 0.28초"]) == "홈 0.24초\n종목상세 0.28초"


def test_병합은_빈_값과_중복을_뺀다():
    merge = _load_migration()._merge_text
    assert merge([None, "  ", "같음", "같음", "다름"]) == "같음\n다름"
    assert merge([None, ""]) is None


def _rows(*specs):
    """(id, result, actual, remarks, link, executed_by, at, start, fin, dur) 를 dict 로."""
    keys = ("id", "result", "actual_result", "remarks", "issue_link",
            "executed_by", "executed_at", "started_at", "finished_at", "duration_sec")
    return [dict(zip(keys, spec)) for spec in specs]


def test_실제_결과가_있는_행을_남겨_실행_메타데이터를_지킨다():
    """★남길 행을 '가장 최근' 으로 잡으면 그게 NS 자리표시자일 때 실행자와
       소요시간이 통째로 사라진다. 실제 결과가 있는 행을 남겨야 한다(QA2 지적)."""
    plan = _load_migration().plan_merge
    keep, vals, drop = plan(_rows(
        (10, "PASS", "측정 0.24초", None, None, 7, "2026-04-09", None, None, 3.5),
        (11, "NS", None, None, None, 1, "2026-04-10", None, None, None),
    ))
    assert keep == 10, "NS 자리표시자가 아니라 실제 결과 행을 남겨야 한다"
    assert drop == [11]
    assert vals["executed_by"] == 7 and vals["duration_sec"] == 3.5
    assert vals["actual_result"] == "측정 0.24초"


def test_결과가_서로_다르면_비고에_남긴다():
    """★PASS 와 FAIL 이 섞인 중복을 조용히 하나만 남기면 사람이 못 본다(QA1 지적)."""
    plan = _load_migration().plan_merge
    _, vals, _ = plan(_rows(
        (10, "PASS", None, None, None, 1, None, None, None, None),
        (11, "FAIL", None, None, None, 1, None, None, None, None),
    ))
    assert "결과가 서로 달랐다" in (vals["remarks"] or "")
    assert "PASS" in vals["remarks"] and "FAIL" in vals["remarks"]


def test_이슈_링크는_하나만_남기고_나머지는_비고로():
    """★issue_link 는 단일 URL 칸이다. 줄바꿈으로 이으면 프론트의 startsWith 판정과
       PDF 리포트 셀이 깨진다(QA 양쪽 지적)."""
    plan = _load_migration().plan_merge
    _, vals, _ = plan(_rows(
        (10, "PASS", None, None, "https://a/1", 1, None, None, None, None),
        (11, "FAIL", None, None, "https://b/2", 1, None, None, None, None),
    ))
    assert chr(10) not in (vals["issue_link"] or ""), "링크 칸에 줄바꿈이 들어가면 안 된다"
    assert vals["issue_link"] == "https://b/2"
    assert "https://a/1" in (vals["remarks"] or "")


def test_전부_NS_면_마지막_행을_남긴다():
    plan = _load_migration().plan_merge
    keep, vals, drop = plan(_rows(
        (10, "NS", None, None, None, 1, None, None, None, None),
        (11, "NS", None, None, None, 2, None, None, None, None),
    ))
    assert keep == 11 and drop == [10] and vals["executed_by"] == 2


def test_실제_SQLite_에서_중복이_병합되고_첨부가_따라온다(tmp_path):
    """★헬퍼만 단위 테스트하면 마이그레이션 본체는 한 줄도 안 돌아 본다(QA 양쪽 지적).
       진짜 SQLite 에 중복을 넣고 merge_duplicates 를 돌려 결과를 본다."""
    from sqlalchemy import create_engine, text
    mig = _load_migration()
    eng = create_engine("sqlite:///" + str(tmp_path / "m.db"))
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE test_results ("
            " id INTEGER PRIMARY KEY, test_run_id INT, test_case_id INT, result TEXT,"
            " actual_result TEXT, issue_link TEXT, remarks TEXT, executed_by INT,"
            " executed_at TEXT, started_at TEXT, finished_at TEXT, duration_sec REAL)"))
        c.execute(text(
            "CREATE TABLE attachments (id INTEGER PRIMARY KEY, test_result_id INT)"))
        c.execute(text(
            "INSERT INTO test_results"
            " (id, test_run_id, test_case_id, result, actual_result, executed_by, duration_sec)"
            " VALUES (1, 5, 9, 'PASS', '홈 0.24초', 7, 1.5),"
            "        (2, 5, 9, 'NS', NULL, 1, NULL),"
            "        (3, 5, 8, 'PASS', '단독', 1, NULL)"))
        c.execute(text("INSERT INTO attachments (id, test_result_id) VALUES (1, 2)"))
        groups = mig.merge_duplicates(c)

    with eng.begin() as c:
        rows = c.execute(text(
            "SELECT id, result, actual_result, executed_by, duration_sec"
            " FROM test_results ORDER BY id")).fetchall()
        att = c.execute(text("SELECT test_result_id FROM attachments")).fetchall()
    assert groups == 1
    assert [r[0] for r in rows] == [1, 3], "실제 결과가 있는 1번이 남고 NS 인 2번이 지워져야 한다"
    assert rows[0][3] == 7 and rows[0][4] == 1.5, "실행자와 소요시간이 살아 있어야 한다"
    assert att == [(1,)], "지워진 행의 첨부가 남을 행으로 옮겨져야 한다"
