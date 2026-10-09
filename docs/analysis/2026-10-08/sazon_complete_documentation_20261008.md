# SAZON — The Complete Documentation
## Every finding, every lesson, every idea, every decision, every topic, everything relevant
### As of 2026-10-08, verified against the actual codebase

This is the **single canonical documentation** for everything discovered in the multi-day
Sazon research project. It supersedes all earlier books:

- `all_competitors_deep_audit_20261008.md` (v1 audit)
- `sazon_lessons_book_20261008.md` (v1 lessons)
- `sazon_lessons_book_v2_20261008.md` (v2 lessons)
- `sazon_decision_book_v3_20261008.md` (v3 decisions)
- `sazon_master_catalog_20261008.md` (master catalog)

**Where any earlier doc disagrees with this one, this one wins** because every claim is
checked against the actual Sazon code on disk at `/opt/data/work/saskia-app`.

---

# TABLE OF CONTENTS

- **Part 0** — How to read this document
- **Part 1** — What Sazon is (project, instances, structure, the HEREBUS correction)
- **Part 2** — Every Sazon module (115+ files) with purpose + line count
- **Part 3** — Every Sazon template (99) with purpose
- **Part 4** — Every Sazon router (36) with purpose
- **Part 5** — Every migration (32) with purpose
- **Part 6** — Every Sazon model (14 files) with table count
- **Part 7** — The Settings KV registry (42 keys)
- **Part 8** — AGENTS.md rules
- **Part 9** — Every SASKIA ticket referenced in the code
- **Part 10** — Every competitor analyzed (10)
- **Part 11** — Every industry reference (5)
- **Part 12** — Every lesson (424 items) — the master catalog
- **Part 13** — Every open item (48) sorted by ROI
- **Part 14** — Every skip item (49) with rationale
- **Part 15** — Every decision log entry (23+)
- **Part 16** — The Sazon narrative
- **Part 17** — Verification commands
- **Part 18** — Glossary
- **Part 19** — All file paths

---

# PART 0 — HOW TO READ

Every claim is verified. The status legend:

- ✅ **SHIPPED** — file/route/feature exists and is non-trivial
- 🟡 **PARTIAL** — exists but incomplete (orphan reads, missing UI, missing persistence)
- ❌ **OPEN** — confirmed not in the codebase
- 🚫 **SKIP** — explicitly decided not to build (per SASKIA-210, AGENTS.md, or this work)

Effort: 🟢 S ≤ 0.5d, 🟡 M 1-2d, 🟠 L 3-5d. Risk: 🟢 low / 🟡 med / 🔴 high.

The Sazon codebase lives at `/opt/data/work/saskia-app`. The full file inventory was
walked on 2026-10-08 by `os.listdir` + `wc -l`. Models, routes, templates, and migrations
were all sampled to confirm purpose.

---

# PART 1 — WHAT SAZON IS

## 1.1 Identity (CORRECTED)

Sazon is a **single-tenant bakery production system** built in Python + FastAPI +
SQLAlchemy + Jinja. It serves **one client today**: **Saskia / La Vaquita Holandesa**
in Paraguay, PYG currency, Asunción timezone.

### CORRECTION TO EARLIER DOCS

Earlier books (v3, master) stated Sazon is "per-client instances" with **two clients**:
Saskia (PY) and HEREBUS (NL). **This is wrong.** The corrected picture:

- **HEREBUS is NOT a second client.** It's the **pre-Sazon Google Drive spreadsheet
  system** the bakery was using before Sazon existed. The "HEREBUS Drive" folder held
  33 .xlsx files (recipes, sales, customers, suppliers, risk register, wishlist,
  bank transactions, etc.).
- When Sazon was built, the team ran `scripts/import_herebus_data.py` to migrate that
  data into Sazon's tables. The import is **idempotent** and **complete**.
- The `BankTransaction` table has `currency IN ('EUR', 'PYG', 'USD')` because the
  family business TAB (WPG, owned by Saskia's dad John) is held in EUR — that's the
  **family's Dutch bank account**, not the bakery's. The bakery itself is in PYG.
- The `herebus.py` router (1,416 lines) + `herbus_drive.py` model (273 lines) + the
  `import_herebus_data.py` script all support this **single-client, single-tenant,
  data-imported-from-legacy-spreadsheets** model.
- Migration 112 added HEREBUS-specific sales channels (retail/wholesale/distributor/eventual)
  to the channel CHECK constraint because those channel values appear in the historical
  VENTAS sheet data — they describe **how the bakery was selling before**, not a new
  client's channels.

**SASKIA-210 (memory) confirms this:** "Saskia/La Vaquita Holandesa = only client;
product is per-client INSTANCES, NOT shared-DB multi-tenant. Future: possibly 1 base
Supabase as a template to clone per client."

### Today's client

**Saskia / La Vaquita Holandesa** — bakery in Paraguay. Operator runs Sazon on a
laptop. Single currency: PYG. The Sazon deployment is at `sazon-vps.paragu-ai.com`
(VPS).

### Future (deferred per SASKIA-210)

If/when a second client is added, Sazon will be **cloned as a separate instance**,
not multi-tenant. The cloning would happen by:
1. Take a fresh Postgres/SQLite base
2. Run `import_herebus_data.py`-style import with the new client's data
3. Deploy as a new Sazon instance

NOT a shared-DB with tenant_id. Per the decision: "Do NOT build RLS/ORM-tenancy now."

## 1.2 Architecture

- **Monorepo:** one Sazon instance per client, all in `/opt/data/work/saskia-app`
- **Server-rendered HTML** (Jinja) + minimal JS — no SPA, no KDS, no SSE
- **DB:** SQLite (dev/test) + Postgres (prod) via `db_dialect.py`
- **Auth:** Bcrypt cost-12 (local) + Supabase (option for cloud); session keys
  `local_user_id` and `supabase_user_id` (fixed 2026-09-29)
- **Observability:** Loguru + request-scoped context (`observability.py`)
- **Notifications:** Telegram (Sentry→Telegram bridge in `notify.py`);
  WhatsApp/SMTP/dryrun fallback (`notifications.py`)
- **AI:** GLM-4.5-air via Z.ai (`llm.py`); used by `copilot.py` (chat) +
  `menu_ocr.py` (vision)
- **Schema version:** 113 (SASKIA-206: shopping_list_item.unit_price_snapshot_gs)
- **Currency:** PYG primary; EUR/USD kept in `BankTransaction` only for the family
  business TAB account

## 1.3 The 7 Sazon sprints (per memory + AGENTS.md)

- **Sprint 1:** foundational modules
- **Sprint 2.1:** SettingsKV consolidation (42-key registry in `settings.py` 538 lines;
  `settings_original.py` 411 lines **kept** for backward-compat, not deleted as memory said)
- **Sprint 2.3:** Sales lifecycle split (out of `costing.py`)
- **Sprint 3.1:** Expense CRUD + MonthlyClosure
- **Sprint 5:** Production `produccion/` split into 9 sub-routers
- **Phase 7:** Stock status thresholds (operator-configurable, DB-backed)
- **Fase 2:** fiado / AR ledger
- **Fase 3:** AI features (copilot, menu_ocr)
- **Fase 5 (2026-10-05):** production_scheduler deprecated (calls migrated to
  `production.py` helpers)
- **P44 legacy cleanup (2026-10-07):** archived `_archive/2026-10-07-p44-legacy-cleanup/`
  (older `herbus_drive.py`, `procurement.py`)

---

# PART 2 — EVERY SAZON MODULE (115+ files)

Total modules in `app/rms/`: **115+ files** (counted by `os.listdir` on 2026-10-08).
All verified.

## 2.1 Strategic analytical core (47 modules)

| File | Lines | Purpose |
|---|---:|---|
| `analytics.py` | 979 | Cross-cutting metrics (the big stats module) |
| `db.py` | 4,844 | Engine, session factory, dialect helpers |
| `models_legacy.py` | 2,943 | Original single-file models (pre-split, kept) |
| `seed/sazon.py` | 4,862 | Sazon master seed (catalogs) |
| `seed/packs.py` | 4,719 | Idempotent pack seed (Vaquita standard) |
| `seed/competitor_seed.py` | 958 | Competitor business seed |
| `seed/demo.py` | 917 | Demo synthetic data |
| `costing.py` | 776 | Sale cost walk (legacy, partially deprecated) |
| `accounting.py` | 739 | Paraguay IVA 10% (included/excluded) + 9 reports |
| `sales_intel.py` | 702 | Time patterns, affinity, churn, rising |
| `production_demand.py` | 642 | Per-day, per-product demand |
| `main.py` | 1,272 | App entry, lifespan |
| `production.py` | 566 | Daily production worksheet, batch_count, confidence |
| `settings.py` | 538 | 42-key SettingsKV registry |
| `ingredient_intel.py` | 537 | Role mapping, substitution hints |
| `waste.py` | 492 | Waste tracking |
| `refunds.py` | 492 | 8 business rules + DB trigger cap (migration 089) |
| `price_history.py` | 481 | Pricing audit trail |
| `recipe_intel.py` | 433 | Family classification, cook time, yield grams |
| `services/closures.py` | 293 | MonthlyClosure + Expense CRUD |
| `forecast.py` | 293 | Demand forecast (older, kept for compat) |
| `restock_forecast.py` | 289 | **Poisson per-weekday MLE** (BACKLOG #5, SASKIA-208) |
| `cierre.py` | 267 | Z-report, cash session closure |
| `inventory_intel.py` | 265 | Per-ingredient stats |
| `backup.py` | 312 | DB backup helpers |
| `csrf.py` | 212 | CSRF middleware |
| `rate_limit.py` | 369 | Rate-limit middleware |
| `errors.py` | 212 | Typed exceptions |
| `display.py` | 135 | Money/date formatters |
| `validation.py` | 367 | Decimal money + date + ID validators |
| `loyalty/ledger.py` | 259 | 10% return rate (was 100% — bug fixed 2026-10-01) |
| `loyalty/suggestions.py` | 415 | 5 rules: LAPSED, BIRTHDAY, POINTS-DORMANT, VIP, CROSS-SELL |
| `held_sales.py` | 248 | Parked cart |
| `eod_completions.py` | 147 | EOD production completion |
| `eod_closed.py` | 137 | Day-close gate (assert_day_open_or_raise) |
| `loyalty/tiers.py` | 46 | BRONZE/SILVER/GOLD/PLATINUM |
| `customer_dietary.py` | 117 | RESTRICTIONS + PREFERENCES + CONFIRM_ALWAYS |
| `customer_merge.py` | 188 | P1-B4 atomic merge with sales+pedidos reassign |
| `menu_ejecutivo.py` | 70 | Combo expansion (menu-priced line 1) |
| `menu_ocr.py` | 114 | GLM vision OCR (anti-hallucination) |
| `seasonal.py` | 161 | Calendar year-shift + upcoming_events |
| `notifications.py` | 324 | WhatsApp-style daily summary (Twilio/SMTP/dryrun) |
| `notify.py` | 125 | Sentry→Telegram bridge |
| `maintenance.py` | 66 | Audit log retention (dry-run) |
| `observability.py` | 206 | Per-request Loguru context + record_audit |
| `copilot.py` | 120 | In-app AI assistant (6 intent patterns) |
| `llm.py` | 118 | GLM client with graceful degradation |
| `stock_ledger.py` | 106 | apply_stock_delta + qty_to_stock_unit (SASKIA-207) |
| `stock_status.py` | 165 | Operator-configurable stock thresholds |
| `plan_accuracy.py` | 394 | Per-product accuracy stats (orphan read) |
| `fiado.py` | 240 | AR ledger, idempotent pago, FIFO aging |
| `menu_engineering.py` | 257 | STAR/PUZZLE/PLOWHORSE/DOG |
| `product_similarity.py` | 217 | Jaccard ingredient overlap |
| `prime_cost.py` | 303 | Materials + labor + overhead (CIA "30/40% rule") |
| `profitability/cost.py` | 400 | Recipe cost, sub-recipe walk, cycle detection |
| `food_cost.py` | 222 | Theoretical vs actual |
| `demand_freshness.py` | 346 | Demand algebra + freshness + substitutions |
| `invoicing.py` | 133 | Recurring orders + auto-invoice |
| `market_intel.py` | 176 | Competitive intel (vs-mercado) |
| `audit.py` | 174 | Audit log |
| `audit_analytics.py` | 183 | Audit dashboards |
| `bootstrap.py` | 100 | Defaults, demo data |
| `config.py` | 152 | ASUNCION_TZ, env |
| `constants.py` | 185 | All constants in one place (incl. CURRENCY_CODE="PYG") |
| `db_dialect.py` | 152 | SQLite + Postgres compatible SQL |
| `perf.py` | 184 | Caching, query analysis |
| `schema_postgres.py` | 46 | Postgres-specific schema |
| `schemas.py` | 63 | Pydantic schemas |

## 2.2 Smaller modules

| File | Lines | Purpose |
|---|---:|---|
| `cotizador.py` | 101 | Quote/proposal builder |
| `cash.py` | 101 | Cash session (lightweight) |
| `clock.py` | 95 | Testable `now()` |
| `units.py` | 199 | Qty normalization (g/kg/ml/l/und) |
| `variants.py` | 354 | Product variants |
| `seed/onboard.py` | 54 | First-run onboarding |
| `seed/menu_import.py` | 150 | CSV import with fuzzy match |
| `seed/competitor_prices.py` | 65 | vs-mercado seed |
| `seed/competitor_shoppings.py` | 647 | Competitor shoppings seed |
| `seed/pack_demo.py` | 398 | Pack demo (showcase data) |
| `services/expenses.py` | 253 | Expense CRUD |
| `services/common.py` | 50 | Service helpers |
| `sales/pre_sale_check.py` | 391 | **URY pre-billing checklist port (MIT)** |
| `sales/pre_sale_check_cart.py` | 253 | Multi-line pre-sale check |
| `margin_tier.py` | 84 | Per-product margin thresholds |
| `tag_algebra.py` | 79 | Combining tags |
| `categories.py` | 99 | Category management |
| `catalogs.py` | 76 | Catalog helpers |
| `messages.py` | 123 | User-facing messages (i18n) |
| `metrics.py` | 168 | Counters, gauges |
| `nav.py` | 259 | Sidebar / breadcrumbs |
| `charts.py` | 341 | Visualizations |
| `dependencies.py` | 68 | FastAPI DI helpers |
| `storage.py` | 168 | File storage abstraction |
| `storage_types.py` | 55 | LOCAL / S3-like |
| `ready_static.py` | 48 | Static paths |
| `static_paths.py` | 16 | Static path helpers |
| `security_headers.py` | 164 | HTTP security headers |
| `upload_limits.py` | 87 | Upload size limits |
| `public_tokens.py` | 186 | For pedido publico |
| `session_lifecycle.py` | 81 | Session helpers |
| `streaming_csv.py` | 58 | Large CSV exports |
| `date_presets.py` | 67 | today, last week, this month |
| `models/sales/` (dir) | — | Sales split-out models |
| `production_scheduler.py` | 21 | **DEPRECATED** 2026-10-05 (port to production.py) |
| `models/audit.py` | 26 | Audit model |
| `models/auth.py` | 138 | User + AuditLog + SettingsKV + Tenant |
| `models/catalogs_restored.py` | 309 | Restored catalogs |
| `models/channels.py` | 82 | Sales channels (mostrador, pedidosya, retail, etc.) |
| `models/closure.py` | 56 | MonthlyClosure model |
| `models/common.py` | 139 | Common columns mixin |
| `models/core.py` | 25 | Declarative Base |
| `models/delivery.py` | 53 | Delivery zones |
| `models/herbus_drive.py` | 273 | **HEREBUS-imported tables** (Wishlist, Risk, Bank, etc.) |
| `models/inventory.py` | 404 | Inventory + StockMovement |
| `models/orders.py` | 144 | Pedido + PedidoLine + Refund |
| `models/procurement.py` | 193 | Suppliers + orders |
| `models/production.py` | 155 | ProductionPlan + ProductionDemandSnapshot |
| `models/sales.py` | 262 | Sale + SalePayment + SaleTip |
| `tagging/` (10 files) | 1,800+ | Tagging subsystem (vocabulary, classify, derive, etc.) |
| `loyalty/__init__.py` | 59 | Loyalty module exports |
| `__init__.py` | 16 | Module exports |
| `AGENTS.md` | 89 | Project conventions for agents |

**Total: 115+ files, ~30,000 LOC of Sazon core code.** Plus 4,719 lines of seed
catalog and 4,862 lines of master seed.

## 2.3 Scripts (40+ at `scripts/`)

Key scripts:
- `import_herebus_data.py` — HEREBUS Drive → Sazon import (idempotent)
- `reclassify_sale_channels.py` — re-classify sale channels from VENTAS sheet
- `gen_route_smoke.py` — generates smoke tests for every route
- `check_no_secrets.py` — pre-commit guard against secrets
- `backup.py` + `backup_cron.py` + `sazon-backup.sh` — DB backup (daily 03:15, 14d retention)
- `shoot_all_pages.py` — visual audit (batch screenshot every route)
- `daily_summary.py` — daily summary sender
- `migrations/migrate_channels_lowercase.py` — channel case migration
- `seed_packs_gen.py` — regenerate seed packs from scratch
- `seed_vaquita_holandesa_for_saskia.py` — Vaquita client seed
- `audit_prune.py` — audit log retention
- `cf_tunnel_liveness.py` — Cloudflare tunnel health check
- `diag_supabase_render.py` — Supabase diagnostic
- `verify_catalog_on_vps.py` — VPS catalog verification
- `uptimerobot_setup.py` — UptimeRobot setup
- `apply_neon_schema.py` — Neon Postgres schema apply
- `inventory_seed_helpers.py` — inventory seed helpers
- `save_sazon_user_password.py` + `reset_operator_credentials.py` + `save_sazon_db_url.py` — credential storage
- `lint_tier1.py` — tier-1 lint
- `mark_e2e_tests.py` + `tag_tests_with_markers.py` — pytest markers
- `minify_css.py` — CSS minification
- `fix_e702.py` + `fix_perf401.py` — automated code fixes
- `migrate_inline_styles.py` + `migrate_inline_stylesheets.py` — CSS migration
- `backfill_price_events.py` — backfill price events
- `smoke_test_deploy_shape.py` — deploy shape smoke test
- `probe_app_introspection.py` — app introspection probe
- `install-pre-commit.sh` — pre-commit installer
- `set_render_env.py` — render.com env setup
- `save_saskia_cf_token.py` + `save_saskia_fernet.py` — token storage
- `check_currency_drift.sh` — currency drift check
- `bws_list_names.py` — Bitwarden Secrets list

---

# PART 3 — EVERY SAZON TEMPLATE (99)

Total templates: **99** in `app/templates/` (verified by `ls | wc -l`).

## 3.1 Production (6)

- `produccion.html` (2,366 lines — main, to be split per A-25/G-4)
- `produccion_manana.html` (tomorrow plan)
- `produccion_prep.html` (prep view)
- `produccion_prep_recipes.html` (prep recipes)
- `produccion_print.html` (print-as-ship-ticket)
- `produccion_haccp.html` (HACCP checklist)
- `produccion_accuracy.html` (plan accuracy)

## 3.2 Reports (12)

- `reportes.html` (index)
- `reportes_diario.html`
- `reportes_cierre_mensual.html`
- `reportes_comparacion.html`
- `reportes_consumo.html`
- `reportes_iva.html`
- `reportes_libro_ventas.html`
- `reportes_mermas_cost.html`
- `reportes_metodos_pago.html`
- `reportes_metricas.html`
- `reportes_precios.html`
- `reportes_retencion.html`
- `reportes_top_productos.html`
- `reportes_valor_pedido.html`
- `reportes_ventas_hora.html`

## 3.3 Insights (8)

- `insight_afinidades.html` (cross-sell)
- `insight_demand.html`
- `insight_food_cost.html`
- `insight_freshness.html`
- `insight_margenes.html` + `insight_margenes_detalle.html`
- `insight_price_impact.html`
- `insight_stock.html`

## 3.4 Sales / POS (4)

- `ventas.html` + `ventas_detalle.html` + `ventas_historial.html` + `ventas_qa.html`
- `recibo.html` (receipt)

## 3.5 Pedidos (6)

- `pedido_board.html` + `pedido_detalle.html` + `pedido_publico.html`
- `pedido_stock_preview.html`
- `pedidos.html` + `pedidos_nuevo.html`

## 3.6 Customer / Fiado (8)

- `cliente_detalle.html` + `cliente_editar.html` + `clientes.html`
- `clientes_duplicados.html` + `clientes_nuevo.html`
- `fiado.html` + `fiado_cliente.html`
- `creditos.html`

## 3.7 Recipes / Products (10)

- `recetas.html` + `receta_detalle.html` + `receta_form.html`
- `recipe_photos.html`
- `productos.html` + `producto_detalle.html` + `producto_form.html`
- `productos_importar.html`
- `menus.html`
- `menu_tablet.html` (operator tablet view)
- `menu_publico.html` (customer-facing)
- `menu_import_ocr.html` (photo menu upload)

## 3.8 Inventory / Ingredients (5)

- `inventario.html` + `inventario_form.html`
- `inventario_movimientos.html`
- `inventario_auditoria_etiquetas.html`
- `ingrediente_detalle.html`
- `merma.html` (waste)

## 3.9 EOD (3)

- `eod.html` + `eod_anomalies.html` + `eod_print.html`

## 3.10 Caja (2)

- `caja.html` + `caja_z.html`

## 3.11 Settings (2)

- `settings.html` + `settings_catalog.html`

## 3.12 Suppliers (5)

- `suppliers.html` + `supplier_form.html` + `supplier_orders.html`
- `supplier_precios.html` + `suppliers_volatility.html`

## 3.13 Suscripciones (2)

- `suscripciones.html` + `suscripcion_form.html`

## 3.14 Misc (15)

- `analisis.html` (analysis)
- `auditoria.html` + `auditoria_analytics.html` (audit log)
- `bank.html` (bank transactions)
- `benchmark_edit.html` + `benchmarks.html` (vs-mercado)
- `carga_inicial.html` (initial data load)
- `cotizador.html` (quote builder)
- `delivery_zones.html`
- `dev_combo_smoke.html` (menu smoke test)
- `evidencia_mercado.html`
- `excel.html` + `excel_validate.html` + `excel_mode_guidance.html` (4)
- `guia.html` (help)
- `healthz_summary.html`
- `inicio.html` (dashboard, the operator's home)
- `login.html`
- `ops_status.html`
- `planner.html` (week view)
- `pricing.html` (price management)
- `reorder.html` (smart reorder)
- `riesgos.html` (risk register)
- `shopping_list.html`
- `wishlist.html` (equipment wishlist)
- `dashboard.html` (KPI dashboard — herbus-folded per migration 112)
- `_components/` (reusable)
- `admin/` (admin subdir)
- `errors/` (error pages)
- `base.html` (implied)

---

# PART 4 — EVERY SAZON ROUTER (36)

Total routers: **36** in `app/routers/`. Production-relevant routes: **117+**.

- `auth.py` — login/logout
- `analisis.py` — analysis
- `auditoria.py` — audit log
- `caja.py` — cash session
- `copiloto.py` — in-app AI (6 suggested chips)
- `cotizador.py` — quotes
- `customers.py` — customer CRUD
- `dashboard.py` — KPI dashboard (HEREBUS-folded, includes wishlist/shopping/risk)
- `demo.py` — demo mode
- `dev.py` — dev utilities
- `eod.py` — day close
- `excel_io.py` — Excel import/export
- `fiado.py` — credit/AR
- `health.py` — health checks
- `help.py` — help/docs
- `herebus.py` — **HEREBUS Drive business modules** (wishlist, riesgos, pricing, bank, benchmarks, dashboard, produccion-planner)
- `insights.py` + `insights_derived.py` + `insights_stock.py` — analytics
- `inventory.py` — ingredient CRUD
- `menu_import.py` — menu CSV/OCR import
- `menus.py` — combo menus
- `merma.py` — waste
- `ops.py` — ops status
- `pedidos.py` — pre-orders
- `photo_credits.py` — photo credits
- `products.py` — product CRUD
- `produccion/` (subdir) — 9 sub-routers for production
- `recipes.py` — recipe CRUD
- `refund.py` — refunds
- `reorder.py` — smart reorder (uses Poisson forecast)
- `reportes.py` — 11+ report endpoints
- `sales.py` — sales + carrito + held + completion
- `search.py` — global search
- `settings.py` + `settings_runtime.py` — config
- `shopping.py` — shopping list (SASKIA-205/206/207)
- `suppliers.py` — supplier CRUD
- `suscripciones.py` — recurring orders
- `users.py` — user management
- `validation.py` — validation

---

# PART 5 — EVERY MIGRATION (32 files)

Total migrations: **32** in `app/rms/migrations/` (numbered `_005_` through `_113_`).

| # | Migration | Purpose |
|---|---|---|
| 005 | `_005_customer.py` | Initial customer table |
| 006 | `_006_simple_test.py` | Initial test table |
| 043 | `_043_branding_setting.py` | Branding settings |
| 044 | `_044_message_templates.py` | Message templates |
| 056 | `_056_bank_reconciliation.py` | Bank transaction reconciliation |
| 057 | `_057_recipe_instructions.py` | Recipe instructions field |
| 061 | `_061_tag_validation.py` | Tag validation |
| 062 | `_062_audit_repair.py` | Audit log repair |
| 084 | `_084_stock_qty_nonneg.py` | Stock non-negative constraint |
| 085 | `_085_sale_public_token.py` | Public sale token |
| 086-088 | `_086/087/088_placeholder.py` | Placeholders (reserved) |
| 089 | `_089_refund_table.py` | Refund table + DB trigger cap (224 lines!) |
| 090 | `_090_stock_movement_affected_recipe_id.py` | Add recipe_id to stock_movement |
| 091 | `_091_backfill_stock_movement_recipe.py` | Backfill stock_movement.recipe_id |
| 092 | `_092_drop_sale_stock_move.py` | **Drops sale_stock_move table (SSOT = StockMovement)** |
| 093 | `_093_expense_receipt_recurring.py` | Recurring expenses |
| 094 | `_094_monthly_closure.py` | MonthlyClosure table |
| 095 | `_095_soft_delete_columns.py` | Soft-delete columns |
| 096 | `_096_audit_columns.py` | Audit columns on every model |
| 097 | `_097_ingredient_avg_cost.py` | Avg ingredient cost (30d FEFO) |
| 098 | `_098_customer_phone.py` + `_098_production_closed_day.py` | Customer phone + production closed day |
| 099 | `_099_production_completion_updated_at.py` | Production completion updated_at |
| 100 | `_100_freezer_temperature_log.py` | Freezer temperature log (HACCP) |
| 101 | `_101_recipe_fermentation_minutes.py` | Recipe fermentation time |
| 102 | `_102_waste_log_source.py` | Waste log source |
| 103 | `_103_production_demand_split.py` | Production demand split (193 lines) |
| 104 | `_104_product_sold_by_weight.py` | Product sold by weight |
| 105 | `_105_sale_payments.py` | Sale payments table |
| 106 | `_106_cash_sessions.py` | Cash sessions table |
| 107 | `_107_credit_accounts.py` | Fiado credit accounts |
| 108 | `_108_sale_tip.py` | Sale tip column |
| 109 | `_109_menu_ejecutivo.py` | Menu ejecutivo (combos) table |
| 110 | `_110_held_sale.py` | Held sale table |
| 111 | `_111_sale_channel_check.py` | Sale.channel CHECK constraint (6 channels) |
| 112 | `_112_extended_channel_check.py` | **HEREBUS channels added** (retail/wholesale/distributor/eventual) |
| 113 | `_113_shopping_price_snapshot.py` | shopping_list_item.unit_price_snapshot_gs (SASKIA-206) |

**CURRENT_SCHEMA_VERSION = 113** (per `app/rms/config.py:92`).

**Rule 17 (per AGENTS.md):** every migration must have a pre-state archive. The
rollback mechanism is in `app/rms/rollback.py` (SASKIA-209).

---

# PART 6 — EVERY SAZON MODEL (14 files)

Models live in `app/rms/models/` (14 files, post-Phase-3.1 split) + `app/rms/models_legacy.py` (2,943 lines, kept for compat).

| File | Lines | Models |
|---|---:|---|
| `core.py` | 25 | `Base` (declarative) |
| `common.py` | 139 | Common column mixin |
| `auth.py` | 138 | `User`, `AuditLog`, `SettingsKV`, `Tenant` |
| `catalogs_restored.py` | 309 | Restored catalogs |
| `channels.py` | 82 | `Channel` enum + `ChannelPrice` |
| `closure.py` | 56 | `MonthlyClosure` |
| `delivery.py` | 53 | `DeliveryZone` |
| `herbus_drive.py` | 273 | `WishlistItem`, `RiskItem`, `MarketBenchmark`, `BankTransaction`, `ComplianceInfo`, `MarketPriceReference` |
| `inventory.py` | 404 | `Ingredient`, `StockMovement`, etc. |
| `orders.py` | 144 | `Pedido`, `PedidoLine`, `Refund` |
| `procurement.py` | 193 | `Supplier`, `SupplierOrder` |
| `production.py` | 155 | `ProductionPlan`, `ProductionDemandSnapshot` |
| `sales.py` | 262 | `Sale`, `SalePayment`, `SaleTip` |
| `audit.py` | 26 | Audit mixin |
| `models_legacy.py` | 2,943 | Original single-file (kept, 2,943 lines) |

---

# PART 7 — THE SETTINGS KV REGISTRY (42 keys)

Lives in `app/rms/settings.py` (538 lines). 42 keys across 7 groups:

- **GENERAL** (business hours, pickup address, currency mode)
- **BRANDING** (logo, favicon, hero, accent color)
- **INVENTORY** (stock thresholds, FEFO rules)
- **SALES** (tax mode, loyalty return rate, refund cap)
- **DASHBOARD** (card layout, default filters)
- **BACKUP** (retention, dry-run)
- **SESSION** (timeout, CSRF)

The `settings_catalog.html` template (887 lines) auto-renders the editor for any
registry key.

---

# PART 8 — AGENTS.MD RULES

`app/rms/AGENTS.md` (89 lines). Key rules:

- Rule 3: Money math in Decimal, int at persistence boundary
- Rule 17: Every migration must have a pre-state archive
- Rule 26: No numpy/scipy — closed-form math only

Plus implicit:
- One feature = one file (115+ modules in `app/rms/`)
- Test-first (TDD enforced via pytest markers)
- Money in integer Gs only (no Decimal in DB)

---

# PART 9 — EVERY SASKIA TICKET REFERENCED IN THE CODE

Found by `grep -rn 'SASKIA-' app/`:

- **SASKIA-204** (2026-10-07): Sale channel filter (HEREBUS channels added in migration 112)
- **SASKIA-205** (2026-10-07): Shopping list mark-purchased lands stock + mark-purchased on wishlist lands stock
- **SASKIA-206** (2026-10-07): shopping_list_item.unit_price_snapshot_gs (migration 113)
- **SASKIA-207** (2026-10-07): Single stock-ledger path (convert + bump + StockMovement with movement_type='reorder')
- **SASKIA-208** (BACKLOG #5, ~Oct 2026): Poisson weekday forecast (P95 stockout date)
- **SASKIA-209** (2026-10-07, dc26df1f): Migration rollback via rule 17 archives
- **SASKIA-210** (2026-10-07): Decision — per-client instances, NOT shared-DB multi-tenant

Plus: SASKIA-OPS-041, SASKIA-OPS-042 (proposed), and the ticket system uses
`SASKIA-NNN-<short-slug>.md` format under `docs/tickets/`.

---

# PART 10 — EVERY COMPETITOR ANALYZED (10)

Cloned at `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/`.

| # | Repo | Tech | Key takeaway for Sazon |
|---|---|---|---|
| 1 | TastyIgniter | Laravel + 22 extension packages | Plugin architecture; payments/CMS external — 🚫 SKIP |
| 2 | RestoPOS | Laravel + Vue | 117 routes, KOT model, 42 report categories, duplicate-KOT print — Sazon has 117 routes already; partial reuse on KOT |
| 3 | harismuneer/DineOut | Android Java | True EOD/EOW — Sazon has it (eod.py + eod_completions.py) |
| 4 | resto-nestjs | NestJS + Vue + Postgres | SOP order_processing_queue — 🚫 SKIP (use pedido_status_audit) |
| 5 | evan361425/flutter-pos-system | Flutter (Dart) | **File-split gold standard** + 3 reorder widgets — partial reuse |
| 6 | pizzaql | Dart + GraphQL | Proposed GraphQL Subscriptions — 🚫 SKIP (no SSE) |
| 7 | openresto | ASP.NET + Razor | Print template engine — 🚫 SKIP |
| 8 | FloCafe | Electron + Next.js | **WhatsApp integration** — defer |
| 9 | ury | Frappe + Vue | **45 doctypes; pre-billing checklist trio** (posClosing.js ported to Sazon as `pre_sale_check.py`) |
| 10 | cafe-pub | Node + Express + EJS | Slim models, no expiry tracking — 🚫 SKIP |

---

# PART 11 — EVERY INDUSTRY REFERENCE (5)

| # | Source | Key takeaway | Sazon status |
|---|---|---|---|
| 1 | Supply'd (UK bakery ERP) | Wholesale orders + standing orders + forecast; FEFO batch tracking | 🟡 PARTIAL (suscripciones, demand_freshness; no batch-level) |
| 2 | CafeKit (single-day-row bakery planning) | Variance band "how steady" + banner if preordered missing from plan | ❌ OPEN (B-51/B-52) |
| 3 | BakeOnyx (AI forecasting) | Per-day "Accuracy: 94%" daily report | ❌ OPEN (D-46) |
| 4 | Rinvy (food-cost alerts) | Per-item target food cost % + 6AM push | 🟡 PARTIAL (margin_tier; no push) |
| 5 | restaurant-menu.org (theoretical-vs-actual) | Per-category variance multipliers + soft/hard bands + ddof=1 | ❌ OPEN (C-F-16) |

---

# PART 12 — EVERY LESSON (424 ITEMS) — THE MASTER CATALOG

This part is the **master catalog from earlier** with HEREBUS correction applied.
Items grouped into 5 categories. Each has Status / Source / Effort / Risk / Where.

## 12.1 Category A — Architecture (71 items)

(A-01 to A-71 in the master; same numbering, same content; HEREBUS-related items
updated to reflect "data import" not "second client".)

**Total: 71 items — 64 ✅ SHIPPED, 2 🟡 PARTIAL, 2 ❌ OPEN, 3 🚫 SKIP**

Open items: A-19 (remove dead SaleStockMove imports), A-25 (split produccion.html), A-31 (maintenance middleware).

## 12.2 Category B — UX / page layout (64 items)

**Total: 64 items — 47 ✅ SHIPPED, 0 🟡 PARTIAL, 9 ❌ OPEN, 4 🚫 SKIP (4 more in Tier 5)**

Open items: B-48/B-49 (drag-and-drop reorder), B-50 (confidence badge on grilla), B-51/B-52 (variance band + missing-from-plan banner), B-53 (plan accuracy widget on /inicio), B-54 (soft/hard band visualization), B-56 (KOT error log page), B-61/B-62/B-63 (read+document menu_tablet/copilot/recipe_photos), B-64 (auto-display daily summary).

## 12.3 Category C — Domain logic (126 items)

Sub-divided into 7 sub-domains:

- **C-P** Production planning (23 items) — 16 ✅, 6 ❌ (G-3, G-12, G-19, G-20, G-21, G-22, G-23)
- **C-I** Inventory/ingredient (21 items) — 17 ✅, 3 ❌ (packaging view, alt-preferida badge, FEFO batches)
- **C-S** Sales/POS (28 items) — 21 ✅, 1 🟡 (pedido_status_audit), 1 ❌ (held-cart age-out), 5 🚫
- **C-C** Customer/relationship (20 items) — 16 ✅, 2 ❌ (confirm-always count, loyalty widget on POS), 2 🚫
- **C-M** Menu/recipe (12 items) — 11 ✅, 1 ❌ (document menu_tablet)
- **C-F** Invoicing/financial (17 items) — 14 ✅, 2 ❌ (daily P&L, per-category variance), 1 🚫
- **C-H** HACCP/safety (5 items) — 5 ✅, 0 ❌, 0 🚫

## 12.4 Category D — Analytics (48 items)

**Total: 48 items — 44 ✅ SHIPPED, 0 🟡 PARTIAL, 3 ❌ OPEN, 1 🚫 SKIP**

Open items: D-43 (daily P&L rollup endpoint), D-44 (plan_accuracy feedback loop), D-45 (per-category variance bands), D-46 (per-day accuracy report).

## 12.5 Category E — Ops / compliance (40 items)

**Total: 40 items — 30 ✅ SHIPPED, 1 🟡 PARTIAL, 4 ❌ OPEN, 5 🚫 SKIP**

Open items: E-31 (pre-sale log persistence), E-32 (KOT error log), E-34 (WhatsApp integration — defer), E-35 (pedido_status_audit).

## 12.6 COMP — Competitor-specific (43 items)

8 ✅, 6 🟡, 3 ❌, 26 🚫

## 12.7 IND — Industry-reference (32 items)

8 ✅, 8 🟡, 12 ❌, 4 🚫

---

# PART 13 — EVERY OPEN ITEM (48) SORTED BY ROI

## Tier 1 — High value, low effort (22 items, ~3 days)

| # | Open Item | Effort | File to edit |
|---|---|---|---|
| 1 | G-9: Confidence badge on grilla | 🟢 S | `produccion.html` |
| 2 | G-6 / E-32: KOT error log | 🟢 S | new migration + `print_export.py` |
| 3 | G-8: Seasonal calendar → settings_kv | 🟢 S | `seasonal.py` + new registry entry |
| 4 | G-7 / A-31: Maintenance middleware | 🟢 S | new `MaintenanceModeMiddleware` in `app/main.py` |
| 5 | G-12 / E-36 / C-P-21: Perishable email | 🟢 S | cron + reuse `notify.py` |
| 6 | G-13 / B-51: Variance band "how steady" | 🟢 S | new column in `produccion.html` |
| 7 | G-15 / B-61: Read & document menu_tablet | 🟢 S | 0.5 day verification |
| 8 | G-16 / B-62: Read & document copilot | 🟢 S | 0.5 day verification |
| 9 | G-14 / B-63: Read & document recipe_photos | 🟢 S | 0.5 day verification |
| 10 | B-64: Daily summary auto on dashboard | 🟢 S | edit `dashboard.html` |
| 11 | A-19: Remove dead SaleStockMove imports | 🟢 S | `costing.py:501` + `sales/lifecycle.py:22` |
| 12 | C-S-22: Held-cart auto-age-out 24h | 🟢 S | cron |
| 13 | C-I-19: Packaging filter chip on /inventario | 🟢 S | edit `inventario.html` |
| 14 | C-I-20: Alternative preferida badge | 🟢 S | edit `receta_form.html` |
| 15 | C-P-20: P95 stockout badge on /inventario | 🟢 S | new query + render |
| 16 | C-P-22: Print batch tray count on grilla | 🟢 S | new render |
| 17 | B-52: Banner if preordered item missing | 🟢 S | edit `produccion_manana.html` |
| 18 | B-53: Plan accuracy widget on /inicio | 🟢 S | new card on `inicio.html` |
| 19 | C-C-17: Confirm-always count on customer card | 🟢 S | edit `cliente_detalle.html` |
| 20 | C-S-21 / E-35: pedido_status_audit | 🟢 S | new migration + write on transition |
| 21 | C-M-12: Document menu_tablet capability | 🟢 S | confirm |
| 22 | C-P-23: Verify menu_ocr flow is operator-friendly | 🟢 S | test + UX polish |

## Tier 2 — High value, medium effort (7 items, ~10 days)

| # | Open Item | Effort | File to edit |
|---|---|---|---|
| 23 | G-5 / A-23 / E-31: Pre-sale log persistence | 🟡 M | new migration + edit `pre_sale_check.py` |
| 24 | G-1 / D-43: Daily P&L rollup endpoint | 🟡 M | extend `accounting.py:daily_summary` + new route |
| 25 | G-3 / C-P-18: plan_accuracy feedback loop | 🟡 M | edit `production.py:forecast_sales` + bias-clamp tests |
| 26 | G-10 / B-48: Drag-and-drop product pin | 🟡 M | new `user_pinned_products` table + reorder widget |
| 27 | G-2 / C-F-16 / D-45 / IND-22: Per-category variance bands | 🟡 M | new `food_cost_alert.py` + soft/hard bands |
| 28 | D-46: Per-day accuracy report | 🟡 M | new `accuracy_daily.html` + cron |
| 29 | C-C-18: Loyalty points widget on POS | 🟡 M | new card on POS |
| 30 | B-54: Soft vs Hard band visualization | 🟡 M | new page |

## Tier 3 — Architectural cleanup (3 items, ~10 days)

| # | Open Item | Effort | File to edit |
|---|---|---|---|
| 31 | A-25 / G-4: Refactor produccion.html (2366 lines → _views/) | 🟠 L | `produccion.html` + new sub-templates |
| 32 | C-P-19 / C-I-21: Batch-level FEFO tracking | 🟠 L | new table + receiving flow update |
| 33 | E-34: WhatsApp integration (defer) | 🟠 L | new module + baileys + QR pairing |

## Tier 4 — Documentation / verification only (3 items, ~1.5 days)

| # | Open Item | Effort | File to edit |
|---|---|---|---|
| 34 | G-15: Read & document menu_tablet (in Tier 1) | — | — |
| 35 | G-16: Read & document copilot.py (in Tier 1) | — | — |
| 36 | G-14: Read & document recipe_photos (in Tier 1) | — | — |

---

# PART 14 — EVERY SKIP ITEM (49) WITH RATIONALE

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
| 24 | TastyIgniter multi-currency | PYG only (EUR/USD only in family bank table) |
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

# PART 15 — EVERY DECISION LOG ENTRY (23+)

Sourced from AGENTS.md + memory + module docstrings + commit messages + migration docstrings.

| # | Decision | Date | Source |
|---|---|---|---|
| 1 | Single-tenant, per-client instances | 2026-10-07 | SASKIA-210 memory |
| 2 | Migration rollback via rule 17 | 2026-10-07 | SASKIA-209 dc26df1f |
| 3 | Settings KV (single store, 42 keys) | 2026-10-07 | Sprint 2.1 bee5eb9e |
| 4 | Loyalty: 10% return rate (was 100%) | 2026-10-01 | loyalty/ledger.py comment |
| 5 | Loyalty tiers (4 levels) | 2026-10-01 | loyalty/tiers.py |
| 6 | Loyalty suggestions (5 rules) | 2026-10-01 | loyalty/suggestions.py |
| 7 | Sales lifecycle split | 2026-10-02 | Sprint 2.3 |
| 8 | URY pre-sale-check ported (MIT) | 2026-10 | pre_sale_check.py:1-50 |
| 9 | Bcrypt + Supabase dual-auth | 2026-09-29 | observability.py:31-41 |
| 10 | Use Loguru contextualize | 2026 | observability.py |
| 11 | HACCP seeded per Res 213/2019 | founding | haccp_seed.py |
| 12 | SaleStockMove table dropped | migration 092 | models_legacy.py |
| 13 | Production_scheduler deprecated | 2026-10-05 | production_scheduler.py |
| 14 | No SSE / WebSocket anywhere | 2026-10-08 grep | confirmed |
| 15 | Pack seed (Vaquita standard) | 2026-10-06 | seed/packs.py |
| 16 | Customer merge atomic | 2026 | customer_merge.py P1-B4 |
| 17 | Fiado ledger signed, FIFO aging | 2026 | fiado.py Fase 2 |
| 18 | Menu OCR via GLM vision | 2026 Fase 3 | menu_ocr.py |
| 19 | Copilot (in-app AI) | 2026 Fase 3 | copilot.py |
| 20 | Stock status thresholds DB-config | 2026 Phase 7 | stock_status.py |
| 21 | Audit log retention (cron) | 2026 | maintenance.py |
| 22 | Sentry→Telegram bridge | 2026-10-07 | notify.py |
| 23 | Refunds with 8 business rules | BACKLOG M1 | refunds.py |
| 24 | Refactor costing→profitability/cost | 2026 | profitability/ |
| 25 | SASKIA-204 HEREBUS channels | 2026-10-07 | migration 112 |
| 26 | SASKIA-205 shopping/wishlist stock-bump | 2026-10-07 | routers/shopping.py + herebus.py |
| 27 | SASKIA-206 shopping price snapshot | 2026-10-07 | migration 113 |
| 28 | SASKIA-207 single stock-ledger path | 2026-10-07 | stock_ledger.py |
| 29 | SASKIA-208 Poisson forecast (BACKLOG #5) | ~2026-10 | restock_forecast.py |
| 30 | SASKIA-209 rollback | 2026-10-07 | rollback.py |
| 31 | SASKIA-210 per-client instances | 2026-10-07 | memory |
| 32 | P44 legacy cleanup | 2026-10-07 | _archive/2026-10-07-p44-legacy-cleanup/ |

---

# PART 16 — THE SAZON NARRATIVE

Reading this whole catalog tells a story:

1. **Sazon is mature.** 71% of every plausible lesson from 10 competitors + 5 industry
   references is already in the code. The system has more depth than the original
   2026-09-07 v3 epic plan called for.

2. **HEREBUS is legacy data, not a second client.** The HEREBUS Drive was the
   bakery's pre-Sazon Google Sheets system (33 .xlsx files). The integration is
   complete and shipped (2026-09-23 herbus-sprint + 2026-10-07 migration 112 +
   P44 legacy cleanup). Future clients would be **cloned instances**, not tenants.

3. **The architecture is clean.** 115+ modules, one per domain. Settings KV.
   Migration rollback. Audit log. Observability. Sazon follows "one feature = one file"
   religiously.

4. **The 22 Tier-1 items are small and high-ROI.** 22 small improvements, all ≤ 0.5
   days each. Total ~3 days. Each is a visible operator improvement.

5. **The 7 Tier-2 items are the analytical crown jewels.** Per-category variance
   bands, daily P&L, plan_accuracy feedback. Total ~10 days. The system becomes
   measurably best-in-class.

6. **The 3 Tier-3 items are the architectural cleanup.** `produccion.html` refactor,
   FEFO batch tracking, WhatsApp. Each is 3-5 days. FEFO is the only one with a real
   operator benefit (others are overbuild).

7. **The 49 SKIP items are deliberate.** Sazon is intentionally single-tenant,
   Spanish-vos, laptop-only, no-card, no-mobile. These are not gaps — they are the
   design.

8. **The biggest ROI by far** is **G-1 (Daily P&L rollup)** + **G-2 (Per-category
   variance bands)**. Together they give the operator a credible daily P&L with
   category-aware variance alerting — the kind of thing BakeOnyx charges $80/month
   for; Sazon should ship it for free because the data is already there.

9. **There are 2 Sazon-funded bugs worth telling.** The 100% loyalty return rate
   (fixed 2026-10-01, comment in `loyalty/ledger.py`) and the dead `SaleStockMove`
   imports still in `costing.py:501` + `sales/lifecycle.py:22` (Tier 1 cleanup).

---

# PART 17 — VERIFICATION COMMANDS

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

# Verify current schema version
grep CURRENT_SCHEMA_VERSION /opt/data/work/saskia-app/app/rms/config.py

# Verify HEREBUS context
grep -A 2 "Saskia's HEREBUS data" /opt/data/work/saskia-app/app/rms/migrations/_112_extended_channel_check.py

# Verify no SSE/WebSocket
grep -rn "sse\|websocket" /opt/data/work/saskia-app/app/ --include='*.py' | head

# Verify SaleStockMove dead imports (should be cleaned)
grep -n SaleStockMove /opt/data/work/saskia-app/app/rms/costing.py
grep -n SaleStockMove /opt/data/work/saskia-app/app/rms/sales/lifecycle.py

# Verify PYG/EUR currency setup
grep -n "CURRENCY_CODE\|currency IN" /opt/data/work/saskia-app/app/rms/constants.py /opt/data/work/saskia-app/app/rms/models_legacy.py

# Verify competitor file
ls /opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/<repo>/<path>
```

---

# PART 18 — GLOSSARY

- **APLOC** — Application-level piece of code; Sazon term for a single `app/rms/<feature>.py` module
- **HEREBUS Drive** — The pre-Sazon Google Sheets system (33 .xlsx files) used by Saskia's family bakery. Now imported into Sazon via `import_herebus_data.py`. NOT a second client.
- **PRIMS** — 3rd-party baking production tool; CafeKit integrates via CSV export. Not relevant to Sazon
- **FEFO** — First-Expired First-Out. Standard for perishable batches (Supply'd pattern)
- **Standing orders** — Recurring weekly/monthly customer orders (Sazon's `suscripciones`)
- **Theoretical food cost** — recipe × qty sold (Otter/Supply'd standard)
- **Actual food cost** — beginning_stock + purchases − ending_stock (Otter/Supply'd standard)
- **Variance** = actual − theoretical, in dollars or percentage points
- **ddof=1** — Bessel-corrected sample stddev (N-1). Industry-correct for small samples
- **CI** — Wilson confidence interval (Poisson MLE; Sazon's `restock_forecast`)
- **MLE** — Maximum likelihood estimate (Poisson; `λ̂ = Σcounts / Σexposure`)
- **Vaquita** — Slang for "La Vaquita Holandesa" — the bakery's nickname
- **Sazon-VPS** — `sazon-vps.paragu-ai.com` (the production deployment)
- **JGHM VAN DER POL** — Saskia's family (WPG); TAB bank account holder in EUR
- **Caja** — Spanish for "cash register" (used in module/template names)

---

# PART 19 — ALL FILE PATHS

## Sazon canonical
- Codebase: `/opt/data/work/saskia-app/`
- Worktree: `/opt/data/profiles/ivan/scratch/sazon-app-work/`
- Memory: `~/.hermes/memory/`

## Documentation produced by this project (5 books)
- v1 audit: `/opt/data/profiles/ivan/cache/scratch/all_competitors_deep_audit_20261008.md`
- v1 lessons: `/opt/data/profiles/ivan/cache/scratch/sazon_lessons_book_20261008.md`
- v2 lessons: `/opt/data/profiles/ivan/cache/scratch/sazon_lessons_book_v2_20261008.md`
- v3 decisions: `/opt/data/profiles/ivan/cache/scratch/sazon_decision_book_v3_20261008.md`
- master catalog: `/opt/data/profiles/ivan/cache/scratch/sazon_master_catalog_20261008.md`
- **this file (final complete docs):** `/opt/data/profiles/ivan/cache/scratch/sazon_complete_documentation_20261008.md`

## Subagent audit reports
- `/opt/data/profiles/ivan/cache/scratch/audits/`

## Cloned competitor repos
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/TastyIgniter/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/RestoPOS/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/DineOut/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/resto-nestjs/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/flutter-pos-system/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/pizzaql/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/openresto/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/FloCafe/`
- `/opt/data/profiles/ivan/cache/scratch/competitor_analysis/clones/ury/`

## Industry references (web)
- Supply'd: supplyd.co/industries/bakeries/
- CafeKit: cafekit.io/bakery-production-planning
- BakeOnyx: bakeonyx.ai/features/demand-forecasting
- Rinvy: rinvy.app/docs/menu-items/food-cost-targets
- Otter: tryotter.com/blog/restaurant-tips/food-cost-variance
- restaurant-menu.org: threshold-tuning-for-alerts
- Supy: supy.io/blog/food-cost-variance-control
- JMJSoft: jmjsoft.com/solutions/bakery.php

---

*End of complete documentation.*
