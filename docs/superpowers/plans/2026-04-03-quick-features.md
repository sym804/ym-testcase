# v1.0.3.0 빠른 기능 5개 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TC 복제, TC별 결과 히스토리, 대시보드 날짜 필터, TC 드래그 앤 드롭 정렬, 인앱 알림 5가지 기능을 추가한다.

**Architecture:** 백엔드(FastAPI)에 새 엔드포인트 추가 + 프론트엔드(React + AG-Grid) UI 연동. 각 기능은 독립적이므로 순차적으로 구현하되, 각각 커밋한다.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, React 18, TypeScript, AG-Grid Community, Chart.js, Axios

---

## File Structure

### Feature 1: TC 복제 (Clone)
- Modify: `backend/routes/testcases.py` — POST `/{tc_id}/clone` 엔드포인트 추가
- Modify: `frontend/src/api/index.ts` — `testCasesApi.clone()` 추가
- Modify: `frontend/src/components/TestCaseGrid.tsx` — 복제 버튼 + 핸들러
- Test: `backend/test_v103_features.py` — TC 복제 API 테스트
- Test: `frontend/src/test/api-functions.test.ts` — clone API 함수 테스트

### Feature 2: TC별 테스트 결과 히스토리
- Create: `backend/routes/tc_result_history.py` — GET `/api/projects/{project_id}/testcases/{tc_id}/result-history`
- Modify: `backend/main.py` — 라우터 등록
- Modify: `frontend/src/api/index.ts` — `testCasesApi.resultHistory()` 추가
- Modify: `frontend/src/types/index.ts` — `TCResultHistory` 인터페이스 추가
- Modify: `frontend/src/components/TestCaseGrid.tsx` — 결과 히스토리 모달 추가
- Test: `backend/test_v103_features.py` — 결과 히스토리 API 테스트

### Feature 3: 대시보드 날짜 필터
- Modify: `backend/routes/dashboard.py` — 모든 엔드포인트에 `date_from`, `date_to` 파라미터 추가
- Modify: `frontend/src/api/index.ts` — dashboardApi에 날짜 파라미터 전달
- Modify: `frontend/src/components/Dashboard.tsx` — 날짜 범위 선택 UI + 필터 적용
- Test: `backend/test_v103_features.py` — 날짜 필터 API 테스트

### Feature 4: TC 드래그 앤 드롭 정렬
- Modify: `backend/routes/testcases.py` — PUT `/reorder` 벌크 순서 변경 엔드포인트
- Modify: `frontend/src/api/index.ts` — `testCasesApi.reorder()` 추가
- Modify: `frontend/src/components/TestCaseGrid.tsx` — AG-Grid row drag 활성화 + 핸들러
- Test: `backend/test_v103_features.py` — reorder API 테스트

### Feature 5: 인앱 알림
- Create: `backend/models.py` — `Notification` 모델 추가
- Create: `backend/routes/notifications.py` — CRUD 엔드포인트
- Modify: `backend/main.py` — 라우터 등록
- Modify: `backend/routes/testruns.py` — 런 완료/FAIL 시 알림 생성
- Modify: `frontend/src/types/index.ts` — `Notification` 인터페이스
- Modify: `frontend/src/api/index.ts` — `notificationsApi`
- Modify: `frontend/src/components/Header.tsx` — 알림 벨 아이콘 + 드롭다운
- Test: `backend/test_v103_features.py` — 알림 API 테스트

---

## Task 1: TC 복제 (Clone) — 백엔드

**Files:**
- Modify: `backend/routes/testcases.py` (line ~567 근처, restore 엔드포인트 뒤)

- [ ] **Step 1: 백엔드 테스트 작성**

`backend/test_v103_features.py` 파일 생성:

```python
"""v1.0.3.0 신규 기능 테스트"""
import os
import sys
import requests

BASE = os.getenv("TEST_BASE_URL", "http://localhost:8008")
PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL = 0


def login():
    r = requests.post(f"{BASE}/api/auth/login", json={
        "username": "admin",
        "password": os.getenv("TEST_ADMIN_PASSWORD", "test1234")
    })
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

# 테스트 프로젝트 생성
r = requests.post(f"{BASE}/api/projects", json={"name": "v103_test_project"}, headers=H)
PID = r.json()["id"]
print(f"Test project created: id={PID}")

# ============================================================================
print("\n" + "=" * 70)
print("1. TC 복제 (Clone)")
print("=" * 70)

# TC 생성
r = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
    "no": 1, "tc_id": "TC-001", "category": "로그인",
    "priority": "높음", "test_steps": "1단계", "expected_result": "성공",
    "assignee": "tester1", "sheet_name": "기본"
}, headers=H)
check("TC 생성", r.status_code == 201)
TC_ID = r.json()["id"]

# 1-1. 단건 복제
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/{TC_ID}/clone", headers=H)
check("TC 복제 성공", r.status_code == 201, f"status={r.status_code}, body={r.text}")
cloned = r.json()
check("복제 TC tc_id에 -copy 접미사", "-copy" in cloned["tc_id"], cloned.get("tc_id"))
check("복제 TC category 동일", cloned["category"] == "로그인")
check("복제 TC priority 동일", cloned["priority"] == "높음")
check("복제 TC test_steps 동일", cloned["test_steps"] == "1단계")
check("복제 TC id 다름", cloned["id"] != TC_ID)

# 1-2. 벌크 복제
r2 = requests.post(f"{BASE}/api/projects/{PID}/testcases", json={
    "no": 2, "tc_id": "TC-002", "category": "회원가입",
    "priority": "보통", "test_steps": "가입", "expected_result": "완료",
    "sheet_name": "기본"
}, headers=H)
TC_ID2 = r2.json()["id"]

r = requests.post(f"{BASE}/api/projects/{PID}/testcases/bulk-clone",
    json={"ids": [TC_ID, TC_ID2]}, headers=H)
check("벌크 복제 성공", r.status_code == 201, f"status={r.status_code}")
bulk_cloned = r.json()
check("벌크 복제 2건 반환", len(bulk_cloned) == 2, f"len={len(bulk_cloned)}")

# 1-3. 존재하지 않는 TC 복제 시도
r = requests.post(f"{BASE}/api/projects/{PID}/testcases/99999/clone", headers=H)
check("없는 TC 복제 시 404", r.status_code == 404)


# ============================================================================
# 정리
print("\n" + "=" * 70)
r = requests.delete(f"{BASE}/api/projects/{PID}", headers=H)
print(f"\nResult: {PASS_COUNT}/{TOTAL} PASS, {FAIL_COUNT} FAIL")
if FAIL_COUNT > 0:
    sys.exit(1)
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

Run: `cd backend && python test_v103_features.py`
Expected: clone 엔드포인트가 없으므로 FAIL

- [ ] **Step 3: TC 복제 엔드포인트 구현**

`backend/routes/testcases.py`에 restore 엔드포인트(line ~567) 뒤에 추가:

```python
# ── Clone ────────────────────────────────────────────────────────────────────

class BulkCloneRequest(BaseModel):
    ids: List[int]


@router.post("/{tc_id}/clone", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def clone_testcase(
    project_id: int,
    tc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """TC를 복제한다. tc_id에 -copy 접미사를 붙인다."""
    _get_project_or_404(project_id, db)
    original = db.query(TestCase).filter(
        TestCase.id == tc_id,
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    ).first()
    if not original:
        raise HTTPException(status_code=404, detail="Test case not found")

    max_no = db.query(func.max(TestCase.no)).filter(
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    ).scalar() or 0

    clone = TestCase(
        project_id=project_id,
        no=max_no + 1,
        tc_id=f"{original.tc_id}-copy",
        type=original.type,
        category=original.category,
        depth1=original.depth1,
        depth2=original.depth2,
        priority=original.priority,
        test_type=original.test_type,
        precondition=original.precondition,
        test_steps=original.test_steps,
        expected_result=original.expected_result,
        r1=original.r1,
        r2=original.r2,
        r3=original.r3,
        issue_link=original.issue_link,
        assignee=original.assignee,
        remarks=original.remarks,
        sheet_name=original.sheet_name,
        custom_fields=original.custom_fields,
        created_by=current_user.id,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.post("/bulk-clone", response_model=List[TestCaseResponse], status_code=status.HTTP_201_CREATED)
def bulk_clone_testcases(
    project_id: int,
    payload: BulkCloneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """여러 TC를 한 번에 복제한다."""
    _get_project_or_404(project_id, db)

    originals = db.query(TestCase).filter(
        TestCase.id.in_(payload.ids),
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    ).order_by(TestCase.no).all()

    if not originals:
        raise HTTPException(status_code=404, detail="No test cases found")

    max_no = db.query(func.max(TestCase.no)).filter(
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    ).scalar() or 0

    clones = []
    for i, original in enumerate(originals):
        clone = TestCase(
            project_id=project_id,
            no=max_no + 1 + i,
            tc_id=f"{original.tc_id}-copy",
            type=original.type,
            category=original.category,
            depth1=original.depth1,
            depth2=original.depth2,
            priority=original.priority,
            test_type=original.test_type,
            precondition=original.precondition,
            test_steps=original.test_steps,
            expected_result=original.expected_result,
            r1=original.r1,
            r2=original.r2,
            r3=original.r3,
            issue_link=original.issue_link,
            assignee=original.assignee,
            remarks=original.remarks,
            sheet_name=original.sheet_name,
            custom_fields=original.custom_fields,
            created_by=current_user.id,
        )
        db.add(clone)
        clones.append(clone)

    db.commit()
    for c in clones:
        db.refresh(c)
    return clones
```

NOTE: `bulk-clone` 은 `/{tc_id}/clone` 보다 **먼저** 정의되어야 함 (FastAPI가 "bulk-clone"을 tc_id로 파싱하지 않도록). 순서: `bulk-clone` → `/{tc_id}/clone`.

- [ ] **Step 4: 테스트 실행 → PASS 확인**

Run: `cd backend && python test_v103_features.py`
Expected: 모든 TC 복제 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/routes/testcases.py backend/test_v103_features.py
git commit -m "feat: TC 복제(clone) API — 단건 + 벌크"
```

---

## Task 2: TC 복제 — 프론트엔드

**Files:**
- Modify: `frontend/src/api/index.ts` — testCasesApi에 clone/bulkClone 추가
- Modify: `frontend/src/components/TestCaseGrid.tsx` — 복제 버튼 + 핸들러

- [ ] **Step 1: API 함수 추가**

`frontend/src/api/index.ts`의 `testCasesApi` 객체 안에 추가:

```typescript
  clone: async (projectId: number, tcId: number) => {
    const res = await client.post<TestCase>(
      `/api/projects/${projectId}/testcases/${tcId}/clone`
    );
    return res.data;
  },

  bulkClone: async (projectId: number, ids: number[]) => {
    const res = await client.post<TestCase[]>(
      `/api/projects/${projectId}/testcases/bulk-clone`,
      { ids }
    );
    return res.data;
  },
```

- [ ] **Step 2: TestCaseGrid에 복제 핸들러 추가**

`frontend/src/components/TestCaseGrid.tsx`에서 기존 `handleCopySelected` (line ~904)를 수정하여 서버 사이드 복제를 사용하도록 변경:

```typescript
const handleCloneSelected = useCallback(async () => {
  const selected = gridApiRef.current?.getSelectedRows() as TestCase[];
  if (!selected?.length) {
    toast.error("복제할 행을 선택하세요.");
    return;
  }

  // 저장된 TC만 복제 (id > 0)
  const savedIds = selected.filter(r => r.id > 0).map(r => r.id);
  if (savedIds.length === 0) {
    toast.error("저장되지 않은 행은 복제할 수 없습니다.");
    return;
  }

  try {
    const cloned = await testCasesApi.bulkClone(projectId, savedIds);
    setRowData(prev => [...prev, ...cloned]);
    toast.success(`${cloned.length}건 복제 완료`);
    // 마지막 복제 행으로 스크롤
    setTimeout(() => {
      gridApiRef.current?.ensureIndexVisible(rowData.length + cloned.length - 1);
    }, 100);
  } catch {
    toast.error("복제 실패");
  }
}, [projectId, rowData.length]);
```

기존 `handleCopySelected`(클라이언트 사이드 복사)는 그대로 두고, 툴바의 "선택 복사" 버튼이 `handleCloneSelected`를 호출하도록 변경.

- [ ] **Step 3: 툴바 버튼 텍스트 변경**

기존 "선택 복사" 버튼(line ~1276)의 onClick을 `handleCloneSelected`로 교체:

```tsx
<button onClick={handleCloneSelected} disabled={!canEdit || selectedCount === 0}
  style={styles.toolBtn} title="선택한 행을 서버에 복제">
  📋 선택 복제
</button>
```

- [ ] **Step 4: 동작 확인**

브라우저에서 TC 선택 → "선택 복제" 클릭 → 복제된 TC가 하단에 추가되고 tc_id에 `-copy` 접미사 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/api/index.ts frontend/src/components/TestCaseGrid.tsx
git commit -m "feat(frontend): TC 복제 버튼 — 서버사이드 clone API 연동"
```

---

## Task 3: TC별 테스트 결과 히스토리 — 백엔드

**Files:**
- Create: `backend/routes/tc_result_history.py`
- Modify: `backend/main.py` (line ~107, 라우터 등록)

- [ ] **Step 1: 테스트 추가**

`backend/test_v103_features.py`에 TC 결과 히스토리 섹션 추가:

```python
# ============================================================================
print("\n" + "=" * 70)
print("2. TC별 테스트 결과 히스토리")
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
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

Run: `cd backend && python test_v103_features.py`
Expected: result-history 엔드포인트 없으므로 FAIL

- [ ] **Step 3: 라우터 구현**

`backend/routes/tc_result_history.py` 생성:

```python
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User, TestCase, TestRun, TestResult
from auth import check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/testcases",
    tags=["tc-result-history"],
)


@router.get("/{tc_id}/result-history")
def get_tc_result_history(
    project_id: int,
    tc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """특정 TC의 모든 테스트 결과를 런별로 시간순(최신 먼저) 반환."""
    tc = db.query(TestCase).filter(
        TestCase.id == tc_id,
        TestCase.project_id == project_id,
    ).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    results = (
        db.query(TestResult, TestRun)
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .filter(
            TestResult.test_case_id == tc_id,
            TestRun.project_id == project_id,
        )
        .order_by(TestRun.created_at.desc())
        .all()
    )

    return [
        {
            "result_id": result.id,
            "result": result.result.value if hasattr(result.result, "value") else str(result.result),
            "actual_result": result.actual_result,
            "issue_link": result.issue_link,
            "remarks": result.remarks,
            "executed_at": result.executed_at.isoformat() if result.executed_at else None,
            "duration_sec": result.duration_sec,
            "run_id": run.id,
            "run_name": run.name,
            "version": run.version,
            "environment": run.environment,
            "round": run.round,
            "run_status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "run_created_at": run.created_at.isoformat() if run.created_at else None,
        }
        for result, run in results
    ]
```

- [ ] **Step 4: main.py에 라우터 등록**

`backend/main.py`에서 기존 라우터 import 근처에 추가:

```python
from routes import tc_result_history as tc_result_history_routes
```

라우터 등록 부분(line ~107)에 추가:

```python
app.include_router(tc_result_history_routes.router)
```

- [ ] **Step 5: 테스트 실행 → PASS 확인**

Run: `cd backend && python test_v103_features.py`
Expected: TC 결과 히스토리 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/routes/tc_result_history.py backend/main.py backend/test_v103_features.py
git commit -m "feat: TC별 결과 히스토리 API — 런별 결과 타임라인"
```

---

## Task 4: TC별 테스트 결과 히스토리 — 프론트엔드

**Files:**
- Modify: `frontend/src/types/index.ts` — TCResultHistory 타입
- Modify: `frontend/src/api/index.ts` — resultHistory API
- Modify: `frontend/src/components/TestCaseGrid.tsx` — 결과 히스토리 버튼 + 모달

- [ ] **Step 1: 타입 추가**

`frontend/src/types/index.ts` 끝에 추가:

```typescript
// TC Result History
export interface TCResultHistory {
  result_id: number;
  result: string;
  actual_result: string | null;
  issue_link: string | null;
  remarks: string | null;
  executed_at: string | null;
  duration_sec: number | null;
  run_id: number;
  run_name: string;
  version: string | null;
  environment: string | null;
  round: number;
  run_status: string;
  run_created_at: string | null;
}
```

- [ ] **Step 2: API 함수 추가**

`frontend/src/api/index.ts`의 `testCasesApi`에 추가:

```typescript
  resultHistory: async (projectId: number, tcId: number) => {
    const res = await client.get<TCResultHistory[]>(
      `/api/projects/${projectId}/testcases/${tcId}/result-history`
    );
    return res.data;
  },
```

import에 `TCResultHistory` 추가.

- [ ] **Step 3: TestCaseGrid에 결과 히스토리 모달 추가**

`frontend/src/components/TestCaseGrid.tsx`에 state 추가:

```typescript
const [resultHistory, setResultHistory] = useState<TCResultHistory[]>([]);
const [resultHistoryTcId, setResultHistoryTcId] = useState<string>("");
const [resultHistoryOpen, setResultHistoryOpen] = useState(false);
```

핸들러:

```typescript
const handleResultHistory = useCallback(async () => {
  const selected = gridApiRef.current?.getSelectedRows() as TestCase[];
  if (!selected?.length || selected.length !== 1) {
    toast.error("결과 히스토리를 볼 TC를 1건 선택하세요.");
    return;
  }
  const tc = selected[0];
  if (tc.id === 0) {
    toast.error("저장되지 않은 TC입니다.");
    return;
  }
  try {
    const data = await testCasesApi.resultHistory(projectId, tc.id);
    setResultHistory(data);
    setResultHistoryTcId(tc.tc_id);
    setResultHistoryOpen(true);
  } catch {
    toast.error("결과 히스토리 조회 실패");
  }
}, [projectId]);
```

모달 렌더링 (기존 히스토리 모달 패턴과 유사하게):

```tsx
{resultHistoryOpen && (
  <div style={styles.historyOverlay} onClick={() => setResultHistoryOpen(false)}>
    <div style={styles.historyPanel} onClick={e => e.stopPropagation()}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>📊 {resultHistoryTcId} 결과 히스토리</h3>
        <button onClick={() => setResultHistoryOpen(false)} style={styles.toolBtn}>✕</button>
      </div>
      {resultHistory.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", textAlign: "center", padding: 20 }}>수행 이력이 없습니다.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid var(--border-color)" }}>
              <th style={{ padding: "6px 8px", textAlign: "left" }}>런</th>
              <th style={{ padding: "6px 8px", textAlign: "left" }}>버전</th>
              <th style={{ padding: "6px 8px", textAlign: "left" }}>라운드</th>
              <th style={{ padding: "6px 8px", textAlign: "center" }}>결과</th>
              <th style={{ padding: "6px 8px", textAlign: "left" }}>실제 결과</th>
              <th style={{ padding: "6px 8px", textAlign: "left" }}>수행일</th>
            </tr>
          </thead>
          <tbody>
            {resultHistory.map((h, i) => (
              <tr key={h.result_id} style={{
                borderBottom: "1px solid var(--border-color)",
                backgroundColor: i % 2 === 0 ? "var(--bg-secondary)" : "transparent",
              }}>
                <td style={{ padding: "6px 8px" }}>{h.run_name}</td>
                <td style={{ padding: "6px 8px" }}>{h.version || "-"}</td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>R{h.round}</td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>
                  <span style={{
                    padding: "2px 8px", borderRadius: 4, fontWeight: 600, fontSize: 12,
                    backgroundColor:
                      h.result === "PASS" ? "rgba(26,127,55,0.15)" :
                      h.result === "FAIL" ? "rgba(207,34,46,0.15)" :
                      h.result === "BLOCK" ? "rgba(191,135,0,0.15)" : "rgba(128,128,128,0.15)",
                    color:
                      h.result === "PASS" ? "#1a7f37" :
                      h.result === "FAIL" ? "#cf222e" :
                      h.result === "BLOCK" ? "#bf8700" : "#666",
                  }}>{h.result}</span>
                </td>
                <td style={{ padding: "6px 8px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {h.actual_result || "-"}
                </td>
                <td style={{ padding: "6px 8px", fontSize: 12, color: "var(--text-secondary)" }}>
                  {h.run_created_at ? new Date(h.run_created_at).toLocaleDateString("ko-KR") : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  </div>
)}
```

- [ ] **Step 4: 툴바에 버튼 추가**

기존 "변경 이력" 버튼(line ~1325) 옆에 추가:

```tsx
<button onClick={handleResultHistory} disabled={selectedCount !== 1}
  style={styles.toolBtn} title="선택한 TC의 수행 결과 이력">
  📊 결과이력
</button>
```

- [ ] **Step 5: 동작 확인**

TC 1건 선택 → "결과이력" 클릭 → 모달에 런별 PASS/FAIL 히스토리 표시

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/types/index.ts frontend/src/api/index.ts frontend/src/components/TestCaseGrid.tsx
git commit -m "feat(frontend): TC별 결과 히스토리 모달 — 런별 타임라인 조회"
```

---

## Task 5: 대시보드 날짜 필터 — 백엔드

**Files:**
- Modify: `backend/routes/dashboard.py` — 모든 엔드포인트에 date_from/date_to 추가

- [ ] **Step 1: 테스트 추가**

`backend/test_v103_features.py`에 추가:

```python
# ============================================================================
print("\n" + "=" * 70)
print("3. 대시보드 날짜 필터")
print("=" * 70)

# 대시보드 날짜 필터 - 기본 동작 (파라미터 없어도 동작)
r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/summary", headers=H)
check("대시보드 summary 기본 조회", r.status_code == 200)

# 날짜 범위로 조회
r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/summary",
    params={"date_from": "2020-01-01", "date_to": "2099-12-31"}, headers=H)
check("대시보드 summary 날짜 필터 조회", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/priority",
    params={"date_from": "2020-01-01", "date_to": "2099-12-31"}, headers=H)
check("대시보드 priority 날짜 필터", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/category",
    params={"date_from": "2020-01-01"}, headers=H)
check("대시보드 category date_from만", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/assignee",
    params={"date_to": "2099-12-31"}, headers=H)
check("대시보드 assignee date_to만", r.status_code == 200)

r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/heatmap",
    params={"date_from": "2020-01-01", "date_to": "2099-12-31"}, headers=H)
check("대시보드 heatmap 날짜 필터", r.status_code == 200)

# 미래 날짜 → 빈 결과
r = requests.get(f"{BASE}/api/projects/{PID}/dashboard/summary",
    params={"date_from": "2099-01-01"}, headers=H)
check("미래 날짜 필터 시 0건", r.json()["total"] == 0 or r.json()["pass"] == 0)
```

- [ ] **Step 2: 백엔드 구현**

`backend/routes/dashboard.py`에서 `_get_all_results` 헬퍼와 각 엔드포인트에 `date_from`/`date_to` 파라미터 추가.

헬퍼 함수를 수정하여 날짜 필터 지원:

```python
from datetime import datetime

def _get_all_results(project_id: int, db: Session,
                     date_from: str = None, date_to: str = None) -> list:
    """전체(run_id 미지정) 시: TC별 최신 런의 결과만 반환. 날짜 필터 지원."""
    run_filter = [TestRun.project_id == project_id]
    if date_from:
        run_filter.append(TestRun.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        run_filter.append(TestRun.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    latest_run_per_tc = (
        db.query(
            TestResult.test_case_id,
            func.max(TestResult.test_run_id).label("max_run_id"),
        )
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .filter(*run_filter)
        .group_by(TestResult.test_case_id)
        .subquery()
    )

    return (
        db.query(TestResult)
        .join(
            latest_run_per_tc,
            and_(
                TestResult.test_case_id == latest_run_per_tc.c.test_case_id,
                TestResult.test_run_id == latest_run_per_tc.c.max_run_id,
            ),
        )
        .all()
    )
```

각 엔드포인트(`dashboard_summary`, `priority_distribution`, `category_breakdown`, `assignee_summary`, `get_heatmap`)에 파라미터 추가:

```python
date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
```

그리고 `_get_all_results` 호출 시 전달:

```python
all_results = _get_all_results(project_id, db, date_from, date_to)
```

`run_id` 모드에서도 날짜 필터 적용:

```python
if run_id:
    run_q = db.query(TestRun).filter(TestRun.id == run_id)
    if date_from:
        run_q = run_q.filter(TestRun.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        run_q = run_q.filter(TestRun.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
    run = run_q.first()
    if not run:
        # 날짜 범위 밖이면 빈 결과
        return {"total": total, "pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total,
                **_rates({"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total}, total)}
    results = db.query(TestResult).filter(TestResult.test_run_id == run_id).all()
```

`round_comparison`에도 날짜 필터 추가:

```python
@router.get("/rounds")
def round_comparison(
    project_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    run_q = db.query(TestRun).filter(TestRun.project_id == project_id)
    if date_from:
        run_q = run_q.filter(TestRun.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        run_q = run_q.filter(TestRun.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
    runs = run_q.order_by(TestRun.round).all()
    # ... 나머지 기존 로직
```

- [ ] **Step 3: 테스트 실행 → PASS 확인**

Run: `cd backend && python test_v103_features.py`

- [ ] **Step 4: 커밋**

```bash
git add backend/routes/dashboard.py backend/test_v103_features.py
git commit -m "feat: 대시보드 날짜 필터 — date_from/date_to 파라미터"
```

---

## Task 6: 대시보드 날짜 필터 — 프론트엔드

**Files:**
- Modify: `frontend/src/api/index.ts` — dashboardApi에 날짜 파라미터 전달
- Modify: `frontend/src/components/Dashboard.tsx` — 날짜 범위 선택 UI

- [ ] **Step 1: API 함수 수정**

`frontend/src/api/index.ts`의 `dashboardApi` 각 함수에 날짜 파라미터 추가:

```typescript
export const dashboardApi = {
  summary: async (projectId: number, runId?: number | null, dateFrom?: string, dateTo?: string) => {
    const params: Record<string, string | number> = {};
    if (runId) params.run_id = runId;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    const res = await client.get<DashboardSummary>(
      `/api/projects/${projectId}/dashboard/summary`, { params }
    );
    return res.data;
  },
  // priority, category, rounds, assignee, heatmap 모두 동일 패턴
```

모든 dashboardApi 함수(`summary`, `priority`, `category`, `rounds`, `assignee`, `heatmap`)에 `dateFrom?`, `dateTo?` 파라미터 추가.

- [ ] **Step 2: Dashboard 컴포넌트에 날짜 필터 UI 추가**

`frontend/src/components/Dashboard.tsx`에 state 추가:

```typescript
const [dateFrom, setDateFrom] = useState<string>("");
const [dateTo, setDateTo] = useState<string>("");
```

프리셋 버튼 + 커스텀 날짜 입력 UI를 기존 런 선택 드롭다운 옆에 추가:

```tsx
<div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
  {/* 기존 런 선택 드롭다운 */}
  <select ...>...</select>

  {/* 날짜 프리셋 */}
  <div style={{ display: "flex", gap: 4, marginLeft: 12 }}>
    {[
      { label: "전체", from: "", to: "" },
      { label: "7일", from: new Date(Date.now() - 7*86400000).toISOString().split("T")[0], to: "" },
      { label: "30일", from: new Date(Date.now() - 30*86400000).toISOString().split("T")[0], to: "" },
      { label: "90일", from: new Date(Date.now() - 90*86400000).toISOString().split("T")[0], to: "" },
    ].map(p => (
      <button key={p.label} onClick={() => { setDateFrom(p.from); setDateTo(p.to); }}
        style={{
          padding: "4px 10px", fontSize: 12, borderRadius: 4,
          border: "1px solid var(--border-color)",
          backgroundColor: dateFrom === p.from && dateTo === p.to ? "var(--primary-color)" : "var(--bg-secondary)",
          color: dateFrom === p.from && dateTo === p.to ? "#fff" : "var(--text-primary)",
          cursor: "pointer",
        }}>
        {p.label}
      </button>
    ))}
  </div>

  {/* 커스텀 날짜 */}
  <input type="date" value={dateFrom}
    onChange={e => setDateFrom(e.target.value)}
    style={{ padding: "4px 8px", fontSize: 12, border: "1px solid var(--border-color)", borderRadius: 4, backgroundColor: "var(--bg-primary)", color: "var(--text-primary)" }}
  />
  <span style={{ color: "var(--text-secondary)" }}>~</span>
  <input type="date" value={dateTo}
    onChange={e => setDateTo(e.target.value)}
    style={{ padding: "4px 8px", fontSize: 12, border: "1px solid var(--border-color)", borderRadius: 4, backgroundColor: "var(--bg-primary)", color: "var(--text-primary)" }}
  />
</div>
```

- [ ] **Step 3: 데이터 fetch에 날짜 전달**

`useEffect`의 `Promise.all` 호출에서 날짜 전달:

```typescript
useEffect(() => {
  // ... 기존 로딩 로직
  Promise.all([
    dashboardApi.summary(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
    dashboardApi.priority(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
    dashboardApi.category(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
    dashboardApi.rounds(projectId, dateFrom || undefined, dateTo || undefined),
    dashboardApi.assignee(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
    dashboardApi.heatmap(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
    testRunsApi.list(projectId),
  ]).then(/* ... */);
}, [projectId, selectedRunId, dateFrom, dateTo]);
```

dependency array에 `dateFrom`, `dateTo` 추가.

- [ ] **Step 4: 동작 확인**

대시보드 페이지에서 "7일" 버튼 클릭 → 차트/테이블 갱신 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/api/index.ts frontend/src/components/Dashboard.tsx
git commit -m "feat(frontend): 대시보드 날짜 필터 UI — 프리셋 + 커스텀 범위"
```

---

## Task 7: TC 드래그 앤 드롭 정렬 — 백엔드

**Files:**
- Modify: `backend/routes/testcases.py` — PUT `/reorder` 엔드포인트

- [ ] **Step 1: 테스트 추가**

`backend/test_v103_features.py`에 추가:

```python
# ============================================================================
print("\n" + "=" * 70)
print("4. TC 드래그 앤 드롭 정렬")
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
```

- [ ] **Step 2: 엔드포인트 구현**

`backend/routes/testcases.py`에 bulk update 앞에 추가 (bulk-clone과 유사 위치):

```python
class ReorderItem(BaseModel):
    id: int
    no: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


@router.put("/reorder")
def reorder_testcases(
    project_id: int,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """TC 순서(no)를 일괄 변경한다."""
    _get_project_or_404(project_id, db)

    count = 0
    for item in payload.items:
        updated = (
            db.query(TestCase)
            .filter(TestCase.id == item.id, TestCase.project_id == project_id)
            .update({TestCase.no: item.no}, synchronize_session="fetch")
        )
        count += updated

    db.commit()
    return {"updated": count}
```

NOTE: `/reorder` 는 `/bulk` 와 같은 레벨이므로 `/{tc_id}` 앞에 배치해야 함.

- [ ] **Step 3: 테스트 실행 → PASS 확인**

Run: `cd backend && python test_v103_features.py`

- [ ] **Step 4: 커밋**

```bash
git add backend/routes/testcases.py backend/test_v103_features.py
git commit -m "feat: TC 순서 변경 API — PUT /reorder"
```

---

## Task 8: TC 드래그 앤 드롭 정렬 — 프론트엔드

**Files:**
- Modify: `frontend/src/api/index.ts` — testCasesApi.reorder
- Modify: `frontend/src/components/TestCaseGrid.tsx` — AG-Grid row drag 설정

- [ ] **Step 1: API 함수 추가**

`frontend/src/api/index.ts`의 `testCasesApi`에 추가:

```typescript
  reorder: async (projectId: number, items: { id: number; no: number }[]) => {
    const res = await client.put(
      `/api/projects/${projectId}/testcases/reorder`,
      { items }
    );
    return res.data;
  },
```

- [ ] **Step 2: AG-Grid row drag 설정**

`frontend/src/components/TestCaseGrid.tsx`에서:

1. `no` 컬럼에 `rowDrag: true` 추가 (canEdit일 때만):

```typescript
{
  field: "no",
  headerName: "No",
  width: 55,
  rowDrag: canEdit,  // 편집 모드일 때만 드래그 핸들 표시
  // ... 기존 설정
}
```

2. AG-Grid props에 `onRowDragEnd` 핸들러 추가:

```typescript
const handleRowDragEnd = useCallback(async (event: RowDragEndEvent) => {
  const gridApi = gridApiRef.current;
  if (!gridApi) return;

  // 현재 화면 순서대로 no 재할당
  const items: { id: number; no: number }[] = [];
  gridApi.forEachNodeAfterFilterAndSort((node, index) => {
    const data = node.data as TestCase;
    if (data.id > 0) {
      items.push({ id: data.id, no: index + 1 });
    }
    data.no = index + 1;
  });

  // 즉시 UI 갱신
  gridApi.refreshCells({ columns: ["no"] });

  // 서버 저장
  if (items.length > 0) {
    try {
      await testCasesApi.reorder(projectId, items);
    } catch {
      toast.error("순서 저장 실패");
      loadData(); // 롤백
    }
  }
}, [projectId, loadData]);
```

3. `<AgGridReact>` 컴포넌트에 props 추가:

```tsx
<AgGridReact
  // ... 기존 props
  rowDragManaged={true}
  onRowDragEnd={handleRowDragEnd}
  // ...
/>
```

- [ ] **Step 3: 동작 확인**

TC 목록에서 No 컬럼의 드래그 핸들로 행 드래그 → 순서 변경 → 새로고침 후 순서 유지 확인

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/api/index.ts frontend/src/components/TestCaseGrid.tsx
git commit -m "feat(frontend): TC 드래그 앤 드롭 정렬 — AG-Grid row drag"
```

---

## Task 9: 인앱 알림 — 백엔드

**Files:**
- Modify: `backend/models.py` — Notification 모델
- Create: `backend/routes/notifications.py` — CRUD
- Modify: `backend/main.py` — 라우터 등록
- Modify: `backend/routes/testruns.py` — 알림 생성 트리거

- [ ] **Step 1: 테스트 추가**

`backend/test_v103_features.py`에 추가:

```python
# ============================================================================
print("\n" + "=" * 70)
print("5. 인앱 알림")
print("=" * 70)

# 알림 목록 조회 (빈 상태)
r = requests.get(f"{BASE}/api/notifications", headers=H)
check("알림 목록 조회", r.status_code == 200)
initial_count = len(r.json())

# 테스트 런 생성 + 완료 → 알림 자동 생성
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

# 런 완료
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

# 미읽음 개수 조회
r = requests.get(f"{BASE}/api/notifications/unread-count", headers=H)
check("미읽음 개수 조회", r.status_code == 200)
check("미읽음 0건", r.json().get("count") == 0, str(r.json()))
```

- [ ] **Step 2: Notification 모델 추가**

`backend/models.py` 끝에 추가:

```python
# ── Notification ─────────────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String(500), nullable=False)
    link = Column(String(500), nullable=True)  # 클릭 시 이동할 경로
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now_kst)

    user = relationship("User")
```

- [ ] **Step 3: 알림 라우터 구현**

`backend/routes/notifications.py` 생성:

```python
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import User, Notification
from auth import get_current_user

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
)


@router.get("")
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 사용자의 알림 목록 (최신 50건)."""
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(desc(Notification.created_at))
        .limit(50)
        .all()
    )
    return [
        {
            "id": n.id,
            "message": n.message,
            "link": n.link,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)
        .count()
    )
    return {"count": count}


@router.put("/{notification_id}/read")
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).update({Notification.is_read: True})
    db.commit()
    return {"ok": True}


@router.put("/read-all")
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({Notification.is_read: True})
    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: main.py에 라우터 등록 + 마이그레이션**

import 추가:

```python
from routes import notifications as notification_routes
```

라우터 등록:

```python
app.include_router(notification_routes.router)
```

마이그레이션 함수 추가 (lifespan 내):

```python
def _migrate_notifications(engine):
    """notifications 테이블 생성."""
    from models import Notification
    Notification.__table__.create(bind=engine, checkfirst=True)
```

lifespan에서 호출:

```python
_migrate_notifications(engine)
```

- [ ] **Step 5: testruns.py에 알림 트리거 추가**

`backend/routes/testruns.py`의 `complete_testrun` 함수 안, 상태를 `completed`로 변경한 후에 추가:

```python
from models import Notification, ProjectMember

# 알림 생성: FAIL이 있으면 프로젝트 멤버 전원에게 알림
fail_count = db.query(TestResult).filter(
    TestResult.test_run_id == run_id,
    TestResult.result == TestResultValue.FAIL,
).count()

total_count = db.query(TestResult).filter(
    TestResult.test_run_id == run_id,
).count()

pass_count = db.query(TestResult).filter(
    TestResult.test_run_id == run_id,
    TestResult.result == TestResultValue.PASS,
).count()

if fail_count > 0:
    msg = f"🔴 [{run.name}] 완료 — FAIL {fail_count}건 / 전체 {total_count}건"
else:
    msg = f"✅ [{run.name}] 완료 — PASS {pass_count}/{total_count}건"

link = f"/projects/{project_id}?tab=testrun&run={run_id}"

# 프로젝트 멤버 + 생성자에게 알림
member_user_ids = {m.user_id for m in db.query(ProjectMember).filter(
    ProjectMember.project_id == project_id
).all()}
member_user_ids.add(run.created_by)

for uid in member_user_ids:
    db.add(Notification(user_id=uid, message=msg, link=link))
```

- [ ] **Step 6: 테스트 실행 → PASS 확인**

Run: `cd backend && python test_v103_features.py`

- [ ] **Step 7: 커밋**

```bash
git add backend/models.py backend/routes/notifications.py backend/routes/testruns.py backend/main.py backend/test_v103_features.py
git commit -m "feat: 인앱 알림 시스템 — Notification 모델 + 런 완료 트리거"
```

---

## Task 10: 인앱 알림 — 프론트엔드

**Files:**
- Modify: `frontend/src/types/index.ts` — Notification 타입
- Modify: `frontend/src/api/index.ts` — notificationsApi
- Modify: `frontend/src/components/Header.tsx` — 알림 벨 + 드롭다운

- [ ] **Step 1: 타입 추가**

`frontend/src/types/index.ts` 끝에:

```typescript
// Notification
export interface Notification {
  id: number;
  message: string;
  link: string | null;
  is_read: boolean;
  created_at: string | null;
}
```

- [ ] **Step 2: API 함수 추가**

`frontend/src/api/index.ts` 끝에:

```typescript
// ─── Notifications ──────────────────────────────────────
export const notificationsApi = {
  list: async () => {
    const res = await client.get<Notification[]>("/api/notifications");
    return res.data;
  },

  unreadCount: async () => {
    const res = await client.get<{ count: number }>("/api/notifications/unread-count");
    return res.data;
  },

  markAsRead: async (id: number) => {
    await client.put(`/api/notifications/${id}/read`);
  },

  markAllAsRead: async () => {
    await client.put("/api/notifications/read-all");
  },
};
```

import에 `Notification` 추가 (as `NotificationType`로 이름 충돌 방지).

- [ ] **Step 3: Header에 알림 벨 추가**

`frontend/src/components/Header.tsx`에 state 추가:

```typescript
const [notifications, setNotifications] = useState<NotificationType[]>([]);
const [unreadCount, setUnreadCount] = useState(0);
const [notiOpen, setNotiOpen] = useState(false);
```

주기적 polling (30초마다):

```typescript
useEffect(() => {
  const fetchUnread = async () => {
    try {
      const { count } = await notificationsApi.unreadCount();
      setUnreadCount(count);
    } catch { /* ignore */ }
  };
  fetchUnread();
  const interval = setInterval(fetchUnread, 30000);
  return () => clearInterval(interval);
}, []);
```

알림 드롭다운 열기:

```typescript
const handleOpenNotifications = async () => {
  setNotiOpen(!notiOpen);
  if (!notiOpen) {
    try {
      const data = await notificationsApi.list();
      setNotifications(data);
    } catch { /* ignore */ }
  }
};

const handleReadNotification = async (noti: NotificationType) => {
  if (!noti.is_read) {
    await notificationsApi.markAsRead(noti.id);
    setUnreadCount(prev => Math.max(0, prev - 1));
    setNotifications(prev => prev.map(n => n.id === noti.id ? { ...n, is_read: true } : n));
  }
  if (noti.link) {
    navigate(noti.link);
    setNotiOpen(false);
  }
};

const handleReadAll = async () => {
  await notificationsApi.markAllAsRead();
  setUnreadCount(0);
  setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
};
```

벨 아이콘 UI (테마 토글 버튼 왼쪽에 배치):

```tsx
<div style={{ position: "relative" }}>
  <button onClick={handleOpenNotifications}
    style={{ ...styles.iconBtn, position: "relative" }}
    title="알림">
    🔔
    {unreadCount > 0 && (
      <span style={{
        position: "absolute", top: -4, right: -4,
        backgroundColor: "#cf222e", color: "#fff",
        borderRadius: "50%", width: 18, height: 18,
        fontSize: 11, fontWeight: 700,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>{unreadCount > 9 ? "9+" : unreadCount}</span>
    )}
  </button>

  {notiOpen && (
    <div style={{
      position: "absolute", top: "100%", right: 0, marginTop: 8,
      width: 360, maxHeight: 400, overflowY: "auto",
      backgroundColor: "var(--bg-primary)",
      border: "1px solid var(--border-color)",
      borderRadius: 8, boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
      zIndex: 1000,
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "12px 16px", borderBottom: "1px solid var(--border-color)",
      }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>알림</span>
        {unreadCount > 0 && (
          <button onClick={handleReadAll}
            style={{ fontSize: 12, color: "var(--primary-color)", background: "none", border: "none", cursor: "pointer" }}>
            모두 읽음
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
          알림이 없습니다.
        </div>
      ) : (
        notifications.map(noti => (
          <div key={noti.id} onClick={() => handleReadNotification(noti)}
            style={{
              padding: "10px 16px", cursor: "pointer",
              backgroundColor: noti.is_read ? "transparent" : "rgba(59,130,246,0.05)",
              borderBottom: "1px solid var(--border-color)",
            }}>
            <div style={{ fontSize: 13, lineHeight: 1.4 }}>{noti.message}</div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4 }}>
              {noti.created_at ? new Date(noti.created_at).toLocaleString("ko-KR") : ""}
            </div>
          </div>
        ))
      )}
    </div>
  )}
</div>
```

- [ ] **Step 4: 드롭다운 외부 클릭 시 닫기**

```typescript
useEffect(() => {
  if (!notiOpen) return;
  const handleClickOutside = (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (!target.closest("[data-noti-dropdown]")) {
      setNotiOpen(false);
    }
  };
  document.addEventListener("click", handleClickOutside);
  return () => document.removeEventListener("click", handleClickOutside);
}, [notiOpen]);
```

알림 드롭다운 최상위 div에 `data-noti-dropdown` 속성 추가.

- [ ] **Step 5: 동작 확인**

헤더에 🔔 아이콘 표시 → 테스트 런 완료 → 알림 배지 표시 → 클릭하면 목록 → 알림 클릭 시 읽음 처리

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/types/index.ts frontend/src/api/index.ts frontend/src/components/Header.tsx
git commit -m "feat(frontend): 인앱 알림 — 헤더 벨 아이콘 + 드롭다운"
```

---

## Task 11: 통합 테스트 + 최종 커밋

- [ ] **Step 1: 백엔드 전체 테스트 실행**

Run: `cd backend && python test_v103_features.py`
Expected: 전체 PASS

- [ ] **Step 2: 프론트엔드 타입 체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 3: 프론트엔드 기존 테스트**

Run: `cd frontend && npx vitest run`
Expected: 기존 테스트 PASS (새 기능은 기존 테스트에 영향 없음)

- [ ] **Step 4: 최종 정리 커밋**

```bash
git add -A
git commit -m "v1.0.3.0: TC 복제, 결과 히스토리, 대시보드 날짜필터, 드래그정렬, 인앱 알림"
```
