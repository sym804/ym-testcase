# 회사 배포 가이드 (조직, Google Workspace)

회사 팀이 업무에 쓰도록 올리는 절차입니다. 개인이나 소규모로 쓰려면 [공개 배포 가이드](deploy_public.md) 가 더 간단합니다.

구성은 이렇습니다.

- 공개 레포를 `upstream` 으로 따르는 회사 비공개 레포에 Vercel 과 Supabase 를 연결합니다. 회사 자격 증명과 설정은 비공개 레포와 Vercel 에만 둡니다
- `main` 에 푸시하면 GitHub Actions 가 CI(백엔드, 프론트, E2E)를 돌리고, 통과한 커밋만 배포합니다. 순서는 Vercel 빌드, 운영 DB 마이그레이션, 배포입니다. 빌드가 실패하면 DB 는 그대로입니다
- 매일 03:30(KST)에 DB 덤프와 첨부 파일을 Actions 아티팩트로 남깁니다(14일 보관)
- Google Workspace 회사 계정은 바로 쓰고, 그 밖의 가입은 관리자 승인 뒤에 씁니다

## 준비물

- GitHub: 회사 조직(또는 계정)에 비공개 레포를 만들 권한
- Vercel: Pro 팀. 회사 업무에 쓰면 약관상 Hobby 가 아니라 Pro 대상입니다
- Supabase: 회사 조직. Pro 를 권합니다. Free 는 7일 동안 요청이 없으면 일시 정지되고, 정지 중에는 앱이 503 을 냅니다
- Google Workspace 의 Google Cloud 프로젝트를 만들 권한
- PC 에 Git, Node.js 22, Python 3

## 1. 비공개 레포

GitHub 에서 빈 비공개 레포(예: `<회사>/ymtc`)를 만듭니다. README 나 .gitignore 를 넣지 않습니다.

```bash
git clone https://github.com/sym804/ym-testcase.git ymtc
cd ymtc
git remote rename origin upstream
git remote add origin https://github.com/<회사>/ymtc.git
git push -u origin main
```

코드 파일은 이 레포에서 고치지 않습니다. 고치면 업데이트 때마다 충돌합니다.

푸시하면 Actions 에서 CI 가 돌기 시작합니다. 아직 배포 설정이 없으므로 Deploy 와 Backup 은 건너뜁니다.
`release-notify` 워크플로는 원본 레포의 Slack 알림용이라 이 레포에서는 웹훅이 없어 실패합니다. Actions 화면에서 이 워크플로를 골라 Disable workflow 로 꺼 둡니다.

## 2. Supabase

1. 새 프로젝트를 만듭니다. 리전은 Seoul, DB 비밀번호를 적어 둡니다.
2. Storage 에서 버킷을 만듭니다. 이름은 `attachments`, **Public 은 끕니다.** 버킷 설정에서 파일 크기 상한을 50MB 로 둡니다. 서명 업로드 주소는 크기를 강제하지 않으므로 이 상한이 마지막 방어선입니다.
3. 상단의 Connect 버튼에서 접속 주소 두 개를 복사합니다.
   - Transaction pooler (포트 6543): 앱이 씁니다. 3절의 `DATABASE_URL`
   - Session pooler (포트 5432): 마이그레이션과 백업이 씁니다. 5절의 `DATABASE_URL_DIRECT`. Direct connection 은 IPv6 로만 열려 있어 GitHub Actions 에서 접속하지 못할 수 있습니다
4. 두 주소 모두 앞부분 `postgresql://` 을 `postgresql+psycopg2://` 로 바꾸고, `[YOUR-PASSWORD]` 자리에 비밀번호를 넣습니다. 비밀번호에 `@` `:` `/` `#` 같은 문자가 있으면 URL 인코딩합니다(`@` 는 `%40`).
5. Project Settings 의 API 에서 Project URL 과 `service_role` 키를 복사합니다. `service_role` 키는 서버 전용입니다.

DB 스키마는 첫 배포 때 Actions 가 만듭니다. 여기서 따로 돌리지 않습니다.

## 3. Vercel

### 프로젝트 만들기

배포는 Actions 가 하므로 Vercel 프로젝트를 Git 에 연결하지 않습니다. 연결하면 푸시 때마다 마이그레이션 전에 새 코드가 뜹니다.

```bash
cd ymtc
npx vercel login
npx vercel link
```

`vercel link` 가 묻는 대로 회사 Pro 팀을 고르고, 기존 프로젝트에 연결할지 물으면 No, 새 프로젝트 이름(예: `ymtc`)을 넣습니다.
Git 저장소를 연결할지 물으면 연결하지 않습니다.
끝나면 `.vercel/project.json` 에 `orgId` 와 `projectId` 가 생깁니다. 5절에서 씁니다. 이 폴더는 커밋하지 않습니다(`.gitignore` 에 들어 있습니다).

### 리전

Settings, Functions 에서 Function Region 을 Seoul(`icn1`)로 바꿉니다.
기본값(미국 동부)으로 두면 서울 DB 와 왕복하느라 응답마다 2초 가까이 걸립니다.

### 환경변수

Settings, Environment Variables 에 Production 으로 넣습니다.

| 이름 | 값 |
|---|---|
| `DATABASE_URL` | 트랜잭션 풀러 주소(6543) |
| `SECRET_KEY` | 긴 무작위 문자열. `python -c "import secrets;print(secrets.token_hex(32))"` |
| `ENV` | `production` |
| `STORAGE_BACKEND` | `supabase` |
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | `service_role` 키 |
| `STORAGE_BUCKET` | `attachments` |
| `CRON_SECRET` | 긴 무작위 문자열. 매일 정리 작업(`/api/internal/cron/daily`) 인증 |
| `TRUSTED_PROXY_HEADER` | `x-real-ip` |
| `AUTH_COMPANY_DOMAINS` | 회사 Workspace 도메인. 여러 개면 쉼표로(`company.com,company.co.kr`) |
| `AUTH_APPROVAL` | `personal` |
| `AUTH_ALLOW_PERSONAL` | `1`(협력사 등 외부 메일도 승인 뒤 받음) 또는 `0`(회사 계정만) |
| `BOOTSTRAP_TOKEN` | 긴 무작위 문자열. 첫 관리자를 만들 때 한 번 씁니다 |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | 4절에서 받습니다 |

아래 두 가지를 빠뜨리면 배포는 되지만 운영에서 문제가 납니다.

- `TRUSTED_PROXY_HEADER` 가 비면 모든 요청이 프록시 주소 하나로 잡힙니다. 가입 횟수 제한(시간당 30건)이 회사 전체에 함께 걸리고, 누군가 한 계정의 비밀번호를 열 번 틀리면 그 계정은 모든 접속자에게 5분 동안 잠깁니다
- `AUTH_*` 세 값이 비면 기본값이 "누구나 가입해 바로 사용" 입니다. 인터넷에 열린 주소라 외부인도 가입해 비공개가 아닌 프로젝트를 볼 수 있습니다

정책 조합은 이렇게 동작합니다. 회사 Google 계정 판정은 이메일 끝자리가 아니라 Google 이 보내 주는 Workspace 도메인(`hd`)으로 합니다.

- `AUTH_APPROVAL=personal`, `AUTH_ALLOW_PERSONAL=1`: 회사 Google 로그인은 바로 사용. 개인 Google 과 이메일 가입은 승인 대기
- `AUTH_APPROVAL=personal`, `AUTH_ALLOW_PERSONAL=0`: 회사 Google 로그인만 바로 사용. 개인 Google 과 회사 밖 주소의 이메일 가입은 거절. 회사 주소의 이메일 가입은 주소 소유를 확인하지 않으므로 항상 승인 대기
- `AUTH_APPROVAL=all`: 모두 승인 대기

### 도메인 (선택)

회사 도메인을 쓰려면 Settings, Domains 에서 붙이고 DNS 에 안내된 레코드를 넣습니다.
도메인을 정한 뒤에 4절의 리디렉션 URI 를 만듭니다. 주소가 바뀌면 URI 도 다시 등록해야 합니다.

## 4. Google 로그인

회사 Workspace 의 Google Cloud 에 OAuth 클라이언트를 만듭니다.

1. Google Cloud 콘솔에서 회사 조직 아래에 프로젝트를 만듭니다.
2. Google 인증 플랫폼에서 대상을 **내부**로 둡니다. 내부는 회사 Workspace 계정만 로그인할 수 있고 Google 의 앱 심사가 없습니다. 앱 이름과 지원 이메일을 넣고, 로고는 비워 둡니다.
3. 클라이언트를 웹 애플리케이션으로 만들고 승인된 리디렉션 URI 에 `https://<배포 주소>/api/auth/google/callback` 을 넣습니다. 배포 주소는 회사 도메인이 있으면 그것, 없으면 `<프로젝트>.vercel.app` 입니다. 이름이 이미 쓰이고 있으면 뒤에 글자가 붙으므로 Settings, Domains 에서 실제 주소를 확인합니다.
4. 클라이언트 ID 와 보안 비밀을 Vercel 의 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` 에, 3번의 URI 를 그대로 `GOOGLE_REDIRECT_URI` 에 넣습니다. 보안 비밀은 만들 때 한 번만 보입니다.

대상을 내부로 두면 개인 Google 계정은 Google 화면에서 먼저 막힙니다. 협력사가 들어와야 하면 이메일 가입 후 승인으로 받습니다.

## 5. GitHub Actions 설정

비공개 레포의 Settings, Secrets and variables, Actions 에서 넣습니다.

변수(Variables 탭):

- `DEPLOY_ENABLED` = `true`

비밀값(Secrets 탭):

| 이름 | 값 |
|---|---|
| `DATABASE_URL_DIRECT` | 세션 풀러 주소(5432) |
| `VERCEL_TOKEN` | Vercel Account Settings, Tokens 에서 회사 팀 범위로 만든 토큰 |
| `VERCEL_ORG_ID` | `.vercel/project.json` 의 `orgId` |
| `VERCEL_PROJECT_ID` | `.vercel/project.json` 의 `projectId` |
| `SUPABASE_URL` | Project URL (백업용) |
| `SUPABASE_SERVICE_ROLE_KEY` | `service_role` 키 (백업용) |
| `STORAGE_BUCKET` | `attachments` (백업용) |

## 6. 첫 배포

1. Actions 에서 1절의 푸시로 돈 CI 실행을 열고 Re-run all jobs 를 누릅니다. CI 가 끝나면 Deploy 가 이어서 돕니다(전체 15분 안팎). CI 화면의 Run workflow 로 새로 돌리면 Deploy 가 건너뜁니다. Deploy 는 푸시로 돈 CI 뒤에만 돕니다.
2. Deploy 의 "운영 DB 마이그레이션" 단계에 `Running upgrade ... -> 0008_google_email` 이 보이면 스키마가 만들어진 것입니다.
3. Deploy 가 초록이면 배포 주소를 엽니다.

Deploy 가 실행되지 않고 건너뛰어지면 CI 가 성공했는지, 푸시로 돈 CI 를 다시 돌렸는지, `DEPLOY_ENABLED` 변수가 있는지, 레포가 비공개인지 확인합니다.

## 7. 첫 관리자

1. 배포 주소의 가입 화면에 "관리자 계정 만들기" 가 나옵니다(사용자가 0명일 때만).
2. 아이디, 이름, 비밀번호와 함께 "첫 관리자 토큰" 칸에 `BOOTSTRAP_TOKEN` 값을 넣습니다.
3. 만든 계정으로 로그인한 뒤, 사용자 메뉴의 계정 연결에서 본인 회사 Google 계정을 붙여 둡니다.
4. Vercel 에서 `BOOTSTRAP_TOKEN` 을 지웁니다.

QA 리드처럼 프로젝트 전체를 관리할 사람은 가입 뒤 관리 화면에서 역할을 QA Manager 로 바꿉니다.

## 8. 배포 뒤 확인

팀에 알리기 전에 한 번씩 해 봅니다.

- 회사 Google 계정으로 로그인(다른 사람 계정이나 시크릿 창). 승인 없이 바로 들어와야 합니다
- 개인 메일로 이메일 가입. `AUTH_ALLOW_PERSONAL=1` 이면 승인 대기가 되고 관리 화면에서 승인하면 들어와야 합니다. `0` 이면 "회사 이메일로만 가입할 수 있습니다" 로 거절돼야 합니다
- 프로젝트를 만들고 TC 입력, 새로고침 뒤에도 남는지
- TC 에 이미지 첨부, 다시 열어 보기
- 테스트 수행 하나를 만들어 결과 입력, 엑셀 내보내기
- Vercel Logs 에 `TRUSTED_PROXY_HEADER 가 비어 있다` 오류가 없는지
- 다음 날 Actions 에 Backup 이 초록으로 돌았는지, Vercel 의 Cron Jobs 에 daily 가 성공했는지

## 업데이트

새 버전이 나오면 비공개 레포에서 받기만 합니다. 마이그레이션은 Deploy 가 합니다.

```bash
git pull upstream main
git push origin main
```

받기 전에 `Release_note.md` 의 새 절에 `### 조치` 가 있으면 그대로 합니다(환경변수 추가 등).
배포가 실패하면 원인을 고친 뒤 그 푸시로 돈 CI 실행에서 Re-run all jobs 를 누릅니다. 빌드 단계에서 실패했다면 DB 는 바뀌지 않았습니다.

## 운영

- 퇴사자: Workspace 계정을 지워도 앱의 로그인(최대 30일)과 API 키는 남습니다. 관리 화면에서 사용 중지하면 바로 막힙니다
- 백업 복원: Actions 의 Backup 실행에서 `backup-db-*` 아티팩트를 받아 `pg_restore` 로 넣습니다. 첨부는 `backup-storage-*` 의 zip 입니다
- 백업 실패: 첨부 일부를 못 읽으면 나머지를 담고 실패로 끝납니다. 못 읽은 목록은 zip 안의 `_manifest.txt` 에 있습니다. DB 덤프는 그와 상관없이 먼저 남습니다
- 비밀값 교체: `SECRET_KEY` 를 바꾸면 모든 사용자가 다시 로그인해야 합니다
