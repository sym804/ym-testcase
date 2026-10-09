# 조직 계정 인증 화면, E2E, 문서, 릴리즈 Implementation Plan (계획 4b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계획 4a 의 인증 API 를 화면(로그인, 가입, 관리자 사용자 관리, 계정 연결)에 붙이고, E2E 와 CI 설정, 문서, 릴리즈 기록까지 마쳐 `feat/auth` 를 머지 가능한 상태로 만든다.

**Architecture:** 화면은 `GET /api/auth/config` 로 켜진 기능(Google, 첫 관리자 모드)을 묻고 그에 맞춰 바뀐다. Google 로그인은 페이지 이동(`<a href="/api/auth/google/start">`)이라 화면에 외부 스크립트를 넣지 않는다. 콜백이 넘기는 `?error=` / `?account=` 코드는 i18n 문구로 바꿔 보여 준다.

**Tech Stack:** React 19, TypeScript, react-i18next, Vitest + Testing Library, Playwright

**Spec:** `docs/superpowers/specs/2026-10-09-org-account-auth-design.md` (백엔드 계약은 계획 4a 의 Global Constraints 문구표)

## Global Constraints

- 작업 위치: 워크트리 `tc_manager-pg`, 브랜치 `feat/auth`. 커밋은 로컬, 푸시는 QA 2인 대조 뒤.
- 실사용 서버(8008/5173)가 떠 있으면 로컬 E2E 를 돌리지 않는다(`reuseExistingServer`). 격리 실행은 백엔드 8018 + 프론트 5183 + 임시 DB + 임시 설정 파일(커밋하지 않음).
- 프론트 게이트: `cd frontend && npx tsc -b && npx eslint . && npx vitest run && npm run build`
- 엠대시, 엔대시 금지. 화면 문구는 ko/en 두 벌을 같이 넣는다.
- 로그인 칸 안내 문구: ko `아이디 또는 이메일을 입력하세요`, en `Enter your username or email`. 이 문구에 기대는 테스트를 한 번에 바꾼다.
- 가입 화면의 비밀번호 검사 순서는 필수 칸 -> 8자 -> 확인 일치(이메일 형식은 서버가 본다). E2E `TC-AUTH-008` 이 첫 칸에 아이디 모양을 넣고 8자 문구를 기다리기 때문이다.
- 버전: System 2.1.0.0, Backend 2.1.0.0, Frontend 1.12.0.0, Database 1.1.0.0 (기능 추가 B, 스키마 변경)

## Review Focus

- 콜백이 `?error=pending` 으로 돌려보냈을 때 로그인 화면이 승인 대기 안내를 보여 준다(Task 1 테스트).
- 첫 관리자 모드(사용자 0명)에서 가입 화면이 아이디 칸을 보여 준다(Task 2 테스트).
- 비밀번호 없는 계정(Google 전용)에는 비밀번호 변경 메뉴가 없고 계정 연결 창에 해제 버튼이 없다(Task 4 테스트).
- 관리자 화면에서 승인 대기 계정만 승인/거절 버튼이 보이고, 본인 행에는 사용 중지 버튼이 없다(Task 3 테스트).
- CI 의 E2E 백엔드가 `AUTH_APPROVAL=personal` 이라 이메일 가입이 승인 대기가 된다(Task 5 E2E).

---

### Task 1: API, 타입, 로그인 화면

**Files:**
- Modify: `frontend/src/types/index.ts` (`User` 에 `email`, `status`, `has_password`, `google_linked`; `RegisterForm` 에 `email`, `bootstrap_token`; 새 `AuthConfig`)
- Modify: `frontend/src/api/index.ts` (`authApi.config`, `authApi.register` 응답 `User`, `authApi.unlinkGoogle`, `usersApi.approve|reject|disable|enable|releaseEmail`)
- Modify: `frontend/src/contexts/AuthContext.tsx` (`register` 가 서버 응답 `User` 를 돌려준다, 이메일/아이디/토큰을 그대로 넘긴다)
- Modify: `frontend/src/pages/LoginPage.tsx` (칸 라벨, Google 버튼, `?error=` 안내)
- Modify: `frontend/src/utils/errorMessage.ts` + `i18n/{ko,en}/common.json` (4a 의 새 detail 문구 매핑)
- Modify: `frontend/src/i18n/{ko,en}/login.json`
- Test: `frontend/src/test/LoginPage.test.tsx`, `frontend/src/test/AuthContext.test.tsx`, `frontend/src/test/errorMessage-auth.test.ts`

**Interfaces:**
- Produces:
  - `type AuthConfig = { google_enabled: boolean; signup_mode: "bootstrap" | "email" }`
  - `authApi.config(): Promise<AuthConfig>`
  - `authApi.register(form: { username?: string; email?: string; password: string; display_name: string; bootstrap_token?: string }): Promise<User>`
  - `authApi.unlinkGoogle(): Promise<User>`
  - `usersApi.approve(id) / disable(id) / enable(id) / releaseEmail(id): Promise<User>`, `usersApi.reject(id): Promise<void>`
  - `googleStartUrl(mode: "login" | "link", next?: string): string` (`frontend/src/api/client.ts` 의 `API_BASE_URL` 을 앞에 붙인다)
  - `AuthContext.register(form): Promise<User>`

- [ ] **Step 1: 실패하는 테스트**
  - LoginPage: 안내 문구 `아이디 또는 이메일을 입력하세요`; `authApi.config` 가 `google_enabled: true` 면 `Google 로 로그인` 링크가 보이고 href 가 `/api/auth/google/start` 로 끝난다, false 면 없다; 주소가 `/login?error=pending` 이면 `관리자 승인을 기다리는 중입니다.` 가, `?error=company_only` 면 회사 계정 안내가, 모르는 코드면 일반 Google 로그인 실패 문구가 보인다.
  - errorMessage: 4a 문구표 8개가 각각 i18n 키로 바뀐다.
  - AuthContext: `register` 가 `email` 과 `bootstrap_token` 을 그대로 넘기고 응답 `User` 를 돌려준다.
- [ ] **Step 2: 실패 확인** `cd frontend && npx vitest run src/test/LoginPage.test.tsx src/test/AuthContext.test.tsx src/test/errorMessage-auth.test.ts` -> FAIL
- [ ] **Step 3: 구현**
  - `LoginPage`: `useEffect` 로 `authApi.config()` 를 한 번 부르고 실패하면 Google 버튼을 숨긴다. `useSearchParams` 의 `error` 를 `login:googleErrors.<code>` 로 바꿔 처음 오류로 보여 준다(없는 키면 `login:googleErrors.unknown`). 버튼은 `<a href={googleStartUrl("login")}>` 이다.
  - 오류 코드 키(ko/en): `google_state`, `google_verify`, `google_email_unverified`, `company_only`, `pending`, `disabled`, `email_taken`, `already_linked`, `bootstrap_required`, `google_disabled`, `unknown`.
- [ ] **Step 4: 통과 확인** 같은 명령 -> PASS
- [ ] **Step 5: 커밋(로컬)** `feat(auth-ui): 로그인 화면의 이메일 로그인, Google 버튼, 콜백 오류 안내`

### Task 2: 가입 화면(첫 관리자 / 이메일 가입)

**Files:**
- Modify: `frontend/src/pages/RegisterPage.tsx`, `frontend/src/i18n/{ko,en}/register.json`
- Test: `frontend/src/test/RegisterPage.test.tsx`

**Interfaces:**
- Consumes: `authApi.config`, `AuthContext.register`

- [ ] **Step 1: 실패하는 테스트**
  - `signup_mode: "bootstrap"`: 제목 `관리자 계정 만들기`, 아이디 칸(`아이디를 입력하세요`), 중복 확인(`checkUsername`), 설치 토큰 칸(선택, 안내 `운영 환경에서만 필요합니다`)이 있다.
  - `signup_mode: "email"`: 이메일 칸(`이메일을 입력하세요`)이 있고 아이디 칸과 중복 확인이 없다. `register` 에 `{ email, display_name, password }` 가 간다.
  - 응답 `status: "pending"` 이면 `가입 신청이 접수됐습니다. 관리자 승인 후 로그인할 수 있습니다.` 토스트, `active` 면 기존 완료 토스트. 둘 다 `/login` 으로 간다.
  - 검사 순서: 필수 칸 -> 8자 -> 확인 일치.
- [ ] **Step 2: 실패 확인** `npx vitest run src/test/RegisterPage.test.tsx` -> FAIL
- [ ] **Step 3: 구현** `config` 를 받기 전에는 폼을 그리지 않고 로딩 문구를 보여 준다. 실패하면 이메일 모드로 그린다.
- [ ] **Step 4: 통과 확인** -> PASS
- [ ] **Step 5: 커밋(로컬)** `feat(auth-ui): 가입 화면의 첫 관리자 모드와 이메일 가입`

### Task 3: 관리자 사용자 관리

**Files:**
- Modify: `frontend/src/pages/AdminPage.tsx`, `frontend/src/i18n/{ko,en}/admin.json`
- Test: `frontend/src/test/AdminPage.test.tsx`

- [ ] **Step 1: 실패하는 테스트**
  - 목록에 이메일 열, 로그인 방식(`비밀번호` / `Google` / `비밀번호 + Google`), 상태 배지(`사용` / `승인 대기` / `사용 중지`)가 보인다.
  - 승인 대기 사용자가 있으면 표 위에 `승인 대기 N명` 묶음과 각 행의 `승인`, `거절` 버튼. 누르면 `usersApi.approve` / `usersApi.reject`(거절은 확인창) 뒤 목록을 다시 읽는다.
  - 활성 사용자 행에 `사용 중지`(확인창), 중지된 행에 `다시 사용`. 본인 행에는 없다.
  - 이메일이 있고 Google 확인 전(`google_linked` 거짓)인 행에 `이메일 해제`(확인창).
  - 서버 409 의 detail 을 토스트로 보여 준다(`translateError`).
- [ ] **Step 2: 실패 확인** `npx vitest run src/test/AdminPage.test.tsx` -> FAIL
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** -> PASS
- [ ] **Step 5: 커밋(로컬)** `feat(auth-ui): 관리자 화면의 승인 대기, 사용 중지, 이메일 해제`

### Task 4: 머리글의 계정 연결과 결과 안내

**Files:**
- Create: `frontend/src/components/AccountLinkModal.tsx`
- Modify: `frontend/src/components/Header.tsx`, `frontend/src/i18n/{ko,en}/header.json`
- Test: `frontend/src/test/AccountLinkModal.test.tsx`, `frontend/src/test/Header.test.tsx`

- [ ] **Step 1: 실패하는 테스트**
  - 사용자 메뉴에 `계정 연결` 항목. `has_password` 가 거짓이면 `비밀번호 변경` 항목이 없다.
  - 창: 연결 안 됨이면 `Google 계정 연결` 링크(href 가 `/api/auth/google/start?mode=link` 를 포함), 연결됨이면 `연결 해제` 버튼(비밀번호 없는 계정은 버튼 대신 안내 `비밀번호가 없는 계정은 해제할 수 없습니다`). 해제 성공 시 사용자 정보를 다시 읽는다.
  - 주소에 `?account=linked` 가 있으면 성공 토스트, 다른 코드면 `login:googleErrors.<code>` 오류 토스트를 한 번 보여 주고 쿼리를 지운다.
- [ ] **Step 2: 실패 확인** `npx vitest run src/test/AccountLinkModal.test.tsx src/test/Header.test.tsx` -> FAIL
- [ ] **Step 3: 구현** `AuthContext` 에 `refreshUser()` 를 더해 해제 뒤 `/me` 를 다시 읽는다.
- [ ] **Step 4: 통과 확인** -> PASS
- [ ] **Step 5: 커밋(로컬)** `feat(auth-ui): 머리글의 Google 계정 연결과 해제`

### Task 5: E2E 와 CI

**Files:**
- Modify: E2E 의 로그인 도우미와 단언(안내 문구 교체, `TC-AUTH-006` 의 `아이디` 를 `이메일` 로), `frontend/src/test/App.test.tsx`
- Create: `frontend/e2e/account-approval.spec.ts`
- Modify: `.github/workflows/ci.yml` (E2E 백엔드 환경변수, 스펙 목록)

- [ ] **Step 1: 새 E2E**
  - 이메일 가입(승인 대기 안내) -> 그 계정으로 로그인하면 승인 대기 안내 -> 관리자가 API 로 승인 -> 로그인 성공.
  - 관리자가 사용자를 사용 중지 -> 그 사용자의 다음 화면 이동이 로그인 화면으로 간다.
  - 로그인 화면에 `Google 로 로그인` 이 보이고, `/api/auth/google/start` 응답이 `accounts.google.com` 으로 302.
- [ ] **Step 2: CI** E2E 의 `Start backend` 에 `AUTH_APPROVAL=personal`, `GOOGLE_CLIENT_ID=ci-dummy.apps.googleusercontent.com`, `GOOGLE_CLIENT_SECRET=ci-dummy`, `GOOGLE_REDIRECT_URI=http://localhost:5173/api/auth/google/callback`, `REGISTER_MAX_PER_HOUR=1000` 를 넣고 스펙 목록에 `e2e/account-approval.spec.ts` 를 더한다.
- [ ] **Step 3: 격리 환경에서 E2E 전체 실행** -> PASS
- [ ] **Step 4: 커밋(로컬)** `test(auth): E2E 승인 흐름과 CI 인증 설정`

### Task 6: 문서, 버전, 릴리즈 기록

**Files:**
- Modify: `README.md` (로그인 정책 환경변수, Google 클라이언트 만들기, 회사 배포 권장값, `BOOTSTRAP_TOKEN`, 퇴사자 처리)
- Modify: `docs/manual_admin_confluence.md`, `frontend/src/pages/AdminManualPage.tsx` + `i18n/{ko,en}/adminManual.json` (승인, 중지, 이메일 해제, 계정 연결)
- Modify: `TC_Manager_Regression_Checklist_v2_merged.xlsx` (인증 행 추가)
- Modify: 버전 사본(`backend/main.py`, `frontend/package.json`, `package-lock.json`, 푸터 `common.json`), `Release_note.md`, `Issue_list.xlsx`

- [ ] **Step 1:** 문서 수정, deslop 검사(`technical`, 릴리즈 노트는 `release`), release-lint.
- [ ] **Step 2:** Linear 이슈(issuelog): 작업 이슈 1건(조직 계정 인증) + QA 에서 나온 결함들. 닫힌 상태로 등록하고 릴리즈 노트 `### 이슈` 에 적는다.
- [ ] **Step 3:** 버전 일관성 테스트 통과, 커밋(로컬).
- [ ] **Step 4:** QA 2인(화면 + 전체) -> 대조 -> 수정 -> 푸시 -> CI 확인.
