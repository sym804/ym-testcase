"""계정 복구 (아이디 찾기 / 비밀번호 재설정).

메일 발송 경로가 없어 셀프 서비스가 불가능하므로 관리자 승인 큐로 처리한다.
관리자와 사용자 사이에 오가는 것은 1회용 코드이며 비밀번호 자체는 전달되지 않는다.
"""
import logging
import secrets
import time
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from routes.auth import _check_rate_limit, _clear_failures, _record_failure

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["account-recovery"])

ACK_MESSAGE = "요청이 접수되었습니다. 관리자 확인 후 연락드립니다."
CODE_TTL_HOURS = 24

# 응답 시간으로 계정 존재 여부가 새어 나가는 것을 막기 위한 더미 해시.
# 코드 대조 단계에 도달하지 못한 실패 경로(사용자 없음, 승인 요청 없음, 만료)는
# bcrypt 를 한 번도 돌리지 않아 성공 경로보다 눈에 띄게 빨리 응답한다.
# 그래서 실패 경로마다 이 해시로 한 번씩 대조해 비용을 맞춘다.
# 결과를 쓰지 않는다고 지우면 타이밍 차이가 그대로 되살아난다.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))

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

    existing = q.first()
    if existing is None:
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
    else:
        # 행은 새로 만들지 않되 내용은 새 제출로 갱신한다. 연락처를 잘못 적어 다시 보낸
        # 경우 이전 값을 그대로 두면 관리자가 닿을 수 없는 연락처만 보게 되고,
        # 사용자는 접수되었다는 같은 응답을 받아 잘못된 것을 알 길이 없다.
        existing.contact = payload.contact
        if payload.note:
            # 빈 메모로 기존 메모를 지우지는 않는다.
            existing.note = payload.note
        db.commit()
        logger.info("Account request updated (duplicate suppressed): type=%s ip=%s",
                    req_type.value, _client_ip(request))

    # 응답은 두 경로가 완전히 같아야 한다. 다르면 접수 여부로 계정 존재가 새어 나간다.
    return AccountRequestAck(message=ACK_MESSAGE)


@router.get("/account-requests", response_model=list[AccountRequestListItem])
def list_account_requests(
    status_filter: str = Query("pending", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    try:
        st = AccountRequestStatus(status_filter)
    except ValueError:
        raise HTTPException(status_code=422, detail="상태 값이 올바르지 않습니다.")

    return (
        db.query(AccountRequest)
        .filter(AccountRequest.status == st)
        .order_by(AccountRequest.created_at.desc())
        .all()
    )


@router.post("/account-requests/{request_id}/approve", response_model=AccountRequestApproveResult)
def approve_account_request(
    request_id: int,
    payload: AccountRequestApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    req = db.query(AccountRequest).filter(AccountRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if req.status is not AccountRequestStatus.pending:
        raise HTTPException(status_code=409, detail="이미 처리된 요청입니다.")

    target = db.query(User).filter(User.id == payload.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="대상 사용자를 찾을 수 없습니다.")

    req.user_id = target.id
    req.resolved_by_id = current_user.id
    req.resolved_at = now_kst()

    if req.request_type is AccountRequestType.find_id:
        req.status = AccountRequestStatus.completed
        db.commit()
        logger.info("Find-id approved: request=%s target=%s by=%s",
                    req.id, target.username, current_user.username)
        return AccountRequestApproveResult(
            request_type=req.request_type.value, username=target.username,
        )

    code = secrets.token_urlsafe(9)
    req.code_hash = hash_password(code)
    req.code_expires_at = now_kst() + timedelta(hours=CODE_TTL_HOURS)
    req.status = AccountRequestStatus.approved
    db.commit()
    logger.info("Reset code issued: request=%s target=%s by=%s",
                req.id, target.username, current_user.username)
    return AccountRequestApproveResult(
        request_type=req.request_type.value,
        code=code,
        code_expires_at=req.code_expires_at,
    )


@router.post("/account-requests/{request_id}/reject", response_model=AccountRequestListItem)
def reject_account_request(
    request_id: int,
    payload: AccountRequestReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    req = db.query(AccountRequest).filter(AccountRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if req.status is not AccountRequestStatus.pending:
        raise HTTPException(status_code=409, detail="이미 처리된 요청입니다.")

    req.status = AccountRequestStatus.rejected
    if payload.note:
        # 사용자가 적은 메모를 관리자 사유로 덮어쓰지 않는다. 둘 다 남겨야 나중에
        # 무엇을 요청했고 왜 반려했는지를 같이 볼 수 있다. 라벨은 두 글이 섞이는
        # 경우에만 붙인다. 원래 메모가 없으면 구분할 대상이 없으므로 사유만 남긴다.
        req.note = f"{req.note}\n[반려 사유] {payload.note}" if req.note else payload.note
    req.resolved_by_id = current_user.id
    req.resolved_at = now_kst()
    db.commit()
    db.refresh(req)
    logger.info("Account request rejected: request=%s by=%s", req.id, current_user.username)
    return req


@router.post("/reset-password/verify")
def reset_password_with_code(
    payload: ResetPasswordWithCode,
    request: Request,
    db: Session = Depends(get_db),
):
    """코드로 새 비밀번호를 정한다.

    실패는 단계를 구분하지 않고 모두 같은 401 을 낸다. 어디서 틀렸는지 알려주면
    계정 존재 여부와 승인 여부가 새어 나간다. 응답 본문뿐 아니라 응답 시간도
    같아야 하므로 모든 실패 경로가 bcrypt 대조를 한 번씩 지불한다.
    """
    _check_rate_limit(request, payload.username)
    fail = HTTPException(status_code=401, detail="코드가 올바르지 않거나 만료되었습니다.")

    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        verify_password(payload.code, _DUMMY_HASH)  # 타이밍 균일화. 위 _DUMMY_HASH 주석 참고
        _record_failure(request, payload.username)
        raise fail

    approved = (
        db.query(AccountRequest)
        .filter(
            AccountRequest.user_id == user.id,
            AccountRequest.request_type == AccountRequestType.reset_password,
            AccountRequest.status == AccountRequestStatus.approved,
        )
        # 승인 시각 기준이다. 접수 순서와 승인 순서가 다를 수 있어 created_at 으로
        # 고르면 관리자가 마지막에 건네준 코드가 401 이 난다.
        .order_by(AccountRequest.resolved_at.desc(), AccountRequest.id.desc())
        .all()
    )
    req = approved[0] if approved else None
    if not req or not req.code_hash:
        verify_password(payload.code, _DUMMY_HASH)  # 타이밍 균일화
        _record_failure(request, payload.username)
        raise fail

    if req.code_expires_at is None or req.code_expires_at < now_kst():
        verify_password(payload.code, _DUMMY_HASH)  # 타이밍 균일화
        _record_failure(request, payload.username)
        raise fail

    if not verify_password(payload.code, req.code_hash):
        _record_failure(request, payload.username)
        raise fail

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    # 살아 있는 approved 요청을 전부 닫는다. 중복 억제가 pending 만 보기 때문에 한
    # 사용자가 approved 를 여러 건 들고 있을 수 있고, 쓴 한 건만 닫으면 나머지 코드가
    # 최대 24시간 동안 그대로 유효하다. 이미 메신저로 흘러간 코드가 남는다.
    resolved = now_kst()
    for other in approved:
        other.status = AccountRequestStatus.completed
        other.code_hash = None
        other.resolved_at = resolved
    db.commit()
    # 코드를 몇 번 잘못 입력했다가 성공한 사용자가 그 실패 기록 때문에 곧바로
    # 로그인에서 잠기는 것을 막는다. 로그인 성공 경로와 같은 처리다.
    _clear_failures(request, payload.username)
    logger.info("Password reset via code: user=%s request=%s retired=%s",
                user.username, req.id, len(approved))
    return {"message": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요."}
