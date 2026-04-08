"""
v0.6.0 엣지케이스 포함 확장 테스트
기능별로 정상/비정상/경계값/엣지케이스 전부 커버
"""
import io, csv, sys, json, requests, tempfile, os

BASE = os.getenv("TEST_BASE_URL", "http://localhost:8008")
PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL = 0
RESULTS = []  # (section, tc_id, name, depth1, depth2, result, severity)


def login():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": os.getenv("TEST_ADMIN_PASSWORD", "test1234")})
    if r.status_code != 200:
        print(f"[FATAL] Login failed: {r.text}")
        sys.exit(1)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def check(section, tc_id, name, d1, d2, condition, severity="중간", detail=""):
    global PASS_COUNT, FAIL_COUNT, TOTAL
    TOTAL += 1
    result = "PASS" if condition else "FAIL"
    if condition:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    RESULTS.append((section, tc_id, name, d1, d2, result, severity, detail))
    status = "[PASS]" if condition else f"[FAIL] {detail}"
    print(f"  {status} {tc_id}: {d1}/{d2}")


H = login()
r = requests.post(f"{BASE}/api/projects", json={"name": "v060_edge_test"}, headers=H)
PID = r.json()["id"]

# ============================================================================
print("\n" + "=" * 70)
print("1. 시트 트리 구조 -엣지케이스")
print("=" * 70)
SEC = "시트 트리"

# 기본 CRUD
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Root-A"}, headers=H)
check(SEC, "TC-BE-TREE-E01", SEC, "루트 시트 생성", "정상", r.status_code == 200, "핵심")
rootA = r.json()

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Root-B"}, headers=H)
check(SEC, "TC-BE-TREE-E02", SEC, "루트 시트 2개", "정상", r.status_code == 200, "핵심")
rootB = r.json()

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Child-A1", "parent_id": rootA["id"]}, headers=H)
check(SEC, "TC-BE-TREE-E03", SEC, "하위 시트 생성", "parent_id 지정", r.status_code == 200 and r.json()["parent_id"] == rootA["id"], "핵심")
childA1 = r.json()

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Child-A2", "parent_id": rootA["id"]}, headers=H)
childA2 = r.json()

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Grand-A1a", "parent_id": childA1["id"]}, headers=H)
check(SEC, "TC-BE-TREE-E04", SEC, "3 depth 생성", "손자 시트", r.status_code == 200 and r.json()["parent_id"] == childA1["id"], "핵심")
grandA1a = r.json()

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Great-Grand", "parent_id": grandA1a["id"]}, headers=H)
check(SEC, "TC-BE-TREE-E05", SEC, "4 depth 생성", "증손 시트", r.status_code == 200, "중간")
greatGrand = r.json()

# 트리 조회
r = requests.get(f"{BASE}/api/projects/{PID}/testcases/sheets", headers=H)
tree = r.json()
check(SEC, "TC-BE-TREE-E06", SEC, "트리 조회", "루트 2개", len(tree) == 2, "핵심")

rootA_node = [n for n in tree if n["name"] == "Root-A"][0]
check(SEC, "TC-BE-TREE-E07", SEC, "트리 조회", "Root-A 하위 2개", len(rootA_node["children"]) == 2, "핵심")

child_a1_node = [c for c in rootA_node["children"] if c["name"] == "Child-A1"][0]
check(SEC, "TC-BE-TREE-E08", SEC, "트리 조회", "3 depth 중첩 확인", len(child_a1_node["children"]) == 1, "핵심")

grand_node = child_a1_node["children"][0]
check(SEC, "TC-BE-TREE-E09", SEC, "트리 조회", "4 depth 중첩 확인", len(grand_node["children"]) == 1, "중간")

# 엣지: 중복 이름
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Root-A"}, headers=H)
check(SEC, "TC-BE-TREE-E10", SEC, "중복 이름", "거부", r.status_code == 400, "핵심")

# 엣지: 빈 이름
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": ""}, headers=H)
check(SEC, "TC-BE-TREE-E11", SEC, "빈 이름", "거부", r.status_code == 400, "핵심")

# 엣지: 공백만
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "   "}, headers=H)
check(SEC, "TC-BE-TREE-E12", SEC, "공백만 이름", "거부", r.status_code == 400, "중간")

# 엣지: 특수문자 이름
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Sheet <test> & 'quotes'"}, headers=H)
check(SEC, "TC-BE-TREE-E13", SEC, "특수문자 이름", "허용", r.status_code == 200, "중간")
special_sheet = r.json()

# 엣지: 한글 이름
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "기능 테스트 시트"}, headers=H)
check(SEC, "TC-BE-TREE-E14", SEC, "한글 이름", "허용", r.status_code == 200, "중간")
kr_sheet = r.json()

# 엣지: 존재하지 않는 parent_id
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "orphan", "parent_id": 99999}, headers=H)
check(SEC, "TC-BE-TREE-E15", SEC, "없는 parent_id", "거부 400", r.status_code == 400, "핵심")

# 이름 변경
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{rootB['id']}/rename", json={"new_name": "Root-B-Renamed"}, headers=H)
check(SEC, "TC-BE-TREE-E16", SEC, "이름 변경", "정상", r.status_code == 200 and r.json()["name"] == "Root-B-Renamed", "핵심")

# 이름 변경 + TC sheet_name 동기화
requests.post(f"{BASE}/api/projects/{PID}/testcases", json={"no": 1, "tc_id": "SYNC-001", "sheet_name": "Root-B-Renamed"}, headers=H)
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{rootB['id']}/rename", json={"new_name": "Root-B-Final"}, headers=H)
tcs = requests.get(f"{BASE}/api/projects/{PID}/testcases", params={"sheet_name": "Root-B-Final"}, headers=H).json()
check(SEC, "TC-BE-TREE-E17", SEC, "이름 변경", "TC sheet_name 동기화", len(tcs) == 1 and tcs[0]["tc_id"] == "SYNC-001", "핵심")

# 이름 변경: 빈 이름
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{rootB['id']}/rename", json={"new_name": ""}, headers=H)
check(SEC, "TC-BE-TREE-E18", SEC, "이름 변경", "빈 이름 거부", r.status_code == 400, "중간")

# 이름 변경: 중복 이름
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{rootB['id']}/rename", json={"new_name": "Root-A"}, headers=H)
check(SEC, "TC-BE-TREE-E19", SEC, "이름 변경", "중복 이름 거부", r.status_code == 400, "중간")

# 이동
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{childA2['id']}/move", json={"parent_id": rootB["id"]}, headers=H)
check(SEC, "TC-BE-TREE-E20", SEC, "시트 이동", "다른 부모로", r.status_code == 200 and r.json()["parent_id"] == rootB["id"], "핵심")

# 이동: 루트로
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{childA2['id']}/move", json={"parent_id": None}, headers=H)
check(SEC, "TC-BE-TREE-E21", SEC, "시트 이동", "루트로 이동", r.status_code == 200 and r.json()["parent_id"] is None, "중간")

# 이동: 순환 참조 방지 (부모→자식)
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{rootA['id']}/move", json={"parent_id": childA1["id"]}, headers=H)
check(SEC, "TC-BE-TREE-E22", SEC, "순환 참조", "부모→자식 거부", r.status_code == 400, "핵심")

# 이동: 순환 참조 방지 (부모→손자)
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{rootA['id']}/move", json={"parent_id": grandA1a["id"]}, headers=H)
check(SEC, "TC-BE-TREE-E23", SEC, "순환 참조", "부모→손자 거부", r.status_code == 400, "핵심")

# 이동: 자기 자신
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/sheets/{childA1['id']}/move", json={"parent_id": childA1["id"]}, headers=H)
check(SEC, "TC-BE-TREE-E24", SEC, "순환 참조", "자기 자신 거부", r.status_code == 400, "핵심")

# flat=true 호환
r = requests.get(f"{BASE}/api/projects/{PID}/testcases/sheets", params={"flat": "true"}, headers=H)
check(SEC, "TC-BE-TREE-E25", SEC, "flat 조회", "기존 호환 포맷", r.status_code == 200 and all("name" in s for s in r.json()), "핵심")

# TC가 있는 시트 삭제 시 TC 소프트 삭제
# Root-A/Child-A1/Grand-A1a 모두 is_folder=True → leaf인 Great-Grand에 TC 추가
requests.post(f"{BASE}/api/projects/{PID}/testcases", json={"no": 10, "tc_id": "DEL-TC-001", "sheet_name": "Great-Grand"}, headers=H)
requests.post(f"{BASE}/api/projects/{PID}/testcases", json={"no": 11, "tc_id": "DEL-TC-002", "sheet_name": "Great-Grand"}, headers=H)
r = requests.delete(f"{BASE}/api/projects/{PID}/testcases/sheets/Root-A", headers=H)
check(SEC, "TC-BE-TREE-E26", SEC, "CASCADE 삭제", "TC 소프트 삭제 포함", r.status_code == 200 and r.json()["deleted"] >= 2, "핵심",
      f"deleted={r.json().get('deleted')}")

# CASCADE 확인: 하위 시트도 삭제됨
r = requests.get(f"{BASE}/api/projects/{PID}/testcases/sheets", headers=H)
all_names = []
def collect(nodes):
    for n in nodes:
        all_names.append(n["name"])
        collect(n["children"])
collect(r.json())
check(SEC, "TC-BE-TREE-E27", SEC, "CASCADE 삭제", "Child-A1 삭제됨", "Child-A1" not in all_names, "핵심")
check(SEC, "TC-BE-TREE-E28", SEC, "CASCADE 삭제", "Grand-A1a 삭제됨", "Grand-A1a" not in all_names, "핵심")
check(SEC, "TC-BE-TREE-E29", SEC, "CASCADE 삭제", "Great-Grand 삭제됨", "Great-Grand" not in all_names, "핵심")

# 없는 시트 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/testcases/sheets/NonExistent", headers=H)
check(SEC, "TC-BE-TREE-E30", SEC, "없는 시트 삭제", "정상 처리 (0건)", r.status_code == 200, "중간")

# sort_order 확인
r1 = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Sort-1"}, headers=H)
r2 = requests.post(f"{BASE}/api/projects/{PID}/testcases/sheets", json={"name": "Sort-2"}, headers=H)
check(SEC, "TC-BE-TREE-E31", SEC, "sort_order", "자동 증가", r2.json().get("sort_order", -1) > r1.json().get("sort_order", -1), "중간",
      f"s1={r1.json().get('sort_order')}, s2={r2.json().get('sort_order')}")

# ============================================================================
print("\n" + "=" * 70)
print("2. 커스텀 필드 -엣지케이스")
print("=" * 70)
SEC = "커스텀 필드"

# 각 타입별 생성
for ftype in ["text", "number", "select", "multiselect", "checkbox", "date"]:
    opts = {"field_name": f"CF-{ftype}", "field_type": ftype}
    if ftype in ("select", "multiselect"):
        opts["options"] = ["Opt-A", "Opt-B", "Opt-C"]
    r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json=opts, headers=H)
    check(SEC, f"TC-BE-CF-E{ftype[:3].upper()}", SEC, "타입별 생성", ftype, r.status_code == 201, "핵심")

# 리스트 + sort_order
r = requests.get(f"{BASE}/api/projects/{PID}/custom-fields", headers=H)
cfs = r.json()
check(SEC, "TC-BE-CF-E07", SEC, "리스트", "6개 생성 확인", len(cfs) == 6, "핵심", f"got {len(cfs)}")
check(SEC, "TC-BE-CF-E08", SEC, "sort_order", "순차 증가", [c["sort_order"] for c in cfs] == list(range(6)), "중간")

# 중복 이름
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "CF-text", "field_type": "text"}, headers=H)
check(SEC, "TC-BE-CF-E09", SEC, "중복 이름", "거부 400", r.status_code == 400, "핵심")

# 빈 이름
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "", "field_type": "text"}, headers=H)
check(SEC, "TC-BE-CF-E10", SEC, "빈 이름", "거부 400", r.status_code == 400, "핵심")

# 공백만 이름
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "   ", "field_type": "text"}, headers=H)
check(SEC, "TC-BE-CF-E11", SEC, "공백만", "거부 400", r.status_code == 400, "중간")

# 잘못된 타입
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "bad", "field_type": "color"}, headers=H)
check(SEC, "TC-BE-CF-E12", SEC, "잘못된 타입", "거부 400", r.status_code == 400, "핵심")

# 특수문자 이름
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "필드<>&'\"", "field_type": "text"}, headers=H)
check(SEC, "TC-BE-CF-E13", SEC, "특수문자 이름", "허용", r.status_code == 201, "중간")

# 필드 수정
cf_id = cfs[0]["id"]
r = requests.put(f"{BASE}/api/projects/{PID}/custom-fields/{cf_id}", json={"field_name": "CF-text-updated"}, headers=H)
check(SEC, "TC-BE-CF-E14", SEC, "필드 수정", "이름 변경", r.status_code == 200 and r.json()["field_name"] == "CF-text-updated", "핵심")

# 필드 수정: 옵션 변경
cf_sel = [c for c in cfs if c["field_type"] == "select"][0]
r = requests.put(f"{BASE}/api/projects/{PID}/custom-fields/{cf_sel['id']}", json={"options": ["X", "Y", "Z", "W"]}, headers=H)
check(SEC, "TC-BE-CF-E15", SEC, "필드 수정", "옵션 변경", r.status_code == 200 and len(r.json()["options"]) == 4, "중간")

# 필드 수정: sort_order 변경
r = requests.put(f"{BASE}/api/projects/{PID}/custom-fields/{cf_id}", json={"sort_order": 99}, headers=H)
check(SEC, "TC-BE-CF-E16", SEC, "필드 수정", "sort_order 변경", r.status_code == 200 and r.json()["sort_order"] == 99, "중간")

# 없는 필드 수정
r = requests.put(f"{BASE}/api/projects/{PID}/custom-fields/99999", json={"field_name": "x"}, headers=H)
check(SEC, "TC-BE-CF-E17", SEC, "없는 필드", "수정 404", r.status_code == 404, "중간")

# 없는 필드 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/custom-fields/99999", headers=H)
check(SEC, "TC-BE-CF-E18", SEC, "없는 필드", "삭제 404", r.status_code == 404, "중간")

# TC에 custom_fields 저장
r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
    "no": 50, "tc_id": "CF-TC-001",
    "custom_fields": {"CF-text-updated": "hello", "CF-number": 42, "CF-checkbox": True}
}, headers=H)
check(SEC, "TC-BE-CF-E19", SEC, "TC 저장", "custom_fields 포함 생성", r.status_code == 201 and r.json().get("custom_fields") is not None, "핵심")
cf_tc_id = r.json()["id"]

# TC custom_fields 조회
r = requests.get(f"{BASE}/api/projects/{PID}/testcases", headers=H)
tc = [t for t in r.json() if t["tc_id"] == "CF-TC-001"]
check(SEC, "TC-BE-CF-E20", SEC, "TC 조회", "custom_fields 포함", len(tc) == 1 and tc[0].get("custom_fields", {}).get("CF-number") == 42, "핵심")

# TC custom_fields 수정
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/{cf_tc_id}", json={"custom_fields": {"CF-text-updated": "updated", "CF-number": 99}}, headers=H)
check(SEC, "TC-BE-CF-E21", SEC, "TC 수정", "custom_fields 변경", r.status_code == 200 and r.json()["custom_fields"]["CF-number"] == 99, "핵심")

# TC custom_fields null 저장
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/{cf_tc_id}", json={"custom_fields": None}, headers=H)
check(SEC, "TC-BE-CF-E22", SEC, "TC 수정", "custom_fields null", r.status_code == 200, "중간")

# 필드 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/custom-fields/{cf_id}", headers=H)
check(SEC, "TC-BE-CF-E23", SEC, "필드 삭제", "정상", r.status_code == 200, "핵심")

# is_required 설정
r = requests.post(f"{BASE}/api/projects/{PID}/custom-fields", json={"field_name": "Required-Field", "field_type": "text", "is_required": True}, headers=H)
check(SEC, "TC-BE-CF-E24", SEC, "is_required", "true 설정", r.status_code == 201 and r.json()["is_required"] is True, "중간")

# ============================================================================
print("\n" + "=" * 70)
print("3. 테스트 플랜 -엣지케이스")
print("=" * 70)
SEC = "테스트 플랜"

# 생성
r = requests.post(f"{BASE}/api/projects/{PID}/testplans", json={
    "name": "Plan-Alpha", "milestone": "Sprint-1", "description": "Description",
    "start_date": "2026-03-01T00:00:00", "end_date": "2026-03-31T00:00:00"
}, headers=H)
check(SEC, "TC-BE-PLAN-E01", SEC, "생성", "전체 필드", r.status_code == 201, "핵심")
planA = r.json()
planA_id = planA["id"]
check(SEC, "TC-BE-PLAN-E02", SEC, "생성", "이름 정확", planA["name"] == "Plan-Alpha", "핵심")
check(SEC, "TC-BE-PLAN-E03", SEC, "생성", "마일스톤 정확", planA["milestone"] == "Sprint-1", "핵심")
check(SEC, "TC-BE-PLAN-E04", SEC, "생성", "초기 run_count=0", planA["run_count"] == 0, "핵심")
check(SEC, "TC-BE-PLAN-E05", SEC, "생성", "초기 progress.total=0", planA["progress"]["total"] == 0, "핵심")

# 빈 이름 거부
r = requests.post(f"{BASE}/api/projects/{PID}/testplans", json={"name": " "}, headers=H)
check(SEC, "TC-BE-PLAN-E06", SEC, "빈 이름", "거부 400", r.status_code == 400, "핵심")

# 최소 필드 (이름만)
r = requests.post(f"{BASE}/api/projects/{PID}/testplans", json={"name": "Minimal"}, headers=H)
check(SEC, "TC-BE-PLAN-E07", SEC, "최소 생성", "이름만", r.status_code == 201, "중간")
planB_id = r.json()["id"]

# 수정
r = requests.put(f"{BASE}/api/projects/{PID}/testplans/{planA_id}", json={"milestone": "Sprint-2", "description": "Updated"}, headers=H)
check(SEC, "TC-BE-PLAN-E08", SEC, "수정", "마일스톤 변경", r.status_code == 200 and r.json()["milestone"] == "Sprint-2", "핵심")

# 조회
r = requests.get(f"{BASE}/api/projects/{PID}/testplans/{planA_id}", headers=H)
check(SEC, "TC-BE-PLAN-E09", SEC, "단건 조회", "정상", r.status_code == 200, "핵심")

# 리스트
r = requests.get(f"{BASE}/api/projects/{PID}/testplans", headers=H)
check(SEC, "TC-BE-PLAN-E10", SEC, "리스트", "2개 이상", r.status_code == 200 and len(r.json()) >= 2, "핵심")

# 없는 플랜 조회
r = requests.get(f"{BASE}/api/projects/{PID}/testplans/99999", headers=H)
check(SEC, "TC-BE-PLAN-E11", SEC, "없는 플랜", "404", r.status_code == 404, "중간")

# TestRun 연결
for i in range(1, 4):
    requests.post(f"{BASE}/api/projects/{PID}/testcases", json={"no": 200 + i, "tc_id": f"PLAN-TC-{i:03d}"}, headers=H)

run_r = requests.post(f"{BASE}/api/projects/{PID}/testruns", json={"name": "Plan-Run-1", "test_plan_id": planA_id}, headers=H)
check(SEC, "TC-BE-PLAN-E12", SEC, "Run 연결", "test_plan_id 저장", run_r.status_code == 201 and run_r.json().get("test_plan_id") == planA_id, "핵심",
      f"test_plan_id={run_r.json().get('test_plan_id')}")
run_id = run_r.json()["id"]

# 두 번째 Run 연결
run2 = requests.post(f"{BASE}/api/projects/{PID}/testruns", json={"name": "Plan-Run-2", "test_plan_id": planA_id}, headers=H)
check(SEC, "TC-BE-PLAN-E13", SEC, "다중 Run", "같은 플랜에 2개", run2.status_code == 201, "중간")
run2_id = run2.json()["id"]

# 결과 제출
run_detail = requests.get(f"{BASE}/api/projects/{PID}/testruns/{run_id}", headers=H).json()
results = [{"test_case_id": r["test_case_id"], "result": ["PASS", "FAIL", "PASS"][i % 3]} for i, r in enumerate(run_detail.get("results", []))]
if results:
    requests.post(f"{BASE}/api/projects/{PID}/testruns/{run_id}/results", json=results, headers=H)

# progress 확인
r = requests.get(f"{BASE}/api/projects/{PID}/testplans/{planA_id}", headers=H)
prog = r.json()["progress"]
check(SEC, "TC-BE-PLAN-E14", SEC, "progress", "total > 0", prog["total"] > 0, "핵심", f"total={prog['total']}")
check(SEC, "TC-BE-PLAN-E15", SEC, "progress", "pass_rate 계산", prog["pass_rate"] > 0, "핵심", f"pass_rate={prog['pass_rate']}")
check(SEC, "TC-BE-PLAN-E16", SEC, "run_count", "2", r.json()["run_count"] == 2, "중간")

# 플랜 Run 목록
r = requests.get(f"{BASE}/api/projects/{PID}/testplans/{planA_id}/runs", headers=H)
check(SEC, "TC-BE-PLAN-E17", SEC, "플랜 Runs", "2개 반환", r.status_code == 200 and len(r.json()) == 2, "핵심")

# 없는 플랜 Run 목록
r = requests.get(f"{BASE}/api/projects/{PID}/testplans/99999/runs", headers=H)
check(SEC, "TC-BE-PLAN-E18", SEC, "없는 플랜 Runs", "404", r.status_code == 404, "중간")

# 플랜 삭제 → Run.test_plan_id null
r = requests.delete(f"{BASE}/api/projects/{PID}/testplans/{planA_id}", headers=H)
check(SEC, "TC-BE-PLAN-E19", SEC, "삭제", "정상", r.status_code == 200, "핵심")

run_after = requests.get(f"{BASE}/api/projects/{PID}/testruns/{run_id}", headers=H)
check(SEC, "TC-BE-PLAN-E20", SEC, "삭제 후", "Run.test_plan_id=null", run_after.json().get("test_plan_id") is None, "핵심")

# 없는 플랜 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/testplans/99999", headers=H)
check(SEC, "TC-BE-PLAN-E21", SEC, "없는 플랜", "삭제 404", r.status_code == 404, "중간")

# ============================================================================
print("\n" + "=" * 70)
print("4. CSV Import -엣지케이스")
print("=" * 70)
SEC = "CSV Import"

def make_csv(content, encoding="utf-8"):
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
        f.write(content.encode(encoding) if isinstance(content, str) else content)
        return f.name

# 일반 CSV
path = make_csv("No,TC ID,Category,Priority,Test Steps,Expected Result\n1,CSV-E01,Auth,높음,Step1,Expect1\n2,CSV-E02,Pay,보통,Step2,Expect2\n3,CSV-E03,UI,낮음,Step3,Expect3\n")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("test.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E01", SEC, "일반 CSV", "3건 import", r.status_code == 201 and r.json()["created"] == 3, "핵심", f"created={r.json().get('created')}")
os.unlink(path)

# CSV preview
path = make_csv("TC ID,Priority\nPV-001,높음\nPV-002,보통\n")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import/preview", files={"file": ("pv.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E02", SEC, "미리보기", "tc_count 반환", r.status_code == 200 and r.json()["sheets"][0]["tc_count"] == 2, "핵심")
os.unlink(path)

# Jira 형식
path = make_csv("Issue key,Summary,Issue Type,Priority,Component/s,Description,Assignee,Epic Link\nJIRA-E01,Login,Test,High,Auth,Desc1,robin,Epic1\nJIRA-E02,Signup,Test,Med,Reg,Desc2,admin,Epic1\n")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("jira.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E03", SEC, "Jira CSV", "import 성공", r.status_code == 201 and r.json()["created"] == 2, "핵심")
# 매핑 확인
tcs = requests.get(f"{BASE}/api/projects/{PID}/testcases", params={"sheet_name": "CSV Import"}, headers=H).json()
jt = [t for t in tcs if t["tc_id"] == "JIRA-E01"]
check(SEC, "TC-BE-CSV-E04", SEC, "Jira 매핑", "Summary→depth2", len(jt) == 1 and jt[0]["depth2"] == "Login", "핵심")
check(SEC, "TC-BE-CSV-E05", SEC, "Jira 매핑", "Component→category", jt[0]["category"] == "Auth" if jt else False, "핵심")
check(SEC, "TC-BE-CSV-E06", SEC, "Jira 매핑", "Epic→depth1", jt[0]["depth1"] == "Epic1" if jt else False, "핵심")
check(SEC, "TC-BE-CSV-E07", SEC, "Jira 매핑", "Assignee 매핑", jt[0]["assignee"] == "robin" if jt else False, "중간")
os.unlink(path)

# 덮어쓰기
path = make_csv("Issue key,Summary,Priority\nJIRA-E01,Updated Login,Critical\n")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("ow.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E08", SEC, "덮어쓰기", "updated=1", r.status_code == 201 and r.json()["updated"] == 1, "핵심")
tcs2 = requests.get(f"{BASE}/api/projects/{PID}/testcases", params={"sheet_name": "CSV Import"}, headers=H).json()
jt2 = [t for t in tcs2 if t["tc_id"] == "JIRA-E01"]
check(SEC, "TC-BE-CSV-E09", SEC, "덮어쓰기", "값 변경 확인", jt2[0]["depth2"] == "Updated Login" if jt2 else False, "핵심")
os.unlink(path)

# CP949 인코딩
path = make_csv("TC ID,대분류,우선순위,테스트 절차,기대결과\nCP-E01,인증,높음,한글 스텝,한글 결과\n", "cp949")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("cp949.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E10", SEC, "CP949 인코딩", "import 성공", r.status_code == 201 and r.json()["created"] >= 1, "핵심")
os.unlink(path)

# UTF-8 BOM
bom_content = "\ufeffTC ID,Category,Priority\nBOM-001,Auth,High\n"
path = make_csv(bom_content, "utf-8-sig")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("bom.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E11", SEC, "UTF-8 BOM", "import 성공", r.status_code == 201 and r.json()["created"] >= 1, "중간")
os.unlink(path)

# 빈 CSV (헤더만)
path = make_csv("TC ID,Category\n")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("empty.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E12", SEC, "빈 CSV", "0건 처리", r.status_code == 201 and r.json()["created"] == 0, "중간")
os.unlink(path)

# 완전 빈 파일
path = make_csv("")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("nothing.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E13", SEC, "완전 빈 파일", "0건 처리", r.status_code == 201 and r.json()["created"] == 0, "중간")
os.unlink(path)

# 값에 쉼표/따옴표 포함
path = make_csv('TC ID,Category,Test Steps\nQUOTE-001,"Auth, Login","Step ""with"" quotes"\n')
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("quote.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E14", SEC, "쉼표/따옴표", "CSV 파싱 정상", r.status_code == 201 and r.json()["created"] >= 1, "중간")
os.unlink(path)

# 알 수 없는 헤더 무시
path = make_csv("TC ID,UnknownCol1,Priority,Random\nUNK-001,val1,High,val2\n")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("unk.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E15", SEC, "알 수 없는 헤더", "무시하고 import", r.status_code == 201 and r.json()["created"] >= 1, "중간")
os.unlink(path)

# 대량 CSV (100행)
rows = "No,TC ID,Category,Priority\n"
for i in range(1, 101):
    rows += f"{i},BULK-{i:04d},Cat-{i%5},High\n"
path = make_csv(rows)
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("bulk.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E16", SEC, "대량 CSV", "100건 import", r.status_code == 201 and r.json()["created"] == 100, "핵심", f"created={r.json().get('created')}")
os.unlink(path)

# 비CSV 파일 거부 (.txt)
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("bad.txt", b"not csv")}, headers=H)
check(SEC, "TC-BE-CSV-E17", SEC, "비CSV 파일", "거부", r.status_code == 400, "핵심")

# Zephyr 형식 헤더
path = make_csv("Name,Preconditions,Folder\nZeph Test,Pre cond,Auth/Login\n")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("zephyr.csv", f)}, headers=H)
zeph_r = r.json()
check(SEC, "TC-BE-CSV-E18", SEC, "Zephyr 형식", "import 성공", r.status_code == 201 and (zeph_r.get("created", 0) + zeph_r.get("updated", 0)) >= 1, "중간")
os.unlink(path)

# 한글 헤더 CSV
path = make_csv("TC ID,대분류,우선순위,테스트 절차,기대결과,담당자\nKR-001,인증,높음,스텝1,결과1,홍길동\n")
with open(path, "rb") as f:
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases/import", files={"file": ("kr.csv", f)}, headers=H)
check(SEC, "TC-BE-CSV-E19", SEC, "한글 헤더", "매핑 정상", r.status_code == 201 and r.json()["created"] >= 1, "핵심")
os.unlink(path)

# ============================================================================
print("\n" + "=" * 70)
print("5. 고급 필터 -엣지케이스")
print("=" * 70)
SEC = "고급 필터"

# 테스트 데이터
filter_tcs = [
    {"no": 301, "tc_id": "FLT-E01", "type": "Func.", "priority": "높음", "assignee": "robin", "category": "Auth", "depth1": "Login"},
    {"no": 302, "tc_id": "FLT-E02", "type": "UI/UX", "priority": "보통", "assignee": "", "category": "Auth", "depth1": ""},
    {"no": 303, "tc_id": "FLT-E03", "type": "Func.", "priority": "높음", "assignee": "admin", "category": "Payment", "depth1": "Cart"},
    {"no": 304, "tc_id": "FLT-E04", "type": "API", "priority": "낮음", "assignee": "robin", "category": "Payment", "depth1": "Checkout"},
    {"no": 305, "tc_id": "FLT-E05", "type": "Func.", "priority": "매우 높음", "assignee": "", "category": "", "depth1": "Login"},
    {"no": 306, "tc_id": "FLT-E06", "type": "Perf.", "priority": "보통", "assignee": "tester", "category": "Auth", "depth1": "Login"},
]
for tc in filter_tcs:
    requests.post(f"{BASE}/api/projects/{PID}/testcases", json=tc, headers=H)

def apply_filter(conditions, logic="AND"):
    return requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={"name": "_", "conditions": conditions, "logic": logic}, headers=H)

# eq
r = apply_filter([{"field": "priority", "operator": "eq", "value": "높음"}])
flt_ids = {t["tc_id"] for t in r.json() if t["tc_id"].startswith("FLT-E")}
check(SEC, "TC-BE-FLT-E01", SEC, "eq 연산자", "priority=높음", flt_ids == {"FLT-E01", "FLT-E03"}, "핵심", f"got {flt_ids}")

# neq
r = apply_filter([{"field": "tc_id", "operator": "contains", "value": "FLT-E"}, {"field": "priority", "operator": "neq", "value": "높음"}])
flt_ids = {t["tc_id"] for t in r.json()}
check(SEC, "TC-BE-FLT-E02", SEC, "neq 연산자", "priority≠높음", flt_ids == {"FLT-E02", "FLT-E04", "FLT-E05", "FLT-E06"}, "핵심", f"got {flt_ids}")

# contains
r = apply_filter([{"field": "tc_id", "operator": "contains", "value": "FLT-E0"}])
check(SEC, "TC-BE-FLT-E03", SEC, "contains", "tc_id에 FLT-E0 포함", len(r.json()) == 6, "핵심", f"got {len(r.json())}")

# not_contains
r = apply_filter([{"field": "tc_id", "operator": "contains", "value": "FLT-E"}, {"field": "type", "operator": "not_contains", "value": "Func"}])
flt_ids = {t["tc_id"] for t in r.json()}
check(SEC, "TC-BE-FLT-E04", SEC, "not_contains", "type에 Func 미포함", flt_ids == {"FLT-E02", "FLT-E04", "FLT-E06"}, "핵심", f"got {flt_ids}")

# empty
r = apply_filter([{"field": "tc_id", "operator": "contains", "value": "FLT-E"}, {"field": "assignee", "operator": "empty"}])
flt_ids = {t["tc_id"] for t in r.json()}
check(SEC, "TC-BE-FLT-E05", SEC, "empty", "assignee 비어있음", flt_ids == {"FLT-E02", "FLT-E05"}, "핵심", f"got {flt_ids}")

# not_empty
r = apply_filter([{"field": "tc_id", "operator": "contains", "value": "FLT-E"}, {"field": "assignee", "operator": "not_empty"}])
flt_ids = {t["tc_id"] for t in r.json()}
check(SEC, "TC-BE-FLT-E06", SEC, "not_empty", "assignee 있음", flt_ids == {"FLT-E01", "FLT-E03", "FLT-E04", "FLT-E06"}, "핵심", f"got {flt_ids}")

# AND 다중 조건
r = apply_filter([{"field": "type", "operator": "eq", "value": "Func."}, {"field": "category", "operator": "eq", "value": "Auth"}, {"field": "assignee", "operator": "eq", "value": "robin"}])
flt_ids = {t["tc_id"] for t in r.json() if t["tc_id"].startswith("FLT-E")}
check(SEC, "TC-BE-FLT-E07", SEC, "AND 3조건", "정확히 1건", flt_ids == {"FLT-E01"}, "핵심", f"got {flt_ids}")

# OR
r = apply_filter([{"field": "priority", "operator": "eq", "value": "매우 높음"}, {"field": "type", "operator": "eq", "value": "API"}], "OR")
flt_ids = {t["tc_id"] for t in r.json() if t["tc_id"].startswith("FLT-E")}
check(SEC, "TC-BE-FLT-E08", SEC, "OR 연산", "매우높음 OR API", flt_ids == {"FLT-E04", "FLT-E05"}, "핵심", f"got {flt_ids}")

# 빈 조건 → 전체 반환
r = apply_filter([])
check(SEC, "TC-BE-FLT-E09", SEC, "빈 조건", "전체 반환", r.status_code == 200 and len(r.json()) > 6, "중간")

# sheet_name 필터링과 결합
r = requests.post(f"{BASE}/api/projects/{PID}/filters/apply", json={"name": "_", "conditions": [{"field": "priority", "operator": "eq", "value": "높음"}], "logic": "AND"}, params={"sheet_name": "기본"}, headers=H)
check(SEC, "TC-BE-FLT-E10", SEC, "시트+필터", "sheet_name 결합", r.status_code == 200, "중간")

# 필터 저장
r = requests.post(f"{BASE}/api/projects/{PID}/filters", json={
    "name": "Edge Filter", "conditions": [{"field": "priority", "operator": "eq", "value": "높음"}], "logic": "AND"
}, headers=H)
check(SEC, "TC-BE-FLT-E11", SEC, "저장", "생성 성공", r.status_code == 201, "핵심")
fid = r.json()["id"]

# 필터 리스트
r = requests.get(f"{BASE}/api/projects/{PID}/filters", headers=H)
check(SEC, "TC-BE-FLT-E12", SEC, "리스트", "1개 이상", r.status_code == 200 and len(r.json()) >= 1, "핵심")

# 필터 수정
r = requests.put(f"{BASE}/api/projects/{PID}/filters/{fid}", json={"name": "Updated Filter", "logic": "OR"}, headers=H)
check(SEC, "TC-BE-FLT-E13", SEC, "수정", "이름/logic 변경", r.status_code == 200 and r.json()["name"] == "Updated Filter" and r.json()["logic"] == "OR", "핵심")

# 조건 수정
r = requests.put(f"{BASE}/api/projects/{PID}/filters/{fid}", json={
    "conditions": [{"field": "type", "operator": "eq", "value": "Func."}, {"field": "assignee", "operator": "not_empty"}]
}, headers=H)
check(SEC, "TC-BE-FLT-E14", SEC, "수정", "조건 변경", r.status_code == 200 and len(r.json()["conditions"]) == 2, "중간")

# 잘못된 logic
r = requests.post(f"{BASE}/api/projects/{PID}/filters", json={"name": "bad", "conditions": [], "logic": "XOR"}, headers=H)
check(SEC, "TC-BE-FLT-E15", SEC, "잘못된 logic", "거부 400", r.status_code == 400, "핵심")

# 빈 이름
r = requests.post(f"{BASE}/api/projects/{PID}/filters", json={"name": " ", "conditions": [], "logic": "AND"}, headers=H)
check(SEC, "TC-BE-FLT-E16", SEC, "빈 이름", "거부 400", r.status_code == 400, "핵심")

# 없는 필터 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/filters/99999", headers=H)
check(SEC, "TC-BE-FLT-E17", SEC, "없는 필터", "삭제 404", r.status_code == 404, "중간")

# 없는 필터 수정
r = requests.put(f"{BASE}/api/projects/{PID}/filters/99999", json={"name": "x"}, headers=H)
check(SEC, "TC-BE-FLT-E18", SEC, "없는 필터", "수정 404", r.status_code == 404, "중간")

# 필터 삭제
r = requests.delete(f"{BASE}/api/projects/{PID}/filters/{fid}", headers=H)
check(SEC, "TC-BE-FLT-E19", SEC, "삭제", "정상", r.status_code == 200, "핵심")

# depth1 필터
r = apply_filter([{"field": "depth1", "operator": "eq", "value": "Login"}])
flt_ids = {t["tc_id"] for t in r.json() if t["tc_id"].startswith("FLT-E")}
check(SEC, "TC-BE-FLT-E20", SEC, "depth1 필터", "Login 일치", flt_ids == {"FLT-E01", "FLT-E05", "FLT-E06"}, "중간", f"got {flt_ids}")

# category empty 필터
r = apply_filter([{"field": "tc_id", "operator": "contains", "value": "FLT-E"}, {"field": "category", "operator": "empty"}])
flt_ids = {t["tc_id"] for t in r.json()}
check(SEC, "TC-BE-FLT-E21", SEC, "category empty", "비어있는 것만", flt_ids == {"FLT-E05"}, "중간", f"got {flt_ids}")

# ============================================================================
# 정리
requests.delete(f"{BASE}/api/projects/{PID}", headers=H)

print("\n" + "=" * 70)
print(f"  TOTAL: {TOTAL}  |  PASS: {PASS_COUNT}  |  FAIL: {FAIL_COUNT}")
print("=" * 70)

# 결과를 JSON으로 저장 (엑셀 업데이트용)
with open("edge_test_results.json", "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=2)
print(f"\n결과 저장: edge_test_results.json ({len(RESULTS)}건)")

if FAIL_COUNT > 0:
    print("  *** SOME TESTS FAILED ***")
    for r in RESULTS:
        if r[5] == "FAIL":
            print(f"    FAIL: {r[1]} - {r[3]}/{r[4]} - {r[7]}")
    sys.exit(1)
else:
    print("  *** ALL TESTS PASSED ***")
