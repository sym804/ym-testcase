import os
import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User, TestResult, TestRun, Attachment
from schemas import AttachmentResponse
from auth import get_current_user, get_project_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/attachments", tags=["attachments"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 보안 설정
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {
    ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    ".xlsx", ".xls", ".csv", ".doc", ".docx", ".pptx", ".zip", ".log",
}

# 다운로드 시 브라우저 렌더링 방지용 안전 MIME 타입만 허용
SAFE_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/bmp", "image/webp",
    "application/pdf", "text/plain", "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip", "application/x-zip-compressed",
}

ROLE_HIERARCHY = ["viewer", "tester", "admin"]


def _validate_extension(filename: str) -> str:
    """확장자 검증 후 소문자 확장자 반환. 확장자 없으면 거부."""
    ext = os.path.splitext(filename or "")[1].lower()
    if not ext:
        raise HTTPException(
            status_code=400,
            detail="File must have an extension",
        )
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' is not allowed",
        )
    return ext


def _safe_filepath(base_dir: str, relative_path: str) -> str:
    """Path traversal 방어: 파일 경로가 UPLOAD_DIR 내에 있는지 검증"""
    filepath = os.path.join(base_dir, relative_path)
    abs_filepath = os.path.abspath(filepath)
    abs_base = os.path.abspath(base_dir)
    if not abs_filepath.startswith(abs_base + os.sep) and abs_filepath != abs_base:
        raise HTTPException(status_code=403, detail="Access denied")
    return abs_filepath


def _get_project_id_from_test_result(test_result_id: int, db: Session) -> Optional[int]:
    """TestResult → TestRun → Project 경로로 프로젝트 ID 조회"""
    result = db.query(TestResult).filter(TestResult.id == test_result_id).first()
    if not result:
        return None
    run = db.query(TestRun).filter(TestRun.id == result.test_run_id).first()
    if not run:
        return None
    return run.project_id


def _get_project_id_from_attachment(attachment_id: int, db: Session) -> Optional[int]:
    """Attachment → TestResult → TestRun → Project 경로로 프로젝트 ID 조회"""
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att:
        return None
    return _get_project_id_from_test_result(att.test_result_id, db)


def _check_attachment_access(
    project_id: int, user: User, db: Session, minimum_role: str = "viewer"
):
    """첨부파일 접근 시 프로젝트 권한 검증"""
    from models import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    proj_role = get_project_role(project_id, user, db)

    # 비공개 프로젝트: 멤버만
    if project.is_private and proj_role is None:
        raise HTTPException(status_code=403, detail="Access denied")

    # 공개 프로젝트 조회는 인증만 되면 가능
    if not project.is_private and minimum_role == "viewer":
        return

    # 역할 체크
    min_idx = ROLE_HIERARCHY.index(minimum_role)

    if proj_role is not None:
        if ROLE_HIERARCHY.index(proj_role) >= min_idx:
            return

    # 시스템 역할 폴백
    from models import UserRole
    sys_role = user.role.value if isinstance(user.role, UserRole) else user.role
    if ROLE_HIERARCHY.index(sys_role) >= min_idx:
        return

    raise HTTPException(status_code=403, detail="Insufficient project permissions")


@router.post("/{test_result_id}", response_model=AttachmentResponse)
async def upload_attachment(
    test_result_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = db.query(TestResult).filter(TestResult.id == test_result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Test result not found")

    # 프로젝트 권한 검증
    project_id = _get_project_id_from_test_result(test_result_id, db)
    if not project_id:
        raise HTTPException(status_code=404, detail="Project not found")
    _check_attachment_access(project_id, current_user, db, "tester")

    # 확장자 검증 (확장자 없으면 거부)
    ext = _validate_extension(file.filename)

    # 파일 크기 제한
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    stored_name = f"{uuid.uuid4().hex}{ext}"
    filepath = _safe_filepath(UPLOAD_DIR, stored_name)

    with open(filepath, "wb") as f:
        f.write(content)

    logger.info(
        "File uploaded: user=%s project=%d result_id=%d filename=%s size=%d",
        current_user.username, project_id, test_result_id, file.filename, len(content),
    )

    attachment = Attachment(
        test_result_id=test_result_id,
        filename=file.filename or stored_name,
        filepath=stored_name,
        content_type=file.content_type,
        file_size=len(content),
        uploaded_by=current_user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/{test_result_id}", response_model=List[AttachmentResponse])
def list_attachments(
    test_result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 프로젝트 권한 검증
    project_id = _get_project_id_from_test_result(test_result_id, db)
    if not project_id:
        raise HTTPException(status_code=404, detail="Test result not found")
    _check_attachment_access(project_id, current_user, db, "viewer")

    return (
        db.query(Attachment)
        .filter(Attachment.test_result_id == test_result_id)
        .order_by(Attachment.uploaded_at.desc())
        .all()
    )


@router.get("/download/{attachment_id}")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # 프로젝트 권한 검증
    project_id = _get_project_id_from_attachment(attachment_id, db)
    if not project_id:
        raise HTTPException(status_code=404, detail="Project not found")
    _check_attachment_access(project_id, current_user, db, "viewer")

    # Path traversal 방어
    filepath = _safe_filepath(UPLOAD_DIR, att.filepath)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # 안전한 MIME 타입만 사용, 그 외는 octet-stream으로 강제 다운로드
    media_type = att.content_type if att.content_type in SAFE_CONTENT_TYPES else "application/octet-stream"

    return FileResponse(
        path=filepath,
        filename=att.filename,
        media_type=media_type,
    )


@router.delete("/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # 프로젝트 권한 검증
    project_id = _get_project_id_from_attachment(attachment_id, db)
    if not project_id:
        raise HTTPException(status_code=404, detail="Project not found")
    _check_attachment_access(project_id, current_user, db, "tester")

    try:
        filepath = _safe_filepath(UPLOAD_DIR, att.filepath)
        if os.path.isfile(filepath):
            os.remove(filepath)
    except HTTPException:
        pass

    db.delete(att)
    db.commit()
