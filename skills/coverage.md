---
name: coverage
description: 테스트 자동화율 계산 + 리포트
---

현재 테스트 자동화율을 계산하여 보고합니다.

수집 항목:
1. Playwright E2E 테스트 수: `grep -c "test(" e2e/*.spec.ts`
2. Vitest 단위 테스트 수: `grep -rc "test(\|it(" src/test/`
3. Python API 테스트 수: pytest --collect-only 또는 테스트 파일의 check() 호출 수
4. 회귀 체크리스트 엑셀 (있는 경우): PASS/FAIL/N/A 건수

보고 형식:
| 구분 | 도구 | 수량 | 상태 |
|---|---|---|---|
| Frontend Unit | Vitest | 358 | — |
| E2E | Playwright | 93 | — |
| Backend API | pytest | 116 | — |
| **합계** | | **567** | — |

추가 정보:
- 테스트 파일 수 (frontend/src/test/, frontend/e2e/, backend/test_*.py)
- 마지막 테스트 실행 결과 (있는 경우)
