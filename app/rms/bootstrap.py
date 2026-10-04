"""app/rms/bootstrap.py — Idempotent first-boot initialization.

This module runs once at startup (via app.rms.main lifespan) to align the
local DB state with the deployment's environment. The two responsibilities
are:

1. **Password sync from env vars.** If the operator has set
   ``SASKIA_ADMIN_PASSWORD`` or ``SASKIA_USER_PASSWORD`` (typically via
   Bitwarden Secrets / docker-compose), update the corresponding User row's
   ``password_hash`` to match. Idempotent — re-running with the same env
   values is a no-op.

2. **Schema migration kick-off.** Delegates to ``app.rms.db.init_schema``
   which is already idempotent.

Why env vars? Two reasons:

- Production deploys (Render, VPS) inject the password at runtime, so the
  bcrypt hash baked into the image seed doesn't match the runtime secret.
  The fix is to re-hash on boot from the env value.
- Local dev doesn't set the env var, so this code path is a no-op and the
  ``demo``/``demo1234`` seed continues to work.

Reference: AGENTS.md rule #1 (no new deps), rule #11 (no leaked creds).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def _sync_user_password(
    session: Session,
    username: str,
    env_var: str,
    role: str = "admin",
) -> None:
    """If env var is set, ensure the named user's password_hash matches it.

    Behavior:
      - Env var unset → no-op.
      - User missing → create user with that password (first-boot).
      - User exists and password matches → no-op.
      - User exists but password does NOT match → log a one-line INFO and
        update the hash. We never silently overwrite without logging, so
        the operator can audit via deploy logs.
    """
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return

    # Local import to keep bcrypt optional at import time.
    from app.rms.models import User

    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        # First boot — create the user.
        user = User(
            username=username,
            role=role,
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        user.set_password(raw)
        session.add(user)
        log.info(
            "bootstrap: created user %r (role=%s) from %s",
            username,
            role,
            env_var,
        )
        session.commit()
        return

    if not user.check_password(raw):
        user.set_password(raw)
        session.commit()
        log.info(
            "bootstrap: synced password for user %r from %s",
            username,
            env_var,
        )


def run_password_sync(session: Session) -> None:
    """Sync operator passwords from env vars. Idempotent."""
    _sync_user_password(session, "admin", "SASKIA_ADMIN_PASSWORD", role="admin")
    _sync_user_password(session, "demo", "SASKIA_USER_PASSWORD", role="admin")
    # Backwards-compat: legacy "ivan" user
    _sync_user_password(session, "ivan", "SASKIA_IVAN_TEST_PASSWORD", role="admin")


__all__ = ["run_password_sync"]
