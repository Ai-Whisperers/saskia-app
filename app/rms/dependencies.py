"""app/rms/dependencies.py — shared FastAPI dependencies.

Routers all need a `Session` for the current request. This module
defines a single `get_session` dependency (13 routers had identical
copies) plus a `get_app_state` for accessing app-level config.

Usage in a router:

    from app.rms.dependencies import get_session

    @router.get("")
    def list_view(request: Request, session: Session = Depends(get_session)):
        ...
"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Session:
    """Yield a SQLAlchemy session bound to the request-scoped engine.

    Identical to the 13 inline copies that used to live in
    app/routers/*.py — consolidated here so any future change
    (e.g. read-replica routing) lives in one place.

    Defensive: if session_factory isn't set yet (server is still initializing
    or running without the lifespan hook), create an ephemeral engine for this
    request to prevent 500 crashes.
    """
    sf = getattr(request.app.state, "session_factory", None)
    if sf is None:
        import os
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SQLASession
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL env var not set")
        engine = create_engine(db_url, pool_pre_ping=True)
        return SQLASession(bind=engine)
    return sf()


def get_app_state(request: Request):
    """Return app.state — for accessing engine, ready flag, etc."""
    return request.app.state


__all__ = ["get_session", "get_app_state"]
