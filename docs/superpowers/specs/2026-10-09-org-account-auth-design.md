# 조직 계정 인증 설계 (하위 프로젝트 2)

- 날짜: 2026-10-09
- 상위 설계: `docs/superpowers/specs/2026-10-08-postgresql-vercel-supabase-design.md` 의 하위 프로젝트 2
- 상태: 사용자 검토 대기 (QA 2인 1차 검토 반영)

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

상위 설계의 "관리자 승인 + 1회용 코드 가입", "공개 가입 제거" 는 이 문서의 결정으로 바뀐다. 가입은 남기고, 막을지는 환경변수로 정한다.

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

# 운영(ENV=production)에서 빈 DB 의 첫 관리자를 만들 때만 쓴다
BOOTSTRAP_TOKEN=
```

- `GOOGLE_CLIENT_ID` 가 비어 있으면 Google 로그인을 끈다. 버튼도 숨긴다.
- `GOOGLE_REDIRECT_URI` 는 Google 콘솔에 등록한 주소와 글자까지 같아야 한다. 요청 헤더로 주소를 짐작하지 않는다.
- `AUTH_COMPANY_DOMAINS` 는 쉼표로 여러 개를 받는다. 소문자로 맞추고 앞뒤 공백을 버린다.
- 설정 검사는 모듈을 임포트할 때 한다(서버리스는 lifespan 을 부르지 않을 수 있다. `main.py` 의 기존 검사와 같은 자리). 아래면 기동을 멈춘다.
  - `AUTH_APPROVAL` 이 `none` / `personal` / `all` 밖의 값
  - `AUTH_ALLOW_PERSONAL` 이 `0` / `1` 밖의 값
  - `AUTH_ALLOW_PERSONAL=0` 인데 `AUTH_COMPANY_DOMAINS` 가 비어 있음(아무도 가입할 수 없다)
  - `GOOGLE_CLIENT_ID` 는 있는데 `GOOGLE_CLIENT_SECRET` 이나 `GOOGLE_REDIRECT_URI` 가 비어 있음
- 회사 배포(비공개 레포)의 권장값은 `AUTH_APPROVAL=personal` 이다. 기본값 `none` 은 누구나 가입해 바로 쓰는 설정이라 README 배포 절에 이 점을 적는다.
- 배포는 `ENV=production` 과 고정 `SECRET_KEY` 가 필수다(상위 설계와 같다). 인스턴스마다 키가 다르면 Google 로그인 확인값 검증이 간헐로 실패한다.

## 계정 판정

새 계정의 상태는 함수 하나로 정한다. 설정을 인자로 받는 순수 함수로 만들어 표 테스트를 할 수 있게 한다. Google 신규 계정과 이메일 가입이 함께 쓴다.

- 회사 계정: Google 로그인이고, Google 이 준 Workspace 도메인(`hd`)이 `AUTH_COMPANY_DOMAINS` 에 있다.
- 개인 계정: 그 밖의 Google 계정.
- 이메일 가입: 도메인과 상관없이 따로 다룬다. 메일을 보내지 않으므로 주소 소유를 확인할 수 없다.

`AUTH_ALLOW_PERSONAL=1` 일 때

| `AUTH_APPROVAL` | 회사 계정 | 개인 계정 | 이메일 가입 |
|---|---|---|---|
| none | 사용 | 사용 | 사용 |
| personal | 사용 | 승인 대기 | 승인 대기 |
| all | 승인 대기 | 승인 대기 | 승인 대기 |

`AUTH_ALLOW_PERSONAL=0` 일 때 (회사 계정만)

- 개인 계정은 거절한다(`company_only`).
- 이메일 가입은 이메일 도메인이 `AUTH_COMPANY_DOMAINS` 에 있을 때만 받고, **`AUTH_APPROVAL` 과 상관없이 항상 승인 대기**다. 회사 주소를 적기만 하면 회사 사람으로 통과하는 구멍을 막기 위해서다(QA 2인 공통 지적).
- 회사 계정은 위 표의 회사 계정 칸을 따른다.

회사 도메인 판정에 이메일 끝자리를 쓰지 않는 이유: 회사 주소로 만든 개인 Google 계정이 있다. 그런 계정은 `hd` 가 없다.

설정을 바꿔도 이미 있는 계정의 상태는 소급해서 바꾸지 않는다. 예를 들어 `AUTH_ALLOW_PERSONAL=0` 으로 바꾸면 개인 Google 계정의 Google 로그인은 막히지만, 그 계정에 비밀번호가 있으면 비밀번호 로그인은 된다. 막으려면 관리자가 사용 중지한다.

## 계정 데이터

`users` 표를 바꾼다. 마이그레이션 하나(0007)로 한다.

- `email`: 문자열(100자), 비어도 됨, 소문자로 저장, 유일. 기존 계정은 비어 있다.
- `email_verified`: 불리언, `server_default false`. Google 이 확인해 준 이메일이면 참이다. 이메일 가입은 거짓이다.
- `google_sub`: 문자열, 비어도 됨, 유일. Google 이 계정마다 주는 고유 번호다. Google 로그인은 이 칸으로 계정을 찾는다.
- `status`: `active` / `pending` / `disabled`, `server_default 'active'`. 기존 행은 기본값으로 채워진다. SQLite 이관 스크립트는 원본에 없는 칸을 빼고 INSERT 하므로 서버 기본값이 꼭 있어야 한다.
- `password_hash`: 비어도 되게 바꾼다. Google 로만 가입한 계정에는 비밀번호가 없다.

`account_requests.user_id` 와 `resolved_by_id` 의 외래키는 `ON DELETE SET NULL` 로 바꾼다. 승인 대기 계정을 거절(삭제)할 때 복구 이력 때문에 삭제가 막히지 않게 한다.

길이

- 이메일은 100자 이하만 받는다. 넘으면 422. `username` 칸이 100자다.
- Google 이름은 100자로 잘라 `display_name` 에 넣는다.

이메일 가입과 Google 신규 계정은 `username` 에 이메일을 넣는다. 그 문자열의 아이디가 이미 있으면 Google 신규 계정은 `이메일#숫자` 로 비켜 만든다(로그인은 Google 로 하므로 아이디를 쓸 일이 없다). 이메일 가입은 거절한다.

## 계정 변경의 직렬화

계정을 만들거나 신원·상태·역할을 바꾸는 모든 경로는 전역 트랜잭션 잠금 하나(기존 `FIRST_ADMIN` 네임스페이스를 `ACCOUNTS` 로 이름만 바꿔 재사용)를 잡고, 그 안에서 사용자 수와 활성 관리자 수를 센다.

- 대상: 이메일 가입, 첫 관리자 만들기, Google 신규 계정, 계정 연결과 해제, 이메일 채우기, 승인, 거절, 사용 중지, 다시 사용, 역할 변경, 이메일 해제.
- 관리자 둘이 서로를 동시에 중지하거나 강등해도 활성 관리자가 0명이 되지 않는다. 행 잠금만으로는 서로 다른 행을 잡아 둘 다 통과한다(QA 2인 공통 지적).
- 유일 제약 위반(같은 `google_sub`, 같은 이메일)은 되돌린 뒤 `already_linked` / `email_taken` 으로 바꿔 답한다. 500 으로 내보내지 않는다.
- 잠금을 잡은 요청은 성공, 409, 리디렉션 어느 쪽으로 나가든 응답 전에 커밋하거나 되돌린다. `get_db` 정리는 응답을 보낸 뒤에 돌아서 잠금이 다음 요청까지 남는다(SYM-145 와 같은 유형).
- bcrypt 는 잠금 밖에서 한다(지금 가입과 같다).

## 첫 관리자

- 사용자가 0명이면 `GET /api/auth/config` 가 `signup_mode: "bootstrap"` 을 알리고, 가입 화면은 "관리자 계정 만들기" 로 바뀐다. 지금처럼 아이디, 이름, 비밀번호를 받는다.
- `ENV=production` 이면 `BOOTSTRAP_TOKEN` 이 설정돼 있고 입력값과 같을 때만 만든다. 인터넷에 열린 빈 DB 에서 먼저 들어온 사람이 관리자가 되는 것을 막는다. 개발 환경과 CI 는 토큰 없이 지금처럼 된다.
- 사용자가 0명일 때 Google 로그인은 `bootstrap_required` 로 거절한다. 첫 관리자는 위 경로로만 만든다.
- 첫 계정은 판정 규칙과 상관없이 관리자이고 바로 사용한다.

## Google 로그인

### 시작

`GET /api/auth/google/start?next=<경로>&mode=login|link`

- `state`, `nonce`, PKCE `code_verifier` 를 새로 만든다.
- 인가 요청에 `state`, `nonce`, `code_challenge`(S256), `code_challenge_method=S256` 을 싣는다. 범위는 `openid email profile`, `prompt=select_account`.
- 확인값은 쿠키 `oauth_flow` 에 담는다.
  - 내용: `state`, `nonce`, `code_verifier`, `mode`, `next`, 연결 모드면 시작한 사용자 id, `use: "oauth_flow"`. `sub` 칸은 쓰지 않는다. 로그인 JWT 와 섞이지 않게 하기 위해서다.
  - 서명: `SECRET_KEY` 로 서명한 JWT, 만료 10분.
  - 속성: httpOnly, SameSite=Lax, Secure 는 `COOKIE_SECURE` 를 따른다, 경로 `/api/auth/google`. 지울 때도 같은 경로를 준다.
- 연결 모드는 쿠키 세션으로 로그인해 있어야 한다(API 키 인증은 받지 않는다). 아니면 401.

### 콜백

`GET /api/auth/google/callback?code=...&state=...`

순서를 고정한다. 외부 호출 동안 DB 트랜잭션을 열어 두지 않기 위해서다.

1. 쿠키 검증(DB 없음). `oauth_flow` 의 서명, 만료, `use` 를 확인한다. 쿠키나 쿼리의 `state` 가 없거나 서로 다르면 거절한다. 쿠키는 성공이든 실패든 지운다.
2. 토큰 교환과 검증(DB 없음).
   - 인가 코드를 토큰 주소에서 교환한다(클라이언트 비밀, `code_verifier` 포함). 시간 제한 10초.
   - ID 토큰은 `google-auth` 의 `id_token.verify_oauth2_token` 으로 검증한다. 서명, `aud`(우리 클라이언트 ID), `iss`, 만료를 본다. 시계 오차는 10초까지 허용한다.
   - `nonce` 가 쿠키 값과 같아야 하고 `email_verified` 가 참이어야 한다.
   - `google-auth` 의 HTTP 전송은 `requests` 를 쓴다. `requests` 를 운영 `requirements.txt` 에 넣는다(지금은 개발 의존성에만 있다).
3. 짧은 DB 트랜잭션. `ACCOUNTS` 잠금을 잡는다.
   - 회사/개인을 판정한다. 개인 계정인데 `AUTH_ALLOW_PERSONAL=0` 이면 `company_only`.
   - 로그인 모드
     - `google_sub` 로 계정을 찾는다. 있으면 상태를 본다. `pending` 이면 `pending`, `disabled` 면 `disabled`, `active` 면 로그인시킨다.
     - 없고 같은 이메일을 쓰는 계정이 있으면 `email_taken`. 새로 만들지 않는다.
     - 없으면 새 계정을 만든다(`email_verified` 참). 승인 대기면 로그인시키지 않고 `pending` 으로 안내한다.
   - 연결 모드
     - 세션의 사용자와 쿠키의 사용자 id 가 같아야 한다.
     - 그 `google_sub` 가 다른 계정에 있으면 `already_linked`. 지금 계정에 이미 다른 `google_sub` 가 있으면 덮어쓰지 않고 `already_linked`(먼저 해제해야 한다).
     - 지금 계정에 `google_sub` 를 넣는다. 계정의 `email` 이 비어 있고 그 이메일을 다른 계정이 쓰지 않으면 Google 이메일로 채우고 `email_verified` 를 참으로 둔다.
   - 응답 전에 커밋하거나 되돌린다.
4. 성공하면 기존 로그인과 같은 쿠키(`access_token`, `csrf_token`)를 심고 `next` 로 302. 로그인 실패는 `/login?error=<코드>` 로, 연결 모드의 결과는 `/projects?account=<linked|코드>` 로 302.

`next` 검사

- `/` 로 시작해야 한다. `//`, `/\` 로 시작하면 안 된다.
- 백슬래시, 제어문자, 공백을 거절한다.
- `urllib.parse.urlsplit` 결과의 scheme 과 netloc 이 비어 있어야 한다.
- 하나라도 어기면 `/projects` 로 바꾼다.

### 연결 해제

`POST /api/auth/google/unlink` (쿠키 세션, CSRF 확인)

- 비밀번호가 없는 계정은 거절한다. 해제하면 들어올 방법이 없어진다.

### 화면

- 로그인 화면에 "Google 로 로그인" 버튼. `GOOGLE_CLIENT_ID` 가 없으면 숨긴다.
- 연결과 해제는 머리글 사용자 메뉴의 "계정 연결" 창에서 한다(API 키 창과 같은 방식). 내 정보 화면은 따로 만들지 않는다.

## 이메일 가입

`POST /api/auth/register`

- 사용자가 0명이면 첫 관리자 경로(위)다.
- 사용자가 있으면 `email`, `display_name`, `password`(8자 이상)가 필수다. 판정 규칙으로 상태를 정하고 응답에 `status` 를 담는다. 화면은 `active` 면 "가입이 끝났습니다. 로그인하세요", `pending` 이면 "가입 신청이 접수됐습니다. 관리자 승인 후 로그인할 수 있습니다" 를 보여 준다.
- 이메일은 `username` 과 `email` 두 칸 모두에서 겹치는지 본다.
- IP 기준 횟수 제한을 건다(1시간 10회). 비밀번호 찾기 접수의 제한 방식을 재사용한다. 인터넷에 열린 진입점이라 bcrypt 비용과 승인 대기 목록 스팸을 막는다.
- `GET /api/auth/check-username` 은 첫 관리자 화면에서만 쓴다. 사용자가 있으면 404.

## 로그인

`POST /api/auth/login`

- 식별자 정규화: 앞뒤 공백을 버리고, `@` 가 있으면 소문자로 바꾼다. 횟수 제한 기록 키도 정규화한 값으로 만든다. 대소문자를 바꿔 제한을 비켜 가지 못하게 한다.
- 조회 순서: `email` 칸에서 먼저 찾고, 없으면 `username` 칸에서 찾는다. `@` 가 든 옛 아이디도 계속 로그인된다(실데이터에는 0건).
- `verify_password` 는 해시가 비어 있으면 더미 해시와 한 번 대조한 뒤 거짓을 돌려준다. 계정이 없을 때도 같은 더미 대조를 한다. 응답 시간으로 계정 유무가 새지 않게 한다.
- 비밀번호가 맞은 뒤에만 상태를 본다. `pending` 이면 403 "관리자 승인을 기다리는 중입니다", `disabled` 면 403 "사용이 중지된 계정입니다". 비밀번호가 틀리면 지금처럼 401 한 가지로 답한다.

## 비밀번호와 복구

- 비밀번호가 없는 계정(Google 전용)은 비밀번호 변경 메뉴를 숨기고, API 는 400 "비밀번호가 없는 계정입니다" 로 답한다.
- 비밀번호 찾기(관리자 승인 + 1회용 코드)는 그대로 둔다. Google 전용 계정도 쓸 수 있고, 쓰면 비밀번호가 생긴다.
- 비밀번호 찾기 승인과 코드 확인은 대상 계정이 `active` 일 때만 된다. 승인 대기와 사용 중지 계정은 409.
- 코드 확인의 식별자도 로그인과 같은 정규화와 조회 순서를 쓴다.
- 계정을 되찾는 자리(본인 비밀번호 변경 제외, 관리자 초기화와 비밀번호 찾기 완료)에서는 지금 API 키를 폐기하듯 Google 연결도 끊는다. 탈취한 쪽이 자기 Google 계정을 연결해 두었으면 복구 뒤에도 그 길로 다시 들어오기 때문이다. 정당한 사용자는 다시 연결하면 된다.

## 상태 전이

| 동작 | 허용 출발 상태 | 결과 | 그 밖 |
|---|---|---|---|
| 승인 | pending | active | 409 |
| 거절 | pending | 계정 삭제 | 409 |
| 사용 중지 | active, pending | disabled | 409 |
| 다시 사용 | disabled | active | 409 |

- 사용 중지: `token_version` 을 1 올려 JWT 를 무효로 하고, 그 사용자의 API 키를 모두 폐기한다(`revoke_user_api_keys`). 다시 사용해도 옛 키는 살아나지 않는다.
- 자기 자신, 그리고 마지막 활성 관리자는 사용 중지할 수 없다. 역할 변경(`PUT /users/{id}/role`)에도 마지막 활성 관리자 강등 금지를 넣는다. 지금은 이 검사가 없다.
- 거절은 계정을 지우므로 같은 사람이 다시 신청할 수 있다. 다시 못 들어오게 하려면 사용 중지를 쓴다.
- `get_current_user` 는 쿠키 세션과 API 키 두 경로 모두에서 `status == active` 를 확인한다. API 키 경로는 일찍 반환하므로 그 함수 안에서도 확인한다.

## 이메일 선점 정리

이메일 가입은 주소를 확인하지 않으므로 남의 주소로 가입해 그 이메일을 차지할 수 있다. 그러면 진짜 주인의 Google 로그인이 `email_taken` 으로 막힌다.

- 관리자에게 "이메일 해제" 를 준다(`POST /api/auth/users/{id}/release-email`). 대상의 `email` 을 비우고, `username` 이 그 이메일이면 `released-<id>` 로 바꾼다. `email_verified` 가 참인 계정(Google 이 확인한 이메일)은 해제할 수 없다.
- `email_taken` 안내 문구: "이 이메일을 쓰는 계정이 이미 있습니다. 본인 계정이면 그 계정으로 로그인한 뒤 Google 계정을 연결하세요. 아니면 관리자에게 문의하세요."

## 관리자 화면과 API

관리 > 사용자 화면을 바꾼다.

- 목록에 이메일, 로그인 방식(비밀번호 / Google / 둘 다), 상태를 더한다.
- 맨 위에 승인 대기 목록과 건수를 둔다.
- 버튼: 승인, 거절, 사용 중지, 다시 사용, 이메일 해제.

API (관리자 전용, CSRF 확인)

- `POST /api/auth/users/{id}/approve`
- `POST /api/auth/users/{id}/reject`
- `POST /api/auth/users/{id}/disable`
- `POST /api/auth/users/{id}/enable`
- `POST /api/auth/users/{id}/release-email`
- `GET /api/auth/users` 응답에 `email`, `status`, `has_password`, `google_linked` 를 더한다.

운영 안내(관리자 매뉴얼): 퇴사자는 Workspace 계정을 지워도 앱의 로그인(최대 30일)과 API 키가 남는다. 관리자가 사용 중지해야 바로 막힌다.

## 오류 코드

콜백이 넘기는 값. 화면은 i18n 문구로 바꿔 보여 준다.

- `google_state`: 확인값이 없거나 다르다(10분 초과 포함)
- `google_verify`: 토큰 교환이나 검증 실패
- `google_email_unverified`
- `company_only`: 회사 계정만 받는 설정
- `pending`, `disabled`
- `email_taken`: 같은 이메일의 계정이 있다
- `already_linked`: 그 Google 계정이 다른 계정에 연결돼 있거나, 지금 계정에 이미 다른 Google 계정이 있다
- `bootstrap_required`: 사용자가 0명이다
- `google_disabled`: `GOOGLE_CLIENT_ID` 가 없다

Google 이 `error=access_denied` 로 돌려보내면(사용자가 취소) 메시지 없이 로그인 화면으로 돌아간다.

## 보안 메모

- 토큰, 인가 코드, 클라이언트 비밀은 로그에 남기지 않는다.
- CSP 는 바꾸지 않는다. Google 로 가는 것은 최상위 페이지 이동이라 `connect-src` 나 `script-src` 가 필요 없다. `vercel.json` 에 `form-action` 도 없다.
- `oauth_flow` 쿠키가 SameSite=Lax 여야 Google 에서 돌아오는 최상위 이동에 실린다. 세션 쿠키는 이미 Lax 다.
- 연결 모드에서 쿠키의 사용자 id 를 세션과 대조하는 이유: 다른 사람이 시작한 연결 흐름의 콜백 주소를 피해자에게 열게 해서 공격자의 Google 계정을 피해자 계정에 붙이는 공격을 막는다.
- Google 인증서는 로그인마다 한 번 가져온다. 로그인 빈도가 낮아 캐시는 두지 않는다.

## 테스트

새 테스트(백엔드는 전부 `tests_unit` 안에서 앱을 직접 부른다. 이미 떠 있는 8008 서버를 타면 가짜 Google 응답이 적용되지 않고 개발 DB 에 쓰기 때문이다. SYM-143 과 같은 유형)

- 판정 함수: 세 승인 설정 x 세 계정 종류 x `AUTH_ALLOW_PERSONAL` 두 값의 표 테스트.
- 설정 검사: 잘못된 값이면 임포트에서 멈춘다.
- 콜백: 토큰 교환과 ID 토큰 검증을 가짜로 바꿔 로그인, 신규 생성, 승인 대기, 회사 계정만, `email_taken`, `already_linked`, `bootstrap_required`, state 없음과 불일치, nonce 불일치, `email_verified` 거짓, 중지된 계정을 본다.
- `next` 검사: `//evil`, `/\evil`, 탭이 든 경로, 절대 주소를 거절한다.
- 연결: 세션 사용자와 쿠키 사용자 id 가 다르면 거절, 기존 연결 덮어쓰기 거절, 비밀번호 없는 계정 해제 거절.
- 동시성: 같은 `google_sub` 두 콜백, Google 과 이메일 가입이 같은 이메일로 동시에, 첫 관리자 경합(Google 과 가입), 관리자 둘의 상호 중지와 강등에서 활성 관리자가 남는다.
- 로그인: 이메일 로그인, 대소문자 변형이 같은 제한 키로 묶인다, 승인 대기와 중지 사유는 비밀번호가 맞을 때만, 비밀번호 없는 계정은 401(500 아님).
- 중지: 기존 JWT 와 API 키가 바로 401, 다시 사용해도 옛 키는 401.
- 거절: 복구 이력이 있는 승인 대기 계정도 지워진다.
- 복구: 관리자 초기화와 비밀번호 찾기 완료가 Google 연결을 끊는다. 승인 대기·중지 계정의 복구 승인은 409.
- 마이그레이션: 0007 적용 후 기존 행이 `active`, SQLite 이관 스크립트 테스트가 통과한다.

바뀌는 기존 테스트(QA2 목록, 계획 단계에서 파일별로 고친다)

- 사용자가 있는 상태에서 아이디로 가입하는 픽스처: `test_first_admin_concurrent.py`, `test_security.py`, `test_account_requests.py`, `test_run_tc_sync.py`, `test_staged_upload.py`, `test_token_revocation.py`, `conftest.py` 의 시드. 이메일 가입으로 바꾸고 테스트 이메일은 `example.com` 을 쓴다.
- 프론트 단위: `RegisterPage.test.tsx`, `LoginPage.test.tsx`(`/api/auth/config` 모킹 추가).
- E2E: 로그인 칸 문구가 "아이디 또는 이메일을 입력하세요" 로 바뀌므로 로그인 도우미를 쓰는 15곳 이상, 가입 화면 문구를 단언하는 `regression-full.spec.ts`, `auth.spec.ts`, `accessibility.spec.ts`. 매뉴얼 캡처 스펙도 함께.

CI

- E2E 백엔드에 `AUTH_APPROVAL=personal` 과 더미 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` 를 넣는다. 관리자 시드는 첫 관리자 경로라 그대로 동작한다.
- 새 E2E
  - 이메일 가입(승인 대기) -> 관리자 승인 -> 로그인.
  - 사용 중지 -> 그 사용자의 다음 요청이 로그인 화면으로 간다.
  - Google 버튼이 보이고 `/api/auth/google/start` 가 Google 인가 주소로 302 한다(실제 Google 로그인은 하지 않는다).

손 확인

- 로컬 클라이언트(개인 계정 프로젝트)로 개인 Gmail, 회사 Workspace 계정, 취소, 연결, 해제를 본다.
- 컷오버 전 Vercel 스테이징에서도 같은 항목을 본다.

## 하지 않을 것

- 메일 발송과 이메일 주소 인증
- Google 외 다른 로그인(Microsoft, GitHub 등)
- Workspace 그룹이나 조직 단위로 역할을 정하는 기능
- 기존 계정과 Google 계정을 이메일로 자동 연결
- 초대 코드
- 활동 기록이 있는 계정의 삭제(사용 중지로 대신한다)
- Supabase 로 옮겨 실제로 띄우기(하위 프로젝트 3)

## 배포 메모

- Google 콘솔의 클라이언트에 배포 주소의 리디렉션 URI(`https://<도메인>/api/auth/google/callback`)를 더한다. 서버 측 흐름이라 JavaScript 원본은 필요 없다.
- Vercel 환경변수에 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `AUTH_*` 를 넣는다. 빈 DB 로 시작하면 `BOOTSTRAP_TOKEN` 도 넣는다.
- 팀에 열기 전에 Google 콘솔의 게시 상태를 "프로덕션" 으로 바꾼다. 테스트 상태에서는 테스트 사용자로 등록한 계정만 로그인된다.
