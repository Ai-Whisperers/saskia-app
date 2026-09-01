"""app/rms/main.py — FastAPI app entry point.

Per dev plan §9 Task 1 + v2 §3 (Architecture).

Wires up:
- Engine + Session factory (app/rms/db.py)
- Logging (loguru, local only)
- Health router (already exists)
- Other routers (added in subsequent commits as they're built)
- Lifespan: init DB on startup, run backup scheduler
- Bind assertion: refuses to start if BIND_HOST != "127.0.0.1"

Entry: `uv run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765`
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.rms.config import BIND_HOST, ensure_dirs
from app.rms.db import init_db, make_engine, make_session_factory
from app.routers import (
    dashboard,
    excel_io,
    health,
    inventory,
    products,
    recipes,
    sales,
)


def _assert_bind() -> None:
    """Defensive: refuse to start if bind host is not 127.0.0.1.

    This is a single-user local app. Anything other than 127.0.0.1 would
    expose the app to the LAN. Per dev plan v2 §3 (Architecture) + AGENTS.md.
    """
    if BIND_HOST != "127.0.0.1":
        print(
            f"FATAL: BIND_HOST={BIND_HOST!r} is not allowed. "
            "This is a single-user local app. Set BIND_HOST='127.0.0.1'.",
            file=sys.stderr,
        )
        sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB + run backup scheduler on startup."""
    ensure_dirs()
    engine = make_engine()
    init_db(engine)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    # Backup scheduler (Batch 5): idempotent, no-op if R2 not configured.
    # Runs on a fresh session so it doesn't share state with request handlers.
    try:
        from app.rms.config import DB_PATH
        from app.services.backup_scheduler import run_backup

        with app.state.session_factory() as _s:
            run_backup(_s, DB_PATH)
    except Exception:
        # Don't crash the app on backup failures; the request handlers
        # are independent of this. (Errors are recorded in app_meta.)
        pass
    yield


# Build the app
app = FastAPI(
    title="Saskia RMS — Sistema de gestión local",
    description="Restaurant management system running on Saskia's PC. Single user. Local only.",
    version="2026.09.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# Mount routers
app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(inventory.router)
app.include_router(recipes.router)
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(excel_io.router)


def run() -> None:
    """Programmatic entry point (used by `uv run aiw-saskia` script entry).

    Reads BIND_HOST, PORT from config (which reads env vars). Asserts
    bind=127.0.0.1 before starting.
    """
    import uvicorn

    from app.rms.config import PORT

    _assert_bind()
    uvicorn.run(
        "app.rms.main:app",
        host=BIND_HOST,
        port=PORT,
        log_level="info",
        reload=False,  # dev: set to True for hot reload during development
    )


if __name__ == "__main__":
    # Direct entry: `python -m app.rms.main`
    run()
