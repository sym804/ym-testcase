# Contributing to YM TestCase

YM TestCase에 기여해주셔서 감사합니다!
이 문서는 프로젝트에 기여하기 위한 가이드입니다.

## 시작하기

### 개발 환경 설정

```bash
# 1. 레포 클론
git clone https://github.com/sym804/ym-testcase.git
cd ym-testcase

# 2. 백엔드 설정
cd backend
cp .env.example .env          # SECRET_KEY 설정
pip install -r requirements.txt

# 3. 프론트엔드 설정
cd ../frontend
npm install

# 4. 서버 실행
cd ..
bash run_dev.sh                # Mac/Linux
# 또는
run_dev.bat                    # Windows
```

- 백엔드: http://localhost:8008 (8000 아님)
- 프론트엔드: http://localhost:5173
- API 문서: http://localhost:8008/docs

### 첫 번째 사용자

서버 최초 실행 후 회원가입한 첫 번째 사용자가 자동으로 Admin 역할을 부여받습니다.

## 코드 컨벤션

### Frontend (TypeScript / React)

- TypeScript strict mode
- 함수형 컴포넌트 + Hooks
- 파일명: PascalCase (컴포넌트), camelCase (유틸리티)
- CSS: 인라인 스타일 객체 (CSS-in-JS)
- 빌드 전 반드시 `npx tsc --noEmit` 통과

### Backend (Python / FastAPI)

- Python 3.12
- FastAPI + Pydantic 2 스키마
- SQLAlchemy 2 ORM
- 함수명/변수명: snake_case
- 라우트 파일: `backend/routes/` 아래 모듈별 분리

## 브랜치 규칙

```
master          ← 릴리즈 브랜치 (항상 안정 상태)
feature/xxx     ← 기능 개발
fix/xxx         ← 버그 수정
```

- `master`에 직접 push하지 마세요. PR을 통해 머지합니다.
- 브랜치명은 영문 소문자 + 하이픈 (예: `feature/markdown-import`)

## 커밋 메시지

한글 커밋 메시지를 사용합니다.

```
[타입] 요약 (한 줄)

상세 설명 (필요 시)
```

**타입:**
- `기능`: 새 기능 추가
- `수정`: 버그 수정
- `개선`: 리팩토링, 성능 개선
- `문서`: 문서 수정 (README, 매뉴얼 등)
- `테스트`: 테스트 추가/수정
- `보안`: 보안 관련 수정

**예시:**
```
기능: Markdown(.md) 파일 Import 지원

# 헤딩 → 시트명, Markdown 테이블 파싱, HEADER_MAP 재활용.
백엔드 _parse_md_tables + 프론트 accept 확장 + 매뉴얼 추가.
```

## Pull Request

### PR 제출 전 체크리스트

- [ ] TypeScript 타입 체크 통과 (`cd frontend && npx tsc --noEmit`)
- [ ] ESLint 통과 (`cd frontend && npx eslint src/ --quiet`)
- [ ] Vitest 통과 (`cd frontend && npx vitest run`) — 358+ 테스트
- [ ] Playwright E2E 통과 (`cd frontend && npx playwright test`) — 93+ 테스트
- [ ] pytest 통과 (`cd backend && pytest test_security.py -q`) — 116+ 테스트
- [ ] **전체 567+ 테스트 ALL PASS**
- [ ] 새 기능이면 테스트 추가
- [ ] 사용자 매뉴얼 업데이트 (해당 시)

### PR 제목 형식

```
[타입] 요약
```

예: `[기능] Markdown Import 지원`, `[수정] 대시보드 차트 다크모드 색상`

## 이슈 등록

GitHub Issues에서 템플릿을 선택하여 등록합니다.

### 템플릿 종류

| 템플릿 | 용도 | 제목 접두사 |
|--------|------|-------------|
| 버그 리포트 | 기능 오류, UI 문제 | `[BUG]` |
| 개선 요청 | 기능 개선, UX 향상 | `[ENH]` |
| 보안 이슈 | 보안 취약점 | `[SEC]` |

### 심각도 기준

| 심각도 | 기준 |
|--------|------|
| **Block** | 서비스 전체 장애, 아무것도 못하는 상태 |
| **Critical** | 핵심 기능 마비, 다른 작업은 가능 |
| **Major** | 주요 기능 오류, 중요 UI 문제 |
| **Minor** | 사소한 기능 오류, 경미한 UI 문제 |
| **Trivial** | 기능 무관한 외관/텍스트 |

> 보안 이슈는 최소 Minor, DB 관련은 최소 Major, 개선 요청은 Major/Minor/Trivial만 사용합니다.

### 영역 분류

| 영역 | 대상 |
|------|------|
| **Frontend** | TSX 컴포넌트, UI/UX, 빌드, E2E |
| **Backend** | API, 비즈니스 로직, 인증/권한 |
| **DB** | 테이블, 마이그레이션, 쿼리 최적화 |
| **보안** | 인증, 크레덴셜, CORS, CSRF |
| **기타** | 문서, 설정, 스크립트 |

## 테스트

### 테스트 실행

```bash
# 전체 테스트
cd frontend && npx tsc --noEmit      # TypeScript
cd frontend && npx vitest run         # Unit (358)
cd frontend && npx playwright test    # E2E (93)
cd backend && pytest test_security.py -q  # API (116)
```

### 테스트 작성 규칙

- 새 기능에는 반드시 테스트를 추가합니다.
- 백엔드: `backend/test_*.py`에 pytest 테스트
- 프론트 유닛: `frontend/src/test/`에 Vitest 테스트
- E2E: `frontend/e2e/`에 Playwright 테스트
- 테스트 중 변경한 비밀번호/DB 데이터는 반드시 원복합니다.
- Rate limit 주의: 로그인 실패 10회 시 5분 잠금 (서버 재시작으로 해제)

## 버전 체계

`system.feature.fix.patch` 형식입니다.

| 자리 | 의미 | 예시 |
|------|------|------|
| system | 아키텍처 변경 | 0 → 1 |
| feature | 기능 추가 | 시트 트리, 커스텀 필드 |
| fix | 중요 수정 | 빌드 실패, 보안 취약점 |
| patch | 경미한 수정 | 오타, 색상 조정 |

컴포넌트(Frontend/Backend/Database)별 독립 버전을 사용합니다.
자세한 내용은 `rules/versioning.md`를 참고하세요.

## 라이선스

이 프로젝트는 [AGPL-3.0](LICENSE) 라이선스입니다.
기여하신 코드는 동일한 라이선스가 적용됩니다.

## 문의

- GitHub Issues: 버그/개선/보안 이슈 등록
- 프로젝트 규칙: `rules/` 폴더 참고
