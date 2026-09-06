"""
v1.1.0 추가 기능 테스트
- 글로벌 대시보드 오버뷰 (/api/dashboard/overview)
- 리포트 API (JSON / PDF / Excel)
- 테스트 런 고급 기능 (clone / export / complete / reopen)
- 검색 API (/api/search)
- 멤버 관리 API
- i18n 지원 확인 (Accept-Language)
"""
import sys
import requests
import os

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL = 0


def login(username="admin", password=None):
    if password is None:
        password = os.getenv("TEST_ADMIN_PASSWORD", "test1234")
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        print(f"[FATAL] Login failed ({username}): {r.text}")
        sys.exit(1)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def check(name, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT, TOTAL
    TOTAL += 1
    if condition:
        PASS_COUNT += 1
        print(f"  [PASS] {name}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name} -- {detail}")


H = login()

# 테스트용 프로젝트 생성 + TC + TestRun
r = requests.post(f"{BASE}/api/projects", json={"name": "v110_test_project"}, headers=H)
PID = r.json()["id"]
print(f"Test project created: id={PID}")

# TC 3개 생성
tc_ids = []
for i in range(1, 4):
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
        "no": i, "tc_id": f"V110-{i:03d}",
        "category": "Auth" if i <= 2 else "Payment",
        "priority": "높음" if i == 1 else "보통",
        "test_steps": f"Step {i}", "expected_result": f"Expected {i}",
    }, headers=H)
    tc_ids.append(r.json()["id"])

# TestRun 생성 + 결과 제출
r = requests.post(f"{BASE}/api/projects/{PID}/testruns", json={
    "name": "Run-v110", "version": "v1.1.0", "round": 1, "environment": "staging"
}, headers=H)
RUN_ID = r.json()["id"]
requests.post(f"{BASE}/api/projects/{PID}/testruns/{RUN_ID}/results", json=[
    {"test_case_id": tc_ids[0], "result": "PASS", "actual_result": "OK"},
    {"test_case_id": tc_ids[1], "result": "FAIL", "actual_result": "에러 발생", "issue_link": "JIRA-001"},
    {"test_case_id": tc_ids[2], "result": "NS"},
], headers=H)


# ============================================================================
print("\n" + "=" * 70)
print("1. 글로벌 대시보드 오버뷰")
print("=" * 70)

r = requests.get(f"{BASE}/api/dashboard/overview", headers=H)
check("overview 200", r.status_code == 200, f"status={r.status_code}")
data = r.json()
check("overview summary 존재", "summary" in data)
check("overview projects 존재", "projects" in data and isinstance(data["projects"], list))
check("overview total_projects > 0", data["summary"]["total_projects"] > 0,
      f"total={data['summary'].get('total_projects')}")
check("overview total_tc > 0", data["summary"]["total_tc"] > 0)

# 인증 없이 접근
r = requests.get(f"{BASE}/api/dashboard/overview")
check("overview 인증 필수 401", r.status_code == 401)


# ============================================================================
print("\n" + "=" * 70)
print("2. 리포트 API (JSON)")
print("=" * 70)

r = requests.get(f"{BASE}/api/projects/{PID}/reports", params={"run_id": RUN_ID}, headers=H)
check("report JSON 200", r.status_code == 200, f"status={r.status_code}")
rpt = r.json()
check("report project 정보", "project" in rpt and rpt["project"]["id"] == PID)
check("report test_run 정보", "test_run" in rpt and rpt["test_run"]["id"] == RUN_ID)
check("report summary 존재", "summary" in rpt)
check("report summary total=3", rpt["summary"]["total"] == 3, f"total={rpt['summary'].get('total')}")
check("report summary pass=1", rpt["summary"]["pass"] == 1, f"pass={rpt['summary'].get('pass')}")
check("report summary fail=1", rpt["summary"]["fail"] == 1)
check("report top_failures 존재", "top_failures" in rpt and len(rpt["top_failures"]) >= 1)
check("report category_summary 존재", "category_summary" in rpt)
check("report jira_issues 포함", "JIRA-001" in rpt.get("jira_issues", []),
      str(rpt.get("jira_issues")))

# run_id 없이 조회
r = requests.get(f"{BASE}/api/projects/{PID}/reports", headers=H)
check("report run_id 누락 시 400/422", r.status_code in (400, 422), f"status={r.status_code}")

# 존재하지 않는 run_id
r = requests.get(f"{BASE}/api/projects/{PID}/reports", params={"run_id": 99999}, headers=H)
check("report 없는 run_id 시 404", r.status_code == 404)


# ============================================================================
print("\n" + "=" * 70)
print("3. 리포트 API (PDF / Excel)")
print("=" * 70)

r = requests.get(f"{BASE}/api/projects/{PID}/reports/pdf", params={"run_id": RUN_ID}, headers=H)
check("report PDF 200", r.status_code == 200, f"status={r.status_code}")
check("report PDF content-type", "pdf" in r.headers.get("content-type", ""), r.headers.get("content-type"))
check("report PDF size > 0", len(r.content) > 100, f"size={len(r.content)}")

r = requests.get(f"{BASE}/api/projects/{PID}/reports/excel", params={"run_id": RUN_ID}, headers=H)
check("report Excel 200", r.status_code == 200, f"status={r.status_code}")
check("report Excel content-type", "spreadsheet" in r.headers.get("content-type", ""),
      r.headers.get("content-type"))
check("report Excel size > 0", len(r.content) > 100, f"size={len(r.content)}")


# ============================================================================
print("\n" + "=" * 70)
print("4. 테스트 런 완료/재개")
print("=" * 70)

# 완료
r = requests.put(f"{BASE}/api/projects/{PID}/testruns/{RUN_ID}/complete", headers=H)
check("run complete 200", r.status_code == 200, f"status={r.status_code}")
check("run status=completed", r.json()["status"] == "completed")
check("run completed_at 존재", r.json()["completed_at"] is not None)

# 재개
r = requests.put(f"{BASE}/api/projects/{PID}/testruns/{RUN_ID}/reopen", headers=H)
check("run reopen 200", r.status_code == 200, f"status={r.status_code}")
check("run status=in_progress", r.json()["status"] == "in_progress")
check("run completed_at=null", r.json()["completed_at"] is None)

# 존재하지 않는 런
r = requests.put(f"{BASE}/api/projects/{PID}/testruns/99999/complete", headers=H)
check("없는 런 complete 404", r.status_code == 404)

r = requests.put(f"{BASE}/api/projects/{PID}/testruns/99999/reopen", headers=H)
check("없는 런 reopen 404", r.status_code == 404)


# ============================================================================
print("\n" + "=" * 70)
print("5. 테스트 런 복제")
print("=" * 70)

r = requests.post(f"{BASE}/api/projects/{PID}/testruns/{RUN_ID}/clone", headers=H)
check("run clone 201", r.status_code == 201, f"status={r.status_code}")
cloned_run = r.json()
check("clone name에 (복제)/(Clone) 포함",
      "(복제)" in cloned_run.get("name", "") or "(Clone)" in cloned_run.get("name", ""),
      f"name={cloned_run.get('name')}")
check("clone status=in_progress", cloned_run["status"] == "in_progress")
check("clone version 동일", cloned_run.get("version") == "v1.1.0")

CLONED_RUN_ID = cloned_run["id"]

# 복제된 런 상세 조회 → results 확인
r = requests.get(f"{BASE}/api/projects/{PID}/testruns/{CLONED_RUN_ID}", headers=H)
cloned_detail = r.json()
clone_results = cloned_detail.get("results", [])
check("clone 결과 3건", len(clone_results) == 3, f"count={len(clone_results)}")
all_ns = all(res["result"] == "NS" for res in clone_results)
check("clone 결과 모두 NS 초기화", all_ns)

# 존재하지 않는 런 복제
r = requests.post(f"{BASE}/api/projects/{PID}/testruns/99999/clone", headers=H)
check("없는 런 clone 404", r.status_code == 404)


# ============================================================================
print("\n" + "=" * 70)
print("6. 테스트 런 Export (Excel)")
print("=" * 70)

r = requests.get(f"{BASE}/api/projects/{PID}/testruns/{RUN_ID}/export", headers=H)
check("run export 200", r.status_code == 200, f"status={r.status_code}")
check("run export content-type", "spreadsheet" in r.headers.get("content-type", ""),
      r.headers.get("content-type"))
check("run export size > 0", len(r.content) > 100, f"size={len(r.content)}")

# 존재하지 않는 런 export
r = requests.get(f"{BASE}/api/projects/{PID}/testruns/99999/export", headers=H)
check("없는 런 export 404", r.status_code == 404)


# ============================================================================
print("\n" + "=" * 70)
print("7. 검색 API")
print("=" * 70)

r = requests.get(f"{BASE}/api/search", params={"q": "V110-001"}, headers=H)
check("search 200", r.status_code == 200, f"status={r.status_code}")
found = [tc["tc_id"] for tc in r.json()]
check("search 결과 V110-001 포함", "V110-001" in found, str(found))

# 대소문자 무관
r = requests.get(f"{BASE}/api/search", params={"q": "v110-001"}, headers=H)
check("search 대소문자 무관", r.status_code == 200 and len(r.json()) > 0)

# 빈 결과
r = requests.get(f"{BASE}/api/search", params={"q": "__no_match_xyz_99999__"}, headers=H)
check("search 빈 결과 200", r.status_code == 200 and r.json() == [])

# 빈 쿼리
r = requests.get(f"{BASE}/api/search", params={"q": ""}, headers=H)
check("search 빈 쿼리 422", r.status_code == 422)


# ============================================================================
print("\n" + "=" * 70)
print("8. 멤버 관리 API")
print("=" * 70)

# 멤버 목록
r = requests.get(f"{BASE}/api/projects/{PID}/members", headers=H)
check("members list 200", r.status_code == 200)
members = r.json()
check("members에 admin 포함", any(m["username"] == "admin" for m in members),
      str([m["username"] for m in members]))

# available-users (멤버 추가 가능 사용자)
r = requests.get(f"{BASE}/api/projects/{PID}/members/available-users", headers=H)
check("available-users 200", r.status_code == 200)


# ============================================================================
print("\n" + "=" * 70)
print("9. i18n 지원 확인 (Accept-Language)")
print("=" * 70)

# 영어 요청
h_en = {**H, "Accept-Language": "en"}
h_ko = {**H, "Accept-Language": "ko"}

# 존재하지 않는 프로젝트 → 에러 메시지 확인
r_en = requests.get(f"{BASE}/api/projects/99999", headers=h_en)
r_ko = requests.get(f"{BASE}/api/projects/99999", headers=h_ko)
check("i18n EN 요청 404", r_en.status_code == 404)
check("i18n KO 요청 404", r_ko.status_code == 404)

# 존재하지 않는 TC 삭제 → 에러 메시지
r_en = requests.delete(f"{BASE}/api/projects/{PID}/testcases/99999", headers=h_en)
r_ko = requests.delete(f"{BASE}/api/projects/{PID}/testcases/99999", headers=h_ko)
check("i18n TC 삭제 404 EN", r_en.status_code == 404)
check("i18n TC 삭제 404 KO", r_ko.status_code == 404)


# ============================================================================
print("\n" + "=" * 70)
print("10. 테스트 런 삭제")
print("=" * 70)

# 복제된 런 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/testruns/{CLONED_RUN_ID}", headers=H)
check("run delete 204", r.status_code == 204, f"status={r.status_code}")

# 삭제 후 조회
r = requests.get(f"{BASE}/api/projects/{PID}/testruns/{CLONED_RUN_ID}", headers=H)
check("삭제 후 조회 404", r.status_code == 404)

# 존재하지 않는 런 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/testruns/99999", headers=H)
check("없는 런 delete 404", r.status_code == 404)


# ============================================================================
# 정리: 테스트 프로젝트 삭제
print("\n" + "-" * 70)
r = requests.delete(f"{BASE}/api/projects/{PID}", headers=H)
print(f"Cleanup: delete project {PID} -> {r.status_code}")

# 결과 출력
print("\n" + "=" * 70)
print(f"TOTAL: {TOTAL}  |  PASS: {PASS_COUNT}  |  FAIL: {FAIL_COUNT}")
print("=" * 70)

if FAIL_COUNT > 0:
    sys.exit(1)
