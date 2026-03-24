---
name: build-check
description: 빌드 + 타입체크 + 린트 한번에 실행
---

코드 변경 후 빠른 검증을 위해 빌드/타입/린트를 한번에 실행합니다.

실행 순서:
1. `cd frontend && npx tsc --noEmit` — TypeScript 타입 체크
2. `cd frontend && npx eslint src/ --quiet` — ESLint 린트
3. `cd frontend && npm run build` — Vite 프로덕션 빌드
4. Python 문법 체크: `cd backend && python -m py_compile main.py models.py schemas.py`

각 단계 PASS/FAIL 결과 요약 보고.
실패 시 에러 메시지 포함.
