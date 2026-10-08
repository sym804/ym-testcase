# 계획 3: SQLite -> PostgreSQL 데이터 이관과 릴리즈 준비

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 실사용 SQLite(legacy head `5e0b8c2d4f17`)의 데이터와 첨부를 PostgreSQL + Storage 로 손실 없이 옮기는 일회성 스크립트를 만들고, 로컬 Docker 대상으로 리허설해 검증한 뒤 문서와 릴리즈 기록을 갖춘다.

**Architecture:** `scripts/migrate_sqlite_to_pg.py` 가 사전 점검 -> 한 트랜잭션 복사 -> 독립 검증 -> (커밋) -> 첨부 업로드 순서로 돈다. 변환은 대상 칸의 SQLAlchemy 타입을 보고 정하고, 검증은 변환 코드를 쓰지 않고 대상의 `::text` 를 원본 원문과 따로 만든 기대 표현으로 비교한다. 기대 칸 구성은 모델이 아니라 실 DB 에서 뽑은 `scripts/legacy_schema.json` 이다(데이터 없음).

**Tech Stack:** Python 3.12, sqlite3(`mode=ro`), SQLAlchemy 2.0 core, psycopg2, 기존 `services.storage`.

**Spec:** `docs/superpowers/specs/2026-10-08-postgresql-vercel-supabase-design.md` (데이터 이관, 컷오버, 백업, 버전과 이슈, 문서 갱신 절)

## Global Constraints

- 원본 SQLite 는 `file:<path>?mode=ro` 로만 연다. 원본과 `uploads/` 를 고치거나 지우지 않는다
- 사전 점검이 하나라도 실패하면 대상에 아무것도 쓰지 않는다
- 복사는 한 트랜잭션. 실패하면 대상은 빈 상태로 남는다
- 시각은 KST naive 그대로 옮긴다(변환 없음)
- JSON 칸: SQL NULL 은 SQL NULL, 텍스트 `'null'` 은 JSON null. 문자열을 다시 인코딩하지 않는다
- 공개 레포라 실 DB 의 데이터, 조직 정보, 실 경로를 커밋하지 않는다. `legacy_schema.json` 은 칸 이름과 타입만
- 실사용 서버(원본 `tc_manager` 폴더의 8008)는 건드리지 않는다. 리허설은 원본의 **사본**과 다른 포트로
- 엠대시·엔대시 금지, 문서는 deslop 검사

## Review Focus

- 원본에 `custom_fields = 'null'`(631행)과 SQL NULL(1,541행)이 섞여 있다. 둘 다 그대로 구분돼야 한다
- PostgreSQL 의 timestamp `::text` 는 소수 끝의 0 을 지운다(`.500000` -> `.5`, `.000000` -> 없음). 기대 표현이 이것을 따로 만든다
- 자기 참조 칸(`test_case_sheets.parent_id`, `test_runs.compare_run_id`)이 지금은 0행이지만 값이 있는 데이터에서도 순서 문제 없이 들어가야 한다
- 시퀀스 `is_called` 누락 시 다음 id 가 하나 건너뛴다. 빈 테이블은 `setval(seq, 1, false)`
- 첨부 업로드는 다시 실행해도 같은 키·같은 해시면 건너뛴다

---

### Task 1: 사전 점검

**Files:**
- Create: `scripts/migrate_sqlite_to_pg.py`, `scripts/legacy_schema.json`, `scripts/test_migrate_sqlite_to_pg.py`

**Interfaces:**
- Produces: `precheck(src: sqlite3.Connection, dst: Engine, allow_orphans: set[tuple[str,int]]) -> Precheck` (`excluded: dict[str, set[int]]`, 실패 시 `MigrationError(사유 목록)`), `open_source(path) -> sqlite3.Connection`
- 테스트 픽스처: `legacy_schema.json` 으로 빈 legacy SQLite 를 만드는 `make_legacy_db(tmp_path, rows: dict)`, 대상은 `testing_db.create_database` + `alembic upgrade head`

- [ ] **Step 1:** 실 DB 에서 `legacy_schema.json` 생성(읽기 전용 일회성 명령, 테이블 -> [[칸, 타입, notnull, pk]], 인덱스·FK 정의). 커밋 전 데이터가 없는지 눈으로 확인
- [ ] **Step 2: 실패 테스트**
  - legacy head 가 아니면 멈춘다(`5e0b8c2d4f17` 외 값, 테이블 없음)
  - 칸이 하나 더 있거나 빠지거나 타입이 다르면 멈추고 차이를 적는다
  - FK 고아: 허용 목록(`--allow-orphan test_case_history:347`)에 있으면 제외 목록으로, 없으면 목록을 내고 멈춘다
  - 대상의 alembic 이 head 가 아니거나 사용자 테이블에 행이 있으면 멈춘다
  - 불리언 칸에 0/1 외의 값, enum 칸에 허용 밖 값, `VARCHAR(n)` 초과, JSON 칸의 파싱 불가 텍스트, 시각 칸의 파싱 불가 텍스트가 있으면 멈춘다
  - 원본 파일이 `mode=ro` 로 열려 쓰기가 실패한다
- [ ] **Step 3:** 실행해 실패 확인
- [ ] **Step 4:** 구현. 칸 규칙은 대상 `Base.metadata` 의 칸 타입으로 정한다(`Boolean`, `DateTime`, `JSON`, `Enum`, `String(length)`)
- [ ] **Step 5:** 통과 확인, 커밋 `feat(migrate): SQLite 이관 사전 점검`

### Task 2: 복사와 시퀀스

**Interfaces:**
- Consumes: `Precheck.excluded`
- Produces: `copy_all(src, conn, excluded) -> dict[str, int]`(테이블별 넣은 행 수), `fix_sequences(conn)`

- [ ] **Step 1: 실패 테스트**
  - FK 순서(`Base.metadata.sorted_tables`)로 넣고 id 를 보존한다
  - 자기 참조 칸에 값이 있는 행(부모가 뒤 id)도 들어간다: 처음 NULL 로 넣고 끝에 UPDATE
  - `custom_fields`: SQL NULL 은 `IS NULL`, 텍스트 `'null'` 은 `json_typeof(custom_fields) = 'null'`, `'{"a":1}'` 은 `json_typeof = 'object'`(이중 인코딩이면 `'string'` 이 되어 실패)
  - 제외 행은 들어가지 않는다
  - 시퀀스: 행이 있는 테이블은 다음 INSERT id 가 `max+1`, 빈 테이블은 1
  - 중간 실패(예: 두 번째 테이블에서 강제 오류) 뒤 대상의 모든 테이블이 비어 있다
- [ ] **Step 2:** 실패 확인
- [ ] **Step 3:** 구현. 값 변환: 불리언 0/1 -> bool, 시각 `datetime.fromisoformat`, JSON 은 원문 텍스트를 `CAST(:v AS json)` 으로(NULL 은 NULL), 나머지 그대로. 연관 테이블(`run_issue_test_cases`)은 PK 없이 복사
- [ ] **Step 4:** 통과 확인, 커밋 `feat(migrate): 이관 복사와 시퀀스 보정`

### Task 3: 독립 검증

**Interfaces:**
- Produces: `verify(src, conn, excluded) -> list[str]`(불일치 사유, 비면 통과)

- [ ] **Step 1: 실패 테스트**(검증기 이빨: 대상을 일부러 틀리게 만든 뒤 잡는지)
  - 행 수 차이
  - 칸 값 하나 변경(문자열, 시각 마이크로초, 불리언)
  - `custom_fields` 이중 인코딩(`'"{\"a\":1}"'`)
  - JSON null 과 SQL NULL 이 뒤바뀜
  - 시퀀스 다음 값이 `max+2`
- [ ] **Step 2:** 실패 확인
- [ ] **Step 3:** 구현. 대상은 `SELECT id, col::text`, 원본은 칸 타입별 기대 표현을 **변환 코드와 별도로** 만든다: 불리언 `'true'/'false'`, 시각은 소수 끝 0 제거, float 은 `repr`, JSON 은 양쪽 `json.loads` 비교(+ NULL 여부 따로), 나머지 원문
- [ ] **Step 4:** 통과 확인, 커밋 `feat(migrate): 이관 독립 검증`

### Task 4: 첨부 이관과 CLI

**Interfaces:**
- Produces: `migrate_attachments(conn, uploads_dir, storage) -> AttachmentReport`(`moved`, `skipped_same`, `orphan_files`), `main(argv) -> int`

- [ ] **Step 1: 실패 테스트**
  - DB 행이 있는 파일은 `attachments/<원래 파일명>` 키로 올리고 SHA-256 을 다시 읽어 대조한 뒤 `filepath` 를 새 키로 바꾼다
  - 같은 키에 같은 해시가 있으면 건너뛴다(두 번 실행해도 결과 같음)
  - 같은 키에 다른 해시가 있으면 멈춘다
  - DB 행이 없는 파일은 올리지 않고 `orphan_files` 에 적는다. 행은 있는데 파일이 없으면 멈춘다
  - CLI: `--dry-run` 은 점검·복사·검증 후 롤백하고 첨부는 건너뛴다. 종료코드 0/1, 제외 행은 `--excluded-out` JSON 으로
- [ ] **Step 2:** 실패 확인
- [ ] **Step 3:** 구현. 순서: 점검 -> 복사 -> 검증 -> 커밋 -> 첨부(별도 트랜잭션으로 filepath 갱신)
- [ ] **Step 4:** 통과 확인, CI 스크립트 테스트 단계에 추가, 커밋 `feat(migrate): 첨부 이관과 실행 진입점`

### Task 5: 로컬 리허설

- [ ] **Step 1:** 원본 SQLite 와 `uploads/` 를 스크래치로 복사(원본은 `mode=ro` 로만 읽음)
- [ ] **Step 2:** 로컬 Docker 에 임시 DB 를 만들고 `alembic upgrade head`, 스토리지는 임시 `UPLOAD_DIR`
- [ ] **Step 3:** `--dry-run` 실행, 다음 실제 실행. 기대: 제외 1행(history 347), 검증 불일치 0, 첨부 1건 이동, 고아 파일 목록
- [ ] **Step 4:** API 비교: 사본으로 옛 코드(원본 폴더의 main) 서버를 8028, 이관 DB 로 새 서버를 8029 에 띄우고 같은 관리자 토큰으로 프로젝트 목록(합격률), 대시보드 집계, 리포트 요약을 받아 비교. 두 서버 모두 시작 시 정리 작업을 끈다(또는 같은 결과인지 확인). 끝나면 두 서버를 PID 로 내리고 임시 DB 를 지운다
- [ ] **Step 5:** 결과를 원장에 수치로 기록(공개 레포 문서에는 넣지 않는다)

### Task 6: 문서

- [ ] README: `sqlite-legacy` 안내(기존 사용자는 업데이트 전 Docker 필요, 기존 데이터 이관 명령), 이관 스크립트 사용법
- [ ] 관리자 매뉴얼 백업 절(`AdminManualPage.tsx`, i18n ko/en, `docs/manual_admin_confluence.md`): `cp tc_manager.db` 를 `pg_dump` + Storage 백업 기준으로
- [ ] 회귀 체크리스트(`TC_Manager_Regression_Checklist_v2_merged.xlsx`): 큰 파일 첨부, 용량 초과 안내, 미리보기 뒤 가져오기, 결과 dry run 뒤 적용, Swagger 화면, 동시 편집 409 안내. `OPENPYXL_LXML=False`, 쓰기 후 셀 대조
- [ ] deslop 검사, 커밋 `docs: PostgreSQL 전환 안내와 백업 절`

### Task 7: 릴리즈 기록과 마무리

- [ ] 버전: System 2.0.0.0(기술 스택 교체), BE·FE·DB 는 바뀐 영역에 따라 `rules/versioning.md` 로 판정
- [ ] 이슈: 구현 중 재현한 결함을 `issuelog new` 로 Linear 에 등록(SYM-6 하위), 닫힌 상태와 엑셀 로그 조인 키 확인
- [ ] `Release_note.md` 새 절(release-lint 통과), QA 2인(이관 스크립트 + 문서)
- [ ] 커밋·푸시·CI 확인
- [ ] **멈춤 지점:** `sqlite-legacy` 브랜치 생성과 main 머지는 사용자의 로컬 실사용 경로(원본 폴더의 main)에 영향을 주므로 사용자에게 확인을 받은 뒤 한다
