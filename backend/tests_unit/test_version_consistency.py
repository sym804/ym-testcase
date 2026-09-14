"""버전 표기 정합

버전이 네 곳에 흩어져 있다. 릴리즈 노트가 정본이고 나머지 셋은 사본이다.

    Release_note.md "현재 버전" 블록   <- 정본
    backend/main.py     version=       <- Backend 축
    frontend/package.json "version"    <- Frontend 축
    frontend/src/i18n/*/common.json    <- 화면 푸터, System 축

사본을 손으로 맞추는 한 어긋난다. 실측 2026-09-14 기준 릴리즈는 v1.5.3.0 인데
main.py 와 package.json 은 1.4.0.1 에 멈춰 있었고(일곱 번의 릴리즈 동안), 푸터는
1.5.2.0 이었다. 푸터는 SYM-59 로 한 번 고쳤던 자리가 다시 어긋난 것이다.
규칙만 두고 확인이 없으면 또 어긋나므로 여기서 막는다.
"""
import json
import os
import re

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
