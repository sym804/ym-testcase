---
name: test
description: 전체 테스트 실행 (Vitest 358 + pytest 116 + Playwright 93 = 567)
---

YM TestCase 전체 테스트 스위트를 순차 실행합니다.

실행 순서:
1. TypeScript 타입 체크: `cd frontend && npx tsc --noEmit`
2. Vitest 단위 테스트: `cd frontend && npx vitest run` (358개)
3. Python API 테스트: `cd backend && pytest test_security.py -q` (116개, 서버 실행 필요)
4. Playwright E2E: `cd frontend && npx playwright test` (93개, 서버 자동 시작)

각 단계 결과를 요약하여 보고:
- PASS/FAIL 수
- 실패한 테스트 이름과 원인
- 전체 소요 시간

인자 지원:
- `/test unit` — Vitest만
- `/test api` — Python API만
- `/test e2e` — Playwright만
- `/test type` — TypeScript 타입 체크만
- 인자 없으면 전체 실행 (목표: 567/567 ALL PASS)

주의:
- 테스트 후 비밀번호/DB 데이터 변경 시 반드시 원복
- rate limit: 로그인 실패 10회 시 5분 잠금 (서버 재시작으로 해제)
