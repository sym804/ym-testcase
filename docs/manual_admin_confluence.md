# TC Manager 운영 매뉴얼 (Admin)

> **최종 업데이트**: 2026-03-18
> **버전**: 0.4.0.0
> **대상**: Admin 역할 담당자
> **보안 등급**: 내부 관리용

---

## 1. 시스템 구성

| 구성 요소 | 기술 스택 | 비고 |
|---|---|---|
| **Backend** | FastAPI (Python 3.10+), SQLAlchemy ORM, Uvicorn ASGI | 포트 8008 |
| **Frontend** | React 18, TypeScript, Vite, AG Grid, Chart.js | 포트 5173 (개발) / 80 (프로덕션) |
| **Database** | SQLite (기본) / PostgreSQL (프로덕션 권장) | `tc_manager.db` |
| **인증** | JWT (HS256), bcrypt 해싱 | 토큰 만료 2시간 |
| **배포** | Docker / Docker Compose 지원 | `docker-compose.yml` |

---

## 2. 설치 및 실행

### 2-1. 개발 환경 실행

```bash
# Backend 시작
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8008

# Frontend 시작 (별도 터미널)
cd frontend
npm install
npm run dev
```

### 2-2. Docker Compose 실행

```bash
docker-compose up -d

# 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f backend
```

### 2-3. 프로덕션 빌드

```bash
# Frontend 프로덕션 빌드
cd frontend
npm run build

# TypeScript 타입 체크
npx tsc --noEmit
```

---

## 3. 환경 변수

| 변수명 | 기본값 | 설명 | 필수 |
|---|---|---|---|
| `SECRET_KEY` | (자동 생성/dev) | JWT 서명 키. **프로덕션 필수 설정** | ⚠️ 프로덕션 필수 |
| `ENV` | development | 환경 구분. production 시 SECRET_KEY 미설정 에러 | 선택 |
| `DATABASE_URL` | sqlite:///./tc_manager.db | DB 연결 문자열 | 선택 |
| `TOKEN_EXPIRE_HOURS` | 2 | JWT 토큰 만료 시간 (시간) | 선택 |
| `CORS_ORIGINS` | http://localhost:5173,http://localhost:3000 | CORS 허용 오리진 (콤마 구분) | 선택 |
| `UPLOAD_DIR` | ./uploads | 첨부파일 저장 디렉토리 | 선택 |

⚠️ **주의**: 프로덕션 환경에서는 반드시 `SECRET_KEY`를 고유한 값으로 설정하세요. 미설정 시 서버 시작이 실패합니다.

---

## 4. 데이터베이스

- 기본: SQLite (`backend/tc_manager.db`)
- 테이블은 서버 최초 시작 시 SQLAlchemy가 자동 생성
- PostgreSQL 전환 시 `DATABASE_URL` 환경변수 변경

### 4-1. 주요 테이블

| 테이블 | 설명 | 주요 관계 |
|---|---|---|
| `users` | 사용자 계정 | projects, test_runs 소유 |
| `projects` | 프로젝트 | test_cases, test_runs 포함 |
| `test_cases` | 테스트 케이스 | project 소속, 소프트 삭제 지원 |
| `test_runs` | 테스트 런 | project 소속, test_results 포함 |
| `test_results` | 테스트 결과 | test_run + test_case 참조, attachments 포함 |
| `attachments` | 첨부파일 메타데이터 | test_result 참조 |
| `project_members` | 프로젝트 멤버 | user + project 연결 |
| `test_case_history` | TC 변경 이력 | test_case 참조 |

### 4-2. 소프트 삭제 정책

테스트 케이스는 삭제 시 **소프트 삭제** (deleted_at 필드 설정). **7일 후** 자동 영구 삭제.

복원 API: `POST /api/projects/{id}/testcases/{tc_id}/restore`

---

## 5. 사용자 관리

> 📎 `22_admin_page.png`

### 5-1. 접근

헤더 → **"관리"** 버튼 → 사용자 관리 페이지

### 5-2. 사용자 목록

모든 사용자의 ID, 사용자명, 표시명, 역할, 가입일을 확인할 수 있습니다.

### 5-3. 역할 변경

1. 대상 사용자의 역할 드롭다운을 변경합니다.
2. 변경 즉시 적용됩니다.
3. 해당 사용자의 다음 API 호출부터 새 권한이 적용됩니다.

⚠️ **주의**: 자신의 Admin 역할을 해제하면 관리자 페이지에 접근할 수 없게 됩니다. 최소 1명의 Admin을 유지하세요.

### 5-4. 비밀번호 초기화

1. 대상 사용자 행에서 **비밀번호 초기화** 버튼을 클릭합니다.
2. 12자리 임시 비밀번호가 생성되어 표시됩니다.
3. 해당 임시 비밀번호를 사용자에게 전달합니다.
4. 사용자는 다음 로그인 시 **비밀번호 강제 변경** 화면이 표시됩니다.

⚠️ **주의**: 임시 비밀번호는 화면에 1회만 표시됩니다. 반드시 메모하여 전달하세요.

### 5-5. 초기 계정

시스템 최초 가입 사용자가 자동으로 **Admin** 역할을 부여받습니다. 이후 가입자는 모두 **User**로 시작합니다.

### 5-6. 역할 변경 가이드라인

| 대상 | 권장 역할 |
|---|---|
| QA 엔지니어 | **User** (프로젝트 Tester 역할 부여) |
| PM / QA 리드 | **QA Manager** |
| 인프라/운영 담당자 | **Admin** |
| 외부 참관인 | **User** (공개 프로젝트만 접근 가능) |

---

## 6. 역할/권한 체계

### 6-1. 시스템 역할

| 역할 | 수준 | 주요 권한 |
|---|---|---|
| **Admin** | 최상위 | 모든 기능 + 사용자 관리 + 비밀번호 초기화 + 역할 변경 |
| **QA Manager** | 관리 | 사용자 목록 조회 + 모든 프로젝트 접근 |
| **User** | 일반 | 소속 프로젝트 + 공개 프로젝트 접근 |

### 6-2. 프로젝트 역할

| 역할 | 설명 |
|---|---|
| **Project Admin** | 프로젝트 관리, TC CRUD, 런 관리, 멤버 관리, 설정 변경 |
| **Project Tester** | 테스트 수행, 결과 기록, 첨부파일 업로드 |

- 비공개 프로젝트는 멤버 또는 생성자만 접근 가능
- 공개 프로젝트는 인증된 사용자 모두 조회 가능 (수정은 프로젝트 역할에 따름)
- System Admin / QA Manager는 모든 프로젝트에 접근 가능

### 6-3. 비밀번호 정책

| 항목 | 설정 |
|---|---|
| 최소 길이 | 8자 |
| 동일 비밀번호 재사용 | 불가 (변경 시 현재 비밀번호와 동일하면 거부) |
| 강제 변경 | 관리자 초기화 후 다음 로그인 시 강제 |
| 임시 비밀번호 | 12자리 영문+숫자 랜덤 생성 |

---

## 7. 프로젝트 운영

### 7-1. 프로젝트 삭제 시 영향 범위

⚠️ 프로젝트 삭제 시 다음 데이터가 **모두 영구 삭제**됩니다:
- 프로젝트 정보
- 모든 테스트 케이스 (이력 포함)
- 모든 테스트 런 및 결과
- 모든 첨부파일 (DB 레코드 + 물리 파일)
- 프로젝트 멤버 연결

### 7-2. Jira 연동

- 프로젝트 설정에서 **Jira Base URL** 설정 (예: `https://yourteam.atlassian.net/browse/`)
- TC 또는 결과의 Issue Link에 이슈 키 입력 시 자동 링크 생성

---

## 8. 파일/첨부 관리

| 항목 | 설정 |
|---|---|
| 저장 경로 | `UPLOAD_DIR` 환경변수 (기본: `./uploads`) |
| 파일 크기 제한 | 50MB |
| 허용 확장자 (이미지) | .png, .jpg, .jpeg, .gif, .bmp, .webp |
| 허용 확장자 (문서) | .pdf, .doc, .docx, .xlsx, .xls, .pptx |
| 허용 확장자 (기타) | .zip, .txt, .csv, .log |
| 파일명 처리 | UUID 기반 변환 (경로 탐색 공격 방지) |
| 다운로드 보안 | 안전하지 않은 MIME은 octet-stream 강제 |

💡 **디스크 관리**: 테스트 런 삭제 시 첨부파일 물리 파일도 자동 삭제됩니다. 주기적으로 디스크 사용량을 확인하세요.

---

## 9. 보안 설정

| 보안 항목 | 구현 | 설정 |
|---|---|---|
| 비밀번호 정책 | 최소 8자, 동일 비밀번호 재사용 불가 | 자동 적용 |
| 비밀번호 저장 | bcrypt 해싱 | 자동 적용 |
| 비밀번호 초기화 | Admin이 임시 비밀번호 발급, 강제 변경 플래그 | Admin 페이지 |
| 인증 토큰 | JWT (HS256) | TOKEN_EXPIRE_HOURS (기본 2시간) |
| 로그인 제한 | Rate Limiting | IP+사용자당 5분간 10회 (초과 시 잠금) |
| CORS | 오리진 화이트리스트 | CORS_ORIGINS (와일드카드 금지) |
| 파일 업로드 | 확장자 화이트리스트 + 경로 탐색 방지 | 허용 확장자 고정 |
| XSS 방지 | DOMPurify (프론트엔드) | 마크다운 셀 렌더링 시 자동 적용 |
| API 권한 | 역할 기반 접근 제어 | 엔드포인트별 역할 체크 |

---

## 10. API 엔드포인트 (52개)

API 문서(Swagger UI): `http://localhost:8008/docs`

### 인증 (Auth)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/auth/check-username | 사용자명 중복 확인 |
| POST | /api/auth/register | 회원가입 (비밀번호 최소 8자) |
| POST | /api/auth/login | 로그인 (JWT 토큰 발급) |
| GET | /api/auth/me | 현재 사용자 정보 |
| PUT | /api/auth/change-password | 비밀번호 변경 (최소 8자) |
| GET | /api/auth/users | 사용자 목록 (QA Manager 이상) |
| PUT | /api/auth/users/{user_id}/role | 역할 변경 (Admin) |
| PUT | /api/auth/users/{user_id}/reset-password | 비밀번호 초기화 (Admin) |

### 프로젝트

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/projects | 프로젝트 목록 |
| POST | /api/projects | 프로젝트 생성 (Admin) |
| GET | /api/projects/{id} | 프로젝트 상세 |
| PUT | /api/projects/{id} | 프로젝트 수정 |
| DELETE | /api/projects/{id} | 프로젝트 삭제 (Admin) |

### 테스트 케이스

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/projects/{id}/testcases | TC 목록 |
| POST | /api/projects/{id}/testcases | TC 생성 |
| PUT | /api/projects/{id}/testcases/{tc_id} | TC 수정 |
| PUT | /api/projects/{id}/testcases/bulk | TC 일괄 수정 |
| DELETE | /api/projects/{id}/testcases/{tc_id} | TC 삭제 (소프트) |
| POST | /api/projects/{id}/testcases/{tc_id}/restore | TC 복원 |
| POST | /api/projects/{id}/testcases/import | Excel Import |
| GET | /api/projects/{id}/testcases/export | Excel Export |

### 테스트 런

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/projects/{id}/testruns | 런 목록 |
| POST | /api/projects/{id}/testruns | 런 생성 |
| GET | /api/projects/{id}/testruns/{run_id} | 런 상세 (결과 포함) |
| PUT | /api/projects/{id}/testruns/{run_id} | 런 수정 |
| POST | /api/projects/{id}/testruns/{run_id}/results | 결과 저장 (벌크) |
| PUT | /api/projects/{id}/testruns/{run_id}/complete | 런 완료 |
| POST | /api/projects/{id}/testruns/{run_id}/clone | 런 복제 |
| DELETE | /api/projects/{id}/testruns/{run_id} | 런 삭제 |
| GET | /api/projects/{id}/testruns/{run_id}/export | 런 Excel Export |

### 대시보드

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/projects/{id}/dashboard/summary | 요약 통계 |
| GET | /api/projects/{id}/dashboard/priority | 우선순위별 분포 |
| GET | /api/projects/{id}/dashboard/category | 카테고리별 분포 |
| GET | /api/projects/{id}/dashboard/rounds | 라운드별 비교 |
| GET | /api/projects/{id}/dashboard/assignee | 담당자별 현황 |
| GET | /api/projects/{id}/dashboard/heatmap | 실패 히트맵 |

### 리포트

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/projects/{id}/reports | 리포트 JSON |
| GET | /api/projects/{id}/reports/pdf | PDF 다운로드 |
| GET | /api/projects/{id}/reports/excel | Excel 다운로드 |

### 첨부파일

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/attachments/{result_id} | 첨부파일 목록 |
| POST | /api/attachments/{result_id} | 첨부파일 업로드 |
| GET | /api/attachments/download/{id} | 첨부파일 다운로드 |
| DELETE | /api/attachments/{id} | 첨부파일 삭제 |

### 멤버 관리

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/projects/{id}/members | 멤버 목록 |
| POST | /api/projects/{id}/members | 멤버 추가 |
| PUT | /api/projects/{id}/members/{member_id} | 멤버 역할 변경 |
| DELETE | /api/projects/{id}/members/{member_id} | 멤버 제거 |

### 기타

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/history/project/{project_id} | 프로젝트 변경 이력 |
| GET | /api/history/testcase/{test_case_id} | TC 변경 이력 |
| GET | /api/search?q=... | 글로벌 TC 검색 |
| GET | /api/dashboard/overview | 전체 현황 |

---

## 11. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| 서버 시작 실패 (RuntimeError) | 프로덕션에서 SECRET_KEY 미설정 | 환경변수 SECRET_KEY 설정 |
| 로그인 시 401 에러 | 잘못된 자격증명 또는 토큰 만료 | 자격증명 확인 또는 재로그인 |
| 로그인 잠금 (429) | 5분간 10회 실패 | 5분 대기 후 재시도 |
| CORS 에러 | 프론트엔드 오리진 미등록 | CORS_ORIGINS에 추가 |
| 파일 업로드 실패 | 50MB 초과 또는 비허용 확장자 | 파일 확인 |
| 한글 깨짐 | 소스 파일 인코딩 문제 | UTF-8로 재저장 후 빌드 |
| Excel Import 실패 | 헤더 매핑 실패 | 지원 헤더 형식 확인 |
| PDF 한글 깨짐 | 서버에 한글 폰트 미설치 | Malgun Gothic 설치 |

---

## 12. 백업/복구

### 12-1. 백업 대상

1. 데이터베이스: `backend/tc_manager.db`
2. 첨부파일: `backend/uploads/` 디렉토리

### 12-2. 백업 명령

```bash
# DB 백업
cp backend/tc_manager.db backup/tc_manager_$(date +%Y%m%d).db

# 첨부파일 백업
cp -r backend/uploads backup/uploads_$(date +%Y%m%d)
```

### 12-3. 복구

```bash
# 데이터베이스 복구
cp backup/tc_manager_20260316.db backend/tc_manager.db

# 첨부파일 복구
cp -r backup/uploads_20260316/* backend/uploads/

# 서버 재시작
docker-compose restart backend
```

💡 **권장**: 정기적인 백업 스케줄 설정 (일 1회). SQLite 파일과 uploads 디렉토리를 함께 백업해야 합니다.

---

## 첨부 이미지 목록

| 파일명 | 설명 | 사용 위치 |
|---|---|---|
| `01_login_page.png` | 로그인 페이지 | 사용자 매뉴얼 2-1 |
| `02_register_page.png` | 회원가입 페이지 | 사용자 매뉴얼 2-2 |
| `04_project_list_overview.png` | 프로젝트 목록 전체 현황 | 사용자 매뉴얼 3-1 |
| `05_project_list_cards.png` | 프로젝트 카드 | 사용자 매뉴얼 3-2 |
| `06_project_create_modal.png` | 프로젝트 생성 모달 | 사용자 매뉴얼 3-3 |
| `07_project_detail_tc_tab.png` | 프로젝트 상세 (TC 탭) | 사용자 매뉴얼 5 |
| `08_tc_grid_detail.png` | TC 그리드 상세 | 사용자 매뉴얼 6-2 |
| `09_testrun_tab.png` | 테스트 수행 탭 | 사용자 매뉴얼 7 |
| `12_compare_tab.png` | 비교 탭 | 사용자 매뉴얼 8 |
| `13_dashboard_top.png` | 대시보드 상단 | 사용자 매뉴얼 9 |
| `14_dashboard_charts.png` | 대시보드 차트 | 사용자 매뉴얼 9-2 |
| `15_dashboard_bottom.png` | 대시보드 하단 | 사용자 매뉴얼 9-2 |
| `16_report_tab.png` | 리포트 탭 | 사용자 매뉴얼 10 |
| `17_settings_tab.png` | 설정 탭 | 사용자 매뉴얼 11 |
| `18_settings_members.png` | 멤버 관리 | 사용자 매뉴얼 11-2 |
| `19_global_search.png` | 글로벌 검색 | 사용자 매뉴얼 4 |
| `20_dark_mode_project.png` | 다크모드 프로젝트 | 사용자 매뉴얼 12 |
| `21_dark_mode_dashboard.png` | 다크모드 대시보드 | 사용자 매뉴얼 12 |
| `22_admin_page.png` | 관리자 페이지 | 운영 매뉴얼 5 |
| `23_tc_toolbar.png` | TC 관리 툴바 | 사용자 매뉴얼 6-1 |

---

*TC Manager v0.4.0.0 | 운영 매뉴얼 (Admin 전용)*
