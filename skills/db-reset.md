---
name: db-reset
description: DB 초기화 + 마이그레이션 + 시드 데이터
---

개발용 DB를 깨끗한 상태로 초기화합니다.

실행 순서:
1. 서버가 실행 중이면 경고 (DB 잠금 방지)
2. 기존 DB 파일 백업: `backend/tc_manager.db` → `backend/tc_manager.db.bak.{timestamp}`
3. 기존 DB 파일 삭제
4. 서버 시작하여 create_all + 마이그레이션 자동 실행 (lifespan)
5. admin 계정 생성 확인 (없으면 안내)

주의:
- 실행 전 반드시 사용자에게 확인 ("DB를 초기화하면 모든 데이터가 삭제됩니다")
- 백업 파일은 backend/ 폴더에 보관
- 비밀번호는 사용자가 직접 설정하도록 안내
