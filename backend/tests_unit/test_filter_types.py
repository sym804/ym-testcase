"""정수 칸 no 에 문자열 연산을 걸면 400. SQLite 는 넘어갔지만 PostgreSQL 은 500 이었다."""
import os
import sys

import pytest
from fastapi import HTTPException

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from models import TestCase
from routes.filters import _apply_condition


@pytest.mark.parametrize("op,value", [("contains", "1"), ("not_contains", "1"), ("empty", None), ("not_empty", None)])
def test_정수_칸에_문자열_연산은_400(pg_session, op, value):
    with pytest.raises(HTTPException) as e:
        _apply_condition(pg_session.query(TestCase), "no", op, value)
    assert e.value.status_code == 400


@pytest.mark.parametrize("value", ["abc", "1.5", ""])
def test_정수_칸에_숫자가_아닌_값은_400(pg_session, value):
    with pytest.raises(HTTPException) as e:
        _apply_condition(pg_session.query(TestCase), "no", "gt", value)
    assert e.value.status_code == 400


def test_정수_칸_비교는_실행된다(pg_session):
    assert _apply_condition(pg_session.query(TestCase), "no", "gte", "3").all() == []


def test_정수_칸_in_은_정수로_바꾼다(pg_session):
    assert _apply_condition(pg_session.query(TestCase), "no", "in", ["1", "2"]).all() == []


def test_문자열_칸의_포함은_그대로(pg_session):
    assert _apply_condition(pg_session.query(TestCase), "tc_id", "contains", "TC").all() == []


@pytest.mark.parametrize("value", ["--5", "²", "9" * 400])
def test_정수로_못_바꾸는_값은_500_이_아니라_400(pg_session, value):
    with pytest.raises(HTTPException) as e:
        _apply_condition(pg_session.query(TestCase), "no", "eq", value)
    assert e.value.status_code == 400


@pytest.mark.parametrize("value", ["1", 1, {"a": 1}])
def test_in_은_리스트만_받는다(pg_session, value):
    with pytest.raises(HTTPException) as e:
        _apply_condition(pg_session.query(TestCase), "no", "in", value)
    assert e.value.status_code == 400


def test_문자열_칸에_숫자를_줘도_500_이_아니다(pg_session):
    assert _apply_condition(pg_session.query(TestCase), "tc_id", "eq", 5).all() == []
