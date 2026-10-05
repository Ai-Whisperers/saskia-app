"""Migration 098 (Part 2): customer_phone table for multi-phone customers.

Phase 16 (2026-10-02): A single customer may have many phones: their
own mobile, a work line, a WhatsApp-only number, the spouse's phone,
etc. Today's Customer has a single `phone` column which forces the
cashier to keep overwriting it.

RECOVERED from origin/feat/phase-3-m1-product-detail on 2026-10-05.
Same recovery context as 098_production_closed_day: the migration
ran on the prod DB while the source was lost during a rebase. This
file restores the source. Both this and _098_production_closed_day
share the schema_version 98; whichever ran first on prod is fine —
the other is a no-op CREATE TABLE IF NOT EXISTS.

Idempotent: CREATE TABLE IF NOT EXISTS + NOT EXISTS backfill.
"""
from datetime import datetime, timezone
from typing import Any

from loguru import logger


def _migration_098_customer_phone(conn: Any) -> None:
    ts = datetime.now(timezone.utc).isoformat()

    if conn.dialect.name == "sqlite":
        create_sql = """
            CREATE TABLE IF NOT EXISTS customer_phone (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
                phone VARCHAR(32) NOT NULL,
                kind VARCHAR(16) NOT NULL DEFAULT 'mobile',
                label VARCHAR(48),
                is_default BOOLEAN NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT ck_customer_phone_kind CHECK (
                    kind IN ('mobile','whatsapp','work','home','other')
                )
            )
        """
    else:  # postgres
        create_sql = """
            CREATE TABLE IF NOT EXISTS customer_phone (
                id SERIAL NOT NULL PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
                phone VARCHAR(32) NOT NULL,
                kind VARCHAR(16) NOT NULL DEFAULT 'mobile',
                label VARCHAR(48),
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                CONSTRAINT ck_customer_phone_kind CHECK (
                    kind IN ('mobile','whatsapp','work','home','other')
                )
            )
        """

    try:
        conn.exec_driver_sql(create_sql)
    except Exception as exc:  # noqa: BLE001
        logger.debug("migration 098 CREATE TABLE customer_phone skipped: %s", exc)

    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS ix_customer_phone_customer_id "
            "ON customer_phone (customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_customer_phone_customer_default "
            "ON customer_phone (customer_id, is_default)",
        "CREATE INDEX IF NOT EXISTS ix_customer_phone_phone "
            "ON customer_phone (phone)",
    ):
        try:
            conn.exec_driver_sql(idx_sql)
        except Exception as exc:  # noqa: BLE001
            logger.debug("migration 098 index skipped: %s", exc)

    # Backfill: every customer with non-empty `phone` gets one default row.
    # Idempotent via NOT EXISTS — re-runs no-op.
    try:
        conn.exec_driver_sql(
            """
            INSERT INTO customer_phone
                (customer_id, phone, kind, label, is_default, is_active,
                 sort_order, created_at, updated_at)
            SELECT
                c.id,
                c.phone,
                'mobile',
                'Personal',
                1,
                1,
                0,
                :ts,
                :ts
            FROM customer c
            WHERE c.phone IS NOT NULL AND TRIM(c.phone) != ''
              AND NOT EXISTS (
                  SELECT 1 FROM customer_phone p
                  WHERE p.customer_id = c.id
              )
            """,
            {"ts": ts},
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("migration 098 backfill skipped: %s", exc)

    # Schema-version bump is the responsibility of
    # _098_production_closed_day (the first 098 to register). This
    # migration is intentionally a no-op on the schema version since
    # both 098s share version 98.
