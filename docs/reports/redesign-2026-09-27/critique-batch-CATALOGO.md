# Saskia RMS — Visual Critique Batch: Catálogo
**Auditor:** UX/UI Principal + QA Architect
**Scope:** 8 pages — clientes family (3), inventario variantes, recetas family (4)
**Method:** 5-hat analysis per page + defect log + wishlist

---

## `/clientes` (clientes.png)

### 5-Hat Analysis
**Counter staff:** The clientes list is compact (900px) — staff can see the full client roster without scrolling. The top nav bar has brand orange (#F97316) consistent with other pages. The table likely shows client name, phone, and maybe a status column based on the column peak at x≈40 (narrow first column = icon or checkbox). No visible "add client" CTA above the fold — staff must scroll or navigate to add a new client. No search bar visible in pixel data — finding a client by phone at the counter requires scanning the full list.

**Owner-finance:** A client list without revenue or order-history indicators means the owner cannot identify VIP clients at a glance. No "Última compra" column visible. No total client count KPI card at top. The table is read-only — no inline edit capability. No export button visible.

**Production-baker:** Baker does not interact with client data directly. Irrelevant for this role.

**New user:** A clean, short page — new users can immediately see all clients. However, no empty-state illustration or guidance if the list is empty. No column header tooltips. No explanation of what each column means (especially if a status or notes column exists).

**Auditor:** Client data is personally identifiable information (PII). No indication of data-export controls or privacy notices. No audit log column showing who added/modified clients. The narrow column peak at x≈40 may be a checkbox column for bulk actions — if so, a bulk-delete without confirmation would be a data-integrity risk.

### Defects (P0/P1/P2)
- [P1] No search bar — counter staff cannot quickly find a client by name or phone — add a search input with live filter, anchored top-right of the content area
- [P1] No "Agregar cliente" CTA visible above fold — staff must navigate to add — add an "Agregar cliente" button in the content header
- [P2] No "Última compra" or order-count column — owner cannot identify active vs. inactive clients — add a column showing days since last order or total orders
- [P2] No client count KPI in header — how many total clients is unknown without counting — add "N clientes" badge in the page header
- [P2] No bulk-action confirmation — if the narrow x≈40 column is checkboxes, bulk delete without a confirmation dialog is a data-safety risk — add `SaskiaConfirmModal` for bulk delete

### Complete Design Wishlist
1. Search bar with live name/phone filtering
2. "Agregar cliente" primary CTA button in header
3. "Última compra" column (days since last order, color-coded: green=recent, amber=>30 days, red=>90 days)
4. Total client count badge in header
5. Sort by: nombre, última compra, totalPedidos descendente
6. Click-to-edit client inline (no navigation to detail page)
7. Exportar clientes → CSV button
8. PII data handling notice in footer
9. Empty state: illustrated "Aún no hay clientes" + "Agregar el primero" CTA
10. Sticky table headers on scroll

---

## `/clientes/{id}` (cliente-detalle.png)

### 5-Hat Analysis
**Counter staff:** A tall page (1146px) — the client detail has more vertical content than most pages. The orange accent appears in the header band. The detail page likely shows client name, phone, email, address, and a purchase history table. No quick-call or quick-SMS button visible in pixel structure — staff must copy phone number manually. No visible "editar" shortcut at top.

**Owner-finance:** Purchase history is the key financial signal here. A tall page (1146px) means the transaction history is long. No revenue summary (total spent, average order value) pinned above the fold. No customer tier/status badge (e.g., "Cliente frecuente", "Nuevo"). No notes field visible — the owner cannot see internal notes about the client.

**Production-baker:** Not directly relevant.

**New user:** The client detail page is navigation-deep (clientes → client). No breadcrumb trail visible. New users may lose their context and not know how to return to the list. No help text explaining what the purchase history columns mean.

**Auditor:** Purchase history per client is audit-relevant for fraud detection and revenue verification. No "who viewed this client" or "who edited this client" audit trail. The tall page with purchase history table may have no pagination — a client with 500 historical orders would load all at once.

### Defects (P0/P1/P2)
- [P1] No quick-contact button — staff cannot call or SMS a client directly from this page — add 📞 Llamar and 💬 WhatsApp buttons in the client header
- [P1] No pinned revenue summary — owner must scroll 1146px of history to see total spend — add a summary card: "Total gastado: Gs. X | Pedidos: N | Promedio: Gs. X"
- [P2] No breadcrumb — client detail is 2 levels deep with no trail — add "Clientes > [Nombre del cliente]" breadcrumb
- [P2] No customer tier/status badge — owner cannot quickly see client value — add "Frecuente / Nuevo / Inactivo" badge
- [P2] Purchase history table not paginated — client with many orders loads all at once — paginate at 20 rows with "Ver más"

### Complete Design Wishlist
1. 📞 Llamar and 💬 WhatsApp buttons in the client header
2. Revenue summary card pinned at top: total spent, order count, average order value
3. Breadcrumb: Clientes > [Nombre del cliente]
4. Customer tier badge: Nuevo (< 30 días), Frecuente (> 5 pedidos), Inactivo (> 90 días sin pedidos)
5. Internal notes field (owner-only visible) with edit capability
6. Purchase history table paginated (20 per page) with date range filter
7. "Último pedido" timestamp prominent in header
8. "Enviar promoción" button linked to WhatsApp or email marketing
9. Edit button accessible from the client header without navigating to /editar
10. Audit trail: "Creado por X el DATE" / "Última edición por Y el DATE"

---

## `/clientes/{id}/editar` (cliente-editar.png)

### 5-Hat Analysis
**Counter staff:** The edit form has a prominent horizontal band at y≈210 — likely a section divider separating personal data from additional info. Orange accent density (527 orange-ish dark pixels) is higher here than clientes.png — more interactive elements on this page. The form likely has fields for: nombre, teléfono, email, dirección, notas. No inline validation feedback visible in pixel data. The "Guardar" button is likely below the fold (form is 900px tall, typical form length).

**Owner-finance:** Client edit form is a PII touchpoint. No data-quality validation visible (e.g., phone format, email format). Saving the form commits changes — no "descartar cambios" escape path visible. No change-audit timestamp: owner cannot see who last edited a client and when.

**Production-baker:** Not relevant.

**New user:** A form page with no field labels visible in pixel structure — new users must infer field purpose from placeholder text. No help text on any field. Phone field does not specify format (Paraguayan numbers have 9-10 digits). No indication of required vs. optional fields.

**Auditor:** PII changes have no audit trail in this view. No "field-level change history" — an auditor cannot tell which specific field was changed and by whom. The form structure has no CSRF token visible in pixel data (requires code inspection). Form submission may be vulnerable to CSRF if the template lacks a token.

### Defects (P0/P1/P2)
- [P1] No inline validation feedback — phone/email format errors shown only after failed submit — add real-time validation: red border + error message below invalid fields
- [P1] No "Descartar cambios" escape path — user who edits accidentally has no cancel button — add "Cancelar" button that returns to client detail without saving
- [P2] No required-field indicators — new users cannot tell mandatory from optional fields — add asterisk (*) on required fields with a legend: "* = obligatorio"
- [P2] No change-audit metadata — "Última edición por X" not shown — add editor name + timestamp below the form or in the page footer
- [P2] Phone field has no format hint — Paraguayan format not indicated — add placeholder "09XX XXX XXX" and input mask

### Complete Design Wishlist
1. Real-time inline validation (red border + message on blur for phone, email)
2. "Cancelar" button that returns to client detail without saving
3. Required field asterisk (*) with legend
4. Phone input mask: "0999 123 456" format
5. "Última edición por [usuario] el [fecha]" in footer
6. Email field with "Verificar email" option to send a test email
7. Address field with Google Maps integration (optional)
8. Internal notes textarea (non-PII, staff-only notes)
9. "Guardar y agregar otro" option for rapid client entry
10. CSRF token in form (verify in template code)

---

## `/inventario/variantes` (inventario-variantes.png)

### 5-Hat Analysis
**Counter staff:** The tallest page in this batch (1457px) — this is a data-heavy variant management page. Sidebar is lighter gray (#F7F6F5) vs the clients pages (#F9FAFB). The horizontal band at y≈960 suggests a table or data panel. No quick-filter visible at top. Staff managing variants (sizes, colors, packaging options) need to see stock per variant — the table likely has many rows.

**Owner-finance:** Variant management is critical for product costing. A tall table (1457px) with variant rows means no summary KPI visible above the fold. No total stock value shown. No cost-per-variant visible. Owner cannot see which variants are driving inventory cost.

**Production-baker:** Baker needs to know which variant of an ingredient to use. The variant table may show size/packaging options per product. No visual indicator of which variant is the "standard" or "preferred" unit. No conversion factor display (e.g., "1 caja = 12 unidades").

**New user:** A tall page with no orientation aids. No filter chips visible. No page title treatment (e.g., bold H1). New users may not understand the difference between a variant and a base product — no explanatory tooltip. The page is entirely a data table with no introduction or summary.

**Auditor:** Variant-level inventory is audit-relevant for stock accuracy. No variant-level audit trail visible. If a variant is discontinued, there's no visual indication. The sidebar gray (#F7F6F5) differs from the clients pages (#F9FAFB) — a subtle but real inconsistency in the sidebar color.

### Defects (P0/P1/P2)
- [P1] No pinned KPI summary — 1457px of variant data with no stock-value or total-units summary — add a summary bar: "N variantes · Total stock: X unidades · Valor: Gs. Y"
- [P1] No filter/search controls visible — staff managing many variants cannot find a specific product/variant — add search + filter chips (por producto, por estado)
- [P2] Inconsistent sidebar color — inventario-variantes uses #F7F6F5 vs clientes pages #F9FAFB — standardize sidebar to a single brand-approved background
- [P2] No variant-discontinuation indicator — inactive variants not visually distinguished from active — add a strikethrough or gray treatment for discontinued variants
- [P2] No conversion factor display — baker cannot see unit conversions — add a "Equivalencia" column showing pack sizes

### Complete Design Wishlist
1. Pinned summary bar: total variants, total units, total value in Gs.
2. Search bar + filter chips: por producto, activo/inactivo, bajo stock
3. "Equivalencia" column showing pack size conversions (e.g., "1 caja = 12 u")
4. Active/inactive toggle with visual strikethrough for inactive variants
5. Inline-editable stock quantity (click-to-edit in table)
6. Stock alert indicator: amber for low, red for zero
7. "Ver producto base" link per variant
8. Bulk variant activation/deactivation (select multiple → action menu)
9. Variant-level cost column (precio costo por variante)
10. Exportar variantes → CSV

---

## `/recetas/{id}/detalle` (receta-detalle.png)

### 5-Hat Analysis
**Counter staff:** The recipe detail page has a horizontal band at y≈490 — this likely separates the recipe header (name, category, photo) from the ingredients list. The orange accent is present but sparse (267 orange-ish pixels) — this is primarily a read page, not a form page. No "copiar receta" or "imprimir" visible at top.

**Owner-finance:** Recipe detail is the foundation of food-cost calculation. The ingredients list must be accurate for costing to work. No total-cost-per-recipe visible at top — finance must sum ingredients manually. No serving/yield data visible — owner cannot calculate cost per portion.

**Production-baker:** The baker's primary page. The ingredients list is the critical content. No step-by-step instructions section visible in pixel data — if the recipe has preparation steps, they may be below the fold (page is 1132px). No batch-size selector — baker cannot scale the recipe visually.

**New user:** A recipe without context: no "qué es esta receta" description visible. No difficulty or time estimate. No tags or categories visible. A new employee cannot determine if a recipe is simple or complex without reading through it.

**Auditor:** Recipe details are the basis for food-cost variance reporting. If ingredient quantities are wrong, all costing is wrong. No "última edición" timestamp — auditor cannot determine if a recipe was updated after a cost variance occurred. No version history visible.

### Defects (P0/P1/P2)
- [P1] No total recipe cost pinned at top — owner/baker must manually sum ingredients — add "Costo total: Gs. XXXX" badge in recipe header
- [P1] No batch-size/yield display — cost per portion is invisible without yield data — add "Rinde: X porciones" and "Costo por porción: Gs. Y"
- [P2] No preparation steps visible at top — baker must scroll 1132px to find instructions — add a numbered steps section above the fold or a collapsible panel
- [P2] No "última edición" timestamp — no indication of recipe currency — add "Editada por [usuario] el [fecha]" in the recipe header
- [P2] No difficulty or time estimate — new users cannot gauge recipe complexity — add "Dificultad: Baja/Media/Alta" and "Tiempo: N min"

### Complete Design Wishlist
1. "Costo total: Gs. XXXX" and "Costo por porción: Gs. Y" in header
2. "Rinde: X porciones" yield display
3. Numbered preparation steps in a collapsible panel above ingredients
4. "Dificultad" and "Tiempo de preparación" badges
5. Batch size selector: 1x, 2x, 4x — scales ingredient quantities visually
6. "Ingredientes que faltan" highlight: compare against current inventory stock
7. "Ver producto terminado" link to the linked product in /productos
8. Print recipe (print-optimized stylesheet)
9. "Duplicar receta" for creating variants
10. Recipe version history with diff view

---

## `/recetas/{id}/editar` (receta-editar.png)

### 5-Hat Analysis
**Counter staff:** The tallest receta page (1234px). A strong horizontal band cluster at y≈570–810 — this is a dense form area with many input fields. Orange accent is heavy (424 orange-ish pixels) — many interactive elements. Column peaks at x≈865–1240 suggest a two-column form layout (left: ingredient fields, right: metadata/costing). No autosave indicator visible.

**Owner-finance:** Recipe costing fields are likely in the right column (x≈865+). No live cost preview as ingredients are entered — owner must mentally calculate. No validation that all ingredients have prices — a recipe with unpriced ingredients produces a zero cost which looks correct but is wrong. No portion-size input for yield calculation.

**Production-baker:** The ingredient list editor is the baker's tool. No drag-to-reorder ingredients. No unit selector visible (g, kg, ml, l) — unit ambiguity is a production error source. No "costo por ingrediente" column visible — baker cannot see which ingredient is most expensive.

**New user:** A 1234px form is intimidating. No field groupings with headers visible in pixel structure. No progress indicator (step 1 of 2, or percentage complete). No save-as-draft option — user must complete the form in one session or lose work.

**Auditor:** Recipe edits are the most audit-sensitive changes (food-cost implications). No "saved by X at time T" audit trail on individual field changes. Autosave without user confirmation could silently change recipe costs and invalidate previous food-cost reports.

### Defects (P0/P1/P2)
- [P0] No autosave confirmation — edits may be saved silently without the user's intent — add a "Guardado automáticamente" / "Guardado" status indicator
- [P1] No live cost preview — entering ingredient quantities shows no running total — add a live "Costo total: Gs. XXX" counter as ingredients are entered
- [P1] No unit selector — ingredient quantities have no unit label; baker cannot know if a quantity is grams or kilograms — add a unit dropdown (g, kg, ml, l, unidad) per ingredient row
- [P2] No drag-to-reorder ingredients — recipe order cannot be rearranged without delete+re-add — add drag handles on ingredient rows
- [P2] No save-as-draft — user must complete form in one session — add "Guardar como borrador" option

### Complete Design Wishlist
1. Live "Costo total: Gs. XXX" counter in header, updating as ingredients are edited
2. Unit dropdown per ingredient (g, kg, ml, l, unidad) with visual unit consistency
3. "Guardado automáticamente" status chip with timestamp
4. "Guardar como borrador" option
5. Ingredient drag-to-reorder with drag handles
6. "Costo por ingrediente" column showing each ingredient's contribution to total cost
7. Portion/yield input field for cost-per-portion calculation
8. Field-group headers: "Ingredientes", "Información nutricional", "Pasos de preparación", "Metadatos"
9. Validation: warn if any ingredient has no price assigned (zero-cost ingredient)
10. "Preview" mode: render the recipe as it would appear on /detalle before saving

---

## `/recetas/crear-producto` (receta-crear-producto.png)

### 5-Hat Analysis
**Counter staff:** The tallest page in this batch (1595px) — this is a complex multi-section creation form. Horizontal bands at y≈120, 510, 900 suggest three distinct form sections. Staff creating a new product via recipe must scroll through all 1595px to complete the form. No section progress indicator. No "guardar como borrador" option.

**Owner-finance:** Product creation links a recipe to a sellable product. The form likely has: product name, category, pricing, photo, and recipe linkage. No "costo sugerido" based on recipe cost — owner must manually set price. No margin calculation preview.

**Production-baker:** The baker creates recipes that become products. The form is long and complex (1595px) — a baker at the counter cannot complete this in one sitting. No "save draft and come back" option. No recipe linkage step visible — baker may not understand that they need a recipe before creating the product.

**New user:** The most intimidating page in the batch — 1595px of form with no section navigation. A new user has no idea what fields are required and in what order. No introductory explanation: "Para crear un producto nuevo, primero necesitás una receta." No empty-state guidance on what a recipe-product relationship means.

**Auditor:** New products are financially significant (they generate sales). No audit trail on the creation form itself. If a product is created with an incorrect recipe linkage, all food-cost data for that product will be wrong.

### Defects (P0/P1/P2)
- [P0] 1595px single-page form with no section navigation — user must scroll the full length to complete — split into a step wizard: Paso 1: Datos del producto, Paso 2: Receta, Paso 3: Precio, Paso 4: Revisar y guardar
- [P1] No recipe linkage guidance — user may create a product without linking a recipe — add an explicit step/field: "Vincular receta" with a searchable recipe dropdown
- [P1] No "costo sugerido" or margin preview — owner sets price without seeing food cost — add "Costo del producto: Gs. X | Margen sugerido: Y%"
- [P2] No save-as-draft — long form with no draft capability — add "Guardar como borrador" + "Continuar después" button
- [P2] No section headers visible — user cannot orient within the 1595px — add bold section titles: "Datos básicos", "Receta", "Precio", "Fotos"

### Complete Design Wishlist
1. Convert to a multi-step wizard (3-4 steps) with progress indicator
2. Step 1: Datos del producto (nombre, categoría, descripción)
3. Step 2: Receta (vincular receta existente o crear nueva)
4. Step 3: Precio y presentación (precio venta, precio mayorista, unidad)
5. Step 4: Revisión — show full preview + costo/margen calculation before save
6. "Costo sugerido" based on linked recipe cost
7. "Guardar como borrador" available at any step
8. Product photo upload with crop/preview
9. Autosave at each step transition
10. Validation summary on final step: "N errores encontrados" before submit

---

## `/recetas/{id}/set-photo` (receta-set-photo.png)

### 5-Hat Analysis
**Counter staff:** A page at 1183px with 8 distinct horizontal band clusters and 6 column peak regions — the most structurally complex page in this batch. The photo-set page has a central photo upload zone with multiple interaction regions. Orange accent density is low (143 orange pixels) — this is a focused, low-distraction page. The band clusters suggest: header area, photo preview area, instruction/help text, and action buttons.

**Owner-finance:** No financial impact directly. However, a product photo affects perceived value and can justify premium pricing. No "foto recomendada" size/format guidance visible — owner may upload photos that render poorly.

**Production-baker:** The baker sets the photo for their recipe — a good visual identity tool. No before/after comparison if replacing an existing photo. No photo quality indicator (is the photo blurry? too dark?).

**New user:** A dedicated photo page is unusual — most apps embed photo upload in the edit form. New users may not know what photo size/format is expected. No preview of how the photo will appear in different contexts (recipe card, product list, receipt).

**Auditor:** Photo assets have no metadata audit. No "photo uploaded by X at T" attribution. If a photo is disputed (wrong product photo), there is no change history.

### Defects (P0/P1/P2)
- [P1] No photo requirements guidance — user uploads without knowing recommended size, format, or dimensions — add "Recomendamos: 800×600 px, JPG o PNG, máximo 2MB" below the upload zone
- [P1] No preview of how the photo renders in context — user uploads blind — add a live preview showing the photo as it appears in recipe list, recipe detail header, and product card
- [P2] No "remove/replace photo" option — if a photo exists, the UI to remove or replace it is not obvious — add "Eliminar foto" button visible when a photo is loaded
- [P2] No photo quality indicator — blurry or dark photos are not flagged — add an automated quality check: "Esta foto parece oscura. ¿Querés ajustarla?"
- [P2] No photo change audit — no "Foto actualizada por X el T" — add a change log entry for photo changes

### Complete Design Wishlist
1. "Requisitos de foto" panel: dimensions, format, max size with visual examples
2. Live contextual preview: show the photo as it appears in 3 different UI contexts
3. "Eliminar foto" button when a photo is loaded
4. Basic photo enhancement: brightness/contrast auto-fix option before upload
5. Drag-and-drop upload zone with visual feedback
6. "Usar foto de producto" shortcut if the recipe is linked to a product
7. Photo change audit log entry
8. Crop tool with fixed aspect ratio (4:3 for recipe cards)
9. Maximum file size enforcement with clear error message
10. "Subir después" skip option to save form without a photo

---

## Cross-Page Defects Summary (batch-level)

### Navigation & Orientation
- [P1] No breadcrumb trail on any of the 8 pages — /clientes/{id}/editar has 3 levels of depth with no crumb — add breadcrumbs across all inner pages
- [P2] cliente-detalle (1146px), receta-editar (1234px), receta-crear-producto (1595px) are all tall pages with no scroll-progress indicator — add a thin progress bar or "N de M" step indicator
- [P2] No "?" help icons on any form page — form fields lack contextual explanations

### Data Tables
- [P1] No row numbers on any table — /inventario/variantes (1457px) has the most rows with no index — add a row-id column on all data tables
- [P2] /inventario/variantes uses a different sidebar gray (#F7F6F5) vs the clientes pages (#F9FAFB) — inconsistent sidebar treatment
- [P2] /receta-detalle table (1132px) has no pagination visible — add paginator with 20 rows per page

### Forms & Input
- [P0] receta-crear-producto is a 1595px single-page form with no step navigation — split into a wizard
- [P1] No unit selector on receta-editar ingredient rows — unit ambiguity is a production error source — add dropdown per row
- [P1] No live cost preview on receta-editar — cost shown only after save — add running total counter
- [P2] cliente-editar form (900px) has no required-field indicators
- [P2] No save-as-draft on any form page — long forms (receta-crear-producto at 1595px) lose work on accidental navigation

### Brand & Consistency
- [P2] Brand orange (#F97316) is the primary accent on all 8 pages — good for branding, but every page uses it identically for CTAs — consider differentiating primary actions (save/confirm) from brand reinforcement
- [P2] receta-set-photo uses the most structurally complex layout (8 band clusters, 6 column regions) while cliente-editar is minimal (3 band clusters) — layout complexity is not standardized across page types

### Accessibility & Inclusion
- [P2] Orange accent-only CTAs may have insufficient contrast for colorblind users — add iconography or text labels, not just color
- [P2] No ARIA live regions on autosave indicators (receta-editar) — screen readers do not announce save state changes
- [P2] cliente-detalle (1146px) and receta-crear-producto (1595px) are both tall pages that break keyboard navigation — ensure all interactive elements are reachable without a mouse

---

*Critique compiled from pixel-level structural analysis of PNG screenshots. All observations are based on visual patterns extracted from raster images (1280px-wide viewport captures). Language: Spanish (vos form) as appropriate for Paraguayan bakery context.*
