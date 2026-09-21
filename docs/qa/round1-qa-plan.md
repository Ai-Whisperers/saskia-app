# QA Plan — Review Round 1 (Thu 18-sep 2026)

**Branch:** `feat/rms-fase1-review-round1` · **Author:** Hermes Agent (T9)
**Scope:** everything shipped in Phases A–D of the round-1 review (T1–T8, Q1, Q2, Q3).
**Method:** user stories → smoke checklist → regression map → end-to-end functionality
cases → gap closure. Automated coverage is referenced as `tests/<file>.py::<test>`
wherever it exists; everything else is marked **manual**.

Saskia's ask (her words): *"Crea y analiza todos los user cases y user stories y
crea pruebas de QA correspondientes, para smoke testing, regression testing,
functionality testing, etc"*. Quoted Spanish below is verbatim from her review;
the analysis around it is in English for the dev team.

---

## 1. User stories

One story per shipped feature. Acceptance criteria are pulled from the actual
implemented behavior on this branch (not from the original spec), so each AC is
verifiable against the code as merged.

### S1 — Recipe lines with per-line units (T1)

> **Como Saskia, quiero** especificar la unidad de cada línea de la receta
> (g/kg/ml/l/und) **para** pesar en gramos aunque el ingrediente se compre por
> kilo, sin que el costo salga mal.

Context: Saskia's complaint was that entering "500" for flour when the
ingredient is priced per kg produced a 1000× cost error.

**Acceptance criteria**
- AC1: Each recipe line stores its own `line_unit`; empty `line_unit` falls back
  to the ingredient's unit (legacy rows unaffected).
- AC2: Costing normalizes the line qty into the ingredient's unit before pricing
  (500 g of a kg-priced ingredient costs 0.5 × price, not 500 × price).
- AC3: Cross-family conversions (g → l, und → kg) are rejected and surface as
  "unidades incompatibles" in the recipe UI instead of crashing the cost walk.
- AC4: Production planning normalizes with the same rule, so the shopping list
  and the cost sheet agree.

**Automated coverage**
- `tests/test_recipe_polymorphic.py::test_recipe_line_stores_line_unit`
- `tests/test_recipe_polymorphic.py::test_recipe_line_defaults_line_unit_to_empty_string`
- `tests/test_recipe_polymorphic.py::test_costing_uses_line_unit_for_cross_unit_recipe`
- `tests/test_recipe_polymorphic.py::test_costing_same_unit_recipe_unchanged`
- `tests/test_units.py::test_normalize_recipe_line_qty_same_family` (+ floats/strings/zero variants)
- `tests/test_units.py::test_normalize_recipe_line_qty_cross_family_forbidden`
- `tests/test_units.py::test_unit_coerce_aliases`

**Manual check (2 min):** open `/recetas/{id}/editar`, set a line to `500 g`
against a kg ingredient, save, confirm the batch cost changes by the expected
half-kilo amount.

### S2 — Hidden auditoría/ops from topnav (T2)

> **Como Saskia, quiero** que Auditoría y Ops no aparezcan en el menú principal
> **para** que la pantalla tenga menos ruido y no toque cosas dedeveloper por
> accidente.

**Acceptance criteria**
- AC1: `/auditoria` and `/ops/status` links absent from the topnav on every page.
- AC2: Both routes still work via direct URL (admin escape hatch preserved).

**Automated coverage:** none directly (no test asserts nav-link absence). See
gap G1 in §3. **Manual check:** eyeball topnav on `/`; then visit both URLs
directly and confirm 200.

### S3 — Producción 'Ver receta' links to the recipe editor (T3)

> **Como Saskia, quiero** que 'Ver receta' en producción me lleve a la receta
> **para** editarla sin tener que buscarla en productos.

**Acceptance criteria**
- AC1: `/produccion` rows with a linked recipe show a 'Ver receta' button whose
  href is `/recetas/{recipe_id}/editar`.
- AC2: Products with no recipe show no button (no dead link).

**Automated coverage:** none (template href not asserted). Gap G2. **Manual
check:** hover the button on `/produccion`, confirm the target URL.

### S4 — Pedidos status filter (T4)

> **Como Saskia, quiero** filtrar pedidos por pendientes/terminados/todos
> **para** ver rápido qué me queda por entregar.

**Acceptance criteria**
- AC1: `?status_filter=pendientes|terminados|todos` scopes the list; default is
  `pendientes` (unchanged prior behavior).
- AC2: Pill row renders above the cards with the three Spanish labels.

**Automated coverage:** no dedicated tests landed in T4 (list scoping is
exercised indirectly by `tests/test_pedidos.py::test_pedidos_list_groups_by_recency`
and `::test_pedidos_list_excludes_fulfilled_past_due`). Gap G3. **Manual check:**
create a pedido, mark it `terminado`, confirm it disappears from 'Pendientes'
and appears under 'Terminados'.

### S5 — EOD production completion, Plan vs Hecho (T5)

> **Como Saskia, quiero** marcar cuánto producí realmente de lo planificado
> **para** ver el delta Plan vs Hecho al cierre del día.

**Acceptance criteria**
- AC1: `POST /eod/completar` upserts one completion row per (date, product);
  re-posting updates instead of duplicating.
- AC2: Negative qty → 400; unknown product → 404.
- AC3: `/eod` renders the completion in the 'Hecho' column with the delta.
- AC4: Migration v19 is idempotent.

**Automated coverage**
- `tests/test_eod_completion.py::test_upsert_creates_then_updates`
- `tests/test_eod_completion.py::test_upsert_rejects_negative`
- `tests/test_eod_completion.py::test_post_completar_route_creates_row`
- `tests/test_eod_completion.py::test_post_completar_rejects_negative_qty`
- `tests/test_eod_completion.py::test_post_completar_rejects_unknown_product`
- `tests/test_eod_completion.py::test_eod_view_shows_completion_in_hecho_column`
- `tests/test_eod_completion.py::test_migration_v19_idempotent`

### S6 — Whole-batch merma (T6)

> **Como Saskia, quiero** registrar la merma de una receta completa
> **para** descuentar todos los ingredientes de una sola vez cuando se
> arruina una hornada.

**Acceptance criteria**
- AC1: Recording recipe waste creates one waste log per ingredient line, scaled
  by the number of batches wasted.
- AC2: Unknown recipe / missing yield / zero batch are rejected.
- AC3: Stock never goes negative.

**Automated coverage**
- `tests/test_waste.py::test_record_recipe_waste_creates_one_log_per_ingredient`
- `tests/test_waste.py::test_record_recipe_waste_rejects_unknown_recipe`
- `tests/test_waste.py::test_record_recipe_waste_rejects_missing_yield`
- `tests/test_waste.py::test_record_recipe_waste_rejects_zero_batch`
- `tests/test_waste.py::test_stock_does_not_go_negative`

### S7 — Settings per-row forms (T7)

> **Como Saskia, quiero** formularios claros por fila en ajustes **para**
> cambiar un valor sin tocar los demás.

**Acceptance criteria**
- AC1: Each setting renders as its own labeled form (card list, not a wide table).
- AC2: Bounded choices render as a dropdown; free values as inputs.
- AC3: POST updates only the submitted key.

**Automated coverage**
- `tests/test_settings_ui.py::test_settings_index_loads`
- `tests/test_settings_ui.py::test_settings_lists_general_group`
- `tests/test_settings_ui.py::test_settings_post_updates_value`
- `tests/test_settings.py` (broader settings behavior)

### S8 — Cross-page consistency (T8)

> **Como Saskia, quiero** que los montos coincidan entre páginas **para**
> confurar los reportes. (Her words: *"Debe coincidir con los registros de las
> demás páginas"*.)

**Acceptance criteria**
- AC1: No raw `{:,.0f}` money formatting in templates — everything via the
  `m.gs` / `m.gs_full` macros (period thousands separator, Paraguay style).
- AC2: No US `mm/dd/yyyy` date formats on user-facing pages (dd/mm/yyyy only;
  ISO allowed only inside form input values).
- AC3: Daily-summary totals reconcile with direct Sale-table sums.

**Automated coverage**
- `tests/test_cross_page_consistency.py::test_no_raw_money_formatting_in_templates`
- `tests/test_cross_page_consistency.py::test_no_us_date_format_in_templates`
- `tests/test_cross_page_consistency.py::test_daily_totals_reconcile`

### S9 — Restock records price events (Q1 core)

> **Como Saskia, quiero** que cada vez que restockeo se cargue el precio
> **para** ver en los paneles cuánto estoy ganando realmente aunque los
> precios fluctúen. (Her words: *"cada vez que la clienta restockea tiene que
> cargar los precios, y así puede ver en los paneles de gestión cuánto está
> ganando realmente aunque los precios fluctúen"*.)

**Acceptance criteria**
- AC1: `POST /reorder/registrar` bumps stock AND appends an
  `IngredientPriceEvent` with `source='restock'`.
- AC2: The ingredient's denormalized `purchase_price_gs` updates to the new price.
- AC3: Validation: qty ≤ 0 → 400, negative price → 400, unknown ingredient → 404.
- AC4: Rate limited to 10 writes/min → 429 (protects against double-submits).
- AC5: Manual price edits in `/inventario` also write events
  (`source='manual'`); no event when no price given.

**Automated coverage**
- `tests/test_reorder_restock.py::test_post_registrar_creates_price_event_and_increments_stock`
- `tests/test_reorder_restock.py::test_post_registrar_rejects_zero_qty` (+ negative qty/price, 404, rate-limit variants)
- `tests/test_reorder_restock.py::test_reorder_view_has_restock_form`
- `tests/test_price_history.py::test_inventory_create_writes_manual_price_event`
- `tests/test_price_history.py::test_inventory_update_writes_price_event_on_price_change`
- `tests/test_price_history.py::test_record_price_event_default_source_is_restock`

### S10 — /inventario price strip + sparkline (Q1 surface)

> **Como Saskia, quiero** ver el mínimo y máximo del precio de los últimos 90
> días bajo el precio **para** notar de un vistazo si el proveedor me está
> subiendo el precio.

**Acceptance criteria**
- AC1: ≥2 price events in the last 90 days → muted "90d: min X · max Y" strip
  under the price cell.
- AC2: ≥3 events → sparkline SVG rendered inline.
- AC3: 0–1 events → no strip, no sparkline.

**Automated coverage**
- `tests/test_inventario_price_strip.py::test_single_event_no_strip`
- `tests/test_inventario_price_strip.py::test_three_events_show_strip_and_sparkline`

### S11 — /reportes/precios + CSV export (Q1 surface)

> **Como Saskia, quiero** un reporte de precios por ingrediente con
> exportación **para** llevarlo a Excel y negociar con proveedores.

**Acceptance criteria**
- AC1: `/reportes/precios` lists ingredients with stats (current, min/max/avg).
- AC2: `/reportes/precios/{id}` detail has chart + event list; unknown id → 404.
- AC3: `/reportes/precios/csv` streams a CSV with headers + one row per event;
  `days` param validated (365 max OK, garbage rejected).

**Automated coverage**
- `tests/test_reportes_precios.py::test_list_view_200_shows_stats`
- `tests/test_reportes_precios.py::test_detail_view_200_has_chart_and_events`
- `tests/test_reportes_precios.py::test_detail_view_unknown_ingredient_404`
- `tests/test_reportes_precios.py::test_csv_export_headers_and_rows`
- `tests/test_reportes_precios.py::test_days_param_validated`
- `tests/test_reportes_precios.py::test_days_365_ok`

### S12 — Dashboard 'Precios en alza' insight (Q1 surface)

> **Como Saskia, quiero** que el panel me avise cuando un ingrediente subió más
> de 20% **para** repreciar mis productos antes de perder plata.

**Acceptance criteria**
- AC1: Ingredients whose current price is >20% above their 30-day average appear
  in the insight card, sorted by % above average.
- AC2: Stable ingredients (<20%) never appear.
- AC3: Empty DB → no card, no error.
- AC4: The dashboard only renders the card when at least one ingredient crosses.

**Automated coverage**
- `tests/test_price_insight.py::test_rising_ingredient_appears_in_insight`
- `tests/test_price_insight.py::test_stable_ingredient_not_flagged`
- `tests/test_price_insight.py::test_empty_db_no_card_no_error`
- `tests/test_price_insight.py::test_dashboard_shows_card_only_when_crossing`

### S13 — Production calendar day/week/month (Q2)

> **Como Saskia, quiero** un calendario cíclico por semana (y mes)
> **para** planear la producción de la semana entera. (Her words: *"Haz que
> sea un calendario cíclico, por semana"*.)

**Acceptance criteria**
- AC1: `/produccion` defaults to day view (backward compat); `?view=week`
  renders a Lun–Dom 7-cell grid with per-day product counts and prev/next nav;
  `?view=month` renders the correct day count for the month.
- AC2: View switcher (Día/Semana/Mes) present in all three modes.
- AC3: Week/month grids mark today and the selected day, weekday header in
  Spanish, empty state copy in vos.

**Automated coverage**
- `tests/test_produccion_calendar.py::test_day_view_backward_compat`
- `tests/test_produccion_calendar.py::test_week_view_renders_seven_cells`
- `tests/test_produccion_calendar.py::test_month_view_renders_day_count`
- `tests/test_produccion_calendar.py::test_view_switcher_present`
- `tests/test_calendar_macro.py::test_week_grid_macro_renders_seven_cells` (+ nav, empty state, today/selected marks)
- `tests/test_calendar_macro.py::test_month_grid_renders_correct_day_count` (+ nav, weekday header, empty state)
- `tests/test_calendar_macro.py::test_calendar_copy_is_spanish_vos`
- `tests/test_calendar_macro.py::test_calendar_uses_7_col_grid`

### S14 — Portions/yield scaling — THE multiplication bug (Q2)

> **Como Saskia, quiero** que al introducir la cantidad a producir la receta
> se multiplique por la cantidad correcta **para** que la lista de compras no
> salga 12 veces más grande. (Her words: *"al introducir la cantidad que se va
> a producir e ingresar en la receta debe de estar multiplicado por la
> cantidad correcta"*.)

**Acceptance criteria**
- AC1: Recipe lines are per BATCH; producing N portions of a recipe with
  `yield_qty` Y consumes `(N / Y) × line.qty` per ingredient.
- AC2: Requirements scale linearly with the forecast (2× forecast → 2× flour).
- AC3: The inline 'Usar' override re-plans with the manual qty.

**Automated coverage**
- `tests/test_produccion_calendar.py::test_production_math_multiplication`
- `tests/test_produccion_calendar.py::test_override_re_renders_with_manual_qty`
- `tests/test_produccion_calendar.py::test_override_rejects_negative` (+ unknown product)
- `tests/test_production.py::test_plan_production_computes_lines_from_recipes`

### S15 — forecast_source Spanish labels (Q3)

> **Como Saskia, quiero** saber de dónde sale el número previsto **para**
> confiar en el plan. (Her complaint: raw `rolling_14d_avg` in the UI.)

**Acceptance criteria**
- AC1: `/produccion` renders 'Promedio 14 días' / 'Manual' (never the raw
  English keys) with a 'Cómo se calcula' header.

**Automated coverage**
- `tests/test_produccion_calendar.py::test_forecast_source_labels_in_spanish`

### S16 — Single-operator baseline (standing acceptance criteria)

Every page ships Spanish-vos copy, `Gs.` money format with period thousands
separators, and int-Gs money math. Not one feature — the contract the whole
round must not regress.

**Automated coverage**
- `tests/test_ui_smoke.py::test_every_page_returns_200` / `::test_every_page_uses_spanish_copy`
- `tests/test_ui_smoke.py::test_money_format_in_inventory_page` / `::test_money_format_in_products_page`
- `tests/test_money.py`, `tests/test_routes.py::test_inventory_vos_copy_present`

---

## 2. Smoke tests (deploy-blocking)

Run these after every deploy to hosted before declaring the release good. Each
is 200-or-bust; anything marked *manual* needs a human (browser) pass.

| # | Check | Automated coverage |
|---|-------|--------------------|
| 1 | `/healthz` returns 200 and DB check passes | `tests/test_healthz.py::test_healthz`, `::test_healthz_db` |
| 2 | `/` (dashboard) renders 200 with Spanish copy | `tests/test_ui_smoke.py::test_every_page_returns_200`, `tests/test_routes.py::test_dashboard_empty` |
| 3 | `/inventario` renders 200 | `tests/test_ui_smoke.py::test_every_page_returns_200` |
| 4 | `/recetas` renders 200 | `tests/test_ui_smoke.py::test_every_page_returns_200` |
| 5 | `/productos` renders 200 | `tests/test_ui_smoke.py::test_every_page_returns_200` |
| 6 | `/ventas` renders 200 | `tests/test_ui_smoke.py::test_every_page_returns_200` |
| 7 | `/produccion` renders day view 200 | `tests/test_produccion_calendar.py::test_day_view_backward_compat` |
| 8 | `/produccion?view=week` and `?view=month` render 200 | `tests/test_produccion_calendar.py::test_week_view_renders_seven_cells`, `::test_month_view_renders_day_count` |
| 9 | `/eod` renders 200 with Plan vs Hecho columns | `tests/test_eod_completion.py::test_eod_view_shows_completion_in_hecho_column` |
| 10 | `/pedidos` renders 200, default filter = pendientes | `tests/test_pedidos.py::test_pedidos_list_groups_by_recency` (partial — filter default itself: manual) |
| 11 | A sale records and drops stock | `tests/test_routes.py::test_sale_create_drops_stock` |
| 12 | A restock records (stock + price event) | `tests/test_reorder_restock.py::test_post_registrar_creates_price_event_and_increments_stock` |
| 13 | `/reportes/precios` + `/reportes/precios/csv` return 200 | `tests/test_reportes_precios.py::test_list_view_200_shows_stats`, `::test_csv_export_headers_and_rows` |
| 14 | Login page renders and auth gate blocks unauthenticated writes | `tests/test_auth_gate.py`, `tests/test_auth.py` |
| 15 | Money renders `Gs. N.NNN.NNN` (no comma thousands) on `/inventario` and `/productos` | `tests/test_ui_smoke.py::test_money_format_in_inventory_page` |
| 16 | No JS/console errors on `/`, `/produccion`, `/inventario` (browser) | **manual** |
| 17 | 'Precios en alza' card absent on a calm DB (no false alarm on fresh deploy) | `tests/test_price_insight.py::test_dashboard_shows_card_only_when_crossing` |

Bare-metal version: `.venv/Scripts/python -m pytest tests/test_healthz.py
tests/test_ui_smoke.py tests/test_routes.py tests/test_produccion_calendar.py
tests/test_reorder_restock.py tests/test_eod_completion.py
tests/test_reportes_precios.py tests/test_price_insight.py -q` — all green
required before promoted to "deployed".

---

## 3. Regression suite map

| Risk area | Covering tests | Gaps |
|---|---|---|
| Units + recipe-line normalization (T1) | `test_units.py` (13), `test_recipe_polymorphic.py` (line-unit ×4, polymorphic ×5) | No test that the *same* mixed-unit recipe yields consistent numbers through costing AND `plan_production` in one pass (see §4 case 1 / gap G5) |
| Costing engine | `test_costing.py` (19: sub-recipes, cycles, missing price/yield, margins, N+1 batch) | — |
| Production planning + scaling bug (Q2) | `test_production.py` (9), `test_produccion_calendar.py` (9), `test_production_scheduler.py`, `test_production_session_safety.py` | Seasonal-multiplier editor untested — blocked by T-0.1 (not shipped) |
| Calendar macros (Q2) | `test_calendar_macro.py` (10) | Macro tests are Jinja-level; no screenshot/visual check — acceptable |
| EOD completion (T5) | `test_eod_completion.py` (7) | — |
| Merma (T6) | `test_waste.py` (17) | — |
| Pedidos lifecycle | `test_pedidos.py` (17) | `status_filter` param untested directly (G3); 'Ver receta' href untested (G2) |
| Restock + price history (Q1) | `test_reorder_restock.py` (7), `test_price_history.py` (16) | Pieces tested in isolation; no single test drives restock → event → insight card end-to-end (G4 — **closed this round**, see §6) |
| Price surfaces (Q1) | `test_inventario_price_strip.py` (2), `test_reportes_precios.py` (6), `test_price_insight.py` (4) | CSV reimport-in-Excel is inherently manual (§4 case 7) |
| Cross-page consistency (T8) | `test_cross_page_consistency.py` (3) | Reconciliation covers daily totals; monthly reportes not reconciled (low risk, same code path) |
| Settings (T7) | `test_settings_ui.py` (3), `test_settings.py` | Dropdown rendering per bounded choice is cosmetic — manual |
| Nav/a11y baseline | `test_a11y_navigation.py` (9) | Nav *absence* of auditoría/ops links not asserted (G1) |
| Smoke/routes | `test_ui_smoke.py`, `test_routes.py` | — |
| Money/i18n contract | `test_money.py`, `test_cross_page_consistency.py` | — |

### Known issues — 17 pre-existing environment failures

The suite carries **17 failures that pre-date this branch** (Windows path
assumptions, env-var-dependent Postgres/R2 cases, and one timezone-sensitive
public-pickup test). They are NOT regressions from round 1 — verified during
Phase A by stashing and re-running on main.

**Recommendation (decision is K.W.'s):** quarantine, don't fix in this round.
Add a `pytest.mark.env` marker + a CI deselect
(`-m "not env"`), keep them running in the nightly full job where Linux + the
real service env exist. Fixing 17 Windows-path/env tests inside the review
round would burn billable hours that round 2 triage
(`docs/operations/round-2-triage-process.md`) should prioritize instead. If any
of the 17 touches a flow Saskia uses daily, promote it out of quarantine
individually.

### Open gap register

- **G1** — no test that auditoría/ops links are absent from topnav (S2/AC1). Cheap template assert.
- **G2** — no test that 'Ver receta' href targets `/recetas/{id}/editar` (S3/AC1). Cheap template assert.
- **G3** — `?status_filter=` scoping on `/pedidos` untested directly (S4). Cheap client test.
- **G4** — restock → price event → strip/report/insight end-to-end chain untested. **CLOSED in this round** by `tests/test_qa_round1_user_journeys.py` (commit 2 of T9).
- **G5** — mixed-unit recipe → costing → plan consistency in one journey. **PARTIALLY CLOSED** by `tests/test_qa_round1_user_journeys.py::test_mixed_unit_recipe_costs_and_plans_consistently` (same file).
- **G6** — CSV → Excel reimport: manual by nature (correct headers/rows asserted; Excel-side is human).

---

## 4. Functionality test cases (the "user cases")

Given/When/Then scenarios over the real bakery flows. Coverage status is
against the automated suite on this branch *after* T9's gap closure.

### UC1 — Receta con unidades mixtas → costo correcto

- **Given** harina stored in `kg` at Gs. 5.000/kg and leche stored in `l` at
  Gs. 8.000/l, and a recipe "Pan" with line A = `500 g` harina and
  line B = `250 ml` leche, yield 12 und.
- **When** the recipe's batch cost is computed and the product's production is
  planned for 24 portions.
- **Then** batch cost = 0.5×5.000 + 0.25×8.000 = Gs. 4.500, and the plan
  requires 1.0 kg harina and 0.5 l leche (2 batches × normalized line qty).
- **Status: PARTIALLY COVERED → COVERED (this round).** Normalization:
  `test_units.py`; costing with line_unit:
  `test_recipe_polymorphic.py::test_costing_uses_line_unit_for_cross_unit_recipe`;
  plan scaling: `test_produccion_calendar.py::test_production_math_multiplication`.
  The one-journey consistency test is
  `test_qa_round1_user_journeys.py::test_mixed_unit_recipe_costs_and_plans_consistently`.

### UC2 — Planificador semanal → clic día → override qty → matemática de ingredientes

- **Given** a product with recipe (yield 12) and 5 days of sales history.
- **When** Saskia opens `/produccion?view=week`, and POSTs
  `/produccion/override` with qty 10 for one day.
- **Then** the day re-renders with 'Manual' as forecast source and ingredient
  lines = (10/12) × per-batch qty; negative qty → 400, unknown product → 404.
- **Status: COVERED.** `test_produccion_calendar.py::test_week_view_renders_seven_cells`,
  `::test_override_re_renders_with_manual_qty`, `::test_override_rejects_negative`,
  `::test_override_rejects_unknown_product`, `::test_production_math_multiplication`.

### UC3 — Restock con precio nuevo → evento de precio → insight 'Precios en alza' al cruzar 20%

- **Given** harina below min stock, current price events averaging Gs. 5.000.
- **When** Saskia restocks three times via `POST /reorder/registrar` at rising
  prices that push the current price >20% over the 30-day average.
- **Then** stock increments, three `source='restock'` events exist, the
  ingredient's price is denormalized, `/inventario` shows the 90d strip +
  sparkline, `/reportes/precios` lists it, and `/` shows the 'Precios en alza'
  card with the ingredient name and a `+N%` badge.
- **Status: WAS NOT COVERED END-TO-END → COVERED (this round)** by
  `test_qa_round1_user_journeys.py::test_restock_chain_price_event_to_insight_card`.
  Piecewise: `test_reorder_restock.py`, `test_inventario_price_strip.py`,
  `test_reportes_precios.py`, `test_price_insight.py`.

### UC4 — Merma de receta completa → stock drop proporcional

- **Given** a recipe with 2 ingredient lines and stock on hand.
- **When** Saskia records waste of 1.5 batches of the whole recipe.
- **Then** one waste log per ingredient appears, each line's stock drops by
  1.5 × per-batch qty, stock never goes negative, and unknown recipe /
  missing yield / zero batch are rejected.
- **Status: COVERED.** `test_waste.py::test_record_recipe_waste_creates_one_log_per_ingredient`
  and the reject/`::test_stock_does_not_go_negative` family. Note: the
  multi-batch *proportionality* constant (1.5×) is exercised inside the first
  test's assertions.

### UC5 — Cierre del día con completitud de producción

- **Given** a product planned for today via the production sheet.
- **When** Saskia POSTs `/eod/completar` with the actually-produced qty, then
  re-POSTs a corrected qty.
- **Then** one completion row exists (upsert, not duplicate), `/eod` shows
  Plan vs Hecho + delta, negative qty → 400, unknown product → 404.
- **Status: COVERED.** `test_eod_completion.py` (all 7 tests).

### UC6 — Pedido WhatsApp → marcar terminado → filtro

- **Given** a pending pedido created from a WhatsApp order.
- **When** Saskia fulfills it (or walks status pending → confirmed → ready →
  fulfilled) and switches `/pedidos?status_filter=terminados`.
- **Then** fulfillment creates the Sale rows and decrements stock, the pedido
  disappears from 'pendientes' and shows under 'terminados'.
- **Status: PARTIALLY COVERED.** Lifecycle + fulfillment:
  `test_pedidos.py::test_fulfill_creates_sales_and_decrements_stock`,
  `::test_status_transition_pending_to_confirmed_to_ready_to_fulfilled`. The
  `status_filter` scoping itself has no direct test (gap G3 — top-3
  recommendation #2).

### UC7 — Export CSV precios → reimport en Excel

- **Given** an ingredient with ≥3 price events.
- **When** Saskia downloads `/reportes/precios/csv` and opens it in Excel.
- **Then** the CSV has stable headers, one row per event, UTF-8 charset, sane
  `days` validation (≤365).
- **Status: PARTIALLY COVERED.** Export correctness:
  `test_reportes_precios.py::test_csv_export_headers_and_rows`,
  `::test_days_365_ok`, `::test_days_param_validated`. The Excel-open step is
  inherently **manual** (gap G6) — do one manual open per release.

### UC8 — Consistencia de totales entre páginas

- **Given** a seeded window of sales.
- **When** the daily summary totals are compared with a direct sum over the
  Sale table, and every template is scanned for raw money/date formatting.
- **Then** totals match to the guaraní and no page renders `{:,.0f}` money or
  US dates.
- **Status: COVERED.** `test_cross_page_consistency.py` (all 3 tests).

### UC9 (bonus) — Bug de multiplicación no reaparece

- **Given** a recipe yield 12, line 0.3 kg flour, manual forecast 24 portions.
- **When** the plan is computed.
- **Then** required flour is 0.6 kg (not 7.2), and 2× forecast → exactly 2× flour.
- **Status: COVERED.** `test_produccion_calendar.py::test_production_math_multiplication`.
  This is the single highest-consequence regression of the round; it stays
  pinned at the top of the calendar test file.

---

## 5. Recommendations

### Top 3 uncovered scenarios to cover before merge to main

1. **Restock → price event → surfaces end-to-end (was G4/UC3).** The Q1
   pipeline spans four modules (router → price_history → insights → three
   templates); every piece was green in isolation but nothing proved they
   compose. A silent break here is exactly the "wrong margin" failure Saskia
   bought this feature to prevent. **→ CLOSED in this round**
   (`test_qa_round1_user_journeys.py`); keep it in the smoke batch.
2. **Pedidos `status_filter` scoping (G3/UC6).** T4 shipped user-visible
   filtering with zero direct tests — the default-scope ('pendientes') bug
   class would hide *actionable orders* from Saskia. ~30 min: parametrized
   client test over the three values against seeded pedidos in each status.
3. **Nav hygiene template assert (G1+G2 combined).** One test file asserting
   (a) no `/auditoria`/`/ops/status` hrefs in the topnav block and (b) 'Ver
   receta' hrefs match `/recetas/{id}/editar` on `/produccion`. These are the
   two round-1 asks whose regression would be immediately visible to Saskia
   and are currently guarded only by eyeball. ~20 min.

(Also worth noting: the mixed-unit one-journey consistency check, G5, landed
with #1's file — it guards the T1 normalization contract across costing and
planning simultaneously.)

### T-0.1 blocker status

**Still open.** `forecast_source` semantics were never clarified with Saskia,
so the per-day seasonal-multiplier editor did NOT ship in round 1 — the 'Usar'
override UI did (what-if re-plan, no persistence). QA impact: nothing to test
for the editor; the shipped override is fully covered. Recommendation: send
the WhatsApp clarification before round 2 scoping; if she says "just an
average with a manual knob", the editor is a ~2h task with the override
plumbing already in place.

### Deploy gate

Ship to hosted when: smoke batch (§2) green, `test_qa_round1_user_journeys.py`
green, manual checks 10 (pedidos default filter), 16 (console errors), and
UC7's Excel open done. The 17 quarantined env failures do not gate the deploy.

---

## 6. Gap closure executed in T9

`tests/test_qa_round1_user_journeys.py` (second T9 commit) closes G4 — the
highest-value gap — and covers G5 in passing:

- `test_restock_chain_price_event_to_insight_card` — drives the REAL
  `/reorder/registrar` POST three times at rising prices, then asserts the
  full chain in one DB+UI pass: stock incremented, three `restock` events,
  denormalized price, `/inventario` strip + sparkline, `/reportes/precios`
  listing, and the dashboard 'Precios en alza' card with name + `+%`.
- `test_mixed_unit_recipe_costs_and_plans_consistently` — one recipe with a
  `g` line against a `kg` ingredient and an `ml` line against an `l`
  ingredient; asserts batch cost via the costing walk AND `plan_production`
  requirements agree with hand-computed normalized values.

Both are coverage-gap closures, not TDD: the behavior already shipped in
Phases B–D; these tests prove the pieces compose. They should pass
immediately on this branch — that is expected and correct.
