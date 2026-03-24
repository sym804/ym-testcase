# 릴리즈 프로세스 규칙

## 릴리즈 노트 작성 원칙

### 구조

각 릴리즈 항목에 반드시 포함할 내용:

1. **버전 + 날짜 + 요약 제목**
2. **컴포넌트별 버전 변경 테이블** (이전 → 이후, 변경 사유)
3. **컴포넌트별 변경사항** (Frontend / Backend / Database 구분)
4. **변경 파일 목록** (주요 변경 시)

### 변경사항 분류

| 분류 | 설명 |
|---|---|
| 신규 기능 | 새로 추가된 기능 |
| 버그 수정 | 기존 기능의 오류 수정 |
| 보안 수정 | 보안 취약점 수정 |
| 개선 | 성능, UX, 코드 품질 개선 |
| 문서 | 매뉴얼, 가이드, README |

## 릴리즈 체크리스트

배포 전 확인 사항:

### Frontend
- [ ] TypeScript 컴파일 통과 (`npx tsc --noEmit`)
- [ ] Vite 프로덕션 빌드 통과 (`npm run build`)
- [ ] Vitest 단위 테스트 전체 통과 (`npx vitest run`) — 현재 358개
- [ ] Playwright E2E 테스트 전체 통과 (`npx playwright test`) — 현재 93개
- [ ] 주요 화면 스모크 테스트 (로그인 → 프로젝트 목록 → TC 탭 → 테스트 수행)

### Backend
- [ ] 서버 정상 시작 확인 (`uvicorn main:app --port 8008`)
- [ ] pytest 전체 통과 (`pytest test_security.py`) — 현재 116개
- [ ] 핵심 API 스모크 테스트 (로그인, TC 조회, 런 생성, 결과 저장)

### Database
- [ ] DB 마이그레이션 적용 확인 (해당 시)
- [ ] 기존 데이터 정합성 확인 (스키마 변경 시)

### 이슈 정리 (push 전 필수)
- [ ] Issue_list.xlsx에 이번 버전 이슈 추가/업데이트
- [ ] 재현 방법/개선 사항 + 원인 및 수정/개선 사유 빈 셀 없는지 확인
- [ ] GitHub Issues 동기화 (새 이슈 create, 완료 이슈 close)
- [ ] 엑셀 ↔ GitHub 이슈 개수 일치 확인

### 공통
- [ ] Open 이슈 중 Block/Critical 없는지 확인
- [ ] 보안 이슈 중 Major 이상 미해결 여부 재확인
- [ ] 롤백 계획 수립 (이전 버전 복구 절차 확인)
- [ ] Release_note.md 최상단에 새 버전 추가
- [ ] 컴포넌트별 버전 번호 갱신 (rules/versioning.md)

### 커밋 & 푸시
- [ ] 변경 파일 스테이징 (소스 + Issue_list.xlsx + Release_note.md + rules/)
- [ ] 커밋 메시지: `vX.X.X 릴리즈 (주요 변경 요약)`
- [ ] 태그 생성: `git tag vX.X.X`
- [ ] `git push origin master --tags`

### 배포 후
- [ ] 운영 환경 스모크 테스트
- [ ] 로그 모니터링 (에러 발생 여부)
- [ ] 이슈 상태 Released로 일괄 전환

## 테스트 현황 (v1.0.0.0 기준)

| 구분 | 도구 | 수량 | 대상 |
|---|---|---|---|
| Frontend Unit | Vitest | 358 | 23개 테스트 파일, 컴포넌트/API/유틸리티 |
| E2E | Playwright | 93 | 9개 스펙 파일, 인증/TC/시트/커스텀 필드 |
| Backend API | pytest | 116 | 보안/기능/엣지 케이스 통합 테스트 |
| **합계** | | **567** | **100% PASS** |

## 롤백 절차

1. 이전 버전 Frontend 빌드 파일 복원
2. 이전 버전 Backend 코드 복원
3. DB 롤백 (스키마 변경 시 — 백업에서 복원)
4. 서버 재시작
5. 스모크 테스트로 롤백 확인

## 관리 파일

- `Release_note.md` — 전체 릴리즈 이력
- `Issue_list.xlsx` — 이슈 추적 (94건, GitHub 동기화)
- `rules/versioning.md` — 버전 체계
- `rules/issue_management.md` — 이슈 관리 규칙
