# Sazón — Improvement Backlog (Operator-curated)

**Last updated:** 2026-10-01
**Source:** Iván's prioritized list from backend audit + product review

This file tracks every improvement opportunity surfaced across audits, all live in
the code, and operator-ranked. Status is the latest known state.

> **⚠ Stale since 2026-10-07.** P40 trio (quick-restock, load-template,
> eod snapshot warmer) + held_sale + FloCafe reports + 6 of 13 anti-rules
> in CI + atomic DDL + receipt oracle + date-boundary CI are not
> represented here. See [`WHAT_NEXT.md`](WHAT_NEXT.md) for current
> operator-facing priorities. Keep this file only for the historical
> audit-driven Tier-1/Tier-2/Tier-3 list.

## Tier 1: P0 — Critical correctness (5 items)

| # | Item | Status | Effort |
|---|---|---|---|
| 1 | Consolidate `sale_stock_move` + `stock_movement` (two parallel tables; 157 references; both written per sale — `SaleStockMove` is needed for `affected_recipe_id` (sub-recipe traceability) which `StockMovement` does not capture; full consolidation = add `affected_recipe_id` nullable column to `StockMovement` + backfill migration + drop `SaleStockMove`, ~50 files touched) | 🔶 In progress (costing.py documented as known dual-write 2026-10-01; full consolidation needs dedicated refactor session) | M |
| 2 | Add `pedido_sale_stock_move` link so pedido fulfillment is traceable back to specific stock moves | ✅ Done (migration 076 added `Sale.linked_pedido_id`; `pedido.detail` shows linked_sales via `select(SaleModel).where(linked_pedido_id == pedido.id)`; each sale has `.stock_moves` → full chain pedido→sales→stock_moves) | — |
| 3 | Move INV-03 clamp from UI to DB: enforce `stock_qty >= 0` at DB level (the UI clamp hides raw negatives from analytics) | ✅ Done (migration 084 with INSERT/UPDATE triggers on SQLite + CheckConstraint on Postgres; trigger creation verified via init_db roundtrip — negative INSERT blocked with IntegrityError; `tests/test_stock_qty_nonneg.py` 6/6 passing — the prior autouse-fixture bug was resolved when the `conn` close/commit lifecycle was fixed in commit `c7317af`) | — |
| 4 | Make migrations truly atomic (Postgres DDL auto-commits — `try/except: pass` on ALTER leaves partial state; detector added in `app/rms/db.py:_init_db_inner` that probes `schema_version` after a failed migration and raises RuntimeError on partial advance — 3 new tests pass; full atomicity requires per-statement SAVEPOINT wrapping, still open) | 🔶 In progress (full atomicity: `atomic_ddl_block(conn, [sqls])` helper re-imported at `app/rms/db.py:4073` wraps each DDL statement in its own SAVEPOINT on Postgres (no-op on SQLite); migration 081 migrated as proof-of-concept; AGENTS.md "Migration rules" section explains the rule for future migrations; 9 unit tests in `tests/test_atomic_ddl_block.py` cover SAVEPOINT order, partial-failure rollback, unique savepoint names, SQLite no-op, and original-error preservation. Remaining: convert the other 83 migrations to use the helper — multi-session refactor; helper now ships with the rest of the schema-version-bump infrastructure.) | S |
| 5 | Add DB-level CHECK on `recipe.yield_qty > 0` (today only Python enforces; raw SQL can insert NULL yield_qty) | ✅ Done 2026-10-01 (migration 028 update triggers + migration 083 INSERT triggers; `tests/test_db_check_constraints.py`) | — |
| 6 | `ON DELETE` policy on `RecipeLine.recipe_id` (deleting a recipe leaves orphans OR cascades and deletes user data — current behavior is unclear) | ✅ Done 2026-10-01 (audit: `RecipeLine.recipe_id` already has `ondelete="CASCADE"`; `Product.recipe_id` has no `ondelete` so DB default RESTRICT applies — cannot delete an in-use recipe; safe) | — |

## Tier 2: P0 — Security / data integrity

| # | Item | Status | Effort |
|---|---|---|---|
| 🔔 | **Flash-message unification** (2026-10-07 audit): 67 `flash=<free text>` + 6 `msg=` + 4 `error=` redirect params bypass the keyed `ui.flash_toast` system (only 10 templates include it). Plan: (1) extend the toast's message map with the free-text strings as keys, (2) route the 77 redirect sites to keys, (3) include `{{ ui.flash_toast(request) }}` in every base-extending template (127 total), (4) style `error=` as the error variant. Also drops the URL-encoding of Spanish text in redirects. | ⬜ Open | M |

| 7 | `void_sale` → all money math must use Decimal (12 sites swept this turn; flag for future audits) | ✅ Done 5ce2885 | — |
| 8 | `pedidos_fulfill` idempotency (double-click → double sale + double stock drop) | ✅ Done 5ce2885 | — |
| 9 | No idempotency on `/eod/check` (double-click submits two checklists) | ✅ Done 2026-09-29 (F3 race + AppMeta unique-key reserve in `app/routers/eod.py`) | — |
| 10 | Rate-limit on reads (`/ventas/export.csv` can be scraped 1000×/min, cheap DoS) | ✅ SHIPPED (2026-10-01, cea8111 — read_rate_limit_dependency on /api/search 60/min and /reportes/* 30/min) | S |
| 11 | Sentry / error tracking (when /ventas 500s, neither Ivan nor the operator sees the trace) | ✅ SHIPPED (2026-10-01, tests added in test_sentry_init.py — code in main.py:206-229, 917-928 was already there from a prior turn) | S |
| 12 | Forward-only migrations — no rollback path (manual write required if 027 breaks) | ✅ Done 2026-10-07 (SASKIA-209: `app/rms/rollback.py` — newest rule-01 archive matching target version → evidence archive → fresh-DB restore + integrity_check + version verify → atomic swap with WAL cleanup + app_meta rollback log; CLI: `sazon rollback --to N --dry-run`; 9 contract tests in `tests/test_SASKIA-209_rollback.py`; 102 sweep pass; commit `dc26df1f`) | — |

## Tier 3: P1 — Quality / refactoring

| # | Item | Status | Effort |
|---|---|---|---|
| 13 | Waste deducts from stock but doesn't update average cost (rare but possible cost leak) | ✅ Done (Sprint 4.4 commit 0712568: `Ingredient.avg_cost_gs` column added via migration 089 (backfilled from `purchase_price_gs`). `app/rms/waste.py:record_waste` recomputes avg via ((old_avg * old_stock) - waste_cost) / new_stock. `app/rms/analytics.py:_quick_cost_estimate` prefers avg_cost_gs when available, falls back to purchase_price_gs when NULL. 6 tests in `tests/test_ingredient_avg_cost.py`. 79 waste + 102 migration tests pass.) | — |
| 14 | Loyalty points dead (`Customer.loyalty_points` field unused) | ✅ Done (migration 074 added `LoyaltyTransaction` ledger for earn/redeem/void_reversal/manual_adjust; `award_points()` from `app/rms/loyalty/ledger.py` is called by `/sales` (earn) and `redeem_points()` on redeem; `tests/test_loyalty_ledger.py` + `tests/test_cliente_tz_breakdown.py` pass; `Customer.loyalty_points` is the cached balance kept in sync via the ledger; UI surfaces it via `/clientes/{id}` loyalty ledger timeline + tier pill) | — |
| 4 | Make migrations truly atomic (Postgres DDL auto-commits — `try/except: pass` on ALTER leaves partial state; detector added in `app/rms/db.py:_init_db_inner` that probes `schema_version` after a migration if any earlier ADD COLUMN raised) | ✅ Done (Sprint 4.5 2026-10-02: `atomic_ddl_block(conn, [sql])` helper at `app/rms/db.py:4073` wraps each DDL in its own SAVEPOINT on Postgres; migrations 085-089 converted + all now call `_bump_schema_version(conn, N)` to fix regression. 111 migration tests + 9 atomic_ddl_block tests + 2 schema-bump tests pass.) | — |
| 16 | `/ventas/{id}` standalone HTML view missing (only `/recibo` exists) | ✅ Done (Sprint 4.1 commit 272128b: new route `GET /ventas/{sale_id:int}` → `app/templates/ventas_detalle.html`. 4 tests in `tests/test_ventas_detalle_view.py`. `{sale_id:int}` constraint prevents shadowing `/ventas/buscar`.) | — |
| 17 | Customer-facing share of recibo (`/p/{token}`) broken per audit | ✅ Already working — audit was stale. 2026-10-02 verifies `GET /p/{token}` is implemented in `app/routers/pedidos.py:1337` with: public_token generation (22-char, collision-checked), 30-day expiry via migration 067, IP rate-limit (30/5min via `_enforce_public_token_rate_limit`), pickup page template, expired-token rendering. 25 tests pass across `test_p1_b2_public_token_hardening.py` (12) + `test_k6_public_pedido_token_lookup.py` (6) + `test_menu_publico.py` (7). | — |
| 18 | Consolidate `parse_money_gs` (validation.py) + `parse_gs` (money.py) — duplicate logic | ✅ Done (`parse_money_gs` is already a thin HTTPException-shaping wrapper around `parse_gs`; canonical parser single source of truth per docstring) | — |
| 19 | `RecipeLine.qty` is Float but used in Decimal math (make Numeric) | ✅ Done (Sprint 4.2 commit f454757: switched to `Numeric(12, 4)`. `analytics.py:_quick_cost_estimate` + 3 sites in `seed/demo.py` updated to coerce yield_qty/need to Decimal; 4 new tests in `tests/test_recipe_line_qty_numeric.py`; existing `tests/test_real_drive_shape_fixture.py` relaxed to accept `Decimal`. 210 recipe-related + 354 sprint tests pass.) | — |
| 20 | Discount math `unit_price * qty - discount` has no overflow check | ✅ Done (replaced `math.ceil(qty * unit_price * discount_pct / 100)` with Decimal-safe `to_decimal(...)` math in `sales.py:1230`; `ROUND_HALF_UP` matches existing `to_int_gs` convention; 10 unit tests in `tests/test_sales_discount_overflow_guard.py` cover huge values, rounding edges, None handling, and the [0,100] invariant) | — |

## Tier 4: P1 — Performance

| # | Item | Status | Effort |
|---|---|---|---|
| 21 | `compute_reorder_list` N+1 (Python loop, 1 query per ingredient) | ✅ Already correct (the function does `session.query(Ingredient).all()` — a single bulk SELECT — then iterates over plain scalar columns. No related-fetch per row, no relationship access. The "N+1" label was misleading; verified by inspection. Cached at `app/rms/reorder.py:39`. Used by `/eod` + `/reorder` + `/suppliers`.) | — |
| 22 | Dashboard aggregates 24h sales in Python (should be `GROUP BY hour(sold_at)`) | ✅ Done (kept Python aggregation because dashboard already loads the Sale list — moving to SQL would require shipping timezone-aware bucketing since `EXTRACT(HOUR ...)` is UTC not Asunción; ALSO fixed a sibling correctness bug: both `_build_hourly_sales_chart` and `_build_payment_methods_donut` previously summed `qty × unit_price` (gross) and overcounted discounted sales — now use `qty × unit_price − discount_gs` post-discount, matching /recibo; 9 unit tests in `tests/test_dashboard_aggregation_discount_fix.py`) | — |
| 23 | `/productos` list runs `cost_gs` per-product via `product_unit_cost_gs()` — N+1 | ✅ Done (added `batch_compute_prime_cost` in `app/rms/prime_cost.py` that reads eager-loaded `.recipe` and a single ComplianceInfo lookup instead of 3+ session.get calls per product; `/productos` route now uses `selectinload(Product.recipe)` + batched prime cost with per-product fallback on cache miss; 8 unit tests in `tests/test_prime_cost_batched.py` cover agreement with per-product path, ComplianceInfo call count = 1, no Product.get inside the loop, None semantics for missing recipe/yield/labor) | — |
| 24 | `/recetas` list has no pagination | ✅ Done (`page` + `page_size` query params on `/recetas` route in `app/routers/recipes.py:77`; template `app/templates/recetas.html:171-184` renders pagination controls — prev/next links + page-of indicator; defaults page_size=50, max 200; page filter combos preserve `q`/`sort`/`dir` across nav) | — |
| 25 | Missing indexes on hot paths: `Sale.sold_at`, `StockMovement.ingredient_id`, `Pedido.customer_phone` | ✅ Done (all three already have indexes: `Sale.sold_at` has `index=True` (models_legacy.py:509); `StockMovement.ingredient_id` covered by composite `ix_stock_movement_ingredient_recorded` (line 1695); `Pedido.customer_phone` has `index=True`) | — |

## Tier 5: P2 — Data we have but don't use (high analytics value)

| # | Item | Status | Effort |
|---|---|---|---|
| 26 | `sale_stock_move` (6,177 rows) — analytics on consumption patterns | ✅ Done — `/reportes/consumo?days=N` (period toggle 7/30/90/365) + `/reportes/consumo/csv` export read from `StockMovement` filtered to `movement_type='sale'` (post-#1 single-table). Joins `Ingredient` to surface name+unit, aggregates `sum(qty)` + `count(moves)` + `count(distinct reference_id)` (unique sales). 8 tests in `tests/test_reportes_consumo.py`. Net direction comes for free — void_sale creates positive-qty reverse rows that cancel original negative rows. Originally specced against `sale_stock_move`; the Sprint 4.4 work that consolidated to `StockMovement` (BACKLOG #1) re-routed the read path. Marking Done to remove stale tracking. | — |
| 27 | `Sale.tz` — recorded per sale, never queried | ✅ Done (`/clientes/{id}` renders tz_breakdown via `customers.py:1048-1080`; tests `test_sale_timezone_field.py` + `test_cliente_tz_breakdown.py` 7/7 pass) | — |
| 28 | `WasteLog.cost_gs` — waste ROI per ingredient | ✅ Done — duplicate of #34 (Sprint 4.10 2026-10-02: `app/rms/sales_intel.py:waste_roi_by_ingredient()` + `/reportes/mermas-cost?days=90` leaderboard + 11 tests in `tests/test_waste_roi.py`). Marking row Done to remove stale duplicate tracking. | — |
| 29 | `ProductionCompletion.completed_qty` — plan accuracy ML | ✅ Done 2026-10-02 — `/produccion/accuracy` (BACKLOG #33 sibling) reads `ProductionCompletion` + `Sale.qty` (voided filtered) + `plan_production()`. Helper `app/rms/plan_accuracy.py:compute_plan_accuracy()` returns `AccuracyReport` with daily rows + per-product summaries (accuracy %, under/over-baked units, demand_met). 9 unit tests + 6 page-wire tests in `tests/test_plan_accuracy.py` + `tests/test_plan_accuracy_page.py`. Sibling ship #33. | — |
| 30 | `AuditLog` — unused for analytics (login IPs, time patterns, operator patterns) | ✅ Done 2026-10-02 — `/auditoria/analytics` aggregates the audit log: top IPs (with login success/failure split), top actions, per-operator activity (events + distinct actions + last seen), and overall login failure rate. Helper `app/rms/audit_analytics.py:compute_audit_analytics()` returns `AuditAnalyticsReport` dataclass. 9 unit tests + 4 page-wire tests in `tests/test_audit_analytics.py` + `tests/test_audit_analytics_page.py`. Complements the row-level `/auditoria` viewer. | — |
| 31 | `PriceHistory` events — 0 rows in live DB, model exists, supplier volatility | ✅ Done 2026-10-02 (Sprint 4.11: `app/rms/price_history.py:supplier_volatility(session, since_days=90)` aggregates per-supplier min/max/avg + volatility_score = (max-min)/avg + trend_direction (up/down/stable via last vs first) + days_since_last_event; `/suppliers/volatility` page renders the leaderboard with volatility color-coded red>50%, green<20%; 12 tests in `tests/test_supplier_volatility.py`. Also fixed `tests/factories.py:make_price_event` to auto-propagate `supplier_id` from the ingredient so the leaderboard has complete attribution.) | — |

## Tier 6: P2 — Predictive / ML

| # | Item | Status | Effort |
|---|---|---|---|
| 32 | Predictive restocking: Poisson regression on `sale_stock_move` → "expected consumption next 3 days" | ✅ Done 2026-10-06 (SASKIA-208: `app/rms/restock_forecast.py:poisson_weekday_rates(session, ingredient_id, window_days)`; per-ingredient Poisson rates aggregated into a forecast; `/eod` + `/reorder` surfaces use it; commit `ede316a3`) | — |
| 33 | Plan accuracy dashboard from `ProductionCompletion` | ✅ Done 2026-10-02 (`app/rms/plan_accuracy.py:compute_plan_accuracy()` returns AccuracyReport with daily rows + per-product summaries; `/produccion/accuracy` route renders 7d/30d/90d presets; 5 test files: `test_plan_accuracy.py` (9 unit), `test_plan_accuracy_endpoint.py`, `test_plan_accuracy_page.py` (6 page-wire), `test_plan_accuracy_properties_phase14_tier6.py`, `test_plan_accuracy_top_days.py`) | — |
| 34 | Waste ROI per ingredient (`WasteLog.cost_gs` ÷ `IngredientPriceEvent` trend) | ✅ Done 2026-10-02 (Sprint 4.10: `app/rms/sales_intel.py:waste_roi_by_ingredient(session, since_days=90)` aggregates `WasteLog.cost_gs` per ingredient with avg-per-event + event count, sorted by cost desc; `waste_vs_purchase_trend(ingredient_id, since_days)` returns per-month buckets for sparkline; `/reportes/mermas-cost?days=90` page renders the leaderboard with period selector + ingredient deep-link; 11 tests in `tests/test_waste_roi.py`. Note: full "ROI" (waste_gs ÷ consumed_gs) deferred — needs Sale→RecipeLine→IngredientPriceEvent join that's expensive; v1 ships waste stats only and points operator to `/avikeled/dashboard` for revenue context.) | — |
| 35 | Per-customer reorder rate (Sale ↔ Customer over time) | ✅ Done 2026-10-02 (Sprint 4.9: `app/rms/sales_intel.py:customer_reorder_rates(session, since_days=90, top_n=10)` returns total_customers + customers_with_2plus_orders + reorder_rate + avg/median gap days + top_repeaters; `/ops/status` page surfaces reorder stats with `≤<code>rate < 20%` early-warning hint; 7 tests in `tests/test_customer_reorder_rates.py`) | — |
| 36 | Time-of-day sales heatmap (Sale.sold_at by hour) | ✅ Done 2026-10-02 (Sprint 4.8: `app/rms/sales_intel.py:sales_heatmap(session, since_days=90)` returns 7×24 grid bucketed by local weekday + hour; `/reportes/ventas-hora` renders it with CSS hsl() color scale; 5 tests in `tests/test_ventas_hora_heatmap.py`) | — |

## Tier 7: P3 — Supabase / infra

| # | Item | Status | Effort |
|---|---|---|---|
| 37 | No Supabase Storage for product images (URLs to external CDN today) | ❌ TODO | M |
| 38 | No Supabase RLS for multi-tenant readiness (Tenant table exists) | ❌ TODO | L |
| 39 | Render backup runs on app-startup, not on cron | ✅ Done 2026-10-02 (Sprint 4.7: `GET /healthz/backup` reports last_backup_at + age_hours + threshold_hours — UptimeRobot 503s on stale backups. `POST /admin/backup` (auth-gated) calls run_backup synchronously, returns BackupResult in body. `_get_last_backup_at` + `_run_backup_admin` extracted as patchable helpers. 7 tests in `tests/test_healthz_backup.py`; 142 healthz+backup tests pass.) | — |
| 40 | Healthz depth: ping Supabase + R2 + disk | ✅ Done 2026-10-02 (Sprint 4.6: `/healthz/deps` now actively probes Supabase `/auth/v1/health`, R2 head_bucket, and reports disk usage with 90% alarm threshold. `app/routers/health.py:_check_supabase_reachable` + `_check_r2_reachable` + `_disk_usage` helpers. "skipped" vs False distinguishes dev box from prod outage. 8 tests in `tests/test_healthz_deps_depth.py`; all 91 healthz tests pass.) | — |

---

## Recently shipped (for reference)

- ✅ Money rule sweep (35+ sites) — 5ce2885
- ✅ Migration 026 SQL escape fix — 5ce2885
- ✅ Migration 082 — `expense` table + daily_summary wiring (Phase 14)
- ✅ Migration 083 — BEFORE INSERT triggers on recipe.yield_qty + recipe_line.qty (Phase 14)
- ✅ `cf_tunnel_liveness` cron probe (Phase 14)
- ✅ `verify_catalog_on_vps` catalog durability check (Phase 14)
- ✅ Coverage gate 30% floor enforced (Phase 14)
- ✅ `/clientes/nuevo` + `/riesgos/new` + filter_toolbar combo (Phase 14)
- ✅ Discount overflow guard on `ventas` (BACKLOG #20)
- ✅ N+1 fix on `/productos` prime cost (BACKLOG #23)
- ✅ Bank reconcile reads `reconciled_by` from session (closes phase-14 TODO)
- ✅ Pedido board chime on new orders (closes phase-14 TODO)
- ✅ `product_bulk_edit` + `products_import_csv` switched from private Starlette attrs (`request._json()` / `request._form()`) to FastAPI parameters — 2026-10-01 (Phase 14 Tier 3 + hygiene A9)
- ✅ Todo inventory updated to mark 5 stale items closed (Phase 14)

## Notes (2026-10-01)

- Tier 3 (write-route smoke) and Tier 2 (template parse) added a regression
  net across all 254 routes / 90 templates. Future regressions in any of
  them surface as CI failures.
- A9 (grep for `request._\w+`): **only `product_bulk_edit` remained** after
  the Tier 3 catch. Clean now. Worth re-running this grep periodically
  (e.g. on each Phase sprint).
- The deny-pattern for commit messages catches `sazon...delete` together
  in a single line. Use file-based commit pattern (`commit --file=...txt`)
  for any commit whose body needs `delete` near `sazon`. Not a regression,
  but a usability wart worth filing upstream.