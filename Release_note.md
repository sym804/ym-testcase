# YM TestCase Release Notes

## 버전 체계

### 형식: `system.feature.major.minor`

| 자리 | 의미 | 변경 기준 |
|---|---|---|
| **system** | 시스템 구조 변경 | 대규모 리팩토링, 아키텍처 변경, 하위 호환 불가 |
| **feature** | 기능 변경 | 신규 기능 추가, 기존 기능 대규모 수정 |
| **major** | 중요 버그 수정 | 빌드 실패, 데이터 정합성, 보안 취약점 등 |
| **minor** | 사소한 버그 수정 | UI 텍스트, 스타일, 미미한 동작 수정 |

### 컴포넌트별 버전 관리

YM TestCase는 3개 컴포넌트로 구성되며, 각각 독립적으로 버전을 관리합니다.

| 컴포넌트 | 설명 | 버전 변경 시점 |
|---|---|---|
| **Frontend** | React + TypeScript + Vite | UI/UX 변경, 페이지 추가, 컴포넌트 수정 |
| **Backend** | FastAPI + SQLAlchemy | API 변경, 비즈니스 로직, 보안 수정 |
| **Database** | SQLite (SQLAlchemy 모델) | 테이블/컬럼 추가·변경·삭제, 마이그레이션 |

**System Version**은 전체 릴리즈 단위의 태그 역할이며, 컴포넌트 중 하나라도 변경되면 함께 올립니다.

### 버전 변경 규칙

| 변경 대상 | 올리는 버전 |
|---|---|
| Frontend만 수정 | Frontend + System |
| Backend만 수정 | Backend + System |
| DB 스키마 변경 | Database + Backend + System |
| 전체 변경 | Frontend + Backend + Database(해당 시) + System |

---

## 현재 버전

```
YM TestCase System  v0.7.1.0  (2026-03-23)
├── Frontend       v0.7.1.0
├── Backend        v0.7.1.0
└── Database       v0.3.0.0
```

---

## v0.7.1.0 (2026-03-23) — 품질 게이트 수정 + 라이선스 변경 + README 정비

> 빌드/린트/테스트 전체 통과 + AGPL-3.0 전환 + README 정확성 개선 + 전체 테스트 567건 PASS

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.7.0.0 | **0.7.1.0** | 품질 게이트 수정, 라이선스 변경 |
| Frontend | 0.7.0.0 | **0.7.1.0** | 빌드 타입 오류 수정, lint 정리, 대시보드 차트 색상 수정, E2E 셀렉터 수정 |
| Backend | 0.7.0.0 | **0.7.1.0** | pytest 수집 오류 해결, 마이그레이션 로깅 추가, .env.example 생성 |
| Database | 0.3.0.0 | 0.3.0.0 | 변경 없음 |

### 버그 수정

- **BUG-056**: 프론트 빌드 실패 — 테스트 파일 타입 오류 9개 수정 (잘못된 필드명, 누락 프로퍼티, 미사용 import)
- **BUG-057**: vite.config.ts writeHead 타입 오류 수정
- **BUG-058**: 대시보드 차트 색상 전부 검은색 — Chart.js가 CSS 변수 미지원, 라이트/다크 hex 값으로 분리
- **BUG-059**: ESLint가 coverage/e2e 디렉토리까지 검사 — globalIgnores 추가
- **BUG-060**: 소스 파일 lint 에러 7개 (빈 블록, 삼항식을 표현식으로 사용)
- **BUG-061**: backend pytest 수집 단계 실패 — 독립 스크립트(test_v060_*.py)가 모듈 레벨에서 login() 호출, collect_ignore 추가
- **BUG-062**: 마이그레이션 예외를 삼키고 로그 없음 — logger.warning/debug 추가
- **BUG-063**: E2E 시트 트리 테스트 2개 실패 — 셀렉터 `루트 시트 추가` → `시트 추가` 수정

### 개선

- **ENH-014**: 라이선스 MIT → AGPL-3.0 변경 (웹앱 SaaS 무임승차 방어)
- **ENH-015**: README 섹션명 개선 (왜 이 도구인가 → 기존 도구와의 비교, 빠른 시작 → 환경설정 방법)
- **ENH-016**: README 비교 테이블 HTML 전환 (YM TestCase 열 파란색)
- **ENH-017**: README SECRET_KEY 설명 보강 (용도, 미설정 시 영향)
- **ENH-018**: README 사전 요구사항 추가 (Python 3.12+, Node.js 18+, Git)
- **ENH-019**: README에서 존재하지 않는 Docker 관련 내용 제거
- **ENH-020**: backend/.env.example 생성
- **ENH-021**: .gitignore에 coverage 추가
- **ENH-022**: 테스트 파일에 any/react-refresh lint 룰 완화

### 문서

- 대시보드 스크린샷 5장 재촬영 (라이트 + 다크모드)
- README 디렉토리 구조 정확성 수정

### 테스트

- Frontend (Vitest): 358/358 PASS
- E2E (Playwright): 93/93 PASS
- Backend (pytest): 116/116 PASS
- 합계: **567/567 ALL PASS**

---

## v0.7.0.0 (2026-03-21) — Git 관리 + GitHub 공개 + 브랜딩

> 브랜딩 변경 (TC Manager → YM TestCase) + Git 공개 준비 + 테스트 293건 PASS

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.6.0.0 | **0.7.0.0** | Git 공개 준비, 브랜딩 통합 |
| Frontend | 0.6.0.0 | **0.7.0.0** | YM TestCase 브랜딩, children 방어 코드, 테스트 수정 |
| Backend | 0.6.0.0 | **0.7.0.0** | API 타이틀 변경, 크레덴셜 환경변수화 |
| Database | 0.3.0.0 | 0.3.0.0 | 변경 없음 |

### 변경 내역

- **브랜딩**: TC Manager → YM TestCase (Your Method, Your Test Case Manager)
- **.gitignore**: DB, 캐시, 개인 파일 제외
- **.env.example**: 환경변수 문서화
- **크레덴셜 제거**: 하드코딩 비밀번호 → 환경변수 전환
- **Docker Compose**: 포트 매핑 수정 (8008:8000)
- **README.md**: 설치 가이드 + 스크린샷 7장
- **MIT LICENSE** 추가
- **run_dev.sh**: Mac/Linux 지원
- **테스트 수정**: 트리 구조 변경 반영 (children 방어, 셀렉터 수정)

### 테스트

- Frontend (Vitest): 177/177 PASS
- Backend (pytest): 116/116 PASS
- 합계: **293/293 ALL PASS**

---

## v0.6.0.0 (2026-03-20) — 시트 트리, 커스텀 필드, 테스트 플랜, Jira CSV, 고급 필터

> TC 관리 본질 기능 5개 구현 + 326건 PASS

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.5.0.0 | **0.6.0.0** | 5대 기능 추가 |
| Frontend | 0.5.0.0 | **0.6.0.0** | 시트 트리 사이드바, 커스텀 필드 UI, 필터 패널, 테스트 플랜 |
| Backend | 0.5.0.0 | **0.6.0.0** | 시트 트리 API, 커스텀 필드, 테스트 플랜, CSV Import, 필터 API |
| Database | 0.3.0.0 | 0.3.0.0 | parent_id, custom_fields, test_plan_id 컬럼 추가 (마이그레이션) |

### 주요 기능

1. **시트 트리 구조** — N-depth 계층, VS Code 사이드바 UI
2. **커스텀 필드** — 6타입 (text, number, select, multiselect, checkbox, date)
3. **테스트 플랜/마일스톤** — 릴리즈 단위 수행 관리
4. **Jira CSV Import** — 35+ 헤더 매핑, CP949/UTF-8 BOM 자동 감지
5. **고급 필터 + 저장된 뷰** — AND/OR 다중 조건, 6개 연산자

### 테스트

- Python API: 139/139 PASS
- 엣지케이스: 116/116 PASS
- Playwright E2E: 71/71 PASS
- 합계: **326/326 ALL PASS**

---

## v0.5.0.0 (2026-03-19) — 시트 관리, 자동저장, 테스트 자동화 312건

> 신규 기능 5개 + DB 스키마 변경 + 테스트 0개 → 312개 구축

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.4.1.0 | **0.5.0.0** | 대규모 신규 기능 + 테스트 자동화 |
| Frontend | 0.4.1.0 | **0.5.0.0** | 시트 UI, 자동저장, 벌크 삭제, 임포트 개선, 매뉴얼 업데이트 |
| Backend | 0.4.1.0 | **0.5.0.0** | 시트 CRUD API, 벌크 삭제 API, 임포트 덮어쓰기, deleted_at 필터 |
| Database | 0.2.0.0 | **0.3.0.0** | test_case_sheets 테이블 신설, test_cases.sheet_name 컬럼 추가 |

### 신규 기능

**1. 시트 관리**
- 프로젝트 내 TC를 시트 단위로 분류 (엑셀 시트 탭과 동일)
- 빈 프로젝트에서 "시트 추가" 또는 "Excel Import"로 시작
- 하단 탭 바: 시트 전환, 전체 보기 (2개+ 시트), + 버튼으로 새 시트 추가
- 시트 삭제 (× 버튼, TC 소프트 삭제)
- 시트별 No 1부터 시작, 전체 보기에서 시트 순서대로 연속 번호
- "기본" 시트 1개뿐이면 탭 바 숨김
- TC 관리 + 테스트 수행 양쪽에 시트 탭 적용

**2. 자동저장 (Google Sheets 방식)**
- 저장 버튼 제거, modifiedIds 상태 제거
- 셀 편집 → 디바운스 300ms → API 자동 호출
- 행 추가 → 즉시 API 생성
- Undo/Redo, 찾기/바꾸기, 일괄 변경, Ctrl+D, TC ID 자동채우기 모두 자동저장 연동

**3. Excel Import 개선**
- 멀티시트 임포트: 시트 선택 모달 (체크박스)
- 동일 TC ID 덮어쓰기 (upsert): 기존 TC 보존, 변경분만 업데이트
- 중복 시 사전 알림: "기존 N개 덮어쓰기" 팝업
- 섹션 헤더 행 자동 필터링 (머지 셀 감지)
- 시트 레코드 자동 생성 (import 시 TestCaseSheet 테이블에 등록)
- Import Preview API: 시트 목록 + TC 수 + 기존 중복 수 반환
- HEADER_MAP 한국어 확장: 사전조건/테스트 가이드, 심각도, 버그/이슈, 결과, 자동화

**4. 벌크 삭제**
- TC 벌크 삭제 API: `DELETE /testcases/bulk?ids=1,2,3` (237개 280ms)
- 프로젝트 목록 일괄 삭제: 테이블 체크박스 + 전체 선택 + "N개 삭제" 버튼

**5. 테스트 자동화 (0 → 312개)**
- Vitest 177개: 21개 파일 (컴포넌트 단위 + API 함수 + 시트 탭 + 자동저장)
- Playwright E2E 19개: 4개 파일 (인증, 프로젝트, TC 관리, 관리자)
- pytest 116개: 백엔드 통합 테스트 (기존 70 + 신규 46)
- 자동화 커버율: 65% (237개 체크리스트 중 155개)

### Backend 변경사항

**신규 API (7개)**
- `GET /api/projects/{id}/testcases/sheets` — 시트 목록 (TC 수 포함)
- `POST /api/projects/{id}/testcases/sheets` — 시트 생성
- `DELETE /api/projects/{id}/testcases/sheets/{name}` — 시트 삭제
- `POST /api/projects/{id}/testcases/import/preview` — Import 미리보기
- `DELETE /api/projects/{id}/testcases/bulk` — TC 벌크 삭제
- Import API 개선: `sheet_names` 파라미터, upsert 로직

**버그 수정 (4건)**
- `overview.py` — deleted_at 필터 누락 → TC 카운트 부풀림
- `dashboard.py` — deleted_at 필터 누락 → 라운드 비교 부정확
- `testruns.py` — deleted_at 필터 누락 → 삭제된 TC가 TestResult에 포함
- `schemas.py` — ProjectCreate에 `name: min_length=1` 추가 (빈 이름 방어)

**코드 리팩토링**
- `_parse_sheet()` 함수 분리 (임포트 로직 재사용)
- `_detect_header_row()`, `_count_tc_rows()` 유틸 함수 분리
- 섹션 헤더 감지: depth3 병합 전 unique_vals 검사

### Frontend 변경사항

**TC 관리 (TestCaseGrid.tsx)**
- 시트 탭 바 (하단), 시트 추가/삭제 UI
- 빈 프로젝트 시트 추가 화면
- 자동저장: autoSaveRow (디바운스 300ms), autoSaveRowRef (TDZ 버그 수정)
- 행 추가 즉시 API 호출, 저장 버튼 제거
- ag-grid rowSelection v35 API 전환 (multiRow + checkboxes + headerCheckbox)
- Import: 시트 선택 모달, 중복 경고, 시트 자동 전환

**테스트 수행 (TestRunManager.tsx)**
- 시트 탭 바 (우측 패널 하단)
- 시트별 결과 필터링
- 전체 보기 시 시트 순서대로 연속 번호
- 첨부파일 lazy load (행 포커스 시만 로드, 기존: 전체 동시 API 호출)

**프로젝트 목록 (ProjectListPage.tsx)**
- 테이블 행 체크박스 + 전체 선택 + 일괄 삭제 버튼

**매뉴얼 (UserManualPage.tsx)**
- 6-2. 시트 관리 섹션 신규
- 3-4. 프로젝트 일괄 삭제 섹션 추가
- 자동저장 안내로 변경 (저장 버튼 설명 제거)
- Excel Import 설명 업데이트
- 상단 바/테이블 헤더 색상 수정 (라이트 모드 가시성)

**운영 매뉴얼 (AdminManualPage.tsx)**
- API 엔드포인트 6개 추가

**대시보드 (Dashboard.tsx)**
- 카드/차트/테이블에 border 추가 (라이트 모드 가시성)
- 도넛 차트 borderColor: transparent 추가

### Database 변경사항

**신규 테이블**
- `test_case_sheets`: 프로젝트별 시트 관리
  - `id`, `project_id`, `name`, `sort_order`, `created_at`

**컬럼 추가**
- `test_cases.sheet_name`: VARCHAR(100), DEFAULT '기본', NOT NULL

### 변경 파일 목록

**Backend (10개)**
- `models.py`, `schemas.py`
- `routes/testcases.py`, `routes/overview.py`, `routes/dashboard.py`, `routes/testruns.py`
- `test_security.py`

**Frontend (15개)**
- `api/index.ts`, `types/index.ts`
- `components/TestCaseGrid.tsx`, `components/TestRunManager.tsx`, `components/Dashboard.tsx`
- `pages/ProjectListPage.tsx`, `pages/UserManualPage.tsx`, `pages/AdminManualPage.tsx`
- `vite.config.ts`, `package.json`, `playwright.config.ts`
- `src/test/` (21개 파일), `e2e/` (4개 파일)

---

## v0.4.1.0 (2026-03-18) — 전수 검증 27건 수정 (보안+안정성)

> Backend 14건 + Frontend 13건 버그/보안 수정

### Backend (14건)

**심각 (3건)**
- `routes/history.py` — 이력 조회 프로젝트 멤버 권한 체크 추가
- `routes/attachments.py` — ROLE_HIERARCHY에서 모델에 없는 "editor" 제거
- `auth.py` — user_id 파싱 ValueError/TypeError 예외 처리 추가 (500→401)

**높음 (4건)**
- `routes/dashboard.py` — not_started를 실제 "NS" 결과 건수로 카운트 (기존: total에서 빼기)
- `routes/testruns.py` — 엑셀 열 26개 초과 시 get_column_letter() 사용
- `routes/search.py` — 프라이빗 프로젝트 검색 필터 추가 (is_private + 멤버 체크)
- `routes/reports.py` — PDF 한글 폰트 탐색 경로에 NanumGothic 추가 + 미발견 시 경고 로그

**중간 (4건)**
- `routes/members.py` — joinedload()로 N+1 쿼리 해소
- `routes/dashboard.py` — 미사용 매개변수 total_tc 제거
- `routes/dashboard.py` — 메모리 로드 최적화 TODO 주석
- `routes/auth.py` — 레이트리밋 O(n) 탐색 TODO 주석

**낮음 (3건)**
- `routes/search.py` — limit 매개변수화 (기본 100, 최대 500)
- `routes/testcases.py` — depth3 병합 로직 의도 주석

### Frontend (13건)

**심각 (2건)**
- `MarkdownCell.tsx` — DOMPurify 이미 적용 확인 (수정 불필요)
- `api/client.ts` — localStorage JWT + CSRF 미적용 TODO 주석 추가

**높음 (5건)**
- 5개 컴포넌트 catch 블록에 에러 로깅 추가 (TestCaseGrid 8곳, Dashboard 1곳, ReportView 3곳, CompareView 1곳, AdminPage 7곳, ProjectListPage 2곳)
- `Header.tsx` — searchTimer useEffect cleanup 추가
- `Header.tsx` — catch ignore → console.warn 변경

**중간 (4건)**
- `TestCaseGrid.tsx` — 경쟁 조건 TODO 주석
- `ProjectListPage.tsx` — 프로젝트 이름 100자 제한
- `TestCaseGrid.tsx` — 낙관적 업데이트 TODO 주석
- `ProjectListPage.tsx` — Date 파싱 실패 방어 (isNaN 체크)

**낮음 (2건)**
- 전체 console.error 로깅 (위에서 함께 처리)
- 접근성 TODO 주석

---

## v0.4.0.0 (2026-03-16) — 권한 체계 개편 및 관리 기능 강화

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.3.0.0 | **0.4.0.0** | 권한 체계 전면 개편, 다수 신규 기능 |
| Frontend | 0.3.0.0 | **0.4.0.0** | 권한 UI 전면 수정, 회원가입 개선, 관리 페이지 확장 |
| Backend | 0.2.1.1 | **0.4.0.0** | 역할 체계 변경, API 다수 추가/수정 |
| Database | 0.1.0.0 | **0.2.0.0** | UserRole/ProjectRole 열거형 변경, 자동 마이그레이션 |

### 권한 체계 개편 (Breaking Change)

**기존 (4단계 플랫 구조)**
- `admin` / `editor` / `tester` / `viewer`

**신규 (2-tier 역할 체계)**

| 시스템 역할 | 설명 | 프로젝트 접근 |
|---|---|---|
| `admin` (시스템 관리자) | 최상위 권한, 전체 시스템 관리 | 모든 프로젝트 admin |
| `qa_manager` (QA 관리자) | 프로젝트 생성·관리, 사용자 목록 조회 | 모든 프로젝트 admin |
| `user` (일반 사용자) | 배정된 프로젝트만 접근 | 프로젝트별 역할 적용 |

| 프로젝트 역할 | 설명 |
|---|---|
| `admin` (프로젝트 관리자) | TC 읽기/쓰기, 테스트 런 삭제, 멤버 관리 |
| `tester` (프로젝트 테스터) | TC 읽기 전용, 테스트 수행만 가능 |

- DB 자동 마이그레이션: 서버 시작 시 기존 역할을 새 체계로 변환
  - `viewer`/`tester` → `user`, `editor` → `qa_manager`
  - 프로젝트: `viewer` → `tester`, `editor` → `admin`

### Backend 변경사항

**권한 관련**
- `auth.py` 전면 재작성: `SYSTEM_ROLE_HIERARCHY` + `PROJECT_ROLE_HIERARCHY` 분리
- `get_project_role()`: admin/qa_manager는 모든 프로젝트에 암묵적 admin 권한
- `check_project_access()`: 일반 사용자는 ProjectMember에 등록된 프로젝트만 접근
- `role_required()`: 시스템 역할 계층만 검사
- 프로젝트 생성 권한: `admin` → `qa_manager` 이상

**신규 API**
- `GET /api/auth/check-username` — 아이디 중복 확인
- `PUT /api/auth/users/{user_id}/reset-password` — 비밀번호 초기화 (임시 PW 발급 + 강제 변경)
- `POST /api/projects/assign-all` — 사용자를 모든 프로젝트에 일괄 배정
- `GET /api/projects/all-assignments` — 전체 사용자의 프로젝트 배정 현황 조회

**대시보드 수정**
- "전체" 모드: 모든 run의 결과를 합산 (기존: 최근 run 1개만 표시)
- summary, priority, category, assignee, heatmap 5개 엔드포인트 모두 수정
- `deleted_at.is_(None)` 필터 추가 (소프트 삭제 TC 제외)

**오류 메시지 한글화**
- 로그인/회원가입/비밀번호 변경 오류 메시지 전체 한글 전환

**변경 파일**
- `auth.py`, `models.py`, `schemas.py`, `main.py`
- `routes/auth.py`, `routes/projects.py`, `routes/testcases.py`, `routes/testruns.py`
- `routes/dashboard.py`, `routes/members.py`, `routes/overview.py`, `routes/search.py`

### Frontend 변경사항

**회원가입 개선**
- 실시간 아이디 중복 확인 (400ms 디바운스, 상태 표시: 확인 중/사용 가능/사용 불가)
- 회원가입 완료 토스트 중복 제거 (2개 → 1개)
- 토스트 위치 변경 (`top-right` → `top-center`)

**관리자 페이지 확장**
- 시스템 역할 드롭다운: 일반 사용자 / QA 관리자 / 시스템 관리자
- 프로젝트 배정 모달: 개별 프로젝트 추가/제거, 역할 변경, 전체 일괄 배정
- **프로젝트 배정 현황 인라인 표시**: 사용자 목록에서 배정된 프로젝트를 태그로 즉시 확인
  - 파란 태그: 관리자 역할 / 회색 태그: 테스터 역할
  - "미배정" 상태 표시
- 비밀번호 초기화 기능 (임시 PW 표시 + 클립보드 복사)

**권한 기반 UI 제어**
- TC 그리드: `project.my_role === "admin"`일 때만 편집 가능 (추가/삭제/복사/수정/가져오기/저장)
- 테스트 런: 관리자만 런 삭제 가능
- 프로젝트 목록: QA 관리자 이상만 프로젝트 생성 버튼 표시
- 프로젝트 멤버: 역할 선택지를 `tester`/`admin`으로 변경
- 헤더: 역할별 뱃지 색상 구분, 한글 역할명 표시

**비밀번호 분실 안내**
- 로그인 페이지에 "관리자에게 초기화를 요청하세요" 안내 텍스트 추가
- 비밀번호 변경 모달 인라인 에러 메시지 전환 (토스트 → 인라인)

**변경 파일**
- `api/index.ts`, `types/index.ts`, `contexts/AuthContext.tsx`, `main.tsx`
- `pages/AdminPage.tsx`, `pages/RegisterPage.tsx`, `pages/LoginPage.tsx`, `pages/ProjectListPage.tsx`, `pages/ProjectPage.tsx`
- `components/Header.tsx`, `components/TestCaseGrid.tsx`, `components/TestRunManager.tsx`
- `components/ProjectMembers.tsx`, `components/ChangePasswordModal.tsx`

### Database 변경사항

- `UserRole` 열거형: `viewer, tester, editor, admin` → `user, qa_manager, admin`
- `ProjectRole` 열거형: `viewer, tester, editor, admin` → `tester, admin`
- 기본값 변경: 신규 사용자 `user`, 신규 프로젝트 멤버 `tester`
- 시작 시 자동 마이그레이션 (`_migrate_roles()`)

---

## v0.3.0.0 (2026-03-16) — 매뉴얼 및 문서화

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.2.1.1 | **0.3.0.0** | 신규 기능 (매뉴얼 페이지) |
| Frontend | 0.2.1.0 | **0.3.0.0** | 페이지 2개 추가, 헤더 수정, 라우팅 추가 |
| Backend | 0.2.1.1 | 0.2.1.1 | 변경 없음 |
| Database | 0.1.0.0 | 0.1.0.0 | 변경 없음 |

### Frontend 변경사항

**신규 기능**
- **사용자 매뉴얼 페이지** (`/manual`)
  - 14개 섹션 (개요, 로그인, 프로젝트, TC 관리, 테스트 수행, 비교, 대시보드, 리포트, 설정, 테마, 단축키, 역할별 권한)
  - 좌측 고정 목차 네비게이션
  - 실제 앱 캡처 스크린샷 23장 포함
  - 모든 로그인 사용자 접근 가능

- **운영 매뉴얼 페이지** (`/admin-manual`)
  - 12개 섹션 (시스템 구성, 설치, 환경변수, DB, 사용자 관리, 권한 체계, API 52개 목록, 보안, 트러블슈팅, 백업)
  - Admin 역할 전용 (비관리자 접근 시 자동 리다이렉트)

- **헤더 "도움말" 버튼 추가**: 사용자 매뉴얼 페이지로 이동

**변경 파일**
- `App.tsx` — `/manual`, `/admin-manual` 라우트 추가
- `Header.tsx` — 도움말 버튼 추가
- `pages/UserManualPage.tsx` — 신규
- `pages/AdminManualPage.tsx` — 신규
- `public/manual-images/` — 캡처 이미지 23장

### 문서
- Confluence 사내 업무 가이드 초안 (`docs/confluence_draft.md`)
- TC 리그레션 체크리스트 한글화 및 확장 (46건 → 150건)
- 릴리즈 노트 신규 작성 (`Release_note.md`)
- 이슈 목록 신규 작성 (`Issue_list.xlsx`)

---

## v0.2.1.1 (2026-03-16) — 보안 강화

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.2.1.0 | **0.2.1.1** | 보안 패치 |
| Frontend | 0.2.1.0 | 0.2.1.0 | 변경 없음 |
| Backend | 0.2.1.0 | **0.2.1.1** | 보안 취약점 수정 |
| Database | 0.1.0.0 | 0.1.0.0 | 변경 없음 |

### Backend 변경사항

**보안 수정**
- **첨부파일 API 프로젝트 권한 검증**: 업로드/다운로드/삭제 시 프로젝트 멤버 여부 확인
- **확장자 없는 파일 업로드 차단**: 확장자가 없는 파일은 업로드 거부
- **다운로드 MIME 타입 안전 처리**: 안전하지 않은 MIME 타입은 `application/octet-stream` 강제
- **Rate Limiting 수정**: 성공 시도 미카운트, 성공 시 실패 카운터 초기화
- **SECRET_KEY 하드코딩 제거**: 프로덕션 환경에서 환경변수 미설정 시 서버 시작 실패
- **CORS 강화**: 와일드카드(`*`) → 특정 도메인 화이트리스트
- **보안 테스트 정비**: pytest 기반 36개 테스트 통과

### 리뷰
- 제품 리뷰 수행 (`product_review_2026-03-16.md`)
- 보안 리뷰 3차 수행 (`security_review_2026-03-16.md`)
- OWASP Top 10 기반 취약점 점검

---

## v0.2.1.0 (2026-03-09) — 코드 리뷰 반영 및 안정화

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.2.0.0 | **0.2.1.0** | 빌드 실패 수정, 중요 버그 수정 |
| Frontend | 0.2.0.0 | **0.2.1.0** | 빌드 에러 수정, 검색 네비게이션, 다크 모드 통일 |
| Backend | 0.2.0.0 | **0.2.1.0** | 첨부파일 물리 삭제 연결 |
| Database | 0.1.0.0 | 0.1.0.0 | 변경 없음 |

### Frontend 변경사항

**버그 수정**
- **TypeScript 빌드 에러 해결**
  - `TestRunManager.tsx` handleDeleteAttachment 미사용 변수 제거
  - `doesExternalFilterPass` 파라미터 타입 수정 (`IRowNode<TestResult>`)
  - Vite 프로덕션 빌드 정상 통과

- **글로벌 검색 TC 위치 이동**
  - 검색 결과 클릭 시 `?tab=tc&highlight=TC_ID` 파라미터 전달
  - `TestCaseGrid`에서 해당 행 자동 선택 및 스크롤

- **관리자 페이지 권한 가드**
  - `useEffect`로 Admin 여부 사전 체크
  - 비관리자 접근 시 API 호출 없이 안내 메시지 표시

**개선**
- **한글 인코딩 대응**: `vite.config.ts`에 `charsetPlugin` 추가, `index.html`에 `lang="ko"`
- **다크 모드 테마 통일**: 6개 컴포넌트의 하드코딩 인라인 색상 → CSS 변수 전환

### Backend 변경사항

**버그 수정**
- **첨부파일 물리 삭제 연결**: 테스트 런 삭제 시 `UPLOAD_DIR` 기반 실제 파일 경로 구성하여 물리 파일 삭제

---

## v0.2.0.0 (2026-03-06) — 핵심 기능 구현 완료

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.1.0.0 | **0.2.0.0** | 다수 신규 기능 추가 |
| Frontend | 0.1.0.0 | **0.2.0.0** | 비교 뷰, 대시보드, 단축키, 타이머, 다크 모드 등 |
| Backend | 0.1.0.0 | **0.2.0.0** | 대시보드 API, 비교 API, Excel Export API 등 |
| Database | 0.1.0.0 | 0.1.0.0 | 변경 없음 |

### Frontend 변경사항

**테스트 수행**
- **키보드 단축키** (P/F/B/N): 결과 셀에서 키 입력으로 빠른 결과 입력, 자동 다음 행 이동
- **TC 수행 타이머**: 행 포커스 시 자동 타이머 시작, 행 변경 시 누적 기록
- **Undo/Redo**: Ctrl+Z로 결과 변경 실행 취소 (최대 200단계 스택)
- **드래그 앤 드롭 이미지 첨부**: 그리드 영역에 이미지 드롭 → 포커스된 행에 첨부
- **결과 Excel Export**: 테스트 수행 결과를 서식 적용된 엑셀 파일로 다운로드

**분석**
- **비교 뷰**: 두 테스트 런 간 결과 비교, 변경/리그레션/개선 자동 감지, 필터링
- **대시보드**: 요약 카드, 결과 분포 도넛 차트, 라운드별 비교 바 차트, 추이 라인 차트
- **실패 히트맵**: 카테고리 × 우선순위 매트릭스에서 실패 건수 색상 강도 표시
- **담당자별 현황**: 담당자별 진행률/완료율 테이블

**기타**
- **다크 모드**: ThemeContext + CSS 변수 기반, 헤더 토글 버튼
- **그리드 정렬/필터 개선**: 결과/카테고리/우선순위 드롭다운 필터 + 텍스트 검색 + 초기화
- **텍스트 줄바꿈**: `white-space: pre-wrap` 전역 적용

### Backend 변경사항

- **대시보드 API**: summary, priority, category, rounds, assignee, heatmap 6개 엔드포인트
- **비교 API**: 두 런 간 결과 비교 데이터
- **Excel Export API**: 테스트 런 결과 엑셀 다운로드
- **전체 현황 API**: 프로젝트 횡단 집계

---

## v0.1.0.0 (2026-03-05 이전) — MVP 초기 구현

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | - | **0.1.0.0** | 최초 릴리즈 |
| Frontend | - | **0.1.0.0** | 최초 구현 |
| Backend | - | **0.1.0.0** | 최초 구현 |
| Database | - | **0.1.0.0** | 스키마 최초 생성 |

### Frontend

- 로그인/회원가입 페이지
- 프로젝트 목록 페이지 (전체 현황, 프로젝트 카드)
- 프로젝트 상세 페이지 (탭 구조: TC 관리, 테스트 수행, 비교, 대시보드, 리포트, 설정)
- TC 관리 그리드 (AG Grid 인라인 편집, Excel Import/Export)
- 테스트 런 관리 (생성/복제/완료/삭제, 결과 기록)
- 첨부파일 업로드/다운로드/미리보기
- 리포트 뷰 (PDF/Excel 다운로드)
- 글로벌 검색 (헤더 검색바)
- 관리자 페이지 (사용자 목록, 역할 변경)

### Backend

- **인증**: 회원가입/로그인/로그아웃, JWT (HS256), bcrypt, 최초 가입자 Admin 자동 부여
- **RBAC**: Admin/Editor/Tester/Viewer 4단계 + 프로젝트별 역할
- **프로젝트**: CRUD, 공개/비공개, Jira Base URL, 멤버 관리
- **TC**: CRUD, 벌크 업데이트, 소프트 삭제/복원 (7일), 변경 이력 추적
- **Excel Import**: 50+ 영문/한글 헤더 자동 매핑, 스마트 헤더 감지, 병합 셀 처리
- **테스트 런**: 생성/복제/완료/삭제, 결과 벌크 저장
- **첨부파일**: 업로드/다운로드/삭제, 이미지/문서/아카이브 (50MB), UUID 파일명
- **리포트**: JSON/PDF/Excel 생성, 한글 폰트 지원 (Malgun Gothic)
- **글로벌 검색**: 전체 프로젝트 TC 검색 (100건 제한)

### Database

- **스키마 v0.1.0.0**: 8개 테이블 초기 생성
  - `users`, `projects`, `test_cases`, `test_runs`, `test_results`, `attachments`, `project_members`, `test_case_history`
- SQLAlchemy `create_all()` 기반 자동 생성
- SQLite (`tc_manager.db`)

### 인프라

- Backend: FastAPI + Uvicorn (포트 8000)
- Frontend: React 18 + TypeScript + Vite (포트 5173)
- Docker / Docker Compose 지원
- Swagger API 문서 자동 생성 (`/docs`)

---

## 미구현 기능 (Backlog)

| ID | 기능 | 우선순위 | 영향 컴포넌트 | 비고 |
|---|---|---|---|---|
| #2 | Jira 이슈 자동 생성 (FAIL 시) | 중간 | BE | 외부 Jira API 연동 필요 |
| #12 | Slack/Email 알림 | 낮음 | BE | 외부 연동 필요 |
| #13 | 실시간 협업 편집 (WebSocket) | 낮음 | FE + BE | 인프라 구성 필요 |
| #14 | 코멘트/스레드 | 중간 | FE + BE + DB | TC별 토론 기능 |
| #15 | @멘션 + 알림 | 낮음 | FE + BE + DB | FAIL 케이스 담당자 지정 |
| #16 | TC 버전 관리 | 중간 | FE + BE | 변경 이력 diff 뷰 |
| #17 | 테스트 계획 관리 | 중간 | FE + BE + DB | 스프린트/마일스톤 범위 |
| #18 | API 자동화 연동 | 높음 | BE + DB | Playwright/pytest 결과 자동 기록 |
| #19 | 태그/라벨 시스템 | 낮음 | FE + BE + DB | 자유 형식 TC 태깅 |

---

## 알려진 이슈

> 상세 내역은 `Issue_list.xlsx` 참고
> 최종 검증일: 2026-03-16

### 현황: Open 3건 / Fixed 31건 / Deferred 1건

**Open (3건)**
- ENH-001: Alembic 마이그레이션 미도입 — `create_all()` + 수동 ALTER TABLE 사용 중 (프로덕션 전 필수)
- ENH-002: PostgreSQL 전환 준비 — 현재 SQLite, 프로덕션 시 전환 필요
- ENH-003: N+1 쿼리 최적화 — overview/dashboard/reports 대량 데이터 시 성능 저하 가능

**Deferred (1건)**
- SEC-002: localStorage JWT 토큰 저장 — XSS 시 탈취 가능 (장기 과제, DOMPurify로 현재 리스크 낮음)

**v0.5.0.0에서 해결 (4건)**
- FIX-032: overview/dashboard/testruns에서 deleted_at 필터 누락 → 삭제된 TC가 카운트에 포함
- FIX-033: TC 삭제 시 순차 DELETE로 수십 초 소요 → 벌크 DELETE API로 280ms 이내
- FIX-034: 첨부파일 전체 동시 API 호출로 237개 TC에서 버벅임 → 행 포커스 시 lazy load
- FIX-035: 빈 이름으로 프로젝트 생성 가능 → ProjectCreate에 min_length=1 추가

**v0.4.0.0에서 해결 (5건)**
- FIX-028: 로그인 오류 메시지 영문 표시 → 한글로 변경
- FIX-029: 회원가입 시 아이디 중복 체크 미제공 → 실시간 중복 확인 추가
- FIX-030: 회원가입 완료 시 토스트 2개 중복 표시 → 1개로 수정
- FIX-031: 대시보드 "전체" 모드가 특정 run과 동일 데이터 표시 → 모든 run 결과 합산으로 수정
- ENH-004: 권한 체계 세분화 미흡 (viewer/admin 구분 불명확) → 2-tier 역할 체계로 전면 개편

---

*이 문서는 YM TestCase의 모든 릴리즈 이력을 관리합니다. 새로운 배포 시 최상단에 새 버전을 추가하세요.*
