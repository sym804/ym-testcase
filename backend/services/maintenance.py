"""일일 정리. Vercel Cron(/api/internal/cron/daily)과 로컬 기동 정리가 같이 쓴다.

- 하루 지난 스테이징 업로드(버려진 것, 처리가 끝난 가져오기 파일)
- 지우지 못했던 저장소 객체 재시도
- 기한이 지난 소프트 삭제 TC
- 오래된 횟수 제한 기록

★한 항목이 실패해도 나머지는 한다. 저장소 장애는 세이브포인트로 그 항목만 되돌리고
  기록을 남겨 다음 정리에서 다시 시도한다.
"""
import logging

from sqlalchemy.orm import Session

from models import StorageDeletion
from services import rate_limit
from services.purge_service import purge_deleted_testcases
from services.staged_upload import cleanup_staging
from services.storage import get_storage

logger = logging.getLogger(__name__)

#: 횟수 제한 기록 보존 기간. 가장 긴 창(접수 1시간)보다 넉넉하게
RATE_LIMIT_KEEP_SEC = 2 * 24 * 3600
#: 한 번에 다시 시도할 삭제 건수
RETRY_BATCH = 500


def retry_storage_deletions(db: Session) -> int:
    rows = db.query(StorageDeletion).order_by(StorageDeletion.id).limit(RETRY_BATCH).all()
    if not rows:
        return 0
    get_storage().delete([r.storage_key for r in rows])
    for r in rows:
        db.delete(r)
    return len(rows)


def _guarded(db: Session, name: str, fn) -> int:
    try:
        with db.begin_nested():
            return fn(db)
    except Exception:  # noqa: BLE001  다음 정리에서 다시 시도한다
        logger.warning("daily maintenance step failed: %s", name, exc_info=True)
        return 0


def run_daily(db: Session, engine=None) -> dict:
    """커밋까지 한다. 부른 쪽이 잡은 트랜잭션 잠금은 커밋에서 풀린다."""
    result = {
        "staged_uploads": _guarded(db, "staging", cleanup_staging),
        "storage_retries": _guarded(db, "storage_retry", retry_storage_deletions),
        "testcases": _guarded(db, "purge", lambda s: purge_deleted_testcases(s, commit=False)),
    }
    db.commit()
    result["rate_limit_events"] = rate_limit.purge_older_than(
        RATE_LIMIT_KEEP_SEC, engine=engine or db.get_bind())
    logger.info("daily maintenance: %s", result)
    return result
