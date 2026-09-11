"""로컬 개발 서버를 띄우고, 내리고, API 를 부르는 한 자리.

에이전트와 사람이 같이 쓴다. `run_dev.sh` 는 포그라운드로 잡고 Ctrl+C 를 기다리므로
자동화에서는 쓸 수 없다. 여기서는 백그라운드로 띄우고 헬스체크까지 기다린 뒤 빠진다.

    python scripts/devctl.py up            # 백엔드 + 프론트
    python scripts/devctl.py up --backend  # 백엔드만
    python scripts/devctl.py status
    python scripts/devctl.py token
    python scripts/devctl.py api GET /api/projects
    python scripts/devctl.py api GET "/api/projects/30/reports?run_id=27"
    python scripts/devctl.py down

비밀번호는 저장하지 않는다. 환경변수 TCM_ADMIN_PW 를 먼저 보고, 없으면 레포 루트의
account.txt(gitignore 대상)에서 읽는다.
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_PORT = 8008
FRONTEND_PORT = 5173
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
# vite 는 localhost 에 바인딩한다. 127.0.0.1 로 부르면 연결이 거부된다.
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

IS_WINDOWS = platform.system() == "Windows"


# ── 포트와 프로세스 ───────────────────────────────────────────────────────────

def listening_pids(port: int) -> set:
    """그 포트를 LISTEN 중인 PID. 이름으로 찾지 않는다(다른 세션을 죽인다).

    `netstat -p TCP` 는 IPv4 만 낸다. vite 는 [::1] 에 바인딩하므로 그 필터를 쓰면
    프론트가 떠 있는데도 없는 것으로 보인다. 프로토콜을 지정하지 않고 로컬 주소의
    끝이 그 포트인 줄만 고른다.
    """
    if IS_WINDOWS:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
        pids = set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "LISTENING":
                if parts[1].endswith(f":{port}"):
                    pids.add(parts[4])
        return pids
    out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
    return {p for p in out.split() if p}


def kill_pid(pid: str) -> None:
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
    else:
        subprocess.run(["kill", "-9", pid], capture_output=True)


def wait_until_up(url: str, timeout: int = 40) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


# ── 기동과 종료 ──────────────────────────────────────────────────────────────

def start_backend() -> None:
    """reloader 없이 띄운다. watchfiles 폴링이 CPU 를 먹는다."""
    stale = listening_pids(BACKEND_PORT)
    for pid in stale:
        # 이미 떠 있는 것을 두고 새로 띄우면 옛 프로세스가 계속 응답한다.
        # 고친 코드를 확인하는 줄 알았는데 옛 코드가 답하는 사고가 실제로 났다.
        print(f"  기존 백엔드 종료 PID {pid}")
        kill_pid(pid)
    if stale:
        time.sleep(1)

    log = os.path.join(ROOT, "backend", "devctl_backend.log")
    with open(log, "wb") as f:
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
            cwd=os.path.join(ROOT, "backend"),
            stdout=f, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0,
        )
    ok = wait_until_up(f"{BACKEND_URL}/docs")
    print(f"  백엔드 {BACKEND_URL} {'기동' if ok else '응답 없음 - ' + log}")


def start_frontend() -> None:
    stale = listening_pids(FRONTEND_PORT)
    for pid in stale:
        print(f"  기존 프론트 종료 PID {pid}")
        kill_pid(pid)
    if stale:
        time.sleep(1)

    log = os.path.join(ROOT, "frontend", "devctl_frontend.log")
    npx = "npx.cmd" if IS_WINDOWS else "npx"
    with open(log, "wb") as f:
        subprocess.Popen(
            [npx, "vite", "--port", str(FRONTEND_PORT), "--strictPort"],
            cwd=os.path.join(ROOT, "frontend"),
            stdout=f, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0,
        )
    ok = wait_until_up(FRONTEND_URL)
    print(f"  프론트 {FRONTEND_URL} {'기동' if ok else '응답 없음 - ' + log}")


def cmd_up(args) -> int:
    both = not args.backend and not args.frontend
    if args.backend or both:
        start_backend()
    if args.frontend or both:
        start_frontend()
    return 0


def cmd_down(args) -> int:
    found = False
    for name, port in (("백엔드", BACKEND_PORT), ("프론트", FRONTEND_PORT)):
        for pid in listening_pids(port):
            found = True
            print(f"  {name} 종료 PID {pid}")
            kill_pid(pid)
    if not found:
        print("  떠 있는 서버 없음")
    return 0


def cmd_status(args) -> int:
    for name, port, url in (
        ("백엔드", BACKEND_PORT, f"{BACKEND_URL}/docs"),
        ("프론트", FRONTEND_PORT, FRONTEND_URL),
    ):
        pids = listening_pids(port)
        alive = False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                alive = r.status == 200
        except Exception:
            pass
        print(f"  {name} :{port} PID {sorted(pids) or '없음'} 응답 {'정상' if alive else '없음'}")
    return 0


# ── 인증과 API ───────────────────────────────────────────────────────────────

def admin_password() -> str:
    pw = os.getenv("TCM_ADMIN_PW")
    if pw:
        return pw
    path = os.path.join(ROOT, "account.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            line = f.read().strip().splitlines()[0]
        if "/" in line:
            return line.split("/", 1)[1].strip()
    raise SystemExit("비밀번호를 찾지 못했다. TCM_ADMIN_PW 를 주거나 account.txt 를 두라.")


def get_token(username: str = "admin") -> str:
    body = json.dumps({"username": username, "password": admin_password()}).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/auth/login", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"로그인 실패 {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
    except urllib.error.URLError:
        raise SystemExit(f"백엔드가 떠 있지 않다. 먼저 `python scripts/devctl.py up --backend`")


def cmd_token(args) -> int:
    print(get_token())
    return 0


def normalize_path(raw: str) -> str:
    """Git Bash 가 바꿔 놓은 경로를 되돌린다.

    MSYS 는 `/api/projects` 같은 인자를 Windows 경로로 본다. 그대로 두면
    `/C:/Program Files/Git/api/projects` 가 되어 요청이 만들어지지 않는다.
    쿼리스트링이 붙은 인자는 변환되지 않아 증상이 들쭉날쭉하게 보인다.
    """
    path = raw.replace("\\", "/")
    marker = path.find("/api/")
    if marker > 0:
        path = path[marker:]
    return path if path.startswith("/") else "/" + path


def cmd_api(args) -> int:
    path = normalize_path(args.path)
    data = args.data.encode() if args.data else None
    req = urllib.request.Request(
        BACKEND_URL + path,
        data=data,
        method=args.method.upper(),
        headers={
            "Authorization": f"Bearer {get_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            status = r.status
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw, status, ctype = e.read(), e.code, e.headers.get("Content-Type", "")

    if args.out:
        with open(args.out, "wb") as f:
            f.write(raw)
        print(f"HTTP {status} / {len(raw)} bytes -> {args.out}")
        return 0 if status < 400 else 1

    print(f"HTTP {status} / {len(raw)} bytes")
    if "json" in ctype:
        try:
            print(json.dumps(json.loads(raw), ensure_ascii=False, indent=2)[: args.limit])
            return 0 if status < 400 else 1
        except Exception:
            pass
    if raw[:2] == b"PK":
        print("  (바이너리 응답. 파일로 받으려면 --out 을 주라)")
    else:
        print(raw.decode("utf-8", "replace")[: args.limit])
    return 0 if status < 400 else 1


def main() -> int:
    p = argparse.ArgumentParser(description="로컬 개발 서버 제어와 API 호출")
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("up", help="서버 기동(기존 프로세스를 먼저 정리한다)")
    up.add_argument("--backend", action="store_true")
    up.add_argument("--frontend", action="store_true")
    up.set_defaults(func=cmd_up)

    sub.add_parser("down", help="포트를 잡은 PID 만 종료").set_defaults(func=cmd_down)
    sub.add_parser("status", help="포트별 PID 와 응답").set_defaults(func=cmd_status)
    sub.add_parser("token", help="admin 토큰 출력").set_defaults(func=cmd_token)

    api = sub.add_parser("api", help="토큰을 붙여 API 호출")
    api.add_argument("method")
    api.add_argument("path")
    api.add_argument("--data", help="요청 본문 JSON 문자열")
    api.add_argument("--out", help="응답을 파일로 저장(엑셀, PDF)")
    api.add_argument("--limit", type=int, default=4000, help="출력 자르기 기준")
    api.set_defaults(func=cmd_api)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
