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
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import JWTError, jwt
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


def new_upload(db: Session, user: User, purpose: str, filename: str, size: int,
               content_type: str | None) -> StagedUpload:
    limit = _limit(purpose)
    if size < 0 or size > limit:
        raise _too_large(limit)
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
    row = db.query(StagedUpload).filter(StagedUpload.id == upload_id).with_for_update().first()
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
