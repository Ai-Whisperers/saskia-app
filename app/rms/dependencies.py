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
    """
    return request.app.state.session_factory()


def get_app_state(request: Request):
    """Return app.state — for accessing engine, ready flag, etc."""
    return request.app.state


__all__ = ["get_session", "get_app_state"]
