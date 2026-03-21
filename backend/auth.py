import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, List

import bcrypt

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole, Project, ProjectMember, ProjectRole

logger = logging.getLogger(__name__)

_ENV = os.getenv("ENV", "development")
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if _ENV == "production":
        raise RuntimeError("SECRET_KEY environment variable must be set in production")
    # 개발 환경: 프로세스마다 랜덤 키 생성 (재시작 시 기존 토큰 무효화)
    SECRET_KEY = secrets.token_urlsafe(64)
    logger.warning("SECRET_KEY not set – using random key (dev only)")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "2"))

# Cookie 설정
COOKIE_SECURE = _ENV == "production"
COOKIE_SAMESITE = "lax"
COOKIE_MAX_AGE = ACCESS_TOKEN_EXPIRE_HOURS * 3600

# Swagger UI용 (OpenAPI docs에서 Authorization 버튼 표시)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# System role hierarchy – higher index = more privileged
SYSTEM_ROLE_HIERARCHY: List[str] = ["user", "qa_manager", "admin"]

# Project role hierarchy – higher index = more privileged
PROJECT_ROLE_HIERARCHY: List[str] = ["viewer", "tester", "admin"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _extract_token(request: Request, bearer_token: Optional[str] = None) -> tuple[str, str]:
    """쿠키 또는 Authorization 헤더에서 JWT 추출. (token, source) 반환."""
    # 1) Authorization 헤더 (Swagger UI, API 클라이언트)
    if bearer_token:
        return bearer_token, "header"
    # 2) httpOnly 쿠키
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token, "cookie"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _check_csrf(request: Request, auth_source: str):
    """쿠키 인증 시 상태 변경 요청에 CSRF 검증."""
    if auth_source != "cookie":
        return  # Authorization 헤더 인증은 CSRF 면역
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    csrf_cookie = request.cookies.get("csrf_token")
    csrf_header = request.headers.get("X-CSRF-Token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=403, detail="CSRF 토큰이 유효하지 않습니다.")


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    jwt_token, auth_source = _extract_token(request, token)

    # CSRF 검증 (쿠키 인증 + 상태 변경 요청)
    _check_csrf(request, auth_source)

    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def role_required(minimum_role: str):
    """Dependency factory that enforces a minimum system role level."""
    min_index = SYSTEM_ROLE_HIERARCHY.index(minimum_role)

    def _check(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.value if isinstance(current_user.role, UserRole) else current_user.role
        user_index = SYSTEM_ROLE_HIERARCHY.index(user_role)
        if user_index < min_index:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum_role}' or higher required",
            )
        return current_user

    return _check


def get_project_role(
    project_id: int, user: User, db: Session
) -> Optional[str]:
    """사용자의 프로젝트 내 역할 반환. 접근 불가시 None."""
    user_role = user.role.value if isinstance(user.role, UserRole) else user.role

    # 시스템 admin / qa_manager는 모든 프로젝트에 admin 접근
    if user_role in ("admin", "qa_manager"):
        return "admin"

    # 프로젝트 생성자도 admin
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.created_by == user.id:
        return "admin"

    # 멤버 테이블 조회
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id,
    ).first()
    if member:
        return member.role.value if isinstance(member.role, ProjectRole) else member.role

    # 공개 프로젝트는 비멤버도 viewer 접근 허용
    if project and not project.is_private:
        return "viewer"

    return None


def check_project_access(minimum_role: str = "viewer"):
    """프로젝트 접근 권한 체크 dependency factory.

    minimum_role 값:
      - "viewer": 읽기 전용 접근 (admin/qa_manager → 전체, 멤버 → 모두, 비멤버 → 거부)
      - "tester": 테스트 수행 권한 (프로젝트 역할 tester 이상)
      - "admin": 프로젝트 관리 권한 (프로젝트 역할 admin)
    """

    def _check(
        project_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        proj_role = get_project_role(project_id, current_user, db)

        # 프로젝트에 접근 권한이 없으면 거부
        if proj_role is None:
            raise HTTPException(status_code=403, detail="이 프로젝트에 접근 권한이 없습니다.")

        # viewer(읽기)는 멤버이기만 하면 허용
        if minimum_role == "viewer":
            return current_user

        # tester/admin 권한 체크: 프로젝트 역할 계층으로 비교
        min_index = PROJECT_ROLE_HIERARCHY.index(minimum_role)
        role_index = PROJECT_ROLE_HIERARCHY.index(proj_role)
        if role_index >= min_index:
            return current_user

        raise HTTPException(status_code=403, detail="이 작업을 수행할 권한이 없습니다.")

    return _check
