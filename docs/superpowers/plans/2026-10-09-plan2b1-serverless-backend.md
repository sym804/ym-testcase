# 계획 2b-1: 서버리스 준비 (백엔드) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 백엔드가 Vercel 서버리스(디스크 휘발, 요청 본문 4.5MB, 여러 인스턴스)와 Supabase(Storage, RLS)에서 동작한다. 로컬은 지금처럼 디스크로 동작한다.

**Architecture:** 파일은 `services/storage.py` 의 두 구현(로컬 디스크, Supabase Storage REST) 중 하나로 다룬다. 업로드는 "스테이징" 세 단계(주소 발급 → 클라이언트가 직접 올림 → 처리 요청에 `upload_id`)로 바꾸되 기존 multipart 도 받는다. 기동 훅에 있던 정리 작업은 Cron 엔드포인트로, 마이그레이션 불일치는 503 으로 드러낸다.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, 표준 라이브러리 `urllib`(Storage REST, 새 의존성 없음), python-jose(로컬 업로드 토큰).

**Spec:** `docs/superpowers/specs/2026-10-08-postgresql-vercel-supabase-design.md` (배포 구조, 파일 저장, Supabase 보안, 배포 순서와 스키마 절)

## Global Constraints

- 작업 위치: worktree `tc_manager-pg`, 브랜치 `feat/postgresql`. 계획 1, 2a 위에 쌓는다.
- 기존 상한 유지: 첨부 50MB, TC 가져오기 10MB, 자동화 결과 20MB.
- 기존 multipart 업로드 API 는 하위 호환으로 남긴다(작은 파일, 외부 스크립트).
- Storage 서비스 키(`SUPABASE_SERVICE_ROLE_KEY`)는 서버에서만 쓴다. 응답·로그에 남기지 않는다.
- 새 Python 의존성 없음(표준 `urllib`).
- 커밋 직후 `git status` 로 미스테이징 0건 확인(2026-10-08 사고).

## Review Focus

- 스테이징 업로드의 소유권: 다른 사용자가 만든 `upload_id` 를 가로채 처리하거나 첨부로 붙일 수 없어야 한다. Task 2 테스트가 고정한다.
- 선언한 크기와 실제 크기가 다른 업로드: 처리 단계에서 실제 크기로 다시 막아야 한다. Task 2, 3 테스트가 고정한다.
- 로컬 업로드 주소의 토큰 위조·재사용·만료. Task 2 테스트가 고정한다.
- 마이그레이션이 안 된 DB 에서 서버리스 기동: 조용히 500 이 아니라 503 과 이유. Task 6 테스트가 고정한다.
- Cron 엔드포인트 무인증·오인증·비밀값 미설정. Task 5 테스트가 고정한다.

---

### Task 1: Storage 서비스

**Files:** Create `backend/services/storage.py`, Test `backend/tests_unit/test_storage.py`

**Interfaces (Produces):**
- `get_storage() -> Storage`: `STORAGE_BACKEND=supabase` 면 Supabase, 아니면 로컬(기본, `UPLOAD_DIR` 또는 `backend/uploads`)
- `Storage.put(key: str, data: bytes, content_type: str | None) -> None`
- `Storage.read(key: str, max_bytes: int) -> bytes` (넘으면 `HTTPException(413)`)
- `Storage.size(key: str) -> int | None` (없으면 None)
- `Storage.delete(keys: list[str]) -> None` (없는 키는 무시)
- `Storage.upload_target(key: str, content_type: str | None) -> dict | None`: 클라이언트가 직접 올릴 주소. 로컬은 None(백엔드가 받는다)
- `Storage.download_url(key: str, filename: str, expires_sec: int = 60) -> str | None`: 서명 URL. 로컬은 None(백엔드가 스트리밍)
- 키 규칙: `[A-Za-z0-9/_.-]` 만, `..` 금지, 앞 `/` 금지. 어기면 `ValueError`

- [ ] 로컬 구현 테스트: put/read/size/delete 왕복, 키 검증(`../x`, `/abs`, 한글 거부), read 의 max_bytes 413, 모듈 임포트만으로 폴더를 만들지 않음
- [ ] Supabase 구현 테스트: 표준 라이브러리 `http.server` 로 가짜 Storage 를 띄워 요청 경로·메서드·헤더(`Authorization: Bearer <서비스 키>`, `apikey`)·본문을 단언한다. 서명 업로드 응답 `{"url": "/object/upload/sign/b/k?token=T"}` 를 `{"method": "PUT", "url": "<SUPABASE_URL>/storage/v1/object/upload/sign/b/k?token=T", "headers": {"content-type": ...}}` 로 바꾸는지, 서명 다운로드 `{"signedURL": ...}` 를 절대 주소로 바꾸고 `download=<파일명>` 을 붙이는지 본다
- [ ] 구현 후 통과, 커밋

### Task 2: 스테이징 업로드

**Files:** Create `backend/routes/uploads.py`, `backend/services/staged_upload.py`, `backend/alembic/versions/0004_staged_uploads.py`; Modify `backend/models.py`, `backend/main.py`; Test `backend/tests_unit/test_staged_upload.py`

**Interfaces (Produces):**
- 모델 `StagedUpload(id: str(32) PK, user_id FK, purpose: str(32), filename: str(255), content_type, declared_size: int, storage_key: str(512), created_at, consumed_at nullable)`
- `PURPOSE_LIMITS = {"attachment": 50MB, "tc_import": 10MB, "result_import": 20MB}`
- `POST /api/uploads` 본문 `{purpose, filename, size, content_type}` → `{upload_id, method, url, headers}`. 선언 크기가 상한을 넘으면 413. 로컬은 `url` 이 `/api/uploads/{id}/content?token=...`
- `PUT /api/uploads/{id}/content?token=` (로컬 전용): 토큰(만료 15분, upload_id·user_id 서명) 확인, 상한까지만 읽어 저장. 이미 올린 업로드는 409
- `consume(db, upload_id, user, purpose) -> (filename, content_type, bytes)`: 소유자·목적 확인, 실제 크기로 상한 재검사, `consumed_at` 기록. 가져오기용
- `claim_for_attachment(db, upload_id, user) -> (filename, content_type, size, storage_key)`: 바이트를 읽지 않고 `size()` 로 상한 확인, 키를 넘긴다
- 스테이징 키: `staging/{upload_id}/{안전한 파일명}`

- [ ] 테스트: 발급 → 로컬 PUT → consume 왕복, 다른 사용자 consume 403, 다른 목적 400, 두 번 consume 409, 선언은 작게 하고 실제로 크게 올리면 consume 413, 토큰 위조·만료 401, 상한 넘는 선언 413
- [ ] 구현 후 통과, 커밋

### Task 3: 세 업로드 경로가 upload_id 를 받는다, 첨부는 Storage 로

**Files:** Modify `backend/routes/attachments.py`, `backend/routes/testcases.py`(import, import/preview), `backend/routes/testruns.py`(results/import, import by name), `backend/routes/projects.py`, `backend/routes/testruns.py`(delete_testrun); Test `backend/tests_unit/test_upload_paths.py`

- 각 라우트는 `file: UploadFile | None = File(None)` 과 `upload_id: str | None = Form(None)`(또는 Query)를 받고 둘 중 정확히 하나를 요구한다(둘 다/둘 다 없음 400)
- 가져오기: `consume` 으로 바이트를 얻어 기존 파서에 넘긴다. 기존 파서가 `UploadFile` 을 받는 곳은 바이트 기반 진입점을 둔다
- 첨부: multipart 는 서버가 `storage.put` 으로 최종 키 `attachments/{uuid}{ext}` 에 저장, `upload_id` 는 스테이징 키를 그대로 `filepath` 로 쓴다(복사 없음). 확장자 검증은 두 경로 모두
- 다운로드: `download_url` 이 있으면 302, 없으면 로컬 파일 스트리밍(지금 동작)
- 삭제·프로젝트 삭제·수행 삭제: `storage.delete`
- `routes/attachments.py:21` 의 import 시점 `os.makedirs` 제거, `UPLOAD_DIR` 상수 사용처 제거

- [ ] 테스트: 세 경로 각각 multipart 와 upload_id 둘 다 동작, 둘 다/둘 다 없음 400, 첨부 다운로드(로컬 스트리밍), 첨부 삭제 시 객체 삭제, 확장자 거부가 upload_id 경로에도 적용
- [ ] 기존 첨부·가져오기 테스트 전부 통과, 커밋

### Task 4: /api/config

- `GET /api/config` (인증 불필요): `{"upload_limits": {"attachment": 52428800, "tc_import": 10485760, "result_import": 20971520}, "direct_upload": bool}`
- [ ] 테스트 후 구현, 커밋

### Task 5: Cron 엔드포인트

**Files:** Create `backend/routes/internal.py`; Modify `backend/main.py`(기동 훅의 purge 제거, 로컬은 `RUN_MAINTENANCE_ON_STARTUP` 기본 1 로 유지)

- `GET /api/internal/cron/daily`: `Authorization: Bearer <CRON_SECRET>`. 비밀값 미설정이면 503, 틀리면 401
- 하는 일: 소프트 삭제 TC 정리(`purge_service`), `rate_limit.purge_older_than(2일)`, 1일 넘은 미처리 스테이징 업로드의 객체와 행 삭제
- `pg_try_advisory_xact_lock(CRON)` 실패면 `{"skipped": "running"}`. 겹쳐 돌지 않는다
- [ ] 테스트: 무인증 401, 오인증 401, 미설정 503, 정상 실행 결과 건수, 오래된 스테이징 정리, 동시 실행 하나는 skipped
- [ ] 구현 후 통과, 커밋

### Task 6: 스키마 버전 불일치 503

- 기동 시 `RUN_MIGRATIONS_ON_STARTUP=0` 이면 DB 리비전을 head 와 비교한다. 없음(미초기화)이거나 head 보다 옛것이면 `app.state.schema_behind = True`
- 미들웨어: `schema_behind` 면 `/api/*` 요청에 503 `{"detail": "DB 스키마가 코드보다 옛 버전입니다. 배포 마이그레이션을 확인하세요."}`. `/` 헬스와 `/api/internal/cron/*` 는 통과
- 코드가 모르는 더 새 리비전(롤백 상태)은 막지 않는다(계획 1 판단 유지)
- [ ] 테스트: 미초기화 DB 503, head DB 정상, 더 새 리비전 정상
- [ ] 구현 후 통과, 커밋

### Task 7: RLS 마이그레이션

**Files:** Create `backend/alembic/versions/0005_supabase_rls.py`; Test `backend/tests_unit/test_rls_migration.py`

- `anon` 역할이 있을 때만: `public` 의 모든 테이블(앞으로 만들 것 포함은 아님)과 `alembic_version` 에 `ENABLE ROW LEVEL SECURITY`, `anon`·`authenticated` 의 테이블·시퀀스 권한 `REVOKE ALL`, `ALTER DEFAULT PRIVILEGES ... REVOKE ALL ... FROM anon, authenticated`
- [ ] 테스트: 임시 DB 에 `anon`, `authenticated` 역할을 만들고(로컬 슈퍼유저) 마이그레이션 → 모든 테이블 `relrowsecurity`, `anon` 의 `has_table_privilege(..., 'SELECT')` 거짓. 역할이 없는 DB 에서는 아무것도 하지 않고 통과
- [ ] "RLS 꺼진 테이블이 있으면 실패" 가드: 같은 테스트에서 모델의 모든 테이블을 대조
- [ ] 구현 후 통과, 커밋

### Task 8: 서버리스 환경 기본값과 경고

- `VERCEL` 환경변수가 있으면 `DB_POOL` 기본 `null`, `RUN_MIGRATIONS_ON_STARTUP` 기본 `0`, `STORAGE_BACKEND` 가 `supabase` 가 아니면 기동 실패(디스크가 휘발)
- `VERCEL` 인데 `TRUSTED_PROXY_HEADER` 가 비면 ERROR 로그(조직 전체가 한 IP 로 묶일 수 있음)
- [ ] 테스트: 하위 프로세스로 `VERCEL=1` 기동 조건 확인(스토리지 미설정 실패, 경고 로그)
- [ ] 구현 후 통과, 커밋

## 계획 2b-1 완료 조건

- 전체 pytest 실패 0, `grep -rn "UPLOAD_DIR\|os.makedirs" backend/routes` 0건
- QA 2인 통과 후 계획 2b-2
