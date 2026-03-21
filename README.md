# TC Manager

경량 테스트 케이스 관리 도구. TestRail/Kiwi TCMS 대안으로 설계된 셀프 호스팅 웹 애플리케이션.

## 주요 기능

- **스프레드시트 스타일 TC 편집** — ag-grid 기반 인라인 편집, 다중 행 추가, 벌크 삭제
- **시트 트리 구조** — N-depth 계층형 Test Suite 관리
- **커스텀 필드** — 프로젝트별 컬럼 정의 (text, number, select, multiselect, checkbox, date)
- **테스트 수행(Test Run)** — 실행 결과 기록, 진행률 추적, 다시 수행
- **테스트 플랜/마일스톤** — 릴리즈 단위 수행 관리, 마일스톤별 진행률
- **대시보드** — 프로젝트별 통계, 차트 (Chart.js)
- **Import/Export** — Excel(xlsx), Jira CSV, PDF 리포트
- **고급 필터 + 저장된 뷰** — AND/OR 다중 조건, 필터 저장/불러오기
- **역할 기반 접근 제어** — 시스템 역할(admin/qa_manager/user) + 프로젝트 역할(admin/tester/viewer)
- **보안** — JWT 인증, Rate Limiting, CORS, 비밀번호 bcrypt 해싱

## 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | React 19, TypeScript, Vite, ag-grid, Chart.js |
| Backend | Python 3.12, FastAPI, SQLAlchemy, SQLite |
| Test | Vitest, Playwright, pytest |
| Deploy | Docker Compose, Nginx |

## 빠른 시작

### 사전 요구사항

- Python 3.12+
- Node.js 20+

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/tc-manager.git
cd tc-manager
```

### 2. 환경 설정

```bash
cp .env.example .env
# .env 파일에서 SECRET_KEY 등 설정
```

### 3. 백엔드 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8008
```

### 4. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

### 5. 접속

- Frontend: http://localhost:5173
- Backend API: http://localhost:8008
- API Docs (Swagger): http://localhost:8008/docs

> 첫 번째로 가입하는 사용자가 자동으로 **admin** 권한을 받습니다.

## Docker로 실행

```bash
# 환경변수 설정
cp .env.example .env
# SECRET_KEY를 반드시 변경하세요!

docker compose up -d
```

- Frontend: http://localhost (포트 80)
- Backend API: http://localhost:8008

## 테스트

```bash
# Backend API 테스트
cd backend
python -m pytest test_security.py -v

# Frontend 단위 테스트
cd frontend
npm run test

# E2E 테스트
cd frontend
npx playwright test
```

## 프로젝트 구조

```
tc-manager/
├── backend/          # FastAPI 백엔드
│   ├── main.py       # 앱 엔트리포인트
│   ├── models.py     # SQLAlchemy 모델
│   ├── routes/       # API 라우터
│   └── Dockerfile
├── frontend/         # React 프론트엔드
│   ├── src/
│   │   ├── pages/    # 페이지 컴포넌트
│   │   ├── components/
│   │   └── api/      # API 클라이언트
│   ├── e2e/          # Playwright E2E 테스트
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## 라이선스

MIT License
