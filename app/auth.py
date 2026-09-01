"""app/auth.py — auth abstraction layer.

Single user, single tenant (Milestone 7 adds multi-tenant).

Two backends supported:
1. **Supabase Auth** (preferred when SUPABASE_URL is set) — managed
   email/password, JWT validation, password reset flow
2. **Self-built bcrypt** (fallback for local dev / tests) — own user
   table, bcrypt password hashing

Both backends store the session in a server-side encrypted cookie
(Starlette SessionMiddleware). The public API of this module
(get_current_user, require_login, login_user, logout_user) is the
same for both backends.

Why Supabase Auth when available:
- Email-based password reset out of the box (vs. building + sending
  email ourselves)
- Bcrypt cost handled by Supabase
- JWT validation against Supabase's JWKS (cached locally, ~5ms)
- User metadata lives in Supabase; we keep our own User table only
  for app-level metadata (last_login_at, etc.)

Why we still own the session cookie:
- Tokens never touch the browser JS (XSS protection)
- Same SessionMiddleware pattern for both backends; routes don't
  change
- Logout is instant (cookie cleared) without waiting for Supabase

Reference:
- https://supabase.com/docs/reference/python/auth-getuser
- https://supabase.com/docs/guides/auth/jwts
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

# Re-export the session secret config (used by SessionMiddleware in main.py)
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    SESSION_SECRET = os.getenv(
        "DEV_SESSION_SECRET",
        "dev-only-not-secret-replace-in-prod-9f8e7d6c5b4a3920",
    )


# --- Backend detection ---


def _supabase_enabled() -> bool:
    """True if Supabase Auth is configured."""
    from app.auth_supabase import is_supabase_auth_enabled

    return is_supabase_auth_enabled()


def using_supabase() -> bool:
    """Public check: is this deployment using Supabase Auth?"""
    return _supabase_enabled()


# --- Self-built bcrypt backend (used when Supabase not configured) ---


# Lazy bcrypt import (5.x changed API surface)
def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt cost-12."""
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


# --- User model selector (dialect-agnostic, bcrypt path only) ---


def get_user_model():
    """Return User model matching the active dialect (bcrypt backend only).

    With Supabase Auth, user metadata lives in Supabase — not in our DB.
    """
    from app.rms.db_dialect import _is_postgres

    if _is_postgres(os.getenv("DATABASE_URL", "")):
        from app.rms.schema_postgres import User as PgUser

        return PgUser
    from app.rms.models import User as SqliteUser

    return SqliteUser


# --- Session helpers (dispatch to backend) ---

# Local-bcrypt session keys
LOCAL_SESSION_KEY_USER_ID = "local_user_id"
LOCAL_SESSION_KEY_USERNAME = "local_username"


def login_user_local(request: Request, user_id, username: str) -> None:
    """Bcrypt backend: store user_id + username in session."""
    request.session[LOCAL_SESSION_KEY_USER_ID] = user_id
    request.session[LOCAL_SESSION_KEY_USERNAME] = username


def login_user(request: Request, user_id, username: str) -> None:
    """Dispatch to whichever backend is configured."""
    if _supabase_enabled():
        # The Supabase login flow happens in routers/auth.py via
        # auth_supabase.sign_in_with_password, not here. This function
        # is for the bcrypt flow only.
        return
    login_user_local(request, user_id, username)


def logout_user(request: Request) -> None:
    """Clear session regardless of backend."""
    if _supabase_enabled():
        from app.auth_supabase import clear_session

        clear_session(request)
        return
    request.session.clear()


def current_user_id(request: Request) -> Optional[int]:
    """Return the current user identifier, or None.

    For bcrypt backend: returns the integer user_id (from ORM).
    For Supabase backend: returns the user UUID string.

    Mixed return type is intentional — callers should treat it as an
    opaque identifier and use get_current_user() for the full User.
    """
    if _supabase_enabled():
        from app.auth_supabase import SESSION_KEY_USER_ID

        return request.session.get(SESSION_KEY_USER_ID)
    return request.session.get(LOCAL_SESSION_KEY_USER_ID)


def require_login(request: Request):
    """FastAPI dependency: returns user_id if logged in, else raises 401/redirect."""
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
    return user_id


# --- Database session per request ---


def get_db_session(request: Request) -> Session:
    """FastAPI dependency: open a session from app.state.session_factory."""
    return request.app.state.session_factory()


def get_current_user(
    request: Request,
    session: Session = Depends(get_db_session),
):
    """FastAPI dependency: return the logged-in User, or raise 401.

    For Supabase backend: returns a SupabaseUser (id + email + claims).
    For bcrypt backend: returns the ORM User row.
    """
    if _supabase_enabled():
        from app.auth_supabase import get_session_user

        user = get_session_user(request)
        if user is None:
            _redirect_to_login(request)
        return user

    # Bcrypt backend
    user_id = current_user_id(request)
    if user_id is None:
        _redirect_to_login(request)

    User = get_user_model()
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        logout_user(request)
        _redirect_to_login(request)
    return user


def _redirect_to_login(request: Request) -> None:
    """Internal: raise the appropriate redirect/401 for the request type."""
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


__all__ = [
    "SESSION_SECRET",
    "using_supabase",
    "hash_password",
    "verify_password",
    "get_user_model",
    "login_user",
    "login_user_local",
    "logout_user",
    "current_user_id",
    "require_login",
    "get_db_session",
    "get_current_user",
]
