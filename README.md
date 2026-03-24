# YM TestCase

> **Y**our **M**ethod, Your Test Case Manager

QA 팀과 개발팀을 위한 셀프 호스팅형 테스트케이스 관리 도구.
TestRail · Kiwi TCMS 대안으로, **작성 → 실행 → 집계 → 리포트**를 한 곳에서 관리합니다.

- **빠르게 작성** — 스프레드시트 스타일 그리드로 TC를 즉시 편집
- **실행 결과 추적** — 테스트 런 · 플랜 · 대시보드로 진행률을 한눈에
- **팀 프로세스에 맞춤** — 역할 기반 접근 제어, 커스텀 필드, 고급 필터

![TC 관리 — 스프레드시트 스타일 편집](docs/screenshots/tc_grid.png)

| ![프로젝트 목록](docs/screenshots/project_list.png) | ![대시보드](docs/screenshots/dashboard.png) |
|---|---|
| **프로젝트 목록** — 현황 및 진행률 | **대시보드** — 통계 한눈에 |

## 기존 도구와의 비교

<table>
<thead>
<tr><th>기존 방식</th><th>YM TestCase</th></tr>
</thead>
<tbody>
<tr><td>스프레드시트로 TC 관리 → 버전 충돌, 통계 불가</td><td><b><a href="#">웹 기반 실시간 편집, 자동 집계</a></b></td></tr>
<tr><td>상용 도구(TestRail 등) → 비용, 셀프호스팅 불가</td><td><b><a href="#">무료 오픈소스, 셀프호스팅 가능</a></b></td></tr>
<tr><td>자체 개발 → 구축 기간, 유지보수 부담</td><td><b><a href="#">설치 즉시 사용 가능, AGPL-3.0 라이선스</a></b></td></tr>
</tbody>
</table>

## 환경설정 방법

**사전 요구사항**:
- [Python 3.12+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/)
- [Git](https://git-scm.com/)

```bash
git clone https://github.com/sym804/ym-testcase.git
cd ym-testcase
cp backend/.env.example backend/.env
```

> **SECRET_KEY 설정**: `backend/.env` 파일 안의 `SECRET_KEY` 값을 변경하세요.
> 이 키는 JWT 인증 토큰 서명에 사용됩니다. 미설정 시 서버 시작마다 랜덤 키가 생성되어
> **재시작할 때 기존 로그인이 모두 풀립니다.** 운영 환경에서는 반드시 고정 값을 설정하세요.

**서버 실행**:
```bash
# 백엔드
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8008

# 프론트엔드 (새 터미널)
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

> 첫 번째로 가입하는 사용자가 자동으로 **admin** 권한을 받습니다.

## 주요 기능

| 기능 | 설명 |
|---|---|
| 스프레드시트 TC 편집 | ag-grid 기반 인라인 편집, 다중 행 추가, 벌크 삭제 |
| 시트 트리 구조 | N-depth 계층형 Test Suite 관리 |
| 커스텀 필드 | text, number, select, multiselect, checkbox, date |
| 테스트 런 | 실행 결과 기록, 진행률 추적, 재실행 |
| 테스트 플랜 | 릴리즈 단위 수행 관리, 마일스톤별 진행률 |
| 대시보드 | 프로젝트별 통계 차트 (Chart.js) |
| 고급 필터 | AND/OR 다중 조건, 필터 저장/불러오기 |
| Import/Export | Excel(xlsx), Jira CSV, PDF 리포트 |
| 접근 제어 | 시스템 역할 + 프로젝트 역할 이중 구조 |
| 보안 | httpOnly 쿠키 인증, CSRF 보호, Rate Limiting, bcrypt |

## 스크린샷

<details>
<summary>더 보기</summary>

### 프로젝트 목록
![프로젝트 목록](docs/screenshots/project_list.png)

### TC 관리 (스프레드시트 스타일)
![TC 관리](docs/screenshots/tc_grid.png)

### 시트 트리 구조
![시트 트리](docs/screenshots/sheet_tree.png)

### 테스트 수행 결과
![테스트 수행](docs/screenshots/testrun.png)

### 고급 필터
![고급 필터](docs/screenshots/filter.png)

### 다크 모드
![다크 모드](docs/screenshots/dark_mode.png)

</details>

## 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | React 19, TypeScript, Vite, ag-grid, Chart.js |
| Backend | Python 3.12, FastAPI, SQLAlchemy, SQLite |
| Test | Vitest (357 tests), Playwright (E2E), pytest |
| Deploy | 셀프호스팅 (로컬 실행) |

## 테스트

```bash
# Frontend 단위 테스트
cd frontend && npm run test

# Backend API 테스트 (서버 실행 상태에서)
cd backend && python -m pytest -v

# E2E 테스트 (서버 실행 상태에서)
cd frontend && npx playwright test
```

## 프로젝트 구조

```
ym-testcase/
├── backend/          # FastAPI 백엔드
│   ├── main.py       # 앱 엔트리포인트
│   ├── models.py     # SQLAlchemy 모델
│   ├── routes/       # API 라우터 (15 모듈)
├── frontend/         # React 프론트엔드
│   ├── src/
│   │   ├── pages/    # 페이지 컴포넌트
│   │   ├── components/
│   │   └── api/      # API 클라이언트
│   ├── e2e/          # Playwright E2E 테스트
├── backend/.env.example
├── run_dev.bat       # Windows 개발 서버
├── run_dev.sh        # Mac/Linux 개발 서버
└── README.md
```

## 기여하기

기여를 환영합니다! [CONTRIBUTING.md](CONTRIBUTING.md)를 읽어주세요.

## 라이선스

AGPL-3.0 — [GNU Affero General Public License v3.0](LICENSE)
