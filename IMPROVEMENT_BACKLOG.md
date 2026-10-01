# Saskia RMS — Improvement Backlog (Operator-curated)

**Last updated:** 2026-09-22
**Source:** Iván's prioritized list from backend audit + product review

This file tracks every improvement opportunity surfaced across audits, all live in
the code, and operator-ranked. Status is the latest known state.

## Tier 1: P0 — Critical correctness (5 items)

| # | Item | Status | Effort |
|---|---|---|---|
| 1 | Consolidate `sale_stock_move` + `stock_movement` (two parallel tables; reports on `stock_movement` see nothing) | ❌ TODO | M |
| 2 | Add `pedido_sale_stock_move` link so pedido fulfillment is traceable back to specific stock moves | ❌ TODO | M |
| 3 | Move INV-03 clamp from UI to DB: enforce `stock_qty >= 0` at DB level (the UI clamp hides raw negatives from analytics) | ❌ TODO | S |
| 4 | Make migrations truly atomic (Postgres DDL auto-commits — `try/except: pass` on ALTER leaves partial state) | ❌ TODO | M |
| 5 | Add DB-level CHECK on `recipe.yield_qty > 0` (today only Python enforces; raw SQL can insert NULL yield_qty) | ✅ Done 2026-10-01 (migration 028 update triggers + migration 083 INSERT triggers; `tests/test_db_check_constraints.py`) | — |
| 6 | `ON DELETE` policy on `RecipeLine.recipe_id` (deleting a recipe leaves orphans OR cascades and deletes user data — current behavior is unclear) | ❌ TODO | S |

## Tier 2: P0 — Security / data integrity

| # | Item | Status | Effort |
|---|---|---|---|
| 7 | `void_sale` → all money math must use Decimal (12 sites swept this turn; flag for future audits) | ✅ Done 5ce2885 | — |
| 8 | `pedidos_fulfill` idempotency (double-click → double sale + double stock drop) | ✅ Done 5ce2885 | — |
| 9 | No idempotency on `/eod/check` (double-click submits two checklists) | ✅ Done 2026-09-29 (F3 race + AppMeta unique-key reserve in `app/routers/eod.py`) | — |
| 10 | Rate-limit on reads (`/ventas/export.csv` can be scraped 1000×/min, cheap DoS) | ❌ TODO | S |
| 11 | Sentry / error tracking (when /ventas 500s, neither Ivan nor Saskia sees the trace) | ❌ TODO | S |
| 12 | Forward-only migrations — no rollback path (manual write required if 027 breaks) | ❌ TODO | L |

## Tier 3: P1 — Quality / refactoring

| # | Item | Status | Effort |
|---|---|---|---|
| 13 | Waste deducts from stock but doesn't update average cost (rare but possible cost leak) | ❌ TODO | M |
| 14 | Loyalty points dead (`Customer.loyalty_points` field unused) | ❌ TODO | M |
| 15 | Cierre del día doesn't actually mark anything closed — can re-open yesterday | ❌ TODO | M |
| 16 | `/ventas/{id}` standalone HTML view missing (only `/recibo` exists) | ❌ TODO | S |
| 17 | Customer-facing share of recibo (`/p/{token}`) broken per audit | ❌ TODO | M |
| 18 | Consolidate `parse_money_gs` (validation.py) + `parse_gs` (money.py) — duplicate logic | ❌ TODO | S |
| 19 | `RecipeLine.qty` is Float but used in Decimal math (make Numeric) | ❌ TODO | S |
| 20 | Discount math `unit_price * qty - discount` has no overflow check | ❌ TODO | XS |

## Tier 4: P1 — Performance

| # | Item | Status | Effort |
|---|---|---|---|
| 21 | `compute_reorder_list` N+1 (Python loop, 1 query per ingredient) | ❌ TODO | M |
| 22 | Dashboard aggregates 24h sales in Python (should be `GROUP BY hour(sold_at)`) | ❌ TODO | S |
| 23 | `/productos` list runs `cost_gs` per-product via `product_unit_cost_gs()` — N+1 | ❌ TODO | S |
| 24 | `/recetas` list has no pagination | ❌ TODO | S |
| 25 | Missing indexes on hot paths: `Sale.sold_at`, `StockMovement.ingredient_id`, `Pedido.customer_phone` | ❌ TODO | S |

## Tier 5: P2 — Data we have but don't use (high analytics value)

| # | Item | Status | Effort |
|---|---|---|---|
| 26 | `sale_stock_move` (6,177 rows) — analytics on consumption patterns | ❌ TODO | M |
| 27 | `Sale.tz` — recorded per sale, never queried | ❌ TODO | S |
| 28 | `WasteLog.cost_gs` — waste ROI per ingredient | ❌ TODO | M |
| 29 | `ProductionCompletion.completed_qty` — plan accuracy ML | ❌ TODO | L |
| 30 | `AuditLog` — unused for analytics (login IPs, time patterns, operator patterns) | ❌ TODO | L |
| 31 | `PriceHistory` events — 0 rows in live DB, model exists, supplier volatility | ❌ TODO | M |

## Tier 6: P2 — Predictive / ML

| # | Item | Status | Effort |
|---|---|---|---|
| 32 | Predictive restocking: Poisson regression on `sale_stock_move` → "expected consumption next 3 days" | ❌ TODO | L |
| 33 | Plan accuracy dashboard from `ProductionCompletion` | ❌ TODO | M |
| 34 | Waste ROI per ingredient (`WasteLog.cost_gs` ÷ `IngredientPriceEvent` trend) | ❌ TODO | M |
| 35 | Per-customer reorder rate (Sale ↔ Customer over time) | ❌ TODO | M |
| 36 | Time-of-day sales heatmap (Sale.sold_at by hour) | ❌ TODO | M |

## Tier 7: P3 — Supabase / infra

| # | Item | Status | Effort |
|---|---|---|---|
| 37 | No Supabase Storage for product images (URLs to external CDN today) | ❌ TODO | M |
| 38 | No Supabase RLS for multi-tenant readiness (Tenant table exists) | ❌ TODO | L |
| 39 | Render backup runs on app-startup, not on cron | ❌ TODO | M |
| 40 | Healthz depth: ping Supabase + R2 + disk | ❌ TODO | M |

---

## Recently shipped (for reference)

- ✅ Money rule sweep (35+ sites) — 5ce2885
- ✅ Migration 026 SQL escape fix — 5ce2885
- ✅ Migr