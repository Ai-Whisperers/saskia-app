"""Migration 089: Add Ingredient.avg_cost_gs for moving-average cost tracking.

Sprint 4.4 / BACKLOG #13 (2026-10-02): Waste (merma) deducts stock but
does not update the per-ingredient average cost. The latest supplier
price (purchase_price_gs) is used for cost math in analytics, which
silently hides cost drift when supplier prices change mid-batch.

Adds one nullable column:
- ingredient.avg_cost_gs INTEGER — moving-average cost per unit in Gs.

NULL means "not yet computed". Analytics fall back to purchase_price_gs
when this is NULL, so behaviour is unchanged for legacy data.

Backfill: copy purchase_price_gs into avg_cost_gs for existing rows.
This is conservative — it uses the latest supplier price as the
initial "average" rather than leaving everything NULL. From this point
on, waste events keep the column up to date.

Postgres-side: ALTER COLUMN TYPE is not needed (Integer maps to INTEGER
on both dialects).
"""
from typing import Any

from sqlalchemy import text
