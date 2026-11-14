"""스테이징 업로드: 주소 발급, 꺼내 쓰기.

흐름은 세 단계다.
  1. 클라이언트가 목적·파일명·크기를 알리고 업로드 주소를 받는다(new_upload).
  2. 클라이언트가 그 주소에 파일을 올린다. 배포는 Supabase 서명 주소, 로컬은 백엔드
     `/api/uploads/{id}/content?token=`(save_local_content).
  3. 처리 요청이 upload_id 를 보내면 서버가 저장소에서 꺼내 쓴다(consume,
     claim_for_attachment).

★선언한 크기는 믿지 않는다. 발급 때는 선언을 보고, 꺼낼 때는 실제 크기로 다시 막는다.
★남이 올린 것을 꺼낼 수 없다. 소유자와 목적을 대조하고, 한 번 쓴 것은 다시 쓸 수 없다.
"""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
import jwt
from jwt import PyJWTError as JWTError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from models import StagedUpload, User, now_kst
from services.storage import get_storage

MB = 1024 * 1024
#: 목적별 상한. 기존 multipart 상한과 같다(첨부 50MB, TC 가져오기 10MB, 자동화 결과 20MB).
PURPOSE_LIMITS = {"attachment": 50 * MB, "tc_import": 10 * MB, "result_import": 20 * MB}
TOKEN_TTL = timedelta(minutes=15)
_TOKEN_USE = "staged-upload"


def _safe_name(filename: str) -> str:
    base = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem, dot, ext = base.rpartition(".")
    clean = lambda s: re.sub(r"[^A-Za-z0-9_-]", "_", s)[:80].strip("_")  # noqa: E731
    ext = clean(ext)[:10] if dot else ""
    stem = clean(stem if dot else base) or "file"
    return f"{stem}.{ext}" if ext else stem


def _limit(purpose: str) -> int:
    if purpose not in PURPOSE_LIMITS:
        raise HTTPException(status_code=400, detail=f"알 수 없는 업로드 목적: {purpose}")
    return PURPOSE_LIMITS[purpose]


def _too_large(limit: int) -> HTTPException:
    return HTTPException(status_code=413, detail=f"File too large. Maximum size is {limit // MB}MB")


TOO_MANY_PENDING = "처리하지 않은 업로드가 너무 많습니다. 최대 1시간 뒤 다시 시도해 주세요."
TOO_MANY_UPLOADS = "업로드 요청이 너무 많습니다. 최대 1시간 뒤 다시 시도해 주세요."
BUCKET_STAGING = "staging"
STAGING_WINDOW_SEC = 3600
#: 미처리 상한을 세는 범위. 미리보기·dry run 은 처리 표시를 롤백하므로 고르기만 하고 그만둔
#: 업로드가 남는다. 정리(하루 뒤 Cron)까지 세면 그동안 업로드를 전혀 못 한다(QA1 지적).
STAGING_PENDING_WINDOW = timedelta(hours=1)


def _pending_limit() -> int:
    return int(os.getenv("STAGING_MAX_PENDING", "30"))


def _pending_bytes_limit() -> int:
    return int(os.getenv("STAGING_MAX_PENDING_MB", "500")) * MB


def _hourly_limit() -> int:
    """시간당 발급 수. CI 업로드(ymtc-upload)는 실행마다 한 번이다. 파이프라인 여럿이 계정 하나를
    같이 쓰면 그 합계로 센다(할당량은 API 키가 아니라 사용자별이다)."""
    return int(os.getenv("STAGING_MAX_PER_HOUR", "120"))


def _check_user_quota(db: Session, user: User, size: int) -> None:
    """사용자별 발급 상한(SYM-219). 발급 하나가 최대 50MB 저장소 자리이고 정리는 하루 뒤다.

    - 최근 1시간에 발급하고 처리하지 않은 업로드(consumed_at 이 빈 것) 개수와 선언 크기 합계
    - 시간당 발급 횟수. 처리한 것도 센다. 발급과 처리를 반복해도 저장소는 하루 동안 찬다
    ★선언 크기는 믿지 않는 값이다. 실제 크기는 목적별 상한(꺼낼 때 다시 잰다)을 못 넘으므로,
      저장소 총량을 묶는 것은 시간당 발급 수다(정리 전 하루 최대 120 x 24건). 미처리 상한은 최근
      1시간분만 세므로 짧은 시간에 몰아 쌓는 것을 막는다.
    ★사용자별로 잠근다. 잠그지 않으면 동시에 온 발급이 모두 같은 개수를 보고 통과한다.
    """
    from sqlalchemy import func

    from services import rate_limit
    from services.locks import LockNs, keyed_xact_lock

    keyed_xact_lock(db, LockNs.RATE_LIMIT, f"{BUCKET_STAGING}:{user.id}")
    key = f"user:{user.id}"
    if rate_limit.count_recent(BUCKET_STAGING, key, STAGING_WINDOW_SEC, engine=db.get_bind()) >= _hourly_limit():
        raise HTTPException(status_code=429, detail=TOO_MANY_UPLOADS)
    count, total = (db.query(func.count(StagedUpload.id), func.coalesce(func.sum(StagedUpload.declared_size), 0))
                    .filter(StagedUpload.user_id == user.id, StagedUpload.consumed_at.is_(None),
                            StagedUpload.created_at >= now_kst() - STAGING_PENDING_WINDOW).one())
    if count >= _pending_limit() or total + size > _pending_bytes_limit():
        raise HTTPException(status_code=429, detail=TOO_MANY_PENDING)
    # 받기로 정한 뒤에 센다. 거절된 요청까지 세면 상한이 풀린 뒤에도 한 시간 더 막힌다.
    rate_limit.record(BUCKET_STAGING, key, engine=db.get_bind())


def new_upload(db: Session, user: User, purpose: str, filename: str, size: int,
               content_type: str | None) -> StagedUpload:
    limit = _limit(purpose)
    if size < 0 or size > limit:
        raise _too_large(limit)
    _check_user_quota(db, user, size)
    upload_id = uuid.uuid4().hex
    row = StagedUpload(
        id=upload_id, user_id=user.id, purpose=purpose, filename=(filename or "file")[:255],
        content_type=content_type, declared_size=size,
        storage_key=f"staging/{upload_id}/{_safe_name(filename)}",
    )
    db.add(row)
    db.flush()
    return row


def upload_token(row: StagedUpload) -> str:
    from auth import ALGORITHM, SECRET_KEY
    exp = datetime.now(timezone.utc) + TOKEN_TTL
    return jwt.encode({"use": _TOKEN_USE, "uid": row.id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, upload_id: str) -> None:
    from auth import ALGORITHM, SECRET_KEY
    try:
        payload = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="업로드 주소가 유효하지 않습니다.")
    if payload.get("use") != _TOKEN_USE or payload.get("uid") != upload_id:
        raise HTTPException(status_code=401, detail="업로드 주소가 유효하지 않습니다.")


def upload_target(row: StagedUpload) -> dict:
    """클라이언트가 파일을 올릴 곳. 저장소가 직접 받으면 서명 주소, 아니면 백엔드."""
    target = get_storage().upload_target(row.storage_key, row.content_type)
    if target is not None:
        return target
    return {
        "method": "PUT",
        "url": f"/api/uploads/{row.id}/content?token={upload_token(row)}",
        "headers": {"content-type": row.content_type or "application/octet-stream"},
    }


def _get(db: Session, upload_id: str, user: User, purpose: str) -> StagedUpload:
    # NOWAIT: 첨부 라우트는 async 라 잠금을 기다리면 이벤트 루프가 멈춘다. 동시에 같은
    # 업로드를 쓰려 하면 하나는 바로 409 로 끝난다.
    try:
        row = (db.query(StagedUpload).filter(StagedUpload.id == upload_id)
               .with_for_update(nowait=True).first())
    except OperationalError:
        db.rollback()
        raise HTTPException(status_code=409, detail="같은 업로드를 처리하는 중입니다.")
    if row is None:
        raise HTTPException(status_code=404, detail="업로드를 찾을 수 없습니다.")
    if row.user_id != user.id:
        raise HTTPException(status_code=403, detail="다른 사용자의 업로드입니다.")
    if row.purpose != purpose:
        raise HTTPException(status_code=400, detail="이 작업에 쓸 업로드가 아닙니다.")
    if row.consumed_at is not None:
        raise HTTPException(status_code=409, detail="이미 처리한 업로드입니다.")
    return row


def consume(db: Session, upload_id: str, user: User, purpose: str) -> tuple[str, str | None, bytes]:
    """가져오기용. 바이트를 꺼내고 처리 표시를 한다. 커밋은 부른 쪽이 한다."""
    row = _get(db, upload_id, user, purpose)
    storage = get_storage()
    if storage.size(row.storage_key) is None:
        raise HTTPException(status_code=400, detail="파일이 아직 올라오지 않았습니다.")
    data = storage.read(row.storage_key, PURPOSE_LIMITS[purpose])
    row.consumed_at = now_kst()
    return row.filename, row.content_type, data


def claim_for_attachment(db: Session, upload_id: str, user: User) -> tuple[str, str | None, int, str]:
    """첨부용. 바이트를 읽지 않고 실제 크기만 확인해 저장소 키를 넘긴다."""
    row = _get(db, upload_id, user, "attachment")
    size = get_storage().size(row.storage_key)
    if size is None:
        raise HTTPException(status_code=400, detail="파일이 아직 올라오지 않았습니다.")
    if size > PURPOSE_LIMITS["attachment"]:
        raise _too_large(PURPOSE_LIMITS["attachment"])
    filename, content_type, key = row.filename, row.content_type, row.storage_key
    # ★스테이징 기록을 지운다. 이 객체는 이제 첨부의 것이라 스테이징 정리 대상이 아니다.
    #   기록을 남겨 두면 정리 작업이 하루 뒤 첨부 파일을 지운다(QA 2인 지적, 재현).
    db.delete(row)
    return filename, content_type, size, key


#: 처리되지 않았거나 처리가 끝난 가져오기 업로드를 지우는 기준
STAGED_TTL = timedelta(days=1)


def cleanup_staging(db: Session) -> int:
    """하루 지난 스테이징 업로드의 객체와 기록을 지운다. 커밋은 부른 쪽이 한다.

    첨부로 쓰인 업로드는 claim 때 기록이 지워지므로 여기 남아 있지 않다. 남은 것은
    버려진 업로드와 처리가 끝난 가져오기 파일뿐이다. Cron 과 로컬 기동 정리가 같이 쓴다.
    """
    stale = db.query(StagedUpload).filter(StagedUpload.created_at < now_kst() - STAGED_TTL).all()
    if not stale:
        return 0
    get_storage().delete([row.storage_key for row in stale])
    for row in stale:
        db.delete(row)
    return len(stale)


class BytesUpload:
    """꺼낸 바이트를 UploadFile 과 같은 모양(filename, file, content_type, read)으로 감싼다.

    기존 파서가 UploadFile 의 이 속성들만 쓰므로, upload_id 경로를 위해 파서를 고치지 않는다.
    """

    def __init__(self, filename: str, data: bytes, content_type: str | None = None):
        import io
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self.file.read(size)


def resolve_file(db: Session, user: User, purpose: str, file, upload_id: str | None):
    """multipart 파일과 upload_id 중 정확히 하나를 받아 UploadFile 모양으로 돌려준다."""
    # 라우트 함수를 직접 부르면(테스트, 내부 호출) 기본값이 None 이 아니라 FastAPI 의
    # Query/File 표지 객체로 들어온다. 문자열이 아니면 보내지 않은 것으로 본다.
    if not isinstance(upload_id, str):
        upload_id = None
    if file is not None and not hasattr(file, "filename"):
        file = None
    if (file is None) == (upload_id is None):
        raise HTTPException(status_code=400, detail="파일 또는 upload_id 중 하나만 보냅니다.")
    if file is not None:
        return file
    name, content_type, data = consume(db, upload_id, user, purpose)
    return BytesUpload(name, data, content_type)
