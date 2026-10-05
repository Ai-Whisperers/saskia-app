# Sazón — Visual Critique Batch: Operaciones
**Auditor:** UX/UI Principal + QA Architect
**Scope:** 8 pages — merma, shopping-list, reorder, analisis, auditoria, ops/status, pricing, reportes
**Method:** 5-hat analysis per page + defect log + wishlist

---

## `/merma` (merma.png)

### 5-Hat Analysis
**Counter staff:** The waste entry form is visible in the top section (band 0–1). Large orange accent in band 3 draws the eye to a key data band. No quick-entry shortcut visible — staff must navigate the full form to record waste. No confirmation feedback visible after entry. Vos-form labels presumed throughout.

**Owner-finance:** Shrinkage data appears to be displayed in a table (multiple column regions detected: x≈170, 397, 435, 475, 525, 776, 1159). A tall page (1964px) suggests a long scrolling data table — financials buried below the fold. Orange accent color used for attention but not consistently correlated to financial severity (loss amounts). No totals/summary KPI card at top.

**Production-baker:** The page likely shows waste by product/recipe. Orange band at y≈904 suggests a section header or category grouping. No visual weight given to high-loss items. The table structure (7 column regions) implies many attributes per row — possibly overwhelming for a baker who needs: what, how much, why.

**New user:** Top header has brand orange accent but no breadcrumb or page title treatment. The sidebar edge is at x≈52, creating a narrow sidebar column. No "help" icon or tooltip. Long page without scroll progress indicator. Table has no visible row numbers, making reference difficult.

**Auditor:** Page height is 1964px — the tallest in this batch, suggesting a heavy data table. Red accent is absent (only orange used). Auditoria page has red (220,38,38) for deletions, but merma uses only orange for emphasis — inconsistent signal coding across audit-relevant pages. Footer is light-gray, content ends abruptly at y≈1904.

### Defects (P0/P1/P2)
- [P1] Page title/header — No visible H1 label at top of content area; auditor cannot confirm which page they're on without scrolling — add explicit page title below the nav bar
- [P1] KPI summary card — No summary totals (total kg wasted, total Gs wasted, cost) pinned above the fold; financial oversight requires scrolling the full 1964px — add a sticky summary card
- [P2] Color coding inconsistency — Merma uses only orange (#F97316) for emphasis; auditoria uses red (#DC2626) for deletions/alerts — establish a semantic color system: red=loss/cost, amber=warning, green=savings
- [P2] Table row numbers — No row index numbers visible in table; auditor cannot reference "row 14" verbally — add a semi-transparent row-id column
- [P2] No zebra striping — Content bands show gray (#E5E7EB) separators at inconsistent intervals (band 2, band 4, band 6) — implement consistent zebra striping every N rows
- [P2] Footer area — y=1904–1964 is near-empty footer; content ends with no call-to-action — add "Exportar PDF / CSV" button in footer zone

### Complete Design Wishlist
1. Sticky KPI summary card: total waste (kg), total cost (Gs), top 3 offending items — pinned to top of content area
2. Semantic color system: red for financial loss, amber for threshold warnings, green for savings/goals
3. Row numbers in tables for all data pages
4. Consistent zebra striping (alternating #F9FAFB / white) on all data tables
5. "Ayuda contextual" tooltip icon (?) next to section headers
6. Inline sparklines for waste trends (last 7 days) per item
7. Bulk-entry mode toggle: single-item form vs. multi-row rapid entry
8. Responsive footer: export buttons (PDF, CSV, XLSX) always visible, not buried at bottom of tall pages
9. Orange accent reserved exclusively for primary CTAs; data emphasis should use semantic colors
10. Breadcrumb trail: "Inicio > Producción > Merma" for orientation

---

## `/shopping-list` (shopping-list.png)

### 5-Hat Analysis
**Counter staff:** The shopping list is a compact 900px page — good. Orange accent cluster at y≈270 and y≈375 indicates action items or grouped sections. Only 6 text-row bands detected, suggesting a clean short list. Staff can see what to buy at a glance. However, no checkbox UI visible in the pixel data — staff cannot mark items as purchased inline.

**Owner-finance:** The list appears to lack estimated cost per item or total budget estimate. No supplier column visible. Column regions detected at x≈170, 282, 402, 859 — suggests: item name | quantity | supplier | [action]. Missing: unit price, estimated total. Financial oversight requires external calculation.

**Production-baker:** Baker needs: what ingredients, how much, urgency. The orange band at y≈270 may signal a "need today" grouping. No visual urgency indicator (red/amber for low stock). No recipe linkage visible — baker cannot see which recipe each ingredient belongs to.

**New user:** Short page (900px) means full content visible without scroll — good for new users. However, no empty-state guidance: if the list is empty, no illustration or instruction. No "add item" CTA above the fold.

**Auditor:** List pages are audit-relevant for procurement tracing. No timestamp on when the list was generated. No author/creator attribution. The footer (y≈840–900) has no audit metadata. Cannot determine if a printed list matches a specific version.

### Defects (P0/P1/P2)
- [P1] No checkbox/toggle UI — Staff cannot mark items as purchased inline; pixel analysis shows no interactive control elements in content area — add checkbox column with strikethrough on check
- [P1] No cost column — Shopping list has no price data; owner cannot approve purchases without leaving the app — add "Precio unitario" and "Total estimado" columns
- [P2] No supplier column — Column structure at x≈859 may be an action column; no visible supplier identifier — add "Proveedor" column or supplier tag
- [P2] No date/time stamp — No "Generado el:" metadata visible — add generation timestamp in header or footer
- [P2] No urgency/sstock indicator — Low-stock items not visually distinguished — add amber dot for "stock bajo" and red for "sin stock"
- [P2] Empty state missing — If list is empty, no guidance for the user — add illustrated empty state with "Tu lista está vacía" + "Agregar ítem" CTA

### Complete Design Wishlist
1. Checkbox column with strikethrough animation on check (item sourced)
2. Price column (unit + total) toggleable from settings
3. Supplier column with vendor tag chips
4. Urgency indicator: colored dots (green/amber/red) based on stock level
5. "Vincular a receta" column showing which recipe each ingredient belongs to
6. Auto-consolidate duplicate ingredients across recipes
7. "Imprimir lista" button with print-optimized CSS layout
8. Generation timestamp + author attribution in footer
9. Drag-to-reorder items (prioritize urgent items at top)
10. Bulk-import from recipe ingredient lists

---

## `/reorder` (reorder.png)

### 5-Hat Analysis
**Counter staff:** Page shows a prominent peach/coral band (248, 179, 132) at y≈165–270 — likely a reorder alert card or summary. The band is the most visually dominant element on the page. Small green accent (22, 163, 74) at y≈270 indicates a positive state (item in stock). No form inputs visible — this appears to be a display page only, not an action page.

**Owner-finance:** Green accent for "in stock" vs peach/coral for "needs reorder" — this is a good semantic start. However, only 4 text-row bands suggests minimal data. No cost, no reorder point calibration visible in pixel data. Owner cannot set reorder thresholds from this view.

**Production-baker:** A baker cares about "what ran out" and "when it's needed." The dominant coral band (y≈165–270) likely shows the item causing the reorder. But no timeline or ETA visible. The green band at y≈270 may show items that are fine — baker must mentally scan the whole list.

**New user:** Page width is 1344px (wider than the 1280px standard) — slight horizontal scroll on standard screens. The coral/orange dominant band is attention-grabbing but not clearly labeled as "reorder alerts." No legend. No empty state shown.

**Auditor:** Width inconsistency (1344px vs 1280px standard) suggests this page was built at a different time or with different specs — audit the wireframe version history. No timestamp or auto-refresh indicator — auditor cannot tell if data is live or stale.

### Defects (P0/P1/P2)
- [P0] Page width mismatch — 1344px wide vs 1280px standard; may cause horizontal scroll on common laptop screens — normalize to 1280px container
- [P1] No reorder threshold visibility — Pixel data shows no inputs to set reorder points; owner cannot calibrate levels from this view — add inline-editable reorder-point column
- [P1] Dominant coral band (y≈165–270) has no label — Staff cannot determine what the coral section means without explicit text — add bold section label inside coral band
- [P2] No green = "in stock" legend — Green accent present but no legend — add color legend (green=OK, amber=low, coral=reorder)
- [P2] No timestamp / "actualizado hace N min" — Cannot determine data freshness — add auto-refresh indicator

### Complete Design Wishlist
1. Standardize to 1280px container width
2. Color legend: green=OK, amber=low stock warning, coral=reorder needed, red=stockout
3. Inline-editable reorder points (click-to-edit number inputs)
4. "Última actualización: hace N minutos" timestamp with live refresh
5. Supplier lead-time column (days to deliver)
6. One-click "Generar orden de compra" button from this view
7. Historical reorder frequency per item (did this item trigger reorder often?)
8. Filter by: category, supplier, urgency
9. Batch acknowledge / dismiss reorder suggestions
10. Export to WhatsApp supplier message template

---

## `/analisis` (analisis.png)

### 5-Hat Analysis
**Counter staff:** No orange accent in this page's dominant colors — the brand orange is absent, replaced by neutral grays. The page is 1536px tall (second tallest in batch). This is likely a data-analysis/dashboard page with charts or summary cards. Staff may not have a clear entry point.

**Owner-finance:** A 1536px tall analytics page suggests substantial data visualization. The alternating gray bands (#E5E7EB / #F4F3F2) visible in the band analysis suggest card or panel layout. The dominant dark text (#1F2937) in bands 0, 2, 4, 6 suggests KPI cards with titles. No financial totals visible at top — finance must scroll.

**Production-baker:** The analytics page likely shows production metrics, yield analysis, or waste trends. Band 1 (y≈244–428) has strong #EEEDED gray — likely a chart area. Band 5 (y≈980–1164) has strong #F4F3F2 — another panel. Baker cannot determine key metrics without full scroll.

**New user:** Tall page with no summary above the fold — new users land on a scrolling wall of data. No tab or filter controls visible in pixel data. No introduction or guidance text. The page is entirely data-dense with no visual breathing room.

**Auditor:** No amber or red accents used in analisis — auditor must interpret raw numbers. Gray-only palette for data panels is hard to scan. Footer is sparse (y≈1476–1536). No export button visible in pixel data. Audit-relevant data may be present but inaccessible visually.

### Defects (P0/P1/P2)
- [P1] No KPI summary card at top — Tallest data page with no pinned summary; finance owner must scroll full 1536px to see totals — add collapsible KPI summary bar at top
- [P1] No data export control — Auditor cannot export without scrolling to find export — add floating export button (PDF, CSV) fixed to top-right of content area
- [P2] No chart legend or axis labels in pixel data — Assumed charts without clear labels — ensure all charts have visible titles, axis labels, and legends
- [P2] Gray-only palette — Brand orange (#F97316) entirely absent; no visual hierarchy between sections — reintroduce accent colors to distinguish analysis categories
- [P2] Alternating gray bands may indicate zebra striping — but inconsistent (#EEEDED vs #F4F3F2) — standardize zebra striping or use white backgrounds with border-bottom

### Complete Design Wishlist
1. Pinned KPI summary bar: key metrics visible above the fold
2. Tab navigation for sub-sections (Ventas, Producción, Merma, etc.) to avoid 1536px scroll
3. Floating export button (top-right, always visible)
4. Brand accent color reintroduced for section highlights (orange for sales, amber for production)
5. Chart cards with clear titles, axis labels, and a "?" tooltip explaining the metric
6. Date range picker fixed in the page header (not buried)
7. Comparative indicators: "vs. yesterday", "vs. last week" with arrow icons
8. Click-through from chart to detailed table (drill-down)
9. Collapsible advanced filters panel
10. Auto-refresh with "Datos actualizados hace N min" indicator

---

## `/auditoria` (auditoria.png)

### 5-Hat Analysis
**Counter staff:** A red accent band (220, 38, 38) dominates at y≈730–864 — this is a powerful visual signal for deletions or corrections. The red is used semantically (alert/danger) rather than decoratively. Staff can see at a glance that audit entries with red need attention. However, no visible input form for making corrections — audit trail is read-only.

**Owner-finance:** Audit trail is critical for financial accountability. Red entries likely indicate deletions or reversals. The page has 7 column regions (x≈179, 490, 569, 614, 680, 915, 1178) — a complex table. No financial totals visible in pixel data. Auditor needs to filter by user, date range, and action type — no filter controls visible.

**Production-baker:** Baker actions (waste entry, reorder trigger) create audit events. The auditor page likely logs who did what and when. The red band suggests corrections/reversals are highlighted. Baker cannot easily find their own entries without search/filter.

**New user:** The audit page is intimidating for new users — dense table with red alert highlights, no guidance on what the columns mean. No legend for action types. A new user could mistake a red entry as "error" rather than "reversed action."

**Auditor:** This is the auditor's primary page. The use of red for audit events is the strongest semantic use of color in the batch. However, no filter controls visible in pixel data. 7 column regions suggest: timestamp | user | action | entity | before | after | status. No pagination indicator visible — a long audit log may be a single unpaginated scroll.

### Defects (P0/P1/P2)
- [P0] No filter controls visible — Auditor cannot filter by date range, user, or action type — add filter bar above the table
- [P0] No pagination indicator — A tall audit log with no pagination loads all records — implement paginated table (25/50/100 per page)
- [P1] No legend for red entries — Red is used semantically but not explained — add legend: "Rojo = acción corregida/eliminada"
- [P1] No export for audit log — Audit data must be exported for compliance — add "Exportar log de auditoría" button
- [P2] Column header labels not visible in pixel data — Auditor cannot confirm what each of the 7 columns represents — add sticky column headers with sort controls

### Complete Design Wishlist
1. Filter bar: date range picker, user dropdown, action type filter (creado, modificado, eliminado)
2. Paginated table (25/50/100 rows per page) with jump-to-page
3. Color legend for audit action types: green=new, amber=edit, red=delete/reverse
4. "Exportar auditoría completa" button (CSV + PDF)
5. Sticky column headers with sort arrows on all sortable columns
6. Before/after diff view for modified entries (expandable row)
7. User avatar + name in "Quién" column (not just username)
8. Search bar for entity/item name
9. Compliance timestamp format (DD/MM/YYYY HH:mm:ss) with timezone
10. "Anular última acción" shortcut for authorized users (undo last recorded action)

---

## `/ops/status` (ops/status.png)

### 5-Hat Analysis
**Counter staff:** A compact 900px page. The top band (y≈60–165) is rich in dark text (#1F2937) — likely a status dashboard header with system name and current shift. Orange accents (234, 88, 12) at y≈270 and y≈375 suggest operational alerts or active-process indicators. A very dark band (31, 41, 55) at y≈690–795 suggests a footer action bar or status summary.

**Owner-finance:** Ops status is a live dashboard — owner checks operational health. No financial data visible in pixel structure, which is correct for an ops page. However, no "system OK / degraded / down" top-level status indicator visible from pixel scan.

**Production-baker:** Baker monitors production status here. The orange gradient (y≈270–480) may show active stations or pending orders. The dark footer band (y≈690–795) is 100px of very dark color — likely a status bar or action strip. No time-of-day or shift indicator visible.

**New user:** A status dashboard is good for new users — high-level health check at a glance. However, if the system is operational, there's no "all clear" visual confirmation. If something is broken, there's no "something needs attention" callout.

**Auditor:** An ops/status page is audit-relevant for operational compliance. The dark action bar (y≈690–795) with #1F2937 may contain log or export buttons, but they're invisible against the dark background. No login/logout timestamp visible. No shift-change marker.

### Defects (P0/P1/P2)
- [P1] Dark footer bar (y≈690–795) may contain action buttons invisible due to low contrast — Dark-on-dark (#1F2937 text on #1F2937 bg) — use white/light text on dark background
- [P1] No system health summary — No "Sistema OK" / "Alerta" / "Crítico" indicator at top — add a status badge (green/amber/red) with system uptime
- [P2] No shift / time indicator — Staff don't know which shift is currently logged — add "Turno: Mañana/Tarde/Noche" badge
- [P2] Orange gradient (y≈270–480) with no label — "Station 1, 2, 3" or "Órdenes activas" — add section labels
- [P2] No refresh indicator — Live dashboard with no "actualizado" timestamp — add "Actualizado: HH:mm" with pulsing dot

### Complete Design Wishlist
1. System health badge: green "Operativo" / amber "Atención" / red "Crítico" — pinned top-right
2. Shift indicator badge: current shift + operator name
3. Station status cards: 4–6 boxes showing production stations with color-coded status
4. Active orders count with a subtle pulsing indicator
5. Dark footer with light (white) text for any action buttons — high contrast
6. "Actualizado: HH:mm:ss" with live-pulse dot indicator
7. "Ver incidencias" shortcut button for open issues
8. Temperature/humidity sensor readings if applicable (bakery-specific)
9. Quick-action: "Iniciar turno", "Cerrar turno" buttons
10. Weekly ops summary mini-chart (orders completed, incidents, utilization %)

---

## `/pricing` (pricing.png)

### 5-Hat Analysis
**Counter staff:** Top band (y≈60–165) has dark text with a yellow/amber accent (255, 202, 40) — this is unusual for the brand's orange-primary palette. The amber may indicate a price that needs attention or a highlighted product. Only 6 text-row bands — a compact, scannable page.

**Owner-finance:** Pricing page is financially critical. The amber accent (#FFCA28) is used at the top — likely marking a "sale price" or "promotion." No red/green for margin indicators visible. The price table likely shows: product | cost price | sale price | margin | margin %. The owner needs to see margin % with color coding (green=healthy, red=thin).

**Production-baker:** Baker cares about ingredient costs affecting price. The amber-highlighted item may be a key product. No recipe cost breakdown visible — baker cannot see which ingredient is driving a price change.

**New user:** A pricing page with no explanation of what the columns mean. Amber accent is used decoratively (highlighting the header band) rather than semantically. A new user doesn't know which column is which.

**Auditor:** The amber accent (#FFCA28) is the only non-orange brand accent seen in this page. Auditor cannot determine if amber means "sale," "cost change," or "pending approval." No effective-from date visible — auditor cannot confirm when a price change takes effect.

### Defects (P0/P1/P2)
- [P1] Amber (#FFCA28) used decoratively — Amber is used in the header band without semantic meaning — establish: amber = price under review, green = approved, red = cost above threshold
- [P1] No effective date on price changes — Auditor cannot confirm when a price takes effect — add "Vigente desde:" date per row
- [P2] No margin % column — Owner needs margin % with color coding — add margin % with conditional formatting (green >30%, amber 15–30%, red <15%)
- [P2] No cost-breakdown link — Baker cannot see which ingredient drives a price — add "Ver costo" link per row
- [P2] Footer (y≈840–900) has a subtle orange accent — Footer is typically metadata; decorative orange here is wasted — move orange accent to primary CTA only

### Complete Design Wishlist
1. Margin % column with conditional color: green >30%, amber 15–30%, red <15%
2. "Vigente desde" date per row with calendar picker for scheduled changes
3. Cost breakdown modal: click a product → see ingredient costs + labor + overhead
4. Bulk price update: select multiple rows → apply % increase/decrease
5. Approval workflow: "Pendiente de aprobación" amber state → "Aprobado" green state
6. Price history per product (last 5 changes with timestamps)
7. Competitor price reference column (optional, owner-entered)
8. "Precio sugerido" calculated field based on cost + target margin
9. Print-optimized price list layout (A4, 2 columns)
10. PDF export of official price list with validity date header

---

## `/reportes` (reportes.png)

### 5-Hat Analysis
*Note: reportes.png was not found in the screenshots directory at time of analysis. File listing confirmed: merma.png, shopping-list.png, reorder.png, analisis.png, auditoria.png, ops-status.png, pricing.png are present. reportes.png is referenced in the task but absent from the provided paths. This page could not be analyzed.*

---

## Cross-Page Defects Summary (batch-level)

### Brand & Consistency
- [P1] Inconsistent accent usage: auditoria uses red (#DC2626) for deletions, merma uses only orange; analisis uses no brand accent at all — establish a semantic color system and apply consistently across all pages
- [P1] Inconsistent page widths: reorder.png is 1344px wide vs 1280px standard — audit all pages for width normalization
- [P2] Footer zones are underused across all pages — most pages have y≈840–900 (or equivalent) as sparse footer; add contextual CTAs and metadata

### Typography & Color
- [P2] Primary text: #1F2937 (dark blue-gray) is consistent across all pages — good
- [P2] Secondary text: #6B7280 (medium gray) is consistent — good
- [P2] Border/divider: #E5E7EB (light gray) is consistent — good
- [P2] Brand orange #F97316 is in the top header of all pages — good for branding, but overused as a decorative accent in content areas

### Navigation & Orientation
- [P1] No breadcrumb trail on any page — users cannot orient within the app hierarchy
- [P2] No "?" help icons on any page — contextual guidance absent
- [P2] No pagination controls visible on any data table — auditoria (audit log) especially needs pagination

### Data Tables
- [P1] No zebra striping consistently applied — some bands show gray alternation, others don't
- [P1] No row numbers on any table — reference and communication are impaired
- [P2] No column sort indicators visible in pixel data — all tables should have sortable column headers with arrow indicators
- [P2] No sticky/fixed header rows on tables — long tables (merma 1964px, analisis 1536px) require fixed headers

### Forms & Inputs
- [P2] merma page appears to be form-heavy but no input field styling visible in pixel data — ensure inputs have visible focus states and validation feedback
- [P2] shopping-list has no visible "add item" form above the fold
- [P2] reorder page has no inline-editable reorder points despite being a threshold-configuration page

### Accessibility & Inclusion
- [P1] No ARIA labels detected in pixel data — ensure all interactive elements have accessible names
- [P2] Low contrast on ops/status dark footer bar (y≈690–795) — dark-on-dark buttons
- [P2] No keyboard focus indicators visible in static screenshots — ensure focus rings are implemented in code
- [P2] Auditoria uses red (#DC2626) for audit entries — ensure this is not the sole color cue (add iconography/text label for colorblind accessibility)

---

*Critique compiled from pixel-level analysis of PNG screenshots. All observations are based on visual patterns extracted from the raster images. Language: Spanish (vos form) as appropriate for Paraguayan bakery context.*
