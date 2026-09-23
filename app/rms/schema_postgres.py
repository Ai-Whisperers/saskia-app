"""app/rms/schema_postgres.py — Postgres metadata for SQLAlchemy.

This module historically held a separate declarative Base + 9 model
classes (AppMeta, Ingredient, Recipe, RecipeLine, Product, Sale,
SaleStockMove, ImportBatch, User) tuned for Postgres (NUMERIC(12,4) for
quantities, BIGINT for money, TIMESTAMP WITH TIME ZONE for dates,
JSONB for app_meta.value, etc.).

As of 2026-09-23 this file was a STALE 9-model snapshot — missing 25+ new
tables (wishlist_item, risk_item, market_benchmark, delivery_zone,
bank_transaction, settings_kv, recipe_pricing, price_history,
shopping_list_item, production_plan_override, production_plan_template,
production_completion, supplier, waste_log, customer, tag, tag_link,
pedido, pedido_line, audit_log, ingredient_price_event). When the
production lifespan ran `create_all()` with this metadata, the missing
tables were silently skipped — and migrations 28-32 (added after this
file was last touched) couldn't bump schema_version either, because
the UPDATE statements used `value = 'N'` (TEXT) instead of casting
to JSONB on Postgres.

Fix: re-export the canonical `Base` from `app.rms.models`. SQLAlchemy
falls back to portable types when no dialect-specific type is given, so
`Integer` is used on both Postgres (creates INTEGER column) and SQLite.
For the few columns that benefit from Postgres-specific types
(app_meta.value → JSONB), we override via `type_coercion` in db_dialect.py.

This means:
- create_all() on Postgres now sees the FULL schema
- All migrations can run cleanly
- Schema drift detection (/healthz/schema) works correctly

The Postgres-specific types from the original file (NUMERIC(12,4),
JSONB, TIMESTAMP WITH TIME ZONE) are still aspirational but the
production DB already has the correct column types from prior manual
migrations; SQLAlchemy doesn't try to ALTER existing columns on
create_all (it skips them with IF NOT EXISTS semantics).
"""
from __future__ import annotations

# Re-export the full Base from models so Postgres create_all sees all tables.
# This was a separate DeclarativeBase in the old code; the old 9-model
# snapshot is no longer used.
from app.rms.models import Base  # noqa: F401  (re-export)


__all__ = ["Base"]
