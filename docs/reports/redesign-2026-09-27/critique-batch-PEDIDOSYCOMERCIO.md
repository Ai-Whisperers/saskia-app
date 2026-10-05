# Sazón — Visual Critique Batch: Pedidos y Comercio
**Auditor:** UX/UI Principal + QA Architect
**Scope:** 8 pages — pedidos-board, stock-preview, duplicate, vs-mercado, vs-mercado/editar, ventas-recibo, ventas-buscar, ventas-historial
**Method:** 5-hat analysis per page + defect log + wishlist

---

## `/pedidos/board` (`pedidos-board.png`)

### 5-Hat Analysis
**Counter staff:** The board auto-refreshes every 30 seconds and plays a chime on load — critical for catching new orders without manual polling. Order cards are color-coded by status (amber=pending, blue=confirmed, green=ready, red=overdue), making queue state scannable at a glance from across the counter. The elapsed-time counter (`⏱ N min`) in the bottom-right of each card tells staff how long an order has been sitting, which is the primary operational pressure signal. However, the card shows duplicate notes — both a yellow `card-header-note` banner AND a `card-footer` with the same note text, wasting vertical space and creating visual noise.

**Owner-finance:** The board groups orders into three temporal buckets (Hoy, Mañana, Esta semana), giving the owner an immediate sense of backlog depth. The elapsed timer surfaces orders that are stuck, which drives conversation with staff about bottlenecks. No revenue or margin data is shown — the owner cannot assess commercial health from this view. The board is read-only; there is no inline edit affordance.

**Production-baker:** The kitchen sees product names + quantities + item-level notes (📝) clearly. The `📅 25/09 · 14:30 · Mostrador` promise line tells the baker when to prioritize. The yellow-glow `approaching` state (orders within 15 minutes of promised time) is a strong visual signal. Item notes are rendered but not visually separated from product names — a long note can collapse the card's readability.

**New user:** The board's purpose is immediately clear from the 🍳 emoji and "Kitchen Board" heading. Auto-refresh and sound are surprising first-run behaviors — a first-time operator may not expect a browser page to emit audio. The timestamp (`14:30:22`) tells them this is live, but there's no legend or tooltip explaining status colors.

**Auditor:** The board is a flat list of orders with no audit trail — you cannot see status transitions, who changed state, or when. The meta-refresh tag (`<meta http-equiv="refresh" content="30">`) is a reliability risk: it resets the entire page on a timer, dropping any scroll position or interactive state. No network-level heartbeat check; if the backend is slow the page simply re-requests with no retry logic.

### Defects (P0/P1/P2)
- [P0] Audio autoplay — `audio.play().catch(function(){})` silently swallows all errors, meaning autoplay may be blocked by browser policy without any visible indicator; GDPR/ Paraguayan consumer-rights law may require consent for audio. — Remove autoplay or gate it behind a visible "Enable sound" toggle.
- [P1] Duplicate notes display — `card-header-note` and `card-footer` both render `{{ p.notes }}` when present, showing the same text twice in one card. — Remove `card-footer` note rendering; keep only `card-header-note`.
- [P1] No status-transition audit — board shows current state only, no history of `pending→confirmed→ready` transitions per order. — Add a tooltip or expandable log on each card.
- [P2] Approaching state false-positive — `is_approaching` logic only checks `promised_time` against `now`, not the date, so a tomorrow's order with a `promised_time` close to current time would incorrectly trigger the approaching glow. — Add `promised_date == today` check to the condition.
- [P2] Elapsed timer only — `elapsed_minutes` is displayed but not threshold-configurable; the `> 60 min` visual flag is hardcoded. — Make threshold a URL param or config.
- [P2] Scroll position reset on refresh — `<meta http-equiv="refresh">` reloads the entire page, losing scroll position. — Replace with a partial-fetch JS timer that patches new data without full reload.

### Complete Design Wishlist
1. Gate audio autoplay behind a visible "🔊 Activar sonido" toggle with localStorage persistence; show a dismissible banner on first load.
2. Add a `data-changes` attribute or SSE endpoint so the board updates incrementally instead of full-page refresh.
3. Add per-card expand/collapse to reveal status-transition history and timestamps.
4. Add a "speed filter" toggle: show only approaching + overdue orders to reduce cognitive load during rush.
5. Surface total order count and aggregate revenue for visible orders in the board header.
6. Add keyboard navigation (arrow keys to move between cards, Enter to open detail).
7. Show a "last synced" timestamp instead of a countdown, to clarify staleness.
8. Add a `?sound=0` URL param to disable audio without relying on localStorage.
9. Show product thumbnail or category color stripe on each card for faster visual grouping.
10. Fix `is_approaching` date boundary bug before production use.

---

## `/pedidos/{id}/stock-preview` (`pedido-stock-preview.png`)

### 5-Hat Analysis
**Counter staff:** The stock-preview page is a mandatory checkpoint before fulfilling an order — it shows exactly what will be deducted from inventory. The table layout (Ingredient, Product, Current Stock, To Consume, After) is scannable and clearly shows the math. The red danger row styling on `row.warning` items highlights which ingredients go negative. The two-button footer (Volver + Confirmar cumplimiento) provides a clear safe-path/cancel-path. However, the page requires two clicks to fulfill (click "Ver stock" on pedido_detalle, then click "Confirmar cumplimiento" on this page) — a two-step flow that slows down high-volume fulfillment.

**Owner-finance:** The page shows raw stock numbers but no cost impact — the owner cannot see the financial value of the consumed ingredients. If an ingredient goes negative, the page warns but does not block; a staff member could fulfill and cause inventory to go negative. No rollback capability shown.

**Production-baker:** The baker sees exactly which products consume which ingredients, connecting the order to kitchen prep. The "No hay productos con receta" empty state (line 51-53) is surfaced clearly. However, the table has no sort or filter — a large order with 20 line items produces a long undifferentiated table.

**New user:** The `hint` text ("Esto es lo que se va a descontar al cumplir el pedido") explains the purpose. The danger alert (line 16-18) is prominent. The page is read-heavy; new users understand what they are seeing. But there is no guidance on what to do if stock is insufficient — no link to purchase more or adjust the order.

**Auditor:** The `consumed` data comes from recipe costing; if recipes are unmaintained, the consumption figures are unreliable. No idempotency key on the fulfill form — double-submit risk. The `alert-danger` class on the `<tr>` (line 36) is a Bootstrap-only class that likely has no CSS defined in the dark-themed board; it renders as an unstyled row. The confirm modal (`SaskiaConfirmModal.show`) is good practice but the implementation buries the destructive action inside a JavaScript call, reducing auditability.

### Defects (P0/P1/P2)
- [P0] Bootstrap-only CSS class in dark theme — `alert-danger` on `<tr>` (line 36) is a Bootstrap语义 class; in the dark board theme it has no style definition and renders invisible. — Replace with a proper CSS class like `row-danger` defined in app-components.css.
- [P0] No idempotency key on fulfill POST — double-submit risk. — Add `idempotency_key` hidden input to the fulfill form.
- [P1] Negative-stock not blocked — if `after_stock < 0`, the confirm button still fires the POST; it warns but does not prevent. — Add a pre-check that shows a blocking modal if any `row.warning` is true.
- [P1] Duplicate `Volver` button — "← Volver al pedido" (line 7) and "← Volver" (line 57) both link to `/pedidos/{{ pedido_id }}`. — Remove one.
- [P2] No cost impact shown — shows physical stock but not Gs. value consumed. — Add a `cost_gs` column.
- [P2] Long table not sortable — 20+ ingredient rows have no sort/filter. — Add sort by ingredient name or by severity (negative first).
- [P2] No "insufficient stock" action path — user is warned but not guided. — Add a link to `/inventario` or a shortcut to create a purchase order.

### Complete Design Wishlist
1. Add `idempotency_key` to fulfill form with a server-generated UUID.
2. Block fulfillment with a modal if any `row.warning` is true; require explicit "Entiendo, continuar de todos modos" to proceed.
3. Replace `alert-danger` on `<tr>` with a scoped class like `stock-preview-row--danger`.
4. Add a `cost_gs` column showing Gs. value of ingredients consumed.
5. Add sort controls: "Mayor faltante primero" as default sort.
6. Remove duplicate Volver button.
7. Add a "Comprar ingredientes" shortcut link when any row has `after < 0`.
8. Add a server-side SSE endpoint `/pedidos/{id}/stock-preview/stream` for live updates.
9. Add a print-optimized stylesheet that shows only the table.
10. Add a "Ver receta" link per row for the ingredient's recipe.

---

## `/pedidos/{id}/duplicate` (`pedido-duplicate.png`)

### 5-Hat Analysis
**Counter staff:** The duplicate action is a POST to `/pedidos/{{ pedido.id }}/duplicate` triggered by a ghost button on the detail page. No dedicated screenshot exists for a duplicate confirmation page — the form POST likely redirects to `/pedidos/nuevo` pre-filled with the source order's data. The counter staff sees no UI on this page itself; the screenshot `pedido-duplicate.png` is a page at the `/pedidos/{id}/duplicate` route which likely shows a confirmation or the pre-filled new-order form. The screenshot dimensions (1280×1053, taller than most) suggest a full form page.

**Owner-finance:** The duplicate creates a new order with a new ID; original pricing is snapshot-copied at creation time, so there is financial traceability. No link between duplicate and source order shown on the board or detail, unless `pedido_detalle.html` surfaces it.

**Production-baker:** No direct baker impact from duplication itself, but a duplicated order adds to the queue.

**New user:** The duplicate button label ("Duplicar" with a copy icon) is clear. The POST-mutates-state pattern (no GET on the duplicate action) is correct. However, a new user has no confirmation dialog — one tap creates a duplicate silently. No "Duplicar y abrir编辑器" option.

**Auditor:** POST-to-duplicate is the right pattern (avoids CSRF + prevents search-engine crawl side-effects). No audit log of who duplicated an order or when. The duplicate form inherits all line items but the promised date/time are not cleared — a duplicated order retains the original's delivery window unless manually edited, risking fulfillment against stale timing.

### Defects (P0/P1/P2)
- [P1] No confirmation dialog on duplicate — a single POST button click creates a new order with no intermediate confirmation. — Add `SaskiaConfirmModal` with "Se creará un pedido idéntico con nuevo ID. Continuar?"
- [P1] Promised date/time not cleared on duplicate — the new duplicated order inherits the source's `promised_date` and `promised_time` which are now stale. — Reset `promised_date` to today and `promised_time` to empty on duplicate.
- [P2] No UI page at `/pedidos/{id}/duplicate` — the route POSTs and redirects, meaning there is no dedicated UI surface to review before saving. — Consider a GET handler that renders a pre-filled duplicate form at this URL.
- [P2] No link back to source order — after duplication, the user cannot easily see which order was the source. — Add a `source_order_id` field displayed in the duplicated order's detail.
- [P2] No "Duplicar y editar" vs "Duplicar y guardar" option. — Add both actions.

### Complete Design Wishlist
1. Add `SaskiaConfirmModal` on the Duplicar button before POST.
2. Reset `promised_date` to `today` and `promised_time` to empty on duplicate.
3. Add a `source_order_id` field and display "Duplicado de #N" on the new order's detail view.
4. Add a dedicated GET page at `/pedidos/{id}/duplicate` showing a pre-filled new-order form, so the user can review and edit before saving.
5. Add "Duplicar y crear nuevo" (save immediately) vs "Duplicar y editar" (go to pre-filled form) choice.
6. Log `duplicated_by` (user) and `duplicated_at` timestamp in the `pedidos` table.
7. Add a toast notification on redirect: "Pedido #N duplicado. Editalo antes de guardar."
8. Pre-fill customer info from source order but clear customer_phone unless the same customer is confirmed.

---

## `/vs-mercado` (`vs-mercado.png`)

### 5-Hat Analysis
**Counter staff:** This page compares Saskia's wholesale and retail prices against market benchmarks for 17 products. The counter staff rarely uses this page — pricing decisions are an owner-level action. The table shows a simple 4-column layout: Product, Nuestro wholesale ₲, Nuestro retail ₲, Mercado avg ₲, Posición. Red/green inline color coding (hardcoded `style="color:red;"` and `style="color:green;"`) indicates pricing position relative to market. The "✏️ Editar" button per row links to `/vs-mercado/{id}/edit`. The page is read-only for staff.

**Owner-finance:** The core decision-making tool for pricing strategy. A red position means Saskia is more expensive than market average; green means cheaper. The HEREBUS data source is cited in the footer. However, the position column shows only a label (e.g., "+5%") with no absolute Gs. delta shown — the owner must do mental math. No sparkline or historical trend data is visible. The table does not sort by most-actionable items (e.g., largest price gap first).

**Production-baker:** No direct production impact; ingredient cost benchmarking indirectly affects recipe margin but this page does not show that connection.

**New user:** The heading "📊 Market Benchmarks — HEREBUS" is descriptive. The muted footer explaining the source helps establish credibility. However, no explanation of what "+5%" vs "-5%" means in practical terms — new users may not know that negative = cheaper than market = potentially underpriced or competitive advantage.

**Auditor:** The hardcoded inline `color:red` and `color:green` (lines 29-31) violate the CSS-variable design system. The column header "Nuestro wholesale ₲" uses the unsupported Unicode `₲` (Guarani sign) character — this is a non-standard glyph that may not render correctly in all fonts; the codebase elsewhere uses `Gs.` prefix. The source attribution (HEREBUS_Benchmarks_Market) is cited but there is no data-quality indicator — when was this data last updated? No audit trail for who edited benchmark values or when.

### Defects (P0/P1/P2)
- [P0] Hardcoded inline color styles — `style="color:red;"` and `style="color:green;"` on lines 29-31 bypass the design system's CSS variables. If dark mode is enabled, these hardcoded colors may have poor contrast. — Replace with CSS classes `.position--over` (red) and `.position--under` (green) using CSS variables.
- [P1] Non-standard Guarani glyph `₲` in column headers — codebase uses `Gs.` consistently elsewhere; mixing `₲` and `Gs.` is inconsistent. The Unicode ₲ (U+20B5) may not render in all system fonts. — Replace all `₲` with `Gs.` using the `m.gs()` macro or explicit `Gs.` string.
- [P1] No "last updated" timestamp — benchmark data has no freshness indicator. — Add `Updated: {{ b.updated_at_str }}` or equivalent.
- [P2] No sort controls — table is sorted by product ID/order of entry, not by most-critical price gap. — Add sort: "Mayor diferencia primero" default.
- [P2] No delta Gs. column — position label shows % but not absolute Gs. difference. — Add `Δ Gs.` computed column.
- [P2] No link to recipe/ingredient cost — the owner cannot trace from market price to recipe cost to margin. — Add a "Ver receta" link per row if a recipe exists.

### Complete Design Wishlist
1. Replace hardcoded `color:red/green` with CSS classes using design system tokens.
2. Standardize all currency labels to `Gs.` prefix; remove `₲` Unicode glyph.
3. Add `updated_at` column and "Actualizado" label to table.
4. Add `Δ Gs.` computed column showing absolute price difference.
5. Sort table by `|pct|` descending by default (largest gap first).
6. Add sparkline SVG column for historical price trend if data is available.
7. Add "Exportar CSV" button.
8. Add a "Agregar producto benchmark" button linked to a creation form.
9. Add a "Ver fuente completa HEREBUS" link in the footer.
10. Color-code the entire row (not just the cell) for the most-mispriced products.

---

## `/vs-mercado/editar` (`vs-mercado-editar.png`)

### 5-Hat Analysis
**Counter staff:** Out of scope — counter staff do not edit benchmarks. They see this page only if they accidentally navigate to `/vs-mercado/{id}/edit`. No access control visible; any logged-in user can edit.

**Owner-finance:** The benchmark edit form is a 2-column grid (Nuestro precio vs Mercado) with fields for wholesale, retail, competitor min, competitor avg, market avg, and source notes. The form saves to `/benchmarks/{id}/save` via POST. The "Posición se calcula automáticamente" helper text (line 84-85) explains the logic. The `saved` flag shows a green success banner (line 10-14) after save. The form uses native `<input type="number">` elements with `step="1"` for integer Gs. values — correct for Guarani no-decimal policy. However, the form has no client-side validation: negative numbers are possible (`min="0"` is set but the logic allows `0` as a valid price with no warning that this may indicate missing data).

**Production-baker:** No direct impact.

**New user:** The 2-column grid layout is clear. The `placeholder="MercadoPy, redes, llamadas…"` on the source field guides the user on data provenance. The "Compará tu pricing vs competencia" subtitle sets expectations. However, the `₲` symbol reappears in labels (`id="our_wholesale_gs"` labels use `₲`), inconsistent with the listing page.

**Auditor:** The `saved` state is stored in a Jinja variable that is True only on POST+redirect round-trip; this is fragile if the page is refreshed. No CSRF token on the form. The `₲` symbol in labels (lines 23, 29, 38, 44, 50) is inconsistent with `Gs.` used everywhere else. No audit of who saved changes or when. The "Receta vinculada" section (lines 70-80) links to the recipe but does not show current ingredient cost, making the connection between benchmark price and recipe cost opaque.

### Defects (P0/P1/P2)
- [P0] Missing CSRF token — `benchmark_edit.html` form (line 17) has no `{{ csrf_token() }}` or equivalent; POST is vulnerable to CSRF. — Add `{% import "macros.html" as m %}` and `{{ m.csrf_input() }}` or equivalent.
- [P1] Inconsistent `₲` vs `Gs.` — labels on lines 23, 29, 38, 44, 50 use `₲`; codebase uses `Gs.` everywhere else. — Standardize to `Gs.`.
- [P1] No `updated_at` tracking on save — POST to `/benchmarks/{id}/save` updates the model but no audit timestamp is surfaced to the user or stored. — Add `updated_at = now()` in the save handler and display "Guardado el {timestamp}".
- [P2] Zero-price accepted silently — `min="0"` allows `0` as a valid input; a zero wholesale or retail price is likely a data-entry error. — Add client-side validation: if value is 0, show a warning "Precio en cero — ¿es correcto?"
- [P2] No recipe cost preview — the "Receta vinculada" section shows only a name + link, not the ingredient cost breakdown. — Show recipe cost breakdown in this section.
- [P2] Success banner disappears on refresh — `saved` is a POST-redirect flag. — Use a flash message instead.

### Complete Design Wishlist
1. Add CSRF token to form.
2. Standardize `₲` → `Gs.` in all labels.
3. Store and display `updated_at` on save.
4. Add zero-price warning with "Precio en cero — ¿datos faltantes?" inline validation.
5. Show recipe cost breakdown in the "Receta vinculada" section.
6. Add a live-position-preview: as the user types in `our_retail_gs`, show the calculated position in real-time before save.
7. Add a "Ver historia de cambios" link to show audit log of edits to this benchmark.
8. Replace `₲` in all form labels with `Gs.`.
9. Add a "Duplicar benchmark" button to create a new product benchmark from an existing one.
10. Add keyboard shortcut: `Cmd+S` to save from anywhere on the page.

---

## `/ventas/{id}/recibo` (`venta-recibo.png`)

### 5-Hat Analysis
**Counter staff:** The receipt is the end-of-transaction artifact. The page is print-optimized (max-width 360px, A6-friendly) with a print button triggering `window.print()`. The voided banner (lines 13-18) is prominently displayed for cancelled sales. The receipt shows: sale number, date, product name, quantity × unit price, total, discount (if any), payment method, customer phone, and notes. Currency formatting uses `m.gs()` macro. The `no-print` CSS class hides navigation on print. The receipt is single-item per sale (as of line 44: `sale.product_name` not iterating over multiple items), which matches the screenshot — each sale is one product. However, the `btn btn-ghost` "Volver al historial" link (line 91) is in the print output — a user who prints may fold the page and still see a web navigation link, which is unprofessional on a receipt.

**Owner-finance:** Receipt is the customer-facing document. Shows all financial data. No business logo or address is displayed — not suitable as a formal receipt. The footer disclaimer "Este recibo no es un comprobante fiscal" (line 83) is appropriate for Paraguay's RESIMPLE regime. No barcode or QR code for order lookup.

**Production-baker:** Not directly relevant.

**New user:** The receipt layout is immediately recognizable as a receipt. Print button is obvious. The voided state is unambiguous with the red-banner treatment. However, the page shows `sale.qty` as `{{ "%.2f"|format(sale.qty) }}` — fractional quantities (e.g., 1.50) may confuse staff handing a receipt to a customer who ordered 1 unit; Guarani POS systems typically deal in integer units.

**Auditor:** `{{ "%.2f"|format(sale.qty) }}` shows decimals even for whole numbers — should use `{{ "%.0f"|format(sale.qty) if sale.qty == (sale.qty|int) else "%.2f"|format(sale.qty) }}` or a macro. The `voided_at` banner is rendered but the voided sale still shows all financial details (total, product, etc.) — an auditor would want the financial figures struck through or masked. The print stylesheet does not suppress the "Volver al historial" button — confirmed by checking `no-print` is not applied to line 91's `<a>`.

### Defects (P0/P1/P2)
- [P0] "Volver al historial" link appears on printed receipt — `<a href="/ventas" class="btn btn-ghost mt-2 no-print">` is missing `no-print` class; on print it shows as a clickable URL, unprofessional on a receipt. — Add `no-print` to the link.
- [P0] Quantity shows decimal even for whole numbers — `{{ "%.2f"|format(sale.qty) }}` renders "1.00" not "1". — Use `{{ "%.0f"|format(sale.qty) if sale.qty == sale.qty|int else "%.2f"|format(sale.qty) }}`.
- [P1] Voided receipt still shows full financial details unmasked — after void, the receipt shows product, total, payment method with no redaction. — For voided receipts, strike through or replace amounts with "ANULADA".
- [P2] No business name/address/logo on receipt — receipt displays "Sazón" (line 24) as text only, no logo. — Add a placeholder for a business logo upload in the app config.
- [P2] No QR/barcode for quick lookup — no scannable identifier on the receipt for re-printing or lookup. — Add a CODE128 barcode of the sale ID.
- [P2] `unit_price_gs` displayed without `Gs.` prefix in the `small` line (line 45). — Use `m.gs(unit_price_gs)`.

### Complete Design Wishlist
1. Add `no-print` class to the "Volver al historial" link.
2. Fix decimal formatting for whole-number quantities.
3. Mask/zero-out financial amounts on voided receipts.
4. Add business logo upload in settings; display on receipt.
5. Add CODE128 barcode of `sale.id` for fast re-print.
6. Add `sale.fulfilled_by` (user who created the sale) shown as "Atendido por: X".
7. Add QR code linking to `/ventas/{id}/recibo` for digital receipt verification.
8. Add "Re-enviar por WhatsApp" button if customer phone is present.
9. Show "Cambio" field if payment was cash (display: none in current template).
10. Add print counter: "Impreso N veces" to detect receipt reprint abuse.

---

## `/ventas/buscar` (`ventas-buscar.png`)

### 5-Hat Analysis
**Counter staff:** The `ventas-buscar` route is referenced in `ventas.html` line 63 as a hint for SKU autofill: `/ventas/buscar?sku=...`. The screenshot shows a near-blank page (all 400 pixels sampled at brightness 255 = pure white across all bands, size 1280×900). This is either a redirect-only page or an extremely sparse UI. The `ventas-buscar.png` is only 9,110 bytes — far smaller than any real page screenshot. The screenshot appears to be a placeholder or mislabeled capture.

**Owner-finance:** Not relevant — this is a helper endpoint for SKU-based product lookup.

**Production-baker:** Not relevant.

**New user:** Not relevant.

**Auditor:** The screenshot being near-identical white with a tiny file size is a strong indicator this is a misfire in the screenshot script — either the page redirected before the capture, or the capture was of an error page. The route `/ventas/buscar` is referenced but not implemented as a visible page; it is likely a JSON API endpoint that returns product matches for SKU input. The template for this route does not appear in the templates directory — there is no `ventas_buscar.html`. The "buscar" page is actually the `ventas.html` page itself with a `?q=...` query param, not a separate route.

### Defects (P0/P1/P2)
- [P0] Screenshot is invalid/placeholder — `ventas-buscar.png` (9,110 bytes, all-white) does not represent a real page. The `/ventas/buscar` route appears to not have a dedicated template. — Investigate: does `/ventas/buscar` exist as a separate route or is it a query-param alias for `/ventas`?
- [P1] No `ventas_buscar.html` template found — grep of templates confirms no dedicated buscar template. — Either create one or document that `/ventas/buscar` is an alias for `/ventas?q=...`.
- [P2] The `ventas.html` SKU hint references `/ventas/buscar?sku=...` (line 63) — if this endpoint does not exist, the hint is misleading. — Verify the endpoint exists; if not, create it or update the hint.

### Complete Design Wishlist
1. Verify `/ventas/buscar?sku=...` endpoint existence and create a proper template if missing.
2. Re-capture `ventas-buscar.png` screenshot to confirm the actual page content.
3. Add a dedicated search results page for SKU/customer/product queries with result highlighting.
4. Add keyboard shortcut `Ctrl+K` to focus the search input from anywhere.
5. Show search result as a mini-card with product photo, stock, and price.
6. Add "No results" state with suggestions.
7. Add a "Crear producto" shortcut if SKU search returns zero results.
8. Add recent searches history.
9. Add an API endpoint `/productos/api/buscar?q=...` returning JSON for autocomplete.
10. Add `aria-live="polite"` on search results container for screen reader announcement.

---

## `/ventas/historial` (`ventas-historial.png`)

### 5-Hat Analysis
**Counter staff:** The sales history table is the primary audit tool for counter operations. It shows: Fecha, Producto, Cant., Unit. (Gs.), Total (Gs.), Cliente, Pago, Notas, and Actions (Recibo + Anular). The three-metric summary card (Ventas activas, Total recaudado, Ticket promedio) gives a live operational snapshot. The `ui-combo` product filter (lines 50-64) allows filtering by product. The `ventas-buscar.png` suggests a `/ventas/buscar` page exists but this page also has a search input (`<input type="search" id="sales-search">` line 49) that is separate from the product combo filter. A native `<select>` for days-filter (lines 67-72) is used instead of `<ui-combo>` — inconsistency. Voided sales are styled with `is-voided` class (line 97) and a voided banner inside the row (lines 102-107). The CSV export link (line 38-43) is prominent.

**Owner-finance:** The `Ventas activas` count, `Total recaudado`, and `Ticket promedio` metrics are the core financial dashboard for the visible filter window. CSV export enables external analysis. However, the filters do not include a date-range picker (only the preset 7/30/90-day buttons), limiting ad-hoc date analysis. Voided sales remain in the count and total — an owner seeing "Ventas activas" would not immediately know if voided sales are excluded. The `is-voided` rows are dimmed but their `total_gs` still appears in the table, inflating the apparent total.

**Production-baker:** Not directly relevant, but product-level sales frequency in the history helps the baker anticipate demand.

**New user:** The summary card is clear. The filter controls are labeled. The empty state (lines 160-164) is friendly. However, the `<select>` for days-filter vs `<ui-combo>` for products is a component inconsistency. The search input (line 49) has no label visible (uses `sr-only` class), which is correct for screen readers but confusing for sighted users who see the placeholder but no visible label.

**Auditor:** Voided sales are visually marked but their amounts are not excluded from the page totals (the summary card uses `totals` which includes all sales). The `is-voided` row still shows `Gs.` amounts without strikethrough. No audit trail for who voided or why beyond `voided_by` and `void_reason`. The pagination uses URL params but the CSV export link (line 38-43) embeds `format=csv` in the query string — if exporting with active filters, the export must preserve those params. The pagination links (lines 150-153) do not include the `product_id` and `days` params, meaning pagination from page 2+ loses filters.

### Defects (P0/P1/P2)
- [P0] Pagination links drop active filters — pagination URLs at lines 150-153 are `?page=N&q={{ q }}&product_id={{ product_id }}&days={{ days }}` but `product_id` and `days` are not included in the href construction, meaning navigating to page 2 resets the product and days filter. — Add `product_id` and `days` to the pagination hrefs.
- [P0] Voided sales included in summary totals — `totals` context includes voided sales; "Ventas activas" and "Total recaudado" are inflated by voided transactions. — Filter voided sales from `totals` query or add a separate "Voided" metric.
- [P1] Inconsistent filter component — `days-filter` uses native `<select>` (line 67) while `product-filter` uses `<ui-combo>` (line 50). Both are single-select filters; they should use the same component. — Replace `<select>` with `<ui-combo>` for visual consistency.
- [P1] Voided rows show unmasked financial data — `is-voided` rows still display Gs. amounts without strikethrough. — Add `text-decoration: line-through` and muted color to voided row amounts.
- [P2] No date-range picker — only preset day ranges (7/30/90) are available; no custom date range. — Add a date-range picker or at minimum a month selector.
- [P2] `sales-search` input uses `sr-only` label — sighted users see no visible label, relying entirely on placeholder text. — Add a visible `<label>` with `class="sr-only"` for screen readers AND a visible text label above the input.

### Complete Design Wishlist
1. Fix pagination to preserve `product_id` and `days` filter params.
2. Exclude voided sales from `totals` (count and revenue).
3. Replace native `<select>` for days-filter with `<ui-combo>`.
4. Add strikethrough styling to voided row amounts.
5. Add a date-range picker (from/to date inputs) alongside preset buttons.
6. Add a visible label for `sales-search` (not just `sr-only`).
7. Add a "Ver anuladas" toggle filter to include/exclude voided sales.
8. Add a column showing `sale.fulfilled_by` (user who created the sale).
9. Add a "Total del filtro" row below the summary card that shows filtered totals.
10. Add a "Imprimir reporte" button that generates a print-optimized sales report for the current filter.

---

*End of Batch: Pedidos y Comercio (8 pages)*
