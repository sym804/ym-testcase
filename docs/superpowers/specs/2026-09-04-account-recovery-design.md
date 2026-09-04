# 계정 복구 (아이디 찾기 / 비밀번호 재설정) 설계

**작성일:** 2026-09-04
**상태:** 설계 확정, 구현 전

## 배경

여러 사람이 쓰기 시작하면서 계정을 잃은 사용자를 되돌릴 경로가 필요해졌다.

지금은 아이디 찾기가 아예 없고, 비밀번호는 관리자만 초기화할 수 있다.
로그인 화면(`frontend/src/pages/LoginPage.tsx:86`)에 "비밀번호를 잊으셨다면 관리자에게
초기화를 요청하세요" 라는 문구가 있지만 링크가 아니라 안내 텍스트일 뿐이다.
실제 동작은 `PUT /api/auth/users/{user_id}/reset-password` (`backend/routes/auth.py:237`)
하나뿐이고 `role_required("admin")` 으로 막혀 있다.

셀프 서비스를 만들 수 없는 이유가 데이터에 있다. `User` 모델(`backend/models.py:46`)에는
`username`, `password_hash`, `display_name`, `role`, `must_change_password`, `created_at`
뿐이라 본인 확인에 쓸 연락 수단이 없다. SMTP 설정도 코드베이스에 없다.

## 설계 결정

세 가지를 먼저 정했다. 각각이 나머지를 제약한다.

**본인 확인은 관리자가 한다.** 이메일 컬럼을 추가하고 메일을 보내는 안도 검토했지만,
기존 사용자 전원의 이메일을 채워야 하고 사내망에서 발송이 막힐 수 있다. 관리자 승인 큐는
외부 의존이 없고 이미 있는 초기화 로직을 그대로 쓴다. 대신 즉시 해결되지는 않는다.

**아이디 찾기도 같은 큐에 태운다.** 사용자가 아이디를 모르는 상태라 판별할 값이
`display_name` 뿐인데, 이것만으로 자동 조회를 열면 본인 확인 없이 "누가 가입되어 있는지"
훑을 수 있다. 요청 종류만 다를 뿐 수명주기가 같으므로 한 큐에서 관리한다.

**관리자와 사용자 사이에는 1회용 코드가 오간다.** 임시 비밀번호를 전달하면 유효한
비밀번호가 메신저에 남는다. 코드는 만료되고 한 번 쓰면 죽으며, 새 비밀번호는 사용자가
직접 정하므로 비밀번호 자체가 사람 손을 거치지 않는다.

**모델은 전용 테이블 하나로 둔다.** 요청과 코드를 두 테이블로 나누면 각 테이블이 한 가지
일만 하지만, 이 규모에서는 조인과 마이그레이션만 늘어난다. 코드 발급이 요청 승인 외의
경로로도 생기면 그때 분리한다. 인메모리는 서버 재시작 때 관리자가 아직 못 본 대기 요청이
증발하므로 탈락시켰다.

## 데이터 모델

새 테이블 `account_requests` 하나를 추가한다. 기존 테이블은 변경하지 않으므로 기존
데이터에 영향이 없다.

enum 두 개는 기존 `UserRole` / `TestResultValue` 와 같은 `str, enum.Enum` 패턴을 따른다.

```python
class AccountRequestType(str, enum.Enum):
    find_id = "find_id"
    reset_password = "reset_password"


class AccountRequestStatus(str, enum.Enum):
    pending = "pending"        # 관리자 확인 대기
    approved = "approved"      # 코드 발급됨, 아직 미사용 (reset_password 만)
    rejected = "rejected"      # 관리자가 반려
    completed = "completed"    # 아이디 전달 완료 또는 코드 사용됨
```

컬럼은 다음과 같다.

- `id` - PK
- `request_type` - `AccountRequestType`, not null
- `status` - `AccountRequestStatus`, 기본값 `pending`, not null
- `claimed_username` - `String(100)`, nullable. 비밀번호 재설정 요청 시 사용자가 적은 아이디
- `claimed_display_name` - `String(100)`, nullable. 아이디 찾기 요청 시 적은 표시 이름
- `contact` - `String(200)`, not null. 관리자가 연락할 수단
- `note` - `Text`, nullable. 사용자 메모 또는 관리자 반려 사유
- `user_id` - `FK users.id`, nullable. 승인 시 관리자가 확정한 대상
- `code_hash` - `String(255)`, nullable. 1회용 코드의 해시
- `code_expires_at` - `DateTime`, nullable
- `created_at` - `DateTime`, 기본값 `now_kst`
- `resolved_at` - `DateTime`, nullable
- `resolved_by_id` - `FK users.id`, nullable. 처리한 관리자

`claimed_username` 과 `claimed_display_name` 을 나눈 이유는, 사용자가 적은 값을 검증 없이
그대로 담는 자리라서다. 승인 전까지는 실재하는 계정을 가리킨다는 보장이 없다. 관리자가
확정한 대상만 `user_id` 로 들어간다.

인덱스는 `(status, created_at)` 하나. 관리자 화면이 대기 목록을 최신순으로 읽는다.

alembic revision 하나를 추가하며 `down_revision` 은 현재 head 인 `06933fddb519` 다.

## 엔드포인트

비로그인 2개, 관리자 3개. 기존 `PUT /api/auth/users/{user_id}/reset-password`(관리자
직권 초기화)는 그대로 둔다. 관리자가 큐를 거치지 않고 바로 처리해야 하는 경우가 있다.

### POST /api/auth/account-requests (비로그인)

요청 접수. body 는 `request_type`, `claimed_username`, `claimed_display_name`,
`contact`, `note`.

필수 필드가 종류마다 다르다. `reset_password` 는 `claimed_username`, `find_id` 는
`claimed_display_name` 이 있어야 한다. 없으면 422. `contact` 는 두 종류 모두 필수다.

응답은 요청 대상이 실재하는지와 무관하게 동일하다. 없는 아이디로 요청해도 201 이고
같은 메시지가 나간다. 존재 여부는 관리자만 알며, 없는 계정 요청은 관리자가 반려한다.

중복 요청은 만들지 않는다. 판정 기준은 종류를 포함한다. `reset_password` 는 같은
`claimed_username`, `find_id` 는 같은 `claimed_display_name` 으로 `pending` 이 이미
있으면 새로 만들지 않고 기존 요청을 그대로 둔다. 응답은 동일하다. 관리자 화면이 같은
요청으로 도배되는 것을 막는다.

### POST /api/auth/reset-password/verify (비로그인)

body 는 `username`, `code`, `new_password`. 새 비밀번호는 기존 `PasswordChange` 와 같이
최소 8자.

검증 순서는 대상 사용자 조회, 그 사용자의 `approved` 요청 조회, 만료 확인, 코드 대조다.
어느 단계에서 실패하든 같은 401 을 낸다.

성공하면 `password_hash` 를 갱신하고 `must_change_password` 를 `False` 로 둔다. 사용자가
직접 정한 비밀번호이므로 재변경을 강제할 이유가 없다. 요청은 `completed` 로 바뀌고
`code_hash` 는 `None` 이 된다.

### GET /api/auth/account-requests (관리자)

`status` 로 필터. 기본은 `pending`. `code_hash` 는 응답에 절대 싣지 않는다.

### POST /api/auth/account-requests/{id}/approve (관리자)

body 는 `user_id`. 관리자가 목록에서 대상 계정을 고른다.

동작이 요청 종류마다 다르다.

- `find_id`: 코드를 만들지 않는다. `completed` 로 바꾸고 응답에 대상 `username` 을 싣는다.
  관리자가 그것을 사용자에게 전달한다.
- `reset_password`: `secrets.token_urlsafe(9)` 로 12자 코드를 만들어 해시만 저장하고
  `approved` 로 바꾼다. 해시는 기존 `hash_password` 를 재사용한다. 평문 코드는 이 응답에
  딱 한 번 실린다. 다시 볼 수 없다.

`pending` 이 아닌 요청을 승인하려 하면 409.

### POST /api/auth/account-requests/{id}/reject (관리자)

`rejected` 로 바꾸고 `note` 에 사유를 남긴다.

## 코드 수명

유효기간은 24시간이다. 사람이 전달해야 하는 구조라 1시간은 짧다. 만료는 별도 배치 없이
검증 시점에 `code_expires_at` 을 비교해 판단한다. 요청 건수가 적어 정리 작업이 필요없다.

코드는 한 번 쓰면 죽는다. 사용 즉시 `completed` + `code_hash = None` 이므로 재사용이
구조적으로 불가능하다.

## 보안

이 기능의 위험 지점을 모아둔다.

**계정 열거 방지.** 요청 접수 응답이 대상 존재 여부와 무관하게 동일하다. 검증 실패도
단계를 구분하지 않고 같은 401 이다.

**코드는 평문으로 저장하지 않는다.** 해시만 남기고 평문은 승인 응답 1회로 끝난다.

**코드 대입 방어.** 검증 엔드포인트에 기존 rate limit(`_check_rate_limit`, IP+아이디
기준 5분 10회)을 건다. 실패 시 `_record_failure` 로 누적한다.

**요청 접수 남용 방어.** 기존 카운터(`_login_failures`)는 이름 그대로 **실패만** 세기
때문에 접수 제한에 그대로 쓸 수 없다. 성공/실패 무관하게 시도를 세는 별도 카운터를
IP 기준으로 두고 1시간에 10회로 제한한다. 초과하면 429. 기존 `_purge_expired_keys` 와
같은 방식으로 만료 키를 정리하며 키 수 상한도 같이 둔다.

**권한.** 목록, 승인, 반려는 `role_required("admin")`.

**로깅.** 접수, 승인, 반려, 재설정 성공/실패를 남긴다. 코드 평문은 로그에 남기지 않는다.

## 프론트엔드

- `/account-help` 신규, 비로그인. 탭 두 개로 아이디 찾기와 비밀번호 재설정 요청을 받는다.
  제출 후 안내는 성공 여부와 무관하게 같은 문구를 보여준다.
- `/reset-password` 신규, 비로그인. 아이디, 코드, 새 비밀번호, 확인.
- `LoginPage` 의 안내 문구를 `/account-help` 링크로 바꾼다.
- `AdminPage` 에 '계정 요청' 섹션을 추가한다. 대기 목록, 승인 시 대상 선택과 코드 표시,
  반려. 코드는 복사할 수 있어야 하고 다시 볼 수 없다는 것을 화면에 명시한다.
  액션 버튼(승인/반려/새로고침)은 프로젝트 규칙대로 해당 표 바로 위에 둔다.
- i18n `accountHelp.json` 을 ko/en 신규 추가하고 `login.json`, `admin.json` 에 키를 더한다.

## 테스트

`backend/test_account_requests.py` 를 새로 만든다. TDD 로 간다.

- 없는 아이디로 요청해도 201 이고 응답이 있는 경우와 동일하다
- 같은 아이디로 pending 이 중복 생성되지 않는다
- 비관리자는 목록과 승인에서 403
- 승인 응답에 평문 코드가 있고 DB 에는 해시만 있다
- 코드로 재설정한 뒤 새 비밀번호로 로그인되고 옛 비밀번호는 실패한다
- 같은 코드를 다시 쓰면 실패한다
- 만료된 코드는 실패한다 (만료 시각을 과거로 조작해 검증)
- 틀린 코드를 반복하면 429
- 아이디 찾기 승인은 코드를 만들지 않는다
- `pending` 이 아닌 요청 승인 시 409

프론트는 `frontend/src/test/api-index.test.ts` 에 새 API 호출 검증을 더한다.

## 버전 계획

`rules/versioning.md` 의 `system.feature.fix.patch` 체계를 따른다. 새 테이블을 만들고
신규 기능을 얹으므로 네 컴포넌트 모두 feature 자리를 올린다.

- System: 1.2.3.0 -> 1.3.0.0
- Frontend: 1.2.2.0 -> 1.3.0.0 (신규 페이지 2개, 관리자 섹션)
- Backend: 1.2.3.0 -> 1.3.0.0 (신규 엔드포인트 5개)
- Database: 0.6.0.0 -> 0.7.0.0 (테이블 추가)

버전을 적는 자리는 `frontend/package.json`, `backend/main.py` 의 `version=`,
`rules/versioning.md` 의 이력 표, `Release_note.md` 신규 섹션이다.

작업 중 확인된 별건이 하나 있다. `frontend/src/i18n/{ko,en}/common.json` 의 `version`
문자열이 "YM TestCase v1.0.0.0" 으로 멈춰 있어 화면 하단에 실제와 다른 버전이 표시된다.
프론트가 1.2.2.0 인데 사용자에게는 1.0.0.0 으로 보인다. 이번 릴리즈에서 같이 맞춘다.

## 기능 추가 체크리스트

`CLAUDE.md` 의 필수 체크리스트를 이 기능에 대입한다.

1. 코드 구현과 TypeScript 타입 체크 통과
2. 테스트 작성과 수행. 아래 테스트 절에 정리했다
3. 사용자 매뉴얼 갱신. `frontend/src/pages/UserManualPage.tsx` 에 계정 복구 절을 넣고
   `AdminManualPage.tsx` 에 승인 절차와 새 엔드포인트를 넣는다. 스크린샷을 첨부한다
4. 회귀 체크리스트 엑셀(`TC_Manager_Full_Regression_Checklist.xlsx`)에 TC 추가.
   `rules/tc_writing_guide.md` 의 `TC-[모듈약어]-[번호]` 형식을 따라 `TC-AUTH-` 대역을
   쓰고 기존 마지막 번호 다음부터 채운다
5. 테스트 중 바꾼 비밀번호와 DB 데이터는 수행 후 원복한다

릴리즈 기록은 `Release_note.md` 신규 섹션, `Issue_list.xlsx`, GitHub Issues 순으로 남긴다.

## 로컬 확인

백엔드 8008, 프론트엔드 5173 이다. 8000 은 다른 프로젝트가 쓴다.

수동 확인 중 로그인 실패가 10회 쌓이면 5분 잠기고 서버 재시작으로만 풀린다.
코드 오입력 테스트를 반복할 때 이 한도에 먼저 걸릴 수 있으니, 자동화 테스트는
계정과 IP 키를 나눠 쓰고 수동 확인은 마지막에 한다.

## 범위 밖

메일 발송, `users` 테이블 이메일 컬럼, 관리자 없이 완결되는 셀프 서비스는 이번에 하지
않는다. 나중에 메일이 필요해지면 이 테이블 위에 발송 경로만 얹으면 되도록, 코드 생성과
전달을 분리해 둔다.

## 영향 범위

새 테이블 하나와 새 엔드포인트 5개. 기존 로그인, 권한, 세션 흐름은 바뀌지 않는다.
기존 관리자 직권 초기화도 그대로다. 마이그레이션은 테이블 생성뿐이라 기존 데이터를
건드리지 않는다.
