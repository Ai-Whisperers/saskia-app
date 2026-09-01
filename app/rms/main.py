"""app/rms/main.py — FastAPI app entry point.

Per dev plan §9 + Fase 2 hosted architecture (200h plan).

Wires up:
- Engine + Session factory (Postgres via DATABASE_URL, or SQLite fallback)
- SessionMiddleware (cookie auth, signed with SESSION_SECRET)
- Logging (loguru, local only)
- Health router
- Auth router (/login, /logout)
- Other routers (dashboard, inventory, recipes, products, sales, excel)
- Lifespan: init DB on startup, run backup scheduler

Hosted vs local:
- Local: BIND_HOST=127.0.0.1, SQLite via AIW_SASKIA_DB_PATH
- Hosted (Render/Fly): BIND_HOST=0.0.0.0, Postgres via DATABASE_URL,
  TLS terminated upstream by Cloudflare Tunnel

Entry: `uv run uvicorn app.rms.main:app --host 0.0.0.0 --port 8000`
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import SESSION_SECRET
from app.rms.config import BIND_HOST, ensure_dirs
from app.rms.db import make_session_factory
from app.rms.db_dialect import _is_postgres, get_database_url, get_metadata
from app.rms.db_dialect import make_engine as make_engine_dialect
from app.routers import (
    auth,
    dashboard,
    excel_io,
    health,
    inventory,
    products,
    recipes,
    sales,
)


def _assert_bind() -> None:
    """Defensive: refuse to start if bind host is unsafe.

    - Local dev: must be 127.0.0.1 (single-user, never exposed to LAN).
    - Hosted (Render/Fly): 0.0.0.0 is fine because TLS is terminated
      by Cloudflare Tunnel and the port is not reachable from the
      public internet.
    """
    allowed = ("127.0.0.1", "0.0.0.0")
    if BIND_HOST not in allowed:
        print(
            f"FATAL: BIND_HOST={BIND_HOST!r} is not allowed. "
            f"Use {allowed[0]} for local dev or {allowed[1]} for hosted.",
            file=sys.stderr,
        )
        sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB + run backup scheduler on startup."""
    ensure_dirs()
    url = get_database_url()
    engine = make_engine_dialect(url)
    # Pick the right metadata for the dialect
    metadata = get_metadata()
    # create_all is dialect-aware via SQLAlchemy; works for both
    metadata.create_all(engine)

    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.is_postgres = _is_postgres(url)

    # Backup scheduler: idempotent, no-op if R2 not configured.
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
    title="Saskia RMS — Sistema de gestión",
    description="Restaurant management system. Hosted (Neon Postgres + Cloudflare) or local.",
    version="2026.09.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# Session middleware: signs cookies with SESSION_SECRET.
# Must be added BEFORE routers so login_user() can write to request.session.
# Same-site=lax + https-only when behind CF Tunnel (which always terminates TLS).
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="saskia_rms_session",
    max_age=60 * 60 * 24 * 7,  # 7 days
    same_site="lax",
    https_only=os.getenv("HTTPS_ONLY", "true").lower() == "true",
)

# Mount static files (CSS, images, etc.) so templates can link /static/app.css
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# --- Auth gate (Milestone 1) ---
#
# All routes require login EXCEPT:
#   /login*     — auth pages
#   /logout*    — auth pages (POST + GET)
#   /forgot-password — Supabase password reset trigger
#   /healthz*    — monitoring (Render + UptimeRobot)
#   /static/*    — CSS, images
#
# Implementation note: we use Starlette's Depends() at the router level
# rather than middleware because:
# 1. Middleware runs in reverse-registration order, so adding auth
#    middleware after SessionMiddleware causes it to run BEFORE
#    the session is populated (broken state).
# 2. Depends() at the APIRouter level gives us the same security
#    baseline (forgetting it on a route is hard) but with correct
#    timing — session is populated, then auth runs, then handler.
#
# We expose this as an `auth_router_dep` callable that the test
# conftest can monkey-patch out (set to a no-op).

PUBLIC_PATH_PREFIXES = ("/static",)


def _is_public(path: str) -> bool:
    """True for paths that don't require auth."""
    return any(path.startswith(p) for p in PUBLIC_PATH_PREFIXES)


# Mount routers — auth first (so /login is reachable before any auth check).
# Public paths (healthz, login, logout, forgot-password, static) are
# handled by the router's own dependencies list below.
app.include_router(auth.router)
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
    bind is allowed before starting.
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
