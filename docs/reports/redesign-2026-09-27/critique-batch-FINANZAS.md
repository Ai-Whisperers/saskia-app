# Saskia RMS — Visual Critique Batch: Finanzas
**Auditor:** UX/UI Principal + QA Architect
**Scope:** 8 pages — bank, cierre-mensual, margenes, margenes-detalle, retencion, afinidades*, comparacion, food-cost-variance*
**Method:** Template + router analysis (screenshots unavailable in this environment) — grounded in live template inspection. Pages marked * are missing template/route.
**Date:** 2026-09-27

---

## `/bank` (bank.html)

### 5-Hat Analysis
**Counter staff:** Never uses this. Bank imports are done by owner/admin; counter staff sees only POS sales.

**Owner-finance:** Goldmine — dual-currency EUR/PYG KPIs at top (EUR income/spent/net + PYG balance). Transaction table below shows all bank movements with date, currency, amount, category, counterparty, description. Filter by category exists. Manual add form collapsible under `<details>` — good progressive disclosure. Source attribution footnote at bottom (TXT260711013722.TAB, Sep'25→Jun'26, 307 txns).

**Production-baker:** No relevance.

**New user:** "Dutch EUR (JGHM VAN DER POL) + PY Guaraní (SASKIA WEISS VANDER)" header explains the two accounts. But the form fields are unlabeled for currency selection and amounts — user must infer. "Importe (+/-)" label is ambiguous: positive = income, negative = expense? No helper text.

**Auditor:** Transaction log is complete with timestamps, counterparty, and categorization. Source data is documented. However: no export to CSV/Excel, no pagination on the table, no date range filter.

### Defects (P0/P1/P2)
- [P1] Amount field — inline style `color: green/red` hardcoded in template (line 86: `style="color: {{ 'green' if tx.amount > 0 else 'red' }};"`) bypasses CSS design tokens — breaks dark theme
- [P1] No pagination — all 307 transactions render on one page; will degrade with scale
- [P1] No date range filter — all transactions shown regardless of period
- [P1] Inline `+` string concatenation for positive amounts — fragile Jinja expression, risks type errors
- [P2] Category filter only active when `active_category` is set; "clear" link shown even when no filter is active
- [P2] Amount `0` transactions would show neither green nor red (blank color) — edge case unhandled

### Complete Design Wishlist
1. Add CSV/PDF export for the transaction table
2. Add date range filter (start + end date pickers)
3. Replace inline `color:` styles with CSS class `tx-positive` / `tx-negative`
4. Add pagination (20/50/100 per page)
5. Add `posted_at` datetime column for sub-day resolution
6. Add counterparty search/filter
7. Add "Import bank statement" CTA (actual file upload for .TAB parsing)
8. Document the hardcoded source file in the UI footer
9. Add currency toggle (show all / EUR only / PYG only)
10. Add running balance column

---

## `/reportes/cierre-mensual` (reportes_cierre_mensual.html)

### 5-Hat Analysis
**Counter staff:** No direct use.

**Owner-finance:** Excellent monthly close tool. Month navigation (← Anterior / Siguiente →) with a `saskia-month` picker in the middle. 4 KPI cards: Ventas totales, IVA ventas, Prime Cost, Margen neto (with % color-coded green/amber/red). Detail table with 10 columns: Línea, Cantidad, Ventas, IVA, Materiales, Mano de obra, Overhead, Prime Cost, Margen, Margen %. Footer notes explain the methodology. Star product alert at top.

**Production-baker:** No direct use.

**New user:** Notes section explains labor=0 for recipes without declared time, overhead % configuration, and IVA scope (Facturas only, not Boletas). Clear.

**Auditor:** Complete — per-line cost breakdown with Prime Cost methodology. But: the notes refer to `close.rows[0].overhead_gs` (line 154) which would crash if `close.rows` is empty.

### Defects (P0/P1/P2)
- [P0] Template bug: `</div>` appears at line 81 outside the `data-loaded-section` div but no opening `<div>` for it — mismatched structure
- [P0] Line 154: `{{ close.rows[0].overhead_gs }}` crashes with IndexError if `close.rows` is empty — must use `close.rows[0].overhead_gs if close.rows else 0`
- [P1] No CSV/PDF export for the detail table
- [P1]IVA scope footnote is static text, not a collapsible note — verbose for daily use
- [P2] Month picker requires JavaScript; noscript fallback submits a bare button without year/month context

### Complete Design Wishlist
1. Fix the `</div>` mismatch at line 81
2. Fix `close.rows[0].overhead_gs` with safe fallback
3. Add CSV download for the detail table
4. Add PDF export of full monthly close report
5. Add year-over-year comparison overlay
6. Collapse the methodology notes into a `<details>` element
7. Add "Print close report" button (print CSS)
8. Add profit-per-product export per close period

---

## `/reportes/margenes` (insight_margenes.html)

### 5-Hat Analysis
**Counter staff:** No direct use.

**Owner-finance:** Margin drift report — tracks price vs cost over time. Table shows: Producto, Precio inicial, Precio actual, Δ Precio, Margen inicial, Margen actual, Δ Margen. Color-coded badges for margin changes. Links to per-product detail. Only shows products with enough sales data.

**Production-baker:** No direct use.

**New user:** Description at top explains the purpose clearly: "Precio de venta observado (primera vs última venta del período) contra el costo de receta actual. Márgenes que bajan = costo subiendo más rápido que el precio." Self-explanatory.

**Auditor:** Per-product history is auditable via the detail drill-down. No export.

### Defects (P0/P1/P2)
- [P1] No date range filter — defaults to last N days (days parameter), but no UI to change it on this page
- [P1] No CSV export
- [P2] Δ Precio shows `+0%` (rounded to 0) when price change is small but non-zero — confusing
- [P2] Margin Δ uses `m.gs()` for Gs. amounts but the delta is shown as a badge, not as absolute Gs. change — lacks context

### Complete Design Wishlist
1. Add date range filter (start/end saskia-date pickers)
2. Add CSV export
3. Sort by Δ Margen (worst first) by default
4. Add "products with margin < 15%" quick filter
5. Add supplier/category filter
6. Add sparkline showing margin trend over time per product
7. Add "Notify me when margin drops below X%" alert config

---

## `/reportes/margenes/{id}` (insight_margenes_detalle.html)

### 5-Hat Analysis
**Counter staff:** No direct use.

**Owner-finance:** Per-product price history: daily last-sale price over the period. Clean 2-column table (Día, Precio de venta). Uses `strftime('%d-%m-%Y')` for dates.

**Production-baker:** Sees which prices were active on which days — useful for cost modeling.

**New user:** Description explains "última venta del día" concept clearly. Minimal — no confusion possible.

**Auditor:** Clean audit trail of prices charged per day.

### Defects (P0/P1/P2)
- [P1] Date format inconsistency: uses `'%d-%m-%Y'` (hyphens) — most other pages use `'%d/%m/%Y'` (slashes)
- [P2] No price-vs-cost overlay — user can't see at a glance when price was below cost
- [P2] No pagination for products with >100 days of history

### Complete Design Wishlist
1. Fix date format to `'%d/%m/%Y'` for consistency
2. Add cost overlay line (if recipe cost changed over period)
3. Add pagination for long histories
4. Add "Export price history" CSV
5. Add margin calculation column (price − recipe_cost_at_time)

---

## `/reportes/retencion` (reportes_retencion.html)

### 5-Hat Analysis
**Counter staff:** No direct use.

**Owner-finance:** 3 KPI cards: Total clientes, Nuevos (%, green), Recurrentes (%, blue). Date range picker (start/end). Clear retention metrics.

**Production-baker:** No direct use.

**New user:** Clear description: "Clientes nuevos vs recurrentes en el período seleccionado."

**Auditor:** Simple, auditable metric. But: percentage calculation in template (lines 40, 47) uses Jinja `|format` which silently renders `0.0%` for `stats.total == 0` — no divide-by-zero guard.

### Defects (P0/P1/P2)
- [P1] Line 40, 47: `{{ "%.0f"|format((stats.new_customers / stats.total * 100) if stats.total > 0 else 0) }}` — the conditional is in the Jinja expression, but the `%` format string itself implies float — `0` is returned as `0` not `0.0%` — verify this renders correctly
- [P1] Empty state inside `{% if stats %}` block (line 53) — the outer block passes so stats exists, but if all values are 0 the KPIs show 0, not the empty state
- [P2] No CSV export of retention data

### Complete Design Wishlist
1. Add cohort analysis (month-over-month new vs returning)
2. Add "Repeat customer rate" as a metric
3. Add export to CSV
4. Add customer tier breakdown (Bronze/Silver/Gold retention rates)
5. Add chart (stacked bar: new vs returning per week/month)

---

## `/reportes/afinidades` ⚠️ TEMPLATE MISSING

### 5-Hat Analysis
**Owner-finance:** (No template found at `reportes_afinidades.html` or matching route in routers — this page may not exist yet or uses a different template path.)

**Status:** Page does not appear to have a dedicated template. Needs verification against the running app.

### Defects (P0/P1/P2)
- [P0] Route/template not found — page may be unimplemented

### Complete Design Wishlist
1. Verify if this page exists or is planned
2. If planned: design affinity analysis report (which products are bought together)
3. Add market basket analysis output

---

## `/reportes/food-cost-variance` ⚠️ TEMPLATE MISSING

### 5-Hat Analysis
**Owner-finance:** (No template found at `reportes_food_cost.html` or matching route — this page may not exist yet.)

**Status:** Page does not appear to have a dedicated template. Needs verification against the running app.

### Defects (P0/P1/P2)
- [P0] Route/template not found — page may be unimplemented

### Complete Design Wishlist
1. Verify if this page exists or is planned
2. If planned: design food cost variance report (actual vs standard cost per product)
3. Add per-ingredient cost variance tracking

---

## `/reportes/comparacion` (reportes_comparacion.html)

### 5-Hat Analysis
**Counter staff:** No direct use.

**Owner-finance:** Period comparison tool — select two date ranges side-by-side (fieldset layout). Shows: Período 1 Ingresos, Período 2 Ingresos, then a changes table: Ingresos, Cantidad de ventas, Margen bruto — each with Período 1 value, Período 2 value, and Change % (color-coded is-up/is-down). Solid analytical tool.

**Production-baker:** No direct use.

**New user:** Fieldset grouping (Período 1 / Período 2) with period labels is clear. "Comparar" CTA is prominent.

**Auditor:** Two-period comparison is auditable. Change % uses `|format` on possibly-None values — silent `——` fallback.

### Defects (P0/P1/P2)
- [P1] Lines 79, 87, 95: `comparison.revenue_change_pct` etc. may be `None` but the Jinja `{% if ... is not none %}` wrapper (line 60) is only around the entire table — individual cells use `%.1f|format` on None which renders "nan" — should use explicit `{% if ... is not none %}{{ ... }}{% else %}—{% endif %}`
- [P1] No CSV export of comparison data
- [P2] "Período 1 — Ingresos" uses hardcoded "Ingresos" label instead of a dynamic label based on the comparison metric type

### Complete Design Wishlist
1. Fix None handling in all `format` calls — use explicit else branch
2. Add CSV export
3. Add more comparison metrics (average ticket, products sold, new customers)
4. Add visual delta bar (e.g., a horizontal bar showing P1 vs P2)
5. Add "This period vs same period last year" quick-select preset

---

## Cross-Page Defects: Finanzas

| ID | Page | Severity | Issue |
|----|------|----------|-------|
| F1 | All reportes | P1 | No `ui.report_source_footer()` on: `insight_margenes.html`, `insight_margenes_detalle.html`, `reportes_retencion.html` — inconsistent with other report pages |
| F2 | All reportes | P1 | No date range filter on: `insight_margenes.html`, `insight_margenes_detalle.html`, `reportes_retencion.html` |
| F3 | All reportes | P2 | Date format inconsistency: `%d-%m-%Y` (insight_margenes_detalle) vs `%d/%m/%Y` (cierre_mensual) vs `%Y-%m-%d` (bank) |
| F4 | bank | P1 | Hardcoded `color: green/red` inline styles — accessibility/dark-theme violation |
| F5 | cierre-mensual | P0 | Mismatched `</div>` at line 81 |
| F6 | cierre-mensual | P0 | `rows[0].overhead_gs` crashes on empty rows |
| F7 | comparacion | P1 | None values may render as "nan" in table cells |
| F8 | reportes | P2 | No PDF export on any report page |
