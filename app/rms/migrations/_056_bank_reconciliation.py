"""Migration: Add bank reconciliation fields.

Adds fields to bank_transaction table to track reconciliation status:
- reconciled: boolean (default false)
- reconciled_with_type: 'pedido', 'gasto', 'ingreso', or None
- reconciled_with_id: integer FK reference, or None
- reconciled_at: timestamp of reconciliation
- reconciled_by: user who reconciled or None

Original implementation used ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``,
which works on Postgres / MySQL but is rejected by SQLite (``near
"EXISTS": syntax error``).  Replaced with portable try/except helpers
that read the column list from the connection inspector before issuing
the ALTER — works on every dialect we support (sqlite, postgresql).
"""
from typing import Any

from sqlalchemy import inspect, text

from app.rms.db import _bump_schema_version


def _add_col_if_missing(conn: object, table: str, column: str, ddl: str) -> None:
    """SQLite doesn't support ``ADD COLUMN IF NOT EXISTS``.  Use the
    inspector to read existing columns first and skip when present.
    ``ddl`` is the full column definition (type + defaults) past the
    column name, e.g. ``BOOLEAN DEFAULT 0 NOT NULL``.
    """
    insp = inspect(conn)
    cols = {c["name"] for c in insp.get_columns(table)}
    if column in cols:
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _create_index_if_missing(conn: object, index_name: str, table: str, cols: str) -> None:
    insp = inspect(conn)
    existing = {ix["name"] for ix in insp.get_indexes(table)}
    if index_name in existing:
        return
    conn.execute(text(f"CREATE INDEX {index_name} ON {table}({cols})"))


def _migration_056_bank_reconciliation(conn: Any) -> None:
    """Add reconciliation fields to bank_transaction table.

    Tracks which bank transactions have been matched to:
    - pedidos (orders)
    - gastos (expenses)
    - ingresos (income/sales)
    """
    _add_col_if_missing(conn, "bank_transaction", "reconciled", "BOOLEAN DEFAULT 0 NOT NULL")
    _add_col_if_missing(conn, "bank_transaction", "reconciled_with_type", "VARCHAR(20)")
    _add_col_if_missing(conn, "bank_transaction", "reconciled_with_id", "INTEGER")
    _add_col_if_missing(conn, "bank_transaction", "reconciled_at", "TIMESTAMP")
    _add_col_if_missing(conn, "bank_transaction", "reconciled_by", "VARCHAR(64)")

    _create_index_if_missing(
        conn, "ix_bank_reconciled", "bank_transaction", "reconciled, posted_at"
    )
    _create_index_if_missing(
        conn,
        "ix_bank_reconciled_with",
        "bank_transaction",
        "reconciled_with_type, reconciled_with_id",
    )

    _bump_schema_version(conn, 56)