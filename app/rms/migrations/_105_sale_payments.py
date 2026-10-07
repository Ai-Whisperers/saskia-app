"""Migration 105 (WP-1.2, 2026-10-07): sale_payment table — pagos mixtos.

Una venta pagada mitad efectivo mitad transferencia. Uniform ledger:
a single-method sale writes exactly ONE sale_payment row (method =
sale.payment_method, amount = line total), so reports never special-case
mixed vs simple. Refund/void deletes the rows with the sale.

Idempotent via try/except + IF NOT EXISTS (house idiom _103/_104).
Bumps schema_version to 105.
"""

from __future__ import annotations

from typing import Any


def _migration_105_sale_payments(conn: Any) -> None:
    is_postgres = conn.dialect.name == "postgresql"
    pk = "SERIAL" if is_postgres else "INTEGER"
    try:
        conn.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS sale_payment (
                id {pk} NOT NULL PRIMARY KEY,
                sale_id INTEGER NOT NULL REFERENCES sale(id) ON DELETE CASCADE,
                method VARCHAR(32) NOT NULL,
                amount_gs INTEGER NOT NULL,
                created_at {"TIMESTAMP" if is_postgres else "DATETIME"} NOT NULL,
                CONSTRAINT ck_sale_payment_amount CHECK (amount_gs >= 0),
                CONSTRAINT ck_sale_payment_method CHECK (
                    method IN ('efectivo','transferencia','qr','tarjeta','otro')
                )
            )
            """
        )
    except Exception:  # noqa: S110 — table may already exist
        pass
    try:
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_sale_payment_sale_id ON sale_payment (sale_id)"
        )
    except Exception:  # noqa: S110
        pass

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 105)
