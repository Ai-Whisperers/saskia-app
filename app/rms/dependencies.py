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


def get_session(request: Request) -> object:
    """YIELD a SQLAlchemy session bound to the request-scoped engine.

    Generator dependency: FastAPI runs the code after ``yield`` at request
    teardown, guaranteeing.close() → connection returned to the pool even
    when the handler raises. The previous plain-function version returned
    the Session and NOTHING ever closed it — every route leaked its
    connection until GC (184 routes). Under WAL SQLite this surfaced as
    `database is locked` on the next write from another connection (found
    by tests/e2e shopping flows: add → mark-purchased → unmark).

    Defensive: if session_factory isn't set yet (server is still
    initializing or running without the lifespan hook), create an
    ephemeral engine for this request to prevent 500 crashes during
    cold-start or on pre-lifespan code.
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
        session = SQLASession(bind=engine)
        try:
            yield session
        finally:
            session.close()
            engine.dispose()
        return

    session = sf()
    try:
        yield session
    finally:
        session.close()


def get_app_state(request: Request) -> object:
    """Return app.state — for accessing engine, ready flag, etc."""
    return request.app.state


__all__ = ["get_app_state", "get_session"]
