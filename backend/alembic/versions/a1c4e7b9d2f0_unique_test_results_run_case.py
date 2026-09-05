"""test_results 에 (test_run_id, test_case_id) 유니크 제약 추가

결과 행을 만드는 경로가 셋이다(런 생성, 런 동기화, 결과 제출). 셋 다 "없는 것을
조회한 뒤 넣는" 모양이라 동시 요청에서 같은 (run, case) 를 두 번 넣을 수 있다.
실제로 운영 DB 에 중복이 하나 있었다(run=25, case=5345).

중복이 있으면 두 가지가 깨진다.
- routes/reports.py 의 집계가 func.count(TestResult.id) 라 total 이 부풀려진다
- submit_results 의 existing_map 은 test_case_id 를 키로 마지막 행만 잡으므로
  나머지 행은 고아 NS 로 남아 진행률을 왜곡한다

SQLite 는 기존 테이블에 UNIQUE 제약을 붙이려면 테이블을 다시 만들어야 한다.
유니크 인덱스는 같은 강제력을 가지면서 재생성이 필요 없다. 그래서 인덱스를 쓴다.

중복 정리는 삭제가 아니라 **병합**이다. 실측한 중복 두 행은 둘 다 실제 측정값을
갖고 있었다(`actual_result` 가 서로 달랐다). 지우면 기록이 사라진다.

Revision ID: a1c4e7b9d2f0
Revises: 05f8800a57f5
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa


revision = "a1c4e7b9d2f0"
down_revision = "05f8800a57f5"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_test_results_run_case"

#: NS 는 "아직 안 함" 이라 정보가 없다. 병합 시 실제 결과가 있으면 그쪽을 남긴다.
_EMPTY_RESULT = "NS"

#: 남길 행을 고를 때 함께 따라가야 하는 실행 메타데이터.
#: ★텍스트만 병합하고 이 칸들을 놔두면 "누가 언제 얼마나 걸려 실행했는지" 가 사라진다.
#:   남길 행이 우연히 NS 자리표시자면 실행자와 소요시간이 통째로 날아간다(QA2 지적).
_EXEC_COLUMNS = ("executed_by", "executed_at", "started_at", "finished_at", "duration_sec")

_SELECT_COLUMNS = ("id", "result", "actual_result", "remarks", "issue_link") + _EXEC_COLUMNS


def _merge_text(values):
    """빈 값을 빼고 중복을 없앤 뒤 줄바꿈으로 잇는다. 순서는 원본 순서를 지킨다."""
    out = []
    for v in values:
        v = (v or "").strip()
        if v and v not in out:
            out.append(v)
    return "\n".join(out) or None


def _is_real(result):
    return (result or "").upper() != _EMPTY_RESULT


def plan_merge(rows):
    """중복 행 목록을 받아 (남길 id, 갱신할 값, 지울 id 목록) 을 낸다.

    ★남길 행은 "가장 최근" 이 아니라 **실제 결과가 있는 행 중 가장 최근** 이다.
      그래야 실행자와 소요시간이 따라온다. 실제 결과가 없으면 마지막 행을 남긴다.
    ★issue_link 는 단일 URL 칸(String(500))이다. 줄바꿈으로 이으면 프론트의
      startsWith("http") 판정과 PDF 리포트 셀이 깨진다(QA 지적). 하나만 남기고
      나머지는 remarks 에 적는다.
    """
    real = [r for r in rows if _is_real(r["result"])]
    keep_row = real[-1] if real else rows[-1]

    notes = []
    distinct = []
    for r in real:
        if r["result"] not in distinct:
            distinct.append(r["result"])
    if len(distinct) > 1:
        # 결과가 서로 다른 중복은 사람이 봐야 한다. 조용히 하나만 남기지 않는다.
        notes.append("(병합: 결과가 서로 달랐다 - %s. %s 를 남김)"
                     % (", ".join(str(d) for d in distinct), keep_row["result"]))

    links = [r["issue_link"] for r in rows if (r["issue_link"] or "").strip()]
    kept_link = keep_row["issue_link"] or (links[0] if links else None)
    extra = [l for l in links if l != kept_link]
    if extra:
        notes.append("(병합된 이슈 링크: %s)" % ", ".join(extra))

    values = {
        "actual_result": _merge_text([r["actual_result"] for r in rows]),
        "remarks": _merge_text([r["remarks"] for r in rows] + notes),
        "result": keep_row["result"],
        "issue_link": kept_link,
    }
    for c in _EXEC_COLUMNS:
        values[c] = keep_row[c]
    return keep_row["id"], values, [r["id"] for r in rows if r["id"] != keep_row["id"]]


def merge_duplicates(conn):
    """중복 그룹을 병합한다. 반환값은 정리한 그룹 수."""
    groups = conn.execute(sa.text("""
        SELECT test_run_id, test_case_id
        FROM test_results
        GROUP BY test_run_id, test_case_id
        HAVING COUNT(*) > 1
    """)).fetchall()

    for run_id, case_id in groups:
        raw = conn.execute(sa.text("""
            SELECT %s FROM test_results
            WHERE test_run_id = :r AND test_case_id = :c
            ORDER BY id
        """ % ", ".join(_SELECT_COLUMNS)), {"r": run_id, "c": case_id}).fetchall()
        rows = [dict(zip(_SELECT_COLUMNS, r)) for r in raw]

        keep, values, drop = plan_merge(rows)
        if not drop:
            continue

        sets = ", ".join(f"{k} = :{k}" for k in values)
        conn.execute(sa.text(f"UPDATE test_results SET {sets} WHERE id = :_id"),
                     {**values, "_id": keep})

        # 첨부가 사라지지 않도록 남길 행으로 옮긴다
        conn.execute(sa.text(
            "UPDATE attachments SET test_result_id = :keep WHERE test_result_id IN :drop"
        ).bindparams(sa.bindparam("drop", expanding=True)), {"keep": keep, "drop": drop})

        conn.execute(sa.text(
            "DELETE FROM test_results WHERE id IN :drop"
        ).bindparams(sa.bindparam("drop", expanding=True)), {"drop": drop})

    return len(groups)


def upgrade() -> None:
    merge_duplicates(op.get_bind())
    op.create_index(
        INDEX_NAME, "test_results", ["test_run_id", "test_case_id"], unique=True
    )


def downgrade() -> None:
    # 병합된 텍스트는 되돌릴 수 없다. 제약만 푼다.
    op.drop_index(INDEX_NAME, table_name="test_results")
