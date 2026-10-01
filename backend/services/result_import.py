"""자동화 결과 파일(Playwright JSON · JUnit XML)을 회차 결과로 옮기는 규칙.

`starfort project/tc/record_run_from_e2e.py` 가 하던 판정을 서버로 옮긴 것이다
(docs/plan_playwright_integration.md 4-7). 기록 스크립트와 같은 파일을 넣으면
PASS · FAIL · NS 건수가 같아야 한다.

판정 (Playwright JSON 기준. list 리포터의 ✘ 로 보지 않는다)
    expected   + expectedStatus=passed      -> PASS
    expected   + expectedStatus=failed      -> FAIL  test.fail 로 고정한 결함이 그대로 재현
    unexpected + expectedStatus=failed      -> FAIL  test.fail 인데 통과. 결함 해소 후보
    unexpected                              -> FAIL  예상 밖 실패
    flaky                                   -> PASS  재시도 뒤 통과
    skipped + skip 주석                     -> NS    test.skip 사유
    그 밖의 skipped                          -> NS    앞 테스트 실패로 연쇄가 끊김

JUnit XML 은 `<failure>` · `<error>` · `<skipped>` 와 속성(property)으로 같은 판정을 낸다.
Playwright 의 junit 리포터는 `embedAnnotationsAsProperties: true` 일 때만 test.fail 을
`<property name="fail">` 로 남긴다. 그 옵션이 없으면 test.fail 재현은 통과로 보인다.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat
from dataclasses import dataclass, field

# 판정 종류. 결과 값과 비고 문구를 함께 정한다.
KIND_PASS = "pass"
KIND_FLAKY = "flaky"
KIND_FAIL = "fail"
KIND_KNOWN_FAIL = "known_fail"      # test.fail 재현
KIND_FIXED = "fixed_candidate"      # test.fail 인데 통과
KIND_SKIP = "skip"                  # test.skip 사유 있음
KIND_NOT_RUN = "not_run"            # 연쇄가 끊겨 미실행

KIND_RESULT = {
    KIND_PASS: "PASS",
    KIND_FLAKY: "PASS",
    KIND_FAIL: "FAIL",
    KIND_KNOWN_FAIL: "FAIL",
    KIND_FIXED: "FAIL",
    KIND_SKIP: "NS",
    KIND_NOT_RUN: "NS",
}

# 같은 TC 를 여러 테스트가 덮으면 나쁜 쪽을 남긴다. 기록 스크립트와 같은 순서다.
# NS 가 PASS 보다 나쁘다: 한쪽이 돌지 않았으면 그 TC 는 다 확인된 것이 아니다.
RESULT_RANK = {"FAIL": 3, "NS": 2, "PASS": 1}

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# 제목 맨 앞의 ID 후보. 괄호로 감싼 형태([FE-AUTH-05])도 받는다.
LEAD_TOKEN_RE = re.compile(r"^[\[(]?\s*([A-Za-z0-9][A-Za-z0-9_-]*)")
MAX_ERR = 300


class ImportFormatError(ValueError):
    """읽을 수 없는 파일. 사용자에게 그대로 보여 줄 문구를 담는다."""


@dataclass
class TestEntry:
    titles: list[str]          # describe 들 + 테스트 제목. 마지막이 테스트 제목
    kind: str
    error: str = ""
    reason: str = ""           # skip · fail 주석 설명
    retries: int = 0
    duration_sec: float | None = None

    @property
    def full_title(self) -> str:
        return " › ".join(t for t in self.titles if t)


@dataclass
class TcOutcome:
    tc_id: str
    result: str
    kind: str
    note: str
    actual: str
    duration_sec: float | None
    titles: list[str] = field(default_factory=list)


def _first_line(msg: str | None) -> str:
    if not msg:
        return ""
    for line in ANSI_RE.sub("", msg).splitlines():
        line = line.strip()
        if line:
            return line[:MAX_ERR]
    return ""


# ── Playwright JSON ─────────────────────────────────────────────────────────

def _pw_annotation(test: dict, kind: str) -> dict | None:
    return next((a for a in test.get("annotations") or [] if a.get("type") == kind), None)


def _pw_kind(test: dict) -> tuple[str, str, str]:
    """(판정 종류, 오류 첫 줄, 사유)"""
    status = test.get("status")
    expected = test.get("expectedStatus")
    results = test.get("results") or []
    err = ""
    # 마지막 시도의 오류를 쓴다. 재시도에서 통과했다면 오류가 없다.
    for res in reversed(results):
        err = _first_line((res.get("error") or {}).get("message"))
        if err:
            break
    skip = _pw_annotation(test, "skip")
    fail = _pw_annotation(test, "fail")
    if skip and status == "skipped":
        return KIND_SKIP, "", skip.get("description") or ""
    if status == "skipped" or not results:
        return KIND_NOT_RUN, "", ""
    if status == "expected" and expected == "failed":
        return KIND_KNOWN_FAIL, err, (fail or {}).get("description") or ""
    if status == "expected":
        return KIND_PASS, "", ""
    if status == "flaky":
        return KIND_FLAKY, "", ""
    if expected == "failed":
        return KIND_FIXED, "", (fail or {}).get("description") or ""
    return KIND_FAIL, err, ""


def _pw_walk(suite: dict, parents: list[str], out: list[TestEntry]) -> None:
    # 최상위 suite 는 파일이다. 파일 이름은 제목 경로에 넣지 않는다.
    for spec in suite.get("specs") or []:
        for test in spec.get("tests") or []:
            kind, err, reason = _pw_kind(test)
            results = test.get("results") or []
            last = results[-1] if results else {}
            dur = last.get("duration")
            out.append(TestEntry(
                titles=parents + [str(spec.get("title") or "").strip()],
                kind=kind,
                error=err,
                reason=reason,
                retries=max(len(results) - 1, 0),
                duration_sec=round(dur / 1000, 3) if isinstance(dur, (int, float)) else None,
            ))
    for child in suite.get("suites") or []:
        _pw_walk(child, parents + [str(child.get("title") or "").strip()], out)


def parse_playwright_json(content: bytes) -> list[TestEntry]:
    try:
        report = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportFormatError("JSON 을 읽을 수 없습니다.") from exc
    if not isinstance(report, dict) or not isinstance(report.get("suites"), list):
        raise ImportFormatError("Playwright JSON 리포트가 아닙니다. suites 항목이 없습니다.")
    out: list[TestEntry] = []
    for suite in report["suites"]:
        _pw_walk(suite, [], out)
    return out


# ── JUnit XML ───────────────────────────────────────────────────────────────

def _junit_kind(tc: ET.Element) -> tuple[str, str, str]:
    props = {
        (p.get("name") or ""): (p.get("value") or "")
        for p in tc.iter("property")
    }
    failure = tc.find("failure")
    if failure is None:
        failure = tc.find("error")
    skipped = tc.find("skipped")

    if skipped is not None:
        if "skip" in props:
            return KIND_SKIP, "", props["skip"]
        msg = (skipped.get("message") or "").strip()
        # 다른 도구는 건너뛴 사유를 message 에 담는다. 사유가 있으면 의도된 건너뜀이다.
        return (KIND_SKIP, "", msg) if msg else (KIND_NOT_RUN, "", "")
    if "fail" in props:
        if failure is None:
            return KIND_KNOWN_FAIL, "", props["fail"]
        return KIND_FIXED, "", props["fail"]
    if failure is not None:
        err = _first_line(failure.get("message")) or _first_line(failure.text)
        return KIND_FAIL, err, ""
    return KIND_PASS, "", ""


def _forbid_dtd(*_args) -> None:
    raise ImportFormatError("DTD 가 포함된 XML 은 받지 않습니다.")


def _safe_fromstring(content: bytes) -> ET.Element:
    """DOCTYPE · 엔티티 선언을 만나는 즉시 멈추는 파서로 읽는다.

    ★엔티티 확장(billion laughs)과 외부 엔티티는 DTD 가 있어야 성립한다. 문자열 검사로
      막으면 실패 메시지 CDATA 에 든 HTML 조각까지 걸리므로 expat 핸들러에서 막는다
      (defusedxml 과 같은 방식). 테스트 리포터가 DTD 를 쓰는 경우는 없다.
    """
    # C 가속 XMLParser 는 안쪽 expat 객체를 내주지 않아 핸들러를 걸 수 없다. expat 을 직접 쓴다.
    builder = ET.TreeBuilder()
    p = expat.ParserCreate()
    p.buffer_text = True
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    p.StartDoctypeDeclHandler = _forbid_dtd
    p.EntityDeclHandler = _forbid_dtd
    p.UnparsedEntityDeclHandler = _forbid_dtd
    p.ExternalEntityRefHandler = _forbid_dtd
    p.StartElementHandler = builder.start
    p.EndElementHandler = builder.end
    p.CharacterDataHandler = builder.data
    p.Parse(content, True)
    return builder.close()


def parse_junit_xml(content: bytes) -> list[TestEntry]:
    try:
        root = _safe_fromstring(content)
    except expat.ExpatError as exc:
        raise ImportFormatError("XML 을 읽을 수 없습니다.") from exc
    if root.tag not in ("testsuites", "testsuite"):
        raise ImportFormatError("JUnit XML 이 아닙니다. testsuites 또는 testsuite 로 시작해야 합니다.")

    out: list[TestEntry] = []
    for tc in root.iter("testcase"):
        name = (tc.get("name") or "").strip()
        kind, err, reason = _junit_kind(tc)
        try:
            dur = float(tc.get("time")) if tc.get("time") else None
        except ValueError:
            dur = None
        # Playwright 는 describe 와 제목을 " › " 로 이어 name 에 담는다.
        titles = [t.strip() for t in name.split(" › ")] if " › " in name else [name]
        out.append(TestEntry(titles=titles, kind=kind, error=err, reason=reason,
                             duration_sec=round(dur, 3) if dur is not None else None))
    return out


def parse_report(content: bytes, filename: str | None = None) -> tuple[str, list[TestEntry]]:
    """파일 형식을 내용으로 가려 읽는다. (형식 이름, 테스트 목록)"""
    stripped = content.lstrip(b"\xef\xbb\xbf \t\r\n")
    if stripped.startswith(b"{"):
        return "playwright-json", parse_playwright_json(content)
    if stripped.startswith(b"<"):
        return "junit-xml", parse_junit_xml(content)
    raise ImportFormatError("Playwright JSON 리포트나 JUnit XML 파일을 올려 주세요.")


# ── TC 매칭과 합산 ──────────────────────────────────────────────────────────

def match_tc_id(title: str, known_ids: set[str]) -> str | None:
    """제목 맨 앞 토큰이 아는 TC ID 와 정확히 같으면 그 ID.

    `FE-ORG-01b` 처럼 접미어가 붙은 TC 는 별개의 TC 다. 토큰 전체가 같아야 하므로
    `FE-ORG-01b` 테스트가 `FE-ORG-01` 로 들어가지 않는다.
    """
    m = LEAD_TOKEN_RE.match(title.strip())
    if not m:
        return None
    token = m.group(1)
    return token if token in known_ids else None


def resolve_tc_id(entry: TestEntry, known_ids: set[str]) -> str | None:
    """테스트 제목에서만 찾는다.

    ★기획안(4-2)의 두 규칙은 일부러 뺐다. 실제 리포트로 기록 스크립트와 대조하니 둘 다
      결과를 뒤집었다(2026-10-01).
      - describe 제목에서 ID 를 찾으면, TC 를 PASS 로 확정한 뒤 ID 를 떼어 둔 test.fail
        감시 테스트가 다시 그 TC 로 들어가 FAIL 로 만든다(FE-ENT-04 의 「이슈 #34」).
      - 접미어를 떼고 보면, 시트에서 지운 접미어 TC 의 테스트가 기본 TC 로 흘러든다
        (09-21 에 지운 FE-ORG-01b 가 FE-ORG-01 을 FAIL 로 만듦).
      TC 로 셀 테스트는 제목 맨 앞에 ID 를 정확히 쓴다는 스위트 규약을 그대로 따른다.
    """
    return match_tc_id(entry.titles[-1], known_ids) if entry.titles else None


def _note(kind: str, reason: str, retries: int) -> str:
    if kind == KIND_KNOWN_FAIL:
        return "test.fail 로 고정한 기존 결함이 그대로 재현됨" + (f" ({reason})" if reason else "")
    if kind == KIND_FIXED:
        return "test.fail 표식인데 통과함. 결함 해소 후보라 수동 재확인 필요" + (f" ({reason})" if reason else "")
    if kind == KIND_FAIL:
        return "예상 밖 실패. 제품 결함인지 하네스 문제인지 확인 필요"
    if kind == KIND_FLAKY:
        return f"재시도 {retries}회 후 통과 (flaky)"
    if kind == KIND_SKIP:
        return "절차를 수행할 수 없어 건너뜀: " + (reason or "사유 없음")
    if kind == KIND_NOT_RUN:
        return "연쇄가 끊겨 미실행"
    return ""


def aggregate(entries: list[TestEntry], known_ids: set[str]) -> tuple[dict[str, TcOutcome], list[str]]:
    """TC 별 최종 결과와, TC ID 를 찾지 못한 테스트 제목 목록."""
    best: dict[str, TcOutcome] = {}
    unmatched: list[str] = []
    for e in entries:
        tc_id = resolve_tc_id(e, known_ids)
        if tc_id is None:
            unmatched.append(e.full_title)
            continue
        result = KIND_RESULT[e.kind]
        outcome = TcOutcome(
            tc_id=tc_id,
            result=result,
            kind=e.kind,
            note=_note(e.kind, e.reason, e.retries),
            actual=e.error or ("통과" if result == "PASS" else ""),
            duration_sec=e.duration_sec,
            titles=[e.full_title],
        )
        cur = best.get(tc_id)
        if cur is None:
            best[tc_id] = outcome
            continue
        cur.titles.append(e.full_title)
        if e.duration_sec is not None:
            cur.duration_sec = round((cur.duration_sec or 0) + e.duration_sec, 3)
        if RESULT_RANK[result] > RESULT_RANK[cur.result]:
            outcome.titles = cur.titles
            outcome.duration_sec = cur.duration_sec
            best[tc_id] = outcome
    return best, unmatched
