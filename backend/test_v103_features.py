"""
v1.0.3 기능 테스트
- TC 단건 복제 (clone)
- TC 벌크 복제 (bulk-clone)
"""
import sys
import requests
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
r = requests.post(f"{BASE}/api/projects", json={"name": "v103_test_project"}, headers=H)
PID = r.json()["id"]
print(f"Test project created: id={PID}")

# ============================================================================
print("\n" + "=" * 70)
print("1. TC 단건 복제 (clone)")
print("=" * 70)

# TC 생성
tc_data = {
    "tc_id": "TC-CLONE-001",
    "category": "로그인",
    "priority": "High",
    "test_steps": "1. 로그인 페이지 접속\n2. 계정 입력\n3. 로그인 클릭",
    "expected_result": "로그인 성공",
    "type": "Func.",
    "depth1": "인증",
    "depth2": "로그인",
    "test_type": "Manual",
    "precondition": "유효한 계정 필요",
    "remarks": "비고란",
}
r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json=tc_data, headers=H)
check("TC 생성", r.status_code == 201, f"status={r.status_code}, body={r.text}")
original = r.json()
original_id = original["id"]

# 단건 복제
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/{original_id}/clone", headers=H)
check("단건 복제 201", r.status_code == 201, f"status={r.status_code}, body={r.text}")
cloned = r.json()
check("복제 tc_id에 -copy 접미사", cloned.get("tc_id") == "TC-CLONE-001-copy", f"tc_id={cloned.get('tc_id')}")
check("복제 id 다름", cloned["id"] != original_id, f"cloned_id={cloned['id']}, original_id={original_id}")
check("복제 category 동일", cloned.get("category") == tc_data["category"], f"category={cloned.get('category')}")
check("복제 priority 동일", cloned.get("priority") == tc_data["priority"], f"priority={cloned.get('priority')}")
check("복제 test_steps 동일", cloned.get("test_steps") == tc_data["test_steps"], f"test_steps={cloned.get('test_steps')}")
check("복제 no 증가", cloned.get("no") > original.get("no"), f"cloned_no={cloned.get('no')}, original_no={original.get('no')}")

# ============================================================================
print("\n" + "=" * 70)
print("2. TC 벌크 복제 (bulk-clone)")
print("=" * 70)

# TC 2개 추가 생성
tc_data2 = {**tc_data, "tc_id": "TC-CLONE-002"}
tc_data3 = {**tc_data, "tc_id": "TC-CLONE-003"}
r2 = requests.post(f"{BASE}/api/projects/{PID}/testcases", json=tc_data2, headers=H)
check("TC2 생성", r2.status_code == 201, f"status={r2.status_code}")
tc2 = r2.json()

r3 = requests.post(f"{BASE}/api/projects/{PID}/testcases", json=tc_data3, headers=H)
check("TC3 생성", r3.status_code == 201, f"status={r3.status_code}")
tc3 = r3.json()

# 벌크 복제
r = requests.post(
    f"{BASE}/api/projects/{PID}/testcases/bulk-clone",
    json={"ids": [tc2["id"], tc3["id"]]},
    headers=H,
)
check("벌크 복제 201", r.status_code == 201, f"status={r.status_code}, body={r.text}")
bulk_result = r.json()
check("벌크 복제 2건 반환", len(bulk_result) == 2, f"count={len(bulk_result)}")
check("벌크 복제 첫번째 tc_id", bulk_result[0].get("tc_id") == "TC-CLONE-002-copy", f"tc_id={bulk_result[0].get('tc_id')}")
check("벌크 복제 두번째 tc_id", bulk_result[1].get("tc_id") == "TC-CLONE-003-copy", f"tc_id={bulk_result[1].get('tc_id')}")

# ============================================================================
print("\n" + "=" * 70)
print("3. 존재하지 않는 TC 복제 시 404")
print("=" * 70)

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/999999/clone", headers=H)
check("존재하지 않는 TC 단건 복제 404", r.status_code == 404, f"status={r.status_code}")

r = requests.post(
    f"{BASE}/api/projects/{PID}/testcases/bulk-clone",
    json={"ids": [999998, 999999]},
    headers=H,
)
check("존재하지 않는 TC 벌크 복제 404", r.status_code == 404, f"status={r.status_code}")

# ============================================================================
print("\n" + "=" * 70)
print("4. TC별 테스트 결과 히스토리")
print("=" * 70)

# TC 생성
r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
    "no": 10, "tc_id": "HIST-001", "category": "히스토리테스트",
    "priority": "보통", "test_steps": "스텝", "expected_result": "결과",
    "sheet_name": "기본"
}, headers=H)
HIST_TC_ID = r.json()["id"]

# 테스트 런 2개 생성 + 결과 제출
for i, result_val in enumerate(["PASS", "FAIL"], 1):
    r = requests.post(f"{BASE}/api/projects/{PID}/testruns", json={
        "name": f"Run{i}", "version": f"v{i}", "round": i
    }, headers=H)
    run_id = r.json()["id"]
    requests.post(f"{BASE}/api/projects/{PID}/testruns/{run_id}/results", json=[
        {"test_case_id": HIST_TC_ID, "result": result_val, "actual_result": f"실제결과{i}"}
    ], headers=H)

# 히스토리 조회
r = requests.get(
    f"{BASE}/api/projects/{PID}/testcases/{HIST_TC_ID}/result-history",
    headers=H
)
check("TC 결과 히스토리 조회 성공", r.status_code == 200, f"status={r.status_code}")
history = r.json()
check("히스토리 2건", len(history) == 2, f"len={len(history)}")
check("최신이 먼저 (FAIL)", history[0]["result"] == "FAIL")
check("이전이 나중 (PASS)", history[1]["result"] == "PASS")
check("런 이름 포함", "run_name" in history[0])
check("버전 포함", "version" in history[0])
check("라운드 포함", "round" in history[0])

# 존재하지 않는 TC
r = requests.get(
    f"{BASE}/api/projects/{PID}/testcases/99999/result-history",
    headers=H
)
check("없는 TC 히스토리 조회 시 404", r.status_code == 404)

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
