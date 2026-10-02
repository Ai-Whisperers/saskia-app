"""Phase 16 (2026-10-02): Multiple phones per customer.

Research (WhatsApp Business API multi-device, MercadoLibre PY contact
phone, Uber Delivery receiver phone) — a single customer may have many
phones: their own mobile, a work line, a WhatsApp-only number, the
spouse's phone, etc. Today's Customer has a single `phone` column
which forces the cashier to keep overwriting it.

This migration creates `customer_phone` (1:N from customer) with the
fields the cashier / delivery dispatcher actually need:

  phone (VARCHAR(32) — keeps '+' and ' ' for readability)
  kind (mobile / whatsapp / work / home / other)
  is_default (used by prefill)
  is_active (soft-disable, never hard-delete audit history)
  label (operator-facing "Línea personal", "WhatsApp", "Oficina")
  sort_order

Backfill: every customer with non-empty `phone` gets a "Personal"
default row. Idempotent via NOT EXISTS.
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

    from app.rms.db import _bump_schema_version
    _bump_schema_version(conn, 98)
