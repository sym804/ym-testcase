---
name: dev
description: ym-testcase(TC Manager) 로컬 개발 서버를 띄우거나 내리고, 인증이 필요한 API 를 부르고, 화면을 브라우저로 확인할 때 사용한다. 서버 기동, 토큰 발급, 엑셀/PDF 내려받기, 스크린샷 확인, 작업 후 서버 정리를 다룬다.
---

# 로컬 구동과 확인

`scripts/devctl.py` 하나로 띄우고, 부르고, 내린다. 포트는 백엔드 8008, 프론트 5173 고정이다.

```bash
python scripts/devctl.py up              # 백엔드 + 프론트
python scripts/devctl.py up --backend    # 백엔드만
python scripts/devctl.py status
python scripts/devctl.py api GET /api/projects
python scripts/devctl.py api GET "/api/projects/30/reports?run_id=27"
python scripts/devctl.py api POST /api/projects --data '{"name":"TMP"}'
python scripts/devctl.py api GET "/api/projects/30/testcases/export?split_sheets=true" --out out.xlsx
python scripts/devctl.py down
```

`api` 는 로그인과 토큰을 알아서 처리한다. 비밀번호는 환경변수 `TCM_ADMIN_PW`, 없으면 레포 루트
`account.txt`(gitignore 대상)에서 읽는다. 스크립트에 적지 않는다.

`run_dev.sh` 와 `run_dev.bat` 은 사람이 터미널에서 쓰는 용도다. 포그라운드로 잡고 Ctrl+C 를
기다리므로 자동화에서는 쓰지 않는다.

## 반드시 지킬 것

**띄우기 전에 이미 떠 있는 것을 먼저 내린다.** `up` 이 그 일을 한다. 손으로 uvicorn 을 또
띄우면 옛 프로세스가 포트를 계속 쥐고 응답한다. 고친 코드를 확인하는 줄 알았는데 수정 전
코드가 답하는 사고가 실제로 났다.

**작업이 끝나면 `down` 한다.** 방치한 dev 서버가 메모리를 수 GB 씩 먹는다. 포트를 옮겨
새로 띄우지 말고 쓰던 것을 내린다.

**프로세스는 PID 로만 죽인다.** 이름으로 거르면(`Get-Process -Name python | Stop-Process`)
사용자의 다른 세션까지 죽는다. `devctl.py` 는 포트를 LISTEN 중인 PID 만 본다.

**백엔드는 reloader 없이 띄운다.** `--reload` 의 파일 감시가 CPU 를 먹는다. `devctl.py up` 이
이미 그렇게 띄운다.

## 함정

**프론트는 `localhost` 로만 열린다.** vite 가 IPv6 `[::1]:5173` 에 바인딩하므로
`http://127.0.0.1:5173` 은 연결이 거부된다. Playwright 와 curl 모두 `http://localhost:5173` 을 쓴다.

같은 이유로 `netstat -ano -p TCP` 로는 프론트 PID 가 보이지 않는다. 그 옵션은 IPv4 만 낸다.
서버가 떠 있는데도 "없음" 으로 읽고 넘어가게 된다. `devctl.py` 는 프로토콜을 지정하지 않고
로컬 주소 끝이 그 포트인 줄을 고른다.

**Git Bash 는 `/api/...` 인자를 Windows 경로로 바꾼다.** `devctl.py` 가 되돌리므로 그냥 쓰면
된다. 다른 스크립트에서 curl 로 직접 부를 때는 `MSYS_NO_PATHCONV=1` 을 앞에 붙인다.
쿼리스트링이 붙은 인자는 변환되지 않아, 어떤 호출은 되고 어떤 호출은 안 되는 것처럼 보인다.

**DB 는 `backend/tc_manager.db` 다.** 루트의 `tc_manager.db` 는 4월에 멈춘 껍데기라
그것을 열면 테이블이 비어 보인다.

**쓰기 전에 백업하고 잠금을 먼저 잡는다.** `BEGIN IMMEDIATE` 로 잠금을 확인한 뒤 쓰고,
`PRAGMA busy_timeout` 은 30초 이상 준다. 교정 전후 행 수를 대조한다.

**테스트로 만든 데이터는 그 자리에서 지운다.** 프로젝트를 만들었으면 `DELETE /api/projects/{id}`
까지 하고, 고아 시트와 고아 TC 가 0건인지 확인한다.

## 브라우저로 확인할 때

로그인 입력칸은 name 이 아니라 placeholder 로 잡는다.

```python
pg.goto("http://localhost:5173/login", wait_until="networkidle")
pg.get_by_placeholder("아이디를 입력하세요").fill("admin")
pg.get_by_placeholder("비밀번호를 입력하세요").fill(pw)
pg.get_by_role("button", name="로그인").click()
pg.wait_for_url("**/projects", timeout=15000)
```

화면 주소는 `/projects/{id}?tab=` 에 `tc` `run` `compare` `dashboard` `report` `settings` 중 하나다.

리포트 탭에서 런을 고를 때 `page.locator("select").first` 는 헤더의 프로젝트 셀렉터를 잡는다.
런 셀렉터는 `.last` 다.

로그인 직후 콘솔에 찍히는 `/api/auth/me` 401 두 건은 정상이다. 토큰이 붙기 전 호출이다.

## 테스트

프론트는 서버 없이 돈다.

```bash
cd frontend && npx tsc --noEmit && npx vitest run
```

백엔드는 파일마다 다르다. `services/` 를 직접 부르는 것(`test_export_empty_project.py`,
`test_tc_renumber_service.py`)은 서버 없이 돌고, `requests` 로 `BASE` 를 부르는 것은 서버가
떠 있어야 한다. 후자는 개발 DB 를 건드리므로 `dev_db_guard` 가 막는 경우가 있다.

E2E 는 빌드된 `dist` 를 보므로 소스만 고치고 돌리면 옛 번들로 돈다.
