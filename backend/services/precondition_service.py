"""사전조건 셀의 "<TC-ID> 의 사전조건 [1~N] 참조" 표기를 해석한다.

프론트엔드의 src/utils/precondition.ts 와 같은 규칙을 쓴다. 두 곳을 함께 고쳐야 한다.
"""

import re
from typing import Dict, List, Optional, Set, Tuple

# 참조 문구. 셀 전체이거나 "1. " 로 시작하는 첫 항목으로 나타난다.
_REF_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*의\s*사전조건(?:\s*1~(\d+))?\s*참조\s*$")
_NUM_RE = re.compile(r"^\d+\.\s")


def split_items(raw: Optional[str]) -> List[str]:
    """사전조건 원문을 번호 항목 단위로 쪼갠다.

    번호로 시작하지 않는 줄은 직전 항목의 이어지는 줄로 붙인다.
    번호 항목이 하나도 없으면 원문 전체를 항목 1개로 본다.
    """
    text = (raw or "").strip()
    if not text:
        return []
    items: List[str] = []
    cur: Optional[str] = None
    for line in text.split("\n"):
        if _NUM_RE.match(line):
            if cur is not None:
                items.append(cur)
            cur = _NUM_RE.sub("", line, count=1)
        elif cur is None:
            cur = line
        else:
            cur += "\n" + line
    if cur is not None:
        items.append(cur)
    return items


def parse_ref(item: str) -> Optional[Tuple[str, Optional[int]]]:
    """항목 하나가 참조 문구이면 (대상 TC ID, 범위 끝) 을 돌려준다."""
    m = _REF_RE.match(item.strip())
    if not m:
        return None
    return m.group(1), int(m.group(2)) if m.group(2) else None


def has_ref(raw: Optional[str]) -> bool:
    return any(parse_ref(it) is not None for it in split_items(raw))


def resolve_items(tc_id: str, index: Dict[str, str], seen: Optional[Set[str]] = None) -> List[str]:
    """TC 의 사전조건을 참조 없는 항목 목록으로 펼친다.

    index 는 tc_id -> 사전조건 원문. 대상이 없거나 순환이면 안내 문구 1줄을 돌려준다.
    """
    seen = seen or set()
    if tc_id in seen:
        return [f"(순환 참조: {tc_id})"]
    raw = index.get(tc_id)
    if raw is None:
        return [f"(참조 대상을 찾을 수 없음: {tc_id})"]

    nxt = set(seen)
    nxt.add(tc_id)

    out: List[str] = []
    for item in split_items(raw):
        ref = parse_ref(item)
        if ref is None:
            out.append(item)
            continue
        target, upto = ref
        resolved = resolve_items(target, index, nxt)
        out.extend(resolved[:upto] if upto is not None else resolved)
    return out


def expand_text(tc_id: str, index: Dict[str, str]) -> str:
    """펼친 항목을 "1. ...\n2. ..." 형태의 사전조건 원문으로 되돌린다."""
    items = resolve_items(tc_id, index)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "\n".join(f"{i + 1}. {it}" for i, it in enumerate(items))


def build_index(testcases) -> Dict[str, str]:
    """TC 목록에서 tc_id -> 사전조건 원문 색인을 만든다."""
    return {tc.tc_id: (tc.precondition or "") for tc in testcases if tc.tc_id}
