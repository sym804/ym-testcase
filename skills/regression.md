---
name: regression
description: 회귀 테스트 전체 수행 + 결과 보고
---

전체 회귀 테스트를 수행하고 결과를 보고합니다.

실행 순서:
1. 서버 상태 확인 (없으면 시작)
2. TypeScript 타입 체크
3. Vitest 단위 테스트 실행 (358개)
4. Python API 테스트 실행 (116개, 서버 실행 필요)
5. Playwright E2E 테스트 실행 (93개)
6. 결과 수집 + 요약 보고

보고 형식:
| 구분 | 전체 | PASS | FAIL | 결과 |
|---|---|---|---|---|
| TypeScript | - | - | - | PASS/FAIL |
| Vitest | 358 | X | X | — |
| pytest | 116 | X | X | — |
| Playwright | 93 | X | X | — |
| **합계** | **567** | **X** | **X** | — |

주의:
- rate limit 방지를 위해 테스트 간 서버 재시작 필요할 수 있음
- 테스트 후 비밀번호 등 변경사항 반드시 원복
- FAIL 발생 시 Issue_list.xlsx에 이슈 등록 권고
