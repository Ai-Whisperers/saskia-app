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
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles as _StaticFiles  # noqa: F401  (re-exported for tests)
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from app.auth import SESSION_SECRET
from app.rms.config import BIND_HOST, CURRENT_SCHEMA_VERSION, ensure_dirs
from app.rms.csrf import csrf_cookie_middleware
from app.rms.db import make_session_factory
from app.rms.db_dialect import _is_postgres, get_database_url, get_metadata
from app.rms.db_dialect import make_engine as make_engine_dialect
from app.rms.observability import RequestContextMiddleware
from app.rms.security_headers import SecurityHeadersMiddleware
from app.rms.session_lifecycle import SessionLifecycleMiddleware
from app.routers import (
    insights_derived,
    insights_stock,
    auditoria,
    auth,
    customers,
    dashboard,
    eod,
    excel_io,
    health,
    help,
    herebus,
    inventory,
    merma,
    ops,
    pedidos,
    produccion,
    products,
    recipes,
    reorder,
    reportes,
    sales,
    search,
    settings,
    settings_runtime,
    shopping,
    suppliers,
    users,
)
from app.services.template_render import templates


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
            format=("<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}"),
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
            from app.rms.db import init_db, schema_version

            init_db(engine)
            with engine.connect() as conn:
                post = schema_version(conn)
            print(
                f"MIGRATIONS: applied (schema_version={post}, code={CURRENT_SCHEMA_VERSION})",
                file=sys.stderr,
            )
            app.state.migration_status = "ok"
            app.state.migration_error = None
            app.state.migration_schema_version = post
        except Exception as exc:
            # Migrations must never crash the app. Log and continue.
            print(f"MIGRATIONS: failed to apply: {exc!r}", file=sys.stderr)
            logger.exception("migration apply failed on startup")
            # Store error state so /healthz/migrate can surface it.
            try:
                from app.rms.db import schema_version as _sv
                with engine.connect() as conn:
                    pre = _sv(conn)
            except Exception:
                pre = None
            app.state.migration_status = "failed"
            app.state.migration_error = repr(exc)
            app.state.migration_schema_version = pre

    # Phase 1.A — Idempotent password sync from env vars (SASKIA_ADMIN_PASSWORD,
    # SASKIA_USER_PASSWORD, SASKIA_IVAN_TEST_PASSWORD). When the deployment injects
    # a fresh password via docker-compose / Render env, this aligns the bcrypt
    # hash on boot. No-op when env vars are unset (local dev).
    try:
        from app.rms.bootstrap import run_password_sync
        from app.rms.db import make_session_factory as _make_session
        with _make_session(engine)() as _bs:
            run_password_sync(_bs)
    except Exception:
        logger.exception("password bootstrap failed (non-fatal)")

    # Phase 1.C — Apply HACCP defaults to ingredients that have a known
    # category but no temperature/humidity/water-activity values yet.
    # Idempotent: skips rows that are already populated.
    try:
        from app.rms.haccp_seed import apply_haccp_defaults
        with _make_session(engine)() as _bs:
            n = apply_haccp_defaults(_bs)
            if n:
                logger.info("haccp: applied defaults to %d ingredients", n)
    except Exception:
        logger.exception("haccp seed failed (non-fatal)")

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
    except Exception as exc:
        # Don't crash the app on backup failures; the request handlers
        # are independent of this. (Errors are recorded in app_meta.)
        logger.warning(f"backup scheduler failed: {exc!r}")
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
    """Add Cache-Control: max-age=1year, immutable to /static/* responses.

    Assets behind /static/* are version-busted via the ?v= query parameter
    (e.g. app.css?v=1790018202). When the server deploys a new version,
    the v= value changes, producing a new URL — the old URL is never
    re-requested. Therefore these responses can be cached "forever" in
    both browser and CDN with the immutable directive, which suppresses
    all conditional revalidation (If-Modified-Since, ETag) for maximum
    perf.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "max-age=31536000, immutable"
        return response


# GZip compression: ~70% bandwidth reduction on all HTML/CSS/JS responses.
# minimum_size=500 avoids compressing tiny responses (overhead > savings).
# Registered LAST so it runs INNERMOST (closest to the route handler) and
# wraps every response body before the other middlewares see it. This
# ordering also keeps GZip's body-size check working correctly — our
# RequestContext middleware (registered earlier = outer) just attaches
# X-Request-Id without reading the body.
app.add_middleware(GZipMiddleware, minimum_size=500)

# Request context middleware: attaches request_id, user_id, method, path
# to every loguru emission via logger.contextualize. Registered FIRST so
# even the other middlewares' logs are tagged. The original ordering
# (GZip before RequestContext) worked but caused GZip to apply to all
# responses including tiny ones because the body-size check ran AFTER
# our access-log timing read. Re-registered GZip AFTER RequestContext
# below so GZip is the INNERMOST middleware (closest to the route).
app.add_middleware(RequestContextMiddleware)

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
    # Mount uploaded product images at /static/uploads/ — written by
    # /productos/upload-image (see routers/products.py). The directory is
    # created on demand inside the upload route, so no need to mkdir here.
    uploads_dir = os.path.join(_static_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/static/uploads", ReadyStaticFiles(directory=uploads_dir), name="uploads")

    # Browsers auto-request /favicon.ico and /favicon.svg at the root (not
    # under /static/). Without these, the browser logs a 404 and falls back
    # to its built-in icon, which is ugly and shows up as a console error.
    # Alias the same files so both /static/favicon.* and /favicon.* work.
    # Bypasses ReadyStaticFiles (intentional — favicon must work during
    # cold-start so the browser's initial request succeeds).
    @app.get("/favicon.svg", include_in_schema=False)
    def _favicon_svg() -> FileResponse:
        return FileResponse(
            os.path.join(_static_dir, "favicon.svg"),
            media_type="image/svg+xml",
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def _favicon_ico() -> FileResponse:
        return FileResponse(
            os.path.join(_static_dir, "favicon.ico"),
            media_type="image/x-icon",
        )


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
app.include_router(suppliers.router)
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(search.router)
app.include_router(excel_io.router)
app.include_router(customers.router)
app.include_router(produccion.router)
app.include_router(eod.router)
app.include_router(merma.router)
app.include_router(reportes.router)

# HEREBUS Drive integration modules
app.include_router(herebus.wishlist_router)
app.include_router(herebus.risks_router)
app.include_router(herebus.pricing_router)
app.include_router(herebus.bank_router)
app.include_router(herebus.benchmarks_router)
app.include_router(herebus.dashboard_router)
app.include_router(insights_derived.router)
app.include_router(insights_stock.router)
app.include_router(herebus.planner_router)
app.include_router(herebus.delivery_router)
app.include_router(shopping.router)
# NAV-02: Auditoría and Ops are internal-only. The product surface does
# not include them (Saskia does not run audits). In production they
# 404; in tests / dev they are still mounted so the test suite can
# exercise them.
#
# Default behaviour (no env var): NOT mounted (production).
# Set AIW_SASKIA_INTERNAL_ROUTES=1 to mount (tests, internal admin).
# This env var must be set BEFORE app.rms.main is imported.
if os.getenv("AIW_SASKIA_INTERNAL_ROUTES") == "1":
    app.include_router(auditoria.router)
    app.include_router(ops.router)
app.include_router(settings.router)
app.include_router(settings_runtime.router)


# Spanish-language alias: /proveedores → /suppliers
# Operators see "proveedores" in UI copy. Accepting both URLs means
# external links/bookmarks work regardless of which word was used.
@app.get("/proveedores", include_in_schema=False)
def proveedores_alias():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/suppliers", status_code=303)
app.include_router(users.router)
app.include_router(reorder.router)
app.include_router(help.router)
app.include_router(pedidos.public_router)
app.include_router(pedidos.router)


def _request_id() -> str:
    """Generate a short request id for log correlation."""
    import uuid

    return uuid.uuid4().hex[:12]


def _wants_html(request: Request) -> bool:
    """True if the client likely expects HTML over JSON.

    Used by error handlers to serve friendly HTML pages to browsers
    while preserving JSON shape for API/curl clients.
    """
    accept = (request.headers.get("accept") or "").lower()
    # Browsers send text/html. API clients (curl, fetch from JS) send application/json
    # or */*. If html is explicitly preferred OR no JSON preference is set, return HTML.
    return "text/html" in accept and "application/json" not in accept.split(";")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Spanish 422 errors so /ventas/nueva etc. don't show English defaults.

    Translates the standard FastAPI 422 (English "Field required", "value is not a valid integer")
    into a Spanish message that says which field is wrong and what to enter.
    """
    errors = exc.errors()
    parts: list[str] = []
    for err in errors[:3]:  # at most 3 errors per response
        loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path", "form")]
        field = loc[-1] if loc else "campo"
        etype = err.get("type", "")
        msg_en = err.get("msg", "")
        # Translate the most common FastAPI validation types
        if etype == "missing":
            parts.append(f"{field} es obligatorio")
        elif etype in ("greater_than", "greater_than_equal"):
            limit = err.get("ctx", {}).get("ge") or err.get("ctx", {}).get("gt")
            parts.append(f"{field} debe ser ≥ {limit}" if etype == "greater_than_equal" else f"{field} debe ser > {limit}")
        elif etype in ("less_than", "less_than_equal"):
            limit = err.get("ctx", {}).get("le") or err.get("ctx", {}).get("lt")
            parts.append(f"{field} debe ser ≤ {limit}" if etype == "less_than_equal" else f"{field} debe ser < {limit}")
        elif etype in ("int_parsing", "type_error.integer"):
            parts.append(f"{field} debe ser un número entero")
        elif etype in ("float_parsing", "type_error.float"):
            parts.append(f"{field} debe ser un número")
        elif etype == "value_error":
            parts.append(f"{field}: {msg_en}")
        else:
            parts.append(f"{field} inválido")
    detail = "; ".join(parts) if parts else "Datos inválidos"
    return JSONResponse(
        status_code=400,  # BUG-00: 400 is more accurate than 422 for client-side form errors
        content={"detail": detail, "fields": [loc[-1] if loc else "campo" for loc in [
            [str(x) for x in e.get("loc", []) if x not in ("body", "query", "path", "form")]
            for e in errors
        ]]},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Global exception handler.

    Order of dispatch:
      1. AppError (our hierarchy): mapped to status_code + structured detail.
         Use `raise NotFound("pedido", id=42)` in a router and the
         global handler renders the right status + JSON.
      2. HTTPException: FastAPI's intentional 4xx/5xx (CSRF 403, auth 401, etc).
         Pass-through with our extended payload.
      3. Anything else: 500 handler. HTML for browsers, JSON for clients.
         Always logs full traceback; never leaks internal text to the user.
    """
    from app.rms.errors import AppError
    from fastapi import HTTPException

    rid = getattr(request.state, "request_id", None) or _request_id()

    # ─── 1. AppError (typed errors from our hierarchy) ─────────────
    if isinstance(exc, AppError):
        logger.warning(
            "app_error request_id={} type={} reason={} msg={} context={!r}",
            rid, exc.__class__.__name__, exc.reason_code,
            exc.message, exc.context,
        )
        # AppErrors are NOT 500s unless explicitly typed as such. The
        # whole point of the hierarchy is that business errors don't
        # pollute the "internal server error" bucket.
        payload = exc.to_dict()
        payload["request_id"] = rid
        if _wants_html(request) and exc.status_code in (404,):
            from app.services.template_render import render as _render
            return _render(
                request, "errors/404.html",
                {"path": request.url.path, "reason": exc.reason_code},
                status_code=404,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
            headers={"X-Reason-Code": exc.reason_code},
        )

    # ─── 2. HTTPException (FastAPI control-flow) ───────────────────
    if isinstance(exc, HTTPException):
        logger.info(
            "http_exception request_id={} status={} detail={!r}",
            rid, exc.status_code, exc.detail,
        )
        if _wants_html(request) and exc.status_code == 404:
            from app.services.template_render import render as _render
            return _render(
                request, "errors/404.html",
                {"path": request.url.path},
                status_code=404,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail if exc.detail is not None else "http_error",
                "type": exc.__class__.__name__,
                "status": exc.status_code,
                "request_id": rid,
            },
            headers=exc.headers,
        )

    # ─── 3. Unhandled: genuine 500 ─────────────────────────────────
    logger.exception(
        "unhandled error request_id={} method={} path={}: {!r}",
        rid, request.method, request.url.path, exc,
    )
    # Best-effort audit log row so operators can see error counts per hour.
    # Failures here MUST NOT bubble up — use a fresh session.
    try:
        from app.rms.audit import record

        with request.app.state.session_factory() as _s:
            record(
                _s,
                user_id=getattr(request.state, "user_id", None),
                action="http.500",
                target_type=exc.__class__.__name__,
                target_id=rid,
                detail={
                    "method": request.method,
                    "path": request.url.path,
                    "msg": str(exc)[:500],
                },
            )
            _s.commit()
    except Exception:
        logger.warning("audit.record for http.500 failed (non-fatal)")

    # Browsers get the styled 500 page; API clients get JSON.
    if _wants_html(request):
        try:
            from app.services.template_render import render as _render
            return _render(
                request, "errors/500.html",
                {
                    "request_id": rid,
                    "error_class": exc.__class__.__name__,
                },
                status_code=500,
            )
        except Exception:
            logger.warning("500 template render failed")

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "type": exc.__class__.__name__,
            "request_id": rid,
            "hint": "Pass the request_id to the operator for diagnosis.",
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    """404 handler — HTML for browsers, JSON for API clients."""
    if _wants_html(request):
        from app.services.template_render import render as _render
        return _render(
            request, "errors/404.html",
            {"path": request.url.path},
            status_code=404,
        )
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "path": request.url.path,
        },
    )


# Per-request access logging is now done by RequestContextMiddleware
# (registered earlier) which binds request_id + user_id + method + path
# to every loguru line. The older standalone middleware was removed
# to avoid duplicate access-log lines and double-request-id assignments.


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
