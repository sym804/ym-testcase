# YM TestCase

> **Y**our **M**ethod, Your Test Case Manager

QA 팀과 개발팀을 위한 셀프 호스팅형 테스트케이스 관리 도구.
TestRail · Kiwi TCMS 대안으로, **작성 → 실행 → 집계 → 리포트**를 한 곳에서 관리합니다.

- **빠르게 작성** - 스프레드시트 스타일 그리드로 TC를 즉시 편집
- **실행 결과 추적** - 테스트 런 · 플랜 · 대시보드로 진행률을 한눈에
- **팀 프로세스에 맞춤** - 역할 기반 접근 제어, 커스텀 필드, 고급 필터

![TC 관리 - 스프레드시트 스타일 편집](docs/screenshots/tc_grid.png)

| ![프로젝트 목록](docs/screenshots/project_list.png) | ![대시보드](docs/screenshots/dashboard.png) |
|---|---|
| **프로젝트 목록** - 현황 및 진행률 | **대시보드** - 통계 한눈에 |

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

## 설치 및 실행

> **💡 Tip: AI Agent에게 이 레포지토리 주소를 알려주고 README 문서대로 설치할 것을 요청하면 더 쉽게 설치가 가능합니다.**

### 1. 사전 요구사항

- [Python 3.11 ~ 3.14](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/)
- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (로컬 PostgreSQL)

### 2. 소스 코드 다운로드

```bash
git clone https://github.com/sym804/ym-testcase.git
cd ym-testcase
```

### 3. 환경변수 설정

```bash
cp backend/.env.example backend/.env
```

복사한 `backend/.env` 파일을 열어서 **SECRET_KEY를 반드시 변경**하세요:

```dotenv
# 변경 전 (기본값 - 이대로 쓰면 안 됩니다)
SECRET_KEY=change-me-to-a-random-string

# 변경 후 (아무 랜덤 문자열로 교체)
SECRET_KEY=my-super-secret-key-abc123xyz
```

> **왜 바꿔야 하나요?** 이 키는 로그인 토큰 암호화에 사용됩니다.
> 기본값 그대로 두면 서버를 재시작할 때마다 **로그인이 풀립니다.**

나머지 설정은 기본값으로 동작하므로 로컬 개발 시 수정할 필요 없습니다.
상세한 설정 항목은 `backend/.env.example` 파일의 주석을 참고하세요.

### 4. 서버 실행

**DB** (레포 루트에서 한 번):
```bash
docker compose up -d --wait db
```

**백엔드** (터미널 1):
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8008
```

**프론트엔드** (터미널 2):
```bash
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:5173 접속 → 첫 번째로 가입하는 사용자가 자동으로 **admin** 권한을 받습니다.

### 5. 업데이트

```bash
cd ym-testcase
git pull origin main
pip install -r backend/requirements.txt   # 백엔드 의존성 변경 시
cd frontend && npm install                # 프론트엔드 의존성 변경 시
```

이후 서버를 재시작하면 최신 버전이 적용됩니다.

## 배포 (Vercel + Supabase)

팀이 인터넷에서 쓰도록 올릴 때의 구성입니다. 화면과 API 가 한 Vercel 프로젝트, 한 도메인에서 돌고(`vercel.json` 의 Services), 데이터는 Supabase 의 PostgreSQL 과 Storage 에 둡니다.

배포 자격증명은 이 공개 레포에 두지 않습니다. 이 레포를 `upstream` 으로 따르는 비공개 레포를 하나 만들고, 그 레포에 Vercel 과 Supabase 를 연결합니다. 코드 파일은 고치지 않고 `git pull upstream main` 으로 따라갑니다.

### 1. Supabase

- 프로젝트를 만듭니다. 리전은 사용자와 가까운 곳(한국이면 서울)으로 고릅니다.
- Storage 에 비공개 버킷을 만들고 파일 크기 상한을 50MB 로 둡니다. 서명 업로드 주소는 크기를 강제하지 않으므로 버킷 상한이 마지막 방어선입니다.
- 접속 주소 두 개를 확인합니다. 앱은 트랜잭션 풀러 주소, 마이그레이션은 직결(또는 세션 풀러) 주소를 씁니다.

### 2. Vercel

- 비공개 레포로 프로젝트를 만듭니다. 설정은 레포의 `vercel.json` 을 그대로 씁니다.
- 운영(Production)의 Git 자동 배포를 끕니다. 배포는 GitHub Actions 가 마이그레이션 뒤에 합니다.
- 환경변수(Production, Preview 둘 다):

| 이름 | 값 |
|---|---|
| `DATABASE_URL` | Supabase 트랜잭션 풀러 주소 (`postgresql+psycopg2://...:6543/postgres`) |
| `SECRET_KEY` | 긴 무작위 문자열 |
| `ENV` | `production` |
| `STORAGE_BACKEND` | `supabase` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_BUCKET` | Supabase 프로젝트 주소, 서비스 키, 버킷 이름 |
| `CRON_SECRET` | 긴 무작위 문자열. 매일 정리 작업(`/api/internal/cron/daily`) 인증 |
| `TRUSTED_PROXY_HEADER` | 플랫폼이 덮어쓰는 클라이언트 IP 헤더. 스테이징에서 확인해 정합니다 |

Preview 는 합성 데이터만 든 별도 Supabase 프로젝트에 연결합니다.

### 3. GitHub Actions (비공개 레포)

- 저장소 변수 `DEPLOY_ENABLED` 를 `true` 로 둡니다. 공개 레포에서는 배포·백업 워크플로가 돌지 않습니다.
- 비밀값: `DATABASE_URL_DIRECT`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, 백업용 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_BUCKET`.
- `main` 에 푸시하면 테스트, 운영 DB 마이그레이션, Vercel 배포 순서로 돕니다(`.github/workflows/deploy.yml`). 매일 DB 덤프와 Storage 객체를 아티팩트로 남깁니다(`backup.yml`, 14일 보관).

## 주요 기능

| 기능 | 설명 |
|---|---|
| 스프레드시트 TC 편집 | ag-grid 기반 인라인 편집, 다중 행 추가, 벌크 삭제 |
| 시트 트리 구조 | N-depth 계층형 Test Suite 관리, 그 자리에서 이름 변경 |
| 커스텀 필드 | text, number, select, multiselect, checkbox, date |
| 테스트 런 | 실행 결과 기록, 진행률 추적, 재실행 |
| 테스트 플랜 | 릴리즈 단위 수행 관리, 마일스톤별 진행률 |
| 대시보드 | 프로젝트별 통계 차트 (Chart.js), 회차 간 결과가 바뀐 TC 를 찾는 TC 안정성 표 |
| 리포트 | 웹 · PDF · 엑셀. 우선순위별 · 분류별 PASS Rate, 직전 수행 대비 퇴보/개선, 실패·차단 항목 |
| 이슈 관리 도구 연동 | Jira, Linear 주소 설정. 이슈 키를 테스트 수행 시트와 리포트에서 링크 |
| 고급 필터 | AND/OR 다중 조건, 필터 저장/불러오기 |
| Import/Export | Excel(xlsx), Jira CSV, Markdown |
| 자동화 결과 가져오기 | Playwright JSON · JUnit XML 결과를 테스트 런에 기록 (미리보기 후 적용). CI 용 CLI `scripts/ymtc-upload.mjs` 는 수행 이름만으로 다음 회차를 만들어 올림 |
| API 키 | 스크립트 · CI 용 사용자별 키, Bearer 인증, 발급 · 폐기 |
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
| Backend | Python 3.11 ~ 3.14, FastAPI, SQLAlchemy, PostgreSQL 17 |
| Test | Vitest 570+ (프론트 단위), pytest 730+ (백엔드 API·보안·통합), Playwright 99 (E2E) |
| Deploy | 셀프호스팅 (로컬 실행) 또는 Vercel + Supabase |

## 테스트

테스트에는 실행용 의존성 외에 테스트 전용 패키지가 추가로 필요합니다.

```bash
# 테스트 의존성 설치 (최초 1회)
cd backend && pip install -r requirements-dev.txt
cd ../frontend && npx playwright install chromium
```

```bash
# Frontend 단위 테스트
cd frontend && npm run test

# Backend 테스트. 로컬 PostgreSQL 이 떠 있어야 한다. 세션마다 임시 DB 를 만들고 지운다.
# 테스트용 서버는 8009 에 따로 띄운다(8008 개발 서버를 건드리지 않는다)
docker compose up -d --wait db
cd backend && TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 python -m pytest -q

# E2E 테스트 (서버 실행 상태에서)
cd frontend && npx playwright test
```

## 프로젝트 구조

```
ym-testcase/
├── backend/          # FastAPI 백엔드
│   ├── main.py       # 앱 엔트리포인트
│   ├── models.py     # SQLAlchemy 모델
│   ├── routes/       # API 라우터 (17 모듈)
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

AGPL-3.0 - [GNU Affero General Public License v3.0](LICENSE)

## 만든 사람

| 역할 | 담당 |
|------|------|
| 제품 기획 및 UI 테스트 | **sym804** |
| 풀스택 구현 및 자동화 테스트 | **Claude Code** |
