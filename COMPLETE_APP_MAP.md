# Sazón — Complete Page & Element Map

## How to read this
- **Page** = route → template file
- **Sections** = visual blocks on the page
- **Popups** = `<dialog>`, `.modal`, confirmation `confirm()` dialogs
- **Forms** = `<form>` POST actions + all fields
- **Buttons** = every interactive `<a>`, `<button>` with non-navigation action
- **Data shown** = what the page computes and displays
- **JS** = client-side interactivity
- **Issues** = bugs, missing UX, broken elements
- **Missing** = features that belong here but don't exist

---

## Global

### Navigation Bar (base.html)
- **Logo**: icon-only brand, 48px height
- **Links**: Inicio `/` · Ventas `/ventas` · Productos `/productos` · Recetas `/recetas` · Inventario `/inventario` · Clientes `/clientes` · Pedidos `/pedidos` · EOD `/eod` · Merma `/merma` · Reportes `/reportes` · Config `/settings`
- **Right side**: shortcuts button (`#open-shortcuts`), user name, logout
- **Dropdown menus**: triggered by `aria-haspopup="true"` with `aria-expanded`
- **Keyboard shortcut modal**: `shortcut-help-modal` (`?` key or nav button)
  - Lists all `g+{key}` shortcuts + `Esc` to close
- **Alerts region**: `div.alerts-region` with `aria-live="polite"` for flash messages
- **Issues**: Dropdown CSS was recently added but the actual dropdown trigger/hide toggle behavior may not be wired to JavaScript; base.html has `aria-haspopup` but no `aria-expanded` toggle in JS

---

## `/` → inicio.html (Dashboard)

### Sections
1. **Alert bar** — `div.alerts-bar` with `role="status"`, renders flash messages (success/error/warning)
2. **Stock alerts card** — `m.alert_list_card()` macro, icon=icon-warn, shows low-stock ingredients with days-of-stock and severity badge
3. **Insights row** — 4 KPI cards:
   - Revenue vs. prior period (delta %)
   - Ticket medio (avg sale value)
   - Products sold today
   - New customers this week
4. **30-day revenue line chart** — SVG line chart, 30-day window
5. **Hourly sales bar chart** — sales by hour today (if data exists)
6. **Top products by revenue** — ranked list with revenue Gs
7. **Payment methods donut** — pie chart breakdown
8. **Insights panel** — dynamically computed tips (low stock, margin erosion, dead stock, churn risk)
9. **EOD checklist summary** — shows pending/open EOD items

### Forms
- None (read-only dashboard)

### Popups
- **Keyboard shortcut help modal** — `shortcut-help-modal` dialog
- **Insight cards** — static HTML, no popup

### JS
- Charts rendered server-side as SVG strings injected via Jinja
- `SaskiaCustomerPicker` loaded but not used on this page

### Issues
- Insight cards are built in Jinja templates — should be pre-computed in Python (already noted in audit)
- No refresh button — data could be stale on long-running sessions
- EOD checklist section links to `/eod` but doesn't show item count

### Missing
- No live clock or "last refreshed" timestamp
- No drill-down from KPI cards to relevant filtered report
- No date-range picker on dashboard itself (only via URL params passed to analytics)

---

## `/ventas` → ventas.html (Sales + Quick-sell)

### Sections
1. **Quick-sell grid** — top 5 products by revenue (last 14 days)
   - One-tap POST to `/ventas/nueva` with `product_id` + `qty=1`
   - Shows: product name + price
2. **Sale form** (`POST /ventas/nueva`):
   - SKU scanner input (`/ventas/buscar?sku=...`)
   - Product `<select>` (all products with price in `data-price`)
   - Quantity `number` (step 0.01)
   - Date/time `datetime-local`
   - **Customer picker** — dialog-based picker with search API
   - Channel select (mostrador / Delivery / WhatsApp / Rappi / PedidosYa / Encargo)
   - Payment method select
   - Discount Gs.
   - Notes textarea
3. **Recent sales table** (below form):
   - Columns: ID, fecha, producto, cliente, canal, pago, total, acciones
   - Row actions: Ver `/ventas/{id}` · Anular (POST with `confirm()` dialog)
4. **Sales filter bar**:
   - Product filter `<select>`
   - Days filter (7 / 14 / 30 / 90)
   - Search input
   - "Exportar CSV" link → `/ventas/export.csv?...`

### Forms
| Form ID / Action | Method | Fields |
|---|---|---|
| Quick-sell buttons | POST `/ventas/nueva` | `product_id`, `qty=1` |
| Sale form | POST `/ventas/nueva` | `product_id`, `qty`, `sold_at`, `customer_id`, `channel`, `payment_method`, `discount_gs`, `notes` |
| Anular button | POST `/ventas/{id}/anular` | — (uses `confirm()`) |
| SKU autocomplete | GET `/ventas/buscar?sku=...` | — (inline fetch) |

### Customer Picker Modal (`_customer_picker.html`)
- **Trigger**: `#customer_picker_trigger` button
- **Modal**: `<dialog id="customer_picker_modal">`
- **Search input**: debounced 120ms → `GET /clientes/api/search?q=...&limit=10`
- **Results**: rendered as `.customer-picker-result` buttons
- **New customer sub-panel**:
  - Fields: name, phone, cedula, email, notes
  - Submit → `POST /clientes/api/create`
  - Error displayed in `#cp_new_error`
- **Clear button**: resets hidden `customer_id` field
- **Backdrop click**: closes modal

### Popups
- `confirm('¿Anular esta venta? Se devuelve el stock.')` — inline JS on button
- Customer picker `<dialog>` modal
- Keyboard shortcut help dialog

### JS
- `customer-picker.js` — `SaskiaCustomerPicker` object
- SKU field: `input` event → debounced fetch to `/ventas/buscar?sku=...`
- Product `<select>`: inline `data-price` attributes used for price display

### Issues
- SKU lookup hits API on every keystroke (150ms debounce helps but no `AbortController`)
- No validation: can submit sale with zero quantity
- No optimistic UI: sale POST causes full page reload
- Quick-sell has no feedback on tap (button doesn't change state before reload)
- "Anular" uses browser `confirm()` — should be a styled modal
- No undo after void (if accidental, must re-enter sale)
- Recent sales table: no pagination (shows all — N+1 if many sales)
- `channel_default` / `payment_method_default` — if missing from session settings, falls back silently

### Missing
- Barcode scanner integration (only SKU text field, no actual scanner hook)
- Receipt reprint from sale ID
- Split payment (two payment methods on one sale)
- Sale notes visible in the table (only shown on detail view)

---

## `/productos` → productos.html (Product Catalog)

### Sections
1. **Header** with count: "N productos"
2. **Filter bar**:
   - Tag filter (multi-select via `<select>`)
   - Category filter
   - Search input
   - "Nuevo producto" button
3. **Product table**:
   - Columns: SKU, nombre, categoría, venta Gs, costo Gs, margen %, estado, acciones
   - Row actions: Edit `/productos/{id}/editar` · Eliminar (POST with `confirm()`)
4. **Empty state**: "No hay productos todavía. Empezá cargando tu primer producto."

### Forms
| Action | Method | Fields |
|---|---|---|
| Filter form | GET `/productos` (URL params) | `q`, `tag`, `category` |
| Delete product | POST `/productos/{id}/eliminar` | `_csrf_token` |
| New product (separate page) | GET `/productos/nuevo` then POST `/productos/nuevo` | name, sku, category, sale_price_gs, cost_gs, tags, recipe_id |

### Popups
- `confirm('¿Eliminar producto? Esta acción no se puede deshacer.')` on delete

### Issues
- Tag filter uses plain `<select>` — multi-select not user-friendly
- SKU displayed as plain text — no copy-to-clipboard
- No product image field (even empty placeholder)
- No category management page (categories created implicitly by naming)
- Product table: no pagination

### Missing
- Bulk tag assignment (checkboxes + single "Apply tags" action)
- Product clone/duplicate
- CSV import of products
- Product detail view page (only edit, no read-only view)

---

## `/recetas` → recetas.html (Recipe Library)

### Sections
1. **Header**: recipe count
2. **Filter bar**: search, tag filter
3. **Recipe table**:
   - Columns: nombre, rendimiento (g), costo Gs, precio venta Gs, margen %, ingredientes count, acciones
   - Row actions: Edit · Ver (expandable inline or dedicated page)
4. **New recipe button** → `/recetas/nueva`

### Forms
- Filter: GET `/recetas?q=...&tag=...`
- Delete: POST `/recetas/{id}/eliminar` with `confirm()`
- New/Edit recipe form (`POST /recetas/nueva` or `POST /recetas/{id}/editar`):
  - Name, yield grams, tags
  - Dynamic ingredient lines: ingredient `<select>`, qty, unit (g/kg/ml/l)
  - Sub-recipe support (can add a recipe as an ingredient)

### Popups
- Delete `confirm()`
- Edit form is a full page navigation (no modal)

### Issues
- No dedicated recipe detail view page — edit page is the only view
- Cost/margin shown in table but actual recipe cost breakdown requires opening edit
- Tags: no tag management UI in recipe section
- Sub-recipe circular dependency not prevented at UI level

### Missing
- Recipe cost breakdown modal (show ingredient-level costs)
- Recipe duplicate
- Recipe category/group
- Recipe search by ingredient
- Printable recipe card (kitchen-friendly)

---

## `/inventario` → inventario.html (Ingredient Inventory)

### Sections
1. **Filter bar**: search, category, tag filter, low-stock toggle
2. **Inventory table**:
   - Columns: nombre, categoría, stock actual, unidad, costo unit., costo total, días stock, estado, acciones
   - Stock shown with color-coded badges: green=OK, yellow=low, red=critical
   - Row actions: Edit `/inventario/{id}/editar` · Eliminar (POST)
3. **Low stock alert card** — `m.alert_list_card()` macro
4. **New ingredient button** → `/inventario/nuevo`

### Forms
| Action | Method | Fields |
|---|---|---|
| Filter | GET `/inventario` (URL params) | `q`, `category`, `tag`, `low_stock` |
| New ingredient | POST `/inventario/nuevo` | name, category, unit, stock_qty, cost_per_unit, lead_time_days, tags |
| Edit ingredient | POST `/inventario/{id}/editar` | same as new |
| Delete ingredient | POST `/inventario/{id}/eliminar` | `_csrf_token` |

### Popups
- Delete `confirm()`
- Low stock badge (inline, not a popup)

### Issues
- No reorder automation or suggested order quantities
- Stock displayed without unit — some ingredients use kg, some g, some units
- No receiving/GRN workflow (stock only editable manually)
- No history of stock changes (audit trail on inventory movements)

### Missing
- Stock adjustment modal (record wastage, breakages, corrections)
- Purchase order integration
- Supplier info per ingredient
- Min/max stock thresholds per ingredient (only global reorder logic exists)

---

## `/clientes` → clientes.html (Customer Management)

### Sections
1. **Filter bar**: tier filter (Todos / Bronce / Plata / Oro), search input
2. **Customer table**:
   - Columns: nombre, teléfono, cédula, email, lifetime spend Gs, visitas, tier badge, última visita, acciones
   - Tier badges: 🟫 Bronce / 🟩 Plata / ⭐ Oro (color-coded)
   - Row actions: Ver `/clientes/{id}` · Edit notes
3. **Stats row** (top of table): total customers, avg spend, gold/silver/bronze counts

### Forms
| Action | Method | Fields |
|---|---|---|
| Filter/search | GET `/clientes` (URL params) | `q`, `tier` |
| Customer detail | GET `/clientes/{id}` | — |
| Customer picker API | GET `/clientes/api/search?q=...&limit=10` | — (used by ventas modal) |
| Create customer API | POST `/clientes/api/create` | name, phone, cedula, email, notes (JSON body) |

### Modals
- **Customer picker modal** (same component as ventas, loaded here too)
  - Used by `/ventas` page — not typically opened from `/clientes`
  - Search: `GET /clientes/api/search`
  - Create: `POST /clientes/api/create`

### Customer Detail Page (`/clientes/{id}` → cliente_detalle.html)
Sections:
- Customer info card: name, phone, email, cédula, tier badge, join date
- Lifetime stats: total spend Gs, visit count, avg ticket, last visit
- Tier progress bar: shows spend toward next tier
- **Purchase history table**: date, products bought, total, channel — paginated
- **Point balance**: current points, redeem button
- Actions: Edit · Award points manually

### Issues
- No pagination on customer list (loads all — performance issue with batch fix applied)
- Customer detail: purchase history is paginated but no page size control
- Points system is basic — no expiry date on points
- No customer delete/archive

### Missing
- Customer merge (duplicate detection and merge)
- Export customer list to CSV
- Customer note history (who added notes, when)
- Loyalty tier auto-update runs on login — tier badge could be stale between logins

---

## `/pedidos` → pedidos.html (Orders / Pedidos)

### Sections
1. **Status tabs**: Todos / Pendientes / En preparación / Listos / Entregados / Cancelados
2. **Pedido list** (table):
   - Columns: #ID, cliente, promised date/time, items count, total Gs, status badge, created
   - Status badges: color-coded (yellow=pending, blue=preparing, green=ready, gray=cancelled)
   - Row actions: View `/pedidos/{id}` · Update status dropdown
3. **New pedido button** → `/pedidos/nuevo`
4. **Public link indicator**: each pedido has a public token URL `/pedidos/p/{token}`

### Forms
| Action | Method | Fields |
|---|---|---|
| New pedido | POST `/pedidos/nuevo` | customer_id, promised_at, notes, line items (product_id, qty) |
| Update status | POST `/pedidos/{id}/status` | status (pendiente/en_preparacion/listo/entregado/cancelado) |
| Mark fulfilled | POST `/pedidos/{id}/fulfill` | — (marks all lines as fulfilled) |
| Filter by status | GET `/pedidos?status=...` | `status` |

### Pedido Detail Page (`/pedidos/{id}` → pedido_detalle.html)
Sections:
- Order header: ID, cliente, status badge, promised time, created
- **Line items table**: product, qty, unit price, subtotal, fulfilled qty, fulfilled toggle
- Fulfillment form: per-line fulfilled checkbox + "Confirmar entrega" button
- Order total Gs
- Notes
- Public link: `/pedidos/p/{token}` (click to copy)

### Public Pedido Page (`/pedidos/p/{token}` → pedido_publico.html)
- Read-only page, no auth required
- Shows: pedido details, line items, status, pickup instructions
- No actions available (purely informational)

### Popups
- `confirm()` on status change (inline)
- No styled modal — uses browser `confirm()`

### Issues
- No pagination on pedido list
- No due-date overdue highlighting (pedidos past their promised time not visually urgent)
- No customer notification when status changes (WhatsApp/email webhook)
- Fulfillment is per-line checkbox — could have bulk "mark all ready" for kitchen
- Pedido line editing after creation: no edit — must delete and recreate
- Public token: no expiry on token, no revocation mechanism

### Missing
- Pedido duplication (clone a previous pedido)
- Pedido cancel with restock (void sale-like behavior for orders)
- Kitchen display (prep board view) — shows only pending items, large cards
- Automatic SMS/WhatsApp when status changes
- Pedido reminders (overdue notifications)

---

## `/reportes` → reportes.html (Reports Hub)

### Sections
1. **Report cards** (grid):
   - 📊 Reporte diario — `/reportes/diario` — daily sales summary
   - 📄 Libro de ventas — `/reportes/libro-ventas` — sales ledger for accounting
   - 💰 IVA — `/reportes/iva` — VAT/tax report
   - 📈 Márgenes — (leads to productos page with margin data)
   - 🏭 Menu engineering — (leads to products classified by quadrant)
   - 🗓️ Producción — `/produccion` — production planning
   - 📦 Stock / Reorder — `/reorder` — reorder recommendations
   - ⚠️ Merma — `/merma` — waste tracking

Each card links to the respective report or page.

### Report Sub-pages

#### `/reportes/diario` → reportes_diario.html
- Date picker (default: today)
- Table: product name, qty sold, revenue Gs, cost Gs, margin Gs, margin %
- Totals row at bottom

#### `/reportes/libro-ventas` → reportes_libro_ventas.html
- Month/year selector
- Columns: fecha, nro documento, cliente, rut/ci, exentas Gs, gravadas Gs, 5% Gs, 10% Gs, total Gs
- Compliance format for Paraguayan tax authority
- Totals and signature fields at bottom (for printed version)

#### `/reportes/iva` → reportes_iva.html
- Month selector
- VAT breakdown: 5% rate, 10% rate, exemptions, totals
- Tax amount calculation

#### `/reportes/precios` → reportes_precios.html
- Ingredient price history table
- Per ingredient: name, current price, min/max/avg over N days, last change date
- Row: click to expand → price change timeline

### Forms
- Date range picker on each report (form GET with URL params)

### Issues
- No export to PDF on libro-ventas (would be needed for tax submission)
- All reports are server-rendered HTML — no client-side interactivity (sort, filter, search)
- Date pickers are basic `<input type="date">` — no calendar widget
- No report bookmarking (URL contains date params, but no "copy shareable link" button)
- No email report delivery (notifications system exists but not wired to reports)

### Missing
- Comparative report (this month vs. last month, YoY)
- Cash flow report (cash in/out)
- Staff performance report
- Customer cohort analysis
- Recipe profitability ranking
- All reports lack a "print" button optimized for A4

---

## `/eod` → eod.html (End of Day)

### Sections
1. **EOD Checklist**: items from `fresh_eod_checklist()` — each is a task with status:
   - ☑️ Open / ✅ Completed / 🔄 In Progress
   - Items: Cash count, Daily sales reconciled, Inventory topped up, Delivery orders dispatched, Waste recorded, Backup verified, Tomorrow's production planned
2. **Summary panel**: today's sales total, transaction count, top product
3. **Cash reconciliation form**:
   - Expected cash (from sales) vs. actual cash counted
   - Difference → recorded as variance
4. **"Completar día" button**: POST `/eod/completar` — marks day as closed

### Forms
| Action | Method | Fields |
|---|---|---|
| Complete EOD | POST `/eod/completar` | `_csrf_token` |
| Cash reconciliation | (part of EOD form, POST with sale data) | expected, actual, notes |

### Issues
- No date selection (always today)
- Checklist items are static — not dynamically generated based on actual operations (e.g., if no deliveries today, "Delivery orders dispatched" shouldn't be a required item)
- No signature capture field for manager sign-off
- No EOD history (can't review past EOD closes)

### Missing
- EOD report that can be emailed to owner
- Multi-shift support (two EODs per day for lunch/dinner service)
- Cash variance alerts (if difference > threshold, trigger notification)
- Integration with actual POS cash drawer

---

## `/merma` → merma.html (Waste Tracking)

### Sections
1. **Waste summary cards** (today / this week / this month):
   - Total waste Gs
   - Waste as % of revenue
   - Top wasted ingredient
2. **Log waste form** (`POST /merma/registrar`):
   - Ingredient `<select>` (all ingredients)
   - Quantity (decimal)
   - Unit (g/kg/ml/unit)
   - Reason `<select>`: preparation / expired / damaged / customer_return / other
   - Notes
3. **Recipe waste form** (`POST /merma/receta`):
   - Recipe `<select>`
   - Quantity produced vs. wasted
4. **Waste history table**:
   - Columns: fecha, ingrediente/producto, cantidad, unidad, razón, costo Gs
   - Filter by: date range, reason, ingredient

### Forms
| Action | Method | Fields |
|---|---|---|
| Log ingredient waste | POST `/merma/registrar` | ingredient_id, qty, unit, reason, notes |
| Log recipe waste | POST `/merma/receta` | recipe_id, qty_kg, reason, notes |
| Filter | GET `/merma` (URL params) | `from`, `to`, `reason`, `ingredient_id` |

### Issues
- No cost calculation shown in the waste table (only shows qty)
- Waste reasons are free-text in some places (inconsistent)
- No visualization of waste trends over time

### Missing
- Waste alert threshold (if waste exceeds X% of revenue, fire notification)
- Waste photo attachment (camera icon)
- Waste reduction tips based on common reasons
- Integration with inventory (waste logging should reduce stock levels automatically)

---

## `/produccion` → produccion.html (Production Planning)

### Sections
1. **Week calendar header**: Mon–Sun with date, each day shows:
   - Expected sales units per product
   - Production plan per product
   - "Override" input to manually adjust production qty
2. **Production table**:
   - Rows: each product
   - Per day: expected units, planned units, difference (over/under)
   - Override input per product/day
3. **Ingredient requirements panel**:
   - Per ingredient: required qty for the planned production
   - Shows: current stock vs. needed
   - Highlights: ingredients that will run short
4. **Calendar link**: `/produccion/calendario` — calendar view

### Forms
| Action | Method | Fields |
|---|---|---|
| Save overrides | POST `/produccion/override` | `{product_id: {date: qty}, ...}` |
| Filter week | GET `/produccion` (URL params) | `week_start` (Monday date) |

### Sub-page: `/produccion/calendario` → produccion_calendario.html
- Monthly calendar view
- Color-coded production intensity per day
- Click day → drill down to that day's production plan

### Issues
- Override saves per product/day — no bulk save
- Production plan only works for products with recipes (no simple-buy products)
- No Gantt or timeline view — just tabular

### Missing
- Auto-suggest production based on historical sales (the `batch_expected_daily_sales` function exists but isn't wired to a UI)
- Print-friendly production ticket for kitchen
- Actual vs. planned comparison after day closes
- Sub-recipe explosion in ingredient requirements (if a recipe uses a sub-recipe)

---

## `/settings` → settings.html (Configuration)

### Sections
1. **Settings groups** (tabs or sections):
   - General: business name, currency, timezone
   - Notifications: WhatsApp enabled, email enabled, daily summary time
   - Printer: IP/hostname, type (thermal/EscPos), paper width
   - Loyalty: points per Gs, tier thresholds (Bronce/Silver/Gold spend)
   - Sales defaults: default channel, default payment method
   - Notifications contacts: WhatsApp number, email addresses
2. **Save button** per section
3. **Reset to defaults** button (POST `/settings/reset`)

### Forms
| Action | Method | Fields |
|---|---|---|
| Update settings | POST `/settings` | setting key-value pairs |
| Reset all | POST `/settings/reset` | `_csrf_token` |

### Issues
- No setting for low-stock alert threshold (global, not per-ingredient)
- No setting for notification frequency (e.g., only alert if waste > X%)
- Printer config: no test print button
- WhatsApp: no template preview

### Missing
- User management (add staff accounts, roles)
- Backup schedule configuration
- Tax rate configuration (IVA %)
- Data export (full DB dump)
- Audit log viewer UI

---

## `/reorder` → reorder.html (Reorder Recommendations)

### Sections
1. **Reorder alerts table**:
   - Columns: ingrediente, stock actual, reorder point, reorder qty, lead time días, proveedor, acción
   - Row: shows which ingredients need purchasing
2. **Quick actions**: Mark as ordered (removes from alert)
3. **Supplier info**: per-ingredient preferred supplier

### Forms
| Action | Method | Fields |
|---|---|---|
| Mark as ordered | POST `/reorder/registrar` | `ingredient_id` (removes from alert list) |
| Filter | GET `/reorder` | `category`, `supplier` |

### Issues
- No actual purchase order generation (just a "mark as ordered" button)
- No supplier management UI (supplier info must be entered per ingredient manually)
- No integration with actual supplier APIs or email

### Missing
- Purchase order PDF generation
- Supplier price comparison
- Reorder automation based on consumption rate (the `compute_reorder_list` function exists but UI is minimal)
- Multi-supplier support

---

## `/auditoria` → auditoria.html (Audit Log)

### Sections
1. **Audit log table**:
   - Columns: timestamp, usuario, acción, detalles, IP
   - Paginated
2. **Filter bar**: user, action type, date range

### Issues
- No export of audit log
- No real-time view (must refresh page)
- Pagination is basic (no date-based quick jumps)

### Missing
- Audit log retention policy (auto-prune old entries)
- Dashboard-style summary of activity (who did what today)

---

## `/ops/status` → ops_status.html (Operations Status)

### Sections
1. **System health indicators**:
   - Database: connected/disconnected
   - Last backup: timestamp + status
   - Schema version: code vs. DB
2. **Demo data reset**: `POST /ops/reset-demo-data` — clears and reseeds demo data
3. **Environment info** (non-sensitive): Python version, database type, feature flags

### Forms
| Action | Method | Fields |
|---|---|---|
| Reset demo data | POST `/ops/reset-demo-data` | `_csrf_token` |

### Issues
- No "schema drift" warning with actionable message (just shows version numbers)

### Missing
- Manual backup trigger
- Log viewer (tail application logs)
- Active session viewer
- Cache clear button

---

## `/excel` → excel.html (Import/Export)

### Sections
1. **Import tab**:
   - Dropzone for CSV/XLSX files
   - Mode selector: products / ingredients / price events
   - Preview table after file selected (shows first 10 rows)
   - "Importar" button → `POST /excel/importar`
   - Mapping: column assignment UI (which CSV column = which DB field)
2. **Export tab**:
   - Entity selector: products / ingredients / sales / recipes
   - Date range (for sales)
   - "Descargar" button → `GET /excel/exportar?entity=...&...`

### Forms
| Action | Method | Fields |
|---|---|---|
| Import file | POST `/excel/importar` | file, mode |
| Export | GET `/excel/exportar` | entity, date_from, date_to |
| Download template | GET `/excel/plantilla` | mode (products/ingredients) |

### Issues
- No import validation report (shows errors after import, not before)
- Import preview only shows 10 rows — large files can't be fully previewed
- No import rollback (if 50 of 1000 rows fail, partial import proceeds)

### Missing
- Scheduled export (daily/weekly email with CSV attached)
- Google Sheets import/export
- Import templates for more entities (customers, pedidos)

---

## `/guia` → guia.html (Help Guide)

### Sections
- Markdown-rendered help content loaded from files in `docs/` directory
- Sidebar: section list
- Content: step-by-step guides with screenshots (if embedded)

### Issues
- No search within help
- No "Was this helpful?" feedback

### Missing
- Video tutorials embedded
- Contextual help (help button on each page that links to relevant guide section)
- Offline/PDF version of help

---

## Reusable Components (`_components/`)

### `macros.html`
- `m.alert_list_card(title, items, icon)` — card with list of alert items + icon
- `m.gs(value)` — format integer as Gs. with dot separators (e.g., `1.234.567`)
- `m.stock_badge(qty, unit)` — green/yellow/red badge based on stock level
- `m.tier_badge(tier)` — Bronce/Silver/Gold colored badge
- `m.format_date(dt)` — locale date formatting
- `m.format_datetime(dt)` — locale datetime formatting
- `m.price_row(ingredient)` — price history table row
- `m.nav_link(url, icon, label)` — navigation link with icon
- `m.pagination(current_page, total_pages, url_fn)` — prev/next pagination
- `m.chart_section(id, title, content)` — accessible chart container with `role="img"` + `aria-label`
- `m.shortcut_button(url, key, label)` — keyboard shortcut hint button

### `calendar.html`
- Week view calendar component for production planning
- Renders Mon–Sun grid with production quantities per product

### `_customer_picker.html`
- Dialog-based customer search and create
- States: search panel, results list, new-customer form
- Empty state: "No se encontraron clientes."

### `icons.svg`
- SVG sprite with all icons: check, x, chevron-down, chevron-up, plus, edit, trash, eye, warning, info, help, ops, star, calendar, printer, download, search, filter, alert, heart, etc.
- Recently added: `icon-warn` (triangle ⚠) and `icon-heart`

---

## Missing Features (Not Implemented)

| Feature | Where It Should Live | Priority |
|---|---|---|
| Print receipt from sale ID | `/ventas/{id}/recibo` | High |
| Kitchen display (pedido prep board) | `/pedidos/board` or `/pedidos/kitchen` | High |
| Stock adjustment modal | `/inventario/{id}/ajustar` | High |
| Dashboard date-range picker | `/` inicio.html | Medium |
| Customer merge/duplicate detection | `/clientes` | Medium |
| PDF export for libro-ventas | `/reportes/libro-ventas` | Medium |
| Backup restore UI | `/ops/status` or new `/backup` page | Medium |
| User management + roles | `/settings/users` | Medium |
| Help search | `/guia` | Low |
| Staff performance report | `/reportes/staff` | Low |
| Cash flow report | `/reportes/cashflow` | Low |
| Barcode scanner integration | `/ventas` (hardware hook) | Low |
| WhatsApp message template editor | `/settings` | Low |
| Product image upload | `/productos/{id}/editar` | Low |
| Real-time WebSocket updates | `/pedidos`, `/ventas` | Low |

---

## UX Anti-Patterns to Fix

| Page | Issue | Fix |
|---|---|---|
| ventas | `confirm()` browser dialog for void | Replace with styled modal |
| ventas | Quick-sell buttons reload page | Add spinner/disabled state on submit |
| ventas | No sale success feedback | Add flash message styled as banner |
| pedidos | Status change uses `confirm()` | Dropdown with immediate POST |
| inventario | Delete uses `confirm()` | Modal with "type ingredient name to confirm" |
| productos | Tag filter is single-select | Multi-select checkboxes |
| reportes | All reports reload page on date change | Add "Apply" button with URL param, not auto-submit |
| eod | Always defaults to today | Add date picker |
| All pages | No global search (Ctrl+K) | Add command palette |
| All pages | No breadcrumbs | Add `nav aria-label="breadcrumb"` |
| All tables | No column sorting | Add sort icons on table headers |
| All tables | No row selection for bulk actions | Checkbox column + bulk action bar |
