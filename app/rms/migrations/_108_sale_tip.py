"""Migration 108 (WP-4.1 propina, 2026-10-07): sale.tip_gs.

Propina por venta (POS botones 5%/10%/monto fijo). El multi-sale la
coloca en la PRIMERA fila de la venta (reportes: SUM(tip_gs)); los
pagos (SalePayment) cubren total + propina, así el arqueo la cuenta
sola vía ledger. Idempotente (column check) + self-bump 108
(house idiom _104.._107).
"""

from __future__ import annotations

from typing import Any


def _migration_108_sale_tip(conn: Any) -> None:
    """Add sale.tip_gs (propina por venta)."""
    def _column_exists() -> bool:
        if conn.dialect.name == "sqlite":
            row = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM pragma_table_info('sale') WHERE name = 'tip_gs'"
            ).scalar()
            return bool(row)
        row = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'sale' AND column_name = 'tip_gs'"
        ).scalar()
        return bool(row)

    if not _column_exists():
        try:
            conn.exec_driver_sql(
                "ALTER TABLE sale ADD COLUMN tip_gs INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:  # noqa: S110 — concurrent migration
            pass

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 108)
