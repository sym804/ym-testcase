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
    "no": 1,
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
print("\n" + "=" * 70)
print("5. 대시보드 날짜 필터")
print("=" * 70)

# 기본 조회 (날짜 없이)
r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/summary", headers=H)
check("대시보드 summary 기본 조회", r.status_code == 200)

# 날짜 범위로 조회
r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/summary",
    params={"date_from": "2020-01-01", "date_to": "2099-12-31"}, headers=H)
check("대시보드 summary 날짜 필터", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/priority",
    params={"date_from": "2020-01-01", "date_to": "2099-12-31"}, headers=H)
check("대시보드 priority 날짜 필터", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/category",
    params={"date_from": "2020-01-01"}, headers=H)
check("대시보드 category date_from만", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/rounds",
    params={"date_from": "2020-01-01", "date_to": "2099-12-31"}, headers=H)
check("대시보드 rounds 날짜 필터", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/assignee",
    params={"date_to": "2099-12-31"}, headers=H)
check("대시보드 assignee date_to만", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/heatmap",
    params={"date_from": "2020-01-01", "date_to": "2099-12-31"}, headers=H)
check("대시보드 heatmap 날짜 필터", r.status_code == 200)

# ============================================================================
print("\n" + "=" * 70)
print("6. TC 드래그 앤 드롭 정렬")
print("=" * 70)

# TC 3개 생성
tc_ids_for_reorder = []
for i in range(1, 4):
    r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
        "no": 100 + i, "tc_id": f"DND-{i:03d}", "category": "정렬테스트",
        "priority": "보통", "sheet_name": "기본"
    }, headers=H)
    tc_ids_for_reorder.append(r.json()["id"])

# 순서 변경: 3→1→2
new_order = [
    {"id": tc_ids_for_reorder[2], "no": 1},
    {"id": tc_ids_for_reorder[0], "no": 2},
    {"id": tc_ids_for_reorder[1], "no": 3},
]
r = requests.put(f"{BASE}/api/projects/{PID}/testcases/reorder",
    json={"items": new_order}, headers=H)
check("reorder 성공", r.status_code == 200, f"status={r.status_code}")
check("reorder 3건 반환", r.json().get("updated") == 3, str(r.json()))

# 순서 확인
r = requests.get(f"{BASE}/api/projects/{PID}/testcases", headers=H)
tcs = [tc for tc in r.json() if tc["category"] == "정렬테스트"]
tcs.sort(key=lambda x: x["no"])
check("첫 번째 TC는 DND-003", tcs[0]["tc_id"] == "DND-003", tcs[0]["tc_id"])
check("두 번째 TC는 DND-001", tcs[1]["tc_id"] == "DND-001", tcs[1]["tc_id"])
check("세 번째 TC는 DND-002", tcs[2]["tc_id"] == "DND-002", tcs[2]["tc_id"])

# ============================================================================
print("\n" + "=" * 70)
print("5. 인앱 알림")
print("=" * 70)

# 알림 목록 조회 (기존 상태)
r = requests.get(f"{BASE}/api/notifications", headers=H)
check("알림 목록 조회", r.status_code == 200)
initial_count = len(r.json())

# TC + 테스트 런 생성
r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
    "no": 200, "tc_id": "NOTI-001", "category": "알림",
    "priority": "보통", "sheet_name": "기본"
}, headers=H)
noti_tc_id = r.json()["id"]

r = requests.post(f"{BASE}/api/projects/{PID}/testruns", json={
    "name": "알림테스트런", "version": "v1", "round": 1
}, headers=H)
noti_run_id = r.json()["id"]

# FAIL 결과 제출
requests.post(f"{BASE}/api/projects/{PID}/testruns/{noti_run_id}/results", json=[
    {"test_case_id": noti_tc_id, "result": "FAIL", "actual_result": "실패함"}
], headers=H)

# 런 완료 → 알림 자동 생성
requests.put(f"{BASE}/api/projects/{PID}/testruns/{noti_run_id}/complete", headers=H)

# 알림 확인
r = requests.get(f"{BASE}/api/notifications", headers=H)
check("알림 생성됨", len(r.json()) > initial_count, f"before={initial_count}, after={len(r.json())}")
notifications = r.json()
if notifications:
    latest = notifications[0]
    check("알림에 message 필드", "message" in latest)
    check("알림에 is_read 필드", "is_read" in latest)
    check("알림 미읽음 상태", latest["is_read"] == False)

    # 읽음 처리
    noti_id = latest["id"]
    r = requests.put(f"{BASE}/api/notifications/{noti_id}/read", headers=H)
    check("읽음 처리 성공", r.status_code == 200)

    # 전체 읽음 처리
    r = requests.put(f"{BASE}/api/notifications/read-all", headers=H)
    check("전체 읽음 처리", r.status_code == 200)

# 미읽음 개수
r = requests.get(f"{BASE}/api/notifications/unread-count", headers=H)
check("미읽음 개수 조회", r.status_code == 200)
check("미읽음 0건", r.json().get("count") == 0, str(r.json()))

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
