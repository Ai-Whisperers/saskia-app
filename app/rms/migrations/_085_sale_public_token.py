"""Migration 085: Sale.public_token + public_token_expires_at for /r/{token}.

Closes BACKLOG #17 — customer-facing share of recibo. The operator hands
the customer a URL like ``https://sazon-vps.paragu-ai.com/r/{token}`` and
the customer can view the printable digital recibo in their browser
without logging in. Mirrors the /p/{token} pedido-share pattern that was
hardened in migration 067 (P1-2, 2026-09-29).

Why 30 days: long enough to cover typical customer-comes-back-for-receipt
windows (a customer might lose the paper receipt and ask for a digital
copy a week later), short enough that a leaked link has bounded blast
radius. Same number as /p/{token} for operational consistency.

Backfill: existing sales get ``sold_at + 30 days``. Sales that never had
a token get one issued on first /ventas/{id}/share call (the share endpoint
generates a fresh token per call and stores expiry at the same time).

Idempotent: ALTER try/except (matches _067 pattern).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text


def _migration_085_sale_public_token(conn: Any) -> None:
    """Add sale.public_token + sale.public_token_expires_at for /r/{token}.

    Schema bump: 84 → 85. Sale gains two nullable columns + a flag pair so
    the public route can rate-limit / audit + enforce 30-day expiry.
    """
    # Import locally to avoid the circular-import trap: db.py imports this
    # module at top, so any top-level import from db.py would fail.
    from app.rms.db import _bump_schema_version

    # 1. Add public_token column (nullable; only populated when share is called)
    try:
        conn.execute(text("ALTER TABLE sale ADD COLUMN public_token VARCHAR(64)"))
    except Exception:
        pass

    # 2. Add public_token_expires_at column (nullable; matches /p/{token} pattern)
    try:
        conn.execute(text("ALTER TABLE sale ADD COLUMN public_token_expires_at TIMESTAMP"))
    except Exception:
        pass

    # 3. Add public_token_shared_at column — when did the share happen.
    # Used for "Last shared" display on /ventas/{id} and for audit.
    try:
        conn.execute(text("ALTER TABLE sale ADD COLUMN public_token_shared_at TIMESTAMP"))
    except Exception:
        pass

    # 4. Backfill: existing sales get sold_at + 30 days as a one-time grace
    # window. Rows where sold_at is NULL or unparseable fall back to now+30d.
    try:
        rows = conn.execute(
            text("SELECT id, sold_at FROM sale WHERE public_token_expires_at IS NULL")
        ).all()

        now = datetime.now(timezone.utc)
        for row in rows:
            sold = row.sold_at
            expires = now + timedelta(days=30)
            if sold is not None and isinstance(sold, str):
                # SQLite returns datetimes as strings; handle the two common forms.
                normalized = sold.replace("T", " ")
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                    try:
                        parsed = datetime.strptime(normalized, fmt)
                        expires = parsed + timedelta(days=30)
                        break
                    except ValueError:
                        continue
            elif sold is not None:
                # datetime object
                expires = sold + timedelta(days=30)

            conn.execute(
                text("UPDATE sale SET public_token_expires_at = :exp WHERE id = :sid"),
                {"exp": expires, "sid": row.id},
            )
    except Exception:
        pass

    # 5. Index for fast "is this token still valid" lookups.
    try:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_sale_token_expires "
                "ON sale (public_token, public_token_expires_at)"
            )
        )
    except Exception:
        pass

    _bump_schema_version(conn, 85)
