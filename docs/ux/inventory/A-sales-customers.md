# Sazon/Saskia Sales + Customers + Credit Content Audit

**Generated:** 2026-10-07
**Scope:** Sales / POS / Cash (10 pages) + Customers / CRM (5 pages) + Credit (3 pages) + Fiado (2 pages) + Suscripciones (2 pages)
**Total pages audited:** 22
**Source templates:** `app/templates/ventas*.html`, `recibo.html`, `caja*.html`, `wishlist.html`, `clientes*.html`, `creditos.html`, `fiado*.html`, `suscripcion*.html`
**Router files:** `app/routers/sales.py`, `customers.py`, `fiado.py`, `creditos.py`, `suscripciones.py`

---

## ventas.html — POS (Point of Sale)

### 1. Identity
- **URL/route**: `/ventas` (root) — also handles `POST /ventas/nueva/multi` (cart submit) and `POST /ventas/nueva` (one-tap submit)
- **Page title**: `Ventas`
- **Section**: POS / cashier
- **User persona**: Operator (cashier) at the mostrador

### 2. Structure
- **Page header (top)**: `Ventas` with desc `Registrá una venta al mostrador o consultá el historial del día`
- **Sub-heading (left pane)**: `Nueva venta`
- **Sub-heading (cart panel)**: `Carrito`
- **Sub-heading (right pane)**: `Productos`
- **Quick-sell sub-heading**: `Quick-sell`
- **Menú ejecutivo sub-heading**: `Menús ejecutivos`
- **Sale metadata sub-heading**: `Venta`
- **Comprobante fiscal legend**: `Comprobante fiscal`
- **Held-sales panel header**: `Ventas en espera`

### 3. All visible user-facing text

**Page-level messages:**
- Flash area: `{{ ui.flash_toast(request) }}` (toast notifications)

**Button + link text:**
- `Pausar` (hold-cart button with title `Pausar carrito — el cliente puede volver y retomar`)
- `Dividir pago` (split-payment toggle)
- `Propina:` (tip row label) + quick buttons `0%`, `5%`, `10%`
- `Sugerencias para sumar:` (cross-sell rail header)
- `Actualizar lista` (held-list refresh button title)
- `Buscar producto en venta rápida…` (quick-sell search placeholder)
- `Filtrar por categoría (selección múltiple)` (filter group aria-label)
- `Productos para venta rápida` (grid aria-label)
- `Buscar producto, nota o teléfono` (history search aria-label)
- `Mostrador` (default channel display)
- `Seleccioná canal…`, `Seleccioná forma de pago…`, `Tipo` (combo placeholders)
- `Para transferencia/QR indicá el alias en el campo de notas.` (payment helper)
- `Boleta Resimple (IRE RESIMPLE)`, `Factura (IVA General)`, `Sin comprobante (interno)` (invoice type options)
- `RUC del cliente` label, placeholder `80012345-6 o CI del cliente`
- `Razón social / Nombre` label, placeholder `Cliente S.A.`
- `Notas` label, placeholder `Alias de transferencia, observaciones…`
- `Cancelar` (clear cart button)
- `Ver historial` (link to history)
- `Registrá venta` (submit button; shows `<count>` items in span)
- `Escaneá código o tipeá SKU…` (scan input placeholder)
- `Tocá un producto o escaneá un código para agregarlo al carrito.` (right pane hint)
- `Todos`, `Favoritos` (filter pills)
- `Quick-sell` (heading)
- `El catálogo todavía no tiene productos con ventas recientes.` (empty-state message)
- `Venta libre` (free-price button), `Precio a definir` (sublabel)
- `Agotado` (sold-out badge), `Sin stock` (unavailable badge)
- `⚠ Quedan {{n}}` (low-stock badge)
- `Ningún producto en esta categoría.` (no-results JS message)
- `Ningún producto coincide con esa búsqueda.` (no-search-results JS message)

**Form labels + placeholders:**
- `Fecha y hora` (sold_at datetime)
- `Canal` (channel combo)
- `Forma de pago` (payment combo)
- `RUC del cliente`, `Razón social / Nombre` (factura fields)
- `Notas` (sale notes textarea)

**Table column headers (carrito):**
- `Producto`, `Precio`, `Cant.`, `Dto. %`, `Subtotal` (cart columns)
- `Ítems del carrito` (table aria-label)

**Tooltips (title attributes):**
- `Pausar carrito — el cliente puede volver y retomar` (hold button)
- `Actualizar lista` (held refresh button)
- `{{ fmt.entity_name(q) }} — {{ m.gs(q.sale_price_gs) }}` (quick-sell aria-label; rendered as title)
- `{{ mu.name }} — {{ m.gs(mu.price_gs) }}` (menú button aria-label)
- `{{ mu.items_summary }}` (menú title attribute)
- `Anular` button aria-label + dynamic title on history rows

**Status badges + tags:**
- `Agotado` (red), `Sin stock` (red), `⚠ Quedan N` (yellow)
- Cart-count badge shows item count
- Held-count badge shows paused count

**Error / success / warning messages:**
- JS preflight banner `id="preflight-banner"` (dynamic; displays warnings like `Sin stock para X`, `Cliente requiere RUC`)
- Toast area renders flash messages (success/error from server)

**Helper copy:**
- `Para transferencia/QR indicá el alias en el campo de notas.` (payment help)

### 4. Displayed data

**Left pane — Sale form (`/ventas/nueva/multi`):**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| Customer picker (top) | Selected customer name, phone, points | `María (0981…) 220pts` | Card on dark bg |
| Cart items table | Per-product line item with qty, unit price, discount, subtotal | `Chipa · Gs. 8.000 · 2 · 0% · 16.000` | Editable qty input |
| Cart total row | Sum of cart subtotals (Gs.) | `Gs. 23.000` | Bold |
| Tip row (optional) | Customer tip; quick 0/5/10% + manual Gs. | `Propina: Gs. 1.150` | Inline row |
| `sold_at` datetime | Override sale date/time (defaults to now) | `2026-10-07T14:30` | Native datetime input |
| `channel` combo | Mostrador / Salón / Pickup / etc. | `Mostrador` | Combo (searchable) |
| `payment_method` combo | efectivo / transferencia / QR / tarjeta / fiado / crédito | `Efectivo` | Combo |
| `invoice_type` combo | boleta_resimple / factura / none | `Boleta Resimple (IRE RESIMPLE)` | Combo |
| `invoice_customer_ruc` | RUC or CI shown on fiscal invoice | `80012345-6` | Text input |
| `invoice_customer_name` | Razón social for invoice | `Cliente S.A.` | Text input |
| `notes` | Free-form notes; QR alias, observations | `Alias: tuqui` | Textarea (2 rows) |

**Right pane — Quick-sell grid:**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| Scan input | Barcode or SKU text | `Scan all` | Autofocused text |
| Filter pills | All / Favoritos / category names | `Todos` (active) `Favoritos` `Panadería` | Pills, multi-select |
| Quick-sell grid | Product button: thumb + name + price | `Chipa — Gs. 8.000` | Image + price; sold-out state disables button |
| Menú ejecutivo strip | Combo meals (when `menus_activos`) | `Menú Café — Gs. 15.000` | Smaller tile |
| Venta libre tile | Always-visible free-price product | `Venta libre — Precio a definir` | Special purple tile |

### 5. Tooltips / hover text

| Element | Tooltip text |
|---|---|
| Hold-cart button | `Pausar carrito — el cliente puede volver y retomar` |
| Held-list refresh | `Actualizar lista` |
| Quick-sell button (per product) | `<name> — <Gs. price>` (visible to screen readers as aria-label) |
| Menú ejecutivo button | `<name> — <Gs. price>` + title=`<items_summary>` |
| Held-list refresh | `Actualizar lista` (via `title=` attribute) |
| Scan input | `aria-label="Escanear código"` (hover text via browser tooltip) |

### 6. UX/copy audit — flags

**Terminology consistency:**
- `mostrador` (default channel value) vs `Mostrador` (display) — consistent.
- `salon` vs `salón` — Spanish uses `salón` with accent; raw value `salon` without. Inconsistency in autocomplete options.
- **Pedido vs Orden**: ventas uses `Pedido` for orders; POS shows `Ver historial` (not "Ver pedidos"). OK.
- **Cliente vs Comprador**: ventas uses `Cliente` exclusively (good).

**Copy / UX issues:**
- `Pausar carrito` button hidden by default (`display:none`) until JS detects state — operator may not know it exists.
- `Dividir pago` and `Propina` rows are hidden by default (`display:none`) — operator may miss the split-payment flow.
- The `invoice_type` combo shows raw values like `Boleta Resimple (IRE RESIMPLE)` for `boleta_resimple` — that's an internal abbreviation (IRE = Impuesto a la Renta Empresarial, RESIMPLE = Régimen Simplificado). May be too technical for a non-accountant operator.
- `Quitar de favoritos` / `Marcar como favorito` buttons (referenced in productos.html) are not visible on ventas.html — feature is hidden here.
- The `cross-sell rail` is JS-populated; if backend categories don't match, no suggestions appear with no explanation.
- `Venta libre` is rendered as a button with `<svg>` icon but the tile name shows `Venta libre` — consistent with the seed. OK.
- "Quick-sell" is a loan word — used both in heading and JS class names. The Spanish-native equivalent (`venta rápida`) appears in the placeholder only. Mixed terminology.
- "Comprobante fiscal" — a Paraguayan tax term; correct.

**Icon-only buttons needing aria-label (checked):**
- Most buttons have aria-label or visible text. Hold-cart uses svg + "Pausar"; refresh uses ↻ with title. OK.

**Empty states:**
- `El catálogo todavía no tiene productos con ventas recientes.` — clear and actionable.
- `Ningún producto en esta categoría.` — added by JS when filter empties grid.
- `Ningún producto coincide con esa búsqueda.` — added by JS when search empties grid.

---

## ventas_detalle.html — Single-sale detail

### 1. Identity
- **URL/route**: `/ventas/{sale_id}`
- **Page title**: `Venta #<id>`
- **Section**: Sales / ledger
- **User persona**: Operator, manager

### 2. Structure
- Breadcrumb: `Ventas > Venta #id` (implicit; no explicit crumb)
- Card 1: `Datos de la venta` (h2)
- Card 2: `Cliente` (h2)
- Card 3: `Pedido asociado` (h2; only if linked pedido)
- Card 4: `Movimientos de stock (N)` (h2; per ingredient)

### 3. All visible user-facing text

**Page-level messages:**
- `<strong>ANULADA</strong>` banner (when voided)

**Button + link text:**
- `Ver recibo imprimible →` (link to /ventas/{id}/recibo)
- `← Volver al historial` (back link)
- `Ver recibo` (primary button)

**Definition-list items:**
- `Fecha` (sold_at), `Producto`, `Cantidad`, `Precio unitario`, `Descuento`, `Total` (sale lines)
- `Forma de pago`, `Canal`, `Notas` (sale meta)
- `Puntos ganados`, `Puntos canjeados`, `Saldo actual` (points)
- `Cliente no asociado` (when no customer)

**Table column headers (stock movements):**
- `Ingrediente`, `Cantidad`, `Fecha`

**Empty/edge states:**
- When `pedido` is None, card 3 is hidden.
- When `stock_moves` is empty, card 4 shows `Movimientos de stock (0)`.

### 4. Displayed data

**Sale detail card:**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| `Fecha` | Sale timestamp | `07/10/2026 14:30` | dt |
| Sale line items | Each row: product, qty, unit price, discount, total | `Chipa · 2 · 8.000 · 0% · 16.000` | dt/dd rows |
| `Forma de pago` | Cash/transfer/etc. | `efectivo` | dt |
| `Canal` | Channel | `mostrador` | dt |
| `Notas` | Sale notes | `alias tuqui` | dt |
| `ANULADA` banner | Voided marker | `ANULADA` | Strong red text |

**Customer card:**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| Customer link | Goes to /clientes/{id} | `María (0981…)` | <a> |

**Stock movements:**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| `Ingrediente` | Ingredient ID | `12` | td |
| `Cantidad` | qty consumed (3dp) | `0.250` | td |
| `Fecha` | When recorded | `07/10/2026 14:30` | td |

### 5. Tooltips / hover text

(none explicit — buttons use title-like text on action confirmation modals.)

### 6. UX/copy audit — flags

- No tooltips on table cells — ingredient IDs are raw integers; should resolve to ingredient name.
- `Forma de pago` and `Canal` shown raw (`efectivo` not `Efectivo`).
- "Ver recibo imprimible" — clear action.

---

## ventas_historial.html — Sales history

### 1. Identity
- **URL/route**: `/ventas/historial`
- **Page title**: `Historial de ventas`
- **Section**: Sales / ledger
- **User persona**: Operator, manager

### 2. Structure
- H1: `Historial de ventas`
- KPI row (grid): `<aria-label="Resumen del historial">` — daily total, count, avg ticket, etc.
- Filters card: `<aria-label="Filtros del historial">`
- Sales table
- Pagination nav: `<aria-label="Paginación de ventas">`

### 3. All visible user-facing text

**Page-level messages:**
- KPI summary cards (4 metrics): Total Gs., # ventas, ticket promedio, mejor día
- `Mostrando <start>–<end> de <total> ventas` (pagination info)
- `{{ ui.empty_state(title="Todavía no hay ventas en el historial", icon="icon-sale", hint="Las ventas que registres aparecerán acá.") }}`

**Button + link text:**
- `Filtrar` (submit), `Limpiar` (clear filters)
- `🖨 Imprimir reporte` (print action; no-print class hides in print)
- `Anular` (per-row void button; opens `UIConfirmModal.show({title:'¿Anular venta #X?', body:'Esta acción devuelve el stock y queda registrada en auditoría.', confirmLabel:'Sí, anular', danger:true, formId:'void-form-X', reasonInputId:'anular-reason-X', reasonField:true})`)
- `← Anterior`, `Siguiente →` (pagination)
- `<a title="Crear pedido para <customer_name> basado en esta venta">` — implicit icon link to create a pedido

**Form labels + placeholders:**
- `Buscar:` label, placeholder `Producto, nota o teléfono`
- `Rango` placeholder (days filter)
- `Canal` placeholder (channel filter)

**Table column headers:**
- `Fecha`, `Producto`, `Cant.`, `Unit. (Gs.)`, `Total (Gs.)`, `Cliente`, `Pago`, `Canal`, `Atendido por`, `Notas`, `Acciones`

**Status badges:**
- `<strong>ANULADA</strong>` (when voided)

**Pagination:**
- `Mostrando 1–25 de <N> ventas`

### 4. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Fecha` | sold_at_str (custom formatted) | `07/10 14:30` | td |
| `Producto` | product name | `Chipa` | td |
| `Cant.` | qty sold | `2` | td right |
| `Unit. (Gs.)` | unit price | `8.000` | td right |
| `Total (Gs.)` | subtotal incl. discount | `16.000` | td right |
| `Cliente` | customer name + phone | `María (0981…)` | td (a) |
| `Pago` | payment_method | `efectivo` | td |
| `Canal` | channel | `mostrador` | td |
| `Atendido por` | fulfilled_by | `ivan` | td |
| `Notas` | sale notes | `alias tuqui` | td |
| `Acciones` | buttons: crear pedido, anular | `+ 📄 Anular` | td |

**Totals row at bottom:**
| `Total ({{ count }} ventas)` | count | sum(qty) | sum(total_gs) |

### 5. Tooltips / hover text

| Element | Tooltip text |
|---|---|
| "Crear pedido" link | `Crear pedido para <customer_name> basado en esta venta` |
| Anular button (modal title) | `¿Anular venta #X?` |
| Anular button (modal body) | `Esta acción devuelve el stock y queda registrada en auditoría.` |
| Anular confirm label | `Sí, anular` |

### 6. UX/copy audit — flags

- `Cant.` abbreviation instead of `Cantidad` — fine for tight columns.
- `Pago` and `Canal` shown raw (`efectivo`/`mostrador`) — same display issue as ventas_detalle.
- The `Anular` button is an icon-only button (uses `<svg>` inside, no visible text on small screens) — relies on confirm modal. OK because confirm modal has `Anular` label.
- The `+ Pedido` button next to the row has no aria-label; relies on hover title. Borderline.

---

## ventas_qa.html — QA / smoke tests

### 1. Identity
- **URL/route**: `/ventas/qa`
- **Page title**: `QA · Ventas`
- **Section**: Dev / QA
- **User persona**: Dev, admin (deploy gate)

### 2. Structure
- H2: `¿Qué hace esta página?`
- Description block (paragraph)
- Run button
- Results table (`aria-label="Resultados"`)

### 3. All visible user-facing text

**Page description (static copy):**
- H2 + paragraph: `Cada test hace un fetch() contra un endpoint real de la app y verifica el resultado. Algunos tests crean datos de prueba (clientes QA-NNN, ventas QA-NNN) que quedan en la DB.`
- Note: `Tests create QA-NNN test data` (warning to operator)

**Button + link text:**
- `Run all tests` (the JS button `btn-run`; text comes from JS layer, default `Correr tests`)

**Table column headers:**
- `#`, `Test`, `Descripción`, `Estado`, `Detalle`

**Status badges (populated by JS):**
- `⏳ pendiente` (pending)
- `✅ ok` (passed)
- `❌ error` (failed)

### 4. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `#` | Test ID | `1` | td center |
| `Test` | Test name | `login + healthz` | td |
| `Descripción` | What the test checks | `verifies login + session` | td small |
| `Estado` | Pass/fail/pending | `✅ ok` | td badge |
| `Detalle` | Error message or "—" | `—` | td small |

### 5. Tooltips / hover text

(none)

### 6. UX/copy audit — flags

- "QA · Ventas" — uses middot, fine.
- The description paragraph uses `<code>` blocks for `fetch()` and `QA-NNN` — good technical clarity.
- The page mentions "clientes QA-NNN" test pollution but doesn't link to a cleanup tool — operator might forget to clean up.
- Status badges use emoji + word (✅ ok / ❌ error / ⏳ pendiente) — emoji colorblind-debatable; emoji plus word is OK.

---

## recibo.html — Printable receipt

### 1. Identity
- **URL/route**: `/ventas/{id}/recibo`
- **Page title**: (none — print-focused; title via `<title>` block)
- **Section**: Sales / receipt
- **User persona**: Cashier (print), customer (receives)

### 2. Structure
- Voided banner (top, only if voided): `<strong>ANULADO</strong>`
- Header: business info (h1 = business name from settings)
- Sale metadata: Venta # / Fecha / Atendido por
- Items list (qty × unit price)
- Totals: Descuento / Propina / Total / Pago
- Cliente line
- Notas line
- Footer: `¡Gracias por tu compra!`
- Barcode (CSS-rendered, monospace)
- Disclaimer: `Este recibo no es un comprobante fiscal.`
- Print button (`no-print` class — hidden in print)

### 3. All visible user-facing text

**Page-level messages:**
- `ANULADO` (voided banner)
- `¡Gracias por tu compra!` (footer)
- `Este recibo no es un comprobante fiscal.` (disclaimer)
- `Esta venta fue anulada.` (additional voided disclaimer in red)

**Metric labels:**
- `Venta` (metric-label)
- `Número`, `Fecha`, `Atendido por` (line labels)
- `Descuento`, `Propina`, `Pago`, `Cliente` (totals labels)
- `Notas` (notes section)

**Form actions (no-print):**
- `Imprimir` button: text via JS (`onclick="window.print();var c=parseInt(document.getElementById('print-count').textContent||'1')+1;..."`) — render text is `Imprimir` + count
- `Volver al historial` (back link)

**Tooltips / labels:**
- Barcode div: `aria-label="Código de barras del recibo"` (visual-only)

### 4. Displayed data

| Field | Semantics | Example | Visual |
|---|---|---|---|
| Business name | Tenant/operator name | `Panadería Kyrian` | h1 |
| `Venta #` | Sale ID | `#1234` | metric |
| `Fecha` | Sold-at | `07/10/2026 14:30` | line |
| `Atendido por` | Fulfilled-by | `ivan` | line |
| Item lines | `<qty> × <unit_price>` | `2 × Gs. 8.000` | line |
| `Descuento` | Discount (Gs.) | `0` | total |
| `Propina` | Tip (Gs.) | `1.000` | total |
| `Pago` | Total paid (Gs.) | `Gs. 17.000` | total |
| `Cliente` | Customer name | `María` | line |
| `Notas` | Sale notes | `alias tuqui` | paragraph |

### 5. Tooltips / hover text

(none)

### 6. UX/copy audit — flags

- Uses `m.gs()` for currency formatting (consistent with rest of app).
- The disclaimer `Este recibo no es un comprobante fiscal.` is a **legal disclaimer** — correct.
- `Atendido por` shows raw username (e.g. `ivan`); could be full name.
- `Venta #` doesn't include customer RUC/invoice line — separate path for fiscal.
- Print count increments each print — interesting audit hook (prevents operator from reprinting without awareness).

---

## caja.html — Cash register / drawer

### 1. Identity
- **URL/route**: `/caja`
- **Page title**: `Caja`
- **Section**: Cash management
- **User persona**: Operator (cashier)

### 2. Structure
- Flash alerts (success: caja_abierta / caja_cerrada)
- H2: `Caja abierta` (when session is open)
- Closing form (counted_gs)
- H2: `Abrir caja` (when no session)
- H2: `Sesiones recientes` (history table)

### 3. All visible user-facing text

**Page-level messages:**
- `<div class="alert alert-success">Caja abierta.</div>`
- `<div class="alert alert-success">Caja cerrada. <a href="/caja/z/{zid}">Ver ticket Z</a></div>`

**Button + link text:**
- `Cerrar caja (Z)` (submit closing)
- `Abrir caja` (submit opening)
- `Z` link (per row, when status='closed')

**Confirm modal data:**
- Title: `¿Cerrar caja?`
- Body: `Se registra el cierre del turno con el efectivo declarado.`
- `danger: true`

**Form labels + placeholders:**
- `Conteo físico al cerrar (Gs.)` (closing count)
- `Monto inicial (Gs.)` (opening amount)
- `Canal (opcional)` — placeholder `salón / delivery`

**Table column headers (Sesiones recientes):**
- `Apertura`, `Cierre`, `Apertura` (Gs.), `Esperado` (Gs.), `Contado` (Gs.), `Diff`, (action)

**Status badges / inline:**
- `<strong>abierta</strong>` (when session is open)
- Diff cell colored: red if diff ≠ 0, green if diff = 0

**Sample data display:**
- `Apertura: {{ s.opened_at.strftime('%d/%m %H:%M') }} · {{ s.opened_by }}`
- `Cierre: {{ closed_at or '<strong>abierta</strong>' }}`

### 4. Displayed data

**Open-session block:**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| `Apertura` | Opening amount (Gs.) | `50.000` | p/strong |
| `Esperado ahora (X)` | Expected drawer cash based on sales − payouts | `Gs. 78.500` | p/strong |

**Open-cash form:**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| `Monto inicial (Gs.)` | Cash put in drawer at start | `50.000` | input |
| `Canal (opcional)` | Optional channel tag | `salón / delivery` | input |

**Close-cash form:**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| `Conteo físico al cerrar (Gs.)` | Cash physically counted | `78.500` | input |

**Sesiones recientes table:**
| Column | Semantics | Example | Visual |
|---|---|---|---|
| Apertura (when) | opened_at | `07/10 09:00 · ivan` | td |
| Cierre (when) | closed_at or `<strong>abierta</strong>` | `07/10 18:00` | td |
| Apertura (Gs.) | opening_gs | `50.000` | td right |
| Esperado | expected_gs at close | `78.500` | td right |
| Contado | counted_gs | `78.500` | td right |
| Diff | counted − expected | `0` | td right (red if ≠0) |
| Action | Link to ticket Z if closed | `Z` | td center |

### 5. Tooltips / hover text

(none explicit; relies on confirm modal text.)

### 6. UX/copy audit — flags

- Page title is just `Caja` (singular) — fine; whole section is the cash register.
- Diff cell uses inline color: red when diff ≠ 0 (`var(--destructive, #b91c1c)`), green when 0. Works.
- No empty state for Sesiones recientes table — when empty, just shows nothing (blank rows).
- The opening form has no channel default — placeholder says `salón / delivery` (informal).
- `Cerrar caja (Z)` button shows the Z close-shift suffix — operator needs to know "Z" means close-shift.

---

## caja_z.html — Cash session Z-ticket (close-shift)

### 1. Identity
- **URL/route**: `/caja/z/{session_id}`
- **Page title**: `Caja` (same — Z-ticket inherits title block)
- **Section**: Cash management
- **User persona**: Operator, manager (audit)

### 2. Structure
- H1: ticket header (date + opened_by)
- Session summary block
- Sales breakdown by payment method
- Cash count summary
- Diff line
- Print button

### 3. All visible user-facing text

**Page-level messages:**
- Banner if session is still open: `Esta caja sigue abierta.`

**Field labels:**
- `Apertura: {{ opening_gs }}`
- `Esperado ahora: {{ expected_gs }}`
- `Contado: {{ counted_gs }}`
- `Diferencia: {{ diff_gs }}` (color-coded)

**Button text:**
- `Imprimir Z` (print)
- `← Volver a caja` (back)

### 4. Displayed data

| Field | Semantics | Example | Visual |
|---|---|---|---|
| `Apertura` | opening_gs | `50.000` | p |
| `Ventas (efectivo)` | total cash sales | `Gs. 78.000` | p |
| `Esperado` | opening + cash sales | `Gs. 128.000` | p |
| `Contado` | operator's count | `Gs. 128.000` | p |
| `Diferencia` | counted − expected | `0` | p (red if ≠0) |
| `Cierre:` | closed_at | `07/10/2026 18:00` | p |

### 5. Tooltips / hover text

(none)

### 6. UX/copy audit — flags

- "Esperado" vs "Esperado ahora" — two distinct concepts; the close ticket shows the full report, the live caja shows current. Consistent.
- The Z-ticket is essentially a printable shift-close summary — no per-product breakdown here; that lives in /reportes.

---

## wishlist.html — Operator wishlist (not on sale sheet; input inventory)

> Note: wishlist is technically in the inventory section but lives under customer wishlist category. Treating it as a separate page.

### 1. Identity
- **URL/route**: `/wishlist`
- **Page title**: `Lista de deseos · Sazón`
- **Section**: Operator's personal wishlist (input for pedidos)
- **User persona**: Operator (personal wishlist)

### 2. Structure
- H2: `Lista de deseos` (with count of items)
- Sub-heading: per-priority bucket
- Table per priority
- Action buttons

### 3. All visible user-facing text

**Page-level messages:**
- Count badge per priority: `({{ count }})`

**Button + link text:**
- `Marcar comprado` (mark purchased)
- `🛒` (send to shopping list; title: `Enviar a la lista de compras`)

**Table column headers:**
- `ID`, `Item`, `Qty`, `Unit Gs.`, `Total Gs.`, `Categoría`, `Dónde comprar`, `Status`, (action)

**Sample data display:**
- `{{ item.code }}` (raw code; may be empty)
- `{{ fmt.entity_name(item) }}` (item name)
- `{{ item.notes or '' }}` (item notes)
- `{{ m.gs(item.unit_price_gs) }}` (unit price Gs.)
- `{{ m.gs(item.unit_price_gs * item.quantity) }}` (line total Gs.)

### 4. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `ID` | item code | `W-12` | td code |
| `Item` | item name + notes | `Harina 0000` / `Notas…` | td strong + small |
| `Qty` | quantity | `5` | td |
| `Unit Gs.` | unit price (Gs.) | `12.000` | td right |
| `Total Gs.` | line total (Gs.) | `60.000` | td right strong |
| `Categoría` | category | `Insumos` | td |
| `Dónde comprar` | buy_location | `Casa Carlos` | td small |
| `Status` | status | `pendiente` | td |
| (action) | buttons: marcar comprado / enviar | `🛒` | td |

### 6. UX/copy audit — flags

- The `Wishlist` is operator's personal wishlist (not customer-facing). Title uses `Lista de deseos` (Spanish).
- Action button `🛒` is emoji-only — needs `aria-label`; title attr is `Enviar a la lista de compras` which screen readers pick up.
- "Dónde comprar" is a separate column — common for shop owners (they buy from multiple suppliers).

---

## clientes.html — Customer directory

### 1. Identity
- **URL/route**: `/clientes`
- **Page title**: `Clientes`
- **Section**: CRM
- **User persona**: Operator, manager

### 2. Structure
- Title `<title='Clientes'>`
- Banner: `Datos incompletos — completá las fichas para que las alertas y...` (warn about incomplete data)
- Filter row (search + tier + actions)
- Bulk delete button
- Customers table
- Pagination

### 3. All visible user-facing text

**Page-level messages:**
- `Datos incompletos — completá las fichas para que las alertas y ...` (banner; truncated in template; full text in router: `Datos incompletos — completá las fichas para que las alertas y resúmenes sean correctos.`)
- `Mostrando 1–25 de <N> clientes` (pagination)
- `{{ ui.empty_state(title="No hay clientes todavía", ...) }}`

**Button + link text:**
- `Filtrar` (submit filters)
- `Limpiar todo` (clear all filters)
- `bulkDeleteClients()` (bulk-delete button via JS; rendered as danger-ghost)
- `Ver` (per-row link to detail)
- `+ Pedido` (per-row link to new pedido; title `Crear pedido nuevo para <customer_name>`)
- `← Anterior`, `Siguiente →` (pagination)

**Filter form:**
- `Buscar nombre o teléfono…` (search placeholder)
- `Nivel: <tier> ▾` (filter dropdown; tiers shown: `Todos`, then per-tier labels via `fmt.status_es(t)`)
- Per-tier filter options: each tier label (e.g. `Nuevo`, `Ocasional`, `Frecuente`, `VIP`)

**Table column headers:**
- (checkbox column) `Seleccionar todos` (header aria-label)
- (sortable) `Cliente` (with sort indicator)
- `Teléfono`
- (sortable) `# Ventas` (with sort indicator)
- (sortable) `Gastado (Gs.)`
- `Puntos`
- (sortable) `Última`
- `Sub · Ped` (active subs / open pedidos; title `Suscripciones activas / Pedidos abiertos`)
- `Registrado`
- (actions)

**Status badges:**
- `Sub` (badge-info, title `<n> suscripción(es) activa(s)`)
- `<n>p` (badge-warn, title `<n> pedido(s) abierto(s)`) — note the abbreviation `p`

**Sample data display:**
- `{{ c.phone }}` (phone)
- `{{ c.n_sales }}` (count)
- `{{ m.gs(c.lifetime_spend_gs) }}` (Gs. formatted)
- `{{ c.points }}` (points)
- `{{ c.last_sale_at.strftime('%d/%m/%y') }}` (last sale date)
- `{{ c.created_at.strftime('%d/%m/%Y') }}` (created date)

**Customer name cell:**
- `data-copy="{{ c.id }}" title="Click to copy ID"` — operator clicks the name to copy the customer ID to clipboard.

### 4. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| (checkbox) | select for bulk action | `<input>` | td checkbox |
| `Cliente` | customer name | `María` | td strong |
| `Teléfono` | phone | `0981 123 456` | td |
| `# Ventas` | lifetime sale count | `42` | td right |
| `Gastado (Gs.)` | lifetime spend (Gs.) | `Gs. 350.000` | td right |
| `Puntos` | points balance | `220` | td right |
| `Última` | last sale date | `07/10/26` | td right small |
| `Sub · Ped` | active subs / open pedidos | `Sub 2p` | td badges |
| `Registrado` | created_at | `15/03/2026` | td small |
| (actions) | `Ver` link | `Ver` | td |

**Filter dropdown trigger: `Nivel: <tier> ▾`** — the `▾` is a unicode arrow.

### 5. Tooltips / hover text

| Element | Tooltip text |
|---|---|
| Customer name | `Click to copy ID` (title on `<strong>` cell) |
| `Sub` badge | `<n> suscripción(es) activa(s)` |
| `<n>p` badge | `<n> pedido(s) abierto(s)` |
| `+ Pedido` link | `Crear pedido nuevo para <customer_name>` |
| `Sub · Ped` header | `Suscripciones activas / Pedidos abiertos` |

### 6. UX/copy audit — flags

- `Datos incompletos` banner — full text appears in router-side; template only shows truncated copy. Should be in a single place to avoid drift.
- `Sub · Ped` header uses middot; the value uses badges `Sub` (info-blue) + `<n>p` (warn-orange). Mixed signal — `Sub` always shows when 0+ subs (which is misleading if 0).
- Tier dropdown uses `▾` Unicode arrow — consistent with other dropdowns; OK.
- `<n>p` abbreviation is opaque — no aria-label, only a title attr.
- `Ver` per-row action is Spanish for "view" — could be more specific ("Ver ficha").
- Bulk-delete button calls `bulkDeleteClients()` JS — no confirm-modal text visible in the template (handled by JS modal).

---

## cliente_detalle.html — Customer detail page

### 1. Identity
- **URL/route**: `/clientes/{customer_id}`
- **Page title**: `<customer.name|title> — Cliente`
- **Section**: CRM
- **User persona**: Operator, manager

### 2. Structure
- Breadcrumb: `Clientes › <name>`
- H1: customer name (or `(sin nombre)` fallback)
- Status indicator (icon: title `Sin compras hace más de 90 días`, `Última compra hace N días — recontactar`, `Compró en los últimos N días`)
- Subscription info card (if active sub)
- `Contacto` card (phone, WhatsApp, email, CI/RUC, customer since)
- `Notas` card
- `Perfiles de facturación` card (invoice profiles)
- `Direcciones de entrega` card
- `Actividad` card
- `Zonas de compra` (mini-section)
- `Puntos de fidelidad` card (with `Canjear puntos` form)
- `Sugerencias automáticas` card
- `Pedidos recientes` card

### 3. All visible user-facing text

**Page-level messages:**
- H1 fallback: `(sin nombre)` (when name is null)
- `Preguntar siempre en cada pedido.` (italic note)
- `Sin notas registradas.` (italic, when notes empty)
- `Sin perfiles de facturación registrados.` (italic, when empty)
- `Sin direcciones guardadas.` (italic, when empty)
- `Sin movimientos. Los puntos se acumulan automáticamente con cada venta.` (italic, when empty)

**Button + link text:**
- `📞 <phone>` (tel: link)
- `💬 WhatsApp` (wa.me link to `595<phone>`)
- `Canjear` (redeem points submit; `<button type="submit">` — JS confirms)
- `+ Pedido` (per-pedido row, same as clientes.html)
- `<button type="submit">` for saving notes (button text is generic; needs label)

**Subscription card:**
- `<h2>{{ sub.cadence }} · {{ sub.price_gs }}</h2>`
- Sub notes (small text)

**Contacto card:**
- Labels: `Teléfono`, `Email`, `CI / RUC`, `Cliente desde`
- Phone button text: `📞 <phone>`
- WhatsApp button text: `💬 WhatsApp`

**Actividad card:**
- Labels: `Cliente registrado`, `Última compra`, `Perfil actualizado`

**Zonas de compra mini-section:**
- H3: `Zonas de compra`
- Labels: `Gasto total`, `Visitas`, `Puntos`

**Puntos de fidelidad card:**
- H3: `Canjear puntos`
- Label: `Cantidad a canjear` (placeholder `ej. 10`)
- Label: `Motivo` (placeholder `ej. descuento por cumpleaños`)
- Submit button: (generic)

**Puntos movimientos table:**
- Headers: `Fecha`, `Motivo`, `Δ`, `Venta`
- Cells: `tx.recorded_at.strftime('%Y-%m-%d %H:%M')`, motive text, delta colored green/red, `tx.sale_id` link

**Sugerencias automáticas card:**
- Auto-suggestions: rendered dynamically (likely via JS)

**Pedidos recientes card:**
- H2: `Pedidos recientes`
- Per row: `#{{ pedido.id }}` link, button `Re-petir este pedido` (title)

### 4. Displayed data

**Status indicator (icon title):**
| Status | Title text |
|---|---|
| `Sin compras hace más de 90 días` | (no name) |
| `Última compra hace {{N}} días — recontactar` | (urges outreach) |
| `Compró en los últimos {{N}} días` | (recent) |

**Puntos movimientos table:**
| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Fecha` | tx.recorded_at | `2026-10-07 14:30` | td |
| `Motivo` | reason text | `Compra #1234` | td |
| `Δ` | delta (color: green if >0, red if <0) | `+15` | td right |
| `Venta` | linked sale ID | `#1234` | td a |

**Perfiles de facturación:**
| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Alias` | invoice alias | `Personal` | td |
| `Por defecto` badge | is_default=true | (badge) | td |
| `RUC/CI` | ruc_ci | `80012345-6` | td |
| `Razón social` | razon_social | `María S.A.` | td |

**Direcciones de entrega:**
| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Etiqueta` | address label | `casa` | td |
| `Por defecto` badge | is_default=true | (badge) | td |
| `Dirección` | address_text | `Calle Palma 123` | td |
| `Zona` | zone_id → name | `Centro` | td |
| (action) | buttons: ★ (default) / ✕ (delete) | `★ ✕` | td |

### 5. Tooltips / hover text

| Element | Tooltip text |
|---|---|
| Status icon (no sales 90d) | `Sin compras hace más de 90 días` |
| Status icon (last sale N days ago) | `Última compra hace {{N}} días — recontactar` |
| Status icon (recent) | `Compró en los últimos {{N}} días` |
| Address kind | `{{ a.address_kind }}` (shown via title) |
| `Re-petir` button | `Re-petir este pedido` |

### 6. UX/copy audit — flags

- "Canjear" button has no visible text in template — needs a label or aria-label.
- "Re-petir" uses hyphen instead of accent — should be `Repetir`.
- Multiple cards use italic `<p>` for empty states; consistent style.
- `Sin notas registradas.` comments in italic across the page — consistent.
- `email` shown as `mailto:` link; `CI/RUC` shown as plain text (no copy).
- No way to edit customer from detail (must use `/clientes/{id}/editar`).
- Subscription card doesn't show cancel/pause controls — link to /suscripciones for that.

---

## cliente_editar.html — Customer edit form

### 1. Identity
- **URL/route**: `/clientes/{customer_id}/editar`
- **Page title**: `Editar <name> — Cliente`
- **Section**: CRM
- **User persona**: Operator, manager

### 2. Structure
- Breadcrumb: `Clientes › <customer> › Editar`
- H1: `Editar <name>` (or `Editar cliente` if no name)
- Error banner: `No se pudo guardar: <form_error>`
- Fieldset `Perfil`
- Fieldset `Direcciones de delivery`
- Fieldset `Perfiles de facturación`
- Fieldset `Perfil dietético`

### 3. All visible user-facing text

**Page-level messages:**
- Error banner: `<strong>No se pudo guardar:</strong> {{ form_error }}`

**Button + link text:**
- `Guardar` (submit)
- `Cancelar` (link back to detail)

**Perfil fieldset:**
- `Nombre *` (required)
- `Teléfono`
- `Email`
- `CI / RUC`
- `Notas`
- `Cumpleaños` (placeholder `DD-MM o DD-MM-AAAA`, maxlength 10, helper `Para promos de cumpleaños.`)
- `¿Cómo nos encontró?` (how_found)
- `Canal preferido` (preferred_channel)
- `Acepta recibir promos (WhatsApp)` (checkbox)

**Facturación (within Perfil):**
- `Facturación — razón social` (invoice_name; placeholder `For pedidos con factura`)
- `Facturación — RUC / CI` (invoice_ruc; placeholder `Se precarga en pedidos`)

**Direcciones de delivery fieldset:**
- Existing table headers: `Etiqueta`, `Dirección`, `Zona`, (action)
- Per-row badges: `predet.` (default)
- Buttons: `★` (set default; aria-label `Marcar <label> como predeterminada`), `✕` (delete; aria-label `Eliminar dirección <label>`)
- Empty message: `Sin direcciones guardadas.`
- New-address form: labels `Etiqueta` (placeholder `casa`), `Dirección` (placeholder `Calle, número, barrio…`), `Zona`
- Add button: `+ Agregar`

**Perfiles de facturación fieldset:**
- Existing table headers: `Alias`, `RUC / CI`, `Razón social`, `Tipo`, (action)
- Per-row badges: `predet.`
- Buttons: `★` (aria-label `Marcar <alias> como predeterminado`), `✕` (aria-label `Eliminar perfil <alias>`)
- Empty message: `Sin perfiles de facturación. El cliente se factura siempre con RUC/CI manual.`
- New-profile form: labels `Alias` (placeholder `Personal`), `RUC / CI` (placeholder `80012345-6`), `Razón social / Nombre` (placeholder `Kyrian Weiss o Empresa S.A.`)
- Tipo de documento options: `CI paraguaya`, `Pasaporte`, `CI extranjera`, `Carnet de residencia`, `Innominado`, `Tarjeta diplomática (exoneración)`, `Otro`
- Tipo de operación options: `B2C (consumidor final)`, `B2B (entre empresas)`, `B2G (gobierno)`, `B2F (extranjero)`
- Add button: `+ Agregar perfil`

**Perfil dietético fieldset:**
- Hint paragraph: about dietary preferences/allergens
- Inline labels: dietary chips (text populated from data)

### 4. Displayed data

**Perfil fields:**
| Field | Semantics | Example |
|---|---|---|
| `Nombre *` | customer name | `María González` |
| `Teléfono` | phone | `0981 123 456` |
| `Email` | email | `maria@example.com` |
| `CI / RUC` | tax id | `1234567-8` |
| `Notas` | notes | `Cliente VIP, sin TACC` |
| `Cumpleaños` | DD-MM or DD-MM-AAAA | `15-03` or `15-03-1990` |
| `¿Cómo nos encontró?` | how_found | `Instagram` |
| `Canal preferido` | preferred_channel | `WhatsApp` |
| `Acepta recibir promos (WhatsApp)` | accepts_promo checkbox | `checked` |

**Direcciones table:**
| Column | Semantics | Example |
|---|---|---|
| `Etiqueta` | label | `casa` |
| `Dirección` | address_text | `Calle Palma 123` |
| `Zona` | zone name | `Centro` |
| (action) | ★ / ✕ | `★ ✕` |

**Perfiles facturación table:**
| Column | Semantics | Example |
|---|---|---|
| `Alias` | alias | `Personal` |
| `RUC / CI` | ruc_ci | `80012345-6` |
| `Razón social` | razon_social | `María S.A.` |
| `Tipo` | tipo_documento · tipo_operacion | `CI_PARAGUAYA · B2C` |

### 5. Tooltips / hover text

(none explicit; relies on aria-labels for icon buttons.)

### 6. UX/copy audit — flags

- Many icon-only buttons rely on aria-label — good for accessibility.
- `predet.` abbreviation instead of `Por defecto` (Spanish native) — short, but unexplained.
- Tipo de documento dropdown uses internal values (`CI_PARAGUAYA`) as option values; visible labels are Spanish — clean.
- "Se precarga en pedidos" — clear helper text.
- `Facturación — razón social` label is long but unambiguous.

---

## clientes_nuevo.html — New customer form

### 1. Identity
- **URL/route**: `/clientes/nuevo`
- **Page title**: `Nuevo cliente`
- **Section**: CRM
- **User persona**: Operator

### 2. Structure
- Breadcrumb: `Clientes › Nuevo cliente`
- H1: `Nuevo cliente`
- Perfil fieldset (same as cliente_editar minus direccciones/perfiles facturación)
- Submit + Cancel

### 3. All visible user-facing text

**Form labels + placeholders:**
- `Nombre`
- `Teléfono`
- `Email`
- `CI / RUC`
- `Notas`
- `Cumpleaños` (placeholder `DD-MM o DD-MM-AAAA`, maxlength 10, helper `Para promos de cumpleaños.`)
- `¿Cómo nos encontró?`
- `Canal preferido`
- `Acepta recibir promos (WhatsApp)`

**Legend:**
- `Perfil (opcional)` (fieldset legend)

**Button + link text:**
- `Crear cliente` (submit primary)
- `Cancelar` (link to /clientes)

**Helper:**
- `Si el teléfono ya existe, se actualizará ese cliente.` (inline helper, right-aligned)

### 4. Displayed data

Same shape as cliente_editar's Perfil section, but no existing data — empty form.

### 5. Tooltips / hover text

(none)

### 6. UX/copy audit — flags

- Perfil is marked `(opcional)` — all fields are optional except `Nombre` (implied by asterisk on edit; new page doesn't show asterisk, but form still requires it server-side).
- "Si el teléfono ya existe, se actualizará ese cliente." — important behavior; well-documented inline.

---

## clientes_duplicados.html — Duplicate customer detection

### 1. Identity
- **URL/route**: `/clientes/duplicados`
- **Page title**: `Clientes duplicados`
- **Section**: CRM / data hygiene
- **User persona**: Manager, admin

### 2. Structure
- H1: `Clientes duplicados`
- Back link: `← Volver al directorio`
- Description paragraph
- Per-group section: `Canónico (sobrevive)` + `Duplicados (se fusionan)`
- Per-group: merge form with list

### 3. All visible user-facing text

**Page-level messages:**
- Description: `El registro canónico sugerido es el más antiguo (menor id); podés cambiarlo antes de fusionar.`
- Empty state: `No se detectaron duplicados`

**Section headings:**
- H2: `<canonical.name> <small>(id={{ canonical.id }})</small>`
- H3 (per group): `Canónico (sobrevive)` — uppercase, muted color
- H3 (per group): `Duplicados (se fusionan)` — uppercase, muted color

**Button + link text:**
- `← Volver al directorio` (back link)
- `Fusionar en canónico` (merge submit, primary)

**Sample data display:**
- `{{ fmt.entity_name(g.canonical) }} <small>(id={{ g.canonical.id }})</small>`
- Per duplicate: `{{ fmt.entity_name(d) }} <small>(id={{ d.id }})</small>`

### 4. Displayed data

Per duplicate group:
- Canonical entry: name + ID
- Duplicate list: each entry with name + ID
- Merge button (per duplicate)

### 5. Tooltips / hover text

| Element | Tooltip text |
|---|---|
| Page title icon area | `title='Clientes duplicados'` (browser tab tooltip) |
| Empty state | `title='No se detectaron duplicados'` |

### 6. UX/copy audit — flags

- Page uses uppercase H3 headers with `var(--color-muted)` — distinct visual style.
- Merge logic: "El registro canónico sugerido es el más antiguo" — clear policy.
- No bulk merge — one group at a time.

---

## creditos.html — Image credits

### 1. Identity
- **URL/route**: `/creditos`
- **Page title**: `Créditos de imágenes — Sazón`
- **Section**: Legal / attributions
- **User persona**: Manager, admin (rare)

### 2. Structure
- H1: `Créditos de imágenes` (with `<svg>` icon)
- Description paragraph
- Table: image / attribution / source

### 3. All visible user-facing text

**Page-level messages:**
- Description: `Las fotografías de productos y recetas de este sistema provienen de Openverse bajo licencias Creative Commons.`

**Table column headers:**
- `Imagen`, `Autoría y licencia`, `Fuente`

**Sample data display:**
- `{{ e.entity }}` (image name)
- `{{ e.credit }}` (attribution + license text)
- `ver original` (link to source URL)

**Empty state:**
- `ui.empty_state(title="Sin imágenes registradas", icon="icon-image", hint="Todavía no hay imágenes con atribución registradas.")`

### 4. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Imagen` | entity (e.g. product name) | `Chipa` | td |
| `Autoría y licencia` | credit text | `Foto de Juan Pérez / CC BY 2.0` | td |
| `Fuente` | source URL link | `ver original` | td a |

### 5. Tooltips / hover text

(none)

### 6. UX/copy audit — flags

- Page is functional but very rare — links to Openverse (`https://openverse.org`) for context.
- No filter/sort — minimal page.

---

## suscripciones.html — Subscriptions list

### 1. Identity
- **URL/route**: `/suscripciones`
- **Page title**: `Suscripciones`
- **Section**: CRM / recurring orders
- **User persona**: Operator, manager

### 2. Structure
- H1: `Suscripciones`
- Hint paragraph (mentions Pedidos pendientes link)
- Filter nav: `<nav aria-label="Filtrar por estado">` with status filters
- Subscriptions table
- Pagination

### 3. All visible user-facing text

**Page-level messages:**
- Hint: `Para gestionar entregas semanales/quincenales/mensuales...`
- Pagination: `Mostrando 1–25 de <N> suscripciones`
- Empty state title: `Sin suscripciones todavía`

**Button + link text:**
- `<a href="/pedidos?status_filter=pendientes">Pedidos pendientes</a>` (link in hint)
- `<button>` (per row: status actions) — `Pausar`, `Reanudar`, `Cancelar`, `Eliminar`
- `Pausar`, `Reanudar` (per-row action; green/grey)

**Confirm modals:**
- Title: `¿Cancelar suscripción?`
- Body: `La suscripción quedará como cancelada y no generará más recordatorios.`
- Title: `¿Eliminar suscripción?`
- Body: `Esta acción no se puede deshacer.`

**Form label + filter options:**
- Status options: (all/activa/pausada/cancelada — render via filter nav)

**Table column headers:**
- `Cliente`, `Descripción`, `Cadencia`, `Día / hora`, `Precio Gs.`, `Vigencia`, `Estado`, (actions)

**Status badges:**
- `Semanal`, `Quincenal`, `Mensual` (cadence badges; all `badge-info`)
- `activa`, `pausada`, `cancelada` (status; rendered dynamically)

**Sample data display:**
- `{{ cust.name }}` (with phone in `<small>` below)
- `cliente eliminado` (when customer was deleted; italic muted)
- `{{ s.notes or '' }}` (notes)
- `{{ s.preferred_time }}` (time, in `<small>`)
- `{{ m.gs(s.price_gs) }}` (Gs. formatted)
- `desde {{ s.start_date.strftime('%d/%m/%Y') }}`
- `hasta {{ s.end_date.strftime('%d/%m/%Y') }}` (if end_date)
- `sin fin` (italic muted; if no end_date)

### 4. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Cliente` | customer name + phone | `María (0981…)` | td |
| `Descripción` | product_summary | `1 kg chipa + 2 facturas` | td |
| `Cadencia` | cadence badge | `Semanal` | td |
| `Día / hora` | preferred day/time | `Sábados 09:00` | td |
| `Precio Gs.` | price_gs | `Gs. 80.000` | td right |
| `Vigencia` | date range | `desde 01/10/2026 → sin fin` | td small |
| `Estado` | status | `activa` | td badge |
| (actions) | buttons | `Pausar Reanudar Cancelar Eliminar` | td |

### 5. Tooltips / hover text

| Element | Tooltip text |
|---|---|
| Cancel modal title | `¿Cancelar suscripción?` |
| Cancel modal body | `La suscripción quedará como cancelada y no generará más recordatorios.` |
| Delete modal title | `¿Eliminar suscripción?` |
| Delete modal body | `Esta acción no se puede deshacer.` |
| Empty state | `Sin suscripciones todavía` |

### 6. UX/copy audit — flags

- All cadence badges use same color (`badge-info`) — `Semanal`/`Quincenal`/`Mensual` are visually indistinguishable.
- `<button>` per-row actions use no text labels — rely on action names from JS.
- `cliente eliminado` (italic muted) is a fallback; correct.
- `desde/hasta/sin fin` formatting is consistent.

---

## suscripcion_form.html — Subscription form (new/edit)

### 1. Identity
- **URL/route**: `/suscripciones/nueva` or `/suscripciones/{id}/editar`
- **Page title**: `Nueva suscripción` or `Editar suscripción`
- **Section**: CRM / recurring orders
- **User persona**: Operator, manager

### 2. Structure
- H1 (set by `title`): `Nueva suscripción` or `Editar suscripción`
- Warning block (when no customers exist)
- Form: fields per spec

### 3. All visible user-facing text

**Page-level messages (when no customers):**
- `<strong>No hay clientes todavía.</strong>`
- `Antes de crear una suscripción necesitás <a href="/clientes">cargar al menos un cliente</a>.`

**Form labels + placeholders:**
- `Cliente *` (customer_id, required)
- `Descripción del pedido *` (product_summary; placeholder `Ej: 1 kg de chipa + 2 facturas`)
- `Cadencia *` (cadence; options: Semanal / Quincenal / Mensual)
- `Estado` (status; options: activa / pausada)
- `Día preferido` (preferred_day_of_week)
- `Hora preferida` (preferred_time; placeholder `Ej: 09:00`)
- `Fecha de inicio *` (start_date; required)
- `Fecha de fin (opcional)` (end_date)
- `Precio estimado (Gs.)` (price_gs; placeholder `0`)
- `Notas` (notes; placeholder `Ej: pasa los sábados a retirar antes del cierre`)

**Button + link text:**
- `<button type="submit" disabled if no customers>` (saves; label `Guardar`)
- `Cancelar` (link to /suscripciones)

### 4. Displayed data

| Field | Semantics | Example |
|---|---|---|
| `Cliente *` | customer_id | `María` |
| `Descripción del pedido *` | product_summary | `1 kg chipa + 2 facturas` |
| `Cadencia *` | weekly/biweekly/monthly | `Semanal` |
| `Estado` | activa/pausada | `activa` |
| `Día preferido` | day of week | `Sábado` |
| `Hora preferida` | time HH:MM | `09:00` |
| `Fecha de inicio *` | start date | `01/10/2026` |
| `Fecha de fin (opcional)` | end date | `31/12/2026` |
| `Precio estimado (Gs.)` | price_gs | `80.000` |
| `Notas` | notes | `pasa los sábados a retirar antes del cierre` |

### 5. Tooltips / hover text

(none)

### 6. UX/copy audit — flags

- Required fields marked with `*` — consistent.
- "Fecha de fin (opcional)" — explicit (optional) suffix.
- Helper copy in placeholders — operator gets example format on focus.

---

## fiado.html — Fiado (customer credit) list

### 1. Identity
- **URL/route**: `/fiado`
- **Page title**: `Fiado`
- **Section**: Credit (informal credit extended to customers)
- **User persona**: Operator, manager

### 2. Structure
- H1: `Fiado`
- Aging buckets: `Por vencer (0-30 d)`, `31-60 días`, `61+ días`
- Accounts table

### 3. All visible user-facing text

**Page-level messages:**
- Aging labels (3 buckets): `Por vencer (0-30 d)`, `31-60 días`, `61+ días`
- Empty: `Sin cuentas de fiado todavía.`

**Button + link text:**
- `Ver` (per-row link to /fiado/{customer_id})

**Table column headers:**
- `Cliente`, `Saldo`, `Límite`, `Estado`, (action)

**Sample data display:**
- `{{ r.nombre }}` (customer name)
- `{{ m.gs(r.saldo) }}` (current balance, Gs.; red if > 0, green if 0)
- `{{ m.gs_full(r.limit_gs) }}` (credit limit; or `—` if no limit)
- `{% if r.active %}activa{% else %}<strong>suspendida</strong>{% endif %}`

### 4. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Cliente` | customer name | `María` | td |
| `Saldo` | outstanding balance | `Bs. 35.000` | td right (red if >0) |
| `Límite` | credit limit (or —) | `Bs. 50.000` | td right |
| `Estado` | active or suspended | `activa` / `suspendida` | td center |
| (action) | link to detail | `Ver` | td center |

### 5. Tooltips / hover text

(none)

### 6. UX/copy audit — flags

- Aging buckets render as small muted labels (totals per bucket shown elsewhere).
- Currency formatting uses `m.gs_full()` for limits (full format) but `m.gs()` for saldo (short format) — inconsistent.
- "Fiado" is a Paraguay-specific informal-credit term — correct in context.
- No filter/search — list is short enough.

---

## fiado_cliente.html — Fiado detail (per customer)

### 1. Identity
- **URL/route**: `/fiado/{customer_id}`
- **Page title**: `Fiado · <customer.name>`
- **Section**: Credit
- **User persona**: Operator, manager

### 2. Structure
- H1: customer name
- Status line: `Estado: activa` or `Estado: <strong>suspendida</strong>`
- Flash messages: `Cargo registrado`, `Pago registrado`, `Ese pago ya estaba registrado (idempotencia)`
- Section: `Cargar (ajuste manual)` (charge form)
- Section: `Cobrar pago` (payment form)
- Section: `Cuenta` (account info; status toggle)
- Section: `Historial` (movements table)

### 3. All visible user-facing text

**Page-level messages:**
- `Cargo registrado.` (success flash)
- `Pago registrado.` (success flash)
- `Ese pago ya estaba registrado (idempotencia).` (warning flash — duplicate)
- `Sin movimientos.` (empty state)

**Button + link text:**
- `Cargar` (charge submit)
- `Cobrar` (payment submit; primary)

**Form labels + placeholders:**
- `Monto Gs.` (input placeholder; required, min=1, step=1)
- `Nota (opcional)` (note placeholder)
- (for payment form, same fields)

**Section labels:**
- `Cargar (ajuste manual)`
- `Cobrar pago`
- `Cuenta`
- `Historial`

**Table column headers:**
- `Fecha`, `Tipo`, `Monto`, `Nota`

**Sample data display:**
- `{{ tx.ts.strftime('%d/%m/%Y %H:%M') }}` (timestamp)
- `{{ tx.kind }}` (transaction kind: cargo / pago)
- `{{ m.gs_full(tx.amount_gs) }}` (amount; red if positive, green if negative)
- `{{ tx.note or '' }}` (note)

### 4. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Fecha` | ts | `07/10/2026 14:30` | td |
| `Tipo` | kind | `cargo` | td |
| `Monto` | amount_gs | `Bs. 35.000` | td right (red if >0) |
| `Nota` | note | `casa` | td |

### 5. Tooltips / hover text

(none)

### 6. UX/copy audit — flags

- Idempotency warning is explicit (`Ese pago ya estaba registrado`) — correct behavior.
- "Cargar" vs "Cobrar" — verb selection is good (charge = add debt, cobrar = collect).
- Both forms have the same fields but different submit button labels — minor risk of operator confusion if they look similar.
- No limit indicator shown on the page — operator must remember limit from /fiado list.

---

## Section-wide issues

### Cross-page consistency

| Issue | Pages affected | Notes |
|---|---|---|
| **Currency format inconsistency** | ventas_detalle, ventas_historial, fiado, fiado_cliente | Some pages use `m.gs()` (short: `Gs. 8.000`); others use `m.gs_full()` (full: `Gs. 8.696.000`). Recommend one standard. |
| **Raw value display** | ventas_detalle, ventas_historial, recibo | `Pago` (`efectivo`) and `Canal` (`mostrador`) shown as raw stored values instead of capitalized display labels. Inconsistent with combo display names. |
| **Spanish vs English loan words** | ventas.html | `Quick-sell` (English) vs `venta rápida` (Spanish placeholder). Same concept in two languages. |
| **Abbreviation `p`** in badges | clientes.html | `<n>p` (open pedidos badge) — abbreviation without explanation. |
| **`predet.` abbreviation** | cliente_editar.html | `predet.` for `Por defecto`. Common Spanish abbreviation but undocumented. |
| **Icon-only buttons without title** | ventas.html | Some svg-only buttons rely on aria-label; if aria-label missing, screen readers fail. Cross-page audit needed. |
| **Multiple `<button>` per row** | suscripciones.html, clientes.html | Per-row actions (Pausar/Reanudar/Cancelar/Eliminar) use plain `<button type="submit">` with text — OK, but worth verifying that JS doesn't override the label. |
| **Customer / Comprador terminology** | ventas.html | Uses `Cliente` consistently. No issue found. |
| **Pedido / Orden terminology** | ventas.html, cliente_detalle.html | Uses `Pedido` consistently. No issue found. |
| **`salón` vs `salon` accent** | ventas.html | Default channel value `salon` (no accent); display uses `Mostrador`. Future channel options must use accent for display, raw without for storage. |
| **Haccp / Compliance copy** | None of these templates | HACCP-related pages (produccion_haccp.html) live in production section. |
| **AI / Copilot text** | None | Only ventas_qa has automated test descriptions. AI copy elsewhere is in copiloto.html (Section E). |

### Copy issues

| Page | Issue |
|---|---|
| ventas.html | `invoice_type` default is `boleta_resimple` for non-general tax regime; label `Boleta Resimple (IRE RESIMPLE)` may confuse non-accountant operators. |
| ventas.html | The cross-sell rail is JS-populated with no "no suggestions available" fallback. |
| ventas.html | The Venta libre tile uses `<svg>` plus `Venta libre` and `Precio a definir` — operator may not know what "Precio a definir" means without clicking. |
| ventas_qa.html | Creates test pollution (`QA-NNN`) without documenting cleanup. |
| recibo.html | `Atendido por` shows raw username (e.g. `ivan`) — should display full name. |
| cliente_detalle.html | "Re-petir este pedido" — typo: should be `Repetir`. |
| cliente_detalle.html | "Canjear" button has no visible text — needs label. |
| clientes.html | Tier filter dropdown uses `▾` Unicode arrow — depends on font support. |
| fiado.html | Aging bucket totals not visible on this page (rendered elsewhere). |
| fiado_cliente.html | Both forms (Cargar / Cobrar) have identical fields; only submit button differs. Risk of operator error. |

### Spanish-language quality

- Generally **excellent** Spanish throughout; native Paraguayan vocabulary (mostrador, fiado, boleta_resimple, IRE RESIMPLE) used correctly.
- One English loan word: `Quick-sell` (ventas.html).
- One Italian/Spanish typo: `Re-petir` (cliente_detalle.html).
- Internal values like `boleta_resimple`, `CI_PARAGUAYA`, `B2C` are consistent with Paraguayan tax/regulatory terms.

### Accessibility gaps

- Most icon-only buttons have `aria-label` or `title` — good.
- Color-only signals (Diff column in Caja) need also a textual indicator. Currently only color (red/green) + value. The text value itself shows the diff so it's readable.
- `preflight-banner` (ventas.html) uses color + text — good.
- `flash_toast` renders flash messages — should be `role="status"` or `aria-live="polite"` (depends on atoms.html implementation).

### What's missing in this audit

- **Macro content**: ventas.html uses `_components/_customer_picker.html` and `_customer_card.html`; cliente_detalle uses macros. The macro content is shared across pages; this audit covers the page-level contents.
- **JS-injected DOM**: ventas.html JS dynamically inserts "No hay productos en esta categoría." etc. — these are runtime-only DOM nodes.
- **Error/success messages**: Many JS-driven modals (`UIConfirmModal.show(...)`) inject dynamic titles/bodies; captured where visible.

---

## Appendix: Quick-reference by element type

**Buttons (verbatim, full inventory):**
`Pausar carrito — el cliente puede volver y retomar`, `Dividir pago`, `0%`, `5%`, `10%`, `Propina`, `Sugerencias para sumar:`, `Actualizar lista`, `Buscar producto en venta rápida…`, `Filtrar por categoría (selección múltiple)`, `Todos`, `Favoritos`, `Productos para venta rápida`, `Buscar producto, nota o teléfono`, `Seleccioná canal…`, `Seleccioná forma de pago…`, `Tipo`, `Cancelar`, `Ver historial`, `Registrá venta`, `Escaneá código o tipeá SKU…`, `Tocá un producto o escaneá un código para agregarlo al carrito.`, `Quick-sell`, `El catálogo todavía no tiene productos con ventas recientes.`, `Venta libre`, `Precio a definir`, `Agotado`, `Sin stock`, `⚠ Quedan {{n}}`, `Ningún producto en esta categoría.`, `Ningún producto coincide con esa búsqueda.`, `Ver recibo imprimible →`, `← Volver al historial`, `Ver recibo`, `🖨 Imprimir reporte`, `Anular`, `← Anterior`, `Siguiente →`, `+ Pedido`, `Filtrar`, `Limpiar`, `Limpiar todo`, `Cerrar caja (Z)`, `Abrir caja`, `Ver ticket Z`, `Ver`, `Editar`, `Editar <name>`, `Editar cliente`, `Crear cliente`, `Nuevo cliente`, `← Volver al directorio`, `Fusionar en canónico`, `Guardar`, `Pausar`, `Reanudar`, `Cancelar`, `Eliminar`, `Sin suscripciones todavía`, `Marcar comprado`, `🛒`, `Cargar`, `Cobrar`, `★`, `✕`, `+ Agregar`, `+ Agregar perfil`, `No se pudo guardar`, `Cargo registrado`, `Pago registrado`, `Ese pago ya estaba registrado (idempotencia)`, `Canjear`

**Status badges:** `activa`, `pausada`, `cancelada`, `Semanal`, `Quincenal`, `Mensual`, `Por defecto`, `predet.`, `Sub`, `<n>p`, `ANULADA`, `ANULADO`, `pendiente`, `✅ ok`, `❌ error`, `⏳ pendiente`, `Sin ventas rec`, `abierta`, `suspendida`, `suspendida`, `cliente eliminado`, `sin fin`

**Empty states:** `Todavía no hay ventas en el historial`, `Las ventas que registres aparecerán acá.`, `El catálogo todavía no tiene productos con ventas recientes.`, `Ningún producto en esta categoría.`, `Ningún producto coincide con esa búsqueda.`, `Sin notas registradas.`, `Sin perfiles de facturación registrados.`, `Sin direcciones guardadas.`, `Sin movimientos. Los puntos se acumulan automáticamente con cada venta.`, `Sin cuentas de fiado todavía.`, `Sin suscripciones todavía`, `Sin imágenes registradas`, `Todavía no hay imágenes con atribución registradas.`, `No hay clientes todavía`, `No se detectaron duplicados`, `Sin suscripciones todavía`

**Currency display:** All currency formatted via `m.gs()` (short: `Gs. 8.000`) or `m.gs_full()` (long: `Gs. 8.696.000`). No raw integers appear in user-facing text.

**Date format:** `DD/MM/YYYY HH:MM` is dominant (e.g. `07/10/2026 14:30`). Date-only: `DD/MM/YYYY`. Short date: `DD/MM/YY`.

---

*End of Section A — Sales + Customers + Credit*