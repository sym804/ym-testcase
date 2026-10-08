# .env 로딩 - 아래 os.getenv 호출보다 먼저 실행되어야 한다
import env_setup  # noqa: F401

import logging
import os
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from routes import auth as auth_routes
from routes import projects as project_routes
from routes import testcases as testcase_routes
from routes import sheets as sheets_routes
from routes import testruns as testrun_routes
from routes import dashboard as dashboard_routes
from routes import reports as report_routes
from routes import overview as overview_routes
from routes import attachments as attachment_routes
from routes import history as history_routes
from routes import search as search_routes
from routes import members as member_routes
from routes import custom_fields as custom_fields_routes
from routes import testplans as testplan_routes
from routes import run_issues as run_issue_routes
from routes import filters as filter_routes
from routes import tc_result_history as tc_result_history_routes
from routes import account_requests as account_request_routes
from routes import api_keys as api_key_routes
from routes import uploads as upload_routes
from routes import internal as internal_routes
# Import models so Base.metadata knows about all tables
import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command
    from alembic.script import ScriptDirectory
    from database import engine
    from services.schema_version import assert_known_revision

    # script_location 은 alembic.ini 의 %(here)s 기준이라 작업 폴더와 무관하다.
    # 접속 주소는 alembic/env.py 가 환경변수에서 직접 읽는다.
    alembic_cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "alembic.ini"))

    with engine.connect() as conn:
        assert_known_revision(conn, ScriptDirectory.from_config(alembic_cfg))

    # 서버리스에서는 끈다. 실행 환경마다 동시에 돌기 때문이다. 배포 워크플로가 대신 한다.
    if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "1") == "1":
        alembic_command.upgrade(alembic_cfg, "head")

    # 로컬은 기동 때 정리한다. 서버리스는 Cron(/api/internal/cron/daily)이 한다.
    if os.getenv("RUN_MAINTENANCE_ON_STARTUP", "1") == "1":
        _purge_old_deleted_testcases()
    yield


app = FastAPI(
    title="YM TestCase API",
    description="Your Method, Your Test Case Manager",
    version="1.10.3.0",
    lifespan=lifespan,
)

# CORS - use CORS_ORIGINS env var in production (comma-separated)
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    # 교차 출처로 배포하면 브라우저가 이 헤더를 스크립트에 감춘다. 리포트 다운로드가
    # 서버가 정한 파일 이름을 읽으려면 열어 둬야 한다.
    expose_headers=["Content-Disposition"],
)

# ── Security headers middleware ──────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    if os.getenv("ENV") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Global exception handler ─────────────────────────────────────────────────
# TC ID 중복은 사용자가 그리드에서 흔히 만드는 상황이다. 500 으로 떨어지면
# 자동 저장이 "저장 실패"만 띄워 이유를 알 수 없으므로 409 로 갈라 준다.
_TC_ID_INDEX = "uq_test_cases_project_tc_id"


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    detail = str(getattr(exc, "orig", exc))
    if _TC_ID_INDEX in detail:
        logger.info("TC ID 중복 거절: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=409,
            content={"detail": "이미 쓰이는 TC ID입니다. 다른 값으로 변경해 주세요."},
        )
    logger.error("Integrity error on %s %s: %s", request.method, request.url.path, detail)
    return JSONResponse(status_code=409, content={"detail": "데이터 제약 조건에 걸렸습니다."})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include routers
app.include_router(auth_routes.router)
app.include_router(project_routes.router)
app.include_router(testcase_routes.router)
app.include_router(sheets_routes.router)
app.include_router(testrun_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(report_routes.router)
app.include_router(overview_routes.router)
app.include_router(attachment_routes.router)
app.include_router(history_routes.router)
app.include_router(search_routes.router)
app.include_router(member_routes.router)
app.include_router(member_routes.assign_all_router)
app.include_router(custom_fields_routes.router)
app.include_router(testplan_routes.router)
app.include_router(run_issue_routes.router)
app.include_router(filter_routes.router)
app.include_router(tc_result_history_routes.router)
app.include_router(account_request_routes.router)
app.include_router(api_key_routes.router)
app.include_router(upload_routes.router)
app.include_router(internal_routes.router)



def _purge_old_deleted_testcases():
    """기한이 지난 소프트 삭제 TC 정리. 실제 판정은 purge_service 가 한다."""
    from database import SessionLocal
    from services.purge_service import purge_deleted_testcases

    db = SessionLocal()
    try:
        purge_deleted_testcases(db)
    finally:
        db.close()


# Mount static files directory if it exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    return {"status": "YM TestCase API running"}
