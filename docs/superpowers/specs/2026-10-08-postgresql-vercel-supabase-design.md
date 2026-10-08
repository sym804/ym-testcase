# PostgreSQL 단일화와 Vercel + Supabase 배포 설계

**작성일:** 2026-10-08
**상태:** 설계 확정, 구현 전
**이슈:** SYM-6 (PostgreSQL 전환 준비)

## 배경

YM TestCase 는 FastAPI + SQLAlchemy 2.0 + Alembic 백엔드가 SQLite 파일 하나를 쓰는 구조다.
한 PC 에서 혼자 쓰기에는 충분하지만, 여러 사람이 인터넷 너머에서 동시에 쓰는 팀 운영에는
맞지 않는다. 쓰기가 파일 잠금으로 한 줄로 서고, 여러 서버가 같은 파일을 공유할 수 없다.

이 문서는 세 하위 프로젝트 중 첫 번째를 다룬다.

1. PostgreSQL 단일화, Vercel + Supabase 배포 구성, 기존 SQLite 데이터 이관 (이 문서)
2. 조직 계정 인증: Google 로그인(서버에서 `hd` 와 이메일 도메인 검증), 관리자 승인 + 1회용 코드 가입,
   `ALLOWED_EMAIL_DOMAINS`, 공개 가입 제거, 관리자 비활성화
3. 컷오버: 2 가 끝난 뒤에만 실행한다. 접근 제한 없이 인터넷에 먼저 열지 않기 위해서다.

이전 규모는 SQLite 9.8MB, 약 1만 5천 행(테스트 케이스, 실행 결과, 변경 이력이 대부분)과
첨부 파일 1건이다.

## 설계 결정

**main 은 PostgreSQL 하나만 지원한다.** 두 DB 를 모두 지원하는 안도 검토했다. 그러면 모든
마이그레이션과 동시성 코드를 양쪽에서 검증해야 하고, 개발은 SQLite 로 하고 운영은 PostgreSQL
로 해서 운영에서만 나는 버그를 개발 중에 못 본다. 현재 SQLite 버전은 태그 `v1.10.3.1` 에서
`sqlite-legacy` 브랜치로 동결하고 더 고치지 않는다. README 에 이 브랜치를 한 줄로 안내한다.

**프론트와 API 를 한 Vercel 프로젝트, 한 도메인에 둔다.** 인증이 httpOnly 쿠키 JWT 와
CSRF 쿠키(`SameSite=lax`)라서, 도메인이 갈리면 쿠키를 `SameSite=None` 으로 풀어야 하고
CSRF 노출면이 넓어진다. 같은 도메인이면 로컬에서 Vite 가 `/api` 를 8008 로 넘기는 것과
같은 구조가 되어 인증 코드를 바꿀 필요가 없다.

**배포 자격증명은 공개 레포에 두지 않는다.** 조직 배포는 공개 레포를 `upstream` 으로 따라가는
별도 비공개 레포에서 한다. 비공개 레포는 코드 파일을 고치지 않고, Vercel 과 Supabase 연결,
GitHub Secrets, 운영 문서만 갖는다. 공개 레포에는 범용 배포 설정과 배포 워크플로가 들어가되
워크플로는 `vars.DEPLOY_ENABLED == 'true'` 일 때만 돈다. 같은 파일이 두 레포에서 갈라지지 않고,
외부 포크 PR 의 Preview 가 DB 자격증명을 받을 경로도 없다.

**큰 파일은 Supabase Storage 로 직접 올린다.** Vercel 함수는 요청 본문을 4.5MB 까지만 받는다.
첨부(50MB), TC 엑셀 가져오기(10MB), 자동화 결과 가져오기(20MB) 상한을 4MB 로 낮추는 안을
먼저 검토했지만, 결과 가져오기는 전량 스위트 JSON 이 수 MB 라 CI 업로드(`scripts/ymtc-upload.mjs`)가
막힌다. 그래서 업로드 주소를 발급받아 클라이언트가 저장소에 직접 올리고, 백엔드는 저장소에서
읽어 처리한다. 기존 상한은 그대로 둔다.

**Alembic 이력을 PostgreSQL 기준점 하나로 압축한다.** 현재 14개 리비전 중 여럿이 SQLite 의
테이블 재생성과 `temp.` 테이블에 의존한다. 운영 DB 는 빈 PostgreSQL 에서 시작하므로 그 이력을
PostgreSQL 에서 다시 돌릴 일이 없다. 옛 이력은 `sqlite-legacy` 에 남는다.

## 배포 구조

레포 루트에 Vercel Python 함수 입구 `api/index.py` 를 둔다. 백엔드는 `from routes ...` 같은
최상위 import 를 쓰므로, 입구에서 `backend/` 를 모듈 검색 경로에 넣은 뒤 `main.app` 을 불러온다.
루트 `requirements.txt` 는 `-r backend/requirements.txt` 한 줄이다. PDF 리포트의 Pretendard
폰트(`backend/routes/reports.py:1084` 의 탐색 경로)와 백엔드 코드를 함수 번들에 포함한다.

루트 `vercel.json` 이 정하는 것:

- 빌드: `frontend` 에서 `npm ci && npm run build`, 결과물 `frontend/dist`
- 라우팅: `/api/*` 는 함수, 나머지는 `index.html`
- 정적 응답의 보안 헤더(CSP 등). 지금은 FastAPI 미들웨어가 API 응답에만 붙인다
- Cron: 하루 한 번 소프트 삭제 TC 정리 엔드포인트 호출

쓰지 않는 `/static` 마운트(`main.py:180`, 폴더 없음)는 지운다. Swagger 는 rewrite 에 걸리지
않도록 `/api/docs`, `/api/openapi.json` 으로 옮긴다. 함수와 Supabase 는 모두 서울 리전에 둔다.
함수 실행 시간 상한, 리전 코드, Supabase 의 PostgreSQL 메이저 버전은 구현 착수 시 공식 문서로
확인해 고정하고, 로컬 Docker 이미지 버전도 그 값에 맞춘다.

환경은 넷이다. 비공개 레포의 `main` 은 운영 Supabase, 비공개 레포의 PR Preview 는 합성 데이터만
든 스테이징 Supabase, 실데이터 리허설은 끝나면 지우는 임시 Supabase 프로젝트, 로컬은 Docker
PostgreSQL 이다.

### 배포 순서와 스키마

운영 배포는 Vercel 의 Git 자동 배포를 끄고 워크플로가 순서를 강제한다. 테스트, `alembic upgrade head`,
성공했을 때만 `vercel deploy --prod` 순이다. 동시 실행은 `concurrency` 로 하나씩만 돌린다.

`backend/alembic/env.py` 는 `DATABASE_URL_DIRECT` 가 있으면 그것을, 없으면 `DATABASE_URL` 을
쓴다. 앱은 트랜잭션 풀러를 쓰지만 DDL 은 직결 또는 세션 풀러로 해야 해서다. Supabase 직결 주소가
IPv6 전용이면 GitHub 러너가 붙지 못할 수 있으므로, 세션 풀러 주소로 대체 가능한지 착수 시 확인한다.

SQLite 기본값은 `alembic.ini:89`, `main.py:47`, `database.py:9` 세 곳에 있다. 모두 지우고
`DATABASE_URL` 이 없으면 기동 단계에서 예외를 낸다. 주소 전달이 빠졌을 때 마이그레이션이 로컬
SQLite 파일에 "성공" 하고 배포가 진행되는 일을 막는다.

기동 시 자동 마이그레이션(`main.py` lifespan)은 `RUN_MIGRATIONS_ON_STARTUP` 으로 제어한다. 로컬은
켜고 Vercel 은 끈다. Vercel 에서는 대신 DB 의 `alembic_version` 이 코드의 head 와 다르면 API 가
503 을 낸다. Alembic 이전 시절 DB 를 감지해 stamp 하는 분기(`services/schema_guard.py` 경로)는
더 필요 없어 지운다. 모르는 리비전을 만나면 `sqlite-legacy` 이력이라고 안내하고 멈춘다. 옛 체인을
PostgreSQL 에서 돌린 외부 사용자를 위한 장치다.

스키마 변경은 추가를 먼저 하고 삭제는 다음 릴리즈에서 한다. Vercel 의 즉시 롤백(이전 배포 승격)은
새 스키마 위에서 옛 코드를 띄우기 때문이다.

Cron 엔드포인트는 `CRON_SECRET` 이 비어 있거나 `Authorization` 값이 다르면 거부한다. 겹쳐 실행되지
않도록 advisory lock 을 잡는다.

### 환경변수

- `DATABASE_URL`: Supabase 트랜잭션 풀러 (앱)
- `DATABASE_URL_DIRECT`: 직결 또는 세션 풀러 (마이그레이션, 이관). GitHub Secrets 에만 둔다
- `SECRET_KEY`, `ENV=production`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_BUCKET`: 서비스 키는 서버 전용. 빌드 후
  `frontend/dist` 에 키 문자열이 없는지 검사한다
- `CRON_SECRET`
- `RUN_MIGRATIONS_ON_STARTUP`

같은 도메인이라 `CORS_ORIGINS` 는 쓰지 않는다. `VITE_API_URL` 은 비워 둔다.

## DB 계층

### 연결

`backend/database.py` 에서 SQLite 분기(`check_same_thread`, PRAGMA)를 지운다. Vercel 에서는
`NullPool` 을 쓴다. 실행 환경이 수시로 생기고 사라지므로 연결 재사용은 Supabase 풀러가 맡는다.
로컬은 기본 풀을 쓴다. 양쪽 모두 `pool_pre_ping` 을 켠다.

문 단위 시간 제한은 DB 역할 설정(`ALTER ROLE ... SET statement_timeout`)으로 건다. 트랜잭션
풀러를 지나면 세션 수준 `SET` 이 유지되지 않는다. 실제 6543 경로에서 걸리는지 스테이징에서 확인한다.

### 스키마 기준점

새 기준 리비전 하나가 현재 모델의 스키마 전체를 만든다. 검증 기준은 "기준점으로 만든 PostgreSQL
스키마와 `Base.metadata` 가 같다" 이다. Alembic `compare_metadata` 차이가 0이어야 하고, 부분 유니크
인덱스 조건(`deleted_at IS NULL`), server default, FK 삭제 동작은 따로 단언한다.

옛 이력과 비교하지 않는 이유가 있다. 현재 운영 SQLite 는 Alembic 이전에 만들어져 stamp 된 DB 라서
옛 이력의 결과와도, 모델과도 다르다. `test_cases.custom_fields` 가 실 DB 에서는 TEXT(모델은 JSON)이고,
`test_runs.test_plan_id` 의 삭제 동작이 실 DB 에서는 NO ACTION(모델은 SET NULL)이다. 이 차이는
이관 스크립트가 다룬다.

RLS 는 PostgreSQL 전용 리비전에서 켠다. `anon` 역할이 있을 때만(`pg_roles` 확인) 모든 `public`
테이블과 `alembic_version` 에 RLS 를 켜고 `anon`, `authenticated` 의 권한을 회수한다. 로컬과 CI 의
순수 PostgreSQL 에는 이 역할이 없어서 조건 없이 실행하면 실패한다. 앱은 테이블 소유자로 접속하므로
RLS 의 영향을 받지 않는다. RLS 는 Supabase REST 노출 차단용이지 프로젝트 간 접근 격리 수단이 아니다.
그 격리는 지금처럼 앱의 권한 검사가 맡는다.

### SQLite 전용 코드

`services/tc_numbering.py:74` 의 `renumber_sheet()` 가 `temp._tc_rank` 임시 테이블을 쓴다. `temp.`
는 SQLite 전용 스키마 이름이고, 트랜잭션 풀러에서는 임시 테이블 자체가 위험하다. 시트 이동,
엑셀 가져오기, 일괄 수정이 이 함수를 부른다. `UPDATE ... FROM (SELECT id, ROW_NUMBER() OVER (...))`
한 문장으로 바꾸고, 유니크 충돌을 피하는 두 단계 번호 변경은 유지한다.

고급 필터(`routes/filters.py:123` 의 `_apply_condition`)는 정수 칸 `no` 에도 `ILIKE` 와 `== ""` 를
그대로 적용한다. SQLite 는 넘어가지만 PostgreSQL 은 타입 오류로 500 을 낸다. 칸 타입별로 허용
연산자를 나누고, 맞지 않는 연산자나 값은 400 으로 거절한다.

검색의 `ilike` 15곳은 이미 대소문자를 무시하므로 바꾸지 않는다. 다만 PostgreSQL 의 LIKE 는 `\` 를
이스케이프 문자로 쓰므로 검색어의 `%`, `_`, `\` 이스케이프를 확인한다.

`services/run_sync_service.py` 의 SQLite 분기와, 전환 후 낡게 되는 "SQLite 전제" 주석
(`routes/testcases.py:428`, `database.py`, `.claude/skills/dev/SKILL.md` 등)을 정리한다.

## 동시성 계약

SQLite 는 쓰기를 한 줄로 세워서 "읽고 판단한 뒤 쓰는" 코드가 우연히 안전했다. PostgreSQL 의
READ COMMITTED 에서는 두 트랜잭션이 같은 값을 읽고 둘 다 쓴다. 바꿀 지점과 방법은 아래와 같다.

번호 매기기는 프로젝트 단위 `pg_advisory_xact_lock` 으로 줄을 세운다(`services/locks.py`). 잠금은
번호나 존재 여부를 **읽기 전에** 잡는다. 대상은 TC 생성, 복제, 복원, 삭제, 재정렬, 시트 생성·이름
변경·이동·삭제, 수행 생성, 다음 회차(`routes/testruns.py` 의 런 복제와 이름으로 결과 올리기)다.
잠금 키는 두 정수 형태로 용도와 대상 id 를 나눈다. 트랜잭션 잠금이라 같은 트랜잭션 안에서는 트랜잭션
풀러에서도 유지된다. 중간 `commit()` 뒤의 작업은 잠금이 풀린 새 트랜잭션이다.

잠금 구간은 번호를 건드리는 부분으로 줄인다. 시트 이동이 없는 TC 수정(셀 자동 저장)과 일괄 수정은
잠그지 않고, 이동이 있을 때만 그 자리에서 잡는다. 엑셀 가져오기는 업로드 수신과 워크북 로딩 뒤에 잡는다.
잠금 대기는 `LOCK_WAIT_TIMEOUT_MS`(기본 10초)를 넘으면 409 와 재시도 안내로 끝낸다. 기다리는 요청은
DB 연결을 쥐고 있어서, 상한이 없으면 긴 작업 하나가 다른 프로젝트의 연결까지 말린다.

다음 회차에는 유니크 제약을 걸지 않는다. 수행 생성은 회차 기본값이 1이라 같은 이름으로 다시 만들면
같은 회차가 생기는 것이 정상 흐름이고, 대시보드는 그 경우 가장 최근 수행을 쓴다
(`tests_unit/test_dashboard_rounds.py`). 자동으로 정하는 다음 회차의 경쟁은 프로젝트 잠금이 막는다.

최초 관리자 판정은 전역 advisory lock 으로 가입을 줄 세운다(`routes/auth.py` 의 `register`). 삽입 뒤
강등하던 옛 방식은 지웠다. bcrypt 는 잠금 밖에서 한다. 공개 가입 자체를 없애는 것은 하위 프로젝트 2 의 일이다.

결과를 쓰는 세 경로(저장 `submit_results`, 파일 가져오기 `_record_import`, 누락 행 동기화
`sync_run_results`)는 수행 단위 잠금을 먼저 잡는다. 가져오기가 결과를 읽고 판단한 사이 사람이 저장한
값을 덮는 경쟁과, 누락 행을 서로 다른 순서로 넣는 교착을 막는다. 동기화는 넣을 행이 있을 때만 잡는다.
저장은 그 안에서 결과 행을 `SELECT ... FOR UPDATE` 로 잠그고 읽어 충돌 검사(수정 시각 비교)를 한다.

1회용 코드 소비(`routes/account_requests.py`)는 조회, 검증, 소비 사이에 잠금이 없어 같은 코드로
두 번 비밀번호를 바꿀 수 있다. 요청 행을 `SELECT ... FOR UPDATE` 로 잠근 뒤 재검증하고 소비한다.
관리자 승인과 반려도 같은 행을 잠그고 상태를 본다. 하위 프로젝트 2 의 가입 코드도 이 방식을 쓴다.

결과 행 일괄 생성은 이미 `ON CONFLICT DO NOTHING`(`services/run_sync_service.py:27`)이라 그대로 둔다.

## 공유 상태

로그인 실패 잠금(`routes/auth.py:28` `_login_failures`)과 계정 요청 제출 제한
(`routes/account_requests.py:42` `_submit_hits`)은 프로세스 메모리에 있다. 실행 환경이 여러 개면
각자 따로 센다. 둘 다 DB 테이블 `rate_limit_events`(버킷, 키, 시각)로 옮기고 오래된 행은 Cron 정리에서
지운다. 기록은 요청 세션과 별도 트랜잭션으로 써서 실패 응답(401, 429)의 롤백에 휩쓸리지 않게 하고, 같은
키는 요청 동안 advisory lock 으로 잠가 확인과 기록 사이에 동시 요청이 한도를 넘지 못하게 한다.

두 제한 모두 `request.client.host` 를 키로 쓴다. Vercel 에서 이 값이 무엇으로 오는지 정해지지 않았다.
상수로 오면 조직 전체가 한 IP 로 묶여 함께 잠기고, `X-Forwarded-For` 를 그대로 믿으면 위조된다.
신뢰할 수 있는 헤더 하나만 읽는 함수로 두 곳을 모으고, 어떤 헤더를 쓸지는 스테이징에서 실측해 정한다.

## 파일 저장

`services/storage.py` 가 저장소를 감싼다. 로컬은 디스크(`backend/uploads/`), 배포는 Supabase Storage
비공개 버킷이다. 지금 `UPLOAD_DIR` 을 직접 쓰는 곳은 `routes/attachments.py`, `routes/projects.py:192`,
`routes/testruns.py:747` 이다. `routes/attachments.py:21` 의 import 시점 `os.makedirs` 는 로컬 저장소
초기화로 옮긴다. 쓰기 불가한 함수 파일시스템에서 기동 단계에 터지지 않게 하기 위해서다.

업로드는 세 단계다.

1. 클라이언트가 업로드 주소를 요청한다. 백엔드는 권한과 선언된 크기를 확인하고 주소를 발급한다.
2. 클라이언트가 그 주소에 파일을 올린다. 배포에서는 Supabase 서명 업로드 URL, 로컬에서는 백엔드 자신의 주소다.
3. 클라이언트가 처리를 요청한다. 백엔드는 저장소에서 파일을 읽어 실제 크기를 다시 확인하고 처리한다.

첨부, TC 엑셀 가져오기, 자동화 결과 가져오기가 이 흐름을 쓴다. 기존 multipart 업로드 API 는
하위 호환으로 남긴다. 작은 파일과 외부 사용자의 스크립트가 계속 동작해야 한다. `scripts/ymtc-upload.mjs`
는 새 흐름으로 바꾼다. 처리되지 않은 업로드 객체는 Cron 정리에서 지운다.

다운로드는 권한을 확인한 뒤 짧은 수명의 서명 URL 로 넘긴다. Vercel 의 응답 크기 한도와 함수 실행
시간을 피한다. PDF 와 엑셀 리포트, 프로젝트 내보내기는 지금처럼 메모리에서 만든다. 결과가 4MB 이하면 그대로
응답하고, 넘으면 Storage 에 임시 객체로 올린 뒤 서명 URL 로 넘긴다. Vercel 은 응답 본문에도 같은
한도를 둔다. 임시 객체는 Cron 정리에서 지운다. 큰 프로젝트의 생성 시간과 메모리는 스테이징에서 잰다.

실제 상한 값은 `/api/config` 로 내려 준다. 화면과 매뉴얼에 "50MB" 로 고정된 문구(i18n
`manual.json`, `adminManual.json`)가 이 값을 쓰게 하고, 프론트에 사전 크기 검사와 413 안내를 넣는다.
Vercel 엣지의 413 은 JSON 이 아니므로 응답 형식에 기대지 않는다.

## 시간

DB 의 시각은 지금처럼 KST naive(`models.py` 의 `now_kst`)로 둔다. `timestamptz` 로 바꾸거나 UTC 로
해석하면 기존 값이 9시간 어긋난다. 리포트 파일명과 생성 시각(`routes/reports.py:534`, `:770` 의
`datetime.now()`)은 Vercel 에서 UTC 가 되므로 `models.now_kst` 와 같은 고정 오프셋(UTC+9)으로 낸다.
`zoneinfo` 는 시간대 DB(`tzdata`)가 없는 환경에서 실패하고, 한국은 서머타임이 없다.

PostgreSQL 과 SQLite 는 NULL 정렬 위치가 다르다(`resolved_at DESC` 등). 정렬에 nullable 칸이 들어가는
쿼리는 `nulls_last()` 같은 명시로 지금 결과를 고정한다. 한글과 영문이 섞인 문자열 정렬은 DB collation
을 따르므로, 정렬 결과를 단언하는 테스트가 있으면 PostgreSQL 기준으로 맞춘다.

## 데이터 이관

`scripts/migrate_sqlite_to_pg.py` 는 일회성 스크립트다. 원본 SQLite 경로, 대상 주소, `--dry-run` 을 받는다.

### 사전 점검

하나라도 걸리면 아무것도 쓰지 않고 멈춘다.

- 원본을 읽기 전용(`mode=ro`)으로 열고 `alembic_version` 이 legacy head `5e0b8c2d4f17` 인지 확인
- 원본의 테이블과 칸 구성이 예상과 같은지 대조. 예상은 모델이 아니라 실 DB 의 실제 모양이다
- `PRAGMA foreign_key_check`. 현재 운영 DB 에 1건이 있다. `test_case_history` 347번이 이미 영구
  삭제된 테스트 케이스를 가리킨다. 이 행은 이관에서 빼고 `excluded_rows.json` 으로 보관한다.
  화면 어디에서도 보이지 않는 행이다. 다른 고아가 새로 나오면 목록을 내고 멈춘다
- 대상 PostgreSQL 의 사용자 테이블이 모두 비어 있는지 확인

### 복사

대상에 기준점 스키마를 올린 뒤 FK 순서대로 복사한다. id 는 원본 그대로 쓴다. 자기 참조 칸
(`test_case_sheets.parent_id`, `test_runs.compare_run_id`)은 처음에 비워 넣고 모든 행을 넣은 뒤 채운다.
현재 데이터에는 두 칸 모두 값이 있는 행이 없지만 스크립트는 일반적으로 처리한다.

칸별 변환 규칙을 명시한다.

- `custom_fields`: 원본 TEXT 를 `json.loads` 로 파싱해 넣는다. 문자열 그대로 JSON 칸에 넣으면
  JSON 문자열 리터럴로 이중 인코딩된다. 해당 행이 약 600건이다
- `projects.field_config`: 지금 계약이 Text + 직접 `json.loads` 이므로 Text 그대로 둔다
- SQL NULL 과 JSON `null` 을 구분한다
- 불리언은 0/1 외의 값이면 멈춘다
- enum 은 허용 값과 대조한다. 결과는 대문자(`PASS` 등), 역할은 소문자다
- 시각은 KST naive 그대로 옮긴다
- `VARCHAR(n)` 길이 초과 값이 있으면 멈춘다. 현재 운영 DB 에는 0건이다

소프트 삭제된 테스트 케이스는 결과와 이력이 참조하므로 전부 옮긴다. 복사는 한 트랜잭션이고,
실패하면 대상은 빈 상태로 남아 처음부터 다시 실행할 수 있다.

시퀀스는 테이블마다 `setval(seq, max(id), true)` 로 맞춘다. 빈 테이블은 `setval(seq, 1, false)` 다.
`is_called` 를 빠뜨리면 다음 값이 하나 더 건너뛴다.

### 검증

이관 변환 코드는 여기서 쓰지 않는다. 같은 변환 함수로 계산한 해시는 변환의 버그를 그대로 통과시킨다.
`custom_fields` 이중 인코딩이 그런 예다. 다시 같은 타입으로 읽으면 원래 문자열이 돌아와 해시가 맞는다.

- 테이블마다 행 수가 원본에서 제외 행을 뺀 수와 같다
- PK 로 행을 짝지어 칸마다 비교한다. 대상은 `::text` 로 읽고, 원본 원문은 칸별 기대 표현으로 바꿔 비교한다.
  `custom_fields` 는 양쪽을 JSON 객체로 파싱해 비교한다
- 각 시퀀스의 다음 값이 `max(id)+1` 이다
- 대시보드 집계, 프로젝트 목록 합격률, 리포트 요약을 이관 전 로컬 서버와 이관 후 서버에서 각각 받아 비교한다

### 첨부

DB 에 행이 있는 첨부 1건을 Storage 로 옮기고 SHA-256 을 대조한 뒤 `attachments.filepath` 를 새 키로
바꾼다. `uploads/` 에만 있고 DB 에 행이 없는 파일 2개는 옮기지 않고 목록만 남긴다. Storage 업로드는
DB 트랜잭션과 따로 도는 단계라, 같은 키에 같은 해시가 있으면 건너뛰게 해서 다시 실행해도 안전하게 한다.

## 컷오버

하위 프로젝트 2 가 끝난 뒤 비공개 레포에서 진행한다.

1. 로컬 서버를 내려 쓰기를 멈추고 SQLite 와 `uploads/` 의 백업 사본을 만든다
2. 임시 Supabase 프로젝트에 사본을 이관하고 검증한다. 통과하면 임시 프로젝트를 지운다
3. 운영 Supabase 에 이관하고 검증한다
4. 운영 주소를 안내한다. 원본 SQLite 와 `uploads/` 는 지우지 않는다

롤백은 운영에 새 데이터가 쓰이기 전까지만 손실이 없다. 그 뒤에 로컬로 돌아가면 그 사이 데이터를 잃는다.
첫 업무 사용 시작을 롤백 종료 시점으로 둔다.

## 백업

Supabase 의 DB 백업에는 Storage 객체가 들어가지 않는다. DB 는 Supabase 백업에 더해 워크플로가
주기적으로 `pg_dump` 를 떠서 보관하고, Storage 는 버킷 복사 작업을 따로 둔다. 관리자 매뉴얼의 백업 절
(`frontend/src/pages/AdminManualPage.tsx:507`, `docs/manual_admin_confluence.md`)은 `cp tc_manager.db`
기준이라 다시 쓴다.

## 로컬 개발

`docker-compose.yml` 은 지금 `.gitignore` 에 들어 있고 추적되지 않으며, 참조하는 Dockerfile 도 없다.
gitignore 에서 빼고 PostgreSQL 서비스 하나만 두는 파일로 새로 추적한다.

`python scripts/devctl.py up` 이 컨테이너를 띄우고, 준비될 때까지 기다리고, `alembic upgrade head` 를
한 뒤 서버를 올린다. 사용법은 지금과 같다. `.env.example` 의 `DATABASE_URL` 예시를 로컬 PostgreSQL 로 바꾼다.

## 테스트

### 하네스

테스트 파일 27개가 `sqlite:///` 엔진을 직접 만들고 `Base.metadata.create_all` 을 부른다. 이대로면
`DATABASE_URL` 을 바꿔도 이 테스트들은 계속 SQLite 에서 돌아 통과한다. 공용 PostgreSQL 픽스처 하나로
모은다. 세션마다 임시 DB 를 만들어 기준점 스키마를 올리고, 테스트마다 테이블을 비운다.

가드를 둘 둔다. 테스트 중 `sqlite://` 로 엔진을 만들면 실패한다. 테스트 DB 관리 주소
(`TEST_DATABASE_ADMIN_URL`)의 호스트가 localhost 가 아니면 거부한다. 지금 `conftest.py:80` 의 격리
판정은 주소가 `/tc_manager.db` 로 끝나는지만 봐서, PostgreSQL 주소는 그대로 쓰인다. 설정에 따라
테스트가 운영 DB 에 쓴다. 이 동작을 정상으로 고정한 `test_db_isolation.py:87` 은 원격 주소를 거부하는
쪽으로 다시 쓴다. 이미 떠 있는 8008 서버를 쓰는 모드의 건너뛰기 가드(`dev_db_guard.py`)는 유지한다.

메모리 상태를 직접 비우던 픽스처(`test_account_requests.py:21` 의 `except ImportError: pass`,
`tests_unit/test_api_keys.py:106`)는 DB 테이블 비우기로 바꾼다. 그대로 두면 아무 일도 안 하고 뒤쪽
테스트가 429 로 간헐 실패한다. `PRAGMA busy_timeout` 을 검사하는 `test_run_tc_sync.py:266` 은 지운다.

옛 마이그레이션을 직접 돌리는 테스트 7개(`test_migration_preserves_schema`, `test_result_uniqueness`,
`test_tc_no_normalize`, `test_migration_dedup_safety`, `test_schema_guard`, `test_unique_tc_id_migration`,
`test_run_issues` 의 해당 부분)는 압축과 함께 정리한다. `sqlite-legacy` 에는 남는다.

`test_security.py:647` 처럼 소스 문자열(`MAX_FILE_SIZE`)을 검사하는 테스트는 이름을 바꾸면 깨지므로
함께 고친다.

CI(`.github/workflows/ci.yml`)의 단위, API, E2E 세 잡을 PostgreSQL 서비스 컨테이너 기준으로 바꾼다.
CI 의 관리자 시드는 지금 `/api/auth/register` 를 쓴다. 하위 프로젝트 2 에서 공개 가입을 없애면 함께
바꿔야 하므로, 이번에 시드 스크립트로 분리해 둔다.

### 결함을 잡는지 확인하는 테스트

기존 동시 복제 테스트(`test_tc_clone_concurrent.py:78`)는 8개 중 1개만 성공해도 통과한다. 잠금이 없어도
유니크 제약이 실패 쪽을 409 로 만들고 남은 번호는 이어지므로 결함을 못 잡는다. 동시성 테스트는 아래를 지킨다.

- 배리어로 시작을 맞추고 요청마다 독립 연결을 쓴다
- 성공 N건, 번호 N개 증가, 중복 0건을 정확히 단언한다. 500 과 타임아웃도 실패로 센다
- 잠금을 뺀 코드에서 반드시 실패하는지 먼저 확인한다

대상은 TC 복제, 다음 회차, 최초 관리자, 결과 동시 수정, 1회용 코드 이중 사용, 로그인 잠금(서로 다른
연결에서 같은 횟수를 보는지)이다.

이관 테스트 픽스처는 `create_all` 로 만든 깨끗한 SQLite 가 아니라 실 DB 의 스키마 사본에 실제 이상치를
심어 만든다. 고아 FK 행, TEXT `custom_fields`, NO ACTION FK, 자기 참조 값, 소프트 삭제 행, 빈 테이블이다.

스키마 테스트는 기준점과 모델의 동등성, RLS 대상 누락 0건을 본다.

### 스테이징 스모크

비공개 레포의 스테이징에서 실제 브라우저와 실제 Supabase 풀러로 확인한다. 로컬 PostgreSQL 직결로는
풀러, 콜드 스타트, 여러 함수 인스턴스, 브라우저 쿠키와 CSRF 를 검증할 수 없다.

로그인과 CSRF, TC 생성·수정·삭제, 시트 이동과 재정렬, 실행 결과 입력, 엑셀 가져오기와 내보내기,
4.5MB 를 넘는 CI 결과 업로드, PDF 리포트, 첨부 업로드와 다운로드, Cron 호출(무인증·오인증 거부 포함),
anon 키로 REST 를 호출했을 때 거부되는지, 클라이언트 IP 헤더 실측, 문 단위 시간 제한 적용 여부를 본다.

## 버전과 이슈

DB 엔진과 배포 플랫폼 교체는 기술 스택 교체라 System 을 2.0.0.0 으로 올린다. BE, FE, DB 축은 구현
커밋에서 바뀐 영역에 따라 올린다.

이 작업은 SYM-6 을 이어서 닫는다. 설계 단계에서 발견한 결함(임시 테이블, 회차 경쟁, 필터 타입, 결과
수정 경쟁, 1회용 코드 이중 사용, 테스트 격리 판정)은 구현 착수 시 Linear 에 따로 등록한다.

공개 레포의 문서에는 범용 배포 방법만 쓴다. 조직 운영 기록과 수치는 비공개 레포에 둔다.

## 문서 갱신

README(`sqlite-legacy` 안내, 로컬 PostgreSQL 실행법, 배포 방법), `backend/.env.example`,
사용자·관리자 매뉴얼(`UserManualPage.tsx`, `AdminManualPage.tsx`, i18n), `docs/manual_*_confluence.md`,
`.claude/skills/dev/SKILL.md`, `CLAUDE.md` 의 로컬 구동 절을 고친다. i18n 문구는 키 단위로 고치고
일괄 치환하지 않는다. E2E 가 화면 문구로 셀렉터를 잡는 곳이 있으면 함께 확인한다.

## 범위 밖

- 조직 계정 인증 전체 (하위 프로젝트 2)
- 컷오버 실행 (하위 프로젝트 3)
- 매직 링크 로그인, 메일 발송 기능
- 브라우저가 Supabase 를 직접 호출하는 구조. 프론트는 지금처럼 백엔드 API 만 부른다
