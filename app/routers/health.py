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
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from loguru import logger
from sqlalchemy import text

router = APIRouter()


# --- Dependency-probe helpers (BACKLOG #40) ---


def _disk_usage(path: str):
    """Wrapper for shutil.disk_usage — patchable in tests."""
    return shutil.disk_usage(path)


def _get_last_backup_at(request: Request):
    """Read the last_backup_at app_meta row, return ISO string or None.

    BACKLOG #39 (2026-10-02): this helper exposes backup freshness to
    /healthz/backup. Tests patch it to simulate stale / missing states.
    """
    try:
        from app.rms.models import AppMeta
        from sqlalchemy import select

        with request.app.state.session_factory() as s:
            row = s.scalars(
                select(AppMeta).where(AppMeta.key == "last_backup_at")
            ).first()
            return row.value if row else None
    except Exception:  # noqa: BLE001 — defensive default
        # On any DB error we report "no backup" rather than failing the
        # endpoint. The /healthz/db endpoint already surfaces DB issues.
        return None


def _check_supabase_reachable(url: str, timeout: float = 2.0) -> bool:
    """HEAD the Supabase auth health endpoint. Returns True on 2xx/3xx.

    BACKLOG #40 (2026-10-02): live-site incident showed auth sign-in
    silently broke when SUPABASE_URL was misconfigured; an external
    probe in /healthz/deps makes the outage visible in UptimeRobot.
    """
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    health = f"{parsed.scheme}://{parsed.netloc}/auth/v1/health"
    try:
        req = urllib.request.Request(health, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _check_r2_reachable(timeout: float = 2.0) -> bool:
    """List objects in the R2 bucket — proves bucket + creds + network.

    Returns False if R2 isn't set up (caller treats as 'skipped' first).
    """
    try:
        from app.services.r2_backup import (
            load_r2_settings,
            make_boto3_client,
        )
    except ImportError:
        return False
    settings = load_r2_settings()
    if settings is None:
        return False
    try:
        client = make_boto3_client(settings)
        # head_bucket is the cheapest call — confirms creds + bucket exist
        # without enumerating objects. The boto3 client is typed loosely
        # as `object` upstream, so we cast for type-checker clarity.
        client.head_bucket(Bucket=settings.bucket)  # type: ignore[attr-defined]
        return True
    except Exception:  # noqa: BLE001 — defensive default
        return False


# --- Original endpoints ---


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

    from app.rms.config import ASUNCION_TZ
    from app.rms.models import AuditLog

    now = datetime.now(ASUNCION_TZ)
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
    """Dependency fingerprint + reachability for debugging on the VPS.

    BACKLOG #40 (2026-10-02): expanded from env fingerprints only to
    actually probe Supabase (auth), R2 (bucket), and disk space.

    Reports:
    - env var presence + sha256 fingerprints (no values)
    - package versions
    - supabase: {ok, url} — True/False/"skipped"
    - r2: {ok, bucket} — True/False/"skipped"
    - disk: {total_gb, used_gb, free_gb, used_pct, path}

    "skipped" means the dep isn't configured (dev box / local test) —
    not a 503. False means configured + unreachable = 503 + alarm.

    Public endpoint (no PII, just metadata). Gated on app.state.ready
    so probes during cold-start distinguish "broken" from "warming up".
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
        except Exception:  # noqa: BLE001 — defensive default
            pkgs[pkg] = "NOT INSTALLED"

    # --- Supabase reachability ---
    sb_env_url = os.environ.get("SUPABASE_URL", "")
    if not sb_env_url:
        supabase_block: dict = {"ok": "skipped", "reason": "SUPABASE_URL not set"}
    else:
        supabase_block = {
            "ok": _check_supabase_reachable(sb_env_url, timeout=2.0),
            "url_host": urllib.parse.urlparse(sb_env_url).netloc,
        }

    # --- R2 reachability ---
    try:
        from app.services.r2_backup import load_r2_settings

        settings = load_r2_settings()
    except ImportError:
        settings = None
    if settings is None:
        r2_block: dict = {"ok": "skipped", "reason": "R2 config not found"}
    else:
        r2_block = {
            "ok": _check_r2_reachable(timeout=2.0),
            "bucket": settings.bucket,
        }

    # --- Disk usage ---
    # The app stores DB + state under this root. On VPS: /opt/data.
    # On dev boxes: /tmp. Report on whatever exists.
    disk_root = "/opt/data" if os.path.isdir("/opt/data") else "/tmp"
    try:
        usage = _disk_usage(disk_root)
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        free_gb = usage.free / (1024**3)
        used_pct = round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0
    except OSError as exc:
        disk_block: dict = {"error": str(exc), "path": disk_root}
        total_gb = used_gb = free_gb = used_pct = 0  # for 503 logic below
    else:
        disk_block = {
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "used_pct": used_pct,
            "path": disk_root,
            "alarm_threshold_pct": 90,
        }
        if used_pct >= 90:
            disk_block["alarm"] = "disk_full"

    # --- Decide HTTP status ---
    # 503 only when a *configured* dep is unreachable (not when skipped).
    bad = []
    if supabase_block.get("ok") is False:
        bad.append("supabase")
    if r2_block.get("ok") is False:
        bad.append("r2")
    body: dict[str, Any] = {
        "SUPABASE_URL": fp("SUPABASE_URL"),
        "SUPABASE_PUBLISHABLE_KEY": fp("SUPABASE_PUBLISHABLE_KEY"),
        "SUPABASE_SECRET_KEY": fp("SUPABASE_SECRET_KEY"),
        "packages": pkgs,
        "supabase": supabase_block,
        "r2": r2_block,
        "disk": disk_block,
    }
    if bad:
        body["status"] = "deps_unreachable"
        body["unreachable"] = bad
        return JSONResponse(status_code=503, content=body)
    body["status"] = "ok"
    return body


@router.get("/healthz/depth", response_model=None)
def healthz_depth(request: Request) -> JSONResponse | dict:
    """Depth-of-stack liveness — pings the things the app needs besides DB.

    BACKLOG #40 (Tier 7): the operator can't tell from /healthz or
    /healthz/db whether the rest of the stack is healthy. This endpoint
    probes:
      - disk_free_bytes: free space in DATA_DIR (the SQLite file lives there)
      - r2_reachable: HEAD on the R2 bucket (if R2_BUCKET_URL is set)
      - supabase_reachable: lightweight env-var presence check (a real
        GET would require auth tokens; we just report "configured" vs
        "missing", not a network probe).

    Each probe is timed out to 2s so a slow external never wedges the
    endpoint. Endpoint returns 200 if all probes complete (even if a
    probe reports FAIL — operators need to see the diagnostic, not a
    UptimeRobot alert that hides the detail).

    Read-only, no PII. Safe to hit from monitoring.
    """
    import shutil as _shutil
    import concurrent.futures

    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up", "detail": "App still initializing."},
        )

    # 1. Disk free in DATA_DIR (default = cwd).
    from app.rms.config import DATA_DIR

    try:
        usage = _shutil.disk_usage(DATA_DIR)
        disk_payload: dict[str, Any] = {
            "ok": True,
            "free_bytes": int(usage.free),
            "total_bytes": int(usage.total),
            "path": str(DATA_DIR),
        }
    except Exception as exc:  # noqa: BLE001 — defensive
        disk_payload = {"ok": False, "error": str(exc)[:200], "path": str(DATA_DIR)}

    # 2. R2 reachability — HEAD on the bucket URL, 2s timeout. Optional.
    import urllib.request

    r2_url = os.environ.get("R2_BUCKET_URL")
    r2_payload: dict[str, Any] = {"configured": bool(r2_url)}
    if r2_url:
        try:

            def _head(url: str) -> int:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    return resp.status

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(_head, r2_url)
                status = future.result(timeout=3)
            r2_payload.update({"ok": 200 <= status < 400, "status": status})
        except Exception as exc:  # noqa: BLE001
            r2_payload.update({"ok": False, "error": str(exc)[:200]})
    else:
        r2_payload["ok"] = None  # Not configured — neither ok nor error.

    # 3. Supabase presence (no network probe — auth tokens required).
    supa_payload = {
        "url_set": bool(os.environ.get("SUPABASE_URL")),
        "publishable_set": bool(os.environ.get("SUPABASE_PUBLISHABLE_KEY")),
        "secret_set": bool(os.environ.get("SUPABASE_SECRET_KEY")),
    }

    overall_ok = (
        disk_payload.get("ok") is True
        and (r2_payload.get("ok") is True or r2_payload.get("ok") is None)
    )

    return {
        "status": "ok" if overall_ok else "degraded",
        "disk": disk_payload,
        "r2": r2_payload,
        "supabase_env": supa_payload,
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
        except Exception as inner_exc:  # noqa: BLE001 — defensive default
            # Don't 503 the whole endpoint — DB is reachable, the metadata
            # queries aren't. Surface the detail so the operator can tell
            # the difference between "DB down" and "audit table missing".
            payload["db"] = "ok_no_metadata"
            payload["metadata_error"] = str(inner_exc)
            # Phase 14: still mark DB-up for /metrics even when metadata
            # queries fail (the engine is reachable, that's what matters).
            from app.rms.metrics import set_db_up as _set_db_up

            _set_db_up(True)
        # Happy path: DB is fully healthy — mark the gauge for /metrics.
        from app.rms.metrics import set_db_up as _set_db_up

        _set_db_up(True)
        return payload
    except Exception as exc:  # noqa: BLE001 — defensive default
        from app.rms.metrics import set_db_up as _set_db_up

        _set_db_up(False)
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
def healthz_migrate(request: Request) -> object:
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
    except Exception as exc:  # noqa: BLE001 — defensive default
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
def admin_migrate(request: Request) -> object:
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
    except Exception as exc:  # noqa: BLE001 — defensive default
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


# --- BACKLOG #39 (2026-10-02): backup status + manual backup endpoint ---
#
# `run_backup` was originally only called from the lifespan handler. If the
# app stays up for weeks without restart, no backup ever runs. This
# pair of endpoints exposes backup freshness to UptimeRobot (GET) and
# gives the operator a manual trigger (POST) — matching the existing
# /admin/migrate pattern.
#
# Threshold semantics:
#   - last_backup_at IS NULL           → stale (503)
#   - last_backup_at > 24h ago         → stale (503)
#   - last_backup_at <= 24h ago        → ok (200)
# Both behaviors match the run_backup() gate that already checks
# BACKUP_THRESHOLD_HOURS in app/rms/config.py.


BACKUP_STALE_HOURS = 24  # kept in sync with BACKUP_THRESHOLD_HOURS


@router.get("/healthz/backup", response_model=None)
def healthz_backup(request: Request) -> JSONResponse:
    """Report last successful backup.

    Status:
    - 200: backup ran within BACKUP_STALE_HOURS
    - 503: backup is stale (>24h old) or never ran

    UptimeRobot treats 503 as "down" — operators get paged on stale
    backups the same way they would for any outage. Body includes
    last_backup_at (ISO), stale flag, age_hours, threshold_hours so the
    operator dashboard can render a precise countdown.
    """
    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up", "detail": "App still initializing."},
        )

    raw = _get_last_backup_at(request)
    age_hours: float | None = None
    stale = True  # default: missing = stale

    if raw:
        try:
            last = datetime.fromisoformat(raw)
            now = datetime.now(last.tzinfo) if last.tzinfo else datetime.now()
            age = now - last
            age_hours = round(age.total_seconds() / 3600, 1)
            stale = age_hours > BACKUP_STALE_HOURS
        except ValueError:
            # Unparseable stored date → treat as stale.
            stale = True

    body: dict[str, Any] = {
        "status": "stale" if stale else "ok",
        "last_backup_at": raw,
        "age_hours": age_hours,
        "stale": stale,
        "threshold_hours": BACKUP_STALE_HOURS,
        "hint": (
            "POST /admin/backup to trigger an immediate backup (auth required)."
            if stale
            else None
        ),
    }
    return JSONResponse(
        status_code=503 if stale else 200,
        content=body,
    )


def _run_backup_admin(request: Request):
    """Run run_backup in a fresh session; returns a BackupResult.

    Extracted from admin_backup() so tests can patch it (mocking at
    the request.app.state.session_factory level is more invasive).
    """
    from app.rms.config import DB_PATH

    from app.services.backup_scheduler import run_backup

    with request.app.state.session_factory() as _s:
        return run_backup(_s, DB_PATH)


@router.post("/admin/backup")
def admin_backup(request: Request) -> object:
    """Operator escape hatch: trigger run_backup() now.

    Auth: requires an authenticated admin session (same as /admin/migrate).
    The endpoint runs the backup synchronously (returns when run_backup
    finishes) so the operator gets the result in the response body.
    For long backups, hit this from a script with a generous timeout.

    Returns:
    - 200: {status: backup_complete, local_path, r2_uploaded, r2_key, ...}
    - 401: not logged in
    - 500: a backup step raised (R2 outage, disk full, etc.)
    """
    from app.auth import current_user_id, is_auth_disabled

    # Honor the test bypass — production leaves SASKIA_TEST_AUTH_DISABLED unset.
    user_id = current_user_id(request)
    if user_id is None and not is_auth_disabled():
        return JSONResponse(
            status_code=401,
            content={"error": "authentication_required", "hint": "Login first."},
        )

    try:
        result = _run_backup_admin(request)
    except Exception as exc:  # noqa: BLE001 — defensive default
        logger.exception("admin_backup failed")
        return JSONResponse(
            status_code=500,
            content={"error": "backup_failed", "detail": str(exc)[:500]},
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "backup_complete",
            "local_path": str(result.local_path) if result.local_path else None,
            "r2_uploaded": result.r2_uploaded,
            "r2_key": result.r2_key,
            "local_pruned": result.local_pruned,
            "skipped": result.skipped,
            "reason": result.reason,
        },
    )
