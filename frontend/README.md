# YM TestCase — Frontend

React 19 + TypeScript + Vite 기반 프론트엔드.

전체 프로젝트 설명은 [루트 README](../README.md)를 참고하세요.

## 개발 서버

```bash
npm install
npm run dev          # → http://localhost:5173
```

## 테스트

```bash
npm run test         # Vitest 단위 테스트 (357 tests)
npx playwright test  # E2E 테스트
```

## 빌드

```bash
npm run build        # dist/ 디렉토리에 빌드 결과 생성
```

## 주요 의존성

- **ag-grid** — 스프레드시트 스타일 그리드
- **Chart.js** — 대시보드 차트
- **React Router** — SPA 라우팅
- **Zustand** — 상태 관리
