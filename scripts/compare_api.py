"""이관 전후 서버의 집계 응답을 비교한다. 데이터 이관 검증의 마지막 단계.

같은 관리자 계정으로 두 서버에 로그인해 프로젝트 목록, 전체 개요, 프로젝트별 대시보드 7종,
수행별 리포트를 받아 JSON 이 같은지 본다. 이관은 비밀번호 해시까지 옮기므로 같은 계정이 양쪽에 있다.
읽기만 한다(로그인 기록 외에는 쓰지 않는다).

    CMP_PASSWORD=<관리자 비밀번호> python scripts/compare_api.py \\
        --a http://127.0.0.1:8008 --b https://<새 주소> --username admin --out api_diff.json

종료코드: 0 같음, 1 다른 응답 있음(--out 에 경로별로 남김), 2 로그인·접속 실패.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DASHBOARDS = ("summary", "priority", "category", "rounds", "assignee", "heatmap", "stability")


class CompareError(Exception):
    pass


def _call(base: str, path: str, token: str | None = None, body: dict | None = None):
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise CompareError(f"{base} 에 접속하지 못했습니다: {type(e).__name__}") from None


def login(base: str, username: str, password: str) -> str:
    status, data = _call(base, "/api/auth/login", body={"username": username, "password": password})
    if status != 200 or not isinstance(data, dict) or "access_token" not in data:
        raise CompareError(f"{base} 로그인 실패: HTTP {status}")
    return data["access_token"]


def paths(base: str, token: str) -> list[str]:
    """비교할 경로. 프로젝트와 수행 목록은 a 서버(이관 전) 기준이다."""
    out = ["/api/projects", "/api/dashboard/overview"]
    status, projects = _call(base, "/api/projects", token)
    if status != 200:
        raise CompareError(f"{base} 프로젝트 목록 실패: HTTP {status}")
    for p in projects:
        pid = p["id"]
        out += [f"/api/projects/{pid}/dashboard/{d}" for d in DASHBOARDS]
        _, runs = _call(base, f"/api/projects/{pid}/testruns", token)
        out += [f"/api/projects/{pid}/reports?run_id={r['id']}" for r in (runs if isinstance(runs, list) else [])]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="이관 전후 API 응답 비교")
    ap.add_argument("--a", required=True, help="이관 전 서버 주소")
    ap.add_argument("--b", required=True, help="이관 후 서버 주소")
    ap.add_argument("--username", required=True, help="양쪽에 있는 관리자 아이디")
    ap.add_argument("--password-env", default="CMP_PASSWORD", help="비밀번호를 담은 환경변수 이름")
    ap.add_argument("--out", default="api_diff.json", help="다른 응답을 남길 파일")
    a = ap.parse_args(argv)
    password = os.environ.get(a.password_env, "")
    try:
        ta, tb = login(a.a, a.username, password), login(a.b, a.username, password)
        todo = paths(a.a, ta)
        diffs = []
        for path in todo:
            ra, rb = _call(a.a, path, ta), _call(a.b, path, tb)
            if ra != rb:
                diffs.append({"path": path, "a": ra, "b": rb})
    except CompareError as e:
        print(f"비교를 멈췄습니다: {e}", file=sys.stderr)
        return 2
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(diffs, f, ensure_ascii=False, indent=1)
    print(f"비교 {len(todo)}개: 같음 {len(todo) - len(diffs)}, 다름 {len(diffs)}")
    for d in diffs[:10]:
        print(f"  다름: {d['path']}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
