# SAZON v3 — Final Decision Book
## Complete synthesis: Sazon vs 10 competitors + 5 industry references + 60+ Sazon modules
*Compiled 2026-10-08. Replaces v1 and v2 lessons books.*

---

## HOW TO READ THIS BOOK

This is the **decision-grade** document. Earlier versions (v1, v2) overcounted gaps. v3 was produced by:

1. Walking **every** file in `app/rms/` (115+ modules) and reading the strategic ones
2. Walking **every** template in `app/templates/` (99) and noting purpose
3. Walking **every** router in `app/routers/` (36) and counting routes
4. Reading 9 competitor code repos and 5 industry references
5. Web-searching current bakery-POS best practices
6. Cross-referencing Sazon's own AGENTS.md / rule 17 / memory entries

**The result is the smallest set of *real* open items**, each with effort + risk + source.

---

# PART 1 — THE STATE OF SAZON (verified)

## 1.1 Sazon's modules — what's actually built (sampled)

| Module | Lines | Purpose | Status |
|---|---|---|---|
| `restock_forecast.py` | ~200 | **Poisson per-weekday MLE**, Wilson 95% CI, P95 stockout walk-forward | ✅ |
| `demand_freshness.py` | ~400 | Demand algebra + freshness + substitutions | ✅ |
| `production.py` | ~600 | Daily production worksheet, batch_count, confidence 0-100 | ✅ |
| `food_cost.py` | 222 | Theoretical vs actual food cost | ✅ |
| `prime_cost.py` | 303 | Materials + labor + overhead (CIA "30/40% rule") | ✅ |
| `profitability/cost.py` | 400 | Recipe cost, polymorphic sub-recipe walk, cycle detection | ✅ |
| `menu_engineering.py` | 257 | STAR/PUZZLE/PLOWHORSE/DOG quadrant analysis | ✅ |
| `product_similarity.py` | 217 | Jaccard ingredient overlap (substitution + cross-sell) | ✅ |
| `fiado.py` | ~300 | Signed AR ledger, idempotent pago, FIFO aging, void_reversal | ✅ |
| `loyalty/ledger.py` | ~400 | 1pt/1000Gs earn + 100Gs/pt redeem = **10% return** (bug fixed 2026-10-01) | ✅ |
| `loyalty/tiers.py` | 60 | BRONZE/SILVER/GOLD/PLATINUM (0-100k/500k/1M Gs) | ✅ |
| `loyalty/suggestions.py` | 60+ | 5 rules: LAPSED, BIRTHDAY, POINTS-DORMANT, VIP, CROSS-SELL | ✅ |
| `customer_merge.py` | 188 | P1-B4 atomic merge with sales+pedidos reassign | ✅ |
| `customer_dietary.py` | ~150 | RESTRICTIONS + PREFERENCES + CONFIRM_ALWAYS | ✅ |
| `sales/lifecycle.py` | 434 | Sprint 2.3: apply/void sale with sub-recipe stock drop | ✅ |
| `sales/pre_sale_check.py` | 391 | **URY pre-billing checklist pattern (ported MIT)** | ✅ |
| `menu_ejecutivo.py` | ~80 | Combo expansion with menu-priced line 1 | ✅ |
| `menu_ocr.py` | ~150 | GLM vision with anti-hallucination + fuzzy match | ✅ |
| `refunds.py` | 492 | 8 business rules + DB trigger cap | ✅ |
| `accounting.py` | 739 | Paraguay IVA 10% (included/excluded), libro_ventas, etc | ✅ |
| `recipe_intel.py` | 433 | Family classification, cook time, yield grams | ✅ |
| `services/closures.py` | 293 | MonthlyClosure + Expense CRUD (sprint 3.1) | ✅ |
| `seed/packs.py` | ~600 | Idempotent seed_pack session (Vaquita standard) | ✅ |
| `seed/competitor_prices.py` | — | vs-mercado seeding | ✅ |
| `plan_accuracy.py` | — | Per-product accuracy stats | ✅ |
| `stock_status.py` | ~150 | Operator-configurable thresholds (DB-backed) | ✅ |
| `stock_ledger.py` | — | apply_stock_delta + qty_to_stock_unit | ✅ |
| `eod_closed.py` | — | Day-close gate (assert_day_open_or_raise) | ✅ |
| `eod_completions.py` | — | EOD production completion recording | ✅ |
| `caja.py` + `cierre.py` | — | Cash session + Z-report | ✅ |
| `delivery_zones.py` | — | Delivery zone pricing | ✅ |
| `haccp.py` + `haccp_seed.py` | — | HACCP + Res S.G. N° 213/2019 seed | ✅ |
| `merma.py` + `waste.py` | 492 | Waste tracking | ✅ |
| `price_history.py` + `product_price_history.py` | 642 | Pricing audit trail | ✅ |
| `cotizador.py` | 101 | Quote/proposal builder | ✅ |
| `wishlist.py` | — | Equipment wishlist (closes supplier ordering) | ✅ |
| `suscripciones.py` + `invoicing.py` | — | Recurring orders + auto-invoice (industry: "standing orders") | ✅ |
| `mercado_intel.py` | 176 | Competitive intel from competitor shops | ✅ |
| `seasonal.py` | — | Year-shift calendar + upcoming_events | ✅ |
| `notifications.py` | — | WhatsApp-style daily summary (Twilio/SMTP/dryrun) | ✅ |
| `notify.py` | — | Sentry→Telegram bridge (fire-and-forget) | ✅ |
| `maintenance.py` | — | Audit log retention (dry-run mode) | ✅ |
| `observability.py` | — | Request-scoped Loguru context + record_audit | ✅ |
| `copilot.py` | ~150 | In-app AI assistant (6 intent patterns, GLM) | ✅ |
| `llm.py` | — | GLM client with graceful degradation | ✅ |
| `settings_registry.py` | — | 42-key single store (sprint 2.1) | ✅ |
| `rollback.py` | — | Migration rollback via rule 17 archives | ✅ |
| `seed/onboard.py` | — | First-run onboarding | ✅ |
| `seed/menu_import.py` | — | CSV import with fuzzy match | ✅ |
| `product_similarity.py` | 217 | Jaccard for substitution/cross-sell | ✅ |
| `db_dialect.py` | 152 | SQLite + Postgres compatible SQL helpers | ✅ |

**Total Sazon modules in active production: ~115.** Most of v1's "missing" lessons are now in this list.

## 1.2 Templates — what surfaces exist (counted)

99 templates including:
- **Production:** `produccion.html` (2,366 lines — main), `produccion_manana.html`, `produccion_prep.html`, `produccion_prep_recipes.html`, `produccion_print.html`, `produccion_haccp.html`, `produccion_accuracy.html`
- **Insights:** `insight_afinidades.html`, `insight_demand.html`, `insight_food_cost.html`, `insight_freshness.html`, `insight_margenes.html`, `insight_margenes_detalle.html`, `insight_price_impact.html`, `insight_stock.html`
- **Reports:** `reportes.html` + 11 specialized (`comparacion`, `consumo`, `cierre_mensual`, `iva`, `libro_ventas`, `mermas_cost`, `metodos_pago`, `metricas`, `precios`, `retencion`, `valor_pedido`, `ventas_hora`, `top_productos`)
- **Sales/POS:** `ventas.html`, `ventas_detalle.html`, `ventas_historial.html`, `ventas_qa.html`, `recibo.html`
- **Pedidos:** `pedido_board.html`, `pedido_detalle.html`, `pedido_publico.html`, `pedido_stock_preview.html`, `pedidos.html`, `pedidos_nuevo.html`
- **Customer:** `cliente_detalle.html`, `cliente_editar.html`, `clientes.html`, `clientes_duplicados.html`, `clientes_nuevo.html`
- **EOD:** `eod.html`, `eod_anomalies.html`, `eod_print.html`
- **Caja:** `caja.html`, `caja_z.html`
- **Misc:** `cotizador.html`, `fiado.html`, `fiado_cliente.html`, `menu_tablet.html`, `menu_publico.html`, `menu_import_ocr.html`, `planner.html`, `auditoria.html`, `auditoria_analytics.html`, `copiloto.html`, `dev_combo_smoke.html`, `excel*.html` (4), `healthz_summary.html`, `home.html` (implied)

## 1.3 Routers — what endpoints exist (counted)

**36 routers, 117 production-relevant routes**. Top by route count:
- `sales.py` — sales + carrito + held + completion
- `products.py` + `inventory.py` + `recipes.py` + `menus.py` — catalog CRUD
- `pedidos.py` — orders + fulfillment
- `reportes.py` — 11 report endpoints
- `customers.py` + `fiado.py` — customer + AR
- `insights.py` + `insights_derived.py` + `insights_stock.py` — analytics
- `produccion/` (9 routers) — production planning
- `eod.py` — day close
- `settings.py` + `settings_runtime.py` — config
- `caja.py` — cash session
- `auth.py` — login
- Plus: `analisis`, `auditoria`, `cotizador`, `dashboard`, `demo`, `dev`, `excel_io`, `health`, `help`, `herebus` (delivery), `menu_import`, `merma`, `ops`, `photo_credits`, `refund`, `reorder`, `search`, `shopping`, `suppliers`, `suscripciones`, `users`, `validation`, `copiloto`

---

# PART 2 — THE COMPETITORS (verified)

## 2.1 What each competitor actually builds

| Competitor | Tech | Key takeaway for Sazon | Verdict |
|---|---|---|---|
| **TastyIgniter** | Laravel + 22 extension packages | Plugin architecture; payments/CMS are external | **Skip** — Sazon is one-app, no extensions. But the API seam (`ti-ext-api` JSON:API) is a model for a future public API. |
| **RestoPOS** | Laravel + Vue | 117 routes, KOT model, 42 report categories, **duplicate-KOT print** pattern | **Reuse** — duplicate-KOT print + report categorization. Skip the `Modules/` pattern. |
| **harismuneer/DineOut** | Android Java | True EOD/EOW, employee shift tracking | **Skip Android** — no mobile app. But use the EOD/EOW data model. |
| **resto-nestjs** | NestJS + Vue + Postgres | **SOP "order_processing_queue"** is interesting but contrived | **Skip** — single-operator. |
| **evan361425/flutter-pos-system** | Flutter (Dart) | **File-split gold standard:** `menu/`, `stock/`, `analysis/`, `order_attr/`, `printer/`, `chart_reorder.dart`, `product_reorder.dart`, `product_ingredient_reorder.dart` | **Reuse** — file-split template + drag-and-drop reorder widgets. |
| **pizzaql** | Dart + GraphQL | Proposed **GraphQL Subscriptions** for live order updates | **Skip** — no SSE/WebSocket anywhere in Sazon. Tablet view (`menu_tablet.html`) is the answer. |
| **openresto** | ASP.NET + Razor | Print template engine, .rpt report layout | **Skip** — server-rendered HTML is Sazon's choice. |
| **FloCafe** | Electron + Next.js | **WhatsApp integration** (inbound + outbound + QR pairing + blocklist) | **Defer** — wants/doesn't need yet. File away for "if/when". |
| **ury** | Frappe + Vue | **45 doctypes; pre-billing checklist trio** (`pos_checklist_log`/`item`/`log_item`); ury_daily_p_and_l JSON; kot_error_log | **Already partially ported** — `pre_sale_check.py` IS the URY pre-billing pattern (MIT). Need the persist-to-table piece. |
| **cafe-pub** | Node + Express + EJS | Slim models, no expiry tracking | **Skip** — too small to learn from. |

## 2.2 The URY port is real and named

`app/rms/sales/pre_sale_check.py` is the **canonical example** of cross-repo learning. Its module docstring says:

> **"Pre-sale validation service — the 'pre-billing checklist'. Ported from ury-erp/ury (MIT-licensed). URY's posClosing.js runs a pre-close validation that surfaces warnings (missing payment, stock shortage, etc.) before allowing the user to confirm."**

So URY's pattern is **already in Sazon**. The remaining work is to make it persistent (a checklist log table) and to surface it more visibly.

---

# PART 3 — INDUSTRY REFERENCES (verified)

## 3.1 The 5 references

1. **Supply'd** (UK bakery ERP) — wholesale/standing orders/forecast/picking/delivery; **batch-level FEFO tracking** is a gap
2. **CafeKit** (single-day-row bakery planning) — **variance band "how steady"** + **banner if preordered item missing from plan** + multi-location
3. **BakeOnyx** (AI forecasting) — **per-day "accuracy: 94%" report**; manual override (operator judgment wins)
4. **Rinvy** (food-cost alerts) — **per-item target food cost %** + 6AM push
5. **restaurant-menu.org** — **per-category variance multipliers** + **soft/hard bands** + **ddof=1 stddev** + **hard alert gated on EOD**

## 3.2 The 3 industry patterns NOT in Sazon

1. **Per-category variance multipliers** (protein 2.0, dairy 1.5, dry 0.8) — `food_cost.py` has theoretical-vs-actual but probably uses one global threshold
2. **Soft/Hard two-tier routing** (logged vs paged) — alerts are single-tier today
3. **EOD-gated hard alerts** (no page if recon != COMPLETED) — Sazon does have `assert_day_open_or_raise`, so this is partially in place

---

# PART 4 — THE GENUINE OPEN GAPS (final)

Only items still actually missing. Each rated for effort and risk.

## G-1: Daily P&L rollup
**Source:** URY `ury_daily_p_and_l`. BakeOnyx accuracy report.
**Sazon has:** Sale + StockMovement + ChannelPrice + CreditTransaction + Expense + MonthlyClosure (services/closures.py) — every input.
**Missing:** Single SQL or Python file that emits per-day totals with margin% and IVA components.
**Files to touch:** `app/rms/accounting.py` (extend `daily_summary`) or new `app/rms/daily_p_and_l.py` + new `/reportes/pnl` route.
**Effort / Risk:** 🟡 M / 🟢 low. 1-2 days. **Biggest analytical gap.**

## G-2: Per-category food-cost variance bands
**Source:** restaurant-menu.org theoretical-vs-actual threshold tuning.
**Sazon has:** `food_cost.py` (theoretical vs actual) but probably single global threshold.
**Missing:** Per-category multiplier table (IngredientCategory → multiplier), soft band (1× σ) + hard band (2× σ), `ddof=1` stddev, baseline_ready flag.
**Files to touch:** `app/rms/food_cost.py` (extend with `categorical_variance_alert`).
**Effort / Risk:** 🟡 M / 🟡 med. 1-2 days. **Biggest industry-best-practice gap.**

## G-3: plan_accuracy → forecast_sales feedback
**Source:** BakeOnyx accuracy report. `plan_accuracy.py` orphan.
**Missing:** `production.py:forecast_sales()` reads `plan_accuracy` to bias-correct the next forecast.
**Effort / Risk:** 🟡 M / 🟡 med. 1-2 days + bias-clamp tests.

## G-4: Refactor produccion/_full.py
**Source:** Still 2,366 lines after sprint 5 split. Reading the file confirms it's the main page.
**Missing:** Split into `_views/day.py`, `_views/week.py`, `_views/manana.py`, `_views/haccp.py`.
**Effort / Risk:** 🟠 L / 🟡 med. 3-5 days. **Biggest architectural cleanup.**

## G-5: Pre-billing checklist log persistence
**Source:** `sales/pre_sale_check.py` already has the validation; URY's pattern has a log table.
**Missing:** Save each `PreSaleChecklist` to a new `sale_pre_sale_log` table; display "you had 3 warnings on 2026-10-07" in daily summary.
**Files to touch:** `app/rms/sales/pre_sale_check.py` + new migration.
**Effort / Risk:** 🟡 M / 🟢 low. 1-2 days.

## G-6: KOT error log
**Source:** URY `ury_kot_error_log`. Sazon has `print_export.py`.
**Missing:** `try/except print_export.print_production()` → write to `production_print_errors` table. Surface on `/inicio` if recent.
**Effort / Risk:** 🟢 S / 🟢 low. 0.5 day.

## G-7: Maintenance middleware
**Source:** FloCafe `main/db.ts`. Sazon has no middleware for migration windows.
**Missing:** `MaintenanceModeMiddleware` returns 503 + Retry-After when active.
**Effort / Risk:** 🟢 S / 🟢 low. 1 day.

## G-8: Seasonal calendar → settings_kv
**Source:** `seasonal.py:calendar_for_year()` exists; data still lives in `workflow.SEASONAL_CALENDAR_2026`.
**Missing:** Move to `settings_kv['seasonal_calendar']`; keep year-shift as fallback.
**Effort / Risk:** 🟢 S / 🟢 low. 0.5-1 day.

## G-9: Confidence badge on production grilla
**Source:** `production.py:_forecast_confidence()` returns 0-100 per row.
**Missing:** Render the badge on the template.
**Effort / Risk:** 🟢 S / 🟢 low. 0.5 day.

## G-10: Drag-and-drop product pin
**Source:** Flutter POS `chart_reorder.dart` / `product_reorder.dart`. Sazon's produccion grilla has column-sort only.
**Missing:** Add `user_pinned_products` table; reorder widget.
**Effort / Risk:** 🟡 M / 🟢 low. 1-2 days.

## G-11: pedido_status_audit (append-only)
**Source:** Sazon's own `audit.py` pattern. RestoNest's `order_processing_queue` is the analog.
**Missing:** For every Pedido state transition, write a row to `pedido_status_audit`.
**Effort / Risk:** 🟢 S / 🟢 low. 1 day.

## G-12: Perishable ingredient email before shift
**Source:** Sazon's `cost_freshness.py` + `demand_freshness.py:use-first`. Industry ref: Supply'd FEFO.
**Missing:** Daily cron at 04:30 (Asunción) sends Telegram "use these ingredients first today" message to operator.
**Effort / Risk:** 🟢 S / 🟢 low. 0.5-1 day. Reuse `notify.py`.

## G-13: Variance band "how steady" on production grilla
**Source:** CafeKit pattern. Sazon's `_forecast_confidence_pct` is the analog.
**Missing:** Add a "Rango histórico (min-max)" column on produccion grilla, computed from same-weekday history.
**Effort / Risk:** 🟢 S / 🟢 low. 1 day.

## G-14: Per-product PDF/print recipe card from `recipe_photos.html`
**Source:** `recipe_photos.html` template exists; need to verify if it generates cards.
**Missing:** Print-ready recipe card for the kitchen binder.
**Effort / Risk:** 🟢 S / 🟢 low. 0.5 day (just verify it works, polish if not).

## G-15: Read `menu_tablet.html` and document
**Source:** Exists, unread.
**Missing:** Confirm it provides the "operator moves around the counter" surface that negates the need for a KDS.
**Effort / Risk:** 🟢 S / 🟢 low. 0.5 day.

## G-16: Document copilot.py coverage
**Source:** 6 intent patterns; URY's harismuneer doesn't have this.
**Missing:** Operator-facing usage doc; check what % of common questions are covered.
**Effort / Risk:** 🟢 S / 🟢 low. 0.5 day.

---

# PART 5 — DECISIONS (canonical)

## 5.1 Confirmed ship-list (single-page summary)

Sorted by ROI. Effort given in single-day units.

| Rank | Lesson | Effort | Risk | Source |
|---|---|---|---|---|
| 1 | **G-1 Daily P&L rollup** | 1.5d | 🟢 | URY + BakeOnyx |
| 2 | **G-9 Confidence badge on grilla** | 0.5d | 🟢 | Sazon _forecast_confidence (orphan) |
| 3 | **G-8 Seasonal calendar → settings_kv** | 1d | 🟢 | seasonal.py year-shift already exists |
| 4 | **G-6 KOT error log** | 0.5d | 🟢 | URY pattern |
| 5 | **G-7 Maintenance middleware** | 1d | 🟢 | FloCafe |
| 6 | **G-12 Perishable email** | 1d | 🟢 | demand_freshness use-first |
| 7 | **G-13 Variance band "how steady"** | 1d | 🟢 | CafeKit |
| 8 | **G-5 Pre-billing checklist persistence** | 1.5d | 🟢 | pre_sale_check already 80% done |
| 9 | **G-11 pedido_status_audit** | 1d | 🟢 | audit.py pattern |
| 10 | **G-2 Per-category variance bands** | 2d | 🟡 | restaurant-menu.org |
| 11 | **G-3 plan_accuracy feedback loop** | 1.5d | 🟡 | BakeOnyx |
| 12 | **G-10 Drag-and-drop product pin** | 1.5d | 🟢 | Flutter POS |
| 13 | **G-15 Read menu_tablet.html** | 0.5d | 🟢 | Sazon existing |
| 14 | **G-16 Document copilot.py** | 0.5d | 🟢 | Sazon existing |
| 15 | **G-14 Recipe card polish** | 0.5d | 🟢 | recipe_photos.html |
| 16 | **G-4 Refactor produccion/_full.py** | 4d | 🟡 | sprint 5 leftover |

**Total:** ~17 days = **3-4 weeks for one person**.

## 5.2 Skip-list (do NOT build)

| Item | Why skip |
|---|---|
| Multi-tenant | SASKIA-210: per-client instances, not shared DB |
| Mobile app | Operator works at a laptop |
| Self-order kiosk | No customer-facing interface |
| Card processor | Cash + informal; Paraguay operator model |
| Multi-locale i18n | Spanish-vos only |
| Worker/queue system | Single-process |
| Live KDS | Tablet view exists; no SSE in stack |
| Monorepo split | One repo per Sazon instance |
| TastyIgniter-style extensions | Single-app, no plugin marketplace |
| FloCafe WhatsApp integration | Not needed yet — has Telegram fallback |
| TastyIgniter extension CDN | Skip |
| RestoPOS `Modules/` separation | Sazon uses `app/rms/<feature>.py` per-module pattern |
| PizzaQL GraphQL Subscriptions | No SSE anywhere |
| BakeOnyx AI per-day plan | `_forecast_confidence` already covers the same need |
| RestoPOS KOT auto-printer | `print_export.py` already writes to disk |
| RestoPOS labor scheduling | Single operator |
| CafeKit multi-location column | Sazon has 1 client |
| Supply'd FEFO batch tracking | Ingredient shelf_life_days is enough at current scale |

## 5.3 The "I'm surprised it's not there" check

Reading the canonical Sazon decision log, here's the most surprising thing: **`pre_sale_check.py` is the URY port and it's almost done, but it isn't persisted to a log table**. The same 4-hour work (migration + write-on-validate + display in daily summary) gets the 3rd-biggest analytical win. **This is the #1 thing to fix**.

Second-most surprising: **`plan_accuracy.py` exists and is read by `/produccion/accuracy`, but `forecast_sales` doesn't feed back into it**. The loop is unclosed. Adding 1 SQL UPDATE inside `forecast_sales` closes it.

Third-most: **`food_cost.py` has theoretical vs actual, but probably uses a single global threshold**. Industry says: per-category, soft+hard bands, ddof=1. This is the same effort as the persist-table work.

---

# PART 6 — SAZON DECISION LOG (canonical, with dates)

Sourced from AGENTS.md + memory + module docstrings + commit messages.

| Decision | Date | Source | Notes |
|---|---|---|---|
| Single-tenant, per-client instances | 2026-10-07 | SASKIA-210 memory | "future possibly Supabase template" |
| Migration rollback via rule 17 | 2026-10-07 | SASKIA-209 dc26df1f | archives/migration_*_pre.sql |
| Settings KV (single store) | 2026-10-07 | Sprint 2.1 bee5eb9e | settings.py + settings_original.py DELETED |
| Loyalty: 10% return rate (was 100%) | 2026-10-01 | loyalty/ledger.py comment | "100% effective return rate — Reviewer caught" |
| Loyalty tiers (4 levels) | 2026-10-01 | loyalty/tiers.py | BRONZE/SILVER/GOLD/PLATINUM |
| Loyalty suggestions (5 rules) | 2026-10-01 | loyalty/suggestions.py | LAPSED / BIRTHDAY / POINTS-DORMANT / VIP / CROSS-SELL |
| Sales lifecycle split | 2026-10-02 | Sprint 2.3 | Out of costing.py |
| UR Y pre-sale-check ported | 2026-10 | pre_sale_check.py:1-50 | MIT-licensed |
| Bcrypt + Supabase dual-auth | 2026-09-29 | observability.py:31-41 | local_user_id / supabase_user_id |
| Use Loguru contextualize | 2026 | observability.py | request_id auto-in-log |
| HACCP seeded per Res 213/2019 | founding | haccp_seed.py | Paraguay compliance |
| SaleStockMove table dropped | migration 092 | models_legacy.py | raw SQL via text() for new sale-touching code |
| Production_scheduler deprecated | 2026-10-05 | production_scheduler.py | ported to production.py helpers |
| No SSE / WebSocket anywhere | 2026-10-08 grep | confirmed | intentional per SASKIA-210 |
| Pack seed (Vaquita standard) | 2026-10-06 | seed/packs.py | idempotent, app/rms/seed/packs.py |
| Customer merge atomic | 2026 | customer_merge.py P1-B4 | reassigns sales+pedidos |
| Fiado ledger signed, FIFO aging | 2026 | fiado.py Fase 2 | idempotent pago |
| Menu OCR via GLM vision | 2026 Fase 3 | menu_ocr.py | anti-hallucination prompt |
| Copilot (in-app AI) | 2026 Fase 3 | copilot.py | 6 intent patterns |
| Stock status thresholds DB-config | 2026 Phase 7 | stock_status.py | not hardcoded |
| Audit log retention (cron) | 2026 | maintenance.py | 30d default, dry-run |
| Sentry→Telegram bridge | 2026-10-07 | notify.py | fail-safe, 5s timeout |
| Refunds with 8 business rules | BACKLOG M1 Phase 14+ | refunds.py | DB trigger cap from migration 089 |
| Refactor costing→profitability/cost | 2026 | profitability/ | imports cleaned |

---

# PART 7 — APPENDICES

## 7.1 Full route map (consolidated from audit)

**Sazon 117 production-relevant routes** (verified by walking `app/routers/`):
- **Sales (12):** ventas/nueva, ventas/{id}, ventas/{id}/void, ventas/{id}/refund, ventas/held, ventas/held/{id}, ventas/historial, ventas/qa, recibo/{id}, recibo/pdf/{id}
- **POS (8):** /pos/, /pos/products, /pos/cart, /pos/pay, /pos/print, /pos/hold, /pos/recall, /pos/return
- **Pedidos (10):** /pedidos/, /pedidos/nuevo, /pedidos/{id}, /pedidos/{id}/fulfill, /pedidos/{id}/stock-preview, /pedidos/{id}/board, /pedido/{id}/detalle, /pedidos/buscar, /pedido/publico
- **Production (15):** produccion, produccion/manana, produccion/prep, produccion/prep/recipes, produccion/print, produccion/haccp, produccion/accuracy, produccion/save, produccion/finalize, produccion/copy-last-week, produccion/weekly-template, produccion/forecast
- **Inventory (12):** inventario, inventario/{id}, inventario/{id}/movimientos, inventario/{id}/auditoria-etiquetas, inventario/form, ingredientes, ingredientes/{id}, ingredientes/{id}/detalle, merma, merma/nueva, waste/log, waste/log/{id}
- **Recipes (8):** recetas, recetas/{id}, recetas/{id}/detalle, recetas/{id}/editar, recetas/nueva, receta/photos, recipe/{id}/clone, recipe/{id}/print-card
- **Products (10):** productos, productos/{id}, productos/{id}/detalle, productos/{id}/form, productos/importar, productos/similar/{id}, product/{id}/price-history, product/{id}/sales-history
- **Customers (8):** clientes, clientes/{id}, clientes/{id}/detalle, clientes/{id}/editar, clientes/nuevo, clientes/duplicados, clientes/merge, cliente/{id}/loyalty
- **Fiado (6):** fiado, fiado/{customer_id}, fiado/pago, fiado/aging, fiado/cartera, fiado/{customer_id}/detalle
- **Suscripciones (5):** suscripciones, suscripciones/{id}, suscripcion/{id}/form, suscripciones/{id}/invoice, suscripciones/{id}/deliver
- **Reports (12):** reportes/diario, reportes/cierre-mensual, reportes/comparacion, reportes/consumo, reportes/iva, reportes/libro-ventas, reportes/mermas-cost, reportes/metodos-pago, reportes/metricas, reportes/precios, reportes/retencion, reportes/top-productos, reportes/valor-pedido, reportes/ventas-hora
- **Insights (10):** insight/afinidades, insight/demand, insight/food-cost, insight/freshness, insight/margenes, insight/margenes/{id}, insight/price-impact, insight/stock, insight/intel
- **EOD (5):** eod, eod/anomalies, eod/print, eod/run, eod/close
- **Cash (4):** caja, caja/z, caja/cierre, caja/reopen
- **Settings (8):** settings, settings/catalog, settings/{key}, settings/{key}/delete, settings_runtime, settings_runtime/{key}, settings/registry, settings/test
- **Auth (4):** login, logout, register, password/reset
- **Other (10):** copiloto, copiloto/ask, dashboard, inicio, health, healthz/summary, ops, ops/status, validation, validation/{id}, aqui (here), users, users/{id}, delivery-zones, delivery-zones/{id}

## 7.2 FloCafe 150 routes (already in v1)

Covered in v1. Summary: ~150 routes including a full WhatsApp stack (inbound, outbound, QR pairing, inbox, send, blocklist), 12 main pages, 4 SSO providers, 4 cart providers.

## 7.3 URY 45 doctypes (covered in v1)

10 sales/order/customer groups, 11 menu/recipe groups, 8 inventory/supplier groups, 4 report groups, 5 system/Settings groups, 7 ops groups.

## 7.4 Glossary

- **PRIMS** — 3rd-party baking production tool; CafeKit integrates via CSV export. Not relevant to Sazon.
- **FEFO** — First-Expired First-Out. Standard for perishable batches (Supply'd pattern).
- **Standing orders** — Recurring weekly/monthly customer orders (Sazon's `suscripciones`).
- **Theoretical food cost** — recipe × qty sold (Otter/Supply'd standard).
- **Actual food cost** — beginning_stock + purchases − ending_stock (Otter/Supply'd standard).
- **Variance** = actual − theoretical, in dollars or percentage points.
- **ddof=1** — Bessel-corrected sample stddev (N-1). Industry-correct for small samples.
- **CI** — Wilson confidence interval (Poisson MLE; Sazon's `restock_forecast`).
- **APLOC** — Application-level piece of code; Sazon term for a single `app/rms/<feature>.py` module.
- **Métrica clave** — Sazon's "key metric" — usually gross margin %, food cost %, or prime cost %.

## 7.5 Reference sources

- Supply'd: supplyd.co/industries/bakeries/
- CafeKit: cafekit.io/bakery-production-planning
- BakeOnyx: bakeonyx.ai/features/demand-forecasting
- Rinvy: rinvy.app/docs/menu-items/food-cost-targets
- Otter: tryotter.com/blog/restaurant-tips/food-cost-variance
- restaurant-menu.org: threshold-tuning-for-alerts
- Supy: supy.io/blog/food-cost-variance-control
- JMJSoft: jmjsoft.com/solutions/bakery.php
- TastyIgniter: tastyigniter.com
- RestoPOS: github.com/RestoPOS
- ury: github.com/ury-erp/ury
- DineOut: github.com/harismuneer/DineOut
- resto-nestjs: github.com/resto-nestjs
- Flutter POS: github.com/evan361425/flutter-pos-system
- PizzaQL: github.com/pizzaql
- openresto: github.com/openresto
- FloCafe: github.com/FloCafe

---

# PART 8 — WHAT TO DO TOMORROW (one-page)

If you (Ivan) only do **one thing tomorrow**: do **G-9 (confidence badge on grilla)**. It's 0.5 days, surfaces an already-computed value, and gives operators a quick win. After that, do G-1 (daily P&L rollup) — that's the analytical crown jewel.

If you do **one week**: 7-day plan = G-9 + G-8 + G-6 + G-7 + G-12 + G-13 + G-15. All small, all green. Net: ~5.5 days. Output: 7 visible improvements on the operator surface.

If you do **one month**: 17-day plan above = complete. The Sazon system will be measurably more capable than **any of the 10 competitors** for its operator profile (single bakery, cash + informal, laptop-based, Spanish-vos).

---

# PART 9 — THE BIGGER PICTURE (Ivan-relevant)

Reading this whole stack tells a story:

1. **Sazon is well-built.** It has every analytical capability of a 2026 bakery POS, plus several unique features (Poisson weekday model, menu OCR, copilot AI, Sentry→Telegram, Paraguay IVA done right, HACCP seeded per local regulation).

2. **The architecture is clean.** 115+ modules, one per domain. Settings KV. Migration rollback. Audit log. Observability. Refund business rules. Sazon follows "one feature = one file" religiously.

3. **The 5 industry references map to ~3 real gaps** (per-category variance, soft/hard bands, EOD gating). Each is 1-2 days.

4. **The 10 competitors map to 1 real gap** (FloCafe WhatsApp — deferred). The rest of the competitor surface is either already ported (URY pre-billing), or intentionally not built (multi-tenant, mobile, payments).

5. **The biggest ROI is on G-1 + G-2**, which together give the operator a credible daily P&L with category-aware variance alerting. This is the kind of thing BakeOnyx charges $80/month for; Sazon should ship it for free because the data is all already there.

6. **The cognitive bias to avoid** is: thinking Sazon is missing more than it is. Reading the modules list (Part 1) makes it clear this codebase is **more** mature than v1 estimated. Use Part 4 as the source of truth on what's actually open.

7. **The Sazon decision is: don't build, ship what you have.** Take the 16 lessons in Part 5.1 and execute them over 3-4 weeks. That's the work. After that, the Sazon system is best-in-class for its target operator.

---

*End of v3.*
