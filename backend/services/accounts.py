"""계정 변경 공통 도구. 생성, 연결, 승인, 중지, 역할 변경, 비밀번호 변경·초기화·복구는 모두
lock_accounts 안에서 한다. 잡는 순서는 횟수 제한 키(있으면) -> 계정 잠금 -> 사용자 행 -> API 키 행이다.

★행 잠금만으로는 부족하다. 관리자 둘이 서로를 동시에 중지하면 서로 다른 행을 잠가 둘 다
  '활성 관리자 2명' 을 보고 통과한다. 전역 잠금 하나로 줄 세우고 그 안에서 센다.
"""
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from auth import revoke_user_api_keys
from models import User, UserRole, UserStatus
from services.account_policy import normalize_identifier
from services.locks import LockNs, advisory_xact_lock


def lock_accounts(db: Session) -> None:
    advisory_xact_lock(db, LockNs.ACCOUNTS)


def find_user_by_identifier(db: Session, raw: str) -> Optional[User]:
    ident = normalize_identifier(raw)
    if not ident:
        return None
    if "@" in ident:
        user = db.query(User).filter(User.email == ident).first()
        if user:
            return user
    return db.query(User).filter(User.username == ident).first()


def active_admin_count(db: Session, exclude_id: Optional[int] = None) -> int:
    q = db.query(func.count(User.id)).filter(User.role == UserRole.admin, User.status == UserStatus.active)
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.scalar() or 0


def email_taken(db: Session, email: str, exclude_id: Optional[int] = None) -> bool:
    q = db.query(User.id).filter(or_(User.email == email, User.username == email))
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.first() is not None


def google_username(db: Session, email: str) -> str:
    """Google 신규 계정의 아이디. 같은 문자열의 아이디가 있으면 #숫자로 비켜 만든다."""
    base = email[:95]
    if not db.query(User.id).filter(User.username == base).first():
        return base
    n = 2
    while db.query(User.id).filter(User.username == f"{base}#{n}").first():
        n += 1
    return f"{base}#{n}"


def disable(db: Session, user: User) -> None:
    user.status = UserStatus.disabled
    user.token_version = (user.token_version or 0) + 1
    revoke_user_api_keys(user.id, db)
