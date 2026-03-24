---
name: api-test
description: 특정 API 엔드포인트 빠른 테스트
---

인자로 받은 API 엔드포인트를 빠르게 테스트합니다.
예: `/api-test POST /api/projects`
예: `/api-test GET /api/projects/1/testcases`

실행:
1. 서버 상태 확인 (localhost:8008)
2. admin으로 로그인하여 세션 쿠키 획득 + CSRF 토큰 설정
3. 인자로 받은 METHOD + URL로 API 호출
4. 응답 상태 코드, 헤더, 바디 출력
5. JSON인 경우 pretty print

인자 형식:
- `METHOD URL` — 기본 호출
- `METHOD URL '{"key":"value"}'` — 바디 포함
- URL만 입력 시 GET으로 처리

주의:
- 프로젝트 ID가 필요한 엔드포인트는 실제 존재하는 ID 사용
- 비밀번호는 환경변수 TEST_ADMIN_PASSWORD 사용 (기본값: test1234)
- CSRF 토큰: 로그인 후 csrf_token 쿠키를 X-CSRF-Token 헤더로 전달
