"""최초 관리자 승격의 경쟁 방지.

가입 라우트는 `User.count() == 0` 을 보고 관리자를 준다. 같은 순간에 두 요청이
들어오면 둘 다 0 을 보고 둘 다 관리자가 되어, 최초 관리자 한 명이라는 전제가
깨진다. 조회와 삽입 사이가 열려 있는 것이 원인이다.

판정을 삽입 뒤로 옮긴다. 자기보다 먼저 만들어진 사용자가 있으면 경쟁에서 진
쪽이므로 일반 사용자로 돌린다.

**SQLite 전제다.** SQLite 는 INSERT 가 쓰기 락을 잡아 두 번째 트랜잭션이 첫 커밋까지
기다리므로, 여기서 앞선 사용자가 보인다. PostgreSQL 의 READ COMMITTED 에서는 아직
커밋되지 않은 행이 보이지 않아 둘 다 관리자로 남을 수 있다. 그때는 `role='admin'` 에
부분 유니크 인덱스를 걸어 DB 가 판정하게 해야 한다.
"""
from sqlalchemy.orm import Session

from models import User, UserRole


def demote_if_not_first(db: Session, user: User) -> None:
    """가입 직후에만 부른다. 자기보다 앞선 사용자가 있으면 관리자를 거둔다."""
    if user.role != UserRole.admin:
        return

    earlier = (
        db.query(User.id)
        .filter(User.id < user.id)
        .first()
    )
    if earlier is not None:
        user.role = UserRole.user
