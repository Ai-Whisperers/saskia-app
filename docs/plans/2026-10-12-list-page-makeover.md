# List-page makeover — Reponer pattern everywhere

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every remaining operating list the same compact makeover as Reponer: show the task, keep every existing control one click away, and leave the calculations alone.

**Architecture:** Templates + `theme.css` only. Routers, `apply_sale()`, costing, and money math do not change. Reuse the existing Reponer / Inventario chrome (`.more-menu`, `.row-meta-details`, `.reorder-menu`) instead of a new component library. Each wave ships independently and is verified by source tests plus a browser pass.

**Tech Stack:** Jinja2 + HTMX, `app/static/theme.css`, pytest source-lock tests, Playwright only if an existing e2e selector breaks.

## Global Constraints

- Simplify visibility, never functionality (`docs/ux/redesign-prompt.md`).
- Never delete a field, action, setting, filter, calculation, or workflow.
- Never change business logic or money math to fit the layout.
- User-facing copy: Paraguayan Spanish (vos). Money: `Gs. 729.167`. Dates: DD/MM/YYYY.
- Code, logs, this plan: English.
- No new dependencies. No React/Vue/Tailwind.
- Every wave that touches `app/` or `tests/` must update `app/CHANGELOG.md`.
- A page is not done until every previously reachable control still works for the roles that could use it.
- Hide depth is one click. Labels: **Más**, **Filtros**, **Ver detalles**. No nested Más-inside-Más.

---

## Shared pattern (locked from Reponer)

Reference pages already shipped: `app/templates/reorder.html`, `app/templates/inventario.html` (toolbar only), `app/templates/productos.html` (toolbar only), `app/templates/ventas.html` (POS).

```
[Title + one-line task]
[Primary CTA]  [details.more-menu → Más]

[Search]  [details → Filtros]     ← extra lenses, export, period, advanced

[Row L1]  identity | task fields | alert | [details → Ver detalles]
          L2 inside Ver detalles: remaining columns + secondary row actions
```

CSS already in `app/static/theme.css`:

- `.more-menu` / `.more-menu__panel` — page-level secondary actions
- `.row-meta-details` — per-row disclosure (Inventario already uses `Más info`; rename to **Ver detalles**)
- `.reorder-menu` — Reponer Filtros disclosure
- `.kitchen-more` — Producción Más (unify class to `.more-menu` when touching that page)

Do not invent a new grid system. Prefer compact `<table>` columns or Reponer-style `.reorder-line` only when the page is already a board.

**Capability inventory (every wave):** before editing, list every control in the current template. After editing, grep the old hrefs, form actions, `data-testid`s, and modal ids. If one is missing, the wave is not done.

**Tests:** extend the existing source-lock tests rather than adding screenshot tests. Typical asserts: primary CTA still first, Más contains the parked links, L1 headers present, L2 summary text is `Ver detalles`, old `action=` / `href=` still in the file.

**Out of scope for every wave:** create/edit form redesign (already compact on productos/clientes/pedidos nuevo), recipe tree, costing, migrations, auth.

---

### Task 0: Capability inventory + CSS aliases

**Files:**
- Modify: `app/static/theme.css` (only if `.row-meta-details summary` needs the Ver detalles label style; otherwise skip)
- Create: this plan is the inventory; do not add a new CSS framework

**Interfaces:**
- Consumes: existing `.more-menu`, `.row-meta-details`, `.reorder-menu`
- Produces: naming contract used by Tasks 1–7 (`Más`, `Filtros`, `Ver detalles`)

- [ ] **Step 1: Confirm the three labels**

Use these strings, not synonyms:

| Slot | Label |
|------|--------|
| Page secondary | `Más` |
| Extra filters / export on list | `Filtros` |
| Per-row overflow | `Ver detalles` |

Inventario already has `Más`. Pedidos currently shows filters + CSV in a sticky rail — wrap the extra bits in `Filtros`, keep search + Pendientes/Terminados/Todos visible (those are the daily lens).

- [ ] **Step 2: Grep current labels so later waves can rename without losing hrefs**

Run:

```
rg -n "Más info|Más acciones|kitchen-more|more-menu" app/templates app/static/theme.css
```

Expected: hits in `inventario.html`, `reorder.html`, `productos.html`, `produccion.html`, `theme.css`.

- [ ] **Step 3: Do not commit yet**

This task is the naming lock. First code commit is Task 1.

---

### Task 1: Inventario list

**Files:**
- Modify: `app/templates/inventario.html`
- Modify: `app/static/theme.css` only if the compact row overflow needs a helper (prefer existing `.row-meta-details`)
- Modify: `tests/test_SASKIA-305_inventario_produccion.py` (keep bulk-fill modal + filter toolbar asserts)
- Modify: `tests/test_table_wrap_regression.py` if the wrap class moves
- Modify: `app/CHANGELOG.md`

**Question this page answers:** what is low, what does it cost, what is the alert?

**L1 (always visible):**

| Column | Source today |
|--------|----------------|
| Nombre (link to `/inventario/{id}`) | existing first cell, keep allergens as a compact pill if already on the name |
| Stock actual + unit | `effective_stock_qty` / `i.stock_qty` |
| Precio compra (Gs.) | `i.purchase_price_gs` via `m.gs_full` |
| Estado / alert | `m.stock_badge(...)` |

Primary CTA stays **Nuevo ingrediente**.

**Más (already exists — do not reorder out of Más):**

- Ver mermas/ajustes → `/merma`
- Exportá CSV → `/inventario/export.csv`
- Llenar a 2× mínimo → existing `<dialog id="bulk-fill-modal">` + POST `/inventario/bulk-fill-to-2x-min`

**Ver detalles (move out of the wide row):**

- Proveedor
- Unidad (if not already next to stock)
- Recibir (quick-receipt form, `data-testid="quick-receipt-{{ i.id }}"` must survive)
- Variantes + gestionar / + variante
- Valor (stock × price) — display only, same Jinja
- Stock mínimo
- Price 90d strip + vs mercado badge
- Más info tags (subcategory, role, dietary, storage) — merge into this disclosure
- Row actions: merma modal, detalle link, ajustar modal

KPI strip, filter toolbar, suspicious-price / duplicate / tag-audit banners stay on the page. They are operational alerts, not secondary chrome.

- [ ] **Step 1: Inventory grep**

Confirm these strings still exist after the edit: `bulk-fill-modal`, `quick-receipt-`, `openMermaModal`, `openAdjustModal`, `/inventario/bulk-fill-to-2x-min`, `name="categoria"`, `name="estado"`, `name="alergeno"`.

- [ ] **Step 2: Collapse the `<thead>` to L1 + Ver detalles**

Keep sort links for name, stock, price. Sorting that lived on a parked column (valor, min stock) stays reachable: put the same `m.sort_th(...)` inside Ver detalles or keep a sort control in Filtros. Do not drop a sort key.

- [ ] **Step 3: Update source tests**

`tests/test_SASKIA-305_inventario_produccion.py` must still find the bulk-fill dialog and the filter names. Add:

```python
def test_inventario_row_has_ver_detalles_disclosure():
    src = TEMPLATES.joinpath("inventario.html").read_text()
    assert "Ver detalles" in src
    assert "Nuevo ingrediente" in src
    assert src.find("Nuevo ingrediente") < src.find("Llenar a 2× mínimo")
```

- [ ] **Step 4: Run**

```
uv run pytest tests/test_SASKIA-305_inventario_produccion.py tests/test_table_wrap_regression.py -q
```

Expected: PASS.

- [ ] **Step 5: Browser**

Open `/inventario`. Confirm Nuevo ingrediente is the orange button, Más still has export / mermas / llenar, a low-stock row shows stock + cost + badge, Recibir still posts after opening Ver detalles.

- [ ] **Step 6: CHANGELOG + commit**

`app/CHANGELOG.md` entry: Inventario list row is stock, cost, and alert; remaining columns under Ver detalles.

---

### Task 2: Producción day plan

**Files:**
- Modify: `app/templates/produccion.html` (day view table + header tools)
- Modify: `app/CHANGELOG.md`
- Test: extend `tests/test_SASKIA-305_inventario_produccion.py` or the existing produccion template tests (grep `produccion.html` in `tests/`)

**Question:** what do I make, how much, and is it done?

**L1:**

| Column | Today |
|--------|--------|
| Listo (checkbox) | existing first column — this IS the status action |
| Producto | |
| Lote final / Meta (how much) | `lote` / `meta` — keep the number the baker uses to mix |
| Hecho (status) | |

Day / Semana / Mes tabs and day-nav stay L1 (that is how they pick the plan).

**Más (`details.kitchen-more` → unify to `more-menu`):**

Already inside Más: Producción de mañana, Precisión histórica, Imprimir, Copiar plan, CSV, Hoja en blanco, Prep semanal.

Move in:

- HACCP (`/produccion/haccp?for_date=...`) plus the existing temperature banner/nudge — if `haccp_alert == 'warning'`, keep a one-line warning on L1 and put the form/link in Más
- Weekly template load (`/produccion/template/load-day`) — currently a `kitchen-nudge` details; park it in Más as **Plantilla semanal**
- Shopping-list handoff (`/produccion/prep` is already there; also any “lista de compras” / reorder link on this page)

**Ver detalles per product row:**

- Dificultad, Demanda, Pedidos, Receta, Costo / Margen, Sobrante, Cierre
- Any row-level print / override / notes controls currently in extra `<th>`s

Do not change `fmt_qty`, lote math, forecast, or HACCP recording.

Week and month grids are already compact calendars. Only collapse extra chrome around them (print/CSV already in Más). Do not flatten the week grid.

- [ ] **Step 1: Capability grep**

Must survive: `/produccion/print`, `/produccion/export.csv`, `/produccion/copy-last-week`, `/produccion/template/load-day`, `/produccion/haccp`, `/produccion/prep`, `/produccion/manana`, `/produccion/accuracy`, `name="hecho"` / listo checkbox.

- [ ] **Step 2: Collapse day `<thead>` (~line 852) to Listo / Producto / Lote / Hecho + Ver detalles**

- [ ] **Step 3: Tests + CHANGELOG + browser on `/produccion`**

Mark a row listo. Open Más → Imprimir and HACCP. Open Ver detalles → receta + margen still there.

---

### Task 3: Pedidos list + board

**Files:**
- Modify: `app/templates/pedidos.html`
- Modify: `app/templates/pedido_board.html`
- Modify: `app/CHANGELOG.md`
- Test: `tests/test_table_wrap_regression.py`; any `test_*pedido*` that asserts column headers

**Question (list):** who, when, and what is the next status?

**L1 list:**

| Column | Today |
|--------|--------|
| checkbox (pending only) | keep — bulk fulfill/cancel is the next action |
| Cliente | |
| Fecha prometida | |
| Estado + next-status control (the existing status action buttons) | currently split across Estado + Acciones — keep the **next** button on L1 |

Primary CTA **Nuevo pedido** stays top-right. Do not move it into Más.

**Filtros (`details` wrapping the extra rail):**

- Period chips (Hoy / Mañana, Esta semana, Pendientes viejos)
- Exportar CSV
- Keep search + Pendientes / Terminados / Todos visible (daily lens, same as Reponer urgency chips)

**Ver detalles:**

- Canal, Pago, Líneas, Total
- Secondary actions that are not the next status (enlace, cancel if next-status is fulfill, etc.)
- Bulk bar stays as-is (appears when a checkbox is ticked)

**Board (`pedido_board.html`):**

L1 on each card: customer name, promised time, status column (already a kanban). Park sound toggle, a-tiempo/atrasados extra filters, and revenue strip details one click away if they compete with the columns. Do not remove auto-refresh, chime, or column moves.

- [ ] **Step 1: Keep `data-period`, `data-status`, `#bulk-pedidos-actions`, `#pedidos-search`**

Client-side period filtering must keep working.

- [ ] **Step 2: Tests + browser**

`/pedidos` — Nuevo pedido first, open Filtros → CSV, advance one pedido status. `/pedidos/board` — three columns still move cards.

---

### Task 4: Productos + Clientes lists

**Files:**
- Modify: `app/templates/productos.html`
- Modify: `app/templates/clientes.html`
- Modify: `tests/test_SASKIA-304_clientes_productos.py`
- Modify: `app/CHANGELOG.md`

Create/edit forms stay as they are.

#### Productos

**Question:** what is it and what does it sell for?

**L1:** Nombre (+ thumb), Precio venta, Disp. (or margen badge if that is the alert), primary row link **Editar**.

**Más (already has import/export):** add **duplicates** if a duplicates entry exists on this page; keep Importar CSV / Exportar CSV inside Más (test `test_SASKIA-304` forbids a duplicate Importar button in the header).

**Ver detalles:** SKU, Porción, Mayorista, Receta, Costo, Margen, Margen %, Prime Cost, % Costo, Costo act., Producido, remaining row actions, bulk-select still on L1 checkbox.

Filter toolbar stays (tag, category, margen, disponibilidad, receta). If it feels tall, wrap the popovers except search in **Filtros**.

#### Clientes

**Question:** who is this and where are they in the program?

**L1:** Nombre, Teléfono, Nivel (or Puntos — pick Nivel as the alert), **Nuevo cliente** primary.

**Más:** Exportar CSV, Ver duplicados (currently a sibling of Nuevo — move duplicados into Más).

**Ver detalles:** Visitas, Gasto total, Puntos (if not L1), Última compra, Sub · Ped, Registrado, row actions including `+ Pedido` shortcut (must remain reachable).

- [ ] **Step 1: Update `tests/test_SASKIA-304_clientes_productos.py`**

Keep: no duplicate Importar CSV, full filter toolbar names still in the file, `data-testid="link-duplicados"` still in `clientes.html` (it can live inside Más).

- [ ] **Step 2: Browser**

`/productos` — Nuevo producto first, Más → import/export, Ver detalles → margen %. `/clientes` — Nuevo cliente first, Más → duplicados + CSV, `+ Pedido` still works from Ver detalles.

---

### Task 5: Ventas historial, sale detail, Express

**Files:**
- Modify: `app/templates/ventas_historial.html`
- Modify: `app/templates/ventas_detalle.html`
- Modify: `app/templates/ventas_express.html`
- Modify: `app/CHANGELOG.md`
- POS `/ventas` is done — do not reopen unless a selector breaks.

#### Historial

**Question:** what sold, for how much, when?

**L1:** Fecha, Producto, Total (Gs.), Acciones (Ver / void if that is the cashier next step).

**Filtros:** wrap product combo, days, channel, CSV export. Keep search visible.

**Ver detalles:** Cant., Unit., Cliente, Pago, Canal, Atendido por, Notas.

KPI cards (activas / recaudado / ticket promedio) stay — they are the answer, not chrome.

#### Detalle

**Question:** can I explain this ticket?

L1: total, product + qty, voided pill, **Ver recibo imprimible**.

Put Pago y canal, notes, stock-move table, helpdesk fields in **Ver detalles** / a details block. Do not drop void or reprint.

#### Express

**Question:** tap and charge.

Keep the card grid. L1 per card: name, price, qty, **Cobrar**. Park “Volver al POS” as a ghost link (already). Do not add Más unless a new secondary control appears. Confirm dialog stays.

- [ ] **Step 1: Preserve `action="/ventas/nueva"`, void hrefs, `/ventas/{id}/recibo`**

- [ ] **Step 2: Browser**

Historial filter + CSV from Filtros. Open a sale → recibo. Express Cobrar still posts efectivo qty=1.

---

### Task 6: Proveedores, movimientos, caja Z, banco, fiado

**Files:**
- Modify: `app/templates/suppliers.html`
- Modify: `app/templates/inventario_movimientos.html`
- Modify: `app/templates/caja_z.html` and `app/templates/caja.html` if the recent-sessions table is the noisy part
- Modify: `app/templates/bank.html`
- Modify: `app/templates/fiado.html` (and `fiado_cliente.html` only if the ledger table is a wall of columns)
- Modify: `app/CHANGELOG.md`

Do this wave only after daily lists (Tasks 1–5). Same compact row + disclosure. Open/close caja math stays.

| Page | L1 | Más / Filtros | Ver detalles |
|------|----|---------------|--------------|
| Proveedores | Nombre, Teléfono, **Nuevo proveedor** | import/export if any | Contacto, Email, RUC, Ingredientes, Ver precios, Ordenar, Editar, Desactivar/Reactivar |
| Movimientos | Fecha, Tipo, Cantidad | type/date filters | Balance antes/después, Motivo, Referencia, Operador |
| Caja | Open/close form is L1 (the task) | — | Sesiones recientes: Apertura, Esperado, Contado, Diferencia, ticket Z link under Ver detalles |
| Banco | Fecha, Importe, Conciliación | category filter, add-tx already in details | Cuenta, Categoría, Contraparte, Descripción |
| Fiado | Cliente, Saldo, Estado | nuevo / export | Límite, row actions |

- [ ] **Step 1: Do not touch POST handlers** (`/suppliers/{id}/eliminar`, `/caja/cerrar`, fiado pago)

- [ ] **Step 2: Browser each URL**

`/suppliers`, ingredient movimientos, `/caja`, `/bank`, `/fiado`. Confirm deactivate supplier, close caja, register a pago still work from the disclosure.

---

### Task 7: Dashboard, ajustes, reports (last)

**Files:**
- Modify: `app/templates/inicio.html` (operator dashboard) and/or `app/templates/dashboard.html` (gerencia)
- Modify: `app/templates/settings.html`
- Modify: `app/templates/reportes.html` plus only the report templates whose header is a wall of export+compare (start with `reportes_diario.html` and `reportes_comparacion.html`)
- Modify: `app/CHANGELOG.md`

**Rule:** one question per screen. Export and comparison stay one click away.

| Screen | One question | L1 | One click away |
|--------|--------------|----|----------------|
| Inicio | What needs me today? | Greeting, Hoy KPIs, critical alerts, Registrar venta | Historial, producción de mañana, ranking tables, forecast |
| Dashboard | How is the business this month? | Channel revenue + ops alerts | Deeper tables |
| Ajustes | What am I changing? | Search + the active tab’s required fields | Other tabs already exist — keep them; park demo-data and rare fiscal extras in a details on that tab |
| Reportes index | Which report? | The card grid (already) | — |
| Diario / comparación | What happened in this period? | The headline numbers | Export PDF/CSV, comparison controls |

Do not remove a report card. Do not merge report routes.

- [ ] **Step 1: Inventory report `href`s from `reportes.html` loop — all must remain**

- [ ] **Step 2: Browser `/`, `/dashboard`, `/settings`, `/reportes`**

Export still downloads. Comparison still compares. Settings save still posts.

---

## Suggested PR shape

One PR per task (1–7), not one mega-PR. Task 0 has no PR.

Branch names: `cursor/makeover-inventario`, `cursor/makeover-produccion`, … matching the ticket `SASKIA-NNN` if one is filed.

Each PR:

1. Template + CSS
2. Source-lock tests updated
3. `app/CHANGELOG.md`
4. Browser notes in the PR body (URL + what was clicked)

---

## Definition of done (every page)

The employee can answer:

1. Where am I?
2. What am I supposed to do here?
3. What should I do next?
4. Where can I find additional options? (Más / Filtros / Ver detalles)
5. Has my action been completed successfully?

Compare against the pre-edit inventory. If a control is gone, reopen the wave.

---

## Explicitly not in this plan

- Reponer (already the reference)
- Ventas POS counter (already done)
- Productos/clientes/pedidos **forms**
- Live KDS, WhatsApp, daily P&L (lessons-book gaps — different track)
- Money, stock-movement, or migration changes
