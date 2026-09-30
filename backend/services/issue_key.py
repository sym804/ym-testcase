"""이슈 주소에서 이슈 키(SF-1081, PROJ-12)를 뽑는다.

Jira 는 `/browse/PROJ-12`, Linear 는 `/issue/SF-1081/제목-슬러그` 모양이다.
그 자리가 없으면 경로에서 키 모양을 찾는다. 못 찾으면 None 이다.
"""
import re
from urllib.parse import parse_qs, urlparse

_KEY = r"[A-Za-z][A-Za-z0-9_]*-\d+"
_AFTER_SEGMENT = re.compile(rf"/(?:browse|issue|issues)/({_KEY})(?:[/?#]|$)", re.IGNORECASE)
# 대문자 키만 본다. 소문자까지 보면 제목 슬러그(fix-123)가 키로 잡힌다.
_ANY_UPPER = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9_]*-\d+)(?![A-Za-z0-9_])")


def extract_issue_key(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())

    m = _AFTER_SEGMENT.search(parsed.path)
    if m:
        return m.group(1).upper()

    # Jira 보드 화면: ...?selectedIssue=PROJ-12
    for value in parse_qs(parsed.query).get("selectedIssue", []):
        if re.fullmatch(_KEY, value):
            return value.upper()

    m = _ANY_UPPER.search(parsed.path)
    return m.group(1) if m else None


_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)


def find_issue_refs(text: str | None) -> list[tuple[str | None, str | None]]:
    """자유 문구에서 이슈를 찾아 (키, 주소) 로 돌려준다. 순서를 지키고 중복은 한 번만.

    결과 칸의 issue_link 는 "SF-1081 · sf1006-issues #1 (Major/미등록)" 처럼 설명이
    섞인 문구다. 주소가 있으면 주소와 거기서 뽑은 키를, 주소 밖에서는 대문자 키
    모양만 본다. 소문자 조각(sf1006-issues #1)은 로컬 번호라 이슈로 보지 않는다.
    """
    if not text:
        return []
    refs: list[tuple[str | None, str | None]] = []
    rest = text
    for m in _URL.finditer(text):
        url = m.group(0).rstrip(".,;")
        refs.append((extract_issue_key(url), url))
        rest = rest.replace(m.group(0), " ")
    for m in _ANY_UPPER.finditer(rest):
        refs.append((m.group(1), None))

    seen: set = set()
    out = []
    for key, url in refs:
        mark = key or url
        if mark in seen:
            continue
        seen.add(mark)
        out.append((key, url))
    return out
