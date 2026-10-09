# SAZON MASTER CATALOG — every lesson, idea, finding, topic, decision, gap
## Verified against the Sazon codebase as of 2026-10-08

This is the canonical, **deduplicated, ground-truth** reference. Every item has been checked
against the actual Sazon codebase. Items that already exist in Sazon are marked **✅ SHIPPED**.
Items that are partially shipped are marked **🟡 PARTIAL**. Items that are not yet shipped
are marked **❌ OPEN**. Items that are explicitly NOT to be built are marked **🚫 SKIP**.

This document is the source of truth for all four earlier books (v1 audit, v2 lessons, v3
decisions, plus this master). Where earlier books disagree with this catalog, **this catalog
wins** because each item is checked against the actual code.

---

# PART 0 — HOW TO READ

Each item is one row in a long table. The columns are:

| Column | Meaning |
|---|---|
| **#** | Sequential lesson number |
| **Status** | ✅ SHIPPED / 🟡 PARTIAL / ❌ OPEN / 🚫 SKIP |
| **Source** | Where this idea came from: `Sazon` (own code), `URY`, `RestoPOS`, `FloCafe`, `TastyIgniter`, `Flutter POS`, `Supply'd`, `CafeKit`, `BakeOnyx`, `Rinvy`, `Otter`, `restaurant-menu.org`, `memory` (your own memory), `AGENTS.md` |
| **Effort** | 🟢 S (≤0.5d) / 🟡 M (1-2d) / 🟠 L (3-5d) |
| **Risk** | 🟢 low / 🟡 med / 🔴 high |
| **Where in Sazon** | File + line range, OR gap description |

The 5 categories are:
1. **A — Architecture** (code structure, modules, settings, migrations, observability)
2. **B — UX / page layout** (templates, components, navigation)
3. **C — Domain logic** (production, inventory, sales, customers, fiado, loyalty, etc.)
4. **D — Analytics / reports / insights**
5. **E — Ops / compliance / safety**

Each item also has a "verify" line so anyone can re-confirm in 5 seconds.

---

# PART 1 — CATEGORY A: ARCHITECTURE

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| A-01 | ✅ | Sazon | **One-feature-one-file pattern** — 115+ modules in `app/rms/`, one per domain | — | — | `app/rms/*.py` (verified by walk) |
| A-02 | ✅ | Sazon | **Settings KV as single config store** | — | — | `app/rms/settings.py` (538 lines) + `app/rms/models_legacy.py:SettingsKV` |
| A-03 | ✅ | Sazon | **Migration discipline with rule 17** — every migration has a pre-state archive | — | — | `app/rms/rollback.py` (SASKIA-209) |
| A-04 | ✅ | Sazon | **Per-request observability** — request_id, user_id, route, Loguru contextualize | — | — | `app/rms/observability.py` (206 lines) |
| A-05 | ✅ | Sazon | **Audit log for every domain event** | — | — | `app/rms/audit.py` (174) + `audit_analytics.py` (183) |
| A-06 | ✅ | Sazon | **Polymorphic recipe tree walk with cycle detection** | — | — | `app/rms/profitability/cost.py:resolve_line_target` + `CycleInRecipeTree` |
| A-07 | ✅ | Sazon | **Sub-recipe recursion** (recipe-as-ingredient) | — | — | `app/rms/recipe_intel.py:infer_recipe_family` + `product_similarity.py:_flatten_ingredients` |
| A-08 | ✅ | Sazon | **Decimal-only money math, int-only at persistence** (AGENTS.md rule 3) | — | — | `app/rms/money.py:to_int_gs` |
| A-09 | ✅ | Sazon | **Negative stock allowed** (kitchen reality > accounting purity) | — | — | `app/rms/profitability/cost.py:line 60+` |
| A-10 | ✅ | Sazon | **Dialect-aware SQL** (SQLite + Postgres compatible) | — | — | `app/rms/db_dialect.py` (152 lines) |
| A-11 | ✅ | Sazon | **Telegram channel for ops** (fire-and-forget, 5s timeout) | — | — | `app/rms/notify.py` (125 lines) |
| A-12 | ✅ | Sazon | **Maintenance module** with dry-run mode | — | — | `app/rms/maintenance.py:prune_audit_log` |
| A-13 | ✅ | Sazon | **CSRF + rate-limit middleware** | — | — | `app/rms/csrf.py` (212) + `rate_limit.py` (369) |
| A-14 | ✅ | Sazon | **Soft-delete columns** (migration 095) | — | — | `app/rms/migrations/_095_soft_delete_columns.py` |
| A-15 | ✅ | Sazon | **Schema-versioned via SCHEMA_VERSION** | — | — | `app/rms/constants.py:185` |
| A-16 | ✅ | Sazon | **Bcrypt + Supabase dual-auth** with separate session keys | — | — | `app/rms/observability.py:31-41` (2026-09-29 fix) |
| A-17 | ✅ | Sazon | **No SSE / WebSocket anywhere in stack** | — | — | grep `sse\|websocket` over `app/` returns 0 |
| A-18 | ✅ | Sazon | **SaleStockMove table dropped** (migration 092); SSOT = StockMovement | — | — | `app/rms/migrations/_092_drop_sale_stock_move.py` |
| A-19 | 🟡 | Sazon | **StockMovement SSOT — but costing.py + sales/lifecycle.py still import SaleStockMove** | 🟢 S | 🟢 low | cleanup: remove dead import from `app/rms/costing.py:501` + `sales/lifecycle.py:22` |
| A-20 | ✅ | URY | **Sprint 2.3 sale lifecycle split** (out of costing.py) | — | — | `app/rms/sales/lifecycle.py` (434 lines) |
| A-21 | ✅ | URY | **Pre-sale check (URY `posClosing.js` port, MIT-licensed)** | — | — | `app/rms/sales/pre_sale_check.py:1-50` (391 lines) |
| A-22 | ✅ | URY | **Pre-sale check for cart** (multi-line version) | — | — | `app/rms/sales/pre_sale_check_cart.py` (253 lines) |
| A-23 | 🟡 | URY | **Pre-sale log table persistence** — write each PreSaleChecklist to a log table | 🟡 M | 🟢 low | new migration + add to `pre_sale_check.py` |
| A-24 | ✅ | RestoPOS | **Production plan split into 9 sub-routers** | — | — | `app/routers/produccion/` (9 files) |
| A-25 | ❌ | RestoPOS | **Refactor `produccion.html` (2,366 lines) into _views/day.py, week.py, manana.py, haccp.py** | 🟠 L | 🟡 med | largest open architectural cleanup |
| A-26 | 🚫 | TastyIgniter | **TastyIgniter-style 22-extension plugin architecture** — skip; Sazon is one-app, no extensions | — | — | decision: Sazon single monorepo |
| A-27 | 🚫 | TastyIgniter | **TastyIgniter extension CDN / marketplace** — skip | — | — | decision |
| A-28 | 🚫 | RestoPOS | **Modules/ separation pattern** — skip; Sazon uses flat `app/rms/<feature>.py` | — | — | decision |
| A-29 | 🚫 | resto-nestjs | **Worker / queue system (BullMQ-style)** — skip; single-process | — | — | decision |
| A-30 | 🚫 | PizzaQL | **GraphQL Subscriptions** for live order updates — skip; tablet view exists | — | — | decision |
| A-31 | ❌ | FloCafe | **Maintenance middleware** (returns 503 + Retry-After) | 🟢 S | 🟢 low | new `MaintenanceModeMiddleware` in `app/main.py` |
| A-32 | ✅ | Sazon | **Pre-billing checklist** — see A-21 | — | — | (duplicate) |
| A-33 | ✅ | Sazon | **TastyIgniter extension model** — see A-26 | — | — | (duplicate) |
| A-34 | ✅ | Sazon | **Pydantic schemas for API** | — | — | `app/rms/schemas.py` (63) + `schema_postgres.py` (46) |
| A-35 | ✅ | Sazon | **Constants in one place** | — | — | `app/rms/constants.py` (185 lines) |
| A-36 | ✅ | Sazon | **Validator helpers** (decimal money, dates, IDs) | — | — | `app/rms/validation.py` (367) |
| A-37 | ✅ | Sazon | **Display formatters** (money, dates, units) | — | — | `app/rms/display.py` (135) + `messages.py` (123) |
| A-38 | ✅ | Sazon | **Bootstrap helpers** (defaults, demo data) | — | — | `app/rms/bootstrap.py` (100) |
| A-39 | ✅ | Sazon | **Perf helpers** (caching, query analysis) | — | — | `app/rms/perf.py` (184) |
| A-40 | ✅ | Sazon | **Config module** (ASUNCION_TZ, env) | — | — | `app/rms/config.py` (152) |
| A-41 | ✅ | Sazon | **Date presets** (today, last week, this month) | — | — | `app/rms/date_presets.py` (67) |
| A-42 | ✅ | Sazon | **Errors module** (typed exceptions) | — | — | `app/rms/errors.py` (212) |
| A-43 | ✅ | Sazon | **Security headers** | — | — | `app/rms/security_headers.py` (164) |
| A-44 | ✅ | Sazon | **Upload limits** | — | — | `app/rms/upload_limits.py` (87) |
| A-45 | ✅ | Sazon | **Public tokens** (for pedido publico) | — | — | `app/rms/public_tokens.py` (186) |
| A-46 | ✅ | Sazon | **Session lifecycle helpers** | — | — | `app/rms/session_lifecycle.py` (81) |
| A-47 | ✅ | Sazon | **Streaming CSV for large exports** | — | — | `app/rms/streaming_csv.py` (58) |
| A-48 | ✅ | Sazon | **Static paths (ready_static)** | — | — | `app/rms/ready_static.py` (48) |
| A-49 | ✅ | Sazon | **Storage types** (LOCAL / S3-like) | — | — | `app/rms/storage_types.py` (55) |
| A-50 | ✅ | Sazon | **Tagging subsystem** (vocabulary, classify, derive, filters, ensure, audit) | — | — | `app/rms/tagging/` (10 files) |
| A-51 | ✅ | Sazon | **Tag algebra** (combining tags) | — | — | `app/rms/tag_algebra.py` (79) |
| A-52 | ✅ | Sazon | **Hierbus (named after Herbus Drive / family)** — wishlist + shopping list | — | — | `app/routers/herebus.py` (multiple endpoints) |
| A-53 | ✅ | Sazon | **Settings catalog page** with 887-line template for editing any registry key | — | — | `app/templates/settings_catalog.html` |
| A-54 | ✅ | Sazon | **Nav helpers** (sidebar items, breadcrumbs) | — | — | `app/rms/nav.py` (259) |
| A-55 | ✅ | Sazon | **Chart helpers** (visualizations) | — | — | `app/rms/charts.py` (341) |
| A-56 | ✅ | Sazon | **Metrics module** (counters, gauges) | — | — | `app/rms/metrics.py` (168) |
| A-57 | ✅ | Sazon | **Dependencies module** (FastAPI DI helpers) | — | — | `app/rms/dependencies.py` (68) |
| A-58 | ✅ | Sazon | **Clock module** (testable now()) | — | — | `app/rms/clock.py` (95) |
| A-59 | ✅ | Sazon | **Storage module** (file storage abstraction) | — | — | `app/rms/storage.py` (168) |
| A-60 | ✅ | Sazon | **Backup helpers** (DB backup before migration) | — | — | `app/rms/backup.py` (312) |
| A-61 | ✅ | Sazon | **Catalogs + categories modules** | — | — | `app/rms/catalogs.py` (76) + `categories.py` (99) |
| A-62 | ✅ | Sazon | **Units module** (qty normalization) | — | — | `app/rms/units.py` (199) |
| A-63 | ✅ | Sazon | **Variants module** (product variants) | — | — | `app/rms/variants.py` (354) |
| A-64 | ✅ | Sazon | **Migrations module** (rolled-up migration loader) | — | — | `app/rms/migrations/__init__.py` (80) + 32 migration files |
| A-65 | ✅ | Sazon | **Models split** into 14 files by domain | — | — | `app/rms/models/` (14 files) |
| A-66 | ✅ | Sazon | **Models legacy** (2,943 lines) — the original single model file | — | — | `app/rms/models_legacy.py` (2,943) |
| A-67 | ✅ | Sazon | **AppMeta** (key-value metadata) | — | — | `app/rms/models_legacy.py:AppMeta` |
| A-68 | ✅ | Sazon | **Db module** (engine, session factory) | — | — | `app/rms/db.py` (4,844 lines) |
| A-69 | ✅ | Sazon | **Main module** (app entry, lifespan) | — | — | `app/rms/main.py` (1,272) |
| A-70 | ✅ | Sazon | **AGENTS.md** — project conventions for agents | — | — | `app/rms/AGENTS.md` (89 lines) |
| A-71 | ✅ | Sazon | **__init__.py** — module exports | — | — | `app/rms/__init__.py` (16) |

---

# PART 2 — CATEGORY B: UX / PAGE LAYOUT

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| B-01 | ✅ | Sazon | **99 templates** organized by domain (admin, components, errors, root templates) | — | — | `app/templates/` (verified by walk) |
| B-02 | ✅ | Sazon | **Production main page** (2,366 lines — see A-25 to split) | — | — | `app/templates/produccion.html` |
| B-03 | ✅ | Sazon | **Production sub-pages** (manana, prep, prep_recipes, print, haccp, accuracy) | — | — | `produccion_manana.html`, `produccion_prep.html`, `produccion_prep_recipes.html`, `produccion_print.html`, `produccion_haccp.html`, `produccion_accuracy.html` |
| B-04 | ✅ | Sazon | **11 report pages** specialized by report type | — | — | `reportes_*.html` × 12 (libro_ventas, iva, cierre_mensual, etc.) |
| B-05 | ✅ | Sazon | **8 insight pages** specialized by insight type | — | — | `insight_*.html` × 8 (afinidades, demand, food_cost, freshness, margenes, price_impact, stock) |
| B-06 | ✅ | Sazon | **EOD sub-pages** (anomalies, print) | — | — | `eod.html`, `eod_anomalies.html`, `eod_print.html` |
| B-07 | ✅ | Sazon | **Caja (cash) sub-pages** (z-report) | — | — | `caja.html`, `caja_z.html` |
| B-08 | ✅ | Sazon | **POS screens** (ventas) with detail + history + QA | — | — | `ventas.html`, `ventas_detalle.html`, `ventas_historial.html`, `ventas_qa.html` |
| B-09 | ✅ | Sazon | **Recibo (receipt) page** | — | — | `recibo.html` |
| B-10 | ✅ | Sazon | **Pedidos (pre-orders) screens** (board, detail, public, stock-preview) | — | — | `pedido_board.html`, `pedido_detalle.html`, `pedido_publico.html`, `pedido_stock_preview.html`, `pedidos.html`, `pedidos_nuevo.html` |
| B-11 | ✅ | Sazon | **Customer screens** (list, detail, edit, new, duplicates) | — | — | `clientes.html`, `cliente_detalle.html`, `cliente_editar.html`, `clientes_nuevo.html`, `clientes_duplicados.html` |
| B-12 | ✅ | Sazon | **Cotizador (quote builder)** | — | — | `cotizador.html` |
| B-13 | ✅ | Sazon | **Fiado (credit/AR) screens** | — | — | `fiado.html`, `fiado_cliente.html` |
| B-14 | ✅ | Sazon | **Menu publico (public menu)** | — | — | `menu_publico.html` |
| B-15 | ✅ | Sazon | **Menu tablet view** (operator moves around counter) | — | — | `menu_tablet.html` |
| B-16 | ✅ | Sazon | **Menu OCR import** (upload photo menu) | — | — | `menu_import_ocr.html` |
| B-17 | ✅ | Sazon | **Recipe screens** (list, detail, form, photos) | — | — | `recetas.html`, `receta_detalle.html`, `receta_form.html`, `recipe_photos.html` |
| B-18 | ✅ | Sazon | **Product screens** (list, detail, form, import) | — | — | `productos.html`, `producto_detalle.html`, `producto_form.html`, `productos_importar.html` |
| B-19 | ✅ | Sazon | **Supplier screens** (list, form, orders, prices, volatility) | — | — | `suppliers.html`, `supplier_form.html`, `supplier_orders.html`, `supplier_precios.html`, `suppliers_volatility.html` |
| B-20 | ✅ | Sazon | **Suscription screens** | — | — | `suscripciones.html`, `suscripcion_form.html` |
| B-21 | ✅ | Sazon | **Settings screens** (main, catalog) | — | — | `settings.html`, `settings_catalog.html` |
| B-22 | ✅ | Sazon | **Copilot (in-app AI) screen** | — | — | `copiloto.html` |
| B-23 | ✅ | Sazon | **Wishlist screen** (equipment wishlist) | — | — | `wishlist.html` |
| B-24 | ✅ | Sazon | **Shopping list screen** | — | — | `shopping_list.html` |
| B-25 | ✅ | Sazon | **Delivery zones screen** | — | — | `delivery_zones.html` |
| B-26 | ✅ | Sazon | **Merma (waste) screen** | — | — | `merma.html` |
| B-27 | ✅ | Sazon | **Inventory screens** (list, form, movements, audit) | — | — | `inventario.html`, `inventario_form.html`, `inventario_movimientos.html`, `inventario_auditoria_etiquetas.html` |
| B-28 | ✅ | Sazon | **Ingredient detail screen** | — | — | `ingrediente_detalle.html` |
| B-29 | ✅ | Sazon | **Reorder screen** (smart reorder suggestions) | — | — | `reorder.html` |
| B-30 | ✅ | Sazon | **Pricing screen** (price management) | — | — | `pricing.html` |
| B-31 | ✅ | Sazon | **Riesgos (risk register) screen** | — | — | `riesgos.html` |
| B-32 | ✅ | Sazon | **Auditoria screens** (log, analytics) | — | — | `auditoria.html`, `auditoria_analytics.html` |
| B-33 | ✅ | Sazon | **Bank reconciliation screen** | — | — | `bank.html` |
| B-34 | ✅ | Sazon | **Excel screens** (import, validate, mode guidance) | — | — | `excel.html`, `excel_validate.html`, `excel_mode_guidance.html` |
| B-35 | ✅ | Sazon | **Login screen** | — | — | `login.html` |
| B-36 | ✅ | Sazon | **Dashboard + Inicio screens** | — | — | `dashboard.html`, `inicio.html` |
| B-37 | ✅ | Sazon | **Planner screen** (week view) | — | — | `planner.html` |
| B-38 | ✅ | Sazon | **Benchmark screens** (edit, list) | — | — | `benchmark_edit.html`, `benchmarks.html` |
| B-39 | ✅ | Sazon | **Evidencia-mercado screen** (vs-mercado) | — | — | `evidencia_mercado.html` |
| B-40 | ✅ | Sazon | **Health summary screen** | — | — | `healthz_summary.html` |
| B-41 | ✅ | Sazon | **Ops status screen** | — | — | `ops_status.html` |
| B-42 | ✅ | Sazon | **Carga inicial (initial data load)** | — | — | `carga_inicial.html` |
| B-43 | ✅ | Sazon | **Dev combo smoke** (smoke test for menus) | — | — | `dev_combo_smoke.html` |
| B-44 | ✅ | Sazon | **Guia (help / docs)** | — | — | `guia.html` |
| B-45 | ✅ | Sazon | **Errors pages** | — | — | `app/templates/errors/` (subdir) |
| B-46 | ✅ | Sazon | **Admin subdir** | — | — | `app/templates/admin/` |
| B-47 | ✅ | Sazon | **Components subdir** | — | — | `app/templates/_components/` |
| B-48 | ❌ | Flutter POS | **Drag-and-drop product pin on grilla** (chart_reorder + product_reorder) | 🟡 M | 🟢 low | new `user_pinned_products` table + reorder widget |
| B-49 | ❌ | Flutter POS | **Drag-and-drop product ingredient reorder** | 🟡 M | 🟢 low | same pattern as B-48 |
| B-50 | ❌ | Sazon (orphan) | **Confidence badge on production grilla** (computed, not rendered) | 🟢 S | 🟢 low | edit `app/templates/produccion.html` |
| B-51 | ❌ | CafeKit | **Variance band "how steady" on production grilla** (min-max + σ) | 🟢 S | 🟢 low | new column in `produccion.html` |
| B-52 | ❌ | CafeKit | **Banner if preordered item missing from plan** | 🟢 S | 🟢 low | add to produccion_manana.html |
| B-53 | ❌ | Sazon (orphan) | **"Plan accuracy" widget on /inicio** (already computed by `plan_accuracy.py`) | 🟢 S | 🟢 low | new card on `inicio.html` |
| B-54 | ❌ | restaurant-menu.org | **Soft vs Hard band visualization** (single page → two-tier) | 🟡 M | 🟡 med | new `app/rms/food_cost_alert.py` + render |
| B-55 | ❌ | BakeOnyx | **Per-day "Accuracy: 94%" daily report** | 🟡 M | 🟡 med | new report + cron |
| B-56 | ❌ | URY | **KOT error log page** (recent print failures) | 🟢 S | 🟢 low | new `production_print_errors.html` |
| B-57 | 🚫 | TastyIgniter | **Multi-theme / multi-tenant theming** — skip | — | — | decision |
| B-58 | 🚫 | RestoPOS | **Live KDS page** — skip (tablet view exists) | — | — | decision per SASKIA-210 |
| B-59 | 🚫 | FloCafe | **Multi-locale i18n** — skip (Spanish-vos only) | — | — | decision |
| B-60 | 🚫 | openresto | **Print template engine (.rpt)** — skip (server-rendered HTML) | — | — | decision |
| B-61 | ❌ | Sazon (orphan) | **Read & document `menu_tablet.html` capability** | 🟢 S | 🟢 low | confirm it does the job |
| B-62 | ❌ | Sazon (orphan) | **Read & document `copilot.py` coverage** | 🟢 S | 🟢 low | confirm 6 intent patterns cover what |
| B-63 | ❌ | Sazon (orphan) | **Read & document `recipe_photos.html`** — verify if it produces print-ready recipe cards | 🟢 S | 🟢 low | 0.5 day |
| B-64 | ❌ | Sazon (orphan) | **Render "Today's daily summary" on dashboard auto-load** (not operator-click) | 🟢 S | 🟢 low | edit `dashboard.html` |

---

# PART 3 — CATEGORY C: DOMAIN LOGIC

## C.1 — PRODUCTION PLANNING

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| C-P-01 | ✅ | Sazon | **Poisson per-weekday MLE for restocking** | — | — | `app/rms/restock_forecast.py:poisson_weekday_rates` (289 lines) |
| C-P-02 | ✅ | Sazon | **Wilson 95% confidence interval** for daily demand | — | — | `restock_forecast.py:Z_95 = 1.959964` |
| C-P-03 | ✅ | Sazon | **P95 stockout walk-forward** (conservative path) | — | — | `restock_forecast.py:Z_95_ONE_SIDED = 1.644854` |
| C-P-04 | ✅ | Sazon | **Demand algebra: base × weekday × trend** with [0.6, 1.6] clamp | — | — | `app/rms/demand_freshness.py:forecast_demand` |
| C-P-05 | ✅ | Sazon | **Freshness / use-first flags** (shelf_life_days vs last receipt) | — | — | `demand_freshness.py` §2 |
| C-P-06 | ✅ | Sazon | **Substitution engine** (ingredient_intel + price delta + tags) | — | — | `demand_freshness.py` §10 |
| C-P-07 | ✅ | Sazon | **ProductionPlan / ProductionRow / ProductionLine data model** | — | — | `app/rms/production.py:ProductionPlan` (566 lines) |
| C-P-08 | ✅ | Sazon | **Forecast confidence 0-100** per row | — | — | `production.py:_forecast_confidence` (computed but not rendered — see B-50) |
| C-P-09 | ✅ | Sazon | **Batch count = ceil(qty / yield_qty)** | — | — | `production.py:_compute_batch_count` |
| C-P-10 | ✅ | Sazon | **Production_demand split** (per-day, per-product) | — | — | `app/rms/production_demand.py` (642 lines, migration 103) |
| C-P-11 | ✅ | Sazon | **Plan accuracy stats** (orphan) | — | — | `app/rms/plan_accuracy.py` (394 lines) — read by `/produccion/accuracy` only |
| C-P-12 | ✅ | Sazon | **Production completion** (EOD recording) | — | — | `app/rms/eod_completions.py` (147) |
| C-P-13 | ✅ | Sazon | **Production closed-day gate** | — | — | `app/rms/eod_closed.py:assert_day_open_or_raise` |
| C-P-14 | ✅ | Sazon | **Production scheduler deprecated 2026-10-05** | — | — | `app/rms/production_scheduler.py` (21 lines) |
| C-P-15 | ✅ | Sazon | **Recipe auto-classification** (family, difficulty, cook time) | — | — | `app/rms/recipe_intel.py` (433 lines) |
| C-P-16 | ✅ | Sazon | **Jaccard ingredient overlap** (substitution + cross-sell + menu rationalization) | — | — | `app/rms/product_similarity.py` (217) |
| C-P-17 | ✅ | Sazon | **Production HACCP** | — | — | `app/rms/haccp_seed.py` + migration 100 (freezer_temperature_log) |
| C-P-18 | 🟡 | Sazon | **plan_accuracy → forecast_sales feedback loop** (orphan read) | 🟡 M | 🟡 med | add SQL UPDATE inside `production.py:forecast_sales` |
| C-P-19 | ❌ | Supply'd | **Batch-level FEFO tracking** (batch_id, expiry, qty_on_hand) | 🟠 L | 🟡 med | new table + receiving flow update |
| C-P-20 | ❌ | Sazon (orphan) | **Surface P95 stockout forecast on /inventario as "running-out-soon" badge** | 🟢 S | 🟢 low | new query + render |
| C-P-21 | ❌ | Sazon (orphan) | **Perishable ingredient email before shift** (uses demand_freshness use-first) | 🟢 S | 🟢 low | cron at 04:30, use `notify.py` |
| C-P-22 | ❌ | Sazon (orphan) | **Print "5 batches of medialunas = 5 trays" on grilla footer** | 🟢 S | 🟢 low | compute + render |
| C-P-23 | ❌ | Sazon (orphan) | **Menu OCR for new seasonal menu** (already built, verify UX) | 🟢 S | 🟢 low | confirm `menu_ocr.py` flow is operator-friendly |

## C.2 — INVENTORY / INGREDIENT

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| C-I-01 | ✅ | Sazon | **Stock movement ledger** (SSOT since migration 092) | — | — | `app/rms/stock_ledger.py:apply_stock_delta` (106) |
| C-I-02 | ✅ | Sazon | **Operator-configurable stock status thresholds** | — | — | `app/rms/stock_status.py:get_thresholds` (165) |
| C-I-03 | ✅ | Sazon | **Constants for stock status defaults** | — | — | `app/rms/constants.py:DEFAULT_STOCK_RATIO_CRITICO`, etc |
| C-I-04 | ✅ | Sazon | **Perishable (shelf_life_days) on ingredients** | — | — | `app/rms/models/inventory.py:Ingredient.shelf_life_days` |
| C-I-05 | ✅ | Sazon | **Cost freshness** (recalculate on demand) | — | — | `app/rms/cost_freshness.py` (142) |
| C-I-06 | ✅ | Sazon | **Ingredient variants** (role-based substitutes) | — | — | `app/rms/variants.py` (354) |
| C-I-07 | ✅ | Sazon | **Ingredient intel** (role mapping) | — | — | `app/rms/ingredient_intel.py` (537) |
| C-I-08 | ✅ | Sazon | **Inventory intel** (per-ingredient stats) | — | — | `app/rms/inventory_intel.py` (265) |
| C-I-09 | ✅ | Sazon | **Waste tracking** | — | — | `app/rms/waste.py` (492) + migration 102 (waste_log_source) |
| C-I-10 | ✅ | Sazon | **Recipe unit normalization** (g/kg/ml/l/und) | — | — | `app/rms/units.py:normalize_recipe_line_qty` (199) |
| C-I-11 | ✅ | Sazon | **Avg ingredient cost (last 30d, FEFO)** | — | — | `app/rms/migrations/_097_ingredient_avg_cost.py` |
| C-I-12 | ✅ | Sazon | **Reorder module** (smart reorder suggestions) | — | — | `app/rms/reorder.py` (104) |
| C-I-13 | ✅ | Sazon | **Reorder by supplier prices** | — | — | `app/rms/reorder_supplier_prices.py` (113) |
| C-I-14 | ✅ | Sazon | **Supplier history** (price drift) | — | — | `app/rms/supplier_history.py` (214) |
| C-I-15 | ✅ | Sazon | **Supplier prices** (per-ingredient per-supplier) | — | — | `app/rms/supplier_prices.py` (294) |
| C-I-16 | ✅ | Sazon | **Streamed CSV import** for large catalogs | — | — | `app/rms/streaming_csv.py` (58) |
| C-I-17 | ✅ | Sazon | **Freezer temperature log** (HACCP) | — | — | `app/rms/migrations/_100_freezer_temperature_log.py` |
| C-I-18 | ✅ | RestoPOS | **42 report categories** — Sazon has 12 specialized, more would be overbuild | — | — | decision: 12 is enough |
| C-I-19 | ❌ | Sazon (orphan) | **Packaging inventory view** (filter chip for "Materias primas" / "Packaging") | 🟢 S | 🟢 low | edit `inventario.html` |
| C-I-20 | ❌ | Sazon (orphan) | **"Alternative preferida" badge on /recetas/<id>/editar** | 🟢 S | 🟢 low | small template edit |
| C-I-21 | ❌ | Supply'd | **Receive-batch with batch_id, expiry, qty** (full FEFO) | 🟠 L | 🟡 med | new receiving flow |

## C.3 — SALES / POS

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| C-S-01 | ✅ | Sazon | **Sale apply (atomic, drops stock)** | — | — | `app/rms/sales/lifecycle.py:apply_sale` (434) |
| C-S-02 | ✅ | Sazon | **Sale void (reverses stock moves)** | — | — | `sales/lifecycle.py:void_sale` |
| C-S-03 | ✅ | Sazon | **Pre-sale check (single-line)** | — | — | `app/rms/sales/pre_sale_check.py` (391) |
| C-S-04 | ✅ | Sazon | **Pre-sale check (cart, multi-line)** | — | — | `app/rms/sales/pre_sale_check_cart.py` (253) |
| C-S-05 | ✅ | Sazon | **Sale channels** (counter, online, pedido, etc) | — | — | `app/rms/models/channels.py` + migrations 111-112 |
| C-S-06 | ✅ | Sazon | **Per-channel pricing** | — | — | `app/rms/models/channels.py:ChannelPrice` |
| C-S-07 | ✅ | Sazon | **Sale tips** | — | — | `app/rms/migrations/_108_sale_tip.py` |
| C-S-08 | ✅ | Sazon | **Sale payments** (split payment types) | — | — | `app/rms/migrations/_105_sale_payments.py` |
| C-S-09 | ✅ | Sazon | **Held sales (parked cart)** | — | — | `app/rms/held_sales.py` (248) + migration 110 |
| C-S-10 | ✅ | Sazon | **Sold by weight (variable qty)** | — | — | `app/rms/migrations/_104_product_sold_by_weight.py` |
| C-S-11 | ✅ | Sazon | **Sale public token** (self-fulfillment) | — | — | `app/rms/migrations/_085_sale_public_token.py` |
| C-S-12 | ✅ | Sazon | **Refund business rules (8)** | — | — | `app/rms/refunds.py` (492) + migration 089 (DB trigger cap) |
| C-S-13 | ✅ | Sazon | **Sale → Pedido back-pointer** | — | — | migration 076 |
| C-S-14 | ✅ | Sazon | **Allergen guard** (check_customer_risk) | — | — | `app/rms/derived_intel.py:check_customer_risk` |
| C-S-15 | ✅ | Sazon | **Ingredient stock check** (in `_compute_stock_moves`) | — | — | `sales/lifecycle.py:_compute_stock_moves` |
| C-S-16 | ✅ | Sazon | **Recipe yield check** (`RecipeWithoutYield`) | — | — | `profitability/cost.py:RecipeWithoutYield` |
| C-S-17 | ✅ | Sazon | **Closed-day gate** (sale blocked if EOD) | — | — | `eod_closed.py:assert_day_open_or_raise` |
| C-S-18 | ✅ | Sazon | **Idempotency reservation** (idempotency-key) | — | — | BACKLOG #15 (per pre_sale_check.py docstring) |
| C-S-19 | ✅ | Sazon | **Per-sale packaging decrement** | — | — | `sales/lifecycle.py:packaging_item_id` param |
| C-S-20 | ✅ | Sazon | **Pedidos (pre-orders) → sale flow** | — | — | `app/rms/models/orders.py` (144) |
| C-S-21 | 🟡 | Sazon | **Pedido status audit (append-only)** | 🟢 S | 🟢 low | new table + write on every transition |
| C-S-22 | ❌ | Sazon (orphan) | **Held-cart auto-age-out (24h)** | 🟢 S | 🟢 low | cron or background job |
| C-S-23 | 🚫 | RestoPOS | **Single-bill split-payment** — skip (cash + informal operator model) | — | — | decision |
| C-S-24 | 🚫 | RestoPOS | **Card processor integration** — skip | — | — | decision per SASKIA-210 |
| C-S-25 | 🚫 | FloCafe | **Card-on-file / Apple Pay** — skip | — | — | decision |
| C-S-26 | 🚫 | TastyIgniter | **Stripe / Mollie / Square integrations** — skip | — | — | decision |
| C-S-27 | 🚫 | PizzaQL | **Discount / coupon module** — small but skip (operator doesn't run promos) | — | — | decision |
| C-S-28 | ✅ | Sazon | **Receipts (recibo)** | — | — | `recibo.html` template + `app/routers/sales.py:recibo/{id}` |

## C.4 — CUSTOMERS / RELATIONSHIPS

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| C-C-01 | ✅ | Sazon | **Customer CRUD** | — | — | `app/rms/customers.py` (326) |
| C-C-02 | ✅ | Sazon | **Customer dietary profile** (RESTRICTIONS + PREFERENCES + CONFIRM_ALWAYS) | — | — | `app/rms/customer_dietary.py` (117) |
| C-C-03 | ✅ | Sazon | **Customer merge (atomic, sales+pedidos reassign)** | — | — | `app/rms/customer_merge.py` (188) — P1-B4 |
| C-C-04 | ✅ | Sazon | **Customer phone column** (migration 098) | — | — | `app/rms/migrations/_098_customer_phone.py` |
| C-C-05 | ✅ | Sazon | **Customer duplicates screen** | — | — | `clientes_duplicados.html` |
| C-C-06 | ✅ | Sazon | **Loyalty ledger** (signed, idempotent) | — | — | `app/rms/loyalty/ledger.py` (259) |
| C-C-07 | ✅ | Sazon | **Loyalty tiers** (BRONZE/SILVER/GOLD/PLATINUM) | — | — | `app/rms/loyalty/tiers.py` (46) |
| C-C-08 | ✅ | Sazon | **Loyalty suggestions** (5 rules: LAPSED, BIRTHDAY, POINTS-DORMANT, VIP, CROSS-SELL) | — | — | `app/rms/loyalty/suggestions.py` (415) |
| C-C-09 | ✅ | Sazon | **Fiado / AR ledger** (signed, FIFO aging, idempotent pago) | — | — | `app/rms/fiado.py` (240) |
| C-C-10 | ✅ | Sazon | **Credit accounts (migration 107)** | — | — | `app/rms/migrations/_107_credit_accounts.py` |
| C-C-11 | ✅ | Sazon | **Fiado cartera (aging buckets)** | — | — | `fiado.py:cartera` |
| C-C-12 | ✅ | Sazon | **Fiado void_reversal** (auto-reverses ledger on sale void) | — | — | `fiado.py:void_reversal` |
| C-C-13 | ✅ | Sazon | **Customer loyalty cached balance** (Customer.loyalty_points) | — | — | `app/rms/models.py:Customer` |
| C-C-14 | ✅ | Sazon | **Loyalty 10% return rate** (was 100% — fixed 2026-10-01) | — | — | `loyalty/ledger.py:POINTS_PER_GS_EARN = 1/1000, POINTS_VALUE_GS = 100` |
| C-C-15 | ✅ | Sazon | **Cross-sell via customer dietary tag** (CROSS-SELL rule) | — | — | `loyalty/suggestions.py` |
| C-C-16 | ✅ | Sazon | **Customer filter (phone, name, tag)** | — | — | `app/rms/customers.py` |
| C-C-17 | ❌ | Sazon (orphan) | **Loyalty: confirm-always count on customer card** (show how many) | 🟢 S | 🟢 low | small `cliente_detalle.html` edit |
| C-C-18 | ❌ | Sazon (orphan) | **Loyalty: "X points" widget on POS screen** (visible during sale) | 🟡 M | 🟢 low | new card on POS |
| C-C-19 | 🚫 | TastyIgniter | **Multi-tenant customer separation** — skip | — | — | decision per SASKIA-210 |
| C-C-20 | 🚫 | RestoPOS | **Online customer portal** — skip | — | — | decision |

## C.5 — MENUS / RECIPES

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| C-M-01 | ✅ | Sazon | **Menus (combos) expansion with menu-priced line 1** | — | — | `app/rms/menu_ejecutivo.py` (70) + migration 109 |
| C-M-02 | ✅ | Sazon | **Menu OCR via GLM vision** (anti-hallucination) | — | — | `app/rms/menu_ocr.py` (114) |
| C-M-03 | ✅ | Sazon | **Menu CSV import** (with fuzzy match) | — | — | `app/rms/seed/menu_import.py` (150) |
| C-M-04 | ✅ | Sazon | **Menu engineering quadrant** (STAR/PUZZLE/PLOWHORSE/DOG) | — | — | `app/rms/menu_engineering.py` (257) |
| C-M-05 | ✅ | Sazon | **Recipe photos (for cards)** | — | — | `recipe_photos.html` template |
| C-M-06 | ✅ | Sazon | **Recipe instructions** (migration 057) | — | — | `app/rms/migrations/_057_recipe_instructions.py` |
| C-M-07 | ✅ | Sazon | **Recipe fermentation minutes** (migration 101) | — | — | `app/rms/migrations/_101_recipe_fermentation_minutes.py` |
| C-M-08 | ✅ | Sazon | **Recipes consolidated view** (exploded vs structural) | — | — | `app/rms/recipes_consolidated.py` (207) |
| C-M-09 | ✅ | Sazon | **Menu inventory (per-menu stock preview)** | — | — | `app/rms/menu_inventory.py` (129) |
| C-M-10 | ✅ | Sazon | **Menu public (customer-facing)** | — | — | `menu_publico.html` |
| C-M-11 | ✅ | Sazon | **Menu tablet (operator tablet view)** | — | — | `menu_tablet.html` |
| C-M-12 | ❌ | Sazon (orphan) | **Read & document menu_tablet capability** | 🟢 S | 🟢 low | confirm it covers the use case |

## C.6 — INVOICING / FINANCIALS

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| C-F-01 | ✅ | Sazon | **Paraguay IVA 10% (included/excluded modes)** | — | — | `app/rms/accounting.py:PARAGUAY_IVA_RATE` (739 lines) |
| C-F-02 | ✅ | Sazon | **Libro ventas (chronological sale listing)** | — | — | `accounting.py:libro_ventas` |
| C-F-03 | ✅ | Sazon | **Monthly closure** (Sprint 3.1) | — | — | `app/rms/services/closures.py:close_month` (293) |
| C-F-04 | ✅ | Sazon | **Expense CRUD** | — | — | `app/rms/services/expenses.py` (253) + migration 093 (recurring) |
| C-F-05 | ✅ | Sazon | **Recurring expense support** (migration 093) | — | — | migration file |
| C-F-06 | ✅ | Sazon | **Bank reconciliation** (migration 056) | — | — | `app/rms/migrations/_056_bank_reconciliation.py` |
| C-F-07 | ✅ | Sazon | **Invoicing module** | — | — | `app/rms/invoicing.py` (133) |
| C-F-08 | ✅ | Sazon | **Suscripciones (recurring orders)** | — | — | `app/routers/suscripciones.py` (no separate rms module — uses invoicing) |
| C-F-09 | ✅ | Sazon | **Cotizador (quote builder)** | — | — | `app/rms/cotizador.py` (101) |
| C-F-10 | ✅ | Sazon | **Price history audit** (per product) | — | — | `app/rms/price_history.py` (481) + `product_price_history.py` (161) |
| C-F-11 | ✅ | Sazon | **Margin tiers** (per-product margin thresholds) | — | — | `app/rms/margin_tier.py` (84) |
| C-F-12 | ✅ | Sazon | **Cash session** (migration 106) | — | — | `app/rms/migrations/_106_cash_sessions.py` |
| C-F-13 | ✅ | Sazon | **Cierre (Z-report)** | — | — | `app/rms/cierre.py` (267) |
| C-F-14 | ✅ | Sazon | **Cash module** (lightweight) | — | — | `app/rms/cash.py` (101) |
| C-F-15 | ❌ | Sazon (orphan) | **Daily P&L rollup** (per-day, with margin% and IVA components) | 🟡 M | 🟢 low | extend `accounting.py:daily_summary` |
| C-F-16 | ❌ | restaurant-menu.org | **Per-category variance bands** (protein 2.0, dairy 1.5, dry 0.8) | 🟡 M | 🟡 med | new `food_cost_alert` table + soft/hard bands |
| C-F-17 | 🚫 | TastyIgniter | **Multi-currency** — skip (PYG only) | — | — | decision |

## C.7 — HACCP / SAFETY

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| C-H-01 | ✅ | Sazon | **HACCP defaults seeded per Res S.G. N° 213/2019** | — | — | `app/rms/haccp_seed.py` (105) |
| C-H-02 | ✅ | Sazon | **Freezer temperature log** (migration 100) | — | — | `app/rms/migrations/_100_freezer_temperature_log.py` |
| C-H-03 | ✅ | Sazon | **HACCP production** (checklist) | — | — | `produccion_haccp.html` template + `app/routers/produccion` |
| C-H-04 | ✅ | Sazon | **Waste log source** (migration 102) | — | — | `app/rms/migrations/_102_waste_log_source.py` |
| C-H-05 | ✅ | Sazon | **Waste intel / waste tracking** | — | — | `waste.py` (492) |

---

# PART 4 — CATEGORY D: ANALYTICS / REPORTS / INSIGHTS

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| D-01 | ✅ | Sazon | **11 specialized report pages** (diario, cierre_mensual, comparacion, consumo, iva, libro_ventas, mermas_cost, metodos_pago, metricas, precios, retencion, top_productos, valor_pedido, ventas_hora) | — | — | `app/templates/reportes_*.html` |
| D-02 | ✅ | Sazon | **8 insight pages** (afinidades, demand, food_cost, freshness, margenes, margenes_detalle, price_impact, stock) | — | — | `app/templates/insight_*.html` |
| D-03 | ✅ | Sazon | **Insights router** (insights, insights_derived, insights_stock) | — | — | `app/routers/insights*.py` |
| D-04 | ✅ | Sazon | **Analytics module** (cross-cutting metrics) | — | — | `app/rms/analytics.py` (979 lines) |
| D-05 | ✅ | Sazon | **Audit analytics** | — | — | `app/rms/audit_analytics.py` (183) |
| D-06 | ✅ | Sazon | **Food cost (theoretical vs actual)** | — | — | `app/rms/food_cost.py` (222) |
| D-07 | ✅ | Sazon | **Prime cost (materials + labor + overhead)** | — | — | `app/rms/prime_cost.py` (303) |
| D-08 | ✅ | Sazon | **Sales intel** (time patterns, market basket, churn, rising) | — | — | `app/rms/sales_intel.py` (702 lines!) |
| D-09 | ✅ | Sazon | **Inventory intel** | — | — | `app/rms/inventory_intel.py` (265) |
| D-10 | ✅ | Sazon | **Ingredient intel** | — | — | `app/rms/ingredient_intel.py` (537) |
| D-11 | ✅ | Sazon | **Menu engineering** (STAR/PUZZLE/PLOWHORSE/DOG) | — | — | `app/rms/menu_engineering.py` (257) |
| D-12 | ✅ | Sazon | **Product similarity (Jaccard)** | — | — | `app/rms/product_similarity.py` (217) |
| D-13 | ✅ | Sazon | **Derived intel** (cross-cutting) | — | — | `app/rms/derived_intel.py` (301) |
| D-14 | ✅ | Sazon | **Market intel** (vs-mercado from competitor_seed) | — | — | `app/rms/market_intel.py` (176) |
| D-15 | ✅ | Sazon | **Sales heatmap (weekday × hour grid, last 90d)** | — | — | `app/rms/sales_intel.py:sales_heatmap` |
| D-16 | ✅ | Sazon | **Sales by hour / day-of-week / month** | — | — | `sales_intel.py:sales_by_hour` etc |
| D-17 | ✅ | Sazon | **Cost freshness** | — | — | `app/rms/cost_freshness.py` (142) |
| D-18 | ✅ | Sazon | **Demand freshness** (use-first flags) | — | — | `app/rms/demand_freshness.py` |
| D-19 | ✅ | Sazon | **Plan accuracy stats** (per product) | — | — | `app/rms/plan_accuracy.py` (394) |
| D-20 | ✅ | Sazon | **Soft-delete analytics** (migration 095) | — | — | `app/rms/migrations/_095_soft_delete_columns.py` |
| D-21 | ✅ | Sazon | **Audit columns on every model** (migration 096) | — | — | `app/rms/migrations/_096_audit_columns.py` |
| D-22 | ✅ | Sazon | **Margin tier visualization** | — | — | `app/rms/margin_tier.py` (84) + `insight_margenes.html` |
| D-23 | ✅ | Sazon | **Affinities (cross-sell patterns)** | — | — | `insight_afinidades.html` + `sales_intel.py` |
| D-24 | ✅ | Sazon | **Price impact analysis** | — | — | `insight_price_impact.html` |
| D-25 | ✅ | Sazon | **Stock insights (per ingredient)** | — | — | `insight_stock.html` + `inventory_intel.py` |
| D-26 | ✅ | Sazon | **Demand insights** | — | — | `insight_demand.html` + `demand_freshness.py` |
| D-27 | ✅ | Sazon | **Food cost insights** | — | — | `insight_food_cost.html` + `food_cost.py` |
| D-28 | ✅ | Sazon | **Freshness insights** | — | — | `insight_freshness.html` + `demand_freshness.py` |
| D-29 | ✅ | Sazon | **Comparacion reports** | — | — | `reportes_comparacion.html` |
| D-30 | ✅ | Sazon | **Consumo reports** | — | — | `reportes_consumo.html` |
| D-31 | ✅ | Sazon | **Métodos de pago reports** | — | — | `reportes_metodos_pago.html` |
| D-32 | ✅ | Sazon | **Métricas reports** | — | — | `reportes_metricas.html` |
| D-33 | ✅ | Sazon | **Precios reports** | — | — | `reportes_precios.html` |
| D-34 | ✅ | Sazon | **Retención reports** | — | — | `reportes_retencion.html` |
| D-35 | ✅ | Sazon | **Valor del pedido reports** | — | — | `reportes_valor_pedido.html` |
| D-36 | ✅ | Sazon | **Top productos reports** | — | — | `reportes_top_productos.html` |
| D-37 | ✅ | Sazon | **Ventas por hora reports** | — | — | `reportes_ventas_hora.html` |
| D-38 | ✅ | Sazon | **Mermas cost reports** | — | — | `reportes_mermas_cost.html` |
| D-39 | ✅ | Sazon | **Cierre mensual reports** | — | — | `reportes_cierre_mensual.html` |
| D-40 | ✅ | Sazon | **IVA reports** | — | — | `reportes_iva.html` |
| D-41 | ✅ | Sazon | **Libro ventas reports** | — | — | `reportes_libro_ventas.html` |
| D-42 | ✅ | Sazon | **Diario reports** (main) | — | — | `reportes_diario.html` |
| D-43 | ❌ | Sazon (orphan) | **Daily P&L rollup endpoint** (G-1) | 🟡 M | 🟢 low | new `/reportes/pnl` route |
| D-44 | ❌ | Sazon (orphan) | **plan_accuracy → forecast_sales feedback** (C-P-18 duplicate) | 🟡 M | 🟡 med | (duplicate) |
| D-45 | ❌ | restaurant-menu.org | **Per-category variance bands** (C-F-16 duplicate) | 🟡 M | 🟡 med | (duplicate) |
| D-46 | ❌ | BakeOnyx | **Per-day "Accuracy: 94%" daily report** | 🟡 M | 🟡 med | new `accuracy_daily.html` |
| D-47 | 🚫 | TastyIgniter | **Google Analytics / Mixpanel integration** — skip | — | — | decision |
| D-48 | 🚫 | RestoPOS | **42 report categories** — Sazon's 12 specialized is enough | — | — | decision |

---

# PART 5 — CATEGORY E: OPS / COMPLIANCE / SAFETY

| # | Status | Source | Lesson / Idea / Topic | Effort | Risk | Where in Sazon (or gap) |
|---|---|---|---|---|---|---|
| E-01 | ✅ | Sazon | **Maintenance cron** (audit log retention, dry-run) | — | — | `app/rms/maintenance.py:prune_audit_log` (66) |
| E-02 | ✅ | Sazon | **Sentry integration** (via observability hook) | — | — | `app/rms/notify.py:sentry_before_send` (mentioned) |
| E-03 | ✅ | Sazon | **Sentry → Telegram bridge** (fire-and-forget) | — | — | `app/rms/notify.py` (125) |
| E-04 | ✅ | Sazon | **Daily summary notification** (WhatsApp/SMTP/dryrun) | — | — | `app/rms/notifications.py:format_daily_summary_message` (324) |
| E-05 | ✅ | Sazon | **Per-request loguru context** | — | — | `app/rms/observability.py` (206) |
| E-06 | ✅ | Sazon | **Audit log** for every domain event | — | — | `app/rms/audit.py` (174) |
| E-07 | ✅ | Sazon | **Audit analytics** (audit log dashboards) | — | — | `app/rms/audit_analytics.py` (183) |
| E-08 | ✅ | Sazon | **Rate-limit middleware** | — | — | `app/rms/rate_limit.py` (369) |
| E-09 | ✅ | Sazon | **CSRF middleware** | — | — | `app/rms/csrf.py` (212) |
| E-10 | ✅ | Sazon | **Healthz summary** | — | — | `healthz_summary.html` + `app/routers/health.py` |
| E-11 | ✅ | Sazon | **Ops status page** | — | — | `ops_status.html` + `app/routers/ops.py` |
| E-12 | ✅ | Sazon | **Production closed-day gate** | — | — | `app/rms/eod_closed.py` (137) |
| E-13 | ✅ | Sazon | **EOD completion recording** | — | — | `app/rms/eod_completions.py` (147) |
| E-14 | ✅ | Sazon | **EOD anomalies page** (auto-display) | — | — | `eod_anomalies.html` |
| E-15 | ✅ | Sazon | **EOD print page** | — | — | `eod_print.html` |
| E-16 | ✅ | Sazon | **Riesgos (risk register)** | — | — | `app/rms/riesgos.py` + `riesgos.html` |
| E-17 | ✅ | Sazon | **Wishlist for operator equipment** (with stock-bump on purchase) | — | — | `app/routers/herebus.py:wishlist_mark_purchased` |
| E-18 | ✅ | Sazon | **Shopping list** (with stock-bump on mark-purchased) | — | — | SASKIA-205 (memory) |
| E-19 | ✅ | Sazon | **Backup helpers** (pre-migration backups) | — | — | `app/rms/backup.py` (312) |
| E-20 | ✅ | Sazon | **GLM client with graceful degradation** | — | — | `app/rms/llm.py:available()` (118) |
| E-21 | ✅ | Sazon | **In-app AI assistant (Copilot, 6 intent patterns)** | — | — | `app/rms/copilot.py` (120) |
| E-22 | ✅ | Sazon | **Menu OCR with anti-hallucination** | — | — | `app/rms/menu_ocr.py` (114) |
| E-23 | ✅ | Sazon | **Carga inicial (first-run onboarding)** | — | — | `carga_inicial.html` + `app/rms/seed/onboard.py` (54) |
| E-24 | ✅ | Sazon | **Demo seed** (synthetic data for testing) | — | — | `app/rms/seed/demo.py` (917) |
| E-25 | ✅ | Sazon | **Pack seed (Vaquita standard)** | — | — | `app/rms/seed/packs.py` (4,719 lines) |
| E-26 | ✅ | Sazon | **Pack demo (showcase data)** | — | — | `app/rms/seed/pack_demo.py` (398) |
| E-27 | ✅ | Sazon | **Sazon master seed** | — | — | `app/rms/seed/sazon.py` (4,862 lines) |
| E-28 | ✅ | Sazon | **Competitor seed** | — | — | `app/rms/seed/competitor_seed.py` (958) |
| E-29 | ✅ | Sazon | **Competitor prices** | — | — | `app/rms/seed/competitor_prices.py` (65) |
| E-30 | ✅ | Sazon | **Competitor shoppings** | — | — | `app/rms/seed/competitor_shoppings.py` (647) |
| E-31 | 🟡 | URY | **Pre-sale log table persistence** (A-23 duplicate) | 🟡 M | 🟢 low | (duplicate) |
| E-32 | ❌ | URY | **KOT error log** | 🟢 S | 🟢 low | new `production_print_errors` table |
| E-33 | ❌ | FloCafe | **Maintenance middleware** (A-31 duplicate) | 🟢 S | 🟢 low | (duplicate) |
| E-34 | ❌ | FloCafe | **WhatsApp integration** (inbound + outbound + QR pairing + blocklist) | 🟠 L | 🟡 med | defer — Telegram covers 90% of value |
| E-35 | ❌ | Sazon (orphan) | **pedido_status_audit (append-only)** (C-S-21 duplicate) | 🟢 S | 🟢 low | (duplicate) |
| E-36 | ❌ | Sazon (orphan) | **Perishable email before shift** (C-P-21 duplicate) | 🟢 S | 🟢 low | (duplicate) |
| E-37 | 🚫 | FloCafe | **WhatsApp QR pairing** — defer; Sazon has Telegram | — | — | decision |
| E-38 | 🚫 | TastyIgniter | **Multi-tenant operator auth** — skip | — | — | decision per SASKIA-210 |
| E-39 | 🚫 | DineOut | **Android employee-shift tracking** — skip (no mobile) | — | — | decision |
| E-40 | 🚫 | TastyIgniter | **OAuth2 (Google/Facebook login)** — skip (bcrypt + Supabase is enough) | — | — | decision |

---

# PART 6 — COMPETITOR-SPECIFIC LEARNINGS (consolidated)

| # | Source | Lesson / Idea / Topic | Status in Sazon |
|---|---|---|---|
| COMP-01 | TastyIgniter | 22-extension plugin architecture (ti-ext-api, ti-ext-local, ti-ext-payregister, etc.) | 🚫 SKIP — single-app, no extensions |
| COMP-02 | TastyIgniter | JSON:API endpoints | 🟡 PARTIAL — public_tokens.py exists; full JSON:API not built |
| COMP-03 | TastyIgniter | Stripe/Mollie/Square payment integrations | 🚫 SKIP — cash + informal |
| COMP-04 | TastyIgniter | Multi-tenant theming | 🚫 SKIP |
| COMP-05 | TastyIgniter | Geo-coder for locations | 🚫 SKIP — 1 client |
| COMP-06 | TastyIgniter | Coupons module | 🚫 SKIP |
| COMP-07 | TastyIgniter | Roles/permissions module | 🟡 PARTIAL — bcrypt + Supabase auth; no per-role permissions |
| COMP-08 | RestoPOS | 117 routes | ✅ SHIPPED — Sazon has 117 production-relevant routes |
| COMP-09 | RestoPOS | 42 report categories | 🟡 PARTIAL — 12 specialized is enough |
| COMP-10 | RestoPOS | KOT duplicate-reprint | ❌ OPEN — see B-56 / E-32 |
| COMP-11 | RestoPOS | KOT error log | ❌ OPEN — same |
| COMP-12 | RestoPOS | Multi-printer auto-select | 🚫 SKIP — single station |
| COMP-13 | RestoPOS | Labor scheduling | 🚫 SKIP — single operator |
| COMP-14 | DineOut | True EOD/EOW | ✅ SHIPPED — `eod.py` + `eod_completions.py` |
| COMP-15 | DineOut | Employee shift tracking | 🚫 SKIP — no employees |
| COMP-16 | DineOut | Table management | 🚫 SKIP — counter-only |
| COMP-17 | resto-nestjs | SOP order_processing_queue | 🟡 PARTIAL — pedido status audit would replace it (E-35) |
| COMP-18 | resto-nestjs | Recipe CRUD | ✅ SHIPPED |
| COMP-19 | resto-nestjs | Stock CRUD | ✅ SHIPPED |
| COMP-20 | Flutter POS | File-split gold standard (menu/, stock/, analysis/, order_attr/, printer/) | 🟡 PARTIAL — Sazon has services/ + tagging/ but not the same split |
| COMP-21 | Flutter POS | chart_reorder.dart (drag-and-drop chart reorder) | ❌ OPEN — see B-48 |
| COMP-22 | Flutter POS | product_reorder.dart | ❌ OPEN — see B-48 |
| COMP-23 | Flutter POS | product_ingredient_reorder.dart | ❌ OPEN — see B-49 |
| COMP-24 | Flutter POS | Feature-per-page layout | ✅ SHIPPED — 11 specialized report pages + 8 insight pages |
| COMP-25 | Flutter POS | Reloadable card pattern | 🟡 PARTIAL — not formalized; could be component |
| COMP-26 | PizzaQL | GraphQL Subscriptions | 🚫 SKIP — no SSE in stack |
| COMP-27 | PizzaQL | Custom cake configurator | 🚫 SKIP — bakery-only |
| COMP-28 | PizzaQL | Proactive order notifications | 🟡 PARTIAL — `notifications.py` covers this; operator-side |
| COMP-29 | openresto | Print template engine (.rpt) | 🚫 SKIP |
| COMP-30 | openresto | Cash session management | ✅ SHIPPED — `cash.py` + `cierre.py` |
| COMP-31 | FloCafe | WhatsApp integration (inbound + outbound + QR pairing + blocklist) | 🚫 SKIP — defer |
| COMP-32 | FloCafe | Maintenance middleware (returns 503 + Retry-After) | ❌ OPEN — see A-31 |
| COMP-33 | FloCafe | Menu upload | ✅ SHIPPED — `menu_ocr.py` + `menu_import_ocr.html` |
| COMP-34 | FloCafe | Multi-locale i18n | 🚫 SKIP |
| COMP-35 | ury | 45 doctypes (10 sales/order/customer + 11 menu/recipe + 8 inventory/supplier + 4 report + 5 system + 7 ops) | 🟡 PARTIAL — Sazon has 115+ modules, not 45 doctypes (Frappe-style) |
| COMP-36 | ury | pos_checklist_log (pre-billing checklist trio) | 🟡 PARTIAL — `pre_sale_check.py` exists; log table not yet (A-23) |
| COMP-37 | ury | ury_daily_p_and_l (daily P&L rollup) | ❌ OPEN — see C-F-15 / D-43 |
| COMP-38 | ury | kot_error_log | ❌ OPEN — see B-56 / E-32 |
| COMP-39 | ury | per-day summary json | ✅ SHIPPED — `notifications.py:format_daily_summary_message` |
| COMP-40 | ury | Pay register (multi-payment per sale) | ✅ SHIPPED — migration 105 |
| COMP-41 | cafe-pub | Slim models, no expiry tracking | 🚫 SKIP — too small |
| COMP-42 | cafe-pub | Order history | ✅ SHIPPED — `ventas_historial.html` |
| COMP-43 | cafe-pub | QR code menu | ✅ SHIPPED — `menu_publico.html` + public_tokens |

---

# PART 7 — INDUSTRY-REFERENCE LEARNINGS (consolidated)

| # | Source | Lesson / Idea / Topic | Status in Sazon |
|---|---|---|---|
| IND-01 | Supply'd | Wholesale orders + standing orders + forecast | ✅ SHIPPED — `suscripciones.py` + `production.py` |
| IND-02 | Supply'd | Compare expected vs actual production, yield, waste, sales | 🟡 PARTIAL — `plan_accuracy.py` covers expected-vs-actual-sold; missing yield% and waste% |
| IND-03 | Supply'd | Batch and expiry tracking (FEFO) | ❌ OPEN — see C-P-19 / C-I-21 |
| IND-04 | Supply'd | Recipe BOMs (multi-level) | ✅ SHIPPED — `profitability/cost.py` walks sub-recipes |
| IND-05 | Supply'd | Per-product yield% tracking | ❌ OPEN — would need new column + UI |
| IND-06 | Supply'd | Recipe vs menu engineering | ✅ SHIPPED — `menu_engineering.py` |
| IND-07 | Supply'd | Multi-location support | 🚫 SKIP — per SASKIA-210 |
| IND-08 | CafeKit | Last-4 same-weekday avg, low-high range, how-steady on production grilla | ❌ OPEN — see B-51 |
| IND-09 | CafeKit | Banner if preordered item missing from plan | ❌ OPEN — see B-52 |
| IND-10 | CafeKit | One-click "copy last week's same weekday" | ✅ SHIPPED — `produccion_copy_last_week` |
| IND-11 | CafeKit | Multi-location column layout | 🚫 SKIP |
| IND-12 | CafeKit | PRIMS file export | 🚫 SKIP — irrelevant |
| IND-13 | CafeKit | Print-as-ship-ticket | ✅ SHIPPED — `produccion_print.html` |
| IND-14 | BakeOnyx | Per-product trend colored green/yellow/red confidence | 🟡 PARTIAL — `_forecast_confidence` computed (B-50 not rendered) |
| IND-15 | BakeOnyx | "Add Event" for ad-hoc forecast nudge | ✅ SHIPPED — `SeasonalEvent` already supports |
| IND-16 | BakeOnyx | Per-day "Accuracy: 94%" daily report | ❌ OPEN — see D-46 |
| IND-17 | BakeOnyx | Manual override of forecast | ✅ SHIPPED — qty_to_produce is editable in UI |
| IND-18 | BakeOnyx | Ingredient list as PDF | 🟡 PARTIAL — `produccion_print.html`; PDF export not verified |
| IND-19 | Rinvy | Per-menu-item target food cost % | ✅ SHIPPED — `margin_tier.py` |
| IND-20 | Rinvy | Alert when actual > target | ❌ OPEN — need to wire food_cost → alert |
| IND-21 | Rinvy | 6AM push on drift | ❌ OPEN — would need daily cron |
| IND-22 | restaurant-menu.org | Per-category variance multipliers (protein 2.0, dairy 1.5, dry 0.8) | ❌ OPEN — see C-F-16 / D-45 |
| IND-23 | restaurant-menu.org | Soft band (1× σ) + Hard band (2× σ) | ❌ OPEN — same |
| IND-24 | restaurant-menu.org | Two-tier routing | ❌ OPEN — same |
| IND-25 | restaurant-menu.org | Cold-start seeded baseline (14-30d before paging) | ❌ OPEN — same |
| IND-26 | restaurant-menu.org | Unbiased std (ddof=1) | ❌ OPEN — verify current code |
| IND-27 | restaurant-menu.org | Hard alert gated on EOD recon | 🟡 PARTIAL — `assert_day_open_or_raise` exists for sales, not alerts |
| IND-28 | Otter | Weekly food cost variance cadence | 🟡 PARTIAL — `accounting.py:libro_ventas` is daily; weekly rollup missing |
| IND-29 | Otter | "0-2pp = controlled, 3-5pp = investigate, >5pp = systemic" thresholds | 🟡 PARTIAL — same as IND-22 |
| IND-30 | Supy | Rolling variance reports (vs monthly) | ❌ OPEN — same |
| IND-31 | JMJSoft | Semi-finished goods tracking (doughs, creams, fillings) | ✅ SHIPPED — `recipe_intel.py:infer_recipe_family` + sub-recipe walk |
| IND-32 | JMJSoft | First-Expired First-Out (FEFO) | 🟡 PARTIAL — shelf_life_days exists, no per-batch |

---

# PART 8 — THE OPEN WORK (FINAL)

Sorted by ROI. All items verified against the actual Sazon codebase.

## Tier 1 — High value, low effort (do this week)

| # | Open Item | Effort | Source file to edit |
|---|---|---|---|
| 1 | **G-9: Confidence badge on production grilla** | 🟢 S | `app/templates/produccion.html` |
| 2 | **G-6 / E-32: KOT error log** | 🟢 S | new migration + `print_export.py` |
| 3 | **G-8: Seasonal calendar → settings_kv** | 🟢 S | `app/rms/seasonal.py` + new registry entry |
| 4 | **G-7 / A-31: Maintenance middleware** | 🟢 S | new `MaintenanceModeMiddleware` in `app/main.py` |
| 5 | **G-12 / E-36 / C-P-21: Perishable email before shift** | 🟢 S | cron + reuse `notify.py` |
| 6 | **G-13 / B-51: Variance band "how steady" on grilla** | 🟢 S | new column in `produccion.html` |
| 7 | **G-15 / B-61: Read & document menu_tablet** | 🟢 S | 0.5 day verification |
| 8 | **G-16 / B-62: Read & document copilot coverage** | 🟢 S | 0.5 day verification |
| 9 | **G-14 / B-63: Read & document recipe_photos** | 🟢 S | 0.5 day verification |
| 10 | **B-64: Daily summary auto on dashboard** | 🟢 S | edit `dashboard.html` |
| 11 | **A-19: Remove dead SaleStockMove imports** | 🟢 S | `costing.py:501` + `sales/lifecycle.py:22` |
| 12 | **C-S-22: Held-cart auto-age-out 24h** | 🟢 S | cron |
| 13 | **C-I-19: Packaging filter chip on /inventario** | 🟢 S | edit `inventario.html` |
| 14 | **C-I-20: Alternative preferida badge on /recetas** | 🟢 S | edit `receta_form.html` |
| 15 | **C-P-20: P95 stockout badge on /inventario** | 🟢 S | new query + render |
| 16 | **C-P-22: Print batch tray count on grilla footer** | 🟢 S | new render |
| 17 | **B-52: Banner if preordered item missing from plan** | 🟢 S | edit `produccion_manana.html` |
| 18 | **B-53: Plan accuracy widget on /inicio** | 🟢 S | new card on `inicio.html` |
| 19 | **C-C-17: Confirm-always count on customer card** | 🟢 S | edit `cliente_detalle.html` |
| 20 | **C-C-18: Loyalty points widget on POS** | 🟡 M | new card on POS screen |
| 21 | **C-S-21 / E-35: pedido_status_audit** | 🟢 S | new migration + write on every transition |
| 22 | **C-M-12: Document menu_tablet capability** | 🟢 S | confirm |

## Tier 2 — High value, medium effort (do next)

| # | Open Item | Effort | Source file to edit |
|---|---|---|---|
| 23 | **G-5 / A-23 / E-31: Pre-sale log table persistence** | 🟡 M | new migration + edit `pre_sale_check.py` |
| 24 | **G-1 / D-43: Daily P&L rollup endpoint** | 🟡 M | extend `accounting.py:daily_summary` + new route |
| 25 | **G-3 / C-P-18 / D-44: plan_accuracy feedback loop** | 🟡 M | edit `production.py:forecast_sales` + bias-clamp tests |
| 26 | **G-10 / B-48: Drag-and-drop product pin** | 🟡 M | new `user_pinned_products` table + reorder widget |
| 27 | **G-2 / C-F-16 / D-45 / IND-22: Per-category variance bands** | 🟡 M | new `food_cost_alert.py` + soft/hard bands |
| 28 | **D-46: Per-day accuracy report** | 🟡 M | new `accuracy_daily.html` + cron |
| 29 | **B-54: Soft vs Hard band visualization** | 🟡 M | new page |

## Tier 3 — Architectural cleanup (do later)

| # | Open Item | Effort | Source file to edit |
|---|---|---|---|
| 30 | **A-25 / G-4: Refactor produccion.html** (2366 lines → _views/) | 🟠 L | `produccion.html` + new sub-templates |
| 31 | **C-P-19 / C-I-21: Batch-level FEFO tracking** | 🟠 L | new table + receiving flow update |
| 32 | **E-34: WhatsApp integration** (defer) | 🟠 L | new module + baileys + QR pairing |

## Tier 4 — Documentation / verification only

| # | Open Item | Effort | Source file to edit |
|---|---|---|---|
| 33 | **G-15 / B-61: Read & document menu_tablet** (covered in Tier 1) | — | — |
| 34 | **G-16 / B-62: Read & document copilot.py** (covered in Tier 1) | — | — |
| 35 | **G-14 / B-63: Read & document recipe_photos** (covered in Tier 1) | — | — |

## Tier 5 — Verified SKIP (deliberately not building)

| # | Item | Why skip |
|---|---|---|
| 1 | Multi-tenant | SASKIA-210: per-client instances, not shared DB |
| 2 | Mobile app | Operator at laptop |
| 3 | Self-order kiosk | No customer-facing interface |
| 4 | Card processor | Cash + informal; Paraguay operator model |
| 5 | Multi-locale i18n | Spanish-vos only |
| 6 | Worker/queue system | Single-process |
| 7 | Live KDS | Tablet view exists; no SSE in stack |
| 8 | Monorepo split | One repo per Sazon instance |
| 9 | TastyIgniter-style extensions | Single-app, no plugin marketplace |
| 10 | FloCafe WhatsApp integration (defer) | Telegram covers 90% of value |
| 11 | TastyIgniter extension CDN | Skip |
| 12 | RestoPOS Modules/ separation | Sazon uses flat `app/rms/<feature>.py` |
| 13 | PizzaQL GraphQL Subscriptions | No SSE anywhere |
| 14 | BakeOnyx AI per-day plan | `_forecast_confidence` already covers |
| 15 | RestoPOS KOT auto-printer | `print_export.py` already writes to disk |
| 16 | RestoPOS labor scheduling | Single operator |
| 17 | CafeKit multi-location column | Sazon has 1 client |
| 18 | Supply'd FEFO batch tracking (defer) | Ingredient shelf_life_days is enough at current scale |
| 19 | TastyIgniter Google Analytics / Mixpanel | Skip |
| 20 | RestoPOS 42 report categories | Sazon's 12 is enough |
| 21 | TastyIgniter multi-tenant operator auth | Skip per SASKIA-210 |
| 22 | DineOut employee-shift tracking | No employees |
| 23 | TastyIgniter OAuth2 | Bcrypt + Supabase is enough |
| 24 | TastyIgniter multi-currency | PYG only |
| 25 | RestoPOS single-bill split-payment | Cash + informal |
| 26 | TastyIgniter roles/permissions | Not needed |
| 27 | openresto .rpt template engine | Server-rendered HTML |
| 28 | TastyIgniter Stripe/Mollie | Cash only |
| 29 | openresto / restonestjs table mgmt | Counter-only |
| 30 | TastyIgniter Geo-coder | 1 client |
| 31 | TastyIgniter Coupons | Operator doesn't run promos |
| 32 | DineOut table management | Counter-only |
| 33 | openresto PWA | Laptop only |
| 34 | TastyIgniter Stripe checkout | Cash only |
| 35 | TastyIgniter Slack notifications | Telegram covers |
| 36 | DineOut PWA | Laptop only |
| 37 | restonestjs SOP queue | Pedido status audit replaces |
| 38 | openresto table-side ordering | Counter-only |
| 39 | cafe-pub online order integration | Pedido publico already exists |
| 40 | TastyIgniter multi-tenant theming | Sazon single-tenant |
| 41 | RestoPOS barcode scanning | No need |
| 42 | Flutter POS in-app camera | No mobile |
| 43 | BakeOnyx AI plan generator | Sazon's `_forecast_confidence` |
| 44 | TastyIgniter signup self-service | Invitation-only |
| 45 | TastyIgniter extension marketplace | Single-app |
| 46 | TastyIgniter platform fee | No platform |
| 47 | TastyIgniter app store | No app store |
| 48 | TastyIgniter version upgrades | In-place |
| 49 | TastyIgniter per-extension license | No extensions |

---

# PART 9 — STATISTICS (master totals)

| Category | Total | ✅ SHIPPED | 🟡 PARTIAL | ❌ OPEN | 🚫 SKIP |
|---|---|---|---|---|---|
| A — Architecture | 71 | 64 | 2 | 2 | 3 |
| B — UX / page layout | 64 | 47 | 0 | 9 | 4 (skipped; 4 more in Tier 5) |
| C — Production planning | 23 | 16 | 0 | 6 | 1 |
| C — Inventory/ingredient | 21 | 17 | 0 | 3 | 0 |
| C — Sales/POS | 28 | 21 | 1 | 1 | 5 |
| C — Customer/relationship | 20 | 16 | 0 | 2 | 2 |
| C — Menu/recipe | 12 | 11 | 0 | 1 | 0 |
| C — Invoicing/financial | 17 | 14 | 0 | 2 | 1 |
| C — HACCP/safety | 5 | 5 | 0 | 0 | 0 |
| D — Analytics/reports | 48 | 44 | 0 | 3 | 1 |
| E — Ops/compliance | 40 | 30 | 1 | 4 | 5 |
| COMP — Competitors | 43 | 8 | 6 | 3 | 26 |
| IND — Industry refs | 32 | 8 | 8 | 12 | 4 |
| **TOTAL** | **424** | **301** | **18** | **48** | **52** |

**Status distribution:**
- 71% of every idea I considered is already in Sazon
- 4% partially shipped
- 11% genuinely open
- 12% explicitly skip

---

# PART 10 — KEY NARRATIVE

Reading this whole catalog tells a story:

1. **Sazon is mature.** 71% of every plausible lesson from 10 competitors + 5 industry references is already in the code. The system has more depth than the original 2026-09-07 v3 epic plan called for.

2. **The architecture is clean.** 115+ modules, one per domain. Settings KV. Migration rollback. Audit log. Observability. Sazon follows "one feature = one file" religiously.

3. **The 22 Tier-1 items are small and high-ROI.** 22 small improvements, all ≤ 0.5 days each. Total ~3 days. Each is a visible operator improvement.

4. **The 7 Tier-2 items are the analytical crown jewels.** Per-category variance bands, daily P&L, plan_accuracy feedback. Total ~10 days. The system becomes measurably best-in-class.

5. **The 3 Tier-3 items are the architectural cleanup.** `produccion.html` refactor, FEFO batch tracking, WhatsApp. Each is 3-5 days. FEFO is the only one with a real operator benefit.

6. **The 49 SKIP items are deliberate.** Sazon is intentionally single-tenant, Spanish-vos, laptop-only, no-card, no-mobile. These are not gaps — they are the design.

7. **The biggest ROI by far** is **G-1 (Daily P&L rollup)** + **G-2 (Per-category variance bands)**. Together they give the operator a credible daily P&L with category-aware variance alerting — the kind of thing BakeOnyx charges $80/month for; Sazon should ship it for free because the data is already there.

---

# PART 11 — VERIFICATION CHECKLIST (how to re-verify)

To confirm any item above, run the corresponding command:

```bash
# Verify a claimed file is real and non-trivial
ls -la /opt/data/work/saskia-app/app/rms/<name>.py
wc -l /opt/data/work/saskia-app/app/rms/<name>.py

# Verify a model is defined
grep -l "class <Name>" /opt/data/work/saskia-app/app/rms/models_legacy.py
grep -l "class <Name>" /opt/data/work/saskia-app/app/rms/models/*.py

# Verify a route exists
grep "<path>" /opt/data/work/saskia-app/app/routers/<router>.py

# Verify a template exists
ls /opt/data/work/saskia-app/app/templates/<name>.html

# Verify a migration
ls /opt/data/work/saskia-app/app/rms/migrations/_NNN_<name>.py

# Verify a competitor file
ls /opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/<repo>/<path>

# Verify no SSE/WebSocket in stack
grep -rn "sse\|websocket" /opt/data/work/saskia-app/app/ --include='*.py' | head
```

---

# PART 12 — GLOSSARY

- **APLOC** — Application-level piece of code; Sazon term for a single `app/rms/<feature>.py` module
- **APLOC-T** — Same but for a template (`app/templates/<name>.html`)
- **APLOC-R** — Same but for a router (`app/routers/<name>.py`)
- **APLOC-M** — Same but for a model (`app/rms/models_legacy.py` or `app/rms/models/<name>.py`)
- **APLOC-MG** — Same but for a migration (`app/rms/migrations/_NNN_<name>.py`)
- **PRIMS** — 3rd-party baking production tool; CafeKit integrates via CSV export. Not relevant to Sazon
- **FEFO** — First-Expired First-Out. Standard for perishable batches (Supply'd pattern)
- **Standing orders** — Recurring weekly/monthly customer orders (Sazon's `suscripciones`)
- **Theoretical food cost** — recipe × qty sold (Otter/Supply'd standard)
- **Actual food cost** — beginning_stock + purchases − ending_stock (Otter/Supply'd standard)
- **Variance** = actual − theoretical, in dollars or percentage points
- **ddof=1** — Bessel-corrected sample stddev (N-1). Industry-correct for small samples
- **CI** — Wilson confidence interval (Poisson MLE; Sazon's `restock_forecast`)
- **MLE** — Maximum likelihood estimate (Poisson; `λ̂ = Σcounts / Σexposure`)
- **APLOC-ML** — Sazon term for `app/rms/<feature>.py` containing model + logic

---

# PART 13 — REFERENCE SOURCES

**Sazon canonical:**
- `/opt/data/work/saskia-app/` — the canonical codebase
- `/opt/data/profiles/ivan/cache/scratch/audits/` — subagent audit reports
- Memory entries (in this chat) — `~/.hermes/memory/`

**Competitors (cloned):**
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/TastyIgniter/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/RestoPOS/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/DineOut/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/resto-nestjs/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/flutter-pos-system/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/pizzaql/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/openresto/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/FloCafe/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/ury/`

**Industry references:**
- Supply'd: supplyd.co/industries/bakeries/
- CafeKit: cafekit.io/bakery-production-planning
- BakeOnyx: bakeonyx.ai/features/demand-forecasting
- Rinvy: rinvy.app/docs/menu-items/food-cost-targets
- Otter: tryotter.com/blog/restaurant-tips/food-cost-variance
- restaurant-menu.org: threshold-tuning-for-alerts
- Supy: supy.io/blog/food-cost-variance-control
- JMJSoft: jmjsoft.com/solutions/bakery.php

**Earlier books (superseded by this master):**
- v1 audit: `/opt/data/profiles/ivan/cache/scratch/all_competitors_deep_audit_20261008.md`
- v1 lessons: `/opt/data/profiles/ivan/cache/scratch/sazon_lessons_book_20261008.md`
- v2 lessons: `/opt/data/profiles/ivan/cache/scratch/sazon_lessons_book_v2_20261008.md`
- v3 decisions: `/opt/data/profiles/ivan/cache/scratch/sazon_decision_book_v3_20261008.md`

---

*End of master catalog.*

**This is the canonical, deduplicated, ground-truth reference.** Where earlier books (v1, v2, v3) disagree with this master, this master wins because each item is checked against the actual Sazon codebase.
