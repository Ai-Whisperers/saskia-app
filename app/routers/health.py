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
from fastapi.responses import HTMLResponse, JSONResponse, Response
from loguru import logger
from sqlalchemy import text

router = APIRouter()


# --- Dependency-probe helpers (BACKLOG #40) ---


def _disk_usage(path: str) -> Any:
    """Wrapper for shutil.disk_usage — patchable in tests."""
    return shutil.disk_usage(path)


def _get_last_backup_at(request: Request) -> str | None:
    """Read the last_backup_at app_meta row, return ISO string or None.

    BACKLOG #39 (2026-10-02): this helper exposes backup freshness to
    /healthz/backup. Tests patch it to simulate stale / missing states.
    """
    try:
        from sqlalchemy import select

        from app.rms.models import AppMeta

        with request.app.state.session_factory() as s:
            row = s.scalars(
                select(AppMeta).where(AppMeta.key == "last_backup_at")
            ).first()
            return row.value if row else None
    except Exception:  # noqa: BLE001 — defensive default
        # On any DB error we report "no backup" rather than failing the
        # endpoint. The /healthz/db endpoint already surfaces DB issues.
        return None


def _check_supabase_reachable(
    url: str, timeout: float = 2.0
) -> dict[str, Any]:
    """GET the Supabase auth health endpoint. Returns a diagnostic dict.

    The Supabase auth API (GoTrue) only accepts GET on /auth/v1/health
    per its openapi.yaml — HEAD returns 405 Method Not Allowed, which
    is the exact failure the operator dashboard was surfacing for
    weeks. We previously did HEAD, which meant a perfectly healthy
    project would report ok=False in /healthz/summary.

    Return shape:
      ok: bool | "skipped"  (True only on HTTP 2xx)
      http_status: int | None  (HTTP status if a response was received)
      error_class: str | None  (URLError reason / exception class)
      latency_ms: int | None   (round-trip time on success)
      reason: str | None       (operator-readable failure cause)

    Tests patch this function; the return contract is pinned in
    test_healthz_summary.py + test_healthz_deps_depth.py.
    """
    if not url:
        return {"ok": "skipped", "reason": "SUPABASE_URL not set"}
    parsed = urllib.parse.urlparse(url)
    health = f"{parsed.scheme}://{parsed.netloc}/auth/v1/health"
    import time as _time

    t0 = _time.monotonic()
    try:
        req = urllib.request.Request(health, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = int((_time.monotonic() - t0) * 1000)
            ok = 200 <= resp.status < 300
            return {
                "ok": ok,
                "http_status": resp.status,
                "latency_ms": latency_ms,
                "reason": (
                    None
                    if ok
                    else f"HTTP {resp.status} from auth health endpoint"
                ),
            }
    except urllib.error.HTTPError as e:
        # HEAD returned 405 in production; GET can also hit 401/403 if
        # the API key is missing. Surface the actual status.
        latency_ms = int((_time.monotonic() - t0) * 1000)
        return {
            "ok": False,
            "http_status": e.code,
            "latency_ms": latency_ms,
            "error_class": "HTTPError",
            "reason": f"HTTP {e.code} {e.reason}",
        }
    except urllib.error.URLError as e:
        latency_ms = int((_time.monotonic() - t0) * 1000)
        reason_str = str(e.reason) if e.reason else "unknown"
        # Distinguish DNS NXDOMAIN vs connect refused vs SSL error.
        if "Name or service not known" in reason_str or "nodename" in reason_str:
            error_class = "DNSError"
        elif "Connection refused" in reason_str:
            error_class = "ConnectRefused"
        elif "timed out" in reason_str or "timeout" in reason_str.lower():
            error_class = "Timeout"
        elif "SSL" in reason_str or "certificate" in reason_str.lower():
            error_class = "SSLError"
        else:
            error_class = "URLError"
        return {
            "ok": False,
            "http_status": None,
            "latency_ms": latency_ms,
            "error_class": error_class,
            "reason": reason_str[:200],
        }
    except (TimeoutError, OSError) as e:
        latency_ms = int((_time.monotonic() - t0) * 1000)
        return {
            "ok": False,
            "http_status": None,
            "latency_ms": latency_ms,
            "error_class": type(e).__name__,
            "reason": str(e)[:200],
        }


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
        sb_probe = _check_supabase_reachable(sb_env_url, timeout=2.0)
        supabase_block = {
            "ok": sb_probe.get("ok"),
            "url_host": urllib.parse.urlparse(sb_env_url).netloc,
            "http_status": sb_probe.get("http_status"),
            "error_class": sb_probe.get("error_class"),
            "latency_ms": sb_probe.get("latency_ms"),
            "reason": sb_probe.get("reason"),
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


def _summary_check_db(request: Request) -> dict[str, Any]:
    """Compact DB health for /healthz/summary. Patchable in tests."""
    from app.rms.db import (
        CURRENT_SCHEMA_VERSION,
        schema_version,
        schema_version_mismatch,
    )

    engine = request.app.state.engine
    try:
        with engine.connect() as conn:
            ok = conn.execute(text("SELECT 1")).scalar() == 1
            if not ok:
                return {"ok": False, "detail": "SELECT 1 failed"}
            last = conn.execute(
                text("SELECT MAX(occurred_at) FROM audit_log")
            ).scalar()
            actual = schema_version(conn)
            return {
                "ok": True,
                "schema_version": actual,
                "code_schema_version": CURRENT_SCHEMA_VERSION,
                "migrations_pending": schema_version_mismatch(conn),
                "last_audit_at": (
                    last.isoformat() if hasattr(last, "isoformat") else str(last)
                ) if last else None,
            }
    except Exception as exc:  # noqa: BLE001 — defensive default
        return {"ok": False, "detail": str(exc)[:200]}


def _summary_check_errors(request: Request) -> dict[str, Any]:
    """http.500 counts in the last 1h and 24h. Patchable in tests."""
    from datetime import timedelta as _td

    from sqlalchemy import func, select

    from app.rms.config import ASUNCION_TZ
    from app.rms.models import AuditLog

    try:
        now = datetime.now(ASUNCION_TZ)
        with request.app.state.session_factory() as s:
            n_1h = s.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "http.500",
                    AuditLog.occurred_at >= now - _td(hours=1),
                )
            ).scalar() or 0
            n_24h = s.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "http.500",
                    AuditLog.occurred_at >= now - _td(hours=24),
                )
            ).scalar() or 0
        return {"ok": True, "last_1h": int(n_1h), "last_24h": int(n_24h)}
    except Exception as exc:  # noqa: BLE001 — defensive default
        return {"ok": False, "detail": str(exc)[:200]}


def _summary_check_backup(request: Request) -> dict[str, Any]:
    """Last backup age + freshness. Patchable in tests."""
    raw_ts = _get_last_backup_at(request)
    if not raw_ts:
        return {
            "ok": False,
            "last_backup_at": None,
            "age_hours": None,
            "reason": "never",
        }
    try:
        last = datetime.fromisoformat(raw_ts)
        now = datetime.now(last.tzinfo) if last.tzinfo else datetime.now()
        age_hours = round((now - last).total_seconds() / 3600, 1)
        return {
            "ok": age_hours <= BACKUP_STALE_HOURS,
            "last_backup_at": raw_ts,
            "age_hours": age_hours,
            "threshold_hours": BACKUP_STALE_HOURS,
        }
    except ValueError:
        return {"ok": False, "last_backup_at": raw_ts, "reason": "unparseable"}


def _summary_check_deps(request: Request) -> dict[str, Any]:
    """Reachability of Supabase + R2. Patchable in tests.

    Returns {ok, supabase: dict, r2: dict|bool|"skipped"} where each
    inner dict includes the probe class (DNSError / Timeout / HTTPError
    / ConnectRefused / SSLError) and reason. The summary page shows
    those fields when a dep is down — operators stop guessing "why
    is supabase unreachable".
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    if supabase_url:
        sb = _check_supabase_reachable(supabase_url)
    else:
        sb = {"ok": "skipped", "reason": "SUPABASE_URL not set"}
    r2_ok = _check_r2_reachable() if os.environ.get("R2_BUCKET") else "skipped"

    # overall ok: skipped counts as ok; only False is a fail
    sb_overall = sb.get("ok") in (True, "skipped")
    r2_overall = r2_ok in (True, "skipped")
    return {
        "ok": sb_overall and r2_overall,
        "supabase": sb,
        "r2": r2_ok,
    }


def _summary_check_disk(request: Request) -> dict[str, Any]:
    """Disk usage percent. Patchable in tests."""
    from app.rms.config import DB_PATH

    try:
        u = _disk_usage(os.path.dirname(DB_PATH) or ".")
        used_pct = round(u.used / u.total * 100, 1) if u.total else 0.0
        return {
            "ok": used_pct < 90,
            "used_pct": used_pct,
            "free_gb": round(u.free / 1024**3, 1),
        }
    except Exception as exc:  # noqa: BLE001 — defensive default
        return {"ok": False, "detail": str(exc)[:200]}


def _summary_payload(request: Request) -> dict[str, Any]:
    """Aggregate every healthz check into one dict for /healthz/summary.

    Each sub-check is patchable via the helpers above. The overall
    'all_ok' is True only when every check passes.
    """
    ready = bool(getattr(request.app.state, "ready", False))
    if not ready:
        return {"ready": False, "all_ok": False, "checks": {}}

    checks = {
        "db": _summary_check_db(request),
        "errors": _summary_check_errors(request),
        "backup": _summary_check_backup(request),
        "deps": _summary_check_deps(request),
        "disk": _summary_check_disk(request),
    }
    all_ok = all(c.get("ok") for c in checks.values())
    return {"ready": True, "all_ok": all_ok, "checks": checks}


@router.get("/healthz/summary", response_class=HTMLResponse)
def healthz_summary(request: Request) -> HTMLResponse:
    """Operator one-pager: every check with status pill + drill-down.

    Replaces the operator's habit of opening 6 tabs to diagnose a
    failure. Each check links to its full JSON endpoint for the deep
    drill. Public (no PII, no auth) — safe to bookmark.

    Status mapping (for the pill color):
    - ready=False + each sub-check ok=False → red
    - all_ok=True → green
    - otherwise → yellow

    Returns 200 in all cases (the page always loads; the page shows the
    status). The drill-down JSON endpoints still return 503 on actual
    failure so UptimeRobot can alarm.
    """
    from app.services.template_render import render

    payload = _summary_payload(request)
    return render(request, "healthz_summary.html", payload)


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


def _run_backup_admin(request: Request) -> "BackupResult":
    """Run run_backup in a fresh session; returns a BackupResult.

    Extracted from admin_backup() so tests can patch it (mocking at
    the request.app.state.session_factory level is more invasive).
    """
    from app.rms.config import DB_PATH
    from app.services.backup_scheduler import BackupResult, run_backup  # noqa: F401 — used in return-type annotation

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
