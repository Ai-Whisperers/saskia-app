"""app/auth.py — session-cookie auth (Milestone 1).

Single user, single tenant. Multi-tenant in Milestone 7.

Pattern: Starlette SessionMiddleware + bcrypt password hashing.
- Login form POSTs username/password
- Server verifies bcrypt hash, sets session['user_id']
- Middleware loads user on every request, attaches to request.state
- Logout clears the session
- Session secret loaded from BWS at startup; never committed

Why session cookies over JWT:
- Single user, browser-based → simpler
- No token refresh dance
- Server can invalidate on logout
- bcrypt + signed cookie = standard, well-understood

Why Starlette SessionMiddleware over Flask-Login or roll-our-own:
- Already in our dep tree (FastAPI uses Starlette)
- Signs cookies with itsdangerous (same library, same threat model as JWT)
- ~20 lines of glue vs ~200 lines of custom auth

Reference:
- chatbot-rag-rbac/app/auth.py: API-key pattern we adapted
- https://fastapi.tiangolo.com/advanced/security/http-basic-auth/
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.rms.db_dialect import get_database_url
from app.rms.models import User as SqliteUser  # for tests
from app.rms.schema_postgres import User as PgUser

# --- User model selector (dialect-agnostic) ---


def get_user_model():
    """Return User model matching the active dialect.

    Same class shape (set_password, check_password, etc.) so callers
    don't need to care which dialect is active.
    """
    from app.rms.db_dialect import _is_postgres

    if _is_postgres(get_database_url()):
        return PgUser
    return SqliteUser


# --- Session secret (loaded once at import) ---

SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    # Dev fallback. Production MUST set SESSION_SECRET in env (from BWS).
    # Use a stable-but-not-secret string in dev so cookies survive restarts.
    SESSION_SECRET = os.getenv(
        "DEV_SESSION_SECRET",
        "dev-only-not-secret-replace-in-prod-9f8e7d6c5b4a3920",
    )

# --- Bcrypt helpers (lazy import; bcrypt 5.x changed API surface) ---


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt cost-12. Returns the hash string."""
    import bcrypt

    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verify. Returns False on any error."""
    import bcrypt

    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- Session helpers ---

SESSION_KEY_USER_ID = "user_id"
SESSION_KEY_USERNAME = "username"


def login_user(request: Request, user_id: int, username: str) -> None:
    """Mark the current session as logged in."""
    request.session[SESSION_KEY_USER_ID] = user_id
    request.session[SESSION_KEY_USERNAME] = username


def logout_user(request: Request) -> None:
    """Clear the session."""
    request.session.clear()


def current_user_id(request: Request) -> Optional[int]:
    """Return the current user id from session, or None."""
    return request.session.get(SESSION_KEY_USER_ID)


def require_login(request: Request) -> int:
    """FastAPI dependency: returns user_id if logged in, else raises 401/redirect."""
    user_id = current_user_id(request)
    if user_id is None:
        # For HTML routes, redirect to /login. For API routes, 401.
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": "/login"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user_id


# --- Database session per request ---


def get_db_session(request: Request) -> Session:
    """FastAPI dependency: open a session from app.state.session_factory."""
    return request.app.state.session_factory()


def get_current_user(
    request: Request,
    session: Session = Depends(get_db_session),
) -> object:
    """FastAPI dependency: return the logged-in User, or raise 401."""
    user_id = current_user_id(request)
    if user_id is None:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": "/login"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    User = get_user_model()
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        logout_user(request)
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


__all__ = [
    "SESSION_SECRET",
    "SESSION_KEY_USER_ID",
    "SESSION_KEY_USERNAME",
    "hash_password",
    "verify_password",
    "login_user",
    "logout_user",
    "current_user_id",
    "require_login",
    "get_current_user",
    "get_db_session",
    "get_user_model",
]
