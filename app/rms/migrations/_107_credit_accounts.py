"""Migration 107 (WP Fase 2, 2026-10-07): credit_account + credit_transaction.

Fiado / cuentas por cobrar: línea de crédito por cliente con límite
opcional; ledger firmado (positivo = cargo, negativo = pago/ajuste).
Idempotent via try/except + IF NOT EXISTS (house idiom _103/_104/_105).
Bumps schema_version to 107.
"""

from __future__ import annotations

from typing import Any


def _migration_107_credit_accounts(conn: Any) -> None:
    """Create credit_account + credit_transaction (fiado ledger)."""

    from app.rms.db import atomic_ddl_block
    is_postgres = conn.dialect.name == "postgresql"
    pk = "SERIAL" if is_postgres else "INTEGER"
    ts = "TIMESTAMP" if is_postgres else "DATETIME"
    atomic_ddl_block(conn, [f"""
            CREATE TABLE IF NOT EXISTS credit_account (
                id {pk} NOT NULL PRIMARY KEY,
                customer_id INTEGER NOT NULL UNIQUE REFERENCES customer(id) ON DELETE CASCADE,
                limit_gs INTEGER,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at {ts} NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at {ts}
            )
            """])
    atomic_ddl_block(conn, [f"""
            CREATE TABLE IF NOT EXISTS credit_transaction (
                id {pk} NOT NULL PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES credit_account(id) ON DELETE CASCADE,
                ts {ts} NOT NULL,
                kind VARCHAR(20) NOT NULL,
                amount_gs INTEGER NOT NULL,
                sale_id INTEGER REFERENCES sale(id) ON DELETE SET NULL,
                idem_key VARCHAR(80) UNIQUE,
                note TEXT,
                created_by VARCHAR(120)
            )
            """])
    atomic_ddl_block(conn, ["CREATE INDEX IF NOT EXISTS ix_credit_transaction_account_ts "
            "ON credit_transaction (account_id, ts)"])
    atomic_ddl_block(conn, ["CREATE INDEX IF NOT EXISTS ix_credit_transaction_sale_id "
            "ON credit_transaction (sale_id)"])

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 107)
