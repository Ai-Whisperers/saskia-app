"""Health endpoints — /healthz and /healthz/db.

Per docs/operations/2026-09-fase-1-specs.md §C.

When her browser shows a blank page, the diagnostic chain is:
1. Is uvicorn running? -> /healthz returns 200
2. Is the DB reachable? -> /healthz/db returns 200
3. Is the page route broken? -> look at browser devtools

Without this, debugging takes 10 minutes of "is it Python? is it the
browser? is it Windows Defender?"

Security: these endpoints return no PII, no DB content, no internal
state. They only report liveness and DB mode. Safe to hit.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from loguru import logger
from sqlalchemy import text

router = APIRouter()


def _healthz_payload() -> dict[str, Any]:
    """Shared payload for GET and HEAD (HEAD strips the body at transport level)."""
    return {
        "status": "ok",
        "service": "aiw-saskia-rms",
    }


@router.get("/healthz", response_model=None)
def healthz(request: Request) -> JSONResponse | dict:
    """Cheap health check.

    Returns 200 if the app finished startup. Returns 503 if the lifespan
    is still running (cold-start window). Returns 200 with body if
    startup completed successfully.

    Why gate on app.state.ready: during the cold-start window, uvicorn
    accepts requests before our lifespan calls create_all()/init_db().
    Any request that hits the dashboard during this window returned
    raw 500s with no info. /healthz returning 503 lets the operator
    see "warming up" instead of broken.
    """
    ready = getattr(request.app.state, "ready", False)
    if not ready:
        # Cold-start window — return 503 with structured payload so the
        # operator's UptimeRobot monitor shows "warming up".
        return JSONResponse(
            status_code=503,
            content={
                "status": "warming_up",
                "service": "aiw-saskia-rms",
                "detail": "App is still initializing; retry in a few seconds.",
            },
        )
    return _healthz_payload()


@router.head("/healthz", name="healthz-head")
def healthz_head(request: Request) -> Response:
    """HEAD variant for uptime monitors (UptimeRobot) that probe with HEAD.

    Same 503/200 logic as GET — body is stripped by the transport layer.
    """
    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return Response(status_code=503, media_type="application/json")
    return Response(status_code=200, media_type="application/json")


@router.get("/healthz/errors", response_model=None)
def healthz_errors(request: Request) -> JSONResponse:
    """Quick error-rate snapshot for the operator.

    Counts how many `action="http.500"` rows are in audit_log over the
    last 24h and last 1h. Operators hit this when the user sees "page
    not loading" — instantly know if there were recent server errors.

    Read-only public endpoint (sanitized: no PII, just counts).
    """
    from datetime import datetime, timedelta

    from sqlalchemy import func, select

    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up"},
        )

    from app.rms.models import AuditLog

    now = datetime.now()
    last_1h = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)

    with request.app.state.session_factory() as s:
        n_1h = s.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "http.500", AuditLog.occurred_at >= last_1h)
        ).scalar() or 0
        n_24h = s.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "http.500", AuditLog.occurred_at >= last_24h)
        ).scalar() or 0

    return JSONResponse(
        content={
            "http_500_count": {
                "last_1h": int(n_1h),
                "last_24h": int(n_24h),
            },
            "hint": "If last_1h > 0, check Render deploy logs or /auditoria?action_filter=http.500",
        }
    )


@router.get("/healthz/deps", response_model=None)
def healthz_deps(request: Request) -> JSONResponse | dict:
    """Dependency fingerprint for debugging env mismatches on Render.

    Reports presence + sha256 prefix of key env vars (never the values)
    and importable package versions. Public: safe metadata only.

    Gated on app.state.ready: returns 503 if app is still warming up,
    so probes during the cold-start window correctly distinguish
    "broken" from "warming up".
    """
    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up", "detail": "App still initializing."},
        )
    import hashlib
    import importlib.metadata as md

    def fp(name: str) -> str | None:
        v = os.environ.get(name)
        if v is None:
            return None
        return f"len={len(v)} sha={hashlib.sha256(v.encode()).hexdigest()[:12]}"

    pkgs = {}
    for pkg in ("supabase", "supabase-auth", "fastapi", "starlette"):
        try:
            pkgs[pkg] = md.version(pkg)
        except Exception:
            pkgs[pkg] = "NOT INSTALLED"
    return {
        "SUPABASE_URL": fp("SUPABASE_URL"),
        "SUPABASE_PUBLISHABLE_KEY": fp("SUPABASE_PUBLISHABLE_KEY"),
        "SUPABASE_SECRET_KEY": fp("SUPABASE_SECRET_KEY"),
        "packages": pkgs,
    }


@router.get("/healthz/db")
def healthz_db(request: Request) -> JSONResponse:
    """DB health check.

    Returns 200 if the database is reachable; 503 otherwise.
    Reports:
    - journal_mode on SQLite (must be 'wal' for concurrent-safe writes)
    - server version on Postgres
    - schema_version + migrations_pending (drift detector)
    - last_audit_at (timestamp of most recent audit log row)
    """
    from app.rms.db import (
        CURRENT_SCHEMA_VERSION,
        schema_version,
        schema_version_mismatch,
    )

    engine = request.app.state.engine
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result != 1:
                return JSONResponse(
                    {"db": "unreachable", "detail": "SELECT 1 failed"},
                    status_code=503,
                )
            payload: dict[str, Any] = {"db": "ok"}
            dialect = engine.dialect.name
            if dialect == "sqlite":
                mode = conn.execute(text("PRAGMA journal_mode")).scalar()
                payload["journal_mode"] = mode
                payload["dialect"] = "sqlite"
            elif dialect == "postgresql":
                ver = conn.execute(text("SHOW server_version")).scalar()
                payload["server_version"] = ver
                payload["dialect"] = "postgresql"
            else:
                payload["dialect"] = dialect
        # Schema drift + audit freshness — second roundtrip. Don't fail the
        # 200 just because these queries fail; report them in the body.
        try:
            with engine.connect() as conn:
                actual = schema_version(conn)
                payload["schema_version"] = actual
                payload["code_schema_version"] = CURRENT_SCHEMA_VERSION
                payload["migrations_pending"] = schema_version_mismatch(conn)
                # Most recent audit row — diagnostic for "is anything being
                # written?" without exposing content. SQLite returns the
                # timestamp as a string; Postgres returns a datetime.
                last = conn.execute(
                    text("SELECT MAX(occurred_at) FROM audit_log")
                ).scalar()
                if last is None:
                    payload["last_audit_at"] = None
                elif hasattr(last, "isoformat"):
                    payload["last_audit_at"] = last.isoformat()
                else:
                    payload["last_audit_at"] = str(last)
        except Exception as inner_exc:
            # Don't 503 the whole endpoint — DB is reachable, the metadata
            # queries aren't. Surface the detail so the operator can tell
            # the difference between "DB down" and "audit table missing".
            payload["db"] = "ok_no_metadata"
            payload["metadata_error"] = str(inner_exc)
        return payload
    except Exception as exc:
        return JSONResponse({"db": "error", "detail": str(exc)}, status_code=503)


__all__ = ["router"]


@router.get("/healthz/schema", response_model=None)
def healthz_schema(request: Request) -> JSONResponse:
    """Drift detector: returns code_version, db_version, drift.

    drift > 0 = DB behind code (CRITICAL — production will 500 on
    new columns). Operator action: redeploy to apply pending migrations
    (init_db() auto-runs as of 2026-09-08 by default).

    Returns 500 when drift > 0 so monitoring tools (UptimeRobot) alert.
    """
    from app.rms.db import (
        CURRENT_SCHEMA_VERSION,
        schema_version,
        schema_version_mismatch,
    )

    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up"},
        )

    with request.app.state.session_factory() as s:
        actual = schema_version(s.connection())
        drift = schema_version_mismatch(s.connection())

    body: dict[str, Any] = {
        "code_version": CURRENT_SCHEMA_VERSION,
        "db_version": actual,
        "drift": drift,
    }
    if drift > 0:
        body["hint"] = (
            f"DB schema v{actual}, code expects v{CURRENT_SCHEMA_VERSION}. "
            "Redeploy to apply pending migrations automatically."
        )
        body["status"] = "schema_drift"
        return JSONResponse(status_code=500, content=body)
    body["status"] = "in_sync"
    return JSONResponse(status_code=200, content=body)


@router.post("/healthz/migrate")
def healthz_migrate(request: Request):
    """Unauthenticated migration trigger (operator escape hatch).

    Same effect as /admin/migrate but without auth — intended for
    Render deploy hooks or emergency hotfixes where the operator
    can't log in.

    Idempotent (calls init_db() which no-ops if at target version).
    Public: anyone can hit this, but the operation is harmless
    (only adds missing columns/tables).

    Returns:
      200: {status: migrated, schema_version: N, code_schema_version: 32}
      500: {error: migration_failed, detail: ...}
    """
    from app.rms.db import CURRENT_SCHEMA_VERSION, init_db

    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return JSONResponse(
            status_code=503,
            content={"error": "server_not_ready"},
        )

    try:
        init_db(engine)
    except Exception as exc:
        logger.exception("admin_migrate failed")
        return JSONResponse(
            status_code=500,
            content={"error": "migration_failed", "detail": str(exc)[:500]},
        )

    from app.rms.db import schema_version
    with engine.connect() as conn:
        new_version = schema_version(conn)

    return JSONResponse(
        status_code=200,
        content={
            "status": "migrated",
            "schema_version": new_version,
            "code_schema_version": CURRENT_SCHEMA_VERSION,
            "in_sync": new_version == CURRENT_SCHEMA_VERSION,
        },
    )


@router.post("/admin/migrate")
def admin_migrate(request: Request):
    """Operator escape hatch: trigger init_db() to apply pending migrations.
    Required when Render is slow to redeploy OR when the lifespan
    auto-init failed silently on Postgres (JSONB bug pre-a6843b9).

    Idempotent — re-running is safe. Always runs all pending migrations
    up to CURRENT_SCHEMA_VERSION.

    Auth: requires an authenticated admin session (CSRF + login).
    Public health checks (GET) are intentionally unauthenticated so
    UptimeRobot / monitoring can detect drift; mutating endpoints
    like this one require admin login.

    Returns:
      - 200: migrations applied successfully
      - 401: not logged in
      - 500: a migration failed (the error message includes which step)
    """
    from app.auth import current_user_id
    from app.rms.db import CURRENT_SCHEMA_VERSION, init_db

    user_id = current_user_id(request)
    if user_id is None:
        return JSONResponse(
            status_code=401,
            content={"error": "authentication_required", "hint": "Login first."},
        )

    # Find the engine — same one the lifespan used.
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return JSONResponse(
            status_code=503,
            content={"error": "server_not_ready", "hint": "Lifespan hasn't initialized yet."},
        )

    try:
        init_db(engine)
    except Exception as exc:
        logger.exception("admin_migrate failed")
        return JSONResponse(
            status_code=500,
            content={"error": "migration_failed", "detail": str(exc)[:500]},
        )

    # Read back the new version
    from app.rms.db import schema_version
    with engine.connect() as conn:
        new_version = schema_version(conn)

    return JSONResponse(
        status_code=200,
        content={
            "status": "migrated",
            "schema_version": new_version,
            "code_schema_version": CURRENT_SCHEMA_VERSION,
            "in_sync": new_version == CURRENT_SCHEMA_VERSION,
        },
    )
