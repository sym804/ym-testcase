---
name: capture
description: 매뉴얼 스크린샷 재캡처 (Playwright)
---

UserManualPage에 사용되는 스크린샷을 Playwright로 재캡처합니다.

실행:
1. 서버 시작 (rate limit 초기화를 위해 재시작)
2. `cd frontend && npx playwright test e2e/capture-manual-images.spec.ts --retries=0`
3. 캡처된 이미지 목록 보고 (frontend/public/manual-images/)

캡처 대상:
- 01~03: 로그인/회원가입
- 04~06: 프로젝트 목록/생성
- 07~08: TC 관리/그리드
- 09~11: 테스트 수행/결과
- 13~15: 대시보드/차트
- 17: 설정
- 19~21: 검색/다크모드
- 23: TC 툴바
- 30~35: 시트 트리, 커스텀 필드, 고급 필터, 테스트 플랜

주의:
- admin 비밀번호가 캡처 스크립트와 일치해야 함
- 캡처 스크립트: e2e/capture-manual-images.spec.ts
- 뷰포트: 1280x800
- 캡처 후 비밀번호 원복 확인
