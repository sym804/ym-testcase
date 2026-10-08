"""스테이징 업로드 API. 흐름은 services/staged_upload.py 참고."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import StagedUpload, User
from services import staged_upload
from services.storage import get_storage

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadRequest(BaseModel):
    purpose: str = Field(..., max_length=32)
    filename: str = Field(..., max_length=255)
    size: int = Field(..., ge=0)
    content_type: Optional[str] = Field(None, max_length=255)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_upload(
    payload: UploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = staged_upload.new_upload(db, current_user, payload.purpose, payload.filename,
                                   payload.size, payload.content_type)
    target = staged_upload.upload_target(row)
    db.commit()
    return {"upload_id": row.id, **target}


@router.put("/{upload_id}/content")
async def put_content(upload_id: str, request: Request, token: str = Query(...),
                      db: Session = Depends(get_db)):
    """로컬 저장소 전용 업로드 받기. 배포(Supabase)에서는 클라이언트가 저장소에 직접 올린다.

    인증은 쿠키가 아니라 발급 때 준 토큰(15분, 이 upload_id 전용)으로 한다.
    """
    staged_upload.verify_token(token, upload_id)
    row = db.query(StagedUpload).filter(StagedUpload.id == upload_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="업로드를 찾을 수 없습니다.")
    storage = get_storage()
    if storage.upload_target(row.storage_key, row.content_type) is not None:
        raise HTTPException(status_code=400, detail="이 배포에서는 저장소에 직접 올립니다.")
    if storage.size(row.storage_key) is not None:
        raise HTTPException(status_code=409, detail="이미 올린 업로드입니다.")
    limit = staged_upload.PURPOSE_LIMITS[row.purpose]
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {limit // (1024 * 1024)}MB")
    storage.put(row.storage_key, bytes(buf), row.content_type)
    return {"upload_id": upload_id, "size": len(buf)}
