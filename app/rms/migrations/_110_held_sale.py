"""Migration 110 (BACKLOG, 2026-10-07): held_sale table — pause/resume cart.

Allows the cashier to "suspend" an in-progress multi-line cart and
resume it later (e.g., customer steps away to find their wallet, or
operator switches to a different customer mid-order). Inspired by the
Hao0321/pos-pro "掛單" pattern (MIT-licensed): store the full cart
JSON + a free-text label + the cashier identity + held timestamp.

Cart JSON schema (validated at write time):
    {
      "items": [{"product_id": int, "qty": float,
                 "discount_gs": int, "unit_price_gs": int?, ...}, ...],
      "customer_id": int | null,
      "channel": str,
      "payment_method": str,
      "sold_at": str (ISO),
    }

Atomic guarantees:
- INSERT/UPDATE on held_sale is wrapped in the same transaction as
  the cart_json write (no torn state).
- RESUME deletes the held_sale row in the same transaction that loads
  the cart back into the next sale create. If the resume fails, the
  held_sale row is preserved.

Limits (enforced at the service layer, not the DB):
- Max 50 active held_sales per tenant (configurable). Older ones are
  evicted FIFO with an audit row.

Migration is forward-only and idempotent (house idiom from
_103/_104/_105: try/except + IF NOT EXISTS).
"""

from __future__ import annotations

from typing import Any


def _migration_110_held_sale(conn: Any) -> None:
    """Create held_sale table for in-progress cart pause/resume."""
    is_postgres = conn.dialect.name == "postgresql"
    pk = "SERIAL" if is_postgres else "INTEGER"
    ts = "TIMESTAMP" if is_postgres else "DATETIME"
    try:
        conn.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS held_sale (
                id {pk} NOT NULL PRIMARY KEY,
                held_at {ts} NOT NULL,
                held_by VARCHAR(120) NOT NULL,
                label VARCHAR(120) NOT NULL,
                cart_json TEXT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active'
            )
            """
        )
    except Exception:  # noqa: S110 — table may already exist
        pass
    try:
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_held_sale_status ON held_sale (status)"
        )
    except Exception:  # noqa: S110
        pass

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 110)
