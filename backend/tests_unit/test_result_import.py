"""자동화 결과 파일 가져오기 (Playwright JSON · JUnit XML)

- 판정 규칙: 기록 스크립트(record_run_from_e2e.py)와 같은 결과가 나와야 한다.
- 두 형식이 같은 실행에서 같은 판정을 낸다.
- TC ID 매칭: 접미어 TC 우선, 없으면 변형 접미어를 떼고, 제목에 없으면 describe 에서.
- 저장: 이미 기록된 결과를 NS 로 덮지 않는 기본값, 이슈 링크 보존, 범위 밖 TC 미기록.
- XML: DTD 를 받지 않는다.

실행: cd backend && python -m pytest tests_unit/test_result_import.py -q
"""
import io
import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, TestRunStatus, User
from routes.testruns import import_results
from services.result_import import (
    ImportFormatError, aggregate, match_tc_id, parse_report,
)

R = TestResultValue
IDS = {"FE-A-01", "FE-A-01b", "FE-A-02", "FE-A-03", "FE-A-04", "FE-A-05", "FE-B-01", "FE-B-02", "FE-C-01"}


def _pw_test(status, expected="passed", results=None, annotations=None):
    return {"status": status, "expectedStatus": expected, "annotations": annotations or [],
            "results": results if results is not None else [{"status": "passed", "duration": 1000}]}


def _fail_res(msg="Error: \x1b[31mExpected: 2\x1b[39m\nReceived: 1"):
    return [{"status": "failed", "duration": 2000, "error": {"message": msg}}]


# Playwright 1.63 이 실제로 낸 리포트 모양을 줄인 것 (2026-10-01 실측)
PW_JSON = json.dumps({"suites": [{"title": "a.spec.mjs", "specs": [], "suites": [
    {"title": "묶음 A", "specs": [
        {"title": "FE-A-01 통과", "tests": [_pw_test("expected")]},
        {"title": "FE-A-02 실패", "tests": [_pw_test("unexpected", results=_fail_res())]},
        {"title": "FE-A-03 결함 고정", "tests": [_pw_test("expected", "failed", _fail_res(),
                                                   [{"type": "fail", "description": "이슈 #9"}])]},
        {"title": "FE-A-04 결함 해소", "tests": [_pw_test("unexpected", "failed", None,
                                                   [{"type": "fail", "description": "이슈 #10"}])]},
        {"title": "FE-A-05 건너뜀", "tests": [_pw_test("skipped", "skipped", [{"status": "skipped", "duration": 0}],
                                                 [{"type": "skip", "description": "화면 삭제"}])]},
        {"title": "FE-A-01b 접미어 TC", "tests": [_pw_test("expected")]},
        {"title": "접두어 없는 감시 테스트", "tests": [_pw_test("expected")]},
    ]},
    {"title": "연쇄", "specs": [
        {"title": "FE-B-01 앞", "tests": [_pw_test("unexpected", results=_fail_res())]},
        {"title": "FE-B-02 뒤", "tests": [_pw_test("skipped", "passed", [{"status": "skipped", "duration": 0}])]},
    ]},
]}]}).encode()

# 같은 실행을 Playwright junit 리포터(embedAnnotationsAsProperties: true)로 받은 모양
JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="a.spec.mjs">
<testcase name="묶음 A › FE-A-01 통과" time="1"></testcase>
<testcase name="묶음 A › FE-A-02 실패" time="2"><failure message="Expected: 2" type="expect.toBe"><![CDATA[<!DOCTYPE html> 본문]]></failure></testcase>
<testcase name="묶음 A › FE-A-03 결함 고정" time="2"><properties><property name="fail" value="이슈 #9"></property></properties></testcase>
<testcase name="묶음 A › FE-A-04 결함 해소" time="0"><properties><property name="fail" value="이슈 #10"></property></properties><failure message="Expected to fail, but passed." type="FAILURE"/></testcase>
<testcase name="묶음 A › FE-A-05 건너뜀"><properties><property name="skip" value="화면 삭제"></property></properties><skipped></skipped></testcase>
<testcase name="묶음 A › FE-A-01b 접미어 TC" time="1"></testcase>
<testcase name="묶음 A › 접두어 없는 감시 테스트" time="0"></testcase>
<testcase name="연쇄 › FE-B-01 앞" time="2"><failure message="Expected: 2"/></testcase>
<testcase name="연쇄 › FE-B-02 뒤"><skipped></skipped></testcase>
</testsuite></testsuites>""".encode()

EXPECTED = {
    "FE-A-01": ("PASS", "pass"),
    "FE-A-01b": ("PASS", "pass"),
    "FE-A-02": ("FAIL", "fail"),
    "FE-A-03": ("FAIL", "known_fail"),
    "FE-A-04": ("FAIL", "fixed_candidate"),
    "FE-A-05": ("NS", "skip"),
    "FE-B-01": ("FAIL", "fail"),
    "FE-B-02": ("NS", "not_run"),
}


# ── 판정 규칙 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("content,fmt", [(PW_JSON, "playwright-json"), (JUNIT, "junit-xml")])
def test_두_형식이_같은_판정을_낸다(content, fmt):
    got_fmt, entries = parse_report(content)
    assert got_fmt == fmt
    best, unmatched = aggregate(entries, IDS)
    assert {k: (v.result, v.kind) for k, v in best.items()} == EXPECTED
    assert unmatched == ["묶음 A › 접두어 없는 감시 테스트"]


def test_비고와_실제_결과():
    best, _ = aggregate(parse_report(PW_JSON)[1], IDS)
    assert best["FE-A-03"].note == "test.fail 로 고정한 기존 결함이 그대로 재현됨 (이슈 #9)"
    assert "해소 후보" in best["FE-A-04"].note
    assert best["FE-A-05"].note == "절차를 수행할 수 없어 건너뜀: 화면 삭제"
    assert best["FE-B-02"].note == "연쇄가 끊겨 미실행"
    assert best["FE-A-02"].actual == "Error: Expected: 2", "ANSI 색 코드를 지우고 첫 줄만"
    assert best["FE-A-01"].actual == "통과"
    assert best["FE-A-01"].duration_sec == 1.0


def test_재시도_뒤_통과는_PASS_와_flaky_비고():
    data = json.dumps({"suites": [{"title": "f", "specs": [{"title": "FE-A-01 x", "tests": [
        _pw_test("flaky", results=_fail_res() + [{"status": "passed", "duration": 500}])]}]}]}).encode()
    best, _ = aggregate(parse_report(data)[1], IDS)
    assert best["FE-A-01"].result == "PASS"
    assert best["FE-A-01"].note == "재시도 1회 후 통과 (flaky)"


def test_같은_TC_를_여러_테스트가_덮으면_FAIL_NS_PASS_순으로_나쁜_쪽():
    def run(*statuses):
        specs = []
        for i, st in enumerate(statuses):
            t = {"pass": _pw_test("expected"),
                 "fail": _pw_test("unexpected", results=_fail_res()),
                 "ns": _pw_test("skipped", results=[{"status": "skipped"}])}[st]
            specs.append({"title": f"FE-A-01 변형 {i}", "tests": [t]})
        data = json.dumps({"suites": [{"title": "f", "specs": specs}]}).encode()
        return aggregate(parse_report(data)[1], IDS)[0]["FE-A-01"]

    assert run("pass", "ns").result == "NS", "기록 스크립트 규칙: 한쪽이 안 돌았으면 다 확인된 것이 아니다"
    assert run("ns", "fail", "pass").result == "FAIL"
    o = run("pass", "pass")
    assert o.result == "PASS" and len(o.titles) == 2 and o.duration_sec == 2.0


# ── TC ID 매칭 ───────────────────────────────────────────────────────────────

def test_TC_ID_매칭():
    assert match_tc_id("FE-A-01b 접미어", IDS) == "FE-A-01b", "접미어 TC 는 별개의 TC"
    assert match_tc_id("FE-A-02a 변형", IDS) is None, "없는 접미어 TC 를 기본 TC 로 접지 않는다 (지운 TC 의 테스트가 흘러든다)"
    assert match_tc_id("[FE-A-02] 괄호", IDS) == "FE-A-02"
    assert match_tc_id("FE-A-02 (ko)", IDS) == "FE-A-02"
    assert match_tc_id("FE-A-021 다른 번호", IDS) is None, "숫자가 이어지면 다른 ID"
    assert match_tc_id("감시 FE-A-02", IDS) is None, "맨 앞이 아니면 매칭하지 않는다"
    assert match_tc_id("FE-Z-99 없는 TC", IDS) is None


def test_describe_의_ID_로_감시_테스트를_TC_에_넣지_않는다():
    # PASS 로 확정한 TC 의 test.fail 감시 테스트는 제목에서 ID 를 뗀다(스위트 규약).
    # describe 에 ID 가 있다고 그 테스트를 TC 로 세면 TC 가 FAIL 로 되돌아간다(FE-ENT-04 · 이슈 #34).
    data = json.dumps({"suites": [{"title": "f", "specs": [], "suites": [
        {"title": "FE-C-01 묶음", "specs": [
            {"title": "FE-C-01 본 테스트", "tests": [_pw_test("expected")]},
            {"title": "이슈 #34 감시", "tests": [_pw_test("expected", "failed", _fail_res(), [{"type": "fail"}])]},
        ]}]}]}).encode()
    best, unmatched = aggregate(parse_report(data)[1], IDS)
    assert best["FE-C-01"].result == "PASS"
    assert unmatched == ["FE-C-01 묶음 › 이슈 #34 감시"]


# ── 형식 검사 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("content,msg", [
    (b"garbage", "Playwright JSON"),
    (b'{"a": 1}', "suites"),
    (b"{broken", "JSON"),
    (b"<html/>", "JUnit XML"),
    (b"<testsuites><broken", "XML"),
    (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aa"><!ENTITY b "&a;&a;">]><testsuites><testcase name="&b;"/></testsuites>', "DTD"),
    (b'<?xml version="1.0"?><!DOCTYPE x SYSTEM "file:///etc/passwd"><testsuites/>', "DTD"),
])
def test_읽을_수_없는_파일은_이유를_붙여_거절(content, msg):
    with pytest.raises(ImportFormatError) as e:
        parse_report(content)
    assert msg in str(e.value)


def test_실패_메시지_CDATA_안의_DOCTYPE_문자열은_거절하지_않는다():
    _, entries = parse_report(JUNIT)
    assert len(entries) == 9


# ── 저장 ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def env(pg_engine, tmp_path):
    engine = pg_engine

    db = sessionmaker(bind=engine)()
    a = User(username="a", password_hash="x", display_name="A", role="admin")
    db.add(a)
    db.flush()
    project = Project(name="P", created_by=a.id)
    db.add(project)
    db.flush()
    db.add_all([
        TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False),
        TestCaseSheet(project_id=project.id, name="밖", sort_order=1, is_folder=False),
    ])
    tcs = {}
    for n, tc_id in enumerate(sorted(EXPECTED), start=1):
        tc = TestCase(project_id=project.id, no=n, tc_id=tc_id, sheet_name="S", created_by=a.id)
        db.add(tc)
        tcs[tc_id] = tc
    outside = TestCase(project_id=project.id, no=1, tc_id="FE-C-01", sheet_name="밖", created_by=a.id)
    db.add(outside)
    run = TestRun(project_id=project.id, name="수행", round=1, created_by=a.id, sheet_names=["S"])
    db.add(run)
    db.flush()
    for tc in tcs.values():
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=R.NS, executed_by=a.id))
    db.commit()
    yield db, project, run, tcs, a
    db.close()
    engine.dispose()


def _import(env, content, name="r.json", **kw):
    db, project, run, _, a = env
    upload = UploadFile(file=io.BytesIO(content), filename=name)
    return import_results(project.id, run.id, file=upload, db=db, current_user=a,
                          dry_run=kw.get("dry_run", False), keep_executed=kw.get("keep_executed", True),
                          label=kw.get("label"))


def _row(env, tc_id):
    db, _, run, tcs, _ = env
    db.expire_all()
    return db.query(TestResult).filter_by(test_run_id=run.id, test_case_id=tcs[tc_id].id).one()


def test_미리보기는_저장하지_않는다(env):
    res = _import(env, PW_JSON, dry_run=True)
    assert res["dry_run"] and res["counts"] == {"PASS": 2, "FAIL": 4, "NS": 2}
    assert res["fixed_candidates"] == ["FE-A-04"]
    assert res["unexpected_failures"] == ["FE-A-02", "FE-B-01"]
    assert res["known_failures"] == 1
    assert res["unmatched"] == ["묶음 A › 접두어 없는 감시 테스트"]
    assert _row(env, "FE-A-01").result == R.NS


def test_적용하면_판정과_비고가_기록되고_이슈_링크는_남는다(env):
    row = _row(env, "FE-A-03")
    row.issue_link = "SF-9"
    env[0].commit()
    res = _import(env, JUNIT, name="junit.xml", label="e2e 회차")
    assert res["format"] == "junit-xml" and res["recorded"] == 8
    r3 = _row(env, "FE-A-03")
    assert r3.result == R.FAIL
    assert r3.remarks == "e2e 회차. test.fail 로 고정한 기존 결함이 그대로 재현됨 (이슈 #9)"
    assert r3.issue_link == "SF-9", "자동 기록이 사람이 단 링크를 지우면 안 된다"
    assert r3.duration_sec == 2.0
    r1 = _row(env, "FE-A-01")
    assert r1.result == R.PASS and r1.actual_result == "통과" and r1.remarks == "e2e 회차"


def test_이미_기록된_결과를_NS_로_덮지_않는다(env):
    row = _row(env, "FE-B-02")
    row.result = R.PASS
    env[0].commit()
    res = _import(env, PW_JSON)
    assert res["kept_executed"] == ["FE-B-02"]
    assert _row(env, "FE-B-02").result == R.PASS
    # 옵션을 끄면 덮는다
    res = _import(env, PW_JSON, keep_executed=False)
    assert res["kept_executed"] == []
    assert _row(env, "FE-B-02").result == R.NS


def test_수행_범위_밖_TC_는_기록하지_않고_알려_준다(env):
    data = json.dumps({"suites": [{"title": "f", "specs": [
        {"title": "FE-C-01 범위 밖", "tests": [_pw_test("expected")]},
        {"title": "FE-A-01 범위 안", "tests": [_pw_test("expected")]},
    ]}]}).encode()
    res = _import(env, data)
    assert res["out_of_run"] == ["FE-C-01"] and res["recorded"] == 1
    db, _, run, _, _ = env
    assert db.query(TestResult).filter_by(test_run_id=run.id).count() == len(EXPECTED), "범위 밖 행을 새로 만들지 않는다"


def test_완료된_수행과_빈_파일은_거절(env):
    db, _, run, _, _ = env
    with pytest.raises(HTTPException) as e:
        _import(env, b'{"suites": []}')
    assert e.value.status_code == 400 and "테스트 결과가 없" in e.value.detail
    with pytest.raises(HTTPException) as e:
        _import(env, b"garbage")
    assert e.value.status_code == 400
    run.status = TestRunStatus.completed
    db.commit()
    with pytest.raises(HTTPException) as e:
        _import(env, PW_JSON)
    assert e.value.status_code == 400 and "완료된" in e.value.detail


# ── 이름으로 올리기 (회차 자동 생성) ─────────────────────────────────────────

from routes.testruns import import_results_by_name  # noqa: E402


def _import_by_name(env, content, *, run_name="수행", round_mode="next", version=None, environment=None,
                    sheet_names=None, dry_run=False, keep_executed=True, label=None):
    db, project, _, _, a = env
    upload = UploadFile(file=io.BytesIO(content), filename="r.json")
    return import_results_by_name(
        project.id, run_name=run_name, round_mode=round_mode, version=version, environment=environment,
        sheet_names=sheet_names, file=upload, dry_run=dry_run, keep_executed=keep_executed, label=label,
        db=db, current_user=a,
    )


def _runs(env, name="수행"):
    db, project, _, _, _ = env
    db.expire_all()
    return db.query(TestRun).filter_by(project_id=project.id, name=name).order_by(TestRun.round).all()


def test_이름으로_올리면_다음_회차를_만들어_기록하고_앞_회차는_그대로(env):
    db, _, run, _, _ = env
    run.version, run.environment = "1.5", "prod"
    db.commit()
    res = _import_by_name(env, PW_JSON)
    runs = _runs(env)
    assert [r.round for r in runs] == [1, 2]
    r2 = runs[1]
    assert res["run"] == {"id": r2.id, "name": "수행", "round": 2, "version": "1.5", "environment": "prod", "created": True}
    assert r2.sheet_names == ["S"], "범위를 이어받는다"
    assert res["counts"] == {"PASS": 2, "FAIL": 4, "NS": 2}
    rows = {x.test_case_id: x.result for x in db.query(TestResult).filter_by(test_run_id=r2.id)}
    assert R.FAIL in rows.values()
    assert all(x.result == R.NS for x in db.query(TestResult).filter_by(test_run_id=runs[0].id)), "R1 은 건드리지 않는다"


def test_버전과_환경을_주면_새_회차에_그_값(env):
    res = _import_by_name(env, PW_JSON, version="1.6", environment="dev")
    assert res["run"]["version"] == "1.6" and res["run"]["environment"] == "dev"


def test_open_은_진행_중인_회차에_기록하고_없으면_새로_만든다(env):
    db, _, run, _, _ = env
    res = _import_by_name(env, PW_JSON, round_mode="open")
    assert res["run"]["created"] is False and res["run"]["id"] == run.id
    assert [r.round for r in _runs(env)] == [1]
    run.status = TestRunStatus.completed
    db.commit()
    res = _import_by_name(env, PW_JSON, round_mode="open")
    assert res["run"]["created"] is True and res["run"]["round"] == 2


def test_미리보기는_회차를_남기지_않는다(env):
    res = _import_by_name(env, PW_JSON, dry_run=True)
    assert res["dry_run"] and res["run"]["created"] and res["run"]["id"] is None and res["run"]["round"] == 2
    assert res["counts"] == {"PASS": 2, "FAIL": 4, "NS": 2}
    assert [r.round for r in _runs(env)] == [1], "되돌려서 R2 가 없다"


def test_처음_보는_이름은_R1_범위는_시트_지정이_없으면_프로젝트_전체(env):
    data = json.dumps({"suites": [{"title": "f", "specs": [
        {"title": "FE-C-01 범위 밖 시트", "tests": [_pw_test("expected")]},
        {"title": "FE-A-01 안", "tests": [_pw_test("expected")]},
    ]}]}).encode()
    res = _import_by_name(env, data, run_name="e2e")
    assert res["run"]["round"] == 1 and res["recorded"] == 2 and res["out_of_run"] == []
    res = _import_by_name(env, data, run_name="e2e-S", sheet_names="S")
    assert res["out_of_run"] == ["FE-C-01"]
    assert _runs(env, "e2e-S")[0].sheet_names == ["S"]


def test_시트를_주면_이어받지_않고_그_범위로_다음_회차(env):
    res = _import_by_name(env, PW_JSON, sheet_names="밖")
    assert res["run"]["round"] == 2 and _runs(env)[1].sheet_names == ["밖"]


def test_깨진_파일과_없는_시트는_회차를_만들기_전에_거절(env):
    for kw in ({"content": b"garbage"}, {"content": PW_JSON, "sheet_names": "없는 시트"}):
        content = kw.pop("content")
        with pytest.raises(HTTPException) as e:
            _import_by_name(env, content, **kw)
        assert e.value.status_code == 400
    assert [r.round for r in _runs(env)] == [1]
