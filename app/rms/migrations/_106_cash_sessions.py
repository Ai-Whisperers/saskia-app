"""Migration 106 (WP-1.3, 2026-10-07): cash_session table — arqueo X/Z.

Una sesión de caja = apertura con monto inicial, cierre con conteo
físico. El sistema calcula expected (apertura + pagos en efectivo del
período, vía sale_payment) y diff = counted - expected.

Idempotent via try/except + IF NOT EXISTS (house idiom _103/_104/_105).
Bumps schema_version to 106.
"""

from __future__ import annotations

from typing import Any


def _migration_106_cash_sessions(conn: Any) -> None:
    """Create cash_session table (arqueo de caja X/Z)."""
    is_postgres = conn.dialect.name == "postgresql"
    pk = "SERIAL" if is_postgres else "INTEGER"
    ts = "TIMESTAMP" if is_postgres else "DATETIME"
    try:
        conn.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS cash_session (
                id {pk} NOT NULL PRIMARY KEY,
                opened_at {ts} NOT NULL,
                closed_at {ts},
                opened_by VARCHAR(120) NOT NULL,
                closed_by VARCHAR(120),
                opening_gs INTEGER NOT NULL,
                counted_gs INTEGER,
                expected_gs INTEGER,
                diff_gs INTEGER,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                channel VARCHAR(40),
                note TEXT
            )
            """
        )
    except Exception:
        pass
    try:
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_cash_session_status ON cash_session (status)"
        )
    except Exception:
        pass

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 106)
