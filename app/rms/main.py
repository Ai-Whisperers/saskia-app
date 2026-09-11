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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles as _StaticFiles  # noqa: F401  (re-exported for tests)
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from app.auth import SESSION_SECRET
from app.rms.config import BIND_HOST, ensure_dirs
from app.rms.csrf import csrf_cookie_middleware
from app.rms.db import make_session_factory
from app.rms.db_dialect import _is_postgres, get_database_url, get_metadata
from app.rms.db_dialect import make_engine as make_engine_dialect
from app.rms.security_headers import SecurityHeadersMiddleware
from app.rms.session_lifecycle import SessionLifecycleMiddleware
from app.routers import (
    auditoria,
    auth,
    customers,
    dashboard,
    eod,
    excel_io,
    health,
    help,
    inventory,
    merma,
    ops,
    produccion,
    products,
    recipes,
    reorder,
    reportes,
    sales,
    settings,
)


def _configure_logging() -> None:
    """Configure loguru at import time.

    - In production (AIW_SASKIA_LOG_FORMAT=prod): JSON to stderr so
      Render's log viewer / log aggregators can parse line-by-line.
    - In dev (default): human-readable, color-coded.

    Called once at module import. Idempotent on subsequent calls
    (logger.remove() removes all default sinks).
    """
    fmt = os.getenv("AIW_SASKIA_LOG_FORMAT", "dev").lower()
    logger.remove()  # remove default sink so we don't double-log
    if fmt == "prod":
        logger.add(
            sys.stderr,
            level="INFO",
            serialize=True,
            backtrace=False,
            diagnose=False,
            format="{message}",
        )
    else:
        logger.add(
            sys.stderr,
            level="DEBUG",
            backtrace=True,
            diagnose=False,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <7}</level> | {message}"
            ),
        )


_configure_logging()


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
    """Initialize DB + run backup scheduler on startup.

    Also wires up Sentry error tracking if SENTRY_DSN env var is set.
    No-op when SENTRY_DSN is unset — keeps the dependency optional in dev.
    """
    # Sentry — gated by env var. Free tier 5K events/mo at sentry.io.
    # We add sentry_sdk to deps but never require it to be initialized;
    # if the env var is missing, this block is skipped.
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[FastApiIntegration(), SqlalchemyIntegration()],
                traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
                # Don't capture PII by default. Saskia's data is sensitive.
                send_default_pii=False,
                environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
                release=app.version,
            )
        except Exception as exc:  # noqa: BLE001 — Sentry init must never crash the app
            print(f"WARNING: Sentry init failed: {exc}", file=sys.stderr)

    ensure_dirs()
    url = get_database_url()
    engine = make_engine_dialect(url)
    # Pick the right metadata for the dialect
    metadata = get_metadata()
    # create_all is dialect-aware via SQLAlchemy; works for both
    metadata.create_all(engine)

    # Migration bootstrap. Always-run by default — migrations are idempotent
    # (each adds columns / INSERT/UPDATEs that no-op when not needed).
    #
    # Set AIW_SASKIA_RUN_MIGRATIONS=0 only if you specifically need to
    # pause migration application (e.g. during a maintenance window).
    #
    # History: previously this was gated behind a "1" flag, which left
    # the production DB out of sync with the code (the 2026-09-08 outage
    # where sale.payment_method didn't exist on Neon). Auto-running is
    # safer than opt-in.
    if os.getenv("AIW_SASKIA_RUN_MIGRATIONS", "1") != "0":
        try:
            from app.rms.db import init_db
            init_db(engine)
            print("MIGRATIONS: applied (idempotent, no-op if already current)", file=sys.stderr)
        except Exception as exc:
            # Migrations must never crash the app. Log and continue.
            print(f"MIGRATIONS: failed to apply: {exc!r}", file=sys.stderr)
            logger.exception("migration apply failed on startup")

    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.is_postgres = _is_postgres(url)
    app.state.ready = True  # Readiness flag for /healthz gating

    # Eager-init Supabase client on startup (when configured). The supabase-py
    # SDK takes 1-3 seconds to construct (creates an internal httpx client +
    # connection pool). Doing it here means /login POST doesn't pay the
    # initialization cost on the FIRST request after cold-start.
    # Per docs/operations/2026-09-09-performance-analysis.md improvement #3
    # + performance-research.md section 3 (Supabase Python SDK).
    try:
        from app.auth import using_supabase
        if using_supabase():
            from app.auth_supabase import get_supabase_client
            get_supabase_client()
            logger.info("supabase client pre-warmed")
    except Exception as exc:
        logger.warning(f"supabase pre-warm failed (non-fatal): {exc!r}")

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

class StaticCacheMiddleware(BaseHTTPMiddleware):
    """Add Cache-Control: max-age=3600 to /static/* responses.

    CSS/JS/image assets change only on deploys. Browser revalidation on
    every page load wastes RTT. 1-hour cache balances freshness with
    performance.

    Not applied to other paths — those have session-aware content.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "max-age=3600, public"
        return response


# GZip compression: ~70% bandwidth reduction on all HTML/CSS/JS responses.
# minimum_size=500 avoids compressing tiny responses (overhead > savings).
# Registered LAST so it runs INNERMOST (closest to the route handler) and
# wraps every response body before the other middlewares see it.
app.add_middleware(GZipMiddleware, minimum_size=500)

# Cache headers for /static/*. Browser revalidation is wasteful for assets
# that change only on deploys.
app.add_middleware(StaticCacheMiddleware)


class HealthCacheMiddleware(BaseHTTPMiddleware):
    """Add short Cache-Control to /healthz* responses.

    Health endpoints are idempotent and change infrequently. A 10-second
    edge cache lets Cloudflare absorb UptimeRobot ping storms (every 5 min)
    + the operator's manual probes without hitting the app on every check.

    Per docs/operations/2026-09-09-performance-analysis.md improvement #5
    + performance-research.md section 5 (Cloudflare caching).
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/healthz"):
            # s-maxage is for shared caches (Cloudflare); max-age is for browsers.
            # 10s strikes the balance between freshness and edge-cache hit rate.
            response.headers["Cache-Control"] = "public, max-age=10, s-maxage=10"
        return response


app.add_middleware(HealthCacheMiddleware)

# Security headers middleware: defense-in-depth HTTP response headers
# (X-Frame-Options, CSP, HSTS, etc.). Registered BEFORE SessionMiddleware
# so it runs OUTERMOST and its headers are guaranteed on every response.
app.add_middleware(SecurityHeadersMiddleware)

# Detect session leaks: warns + closes any Session opened during a
# request that wasn't closed by the handler. Defense in depth against
# future code that forgets to use `Depends(get_session)`.
app.add_middleware(SessionLifecycleMiddleware)

# CSRF protection: signed double-submit cookie.
# Set on every GET response to non-exempt paths; required on every POST.
app.middleware("http")(csrf_cookie_middleware)

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
    # Use ReadyStaticFiles to gate on app.state.ready — without this, the
    # browser fetches /static/app.css during Render cold-start (5-30s) and
    # gets broken CSS. With the gate, the browser sees a clean 503 that
    # triggers a natural retry once the app is ready.
    from app.rms.ready_static import ReadyStaticFiles
    app.mount("/static", ReadyStaticFiles(directory=_static_dir), name="static")


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
app.include_router(customers.router)
app.include_router(produccion.router)
app.include_router(eod.router)
app.include_router(merma.router)
app.include_router(reportes.router)
app.include_router(auditoria.router)
app.include_router(ops.router)
app.include_router(settings.router)
app.include_router(reorder.router)
app.include_router(help.router)


def _request_id() -> str:
    """Generate a short request id for log correlation."""
    import uuid

    return uuid.uuid4().hex[:12]


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Global 500 handler: log + structured JSON response.

    Without this, FastAPI returns a generic HTML 500 with no info. The
    operator sees only "Internal Server Error" and can't diagnose.

    Now: logs exception to stderr (loguru) with request context, returns
    JSON {error, type, request_id} so frontend can show the id in a
    "report this issue" hint.

    HTTPException is a control-flow exception raised by FastAPI itself
    for intentional 4xx/5xx responses (e.g. 401 auth, 403 CSRF, 405, etc).
    Return its proper status code + detail verbatim — but emit a
    consistent JSON shape so clients can parse it.
    """
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        # Re-emit as JSON with the original status_code + detail.
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail if exc.detail is not None else "http_error",
                "type": exc.__class__.__name__,
                "status": exc.status_code,
            },
            headers=exc.headers,
        )

    rid = _request_id()
    logger.exception(
        "unhandled error request_id={} method={} path={}: {!r}",
        rid,
        request.method,
        request.url.path,
        exc,
    )
    # Best-effort audit log row so operators can see error counts per hour
    # via /auditoria. Failures here MUST NOT bubble up — we're already
    # handling an exception. Use a fresh session since the request's
    # may be torn down or in an error state.
    try:
        from app.rms.audit import record
        with request.app.state.session_factory() as _s:
            record(
                _s,
                user_id=None,
                action="http.500",
                target_type="http_error",
                target_id=rid,
                detail={
                    "method": request.method,
                    "path": request.url.path,
                    "type": exc.__class__.__name__,
                    "msg": str(exc)[:500],
                },
            )
            _s.commit()
    except Exception:
        logger.warning("audit.record for http.500 failed (non-fatal)")

    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc) or exc.__class__.__name__,
            "type": exc.__class__.__name__,
            "request_id": rid,
            "hint": "Pass the request_id to the operator for diagnosis.",
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    """JSON 404 instead of HTML — consistency with 500."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "path": request.url.path,
        },
    )


@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    """Per-request access log (skips /static/* and /healthz noise)."""
    import time

    if not request.url.path.startswith(("/static/", "/healthz")):
        start = time.perf_counter()
        rid = _request_id()
        request.state.request_id = rid
        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "request_id={} method={} path={} CRASHED",
                rid, request.method, request.url.path,
            )
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request_id={} method={} path={} status={} elapsed_ms={:.0f}",
            rid, request.method, request.url.path,
            response.status_code, elapsed_ms,
        )
        response.headers["X-Request-Id"] = rid
        return response
    return await call_next(request)


def migrate() -> None:
    """Schema migration entry point. Idempotent.

    Usage:
        uv run aiw-saskia migrate            # uses DATABASE_URL or AIW_SASKIA_DB_PATH
        DATABASE_URL=postgres://... uv run aiw-saskia migrate
    """
    import sys

    from sqlalchemy import inspect

    from app.rms.db import CURRENT_SCHEMA_VERSION, _current_schema_version, init_db
    from app.rms.db_dialect import make_engine

    raw = os.environ.get("DATABASE_URL")
    if not raw:
        local_db = os.environ.get("AIW_SASKIA_DB_PATH")
        if local_db:
            raw = f"sqlite:///{local_db}"
        else:
            print(
                "ERROR: DATABASE_URL (or AIW_SASKIA_DB_PATH) not set. "
                "Cannot determine which DB to migrate.",
                file=sys.stderr,
            )
            sys.exit(1)

    engine = make_engine(raw)
    print(f"engine driver: {engine.url.drivername}")
    try:
        with engine.connect() as conn:
            before = _current_schema_version(conn)
    except Exception:
        before = 0

    if before == CURRENT_SCHEMA_VERSION:
        print(f"schema_version already at {CURRENT_SCHEMA_VERSION} (no-op)")
        insp = inspect(engine)
        schema = "public" if engine.dialect.name == "postgresql" else None
        for t in sorted(insp.get_table_names(schema=schema)):
            print(f"  - {t}")
        return

    print(f"schema_version: {before} -> {CURRENT_SCHEMA_VERSION}")
    init_db(engine)
    print(f"schema applied at version {CURRENT_SCHEMA_VERSION}")


def _serve() -> None:
    """Start uvicorn. Internal helper — do not call directly; use run()."""
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


def run() -> None:
    """Programmatic entry point (used by `uv run aiw-saskia` script entry).

    Dispatches based on sys.argv:
      - `aiw-saskia migrate`   -> apply schema migrations (idempotent)
      - `aiw-saskia serve`     -> start uvicorn (default; backward compatible)
      - (no argv)              -> start uvicorn (backward compatible)

    Reads BIND_HOST, PORT from config (which reads env vars). Asserts
    bind is allowed before starting.
    """
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "migrate":
        migrate()
        return
    if argv and argv[0] in ("seed", "demo"):
        _seed()
        return
    if argv and argv[0] in ("serve", "run", "start"):
        _serve()
        return
    # Default: serve (backward compat with pre-argv-dispatch entry)
    _serve()


def _seed() -> None:
    """Insert realistic demo data. Idempotent; --reset wipes seeded rows first.

    Usage:
        uv run aiw-saskia seed                  # additive (skip existing)
        uv run aiw-saskia seed --reset          # destructive: wipe + reseed
    """
    import sys

    from app.rms.db import make_session_factory
    from app.rms.db_dialect import make_engine
    from app.rms.seed import SeedReport, seed_demo_data

    overwrite = "--reset" in sys.argv

    raw = os.environ.get("DATABASE_URL")
    if not raw:
        local_db = os.environ.get("AIW_SASKIA_DB_PATH")
        if local_db:
            raw = f"sqlite:///{local_db}"
        else:
            print(
                "ERROR: DATABASE_URL (or AIW_SASKIA_DB_PATH) not set. "
                "Cannot determine which DB to seed.",
                file=sys.stderr,
            )
            sys.exit(1)

    engine = make_engine(raw)
    SessionLocal = make_session_factory(engine)
    session = SessionLocal()
    try:
        report: SeedReport = seed_demo_data(session, overwrite=overwrite)
        print(f"seed complete: {report.as_dict()}")
    finally:
        session.close()


if __name__ == "__main__":
    # Direct entry: `python -m app.rms.main`
    run()
