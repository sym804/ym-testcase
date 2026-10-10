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

#### SQLite 버전(v1.10.3.1 이하)에서 올라올 때

2.0 부터 DB 가 PostgreSQL 입니다. `git pull` 전에 Docker 를 설치하세요. `backend/.env` 의 `DATABASE_URL` 이 `sqlite:///` 이면 서버가 시작하지 않습니다.

SQLite 를 계속 쓰려면 `git checkout sqlite-legacy` 로 옛 버전에 머뭅니다. 이 브랜치는 더 고치지 않습니다.

기존 데이터를 옮기는 순서입니다. 원본 SQLite 와 `backend/uploads/` 는 지우지 않습니다.

1. 서버를 내리고 `backend/tc_manager.db` 와 `backend/uploads/` 를 따로 복사해 둡니다
2. `docker compose up -d --wait db` 로 PostgreSQL 을 띄우고, `backend/.env` 의 `DATABASE_URL` 을 `.env.example` 의 PostgreSQL 주소로 바꿉니다
3. 빈 스키마를 만들고 먼저 점검만 합니다(`--dry-run` 은 아무것도 남기지 않습니다)

```bash
cd backend && python -m alembic upgrade head && cd ..
python scripts/migrate_sqlite_to_pg.py --source backend/tc_manager.db \
  --target postgresql+psycopg2://ymtc:ymtc@127.0.0.1:54329/ymtc --uploads backend/uploads --dry-run
```

4. 통과하면 `--dry-run` 을 빼고 `--storage local` 을 붙여 다시 실행합니다. 첨부는 `backend/uploads/attachments/` 에 복사됩니다. 이미 지워진 TC 를 가리키는 이력 같은 고아 행이 있으면 스크립트가 목록을 내고 멈춥니다. 옮기지 않아도 되는 행이면 `--allow-orphan 테이블:id` 로 제외하고, 제외한 행은 `excluded_rows.json` 에 남습니다
5. 옛 서버(SQLite 버전)와 새 서버를 같이 띄우고 응답을 비교합니다. 프로젝트 목록, 대시보드, 리포트가 모두 같아야 합니다

```bash
CMP_PASSWORD=<관리자 비밀번호> python scripts/compare_api.py --a <옛 서버 주소> --b <새 서버 주소> --username admin
```

Supabase 로 옮길 때는 `--target` 에 직결 또는 세션 풀러 주소를 쓰고 `--storage supabase` 를 붙입니다. 직결 주소가 IPv6 로만 열리는 네트워크라면 세션 풀러(5432) 주소를 씁니다. `SUPABASE_URL` 의 프로젝트가 `--target` 과 다르면 스크립트가 멈춥니다.

## 배포 (Vercel + Supabase)

팀이 인터넷에서 쓰도록 올릴 때의 구성입니다. 화면과 API 가 한 Vercel 프로젝트, 한 도메인에서 돌고(`vercel.json` 의 Services), 데이터는 Supabase 의 PostgreSQL 과 Storage 에 둡니다. 절차는 용도에 따라 두 가이드로 나눴습니다.

- [공개 배포 가이드](docs/deploy_public.md): 이 레포를 fork 해 개인이나 소규모 팀이 자기 계정에 올립니다. Vercel Git 연동으로 배포하고 마이그레이션은 PC 에서 돌립니다
- [회사 배포 가이드](docs/deploy_company.md): 이 레포를 `upstream` 으로 따르는 회사 비공개 레포에서 GitHub Actions 로 배포합니다. CI 통과, 운영 DB 마이그레이션, 배포가 자동으로 이어지고 매일 백업이 남습니다. Google Workspace 계정과 가입 승인을 씁니다

Vercel Git 연동에서 Preview 배포를 쓰려면 합성 데이터만 든 별도 Supabase 프로젝트를 Preview 환경변수에 연결합니다. 스키마를 바꾸는 브랜치의 Preview 는 그 DB 에 직접 마이그레이션한 뒤 확인합니다. 올리기 전에는 API 가 503(스키마가 코드보다 옛 버전)을 냅니다. 회사 배포 가이드처럼 Git 에 연결하지 않으면 Preview 배포는 생기지 않습니다.

```bash
cd backend
DATABASE_URL=<Preview DB 세션 풀러 주소> DATABASE_URL_DIRECT=<같은 주소> python -m alembic upgrade head
```

### 로그인 정책 (Google 로그인, 가입 승인)

들어올 수 있는 사람은 환경변수 셋으로 정합니다. `backend/.env.example` 에 선택지가 모두 적혀 있고 기본값만 켜져 있습니다.

- `AUTH_COMPANY_DOMAINS`: 회사 도메인(쉼표로 여러 개). Google Workspace 도메인(`hd`)으로 회사 계정을 판정합니다. 이메일 끝자리로는 판정하지 않습니다.
- `AUTH_ALLOW_PERSONAL`: `1` 이면 개인 메일도 받고, `0` 이면 회사 계정만 받습니다.
- `AUTH_APPROVAL`: `none`(모두 바로 사용, 기본값), `personal`(회사 Google 계정만 바로, 나머지는 관리자 승인 후), `all`(모두 승인 후).

기본값은 누구나 가입해 바로 쓰는 설정입니다. 회사 배포는 `AUTH_APPROVAL=personal` 을 권합니다. 이메일 가입은 주소를 확인하지 않으므로, 회사 계정만 받는 설정(`AUTH_ALLOW_PERSONAL=0`)에서는 승인 설정과 상관없이 항상 승인 대기입니다.

Google 로그인을 켜려면 Google Cloud 콘솔에서 OAuth 클라이언트를 만듭니다.

1. Google 인증 플랫폼에서 대상을 **외부**로 두고 앱 이름과 지원 이메일을 넣습니다. 로고를 올리면 브랜드 심사를 받아야 하므로 비워 둡니다. 회사 Workspace 의 Cloud 프로젝트에서 사내 계정만 받으려면 **내부**로 둡니다(회사 배포 가이드 4절).
2. 클라이언트를 **웹 애플리케이션**으로 만들고 승인된 리디렉션 URI 에 `https://<도메인>/api/auth/google/callback` 을 넣습니다. 로컬 개발은 `http://localhost:5173/api/auth/google/callback` 입니다. 화면이 여는 시작 주소와 리디렉션 URI 는 같은 호스트여야 합니다. 프론트를 다른 도메인의 백엔드(`VITE_API_URL`)에 붙이면 확인 쿠키가 콜백에 실리지 않아 Google 로그인이 항상 실패합니다.
3. 클라이언트 ID 와 보안 비밀을 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` 에, 리디렉션 URI 를 `GOOGLE_REDIRECT_URI` 에 넣습니다. 보안 비밀은 만들 때 한 번만 보입니다.
4. 팀에 열기 전에 게시 상태를 **프로덕션**으로 바꿉니다. 테스트 상태에서는 테스트 사용자로 등록한 계정만 로그인됩니다.

기존 아이디 계정은 그대로 로그인되고, 로그인한 뒤 사용자 메뉴의 **계정 연결**에서 Google 계정을 붙일 수 있습니다. 이메일이 같다고 자동으로 잇지 않습니다.

퇴사자는 Workspace 계정을 지워도 앱의 로그인(최대 30일)과 API 키가 남습니다. 관리 화면에서 **사용 중지**해야 바로 막힙니다.

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
