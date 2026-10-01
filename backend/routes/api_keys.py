"""본인 API 키 발급 · 목록 · 폐기.

전부 로그인 세션으로만 받는다(`get_session_user`). 키 하나가 새 키를 찍어 내면
폐기해도 끝나지 않는다.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from auth import generate_api_key, get_session_user, hash_api_key
from database import get_db
from models import ApiKey, User, now_kst

router = APIRouter(prefix="/api/auth/api-keys", tags=["api-keys"])

#: 한 사용자가 동시에 쥘 수 있는 살아 있는 키 수. 쓰지 않는 키가 쌓이지 않게.
MAX_ACTIVE_KEYS = 20
#: 만료 일수 선택지. None 은 만료 없음.
ALLOWED_EXPIRES_DAYS = (30, 90, 180, 365)


class ApiKeyCreate(BaseModel):
    name: str = Field(..., max_length=100)
    expires_days: Optional[int] = 90

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("키 이름을 입력해 주세요.")
        return v

    @field_validator("expires_days")
    @classmethod
    def _check_days(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in ALLOWED_EXPIRES_DAYS:
            raise ValueError(f"만료 기간은 {', '.join(map(str, ALLOWED_EXPIRES_DAYS))}일 또는 없음 중에서 고릅니다.")
        return v


class ApiKeyItem(BaseModel):
    id: int
    name: str
    #: 화면에서 어느 키인지 알아보는 표시. 원문의 앞부분(`ymtc_<key_id>`)이다.
    prefix: str
    created_at: Optional[datetime]
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    #: active | expired | revoked
    status: str


class ApiKeyCreated(ApiKeyItem):
    #: 원문. 이 응답에서만 준다. 서버는 해시만 남긴다.
    key: str


def _status(k: ApiKey, now: datetime) -> str:
    if k.revoked_at is not None:
        return "revoked"
    if k.expires_at is not None and k.expires_at <= now:
        return "expired"
    return "active"


def _item(k: ApiKey, now: datetime) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "prefix": f"ymtc_{k.key_id}",
        "created_at": k.created_at,
        "last_used_at": k.last_used_at,
        "expires_at": k.expires_at,
        "revoked_at": k.revoked_at,
        "status": _status(k, now),
    }


@router.get("", response_model=List[ApiKeyItem])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_session_user),
):
    now = now_kst()
    keys = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
        .all()
    )
    return [_item(k, now) for k in keys]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_session_user),
):
    now = now_kst()
    active = (
        db.query(ApiKey)
        .filter(
            ApiKey.user_id == current_user.id,
            ApiKey.revoked_at.is_(None),
        )
        .all()
    )
    if sum(1 for k in active if _status(k, now) == "active") >= MAX_ACTIVE_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"사용 중인 키가 {MAX_ACTIVE_KEYS}개입니다. 쓰지 않는 키를 폐기한 뒤 만들어 주세요.",
        )

    raw, key_id = generate_api_key()
    key = ApiKey(
        user_id=current_user.id,
        name=payload.name,
        key_id=key_id,
        key_hash=hash_api_key(raw),
        created_at=now,
        expires_at=now + timedelta(days=payload.expires_days) if payload.expires_days else None,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return {**_item(key, now), "key": raw}


@router.delete("/{key_id}", response_model=ApiKeyItem)
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_session_user),
):
    # 다른 사용자의 키는 있어도 없는 것처럼 404 로 답한다. 존재 여부를 알려 주지 않는다.
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id).first()
    if not key:
        raise HTTPException(status_code=404, detail="키를 찾을 수 없습니다.")
    now = now_kst()
    if key.revoked_at is None:
        key.revoked_at = now
        db.commit()
        db.refresh(key)
    return _item(key, now)
