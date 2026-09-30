"""Migration 063: Add competitor_price_observation table (market-intel evidence layer).

Background: the research repo saskia-market-intel collects verified
competitor retail prices (cartas online, 48+ locales PY, corte 2026-09-30).
MarketPriceReference covers INGREDIENTS; this table stores retail
PRODUCT observations from third parties so /vs-mercado can show
"our price vs family p25/median/p75" backed by sourced evidence.

Companion: app/rms/seed_competitor_prices.py (86 curated observations,
idempotent seed) and routes /vs-mercado/evidencia + /vs-mercado/importar.

Idempotent: CREATE TABLE IF NOT EXISTS (dialect-neutral types valid on
SQLite and Postgres — init_db create_all also creates it via the model).
"""

from typing import Any

from sqlalchemy import text

from app.rms.db import _bump_schema_version


def _migration_063_competitor_price_observation(conn: Any) -> None:
    try:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS competitor_price_observation (
                    id INTEGER PRIMARY KEY,
                    competitor_name VARCHAR(120) NOT NULL,
                    competitor_type VARCHAR(32),
                    city VARCHAR(64),
                    product_name VARCHAR(160) NOT NULL,
                    family VARCHAR(24),
                    unit VARCHAR(16) NOT NULL DEFAULT 'unidad',
                    price_gs INTEGER NOT NULL,
                    as_of DATE NOT NULL,
                    source TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    CONSTRAINT ck_cpo_price_positive CHECK (price_gs > 0)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_cpo_family_unit_asof "
                "ON competitor_price_observation (family, unit, as_of)"
            )
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_cpo_as_of ON competitor_price_observation (as_of)")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_cpo_competitor_name "
                "ON competitor_price_observation (competitor_name)"
            )
        )
    except Exception:  # noqa: BLE001, S110 — table may already exist
        pass

    _bump_schema_version(conn, 63)
