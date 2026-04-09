# Codex 리뷰 지적사항 구조 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codex 코드 리뷰에서 지적된 3가지 구조적 약점(pytest 재현성, 대형 파일 분리, Alembic 마이그레이션)을 수정하여 프로젝트 품질을 "사내 파일럿 상급"에서 "상용 운영 준비" 수준으로 올린다.

**Architecture:** 3개 독립 작업 영역으로 나눈다. (1) 백엔드 pytest가 임시 DB + admin seed로 원커맨드 통과하도록 conftest.py 개선, (2) 프론트엔드 2개 + 백엔드 1개 대형 파일을 커스텀 훅/서비스 모듈로 분리, (3) Alembic 초기 설정 + 기존 수동 마이그레이션을 Alembic revision으로 전환.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, pytest, React 19, TypeScript, ag-grid, Vite

---

## Phase 1: pytest 원커맨드 재현성

### Task 1: conftest.py에 임시 DB + admin seed 추가

**Files:**
- Modify: `backend/conftest.py`
- Modify: `backend/test_security.py:37-55` (setup_tokens fixture)

**현재 문제:** conftest.py는 서버만 띄우고, admin 계정 등록은 CI YAML에서 curl로 수동 수행. 로컬에서 `pytest -q`만 치면 admin 로그인 실패로 전체 테스트 FAIL.

- [ ] **Step 1: conftest.py에 임시 DB 환경변수 + admin seed 추가**

`_server()` fixture 안에서 서버 시작 후 admin 계정을 자동 등록한다. 테스트용 임시 DB를 사용하도록 `DATABASE_URL` 환경변수를 설정한다.

```python
# backend/conftest.py 전체 교체

"""pytest 전역 설정 — 테스트 세션 동안 uvicorn 서버를 자동으로 시작/종료"""
import os
import threading
import time
import tempfile

# 독립 실행 스크립트를 pytest 수집에서 제외
collect_ignore = ["test_v060_full.py", "test_v060_edge_cases.py", "test_v103_features.py", "test_v110_features.py"]

import pytest
import requests
import uvicorn


def _server_already_running(port: int) -> bool:
    """이미 서버가 해당 포트에서 실행 중인지 확인"""
    try:
        r = requests.get(f"http://localhost:{port}/", timeout=2)
        return r.status_code < 500
    except requests.ConnectionError:
        return False


def _wait_for_server(url: str, timeout: float = 15):
    """서버가 응답할 때까지 대기"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"Server did not start within {timeout}s at {url}")


def _seed_admin(base_url: str, password: str):
    """admin 계정이 없으면 등록"""
    r = requests.post(f"{base_url}/api/auth/register", json={
        "username": "admin",
        "password": password,
        "display_name": "Admin",
    })
    # 201 = 새로 생성, 409 = 이미 존재 — 둘 다 OK
    assert r.status_code in (201, 409), f"Admin seed failed: {r.status_code} {r.text}"


@pytest.fixture(scope="session", autouse=True)
def _server(tmp_path_factory):
    """세션 시작 시 uvicorn 서버를 백그라운드 스레드로 실행 (이미 실행 중이면 스킵)"""
    port = int(os.getenv("TEST_PORT", "8008"))
    admin_pw = os.getenv("TEST_ADMIN_PASSWORD", "test1234")
    base_url = f"http://localhost:{port}"

    if _server_already_running(port):
        _seed_admin(base_url, admin_pw)
        yield
        return

    # 임시 DB 사용 — 테스트 간 격리
    tmp_dir = tmp_path_factory.mktemp("test_db")
    test_db = str(tmp_dir / "test_tc_manager.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

    from main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    _wait_for_server(f"{base_url}/docs")

    # admin 계정 시드
    _seed_admin(base_url, admin_pw)

    yield
    server.should_exit = True
    thread.join(timeout=5)
```

- [ ] **Step 2: test_security.py의 setup_tokens에서 admin 등록 로직 제거**

conftest.py가 이미 admin을 등록하므로, test_security.py의 `setup_tokens`에서는 로그인만 한다.

```python
# backend/test_security.py — setup_tokens fixture 수정 (기존 37~55행)
@pytest.fixture(scope="session", autouse=True)
def setup_tokens():
    """세션 시작 시 토큰 준비 (admin은 conftest에서 이미 등록됨)"""
    store.admin = login("admin", os.getenv("TEST_ADMIN_PASSWORD", "test1234"))
    assert store.admin, "Admin login failed - is the server running with admin seeded?"

    # 테스트용 viewer 생성
    r = requests.post(f"{BASE}/api/auth/register", json={
        "username": "__sec_viewer__", "password": "viewer1234", "display_name": "Sec Viewer"
    })
    if r.status_code == 201:
        store.viewer_uid = r.json()["id"]
    else:
        r2 = requests.get(f"{BASE}/api/auth/users", headers=auth(store.admin))
        store.viewer_uid = next(
            (u["id"] for u in r2.json() if u["username"] == "__sec_viewer__"), 0
        )
    store.viewer = login("__sec_viewer__", "viewer1234")
    assert store.viewer, "Viewer login failed"
```

- [ ] **Step 3: 로컬에서 원커맨드 테스트 통과 확인**

Run: `cd backend && python -m pytest test_security.py -q --tb=short`
Expected: 서버 자동 시작 → admin 자동 등록 → 전체 PASS (임시 DB 사용)

- [ ] **Step 4: CI YAML에서 수동 admin 등록 제거**

conftest.py가 자동 처리하므로 CI의 수동 curl 등록을 제거한다.

```yaml
# .github/workflows/ci.yml — backend job의 "Start server and register admin" 단계 수정
      - name: Start server
        working-directory: backend
        run: |
          python -m uvicorn main:app --port 8008 &
          sleep 5
          curl -sf http://localhost:8008/ || exit 1

      - name: pytest (116 tests)
        working-directory: backend
        env:
          TEST_ADMIN_PASSWORD: test1234
        run: python -m pytest test_security.py -q --tb=short -k "not test_dompurify_installed"
        timeout-minutes: 15
```

E2E job도 동일하게 수정:
```yaml
      - name: Start backend
        working-directory: backend
        run: |
          python -m uvicorn main:app --port 8008 &
          sleep 5
          curl -sf http://localhost:8008/ || exit 1
          curl -s -X POST http://localhost:8008/api/auth/register \
            -H "Content-Type: application/json" \
            -d '{"username":"admin","password":"test1234","display_name":"Admin"}'
```
E2E는 playwright가 직접 UI 로그인하므로 admin 등록은 유지해야 함 (conftest 미사용).

- [ ] **Step 5: 커밋**

```bash
git add backend/conftest.py backend/test_security.py .github/workflows/ci.yml
git commit -m "fix: pytest 원커맨드 재현성 — conftest에 임시DB + admin seed 자동화"
```

---

## Phase 2: 대형 파일 분리

### Task 2: backend/routes/testcases.py → sheets + import/export 서비스 분리

**Files:**
- Create: `backend/routes/sheets.py` — 시트 CRUD 엔드포인트
- Create: `backend/services/__init__.py`
- Create: `backend/services/import_service.py` — Excel/CSV/MD 파싱 로직
- Create: `backend/services/export_service.py` — Excel export 로직
- Modify: `backend/routes/testcases.py` — 분리된 코드 제거, import 경로 변경
- Modify: `backend/main.py` — sheets router 등록

**현재 문제:** testcases.py가 1722줄. TC CRUD + Sheet CRUD + Excel/CSV/MD import 파싱 + Excel export가 전부 한 파일에 섞여 있음.

**분리 기준:**
- `routes/sheets.py`: 시트/폴더 CRUD (현재 148~429행, ~280줄) — `_build_sheet_tree`, `_collect_descendant_names`, list/create/rename/move/delete + `_validate_sheet_name`
- `services/import_service.py`: `HEADER_MAP`, `_resolve_merged`, `_detect_header_row`, `_count_tc_rows`, `_parse_sheet`, CSV 매핑/파싱, MD 파싱 (현재 727~1588행, ~860줄)
- `services/export_service.py`: Excel export (현재 1590~1722행, ~130줄)
- `routes/testcases.py`: TC CRUD + clone + reorder만 남김 (~530줄)

- [ ] **Step 1: `backend/services/__init__.py` 생성**

```python
# backend/services/__init__.py
```

- [ ] **Step 2: `backend/services/import_service.py` 생성**

testcases.py에서 `HEADER_MAP` (727행~) 부터 `_preview_csv`, `_parse_md_tables` 등 모든 import 관련 헬퍼 함수를 이동한다. 라우트 핸들러(`import/preview`, `import`)는 testcases.py에 남기되 서비스 함수를 호출하는 형태로 변경.

이동 대상 함수 목록:
- `HEADER_MAP` dict
- `_resolve_merged(ws, row, col)`
- `_detect_header_row(ws, max_scan)`
- `_count_tc_rows(ws, header_row)`
- `_parse_sheet(ws, project_id, user_id, db, no_offset, sheet_name)`
- Jira/Xray/Zephyr CSV 헤더 매핑 상수들
- `_parse_csv(content, project_id, user_id, db, sheet_name)`
- `_load_workbook_from_upload(file_bytes)`
- `_is_csv_file(filename)` / `_is_md_file(filename)`
- `_decode_text(raw_bytes)`
- `_parse_md_row(line)` / `_parse_md_tables(text)` / `_preview_md(text)` / `_parse_md_table(rows, project_id, user_id, db, sheet_name)`
- `_preview_csv(content)`

```python
# backend/services/import_service.py
"""TC 임포트 파싱 로직 — Excel, CSV, Markdown"""
import csv
import io
import logging
from typing import List, Optional

from openpyxl import load_workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import TestCase

logger = logging.getLogger(__name__)

HEADER_MAP = {
    # ... (testcases.py 727~810행의 HEADER_MAP 전체를 그대로 이동)
}

# 이하 모든 _resolve_merged, _detect_header_row, ... 함수를 그대로 이동
# (함수 시그니처 변경 없음, import 경로만 조정)
```

- [ ] **Step 3: `backend/services/export_service.py` 생성**

testcases.py의 `_write_sheet` 내부 함수와 export 로직을 모듈 함수로 추출.

```python
# backend/services/export_service.py
"""TC 엑셀 Export 로직"""
import io
from collections import OrderedDict
from urllib.parse import quote

from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def export_testcases_excel(project, testcases, split_sheets: bool) -> StreamingResponse:
    """프로젝트의 TC를 엑셀 파일로 생성하여 StreamingResponse 반환"""
    # ... (testcases.py 1607~1722행의 로직을 그대로 이동)
```

- [ ] **Step 4: `backend/routes/sheets.py` 생성**

testcases.py에서 시트 관련 엔드포인트를 분리.

```python
# backend/routes/sheets.py
"""시트/폴더 CRUD 라우터"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, Project, TestCase, TestCaseSheet
from auth import get_current_user, check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/sheets",
    tags=["sheets"],
)

# _build_sheet_tree, _collect_descendant_names, _validate_sheet_name 이동
# list_sheets, create_sheet, rename_sheet, move_sheet, delete_sheet 이동
```

주의: 현재 시트 엔드포인트는 `/api/projects/{project_id}/testcases/sheets/...` 경로임. **URL 호환성을 위해 prefix는 기존과 동일하게 유지:**

```python
router = APIRouter(
    prefix="/api/projects/{project_id}/testcases",
    tags=["sheets"],
)
```

- [ ] **Step 5: testcases.py에서 분리된 코드 제거 + import 연결**

```python
# backend/routes/testcases.py 상단에 추가
from services.import_service import (
    HEADER_MAP, _resolve_merged, _detect_header_row, _count_tc_rows,
    _parse_sheet, _parse_csv, _load_workbook_from_upload, _is_csv_file,
    _is_md_file, _decode_text, _preview_md, _parse_md_tables,
    _parse_md_table, _preview_csv,
)
from services.export_service import export_testcases_excel
```

export 라우트 핸들러를 서비스 호출로 교체:
```python
@router.get("/export")
def export_testcases(
    project_id: int,
    split_sheets: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    project = _get_project_or_404(project_id, db)
    testcases = (
        db.query(TestCase)
        .filter(TestCase.project_id == project_id)
        .order_by(TestCase.no)
        .all()
    )
    return export_testcases_excel(project, testcases, split_sheets)
```

- [ ] **Step 6: main.py에 sheets router 등록**

```python
from routes import sheets as sheets_routes
# ...
app.include_router(sheets_routes.router)
```

- [ ] **Step 7: 서버 시작 + 기존 테스트 통과 확인**

Run: `cd backend && python -m uvicorn main:app --port 8008`
Run: `cd backend && python -m pytest test_security.py -q --tb=short`
Expected: 기존 테스트 전부 PASS (URL 경로 변경 없음)

- [ ] **Step 8: 커밋**

```bash
git add backend/services/ backend/routes/sheets.py backend/routes/testcases.py backend/main.py
git commit -m "refactor: testcases.py 분리 — sheets 라우터 + import/export 서비스 추출"
```

### Task 3: TestCaseGrid.tsx 커스텀 훅 추출

**Files:**
- Create: `frontend/src/hooks/useUndoRedo.ts`
- Create: `frontend/src/hooks/useFindReplace.ts`
- Create: `frontend/src/hooks/useSheetManager.ts`
- Create: `frontend/src/components/SheetTreeSidebar.tsx`
- Modify: `frontend/src/components/TestCaseGrid.tsx`

**현재 문제:** TestCaseGrid.tsx 2274줄. undo/redo, find/replace, sheet 관리, sidebar 렌더링이 전부 한 컴포넌트에 있음.

**분리 기준 (탐색 결과 기반):**
- `useUndoRedo.ts`: 107~180행 — undo/redo 스택 상태 + pushUndo/applyUndoRedo/handleUndo/handleRedo
- `useFindReplace.ts`: 181~260행 — 찾기/바꾸기 상태 + 핸들러
- `useSheetManager.ts`: 시트 로딩/CRUD/선택 상태 (305~322행 loadSheets + 798~921행 sheet handlers)
- `SheetTreeSidebar.tsx`: 1089~1327행 — VS Code 스타일 재귀 트리 렌더러

- [ ] **Step 1: `frontend/src/hooks/useUndoRedo.ts` 생성**

```typescript
// frontend/src/hooks/useUndoRedo.ts
import { useCallback, useRef } from "react";
import type { GridApi } from "ag-grid-community";

interface UndoEntry {
  rowId: string;
  field: string;
  oldValue: unknown;
  newValue: unknown;
  dataId: number;
}
type UndoGroup = UndoEntry[];

export function useUndoRedo(gridApiRef: React.RefObject<GridApi | null>) {
  const undoStack = useRef<UndoGroup[]>([]);
  const redoStack = useRef<UndoGroup[]>([]);

  const pushUndo = useCallback((group: UndoGroup) => {
    undoStack.current.push(group);
    redoStack.current = [];
  }, []);

  // applyUndoRedo, handleUndo, handleRedo를 TestCaseGrid.tsx 107~180행에서 그대로 이동
  // gridApiRef.current를 통해 grid에 접근

  return { undoStack, redoStack, pushUndo, handleUndo, handleRedo };
}
```

- [ ] **Step 2: `frontend/src/hooks/useFindReplace.ts` 생성**

```typescript
// frontend/src/hooks/useFindReplace.ts
import { useCallback, useState } from "react";
import type { GridApi } from "ag-grid-community";
import type { TestCase } from "../types";

export function useFindReplace(
  gridApiRef: React.RefObject<GridApi | null>,
  rowData: TestCase[],
  setRowData: React.Dispatch<React.SetStateAction<TestCase[]>>,
) {
  const [findOpen, setFindOpen] = useState(false);
  const [findText, setFindText] = useState("");
  const [replaceText, setReplaceText] = useState("");
  const [findField, setFindField] = useState("all");
  const [matchCase, setMatchCase] = useState(false);

  // TestCaseGrid.tsx 181~260행의 find/replace 핸들러를 이동

  return {
    findOpen, setFindOpen,
    findText, setFindText,
    replaceText, setReplaceText,
    findField, setFindField,
    matchCase, setMatchCase,
    handleFindNext, handleReplaceOne, handleReplaceAll,
  };
}
```

- [ ] **Step 3: `frontend/src/hooks/useSheetManager.ts` 생성**

```typescript
// frontend/src/hooks/useSheetManager.ts
import { useCallback, useState } from "react";
import { testCasesApi } from "../api";
import type { SheetNode } from "../types";

export function useSheetManager(projectId: number) {
  const [sheets, setSheets] = useState<SheetNode[]>([]);
  const [activeSheet, setActiveSheet] = useState<string>("기본");
  const [expandedFolders, setExpandedFolders] = useState<Set<number>>(new Set());

  const loadSheets = useCallback(async () => {
    // TestCaseGrid.tsx 305~322행 이동
  }, [projectId]);

  // createSheet, renameSheet, moveSheet, deleteSheet, toggleFolder 등
  // TestCaseGrid.tsx 798~921행 이동

  return {
    sheets, activeSheet, setActiveSheet,
    expandedFolders, setExpandedFolders,
    loadSheets, createSheet, renameSheet, moveSheet, deleteSheet, toggleFolder,
  };
}
```

- [ ] **Step 4: `frontend/src/components/SheetTreeSidebar.tsx` 생성**

```typescript
// frontend/src/components/SheetTreeSidebar.tsx
import type { SheetNode } from "../types";

interface Props {
  sheets: SheetNode[];
  activeSheet: string;
  expandedFolders: Set<number>;
  canEdit: boolean;
  onSelect: (name: string) => void;
  onToggleFolder: (id: number) => void;
  onRename: (id: number, newName: string) => void;
  onMove: (id: number, parentId: number | null) => void;
  onDelete: (id: number) => void;
  onCreate: (name: string, parentId?: number, isFolder?: boolean) => void;
}

// TestCaseGrid.tsx 1089~1327행의 renderSheetTree 로직을 컴포넌트로 변환
export default function SheetTreeSidebar({ sheets, activeSheet, ... }: Props) {
  // ...
}
```

- [ ] **Step 5: TestCaseGrid.tsx에서 훅/컴포넌트 import로 교체**

```typescript
// frontend/src/components/TestCaseGrid.tsx 상단
import { useUndoRedo } from "../hooks/useUndoRedo";
import { useFindReplace } from "../hooks/useFindReplace";
import { useSheetManager } from "../hooks/useSheetManager";
import SheetTreeSidebar from "./SheetTreeSidebar";
```

컴포넌트 내부에서 인라인 로직을 훅 호출로 교체:
```typescript
const { undoStack, redoStack, pushUndo, handleUndo, handleRedo } = useUndoRedo(gridApiRef);
const { findOpen, setFindOpen, ... } = useFindReplace(gridApiRef, rowData, setRowData);
const { sheets, activeSheet, setActiveSheet, loadSheets, ... } = useSheetManager(projectId);
```

JSX에서 `renderSheetTree()` 호출을 `<SheetTreeSidebar ... />` 컴포넌트로 교체.

- [ ] **Step 6: TypeScript 타입 체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 0개

- [ ] **Step 7: 기존 프론트 테스트 통과 확인**

Run: `cd frontend && npx vitest run`
Expected: 358 tests PASS

- [ ] **Step 8: 커밋**

```bash
git add frontend/src/hooks/ frontend/src/components/SheetTreeSidebar.tsx frontend/src/components/TestCaseGrid.tsx
git commit -m "refactor: TestCaseGrid 훅 추출 — useUndoRedo, useFindReplace, useSheetManager, SheetTreeSidebar"
```

### Task 4: TestRunManager.tsx 커스텀 훅 추출

**Files:**
- Create: `frontend/src/hooks/useTestTimer.ts`
- Create: `frontend/src/hooks/useAttachments.ts`
- Create: `frontend/src/hooks/useResultFilters.ts`
- Modify: `frontend/src/components/TestRunManager.tsx`

**현재 문제:** TestRunManager.tsx 1775줄. 타이머, 첨부파일, 필터가 한 컴포넌트에 있음.

- [ ] **Step 1: `frontend/src/hooks/useTestTimer.ts` 생성**

```typescript
// frontend/src/hooks/useTestTimer.ts
import { useCallback, useRef, useState } from "react";

export function useTestTimer() {
  const [timerRunning, setTimerRunning] = useState(false);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [timerTcId, setTimerTcId] = useState<number | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // TestRunManager.tsx 297~370행의 startTimer/stopTimer/onRowFocused 이동

  return {
    timerRunning, timerSeconds, timerTcId,
    startTimer, stopTimer, resetTimer,
  };
}
```

- [ ] **Step 2: `frontend/src/hooks/useAttachments.ts` 생성**

```typescript
// frontend/src/hooks/useAttachments.ts
import { useCallback, useState } from "react";
import { attachmentsApi } from "../api";
import type { Attachment } from "../types";

export function useAttachments() {
  const [attachmentMap, setAttachmentMap] = useState<Record<number, Attachment[]>>({});

  // TestRunManager.tsx 97~161행의 loadAttachmentFor/handleFileUpload/handleDeleteAttachment 이동

  return {
    attachmentMap,
    loadAttachmentFor, handleFileUpload, handleDeleteAttachment,
  };
}
```

- [ ] **Step 3: `frontend/src/hooks/useResultFilters.ts` 생성**

```typescript
// frontend/src/hooks/useResultFilters.ts
import { useCallback, useState } from "react";
import type { GridApi } from "ag-grid-community";

export function useResultFilters(gridApiRef: React.RefObject<GridApi | null>) {
  const [filterResult, setFilterResult] = useState("");
  const [filterAssignee, setFilterAssignee] = useState("");
  const [filterText, setFilterText] = useState("");

  // TestRunManager.tsx 507~569행의 isExternalFilterPresent/doesExternalFilterPass 이동

  return {
    filterResult, setFilterResult,
    filterAssignee, setFilterAssignee,
    filterText, setFilterText,
    isExternalFilterPresent, doesExternalFilterPass,
  };
}
```

- [ ] **Step 4: TestRunManager.tsx에서 훅 import로 교체**

```typescript
import { useTestTimer } from "../hooks/useTestTimer";
import { useAttachments } from "../hooks/useAttachments";
import { useResultFilters } from "../hooks/useResultFilters";

// 컴포넌트 내부
const { timerRunning, timerSeconds, ... } = useTestTimer();
const { attachmentMap, loadAttachmentFor, ... } = useAttachments();
const { filterResult, setFilterResult, ... } = useResultFilters(gridApiRef);
```

- [ ] **Step 5: TypeScript 타입 체크 + 테스트**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: 타입 에러 0개, 358 tests PASS

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/hooks/useTestTimer.ts frontend/src/hooks/useAttachments.ts frontend/src/hooks/useResultFilters.ts frontend/src/components/TestRunManager.tsx
git commit -m "refactor: TestRunManager 훅 추출 — useTestTimer, useAttachments, useResultFilters"
```

---

## Phase 3: Alembic 마이그레이션 도입

### Task 5: Alembic 초기 설정 + 기존 스키마를 initial revision으로 기록

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial_schema.py`
- Modify: `backend/main.py` — 수동 마이그레이션 함수 제거, Alembic 자동 실행으로 교체

**현재 문제:** main.py lifespan에서 `create_all` + 5개 수동 `ALTER TABLE`을 try/except로 실행. 에러를 삼키므로 실패해도 모름.

- [ ] **Step 1: Alembic 초기화**

```bash
cd backend && python -m alembic init alembic
```

- [ ] **Step 2: alembic.ini 수정 — SQLite URL 설정**

```ini
# backend/alembic.ini 핵심 설정
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///./tc_manager.db
```

- [ ] **Step 3: alembic/env.py 수정 — 모델 메타데이터 연결**

```python
# backend/alembic/env.py
import os
import sys

# backend 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Base
import models  # noqa: F401 — 모델 등록용

target_metadata = Base.metadata

# DATABASE_URL 환경변수 우선
def get_url():
    return os.getenv("DATABASE_URL", "sqlite:///./tc_manager.db")

# run_migrations_offline / run_migrations_online에서 get_url() 사용
```

- [ ] **Step 4: initial migration 생성**

현재 스키마 전체를 initial revision으로 기록. `--autogenerate`는 빈 DB 기준으로 생성.

```bash
cd backend && python -m alembic revision --autogenerate -m "initial schema"
```

생성된 파일에서 모든 테이블 + 인덱스가 포함되어 있는지 확인.

- [ ] **Step 5: 기존 DB에 alembic_version 스탬프**

이미 스키마가 존재하는 DB에 "이 revision까지 적용됨"을 마킹:

```bash
cd backend && python -m alembic stamp head
```

- [ ] **Step 6: main.py에서 수동 마이그레이션 제거 + Alembic upgrade 실행**

```python
# backend/main.py — lifespan 수정
from alembic.config import Config
from alembic import command

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic 자동 마이그레이션
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", "sqlite:///./tc_manager.db"))
    command.upgrade(alembic_cfg, "head")

    _purge_old_deleted_testcases()
    yield
```

제거 대상 함수:
- `_migrate_roles()` — 한번 실행되면 더 이상 필요 없음 (이미 적용된 DB)
- `_migrate_sheet_parent_id()` — Alembic initial에 포함
- `_migrate_field_config()` — Alembic initial에 포함
- `_migrate_indexes()` — Alembic initial에 포함

`_purge_old_deleted_testcases()`는 마이그레이션이 아닌 일일 정리 작업이므로 유지.

- [ ] **Step 7: 신규 DB에서 Alembic upgrade 동작 확인**

```bash
cd backend
rm -f test_alembic.db
DATABASE_URL=sqlite:///./test_alembic.db python -m alembic upgrade head
# 모든 테이블 + 인덱스 생성 확인
DATABASE_URL=sqlite:///./test_alembic.db python -c "
from sqlalchemy import create_engine, inspect
e = create_engine('sqlite:///./test_alembic.db')
ins = inspect(e)
tables = ins.get_table_names()
print(f'Tables: {len(tables)}')
for t in sorted(tables):
    cols = [c[\"name\"] for c in ins.get_columns(t)]
    print(f'  {t}: {cols}')
"
rm -f test_alembic.db
```

Expected: 11개 테이블 + alembic_version 테이블

- [ ] **Step 8: 기존 pytest 통과 확인**

Run: `cd backend && python -m pytest test_security.py -q --tb=short`
Expected: 전체 PASS

- [ ] **Step 9: 커밋**

```bash
git add backend/alembic.ini backend/alembic/ backend/main.py
git commit -m "feat: Alembic 마이그레이션 도입 — 수동 ALTER TABLE 제거, initial schema revision"
```

---

## Phase 4: 최종 검증

### Task 6: 전체 통합 테스트 + 줄 수 확인

- [ ] **Step 1: 백엔드 테스트 원커맨드 확인**

Run: `cd backend && python -m pytest test_security.py -q --tb=short`
Expected: 전체 PASS, 임시 DB 사용, admin 자동 시드

- [ ] **Step 2: 프론트엔드 타입 + 린트 + 테스트**

Run: `cd frontend && npx tsc --noEmit && npx eslint src/ --quiet && npx vitest run`
Expected: 에러 0개, 358 tests PASS

- [ ] **Step 3: 분리 결과 줄 수 확인**

```bash
wc -l backend/routes/testcases.py backend/routes/sheets.py backend/services/import_service.py backend/services/export_service.py
wc -l frontend/src/components/TestCaseGrid.tsx frontend/src/components/TestRunManager.tsx
wc -l frontend/src/hooks/*.ts frontend/src/components/SheetTreeSidebar.tsx
```

Expected 목표:
| 파일 | Before | After (목표) |
|------|--------|-------------|
| testcases.py | 1722줄 | ~530줄 |
| TestCaseGrid.tsx | 2274줄 | ~1200줄 |
| TestRunManager.tsx | 1775줄 | ~1100줄 |

- [ ] **Step 4: 서버 시작 + 수동 스모크 테스트**

Run: `cd backend && python -m uvicorn main:app --port 8008`
확인 항목:
- 서버 정상 시작 (Alembic upgrade 로그)
- TC CRUD 동작
- 시트 CRUD 동작
- Excel import/export 동작

- [ ] **Step 5: 최종 커밋**

```bash
git add -A
git commit -m "chore: Codex 리뷰 지적사항 구조 개선 완료 — pytest 재현성 + 파일 분리 + Alembic"
```
