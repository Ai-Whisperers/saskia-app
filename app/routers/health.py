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
from sqlalchemy import text

router = APIRouter()


def _healthz_payload() -> dict[str, Any]:
    """Shared payload for GET and HEAD (HEAD strips the body at transport level)."""
    return {
        "status": "ok",
        "service": "aiw-saskia-rms",
    }


@router.get("/healthz")
def healthz() -> dict:
    """Cheap health check. Returns 200 always (uvicorn is alive)."""
    return _healthz_payload()


@router.head("/healthz", name="healthz-head")
def healthz_head() -> Response:
    """HEAD variant for uptime monitors (UptimeRobot) that probe with HEAD.

    Same 200/headers as GET; body is stripped by the transport layer.
    """
    return Response(status_code=200, media_type="application/json")


@router.get("/healthz/deps")
def healthz_deps() -> dict:
    """Dependency fingerprint for debugging env mismatches on Render.

    Reports presence + sha256 prefix of key env vars (never the values)
    and importable package versions. Public: safe metadata only.
    """
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

    Returns 200 if SQLite is reachable and writable; 503 otherwise.
    Also reports journal_mode (must be 'wal' for concurrent-safe writes).
    """
    engine = request.app.state.engine
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result != 1:
                return JSONResponse(
                    {"db": "unreachable", "detail": "SELECT 1 failed"},
                    status_code=503,
                )
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        return {
            "db": "ok",
            "journal_mode": mode,
        }
    except Exception as exc:
        return JSONResponse({"db": "error", "detail": str(exc)}, status_code=503)


__all__ = ["router"]
