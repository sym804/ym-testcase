"""버전 표기 정합

버전이 다섯 곳에 흩어져 있다. 릴리즈 노트가 정본이고 나머지 넷은 사본이다.

    Release_note.md "현재 버전" 블록      <- 정본
    backend/main.py     version=          <- Backend 축
    frontend/package.json "version"       <- Frontend 축
    frontend/package-lock.json "version"  <- Frontend 축, 자리가 둘
    frontend/src/i18n/*/common.json       <- 화면 푸터, System 축

사본을 손으로 맞추는 한 어긋난다. 실측 2026-09-14 기준 릴리즈는 v1.5.3.0 인데
main.py 와 package.json 은 1.4.0.1 에 멈춰 있었고(일곱 번의 릴리즈 동안), 푸터는
1.5.2.0 이었다. 푸터는 SYM-59 로 한 번 고쳤던 자리가 다시 어긋난 것이다.
규칙만 두고 확인이 없으면 또 어긋나므로 여기서 막는다.

lock 은 이 파일이 감시하지 않아 v1.6.0.0 시점까지 혼자 1.5.5.0 에 남아 있었고
v1.6.0.1 에서 맞췄다.
감시 안에 든 사본은 맞고 감시 밖의 사본만 어긋났으므로, 사본을 늘릴 때는
여기에 케이스부터 붙인다.
"""
import json
import os
import re
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RELEASE_NOTE = os.path.join(ROOT, "Release_note.md")


def _current_versions() -> dict:
    """릴리즈 노트의 "현재 버전" 블록을 읽는다. 이것이 정본이다."""
    text = open(RELEASE_NOTE, encoding="utf-8").read()
    block = re.search(r"## 현재 버전\s*```(.*?)```", text, re.S)
    assert block, "릴리즈 노트에 '현재 버전' 블록이 없다"
    body = block.group(1)

    got = {}
    system = re.search(r"YM TestCase System\s+v([\d.]+)", body)
    assert system, f"System 버전을 못 읽었다: {body!r}"
    got["system"] = system.group(1)
    for axis in ("Frontend", "Backend", "Database"):
        m = re.search(rf"{axis}\s+v([\d.]+)", body)
        assert m, f"{axis} 버전을 못 읽었다"
        got[axis.lower()] = m.group(1)
    return got


VERSIONS = _current_versions()


def test_릴리즈_노트의_최신_절이_현재_System_버전이다():
    text = open(RELEASE_NOTE, encoding="utf-8").read()
    first = re.search(r"^## v([\d.]+) ", text, re.M)
    assert first, "버전 절을 찾지 못했다"
    assert first.group(1) == VERSIONS["system"], (
        f"최신 절 v{first.group(1)} 과 현재 버전 v{VERSIONS['system']} 이 다르다"
    )


def test_백엔드_앱_버전이_릴리즈_노트와_같다():
    main_py = open(os.path.join(ROOT, "backend", "main.py"), encoding="utf-8").read()
    m = re.search(r'version="([\d.]+)"', main_py)
    assert m, "main.py 에서 version 을 못 찾았다"
    assert m.group(1) == VERSIONS["backend"], (
        f"main.py {m.group(1)} != 릴리즈 노트 Backend {VERSIONS['backend']}"
    )


def test_프론트_package_버전이_릴리즈_노트와_같다():
    pkg = json.load(open(os.path.join(ROOT, "frontend", "package.json"), encoding="utf-8"))
    assert pkg["version"] == VERSIONS["frontend"], (
        f"package.json {pkg['version']} != 릴리즈 노트 Frontend {VERSIONS['frontend']}"
    )


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_화면_푸터_버전이_릴리즈_노트와_같다(lang):
    path = os.path.join(ROOT, "frontend", "src", "i18n", lang, "common.json")
    common = json.load(open(path, encoding="utf-8"))
    m = re.search(r"v([\d.]+)", common.get("version", ""))
    assert m, f"{lang} common.json 의 version 문구에서 버전을 못 읽었다"
    assert m.group(1) == VERSIONS["system"], (
        f"{lang} 푸터 {m.group(1)} != 릴리즈 노트 System {VERSIONS['system']}"
    )


def test_프론트_lock_버전이_릴리즈_노트와_같다():
    """lock 의 version 은 npm 이 그 시점 package.json 을 보고 박제하는 값이다.

    그래서 "npm install 먼저, 버전 업 나중" 순서면 한 발 뒤처진 채로 커밋된다.
    2026-09-18 에 발견했을 때 릴리즈는 v1.6.0.0 인데 lock 은 1.5.5.0 이었다.

    축을 섞어 읽지 않도록 커밋 해시로 적는다. package.json 은 Frontend 축이고
    커밋 메시지의 버전은 System 축이다.

        cfa6316  (System v1.5.5.0)  FE 1.5.3.0  lock 1.4.0.1  <- 벌어지기 시작
        10f10d8  (System v1.5.7.0)  FE 1.5.4.0  lock 1.5.4.0  <- 의존성 수정으로
                                                                 install 이 돌아 일치
        6d19b9c  (System v1.5.7.0)  FE 1.5.5.0  lock 1.5.4.0  <- 같은 릴리즈의
                                                                 다음 커밋에서 재발
        a8d2063  (System v1.6.0.0)  FE 1.6.0.0  lock 1.5.5.0

    위 네 사본은 이 파일이 막고 있어 전부 맞아 있었고, 감시 밖의 lock 만 어긋났다.

    자리가 둘이다. 최상위 version 과 packages[""] 의 version 을 따로 본다.
    npm 이 둘을 같이 쓰므로 한쪽만 손으로 고치면 다음 install 에서 되돌아간다.
    """
    path = os.path.join(ROOT, "frontend", "package-lock.json")
    lock = json.load(open(path, encoding="utf-8"))
    assert lock["version"] == VERSIONS["frontend"], (
        f"package-lock.json 최상위 {lock['version']} != 릴리즈 노트 Frontend {VERSIONS['frontend']}"
    )
    root_pkg = lock["packages"][""]
    assert root_pkg["version"] == VERSIONS["frontend"], (
        f"package-lock.json packages[''] {root_pkg['version']} != 릴리즈 노트 Frontend {VERSIONS['frontend']}"
    )


# ── 릴리즈 태그 ──────────────────────────────────────────────────────────────
#
# rules/release_process.md 는 커밋 뒤에 `git tag vX.X.X` 와 `git push --tags` 를
# 지시한다. 그런데 2026-09-22 에 세어 보니 릴리즈 노트 절 52개 중 태그가 달린 것은
# 7개뿐이었다. v1.2.1.0 이후로 45개가 통째로 빠져 있었다.
# 사본 검사와 같은 이유다. 규칙만 두고 확인이 없으면 어긋난다.
#
# 그날 34개는 커밋 메시지의 `(vX.X.X.X` 표기로 되찾아 소급했다. 아래 11개는
# 커밋을 특정하지 못했다. 초기 버전이라 메시지에 버전을 적는 관행이 없었다.
# 틀린 태그는 없는 태그보다 나쁘므로 추정으로 달지 않고 예외로 둔다.
UNTAGGABLE = {
    "v1.2.2.0",
    "v0.7.0.0", "v0.6.0.0", "v0.5.0.0", "v0.4.1.0", "v0.4.0.0",
    "v0.3.0.0", "v0.2.1.1", "v0.2.1.0", "v0.2.0.0", "v0.1.0.0",
}


def _local_tags() -> set:
    r = subprocess.run(
        ["git", "tag"], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        return set()
    return set(r.stdout.split())


def test_지난_릴리즈에_전부_태그가_달려_있다():
    """최신 절 하나만 면제한다. 태그는 커밋 뒤에 다는 것이라 아직 없을 수 있다.

    바꿔 말하면 이 테스트는 한 박자 늦게 잡는다. 이번 릴리즈에서 태그를
    빠뜨리면 다음 릴리즈를 준비할 때 빨간불이 난다. 그때 소급해서 달면 된다.
    """
    tags = _local_tags()
    if not tags:
        pytest.skip("태그를 읽을 수 없다(얕은 클론이거나 git 이 없다)")

    text = open(RELEASE_NOTE, encoding="utf-8").read()
    versions = re.findall(r"^## (v[\d.]+) ", text, re.M)
    assert versions, "릴리즈 노트에서 버전 절을 찾지 못했다"

    past = versions[1:]  # 맨 앞(최신)은 면제
    missing = [v for v in past if v not in tags and v not in UNTAGGABLE]
    assert not missing, (
        "태그가 없는 릴리즈: " + ", ".join(missing)
        + "  ->  git tag <버전> <릴리즈 커밋> 후 git push origin --tags"
    )
