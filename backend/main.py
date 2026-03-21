import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Import models so Base.metadata knows about all tables
import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_roles()
    _migrate_sheet_parent_id()
    _purge_old_deleted_testcases()
    yield


app = FastAPI(
    title="TC Manager API",
    description="Test Case Manager Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS – use CORS_ORIGINS env var in production (comma-separated)
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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
    ]
    for sql in migrations:
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
    return {"status": "TC Manager API running"}
