"""시트가 화면에 놓이는 차례.

수행 엑셀과 리포트 엑셀이 각자 정렬을 들고 있으면 한쪽만 고쳤을 때 같은 수행이
두 파일에서 다른 순서, 다른 번호를 낸다. 두 곳이 이 함수를 같이 쓴다.

기준은 화면이다. `routes/sheets.py:list_sheets` 가 만드는 트리를 깊이 우선으로
펴고 폴더를 걷어 낸 것과 같은 차례여야 한다.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import TestCase, TestCaseSheet


def leaf_sheet_order(project_id: int, db: Session) -> dict:
    """시트 이름 -> 차례(0 부터). 목록에 없는 이름은 담기지 않는다."""
    rows = (
        db.query(TestCaseSheet)
        .filter(TestCaseSheet.project_id == project_id)
        .order_by(TestCaseSheet.sort_order, TestCaseSheet.id)
        .all()
    )
    ids = {s.id for s in rows}
    children: dict = {}
    for s in rows:
        # 부모가 지워졌으면 루트로 본다. 트리 밖으로 새면 순서에서 빠진다.
        parent = s.parent_id if s.parent_id in ids else None
        children.setdefault(parent, []).append(s)

    order: dict = {}

    def walk(parent):
        for s in children.get(parent, []):
            if not s.is_folder and s.name not in order:
                order[s.name] = len(order)
            walk(s.id)

    walk(None)

    # 트리에 없는 sheet_name 은 화면에서도 뒤에 붙는다(sheets.py 의 호환 처리).
    # 지금 API 는 등록되지 않은 시트로 TC 를 만들지 못하게 막지만, 시트를 등록하지
    # 않고 쓰던 시절의 데이터가 남아 있으면 여기서 순서가 없어진다.
    extras = (
        db.query(TestCase.sheet_name)
        .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None))
        .group_by(TestCase.sheet_name)
        .order_by(func.min(TestCase.id))
        .all()
    )
    for (name,) in extras:
        order.setdefault(name or "기본", len(order))

    return order


def sort_results_for_export(results, order: dict):
    """결과 행을 화면과 같은 차례로 세운다. 시트 순서가 먼저고 그 안에서 no 순이다."""
    last = len(order)
    return sorted(
        results,
        key=lambda r: (
            order.get(r.test_case.sheet_name, last) if r.test_case else last,
            r.test_case.no if r.test_case else 0,
        ),
    )
