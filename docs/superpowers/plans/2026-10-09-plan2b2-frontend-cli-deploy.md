# 계획 2b-2: 프론트·CLI 업로드 전환과 Vercel 배포 설정

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 화면과 CI 업로드 CLI 가 4.5MB 를 넘는 파일도 올릴 수 있고(스테이징 업로드), 레포만으로 Vercel 프로젝트를 만들 수 있다.

**Architecture:** 프론트는 `src/api/uploads.ts` 의 `stageUpload` 로 발급·직접 PUT 을 하고, 기존 API 함수는 시그니처를 유지한 채 `upload_id` 를 보낸다. 같은 `File` 은 목적별로 한 번만 올린다. 첨부 미리보기는 `<img src>` 로 다운로드 주소를 직접 쓴다. CLI 는 서버가 `/api/uploads` 를 지원하면 스테이징, 아니면 multipart. 배포 설정은 범용(회사 정보 없음)으로 공개 레포에 둔다.

**Tech Stack:** React 19 + TypeScript + axios + Vitest, Node 18+ fetch(CLI), Vercel(`vercel.json`, Python 함수), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-08-postgresql-vercel-supabase-design.md` (배포 구조, 파일 저장, 백업 절)

## Global Constraints

- 공개 레포: 회사 도메인·Supabase 프로젝트 주소를 넣지 않는다. CSP 의 Supabase 출처는 `https://*.supabase.co`.
- 직접 PUT 은 axios `client` 를 쓰지 않는다(쿠키, CSRF 헤더, 401 리다이렉트 인터셉터가 붙는다). 발급 주소가 상대 경로면 `VITE_API_URL` 을 앞에 붙인다.
- 배포 워크플로는 `vars.DEPLOY_ENABLED == 'true'` 일 때만 돈다.
- 프론트 게이트: `npx tsc -b --force`, `npx eslint src/ --quiet`, `npx vitest run`, `npm run build`.

## Review Focus

- 413 응답(Vercel 엣지의 비 JSON 포함)과 사전 크기 검사 문구
- 같은 파일로 미리보기 뒤 가져오기, 미리보기 뒤 다른 파일
- 상대 발급 주소 + `VITE_API_URL` 이 있는 교차 출처 자체 설치
- CLI 가 옛 서버(스테이징 없음)에 붙는 경우

---

### Task 1: 프론트 스테이징 업로드

- `src/api/uploads.ts`: `getUploadConfig()`(캐시), `stageUpload(purpose, file)`(사전 크기 검사, 발급, fetch PUT, WeakMap 캐시), `UploadTooLargeError`
- `src/api/index.ts`: `importExcel`, `previewImport`, `importResults`, `attachmentsApi.upload` 가 `stageUpload` 를 쓴다
- 테스트 `src/api/uploads.test.ts`: 사전 크기 초과 시 발급 안 함, 상대 주소에 base 붙임, PUT 실패(413/500) 오류, 같은 File 재사용, 다른 목적은 따로

### Task 2: 첨부 미리보기와 413 안내

- `TestRunManager.tsx` 미리보기: `<img src={downloadUrl}>` 직접, 실패 시 `onError` 로 기존 토스트
- `useAttachments.ts`, `ResultImportModal.tsx`, `TestCaseGrid.tsx`: `UploadTooLargeError` 와 413 을 i18n 문구(`uploadTooLarge`, 상한 MB 표시)로 안내
- i18n ko/en 키 추가

### Task 3: CLI 스테이징

- `scripts/ymtc-upload.mjs`: `POST /api/uploads` 가 404 면 multipart, 아니면 발급·PUT 후 `upload_id`
- 테스트 `scripts/test_ymtc_upload.py`: 표준 라이브러리 HTTP 서버로 두 경로(스테이징 지원/미지원)를 흉내 내 CLI 를 실행

### Task 4: Vercel 배치

- `api/index.py`: `backend/` 를 검색 경로에 넣고 `main.app` 노출
- 루트 `requirements.txt`: `-r backend/requirements.txt`
- `vercel.json`: 빌드(`cd frontend && npm ci && npm run build`, 출력 `frontend/dist`), rewrites(`/api/(.*)` -> `/api/index`, 나머지 -> `/index.html`), 정적 응답 보안 헤더(CSP 에 `https://*.supabase.co`), `crons`(매일 한 번 `/api/internal/cron/daily`), 함수 `maxDuration` 60
- 백엔드 Swagger 를 `/api/docs`, `/api/openapi.json` 으로
- 테스트 `backend/tests_unit/test_vercel_config.py`: `vercel.json` 구조, `api/index.py` 가 앱을 임포트하는지(하위 프로세스)

### Task 5: 배포·백업 워크플로

- `.github/workflows/deploy.yml`: `DEPLOY_ENABLED` 일 때만. 순서: 백엔드 테스트(PostgreSQL 서비스) -> `alembic upgrade head`(`DATABASE_URL_DIRECT`) -> `vercel deploy --prod --prebuilt`. `concurrency` 로 직렬화
- `.github/workflows/backup.yml`: `DEPLOY_ENABLED` 일 때만, 매일. `pg_dump` 를 아티팩트(보관 14일)로, Storage 객체 목록·복사는 `scripts/backup_storage.py`
- 테스트: 워크플로 YAML 의 조건과 단계 순서 검사

### Task 6: 문서

- README 배포 절(범용): Supabase 프로젝트·버킷 생성(비공개, `file_size_limit` 50MB), Vercel 환경변수 목록, 회사 비공개 레포에서 `DEPLOY_ENABLED` 켜는 법
- `docs/manual_admin_confluence.md` 와 관리자 매뉴얼 백업 절은 계획 3 에서
