"""TC ID 채번

TC ID 는 프로젝트 안에서 유일해야 한다. 사전조건 참조("<TC-ID> 의 사전조건 참조")를
푸는 색인이 프로젝트 전체 TC 로 만들어지기 때문에(`precondition_service.build_index`),
같은 ID 가 둘 있으면 참조가 어느 쪽을 가리키는지 정해지지 않는다.

DB 쪽은 부분 유니크 인덱스(`uq_test_cases_project_tc_id`, `deleted_at IS NULL`)가
막아 준다. 이 모듈은 그 인덱스에 걸리기 전에 빈 번호를 찾아 주는 역할이다.
"""
from typing import Iterable, Set

from sqlalchemy.orm import Session

from models import TestCase

# models.TestCase.tc_id 는 String(50)
TC_ID_MAX_LEN = 50


def taken_tc_ids(project_id: int, db: Session) -> Set[str]:
    """프로젝트에서 이미 쓰이는 TC ID. 소프트 삭제된 행은 세지 않는다."""
    rows = (
        db.query(TestCase.tc_id)
        .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None))
        .all()
    )
    return {r[0] for r in rows if r[0]}


def allocate_tc_id(base: str, taken: Iterable[str]) -> str:
    """base 가 비어 있으면 그대로, 이미 쓰이면 `-2`, `-3` ... 으로 빈 번호를 찾는다.

    호출부가 결과를 taken 에 넣어 줘야 같은 루프 안에서 또 겹치지 않는다.
    """
    taken_set = taken if isinstance(taken, set) else set(taken)
    base = (base or "").strip() or "TC"

    # 길이를 먼저 맞춘 뒤에 충돌을 본다. 순서를 바꾸면 잘린 결과가
    # 이미 쓰이는 ID 와 같아도 통과해 버린다.
    candidate = _fit(base)
    if candidate not in taken_set:
        return candidate

    n = 2
    while True:
        candidate = _fit(base, suffix=f"-{n}")
        if candidate not in taken_set:
            return candidate
        n += 1


def _fit(base: str, suffix: str = "") -> str:
    """길이 상한(50)을 넘으면 접미사를 살리고 앞부분을 줄인다."""
    if len(base) + len(suffix) <= TC_ID_MAX_LEN:
        return base + suffix
    return base[: TC_ID_MAX_LEN - len(suffix)] + suffix
