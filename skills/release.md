---
name: release
description: 릴리즈 준비 (검증 → 이슈 정리 → 릴리즈 노트 → GitHub 이슈 → 커밋 → 푸시)
---

새 버전 릴리즈를 준비합니다.
인자로 버전을 받습니다: `/release v0.8.0`

실행 순서:

1. **사전 검증**
   - TypeScript 타입 체크 (`npx tsc --noEmit`)
   - 전체 테스트 실행 (567+ ALL PASS 확인, FAIL 있으면 중단)
   - 프로덕션 빌드 성공 확인 (`npm run build`)
   - Open 이슈 중 Block/Critical 없는지 확인

2. **버전 업데이트**
   - `backend/main.py`의 version 필드 갱신
   - `frontend/package.json`의 version 필드 갱신
   - 컴포넌트별 버전 테이블 갱신 (`rules/versioning.md`)

3. **이슈 정리** (push 전 필수)
   - Issue_list.xlsx에 이번 버전 이슈 추가/업데이트
     - 새로 발견된 버그/개선 → 새 행 추가 (ID 자동 채번)
     - 수정 완료된 이슈 → 상태를 "완료"로, 수정 버전 기입
     - 영역(Frontend/Backend/DB/보안/기타) + 심각도(Block~Trivial) 설정
     - 재현 방법/개선 사항, 원인 및 수정/개선 사유 필수 입력
   - GitHub Issues 동기화
     - 엑셀에 새로 추가된 이슈 → `gh issue create` (라벨: 분류+영역+심각도)
     - 수정 완료된 이슈 → `gh issue close`
     - 엑셀 ↔ GitHub 개수 일치 확인

4. **릴리즈 노트 업데이트**
   - Release_note.md 최상단에 새 버전 추가
   - 컴포넌트별 버전 변경 테이블
   - 변경사항 분류 (신규 기능 / 버그 수정 / 보안 수정 / 개선 / 문서)

5. **커밋 & 푸시**
   - 변경 파일 스테이징 (소스 + Issue_list.xlsx + Release_note.md + rules/)
   - 커밋 메시지: `vX.X.X 릴리즈 (주요 변경 요약)`
   - 태그 생성: `git tag vX.X.X`
   - `git push origin master --tags`

순서 요약:
```
검증 → 버전 업 → 이슈 정리(엑셀+GitHub) → 릴리즈 노트 → 커밋 → 푸시
```

주의:
- 이슈 정리 없이 push 금지 — 엑셀/GitHub/릴리즈 노트 3곳 동기화 필수
- 릴리즈 전 모든 테스트 PASS 필수
- 사용자 매뉴얼 최신화 확인
- 테스트 데이터 정리 (비밀번호 원복 등)
