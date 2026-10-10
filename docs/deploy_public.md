# 공개 배포 가이드 (개인, 소규모 팀)

공개 레포를 그대로 받아 자기 Vercel 과 Supabase 계정에 올리는 절차입니다.
회사 업무에 쓰거나 Google Workspace 로 사내 계정만 받으려면 [회사 배포 가이드](deploy_company.md) 를 따릅니다.

이 방식은 Vercel 의 Git 연동으로 배포합니다. 푸시하면 바로 새 코드가 뜨고, DB 마이그레이션은 직접 돌립니다.
마이그레이션까지 자동으로 하려면 회사 배포 가이드의 GitHub Actions 방식을 씁니다(비공개 레포가 필요합니다).

## 준비물

- GitHub 계정. 이 레포를 fork 합니다
- Vercel 계정. 개인의 비상업 용도면 Hobby 로 됩니다. 업무용이면 Pro 가 약관상 대상입니다
- Supabase 계정. Free 로 시작할 수 있습니다. Free 프로젝트는 7일 동안 요청이 없으면 일시 정지되고, 대시보드에서 다시 켜야 합니다
- PC 에 Python 3.12 와 Git. 마이그레이션을 PC 에서 돌립니다

## 1. Supabase 프로젝트

1. 새 프로젝트를 만듭니다. 리전은 사용자와 가까운 곳(한국이면 Seoul)으로 고르고, DB 비밀번호를 적어 둡니다.
2. Storage 에서 버킷을 만듭니다. 이름은 `attachments`, **Public 은 끕니다.** 버킷 설정에서 파일 크기 상한을 50MB 로 둡니다. 서명 업로드 주소는 크기를 강제하지 않으므로 이 상한이 마지막 방어선입니다.
3. 상단의 Connect 버튼에서 접속 주소 두 개를 복사합니다.
   - Transaction pooler (포트 6543): 앱이 씁니다
   - Session pooler (포트 5432): 마이그레이션이 씁니다. Direct connection 은 IPv6 로만 열려 있는 경우가 많아 세션 풀러를 권합니다
4. 두 주소 모두 앞부분 `postgresql://` 을 `postgresql+psycopg2://` 로 바꾸고, `[YOUR-PASSWORD]` 자리에 비밀번호를 넣습니다. 비밀번호에 `@` `:` `/` `#` 같은 문자가 있으면 URL 인코딩합니다(`@` 는 `%40`).
5. Project Settings 의 API 에서 Project URL 과 `service_role` 키를 복사합니다. `service_role` 키는 서버 전용입니다. 프론트 빌드 변수나 공개 장소에 두지 않습니다.

## 2. DB 스키마 만들기

PC 에서 레포를 받고 빈 DB 에 스키마를 올립니다. 두 변수에 같은 세션 풀러 주소를 넣습니다.
하나만 원격 주소면 마이그레이션이 멈춥니다(로컬 `.env` 의 주소와 섞이는 것을 막는 장치입니다).

```bash
git clone https://github.com/<내 계정>/ym-testcase.git
cd ym-testcase/backend
pip install -r requirements.txt
DATABASE_URL="<세션 풀러 주소>" DATABASE_URL_DIRECT="<세션 풀러 주소>" python -m alembic upgrade head
```

Windows PowerShell 이면 변수를 먼저 지정합니다.

```powershell
$env:DATABASE_URL="<세션 풀러 주소>"; $env:DATABASE_URL_DIRECT="<세션 풀러 주소>"
python -m alembic upgrade head
Remove-Item Env:DATABASE_URL, Env:DATABASE_URL_DIRECT
```

마지막 줄을 빠뜨리지 않습니다. 운영 주소가 남은 창에서 로컬 서버를 켜면 로컬 서버가 기동하면서 운영 DB 에 마이그레이션을 겁니다.

끝에 오류 없이 `0008` 까지 올라가면 됩니다.

## 3. Vercel 프로젝트

1. Add New, Project 에서 fork 한 레포를 가져옵니다. Root Directory 는 레포 루트 그대로 둡니다. 빌드 설정은 레포의 `vercel.json` 이 정하므로 건드리지 않습니다.
2. 첫 빌드 전에 Environment Variables 에 아래 값을 넣습니다(Production).

| 이름 | 값 |
|---|---|
| `DATABASE_URL` | 트랜잭션 풀러 주소(6543) |
| `SECRET_KEY` | 긴 무작위 문자열. `python -c "import secrets;print(secrets.token_hex(32))"` |
| `ENV` | `production` |
| `STORAGE_BACKEND` | `supabase` |
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | `service_role` 키 |
| `STORAGE_BUCKET` | `attachments` |
| `CRON_SECRET` | 긴 무작위 문자열. 매일 정리 작업 인증에 씁니다 |
| `TRUSTED_PROXY_HEADER` | `x-real-ip` |
| `BOOTSTRAP_TOKEN` | 긴 무작위 문자열. 첫 관리자를 만들 때 한 번 씁니다 |
| `AUTH_APPROVAL` | 아래 5절에서 고릅니다 |

`TRUSTED_PROXY_HEADER` 를 비우면 모든 요청이 프록시 주소 하나로 잡힙니다. 가입 횟수 제한(시간당 30건)이 사이트 전체에 걸리고, 누군가 한 계정의 비밀번호를 열 번 틀리면 그 계정은 모든 접속자에게 5분 동안 잠깁니다.
`DATABASE_URL_DIRECT` 는 Vercel 에 넣지 않습니다. 서버리스에서는 앱이 마이그레이션을 하지 않습니다.

3. Settings, Functions 에서 Function Region 을 Supabase 와 같은 지역(Seoul 이면 `icn1`)으로 바꿉니다. 기본값(미국 동부)으로 두면 서울 DB 와 왕복하느라 응답마다 2초 가까이 걸립니다.
4. Deployments 에서 최근 배포를 Redeploy 합니다. 환경변수와 리전은 다음 배포부터 적용됩니다.

## 4. 첫 관리자

1. 배포 주소를 열고 가입 화면으로 갑니다. 사용자가 0명이면 "관리자 계정 만들기" 화면이 나옵니다.
2. 아이디, 이름, 비밀번호와 함께 "첫 관리자 토큰" 칸에 `BOOTSTRAP_TOKEN` 값을 넣습니다.
3. 만든 계정으로 로그인합니다. 이후로는 이 화면이 나오지 않습니다. Vercel 에서 `BOOTSTRAP_TOKEN` 을 지워 둡니다.

## 5. 가입 정책

공개 주소는 누구나 열 수 있습니다. 기본값(`AUTH_APPROVAL=none`)이면 아무나 가입해 바로 씁니다.
가입한 사람은 비공개가 아닌 프로젝트를 모두 볼 수 있습니다.

- 혼자 쓰거나 아는 사람만 쓰면 `AUTH_APPROVAL=all`. 가입하면 승인 대기가 되고, 관리자 화면에서 승인한 사람만 들어옵니다
- 데모처럼 정말 공개하려면 `none`. 이때는 실데이터를 넣지 않습니다

값을 바꾼 뒤에는 Redeploy 해야 적용됩니다.

## 6. Google 로그인 (선택)

넣지 않으면 Google 로그인 버튼이 보이지 않고, 이메일과 아이디 로그인만 씁니다.

1. Google Cloud 콘솔의 Google 인증 플랫폼에서 대상을 외부로 두고 앱 이름과 지원 이메일을 넣습니다. 로고를 올리면 브랜드 심사를 받아야 하므로 비워 둡니다.
2. 클라이언트를 웹 애플리케이션으로 만들고 승인된 리디렉션 URI 에 `https://<배포 주소>/api/auth/google/callback` 을 넣습니다.
3. Vercel 에 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`(2번의 URI 그대로) 를 넣고 Redeploy 합니다.
4. 게시 상태를 프로덕션으로 바꿉니다. 테스트 상태에서는 테스트 사용자로 등록한 계정만 로그인됩니다.

## 7. 배포 뒤 확인

- 로그인, 로그아웃
- 다른 브라우저(시크릿 창)에서 이메일 가입. 5절에서 고른 정책대로 바로 쓰이거나 승인 대기가 되는지
- 프로젝트를 만들고 TC 몇 줄 입력, 새로고침 뒤에도 남는지
- TC 에 이미지 첨부, 다시 열어 보기
- 엑셀 내보내기
- Vercel 의 Logs 에 `TRUSTED_PROXY_HEADER 가 비어 있다` 나 `STORAGE_BACKEND` 오류가 없는지

## 업데이트

fork 의 main 에 푸시하는 순간 Vercel 이 새 코드를 띄웁니다. 그래서 마이그레이션을 푸시보다 먼저 합니다.
PC 의 클론에서 아래 순서로 합니다. 마이그레이션은 이미 최신이면 아무것도 하지 않으므로 매번 돌려도 됩니다.

```bash
git remote add upstream https://github.com/sym804/ym-testcase.git   # 처음 한 번
git pull upstream main
cd backend
pip install -r requirements.txt
DATABASE_URL="<세션 풀러 주소>" DATABASE_URL_DIRECT="<세션 풀러 주소>" python -m alembic upgrade head
cd ..
git push origin main
```

GitHub 의 Sync fork 버튼도 fork 의 main 에 푸시하는 것이라 바로 배포됩니다. 새 버전에 스키마 변경이 있으면 마이그레이션을 돌릴 때까지 API 가 503 을 냅니다.
그때는 위 명령의 마이그레이션 줄을 돌리면 30초 안에 풀립니다.

## 백업

자동 백업 워크플로(`backup.yml`)는 비공개 레포에서만 돕니다. 공개 fork 는 직접 받아 둡니다. `pg_dump` 는 Supabase 서버와 같은 메이저 버전을 씁니다(Database 설정 화면에 나옵니다).

```bash
pg_dump --format=custom --no-owner --schema=public "<세션 풀러 주소, postgresql:// 형식>" > ymtc.dump
```

첨부 파일은 Supabase Storage 화면에서 버킷 단위로 내려받습니다.
