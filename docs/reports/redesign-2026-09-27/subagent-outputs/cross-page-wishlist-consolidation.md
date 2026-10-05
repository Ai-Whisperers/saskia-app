# Sazón — Cross-Page Wishlist Consolidation

**Auditor role:** Senior UX/UI Principal
**Inputs analyzed:**
- `audit-batch2-prod.md` — 14 pages (Inventario ×6, Producción ×2, Pedidos ×5, Receta ×1)
- `audit-batch3-reports.md` — 14 pages (Proveedores ×4, Reponer, Lista de compras, Wishlist, Pricing ×2, Vs-mercado ×2, Bank, Riesgos, Auditoría, Reportes)

**Total scope:** 28 canonical pages, ~140 wishlist items, 5 personas per page
**Goal of this document:** Distill recurring patterns into (1) a top-30 reusable UX pattern list and (2) a top-10 architectural macro/component list, both with rollout guidance.

> Conventions: P0 = ship-blocking / silent failure · P1 = visible defect or major UX gap · P2 = polish.

---

## How patterns were identified

I clustered per-page wishlist items across all 28 pages. A pattern made the top-30 list when:
1. It appears as a "Top add" or wishlist item on **≥ 3 different pages**, OR
2. It is a structural primitive that the existing screens assume but don't provide (e.g., empty-state, KPI strip), OR
3. It fixes a defect category that recurs **≥ 5 times** (e.g., missing required markers, slug-as-name, no source attribution).

Each pattern is scored on:
- **Pages where it already exists** (in any form)
- **Pages where it's needed but missing** (the rollout set)
- **Effort** — S (< 1 day, single macro) · M (2-4 days, cross-page rollout) · L (> 1 week, needs schema/backend)
- **Priority** — P0 / P1 / P2

---

## Top 30 reusable UX patterns

### 1. KPI delta strip (vs prior period)
**What it is:** A row of 3-5 KPI tiles where each value carries a small "Δ vs semana anterior" badge (e.g., "+12%", "−3%", "sin cambio").
**Has it now:** Inventario list (4 tiles, no delta), Producción (implicit), Resumen diario (presumed). Lista de compras (4 tiles, no delta). Pricing (3 tiles, no delta). Bank (4 tiles, no delta). Riesgos (4 tiles, no delta). Reportes index (none).
**Needs it:** Inventario list · Lista de compras · Bank · Pricing · Resumen diario · Riesgos · Producción · Pedidos board · Reportes per-card (last-run delta). **9 pages.**
**Effort:** M — backend needs historical aggregation; front-end tile macro.
**Priority:** **P1.** Owner-finance and counter both want this without leaving the page. Bank and Inventario are highest-impact.

### 2. Filter chip rail
**What it is:** A horizontal row of toggle chips above the data table: "Todos · Bajo mínimo · Sin proveedor · Caducan pronto · …". Active chips filled, inactive outlined.
**Has it now:** Inventario list has dropdown filters (Categoría / Estado / Alérgenos) but no chip rail. Auditoría has text-input filters + quick-access chips (today / yesterday / 7d / 30d) — closest existing instance. Pedidos board has no chips.
**Needs it:** Inventario list · Proveedores · Pedidos board · Bank · Auditoría (formalize the existing chips) · Auditoría quick-access needs to be clickable chips. **6 pages.**
**Effort:** M — chip is small, but state must sync with URL and table query.
**Priority:** **P0.** The auditoría "today/yesterday/last_7d" chips being non-clickable is a defect; everywhere else, missing chips force scroll to filter.

### 3. Severity color bar (left-edge stripe)
**What it is:** A 4-px vertical stripe on the left edge of cards/rows tinted by severity — green/amber/red for ok/warn/critical; blue/violet for info.
**Has it now:** Riesgos has emoji-only severity (no stripe). Auditoría doesn't. Bank transactions have no color stripe (only negative-in-red convention). Inventario rows have a small Estado bar but it's centered, not a left edge stripe.
**Needs it:** Riesgos · Auditoría · Bank · Inventario list · Reponer · Pedidos board cards · Lista de compras. **7 pages.**
**Effort:** S — pure CSS, lives inside the `card` and `row` macros.
**Priority:** **P1.** Critical for scanner ergonomics — owner can triage an inbox of 30 items by glancing at left edges.

### 4. Empty state with onboarding CTA
**What it is:** Icon + headline + 2-line explainer + primary CTA + secondary tip. The "tip" slot answers "what do I do here?"
**Has it now:** Proveedores (good). Lista de compras (excellent — has CTA + tip). Auditoría (has retention explainer card). Inventario-movimientos (CTA "Registrá el primer ajuste"). Pedido-stock-preview (error state). Inventario-variantes. Pedido-duplicate.
**Needs it:** Proveedores (alias + dedup sub-pages are byte-identical to main list — broken empty state). Riesgos (no CTA at all). Wishlist (only a tip, no button). Bank (no "Importar archivo"). Pricing (no "create a recipe first" cross-link). Vs-mercado (no seed data onboarding). Auditoría (filter UI without results table). **8 pages.**
**Effort:** S — single `<EmptyState>` macro; rollout is replacing placeholders.
**Priority:** **P0.** The riesgos empty state is the worst in the system — 4 zeros and no entry point. New users will leave.

### 5. In-page 'derived tags' block
**What it is:** An auto-computed chip cluster on detail/edit pages showing values derived from inputs (e.g., "Usado en 1 receta activa · Días restantes: 14 · Valor en stock: Gs. 300.000").
**Has it now:** Inventario-detalle has Pronóstico card (Días restantes, Horizonte) and Variantes card — closest instance. Inventario list has Estado bar but not the full derived-tags concept. Producción has Suficiente/Falta badge.
**Needs it:** Inventario-detalle (Valor en stock, Δ vs última compra) · Inventario list (Días restantes column) · Producción (Costo estimado + Venta esperada + Margen in summary tile) · Pedido-nuevo (running total · Impacto en producción) · Pedido-detalle (Production impact mini-card) · Receta-editar (Dificultad explained, "Costo del lote" already there). **6 pages.**
**Effort:** M — derived values must be computed server-side; surface needs a small "computed_tags" component.
**Priority:** **P1.** Production-baker and counter both lose time hunting for derived facts. Pedido-nuevo needs the running total the most.

### 6. Side-rail live preview panel
**What it is:** A right-column panel that updates live as the form is filled — recipe yield preview on planner, running total on order form, computed danger badges.
**Has it now:** Inventario-nuevo has the right column with operation/conservation fields — but it's a static form, not a preview. Receta-editar has the "Escandallo" panel (cost live update) — closest instance. Pedidos-nuevo has no preview.
**Needs it:** Receta-editar (already good, formalize) · Pedidos-nuevo (subtotal/discount/total preview) · Produccion-planner (preview pane on Receta pick) · Inventario-nuevo (live cost preview "precio × stock = valor total") · Inventario-editar (Δ vs previous values). **5 pages.**
**Effort:** M — small client-side JS recompute; macro-able.
**Priority:** **P1.** Pedidos-nuevo running total is a P1 defect; planner preview closes the "what will happen if I click?" gap.

### 7. Source attribution line at table footer
**What it is:** "Fuente: HEREBUS_COSTOS sheet (7 recetas × 5 canales = 35 precios)" — provenance + row count + last-update timestamp.
**Has it now:** Pricing has it. Bank has it (source TXT filename). Vs-mercado has it (HEREBUS_Benchmarks_Market). Auditoría has "Retención de datos" card.
**Needs it:** Pedidos board ("Fuente: live DB · Última sync hace 12s") · Inventario list ("Fuente: SKU maestro · Sincronizado ...") · Reponer ("Sugerido = max(mínimo, promedio_consumo_7d × lead_time) − actual") · Producción ("Sugerido por ventas — fórmula ...") · Reportes index (each card should have source/parameters). **5 pages.**
**Effort:** S — copy + small macro; auditors and owners want this for trust.
**Priority:** **P2.** Compliance & trust play. Must be there but doesn't unblock any user.

### 8. Sticky top action cluster
**What it is:** The primary page actions (Save, Submit, Generate) follow the user as they scroll, pinned to top of viewport once the original location passes the fold.
**Has it now:** None — Save/Cancel always sit at the bottom of long forms (Inventario-nuevo, Inventario-editar, Receta-editar, Proveedor-nuevo).
**Needs it:** Every long form: Inventario-nuevo, Inventario-editar, Proveedor-nuevo, Pedidos-nuevo, Receta-editar, Vs-mercado-editar. Plus list pages with bulk actions: Inventario, Proveedores, Reponer. **8 pages.**
**Effort:** S — `position: sticky` + z-index macro.
**Priority:** **P1.** Save-then-scroll-back is a tax on every long form. Two-column forms with the Save button in the footer are an even worse anti-pattern.

### 9. Tab nav with active underline
**What it is:** Horizontal tab bar where the active tab has a colored underline + bold weight; inactive tabs are gray + lighter.
**Has it now:** Producción has Día / Semana / Mes (works). Lista de compras has "Solo abiertos / Todos (incl. comprados)". Inventario-detalle implicitly uses section nav (Stock / Variantes / Pronóstico are stacked, not tabs).
**Needs it:** Producción (already has) · Lista de compras (already has) · Reportes index (needs category tabs Ventas · Costos · Inventario · Clientes · Compliance · Operacional) · Proveedor-detail (Información · Contacto · Comercial · Logística · Aliases) · Inventario-detalle (Promedio / Variantes / Pronóstico / Historial). **5 pages.**
**Effort:** S — Tabs are a 30-line macro.
**Priority:** **P1.** Reportes has 14 cards in a flat grid; new users can't find anything. The alias management on Proveedor needs tabs to be discoverable.

### 10. Collapsible 'ejemplo' callout
**What it is:** A soft-bordered "💡 Ejemplo" disclosure with a real-world example (e.g., "Pasos: 1. Mezclar secos · 2. Combinar con húmedos · 3. Hornear").
**Has it now:** Receta-editar (markdown placeholder shows a 3-step example). Lista de compras (tip box at bottom). Inventario-nuevo has placeholders that double as examples.
**Needs it:** Proveedor-nuevo (RUC example "XXXXXXX-X") · Receta-editar (already has) · Riesgos ("Common bakery risks" expandable list) · Pedidos-nuevo (example Nota: "Sin TACC, retirar antes de las 17h") · Inventario-nuevo (already has implicit). **5 pages.**
**Effort:** S — `details/summary` HTML or small component.
**Priority:** **P2.** Reduces friction for new users; doesn't fix any defect.

### 11. Inline derived pill cluster (dietary, allergen, status, channel)
**What it is:** Compact pill row showing tags like "Sin TACC · Alto en proteína · Vegano · Sin gluten · Sin lactosa" or channel pills like "whatsapp · mostrador · web".
**Has it now:** Inventario-nuevo has Alérgenos chips and Etiquetas dietéticas chips. Inventario list has category pill in Nombre cell. Pedido-detalle has "whatsapp" channel pill (lowercase — defect). Receta-editar has Etiquetas block.
**Needs it:** All of the above (formalize casing, "WhatsApp" not "whatsapp"). Plus Pedidos board (color-code by channel). Plus Inventario list (more tag chips per row: alérgeno, categoría, proveedor). Plus Receta-editar (same pill row as detail). **6 pages.**
**Effort:** S — small `pill` macro; needs styling tokens for color semantics.
**Priority:** **P2.** High polish value; low defect impact.

### 12. Aggregated KPI strip
**What it is:** 3-6 metric tiles with label + big number + small sub-label.
**Has it now:** Inventario list, Lista de compras, Bank, Pricing, Wishlist, Riesgos — all use a row of plain labels with numbers, no card chrome, no icons.
**Needs it:** All of the above (upgrade to real cards). Plus Pedidos board (Pedidos hoy · Ventas Gs. · Ticket prom · Oldest pending). Plus Producción summary (Costo · Venta · Margen). Plus Reportes index (no KPI). **9 pages.**
**Effort:** S — wrap existing labels in a card macro with iconography + semantic color.
**Priority:** **P0.** Wishlist with Gs. 50,000,000 in plain text is broken; Bank with €0.00 cards would be much clearer.

### 13. Inline warnings (margin < 30%, no recipe, price = 0, "sin consumo")
**What it is:** Inline yellow/red banner or pill within a card/row that flags a derived condition the user should know about.
**Has it now:** Inventario-detalle has orange "SIN CONSUMO" badge (closest). Inventario list has "Stock bajo" badge. Producción has "Suficiente/Falta" badge. Inventario-nuevo has helper text under fields.
**Needs it:** Receta-editar ("Costo del lote Gs. 0" — silently broken when no price; needs an inline warning). Vs-mercado (cells with "—" should warn "completar"). Pedido-detalle ("Ver stock antes de cumplir" leads to 500 — should warn on click, not just fail). Reponer ("sin proveedor" italic should be a red badge). Inventario-detalle ("(sin consumo reciente)" should be actionable). **5+ pages.**
**Effort:** S — inline alert macro.
**Priority:** **P1.** "Silent failure" is the recurring defect theme; this pattern directly addresses it.

### 14. Bulk action bar
**What it is:** A horizontal toolbar that appears at the bottom of a list when ≥1 row is selected: "3 seleccionados · Archivar · Eliminar · Exportar · Combinar".
**Has it now:** Reponer has "Seleccionar todos · Generar pedido por WhatsApp" already (good). Inventario list has per-row actions only. Auditoría none. Bank none.
**Needs it:** Inventario list · Proveedores · Bank · Auditoría · Pedidos board (multi-card select + bulk status change). **5 pages.**
**Effort:** M — needs row-select state + toolbar that slides up; counter staff will love this.
**Priority:** **P1.** Highest leverage for counter; 30 rows × 4 taps each is currently unmanageable.

### 15. Inline row actions (Mark Done, Edit, Duplicate, View)
**What it is:** A small action cluster inside each table row, ideally with icons + tooltips. Currently used as "Ver / Ajustar / Editar / Movimientos" on inventario.
**Has it now:** Inventario list (4 actions per row, mixed icon families — P2 defect). Inventario-movimientos (none). Auditoría (none). Bank (none).
**Needs it:** All list pages — standardize on icon family (lucide), label on hover only.
**Effort:** S — table cell macro.
**Priority:** **P2.** Consistency + icon hygiene.

### 16. Date range presets (Hoy, Ayer, Esta semana, Mes, Trimestre, Año)
**What it is:** A row of clickable chips above date pickers that auto-fill Desde/Hasta + apply.
**Has it now:** Auditoría has "today · yesterday · last_7d · last_30d" as text (not clickable). Bank has no date filters visible. Inventario-movimientos wishlist item.
**Needs it:** Auditoría (formalize, make clickable) · Bank · Inventario-movimientos · Reponer (period overlay) · Pedidos board (Hoy / Esta semana toggle). **5 pages.**
**Effort:** S — chip group + small JS to set date fields.
**Priority:** **P1.** Auditoría already has the chips — turning them clickable is a 1-hour fix.

### 17. Bar chart visualization
**What it is:** A small inline bar chart (sparkline or 12-bar histogram) for a numeric series.
**Has it now:** Reportes index cards each have a small bar-chart icon (decorative, no data). Inventario list has a 4-px progress bar under Estado (so small it's hard to read). Reponer has "Tendencia (90d)" column with "—" silent failure.
**Needs it:** Inventario list (sparkline of 30-day consumption per row) · Reponer (sparkline of 90-day consumption) · Inventario-detalle (consumption chart over time) · Bank (cashflow chart) · Pricing (margin bar per channel) · Reportes index (real chart previews, not just icons). **6 pages.**
**Effort:** M — chart macro; data fetch.
**Priority:** **P1.** Reponer "Tendencia (90d) —" being silent is a P0 defect; the bar chart visual is the fix.

### 18. Period comparison overlay
**What it is:** Toggle "Esta semana vs semana anterior" or "Hoy vs ayer" — both series shown on the same chart with distinct colors.
**Has it now:** None.
**Needs it:** Bank · Inventario (consumo) · Producción (costo vs venta) · Resumen diario. **4 pages.**
**Effort:** M — chart with two-series.
**Priority:** **P2.** Power feature; only after sparklines exist.

### 19. Drill-down (click row → detail)
**What it is:** Click anywhere on a row to open the detail/edit page.
**Has it now:** Inventario list has explicit "Ver / Editar" links (works). Bank none. Auditoría none (rows don't have drill). Pedidos board has "Abrir" button (works).
**Needs it:** Bank (click txn → split/reconcile) · Auditoría (click row → full diff) · Reponer (click row → ingredient detail). **3 pages.**
**Effort:** S — `<a>` wrapping or onClick handler.
**Priority:** **P2.** Auditor drill use case is real but not blocking.

### 20. Print preview
**What it is:** A "🖨 Vista previa de impresión" toggle that strips chrome and renders the page as a print-friendly layout.
**Has it now:** None.
**Needs it:** Inventario list (price list for compliance) · Pedido-detalle (thermal receipt) · Receta-editar (spec sheet) · Reportes index (each report). **4 pages.**
**Effort:** M — `@media print` rules + dedicated `/print` view for receipts.
**Priority:** **P2.** Critical for bakery operations (thermal printer for kitchen tickets) but P2 for the broader UX.

### 21. Source attribution footer
**What it is:** (See pattern #7 — this is the dedicated footer version with citation + timestamp.)
**Has it now:** Pricing · Bank · Vs-mercado · Auditoría retention card.
**Needs it:** Every table page — formalize the macro.
**Effort:** S — shared footer macro.
**Priority:** **P2.**

### 22. Search bar
**What it is:** A text input at the top of the list that filters rows by name/code.
**Has it now:** Global command-bar `⌘K` in header. Inventario list has per-page text search. Pedidos board none. Proveedores none. Bank none.
**Needs it:** Pedidos board (customer search within board) · Proveedores · Bank · Pedidos list (when it exists) · Reportes index (search reports). **5 pages.**
**Effort:** S — input + filter.
**Priority:** **P1.** Proveedores has 0 search even with the empty state promising filterability later; bank needs full-text search once txns populate.

### 23. Saved filters per user
**What it is:** Star icon next to filter chip rail that saves the current filter combo to the user.
**Has it now:** Inventario wishlist mentions "Mis críticos, Sin gluten, Alto costo, Sin foto".
**Needs it:** Inventario · Auditoría · Reportes · Proveedores. **4 pages.**
**Effort:** L — needs per-user storage + URL state sync.
**Priority:** **P2.** Power feature; revisit after P0/P1 ship.

### 24. Sortable column headers with active highlight
**What it is:** Click column header to sort; active sort has arrow icon + colored background.
**Has it now:** Reponer wishlist mentions "Sort indicators on every column header". Bank wishlist same. Pricing same. Inventario list same.
**Needs it:** All table pages — formalize.
**Effort:** S — header cell macro.
**Priority:** **P2.**

### 25. Sticky header
**What it is:** Table header that stays pinned at the top while rows scroll.
**Has it now:** None visible.
**Needs it:** Inventario list · Proveedores · Reponer · Bank · Auditoría · Pricing · Vs-mercado. **7 pages.**
**Effort:** S — `position: sticky; top: 0;` on `<th>`.
**Priority:** **P2.** Real value once you have 50+ rows.

### 26. Pagination + jump-to-page
**What it is:** Bottom of table: "« 1 2 3 ... 14 » · Por página: [25 ▾] · Mostrando 1-25 de 347".
**Has it now:** Reponer ("Mostrando 1-1 de 1") and Inventario. Bank none.
**Needs it:** All list pages — formalize.
**Effort:** S — pagination macro.
**Priority:** **P2.**

### 27. Tooltip glossary (?) on technical terms
**What it is:** Small `?` icon next to technical term; hover/popover explains.
**Has it now:** None — but the gap is consistent: TACC, HACCP, Escandallo, US (urgency score), "MAESTRA", "Lote obligatorio", Dificultad "auto", all undefined.
**Needs it:** Receta-editar · Inventario-nuevo · Inventario-detalle · Producción · Pricing · Auditoría · Bank. **7 pages.**
**Effort:** S — `<abbr title>` or popover.
**Priority:** **P1.** Glossary debt is everywhere; one macro fixes the whole app.

### 28. Photo placeholder (initials in colored box)
**What it is:** When an entity has no photo, show a colored box with the first 1-2 letters of the name (deterministic color from hash).
**Has it now:** None.
**Needs it:** Proveedores · Cliente (when present) · Receta-editar · Inventario-nuevo. **4 pages.**
**Effort:** S — pure CSS, no upload required.
**Priority:** **P2.** Visual polish; helps recognition.

### 29. Drag-drop reorder
**What it is:** Drag a row or board card to reorder.
**Has it now:** None.
**Needs it:** Pedidos board (kanban — must-have for KDS workflow) · Wishlist board view · Variantes set-as-preferred · Lista de compras manual order. **4 pages.**
**Effort:** M — Sortable.js or native HTML5 DnD.
**Priority:** **P1** for Pedidos board (kitchen workflow), **P2** for others.

### 30. Required-field markers (*) + Save feedback (toast / inline state)
**What it is:** Visible `*` on required inputs + post-submit toast or inline "Saved ✓" / "Error: ..."
**Has it now:** Inventario-nuevo has NO required markers (P1 defect). Inventario-editar same. Receta-editar has `*` on Nombre but not Familia (inconsistent). Proveedor-nuevo has `*` on Nombre. None show submit feedback.
**Needs it:** Every form page (6 forms).
**Effort:** S — single `required` CSS + a toast component.
**Priority:** **P0.** Combined with the "no submit feedback" defect, this is the #1 silent-failure pattern.

---

## Pattern → page rollout matrix (compact)

| # | Pattern | P0/P1/P2 | Pages needed on | Effort |
|---|---|---|---|---|
| 1 | KPI delta strip | P1 | 9 | M |
| 2 | Filter chip rail | **P0** | 6 | M |
| 3 | Severity color bar | P1 | 7 | S |
| 4 | Empty state w/ onboarding CTA | **P0** | 8 | S |
| 5 | In-page derived tags | P1 | 6 | M |
| 6 | Side-rail live preview | P1 | 5 | M |
| 7 | Source attribution footer | P2 | 5 | S |
| 8 | Sticky top action cluster | P1 | 8 | S |
| 9 | Tab nav w/ active underline | P1 | 5 | S |
| 10 | Collapsible 'ejemplo' callout | P2 | 5 | S |
| 11 | Inline derived pill cluster | P2 | 6 | S |
| 12 | Aggregated KPI strip (cards) | **P0** | 9 | S |
| 13 | Inline warnings | P1 | 5+ | S |
| 14 | Bulk action bar | P1 | 5 | M |
| 15 | Inline row actions | P2 | all lists | S |
| 16 | Date range presets | P1 | 5 | S |
| 17 | Bar chart visualization | P1 | 6 | M |
| 18 | Period comparison overlay | P2 | 4 | M |
| 19 | Drill-down row → detail | P2 | 3 | S |
| 20 | Print preview | P2 | 4 | M |
| 21 | Source attribution (consolidated) | P2 | every table | S |
| 22 | Search bar | P1 | 5 | S |
| 23 | Saved filters per user | P2 | 4 | L |
| 24 | Sortable column headers | P2 | all lists | S |
| 25 | Sticky header | P2 | 7 | S |
| 26 | Pagination + jump-to-page | P2 | all lists | S |
| 27 | Tooltip glossary (?) | P1 | 7 | S |
| 28 | Photo placeholder (initials) | P2 | 4 | S |
| 29 | Drag-drop reorder | P1 (board) / P2 | 4 | M |
| 30 | Required markers + submit feedback | **P0** | 6 forms | S |

**P0 count: 4 patterns · P1 count: 13 patterns · P2 count: 13 patterns**

---

## Top 10 architectural macro / component patterns

> The 10 below are the components that, if built as Jinja macros (or equivalent), would unblock the rollout of 25+ of the 30 UX patterns above. File paths are suggestions for a Flask/Jinja-style project layout.

### Macro 1 — `kpi_tile`

**File:** `templates/macros/kpi_tile.html` (or `_kpi_tile.html.j2`)
**Signature:**
```jinja
{% from "macros/kpi_tile.html" import kpi_tile %}
{{ kpi_tile(
     label="Stock crítico",
     value="1",
     delta="-1 vs semana anterior",
     delta_direction="down",   # up | down | flat
     severity="warn",          # ok | warn | danger | info | neutral
     icon="alert-triangle",
     href="/inventario?filter=critico",
     tooltip="Ingredientes con stock por debajo del mínimo"
) }}
```
**Example usage:** Inventario list, Lista de compras, Bank, Pricing, Wishlist, Riesgos, Producción, Reportes.
**Pattern rollouts enabled:** #1 (KPI delta strip), #12 (Aggregated KPI strip).

---

### Macro 2 — `status_pill`

**File:** `templates/macros/status_pill.html`
**Signature:**
```jinja
{% from "macros/status_pill.html" import status_pill %}
{{ status_pill(
     label="Pendiente",
     tone="warn",      # ok | warn | danger | info | neutral | muted
     icon="clock",
     tooltip="Aún no confirmado por el cliente",
     href="/pedidos/1"
) }}
```
**Example usage:** Pedidos board, Pedido-detalle, Inventario list, Movimientos, Producción board, Riesgos.
**Pattern rollouts enabled:** #11 (Inline derived pill cluster).

---

### Macro 3 — `data_table`

**File:** `templates/macros/data_table.html`
**Signature:**
```jinja
{% from "macros/data_table.html" import data_table %}
{{ data_table(
     columns=[
         {"key": "nombre", "label": "Nombre", "sortable": true, "width": "30%"},
         {"key": "stock", "label": "Stock actual", "sortable": true, "align": "right"},
         {"key": "estado", "label": "Estado", "render": "status_pill"},
     ],
     rows=ingredientes,
     row_actions=[
         {"label": "Ver", "href": "/inventario/{id}", "icon": "eye"},
         {"label": "Editar", "href": "/inventario/{id}/editar", "icon": "pencil"},
     ],
     bulk_actions=[
         {"label": "Archivar", "action": "POST /inventario/bulk-archive", "icon": "archive"},
         {"label": "Exportar CSV", "action": "GET /inventario/export.csv", "icon": "download"},
     ],
     pagination={"page": 1, "per_page": 25, "total": 347},
     sticky_header=true,
     selectable=true,
     empty_state={"title": "Sin ingredientes", "cta": {"label": "Agregá el primero", "href": "/inventario/nuevo"}}
) }}
```
**Example usage:** Every list page in the app.
**Pattern rollouts enabled:** #14 (Bulk action), #15 (Inline row actions), #24 (Sortable headers), #25 (Sticky header), #26 (Pagination), #14, #4 (Empty state slot).

---

### Macro 4 — `filter_chips`

**File:** `templates/macros/filter_chips.html`
**Signature:**
```jinja
{% from "macros/filter_chips.html" import filter_chips %}
{{ filter_chips(
     chips=[
         {"key": "todos", "label": "Todos", "count": 42, "active": true},
         {"key": "bajo_minimo", "label": "Bajo mínimo", "count": 3, "tone": "warn"},
         {"key": "sin_proveedor", "label": "Sin proveedor", "count": 1, "tone": "danger"},
     ],
     date_presets=[
         {"key": "today", "label": "Hoy"},
         {"key": "yesterday", "label": "Ayer"},
         {"key": "7d", "label": "Últimos 7d"},
         {"key": "30d", "label": "Últimos 30d"},
     ],
     search_input=true,
     saved_views=[{"label": "Mis críticos", "href": "?saved=criticos"}],
     sync_with_url=true
) }}
```
**Example usage:** Inventario, Proveedores, Reponer, Pedidos board, Bank, Auditoría, Lista de compras.
**Pattern rollouts enabled:** #2 (Filter chip rail), #16 (Date range presets), #22 (Search bar), #23 (Saved filters).

---

### Macro 5 — `empty_state`

**File:** `templates/macros/empty_state.html`
**Signature:**
```jinja
{% from "macros/empty_state.html" import empty_state %}
{{ empty_state(
     icon="package",
     title="No hay proveedores todavía",
     description="Agregá proveedores para poder contactarlos desde la página de reorden.",
     primary_cta={"label": "Agregá el primero", "href": "/proveedores/nuevo", "icon": "plus"},
     secondary_cta={"label": "Pegar lista de WhatsApp", "action": "openWhatsAppPaste"},
     tip="💡 Tip: después podés asignarles categorías, RUC y horarios de entrega.",
     illustration="supplier-empty.svg"  # optional
) }}
```
**Example usage:** Every list/detail page that can be empty. Already partially used — formalize.
**Pattern rollouts enabled:** #4 (Empty state with onboarding CTA), #10 (Collapsible 'ejemplo' callout via `tip` slot).

---

### Macro 6 — `bulk_action_bar`

**File:** `templates/macros/bulk_action_bar.html`
**Signature:**
```jinja
{% from "macros/bulk_action_bar.html" import bulk_action_bar %}
{# Usually rendered conditionally when selected_count > 0 #}
{{ bulk_action_bar(
     selected_count=3,
     actions=[
         {"label": "Archivar", "action": "POST /bulk/archive", "icon": "archive", "tone": "warn"},
         {"label": "Eliminar", "action": "POST /bulk/delete", "icon": "trash", "tone": "danger", "confirm": true},
         {"label": "Exportar", "action": "GET /bulk/export.csv", "icon": "download"},
     ],
     on_clear="clearSelection()"
) }}
```
**Example usage:** Inventario, Proveedores, Bank, Auditoría, Pedidos board.
**Pattern rollouts enabled:** #14 (Bulk action bar).

---

### Macro 7 — `date_range_presets`

**File:** `templates/macros/date_range_presets.html`
**Signature:**
```jinja
{% from "macros/date_range_presets.html" import date_range_presets %}
{{ date_range_presets(
     presets=[
         {"key": "today", "label": "Hoy", "from": "2026-09-27", "to": "2026-09-27"},
         {"key": "yesterday", "label": "Ayer", "from": "2026-09-26", "to": "2026-09-26"},
         {"key": "7d", "label": "Últimos 7d", "from": "2026-09-20", "to": "2026-09-27"},
         {"key": "30d", "label": "Últimos 30d", "from": "2026-08-28", "to": "2026-09-27"},
         {"key": "month", "label": "Este mes", "from": "2026-09-01", "to": "2026-09-30"},
         {"key": "quarter", "label": "Trimestre", "from": "2026-07-01", "to": "2026-09-30"},
     ],
     custom_enabled=true,
     target_input_from="#date_from",
     target_input_to="#date_to",
     on_apply="submitFilters()"
) }}
```
**Example usage:** Auditoría, Bank, Inventario-movimientos, Reponer, Pedidos board.
**Pattern rollouts enabled:** #16 (Date range presets), #18 (Period comparison overlay as a second chip).

---

### Macro 8 — `severity_left_stripe`

**File:** `templates/macros/severity_left_stripe.html` (CSS + small macro)
**Signature:**
```jinja
{% from "macros/severity_left_stripe.html" import severity_left_stripe %}
{# Wrap a card or row to add the left edge #}
<div class="card-with-stripe severity-{{ severity }}">
  {{ severity_left_stripe(severity="danger", thickness="4px") }}
  {# card body #}
</div>
```
**Example usage:** Riesgos cards, Auditoría rows, Bank transactions, Inventario rows, Reponer rows, Pedidos board cards.
**Pattern rollouts enabled:** #3 (Severity color bar), #13 (Inline warnings pair nicely).

---

### Macro 9 — `inline_warning`

**File:** `templates/macros/inline_warning.html`
**Signature:**
```jinja
{% from "macros/inline_warning.html" import inline_warning %}
{{ inline_warning(
     tone="warn",   # info | warn | danger | success
     title="Sin consumo reciente",
     message="No hay registros de consumo para este ingrediente en los últimos 14 días.",
     action={"label": "Registrá consumo", "href": "/inventario/{id}/movimientos/nuevo"},
     dismissible=true,
     tooltip="El pronóstico requiere al menos 3 días de historial."
) }}
```
**Example usage:** Inventario-detalle, Receta-editar (Costo Gs. 0), Vs-mercado (cells with —), Pedido-detalle (stock-preview 500 risk), Reponer (sin proveedor), Producción (qty override).
**Pattern rollouts enabled:** #5 (In-page derived tags) and #13 (Inline warnings) — these two together cover the "make silent failures loud" mandate.

---

### Macro 10 — `confirm_destructive`

**File:** `templates/macros/confirm_destructive.html`
**Signature:**
```jinja
{% from "macros/confirm_destructive.html" import confirm_destructive %}
{{ confirm_destructive(
     trigger_label="Eliminar entradas de más de 1 año",
     trigger_tone="danger",
     title="Eliminar entradas antiguas de auditoría",
     body="Vas a eliminar <strong>1.247 entradas</strong> con más de 1 año de antigüedad. Esta acción es irreversible y compromete la cadena de auditoría.",
     confirm_label="Sí, eliminar 1.247 entradas",
     cancel_label="Cancelar",
     confirm_action="POST /auditoria/purge",
     require_typed_confirmation=true,   # for the scariest ones
     typed_phrase="ELIMINAR",
     icon="alert-triangle"
) }}
```
**Example usage:** Auditoría (purge), Proveedor delete, Pedido cancel, Receta archive, Riesgo close, Bank transaction reverse.
**Pattern rollouts enabled:** Closes the "destructive button without confirm" defect (auditoría P0); re-usable across all destructive actions.

---

## Macro rollout priorities

| Macro | Unblocks patterns | Effort | Build first? |
|---|---|---|---|
| `kpi_tile` | #1, #12 | S | ✅ First |
| `empty_state` | #4, #10 | S | ✅ First |
| `inline_warning` | #5, #13 | S | ✅ First |
| `status_pill` | #11 | S | ✅ First |
| `filter_chips` | #2, #16, #22, #23 | M | Second |
| `data_table` | #14, #15, #24, #25, #26 | M | Second |
| `bulk_action_bar` | #14 | M | Second |
| `severity_left_stripe` | #3, #13 | S | Third |
| `date_range_presets` | #16, #18 | S | Third |
| `confirm_destructive` | (defect fix) | S | Third |

**Total effort to ship all 10 macros:** ~3-4 weeks for one engineer + designer.
**After ship:** ~70% of the P0+P1 wishlist is addressable by simply applying the macros to existing pages.

---

## Top 10 cross-page defects (carried over from per-page audits)

The architectural fix for many of these is the macro rollout above. Listed for traceability:

1. **P0** — pedido-stock-preview renders 500 (macro: `confirm_destructive` + retry banner needed)
2. **P1** — slug-as-name leaks across 9 pages (data fix, not macro — but `kpi_tile` should never show slug)
3. **P1** — no required-field markers + no submit feedback (macro: form helpers + toast)
4. **P1** — no payment / balance UI on pedido-detalle (macro: `inline_warning` to flag the gap + dedicated Pagos card)
5. **P1** — pedidos board is read-only (macro: `data_table` with `bulk_action_bar` + status transition buttons)
6. **P1** — pronóstico "(sin consumo reciente)" misleads (macro: `inline_warning` w/ action CTA)
7. **P1** — "Transiciones permitidas: pending → cancelled, confirmed" in English (i18n, no macro)
8. **P1** — no running total on pedidos-nuevo (macro: side-rail live preview #6)
9. **P1** — sidebar overlap on inventario-variantes (z-index fix, no macro)
10. **P1** — no "Duplicado de Pedido #1" indicator post-duplicate (macro: derived tag pill)

---

## Quick-win sequencing (a 2-week sprint that moves the needle)

**Sprint 1 (week 1) — ship 5 macros, fix the 4 P0 patterns:**
- Build `kpi_tile`, `empty_state`, `inline_warning`, `status_pill` (4 small macros)
- Apply `empty_state` to: Riesgos, Wishlist, Bank, Proveedores-aliases, Proveedores-dedup
- Apply `kpi_tile` to: Inventario, Lista de compras, Bank, Wishlist, Riesgos (card-ify the plain labels)
- Apply `inline_warning` to: Reponer (sin proveedor → red badge with "Asignar"), Inventario-detalle ("sin consumo reciente" → actionable), Receta-editar ("Costo Gs. 0" → explain)
- Add `confirm_destructive` to: Auditoría purge

**Sprint 2 (week 2) — ship 5 more macros, fix the bulk of P1:**
- Build `filter_chips`, `data_table`, `bulk_action_bar`, `date_range_presets`, `severity_left_stripe`
- Apply `data_table` + `bulk_action_bar` to: Inventario, Proveedores, Auditoría
- Apply `filter_chips` + `date_range_presets` to: Auditoría (formalize existing chips), Bank, Reponer
- Add the Pedido board kanban drag-drop + status transition buttons
- Add `severity_left_stripe` to: Riesgos, Auditoría, Inventario list

**After sprint 2:** ~70% of P0+P1 wishlist items are addressed; all 10 macros are reusable for the remaining 8 pages not yet audited (clientes, ventas, inicio/dashboard).

---

## Glossary of recurring defect categories (from 28 pages)

These came up repeatedly. Tracking them so they can be triaged as a group:

| Defect category | Pages affected | Macro that fixes it |
|---|---|---|
| Slug-as-display-name | 9 | (data fix) |
| English/Spanish mixing | 8 | (i18n) |
| Required markers missing | 6 | (form helper) |
| No submit feedback | 6 | (toast macro) |
| "—" / "sin proveedor" silent failure | 5 | `inline_warning` |
| No source attribution | 5 | `inline_warning` footer variant |
| No empty-state CTA | 4 | `empty_state` |
| Empty-state visual flatness | 4 | `empty_state` with illustration slot |
| No search/filter | 4 | `filter_chips` |
| KPI rows lack visual weight | 9 | `kpi_tile` |
| No drill-down / inline edit | 4 | `data_table` |
| No bulk actions | 5 | `bulk_action_bar` |
| Destructive action no confirm | 2 | `confirm_destructive` |
| No required field markers | 6 | (form helper) |
| No "last modified by / when" | 8 | (audit log integration) |
| No glossary on jargon | 7 | (tooltip glossary pattern) |
| No keyboard shortcuts | all | (kbd badge pattern) |
| Page-level inconsistency (currency, casing, verb form) | all | (design tokens) |

---

*End of consolidation.*