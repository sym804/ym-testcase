import logging
import os
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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
from routes import filters as filter_routes
from routes import tc_result_history as tc_result_history_routes
# Import models so Base.metadata knows about all tables
import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run Alembic migrations
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command

    alembic_cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        os.getenv("DATABASE_URL", "sqlite:///./tc_manager.db"),
    )
    alembic_command.upgrade(alembic_cfg, "head")

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
app.include_router(filter_routes.router)
app.include_router(tc_result_history_routes.router)



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
