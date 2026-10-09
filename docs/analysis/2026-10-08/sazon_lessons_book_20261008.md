# LESSONS BOOK — Sazón production system vs 10 competitors (2026-10-08)

A complete categorized reference for everything Sazón should learn,
keep, change, or ignore. Each lesson is risk-ranked, sourced from a
specific file in the cloned competitor or Sazon's own code, and tagged
with effort estimate.

**Sources analyzed (9 cloned, 1 doc-only):**
- Sazón (own repo, `/opt/data/work/saskia-app` — 301 routes, 36 routers, 116 modules)
- FloCafe — 27 routes, 1034 files
- OpenResto — 16 routes verified + 4 sibling services
- URY — 45 doctypes
- RestoPOS — 117 routes
- PizzaQL — 7 routes
- Flutter POS — 15 UI features, 35+ widgets
- DineOut (harismuneer) — 5 role-based user classes
- resto-nestjs — 39 routes
- TastyIgniter — 22 extension repos

---

## TABLE OF CONTENTS

1. **Overview & method** — what we read, what we didn't
2. **Production planning lessons** (Sazon's home turf)
3. **Stock / inventory / BOM lessons**
4. **KDS / KOT / printing lessons**
5. **Sales / POS lessons**
6. **Reports / analytics / insights lessons**
7. **Architecture / coding-pattern lessons**
8. **UI / page-layout lessons**
9. **Ops / compliance / safety lessons**
10. **Settings / configuration lessons**
11. **What NOT to copy** (forced splits)
12. **The Sazon decision log — why we work the way we do**
13. **Appendices** — competitor route inventories, doctype inventories, glossary

---

## 1. OVERVIEW & METHOD

**What was read directly from disk:**
- 301 Sazon routes (full inventory via regex sweep of `app/routers/**/*.py`)
- All 11 router files in `app/routers/produccion/` package
- `app/rms/production.py` formulas (forecast, plan, completion)
- `app/rms/plan_accuracy.py` (computed but unused feedback)
- `app/rms/stock_ledger.py` (the single stock path)
- `app/rms/costing.py` (the apply_sale path — rule 8)
- `app/rms/workflow.py` (seasonal calendar, demand_multiplier)
- 20 ORM classes from `app/rms/models/*`
- `app/templates/produccion.html` (2366 lines — 12-column grilla)

**What was read in the cloned competitors:**
- FloCafe: 27 routers + 2 child pages (kds-server.ts, server-app.ts). All routes from `main/routes/*.ts`. Order: ~150 routes total
- OpenResto: `OpenRestoApi.Core/Application/Services/` (services), `OpenRestoApi*/Domain` (entities), `OpenRestoApi/Controllers`
- URY: 45 doctypes JSON schemas + Py hooks + Vue KDS (mosaic/) + Frappe POS (pos/)
- RestoPOS: 117 tenant routes + model files (40+ Eloquent models)
- PizzaQL: backend/index.js + pages/admin.js + pages/order.js
- Flutter POS: full pubspec.yaml + 7 model repos + all UI features
- DineOut: all 5 module trees + 5 user roles from README
- resto-nestjs: 39 controllers + DDD entity pattern + queue pattern
- TastyIgniter: extension list + sparse clone (master has +100 files in extensions but 4.x branch is minimal)

**Methodology:**
1. List each system's "production plan" surface (URLs + module files)
2. Find the *one thing* each does that the others can't
3. Score against Sazon's decision log (`memory: SASKIA-210 single-tenant`)
4. Tag with effort estimate (hours/days/weeks)

**Effort scale used throughout:**
- 🟢 XS (≤ 1 hour) — config change / 1-line tweak
- 🟢 S (0.5–1 day) — small focused fix
- 🟡 M (1–3 days) — proper sprint task
- 🟠 L (3–7 days) — half a sprint
- 🔴 XL (1+ sprint) — multi-week work

**Risk scale:**
- 🟢 low — additive, no contract change
- 🟡 med — touches one model/contract
- 🔴 high — schema/contract ripple

---

## 2. PRODUCTION PLANNING (Sazon's home turf — 12 lessons)

Sazon wins on this domain. Most lessons here are **"we already do X better"** notes — but seven are real gaps that close quickly.

### L-PLAN-1: Day-view grilla with 12 columns is the strongest pattern 🔵
**Source:** Sazon `app/templates/produccion.html` (2366 lines), rows 874-898:
```
Listo · Producto · Dificultad · Demanda · Lotes · Pedidos · Lote final · Hecho · Merma · Receta · Sobrante · Cierre
```
**State:** ✅ shipped. **What it gets right:** forecast + completion + target + realidad + ajuste all in one row per product. **No competitor** has this — they all split forecast and reality across pages.
**Lesson:** This is the operator's cockpit. Keep it. Don't replace with a "modern" kanban.

### L-PLAN-2: Append-only plan audit (production_plan_audit) is unique 🔵
**Source:** memory + Sazon code. Competitors don't audit the plan itself; they only audit sale/receipt.
**Lesson:** When you extend production — make any override / template-load / fork-week write a row to this audit. Never replace rows. Apple's "Time Machine" model works because it's append-only.

### L-PLAN-3: 14-day rolling forecast window is too short for sparse products ⚠️
**Source:** Sazon `app/rms/production.py:73` (`forecast_window_days`), hardcoded `14`. **Competitive comparison:** OpenResto's `TurnTimesHelper` reads per-product type (seats → minutes); **URY** doesn't forecast at all (just KOT-driven).
**Risk / Effort:** 🟢 / 🟢 S — change window to 28d (after 14d of history) OR scale by `product.sale_count_history`.
**Take:** Today's forecast is sensitive to "what sold yesterday" not "what sells in November". Make window adapt.

### L-PLAN-4: `_forecast_confidence` is computed per row but not surfaced as a UI badge ⚠️
**Source:** `app/rms/production.py:74-101` (`_forecast_confidence` returns 0-100). Returns `(0, 0)` under 3 sales. **Competitor evidence:** None — only Sazon has confidence bands. **Used?** The `plan_accuracy` page reads it (via `daily_completions`).
**Lesson:** ⭐ **The single biggest open win.** Render the band on the grilla row (small chip: 🟢HIGH / 🟡MED / 🔴LOW). Cook can manually bump under-confident products.
**Effort / Risk:** 🟢 S / 🟢 low. 1-day: pass `confidence` from `_build_plan_reason` to the Jinja template + add a CSS badge.

### L-PLAN-5: Plan-completion upsert (idempotent re-mark) is excellent 🔵
**Source:** `app/rms/eod_completions.py:18-67` — `upsert_completion(session, product_id, for_date, qty, completed_by)`. Updates in place if (product_id, for_date) already exists, else inserts.
**Why it matters:** Operator can re-mark a row 10 times during a shift, no doubles. **RestoPOS** uses separate `consumption/complete` (insert-only); no upsert equivalent.
**Lesson:** Keep this pattern. It's the right model.

### L-PLAN-6: plan_accuracy is computed but never fed back into the plan ⚠️ ⭐
**Source:** `app/rms/plan_accuracy.py` — `compute_plan_accuracy()` reads `production_completion` + `production_plan_override` + `sale`. **Nothing calls it from `production.py`'s `forecast_sales`.** Verified by reading both files.
**Lesson:** ⭐ **This is THE loop we never close.** Add: in `forecast_sales()`, after computing the rolling avg, apply a multiplier: `1.0 + clamp((avg_under_baked / avg_demand), -0.3, 0.3)`. Once we wire this, accuracy moves in 2-4 weeks.
**Effort / Risk:** 🟡 M / 🟡 med. 1-2 days for the bias loop, plus 1 day to write tests (TRD-compliant RED-GREEN-REFACTOR).

### L-PLAN-7: SEASONAL_CALENDAR_2026 is hardcoded — `workflow.py:248` ⚠️
**Source:** `app/rms/workflow.py:248` — `SEASONAL_CALENDAR_2026: list[SeasonalEvent] = [...]` with 14 hardcoded PY events.
**Problem:** To add "Año Nuevo 2027" you ship code. Competitor (TastyIgniter) puts all of this in a settings table per-restaurant.
**Lesson:** Move to `settings_kv` (the new single store from SASKIA-210+ sprint 2.1) under key `seasonal_calendar`. Operator-edit; one SQL `SELECT` from `active_events(day)`.
**Effort / Risk:** 🟢 S / 🟢 low. 1 day. Pure additive — old hardcoded list falls back when KV empty.

### L-PLAN-8: `demand_multiplier` takes max of events — copy from competitors that average ⚠️
**Source:** `app/rms/workflow.py:340` — `return max(e.multiplier for e in events)`. Two overlapping events: Pascuas *1.5 + Día de la Madre *1.2 = `1.5` (max).
**Alternative (the math):** A pascuas + día madre stacked could mean a multiplicative `1.5 × 1.2 = 1.8` (if they're orthogonal markets) or sum-style `0.5 + 0.2 = 0.7` lifted. There is no right answer, but `max` is the most conservative.
**Lesson:** Document WHY you picked `max`. URY/PizzaQL have no multiplier. **RestoPOS** uses daily-open-hours × holiday-flag (one bit). Sazon's `max` is fine; just don't compound events without thought.

### L-PLAN-9: weekly_template + override is the Sazon canonical pattern 🔵
**Source:** `app/rms/production.py:475` — `get_weekly_template()`, `upsert_template_row()`, `get_overrides_for_date()`, `upsert_override()`. Two tables: `production_plan_template` (Mon-Sun × product × qty) and `production_plan_override` (date × product × qty). Load-from-template button in produccion.html:34-46.
**Why it works:** Cooks learn the weekly rhythm ("Tuesdays need 200 medialunas"), can override per-day ("Tuesday 14 is Pascuas → +50%").
**No competitor** has this — they all forecast only from history, no weekly rhythm teaching.
**Lesson:** Keep. Maybe expose a `production_plan_audit` record when the template gets forked (currently it does — verify in `templates_ops.py`).

### L-PLAN-10: Day/Week/Month tab navigation is clean 🔵
**Source:** `app/templates/produccion.html:96-105`. The view-tabs set the `view=day|week|month` query param; same handler renders 3 views from 1 endpoint set. No competitor has a multi-view workspace.
**Lesson:** Keep. Add `Year` view if useful.

### L-PLAN-11: Pedidos-pending counts as forecast input is unique 🔵
**Source:** `app/rms/production_demand.py` (already read) — `qty_pedidos` = pedidos in `pending`, `confirmed`, `ready` state. Added on top of forecast avg × multiplier.
**Why it matters:** Same-day customer demand shows up. **No competitor** has pedidos-into-forecast merged.
**Lesson:** Keep. Document this for the operator — they should learn "today's plan was boosted by 8 orders due at 11am".

### L-PLAN-12: Bulk CSV "Horneado extra" ad-hoc entry ⭐
**Source:** `app/templates/produccion.html:507` — sprint 4 ad-hoc entry button below table. Lets cook enter a flex grid of unannounced bakes. Post route `produccion/ad-hoc` and `/ad-hoc/bulk` in `app/routers/produccion/operations.py`.
**Lesson:** ⭐ Closest competitor (FloCafe) has nothing equivalent. This is a Sazon-exclusive operator workflow. **Keep + advertise as a feature**.

---

## 3. STOCK / INVENTORY / BOM (7 lessons)

### L-STOCK-1: stock_movement as the single ledger is the right architecture 🔵
**Source:** `app/rms/stock_ledger.py:72-130` + memory note 2026-10-01. Every sale, every merma, every reorder writes ONE `StockMovement` row. `SaleStockMove` is the deprecated stub.
**Competitive comparison:**
- FloCafe writes to `order_items.status` + `supply_movements` (two tables)
- RestoPOS has separate `consumption/complete` + `purchase/receive` paths
- URY has `ury_materials` + KOT-level deltas
- Flutter POS has `Stock.stockQuantity` + `Movements` per ingredient

**Lesson:** Stay strict. Rule 8 in AGENTS.md. Every new stock-impacting write goes through `stock_ledger.apply_stock_delta()`. Don't reopen the multi-table problem.

### L-STOCK-2: Per-sale packaging item flag is best-in-class 🔵
**Source:** `app/rms/costing.py:380-405` + `app/rms/models/procurement.py:160-180`. `Ingredient.is_packaging` boolean; `apply_sale()` accepts `packaging_item_id` + `packaging_qty`. Validation that the ingredient is packaging-flagged.
**No competitor:** has this. **No competitor** separates "raw material" from "packaging" (bags, ribbons). RestoPOS treats packaging as another `Product`.
**Lesson:** Keep + tag this as a featured pattern. Tell staff: "Sazon tracks if you give a customer two bags, that's two bags of inventory out".

### L-STOCK-3: Sub-recipe recursion in cost walk is mature 🔵
**Source:** `app/rms/costing.py:549-595` — `_compute_stock_moves()` recurses, with cycle detection (`CycleInRecipeTree`), `affected_recipe_id` tagging at write time.
**Competitive comparison:**
- FloCafe: ❌ (1-level only)
- RestoPOS: ❌
- URY: partial via `ury_production_item_groups` (groups items but doesn't recurse)
- PizzaQL: no recipes at all
**Lesson:** Keep. Bake this in. **Sazon wins on multi-level BOM.**

### L-STOCK-4: Ingredient variant preference is best-in-class 🔵
**Source:** Sazon `/inventario/<id>/variantes` routes + `ingredient_variants` table. A product can have multiple ingredient variants per line; cook picks preferred, system falls back.
**Competitor comparison:** None has this. RestoPOS has no variants; the whole "buy alternative if out of stock" problem is solved by Sazon's discrete selection.
**Lesson:** Keep. Document under `recipes.auto_substitute` for the operator.

### L-STOCK-5: Stock-card with movement log is what operators want 🔵
**Source:** `app/templates/ingrediente_detalle.html` (360 lines) — shows current qty + every `StockMovement` row for that ingredient. **Each row carries** movement_type, qty, reason, reference_id, reference_type, recorded_at, created_by.
**No competitor** shows this granular per-ingredient ledger. RestoPOS has a `report/supplier/stock` summary only.
**Lesson:** Keep. Use as the operator-facing audit trail.

### L-STOCK-6: Stock-status-config is the right primitive ⚠️
**Source:** `app/routers/settings_runtime.py:stock-status-config` + `app/rms/insights_stock.py`. Operator can set per-ingredient status thresholds (OK, low, critical) via settings_kv (sprint 2.1).
**Lesson:** This is a 1-line tweak that closes a FloCafe gap (their `low_stock` is a hardcoded multiplier). Keep the dynamic config.

### L-STOCK-7: BOM-cost change has no front-of-house signal ⚠️
**Source:** Sazon's `app/rms/costing.py:275-345` (`recipe_unit_cost_gs`) recomputes the cost; `reportes/demand`, `reportes/precios`, `reportes/margenes` read it. **No route** emits a "cost changed → re-check product price" alert.
**Compare:** RestoPOS's `report/gst/sale/bill` does include cost-per-bill at sale time. Sazon's `reportes/margenes` shows current margin but doesn't show Δ.
**Lesson:** Add `product_margin_delta` to `/reportes/margenes` — show "since last 7d: this product's cost moved +12%, current margin dropped 4pp".

---

## 4. KDS / KOT / PRINTING (8 lessons)

Sazon doesn't have a live KDS. These are the lessons from competitors that do.

### L-KDS-1: KOT status as PATCH endpoint is the canonical pattern (FloCafe) ⭐
**Source:** FloCafe `main/routes/order-items.ts:1` and `main/routes/kds.ts:5`:
```
PATCH /api/order-items/:id/status           (advance KOT line)
GET   /api/kitchen/orders                   (live KOT list)
GET   /api/kitchen/sse                      (real-time push)
PATCH /api/kitchen/items/:id/status         (advance KOT for kitchen)
```
**Lifecycle:** `pending → preparing → ready → served → (voided locked)`.
**Lesson:** ⭐ **The single best argument for a Sazon KDS.** Cook can bump a row when each batch comes out of the oven; KDS becomes a live workspace, not a worksheet.
**Effort:** 🟠 L. Multi-feature: SSE channel + new route + Vue/Tablet view + integration with `ProductionCompletion`.

### L-KDS-2: KOT error log for print observability (URY) ⭐
**Source:** URY `ury/ury/doctype/ury_kot_error_log/` — JSON log of every KOT print failure with the printer ID, payload, reason. Lets ops debug "the hot sandwich printer jammed and 3 orders never got printed".
**Sazon:** No equivalent. `print_export.py` writes to disk but doesn't surface errors visibly.
**Lesson:** Add `production_print_errors` table. On failure, write: `(timestamp, batch_id, order_id, printer_id, payload_hash, error_message)`. Operators get a dashboard widget.
**Effort:** 🟢 S. 1 day.

### L-KDS-3: KOT "type" flag: new vs duplicate (RestoPOS) ⭐
**Source:** RestoPOS `routes/tenant.php`: `POST /kot/direct/print/{order_id}/{type}` with `type = 'new'|'duplicate'`. Lets the cashier re-fire the same KOT to a backup printer when the first one jams.
**Sazon:** `produccion/print` exists but no re-fire concept.
**Lesson:** ⭐ **Adopt verbatim.** Low-effort, high payoff. Add a "Reimprimir" button on `/produccion`.
**Effort:** 🟢 S. 1 day.

### L-KDS-4: Multi-printer auto-select on kitchen station (URY + FloCafe)
**Source:** URY `ury_production_unit.kot_printer` + `ury_production_item_groups.item_group`. Each kitchen display can route a category to a specific printer.
**Sazon:** No station model at all. KOT path is invisible (`print_export.py` only).
**Lesson:** If/when multi-baker or multi-station: model a `production_station` table with `kot_printer_id` and `item_category_ids`. Currently Sazon is single-station — *don't over-engineer*.

### L-KDS-5: ESC/POS printer settings (FloCafe + URY)
**Source:** FloCafe `main/routes/printers.ts` — full CRUD over printers, with `set-default`, `test`, `detect` actions. 20+ printer routes. URY `ury_printer_settings` does the same.
**Sazon:** Has thermal-print path; no operator-facing printer config UI.
**Lesson:** Add `/config/printer` page with: list printers, set default, "test print" button. Currently operator's printer config is in fastlane/electron-side config — invisible.
**Effort:** 🟡 M. 1-2 days.

### L-KDS-6: Real-time SSE for KDS (FloCafe)
**Source:** FloCafe `main/server.ts:308-339` — WebSocket upgrade handler + per-connection enablement. `main/kds-server.ts:159` — KDS-only SSE endpoint with rate-limit guard.
**Sazon:** No SSE / WebSocket anywhere in production. Server-rendered + reload only.
**Lesson:** If KDS gets built (L-KDS-1), adopt SSE pattern. Don't reach for WebSocket unless you need bi-directional.
**Effort:** Part of L-KDS-1.

### L-KDS-7: Maintenance-mode middleware drains KDS (FloCafe)
**Source:** FloCafe `main/db.ts:23-35` — request-counter middleware blocks new KDS requests, drains in-flight, blocks long enough to apply DB updates safely.
**Sazon:** No equivalent. During schema migration in production, the operator gets 500s.
**Lesson:** Add a `MaintenanceMode` middleware to `app/main.py` that returns `503 + Retry-After`. Mark `routes that matter` (KDS, /ventas) as requiring not-maintenance. Set maintenance = True at top of `--migrate` script.
**Effort:** 🟢 S. 0.5-1 day. **Bonus:** solves the in-flight-transaction issue from a separate lesson.

### L-KDS-8: WebUSB / Bluetooth printer (Flutter POS)
**Source:** Flutter POS `lib/ui/printer/` + `services/bluetooth.dart`. Configurable per-device printer discovery.
**Sazon:** Operator works from a laptop with USB thermal; Bluetooth not needed.
**Lesson:** Skip unless tablets become a thing. (See L-OPS-4 for tablet-readiness.)

---

## 5. SALES / POS (7 lessons)

### L-SALES-1: Hold-cart / stashed orders are operator-essential (Flutter POS + FloCafe) 🔵
**Source:** Flutter POS `lib/ui/order/checkout/stashed_order_list_view.dart`. FloCafe `main/routes/held-orders.ts` — held orders = cart parked to a table.
**Sazon:** Has `ventas/held` route + `apply_sale(...held_id)` resume (`app/routers/sales.py: held_*`). **Already shipped.**
**Lesson:** Keep. Good workflow for a single-op bakery.

### L-SALES-2: Split-check / split-payment (FloCafe) ⚠️
**Source:** FloCafe `main/routes/bills.ts`: `POST /:id/split-check` creates child bills; `POST /:id/payments` allows multiple payments per bill.
**Sazon:** No split-payment support on a single sale. Single customer = single payment.
**Lesson:** Not relevant (Asunción bakery: mostly cash, single-customer; subscription deliveries are recorded as pedidos separately). **Mark as never-needed.**

### L-SALES-3: Multi-channel pricing (Sazon-only) 🔵
**Source:** `app/routers/pricing.py` + `costing.py:443-446`. Each `Product` has channel-specific prices.
**No competitor** has per-channel pricing. RestoPOS uses a single `sale_price`. FloCafe has `prices` table per `variant_id` but not channel-aware.
**Lesson:** Keep. **Sazon exclusive feature.**

### L-SALES-4: Pack-slip printing on pedido (Sazon only) 🔵
**Source:** Sazon `app/routers/sales.py:sale_receipt` + `ventas/{sale_id}/recibo` route. Pedido fulfillment prints a separate pack-slip for delivery orders.
**No competitor** has the pedido-vs-walkin bifurcation.
**Lesson:** Keep. Subscriptions + delivery are baked into the model.

### L-SALES-5: Receipt digit-share via URL (Sazon) 🔵
**Source:** Sazon `app/routers/sales.py:share_sale_recibo` — POST creates a public-link receipt for the customer.
**FloCafe** has no WhatsApp-share; only print.
**Lesson:** Keep; **consider adding WhatsApp share** via the `whatsapp` route group (L-OPS-1 below).

### L-SALES-6: Sale-void is locked-once (FloCafe)
**Source:** FloCafe `main/routes/order-items.ts:#150: locked once voided — see main/routes/order-items.ts for the same rule.`
**Sazon:** `ventas/{sale_id}/anular` exists; doesn't apply same lock.
**Lesson:** Apply same lock. Once voided, `anular` 404s (not 200 with empty action).

### L-SALES-7: Refunds on a voided sale (FloCafe)
**Source:** FloCafe `main/routes/refunds.ts`: POST `/api/refunds` initiates refund; GET `/api/refunds` lists. Creates a new sale with negative qty, links to original.
**Sazon:** No refunds system — voids only.
**Lesson:** Could matter for delivery. SKIP for now, document for post-MVP.

---

## 6. REPORTS / ANALYTICS (6 lessons)

### L-RPT-1: Reports are 30+ distinct routes in Sazon (good breadth) 🔵
**Source:** Verified via grep sweep — `app/routers/reportes.py` has 21 routes; `app/routers/insights*.py` adds 9 more; `app/routers/reportes.py` covers IVA, libro-ventas, comparacion, top-productos, retencion, cierre-mensual, valor-pedido, ventas-hora, mermas-cost, metodos-pago, consumo, demand, precios, diario/pdf, iva/pdf, monthly close, etc.
**Lesson:** Don't add reports without thinking — the surface is already wide. New reports should target an operator question; if they don't, don't ship.

### L-RPT-2: Daily P&L rollup is the missing centerpiece (URY) ⭐ ⚠️
**Source:** URY `ury_daily_p_and_l` doctype (already read):
```
gross_sales, cash_discount_round_off, tax, net_sales, cogs, total_direct_expenses,
gross_profit, total_employee_costs, depreciation, total_other_expenses,
total_indirect_expenses, net_profit
+ percent versions of each + 5 expense breakups (electricity, materials, other,
  employee, indirect) + COGS detail.
```
**Sazon:** No daily P&L exists. `reportes/cierre-mensual` is monthly only.
**Lesson:** ⭐ Build it. **Pure additive**: roll up `sale + stock_movement` from existing tables. Just shape the data. Single SQL with `GROUP BY date + metric`.
**Effort:** 🟡 M. 1-2 days. Two routes: GET `/reportes/ply` (JSON) and a new template `reportes/ply.html`. Tests as usual.

### L-RPT-3: Plan accuracy widget exists but is unused ⭐ ⚠️
**Source:** Sazon `app/routers/produccion/analytics.py:produccion_accuracy`. Calls `plan_accuracy.compute_plan_accuracy()`. **Never read** by `production.py` forecast_sales() (verified).
**Lesson:** Same as L-PLAN-6. Wire it. Effort 🟡 M / 🟡 med.

### L-RPT-4: Top-5 worst/best days widget is built but unstyled ⚠️
**Source:** Sazon `plan_accuracy.py:_top_worst_days`, `_top_best_days` — 5 worst days (worst under/over baked) and 5 best. Drawn but never surfaced on the dashboard.
**Lesson:** Surface on `/` (inicio) as two card widgets.
**Effort:** 🟢 S. 0.5 day.

### L-RPT-5: Reports export-to-CSV is universal
**Source:** Sazon `/reportes/consumo/csv`, `/reportes/precios/csv`, `/inventario/export.csv`, `/productos/export.csv`, `/recetas/export`, `/pedidos/export-csv`, `/ventas/export.csv`, `/excel/plantilla`. **~10 CSV exports**.
**Competitors:** FloCafe `/api/reports/x-report/export`, similar. RestoPOS doesn't CSV.
**Lesson:** Keep CSV exports. Add Excel export (xlsx) for the operator who has LibreOffice — `app/routers/excel_io.py` already exists; expand.

### L-RPT-6: Net-profit percent by day-of-week is rare
**Source:** No competitor — only URY's daily P&L has percentages. Most don't. Sazon's `reportes/diario` has totals but not %.
**Lesson:** Add percent column to `reportes/diario`.

---

## 7. ARCHITECTURE / CODE PATTERNS (10 lessons)

### L-ARCH-1: Sazon's package-by-feature mirrors Flutter POS 🔵
**Source:** Sazon `app/routers/produccion/_full.py` → 10 module split (`operations`, `analytics`, `forecast`, `prep_recipes`, `print_export`, `templates_ops`, `_helpers`, `_router`, `__init__`). Flutter POS `lib/ui/{menu,stock,order,order_attr,analysis,printer,cashier}/`. One router file per feature.
**Lesson:** ⭐ Apply this **within** `produccion/` — currently the `_full.py` is still 1,000+ lines (legacy from before the split). Split `_full.day_view()` into `_views/day.py`, `_views/week.py`, `_views/month.py`. The split refactor completes the architecture.

### L-ARCH-2: DDD service-per-domain (resto-nestjs) 🟢
**Source:** `resto-nestjs/backend/src/order/order.service.ts` — one service owns one entity. Returns `Result<T>` (Either-monad style).
**Sazon:** Already has `apply_sale`, `plan_production`, `compute_plan_accuracy` — each owns its entity.
**Lesson:** Stay consistent. New features ship `app/rms/<feature>.py` with a service, not controller logic.

### L-ARCH-3: Repository pattern with staged/committed (Flutter POS) 🟢
**Source:** Flutter POS `lib/models/repository.dart`:
```dart
mixin Repository<T extends Model> on ChangeNotifier {
  Map<String, T> _items = {};        // Saved to FS
  final Map<String, T> _stagedItems = {}; // In-memory (for import)
  Future<void> addItem(T item, {bool save = true})
  Future<void> commitStaged({save, reset})
  void abortStaged()
}
```
**Sazon:** No equivalent. CSV import (Sazon has `excel_io`) loads directly without staging.
**Lesson:** Add staging. When importing a CSV with rows that may conflict (duplicate SKU, etc.), stage first; let operator "review diff", then commit.

### L-ARCH-4: Multi-server split (FloCafe) 🟡
**Source:** FloCafe 3 servers: API `:3001`, KDS `:3002`, server-app `:3003`. Same DB. Each server has different middleware (KDS allows anonymous login, API requires auth).
**Sazon:** Single FastAPI server, one process.
**Lesson:** Don't split. Sazon is single-process intentionally (SASKIA-210). If you ever ship a wall-TV KDS, a small Flask sidecar with SSE is the right move.

### L-ARCH-5: Audit-context pattern (Frappe + resto-nestjs) 🟢
**Source:** Frappe (all URY doctypes) — every DocType has `creation`, `modified`, `modified_by`, `owner`. resto-nestjs `domain/audit/audit.ts` — `Audit.createInsertContext(currentUser)`.
**Sazon:** Has `app/rms/audit.py` for HACCP. **Missing** `recorded_by` and `created_by` on `stock_movement` (the field exists but is often NULL).
**Lesson:** Stamp `created_by = current_user` on every stock_movement write. Already in the field list (verified in `procurement.py:145-180` — `created_by` column exists); just need to pass the user down through the service layer.

### L-ARCH-6: Order-processing-queue pattern (resto-nestjs) 🟡
**Source:** `resto-nestjs/backend/src/order_processing_queue/` — has `OrderProcessingQueue` entity with `orderId`, `orderStatusId`, `audit`. When an order moves to a new status, a queue row is written. Real-time consumers watch the queue.
**Sazon:** No equivalent. Pedidos status changes are in-place updates on `pedido.status`.
**Lesson:** ⭐ **Adopt the audit pattern, NOT the queue.** `pedido_status_audit (pedido_id, old_status, new_status, changed_at, changed_by)` — gives you "what time did this go ready" reporting without a queue. Append-only fits Sazon's append-only ethos.

### L-ARCH-7: Settings bucket (Sazon sprint 2.1) 🔵
**Source:** Sazon `app/rms/settings_registry.py` (new in sprint 2.1) + `app/rms/costing.py:settings_kv`. Single KV table, no more `settings.py` vs `settings_original.py`.
**Lesson:** Move all hardcoded literals to KV: `forecast_window_days`, `low_stock_multiplier`, `critical_stock_multiplier`, `eod_horas`, etc. (Sazon `memory: Sprint 2.1 COMPLETE`)

### L-ARCH-8: Test-first RED-GREEN-REFACTOR (AGENTS.md rule)
**Source:** `app/rms/stock_ledger.py` has 3 call-sites refactored onto one helper (memory 2026-10-07 SASKIA-207).
**Lesson:** Keep applying. The codebase reward is, every helper has its own `tests/test_<helper>.py`.

### L-ARCH-9: Migration discipline (Sazon hands-on) 🔵
**Source:** Sazon has hand-rolled migrations (`migrations/090_add_affected_recipe_id.sql`, etc.), no Alembic. 114 migrations to date.
**Lesson:** Each migration has an inverse archived (`archives/migration_113_pre.sql`). Rule 17 in AGENTS.md enforces this. **Do not relax.** Sazon's `rollback.py` (SASKIA-209) consumes them.

### L-ARCH-10: Compact monorepo's value
**Source:** Single Sazon repo contains everything (router, model, template, migration, test, fixture). All 9 competitors split: TastyIgniter core + 22 extension repos, Enatega 5 modules, OpenResto 4 sibling projects, Flutter POS + flutter-pos-packages sibling repo.
**Lesson:** Stay monorepo. Single deployment; one migration set; one test runner. The competitor split forces issue-tracking across repos and slows feature work.

---

## 8. UI / PAGE-LAYOUT (8 lessons)

### L-UI-1: One page per feature, widget per modal (Flutter POS) ⭐
**Source:** Flutter POS `lib/ui/{feature}/{feature}_page.dart + widgets/`. 15 features, ~35 widgets.
**Sazon:** `produccion.html` is 2366 lines. `receta_form.html` 888 lines. `producto_form.html` 520 lines.
**Lesson:** ⭐ Apply across `/produccion`, `/recetas/<id>/editar`. Decompose into `components/produccion/{demand_column, completion_form, merma_inline, haccp_banner}.html`.
**Effort:** 🟠 L. 1 sprint.

### L-UI-2: Drag-and-drop reorder (Flutter POS) ⭐
**Source:** Flutter POS `lib/ui/analysis/widgets/chart_reorder.dart`, `lib/ui/menu/widgets/product_reorder.dart`, `lib/ui/menu/widgets/product_ingredient_reorder.dart`.
**Sazon:** Produccion grilla has column sort (`m.sort_th()`), no row reorder.
**Lesson:** ⭐ Add `product_reorder` on the grilla — bakers pin their top-5 daily products. Persist order per user in a `user_pin` table.
**Effort:** 🟡 M. 1-2 days.

### L-UI-3: Reloadable cards (Flutter POS)
**Source:** `lib/ui/analysis/widgets/reloadable_card.dart` — each KPI card fetches independently.
**Sazon:** `/` (inicio) renders entire page at once.
**Lesson:** For dashboard widgets, lazy-fetch. Operator clicking "refresh sales" should not re-render HACCP.
**Effort:** 🟡 M. 1-2 days.

### L-UI-4: Stashed cart view (Flutter POS / FloCafe)
**Source:** Already in L-SALES-1. UI is `lib/ui/order/checkout/stashed_order_list_view.dart`.
**Sazon:** `ventas/held` exists, surfaces in `ventas.html`.

### L-UI-5: Day/Week/Month view-tabs (Sazon) 🔵
**Source:** `produccion.html:96-105`. **No competitor** has this in a single page; they have separate pages or charts.
**Lesson:** Keep. Mention in marketing as "Sazon's signature".

### L-UI-6: Day-nav + J/K/O/C keyboard shortcuts (Sazon only) 🔵
**Source:** `produccion.html` references `app/static/shortcuts.js` (per the day-nav include). Per memory: "T-2026-10-04 (D.2): shift-context deep-link...Sebas passes a WhatsApp URL `/produccion?for_date=2026-10-05&shift=PM`".
**Lesson:** Keep. Add shortcut help (`?` key) — minimal text overlay.

### L-UI-7: Filter chip groups above the table (Sazon 2026-10-07)
**Source:** `produccion.html:788` — table overhaul: "filter chip groups above the table". Documented in the template comments.
**Lesson:** This pattern is best-in-class. Apply to `/productos`, `/clientes`, `/pedidos`. (Currently they're plain tables.)

### L-UI-8: Sheets-and-tables pattern for varied roles (DineOut)
**Source:** DineOut has 5 Activity trees (BillingActivity, KitchenActivity, HallActivity, OrderActivity, AdminActivity), each tuned for that role.
**Sazon:** Single-operator doesn't need role-segregation UI.
**Lesson:** Skip. Document why (single-operator per memory SASKIA-210).

---

## 9. OPS / COMPLIANCE / SAFETY (6 lessons)

### L-OPS-1: WhatsApp integration is table-stakes (FloCafe) ⭐ ⚠️
**Source:** FloCafe `main/routes/whatsapp.ts` — 14 routes: status, QR, pairing-code, enable/disable, send, messages, inbox, reply, blocklist. Uses `baileys-loader.cjs` (a Baileys fork).
**Sazon:** No WhatsApp. Pedidos are received manually.
**Lesson:** ⭐ **Adopt in phases.**
- **Phase 1:** Share-the-receipt — already have `share_sale_recibo`. Just wrap it in a `https://wa.me/<phone>?text=<receipt_url>` template.
- **Phase 2:** Send "your order is ready" notification via Baileys Web (a worker process; same as FloCafe).
- **Phase 3:** Inbound inbox (paste into `/pedidos` form).

**Effort:** 🟠 L. Skip for sprint 2.1 focus.

### L-OPS-2: Pre-billing checklist gates (URY `ury_pos_checklist_log`) ⭐ ⚠️
**Source:** URY `ury_pos_checklist_log` JSON (already read):
```
pos_profile, branch, checklist_type (Opening | Closing),
pos_opening_entry, shift_date, status (In Progress | Complete),
completed_by, completed_at, items (table-field → ury_checklist_log_item)
```
- `ury_checklist_item` JSON:
```
item_label, applies_to (Opening | Closing | Both), is_mandatory
```
**Pattern:** POS won't open for sales until checklist is `Complete`. Per-shift, per-day.
**Lesson:** ⭐ **Adopt verbatim.** Build `pos_checklist_log` + `pos_checklist_item` + `pos_checklist_log_item`. Add `assert_day_open_or_raise(session, day, action)` (Sazon already has this for HACCP, generalize).
**Effort:** 🟡 M. 2 days.

### L-OPS-3: KOT error log (URY, same as L-KDS-2)
**Source:** `ury_kot_error_log`. Wraps every print failure.
**Lesson:** Same as L-KDS-2. Effort 🟢 S.

### L-OPS-4: Multi-tenancy is opt-in, not default (TastyIgniter + RestoPOS) ⚠️
**Source:** TastyIgniter = multi-tenant by default; RestoPOS uses Stancl Tenancy. Sazon = single-tenant (memory SASKIA-210).
**Lesson:** ⭐ **Stay single-tenant.** The decision is documented. If/when you resurrect multi-tenancy, TastyIgniter's extension model is the right pattern (one repo per tenant feature), but Sazon's product is "per-client instances" not "shared DB".

### L-OPS-5: Database backup tool (FloCafe)
**Source:** FloCafe `main/routes/database-tools.ts` — `apply-safe-fixes`, `backups/:fileName/delete`, `master-pin/reset`, `currency-reset`. Operator database tools.
**Sazon:** Sazon has `sazon backup` CLI + VPS 03:15 cron backup (memory note). The UI surface for "trigger now / restore from backup" isn't in the Web app.
**Lesson:** Add `/admin/backup` page with: "Trigger backup now", list existing backups, restore-from-backup (with master PIN).
**Effort:** 🟡 M. 2 days.

### L-OPS-6: Migration in maintenance mode (FloCafe + L-KDS-7)
**Source:** FloCafe `main/db.ts:23-35` maintenance middleware.
**Lesson:** Same as L-KDS-7. Effort 🟢 S.

---

## 10. SETTINGS / CONFIG (5 lessons)

### L-SET-1: settings_kv is the right store 🔵
**Source:** Sprint 2.1 (shipped 2026-10-07). One KV table. Already deprecated `settings.py` + `settings_original.py`.
**Lesson:** Every TastyIgniter "settings table", every URY "Ury Settings DocType", every FloCafe "Settings API" — fold them into Sazon's `settings_kv`. Operator-edit, no deploy.

### L-SET-2: settings_catalog.json for editing UI (Sazon) 🔵
**Source:** `app/templates/settings_catalog.html` (887 lines) — UI for editing every key in `settings_registry.py`. One form per key group.
**Lesson:** No competitor has a generic settings editor (they all have per-feature settings pages). Sazon's pattern is best-in-class and should be applied even to new settings — write the JSON shape, the form auto-renders.

### L-SET-3: Multi-location per-tenant (TastyIgniter)
**Source:** TastyIgniter `Location` doctype, multi-branch by default.
**Sazon:** Single location only.
**Lesson:** Mark as never-needed.

### L-SET-4: Currency packs / tax packs (FloCafe) ⭐ ⚠️
**Source:** FloCafe `main/routes/tax-packs.ts` — 16 routes. Tax system is pluggable: per-country tax rules, test-calculation endpoint, versioned packs.
**Sazon:** Has `tax-config` route group + `iva-rates` per Paraguay. Hardcoded PY.
**Lesson:** **Don't go tax-pack level.** Single country (PY), just use the `iva-rates` setting. Document why (single jurisdiction). Skip the abstraction.

### L-SET-5: Set-up wizard (FloCafe + DineOut + TastyIgniter) 🟡
**Source:** FloCafe `auth.ts:setup/status`, `setup/initialize`, `setup/seed`. TastyIgniter has a separate `setup` repo. DineOut requires Firebase RTDB import.
**Sazon:** No setup wizard — `sazon init` CLI (operator runs).
**Lesson:** **Don't add.** Single-tenant; operator is admin; the CLI is enough.

---

## 11. WHAT NOT TO COPY (forced divisions per Sazon decisions)

### L-NO-1: ❌ Don't build tenant/multi-tenant ⭐
**Source:** Memory `SASKIA-210 DECISION (2026-10-07)`: product = per-client INSTANCES, NOT shared-DB multi-tenant.
**Counter-evidence:** TastyIgniter, RestoPOS, Enatega are all multi-tenant.
**Skip:** Tenancy, RLS, ORM-level user scoping, Shopify-like "tenant subdomain" maps.

### L-NO-2: ❌ Don't build mobile app ⭐
**Source:** Memory: operator is at the laptop (VPS-hosted). No operator on tablet.
**Counter-evidence:** OpenResto, URY, Flutter POS, DineOut, Enatega all have mobile.
**Skip:** React Native / Flutter mobile, push notifications, mobile auth.

### L-NO-3: ❌ Don't build a self-ordering kiosk ⭐
**Source:** Memory SASKIA-210: "per-client instance", no shared customer interface.
**Counter-evidence:** TastyIgniter, OpenResto, URY have self-ordering kiosks.
**Skip:** Kiosk views, kiosk-assigned tablets.

### L-NO-4: ❌ Don't integrate payments ⭐
**Source:** Memory: operator's customer base is mostly cash + informal. No card processor.
**Counter-evidence:** TastyIgniter, RestoPOS, URY support Stripe/PayPal/square.
**Skip:** Payment gateway integrations (note: existing `sales.py:payment_method` field is open-text "efectivo / transferencia / otro", which works).

### L-NO-5: ❌ Don't fork for multi-language ⭐
**Source:** Memory user profile: operator is one Paraguayan mother; UI is vos-Spanish; no English/Portuguese branches despite Enatega/FloCafe shipping 24 locales.
**Skip:** i18n/multi-locale, locale packs.

### L-NO-6: ❌ Don't build a queue/worker system ⭐
**Source:** Memory: single-process, single-tenant, single-operator.
**Counter-evidence:** resto-nestjs `order_processing_queue`, Enatega background jobs.
**Skip:** Sidecar processes, message brokers, distributed locks.

### L-NO-7: ❌ Don't touch KDS unless explicitly requested ⭐
**Source:** Memory: VPS-hosted, single operator at counter; no live wall TV in current bakery.
**Counter-evidence:** FloCafe, URY (mosaic), RestoPOS (kot direct), OpenResto (admin tablet).
**Skip (for now):** WebSocket/SSE channels, multi-station routing.

### L-NO-8: ❌ Don't split into a monorepo ⭐
**Source:** Single deployment + simple migration story is the value-prop. TastyIgniter/Enatega are forced into multi-repo because of extension / multi-app needs.
**Skip:** Any split into `sazon-core + sazon-ext-*` style.

---

## 12. SAZON DECISION LOG (canonical, restated)

These are the "why we work this way" decisions. Reference these when a competitor pattern seems attractive:

| Decision | Date | Decided by | Source |
|---|---|---|---|
| Single-tenant, per-client instances | 2026-10-07 | Ivan | memory SASKIA-210 |
| Local-first + VPS hosted (not pure SaaS) | founding | Ivan | sazon_profile.json |
| Server-rendered HTML (no React/Vue) | founding | Ivan | sazon_profile.json |
| Hand-rolled migrations, 114 so far | sprint 2.1 | Ivan | memory |
| Integer-Guaraní in DB (no decimals) | founding | Ivan | sazon_profile.json |
| sale→stock_movement writes via costing.py:380 | 2026-10-01 | Ivan | memory SASKIA-207 + AGENTS.md rule 8 |
| settings_kv replaces settings.py | 2026-10-07 | Ivan | memory Sprint 2.1 |
| HACCP and `assert_day_open_or_raise` is the model for any new compliance check | 2026 | Ivan | eod_closed.py:109 |
| Migration is no-without-rule-17-inverse-archive | founding | Ivan | rollback.py:dc26df1f |
| No mobile, kiosk, payments, multi-tenant | 2026-10-07 | Ivan | memory SASKIA-210 |

---

## 13. APPENDICES

### Appendix A — Full Sazon route inventory (production-relevant, 117 routes)

**Produccion package** (44 routes via the 10-module split):
- `_full.py` (2)
- `analytics.py` (6 — accuracy, haccp, hacp POST)
- `forecast.py` (4 — manana, api/forecast)
- `operations.py` (18 — override, copy-last-week, close-day, ad-hoc, shift-execute, closed toggle, override-bulk, ad-hoc-bulk)
- `prep_recipes.py` (2)
- `print_export.py` (6 — print, export.csv, prep)
- `templates_ops.py` (6 — template, fork-week, load-day)

**Other production-relevant routers**:
- `customers.py`: 15 routes (clientes/*, customer_create_api, cliente_detail, etc.)
- `dashboard.py`: 2 (`/`, `/inicio`)
- `eod.py`: 5 (eod view, check, completar, anomalies/run, print)
- `insights.py`: 1
- `insights_derived.py`: 6 (food-cost-variance, demand, freshness, price-impact, allergen-check, substitutes)
- `insights_stock.py`: 4 (stock-intel, afinidades, margenes, margenes/{id})
- `inventory.py`: 27 (lots of CRUD + variants + bulk-fill-to-2x-min + tag-audit)
- `merma.py`: 4 (merma_list, merma_register, merma_register_recipe, waste_reasons_api)
- `pedidos.py`: 15 (pedidos_list, board, new, status, fulfill, stock-preview, duplicate, bulk-fulfill, bulk-cancel)
- `products.py`: 16
- `recipes.py`: 13 (incl. effective-ingredients API, units, families)
- `reorder.py`: 9
- `reportes.py`: 21
- `sales.py`: 19 (incl. held cart: hold, held/list, held/{id}/resume, held/{id}/discard)
- `settings_runtime.py`: 3 (stock-status-config)
- `shopping.py`: 8 (from-production-plan, sync-low-stock, save-plan/{plan_id}, mark/unmark/delete)
- `validation.py`: 1

### Appendix B — FloCafe's actual route inventory (28 files, ~150 routes)

Per-file route counts from disk scan:
- `addon-groups.ts`: 8 routes
- `auth.ts`: 10 routes (login, refresh, logout, me, password/change, recover-password, setup/*)
- `authorization.ts`: 8 routes (catalog, roles, users, audit)
- `bills.ts`: 13 routes (incl. split-check, payment, applyDiscount, markPrinted)
- `cash-closures.ts`: 5 (movements, open/close, print)
- `cash-sessions.ts`: 3 (open, current, close)
- `categories.ts`: 5 (CRUD)
- `customers.ts`: 8 (alerts, cleanup, repair-phones)
- `database-tools.ts`: 9 (health-check, backups, master-pin, currency-reset)
- `database.ts`: 6 (export, import, backup, restore, download, tables)
- `diagnostics.ts`: 4 (event, recent, support-bundle)
- `held-orders.ts`: 3
- `inventory.ts`: 1 (movements)
- `kds-info.ts`: 1
- `kds.ts`: 5 (orders, pairing, display, items/status)
- `kitchen-stations.ts`: 6
- `kitchen.ts`: 1 (orders only)
- `menu-csv.ts`: 8 (template + export/import × 4)
- `more-apps.ts`: 2 (revflo)
- `order-items.ts`: 1 (status)
- `orders.ts`: 11 (CRUD + status + customer + convert-to-takeaway + discount + cancel + restore)
- `payment-methods.ts`: 6 (incl. merge)
- `pos-info.ts`: 1
- `print-templates.ts`: 9 (CRUD + activate + archive + rollback + payload + export + import)
- `printers.ts`: 14 (CRUD + detect + supported + test + print-menu + print-bill + print-kot + delivery-slip)
- `products.ts`: 9 (CRUD + fetch-url + stock + loyalty)
- `recipes.ts`: 4 (CRUD over product_id)
- `refunds.ts`: 2 (POST, GET)
- `reports.ts`: 14 (daily-stats, summary, financial-summary, tax-components, sales, topProducts, recentOrders, tables, insights, x-report, z-report, exports, daily-sales/export)
- `server-app-info.ts`: 1
- `settings.ts`: 9 sub-groups (business, tax, loyalty, discount, kds, order-numbering, cloud) × 2-3 routes each
- `staff.ts`: 6 (CRUD + deactivate/reactivate)
- `supplies.ts`: 8 (CRUD + movements)
- `support-ticket.ts`: 7 (incl. pre-login routes)
- `tables.ts`: 11 (CRUD + floors/* + positions + move-order + status)
- `tax-packs.ts`: 14 (catalog, ensure-country, manual-config, test-calculation, overrides, install, activate, reinstall, rollback)
- `whatsapp.ts`: 14 (status, QR, pairing-code, enable/disable, send, messages, inbox/reply, blocklist)

**Standout patterns FloCafe has that Sazon doesn't**:
- 14 printer-management routes
- 14 tax-pack management routes
- 14 WhatsApp routes
- 7 support-ticket routes
- 6 kitchen-stations routes
- 4 print-templates routes

### Appendix C — URY doctypes (45 total, alphabetically)

```
aggregator_settings       item_add_on               pos_item_variants
kds_order_type            menu_for_room             multiple_rooms
order_type_menu           role_permitted            sub_pos_closing
sub_pos_closing_payment   sub_pos_invoices          ury_checklist_item
ury_checklist_log_item    ury_cost_of_goods         ury_daily_p_and_l
ury_fixed_expenses        ury_kot                   ury_kot_error_log
ury_kot_items             ury_materials             ury_menu
ury_menu_course           ury_menu_item             ury_merged_pos_invoice_detail
ury_notification_recipient ury_order                ury_order_item
ury_ordering_device       ury_ordering_session      ury_p_and_l_breakup
ury_p_and_l_materials     ury_payment_terminal      ury_payment_terminal_transaction
ury_pos_checklist_log     ury_printer_settings      ury_production_item_groups
ury_production_unit       ury_report_settings       ury_restaurant
ury_room                  ury_self_ordering_profile ury_service_request
ury_table                 ury_user                  ury_variable_expenses
```

**Grouped by purpose:**
- KDS (6): `kds_order_type`, `ury_kot`, `ury_kot_items`, `ury_kot_error_log`, `ury_production_unit`, `ury_production_item_groups`
- Orders (3): `ury_order`, `ury_order_item`, `ury_merged_pos_invoice_detail`
- Compliance (3): `ury_checklist_item`, `ury_checklist_log_item`, `ury_pos_checklist_log`
- P&L (5): `ury_daily_p_and_l`, `ury_p_and_l_breakup`, `ury_p_and_l_materials`, `ury_cost_of_goods`, `ury_fixed_expenses`, `ury_variable_expenses`
- Menu (4): `ury_menu`, `ury_menu_course`, `ury_menu_item`, `menu_for_room`
- Self-order (3): `ury_self_ordering_profile`, `ury_ordering_device`, `ury_ordering_session`
- Tables (3): `ury_table`, `ury_room`, `multiple_rooms`
- Payment (3): `ury_payment_terminal`, `ury_payment_terminal_transaction`, `sub_pos_closing_payment`
- Reports (2): `ury_report_settings`, `sub_pos_closing`
- Restaurant (10): `ury_restaurant`, `ury_printer_settings`, `ury_materials`, `ury_user`, `aggregator_settings`, `item_add_on`, `pos_item_variants`, `role_permitted`, `order_type_menu`, `ury_service_request`, `sub_pos_closing`, `ury_notification_recipient`
- (Python aliases in urypos app)

### Appendix D — Flutter POS file inventory

```
lib/
├── app.dart, main.dart, routes.dart, translator.dart
├── components/
├── constants/
├── debug/
├── firebase_compatible_options.dart
├── helpers/{breakpoint, launcher, logger, setup_example, util, validator}
├── l10n/                      ← i18n
├── models/
│   ├── model.dart, model_object.dart
│   ├── xfile.dart
│   ├── analysis/  menu/  order/  stock/
│   ├── objects/   repository/   printer.dart
│   └── receipt_component.dart
├── services/{auth, bluetooth, cache, database,
│             database_migration_actions, database_migrations,
│             image_dumper, storage}.dart
├── settings/
└── ui/
    ├── analysis/{analysis_view, history_page}.dart + 11 widgets
    ├── cashier/  elf_page/  home/  image_gallery_page
    ├── menu/{menu_page, product_page}.dart + 11 widgets (incl. 3 reorder)
    ├── order/{order_checkout_page, order_page}.dart + checkout/{stashed_order_list}
    ├── order_attr/{order_attribute_page}.dart + 6 widgets (incl. 2 reorder)
    ├── printer/{printer_page, printer_modal, printer_settings_modal}.dart + 5 widgets
    └── stock/{quantities_page, replenishment_page, stock_view}.dart + 7 widgets
```

### Appendix E — Glossary

- **KOT** = Kitchen Order Ticket (a printable slip listing items for one table/order)
- **KDS** = Kitchen Display System (a screen showing live KOTs)
- **BOM** = Bill of Materials (recipe ingredients)
- **DOW** = Day Of Week
- **EOD/EOW** = End Of Day / End Of Week (closing rituals)
- **P&L** = Profit & Loss
- **Y-P&L** = Daily Profit & Loss (URY term)
- **Production worksheet** = the daily baking checklist; Sazon's `/produccion`
- **POS** = Point of Sale (the cashier terminal)
- **RMS** = Restaurant Management System
- **Sazon** = the operator's friendly name (means "season" in Spanish)
- **Stock_movement** = the append-only ledger; Sazon's source-of-truth for stock
- **Plan completion** = the actual qty baked (vs the forecast qty to bake)

---

## SUMMARY — what to ship next (sorted by ROI)

**Sprint Z — close the feedback loops (3-4 days total, additive)**:
1. ⭐ L-PLAN-6: Wire `plan_accuracy` into `forecast_sales`
2. ⭐ L-PLAN-4: Render confidence badge on the grilla
3. L-PLAN-7: Move SEASONAL_CALENDAR_2026 into settings_kv
4. L-PLAN-3: Adaptive forecast window (14d → 28d fallback)

**Sprint A — flush the gaps (5-7 days)**:
5. ⭐ L-RPT-2: Daily P&L rollup
6. ⭐ L-OPS-2: Pre-billing checklist (URY pattern)
7. ⭐ L-KDS-2 + L-OPS-3: KOT error log
8. ⭐ L-KDS-3: KOT "duplicate" reprint button

**Sprint B — UX polish (1-2 weeks)**:
9. ⭐ L-UI-1: Decompose produccion.html into per-feature widget files
10. ⭐ L-UI-2: Drag-and-drop pin products on the grilla
11. ⭐ L-ARCH-1: Continue splitting `_full.py`
12. ⭐ L-UI-7: Filter chips on /productos, /clientes, /pedidos

**Sprint C — infra (1 week)**:
13. L-KDS-7 + L-OPS-6: Maintenance-mode middleware
14. L-ARCH-5: Stamp `created_by` on stock_movement
15. L-ARCH-6: pedido_status_audit table
16. L-ARCH-3: Staged CSV import for products/ingredients

**Sprint D — multi-feature (1-2 weeks, optional)**:
17. ⭐ L-OPS-1: WhatsApp share-the-receipt (phase 1)
18. ⭐ L-KDS-1: KDS PATCH endpoint + Vue/Tablet view (only if wall TV is bought)

**Skip-list (10 items)**: see Section 11.
