# 조직 계정 인증 설계 (하위 프로젝트 2)

- 날짜: 2026-10-09
- 상위 설계: `docs/superpowers/specs/2026-10-08-postgresql-vercel-supabase-design.md` 의 하위 프로젝트 2
- 상태: 사용자 검토 대기

## 목표

회사 팀이 인터넷에 배포된 YM TestCase 를 쓸 때, 들어올 수 있는 사람을 배포자가 환경변수로 정한다.
같은 코드로 "누구나 바로 사용", "회사 계정만", "회사 계정은 바로, 나머지는 승인 후" 를 모두 낼 수 있어야 한다.

## 사용자가 정한 것

- 로그인은 Google 로그인과 이메일 가입 두 가지를 받는다. Google 연동이 막히는 경우를 대비한 것이다.
- 개인 메일 허용 여부, 승인 필요 여부를 환경변수로 고른다. 승인의 기본값은 "승인 없음" 이다.
- `.env.example` 에 선택지를 모두 적고 기본값만 켠다. 나머지는 주석으로 둔다.
- 이메일 가입은 메일 인증 대신 관리자 승인으로 확인한다. 1회용 코드는 쓰지 않는다.
- 기존 계정과 Google 계정은 이메일로 자동 연결하지 않는다. 로그인한 본인이 연결 버튼을 누른다.
- Google 연동은 서버가 Google 과 직접 주고받는 방식(인가 코드 흐름)으로 한다. 화면에 Google 스크립트를 넣지 않는다.

## 환경변수

`backend/.env.example` 에 아래 모양으로 넣는다. 실제 파일에는 줄마다 한글 설명을 단다.

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:5173/api/auth/google/callback

AUTH_COMPANY_DOMAINS=
# AUTH_COMPANY_DOMAINS=company.com

AUTH_ALLOW_PERSONAL=1
# AUTH_ALLOW_PERSONAL=0

AUTH_APPROVAL=none
# AUTH_APPROVAL=personal
# AUTH_APPROVAL=all
```

- `GOOGLE_CLIENT_ID` 가 비어 있으면 Google 로그인을 끈다. 버튼도 숨긴다.
- `GOOGLE_REDIRECT_URI` 는 Google 콘솔에 등록한 주소와 글자까지 같아야 한다. 요청 헤더로 주소를 짐작하지 않는다.
- `AUTH_COMPANY_DOMAINS` 는 쉼표로 여러 개를 받는다. 소문자로 맞추고 앞뒤 공백을 버린다.
- `AUTH_ALLOW_PERSONAL=0` 이면 회사 도메인 밖 계정을 받지 않는다. 이때 `AUTH_COMPANY_DOMAINS` 가 비어 있으면 아무도 가입할 수 없으므로 서버가 기동 때 멈춘다.
- `AUTH_APPROVAL` 은 `none` / `personal` / `all` 셋 중 하나다. 다른 값이면 기동 때 멈춘다.
- 회사 배포(비공개 레포)의 권장값은 `AUTH_APPROVAL=personal` 이다. 기본값 `none` 은 누구나 가입해 바로 쓰는 설정이라 README 배포 절에 이 점을 적는다.

## 계정 판정

새 계정의 상태는 아래 규칙 하나로 정한다. 같은 함수를 Google 신규 계정과 이메일 가입이 함께 쓴다.

- 회사 계정: Google 로그인이고, Google 이 준 Workspace 도메인(`hd`)이 `AUTH_COMPANY_DOMAINS` 에 있다.
- 확인 안 된 계정: 이메일 가입은 도메인과 상관없이 여기에 든다. 메일을 보내지 않으므로 주소 소유를 확인할 수 없다.
- 개인 계정: 그 밖의 Google 계정.

| `AUTH_APPROVAL` | 회사 계정 | 개인 계정 | 이메일 가입 |
|---|---|---|---|
| none | 사용 | 사용 | 사용 |
| personal | 사용 | 승인 대기 | 승인 대기 |
| all | 승인 대기 | 승인 대기 | 승인 대기 |

- `AUTH_ALLOW_PERSONAL=0` 이면 개인 계정은 거절한다. 이메일 가입은 이메일 도메인이 `AUTH_COMPANY_DOMAINS` 에 있을 때만 받는다(도메인 검사는 하되 상태는 위 표를 따른다).
- 회사 도메인 판정에 이메일 끝자리를 쓰지 않는 이유: 회사 주소로 만든 개인 Google 계정이 있다. 그런 계정은 `hd` 가 없다.
- 첫 번째 계정은 이 규칙과 상관없이 관리자이고 바로 사용한다.

## 계정 데이터

`users` 표를 바꾼다. 마이그레이션 하나(0007)로 한다.

- `email`: 문자열, 비어도 됨, 소문자로 저장, 유일. 기존 계정은 비어 있다.
- `google_sub`: 문자열, 비어도 됨, 유일. Google 이 계정마다 주는 고유 번호다. Google 로그인은 이 칸으로 계정을 찾는다.
- `status`: `active` / `pending` / `disabled`. 기존 행은 `active` 로 채운다.
- `password_hash`: 비어도 되게 바꾼다. Google 로만 가입한 계정에는 비밀번호가 없다. 비어 있으면 비밀번호 로그인은 항상 실패한다.

이메일 가입과 Google 신규 계정은 `username` 에 이메일을 넣는다. 같은 문자열의 아이디가 이미 있으면 가입을 거절한다(기존 아이디는 이메일 모양이 아니어서 실제로 겹칠 일은 드물다).

## Google 로그인

### 시작

`GET /api/auth/google/start?next=<경로>&mode=login|link`

- `state`, `nonce`, PKCE `code_verifier` 를 새로 만든다.
- 세 값과 `mode`, `next`, 연결 모드면 현재 사용자 id 를 서명한 쿠키(`oauth_flow`, httpOnly, SameSite=Lax, 10분, 경로 `/api/auth/google`)에 담는다. 서명은 기존 `SECRET_KEY` 로 한다.
- Google 인가 주소로 302. 범위는 `openid email profile`, `prompt=select_account`.
- 연결 모드는 로그인한 세션이 있어야 한다. 없으면 401.

### 콜백

`GET /api/auth/google/callback?code=...&state=...`

1. `oauth_flow` 쿠키를 읽고 서명과 만료를 확인한다. 쿠키의 `state` 와 쿼리의 `state` 가 다르면 거절한다. 쿠키는 성공이든 실패든 지운다.
2. 인가 코드를 토큰 주소에서 교환한다(클라이언트 비밀, `code_verifier` 포함).
3. ID 토큰을 Google 공식 라이브러리 `google-auth` 의 `id_token.verify_oauth2_token` 으로 검증한다. 서명, `aud`(우리 클라이언트 ID), `iss`, 만료를 본다. `nonce` 가 쿠키 값과 같아야 하고 `email_verified` 가 참이어야 한다.
4. 계정 판정 규칙으로 회사/개인을 가른다. 개인 계정인데 `AUTH_ALLOW_PERSONAL=0` 이면 거절한다.
5. 로그인 모드
   - `google_sub` 로 계정을 찾는다. 있으면 상태를 보고 로그인시킨다.
   - 없고 같은 이메일을 쓰는 계정이 있으면 새로 만들지 않고 `email_taken` 으로 거절한다.
   - 없으면 새 계정을 만든다. `display_name` 은 Google 이름, 없으면 이메일 앞부분이다.
   - 새 계정이 승인 대기면 로그인시키지 않고 `pending` 으로 안내한다.
6. 연결 모드
   - 세션의 사용자와 쿠키의 사용자 id 가 같아야 한다.
   - 그 `google_sub` 가 다른 계정에 이미 있으면 `already_linked` 로 거절한다.
   - 지금 계정에 `google_sub` 를 넣는다. 계정의 `email` 이 비어 있으면 Google 이메일로 채운다(다른 계정이 쓰는 이메일이면 채우지 않는다).
7. 성공하면 기존 로그인과 같은 쿠키(`access_token`, `csrf_token`)를 심고 `next` 로 302. 실패하면 `/login?error=<코드>` 로 302. 연결 모드의 성공과 실패는 내 정보 화면으로 돌려보낸다.

`next` 는 `/` 로 시작하고 `//` 로 시작하지 않는 경로만 받는다. 아니면 `/projects` 로 바꾼다.

### 연결 해제

`POST /api/auth/google/unlink` (로그인 필요, CSRF 확인)

- 비밀번호가 없는 계정은 해제를 거절한다. 해제하면 들어올 방법이 없어진다.

## 이메일 가입과 첫 설치

`GET /api/auth/config` 가 화면에 켜진 기능을 알린다.

```json
{ "google_enabled": true, "signup_mode": "bootstrap" }
```

- `signup_mode` 가 `bootstrap` 이면 사용자가 0명이다. 가입 화면은 "관리자 계정 만들기" 로 바뀌고 지금처럼 아이디, 이름, 비밀번호를 받는다.
- 사용자가 1명 이상이면 `email` 이다. 가입은 이메일, 이름, 비밀번호(8자 이상)를 받는다.

`POST /api/auth/register`

- 사용자가 0명이면 아이디 가입을 받고 관리자, 사용으로 만든다. CI 의 관리자 시드가 이 경로를 쓴다.
- 사용자가 있으면 `email` 이 필수다. 판정 규칙으로 상태를 정한다. 응답에 `status` 를 담아 화면이 안내 문구를 고른다.
- 지금처럼 전역 잠금(`FIRST_ADMIN`) 안에서 사용자 수를 센다. 동시 가입으로 관리자가 둘 생기는 결함(SYM-136)을 다시 열지 않는다.
- `GET /api/auth/check-username` 은 첫 설치 화면에서만 쓴다. 사용자가 있으면 404.

## 로그인

`POST /api/auth/login`

- `username` 칸에 아이디 또는 이메일을 받는다. `@` 가 있으면 이메일(소문자)로, 없으면 아이디로 찾는다.
- 비밀번호가 맞은 뒤에만 상태를 본다. `pending` 이면 403 "관리자 승인을 기다리는 중입니다", `disabled` 면 403 "사용이 중지된 계정입니다". 비밀번호가 틀리면 지금처럼 401 한 가지로 답한다.
- 횟수 제한, 비밀번호 찾기(관리자 승인 + 1회용 코드)는 바꾸지 않는다.

## 사용 중지의 효력

- `get_current_user` 가 쿠키 세션과 API 키 둘 다에서 `status == active` 를 확인한다.
- 사용 중지할 때 `token_version` 을 1 올려 발급된 JWT 를 무효로 만든다.

## 관리자 화면과 API

관리 > 사용자 화면을 바꾼다.

- 목록에 이메일, 로그인 방식(비밀번호 / Google / 둘 다), 상태를 더한다.
- 맨 위에 승인 대기 목록과 건수를 둔다.
- 버튼: 승인, 거절, 사용 중지, 다시 사용.

API (관리자 전용, CSRF 확인)

- `POST /api/auth/users/{id}/approve`: `pending` 을 `active` 로.
- `POST /api/auth/users/{id}/reject`: `pending` 계정을 지운다. 한 번도 쓰지 않은 계정이다. `pending` 이 아니면 409. 지웠으므로 같은 사람이 다시 신청할 수 있다. 다시 못 들어오게 하려면 거절 대신 사용 중지를 쓴다.
- `POST /api/auth/users/{id}/disable`: 자기 자신과 마지막 활성 관리자는 409.
- `POST /api/auth/users/{id}/enable`
- `GET /api/auth/users` 응답에 `email`, `status`, `has_password`, `google_linked` 를 더한다.

같은 사용자를 두 관리자가 동시에 처리하는 경우는 행 잠금(`SELECT ... FOR UPDATE`)으로 순서를 세운다. 마지막 활성 관리자 판정도 그 안에서 한다.

## 오류 코드

콜백이 `/login?error=` 로 넘기는 값. 화면은 i18n 문구로 바꿔 보여 준다.

- `google_state`: 확인값이 없거나 다르다(10분 초과 포함)
- `google_verify`: 토큰 교환이나 검증 실패
- `google_email_unverified`
- `company_only`: 회사 계정만 받는 설정
- `pending`, `disabled`
- `email_taken`: 같은 이메일의 계정이 있다
- `already_linked`: 그 Google 계정이 다른 계정에 연결돼 있다
- `google_disabled`: `GOOGLE_CLIENT_ID` 가 없다

Google 이 `error=access_denied` 로 돌려보내면(사용자가 취소) 메시지 없이 로그인 화면으로 돌아간다.

## 보안 메모

- 토큰, 인가 코드, 클라이언트 비밀은 로그에 남기지 않는다.
- CSP 는 바꾸지 않는다. Google 로 가는 것은 페이지 이동이라 `connect-src` 나 `script-src` 가 필요 없다.
- `oauth_flow` 쿠키가 SameSite=Lax 여야 Google 에서 돌아오는 최상위 이동에 실린다. 세션 쿠키는 이미 Lax 다.
- 연결 모드에서 쿠키의 사용자 id 를 세션과 대조하는 이유: 다른 사람이 시작한 연결 흐름의 콜백 주소를 피해자에게 열게 해서 공격자의 Google 계정을 피해자 계정에 붙이는 공격을 막는다.

## 테스트

백엔드

- 계정 판정 함수: 세 설정 x 세 계정 종류 x `AUTH_ALLOW_PERSONAL` 두 값의 표 테스트.
- 환경변수 검증: 잘못된 `AUTH_APPROVAL`, 회사 도메인 없이 `AUTH_ALLOW_PERSONAL=0` 이면 기동 실패.
- 콜백: 토큰 교환과 ID 토큰 검증을 가짜로 바꿔 로그인, 신규 생성, 승인 대기, 회사 계정만, `email_taken`, `already_linked`, state 불일치, nonce 불일치, `email_verified` 거짓, 열린 리디렉션 차단을 본다.
- 연결 모드: 세션 사용자와 쿠키 사용자 id 가 다르면 거절.
- 로그인: 이메일 로그인, 승인 대기와 사용 중지 사유는 비밀번호가 맞을 때만 나온다.
- 사용 중지: 기존 JWT 와 API 키가 바로 401.
- 관리자: 마지막 활성 관리자 중지 거절, 동시 승인·거절, 거절은 `pending` 만.
- 첫 설치: 사용자 0명일 때만 아이디 가입, 동시 가입에서 관리자 1명.

E2E

- 이메일 가입(승인 대기) -> 관리자 승인 -> 로그인.
- 사용 중지 -> 그 사용자의 다음 요청이 로그인 화면으로 간다.
- `GOOGLE_CLIENT_ID` 가 있을 때 Google 버튼이 보이고 `/api/auth/google/start` 로 간다(실제 Google 로그인은 E2E 에서 하지 않는다).

실제 Google 로그인은 로컬 클라이언트(개인 계정 프로젝트)로 손으로 확인한다. 개인 Gmail, 회사 Workspace 계정, 취소, 연결, 해제를 본다.

## 하지 않을 것

- 메일 발송과 이메일 주소 인증
- Google 외 다른 로그인(Microsoft, GitHub 등)
- Workspace 그룹이나 조직 단위로 역할을 정하는 기능
- 기존 계정과 Google 계정을 이메일로 자동 연결
- 초대 코드
- Supabase 로 옮겨 실제로 띄우기(하위 프로젝트 3)

## 배포 메모

- Google 콘솔의 클라이언트에 배포 주소의 리디렉션 URI(`https://<도메인>/api/auth/google/callback`)와 JavaScript 원본을 더한다.
- Vercel 환경변수에 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `AUTH_*` 를 넣는다.
- 팀에 열기 전에 Google 콘솔의 게시 상태를 "프로덕션" 으로 바꾼다. 테스트 상태에서는 테스트 사용자로 등록한 계정만 로그인된다.
- CI 의 관리자 시드는 첫 설치 경로라 바꾸지 않는다.
