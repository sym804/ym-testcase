"""운영 보조 엔드포인트.

- `GET /api/config`: 화면과 CLI 가 업로드 상한을 하드코딩하지 않게 서버 값을 준다.
- `GET /api/internal/cron/daily`: Vercel Cron 이 하루 한 번 부른다. 서버리스에는 상주
  프로세스가 없어서, 기동 훅에서 하던 정리를 여기로 옮겼다.
"""
import hmac
import logging
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from models import StagedUpload, now_kst
from services import rate_limit
from services.locks import LockNs
from services.purge_service import purge_deleted_testcases
from services.staged_upload import PURPOSE_LIMITS
from services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["internal"])

#: 처리되지 않은 스테이징 업로드를 지우는 기준
STAGED_TTL = timedelta(days=1)
#: 횟수 제한 기록 보존 기간. 가장 긴 창(접수 1시간)보다 넉넉하게
RATE_LIMIT_KEEP_SEC = 2 * 24 * 3600


@router.get("/api/config")
def public_config():
    return {
        "upload_limits": dict(PURPOSE_LIMITS),
        # 저장소가 직접 받는가(배포). 로컬은 백엔드가 받는다. 클라이언트 흐름은 같다.
        "direct_upload": os.getenv("STORAGE_BACKEND", "local") == "supabase",
    }


def _check_cron_secret(request: Request) -> None:
    """Vercel Cron 은 `Authorization: Bearer <CRON_SECRET>` 를 붙여 부른다.

    ★비밀값이 비어 있으면 거부한다. 빈 값끼리 비교해 통과하는 일이 없게 한다.
    """
    secret = os.getenv("CRON_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET 이 설정되지 않았습니다.")
    given = request.headers.get("authorization", "")
    if not hmac.compare_digest(given, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/api/internal/cron/daily")
def cron_daily(request: Request, db: Session = Depends(get_db)):
    _check_cron_secret(request)
    # 겹쳐 돌지 않는다. 앞선 실행이 쥐고 있으면 기다리지 않고 건너뛴다.
    got = db.execute(text("SELECT pg_try_advisory_xact_lock(:ns, 0)"), {"ns": int(LockNs.CRON)}).scalar()
    if not got:
        return {"skipped": "running"}

    cutoff = now_kst() - STAGED_TTL
    stale = db.query(StagedUpload).filter(StagedUpload.created_at < cutoff).all()
    keys = [row.storage_key for row in stale]
    try:
        get_storage().delete(keys)
    except Exception:  # noqa: BLE001  객체 삭제 실패는 다음 날 다시 시도한다
        logger.warning("Failed to delete stale staged objects: %d", len(keys), exc_info=True)
        stale = []
    for row in stale:
        db.delete(row)

    purged = purge_deleted_testcases(db, commit=False)
    db.commit()
    events = rate_limit.purge_older_than(RATE_LIMIT_KEEP_SEC, engine=db.get_bind())
    result = {"staged_uploads": len(stale), "testcases": purged, "rate_limit_events": events}
    logger.info("cron daily: %s", result)
    return result
