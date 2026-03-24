---
name: changelog
description: 변경사항 요약 생성 (git diff 기반)
---

최근 변경사항을 분석하여 변경 로그를 생성합니다.

실행:
1. `git diff --stat` + `git log --oneline -20` 분석
2. 변경된 파일을 카테고리별로 분류:
   - Frontend: components, pages, api, test
   - Backend: models, routes, schemas, auth
   - DB: models.py (테이블 변경), migrations
   - 보안: auth.py, CORS, CSRF 관련
   - 기타: README, rules, scripts, docs
3. 변경 요약 생성

출력 형식:
```
## vX.X.X 변경사항 (YYYY-MM-DD)

### 새 기능
- ...

### 버그 수정
- ...

### 개선
- ...

### 변경된 파일
- Frontend: N파일
- Backend: N파일
- DB: N파일

### 테스트
- Vitest: 358 PASS / Playwright: 93 PASS / pytest: 116 PASS
```
