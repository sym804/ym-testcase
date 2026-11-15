"""사용자별 프로젝트 순서 (SYM-228)

메인 화면 프로젝트 표와 상단 프로젝트 선택 목록이 같은 순서를 쓴다.
순서를 정하지 않은 프로젝트(새로 생겼거나 아직 옮긴 적 없는 것)가 맨 위에 만든 순서
최신순으로 오고, 그 아래에 사용자가 정한 순서가 이어진다. 새 프로젝트가 목록 맨 아래에
묻히면 만든 사람도 찾지 못한다.
"""
from sqlalchemy import and_
from sqlalchemy.orm import Query

from models import Project, ProjectOrder


def ordered(q: Query, user_id: int) -> Query:
    """Project 쿼리에 이 사용자의 순서를 붙인다."""
    return (
        q.outerjoin(ProjectOrder, and_(ProjectOrder.project_id == Project.id, ProjectOrder.user_id == user_id))
        .order_by(ProjectOrder.position.asc().nulls_first(), Project.created_at.desc(), Project.id.desc())
    )
