"""Migration 123 — SASKIA-226: drop demo cashier users per operator answer §4.5.

Why: Saskia's 2026-10-08 onboarding questionnaire §4.5 ("¿Habrá cajeros
diferentes a vos que usen el sistema?") was answered NO. The seeder
(`app/rms/seed/sazon.py`) still defines CASHIER_USERS = [("lucia", ...),
("diego", ...)] as a placeholder. The seeder's user-creation branch
seeds these accounts on every fresh DB; on a re-seed they are no-ops
(skip-on-existing). The live saskia-vps DB was seeded before the
questionnaire was filled in, so it has the cashier users.

This migration soft-deletes lucia + diego (is_active = 0) and removes
them from CASHIER_USERS so the next seeder run does NOT recreate them.
Soft-delete preserves the row (with audit trail) so a future re-enable
is a one-line UPDATE if Saskia hires a cashier.

Idempotent: UPDATE is a no-op if is_active is already 0. The CASHIER_USERS
edit is in sazon.py (source code), applied on the next deploy.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

DEMO_CASHIERS = ["lucia", "diego"]


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _migration_123_drop_demo_cashiers(conn: Any) -> None:
    """Soft-delete the demo cashier users (lucia, diego).

    - UPDATE sets is_active=0 and updated_at (user table has no
      updated_at, so we just set is_active=0; the row stays as audit).
    - Idempotent: UPDATE matches 0 rows if the users don't exist.
    - Uses username match (not id) so this works on any DB.
    """
    for username in DEMO_CASHIERS:
        conn.execute(
            text(
                "UPDATE user SET is_active = 0 "
                "WHERE username = :u AND is_active = 1"
            ),
            {"u": username},
        )

    # Bump INSIDE this function — each migration owns its own bump.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 123)
