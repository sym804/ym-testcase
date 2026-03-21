"""
v0.6.0 전체 기능 테스트
- 시트 트리 구조
- 커스텀 필드
- 테스트 플랜/마일스톤
- Jira CSV Import
- 고급 필터 + 저장된 뷰
- 기존 기능 회귀 테스트
"""
import io
import csv
import sys
import json
import requests
import tempfile
import os

BASE = os.getenv("TEST_BASE_URL", "http://localhost:8008")
PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL = 0


def login():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": os.getenv("TEST_ADMIN_PASSWORD", "test1234")})
    if r.status_code != 200:
        print(f"[FATAL] Login failed: {r.text}")
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
# 테스트용 프로젝트 생성
r = requests.post(f"{BASE}/api/projects", json={"name": "v060_test_project"}, headers=H)
PID = r.json()["id"]
print(f"Test project created: id={PID}")

# ============================================================================
print("\n" + "=" * 70)
print("1. 시트 트리 구조")
print("=" * 70)

# 1-1. 루트 시트 생성
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "기능"}, headers=H)
check("루트 시트 생성", r.status_code == 200, f"status={r.status_code}")
root1 = r.json()
check("루트 시트 id 반환", "id" in root1 and root1["id"] > 0, str(root1))
check("루트 시트 parent_id=null", root1.get("parent_id") is None)

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "UI"}, headers=H)
check("루트 시트2 생성", r.status_code == 200)
root2 = r.json()

# 1-2. 하위 시트 생성
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "로그인", "parent_id": root1["id"]}, headers=H)
check("하위 시트 생성", r.status_code == 200)
child1 = r.json()
check("하위 시트 parent_id 정확", child1["parent_id"] == root1["id"])

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "결제", "parent_id": root1["id"]}, headers=H)
check("하위 시트2 생성", r.status_code == 200)
child2 = r.json()

# 1-3. 손자 시트 생성 (3 depth)
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "OAuth", "parent_id": child1["id"]}, headers=H)
check("손자 시트 생성 (3 depth)", r.status_code == 200)
grandchild = r.json()
check("손자 parent_id 정확", grandchild["parent_id"] == child1["id"])

# 1-4. 트리 구조 조회
r = requests.get(f"{BASE}/api/projects/{PID}/testcases/sheets", headers=H)
check("트리 조회 성공", r.status_code == 200)
tree = r.json()
check("루트 노드 2개", len(tree) == 2, f"got {len(tree)}")

feat_node = [n for n in tree if n["name"] == "기능"]
check("기능 노드 존재", len(feat_node) == 1)
feat_node = feat_node[0]
check("기능 하위 2개", len(feat_node["children"]) == 2, f"got {len(feat_node['children'])}")

login_node = [c for c in feat_node["children"] if c["name"] == "로그인"]
check("로그인 노드 존재", len(login_node) == 1)
check("로그인 하위 OAuth 1개", len(login_node[0]["children"]) == 1)
check("OAuth 이름 정확", login_node[0]["children"][0]["name"] == "OAuth")

# 1-5. 중복 시트 이름 방지
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "기능"}, headers=H)
check("중복 시트 이름 거부", r.status_code == 400, f"status={r.status_code}")

# 1-6. 빈 시트 이름 방지
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "  "}, headers=H)
check("빈 시트 이름 거부", r.status_code == 400)

# 1-7. 존재하지 않는 부모 시트
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "orphan", "parent_id": 99999}, headers=H)
check("없는 부모 시트 거부", r.status_code == 400)

# 1-8. 시트 이름 변경
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{root2['id']}/rename", json={"new_name": "화면"}, headers=H)
check("시트 이름 변경 성공", r.status_code == 200)
check("변경 후 이름 정확", r.json()["name"] == "화면")

# TC 추가 후 이름 변경 시 sheet_name 동기화 확인
tc_r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={"no": 1, "tc_id": "TC-001", "sheet_name": "화면"}, headers=H)
check("TC 생성 (화면 시트)", tc_r.status_code == 201)
tc_id_for_rename = tc_r.json()["id"]

r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{root2['id']}/rename", json={"new_name": "UI/UX"}, headers=H)
check("시트 이름 재변경", r.status_code == 200)

tc_after = requests.get(f"{BASE}/api/projects/{PID}/testcases", params={"sheet_name": "UI/UX"}, headers=H)
check("TC sheet_name 동기화됨", len(tc_after.json()) == 1 and tc_after.json()[0]["id"] == tc_id_for_rename,
      f"got {len(tc_after.json())} TCs")

# 1-9. 시트 이동
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{child2['id']}/move",
                 json={"parent_id": root2["id"]}, headers=H)
check("시트 이동 성공", r.status_code == 200)
check("이동 후 parent_id 변경", r.json()["parent_id"] == root2["id"])

# 1-10. 순환 참조 방지
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{root1['id']}/move",
                 json={"parent_id": child1["id"]}, headers=H)
check("순환 참조 방지 (부모→자식)", r.status_code == 400, f"status={r.status_code}")

r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{root1['id']}/move",
                 json={"parent_id": grandchild["id"]}, headers=H)
check("순환 참조 방지 (부모→손자)", r.status_code == 400)

r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{child1['id']}/move",
                 json={"parent_id": child1["id"]}, headers=H)
check("자기 자신 부모 방지", r.status_code == 400)

# 1-11. flat=true 호환
r = requests.get(f"{BASE}/api/projects/{PID}/testcases/sheets", params={"flat": "true"}, headers=H)
check("flat=true 반환", r.status_code == 200)
flat = r.json()
check("flat에 name/tc_count 포함", all("name" in s and "tc_count" in s for s in flat))

# 1-12. CASCADE 삭제 (기능 삭제 → 로그인, OAuth 같이 삭제)
r = requests.delete(f"{BASE}/api/projects/{PID}/testcases/sheets/기능", headers=H)
check("루트 시트 삭제 성공", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/testcases/sheets", headers=H)
tree_after = r.json()
all_names = []
def collect(nodes):
    for n in nodes:
        all_names.append(n["name"])
        collect(n["children"])
collect(tree_after)
check("기능 삭제됨", "기능" not in all_names)
check("로그인 CASCADE 삭제됨", "로그인" not in all_names)
check("OAuth CASCADE 삭제됨", "OAuth" not in all_names)
check("UI/UX 시트 유지", "UI/UX" in all_names)

# ============================================================================
print("\n" + "=" * 70)
print("2. 커스텀 필드")
print("=" * 70)

# 2-1. 각 타입별 생성
types_to_test = [
    {"field_name": "환경", "field_type": "select", "options": ["Dev", "Staging", "Prod"]},
    {"field_name": "예상 시간(분)", "field_type": "number"},
    {"field_name": "자동화 여부", "field_type": "checkbox"},
    {"field_name": "마감일", "field_type": "date"},
    {"field_name": "태그", "field_type": "multiselect", "options": ["Smoke", "Regression", "E2E"]},
    {"field_name": "메모", "field_type": "text"},
]
cf_ids = []
for t in types_to_test:
    r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json=t, headers=H)
    check(f"커스텀 필드 생성 ({t['field_type']})", r.status_code == 201, f"status={r.status_code}, {r.text}")
    if r.status_code == 201:
        cf_ids.append(r.json()["id"])

# 2-2. 리스트 + sort_order 확인
r = requests.get(f"{BASE}/api/projects/{PID}/custom-fields", headers=H)
check("커스텀 필드 리스트", r.status_code == 200)
cfs = r.json()
check("6개 필드 생성됨", len(cfs) == 6, f"got {len(cfs)}")
check("sort_order 순차 (0~5)", [c["sort_order"] for c in cfs] == list(range(6)))

# 2-3. 중복 이름 거부
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "환경", "field_type": "text"}, headers=H)
check("중복 필드 이름 거부", r.status_code == 400)

# 2-4. 빈 이름 거부
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "", "field_type": "text"}, headers=H)
check("빈 필드 이름 거부", r.status_code == 400)

# 2-5. 잘못된 타입 거부
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "invalid", "field_type": "color"}, headers=H)
check("잘못된 필드 타입 거부", r.status_code == 400)

# 2-6. 필드 수정
r = requests.put(f"{BASE}/api/projects/{PID}/custom-fields/{cf_ids[0]}",
                 json={"field_name": "테스트 환경", "options": ["Dev", "QA", "Staging", "Prod"]}, headers=H)
check("필드 수정 성공", r.status_code == 200)
check("수정 후 이름 반영", r.json()["field_name"] == "테스트 환경")
check("수정 후 옵션 반영", len(r.json()["options"]) == 4)

# 2-7. TC에 custom_fields 저장
tc_r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
    "no": 10, "tc_id": "TC-CF-001",
    "custom_fields": {"테스트 환경": "Dev", "예상 시간(분)": 30, "자동화 여부": True}
}, headers=H)
check("TC + custom_fields 생성", tc_r.status_code == 201)
tc_cf = tc_r.json()
check("custom_fields 저장됨", tc_cf.get("custom_fields") is not None)
check("custom_fields 값 정확", tc_cf["custom_fields"].get("테스트 환경") == "Dev")
check("custom_fields 숫자값", tc_cf["custom_fields"].get("예상 시간(분)") == 30)

# 2-8. TC custom_fields 수정
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/{tc_cf['id']}",
                 json={"custom_fields": {"테스트 환경": "Prod", "예상 시간(분)": 60}}, headers=H)
check("TC custom_fields 수정", r.status_code == 200)
check("수정 후 값 반영", r.json()["custom_fields"]["테스트 환경"] == "Prod")

# 2-9. TC 조회 시 custom_fields 포함
r = requests.get(f"{BASE}/api/projects/{PID}/testcases", headers=H)
tcs = r.json()
cf_tc = [t for t in tcs if t["tc_id"] == "TC-CF-001"]
check("TC 리스트에 custom_fields 포함", len(cf_tc) == 1 and cf_tc[0].get("custom_fields") is not None)

# 2-10. 필드 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/custom-fields/{cf_ids[-1]}", headers=H)
check("필드 삭제 성공", r.status_code == 200)
r = requests.get(f"{BASE}/api/projects/{PID}/custom-fields", headers=H)
check("삭제 후 5개 남음", len(r.json()) == 5)

# ============================================================================
print("\n" + "=" * 70)
print("3. 테스트 플랜 / 마일스톤")
print("=" * 70)

# 3-1. 플랜 생성
r = requests.post(f"{BASE}/api/projects/{PID}/testplans", json={
    "name": "v2.0 Release", "milestone": "Sprint 5",
    "description": "릴리즈 전 전체 테스트", "start_date": "2026-03-20T00:00:00", "end_date": "2026-03-25T00:00:00"
}, headers=H)
check("테스트 플랜 생성", r.status_code == 201)
plan = r.json()
check("플랜 이름 정확", plan["name"] == "v2.0 Release")
check("마일스톤 정확", plan["milestone"] == "Sprint 5")
check("run_count=0", plan["run_count"] == 0)
check("progress.total=0", plan["progress"]["total"] == 0)
plan_id = plan["id"]

# 3-2. 빈 이름 거부
r = requests.post(f"{BASE}/api/projects/{PID}/testplans", json={"name": " "}, headers=H)
check("빈 플랜 이름 거부", r.status_code == 400)

# 3-3. 플랜 조회
r = requests.get(f"{BASE}/api/projects/{PID}/testplans/{plan_id}", headers=H)
check("플랜 단건 조회", r.status_code == 200)
check("조회 결과 이름 정확", r.json()["name"] == "v2.0 Release")

# 3-4. 플랜 수정
r = requests.put(f"{BASE}/api/projects/{PID}/testplans/{plan_id}",
                 json={"milestone": "Sprint 6", "description": "수정된 설명"}, headers=H)
check("플랜 수정", r.status_code == 200)
check("수정 후 마일스톤", r.json()["milestone"] == "Sprint 6")

# 3-5. TestRun을 플랜에 연결
# 먼저 TC 몇 개 준비
for i in range(1, 4):
    requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
        "no": 100 + i, "tc_id": f"TC-PLAN-{i:03d}", "sheet_name": "기본"
    }, headers=H)

run_r = requests.post(f"{BASE}/api/projects/{PID}/testruns", json={
    "name": "Plan Run 1", "version": "v2.0", "test_plan_id": plan_id
}, headers=H)
check("TestRun + test_plan_id 생성", run_r.status_code in (200, 201), f"status={run_r.status_code}, {run_r.text}")
if run_r.status_code in (200, 201):
    run = run_r.json()
    run_id = run["id"]
    check("Run의 test_plan_id 정확", run.get("test_plan_id") == plan_id,
          f"got {run.get('test_plan_id')}")

    # 3-6. 결과 제출 후 progress 확인
    run_detail = requests.get(f"{BASE}/api/projects/{PID}/testruns/{run_id}", headers=H).json()
    results_to_submit = []
    for i, res in enumerate(run_detail.get("results", [])):
        val = ["PASS", "FAIL", "PASS"][i % 3]
        results_to_submit.append({"test_case_id": res["test_case_id"], "result": val})

    if results_to_submit:
        requests.post(f"{BASE}/api/projects/{PID}/testruns/{run_id}/results",
                      json=results_to_submit, headers=H)

    # progress 확인
    r = requests.get(f"{BASE}/api/projects/{PID}/testplans/{plan_id}", headers=H)
    prog = r.json()["progress"]
    check("progress 반영됨 (total > 0)", prog["total"] > 0, f"total={prog['total']}")
    check("pass_rate 계산됨", prog["pass_rate"] > 0, f"pass_rate={prog['pass_rate']}")
    check("run_count=1", r.json()["run_count"] == 1)

    # 3-7. 플랜의 Run 목록
    r = requests.get(f"{BASE}/api/projects/{PID}/testplans/{plan_id}/runs", headers=H)
    check("플랜 Run 목록 조회", r.status_code == 200)
    check("Run 1개 연결됨", len(r.json()) == 1)

# 3-8. 플랜 리스트
r = requests.get(f"{BASE}/api/projects/{PID}/testplans", headers=H)
check("플랜 리스트 조회", r.status_code == 200 and len(r.json()) >= 1)

# 3-9. 없는 플랜 조회
r = requests.get(f"{BASE}/api/projects/{PID}/testplans/99999", headers=H)
check("없는 플랜 404", r.status_code == 404)

# 3-10. 플랜 삭제 → TestRun.test_plan_id null 처리
r = requests.delete(f"{BASE}/api/projects/{PID}/testplans/{plan_id}", headers=H)
check("플랜 삭제", r.status_code == 200)

if run_r.status_code in (200, 201):
    run_after = requests.get(f"{BASE}/api/projects/{PID}/testruns/{run_id}", headers=H)
    check("삭제 후 Run.test_plan_id=null", run_after.json().get("test_plan_id") is None,
          f"got {run_after.json().get('test_plan_id')}")

# ============================================================================
print("\n" + "=" * 70)
print("4. Jira CSV Import")
print("=" * 70)

# 4-1. 일반 CSV import
csv_data = "No,TC ID,Category,Depth1,Depth2,Priority,Test Steps,Expected Result\n"
csv_data += "1,CSV-001,Auth,Login,Email Login,높음,Step 1,Result 1\n"
csv_data += "2,CSV-002,Auth,Login,Social Login,보통,Step 2,Result 2\n"
csv_data += "3,CSV-003,Payment,Cart,Add to Cart,낮음,Step 3,Result 3\n"

with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
    f.write(csv_data)
    csv_path = f.name

with open(csv_path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import/preview",
                      files={"file": ("test.csv", f, "text/csv")}, headers=H)
check("CSV 미리보기 성공", r.status_code == 200)
preview = r.json()
check("CSV 시트 1개", len(preview["sheets"]) == 1)
check("CSV TC 3개", preview["sheets"][0]["tc_count"] == 3)

with open(csv_path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import",
                      files={"file": ("test.csv", f, "text/csv")}, headers=H)
check("CSV import 성공", r.status_code == 201)
result = r.json()
check("CSV 3개 생성", result["created"] == 3, f"created={result['created']}")

os.unlink(csv_path)

# 4-2. Jira 형식 CSV
jira_csv = "Issue key,Summary,Issue Type,Priority,Component/s,Description,Assignee,Epic Link\n"
jira_csv += "JIRA-101,Login Flow,Test Case,High,Authentication,Test login flow steps,robin,Auth Epic\n"
jira_csv += "JIRA-102,Signup Flow,Test Case,Medium,Registration,Test signup flow,admin,Auth Epic\n"
jira_csv += "JIRA-103,Password Reset,Test Case,Low,Authentication,Test password reset,robin,Auth Epic\n"

with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
    f.write(jira_csv)
    jira_path = f.name

with open(jira_path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import",
                      files={"file": ("jira_export.csv", f, "text/csv")}, headers=H)
check("Jira CSV import 성공", r.status_code == 201)
jira_result = r.json()
check("Jira 3개 생성", jira_result["created"] == 3, f"created={jira_result['created']}")

# Jira 매핑 검증
jira_tcs = requests.get(f"{BASE}/api/projects/{PID}/testcases", params={"sheet_name": "CSV Import"}, headers=H).json()
jira_tc = [t for t in jira_tcs if t["tc_id"] == "JIRA-101"]
check("Jira TC 존재", len(jira_tc) == 1)
if jira_tc:
    check("Jira Summary→depth2 매핑", jira_tc[0]["depth2"] == "Login Flow")
    check("Jira Priority 매핑", jira_tc[0]["priority"] == "High")
    check("Jira Component→category 매핑", jira_tc[0]["category"] == "Authentication")
    check("Jira Description→test_steps 매핑", jira_tc[0]["test_steps"] == "Test login flow steps")
    check("Jira Assignee 매핑", jira_tc[0]["assignee"] == "robin")
    check("Jira Epic Link→depth1 매핑", jira_tc[0]["depth1"] == "Auth Epic")

os.unlink(jira_path)

# 4-3. 덮어쓰기 테스트
overwrite_csv = "Issue key,Summary,Priority\nJIRA-101,Updated Login,Critical\n"
with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
    f.write(overwrite_csv)
    ow_path = f.name

with open(ow_path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import",
                      files={"file": ("update.csv", f, "text/csv")}, headers=H)
check("CSV 덮어쓰기 성공", r.status_code == 201)
check("updated=1", r.json()["updated"] == 1, f"updated={r.json()['updated']}")

jira_tcs2 = requests.get(f"{BASE}/api/projects/{PID}/testcases", params={"sheet_name": "CSV Import"}, headers=H).json()
jira_tc2 = [t for t in jira_tcs2 if t["tc_id"] == "JIRA-101"]
check("덮어쓰기 후 depth2 변경됨", jira_tc2[0]["depth2"] == "Updated Login" if jira_tc2 else False)
check("덮어쓰기 후 priority 변경됨", jira_tc2[0]["priority"] == "Critical" if jira_tc2 else False)
os.unlink(ow_path)

# 4-4. 빈 CSV
empty_csv = "No,TC ID\n"
with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
    f.write(empty_csv)
    empty_path = f.name

with open(empty_path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import",
                      files={"file": ("empty.csv", f, "text/csv")}, headers=H)
check("빈 CSV import (0건)", r.status_code == 201 and r.json()["created"] == 0,
      f"status={r.status_code}, created={r.json().get('created')}")
os.unlink(empty_path)

# 4-5. CP949 인코딩 CSV
cp949_csv = "TC ID,대분류,우선순위,테스트 절차,기대결과\nCP-001,인증,높음,한글 스텝,한글 결과\n"
with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
    f.write(cp949_csv.encode("cp949"))
    cp949_path = f.name

with open(cp949_path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import",
                      files={"file": ("cp949.csv", f, "text/csv")}, headers=H)
check("CP949 CSV import", r.status_code == 201 and r.json()["created"] >= 1,
      f"status={r.status_code}, {r.json()}")
os.unlink(cp949_path)

# 4-6. xlsx import (기존 기능 회귀)
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import",
                  files={"file": ("test.txt", b"not excel", "application/octet-stream")}, headers=H)
check("비Excel 파일 거부", r.status_code == 400, f"status={r.status_code}")

# ============================================================================
print("\n" + "=" * 70)
print("5. 고급 필터 + 저장된 뷰")
print("=" * 70)

# TC 더 추가 (필터 테스트용)
test_tcs = [
    {"no": 201, "tc_id": "FT-001", "type": "Func.", "priority": "높음", "assignee": "robin", "category": "Auth"},
    {"no": 202, "tc_id": "FT-002", "type": "UI/UX", "priority": "보통", "assignee": "", "category": "Auth"},
    {"no": 203, "tc_id": "FT-003", "type": "Func.", "priority": "높음", "assignee": "admin", "category": "Payment"},
    {"no": 204, "tc_id": "FT-004", "type": "API", "priority": "낮음", "assignee": "robin", "category": "Payment"},
    {"no": 205, "tc_id": "FT-005", "type": "Func.", "priority": "매우 높음", "assignee": "", "category": ""},
]
for tc in test_tcs:
    requests.post(f"{BASE}/api/projects/{PID}/testcases", json=tc, headers=H)

# 5-1. contains 필터
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [{"field": "tc_id", "operator": "contains", "value": "FT-"}], "logic": "AND"
}, headers=H)
check("contains 필터", r.status_code == 200)
check("contains 결과 5건", len(r.json()) == 5, f"got {len(r.json())}")

# 5-2. eq 필터
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [{"field": "priority", "operator": "eq", "value": "높음"}], "logic": "AND"
}, headers=H)
eq_count = len(r.json())
check("eq 필터 (높음)", r.status_code == 200 and eq_count >= 2, f"got {eq_count}")

# 5-3. neq 필터
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [
        {"field": "tc_id", "operator": "contains", "value": "FT-"},
        {"field": "priority", "operator": "neq", "value": "높음"}
    ], "logic": "AND"
}, headers=H)
check("neq 필터", r.status_code == 200 and len(r.json()) == 3, f"got {len(r.json())}")

# 5-4. empty 필터
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [
        {"field": "tc_id", "operator": "contains", "value": "FT-"},
        {"field": "assignee", "operator": "empty"}
    ], "logic": "AND"
}, headers=H)
check("empty 필터 (assignee 비어있음)", r.status_code == 200 and len(r.json()) == 2,
      f"got {len(r.json())}")

# 5-5. not_empty 필터
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [
        {"field": "tc_id", "operator": "contains", "value": "FT-"},
        {"field": "assignee", "operator": "not_empty"}
    ], "logic": "AND"
}, headers=H)
check("not_empty 필터", r.status_code == 200 and len(r.json()) == 3, f"got {len(r.json())}")

# 5-6. not_contains 필터
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [
        {"field": "tc_id", "operator": "contains", "value": "FT-"},
        {"field": "type", "operator": "not_contains", "value": "Func"}
    ], "logic": "AND"
}, headers=H)
check("not_contains 필터", r.status_code == 200 and len(r.json()) == 2, f"got {len(r.json())}")

# 5-7. OR 로직
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [
        {"field": "priority", "operator": "eq", "value": "매우 높음"},
        {"field": "type", "operator": "eq", "value": "API"}
    ], "logic": "OR"
}, headers=H)
check("OR 필터", r.status_code == 200 and len(r.json()) >= 2, f"got {len(r.json())}")

# 5-8. AND 다중 조건
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [
        {"field": "type", "operator": "eq", "value": "Func."},
        {"field": "category", "operator": "eq", "value": "Auth"},
        {"field": "assignee", "operator": "eq", "value": "robin"}
    ], "logic": "AND"
}, headers=H)
check("AND 다중 조건 (3개)", r.status_code == 200 and len(r.json()) == 1, f"got {len(r.json())}")

# 5-9. 빈 조건 필터
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={
    "name": "_", "conditions": [], "logic": "AND"
}, headers=H)
check("빈 조건 → 전체 반환", r.status_code == 200 and len(r.json()) > 5)

# 5-10. 필터 저장
r = requests.post(f"{BASE}/api/projects/{PID}/filters", json={
    "name": "High Priority Func",
    "conditions": [
        {"field": "priority", "operator": "eq", "value": "높음"},
        {"field": "type", "operator": "eq", "value": "Func."}
    ],
    "logic": "AND"
}, headers=H)
check("필터 저장", r.status_code == 201)
saved_filter = r.json()
check("저장된 필터 이름", saved_filter["name"] == "High Priority Func")
check("저장된 조건 2개", len(saved_filter["conditions"]) == 2)
filter_id = saved_filter["id"]

# 5-11. 필터 리스트
r = requests.get(f"{BASE}/api/projects/{PID}/filters", headers=H)
check("필터 리스트", r.status_code == 200 and len(r.json()) >= 1)

# 5-12. 필터 수정
r = requests.put(f"{BASE}/api/projects/{PID}/filters/{filter_id}",
                 json={"name": "Updated Filter", "logic": "OR"}, headers=H)
check("필터 수정", r.status_code == 200)
check("수정 후 이름", r.json()["name"] == "Updated Filter")
check("수정 후 logic", r.json()["logic"] == "OR")

# 5-13. 잘못된 logic
r = requests.post(f"{BASE}/api/projects/{PID}/filters", json={
    "name": "bad", "conditions": [], "logic": "XOR"
}, headers=H)
check("잘못된 logic 거부", r.status_code == 400)

# 5-14. 빈 필터 이름 거부
r = requests.post(f"{BASE}/api/projects/{PID}/filters", json={
    "name": " ", "conditions": [], "logic": "AND"
}, headers=H)
check("빈 필터 이름 거부", r.status_code == 400)

# 5-15. 없는 필터 조작
r = requests.delete(f"{BASE}/api/projects/{PID}/filters/99999", headers=H)
check("없는 필터 삭제 404", r.status_code == 404)

# 5-16. 필터 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/filters/{filter_id}", headers=H)
check("필터 삭제", r.status_code == 200)

# ============================================================================
print("\n" + "=" * 70)
print("6. 기존 기능 회귀 테스트")
print("=" * 70)

# 6-1. TC CRUD
r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
    "no": 301, "tc_id": "REG-001", "type": "Func.", "priority": "보통",
    "test_steps": "Step 1\nStep 2", "expected_result": "Expected"
}, headers=H)
check("TC 생성 (기존)", r.status_code == 201)
reg_tc_id = r.json()["id"]

r = requests.get(f"{BASE}/api/projects/{PID}/testcases", headers=H)
check("TC 리스트 조회 (기존)", r.status_code == 200 and len(r.json()) > 0)

r = requests.put(f"{BASE}/api/projects/{PID}/testcases/{reg_tc_id}",
                 json={"priority": "높음", "assignee": "tester"}, headers=H)
check("TC 수정 (기존)", r.status_code == 200)
check("수정 반영", r.json()["priority"] == "높음" and r.json()["assignee"] == "tester")

# 6-2. TC 소프트 삭제 + 복원
r = requests.delete(f"{BASE}/api/projects/{PID}/testcases/{reg_tc_id}", headers=H)
check("TC 소프트 삭제", r.status_code == 204, f"status={r.status_code}")

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/{reg_tc_id}/restore", headers=H)
check("TC 복원", r.status_code == 200)

# 6-3. Bulk Update
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/bulk", json={
    "items": [{"id": reg_tc_id, "priority": "매우 높음", "remarks": "bulk updated"}]
}, headers=H)
check("Bulk Update", r.status_code == 200)
check("Bulk Update 반영", r.json()[0]["priority"] == "매우 높음")

# 6-4. Bulk Delete
r = requests.delete(f"{BASE}/api/projects/{PID}/testcases/bulk",
                    params={"ids": str(reg_tc_id)}, headers=H)
check("Bulk Delete", r.status_code == 200)

# 6-5. TestRun CRUD (기존)
r = requests.get(f"{BASE}/api/projects/{PID}/testruns", headers=H)
check("TestRun 리스트 (기존)", r.status_code == 200)

# 6-6. Dashboard (기존)
r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/summary", headers=H)
check("Dashboard summary (기존)", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/priority", headers=H)
check("Dashboard priority (기존)", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/category", headers=H)
check("Dashboard category (기존)", r.status_code == 200)

# 6-7. Export Excel (기존)
r = requests.get(f"{BASE}/api/projects/{PID}/testcases/export", headers=H)
check("Excel export (기존)", r.status_code == 200 and len(r.content) > 1000,
      f"status={r.status_code}, size={len(r.content)}")

# 6-8. 시트 필터링 (기존)
r = requests.get(f"{BASE}/api/projects/{PID}/testcases", params={"sheet_name": "기본"}, headers=H)
check("시트별 TC 필터링 (기존)", r.status_code == 200)

# 6-9. 검색 (기존)
r = requests.get(f"{BASE}/api/projects/{PID}/testcases", params={"search": "FT-001"}, headers=H)
check("검색 (기존)", r.status_code == 200 and len(r.json()) >= 1, f"got {len(r.json())}")

# ============================================================================
# 정리: 테스트 프로젝트 삭제
requests.delete(f"{BASE}/api/projects/{PID}", headers=H)

print("\n" + "=" * 70)
print(f"  TOTAL: {TOTAL}  |  PASS: {PASS_COUNT}  |  FAIL: {FAIL_COUNT}")
print("=" * 70)
if FAIL_COUNT > 0:
    print("  *** SOME TESTS FAILED ***")
    sys.exit(1)
else:
    print("  *** ALL TESTS PASSED ***")
