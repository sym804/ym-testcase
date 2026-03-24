---
name: status
description: 프로젝트 현황 (서버 상태, TC 수, 테스트 현황, 버전)
---

YM TestCase 프로젝트의 현재 상태를 한눈에 보여줍니다.

수집 항목:
1. **서버 상태**
   - Backend (localhost:8008): UP/DOWN
   - Frontend (localhost:5173): UP/DOWN

2. **코드 현황**
   - Backend 파일 수 / 라인 수
   - Frontend 파일 수 / 라인 수
   - 마지막 수정 파일 + 시각

3. **DB 현황**
   - DB 파일 크기
   - 프로젝트 수, TC 수, TestRun 수, 사용자 수

4. **테스트 현황**
   - Vitest 단위: 358개
   - Playwright E2E: 93개
   - Python API: 116개
   - 합계: 567개

5. **이슈 현황**
   - Issue_list.xlsx 전체/미해결 건수
   - 심각도별 분포 (Block/Critical/Major/Minor/Trivial)

6. **버전 정보**
   - 현재 System / Frontend / Backend / Database 버전
   - 라이선스: AGPL-3.0

출력은 간결한 테이블 형태로.
