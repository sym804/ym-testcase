import logging
import os
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from database import engine, Base
from routes import auth as auth_routes
from routes import projects as project_routes
from routes import testcases as testcase_routes
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
from routes import filters as filter_routes
from routes import tc_result_history as tc_result_history_routes
# Import models so Base.metadata knows about all tables
import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_roles()
    _migrate_sheet_parent_id()
    _migrate_field_config()
    _migrate_indexes()
    _purge_old_deleted_testcases()
    yield


app = FastAPI(
    title="YM TestCase API",
    description="Your Method, Your Test Case Manager",
    version="1.2.0.0",
    lifespan=lifespan,
)

# CORS – use CORS_ORIGINS env var in production (comma-separated)
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
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
app.include_router(filter_routes.router)
app.include_router(tc_result_history_routes.router)



def _migrate_roles():
    """기존 역할 값을 새 역할 체계로 마이그레이션"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        # UserRole: viewer/tester → user, editor → qa_manager
        db.execute(
            __import__("sqlalchemy").text(
                "UPDATE users SET role = 'user' WHERE role IN ('viewer', 'tester')"
            )
        )
        db.execute(
            __import__("sqlalchemy").text(
                "UPDATE users SET role = 'qa_manager' WHERE role = 'editor'"
            )
        )
        # ProjectRole: viewer → tester, editor → admin
        db.execute(
            __import__("sqlalchemy").text(
                "UPDATE project_members SET role = 'tester' WHERE role = 'viewer'"
            )
        )
        db.execute(
            __import__("sqlalchemy").text(
                "UPDATE project_members SET role = 'admin' WHERE role = 'editor'"
            )
        )
        db.commit()
    except Exception:
        logger.warning("Role migration failed (may already be migrated)", exc_info=True)
        db.rollback()
    finally:
        db.close()


def _migrate_sheet_parent_id():
    """v0.6.0 마이그레이션: 새 컬럼 추가"""
    from database import SessionLocal
    import sqlalchemy as sa
    db = SessionLocal()

    migrations = [
        "ALTER TABLE test_case_sheets ADD COLUMN parent_id INTEGER REFERENCES test_case_sheets(id) ON DELETE CASCADE",
        "ALTER TABLE test_cases ADD COLUMN custom_fields TEXT",
        "ALTER TABLE test_runs ADD COLUMN test_plan_id INTEGER REFERENCES test_plans(id) ON DELETE SET NULL",
        "ALTER TABLE test_case_sheets ADD COLUMN is_folder BOOLEAN NOT NULL DEFAULT 0",
    ]
    for sql in migrations:
        try:
            db.execute(sa.text(sql))
            db.commit()
        except Exception:
            logger.debug("Migration SQL skipped (may already exist): %s", sql[:60])
            db.rollback()

    # 기존 데이터: children이 있는 노드를 is_folder=True로 마이그레이션
    try:
        db.execute(sa.text(
            "UPDATE test_case_sheets SET is_folder = 1 "
            "WHERE id IN (SELECT DISTINCT parent_id FROM test_case_sheets WHERE parent_id IS NOT NULL)"
        ))
        db.commit()
    except Exception:
        logger.warning("is_folder migration failed", exc_info=True)
        db.rollback()

    db.close()


def _migrate_field_config():
    """v1.0.0 마이그레이션: projects 테이블에 field_config 컬럼 추가"""
    from database import SessionLocal
    import sqlalchemy as sa
    db = SessionLocal()
    try:
        result = db.execute(sa.text("PRAGMA table_info(projects)"))
        columns = [row[1] for row in result]
        if "field_config" not in columns:
            db.execute(sa.text("ALTER TABLE projects ADD COLUMN field_config TEXT"))
            db.commit()
            logger.info("Migration: added field_config column to projects")
    except Exception:
        logger.warning("field_config migration failed", exc_info=True)
        db.rollback()
    finally:
        db.close()


def _migrate_indexes():
    """v1.0.3 마이그레이션: 성능 개선을 위한 인덱스 추가"""
    from database import SessionLocal
    import sqlalchemy as sa
    db = SessionLocal()

    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_test_case_sheets_project_id ON test_case_sheets(project_id)",
        "CREATE INDEX IF NOT EXISTS ix_test_case_sheets_parent_id ON test_case_sheets(parent_id)",
        "CREATE INDEX IF NOT EXISTS ix_test_cases_project_id_deleted ON test_cases(project_id, deleted_at)",
        "CREATE INDEX IF NOT EXISTS ix_test_cases_sheet_name ON test_cases(project_id, sheet_name)",
        "CREATE INDEX IF NOT EXISTS ix_test_runs_project_id ON test_runs(project_id)",
        "CREATE INDEX IF NOT EXISTS ix_test_runs_status ON test_runs(project_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_test_results_run_id ON test_results(test_run_id)",
        "CREATE INDEX IF NOT EXISTS ix_test_results_run_result ON test_results(test_run_id, result)",
        "CREATE INDEX IF NOT EXISTS ix_test_results_case_id ON test_results(test_case_id)",
        "CREATE INDEX IF NOT EXISTS ix_project_members_project_user ON project_members(project_id, user_id)",
        "CREATE INDEX IF NOT EXISTS ix_test_case_history_tc_id ON test_case_history(test_case_id)",
    ]
    for sql in indexes:
        try:
            db.execute(sa.text(sql))
            db.commit()
        except Exception:
            db.rollback()

    db.close()


def _purge_old_deleted_testcases():
    from database import SessionLocal
    from models import TestCase, now_kst
    from datetime import timedelta
    db = SessionLocal()
    try:
        cutoff = now_kst() - timedelta(days=7)
        old = db.query(TestCase).filter(
            TestCase.deleted_at.isnot(None),
            TestCase.deleted_at < cutoff,
        ).all()
        for tc in old:
            db.delete(tc)
        if old:
            db.commit()
    finally:
        db.close()


# Mount static files directory if it exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    return {"status": "YM TestCase API running"}
