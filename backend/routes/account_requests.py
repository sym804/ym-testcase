"""계정 복구 (아이디 찾기 / 비밀번호 재설정).

메일 발송 경로가 없어 셀프 서비스가 불가능하므로 관리자 승인 큐로 처리한다.
관리자와 사용자 사이에 오가는 것은 1회용 코드이며 비밀번호 자체는 전달되지 않는다.
"""
import logging
import secrets
import time
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import (
    AccountRequest, AccountRequestStatus, AccountRequestType, User, now_kst,
)
from schemas import (
    AccountRequestAck, AccountRequestApprove, AccountRequestApproveResult,
    AccountRequestCreate, AccountRequestListItem, AccountRequestReject,
    ResetPasswordWithCode,
)
from auth import hash_password, verify_password, role_required

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["account-recovery"])

ACK_MESSAGE = "요청이 접수되었습니다. 관리자 확인 후 연락드립니다."
CODE_TTL_HOURS = 24

# 접수 남용 방어. auth.py 의 _login_failures 는 실패만 세므로 여기에 쓸 수 없다.
_submit_hits: dict[str, list[float]] = defaultdict(list)
SUBMIT_MAX_PER_WINDOW = 10
SUBMIT_WINDOW_SEC = 3600
_MAX_SUBMIT_KEYS = 10000
_last_submit_purge: float = 0.0


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _purge_submit_keys():
    global _last_submit_purge
    now = time.time()
    if now - _last_submit_purge < 60:
        return
    _last_submit_purge = now
    expired = [
        k for k, hits in _submit_hits.items()
        if not hits or now - max(hits) >= SUBMIT_WINDOW_SEC
    ]
    for k in expired:
        del _submit_hits[k]


def _check_submit_limit(request: Request):
    """성공/실패 무관하게 접수 시도를 센다. 1시간 10회."""
    _purge_submit_keys()
    if len(_submit_hits) >= _MAX_SUBMIT_KEYS:
        oldest = min(_submit_hits, key=lambda k: _submit_hits[k][-1] if _submit_hits[k] else 0)
        del _submit_hits[oldest]
    key = _client_ip(request)
    now = time.time()
    _submit_hits[key] = [t for t in _submit_hits[key] if now - t < SUBMIT_WINDOW_SEC]
    if len(_submit_hits[key]) >= SUBMIT_MAX_PER_WINDOW:
        logger.warning("Account request rate limit exceeded: %s", key)
        raise HTTPException(status_code=429, detail="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
    _submit_hits[key].append(now)


@router.post("/account-requests", response_model=AccountRequestAck,
             status_code=status.HTTP_201_CREATED)
def submit_account_request(
    payload: AccountRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _check_submit_limit(request)

    try:
        req_type = AccountRequestType(payload.request_type)
    except ValueError:
        raise HTTPException(status_code=422, detail="요청 종류가 올바르지 않습니다.")

    if req_type is AccountRequestType.reset_password and not payload.claimed_username:
        raise HTTPException(status_code=422, detail="아이디를 입력해 주세요.")
    if req_type is AccountRequestType.find_id and not payload.claimed_display_name:
        raise HTTPException(status_code=422, detail="표시 이름을 입력해 주세요.")

    # 중복 pending 이 있으면 새로 만들지 않는다. 응답은 동일하다.
    q = db.query(AccountRequest).filter(
        AccountRequest.request_type == req_type,
        AccountRequest.status == AccountRequestStatus.pending,
    )
    if req_type is AccountRequestType.reset_password:
        q = q.filter(AccountRequest.claimed_username == payload.claimed_username)
    else:
        q = q.filter(AccountRequest.claimed_display_name == payload.claimed_display_name)

    if q.first() is None:
        db.add(AccountRequest(
            request_type=req_type,
            status=AccountRequestStatus.pending,
            claimed_username=payload.claimed_username,
            claimed_display_name=payload.claimed_display_name,
            contact=payload.contact,
            note=payload.note,
        ))
        db.commit()
        logger.info("Account request submitted: type=%s ip=%s", req_type.value, _client_ip(request))

    return AccountRequestAck(message=ACK_MESSAGE)
