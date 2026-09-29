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
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.orm import Session

# Re-export the session secret config (used by SessionMiddleware in main.py)
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    SESSION_SECRET = os.getenv(
        "DEV_SESSION_SECRET",
        "dev-only-not-secret-replace-in-prod-9f8e7d6c5b4a3920",
    )


# --- Backend detection ---


@lru_cache(maxsize=1)
def _supabase_enabled() -> bool:
    """True if Supabase Auth is configured. Cached — env vars don't change at runtime."""
    from app.auth_supabase import is_supabase_auth_enabled

    return is_supabase_auth_enabled()


@lru_cache(maxsize=1)
def using_supabase() -> bool:
    """Public check: is this deployment using Supabase Auth? Cached — env vars don't change at runtime."""
    return _supabase_enabled()


def is_auth_disabled() -> bool:
    """Test bypass: conftest sets this to True so the gate is skipped.

    Always False in production. Used by the auth-requiring routers via
    `require_login` → `require_login_or_disabled`. Lets us ship the gate
    without breaking the existing 280+ tests that don't pre-login.
    """
    import os

    return os.getenv("SASKIA_TEST_AUTH_DISABLED", "").lower() in ("1", "true", "yes")


# --- Self-built bcrypt backend (used when Supabase not configured) ---


# Lazy bcrypt import (5.x changed API surface)
def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt cost-12."""
    import bcrypt

    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verify. Returns False on any error.

    Backwards-compatible contract: never raises, returns False on any
    failure (wrong password, malformed hash, bcrypt internal error).
    Use `verify_password_or_raise` if you need to distinguish corruption
    from bad-password at the call site.
    """
    try:
        return _verify_password_unsafe(plain, hashed)
    except (ValueError, TypeError):
        return False


def verify_password_or_raise(plain: str, hashed: str) -> bool:
    """Same as verify_password but propagates ValueError/TypeError.

    Use this when the caller needs to distinguish:
      - False return → wrong password (user error, normal flow)
      - ValueError  → malformed hash (DB corruption, schema drift)
      - TypeError   → wrong argument types (caller bug)

    Operators using this for forensics should log the exception so
    a corrupted-hash incident is visible in logs.
    """
    return _verify_password_unsafe(plain, hashed)


def _verify_password_unsafe(plain: str, hashed: str) -> bool:
    """Bcrypt verify. Raises on any error."""
    import bcrypt

    if not hashed:
        # Treat empty hash as a corruption signal — ValueError so callers
        # using verify_password_or_raise can distinguish from wrong-password.
        raise ValueError("Empty hash")
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# --- User model selector (dialect-agnostic, bcrypt path only) ---


def get_user_model() -> object:
    """Return User model matching the active dialect (bcrypt backend only).

    With Supabase Auth, user metadata lives in Supabase — not in our DB.
    """

    # schema_postgres re-exports the canonical Base (2026-09-23 refactor),
    # so both dialects use the same User model now.
    from app.rms.models import User

    return User


# --- Session helpers (dispatch to backend) ---

# Local-bcrypt session keys
LOCAL_SESSION_KEY_USER_ID = "local_user_id"
LOCAL_SESSION_KEY_USERNAME = "local_username"


def login_user_local(request: Request, user_id: object, username: str) -> None:
    """Bcrypt backend: store user_id + username in session."""
    request.session[LOCAL_SESSION_KEY_USER_ID] = user_id
    request.session[LOCAL_SESSION_KEY_USERNAME] = username


def login_user(request: Request, user_id: object, username: str) -> None:
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


def require_login(request: Request) -> object:
    """FastAPI dependency: returns user_id if logged in, else raises 401/redirect.

    Production auth gate. Always enforced (no bypass).
    """
    user_id = current_user_id(request)
    if user_id is None:
        ip = request.client.host if request.client else "?"
        logger.warning(
            "auth_required_denied path={} method={} ip={}",
            request.url.path, request.method, ip,
        )
        # HTML clients get a 303 redirect to /login (preserves the
        # "user navigated and got bounced" UX). API clients get a
        # structured 401 JSON payload with reason_code header.
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": "/login"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Necesitás iniciar sesión para acceder.",
                "reason": "unauthenticated",
                "path": request.url.path,
                "ip": ip,
            },
            headers={"X-Reason-Code": "unauthenticated"},
        )
    return user_id


def require_login_or_disabled(request: Request) -> object:
    """FastAPI dependency: enforces auth UNLESS the test bypass is on.

    Routers use this instead of `require_login` so tests can opt out of
    auth without monkey-patching the dependency tree. Set the env var
    `SASKIA_TEST_AUTH_DISABLED=1` to bypass.

    Production: env var is never set, so this behaves exactly like
    `require_login` — full security gate.
    """
    if is_auth_disabled():
        # Return a fake user; tests don't care about identity for
        # protected-route smoke tests.
        from app.auth_supabase import SupabaseUser

        return SupabaseUser(
            id="test-user",
            email="test@example.com",
            role="authenticated",
            raw_claims={},
        )
    return require_login(request)


# --- Database session per request ---


def get_db_session(request: Request) -> Session:
    """FastAPI dependency: open a session from app.state.session_factory.

    Defensive: if session_factory isn't set yet (server is still initializing
    or running without the lifespan hook), create a ephemeral engine for this
    request. This prevents 500 crashes during cold-start or on pre-lifespan code.
    """
    sf = getattr(request.app.state, "session_factory", None)
    if sf is None:
        # Server is still starting or running old code without lifespan.
        # Create an ephemeral engine just for this request — no pooling, no persist.
        import os

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SQLASession
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL env var not set")
        engine = create_engine(db_url, pool_pre_ping=True)
        return SQLASession(bind=engine)
    return sf()


def get_current_user(
    request: Request,
    session: Session = Depends(get_db_session),
) -> object:
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
    "current_user_id",
    "get_current_user",
    "get_db_session",
    "get_user_model",
    "hash_password",
    "is_auth_disabled",
    "login_user",
    "login_user_local",
    "logout_user",
    "require_login",
    "require_login_or_disabled",
    "using_supabase",
    "verify_password",
]
