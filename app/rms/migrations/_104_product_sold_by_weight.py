"""Migration 104 (WP-1.1, 2026-10-07): product.sold_by_weight.

Venta por peso: panaderías/comedores-kilo venden 0.5 kg de chipa.
Sale.qty is already Float; this flag gates fractional qty on the
multi-sale POS route (SALES-VAL-003 integer rule stays for discrete
goods) and switches the POS cart row to a kg input.

Idempotent: dialect-aware ADD COLUMN with try/except (matches the
_103 house idiom). Bumps schema_version to 104 at the end.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def _migration_104_product_sold_by_weight(conn: Any) -> None:
    """Add product.sold_by_weight (venta por peso, qty fraccional)."""
    is_postgres = conn.dialect.name == "postgresql"
    try:
        if is_postgres:
            conn.execute(
                text(
                    "ALTER TABLE product "
                    "ADD COLUMN IF NOT EXISTS sold_by_weight BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
        else:
            conn.execute(
                text("ALTER TABLE product ADD COLUMN sold_by_weight BOOLEAN NOT NULL DEFAULT 0")
            )
    except Exception:
        pass

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 104)
