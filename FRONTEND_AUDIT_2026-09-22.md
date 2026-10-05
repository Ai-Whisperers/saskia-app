<!-- ROADMAP-REDIRECT -->
# ⚠️ Moved / Superseded

**This file has been moved or superseded.** The canonical location is:

> **`docs/roadmap/audits/FRONTEND_AUDIT_2026-09-22.md`**

Audit, items extracted.

See [`docs/roadmap/README.md`](docs/roadmap/README.md) for the full index.

---

<!-- ORIGINAL CONTENT BELOW -->

# Saskia RMS — Frontend Critical Audit (2026-09-22)

**Scope:** Every page, table, form, affordance, use case, and data-display gap in
the customer-facing UI of Saskia RMS (49 Jinja2 templates + 23 routers + custom
CSS/JS — no framework).

**Method:** Read every template in `app/templates/` (and `_components/`,
`errors/`) plus the data-producing routers (`dashboard.py`, `sales.py`,
`pedidos.py`, `products.py`, `inventory.py`, `recipes.py`, `reorder.py`,
`merma.py`, `reportes.py`, `customers.py`, `auditoria.py`) and the ORM models in
`app/rms/models.py`. Cross-checked every field that's stored against every
field that's displayed.

**Bottom line:** Saskia RMS has 49 templates wired up against ~25 entities, but
the data-display layer is wildly uneven. Most lists are bare bones; the data
model is rich enough to compute things (margin, food cost, channel mix,
time-of-day peaks, churn, supplier price trend) but most of it never reaches
the operator. The POS, pedidos board, merma, and reorder flows are the most
mature; the dashboard, products, inventario, and clientes lists are the most
under-developed.

---

## A. Page-by-page inventory

For every template: what it shows, what fields the model has but the page
doesn't show, what aggregations exist but aren't surfaced, what click-paths
are missing.

### A.1 `inicio.html` (Dashboard) — `app/templates/inicio.html:1`

**What it shows:**
- Period chips: today / week / month + custom date range form (lines 22-34)
- 3 metric cards: ventas / COGS / margen + delta pills vs. previous period
  (lines 36-53)
- Chart row: hourly sales chart, 30-day line, payment-method donut, top
  products, low-stock alert card (lines 55-61)
- Product ranking table by margin (lines 65-93)
- Avisos: stock bajo / receta sin costo / venta sin receta (lines 96-120)
- "Inteligencia (E26-E34)" cards: inventory capital, peak hour, peak DOW,
  food cost % (lines 122-147)
- Insight cards: stars, dogs, low-stock, rising, price-fluctuation, churning
  products, production-for-tomorrow (lines 149-203)

**What the model has but the page doesn't show:**
- `Sale.tz` (timezone per sale, `models.py:231`) — never displayed even though
  Asunción is the assumed default; no visible TZ toggle or indicator
- `Sale.channel` per-sale (models.py:238) — shown as aggregate on the donut
  chart (inicio.html:58) but no per-day or per-hour channel breakdown
- `Sale.discount_gs` (models.py:228) — gross vs net revenue is not split.
  Ventas metric is gross only — net (after discounts) never appears
- `Ingredient.last_consumed_at` (models.py:71) — never surfaced. "Slow-moving
  ingredients" insight is missing
- `Ingredient.shelf_life_days` (models.py:76) — never surfaced. No expiry
  alerts
- `Ingredient.lead_time_days` (models.py:84) — never surfaced
- `Ingredient.allergens` / `dietary_tags` (models.py:82-83) — never surfaced
  anywhere in the UI
- `Ingredient.subcategory` / `role` (models.py:80-81) — never surfaced
- `Recipe.difficulty` (models.py:125) — never surfaced
- `Sale.voided_at` counts: dashboard ventas include voided-or-not?
  (dashboard.py:117-138 computes on all sales without filtering voided) — see
  "data quality bugs" below
- `Customer.tier` / loyalty points — no dashboard tile for "loyal customers
  today" or "top spender this week"
- `SaleStockMove` — the bridge between Sale and Ingredient is computed but the
  dashboard never shows "which ingredients were drained today"
- Hourly chart is built but only shows current period (inicio.html:56 via
  dashboard.py:336-364); no weekday vs weekend overlay
- "Plan accuracy" — `ProductionCompletion` row exists in the DB; insight says
  "you over-baked muffins 30% of the time this month" but only
  `insights.production_tomorrow` is shown, not `accuracy` / `over_bake_ratio`

**Aggregations the router computes but doesn't pass to the template:**
- `dow_buckets` (dashboard.py:287) — weekday heatmap is computed, never
  rendered in the template (variable exists but no chart consumes it)
- `turnover` (dashboard.py:288-296) — stock turnover for top-8 ingredients is
  computed, never rendered
- `top_margin` (dashboard.py:297) — top 5 by margin, distinct from
  `top_products_revenue`, never rendered
- `concentration` (dashboard.py:298) — "80% of cost in these 5 ingredients",
  never rendered
- `erosion_alerts` (dashboard.py:299) — margin erosion alerts, never rendered
- `complexity` (dashboard.py:300) — recipe complexity ranking, never rendered

**Next-click options:**
- Only "Registrar venta" button (inicio.html:92) and chart hover

**Missing drilldowns:**
- Click on hourly chart → list of sales in that hour
- Click on top product → product detail or its recipe
- Click on stock-low alert → ingredient detail with quick-restock CTA
- Click on star/dog/rising → product detail filtered by status
- Click on peak-hour → production calendar for that hour
- No link from any insight card to the underlying data

### A.2 `ventas.html` (POS + sales history) — `app/templates/ventas.html:1`

**What it shows:**
- Quick-sell grid: top 5 products by 14d revenue, with name/price/stock badge
  (lines 22-47)
- "Escanear SKU" autocomplete from `/ventas/buscar` (lines 56-64, JS
  lines 289-320)
- New-sale form: SKU, product select, qty, sold_at, customer picker (full
  modal), channel, payment_method, discount, notes (lines 49-129)
- Totals card: ventas activas count, total recaudado, ticket promedio
  (lines 132-162)
- History table: fecha / producto / qty / unit / total / cliente / pago /
  estado / actions. Filter by q (search), product_id, days (lines 164-184,
  186-259)

**Model fields shown:**
- All Sale scalar fields are surfaced (id, sold_at, qty, unit_price_gs,
  channel, payment_method, discount_gs, voided_at) via the `_decorated`
  helper (sales.py:35-54)

**What the model has but the page doesn't show:**
- `Sale.notes` is rendered in detail/recibo (recibo.html:75) but the history
  list shows neither the icon-with-tooltip nor a truncated version — operator
  must click "Recibo" to see it
- `Sale.id` is hidden (column 1 has the date as link, not the ID — see
  ventas.html:204)
- No operator / "created_by" attribution — though sales router currently
  doesn't track this on Sale (only `audit_log` has it). Could pull from
  audit_log
- No "channel" column in the history — even though `Sale.channel` exists and
  is settable on the form (ventas.html:91-98). Operators can't filter or
  compare channels from the list
- No link to the customer detail page from the history (ventas.html:213-220
  shows the phone but it's not a link to `/clientes/{id}`)
- No "duplicate this sale" button (pedidos have it at pedido_detalle.html:170
  but sales don't)

**Next-click options that exist:**
- "Recibo" link opens `/ventas/{id}/recibo` (ventas.html:231)
- "Anular" button uses `SaskiaConfirmModal` (ventas.html:236-240)

**Missing affordances:**
- No bulk-void (e.g., "I made 6 muffins as the wrong size — void all 6")
- No "edit sale" — typos can't be fixed, only voided
- No inline edit
- No filter by `payment_method` or `channel` on the history (only product +
  days + free text)
- No "what changed" / audit-trail on the sale (e.g., who voided it, when,
  why)
- The totals card says "Filtro actual: {filters}" (ventas.html:149) but
  doesn't show breakdown by channel/method

### A.3 `productos.html` (Product list) — `app/templates/productos.html:1`

**What it shows:**
- Filter by `q` (name search) and `has_recipe` (yes/no) (lines 27-39)
- Column-visibility toggle (lines 41-47, 156-163, 210-220)
- Bulk-delete bar with checkbox per row + "Eliminar seleccionados"
  (lines 49-55, 167-208)
- Table columns: checkbox / name (with "muerto" badge for never-sold) / SKU
  with copy-to-clipboard / Porción / Precio venta (sortable) / Receta /
  Costo (sortable) / Margen (sortable) / Margen % / Disp. badge / Edit
  (lines 58-115)
- Pagination 50/page with sort links that preserve filter state (lines
  118-141)
- Empty state with CTA (lines 143-153)

**Model fields shown:**
- Product.name, sku, portion_label, sale_price_gs, recipe_id, is_available
- Decorated: cost_gs, margin_gs, margin_ratio, recipe_name, is_dead

**What the model has but the page doesn't show:**
- `Product.category` (models.py:200) — has its own form field (producto_form.html:23)
  but the LIST doesn't show or filter by category
- `Product.tags` (models.py:201) — comma-separated, has its own form field
  (producto_form.html:30-35) but the LIST shows neither column nor filter
- `Product.image_url` (models.py:199) — has form input but no thumbnail in
  list
- `Product.notes` — exists on form (producto_form.html:74) but no column in
  list. Even a tooltip would help
- The dead-product badge (productos.html:83) is good, but there's no
  "last-sold-at" column to see WHEN the live ones last moved

**What's missing:**
- No filter by availability (all / live only / hidden only)
- No filter by category
- No filter by tags
- No "last 30d units sold" column (would help rank by velocity)
- No "low stock" indicator on the product itself (only ingredientes
  show min/max)
- No "duplicate" button (pedidos have it at pedido_detalle.html:170)
- No "view" link to product detail page — only Edit. There's no
  `/productos/{id}` detail page at all
- The bulk action is **only delete**. No bulk-edit-price, no bulk-toggle
  availability

### A.4 `inventario.html` (Inventory list) — `app/templates/inventario.html:1`

**What it shows:**
- "Nuevo ingrediente" + "Exportar CSV" buttons (lines 20-29)
- Table: name (linked to detail) / unit / stock_qty / min_stock_qty /
  purchase_price (with 90d min/max + sparkline SVG if ≥3 events) /
  Estado badge / actions (Ajustar / Editar / Movimientos) (lines 31-80)
- Stock-adjust modal with negative-stock warning (lines 121-202)
- Pagination 50/page (lines 83-106)

**Model fields shown:**
- Ingredient.name, unit, stock_qty, min_stock_qty, purchase_price_gs,
  category
- Computed: price_info (90d min/max/sparkline)

**What the model has but the page doesn't show:**
- `Ingredient.category` shown as a badge (inventario.html:49) but not used as
  a filter; same issue as productos
- `Ingredient.subcategory` / `role` / `allergens` / `dietary_tags` —
  nowhere in UI
- `Ingredient.max_stock_qty` (models.py:75) — never displayed (used internally
  for reorder suggestion in `compute_reorder_list` but not surfaced)
- `Ingredient.shelf_life_days` — never shown. No expiry alert
- `Ingredient.lead_time_days` — never shown
- `Ingredient.opening_stock_qty` / `opening_stock_date` (models.py:89-90) —
  shown on detail page (ingrediente_detalle.html:62-70) but not list
- `Ingredient.reorder_point` (models.py:91) — shown on detail, not list
- `Ingredient.last_consumed_at` (models.py:71) — never surfaced. Could give
  "slow-moving" or "stale" warnings
- No link to the supplier from the ingredient row
- No "supplier_name" column even though the FK exists and `Supplier.ingredients`
  is populated (models.py:100)

**Missing affordances:**
- No filter by `category`
- No filter by supplier
- No filter by "stock state" (low / out / overstocked / has-price / no-price)
- No bulk-restock (pedidos have bulk fulfill but no bulk reorder)
- No bulk-edit-min
- Stock-adjust modal: confirm_negative is a click-twice pattern (good — keep)
  but no equivalent for big adjustments (>50% change) which might be typos

### A.5 `recetas.html` (Recipes list) — `app/templates/recetas.html:1`

**What it shows:**
- "Nueva receta" button (lines 9-14)
- Filter: search `q` + ingredient dropdown (lines 17-35)
- Table: name (linked to detail, with family badge) / yield_qty+unit / line
  count / batch_cost / unit_cost / Edit (lines 38-89)
- Empty state with CTA (lines 95-105)

**Model fields shown:**
- Recipe.name, yield_qty, yield_unit, lines count, batch_cost, unit_cost,
  family

**What the model has but the page doesn't show:**
- `Recipe.prep_minutes` / `cook_minutes` (models.py:123-124) — shown on detail
  and edit form (receta_form.html:88-95) but not list. Total time would be a
  useful sort column
- `Recipe.difficulty` (models.py:125) — never surfaced anywhere
- `Recipe.dietary_tags` — never surfaced in list (form has it at
  receta_form.html:99-101)
- `Recipe.notes` — never shown on list (only detail)
- `Recipe.products` (back-ref) — count or names not on list. Useful for "this
  recipe feeds these N products"

**Missing affordances:**
- No "duplicate recipe" button
- No "export to Excel" button (productos and inventario have one)
- No filter by `family` or by `dietary_tags`
- No bulk actions
- No sort by total-time (prep + cook)
- No link to the products that use this recipe (detail does have it at
  receta_detalle.html:128-140)

### A.6 `pedidos.html` (Orders list) — `app/templates/pedidos.html:1`

**What it shows:**
- Status filter chips: Pendientes / Terminados / Todos (lines 25-37)
- Search by customer name/phone (lines 41-50) + CSV export (lines 52-56)
- Three sections: "Hoy/Mañana", "Esta semana", "Pendientes viejos" (lines
  59-183) — each with a table:
  - Checkbox (only pending), Cliente (with 30d spend), Fecha/hora, Canal,
    Líneas count, Total Gs., Estado badge, Edad (today/tomorrow/+Nd/atrasado),
    Ver button
- Bulk fulfill / bulk cancel (lines 82-92, JS 207-235)

**Model fields shown:**
- pedido.id, customer_name, customer_phone, promised_date, promised_time,
  channel (normalized display), n_lines, total_gs, status, age_days,
  spend_30d_gs

**What the model has but the page doesn't show:**
- `Pedido.notes` — not in the row (only on detail at pedido_detalle.html:80)
- `Pedido.payment_intent` — not in the row
- `Pedido.created_at` — not visible (used in board.html:122 for elapsed time
  but not list)
- `Pedido.fulfilled_sale_id` — exists but not surfaced (you can navigate via
  the "Recibo" link in detail pedido_detalle.html:178)
- `Pedido.cancel_reason` — only on detail (pedido_detalle.html:83)
- No "items" preview (what's in the pedido) — must click Ver
- No link to customer detail (just phone shown)

**Missing affordances:**
- No way to filter by `channel` (could be useful — "show me all
  PedidosYa orders")
- No way to filter by date range
- No "today's pickups" dedicated view (the "Hoy/Mañana" section splits it but
  no "ready for pickup now" filter)
- No "draft" state — once created, a pedido is permanent until fulfilled
  or cancelled
- No edit-pickup-time (pedidos don't have an inline editor)

### A.7 `pedido_detalle.html` (Order detail) — `app/templates/pedido_detalle.html:1`

**What it shows:**
- Status badge + ID (lines 7-16)
- Cliente + 30d spend card (lines 19-28)
- Prometido card (date, time, channel, payment intent) (lines 30-39)
- Ítems table: product, qty, unit_price, subtotal, fulfilled_qty (lines
  41-85)
- Public link for WhatsApp (lines 87-99)
- Actions: stock-preview / fulfill / cancel / confirm / ready / duplicate /
  recibo (lines 101-187)

**What the model has but the page doesn't show:**
- `Pedido.created_at` — not shown (but visible in pedido_board via elapsed
  time)
- `Pedido.updated_at` — not shown
- No link from "Cliente" to `/clientes/{id}` (just shows name/phone)

**Missing affordances:**
- No "edit lines" — must duplicate + cancel
- No "send WhatsApp reminder" button (the public link exists at line 94 but
  no "send via WhatsApp" CTA)
- No "view receipt PDF" of the public page
- Cancel modal (lines 132-144) requires cancel_reason but the audit log
  entry is per state transition, not visible here

### A.8 `pedido_board.html` (Kitchen display) — `app/templates/pedido_board.html:1`

**What it shows:**
- Auto-refresh every 30s (line 6)
- Chime on page load (line 84-93)
- Three groups: Hoy / Mañana / Esta semana, each card showing: ID, status,
  notes header, promise date/time/channel, customer name, items list with
  qty+name+line notes, elapsed-minutes (lines 101-159)

**Model fields used:**
- pedido.promised_date, promised_time, status, customer.name, lines,
  product.name, line.notes, created_at (for elapsed), notes

**What the model has but the page doesn't show:**
- `Pedido.total_gs` — never displayed on the board (you can see the lines
  but no total). Critical for a board when fulfilling
- `Pedido.payment_intent` — not on the board (cashier doesn't know if it's
  paid or owed)
- `Pedido.customer_phone` — not visible (you'd need it to call the
  customer if items are missing)
- `line.fulfilled_qty` — not on the board (you don't see "this order is
  partially done")
- No click-to-open detail (must navigate away from board)
- No on-board status change (no "✓ Listo" button on the card itself — must
  go to detail)

**Missing affordances:**
- No printer-friendly layout (it's already dark-theme + big text, OK)
- No sound for "approaching" orders (only fires on page load)
- No way to filter to "only pending" or "only ready"
- No sort within group

### A.9 `pedidos_nuevo.html` (New order) — `app/templates/pedidos_nuevo.html:1`

**What it shows:**
- Customer name (with autocomplete datalist from `/customers/api/search`),
  customer_id fallback, phone (lines 13-37)
- promised_date (defaults to today) + promised_time (lines 39-48)
- channel (defaults whatsapp) + payment_intent (defaults efectivo) (lines
  50-67)
- notes (lines 69-73)
- Items table with add/remove buttons, auto-fill price from product select
  (lines 75-126)

**Missing affordances:**
- No "duplicate previous order for this customer" (would be a one-tap upsell
  for repeat customers)
- No stock-preview here — stock check only happens on `/stock-preview` after
  creation
- No suggested-qty based on past sales
- No way to attach to an existing pedido (combine two pickups)
- The "Cliente existente" select + the "Customer name" autocomplete are
  redundant — operator can do either, but the autocomplete silently
  hijacks both (line 209). Should be one or the other

### A.10 `merma.html` (Waste log) — `app/templates/merma.html:1`

**What it shows:**
- Date presets (7/30/90) + custom date range + reason filter (lines 11-29)
- Whole-batch recipe waste form (lines 37-83)
- Per-ingredient waste form with unit conversion (lines 85-132)
- Summary: total cost, events count, % of revenue, top 10 ingredients with
  ASCII bar chart, by-reason breakdown (lines 134-203)
- Events table: fecha, ingrediente, qty, motivo, cost (lines 205-233)

**Model fields shown:**
- WasteLog.recorded_at, ingredient.name, qty, reason, cost_gs
- Computed: total_cost_gs, n_events, top_ingredients, by_reason, pct of
  revenue

**What the model has but the page doesn't show:**
- `WasteLog.notes` — captured at form (merma.html:71) and stored (per
  merma.py router) but the events table doesn't display it (line 209-217)
- `WasteLog.reference_type` / `reference_id` — exists (per model) but never
  surfaced. For batch waste there's no link to the production batch
- No link from the top-ingredient chart to `/inventario/{id}` to see the
  stock movements that day
- No "compare to last period" — merma today vs same window last week

**Missing affordances:**
- No bulk-edit / no undo
- No export to CSV
- No "what changed" when a recipe batch was logged — operator types qty of
  lost batches but no confirmation of what those batches were worth
- No autocomplete on ingredient — typing "harina" doesn't surface
  "Harina 0000", "Harina leudante", etc.

### A.11 `eod.html` (Daily close checklist) — `app/templates/eod.html:1`

**What it shows:**
- Progress bar (done / total) + "Listo para cerrar" badge (lines 9-19)
- Checklist of items rendered from `items` loop (lines 22-52) — text-only,
  no descriptions, no link-out
- "Notas para el turno siguiente" textarea (lines 43-47)
- "Reposición" section: count of ingredients under minimum + table with
  name / sugerido / costo est., link to /reorder (lines 55-113)
- "Producción del día" section: table with product / plan / hecho (with
  input form to record completion qty), delta display (lines 115-172)

**Model fields shown:**
- items[]: key, label, status, help
- reorder_items[]: name, suggested_qty, unit, has_price, estimated_cost_gs
- today_plan.rows[]: product_name, qty_to_produce
- completions[]: completed_qty

**What the model has but the page doesn't show:**
- `saved_notes` is filled in (line 46) but the items loop (lines 31-39)
  doesn't show whether the close was saved before, who saved it, when
- No "yesterday's close" notes surfaced (the textarea persists but there's
  no banner "Hoy leíste: mañana llega pedido de harina")
- The plan-vs-hecho delta is shown (lines 152-160) but no aggregated metric
  ("accuracy: 87% — over-baked 3 products by 12% on avg")
- The items list is computed by `eod` router; checklist semantics is opaque
  from the template (no `help` for many items)

**Missing affordances:**
- No "previous close" link
- No export to PDF (the daily summary report at /reportes/diario does have
  PDF export)
- No "email me the close summary" button
- No signature/timestamp on the saved close (audit log captures it but no
  badge on the page)
- The ProductionCompletion form (lines 142-150) is inline per-row but
  there's no bulk "all done" submit

### A.12 `reportes.html` (Reports hub) — `app/templates/reportes.html:1`

**What it shows:**
- 10 report cards (IVA, Libro Ventas, Diario, Comparación, Top productos,
  Retención, Valor pedido, Ventas hora, Métodos pago, Precios) (lines 11-25)

**Missing affordances:**
- No "favoritos" / "recently viewed"
- No subscription/email-schedule
- No way to compare two reports side by side

### A.13 Sub-reports (each is a thin template — `reportes_*.html`)

**`reportes_diario.html` (1 page)** — 6 metric cards: ingresos, IVA, COGS,
gastos, ventas, margen bruto. Date picker. PDF export. **No breakdown
of where the sales came from** (by channel, by payment method, by product
top-5).

**`reportes_iva.html`** — monthly rows + YTD cumulative. **No per-product
IVA**, no per-channel.

**`reportes_libro_ventas.html`** — chronological table with fecha/cliente/
producto/qty/base/IVA/total. SET-PDF export. **No filters by channel or
payment method.**

**`reportes_comparacion.html`** — two periods side by side: ingresos /
sales count / margin with % change. **No breakdown by category.**

**`reportes_top_productos.html`** — ranking with n_sold + revenue. **No
margin column** even though it could be computed.

**`reportes_retencion.html`** — total/nuevos/recurrentes 3-card view. **No
cohort analysis**, **no list of the actual customer names**.

**`reportes_ventas_hora.html`** — 24 rows with bar visualisation + peak
hour. **No comparison to yesterday/last week**.

**`reportes_metodos_pago.html`** — distribution by payment method. **No
trends over time**.

**`reportes_precios.html`** — list of ingredients with current/min/max/avg,
or detail view with events table + chart. **No supplier-grouped view**.

**`reportes_valor_pedido.html`** — AOV summary. **No per-product or
per-channel breakdown**.

### A.14 `clientes.html` (Customers list) — `app/templates/clientes.html:1`

**What it shows:**
- "Programa de puntos" header + CSV export + Nuevo cliente (lines 17-30)
- Search `q` + filter by `tier` (lines 32-45)
- Bulk-delete bar (lines 47-54)
- Table: checkbox / name / phone / n_sales (Visitas) /
  lifetime_spend_gs (Gasto total) / points (Puntos) / tier badge /
  Registrado date / Ver (lines 55-100)

**Model fields shown:**
- Customer.name, phone, n_sales, lifetime_spend_gs, points, tier, created_at

**What the model has but the page doesn't show:**
- `Customer.email`, `Customer.cedula` — not in list (only on detail at
  cliente_detalle.html:28-30). Operators can't search by CI/RUC
- `Customer.notes` — not in list. Could surface as a tooltip
- `Customer.updated_at` — not in list (vs `created_at` only)
- No "última compra" date (the detail page shows it at line 40, but the list
  doesn't — critical for re-engagement)
- No "preferred products" or "frequency" — basic RFM segmentation missing

**Missing affordances:**
- No filter by `last_purchase_before` (inactive customers — LAPSED)
- No filter by spend tier
- No bulk-tag
- No "send WhatsApp broadcast to selected" — even though the pedidos list
  has WhatsApp-link columns
- No sort by points (only by name/phone/visits/spend/points/tier, the
  th-macro has all 6 — puntos IS sortable at line 75 but no natural mapping)

### A.15 `cliente_detalle.html` (Customer detail) — `app/templates/cliente_detalle.html:1`

**What it shows:**
- Breadcrumbs (lines 5-7)
- Header with Edit (lines 16-22)
- Metadata dl: phone/email/cedula/tier/points/lifetime spend/visitas/last
  sale/registrado (lines 24-43)
- Timeline (created/last sale/updated) (lines 45-75)
- Notes section (lines 77-87)
- Purchase history table (lines 89-119)

**What the model has but the page doesn't show:**
- No "preferred product" derived from history (top 3 products by count)
- No "frequency" (avg days between purchases)
- No link to pedidos for this customer (pedidos list has a search filter
  but no customer-specific URL)
- No "loyalty points history" (the model only has `loyalty_points` as int
  — no event log)

**Missing affordances:**
- No "send WhatsApp" CTA (you have the phone but no link)
- No "create new sale for this customer" pre-filled link
- No "create pedido for this customer" pre-filled link

### A.16 `produccion.html` (Production plan) — `app/templates/produccion.html:1`

**What it shows:**
- Day / Week / Month view switch (lines 6-10)
- **Day view**: products to produce + ingredient requirements with
  "A comprar" highlighting shortfalls (lines 13-87)
- **Week view**: product × day grid + real sales + week ingredients (lines
  90-179)
- **Month view**: product × day grid + real sales + month ingredients
  + revenue (lines 183-281)

**What the model has but the page doesn't show:**
- The plan has `forecast_source` (e.g. "vendiste X últimos 14d") and the
  template shows it in source_labels (line 40) but only as text, no link
  to the underlying calculation
- "Plan vs Hecho" comparison (the model has ProductionCompletion) — only
  shown on `/eod`, not here
- No "previous week actual" overlay to compare this-week-plan vs last-week-act
- No copy-plan button (one week → next week)
- No "this plan uses these ingredients at these quantities" → link to
  reorder

### A.17 `reorder.html` (Reorder page) — `app/templates/reorder.html:1`

**What it shows:**
- Total estimated cost (line 6-7)
- Bulk-select-all + "Generar pedido por WhatsApp" button (lines 11-23)
- Table: checkbox / ingredient / actual / min / max / sugerido / Urgencia
  badge / costo est. / Supplier (with WhatsApp CTA) / inline qty + price
  + Reponer button (lines 43-131)

**What the model has but the page doesn't show:**
- `Ingredient.last_consumed_at` — would help "is this ingredient actually
  moving?"
- `Ingredient.lead_time_days` — "needed in 3 days" missing
- No link to recent purchase history for this supplier
- No "what you bought this same week last month" comparison
- "Generate WhatsApp PO" opens wa.me link (reorder.py:201-219) but the link
  doesn't include supplier contact names per group unless the template uses
  `_by_supplier` (it doesn't — just one wa.me with the long text)

**Missing affordances:**
- No "save as draft" — must commit immediately
- No multi-supplier orders (one WhatsApp link per supplier would be ideal)
- No "skip this time" / snooze option for false-positives

### A.18 `auditoria.html` (Audit log) — `app/templates/auditoria.html:1`

**What it shows:**
- Filter form: action / start_date / end_date / ip / user / target_type /
  target_id + preset chips (lines 19-71)
- Data-retention prune button (lines 73-85)
- Table: fecha / usuario / accion / target / IP / user_agent_short /
  detail_pairs in `<details>` (lines 100-140)

**Model fields shown:** all of them (AuditLog is small)

**Missing affordances:**
- No "what changed on this record" — clicking target only copies ID, doesn't
  link to the record
- No export to CSV (the task description specifically calls this out)
- No filter by date range with shortcut (only presets for last week/month)
- No "frequently-used filters" save

### A.19 `suppliers.html` + `supplier_form.html` + `supplier_orders.html`

**suppliers.html**: name / contact / phone / email / ingredients-count /
Ordenar/Editar/Eliminar (lines 14-61).

**Missing:**
- No "supplier total spend YTD" column (would help negotiate)
- No "last ordered" date
- No "outstanding balance" indicator
- No link from supplier to the ingredients it supplies (only count)

**supplier_orders.html**: per-supplier order page (lines 4-83) — contact
info + WhatsApp CTA + items table. **No history of past orders**.

### A.20 `settings.html` (Settings) — `app/templates/settings.html:1`

**Tabs:** Información de negocio / Configuración fiscal / Tema y apariencia
(lines 19-23).

**System info grid** (lines 165-186) shows version/username/role/last login
but **last_login_at** is rendered as raw text without formatting (line 183 —
datetime displayed verbatim).

**Missing affordances:**
- No password change UI (only login screen at login.html)
- No notification preferences (the bell icon shows notifications but no
  settings for what generates them)
- No "two-factor" or session management
- No backup/restore config
- The fiscal tab has `timbrado`, `punto_expedicion`, `invoice_sequence` but
  no preview of how they'll look on a receipt

### A.21 Other templates

- **`recibo.html`**: receipt — shows sale data + print button. **No
  QR/link for digital receipt, no fiscal info displayed (timbrado etc.)**
- **`excel.html`**: import/export with PATCH/APPEND/FULL radio cards
  (lines 21-43). Shows import history with warnings (lines 89-137). **No
  status of current import** (just a button + "Importando…" pseudo-loader).
  **No undo of last import**.
- **`login.html`**: login. Standard.
- **`pedido_stock_preview.html`**: shows what fulfilling will consume,
  warns on short stock (lines 15-65). **No "go adjust stock first" link**.
- **`guia.html`**: user guide (not read in detail).
- **`errors/`**: error pages (not read).
- **`users.html`**: user mgmt (not read in detail).

---

## B. Cross-page data connectivity analysis

### B.1 Connections that exist

| From | To | Where the link exists |
|---|---|---|
| Product → Recipe | product edit page links recipe in dropdown (producto_form.html:52) | but only a `<select>` — no preview link |
| Recipe → Products | `receta_detalle.html:128-140` shows "Usada por productos" list with links | ✅ |
| Ingredient → Recipes | `ingrediente_detalle.html:74-97` shows "Usado en recetas" | ✅ |
| Ingredient → Movimientos | `inventario.html:72-75` (button) and `ingrediente_detalle.html:118-121` | ✅ |
| Ingredient → Supplier | `reorder.html:82-93` shows supplier + WhatsApp CTA | partial |
| Sale → Customer | `ventas.html:213-220` shows name/phone (not a link) | ❌ partial |
| Customer → Sales | `cliente_detalle.html:89-119` shows history | ✅ |
| Pedido → Customer | `pedido_detalle.html:21-27` shows name + 30d spend | ✅ but no link |
| Pedido → Sale (fulfilled) | `pedido_detalle.html:178` shows Recibo button | ✅ |
| ProductionCompletion → Production row | `/eod` form (eod.html:142-150) | ✅ |
| SaleStockMove → Sale | `inventario_movimientos.html:64` links to `/ventas/{id}/recibo` | ✅ |
| AuditLog target → record | NOT linked | ❌ |

### B.2 Connections that SHOULD exist but don't

1. **Product ← → Recipe ← → Ingredient ← → Supplier chain** — there is no
   single navigation path. To go "this product" → "its recipe" → "a key
   ingredient" → "who supplies it", the operator clicks through 3
   unrelated pages (productos → receta_detalle → ingrediente_detalle → no
   link to supplier).

2. **Sale ← → Pedido ← → Customer ← → Audit** — fulfillment creates a Sale
   from a Pedido (via `pedidos.py` `/fulfill`), and the Sale has
   `fulfilled_sale_id` reverse pointer (pedidos.py:157) but the Sale
   detail/recibo doesn't say "this came from pedido #N". And neither
   the pedido list nor detail surfaces the audit of state transitions.

3. **WasteLog ← → SaleStockMove (same ingredient, same day)** — `WasteLog`
   has `reference_type` / `reference_id` and `SaleStockMove` has them too
   (per models.py), but no UI says "you wasted 200g of crema today AND
   sold 12 items that consumed 480g of crema today" side by side.

4. **ProductionCompletion ← → SaleStockMove (planned vs actual)** — the
   ProductionCompletion table records what was made, SaleStockMove
   records what was consumed. The eod.html compares to plan, but
   "you planned 30 muffins, you made 24, you sold 22 — net: 2 leftover,
   4 over-baked" is not on any page. Plan accuracy is buried in
   `build_insights` (dashboard.py) and never rendered.

5. **PriceHistory ← → Reorder flow** — the `/reportes/precios` page
   shows 90d history. The `/reorder` page shows current price. When
   ordering, operator can't see "last month this was 8000, today is
   9200 — 15% up" inline. The sparkline (inventario.html:60) helps but
   only if you're on /inventario.

6. **Sale.tz** — set per-sale (models.py:231) but no UI says "you're
   looking at Asunción time, and your sales were made from these other
   TZs". Operators can't audit cross-TZ sales.

7. **Sale.discount_gs** — gross vs net revenue split. Dashboard ventas
   metric is gross only. No "Net after discount" tile, no
   "discounts-given-this-period" tile. The data is there.

8. **Sale.channel** — per-sale channel (mostrador/whatsapp/etc).
   Quick-sell grid doesn't break down by channel. /reportes/iva doesn't
   split by channel. /reportes/ventas-hora doesn't split by channel.
   Only the donut chart (inicio.html:58) shows aggregate.

9. **Pedido.fulfilled_sale_id → Sale → Recibo** — exists
   (pedido_detalle.html:178) but you can't go Sale → Pedido. If a sale
   came from a pedido, the operator viewing the recibo can't tell.

10. **Customer.tier → Pedidos history** — `cliente_detalle` shows the tier
    badge. But pedidos list (pedidos.html) shows `spend_30d_gs` next to
    the customer name — there's no link between these views. Going
    "this customer" → "their pedidos" requires re-searching by phone.

### B.3 The "what does Saskia see when X happens" gaps

- **"Why did stock of Y drop today?"** — there's no path. You'd have to
  open ingrediente_detalle → movimientos → scan the table for "sale"
  badges → open each recibo. Tedious.
- **"Which products contribute most to cost?"** — no page. `concentration`
  metric is computed (dashboard.py:298) but not rendered.
- **"What's our food cost ratio this week vs last week?"** — no page.
  Daily summary shows absolute COGS but not the ratio.
- **"Which customer hasn't bought in 60 days?"** — no page. Clientes
  list doesn't have a "last_purchase_at" column.
- **"Which products are about to go out of stock given yesterday's
  velocity?"** — would require forecasting query, not currently built.

---

## C. Use-case analysis — Saskia's day-to-day

### C.1 Open at 7am — check yesterday, plan today

**What Saskia wants to see:**
- Yesterday's sales total + comparison
- Today's expected prep (production plan)
- Stock that's already done (yesterday's production_completion)
- Pedidos coming in today
- Any overnight issues (failed imports, etc.)

**What the app gives:**
- `/inicio` shows ventas + COGS + margen with delta pills vs. yesterday
  ✅ (inicio.html:36-53)
- "Producción de mañana" table on inicio.html:185-203 shows what to make
- Pedidos board (`pedido_board.html`) shows today's orders grouped by
  Hoy/Mañana ✅
- Stock detail per-ingredient ✅

**Gaps:**
- No "overnight jobs" view (no scheduled tasks or import status surfaced
  beyond `import_history` at /excel)
- No "stock that arrived yesterday" — `IngredientPriceEvent` records it
  but no summary
- No "yesterday's close notes" — `eod_notes_for_next` is saved but not
  shown anywhere except the eod page itself

**Verdict:** 70% supported, 30% gaps.

### C.2 Morning prep — what's already done

**What Saskia wants:**
- "Did we make all the muffins yesterday? What's left?"
- "Who actually produced what?" (operator attribution)

**App gives:** /eod completion form (eod.html:142-150) — operator types
qty per product. Single-line input, no bulk.

**Gaps:**
- No aggregation: "you completed 87% of plan"
- No operator attribution on completion (no `created_by` on
  ProductionCompletion based on what's in the model — should check)
- No time-of-day: "made at 6am vs 11am" — production completions
  have timestamps but it's not surfaced

**Verdict:** 60% supported, 40% gaps.

### C.3 9am rush — quick sell, pedido pickups

**What Saskia wants:**
- One-tap POS (already there as quick-sell ✅)
- See pedido list, mark "ready for pickup"
- Print receipt

**App gives:**
- Quick-sell grid (ventas.html:22-47) — top 5 by revenue, F2/F3/Arrow nav
- SKU scanner with auto-fill ✅
- Pedido detail with status transitions ✅

**Gaps:**
- Pedido board doesn't show the **total** of each pedido, so when
  fulfilling you don't see "this is a 6-item, Gs. 45,000 order"
- Quick-sell grid is "top 5 by 14d revenue" — but at 9am you want "top
  products for this hour". Hour-of-day ranking is computed in
  analytics but not used for quick-sell.
- No "fulfill from board" — board.html has no transition buttons,
  must navigate to detail
- The recibo (recibo.html) doesn't show timbrado / RUC / punto_expedicion
  from /settings — operators can't include fiscal info without editing
  CSS

**Verdict:** 75% supported, 25% gaps.

### C.4 Lunch rush — same as 9am plus volumen

**App gives:** same surfaces.

**Gaps:**
- During rush, no "fast sell" beyond the 5 in quick-sell. If the top
  product for the hour is #6 overall, it's not in quick-sell
- No "void last sale" shortcut (must scroll history)
- No way to record "I gave a discount because..." other than the
  discount_gs number — no discount-reason captured

### C.5 Quiet afternoon — reorder, waste review

**What Saskia wants:**
- See which ingredients are below min (already on /reorder ✅)
- Per-supplier WhatsApp PO (already there ✅)
- See "where am I losing money" — waste summary (already on /merma ✅)
- Review price trends (already on /reportes/precios ✅)

**App gives:** all four.

**Gaps:**
- No unified "afternoon ops" page — must click around
- The reorder page doesn't show "you ordered this from supplier X last
  week, you paid 8000 — today it's 9200"
- Merma doesn't show "this ingredient also had 3 waste events last
  month — pattern?"
- No "supplier price trend" specifically — /reportes/precios is by
  ingredient, not by supplier

**Verdict:** 80% supported.

### C.6 Evening restock — actually buy, record price

**What Saskia wants:**
- Tap an ingredient from reorder, enter qty + actual price paid, save
- See updated stock

**App gives:** the inline form on /reorder (reorder.html:94-119) does
exactly this.

**Gaps:**
- The supplier field isn't selectable per-restock — uses
  Ingredient.supplier_id, which is the default. If Saskia bought from a
  different supplier, no way to record it.
- No "I bought 3 of these, not just 1" — qty field is single

**Verdict:** 85% supported.

### C.7 End of day — close checklist

**What Saskia wants:**
- Walk through the daily checklist
- Confirm production done
- See "today's P&L" snapshot
- Set notes for tomorrow

**App gives:** /eod (eod.html) with progress bar, checklist, production
form, reorder summary, notes textarea.

**Gaps:**
- No "today's P&L" tile on /eod (the daily summary at /reportes/diario
  has it but isn't linked from /eod)
- No "yesterday's notes" surfaced — operator has to remember or guess
- No "your previous close" timestamp / who closed
- "Marcar cierre del día" is the only save action — no draft state

**Verdict:** 70% supported.

### C.8 Weekly review — profitability

**What Saskia wants:**
- Which products are profitable? (Stars) — inicio.html shows ✅
- Which are losing money? (Dogs) — inicio.html shows ✅
- Trend in costs (price fluctuations) — inicio.html shows ✅
- Customer retention — /reportes/retencion ✅

**App gives:** all of these.

**Gaps:**
- /reportes/retencion shows numbers but not customer names — can't see
  WHO churned
- No "weekly margin summary" tile anywhere — daily summary exists,
  weekly doesn't
- No comparison report: "this week vs last week" with all metrics

**Verdict:** 70% supported.

### C.9 Monthly review — supplier trends, churn

**What Saskia wants:**
- Supplier price trends over months
- Customer churn cohort
- Product trends (rising/churning) — ✅ on dashboard

**App gives:**
- Rising / churning products on inicio.html:167-183 ✅
- Price fluctuations ✅ (only 30d window — no multi-month trend)
- /reportes/retencion ✅

**Gaps:**
- No multi-month trend view for prices — /reportes/precios caps at 365d
  but the chart is single-line, no comparison to baseline
- No "customer cohort" analysis (just new vs returning)
- No "supplier reliability" — late deliveries, price stability, etc.
- No supplier-level P&L (how much did we spend with each supplier this
  month)

**Verdict:** 60% supported.

### C.10 Anomaly response — "what changed today?"

**What Saskia wants:**
- "Sales dropped 30% vs. yesterday, why?"
- "Waste spiked 50%, what changed?"

**App gives:**
- /inicio has delta pills vs. previous period ✅
- /auditoria has all events ✅

**Gaps:**
- No anomaly detection (no automatic alert when sales drop >X% or waste
  spike >Y%) — operator must notice themselves
- No "cohort drill-down" — "sales dropped: was it the morning peak or
  the evening peak?" requires manual investigation
- Audit log shows raw events but no "what was the state before and
  after" diff
- No "compare today's hourly distribution to last week's" — would need
  overlay chart on /reportes/ventas-hora

**Verdict:** 40% supported.

---

## D. Table-by-table gap analysis

For each major table: what columns it shows, what the user wants to do,
what's missing, and how it compares to best-in-class.

### D.1 Productos (`productos.html:58-115`)

**Columns:** checkbox, name (with muerto badge), SKU (copy btn), Porción,
Precio venta, Receta, Costo, Margen, Margen %, Disp., Edit.

**User wants to:** find products, sort by performance, edit, identify
dead stock.

**Missing:**
- No category column (model has `Product.category`)
- No tags column (model has `Product.tags`)
- No image_url thumbnail (model has it)
- No "last sold" date
- No "30d units sold" (velocity)
- No filter by availability
- No filter by category
- No "archive" or "duplicate"
- Bulk action: ONLY delete. No bulk edit price, no bulk toggle is_available

**vs. Stripe / Linear / Notion tables:**
- Linear: every column sortable, filterable, resizable. Inline edit.
  Multi-select actions (status change, assign, tag).
- Stripe: rows are clickable to expand. Inline filters above table.
  Saved views.
- Saskia: sort by header link only on a few columns. Filter is a
  separate form above the table. No inline edit. No row expand.
  Single bulk action.

**Priority:** HIGH — this is the operator's main catalog.

### D.2 Inventario (`inventario.html:32-80`)

**Columns:** name (linked), unit, stock_qty, min_stock_qty, purchase_price
(90d min/max + sparkline if ≥3 events), Estado, actions (Ajustar, Editar,
Movimientos).

**User wants to:** monitor stock, see price trends, take action.

**Missing:**
- No supplier column
- No category column (model has `Ingredient.category`)
- No last-consumed-at
- No filter by category, supplier, stock state
- No bulk reorder
- No "show only ingredients used in X recipes" filter
- "Ajustar" modal is great — but there's no inline "use this on next
  sale" or "+5" quick button

**vs. best-in-class:** Linear-style issues have inline property edit.
Saskia has modals only.

### D.3 Recetas (`recetas.html:38-89`)

**Columns:** name (linked), Rinde, Líneas count, batch_cost, unit_cost,
Edit.

**User wants to:** find recipes, see cost, edit.

**Missing:**
- No total-time (prep + cook) column
- No difficulty
- No family column
- No dietary_tags
- No "products that use this" column
- No "duplicate"
- No export to Excel (other lists have it)
- No bulk actions

### D.4 Pedidos (`pedidos.html:95-163`)

**Columns:** checkbox, customer (with 30d spend), fecha/hora, canal,
líneas, total, estado, edad, Ver.

**User wants to:** prioritize today's orders, see aging, fulfill.

**Missing:**
- No items preview (just "n_lines" count)
- No notes preview
- No payment_intent column
- No filter by channel
- No filter by date range
- No sort options (rows in declaration order)
- Bulk action: only "fulfill" and "cancel" — no "print all" or "send
  WhatsApp reminder"

### D.5 Clientes (`clientes.html:55-100`)

**Columns:** checkbox, name, phone, n_sales, lifetime_spend, points,
tier, Registrado, Ver.

**User wants to:** find customers, see loyalty, segment.

**Missing:**
- No email / CI-RUC column
- No "last purchase" date
- No "preferred products" derived
- No filter by last-purchase-before (lapsed)
- No bulk WhatsApp / bulk tag
- No sort by points (column exists but I didn't see a sort link — only
  header link in th-macro at line 60-69)
- No "loyal customer" flag (customers with N+ purchases)

### D.6 Merma events (`merma.html:206-229`)

**Columns:** fecha, ingrediente, qty, motivo, costo.

**User wants to:** see what was wasted, why, cost.

**Missing:**
- No notes column (model has them)
- No link to the ingredient detail
- No "who reported" (created_by)
- No batch-recipe-waste link (when whole recipe is wasted, no link to the
  recipe)

### D.7 Auditoria (`auditoria.html:100-140`)

**Columns:** fecha, usuario, accion, target (with id), IP, user-agent,
detail (in `<details>`).

**User wants to:** find who-did-what, debug, audit.

**Missing:**
- No CSV export (explicit gap)
- No "click target to jump to record"
- No filter chips for common actions
- No "show my actions only"

### D.8 Suppliers (`suppliers.html:14-61`)

**Columns:** name, contact, phone, email, ingredients count, actions.

**User wants to:** find supplier, see what they sell.

**Missing:**
- No "total spend YTD" column
- No "last ordered"
- No "outstanding balance"
- No link to the ingredients they supply (only count)

---

## E. Forms — missing affordances

### E.1 Bulk actions — almost everywhere missing

- Products: bulk DELETE only (productos.html:49-55)
- Clients: bulk DELETE only (clientes.html:48-54)
- Pedidos: bulk fulfill + bulk cancel (pedidos.html:82-92) — only place
  with meaningful bulk
- Inventory: no bulk
- Recipes: no bulk
- Merma events: no bulk
- Suppliers: no bulk

### E.2 Inline edit — none

Every edit goes to a separate page (or modal):
- Product edit: producto_form.html
- Ingredient edit: inventario_form.html
- Recipe edit: receta_form.html
- Customer edit: cliente_editar.html

No inline-edit-on-list. The closest is the "Ajustar stock" modal
(inventario.html:121-159) which is good — should be replicated.

### E.3 Drag-and-drop — none

- Recipe lines: add/remove buttons (receta_form.html:108-178), no
  reorder
- Pedido items: add/remove buttons (pedidos_nuevo.html:113-145), no
  reorder
- Plan template: not exposed at all
- Production calendar: not exposed as drag-to-edit

### E.4 Undo for destructive actions — none

- Delete product: confirm modal then gone (no undo)
- Delete client: same
- Cancel pedido: cancel modal (pedido_detalle.html:132-144) — no undo
- Void sale: confirm modal then voided (no undo) — the audit log shows
  it happened but no "re-instate" button
- Delete ingredient: confirm then gone

### E.5 Duplicate buttons — partial

- Pedido: has Duplicar (pedido_detalle.html:170-175) ✅
- Product: NO
- Recipe: NO
- Customer: NO

### E.6 "What changed" audit on individual records — partial

- Customer detail has a basic timeline (cliente_detalle.html:46-75)
- Sale receipt shows voided_at (recibo.html:13-19)
- Product / recipe / ingredient detail pages: NO change history
- All actions log to AuditLog (auditoria.html) but no drill-through
  from a record to its history

### E.7 Cascading effect preview — none

- Delete product: doesn't warn "you have N sales referencing this
  product". Just soft-deletes via `(deleted)` placeholder (per
  ventas.html:208 "product_name" can be "(deleted)")
- Delete recipe with products: model has cascade (models.py:135) but no
  preview
- Delete ingredient used in recipes: no preview

### E.8 Form affordances missing

- **No date-picker shortcut buttons** ("today", "yesterday", "this week")
  on sale form (ventas.html:82-84) — only datetime-local input
- **No "qty stepper" buttons** (1, 5, 10) on sale form (ventas.html:77-79)
- **No "recent" customer** quick-pick on sale form — only search
- **No autocomplete on pedido nuevo customer_phone** — only on customer_name
  (pedidos_nuevo.html:181-201)
- **No "save as draft"** anywhere
- **No autosave indicator** — the quick-sell recovery works but no UI
  badge "Draft saved 12s ago"
- **No optimistic UI** — all submits are full page reloads
- **No "validate before submit"** on pedido items (pedidos_nuevo.html:101
  — required but doesn't check if product_id is empty)

---

## F. Dashboard / Inicio — data we have vs data we show

The dashboard router (dashboard.py:258-327) computes an enormous amount of
analytics. Most of it never gets rendered.

### F.1 Computed in router, passed but NOT rendered in `inicio.html`

| Variable | What's in it | Rendered? |
|---|---|---|
| `dow_buckets` (line 287) | day-of-week heatmap, 90d | ❌ — variable unused |
| `turnover` (line 288) | stock turnover for top-8 ingredients | ❌ — variable unused |
| `top_margin` (line 297) | top 5 by margin (distinct from revenue) | ❌ — variable unused |
| `concentration` (line 298) | top 5 ingredients by cost share | ❌ — variable unused |
| `erosion_alerts` (line 299) | margin erosion warnings | ❌ — variable unused |
| `complexity` (line 300) | recipe complexity ranking | ❌ — variable unused |

That's **six computed metrics that the dashboard router spends cycles on
but the template never shows.**

### F.2 Computed AND rendered

| Variable | Rendered at | Notes |
|---|---|---|
| `chart_hourly` | inicio.html:56 | ✅ |
| `chart_30day` | inicio.html:57 | ✅ |
| `chart_payment_methods` | inicio.html:58 | ✅ — but only as donut, no per-day trend |
| `top_products_revenue` | inicio.html:59 | ✅ |
| `low_stock_alerts_with_severity` | inicio.html:60 | ✅ |
| `ranking` | inicio.html:65-93 | ✅ |
| `insights.stars` | inicio.html:149-153 | ✅ |
| `insights.dogs` | inicio.html:155-159 | ✅ |
| `insights.low_stock_alerts` | inicio.html:161-165 | ✅ |
| `insights.rising_products` | inicio.html:167-171 | ✅ |
| `insights.price_fluctuation` | inicio.html:173-177 | ✅ |
| `insights.churning_products` | inicio.html:179-183 | ✅ |
| `insights.production_tomorrow` | inicio.html:185-203 | ✅ |
| `insights.food_cost.theoretical_food_cost_pct` | inicio.html:142-146 | ✅ |
| `insights.inventory_capital_gs` | inicio.html:124-127 | ✅ |
| `insights.sales_peak_hour` | inicio.html:128-133 | ✅ |
| `insights.sales_peak_dow` | inicio.html:134-140 | ✅ |

### F.3 Computed and rendered but UNDERUSED

- **Hourly chart** (inicio.html:56): doesn't overlay yesterday, last week,
  or weekday average. Single-period bar.
- **30-day line** (inicio.html:57): doesn't overlay previous 30d for
  comparison.
- **Payment methods donut** (inicio.html:58): no list view, no trend.
- **Top products card** (inicio.html:59): no link to drill into the
  product.
- **Low stock alert card** (inicio.html:60): no link to ingredient.
- **Ranking table** (inicio.html:65-93): no links, no filter, no
  category grouping.

### F.4 Computed and rendered on OTHER pages (could be on dashboard)

- **Customer metrics** (tier, top customer) — only on /clientes, not on
  dashboard
- **Waste summary** (total cost, top ingredient) — only on /merma, not on
  dashboard
- **Production completion rate** — on /eod only, not on dashboard
- **Channel breakdown** — only as donut, no per-hour or per-product

### F.5 What Saskia looks at but the dashboard doesn't show

- "Today's P&L" widget — the daily summary report exists
  (/reportes/diario) but isn't on the home page
- "Low margin warning" on products — model computes margin but dashboard
  never warns "selling X at Y Gs. gives you only 28% margin"
- "Stock about to run out at yesterday's velocity" — no prediction
- "Customer X came back today after N days" — no churn-detection alert

---

## G. UX bugs / missing affordances — concrete list

### G.1 Keyboard / input

- **POS barcode scanner support** — the SKU field exists (ventas.html:56-64)
  with `autofocus` and the lookup runs on `change`/`blur`/Enter. Good.
  But there's **no auto-submit after SKU lookup** — operator still has to
  press Enter or click "Registrá venta". For real POS use, the SKU
  scan should auto-create the sale (qty 1) or move focus to qty
- **Cmd+K search modal exists** (base.html:303-317) ✅ — operators can
  hit Cmd+K to jump to any product/order/recipe
- **Page-specific shortcuts**: only on /ventas (F2/F3/F4/Esc per
  ventas.html:422-446). Other pages: zero shortcuts
- **No Tab navigation polish** — most forms work but no skip-links except
  base.html:53

### G.2 Loading states

- **No skeleton loaders** on any list page — pages either fully load or
  fully empty
- **"Importando…"** on excel.html:46 is a one-shot JS swap, not a real
  progress indicator
- **No "loading…" indicator on long queries** — /reportes/iva and
  /reportes/comparacion can be slow on large datasets
- **No optimistic UI** anywhere — every form submit is a full page reload

### G.3 Empty states

Most major pages have decent empty states with CTAs:
- Productos ✅ (productos.html:144-153)
- Recetas ✅ (recetas.html:96-105)
- Clientes ✅ (clientes.html:124-130)
- Merma ✅ (merma.html:235-240)
- Pedidos grouped (pedidos.html:170-180) ✅

**Missing empty states or weak ones:**
- **Auditoria**: only "no entries" — no "here's what gets logged"
- **Sales history**: "todavía no hay ventas" with CTA ✅ but no
  "here's how to import sales from yesterday"
- **Reorder**: "todo en orden" — good but no "set reorder rules" link

### G.4 Onboarding for new operator

- **No first-run wizard** — empty pages tell operator to add products
  but don't explain the workflow
- **Tooltip on complex fields** — only the dish-id sales form has
  "small" hint text. Recipe form has help (receta_form.html:14-16) but
  no `title` tooltips on hover
- **No interactive tour**
- **No "test mode"** — operator makes mistakes on real data
- **`/guia` exists** (link in base.html:134) — external page with guide

### G.5 Help / tooltips

- Almost no `title=` attributes except on copy buttons (productos.html:88)
  and table badges (productos.html:83)
- No `(?)` info bubbles
- Help text mostly in `<small>` after the input (e.g., ventas.html:62)

### G.6 Undo for accidental deletes

- **Zero undo infrastructure** — AuditLog records "sale.void" but
  there's no "re-instate" button on voided sales
- **Cascading effects not previewed** — delete a recipe, products
  reference `recipe_id` (nullable per models.py:195), but operator isn't
  warned which products will lose cost info

### G.7 Export

- **Auditoria**: NO export (explicit gap)
- **Pedidos detail**: NO export (just receipt per pedido)
- **Merma events**: NO export
- **Sale line items**: NO export (just summary)
- **Movimientos (ingredient stock history)**: NO export
- **ProductionCompletion**: NO export
- Existing CSV exports: productos, inventario, ventas (filter-aware),
  clientes — ✅ on those 4

### G.8 "Today's P&L" widget

- Data exists: `daily_summary` function in accounting.py
- Surface: only at /reportes/diario (separate page)
- Dashboard: no widget

### G.9 "Low margin warning"

- Margin is computed for every product (productos.html:97-98 shows it)
- But there's **no warning** for "this product's margin is below 30%"
- Even a simple color threshold would help (red <30%, yellow 30-50%,
  green >50%)
- The `margin_pct` macro in macros.html:36-46 has badge colors but
  nobody uses them on the list page (productos.html:98 uses `<em>` not
  the macro)

### G.10 Other UX gaps

- **No pagination on Recibo** — recibo.html is single-page only
- **No "your timezone" indicator** on any page — sale.tz is set but
  ignored
- **No "out of stock" toggle for SKU** — products.is_available exists
  but no SKU-based "out of stock" override for emergencies
- **Print receipt**: small button at recibo.html:87 — works but no
  "send to printer" preset (auto-print on sale?)
- **Notification center** (base.html:101-116) exists but no UI to set
  which events trigger notifications
- **Sound alerts**: pedido_board.html:84-99 plays a chime on page load
  (this is buggy — fires every refresh). Should fire on NEW order
  arrival via SSE/WebSocket
- **No "I'm away" / shift handover** — operator notes are only on /eod
- **Login session** has no "stay logged in" toggle visible
- **No profile / avatar** anywhere (not even in the topnav user area)

---

## H. What to build vs fix vs enhance

For every item: **FIX** = bug, missing edge case, polish. **ENHANCE** =
improve existing page without net-new surface. **BUILD** = net-new page
or feature.

### H.1 Top 10 FIXES (high impact, low effort)

1. **FIX — Render the 6 computed-but-unused dashboard metrics.**
   `dow_buckets`, `turnover`, `top_margin`, `concentration`,
   `erosion_alerts`, `complexity` are computed by `dashboard.py:287-300`
   but `inicio.html` never references them. Either render them in
   a "More analytics" section on the dashboard, or remove from the
   router. Currently it's pure waste.

2. **FIX — Show voided sales excluded from ventas total.** The dashboard
   metric card and /reportes/diario both compute ventas gross including
   voided sales (`dashboard.py:117` sums without filtering; verify the
   `/reportes/diario` summary too). When a sale is voided, today's
   ventas on the dashboard should drop. The history table shows
   "Anulada" (ventas.html:225) but the totals don't reconcile.

3. **FIX — Add per-channel filter to sales history.** `Sale.channel`
   exists and is settable on the form (ventas.html:91-98) but no filter
   in ventas.html:164-184. Operator can record WhatsApp sales but
   can't see "how many WhatsApp sales today?".

4. **FIX — Show "discounts given" as its own metric on /inicio.**
   `Sale.discount_gs` is captured (ventas.html:112) but the dashboard
   "Ventas" card is gross only. A small line "−Gs. X descuentos
   aplicados" or a second card "Ventas netas" would close the loop.

5. **FIX — Recipe line items reordering in receta_form.** receta_form.html:108-178
   has add/remove but no drag-to-reorder. Lines render in stored
   order — for a recipe with 10+ ingredients this matters.

6. **FIX — Pedido items reordering in pedidos_nuevo.** Same as above,
   pedidos_nuevo.html:81-111.

7. **FIX — Quick-sell: auto-submit after SKU scan.**
   ventas.html:289-320 auto-fills product but doesn't auto-submit. POS
   workflows should be one scan = one sale (qty 1, click button or
   Enter key on the form submit).

8. **FIX — Auditoria: add CSV export.** Explicit requirement. Easy.

9. **FIX — Recipe lines on receta_detalle.html show costs as `—` for
   sub-recipes.** `receta_detalle.html:99-101` renders sub-recipe line
   cost as `—` even though sub-recipe cost is computable. Operator
   can't see "this sub-recipe contributes X to the batch cost".

10. **FIX — EOD "items" checklist has opaque keys.** eod.html:31-39
    renders `item.label` and `item.help` but no link to the underlying
    page. E.g. "Revisar stock bajo" should be a link to /inventario
    with `?min_stock=yes`.

### H.2 Top 5 ENHANCEMENTS (high impact on existing pages)

1. **ENHANCE — Productos list: add "30d units sold" column + filter
   by category/availability.** No new page, just richer columns and
   filters.

2. **ENHANCE — Inventario list: add supplier column + filter by
   supplier/category.** Same — uses existing FKs.

3. **ENHANCE — Pedidos list: add items preview (collapsible), channel
   filter, payment_intent column.** Use existing data, render more of
   it.

4. **ENHANCE — Pedido board (pedido_board.html): show pedido total,
   phone, payment_intent, click-to-open, and quick-status buttons.**
   No new route, just more card content + clickable cards.

5. **ENHANCE — Cliente detail: link "send WhatsApp" + "preferred
   products" derived from history + "frequency" stat.** No new model
   fields, just rendering.

### H.3 Top 5 BUILDS (net-new)

Only build if H1+H2 are done. Most of what looks like a "build" is
actually an "enhance" once you read the code.

1. **BUILD — "Anomaly" page** (or widget): if sales drop >20% vs. same
   day last week, OR if waste spikes >50%, show an alert with the
   drill-down (which hour, which ingredient, which product). Data
   is all there — just needs a new aggregator and a small new
   template.

2. **BUILD — "Today's P&L" widget on /inicio.** Tiles for gross / net
   / discount / waste cost / COGS / margin. Already a separate
   /reportes/diario page — extract into a dashboard tile.

3. **BUILD — Supplier P&L page.** "How much did we spend with
   supplier X this month? What did we buy? Price trend per
   supplier." Uses `IngredientPriceEvent` aggregated by
   `Ingredient.supplier_id` + SaleStockMove-consumed cost.

4. **BUILD — "Lapsed customers" page.** Customers whose last sale is
   >30 / 60 / 90 days ago. Sortable by spend. CSV export. Critical
   for retention.

5. **BUILD — A 2-way compare page (or upgrade the comparison
   report).** Side-by-side two date ranges with: ventas, gross vs net,
   top-5 products, top-5 ingredients consumed, waste. The data is
   all there.

---

## Summary scorecard

| Page | Data shown | Affordances | UX polish |
|---|---|---|---|
| Inicio | 60% of computed | B- | B |
| Ventas | 80% of model fields | A- | A |
| Productos | 50% of model fields | C+ | B |
| Inventario | 60% of model fields | B | B |
| Recetas | 50% of model fields | C+ | B- |
| Pedidos (list) | 60% of model fields | B | B |
| Pedido detail | 70% of model fields | A | B |
| Pedido board | 40% of model fields | C | B (dark theme + big text) |
| Pedido nuevo | 70% of model fields | B- | C+ |
| Merma | 75% of model fields | B | B |
| EOD | 50% of useful metrics | B- | C+ |
| Reportes | 50% (separate pages) | B | B |
| Clientes | 50% of model fields | C+ | B |
| Cliente detail | 65% of model fields | B- | B |
| Produccion | 70% of model fields | B | B- |
| Reorder | 80% of model fields | A- | A- |
| Suppliers | 50% of model fields | C+ | C+ |
| Auditoria | 100% of model | C+ (no export) | B |
| Settings | 100% of model | C+ (no pw change) | B+ |

**Overall:** the app computes far more than it shows. The biggest wins
are:
1. **Wire the 6 unused dashboard metrics** (H1.1)
2. **Add filter/sort/column affordances to the list pages** (H2.1-3)
3. **Add "what changed?" cross-page navigation** (B.2)
4. **Add bulk edit / undo for destructive actions** (E.1, E.4)
5. **Build the 4-5 anomaly widgets / pages** that the data already
   supports

Saskia already has the data infrastructure for an excellent ops
dashboard. Most of the value is in **rendering what already exists**,
not in building new features.