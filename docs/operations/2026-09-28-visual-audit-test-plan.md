# Sazón — Visual & Behavioral Test Plan
**Date:** 2026-09-28 · **Audit session:** `20260927_182227_f40eb1` · **Live URL:** https://sazon-vps.paragu-ai.com

---

## Executive summary

I reviewed every authenticated route on production (37 routes, 31 returning 200, plus 4 errors: 2× 500, 1× 400, 1× 405, 2× 404). The codebase already has **245 tests**; the gap is not "are routes reachable" (smoke covers that) but **"do action flows actually work end-to-end"** — every click, every submit, every redirect, every state transition.

This document defines **30 test plans** (P-01 through P-30), each scoped to one page or one cross-page action flow, written so any subagent can pick one and execute it via TDD. Each plan follows the same template:

1. **Why this plan exists** — what gap or risk it closes (often one of the 31 bugs from the visual audit)
2. **Pre-conditions** — DB fixtures, cookies, time-of-day if relevant
3. **Action steps** — exact sequence of HTTP requests / clicks / state changes
4. **Assertions** — what the test must verify
5. **Edge cases & failure modes** — what "wrong" looks like
6. **Acceptance** — when this plan can be marked "passed"
7. **Effort estimate** — S/M/L

Test infrastructure assumptions (matches `tests/conftest.py`):
- `client` — FastAPI `TestClient` with `SASKIA_TEST_AUTH_DISABLED=1`
- `session_factory` — temp SQLite bound to `tmp_db_path` fixture
- `factories.py` — `make_ingredient()`, `make_product()`, `make_recipe()`, `make_pedido()`, etc. UUID-suffixed.
- `flows.py` — `flow_post()` / `flow_get()` wrappers that return `FlowResult` with `.ok`, `.flash`, `.json`
- Run via: `./.venv/bin/python -m pytest tests/test_PXX_<name>.py -v --tb=short`

---

## Index of test plans

| # | Scope | Effort | Closes audit bug # |
|---|-------|--------|--------------------|
| P-01 | `/login` — sidebar visibility & form validation | S | #4, #5, #6 |
| P-02 | `/clientes` — CRUD, phone binding, points duplicate | M | #12, #13, #25 |
| P-03 | `/productos` & `/productos/nuevo` — combo getSelectedData regression | M | (regression net) |
| P-04 | `/recetas` & `/recetas/nueva` — combo field integration | M | #20, #21 |
| P-05 | `/inventario` — listing, filters, status pills | M | (regression net) |
| P-06 | `/inventario/nuevo` — form submit, alérgenos, tags | M | (regression net) |
| P-07 | `/ventas` — multi-item cart happy path | M | (verified Mon) |
| P-08 | `/ventas` — cart empty submit guard | S | (smoke covers) |
| P-09 | `/ventas/historial` — filters, pagination, CSV export | M | (regression net) |
| P-10 | `/pedidos` & `/pedidos/board` — listing, tabs | S | (regression net) |
| P-11 | `/pedidos/nuevo` — full form submit with lines | L | (gap) |
| P-12 | `/pedidos/{id}/fulfill` — P1 negative-stock block + force escape hatch | L | (audit #1) |
| P-13 | `/pedidos/{id}/stock-preview` — warnings display + force checkbox | M | (P1 fix) |
| P-14 | `/produccion` — 500 bug, daily_target undefined | M | audit #2 |
| P-15 | `/produccion-planner` — receta × tandas calc | M | (regression net) |
| P-16 | `/merma` — combo + waste registration | M | (regression net) |
| P-17 | `/reorder` — broken Jinja template repair | L | audit #1 |
| P-18 | `/reorder/registrar` — restock POST flow | M | audit #1 |
| P-19 | `/shopping-list` — broken "Para qué" column binding | M | audit #20, #21 |
| P-20 | `/wishlist` — status column visual + mark purchased | M | audit #14 |
| P-21 | `/bank` — bank-data hygiene, EUR/PYG dual account | L | audit #26 |
| P-22 | `/dashboard` — KPI good/bad indicators + MERMA duplication | M | audit #7, #8 |
| P-23 | `/analisis` — empty-state dressed-as-data | L | audit #10, #11 |
| P-24 | `/reportes/cierre-mensual` — label consistency "pérdida" | S | audit #15 |
| P-25 | `/reportes/retencion` — counters unpopulated | M | audit #16, #17 |
| P-26 | `/reportes/margenes` — 500 crash | M | audit #3 |
| P-27 | `/vs-mercado` — missing market data | L | audit #18 |
| P-28 | `/settings/catalog` — heading "Nuestros únicos activos" | S | audit #22 |
| P-29 | `/auditoria` — filters, CSV export, retention banner | M | (regression net) |
| P-30 | Cross-page dead routes 404 (`/ops`, `/settings/riesgos`) + breadcrumb cleanup | S | audit #31 |

---

## Conventions

- All tests live in `tests/test_PXX_<slug>.py`
- All tests use `client` and `session_factory` fixtures from `conftest.py`
- Money in `Gs.` uses `factories.gs()` (Decimal)
- Datetimes use `datetime.now(timezone.utc)` minus explicit offsets for "today/yesterday" — **never** wall-clock math that drifts
- Every action that should produce a 303 redirect asserts `.flash["flash"]` matches expected code
- Every action that mutates DB reads back via the same client to verify
- Every action that mutates stock asserts the resulting `Ingredient.stock_qty` matches expected value
- Every form POST asserts CSRF token is present (per `test_csrf_on_forms.py` convention)
- Every test has at least one negative case — what happens when input is invalid

---

## P-01 · `/login` — sidebar visibility & form validation

**Why:** Visual audit found the **full app sidebar visible to unauthenticated visitors** (#4), "demo" pre-filled (#6), and "Ingresar" button overlapping "Recordar este dispositivo" label (#5). Login form has no validation tests.

**Pre-conditions:** None — public route.

**Action steps:**
```
1. GET /login (unauthenticated) → 200
2. Assert response body does NOT contain:
   - "OPERACIÓN" section header
   - "Inicio" nav link
   - "Inventario" nav link
   - Any of the nav group labels
3. Assert response body DOES contain:
   - "Iniciar sesión" or "Ingresar" button
   - "Usuario" label
   - "Contraseña" label
   - "Mantener sesión abierta" checkbox
4. Assert the Usuario input does NOT have a pre-filled value attribute
5. POST /login with empty body → 422 (validation error, NOT 500)
6. POST /login with username="demo" + wrong password → 200 + form-error (or 303 to ?error=1)
7. POST /login with username="demo" + correct password → 303 + Set-Cookie
8. After login, GET /login → 303 to / (auth check, NOT show login form again)
9. Visual: assert "Recordar este dispositivo" label and the Ingresar button don't overlap (DOM bounding boxes don't intersect)
```

**Edge cases:**
- Whitespace in username (should strip)
- SQL-injection attempt in username field (should sanitize + 200, not 500)
- Very long password (255+ chars) — should not 500
- Login with disabled user account → error, not silent success

**Acceptance:** All 9 steps green; sidebar hidden pre-auth; "demo" not pre-filled; button+label don't overlap.

**Effort:** S (~30 min)

---

## P-02 · `/clientes` — CRUD, phone binding, points duplicate

**Why:** Visual audit found **all 8 customers show "None" for Teléfono** (#13), **"Programa de puntos" rendered twice** (#12), and **placeholder test customers in production data** (#25).

**Pre-conditions:** `session_factory`, seed 3 customers via `make_customer()`.

**Action steps:**
```
1. GET /clientes → 200
2. Count occurrences of "Programa de puntos: 1 punto por cada" in body → MUST equal 1 (not 2)
3. Assert the seeded customer's phone renders correctly (NOT "None")
4. POST /clientes/nuevo with valid name+phone → 303 to /clientes
5. GET /clientes → new customer appears in list
6. GET /clientes/{new_id} → 200, shows phone formatted (not "None")
7. POST /clientes/{new_id}/editar with new phone → 303
8. GET /clientes/{new_id} → phone updated
9. POST /clientes/{new_id}/eliminar → 303, customer gone from list
10. Negative: POST /clientes/nuevo with empty name → 422 (not 500)
11. Negative: POST /clientes/{new_id}/editar with phone="not-a-phone" → 422 or graceful 400
12. The phone formatter (template): assert "+595" prefix or local-format renders correctly
```

**Edge cases:**
- Customer with very long name (255 chars)
- Customer with emoji in name (Unicode)
- Phone with international format (+1, +44, etc.) — should normalize or reject gracefully

**Acceptance:** 12 steps green; "Programa de puntos" appears once; phone field renders for seeded data.

**Effort:** M (~1.5 hours)

---

## P-03 · `/productos` & `/productos/nuevo` — combo getSelectedData regression

**Why:** Today's fix (`d2b2e0c`) added `getSelectedData()` to `ui-combo.js`. Without a regression test, the next refactor strips it again and `ventas.html:301` silently TypeError-crashes (the bug audit caught).

**Pre-conditions:** Seed 5 products via `make_product()`, browser client (TestClient doesn't run JS — use Playwright per `cart-smoke.js` pattern).

**Action steps:**
```
1. Boot Playwright Chromium against https://sazon-vps.paragu-ai.com
2. Login as demo
3. GET /productos/nuevo
4. Inspect the <ui-combo> element via JS:
   - Get the `__comboInstance` reference (or invoke the API directly)
   - Call `instance.setOptionsData([{value:1, label:"prod1", sale_price_gs:1000}, ...])`
   - Open the dropdown, click item
   - Assert `instance.getSelectedData()` returns the full object (NOT undefined)
   - Assert `instance._selectedItem` is set
5. Repeat on /productos (listing) if combo is used there
6. Verify console has no "getSelectedData is not a function" errors
7. Smoke: trigger attributeChangedCallback manually → confirm no "Cannot set properties of null" errors
```

**Edge cases:**
- Rapid click on combo (race conditions)
- setOptionsData called BEFORE connectionCallback completes (verify null guard works)
- Empty options array → no crash

**Acceptance:** `getSelectedData()` always callable; no console errors; null-guard works.

**Effort:** M (~1 hour — Playwright setup needed)

---

## P-04 · `/recetas` & `/recetas/nueva` — combo field integration

**Why:** Visual audit noted the "Vista previa: Producto" panel renders empty when no product selected (might be intentional, but needs explicit test). Existing `test_recetas_pagination.py` and `test_recetas_photo_modal.py` cover parts; this fills in combo + form submit flow.

**Pre-conditions:** Seed 5 recipes via `make_recipe()` with `yield_qty=12, yield_unit="und"`.

**Action steps:**
```
1. GET /recetas → 200, table shows seeded recipes with margin column populated
2. GET /recetas/nueva → 200
3. Assert "Vista previa: Producto" panel exists
4. Assert the panel is empty when no product selected (initial state)
5. POST /recetas/nueva with valid data:
   - name="receta-test-{uuid}"
   - yield_qty=24
   - yield_unit="und"
   - difficulty=2
   - 1 recipe line: ingredient_id=seeded.id, qty=0.3, line_unit="kg"
   - 1 product line: product_id=seeded.id, qty=1, line_unit="und"
6. Assert response = 303 to /recetas
7. GET /recetas/{new_id} → 200, shows all lines, total cost computed
8. POST /recetas/{new_id}/editar with line_qty changed → 303
9. GET /recetas/{new_id} → cost recalculated
10. Negative: POST /recetas/nueva with no lines → 422 or graceful 400
11. Negative: POST /recetas/nueva with invalid line_qty=-5 → 422
12. Verify "Costo/unidad" computes correctly: (0.3kg × purchase_price_gs) / yield_qty
```

**Edge cases:**
- Recipe with no product (no consumer) — should still save
- Recipe with 0 yield → division by zero handling
- Recipe line with negative qty → 422
- Duplicate recipe name → 422 or graceful merge

**Acceptance:** 12 steps green; combo preview updates; recipe persists with cost.

**Effort:** M (~1.5 hours)

---

## P-05 · `/inventario` — listing, filters, status pills

**Why:** Page renders well visually but **status pill colors** + **filter combinations** aren't exhaustively tested. Existing `test_inventory_*` covers CRUD; this focuses on UI states.

**Pre-conditions:** Seed 30 ingredients with varied stock_qty (5 with stock < min, 5 with stock = min, 20 with stock > min).

**Action steps:**
```
1. GET /inventario → 200, table shows all 30
2. Filter by stock crítico → 5 rows shown (not 30)
3. Filter by categoría="harinas" → only matching rows
4. Filter by alérgenos contains "gluten" → only matching rows
5. Filter by almacenamiento="seco" → only matching rows
6. Combine filters (categoría + stock crítico) → AND semantics
7. Status pill verification:
   - Items below min → red "Stock bajo" pill
   - Items at min → yellow "Stock crítico" pill
   - Items above min → green "OK" pill
   - Items at 0 → red "Sin stock" pill
8. Click pagination "2" → next 20 rows
9. Click "Exportar CSV" → 200 + text/csv + Content-Disposition
10. CSV contents match filtered table (not full DB)
11. Sort by stock_actual ASC → ordering correct
```

**Edge cases:**
- Filter with no matches → empty state CTA visible
- Filter with special characters (URL-encoded)
- Pagination on the last page (no "next" button)
- Filter cookie persistence (does filter survive reload?)

**Acceptance:** 11 steps green; pills colored correctly; filters AND correctly.

**Effort:** M (~1.5 hours)

---

## P-06 · `/inventario/nuevo` — form submit, alérgenos, tags

**Why:** Form has multiple field groups (Datos básicos, Operación y cumplimiento, Clasificación y conservación). Need to verify all submits persist.

**Pre-conditions:** Empty DB for unique name check.

**Action steps:**
```
1. GET /inventario/nuevo → 200, all 3 sections render
2. POST with minimal data (name only) → 422 (missing required fields)
3. POST with all required fields:
   - name="harina-test-{uuid}"
   - category="harinas"
   - unit="kg"
   - current_stock=10.0
   - min_stock=2.0
   - purchase_price_gs=3000
   → 303 to /inventario
4. GET /inventario → new ingredient appears
5. POST with alérgenos checkboxes (gluten + lacteos) → saved as multi-value
6. POST with etiquetas (sin TACC, vegano) → saved
7. POST with vida_util_dias=30 → saved
8. Negative: POST with name="" → 422
9. Negative: POST with unit="invalid" → 422
10. Negative: POST with current_stock=-5 → 422
11. Negative: POST with duplicate name → 422 or 409 (unique constraint)
12. Edit flow: POST /inventario/{id}/editar with changed min_stock → 303
13. Verify audit log entry exists for create + update
```

**Edge cases:**
- Very long name (255+ chars)
- Unicode in name (Spanish accents: "azúcar")
- Decimal precision on price (Gs. 1234.56789 → rounds? Truncates?)
- Negative vida_util_dias

**Acceptance:** 13 steps green; full form persists; audit logged.

**Effort:** M (~1.5 hours)

---

## P-07 · `/ventas` — multi-item cart happy path

**Why:** Today's smoke test (deleg_e65a7389 task-1) confirmed cart works. Need a **persistent regression test** so this never silently breaks.

**Pre-conditions:** Seed 5 products with recipes. Playwright session with login.

**Action steps:**
```
1. Login as demo via Playwright
2. GET /ventas → 200
3. Click 2 different quick-sale buttons → cart shows 2 rows, badge="2", total=sum
4. Click +/- qty → updates render + cart JSON live
5. POST /ventas/nueva/multi with cart JSON → 303 + flash=sale_created
6. GET /inventario → ingredient stock decremented for BOTH lines (recipe cascade)
7. Repeat: 3 different products → cart with 3 rows → submit → all 3 lines persisted
8. Customer field: select existing customer → POST → sale has customer_id set
9. Payment method: select "efectivo" → sale.payment_method="efectivo"
10. Channel: select "mostrador" → sale.channel="mostrador"
11. Discount: enter 1000 Gs. discount → sale.discount_gs=1000, total reduced
12. Notes: enter "cliente pidió extra canela" → saved
13. After submit: GET /ventas/historial → today's sale appears
```

**Edge cases:**
- Quick-sale with insufficient stock → client-blocked (alert), server-side fallback 422
- Submit with cart having 1 item with qty=0 → reject
- Submit twice rapidly (double-click) → idempotency_key prevents double-record

**Acceptance:** 13 steps green; cart-to-DB full roundtrip verified.

**Effort:** M (~1.5 hours — Playwright needed)

---

## P-08 · `/ventas` — cart empty submit guard

**Why:** Existing smoke confirms this works (subagent sa-1). Make it a regression test.

**Action steps:**
```
1. Login, GET /ventas
2. Assert submit button is disabled (disabled=true attribute) when cart empty
3. Bypass: invoke handleFormSubmit() directly via JS → returns false
4. Assert alert() fires with "Agregá al menos un producto al carrito."
5. Assert zero POST requests to /ventas/nueva/multi in network log
6. Now click 1 quick-sale → submit enabled
7. Click remove (×) on the row → cart empty, submit disabled again
```

**Effort:** S (~20 min)

---

## P-09 · `/ventas/historial` — filters, pagination, CSV export

**Why:** Page renders 50 rows with filters and pagination; no test for filter+page combination.

**Pre-conditions:** Seed 100 sales across 30 days, 5 customers, 3 channels.

**Action steps:**
```
1. GET /ventas/historial → 200, default page 1 shows 10 rows, total stats show "1.040 ventas"
2. Filter fecha_desde=2026-09-01 → rows from that date onward
3. Filter cliente="Familia Romero" → only that client's sales
4. Filter producto="Cheesecake entera" → only sales of that product
5. Filter channel="mostrador" → only that channel
6. Filter payment_method="efectivo" → only cash sales
7. Combine all 5 filters → AND
8. Click pagination "2" → page 2 of filtered results
9. Click "Exportar CSV" → CSV matches CURRENT filter (not full DB)
10. CSV header columns: id, fecha, cliente, producto, qty, total, channel, payment_method, notes
11. Negative: filter with impossible date range (2030+) → empty state
12. URL state: filters reflected in URL params (bookmarkable)
```

**Acceptance:** 12 steps green; CSV export = filtered view.

**Effort:** M (~1.5 hours)

---

## P-10 · `/pedidos` & `/pedidos/board` — listing, tabs

**Pre-conditions:** Seed 10 pedidos across 3 statuses (pendiente, en_preparacion, listo).

**Action steps:**
```
1. GET /pedidos → 200, 4 tabs visible (Hoy/Mañana, Pendientes, Terminados, Todos)
2. Tab "Hoy/Mañana" → only pedidos with promised_date = today or tomorrow
3. Tab "Pendientes" → all status != "terminado"
4. Tab "Terminados" → status = "terminado"
5. Tab "Todos" → all rows, no filter
6. GET /pedidos/board → 200, 3 columns (Pendientes, En preparación, Listos)
7. Card on board click → detail view
8. Search "Cliente" → filters by name OR phone
9. "CSV download" button → CSV with all pedido metadata
10. Click "Volver" / breadcrumb back → /pedidos
```

**Acceptance:** 10 steps green; tabs filter correctly.

**Effort:** S (~45 min)

---

## P-11 · `/pedidos/nuevo` — full form submit with lines

**Why:** Visual audit showed the form looks complete but **no test verifies the full flow** end-to-end (existing `test_pedidos_*` covers create + cancel only).

**Pre-conditions:** Seed 3 products with recipes, 1 cliente, 1 delivery zone.

**Action steps:**
```
1. GET /pedidos/nuevo → 200, all fields render
2. POST with minimal data (no lines) → 422
3. POST with full data:
   - cliente=seeded.id
   - telefono="+595981123456"
   - promised_date=tomorrow
   - promised_time="15:00"
   - channel="delivery"
   - payment_method="efectivo"
   - delivery_zone=seeded.id
   - notes="Llamar antes de llegar"
   - lines=[{product_id: p1, qty: 2, unit_price_gs: 50000},
            {product_id: p2, qty: 1, unit_price_gs: 25000}]
   → 303 to /pedidos/{new_id}
4. GET /pedidos/{new_id} → 200, all 2 lines persisted
5. Assert total = sum(qty × unit_price_gs) = 125000
6. POST with cliente missing → 422 or default
7. POST with promised_date in past → 422
8. POST with line containing unknown product_id → 422
9. POST with line containing qty=-1 → 422
10. POST with line containing qty=0 → 422
11. POST with line containing non-numeric unit_price_gs → 422
12. Edit flow: POST /pedidos/{id}/editar with one line removed → 303, total recalculated
13. Audit log: pedido_created event recorded with user_id, snapshot
```

**Edge cases:**
- Concurrent edits (rare but possible)
- timezone-aware datetime in promised_date (must serialize correctly)
- Very long notes (255+ chars)
- cliente with special characters in name

**Acceptance:** 13 steps green; full pedido created + persisted + auditable.

**Effort:** L (~3 hours)

---

## P-12 · `/pedidos/{id}/fulfill` — P1 negative-stock block + force escape hatch

**Why:** Today's P1 fix (`de47b58`). Existing `test_pedidos_fulfill_negative_stock.py` (3 tests) covers core flow; this plan extends.

**Pre-conditions:** Seed 1 pedido with 1 line whose recipe demands more ingredient than available.

**Action steps:**
```
1. Setup: ingredient.stock_qty=0.5kg, pedido line qty=24 of yield-12 recipe consuming 0.3kg/batch
2. POST /pedidos/{id}/fulfill (no force) → 303 to /pedidos/{id}/stock-preview
3. Assert flash="Stock+insuficiente+para+<n>+ingredientes"
4. Assert pedido.status unchanged (NOT fulfilled)
5. Assert ingredient.stock_qty unchanged (still 0.5)
6. Assert AppMeta idempotency reservation cleared (not consumed)
7. POST /pedidos/{id}/fulfill with force=true → 303 to /pedidos (success)
8. Assert pedido.status = "fulfilled"
9. Assert ingredient.stock_qty < 0 (negative — forced)
10. Assert audit row has detail.force_fulfilled_over_shortfall = [{ingredient:..., shortfall:...}]
11. POST /pedidos/{id}/fulfill with force=true but stock OK → 303 success, NO audit force row
12. Negative: POST with malformed force="yes" (not "true") → still respects force
13. Negative: POST with force=true on a non-existent pedido → 404
14. Verify log.warning emitted with pedido_id, shortfall_count, user_id (capture via caplog)
```

**Acceptance:** 14 steps green; full positive+force+negative paths covered.

**Effort:** L (~2 hours, extending existing test file)

---

## P-13 · `/pedidos/{id}/stock-preview` — warnings display + force checkbox

**Why:** P1 fix added UI warnings + force checkbox to `pedido_stock_preview.html`. Existing `test_pedidos_fulfill_negative_stock.py` covers the redirect, this plan covers the **page rendering**.

**Action steps:**
```
1. Setup: pedido with 1 line, ingredient.stock_qty=0.5kg, recipe demands 0.6kg
2. GET /pedidos/{id}/stock-preview → 200
3. Assert "⚠️" icon visible
4. Assert "X ingredientes quedarían con stock negativo" text (X = number of shortfalls)
5. Assert "Forzar cumplimiento a pesar del faltante" checkbox present
6. Assert checkbox NOT checked by default
7. Click checkbox → checked
8. Submit form → POST /pedidos/{id}/fulfill with force=true → 303 (covered in P-12)
9. GET /pedidos/{id}/stock-preview (after forced fulfill) → 200, no warning (stock already negative but state changed)
10. New scenario: pedido with no shortfalls → GET preview → 200, NO warning shown
11. New scenario: pedido with 2 shortfalls → GET preview → both ingredient names visible in warning
```

**Acceptance:** 11 steps green; warnings render correctly; checkbox controls form behavior.

**Effort:** M (~1.5 hours)

---

## P-14 · `/produccion` — 500 bug, daily_target undefined

**Why:** Visual audit found **500 crash** on `/produccion`. Audit error: `Tipo: UndefinedError`, ref `17f67d30a274`. Likely `'daily_target' is undefined` in template (matches subagent's noted pre-existing baseline).

**Pre-conditions:** Seed 5 recipes + plan templates.

**Action steps:**
```
1. GET /produccion → 200 (after fix; was 500)
2. Assert response body contains "Plan manual" or "Plan del día" or whatever the correct h1 is
3. Assert NO Jinja "UndefinedError" traceback in body
4. Assert daily_target value visible (if used in template)
5. Run with empty DB → 200 + empty state
6. Run with 5 recipes + no plan templates → 200, no crash
7. Run with 5 recipes + Monday plan template → 200, plan row shows for current weekday
8. POST plan override (qty change) → 303 success
9. Verify override persists across /produccion reload
```

**Edge cases:**
- for_date param invalid (e.g., 2026-13-45) → 422
- for_date in future (next month) → 200, empty plan
- for_date in past → 200, shows what was planned

**Acceptance:** 9 steps green; **/produccion returns 200** (the bug fix verification).

**Effort:** M (~1 hour — find the missing var, fix template, test)

---

## P-15 · `/produccion-planner` — receta × tandas calc

**Why:** Page renders empty state. Need to verify the calculation when user selects receta + tandas.

**Pre-conditions:** Seed 3 recipes (each with 3 ingredients).

**Action steps:**
```
1. GET /produccion-planner → 200
2. Assert empty state visible
3. POST with receta_id + tandas=10 → 200 with calculation
4. Assert ingredient list shows: required_qty = recipe_line.qty × (10/yield_qty) × 1
5. Assert color: red if stock < required, green if stock >= required
6. POST with receta_id + tandas=0 → 422
7. POST with non-existent receta_id → 404
8. POST with non-numeric tandas → 422
9. Click "Calcular necesidad" button → calculation updates live (or full form POST)
```

**Edge cases:**
- Receta with no ingredients → empty state
- Receta with 0 yield_qty → division by zero handling
- Very large tandas (1000+) → calculation still correct

**Acceptance:** 9 steps green; calculation correct; error states handled.

**Effort:** M (~1.5 hours)

---

## P-16 · `/merma` — combo + waste registration

**Pre-conditions:** Seed 5 ingredients, 5 products.

**Action steps:**
```
1. GET /merma → 200
2. Click combo to register merma → modal/form opens
3. Select ingredient, enter qty, select reason → submit
4. Assert /merma page now shows the new merma row
5. Verify ingredient.stock_qty decreased by merma qty
6. Click combo to register product merma (overproduction) → submit
7. Verify product sale price unaffected (merma doesn't roll back)
8. Negative: submit with qty=0 → 422
9. Negative: submit with qty > current_stock → 422 or graceful (can be force-allowed)
10. View merma history → all entries listed
11. Filter merma by date range → filtered
12. Filter by reason (caducidad, error, robo) → filtered
13. CSV export of merma
```

**Acceptance:** 13 steps green; merma decrements stock; audit logged.

**Effort:** M (~1.5 hours)

---

## P-17 · `/reorder` — broken Jinja template repair

**Why:** Visual audit found **critical Jinja template bug** in `reorder.html:137-152` — `{{ item.unit }}`, `value='4500'`, `aria-label="..."` rendered as visible text. Inputs not closed in right order.

**Pre-conditions:** Seed 5 ingredients with stock_qty < min_stock.

**Action steps:**
```
1. GET /reorder → 200 (after fix)
2. Assert response body does NOT contain literal "{{ item.unit }}" anywhere
3. Assert response body does NOT contain "value='4500'" or similar raw Jinja leakage
4. For each restock row, the form must have:
   - <input type="number" name="qty" value="<suggested_qty>"> properly closed
   - <ui-combo name="qty_unit"> with options matching the unit type
   - <input type="number" name="price_gs" value="<purchase_price_gs>"> properly closed
   - <button>Reponer</button>
5. Parse the rendered HTML with an HTML parser (BeautifulSoup or lxml) and assert the form is well-formed (no unclosed tags, no orphan attributes)
6. Visual: Playwright screenshot → assert no `{{ }}` strings visible in any of the 5 rows
7. Visual: assert no `value='4500'` raw attribute visible
8. Visual: assert the qty + unit + price + button are all in the same form row, not floating
9. Click "Seleccionar todos" → all checkboxes checked
10. Click "Generar pedido por WhatsApp" → wa.me/ link with all selected ingredient names
```

**Edge cases:**
- ingredient with no purchase_price_gs → empty price field, still renders
- ingredient with unit="und" (each) → combo shows just "und" option
- ingredient with qty=0 → still renders but suggeste qty = min - current

**Acceptance:** 10 steps green; **template renders valid HTML**; no Jinja leakage.

**Effort:** L (~3 hours — fix template + Playwright visual verification)

---

## P-18 · `/reorder/registrar` — restock POST flow

**Why:** P-17 verifies the page renders. This verifies the form actually submits and stock updates.

**Pre-conditions:** Seed ingredient with stock=2, min=10.

**Action steps:**
```
1. GET /reorder, find the form for the ingredient
2. POST /reorder/registrar with ingredient_id, qty=10, qty_unit="kg", price_gs=3000
3. Assert 303 to /reorder (success)
4. GET /inventario → ingredient stock_qty now 12 (2 + 10)
5. POST without CSRF token → 403 (per CSRF convention)
6. POST with ingredient_id not found → 404
7. POST with qty=-5 → 422
8. POST with qty=0 → 422
9. POST with price_gs=-100 → 422
10. Verify audit row created: "reorder_registrar" with old_stock + new_stock
11. Verify purchase_price_gs updated on ingredient (or separate PriceEvent row)
12. Multiple submits (qty=10, qty=5) → stock accumulated
```

**Acceptance:** 12 steps green; restock persists; stock + price updated; audit logged.

**Effort:** M (~1.5 hours)

---

## P-19 · `/shopping-list` — broken "Para qué" column binding

**Why:** Visual audit found **all rows show literal `Auto stock 0,0,0,0,0...`** in "PARA QUÉ" column (#20) and broken Spanish help text (#21).

**Pre-conditions:** Seed 5 ingredients with stock_qty < min_stock.

**Action steps:**
```
1. GET /shopping-list → 200
2. Assert "PARA QUÉ" column does NOT contain "0,0,0,0,0..." literal
3. Assert the column shows actual data (recipe names, or stock values, depending on what the field is supposed to be)
4. Assert footer help text has correct Spanish with accents and no broken phrasing
5. Click "Lista del día" tab → list of ingredients
6. Click "Todos (incl. comprados)" tab → all including purchased
7. Click "Crear lista" → form opens to create custom list
8. Submit custom list → 303, list created
9. Click "Seleccionar faltantes" → multi-select UI
10. Generate "Hacer un pedido" button → produces WhatsApp message
11. Negative: create list with empty name → 422
```

**Edge cases:**
- List with 0 ingredients → empty state CTA
- List with 100 ingredients → pagination
- Mark as purchased → moves from "Lista del día" to "Todos"

**Acceptance:** 11 steps green; column data correct; help text fixed.

**Effort:** M (~1.5 hours — find template variable binding bug)

---

## P-20 · `/wishlist` — status column visual + mark purchased

**Why:** Visual audit found **status column has orange "Pendiente" pill + tiny green ✅ icon crammed together** (#14).

**Pre-conditions:** Seed 5 wishlist items (3 pending, 2 purchased).

**Action steps:**
```
1. GET /wishlist → 200
2. Assert status column shows ONE indicator per row (either "Pendiente" pill OR "Comprado" check, NOT both)
3. Click "Marcar comprado" on a pending item → 303, status changes
4. GET /wishlist → item now shows "Comprado"
5. KPI tiles: "21 pendientes" decrements by 1, "6 comprados" increments by 1
6. Click "Volver a pendiente" on purchased item → status reverts
7. POST new wishlist item (name, qty, unit_price_gs, category, donde_comprar) → 303
8. Edit wishlist item → 303
9. Delete wishlist item → 303
10. Filter by status=pending → 3 rows
11. Filter by status=purchased → 2 rows
12. Filter by category="Moldes" → filtered
13. CSV export → all wishlist items
```

**Edge cases:**
- Wishlist with 0 items → empty state
- Bulk mark purchased (checkbox + button)
- Bulk delete

**Acceptance:** 13 steps green; status clear; CRUD works.

**Effort:** M (~1.5 hours)

---

## P-21 · `/bank` — bank-data hygiene, EUR/PYG dual account

**Why:** Visual audit found **307 Dutch EUR transactions from "JOHN VAN DER POL"** in production (#26) — this is demo/test data leaking into the prod DB. Either clean it up or guard it from prod.

**Pre-conditions:** Bank table seeded with EUR + PYG transactions.

**Action steps:**
```
1. GET /bank → 200
2. Assert NO transactions from "JOHN VAN DER POL" (or any non-PYG accounts)
3. Assert NO transactions where currency="EUR" (PY bakery uses PYG)
4. If multi-currency IS supported, assert it's documented + tested + scoped
5. Categorization: verify each transaction has a category (incoming_transfer, other, personal, transport)
6. Filter by category=incoming_transfer → only those
7. Filter by date range → working
8. Add manual movement ("Agregar movimiento manualmente") → 303
9. New manual movement shows in list with category="manual"
10. Reconciliation: mark a transaction as reconciled → status updated
11. CSV export of bank movements
12. Negative: add manual movement with negative amount → 422
13. Negative: add manual movement with no category → 422
```

**Edge cases:**
- Bank account with 0 transactions → empty state
- Bank account in different currency (USD, EUR if multi-currency supported)
- Very old transactions (5+ years ago)

**Acceptance:** 13 steps green; **no demo data in production**; multi-currency either proper or removed.

**Effort:** L (~2 hours — may require DB cleanup)

---

## P-22 · `/dashboard` — KPI good/bad indicators + MERMA duplication

**Why:** Visual audit found **no good/bad visual feedback** on KPIs (#7) and **MERMA labeled twice** (#8).

**Pre-conditions:** Seed known sales, costs, merma records to control KPI values.

**Action steps:**
```
1. GET /dashboard → 200
2. Assert each KPI tile has a "good/bad" indicator:
   - COSTO MATERIA PRIMA below target → green check or down-arrow
   - MARGEN BRUTO above target → green check or up-arrow
   - RECURRENCIA below target → red X or warning
3. Assert MERMA label appears ONCE (not twice)
4. Click "Ingresos" tile → drill-down to /reportes/diario (or /ventas/historial)
5. Click "Porciones vendidas" tile → drill-down
6. Click "Receta más vendida" → recipe detail
7. Click "Por canal de venta" → channel breakdown
8. Assert "Objetivos preconfigurados" matches current seeded targets
9. Verify number formatting: "9.576.000" with dot separator, no decimals on whole numbers
10. Verify "PORCIONES VENDIDAS 241.0" shows integer "241" (no .0)
11. Date navigation: change month → KPIs recalculate
12. Negative: dashboard with empty DB → all KPIs 0 with empty-state CTAs
```

**Acceptance:** 12 steps green; **good/bad indicators visible**; **MERMA labeled once**.

**Effort:** M (~2 hours — UI changes)

---

## P-23 · `/analisis` — empty-state dressed-as-data

**Why:** Visual audit found **"Alerta: margen cayendo" shows 100 rows all "-0%"** (#10) and **"Rotación de stock" shows 0.0 kg / 0 días for every item** (#11). Also top banner shows "10:00" which is unclear (#9).

**Pre-conditions:** Seed varied margin data and rotation data.

**Action steps:**
```
1. GET /analisis → 200
2. Assert "Alerta: margen cayendo" section: if no actual deltas exist, show empty-state message ("No hay márgenes cayendo"), NOT a 100-row table
3. Assert "Rotación de stock" section: if no usage data, show empty-state
4. Assert top banner: the "10:00" element either displays correctly with context OR is removed
5. "En stock" section: 100+ ingredients with stock shown
6. "Productos más rentables (últimos 30 días)" → top 5 with revenue
7. "Costo concentrado en pocos ingredientes" → top 5 with concentration %
8. "Promedio de ventas por día de la semana" → bar chart or table per weekday
9. Date range filter → all sections recalculate
10. Export each section to CSV → CSV matches displayed data
```

**Acceptance:** 10 steps green; **empty states replace zero-data masquerade**; all sections functional.

**Effort:** L (~3 hours — multiple section rewrites)

---

## P-24 · `/reportes/cierre-mensual` — label consistency "pérdida"

**Why:** Visual audit found **"Resultado del mes: 7.084.002" (positive) and "Pérdida del mes: 2.459.998" (positive number with "pérdida" label)** (#15).

**Action steps:**
```
1. GET /reportes/cierre-mensual → 200
2. Assert "Resultado del mes" + "Pérdida del mes" use consistent labels:
   - Either "Resultado del mes" + "Pérdida bruta" (with explanation)
   - OR single "Resultado del mes" net value
3. Assert the "pérdida" value, if shown, is either NEGATIVE when it's a real loss OR clearly labeled as "Pérdidas (descuentos/devoluciones)"
4. Click month navigation (Sept 2026 → Oct 2026) → data recalculates
5. Month with no data → empty state
6. Export CSV of cierre mensual
7. Each row's "Margen" column matches definition (e.g., (precio-costo)/precio)
8. Total row at bottom matches sum of column above
```

**Acceptance:** 8 steps green; **labels are unambiguous**.

**Effort:** S (~30 min — label fix)

---

## P-25 · `/reportes/retencion` — counters unpopulated

**Why:** Visual audit found **Activos=0, En riesgo=0, Recuperados=0** despite 8 clientes existing (#16, #17).

**Pre-conditions:** Seed 8 clientes with last_sale_at dates spanning 0-180 days.

**Action steps:**
```
1. GET /reportes/retencion → 200
2. Assert "Activos" counter > 0 if any cliente has last_sale_at within 30 days
3. Assert "En riesgo" counter > 0 if any cliente has 60 < days_since_last_sale < 90
4. Assert "Recuperados" counter > 0 if any cliente went dormant then came back
5. Assert "0 clientes en últimos 90 días" matches actual count
6. Click cliente name in detail table → /clientes/{id}
7. Filter by "Activos" → only that subset
8. Filter by "En riesgo" → only that subset
9. Filter by "Recuperados" → only that subset
10. CSV export → all clientes with their retention status
```

**Edge cases:**
- Cliente with no last_sale_at (never purchased) → not counted as "activo", maybe "nuevo"
- Date math: cliente created today but never purchased

**Acceptance:** 10 steps green; **counters reflect real data**.

**Effort:** M (~1.5 hours — may be query bug)

---

## P-26 · `/reportes/margenes` — 500 crash

**Why:** Visual audit found **500 crash** (#3), ref `abc151fdcc26`. Likely `daily_target` class of bug.

**Action steps:**
```
1. GET /reportes/margenes → 200 (after fix)
2. Assert no UndefinedError in body
3. Assert margin by recipe / by category / by channel all render
4. Date range filter → recalculates
5. CSV export
6. With empty DB → empty state (not 500)
7. With single sale → renders that one sale's margin
```

**Acceptance:** 7 steps green; **page renders**.

**Effort:** M (~1 hour — find missing var, fix)

---

## P-27 · `/vs-mercado` — missing market data

**Why:** Visual audit found **many "Sin datos" zeros** (#18). Market data may not be loaded.

**Pre-conditions:** Seed market_price entries for at least 10 ingredients.

**Action steps:**
```
1. GET /vs-mercado → 200
2. Assert table shows: producto, precio_propio, precio_mercado, diferencia_%, recomendacion
3. For seeded ingredients with market prices, all 4 columns populated
4. For seeded ingredients WITHOUT market prices, "Sin datos" message OR "No comparable" — not just `0`
5. Sort by diferencia % → ascending (cheapest vs market first)
6. Filter by category → filtered
7. Filter by margen < X% → red flags
8. Date range filter → shows market price as of that date (if historical)
9. CSV export
```

**Acceptance:** 9 steps green; **market data populated correctly**; missing data shown as "Sin datos", not `0`.

**Effort:** L (~2 hours — data pipeline + display logic)

---

## P-28 · `/settings/catalog` — heading "Nuestros únicos activos"

**Why:** Visual audit found **"Nuestros únicos activos" heading above empty state "La tienda está vacía..."** (#22). Confusing mixed language + concept.

**Action steps:**
```
1. GET /settings/catalog → 200
2. Assert no "Nuestros únicos activos" heading
3. Assert no "La tienda está vacía..." text (it's a settings page, not a tienda)
4. Assert proper subnav: Categorías producto, Familias de costo, Canales de venta, Forma de pago, etc.
5. Click "Categorías producto" → list of categories
6. Add new category → 303
7. Edit category → 303
8. Delete category (if no dependencies) → 303
9. Repeat for each subnav tab
10. Assert "Umbrales de alerta" tab lets you edit thresholds
11. Assert "Almacenes" lets you add/edit warehouses
12. Negative: try to delete a category used by products → 422 with reason
```

**Acceptance:** 12 steps green; **heading fixed**; all subnav tabs functional.

**Effort:** S (~30 min for heading fix + M for subnav coverage)

---

## P-29 · `/auditoria` — filters, CSV export, retention banner

**Pre-conditions:** Seed 50 audit log entries across 7 days, 3 users, 5 modules.

**Action steps:**
```
1. GET /auditoria → 200
2. Assert retention banner: "los registros de auditoría se eliminan automáticamente después de 1 año"
3. Filter fecha_desde/hasta → rows in range
4. Filter modulo → only that module
5. Filter tipo_ingreso → only that type
6. Filter by user → only that user's actions
7. Combine all 4 filters → AND
8. Click "Exportar CSV" → CSV with current filters applied
9. Verify CSV columns: id, timestamp, user, modulo, action, detail
10. Pagination on large result set
11. Empty filter result → empty state CTA
12. Negative: filter with invalid date format → 422
```

**Acceptance:** 12 steps green.

**Effort:** M (~1.5 hours)

---

## P-30 · Cross-page dead routes 404 (`/ops`, `/settings/riesgos`) + breadcrumb cleanup

**Why:** Visual audit found **`/ops` 404 has breadcrumb pointing to non-existent path**, **`/settings/riesgos` 404 has no breadcrumb** (inconsistent), and `/ventas/nueva` returns raw JSON 405 to GET requests (#27, #31).

**Pre-conditions:** None.

**Action steps:**
```
1. GET /ops → 404 with consistent breadcrumb (or no breadcrumb — pick one)
2. GET /settings/riesgos → 404 with same convention as /ops
3. GET /unknown-path → 404 with same 404 page
4. GET /ventas/nueva → 303 redirect to /ventas (instead of 405 JSON)
5. If 405 is intentional for an API-only endpoint, return HTML error page with "Método no permitido" + link to expected GET URL
6. Verify the 404 page renders in light AND dark theme (already covered by WCAG tests, but verify these new pages)
7. Verify no dead links in any breadcrumb across all 37 pages (Playwright crawl)
8. Verify the "Quizás buscabas una de estas:" suggestions are actually useful for each 404 (heuristic: suggest paths that share URL prefix)
9. Optional: add /ops status page if it's a real feature; remove from sidebar if it's not
10. Optional: add /settings/riesgos if "riesgos" feature exists; remove if not
```

**Acceptance:** 10 steps green; **404 pages consistent**; **no dead breadcrumbs**; **no raw JSON 405 errors**.

**Effort:** S (~1.5 hours — find dead links + standardize)

---

## How to execute

1. **Pick a plan** (P-01 through P-30)
2. **Use `delegate_task`** to spawn a subagent with this plan + relevant skill context
3. **Subagent follows TDD** per `test-driven-development` skill:
   - RED: write failing test, run it, verify failure
   - GREEN: minimal implementation, run it, verify pass
   - REFACTOR: clean up, run again, verify still green
   - Commit per cycle
4. **Verify locally**: `./.venv/bin/python -m pytest tests/test_PXX_*.py -v --tb=short`
5. **Deploy via the standard pipeline**: `vps-sync + docker build -t sazon-rms:v{N} . && docker service update --image sazon-rms:v{N} sazon-vps_web`
6. **Verify in prod**: `./shoot_prod.py` + WCAG spot-check

---

## Estimated total effort

| Plan | Effort | Cumulative |
|------|--------|------------|
| P-01 | 0.5 h | 0.5 |
| P-02 | 1.5 h | 2.0 |
| P-03 | 1.0 h | 3.0 |
| P-04 | 1.5 h | 4.5 |
| P-05 | 1.5 h | 6.0 |
| P-06 | 1.5 h | 7.5 |
| P-07 | 1.5 h | 9.0 |
| P-08 | 0.3 h | 9.3 |
| P-09 | 1.5 h | 10.8 |
| P-10 | 0.75 h | 11.6 |
| P-11 | 3.0 h | 14.6 |
| P-12 | 2.0 h | 16.6 |
| P-13 | 1.5 h | 18.1 |
| P-14 | 1.0 h | 19.1 |
| P-15 | 1.5 h | 20.6 |
| P-16 | 1.5 h | 22.1 |
| P-17 | 3.0 h | 25.1 |
| P-18 | 1.5 h | 26.6 |
| P-19 | 1.5 h | 28.1 |
| P-20 | 1.5 h | 29.6 |
| P-21 | 2.0 h | 31.6 |
| P-22 | 2.0 h | 33.6 |
| P-23 | 3.0 h | 36.6 |
| P-24 | 0.5 h | 37.1 |
| P-25 | 1.5 h | 38.6 |
| P-26 | 1.0 h | 39.6 |
| P-27 | 2.0 h | 41.6 |
| P-28 | 2.0 h | 43.6 |
| P-29 | 1.5 h | 45.1 |
| P-30 | 1.5 h | 46.6 |

**Total:** ~46.6 hours = ~6 person-days of work (or 2-3 days with parallel subagents).

---

## Recommended execution order (priority-ranked)

**Today, before Monday bakery opens (P0 blockers — ~2 hours):**
- P-17 `/reorder` broken Jinja template (M)
- P-14 `/produccion` 500 crash (S)
- P-26 `/reportes/margenes` 500 crash (S)
- P-24 `/reportes/cierre-mensual` label fix (S)

**This week (P1 visible-quality fixes — ~6 hours):**
- P-01 `/login` sidebar hide, demo pre-fill, button overlap (S)
- P-19 `/shopping-list` column + Spanish text (M)
- P-20 `/wishlist` status column (M)
- P-22 `/dashboard` good/bad indicators + MERMA dedup (M)
- P-28 `/settings/catalog` heading fix (S)
- P-30 dead route 404s + breadcrumb (S)

**Next week (regression-test layer — ~10 hours):**
- P-03 combo getSelectedData
- P-07 cart happy path
- P-08 cart empty submit guard
- P-12 P1 negative-stock block
- P-13 stock-preview UI

**Following week (full feature coverage — ~28 hours):**
- P-02, P-04, P-05, P-06, P-09, P-10, P-11, P-15, P-16, P-18, P-25, P-29

**When data is ready (data-quality fixes — ~7 hours):**
- P-21 bank demo data cleanup
- P-23 analisis empty states
- P-25 retencion counters
- P-27 vs-mercado data

---

## Verification command (run after all 30 are done)

```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work
./.venv/bin/python -m pytest tests/ -q -p no:randomly --tb=short 2>&1 | tail -30
```

Expected: **275 passing** (245 existing + 30 new), 0 failures, 0 regressions.
