---
name: db-backup
description: DB 파일 백업 (타임스탬프 포함)
---

현재 DB 파일을 타임스탬프 포함 이름으로 백업합니다.

실행:
1. `backend/tc_manager.db` 파일 존재 확인
2. 복사: `backend/tc_manager.db` → `backend/backups/tc_manager_{YYYYMMDD_HHMMSS}.db`
3. backups/ 폴더 없으면 자동 생성
4. 백업 파일 크기와 경로 보고
5. 기존 백업 목록 표시 (최근 5개)

주의:
- 서버 실행 중에도 안전하게 복사 가능 (SQLite WAL 모드)
