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
- Local: BIND_HOST=127.0.0.1, SQLite via AIW_RMS_DB_PATH
- Hosted (Render/Fly): BIND_HOST=0.0.0.0, Postgres via DATABASE_URL,
  TLS terminated upstream by Cloudflare Tunnel

Entry: `uv run uvicorn app.rms.main:app --host 0.0.0.0 --port 8000`
"""

from __future__ import annotations

import os
import sys
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Imported here only for type-checking; the runtime use of Session is in
# the SessionMiddleware subclass below. Newer starlette versions removed
# the export; provide a minimal stub for backward compat.
if TYPE_CHECKING:
    from starlette.middleware.sessions import Session as _StarletteSession
else:
    try:
        from starlette.middleware.sessions import Session as _StarletteSession
    except ImportError:

        class _StarletteSession(dict):  # type: ignore[no-redef]
            pass


import json
from base64 import b64decode

from itsdangerous.exc import BadSignature
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
    analisis,
    auditoria,
    auth,
    caja,
    copiloto,
    cotizador,
    customers,
    dashboard,
    demo,
    dev,
    eod,
    excel_io,
    fiado,
    gerencia,
    health,
    help,
    herebus,
    insights,
    insights_derived,
    insights_stock,
    inventory,
    menu_import,
    menus,
    merma,
    ops,
    pedidos,
    photo_credits,
    produccion,
    products,
    recipes,
    refund,  # app/routers/refunds.py → router name "refund"
    reorder,
    reportes,
    sales,
    search,
    settings,
    settings_runtime,
    shopping,
    stations,
    suppliers,
    suscripciones,
    users,
    validation,
)


def _configure_logging() -> None:
    """Configure loguru at import time.

    - In production (AIW_SASKIA_LOG_FORMAT=prod): JSON to stderr so
      Render's log viewer / log aggregators can parse line-by-line.
    - In dev (default): human-readable, color-coded.

    A rotating file sink is ALWAYS added (BACKLOG #45) so that:
      - On Render / Fly, the platform keeps ~7 days of structured JSON
        before rotating out.
      - On local dev, the file is ~/.local/share/aiw-restaurant/logs/app.log
        (rotated after 50MB, keep 7 files = ~350MB max disk usage).

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

    # Rotating file sink (BACKLOG #45). Path comes from env so prod and
    # dev can land in different places. Defaults to a per-app data dir
    # so a local dev doesn't pollute the repo. Skipped if AIW_SASKIA_LOG_FILE
    # is set to empty string (operator opted out, e.g. on Render where
    # platform already captures stderr).
    log_file = os.getenv("AIW_SASKIA_LOG_FILE")
    if log_file is None:
        # Default location: <data_dir>/logs/app.log (created lazily).
        from app.rms.config import DATA_DIR  # local import to avoid cycle

        log_dir = DATA_DIR / "logs"
        log_file = str(log_dir / "app.log")
    if log_file:
        log_dir = os.path.dirname(log_file) or "."
        try:
            os.makedirs(log_dir, exist_ok=True)
            logger.add(
                log_file,
                level=os.getenv("AIW_SASKIA_LOG_FILE_LEVEL", "INFO"),
                rotation="50 MB",
                retention="7 days",
                compression="gz",
                enqueue=True,  # thread-safe, non-blocking writes
                backtrace=True,
                diagnose=False,  # never leak env vars to disk
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | {extra[request_id]} | {extra[user_id]} | {name}:{function}:{line} | {message}",
            )
        except Exception as exc:
            sys.stderr.write(f"WARN: could not initialise log file sink at {log_file!r}: {exc!r}\n")


_configure_logging()

# PRO-SEC (2026-09-30): the test-auth bypass must NEVER run in production.
# It leaked once (Swarm service spec carried SASKIA_TEST_AUTH_DISABLED=1 and
# the whole app served without login). Fail loudly at boot if it's ever set
# OUTSIDE a pytest run (the test suite itself needs the bypass via conftest).
_UNDER_PYTEST = "pytest" in sys.modules
if os.getenv("SASKIA_TEST_AUTH_DISABLED") not in (None, "", "0") and not _UNDER_PYTEST:
    raise RuntimeError(
        "SASKIA_TEST_AUTH_DISABLED está activo: este bypass es solo para tests. "
        "Producción nunca debe arrancar con esta variable definida."
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

            # C.1 — mirror Sentry errors to Telegram so the operator
            # sees production incidents without opening Sentry.
            # The hook is a silent no-op when TG_BOT_TOKEN / TG_CHAT_ID
            # are unset (see app/rms/notify.py:telegram_configured).
            from app.rms.notify import sentry_before_send

            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[FastApiIntegration(), SqlalchemyIntegration()],
                traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
                # Don't capture PII by default. the operator's data is sensitive.
                send_default_pii=False,
                environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
                release=app.version,
                before_send=sentry_before_send,  # type: ignore[arg-type]
            )
        except Exception as exc:
            print(f"WARNING: Sentry init failed: {exc}", file=sys.stderr)

    # OpenTelemetry + Prometheus — gated by env var. Off by default.
    # Set OTEL_ENABLED=true + OTEL_EXPORTER_OTLP_ENDPOINT to enable tracing.
    # Set PROMETHEUS_ENABLED=true to expose /metrics.
    # See app/rms/otel.py for the activation matrix.
    try:
        from app.rms.otel import init_observability

        init_observability(app)
    except Exception as exc:
        print(f"WARNING: observability init failed: {exc}", file=sys.stderr)

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
    # Set AIW_RMS_RUN_MIGRATIONS=0 only if you specifically need to
    # pause migration application (e.g. during a maintenance window).
    #
    # History: previously this was gated behind a "1" flag, which left
    # the production DB out of sync with the code (the 2026-09-08 outage
    # where sale.payment_method didn't exist on Neon). Auto-running is
    # safer than opt-in.
    if os.getenv("AIW_RMS_RUN_MIGRATIONS", "1") != "0":
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
            # Tier 8.4 (2026-10-01): email the operator so the
            # migration drift doesn't sit unnoticed. We do this
            # inline (not in a background task) because the lifespan
            # is the only point at which we know whether the run
            # succeeded.
            try:
                from app.observability.alerts import dispatch_failure

                dispatch_failure(
                    title="Falla de migración al arrancar",
                    body=(
                        f"Saskia RMS no pudo aplicar las migraciones en el "
                        f"arranque.\n\n"
                        f"code_schema_version={CURRENT_SCHEMA_VERSION}\n"
                        f"db_schema_version={pre}\n"
                        f"error={exc!r}\n\n"
                        f"Revisá /healthz/migrate en la app y la salida de "
                        f"los logs del servicio."
                    ),
                    severity="error",
                )
            except Exception as alert_exc:
                # Never let a broken alert path block the main one.
                logger.warning(f"migration alert dispatch failed: {alert_exc!r}")

    # Phase 1.A — Idempotent password sync from env vars (SASKIA_ADMIN_PASSWORD,
    # SASKIA_USER_PASSWORD, SASKIA_IVAN_TEST_PASSWORD). When the deployment injects
    # a fresh password via docker-compose / Render env, this aligns the bcrypt
    # hash on boot. No-op when env vars are unset (local dev).
    try:
        from app.rms.bootstrap import run_password_sync

        with make_session_factory(engine)() as _bs:
            run_password_sync(_bs)
    except Exception:
        logger.exception("password bootstrap failed (non-fatal)")

    # Phase 1.C — Apply HACCP defaults to ingredients that have a known
    # category but no temperature/humidity/water-activity values yet.
    # Idempotent: skips rows that are already populated.
    try:
        from app.rms.haccp_seed import apply_haccp_defaults

        with make_session_factory(engine)() as _bs:
            n = apply_haccp_defaults(_bs)
            if n:
                logger.info("haccp: applied defaults to %d ingredients", n)
    except Exception:
        logger.exception("haccp seed failed (non-fatal)")

    # market-intel 2026-09-30 — evidencia de competencia retail
    # (86 observaciones del research repo sazon-market-intel).
    # Idempotente + no-fatal: si el seed falla, /vs-mercado/evidencia
    # queda vacía pero la app arranca igual.
    try:
        from app.rms.db import make_session_factory as _mi_factory

        # noqa: arch-rule — calls seed_competitor_prices at startup (lazy import in lifespan)
        from app.rms.seed.competitor_prices import seed_competitor_prices

        with _mi_factory(engine)() as _bs:
            n_added, _n_skipped = seed_competitor_prices(_bs)
            if n_added:
                logger.info("market-intel: %d observaciones de competencia sembradas", n_added)
    except Exception:
        logger.exception("market-intel seed failed (non-fatal)")

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
        # Tier 8.4 (2026-10-01): email the operator. A backup
        # failure isn't a customer-facing emergency but it IS
        # a "your data is at risk" emergency, so the alert path
        # is critical-severity.
        try:
            from app.observability.alerts import dispatch_failure

            dispatch_failure(
                title="Falla de backup automático",
                body=(
                    f"El backup automático en el arranque falló.\n\n"
                    f"error={exc!r}\n\n"
                    f"Revisá los logs de la app y el storage remoto. "
                    f"Las ventas de hoy todavía están en SQLite local; "
                    f"exportá manualmente si es necesario."
                ),
                severity="critical",
            )
        except Exception as alert_exc:
            logger.warning(f"backup alert dispatch failed: {alert_exc!r}")
    yield


# Build the app


def create_app() -> FastAPI:
    """Build and configure the Sazon FastAPI app.

    Factory pattern (instead of module-level singleton) so that:
    - Tests can instantiate an isolated app with a test DB session.
    - Multi-worker uvicorn (--workers N) doesn't share module-level
      state between workers.
    - The module-level `app = create_app()` at the bottom keeps the
      `app.rms.main:app` uvicorn reference working.

    All middleware, routers, exception handlers, and the lifespan
    are wired up here. CLI commands (migrate, _serve, run, _rollback,
    _seed) are NOT part of the app factory — they're invoked from
    the entry point (python -m app.rms.main ...).
    """
    app = FastAPI(
        title="Sazón — Sistema de gestión",
        description="Restaurant management system. Hosted (Neon Postgres + Cloudflare) or local.",
        version="2026.09.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    class StaticCacheMiddleware:
        """Add Cache-Control + strip vary:Cookie on /static/* responses.

        Implemented as a raw ASGI middleware (not BaseHTTPMiddleware) so we can
        intercept the http.response.start message and remove the vary:Cookie
        header that SessionMiddleware adds *after* BaseHTTPMiddleware.dispatch
        has already returned its modified Response object.

        Assets behind /static/* are version-busted via the ?v= query parameter.
        Responses can therefore be cached "forever" with the immutable directive,
        which suppresses all conditional revalidation (If-Modified-Since, ETag).

        Exception: /static/app.js is NEVER served with `immutable`.  It carries
        bindings registered at deploy time (initConfirmLinks, initSidebar, etc.)
        and a tab with the old /static/app.js?v=<stale> would lose those bindings
        silently for a full year.  We send no-cache instead, forcing
        If-Modified-Since revalidation on every visit.
        """

        # Paths under /static/ that must NOT use the immutable cache header.
        _REVALIDATE_PATHS = frozenset({"/static/app.js"})

        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http" or not scope["path"].startswith("/static/"):
                await self.app(scope, receive, send)
                return

            path = scope["path"]
            vary_stripped = False

            async def wrapped_send(message: Message) -> None:
                nonlocal vary_stripped
                if message["type"] == "http.response.start":
                    if not vary_stripped:
                        vary_stripped = True
                        # Copy the message so our header mutations don't affect
                        # SessionMiddleware.send_wrapper which holds a reference
                        # to the original dict/list and will re-mutate the headers.
                        message = dict(message)
                        message["headers"] = list(message["headers"])

                        new_headers = [
                            (k, v) for k, v in message["headers"] if k.lower() != b"vary"
                        ]
                        message["headers"] = new_headers

                    # Set Cache-Control.
                    # The if above guarantees immutable is only set for immutable paths.
                    cache_value = (
                        "no-cache"
                        if path in self._REVALIDATE_PATHS
                        else "max-age=31536000, immutable"
                    )
                    # Append or replace Cache-Control.
                    headers = [
                        (k, v) for k, v in message["headers"] if k.lower() != b"cache-control"
                    ]
                    headers.append((b"cache-control", cache_value.encode()))
                    message["headers"] = headers

                await send(message)

            await self.app(scope, receive, wrapped_send)

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

        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            response = await call_next(request)
            if request.url.path.startswith("/healthz"):
                # s-maxage is for shared caches (Cloudflare); max-age is for browsers.
                # 10s strikes the balance between freshness and edge-cache hit rate.
                response.headers["Cache-Control"] = "public, max-age=10, s-maxage=10"
            return response

    app.add_middleware(HealthCacheMiddleware)

    # Phase 14 — Prometheus /metrics middleware. Stdlib-only so we don't add
    # starlette_exporter as a dep. Records request count + latency for every
    # route, plus a DB-up gauge updated on each /healthz/db hit.
    class MetricsMiddleware(BaseHTTPMiddleware):
        """Increment request counters and the latency histogram on every response."""

        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            from time import perf_counter

            from app.rms.metrics import record_request

            start = perf_counter()
            try:
                response = await call_next(request)
            except Exception:
                duration = perf_counter() - start
                record_request(request.url.path, request.method, 500, duration)
                raise
            duration = perf_counter() - start
            record_request(
                request.url.path,
                request.method,
                response.status_code,
                duration,
            )
            return response

    app.add_middleware(MetricsMiddleware)

    # Security headers middleware: defense-in-depth HTTP response headers
    # Detect session leaks: warns + closes any Session opened during a
    # request that wasn't closed by the handler. Defense in depth against
    # future code that forgets to use `Depends(get_session)`.
    app.add_middleware(SessionLifecycleMiddleware)

    # CSRF protection: signed double-submit cookie.
    # Set on every GET response to non-exempt paths; required on every POST.
    app.middleware("http")(csrf_cookie_middleware)

    # Security headers MUST be added AFTER csrf_cookie_middleware so that
    # the headers get applied to error responses raised from csrf (e.g.
    # the 403 missing_or_invalid_csrf_token JSONResponse). Starlette/FastAPI
    # runs middleware in REVERSE registration order (last registered =
    # outermost), so adding SecurityHeadersMiddleware here means it wraps
    # everything below it, including csrf's HTTPException responses.
    app.add_middleware(SecurityHeadersMiddleware)

    class StationGateMiddleware(BaseHTTPMiddleware):
        """Keep a chosen station inside its screens.

        With auth disabled and no station in the session (the test default),
        the gate does nothing so existing pages keep working. Once a station
        is chosen, another station's screen is refused.
        """

        async def dispatch(
            self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            path = request.url.path
            if path.startswith(
                ("/static", "/healthz", "/favicon", "/login", "/logout", "/forgot-password")
            ):
                return await call_next(request)
            try:
                session = request.session
            except AssertionError:
                return await call_next(request)
            from app.auth import current_user_id, is_auth_disabled
            from app.rms.stations import decide

            try:
                user_present = current_user_id(request) is not None
            except Exception:
                user_present = False
            result = decide(
                path,
                session,
                auth_disabled=is_auth_disabled(),
                user_present=user_present,
            )
            if result is None:
                return await call_next(request)
            if result == "deny":
                return HTMLResponse(
                    "<!doctype html><meta charset='utf-8'><title>Otro puesto</title>"
                    "<p>Esa pantalla es de otro puesto.</p>",
                    status_code=403,
                )
            return RedirectResponse(result.split(":", 1)[1], status_code=303)

    # Inner relative to SessionMiddleware (added below), so the session cookie
    # is already loaded when the gate reads it.
    app.add_middleware(StationGateMiddleware)

    # Session middleware: signs cookies with SESSION_SECRET.
    # Must be added BEFORE routers so login_user() can write to request.session.
    # Same-site=lax + https-only when behind CF Tunnel (which always terminates TLS).
    class _NoVaryCookieSessionMiddleware(SessionMiddleware):
        """SessionMiddleware that skips adding 'vary: Cookie' for static assets.

        SessionMiddleware normally adds vary:Cookie to every response that accessed
        the session, preventing browsers/CDNs from caching static assets (images,
        CSS, fonts) independently of the session cookie.  For /static/* paths the
        response is always identical regardless of session, so we skip the
        vary:Cookie header there.  (Cache-Control is handled separately by
        StaticCacheMiddleware.)
        """

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] not in ("http", "websocket"):  # pragma: no cover
                await self.app(scope, receive, send)
                return

            if scope["path"].startswith("/static/"):
                # For static assets: pass through without touching the session OR
                # the vary header.  The session signer is still initialized so
                # login_user() can write request.session on the way through.
                connection = HTTPConnection(scope)
                if self.session_cookie in connection.cookies:
                    try:
                        data = connection.cookies[self.session_cookie].encode("utf-8")
                        data = self.signer.unsign(data, max_age=self.max_age)
                        scope["session"] = _StarletteSession(json.loads(b64decode(data)))
                    except BadSignature:
                        scope["session"] = _StarletteSession()
                else:
                    scope["session"] = _StarletteSession()
                await self.app(scope, receive, send)
                return

            # Normal session middleware for all other paths.
            await super().__call__(scope, receive, send)

    app.add_middleware(
        _NoVaryCookieSessionMiddleware,
        secret_key=SESSION_SECRET,
        session_cookie="sazon_session",
        max_age=60 * 60 * 24 * 7,  # 7 days
        same_site="lax",
        https_only=os.getenv("HTTPS_ONLY", "true").lower() == "true",
    )

    # Mount static files (CSS, images, etc.) so templates can link /static/app.css
    _static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.isdir(_static_dir):
        # ── combo component alias — must be registered BEFORE app.mount("/static")
        # so the explicit route wins over the StaticFiles catch-all. The combo
        # Web Component lives at ui-combo.js; /static/combo.js is kept as a
        # legacy alias so existing templates + tests still resolve.
        @app.get("/static/combo.js", include_in_schema=False)
        def _combo_js_alias() -> FileResponse:
            return FileResponse(
                os.path.join(_static_dir, "ui-combo.js"),
                media_type="application/javascript",
            )

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
    app.include_router(stations.router)
    app.include_router(health.router)
    app.include_router(gerencia.router)
    app.include_router(dashboard.router)
    # Dev-only combo smoke page; routes self-gate on DEV_COMBO_SMOKE env (404 in prod).
    app.include_router(dev.router)
    app.include_router(validation.router)
    app.include_router(analisis.router)
    app.include_router(inventory.router)
    app.include_router(recipes.router)
    app.include_router(suppliers.router)
    app.include_router(products.router)
    app.include_router(sales.router)
    app.include_router(caja.router)
    app.include_router(fiado.router)
    app.include_router(menu_import.router)
    app.include_router(menus.router)
    app.include_router(cotizador.router)
    app.include_router(copiloto.router)
    app.include_router(refund.router)
    app.include_router(search.router)
    app.include_router(excel_io.router)
    app.include_router(customers.router)
    app.include_router(demo.router)
    app.include_router(produccion.router)
    app.include_router(eod.router)
    app.include_router(merma.router)
    app.include_router(reportes.router)
    app.include_router(suscripciones.router)

    # HEREBUS Drive integration modules
    app.include_router(herebus.wishlist_router)
    app.include_router(herebus.risks_router)
    app.include_router(herebus.pricing_router)
    app.include_router(herebus.bank_router)
    app.include_router(herebus.benchmarks_router)
    app.include_router(insights_derived.router)
    app.include_router(insights.router, prefix="/api/insights", tags=["insights"])
    app.include_router(insights_stock.router)
    app.include_router(herebus.dashboard_router)
    app.include_router(herebus.planner_router)
    app.include_router(herebus.delivery_router)
    app.include_router(shopping.router)
    # NAV-02: Auditoría and Ops are internal-only. The product surface does
    # not include them (the operator does not run audits). In production they
    # 404; in tests / dev they are still mounted so the test suite can
    # exercise them.
    #
    # Default behaviour (no env var): NOT mounted (production).
    # Set AIW_SASKIA_INTERNAL_ROUTES=1 to mount (tests, internal admin).
    # This env var must be set BEFORE app.rms.main is imported.
    # Audit + ops pages: mounted by DEFAULT since real auth went live
    # (2026-09-25). The audit log is a core multi-user feature. Set
    # AIW_SASKIA_INTERNAL_ROUTES=0 to unmount (tests that need the old 404).
    if os.getenv("AIW_SASKIA_INTERNAL_ROUTES", "1") != "0":
        app.include_router(auditoria.router)
        app.include_router(ops.router)
    app.include_router(settings.router)
    app.include_router(settings_runtime.router)

    # Phase 14 — Prometheus /metrics endpoint. Stdlib-only, no auth (the
    # endpoint reveals paths + status codes but no PII. If you want it
    # locked down, put it behind the same CF Tunnel that already protects
    # the rest of /sazon-vps).
    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        from fastapi.responses import PlainTextResponse

        from app.rms.config import CURRENT_SCHEMA_VERSION
        from app.rms.metrics import render, set_app_info

        set_app_info(version="1.0", schema_version=CURRENT_SCHEMA_VERSION)
        return PlainTextResponse(
            render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # Spanish-language alias: /proveedores → /suppliers
    # Operators see "proveedores" in UI copy. Accepting both URLs means
    # external links/bookmarks work regardless of which word was used.
    @app.get("/proveedores", include_in_schema=False)
    def proveedores_alias() -> object:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/suppliers", status_code=303)

    app.include_router(users.router)
    app.include_router(reorder.router)
    app.include_router(help.router)
    app.include_router(photo_credits.router)
    app.include_router(pedidos.public_router)
    # C2 — public tablet menu at /m/{slug}. Mounted at root so the URL
    # stays short enough for a 1280×720 walk-in tablet to type / display.
    app.include_router(products.public_router)
    # BACKLOG #17 — public digital recibo at /r/{token}. Mounted at root so
    # the URL is short enough for WhatsApp messages (sazon-vps.paragu-ai.com/r/{token}).
    app.include_router(sales.public_router)
    app.include_router(pedidos.router)

    # Dev-only routes (gated by env var, never enabled in production)
    import os as _os

    if _os.getenv("DEV_COMBO_SMOKE"):
        from app.routers import dev as _dev_router

        app.include_router(_dev_router.router)
        app.include_router(_dev_router.api_router)

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
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
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
                parts.append(
                    f"{field} debe ser ≥ {limit}"
                    if etype == "greater_than_equal"
                    else f"{field} debe ser > {limit}"
                )
            elif etype in ("less_than", "less_than_equal"):
                limit = err.get("ctx", {}).get("le") or err.get("ctx", {}).get("lt")
                parts.append(
                    f"{field} debe ser ≤ {limit}"
                    if etype == "less_than_equal"
                    else f"{field} debe ser < {limit}"
                )
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
            content={
                "detail": detail,
                "fields": [
                    loc[-1] if loc else "campo"
                    for loc in [
                        [
                            str(x)
                            for x in e.get("loc", [])
                            if x not in ("body", "query", "path", "form")
                        ]
                        for e in errors
                    ]
                ],
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
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
        from fastapi import HTTPException

        from app.rms.errors import AppError

        rid = getattr(request.state, "request_id", None) or _request_id()

        # ─── 1. AppError (typed errors from our hierarchy) ─────────────
        if isinstance(exc, AppError):
            logger.warning(
                "app_error request_id={} type={} reason={} msg={} context={!r}",
                rid,
                exc.__class__.__name__,
                exc.reason_code,
                exc.message,
                exc.context,
            )
            # AppErrors are NOT 500s unless explicitly typed as such. The
            # whole point of the hierarchy is that business errors don't
            # pollute the "internal server error" bucket.
            payload = exc.to_dict()
            payload["request_id"] = rid
            if _wants_html(request):
                from app.services.template_render import render as _render

                # BACKLOG #48: render a styled 4xx page (or 404 fallback)
                # for browser requests, with reason_code + request_id
                # surfaced so support can grep one identifier.
                resp = None
                if exc.status_code == 404:
                    resp = _render(
                        request,
                        "errors/404.html",
                        {"path": request.url.path, "reason": exc.reason_code},
                        status_code=404,
                    )
                elif 400 <= exc.status_code < 500:
                    from app.rms.errors import _ERROR_TITLES  # local import

                    title, default_msg = _ERROR_TITLES.get(
                        exc.status_code, ("Error", "Algo salió mal.")
                    )
                    resp = _render(
                        request,
                        "errors/4xx.html",
                        {
                            "status_code": exc.status_code,
                            "title": title,
                            "message": exc.message or default_msg,
                            "reason": exc.reason_code,
                            "request_id": rid,
                        },
                        status_code=exc.status_code,
                    )
                if resp is not None:
                    resp.headers["X-Request-Id"] = rid
                    resp.headers["X-Reason-Code"] = exc.reason_code
                    return resp
            return JSONResponse(
                status_code=exc.status_code,
                content=payload,
                headers={"X-Reason-Code": exc.reason_code},
            )

        # ─── 2. HTTPException (FastAPI control-flow) ───────────────────
        if isinstance(exc, HTTPException):
            logger.info(
                "http_exception request_id={} status={} detail={!r}",
                rid,
                exc.status_code,
                exc.detail,
            )
            if _wants_html(request):
                from app.services.template_render import render as _render

                resp = None
                if exc.status_code == 404:
                    resp = _render(
                        request,
                        "errors/404.html",
                        {"path": request.url.path},
                        status_code=404,
                    )
                elif 400 <= exc.status_code < 500:
                    from app.rms.errors import _ERROR_TITLES

                    title, default_msg = _ERROR_TITLES.get(
                        exc.status_code, ("Error", "Algo salió mal.")
                    )
                    detail_msg = exc.detail if isinstance(exc.detail, str) else default_msg
                    resp = _render(
                        request,
                        "errors/4xx.html",
                        {
                            "status_code": exc.status_code,
                            "title": title,
                            "message": detail_msg,
                            "request_id": rid,
                        },
                        status_code=exc.status_code,
                    )
                if resp is not None:
                    resp.headers["X-Request-Id"] = rid
                    if "X-Reason-Code" not in (resp.headers or {}):
                        resp.headers["X-Reason-Code"] = "http_error"
                    return resp
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
            rid,
            request.method,
            request.url.path,
            exc,
        )
        # Tag Sentry events with the request_id so an operator who sees a
        # Sentry alert can grep `/auditoria?action_filter=http.500` (target_id
        # == request_id) to pull the local traceback + breadcrumb. Fixed
        # 2026-09-29 (BACKLOG #44). No-op when Sentry isn't initialised.
        try:
            import sentry_sdk as _sentry

            if _sentry.Hub.current.client is not None:
                _sentry.set_tag("request_id", rid)
                _sentry.set_tag("request_method", request.method)
                _sentry.set_tag("request_path", request.url.path)
        except Exception:  # noqa: S110
            # Sentry not installed, not initialised, or Hub is unavailable.
            # Never let an observability hook break the response.
            pass
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
                    request,
                    "errors/500.html",
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
    async def not_found_handler(request: Request, exc: Exception) -> Response:
        """404 handler — HTML for browsers, JSON for API clients."""
        if _wants_html(request):
            from app.services.template_render import render as _render

            return _render(
                request,
                "errors/404.html",
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

    return app


# Build the module-level app for uvicorn's `app.rms.main:app` reference
# and for any test that does `from app.rms.main import app`.
app = create_app()


def migrate() -> None:
    """Schema migration entry point. Idempotent.

    Usage:
        uv run sazon migrate            # uses DATABASE_URL or AIW_RMS_DB_PATH
        DATABASE_URL=postgres://... uv run sazon migrate
    """
    import sys

    from sqlalchemy import inspect

    from app.rms.db import CURRENT_SCHEMA_VERSION, _current_schema_version, init_db
    from app.rms.db_dialect import make_engine

    raw = os.environ.get("DATABASE_URL")
    if not raw:
        local_db = os.environ.get("AIW_RMS_DB_PATH") or os.environ.get(
            "AIW_SASKIA_DB_PATH"
        )  # AIW_SASKIA_* = legacy env name still set in prod (saskia-vps service)
        if local_db:
            raw = f"sqlite:///{local_db}"
        else:
            print(
                "ERROR: DATABASE_URL (or AIW_RMS_DB_PATH) not set. "
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
    """Programmatic entry point (used by `uv run sazon` script entry).

    Dispatches based on sys.argv:
      - `sazon migrate`   -> apply schema migrations (idempotent)
      - `sazon serve`     -> start uvicorn (default; backward compatible)
      - (no argv)              -> start uvicorn (backward compatible)

    Reads BIND_HOST, PORT from config (which reads env vars). Asserts
    bind is allowed before starting.
    """
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "migrate":
        migrate()
        return
    if argv and argv[0] == "rollback":
        _rollback()
        return
    if argv and argv[0] in ("seed", "demo"):
        _seed()
        return
    if argv and argv[0] == "seed-sazon":
        _seed()
        return
    if argv and argv[0] in ("serve", "run", "start"):
        _serve()
        return
    # Default: serve (backward compat with pre-argv-dispatch entry)
    _serve()


def _rollback() -> None:
    """Undo the last applied migration by restoring its rule-17 backup.

    Usage:
        uv run sazon rollback             # roll back current → previous
        uv run sazon rollback --to 113    # explicit target (must match archive)
        uv run sazon rollback --dry-run   # show what WOULD happen, change nothing

    SQLite-only (prod shape). Fail-closed: no matching archive, integrity
    failure, or non-SQLite URL → refused, live DB untouched.
    """
    import sys

    from app.rms.db_dialect import make_engine
    from app.rms.rollback import RollbackError, rollback_sqlite

    raw = os.environ.get("DATABASE_URL")
    if not raw:
        local_db = os.environ.get("AIW_RMS_DB_PATH") or os.environ.get("AIW_SASKIA_DB_PATH")
        if local_db:
            raw = f"sqlite:///{local_db}"
        else:
            print(
                "ERROR: DATABASE_URL (or AIW_RMS_DB_PATH) not set. "
                "Cannot determine which DB to roll back.",
                file=sys.stderr,
            )
            sys.exit(1)

    to_version: int | None = None
    if "--to" in sys.argv:
        i = sys.argv.index("--to")
        to_version = int(sys.argv[i + 1])

    dry_run = "--dry-run" in sys.argv
    engine = make_engine(raw)
    current_version = None
    try:
        if dry_run:
            # Light dry-run: report versions + the archive that would be used
            from pathlib import Path as _P

            from app.rms.db import _backup_dir_path
            from app.rms.rollback import find_rollback_backup

            url = str(engine.url)
            db_path = _P(url.replace("sqlite:///", "", 1))
            from app.rms.rollback import _read_schema_version

            current_version = _read_schema_version(db_path)
            backup = find_rollback_backup(current_version, _backup_dir_path())
            print(f"DRY-RUN: would roll back v{current_version} using {backup.name}")
            return

        result = rollback_sqlite(engine, to_version=to_version)
        print(
            f"rolled back v{result.previous_version} → v{result.restored_version} "
            f"using {result.backup_used.name}\n"
            f"evidence: {result.evidence_path.name}\n"
            f"log: {result.log_key}\n"
            f"next: uv run sazon migrate to re-apply, or inspect the app."
        )
    except RollbackError as exc:
        print(f"ROLLBACK REFUSED: {exc}", file=sys.stderr)
        sys.exit(2)


def _seed() -> None:
    """Insert realistic demo data. Idempotent; --reset wipes seeded rows first.

    Usage:
        uv run sazon seed                  # additive (skip existing) — basic demo
        uv run sazon seed --reset          # destructive: wipe + reseed basic demo
        uv run sazon seed-sazon            # full multi-tenant seed (La Vaquita Holandesa)
        uv run sazon seed-sazon --reset    # destructive: wipe + reseed full sazon
    """
    import sys

    from app.rms.db import make_session_factory
    from app.rms.db_dialect import make_engine

    is_sazon = "seed-sazon" in sys.argv
    overwrite = "--reset" in sys.argv

    raw = os.environ.get("DATABASE_URL")
    if not raw:
        local_db = os.environ.get("AIW_RMS_DB_PATH") or os.environ.get(
            "AIW_SASKIA_DB_PATH"
        )  # AIW_SASKIA_* = legacy env name still set in prod (saskia-vps service)
        if local_db:
            raw = f"sqlite:///{local_db}"
        else:
            print(
                "ERROR: DATABASE_URL (or AIW_RMS_DB_PATH) not set. "
                "Cannot determine which DB to seed.",
                file=sys.stderr,
            )
            sys.exit(1)

    engine = make_engine(raw)
    SessionLocal = make_session_factory(engine)
    session = SessionLocal()
    try:
        if is_sazon:
            # noqa: arch-rule — main.py is the CLI entry point; seed/ is runtime-loaded package
            from app.rms.seed import SazonReport, seed_sazon

            sazon_report: SazonReport = seed_sazon(session, overwrite=overwrite)
            print(f"seed complete: {sazon_report.as_dict()}")
        else:
            # SeedReport is intentionally not re-exported from app.rms.seed
            # (sazon's public API surface is sazon-only). Import the demo
            # module directly when callers need the report class.

            # noqa: arch-rule — main.py is the CLI entry point; imports demo module (includes seed.demo)
            from app.rms.seed import (
                seed_demo_data,  # noqa: arch-rule — main.py is the CLI entry point
            )
            from app.rms.seed.demo import (
                SeedReport,  # noqa: arch-rule — main.py is the CLI entry point
            )

            demo_report: SeedReport = seed_demo_data(session, overwrite=overwrite)
            print(f"seed complete: {demo_report.as_dict()}")
    finally:
        session.close()


if __name__ == "__main__":
    # Direct entry: `python -m app.rms.main`
    run()
