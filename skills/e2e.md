---
name: e2e
description: Playwright E2E 테스트 실행 (rate limit 방지 서버 재시작 포함)
---

Playwright E2E 테스트를 안전하게 실행합니다.

실행 순서:
1. 기존 Python 서버 프로세스 종료 (rate limit 초기화)
2. 3초 대기
3. `cd frontend && npx playwright test` 실행 (webServer 설정으로 자동 시작)
4. 결과 요약 보고

인자 지원:
- `/e2e` — 전체 E2E 실행
- `/e2e auth` — auth.spec.ts만
- `/e2e v060` — v060-features.spec.ts만
- `/e2e regression` — regression-full.spec.ts만
- `/e2e capture` — 매뉴얼 스크린샷 캡처

주의:
- Playwright config에서 서버를 자동 시작하므로 수동 시작 불필요
- `reuseExistingServer: true`이므로 이미 실행 중이면 재사용
- admin 비밀번호가 테스트 코드와 일치하는지 확인 필요
