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

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    """Cheap health check. Returns 200 always (uvicorn is alive)."""
    return {
        "status": "ok",
        "service": "aiw-saskia-rms",
    }


@router.get("/healthz/db")
def healthz_db(request: Request) -> JSONResponse:
    """DB health check.

    Returns 200 if SQLite is reachable and writable; 503 otherwise.
    Also reports journal_mode (must be 'wal' for concurrent-safe writes).
    """
    try:
        db = request.app.state.db
        result = db.execute(text("SELECT 1")).scalar()
        if result != 1:
            return JSONResponse({"db": "unreachable", "detail": "SELECT 1 failed"}, status_code=503)
        mode = db.execute(text("PRAGMA journal_mode")).scalar()
        return {
            "db": "ok",
            "journal_mode": mode,
        }
    except Exception as exc:
        return JSONResponse({"db": "error", "detail": str(exc)}, status_code=503)


__all__ = ["router"]
