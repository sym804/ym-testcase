"""런타임에서 실제로 도는 재번호 함수를 본다.

`services/tc_numbering.py` 는 임포트와 시트 이동이 부른다. 그런데 검증은 마이그레이션
쪽 복사본만 받고 있었다. 그쪽 테스트는 유니크 인덱스가 없는 최소 테이블을 쓰므로,
인덱스 아래에서만 터지는 결함을 잡지 못한다.

여기서는 모델로 테이블을 만든다. `uq_test_cases_sheet_no` 가 함께 생기므로, 번호를
옮기는 도중 두 행이 같은 번호를 갖는 순간이 있으면 그 자리에서 IntegrityError 가 난다.

실행: cd backend && python -m pytest test_tc_renumber_service.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def session(tmp_path):
    """모델 그대로 만든 DB. 유니크 인덱스가 걸려 있다."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import models

    url = f"sqlite:///{(tmp_path / 'renumber.db').as_posix()}"
    engine = create_engine(url)
    models.Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()

    user = models.User(username="u", password_hash="x", display_name="U")
    s.add(user)
    s.flush()
    project = models.Project(name="P", created_by=user.id)
    s.add(project)
    s.flush()

    yield s, project.id, user.id
    s.close()
    engine.dispose()


def _add(s, pid, uid, sheet, no, tc_id, deleted=False):
    from models import TestCase, now_kst

    tc = TestCase(
        project_id=pid, sheet_name=sheet, no=no, tc_id=tc_id, created_by=uid,
        deleted_at=now_kst() if deleted else None,
    )
    s.add(tc)
    s.flush()
    return tc.id


def _state(s, pid, sheet, alive=True):
    from models import TestCase

    q = s.query(TestCase.id, TestCase.no).filter(
        TestCase.project_id == pid, TestCase.sheet_name == sheet
    )
    q = q.filter(TestCase.deleted_at.is_(None) if alive else TestCase.deleted_at.isnot(None))
    return [(i, n) for i, n in sorted(q.all(), key=lambda r: r[1])]


def test_index_exists(session):
    """이 파일의 전제. 인덱스가 없으면 아래 테스트는 아무것도 못 잡는다."""
    from sqlalchemy import inspect

    s, _, _ = session
    names = {ix["name"] for ix in inspect(s.get_bind()).get_indexes("test_cases")}
    assert "uq_test_cases_sheet_no" in names


def test_renumber_when_order_disagrees_with_rowid(session):
    """번호 순서와 id 순서가 어긋나도 도중에 충돌하지 않는다.

    드래그로 뒤집은 뒤 한 건을 지우면 이 상태가 된다. UPDATE 에는 순서가 없어서,
    한 문장으로 쓰면 아직 다른 행이 쥐고 있는 번호를 먼저 쓰게 된다.
    """
    from services.tc_numbering import renumber_sheet

    s, pid, uid = session
    a = _add(s, pid, uid, "결제", 3, "TC-A")   # id 작고 번호 큼
    b = _add(s, pid, uid, "결제", 2, "TC-B")

    renumber_sheet(pid, "결제", s)
    s.flush()

    assert _state(s, pid, "결제") == [(b, 1), (a, 2)]


def test_renumber_full_reverse(session):
    """완전히 뒤집힌 시트도 통과한다."""
    from services.tc_numbering import renumber_sheet

    s, pid, uid = session
    ids = [_add(s, pid, uid, "결제", n, f"TC-{n}") for n in (5, 4, 3, 2, 1)]

    renumber_sheet(pid, "결제", s)
    s.flush()

    assert _state(s, pid, "결제") == [(ids[4], 1), (ids[3], 2), (ids[2], 3), (ids[1], 4), (ids[0], 5)]


def test_renumber_fills_gaps(session):
    """구멍을 메운다."""
    from services.tc_numbering import renumber_sheet

    s, pid, uid = session
    a = _add(s, pid, uid, "결제", 4, "TC-A")
    b = _add(s, pid, uid, "결제", 9, "TC-B")

    renumber_sheet(pid, "결제", s)
    s.flush()

    assert _state(s, pid, "결제") == [(a, 1), (b, 2)]


def test_renumber_pushes_deleted_behind(session):
    """지운 행은 살아 있는 번호 뒤로 간다."""
    from services.tc_numbering import renumber_sheet

    s, pid, uid = session
    a = _add(s, pid, uid, "결제", 1, "TC-A")
    d = _add(s, pid, uid, "결제", 2, "TC-D", deleted=True)
    b = _add(s, pid, uid, "결제", 3, "TC-B")

    renumber_sheet(pid, "결제", s)
    s.flush()

    assert _state(s, pid, "결제") == [(a, 1), (b, 2)]
    assert _state(s, pid, "결제", alive=False) == [(d, 3)]


def test_renumber_leaves_other_sheets_alone(session):
    """다른 시트는 건드리지 않는다."""
    from services.tc_numbering import renumber_sheet

    s, pid, uid = session
    _add(s, pid, uid, "결제", 7, "TC-P")
    other = _add(s, pid, uid, "로그인", 5, "TC-L")

    renumber_sheet(pid, "결제", s)
    s.flush()

    assert _state(s, pid, "로그인") == [(other, 5)]


def test_park_then_renumber_keeps_order(session):
    """비켜 둔 행은 이번에 다룬 행 뒤로 가고 자기들끼리 차례를 지킨다.

    임포트가 쓰는 흐름이다. 비켜 둔 뒤 파일이 1..N 을 붙이고, 끝나면 정리한다.
    """
    from services.tc_numbering import park_sheet_numbers, renumber_sheet

    s, pid, uid = session
    old1 = _add(s, pid, uid, "결제", 1, "TC-OLD1")
    old2 = _add(s, pid, uid, "결제", 2, "TC-OLD2")

    park_sheet_numbers(pid, "결제", s)
    s.flush()
    new1 = _add(s, pid, uid, "결제", 1, "TC-NEW1")
    new2 = _add(s, pid, uid, "결제", 2, "TC-NEW2")

    renumber_sheet(pid, "결제", s)
    s.flush()

    assert _state(s, pid, "결제") == [(new1, 1), (new2, 2), (old1, 3), (old2, 4)]


def test_renumber_when_negative_numbers_already_exist(session):
    """음수 번호가 이미 있어도 비켜 둘 자리와 부딪치지 않는다.

    비켜 두는 자리를 고정 상수로 잡으면 데이터에 그 값이 들어왔을 때 겹친다.
    """
    from services.tc_numbering import renumber_sheet

    s, pid, uid = session
    a = _add(s, pid, uid, "결제", -1000001, "TC-A")
    b = _add(s, pid, uid, "결제", -1000002, "TC-B")
    c = _add(s, pid, uid, "결제", 3, "TC-C")

    renumber_sheet(pid, "결제", s)
    s.flush()

    # 양수가 앞, 음수는 절대값 순으로 뒤
    assert _state(s, pid, "결제") == [(c, 1), (a, 2), (b, 3)]


def test_park_twice_does_not_collide(session):
    """이미 비켜 둔 시트를 또 비켜 둬도 겹치지 않는다."""
    from services.tc_numbering import park_sheet_numbers, renumber_sheet

    s, pid, uid = session
    a = _add(s, pid, uid, "결제", 1, "TC-A")
    b = _add(s, pid, uid, "결제", 2, "TC-B")

    park_sheet_numbers(pid, "결제", s)
    s.flush()
    park_sheet_numbers(pid, "결제", s)   # 남은 양수가 없으므로 아무 일도 없어야 한다
    s.flush()
    renumber_sheet(pid, "결제", s)
    s.flush()

    assert _state(s, pid, "결제") == [(a, 1), (b, 2)]


def test_park_does_not_hit_existing_negative(session):
    """비켜 둘 자리가 이미 쓰이고 있으면 안 된다.

    바닥을 max(abs(no)) 로 잡으면 0 을 비켜 둘 때 -(floor + 0) 이 되어 기존 -floor
    와 부딪친다.
    """
    from services.tc_numbering import park_sheet_numbers, renumber_sheet

    s, pid, uid = session
    _add(s, pid, uid, "결제", -5, "TC-A")
    _add(s, pid, uid, "결제", 0, "TC-B")
    _add(s, pid, uid, "결제", 5, "TC-C")

    park_sheet_numbers(pid, "결제", s)
    s.flush()
    renumber_sheet(pid, "결제", s)
    s.flush()

    assert [n for _, n in _state(s, pid, "결제")] == [1, 2, 3]


def test_park_moves_zero_behind_imported_rows(session):
    """옛 데이터의 0 도 비켜져야 한다.

    비켜 두는 바닥을 max(abs(no)) 로 잡으면, 0 하나뿐인 시트에서 바닥도 0 이라
    -(0 + 0) = 0 이 되어 park 이 아무 일도 하지 않는다. 그러면 그 행이 임포트한
    행들보다 앞에 선다.
    """
    from services.tc_numbering import park_sheet_numbers, renumber_sheet

    s, pid, uid = session
    old = _add(s, pid, uid, "결제", 0, "TC-OLD")

    park_sheet_numbers(pid, "결제", s)
    s.flush()
    new = _add(s, pid, uid, "결제", 1, "TC-NEW")

    renumber_sheet(pid, "결제", s)
    s.flush()

    assert _state(s, pid, "결제") == [(new, 1), (old, 2)]
