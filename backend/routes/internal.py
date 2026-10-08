"""운영 보조 엔드포인트.

- `GET /api/config`: 화면과 CLI 가 업로드 상한을 하드코딩하지 않게 서버 값을 준다.
- `GET /api/internal/cron/daily`: Vercel Cron 이 하루 한 번 부른다. 서버리스에는 상주
  프로세스가 없어서, 기동 훅에서 하던 정리를 여기로 옮겼다.
"""
import hmac
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from services.locks import LockNs
from services.maintenance import run_daily
from services.staged_upload import PURPOSE_LIMITS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["internal"])



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

    return run_daily(db)
