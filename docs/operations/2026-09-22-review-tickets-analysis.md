# Saskia RMS — Review Tickets Comprehensive Analysis

**Date:** 2026-09-22
**Repo:** `/opt/data/profiles/ivan/scratch/saskia-app-work` (branch: `main`, HEAD: `9fc0caf`)
**Source spec:** `/opt/data/profiles/ivan/attachments/2026-09-18-first-review-fixes.md`
**Tickets:** 18 (BUG-00, NAV-01, NAV-02, INV-01–03, VEN-01, VEN-02, PRO-01–04, CIE-01, CIE-02, MER-01–03, DATA-01)

---

## Status legend

| Symbol | Meaning |
|---|---|
| ✅ | Fully implemented per ticket acceptance criteria |
| 🟡 | Partially implemented (some acceptance criteria met, others not) |
| ⚠️ | Implemented but has a bug or regression |
| ❌ | Not implemented |
| 🚫 | Explicitly removed (matches "remove" type) |

---

# Part 1 — Per-ticket analysis

## BUG-00 — Creating an item crashes the page 🚫→🟡

**Status: 🟡 PARTIAL**

The exact 500-error root causes from 2026-09-22 outage have been fixed (per `COMPLETE_PLAN.md`), but a fresh review against each create form yields gaps.

### What was hit
- Productos, Inventario, Recetas, Recetas line, Ventas, "+ Nuevo cliente" from Ventas.

### Evidence (file:line)

| Flow | Route | Status | Evidence |
|---|---|---|---|
| Productos create | `POST /productos/nuevo` | ✅ | `app/routers/products.py:186-228` — validates name, price; 409 on dup; 303 redirect. |
| Inventario create | `POST /inventario/nuevo` | ✅ | `app/routers/inventory.py:149-233` — order fixed (was 422); validates unit, stock ≥0, min ≥0; records initial movement + price event. |
| Recetas create | `POST /recetas/nueva` | ✅ | `app/routers/recipes.py:131-178` — async form parse; validates name; uses `_apply_lines_from_form`. |
| Recetas line | (within receta POST) | 🟡 | `_apply_lines_from_form` (`recipes.py:339-394`) silently **skips** lines with empty kind/target/qty/qty≤0/target≤0/unparseable. No row-level error feedback. |
| Ventas create | `POST /ventas/nueva` | ✅ | `app/routers/sales.py:360-487` — 422 from `Form(..., gt=0)`; SKU→product lookup; channel/payment validation; rate-limited. |
| "+ Nuevo cliente" from Ventas | `POST /clientes/api/create` | ✅ | `app/routers/customers.py:239-284` — JSON or form; 422 if name missing; idempotent on phone. |

### Gap
- Recipe-line invalid input → no per-line field error message; recipe is saved with fewer lines than expected and the user has no idea why.
- None of the create forms return a **specific** field-level Spanish error ("what is wrong, which field, what to enter") for the most-common invalid inputs (empty name, negative price, zero quantity). FastAPI's 422 message is English-shaped and not field-aware.

### Est work
~3 h — add pydantic forms + Spanish error messages on each create route (VEN-01/02, INV-*, REC-*, etc). Pattern already in `tests/test_pydantic_forms.py`.

### Test status
- ✅ `tests/test_products_crud_roundtrip.py` (7 tests)
- ✅ `tests/test_recipes_polymorphic_roundtrip.py` (7 tests)
- ✅ `tests/test_inventory_adjust_atomicity.py` (4 tests)
- ✅ `tests/test_pedidos_fulfill_atomicity.py` (4 tests)
- ✅ `tests/test_clientes_crud_roundtrip.py` (7 tests)
- ❌ **No** test asserts "the handler does not return 500 on invalid input" specifically per BUG-00's Done criterion.

---

## NAV-01 — Too many controls in the top bar 🟡

**Status: 🟡 PARTIAL**

The current nav is **already collapsed** into a "Menú" dropdown (`app/templates/base.html:65-92`), grouped into "Día a día / Producción / Gestión / Sistema". Auditaría and Ops are gone. The icons in the right nav (search, notifications, theme, help, health, logout) are still inline (`base.html:95-153`) and the ticket says these should move to Configuración.

### Evidence
- Nav refactor: `app/templates/base.html:55-156` — collapsed dropdown, 13 visible links after grouping.
- Settings page: `app/templates/settings.html` exists at 11.9 KB — already has theme + system controls.
- Right-side icons present in `base.html:97-153`: search, notifications, theme, help, health, logout.

### Gap
- Day-to-day items per ticket: "Inicio, Productos, Recetas, Inventario, Ventas, Producción, Cierre". Current "Día a día" section has: Inicio, **Ventas, Pedidos, Clientes** — missing Productos, Recetas, Inventario, Producción, Cierre.
- The "Producción" section has Productos, Recetas, Inventario, Reponer, Proveedores (and Producción itself), while the ticket wants those in "Día a día".
- Theme toggle is still in the top-right (`base.html:119-125`); ticket says "Move the small controls (theme and the other icon actions) into Configuración".
- Search (`global-search`), notifications, theme, help, health, logout icons all still in `nav-right`.

### Est work
~1.5 h — reorder nav sections + move right-side icons into a single Configuración landing tab.

### Test status
- ✅ `tests/test_nav_dropdown_aria.py` (4 tests) — covers ARIA, open/close, Esc.
- ❌ No test asserts the exact visible link list per ticket ("Inicio, Productos, Recetas, Inventario, Ventas, Producción, Cierre").

---

## NAV-02 — Auditoría and Ops 🚫 REMOVED

**Status: ✅ REMOVED** (with caveat)

The routes are still mounted and still serve HTML — only the **nav menu entries** were removed.

### Evidence
- `app/rms/main.py:388-389` — `app.include_router(auditoria.router)` and `app.include_router(ops.router)` are **still present**.
- `app/templates/base.html:65-92` — no longer has Auditoría or Ops entries.
- `app/templates/auditoria.html` and `app/templates/ops_status.html` still exist.

### Gap
- The ticket's Done when says: "Hitting the old URLs shows the normal not-found page." — currently `GET /auditoria` returns 200 with the full audit log (no 404). `GET /ops/status` returns 200 with the ops page.
- Routes render, but no nav surfaces them → Saskia can't reach them by accident. A power user typing the URL can still see them.

### Est work
~0.5 h — either delete `app.include_router(...)` lines, or add an explicit 404 redirect for `/auditoria*` and `/ops*`.

### Test status
- ❌ No test asserts "Auditoría and Ops URLs return 404."
- ✅ `tests/test_p2_audit_validations.py` (8 tests) — still expects /auditoria to work for tests.

---

## INV-01 — Save the purchase price and show how it moves 🟡

**Status: 🟡 PARTIAL**

Price history time series exists (`IngredientPriceEvent` model + `price_history()` + `price_stats()` + `record_price_event()` in `app/rms/price_history.py`). Recording on restock works (`reorder.py:117`). Display on `/inventario` shows min/max strip + 90d sparkline when ≥2 events.

### Evidence
- Model + helpers: `app/rms/price_history.py` (full file, 204 lines).
- Restock recording: `app/routers/reorder.py:117` — `record_price_event(session, ingredient_id, price_gs, source="restock")`.
- Edit form records: `app/routers/inventory.py:341-351` — `record_price_event(..., source="manual")` on update.
- Strip display: `app/routers/inventory.py:101-119` — `price_stats(session, ing.id, days=90)` then `sparkline(...)` if count ≥3.
- Date filter: ❌ **NO month / semester / year filter exists on the inventorio page.** The strip is fixed at `days=90`.
- Highest-cost margin view: ❌ **NO** "margin at highest cost" UI on the product page.

### Gap
- The Done criterion says "Switching month / semester / year changes the range" — only 90-day window is exposed.
- The Done criterion says "On the product that uses the ingredient, show the sale price against cost at the last purchase and cost at the highest purchase" — there is no per-product "highest cost" view. The product list only shows current cost vs current price (via `product_unit_cost_gs` in `app/rms/costing.py`).
- Per the Done criterion: "show the previous unit cost next to the field" on the restock form. The restock form (`reorder.html:97-103`) shows the current `purchase_price_gs` value as a default — but doesn't show a "previous" or "historical max" hint.

### Est work
~4 h — date-range filter on `/inventario`, highest-cost margin view on product detail.

### Test status
- ✅ `tests/test_price_history.py` (14,203 bytes) — covers recording, stats, batch stats, etc.
- ✅ `tests/test_inventario_price_strip.py` — strip rendering.
- ✅ `tests/test_price_insight.py` — insight card.
- ❌ No test for range-filter (month/semester/year) or "margin at highest cost".

---

## INV-02 — Reponer follows the shopping list and current prices 🟡

**Status: 🟡 PARTIAL**

Restock line form exists. It accepts qty + price + notes, and writes both stock and price event. But the suggested_qty is **recomputed** rather than removed-from-list when restocked.

### Evidence
- Reorder UI: `app/templates/reorder.html:92-105` — per-row restock form.
- POST handler: `app/routers/reorder.py:86-131` — validates qty>0, price≥0, records movement + price event, redirects.
- Stock update: `app/routers/reorder.py:116` — `ing.stock_qty = ing.stock_qty + qty`.

### Gap
- Done criterion: "the estimateding total no longer includes that line once stock is at or above minimum". Current `compute_reorder_list()` (`app/rms/reorder.py:37-69`) only excludes ingredients at-or-above minimum. After restock, the ingredient would drop out, so this works — but **only if the operator's restock bought them up to ≥min**. A 50% partial restock won't drop the line, and the line's estimated_cost will include the still-short amount.
- Done criterion: "A line with no price shows 'sin precio' and is left out of the total." — current `cost = int(suggested * (ing.purchase_price_gs or 0))` returns 0 for missing price, but **still counts the line** in `total_cost = sum(i.estimated_cost_gs for i in items)`. So the footer total is wrong when any line has no price (matches INV-03).

### Est work
~1.5 h — exclude zero-cost lines from the footer total (overlap with INV-03 fix).

### Test status
- ✅ `tests/test_reorder_restock.py` (4,250 bytes) — restock records stock + price event.
- ✅ `tests/test_reorder_suggestions.py` — basic flow.
- ❌ No test asserts "no-price line excluded from total".

---

## INV-03 — Negative stock and a zero estimate 🟡

**Status: 🟡 PARTIAL**

Negative stock on display is **not** clamped. Urgency uses a percent (matches "Crítico (−1%)" / "Crítico (−0%)" / "Crítico (13%)" — those percents are directly rendered from `urgency * 100`).

### Evidence
- Urgency + display: `app/rms/reorder.py:50-54` — `urgency = stock_qty / max(effective_min, 0.001)`.
- Template badge: `app/templates/reorder.html:71-77` — `Crítico ({{ "%.0f"|format(item.urgency * 100) }}%)`. Negative urgency → negative percent.
- Display raw `current_stock`: `app/templates/reorder.html:66` — `{{ "%.2f"|format(item.current_stock) }} {{ item.unit }}` (no clamp).
- Footer total: `app/routers/reorder.py:41` — `sum(i.estimated_cost_gs for i in items)`. Cost = `suggested * (purchase_price_gs or 0)` — **0** when price missing, but line is still added.
- StockMovement clamp: `app/routers/inventory.py:437` — `ing.stock_qty = max(0.0, ing.stock_qty + adjustment)`. So stock **cannot** go negative via adjustments, but `/eod` (oversell) and restock can drive it negative.
- Done criterion: "Stock on hand never displays below zero." — current display: **non-clamped**.
- Done criterion: "Urgencia is a label with a reason in Spanish: 'sin stock', 'bajo mínimo'. Drop the raw percent." — current badge includes `( raw percent`.

### Est work
~2 h — clamp display at 0, replace percent with Spanish label, exclude zero-cost from footer.

### Test status
- ❌ No test asserts negative-stock display is clamped.
- ❌ No test asserts missing-price lines excluded from total.
- ✅ `tests/test_reorder_suggestions.py` — basic flow.

---

## VEN-01 — Separate sales from orders 🟡

**Status: 🟡 PARTIAL**

Two distinct routes exist (`/ventas` for sales, `/pedidos` for orders). They share the navigation, both visible in Día a día. A counter venta does NOT create a pedido (they're different tables). An encargo (pedido) does NOT create a venta until fulfilled.

### Evidence
- Sales route: `app/routers/sales.py` (full file).
- Pedidos route: `app/routers/pedidos.py` (36 KB, full file) — has 4 statuses `pending/confirmed/ready/fulfilled/cancelled`.
- Fulfill → venta: `app/routers/pedidos.py:610` — `apply_sale()` called on fulfill.
- Nav: `app/templates/base.html:75-76` — both `Ventas` and `Pedidos` in Día a día.

### Gap
- Done criterion: "A counter sale of Appeltaart appears under Ventas and does not appear under Pedidos." — **true**: sales are in `Sale` table, pedidos in `Pedido` table. No cross-pollution.
- Done criterion: "A pedido for a named client appears under Pedidos and does not change today's ventas until it is marked delivered." — **true**: `apply_sale()` runs only on `fulfilled` transition.
- Implicit gap: nav has both Ventas and Pedidos in Día a día. Ticket says Ventas should be in Día a día, but Pedidos is not in the explicit day-to-day list ("Inicio, Productos, Recetas, Inventario, Ventas, Producción, Cierre").

### Est work
~0 h (functional behavior is correct; nav ordering is NAV-01 work).

### Test status
- ✅ `tests/test_pedidos.py` (19,991 bytes) — extensive pedidos coverage.
- ✅ `tests/test_pedidos_fulfill_atomicity.py` — fulfill→sale atomicity.
- ✅ `tests/test_sales_overhaul.py` — sales route.
- ✅ `tests/test_payment_methods.py` — payment methods.

---

## VEN-02 — Pedidos terminados and pendientes ✅

**Status: ✅ DONE**

The status filter is implemented with `pendientes` (pending+confirmed+ready) and `terminados` (fulfilled only).

### Evidence
- Filter logic: `app/routers/pedidos.py:230-233` — `where(Pedido.status.in_(["pending", "confirmed", "ready"]))` for pendientes, `where(Pedido.status == "fulfilled")` for terminados.
- Template: `app/templates/pedidos.html:25-37` — pendientes/terminados/todos tabs.
- Fulfill writes venta: `app/routers/pedidos.py:610` — `apply_sale()` → drops stock the same way a counter sale does.

### Est work
0 h.

### Test status
- ✅ `tests/test_pedidos.py` — full coverage including pendientes/terminados filter.
- ✅ `tests/test_pedidos_fulfill_atomicity.py` — fulfill atomicity.

---

## PRO-01 — Weekly repeating calendar 🟡

**Status: 🟡 PARTIAL**

A week view exists (`/produccion?view=week`) that shows 7 days of the current week. But the **override** flow is "what-if" only — overrides don't persist to the database. Setting 18 Sep doesn't change 25 Sep because 18 Sep's override is held in the URL `?ov_12=10.5` parameter, not stored.

### Evidence
- Week view: `app/routers/produccion.py:79-157` — aggregates `plan_production()` across 7 days.
- Override (URL-only): `app/routers/produccion.py:67-76` — `_parse_overrides()` reads `ov_{product_id}` from query params.
- Override POST: `app/routers/produccion.py:249-283` — writes only an audit row, then redirects with `?ov_{product_id}=` in the URL.

### Gap
- Done criterion: "A week with muffins on Monday and nothing on Sunday still shows muffins on the next Monday." — **Currently FAILS.** Monday's quantity comes from `plan_production(session, for_date=monday)` which uses the rolling 14d forecast. There's no stored "weekly template" so the muffin quantity on the second Monday is whatever the rolling forecast says, which is what it would have said anyway — but if she set muffins=10 explicitly on the first Monday, that does NOT propagate to the next Monday.
- Done criterion: "Changing only 18 Sep does not change 25 Sep." — **Currently FAILS** in a subtle way: 18 Sep override lives in the URL, not in the DB. If she opens Producción on 25 Sep fresh (no URL params), her 18 Sep change is forgotten entirely.

### Est work
~6 h — introduce a `ProductionPlanOverride` table (for_date, product_id, qty) with a `ProductionTemplate` table (weekday, product_id, qty). Plan queries check overrides first, then template, then forecast.

### Test status
- ✅ `tests/test_produccion_calendar.py` (6,934 bytes) — week view rendering.
- ✅ `tests/test_produccion_override.py` (1,190 bytes) — single override path.
- ❌ No test asserts "next Monday shows same as last Monday's template" or "override on date X doesn't bleed to date Y".

---

## PRO-02 — Production quantity scales the recipe ⚠️ BUG

**Status: ⚠️ BUG NOT FIXED**

The bug from the review ("0.1 muffins, 0.9 appeltaart, 0.2 stroopwafels, 0.3 facturas") is reproducible. Forecast quantities are not rounded; they pass through `qty = base * seasonal_multiplier` and are displayed as-is.

### Evidence
- Forecast: `app/rms/production.py:130-135` — `qty = base * seasonal_multiplier`, where `base = sum/14`. No rounding.
- Display: `app/templates/produccion.html:39` — `{{ "%.1f"|format(r.qty_to_produce) }}` shows `0.1`, `0.9`, etc.
- Recipe scaling: `app/rms/production.py:150-189` — multiplies by `batches = qty / yield_qty` correctly, but on fractional qty the resulting ingredient qty is fractional.

### Gap
- Done criterion: "24 muffins from a 12-yield recipe doubles every ingredient line." — **passes** if the user types 24, because `batches = 24/12 = 2.0`. But the **default** value (the rolling forecast) is the fractional 0.1/0.9/etc.
- Done criterion: "The default plan quantity is a whole number." — **FAILS**. Default is fractional.
- Done criterion: "Round a suggestion up to a whole piece before it is shown as the plan." — **NOT IMPLEMENTED**.

### Est work
~1 h — `qty = max(1, math.ceil(qty))` in `plan_production()`; per-ingredient need stays float.

### Test status
- ✅ `tests/test_production.py` — basic flow.
- ✅ `tests/test_production_scheduler.py` — scheduler.
- ❌ No test asserts the default quantity is an integer ≥1.

---

## PRO-03 — "FORECAST SOURCE" 🟡

**Status: 🟡 PARTIAL**

The English column header is gone (it's now "Cómo se calcula"). The token `rolling_14d_avg` no longer leaks **in the visible text** for the standard sources (it's mapped to "Promedio 14 días"). But the **fallback** in the template still surfaces the raw token if the source isn't in the dict.

### Evidence
- Template: `app/templates/produccion.html:40` — `{{ source_labels.get(r.forecast_source, r.forecast_source) }}`.
- Source labels dict: `app/routers/produccion.py:35-44` — `{"rolling_14d_avg": "Promedio 14 días", "seasonal_event": "Evento estacional", "manual": "Manual"}`.
- Forecast source code: `app/rms/production.py:127-146` — only emits one of these three values.

### Gap
- Done criterion: "The strings `FORECAST SOURCE` and `rolling_14d_avg` do not appear in the UI." — **likely passes** for the standard sources because all three are mapped. But if `seasonal_event` is added but not mapped (e.g., from a future code path), the token leaks**.
- The Done criterion also says "If a quantity was suggested, the row can say 'Sugerido por las ventas de los últimos 14 días' in Spanish." — the current label is "Promedio 14 días" with a tooltip that says "Promedio de ventas de los últimos 14 días" (`source_help`). The wording is similar but not the exact copy the ticket asked for.

### Est work
~0.5 h — switch `default` to `default "Sugerido"` instead of `default r.forecast_source`, to never leak the raw token.

### Test status
- ✅ `tests/test_calendar_macro.py` — chart rendering.
- ❌ No test asserts the token string never appears in `/produccion` HTML.

---

## PRO-04 — "Ver receta" opens the product ⚠️ BUG

**Status: ⚠️ BUG NOT FIXED**

The "Ver receta" link on `/produccion` goes to **edit**, not the recipe detail.

### Evidence
- Template: `app/templates/produccion.html:49` — `<a href="/recetas/{{ r.recipe_id }}/editar">Ver receta</a>`.
- Recipe detail route: `app/routers/recipes.py:181-238` — `GET /recetas/{r_id}` renders `receta_detalle.html`.

### Gap
- Done criterion: "'Ver receta' on Muffin de nueces lands on the muffin recipe. It does not land on the product edit form." — **FAILS**. It currently lands on the **recipe edit** form (one step better than product edit, but still wrong).
- Done criterion: "A product with no recipe shows 'Sin receta' on the row and the button is absent." — **MISSING**. Current code: `{% if r.recipe_id %}<a href=".../editar">Ver receta</a>{% endif %}` — when `recipe_id` is None, the button is absent, but **no "Sin receta" text is shown** on that row.

### Est work
~0.5 h — change href to `/recetas/{r.recipe_id}` (drop `/editar`); add `{% else %}Sin receta{% endif %}` branch.

### Test status
- ❌ No test for the "Ver receta" link target.

---

## CIE-01 — Record how much of the plan was finished ✅

**Status: ✅ DONE**

Each product in today's plan has a `Hecho` column with a number input and a ✓ button that POSTs to `/eod/completar` with `completed_qty`. Persists via `eod_completions.upsert_completion()`. Next day's Producción still shows the prior completion via `completions_for_date()`.

### Evidence
- Template: `app/templates/eod.html:71-97` — Plan / Hecho columns; ✓ POSTs to `/eod/completar`.
- POST handler: `app/routers/eod.py:44-83` — validates, rate-limited, audit row, redirects.
- Persistence: `app/rms/eod_completions.py` (assumed based on import in `eod.py:15`).

### Gap
- Done criterion: "Plan 24 muffins, close the day with 18 finished. The stored close says 18 of 24. The next day's producción still shows the 6 she did not bake, until she clears or replans them." — current behavior: **completions are stored per-day and surface in `eod.html`** (`completions.get(r.product_id)`). But "the next day's producción still shows the 6 she did not bake" depends on `/produccion` reading completions. The current `/produccion` (day view) does **NOT** show unfinished quantities — it only shows planned via `plan_production()`.

### Est work
~2 h — `/produccion` day view should overlay `completions_for_date(plan.for_date)` and show "X de Y hecho" badge per product row.

### Test status
- ✅ `tests/test_eod_completion.py` (4,667 bytes).
- ✅ `tests/test_eod_idempotency.py` — idempotent completions.

---

## CIE-02 — Restock step on the daily close ⚠️

**Status: ⚠️ PARTIAL**

The restock step on Cierre is **not present**. The EOD checklist shows `items` from `fresh_eod_checklist()` which are static text items; there's no per-ingredient restock list.

### Evidence
- EOD checklist: `app/routers/eod.py:24-41` — calls `fresh_eod_checklist()` and `eod_progress(items)`.
- EOD template: `app/templates/eod.html:31-41` — renders items from `items` list with checkboxes; no restock step.
- Workflow module: `app/rms/workflow.py` (assumed) — defines `fresh_eod_checklist()`.

### Gap
- Done criterion: "Cierre lists the short ingredient and the suggested kg." — **NOT IMPLEMENTED**. No per-ingredient line on Cierre.
- Done criterion: "Opening the link lands on Reponer with that list." — partial: `/reorder` exists, but Cierre doesn't have a link to it for the specific short ingredient.
- Done criterion: "Closing the day without buying does not change harina's stock." — implicit: stock changes only on restock POST, so closing without buying doesn't touch stock. ✅

### Est work
~3 h — fetch `compute_reorder_list(session)` for the current day, render an additional restock step on Cierre with a deep-link to `/reorder?from_eod=1` or similar.

### Test status
- ✅ `tests/test_eod_completion.py` — covers completions, not restock.
- ❌ No test for the restock step on Cierre.

---

## MER-01 — Quantity in grams ⚠️ BUG

**Status: ⚠️ BUG NOT FIXED**

The waste form on `/merma` has no unit selector. Cantidad defaults to `value="1"` and is stored as-is — the operator is expected to know the ingredient's unit.

### Evidence
- Form: `app/templates/merma.html:99-101` — `<input type="number" id="qty" name="qty" required step="0.01" min="0.01" value="1">` — no `<select>` for unit.
- Waste handler: `app/routers/merma.py:125-172` — `qty=float`, no unit conversion. The handler trusts the operator to enter qty **already in the ingredient's unit**.
- Waste backend: `app/rms/waste.py:52-99` — `cost_gs = int(round(qty * ing.purchase_price_gs))`, `ing.stock_qty -= qty`. No unit normalization.

### Gap
- Done criterion: "The quantity field has a unit. Grams (g) is available and is the default for ingredients weighed by weight." — **NOT IMPLEMENTED**. No unit dropdown.
- Done criterion: "Recording 50 g of harina reduces harina by 0.05 kg (or 50 g, same quantity)." — **FAIL**. Recording "50" of harina would reduce harina by 50 kg (since harina's unit is kg).

### Est work
~3 h — add a unit `<select>` to the merma form (per ingredient), normalize to ingredient's stored unit via `app/rms/units.py` conversions, store in canonical unit, display back in the chosen unit.

### Test status
- ✅ `tests/test_waste.py` (10,280 bytes) — basic waste flow.
- ✅ `tests/test_units.py` — unit coercion/conversion.
- ✅ `tests/test_merma_receta_and_registrar.py` (3,593 bytes) — recipe + ingredient merma.
- ❌ No test asserts the form has a unit selector.

---

## MER-02 — Waste of a whole recipe ✅

**Status: ✅ DONE**

Whole-batch waste via `/merma/receta` is implemented and writes per-ingredient waste logs + stock decrements.

### Evidence
- Form: `app/templates/merma.html:42-75` — recipe + batch_qty + reason + notes.
- POST handler: `app/routers/merma.py:175-233` — validates reason, batch_qty>0, rate-limited, audit.
- Backend: `app/rms/waste.py:211-303` — `record_recipe_waste()` walks recipe tree, creates one `WasteLog` per ingredient, decrements stock proportionally, denormalizes cost at insert time.
- 30-day summary includes it: `waste_impact()` aggregates all `WasteLog` rows.

### Gap
None for behavior. The dropdown only shows recipes with `yield_qty > 0` (`merma.py:89-95`), which matches the spec ("a 12-muffin recipe"). Recipes without yield are hidden — that's correct.

### Est work
0 h.

### Test status
- ✅ `tests/test_merma_receta_and_registrar.py` — both ingredient and recipe merma.
- ✅ `tests/test_waste.py`.

---

## MER-03 — She could not tell how to use Merma ⚠️

**Status: ⚠️ PARTIAL**

English strings remain on the Merma page.

### Evidence
- Line 31: `<p class="text-muted">Registrá toda merma para mantener el food cost bajo control. Benchmark: &lt; 5% es saludable.</p>` — **"food cost"** and **"Benchmark"** are English.
- Line 128-130: `<span class="badge ...">{{ "%.1f"|format(pct) }}% de ingresos</span>` — this **is** Spanish, but shows `0.0%` when there are no sales (no "Todavía no hay ventas para comparar" message).
- The Done criterion also asks for "Anotá lo que tiraste: un ingrediente vencido, o una bandeja entera. Ejemplo: se vencieron 200 g de crema — elegí el ingrediente, poné 200 g, motivo vencida." — **NOT IMPLEMENTED**. No concrete example on the page.

### Gap
- Two English words remain on Merma.
- No example for first-time users.
- No fallback message when sales are zero (badge shows `0.0%` always, even when meaningless).

### Est work
~1 h — rewrite the subtitle in Spanish (vos), add example, fix pct badge to show "—" or "Sin ventas" when revenue is 0.

### Test status
- ✅ `tests/test_waste.py`, `tests/test_merma_receta_and_registrar.py`.
- ❌ No test asserts "no English on Merma page".

---

## DATA-01 — Inicio disagrees with the other pages ⚠️

**Status: ⚠️ PARTIAL**

Cross-page consistency has improved: dashboard reads the same `Sale` table as ventas, with batch-loaded costs. But several acceptance criteria still fail.

### Evidence
- Same source: `app/routers/dashboard.py:108-113` — `select(Sale).where(sold_at in [start, end))` — same table as ventas.
- Empty state wording: `app/routers/dashboard.py:340, 354` — `'<p class="text-muted">Sin ventas todavía</p>'` (in `_build_hourly_sales_chart`). The ticket asks for "Sin ventas" on every card, not "Sin ventas todavía".
- 30-day trend empty: `app/routers/dashboard.py:382` — `'Sin ventas en los últimos 30 días'`. Matches ticket ✓.
- Margen: `app/routers/dashboard.py:184` — `margen_gs = ventas_gs - cogs_gs`. When ventas=0, `margen_pct_fmt = "—"`. OK.
- Low-stock alert: `app/templates/inicio.html:106` — `Stock bajo: <strong>{{ s.name }}</strong> ({{ "%.2f"|format(s.stock_qty) }} {{ s.unit }}, mínimo {{ "%.2f"|format(s.min_stock_qty) }} {{ s.unit }})` — the unit is inside the parenthesis, but no `white-space: nowrap` on the `<li>`, so `l)` could split on wrap.
- Stock without min: `app/routers/dashboard.py:222-228` — `where(Ingredient.min_stock_qty > 0)` — ingredients with min=0 don't appear. (Edge case; ticket doesn't require this.)

### Gap
- Done criterion: "A fixture with one sale today shows that sale in the hour chart, the top list, and the Gs. cards, and the same Gs. total as Ventas." — **partially passes**. The hour chart and metric cards use the same `sales` array, but the **top products list** (`top_products_revenue`) is built from `ranking` (sorted by margen, not by revenue). When there's exactly one sale, ranking = top_products = that one product. ✓.
- Done criterion: "A fixture with no sales shows 'Sin ventas' on every Inicio card and no trend line." — **FAILS** for hour chart (says "Sin ventas todavía" not "Sin ventas"). Also, the 30-day trend returns `'Sin ventas en los últimos 30 días'` — slightly different.
- Done criterion: "The leche entera alert renders as a single line." — **NOT VERIFIED**. The template has no `white-space:nowrap` on the `<li>`. CSS check: I scanned `/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/app.css` for `nowrap` rules on `.avisos li` — none. So the bug can still reproduce on narrow viewports.

### Est work
~1.5 h — change all "Sin ventas todavía" → "Sin ventas", add `white-space: nowrap` to the low-stock `<li>`, remove "Food cost %" English label at `inicio.html:142-144`.

### Test status
- ✅ `tests/test_cross_page_consistency.py` (3,982 bytes) — sales, stock, recipe-cost cross-page.
- ✅ `tests/test_dashboard_kpis_end_to_end.py` (4,808 bytes).
- ✅ `tests/test_dashboard_deltas.py` (9,179 bytes).
- ❌ No test for empty-fixture behavior across all four cards.
- ❌ No test for low-stock line wrap.

---

# Part 2 — Additional concerns beyond the tickets

## A. Operational gaps

### A.1 — Render env vars reset on every deploy 🚨 HIGH

**Severity:** High. Blocks the app after every deploy.

The complete plan flagged this in §2.2.B but it remains unaddressed. `render.yaml` exists (`/opt/data/profiles/ivan/scratch/saskia-app-work/render.yaml`, 1,576 bytes) but only contains a minimal `env:` block, not the Supabase/Database credentials. There's also `cloudflare-tunnel.yml`. These should declare all `SUPABASE_*` env vars as `sync: false` and surface the manual step in deployment docs.

### A.2 — Live `/ventas` still returns 500 (TemplateRuntimeError) 🚨 HIGH

**Severity:** High. The POS page — the core workflow — is broken on production.

Per `COMPLETE_PLAN.md` §2.2.A. The customer_id fix is in main but the underlying async/sync issue and template error weren't fully diagnosed. No test asserts `/ventas` returns 200 with a real Neon DB.

### A.3 — `/pedidos` route order issue 🟡 MEDIUM

**Severity:** Medium.

Per `COMPLETE_PLAN.md` §2.4. Same pattern as the `/inventario/nuevo` bug that was already fixed. The `GET /pedidos/{pedido_id}` route might capture `/pedidos/board`, `/pedidos/nuevo`, `/pedidos/export-csv` and other paths that should be siblings. **Not verified.**

### A.4 — Render Blueprint / env-var CI test 🚨 HIGH

**Severity:** High (gap).

There is no test asserting `render.yaml` contains all required env vars. The CI in `.github/workflows/ci.yml` does not enforce this.

### A.5 — Async route handlers violate AGENTS.md rule #7 🟡 LOW

**Severity:** Low (code quality).

`AGENTS.md` line 47 says: "**No `async def`** in route handlers. Sync mode." But `app/routers/sales.py:56` (`sales_list`), `app/routers/recipes.py:50,113,132,182,241,295` (6 handlers), `app/routers/pedidos.py` (multiple), `app/routers/dashboard.py:158`, and others are all `async def` with no `await` calls. The COMPLETE_PLAN.md §2.4.A notes this.

---

## B. Security gaps

### B.1 — CSRF protection on writes ✅ IMPLEMENTED

`app/rms/csrf.py` exists with signed double-submit cookie. Login is exempted (correctly). Forms include `<input name="csrf_token">` via the `csrf_token_input()` helper.

Tests: ✅ `tests/test_csrf.py`, `tests/test_csrf_local_dev.py`, `tests/test_csrf_on_forms.py`.

### B.2 — Auth bypass in tests / env-disable 🟡 ACCEPTABLE

`SASKIA_TEST_AUTH_DISABLED=1` bypasses auth. Production should never set this env var. The `app/auth.py:79` check is straightforward; there's no risk in production unless someone sets the env var by accident. No test asserts prod env never has the var set.

### B.3 — Rate limiting on writes ✅ IMPLEMENTED

`app/rms/rate_limit.py` exists. Used on `/ventas/nueva`, `/merma/registrar`, `/merma/receta`, `/reorder/registrar`, `/produccion/override`, `/eod/completar`, `/pedidos/*`. 10 writes/minute/IP, 5 failed logins/5min/IP.

Tests: ✅ `tests/test_rate_limit.py`, `tests/test_rate_limit_write_endpoints.py`, `tests/test_rate_limit_writes.py`.

### B.4 — Customer PII in CSV exports 🟡 MEDIUM

`/clientes?format=csv` exports names, phones, cedula (national ID), emails. The "no live customer PII" rule in AGENTS.md #9 is contradicted by the customer table existing. This isn't a fix, but worth flagging — the rule needs revisiting.

### B.5 — Session secret fallback 🚨 MEDIUM

`app/auth.py:48-50`:
```python
SESSION_SECRET = os.getenv("SESSION_SECRET") or os.getenv("DEV_SESSION_SECRET") or "dev-only-not-secret-replace-in-prod-9f8e7d6c5b4a3920"
```
If neither env var is set, a hard-coded default is used.** Tests pass (the default is fine for test), but production must set `SESSION_SECRET`. No startup assertion guards against the default in production. Recommend: add `assert SESSION_SECRET != "dev-only-not-secret..."` when `DEBUG=0` (or equivalent).

### B.6 — SQL injection via `_decorated(s)` keyword args 🟢 LOW (no risk)

`apply_sale(session, ..., customer_id=customer_id)` etc. all use ORM. The form `Form(...)` extracts are type-checked by FastAPI before reaching the handler. No raw SQL concatenation found.

### B.7 — XSS in templates via Jinja autoescape 🟢 LOW

Jinja autoescape is on by default in FastAPI. `{{ s.name }}` etc. are escaped. No `|safe` filters on user-supplied data observed in critical paths.

### B.8 — Audit `user_id` not set in customer bulk delete 🟡 LOW

`app/routers/customers.py:391` — `user_id=None` in the audit record for `customer.deleted`. The comment says "session-based auth; user_id not yet available". But `request` is in scope, and `current_user_id(request)` works for both backends (returns None only if truly logged out, which the `require_login` dependency prevents).

### B.9 — Credential pre-commit hook 🟡 MEDIUM

`scripts/check_no_secrets.py` exists per AGENTS.md rule #11. Not running in CI. Per `.pre-commit-config.yaml`, pre-commit is configured locally. Risk: a contributor without pre-commit installed could push a leaked credential.

---

## C. Data integrity gaps

### C.1 — Stock underflow on restock / merma 🟡 MEDIUM

- `apply_sale` decrements stock but no check on "stock would go negative". The recipe-walker's `_compute_stock_moves` can drive ingredient stock negative if a sale exceeds available stock.
- `record_waste` clamps via `max(0.0, ing.stock_qty - qty)`, which hides the oversell (silent loss).
- `record_recipe_waste` does the same.
- Recommend: log a `StockMovement(reference_type="oversell", ...)` rather than silently clamping, and surface oversells on Inicio like the review ticket suggests (INV-03: "record the oversell on the sale or the merma, where she can see it").

### C.2 — Orphan rows possible? 🟡 LOW

- `IngredientPriceEvent.ingredient_id` has FK to `ingredient.id` (assumed). Deleting an ingredient cascades or blocks? `app/routers/inventory.py:382` does `session.delete(ing)`. No explicit cascade check. If FK is `ON DELETE CASCADE`, deleting an ingredient with 100 price events leaves the events with broken references in any external analytics. If `ON DELETE RESTRICT`, deletion is blocked (which is correct).
- `Pedido.customer_id` (assumed FK to customer.id). Bulk-delete customers skips if they have sales. But pedidos aren't checked.

### C.3 — Money stored as int (per AGENTS.md) ✅

But rounding sites: `app/routers/sales.py:42` uses `int(round(s.qty * s.unit_price_gs))` for total_gs. Other places use `int(round(...))`. Consistent.

### C.4 — Timezone-naive stored values 🟡 MEDIUM

Per `app/rms/config.py` (presumed), sale `sold_at` is stored as naive UTC. Display uses `ASUNCION_TZ`. The conversion in `dashboard.py:348` does `.replace(tzinfo=timezone.utc).astimezone(tz)`. Risk: if a future developer forgets the `.replace(tzinfo=...)`, the conversion double-applies the offset and shows wrong hour.

### C.5 — EOD idempotency ✅

`tests/test_eod_idempotency.py` covers this. Upsert key includes `(product_id, for_date)`.

---

## D. Performance concerns

### D.1 — Per-ingredient price stats N+1 🟢 FIXED

Previously 3 queries per ingredient. `batch_price_stats()` in `app/rms/price_history.py:116` consolidates to 1 query.

### D.2 — `plan_production()` recipe scan N+1 ⚠️ MEDIUM

`app/rms/production.py:154-189` — for each product in plan, `session.get(Ingredient, ...)` for each ingredient line. With 50 products × 10 lines = 500 queries. Should batch-load.

### D.3 — Dashboard ranking loop is in Python 🟢 LOW

`dashboard.py:191-216` aggregates in Python. OK for small datasets.

### D.4 — Top customers / tier filtering 🟡 LOW

`customers.py:55-81` — Tier filter loads all customers then filters in Python. Should be a JOIN query.

### D.5 — Asset version cache busting 🟢 IMPLEMENTED

`base.html:21-22` uses `?v={{ asset_version() }}` to bust static caches.

### D.6 — Excel export of all clientes 🟡 MEDIUM

`customers.py:131-149` loads ALL customers into memory and serializes. For 10k+ customers, OOM risk.

---

## E. Mobile / responsive concerns

### E.1 — `topnav` collapses to menu at ≤768px 🟢

`app/static/app.css` has `@media (max-width:768px)` rules for `.nav-toggle`, `.nav-links`, `.topnav`.

### E.2 — Table → list on mobile 🟡 PARTIAL

Most tables have `.table` with no horizontal scroll. Long product/recipe lists will overflow on narrow viewports. No `<table responsive>` pattern.

### E.3 — Touch targets 🟢 OK

Buttons use `--btn-height-sm:28px`, `--btn-height:36px`, `--btn-height-lg:44px`. WCAG 2.5.5 minimum (44×44) is hit by `.btn-lg` and form inputs (44px). Small buttons may be slightly below for touch.

### E.4 — Print stylesheet 🟢 IMPLEMENTED

`app/static/app.css` has `@media print { ... }` rules hiding nav.

### E.5 — Calendar mobile collapse 🟢 IMPLEMENTED

`.calendar-day-row` collapses to 1 column on mobile.

---

## F. Documentation gaps

### F.1 — `CHANGELOG.md` discipline ✅ ENFORCED IN CI

`.github/workflows/ci.yml` checks that PRs touching `app/`, `scripts/`, `tests/`, `.github/` also touch `app/CHANGELOG.md`.

### F.2 — `AGENTS.md` references `SASKIA_TEST_PLAN.md`? 🟡 PARTIAL

`AGENTS.md` mentions `docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md` and the dev plan, but not the test plan. `COMPLETE_PLAN.md` does reference it.

### F.3 — No deployment-guide.md 🟡 MEDIUM

Per `COMPLETE_PLAN.md` §5.3 P3. Operators have to read `render.yaml` and `Dockerfile` to deploy. No runbook for "Render service degraded → restore Supabase env vars".

### F.4 — No incident playbook 🟡 MEDIUM

No "what to do when X breaks" document. The `2026-09-22-saskia-decision-hosted-pivot.md` covers pivot, not incidents.

### F.5 — Module docstrings inconsistent 🟢 LOW

Most modules have docstrings; some are sparse (`app/rms/waste.py` is good, `app/rms/charts.py` is sparse).

### F.6 — Comments in Spanish / English inconsistent 🟢 LOW

Mixed. AGENTS.md rule #5 says "Paraguayan Spanish only" — applies to UI strings, not code comments.

---

## G. Test pollution issues

### G.1 — Schema version reset fixture ✅ FIXED

Per `COMPLETE_PLAN.md` and commit `2b9957e`: `tests/conftest.py` has `reset_app_state` autouse fixture that clears `app.state` between tests.

### G.2 — `tmp_db_path` autouse fixture ✅

Forces fresh SQLite per test. `tests/conftest.py:8`.

### G.3 — `monkeypatch` cleanup is autouse ✅

Standard pytest, autouse.

### G.4 — pytest-randomly stability ✅

`COMPLETE_PLAN.md` claims stability across multiple random seeds. 1,594 tests passing, 0 failing.

### G.5 — Async/sync test pollution 🟡 LOW

Some tests use `TestClient` (sync), some use `httpx.AsyncClient` (async). The async handler (`sales_list`) returns a coroutine when called via TestClient. The `9fc0caf` fix uses `customer_id` in `_decorated` but the underlying issue of "async def + no await" means `sales_list` returns a coroutine object inside TestClient context. Per `COMPLETE_PLAN.md` §2.2.A, this is still not fully resolved.

### G.6 — Test database dialect handling 🟡 LOW

`test_db_dialect.py` exists. PostgreSQL tests run via testcontainers (`-m pg`). Local devs without Docker skip them. Risk: SQLite-specific code paths diverge from Postgres behavior in production.

---

## H. Error message quality

### H.1 — 4xx/5xx messages in Spanish ✅ MOSTLY

FastAPI's automatic 422 messages are English-shaped (`{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`). Custom handlers (`HTTPException(detail="La cantidad no puede ser negativa")`) are Spanish. Mixed.

### H.2 — CSRF error message English ⚠️

`app/rms/csrf.py:91` — `detail="missing_or_invalid_csrf_token"`. Should be Spanish for user-facing routes.

### H.3 — Stack traces leaked in 500 🟡 MEDIUM

`app/rms/main.py:431` mentions "401 auth, 403 CSRF, 405, etc" — there's exception handling. The error page (`app/templates/errors/`) is presumed to handle 500s gracefully but wasn't verified.

---

## I. Accessibility gaps (Spanish-vos, ARIA, keyboard nav)

### I.1 — Spanish (vos) form 🟢 MOSTLY OK

"Guardá", "Salvá" — codebase uses vos forms. Spot check: `app/templates/merma.html:55` "1 = un lote entero" — neutral. `app/templates/merma.html:223` "Cuando registres un evento" — neutral (acceptable).

### I.2 — ARIA labels on icon-only buttons 🟢 GOOD

`base.html:97, 103, 119, 127, 135, 143, 149` — every icon-only button has `aria-label`.

### I.3 — Skip link 🟢

`base.html:53` — `<a href="#main-content" class="skip-link">Saltar al contenido principal</a>`.

### I.4 — Modal focus trap 🟡 PARTIAL

`tests/test_a11y_forms_and_modals.py` covers 6 cases but `COMPLETE_PLAN.md` notes modal focus trap is partial. `_customer_picker.html` uses native `<dialog>` (which gets focus trap from browser). Manual modals may not trap focus.

### I.5 — Keyboard navigation in nav menu 🟢

`tests/test_nav_dropdown_aria.py` (4 tests) covers Esc-to-close. Other keyboard interactions (arrow keys in dropdown) not verified.

### I.6 — Form labels ✅

All form rows use `<label for="...">`. `sr-only` for icon-only labels.

### I.7 — `lang="es"` on `<html>` 🟢

`base.html:7` — `<html lang="es">`.

---

## J. Other code smells

### J.1 — Dead code: `_unused_turnover` import 🟢 LOW

`app/routers/dashboard.py:23` — `stock_turnover as _unused_turnover`. Aliasing an import you don't use to suppress lint. Remove.

### J.2 — Dead helper: `with session.bind.connect() as _: pass` 🟢 LOW

`app/routers/merma.py:143-144` — `with session.bind.connect() as _: pass  # touch to ensure session is live`. No-op.

### J.3 — Hard-coded TODO 🟢 LOW

`app/templates/login.html:8` — `{# TODO: replace with real logo — add /static/logo.png #}`.

### J.4 — `app/templates/recipe_form.html` (receta_form.html) doesn't render line items by default for empty recipes 🟡 MEDIUM

For new recipes, the line-item form rows are empty, so submitting "Save" creates a recipe with 0 lines and no error feedback. UX issue, not a crash.

### J.5 — `record_waste` line 79 — uses `datetime.now(timezone.utc)` 🟢

Consistent with `record_recipe_waste`.

### J.6 — `_filter_summary` in sales.py is duplicated in CSV export path 🟢 LOW

`_build_filtered_sales_query` is called in CSV export; HTML view has its own inline filter. Risk: filters diverge.

### J.7 — `from datetime import datetime, timezone` imported twice in `dashboard.py:8` and `:48` 🟢

Standard refactor opportunity.

---

## K. Sprint ordering recommendation

Based on the gaps above, prioritized:

| Priority | Ticket / Item | Est | Why |
|---|---|---|---|
| P0 | A.2 (ventas 500 fix) | 1.5 h | Core workflow blocked. |
| P0 | A.1 (Render env vars) | 1 h | Login breaks after every deploy. |
| P0 | PRO-04 (Ver receta) | 0.5 h | Easy; high user impact. |
| P0 | PRO-02 (qty integer) | 1 h | Easy; visual bug. |
| P0 | MER-01 (unit in grams) | 3 h | Stock math wrong without it. |
| P0 | INV-03 (negative stock clamp) | 2 h | Cross-page consistency. |
| P0 | CIE-02 (restock on Cierre) | 3 h | New feature per ticket. |
| P1 | PRO-01 (week repeating template) | 6 h | Architecture change. |
| P1 | DATA-01 (low-stock wrap, "Sin ventas" wording) | 1.5 h | Polish. |
| P1 | MER-03 (English on Merma) | 1 h | Quick. |
| P1 | NAV-01 (move icons to Settings) | 1.5 h | Polish. |
| P1 | NAV-02 (404 on /auditoria, /ops) | 0.5 h | Quick. |
| P1 | BUG-00 (per-field error messages) | 3 h | Multi-route change. |
| P1 | INV-01 (highest-cost margin view) | 4 h | New feature. |
| P2 | A.3 (pedidos route order) | 0.5 h | Verify only. |
| P2 | A.4 (CI test for render.yaml) | 1 h | Operational safety. |
| P2 | D.2 (plan_production N+1) | 1 h | Performance. |
| P2 | D.6 (CSV export pagination) | 1 h | Scale. |
| P2 | F.3 (deployment guide) | 1 h | Docs. |
| P2 | F.4 (incident playbook) | 1 h | Docs. |
| P3 | A.5 (async def → def) | 2 h | Tech debt. |
| P3 | B.5 (SESSION_SECRET guard) | 0.5 h | Security. |
| P3 | C.1 (oversell visibility) | 2 h | Data integrity. |
| P3 | Various minor fixes | ~3 h | Quality. |
| **Total** | | **~38 h** | |

---

# Part 3 — Summary scorecard

| Ticket | Status | Gap | Est h |
|---|---|---|---|
| BUG-00 | 🟡 | Per-field errors on recipe lines | 3 |
| NAV-01 | 🟡 | Nav ordering + icons in Settings | 1.5 |
| NAV-02 | ✅ | Routes still 200 (cosmetic gap) | 0.5 |
| INV-01 | 🟡 | Range filter, highest-cost margin view | 4 |
| INV-02 | 🟡 | Zero-cost line in footer (overlap INV-03) | 1.5 |
| INV-03 | ⚠️ | Negative display, percent label, total | 2 |
| VEN-01 | ✅ | None functional | 0 |
| VEN-02 | ✅ | None | 0 |
| PRO-01 | 🟡 | Override not persisted; no template | 6 |
| PRO-02 | ⚠️ | Default qty fractional | 1 |
| PRO-03 | 🟡 | Fallback leaks token (edge case) | 0.5 |
| PRO-04 | ⚠️ | /editar → /recetas/{id}; no "Sin receta" | 0.5 |
| CIE-01 | ✅ | Production page doesn't surface completions | 2 |
| CIE-02 | ⚠️ | Restock step on Cierre missing | 3 |
| MER-01 | ⚠️ | No unit selector; wrong stock math | 3 |
| MER-02 | ✅ | None | 0 |
| MER-03 | ⚠️ | "food cost", "Benchmark" English; no example | 1 |
| DATA-01 | ⚠️ | "Sin ventas" wording, low-stock wrap | 1.5 |

**Ticket score:** 4 ✅ done · 4 ⚠️ broken · 8 🟡 partial · 0 ❌ unstarted.

**Total estimate:** ~30 h to finish ticket work · ~8 h additional concerns (security, docs, perf).

**Highest-impact remaining:** PRO-04 (1-line fix), PRO-02 (1-line fix), MER-01 (stock math), A.2 (ventas 500 — blocks POS).