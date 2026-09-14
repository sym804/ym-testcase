"""소프트 삭제된 TC 의 완전 삭제.

`main.py` 의 기동 훅에서 부른다. 세션을 인자로 받아 테스트에서 임시 DB 로
돌릴 수 있게 해 둔다.
"""
from datetime import timedelta

from sqlalchemy.orm import Session

from models import TestCase, TestResult, now_kst

#: 소프트 삭제 뒤 이 기간이 지나면 완전히 지운다.
PURGE_AFTER_DAYS = 7


def purge_deleted_testcases(db: Session) -> int:
    """기한이 지난 소프트 삭제 TC 를 지우고, 지운 건수를 돌려준다.

    ★수행 기록에 한 번이라도 들어간 TC 는 남긴다. 리포트와 런 상세는 "그때의
      수행 기록" 이라 지워진 TC 의 결과도 그대로 세는데, 여기서 TC 를 지우면
      cascade 로 결과 행까지 사라져 완료된 런의 총계가 8일째에 저절로 줄어든다.
      보존하기로 한 기록이 시간이 지나면 없어지는 셈이라 리포트로 쓸 수 없다.
      화면에서는 이미 지워져 보이지 않으므로 남아도 사용자에게 드러나지 않는다.
    """
    cutoff = now_kst() - timedelta(days=PURGE_AFTER_DAYS)
    used_tc_ids = db.query(TestResult.test_case_id).distinct().subquery()

    old = (
        db.query(TestCase)
        .filter(
            TestCase.deleted_at.isnot(None),
            TestCase.deleted_at < cutoff,
            ~TestCase.id.in_(db.query(used_tc_ids.c.test_case_id)),
        )
        .all()
    )
    for tc in old:
        db.delete(tc)
    if old:
        db.commit()
    return len(old)
