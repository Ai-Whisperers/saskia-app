"""Migration: Add bank reconciliation fields.

Adds fields to bank_transaction table to track reconciliation status:
- reconciled: boolean (default false)
- reconciled_with_type: 'pedido', 'gasto', 'ingreso', or None
- reconciled_with_id: integer FK reference, or None
- reconciled_at: timestamp of reconciliation
- reconciled_by: user who reconciled (or None)
"""

from typing import Any

from sqlalchemy import text

from app.rms.db import _bump_schema_version


def _migration_056_bank_reconciliation(conn: Any) -> None:
    """Add reconciliation fields to bank_transaction table.

    Tracks which bank transactions have been matched to:
    - pedidos (orders)
    - gastos (expenses)
    - ingresos (income/sales)
    """
    # Add reconciliation fields to bank_transaction table
    conn.execute(text("""
        ALTER TABLE bank_transaction
        ADD COLUMN IF NOT EXISTS reconciled BOOLEAN DEFAULT 0 NOT NULL
    """))

    conn.execute(text("""
        ALTER TABLE bank_transaction
        ADD COLUMN IF NOT EXISTS reconciled_with_type VARCHAR(20)
    """))

    conn.execute(text("""
        ALTER TABLE bank_transaction
        ADD COLUMN IF NOT EXISTS reconciled_with_id INTEGER
    """))

    conn.execute(text("""
        ALTER TABLE bank_transaction
        ADD COLUMN IF NOT EXISTS reconciled_at TIMESTAMP
    """))

    conn.execute(text("""
        ALTER TABLE bank_transaction
        ADD COLUMN IF NOT EXISTS reconciled_by VARCHAR(64)
    """))

    # Add index for faster queries on reconciliation status
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_bank_reconciled
        ON bank_transaction(reconciled, posted_at)
    """))

    # Add index for matching by type and id
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_bank_reconciled_with
        ON bank_transaction(reconciled_with_type, reconciled_with_id)
    """))

    _bump_schema_version(conn, 56)
