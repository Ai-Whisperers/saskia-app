# Recetas & Productos — Comprehensive Feature Wishlist
**Generated:** 2026-09-28 | **Scope:** `/productos`, `/recetas`, `/inventario`, `/recetas/{id}`, `/recetas/{id}/editar`, `/recetas/nueva`, `/productos/nuevo`, `/productos/{id}/editar`, `/inventario_movimientos`

---

## HOW TO READ THIS DOCUMENT

Each section lists features **currently missing** from the app. Every item represents a gap between what exists and what a professional bakery/café management system should provide. Items are grouped by page and ranked by impact. "Already exists" items are marked ✅ DONE and kept for reference. Items requiring backend changes are marked **[Backend needed]**.

---

## PART 1 — PRODUCTOS LIST PAGE (`/productos`)

### 1.1 Core Data Display

**✅ DONE — Column visibility toggle** (Nombre, SKU, Porción, Precio, Receta, Costo, Margen, Margen %, Disponible)
**✅ DONE — Sortable columns** (Nombre, Precio, Costo, Margen — URL param `?sort=&dir=`)

**❌ MISSING — Product image thumbnails in the table row**
- Currently: `image_url` is stored but NOT rendered in the productos table row
- Should show: 36×36px thumbnail, same as `row-thumb` pattern already used in ventas
- Impact: makes the list scannable at a glance; missing thumbnail = can't visually identify products without opening each one

**❌ MISSING — "Dead product" row highlighting is purely visual**
- Currently: `.row-dead` CSS class adds amber tint; no bulk action
- Should: bulk action "Archivar productos sin ventas" + filter "Solo muertos" to quickly identify and remove stale catalog entries

**❌ MISSING — Category pills render on product rows but there's no category filter**
- Currently: `p.category` renders as pill on row but the filter bar has NO category dropdown for products
- Inventario has `?categoria=` filter; productos list does not
- Should: add `mf-pop` category filter to productos toolbar (same pattern as inventario)

**❌ MISSING — Tag pills on product rows are not filterable**
- Tags like `con-nueces`, `dia-madre`, `docena`, `estacional`, `festivo`, `individual`, `navidad`, `para-eventos`, `popular` exist in DB but there's no "filter by tag" on the productos list
- Should: add "Etiquetas" mf-pop filter with checkboxes per unique tag

**❌ MISSING — Wholesale / Mayorista pricing columns**
- The model has only `sale_price_gs`; no wholesale price
- Bakery operations frequently need: precio minorista vs precio mayorista (catering, events, wholesale to other shops)
- Should: add `mayorista_price_gs` field to Product model, display in separate column when set

**❌ MISSING — Cost history / price change tracking**
- Product cost changes over time; currently only the latest cost is visible
- Should: "Historial de costos" link on the cost column that opens a modal/slide-over showing cost changes over time (linked to IngredientPriceEvent table)

**❌ MISSING — Recipe link is text-only, not clickable**
- `p.recipe_name` renders as plain text link `<a href="/recetas/{{ p.recipe_id }}">` is missing
- Should: wrap `p.recipe_name` in an actual `<a>` tag pointing to `/recetas/{{ p.recipe_id }}`

**❌ MISSING — Unit cost and margin are shown but not explained**
- "Costo" and "Margen" columns show numbers with no tooltip explaining what they mean
- Should: add `title=` attribute explaining: "Costo = costo de ingredientes por porción según receta. Margen = precio venta − costo."

### 1.2 Filtering & Search

**❌ MISSING — Text search is slow (full-page reload)**
- `?q=` search causes full-page form GET reload; should debounce 300ms and use fetch
- Impact: minor UX friction, not a blocker

**❌ MISSING — Filter state in URL is lost on page refresh**
- All active filters should persist in URL params so a refresh keeps the view

**❌ MISSING — Active filter chips / tags showing what's currently filtered**
- After selecting filters, no visible "chip" shows "Margen: negativo ×" that can be dismissed
- Should: render dismissible chips below the toolbar showing active filters

**❌ MISSING — "Sin precio" (missing cost) quick filter**
- Productos list has no quick filter for products where `cost_gs is none`
- Inventario has "Sin precio" filter; productos should match

**❌ MISSING — Combined filter persistence across pagination**
- Pagination links don't carry the active filter state (query params for `q`, `margen_sel`, `has_recipe`, `disp_sel` are missing from pagination URLs)
- Should: pagination links must include all active filter params, not just sort/page

### 1.3 Bulk Operations

**✅ DONE — Bulk delete with confirmation modal**

**❌ MISSING — Bulk edit (price update, availability toggle, category assignment)**
- No bulk operation for: update price by %, set availability, assign category, add tags
- Impact: high for catalog management; adding tags to 30 products currently requires opening each one

**❌ MISSING — Bulk CSV import**
- No inverse of the CSV export; can't import products from a spreadsheet
- Impact: medium — initial catalog setup is manual

**❌ MISSING — Bulk duplicate / clone**
- No "duplicate product" action
- Impact: creating variants (e.g., "Muffin chocolate" → "Muffin vainilla") requires full re-entry

### 1.4 Export

**✅ DONE — CSV export** (`/productos/export.csv`)

**❌ MISSING — CSV export includes ALL columns, not just what's visible**
- Export should match visible columns (including the new prime cost columns if added)

**❌ MISSING — PDF price list / catalog**
- Bakeries need a printed price list for events, catering quotes
- Should: generate PDF with product name, portion, price, category

---

## PART 2 — PRODUCTOS NEW/EDIT FORM (`/productos/nuevo`, `/productos/{id}/editar`)

### 2.1 Form Fields

**✅ DONE — Name, SKU, category, portion_label, sale_price_gs, is_available, image_url, tags**

**❌ MISSING — Wholesale price field**
- No `mayorista_price_gs` field in the form
- Impact: high for catering/business clients

**❌ MISSING — "Requiere RSPA" + RSPA number + expiry date fields are hidden**
- `requires_rspa`, `rspa_number`, `rspa_expiry` exist in the model but are NOT in the form
- Impact: medium — compliance feature for packaged retail products

**❌ MISSING — IVA rate selector is missing from form**
- `iva_rate` field exists in model but not rendered in the edit form
- Impact: fiscal compliance — Paraguay requires correct IVA declaration

**❌ MISSING — Internal note / description field**
- `notes` field exists but is NOT in the form template (only rendered in the productos list row as plain text, not editable)
- Impact: staff need to record notes like "solo disponible viernes", "proveedor X", "presentación para evento"

**❌ MISSING — Yield percentage / waste factor field**
- `yield_percentage` exists on Product but not in the form
- Impact: cost accuracy — a 15% moisture loss means the actual edible yield is lower than batch weight

**❌ MISSING — Barcode / SKU barcode rendering**
- SKU field exists; no barcode rendering
- Should: show a barcode (Code128) below the SKU field in the edit form for physical labeling

**❌ MISSING — Image URL field shows no preview**
- `image_url` is a text field; uploading/pasting a URL gives no preview
- Should: live preview thumbnail as URL is typed/changed

**❌ MISSING — Related products / "paired with" field**
- No way to link products: "usually bought together", "complements", "same family"
- Impact: helpful for POS upselling and purchasing planning

**❌ MISSING — Supplier / provenance field**
- No supplier tracking on products
- Impact: can't answer "which products use ingredient X from supplier Y"

**❌ MISSING — Minimum stock level per product**
- No reorder-point per product
- Impact: can't auto-suggest purchase orders based on sales velocity

### 2.2 Form UX

**❌ MISSING — Inline validation errors**
- Form submits and either succeeds or shows flash error; no inline field-level validation
- Should: validate on blur: required fields, price > 0, SKU uniqueness

**❌ MISSING — Unsaved changes warning**
- Navigating away from edit form with unsaved changes shows no warning
- Should: `beforeunload` event when form is dirty

**❌ MISSING — Form auto-save draft**
- No localStorage draft; a browser crash loses all entered data
- Should: save draft to localStorage every 30s

**❌ MISSING — "Save and create another" workflow**
- After saving a new product, user goes back to list; no "save and add another" option
- Impact: speed for initial catalog entry

**❌ MISSING — "Save and go to recipe" after creating product with no recipe**
- After creating a product, user must manually navigate to create the recipe
- Should: offer "Crear receta ahora →" prompt when saving a product that has no recipe

**❌ MISSING — Tag input should be multi-select combobox, not plain text**
- `tags` is stored as comma-separated string; form has a plain text input
- Should: use the multi-select combobox pattern (same as `mf-pop` but as form input) for selecting/creating tags

### 2.3 Image Upload

**✅ DONE — Image URL field exists**

**❌ MISSING — Direct file upload (not just URL)**
- No drag-and-drop or file picker; user must host images externally
- Impact: high — forces users to use external image hosting

**❌ MISSING — Image cropping / resizing**
- No server-side or client-side image processing
- Impact: uploaded images may be huge, slow to load

**❌ MISSING — Multiple images per product**
- Only one `image_url`; bakeries want gallery views (front, cut, box, label)
- Impact: medium — cosmetic but useful for catalog quality

---

## PART 3 — RECETAS LIST PAGE (`/recetas`)

### 3.1 Core Data Display

**✅ DONE — Table with Foto, Nombre, Rinde, Líneas, Costo del lote, Costo/porción, Costo total**

**❌ MISSING — Recipe difficulty displayed as visual stars, not number**
- `difficulty` (1–5) renders as plain number; should render as ⭐⭐ stars
- Should: `{% for i in range(recipe.difficulty) %}⭐{% endfor %}`

**❌ MISSING — Prep time and cook time not shown in the list**
- `prep_minutes` and `cook_minutes` exist but not displayed in the table
- Should: add columns "Prep" and "Cocción" showing e.g. "15 min" / "45 min"

**❌ MISSING — Total recipe cost not broken down (ingredients vs labor vs overhead)**
- Table shows `batch_cost_gs` but no breakdown
- Impact: operators can't see at a glance what drives cost

**❌ MISSING — Sub-recipe indicator in the list**
- Recipes that are used as sub-recipes in other recipes show no indicator
- Should: badge "Sub-receta" on recipes that appear in other recipes' line items

**❌ MISSING — Recipe last-modified date**
- No "última edición" column
- Impact: hard to find stale recipes needing cost review

**❌ MISSING — Recipe author / created by**
- No user tracking on who created or last edited a recipe
- Impact: multi-user environments need accountability

**❌ MISSING — Filter by ingredient (already wired but has issues)**
- `?ingredient_id=` filter exists but uses a combo field; the filter clears and resets on form submission
- Should: persist the selected ingredient in the URL after filter submit

**❌ MISSING — Family/category filter uses checkboxes but not shown in URL**
- `?familias_sel=` param not carried through pagination links
- Pagination links must include `familias_sel`, `diet_sel`, `ingredient_id`

**❌ MISSING — "Recetas sin ingredientes" (orphan recipes with no lines)**
- No filter to find recipes that have been gutted (all lines deleted)
- Should: add quick filter "Sin ingredientes"

**❌ MISSING — "Recetas sin producto" (orphan recipes not linked to any product)**
- No quick filter to find recipes that exist but have no linked product
- Should: add "Sin producto" filter

### 3.2 Visual Display

**❌ MISSING — Photo thumbnails in the table**
- Recipe photo icon is a button that opens a modal; no thumbnail in the table row itself
- Should: show 40×40px thumbnail in the Foto column (like product images in ventas)

**❌ MISSING — Dietary tag badges render but not as clickable filters**
- Clicking a tag on the recipe row should filter to that tag
- Currently: tags are display-only; clicking does nothing
- Impact: users must use the filter panel instead of clicking directly

### 3.3 Bulk & Export

**❌ MISSING — Bulk delete recipes**
- No bulk selection and delete on recetas list
- Impact: cleaning up test/duplicate recipes is one-by-one

**❌ MISSING — CSV export**
- No `/recetas/export.csv`
- Should: export recipe name, family, difficulty, yield_qty, yield_unit, prep_minutes, cook_minutes, line_count, batch_cost_gs, unit_cost_gs, tags

**❌ MISSING — PDF recipe card / technical sheet**
- Professional kitchens need a printed recipe card (name, ingredients, quantities, procedure notes, cost)
- Should: generate PDF with all recipe data formatted as a kitchen technical sheet

---

## PART 4 — RECETA DETAIL PAGE (`/recetas/{id}`)

### 4.1 Information Architecture

**❌ MISSING — Ingredient lines table is not in the detail page**
- The detail page (`receta_detalle.html`) shows the aside (cost breakdown, used-by products, notes) but the actual ingredient lines are NOT rendered in the main column — the user must click Edit to see them
- Should: show ingredient lines table in the detail page (read-only), with quantities, units, and per-line cost

**❌ MISSING — Recipe procedure / method steps**
- No field for recipe method, steps, or procedure
- The `notes` field is free-text and could contain procedure but is labeled "Notas" and shown separately
- Should: add a structured "Pasos / Procedimiento" section with numbered steps

**❌ MISSING — Serving / portioning instructions**
- No field for how to plate, serve, or portion the final product
- Impact: staff need these instructions; currently they exist only in the staff's head

**❌ MISSING — Storage instructions / shelf life**
- No "conservar a X°C por Y días" field
- Impact: food safety compliance and staff training

**❌ MISSING — Allergen information prominently displayed**
- `allergens` field exists and is derived/cached; should show as prominent warning card
- Should: show allergen alert banner at top of detail page: "Contiene: gluten, lácteos, huevos"

**❌ MISSING — Sub-recipe expansion view**
- When a recipe contains sub-recipes, the detail page should expand and show those sub-recipe lines inline
- Currently: sub-recipe lines show only the sub-recipe name, not its ingredient breakdown
- Impact: cost calculation is opaque for recipes with sub-recipes

**❌ MISSING — Cost breakdown should be live, not estimated**
- The "Desglose estimado" (70% ingredients / 20% labor / 10% overhead) is hardcoded percentages in the template, not real values
- Should: pull actual labor cost from `direct_labor_minutes` × labor rate (from ComplianceInfo), and actual overhead if configured

**❌ MISSING — Theoretical yield vs actual yield tracking**
- `yield_qty` is the target; no "real yield" tracking
- Impact: can't identify when production is running over or under theoretical yield

**❌ MISSING — Production history / how many times this recipe was made**
- No count of production completions or history
- Should: show "Producida N veces" with link to production log

**❌ MISSING — Linked products section shows names but not prices or status**
- `products_using` list shows product names as links; doesn't show price, availability, or whether the product is active
- Should: show a table with product name, price, availability, and quick edit link

**❌ MISSING — "Copy recipe" / duplicate action**
- No "duplicate this recipe" button
- Impact: creating variants requires full re-entry

### 4.2 Actions

**❌ MISSING — Print recipe card action**
- No print button; browser print shows the full page (sidebar, nav) instead of a clean recipe card
- Should: `window.print()` with a `@media print` stylesheet that shows only the recipe content

**❌ MISSING — "Ver costo histórico" link**
- No link to a cost history chart for this recipe over time
- Impact: can't track whether ingredient price changes have affected recipe cost

**❌ MISSING — "Marcar como temporada alta / baja"**
- No seasonal flag; recipes have `temporada` tag but no UI to quickly toggle it
- Should: quick-toggle button on detail page for seasonal status

**❌ MISSING — Share recipe (email/WhatsApp)**
- No share action
- Impact: staff need to send recipes to colleagues

---

## PART 5 — RECETA NEW/EDIT FORM (`/recetas/nueva`, `/recetas/{id}/editar`)

### 5.1 Form Fields

**✅ DONE — Name, family (combobox), yield_qty, yield_unit, prep_minutes, cook_minutes, difficulty, dietary_tags (checkbox buttons)**

**❌ MISSING — Notes field is present but unlabeled and limited**
- `notes` is in the form but labeled generically; should be "Notas / Procedimiento" and be a textarea (not single-line input)
- Impact: procedure/steps can't be written without a proper textarea

**❌ MISSING — Image/photo upload is on a separate page (`/recetas/{id}/set-photo`)**
- Recipe photo requires a separate navigation to `/recetas/{id}/set-photo`; not on the same edit form
- Should: integrate image upload directly into the edit form (drag-drop zone at top)

**❌ MISSING — "Also create product" checkbox is present but workflow is incomplete**
- The form has `also_create_product` checkbox but no inline product name/price fields
- After saving a recipe with this checked, user is redirected to the recipe detail, not to the product edit
- Impact: creates orphaned product stub with no price

**❌ MISSING — Direct labor minutes field is present in model but not in form**
- `direct_labor_minutes` not in the form; labor cost can't be entered
- Impact: prime cost calculation is incomplete (missing labor component)

**❌ MISSING — Yield percentage / loss correction not in form**
- `yield_percentage` not in form; operators can't enter actual yield (e.g., 0.85 for 15% moisture loss)
- Impact: cost calculations assume 100% yield, making them inaccurate for bread/pastry

**❌ MISSING — Allergen fields not editable; auto-derived only**
- `allergens` and `derived_dietary_tags` are cached/derived from ingredient lines but not editable
- For a recipe that contains a product with unknown ingredients (sub-recipe from outside the system), manual override is needed
- Should: allow manual allergen override with "Auto-calculated from ingredients" label

**❌ MISSING — No validation that recipe has at least one line before saving**
- Can save a recipe with zero ingredient lines
- Should: validation error if no lines exist

**❌ MISSING — No validation for circular sub-recipe references**
- Can create recipe A with sub-recipe B, and recipe B with sub-recipe A (cycle)
- Should: detect cycles before saving

**❌ MISSING — Recipe versioning / history**
- No audit trail of edits to a recipe
- Impact: can't see what changed between versions

### 5.2 Ingredient Line Table UX

**✅ DONE — Line kind selector (Insumo / Sub-receta)**

**❌ MISSING — Line unit selector should show the ingredient's actual unit**
- When selecting an ingredient, the line_unit defaults to empty; should default to the ingredient's purchase unit
- Impact: staff must manually select the unit each time

**❌ MISSING — Line cost is shown but not editable inline**
- Cost column shows calculated cost; cannot be manually overridden for price rounding
- Should: allow manual cost override per line (with indicator that it's a manual override vs calculated)

**❌ MISSING — Drag-to-reorder lines**
- No drag-and-drop to reorder ingredient lines
- Impact: recipe order is arbitrary; preferred by baker for reading order

**❌ MISSING — Copy line / duplicate line action**
- No "duplicate this line" action
- Impact: adding similar lines requires re-searching for each ingredient

**❌ MISSING — "Show sub-recipe ingredients" toggle**
- When a line is a sub-recipe, the table shows only the sub-recipe name
- Should: allow expanding to see the sub-recipe's ingredient lines inline (like a tree view)

**❌ MISSING — Line notes are a plain text field, not a proper textarea**
- `line_notes` is `<input type="text">` not a multi-line textarea
- Impact: long notes get cut off

**❌ MISSING — Real-time cost total as lines are edited (JS preview)**
- No live cost total as lines are added/changed
- Should: show running cost total at bottom of the ingredient table

### 5.3 Form UX

**❌ MISSING — Autosave to localStorage**
- No draft save; lost on browser close

**❌ MISSING — "Save and go to product" after creating recipe**
- After saving, no prompt to go create the linked product
- Should: "This recipe isn't linked to a product. Create one now?"

**❌ MISSING — Form help text for each field**
- No contextual help: what is "yield_qty" vs "yield_unit", what does "yield_percentage" mean
- Should: `?` tooltips explaining each field with examples

**❌ MISSING — Difficulty selector should be visual stars**
- Radio buttons 1–5; should be clickable star icons
- Impact: UX quality; current numeric radio is utilitarian

---

## PART 6 — INVENTARIO LIST PAGE (`/inventario`)

### 6.1 KPI Strip

**✅ DONE — Total ingredientes, stock crítico, valor de inventario, sin costo cargado**

**❌ MISSING — "Valor de inventario" is only at purchase price**
- Should also show "Valor a costo de venta" (what inventory would fetch if all sold as finished products)
- Impact: gives margin perspective, not just raw cost

**❌ MISSING — Inventory value trend (vs last week/month)**
- No delta shown: "▲ Gs. 2.3M vs semana pasada"
- Impact: can't see if stock is growing or shrinking at a glance

**❌ MISSING — Expiry alert KPI card**
- No KPI for ingredients nearing expiry
- Should: card showing "N ingredientes próximos a vencer" with link to expiry-filtered view

**❌ MISSING — "Proveedores" KPI**
- No count of active suppliers
- Should: show "N proveedores" in KPI strip

### 6.2 Table Display

**❌ MISSING — Ingredient image**
- No thumbnail for ingredients
- Impact: visual identification is harder

**❌ MISSING — Supplier column**
- No supplier shown in the table
- Should: add supplier name column, filterable

**❌ MISSING — Last purchase date column**
- No "última compra" in the table
- Impact: can't see if an ingredient hasn't been purchased recently

**❌ MISSING — Per-ingredient margin / markup indicator**
- No "markup %" column showing how much above cost the ingredient is sold at (for ingredients sold directly, not used in recipes)
- Should: for ingredients with a `sale_price_gs`, show margin %

**❌ MISSING — Stock value column per row**
- Each row should show `stock_qty × unit_cost_gs` as "valor en inventario" for that ingredient
- Impact: hard to prioritize which low-stock items to order based on value

### 6.3 Filtering & Alerts

**❌ MISSING — Expiry-based filters**
- No filter for "venciendo en 7 días", "vencido"
- Should: add `?expiry=` filter

**❌ MISSING — Stock alert thresholds per ingredient**
- Currently uses global `stock_low_threshold` from ComplianceInfo; should allow per-ingredient override
- Impact: different ingredients have different reorder rhythms

**❌ MISSING — "Order suggested" auto-calculation**
- Based on sales velocity and current stock, no auto-suggestion of order quantities
- Should: "Recommends ordering X kg of flour based on last 30 days sales"

**❌ MISSING — Sub-ingredient stock impact view**
- When an ingredient is used in sub-recipes, and sub-recipes are used in products, and products are sold — no view of the cascade
- Should: "连锁 impact view" showing how much stock is committed in the production chain

---

## PART 7 — CROSS-CUTTING FEATURES

### 7.1 Search

**❌ MISSING — Global search doesn't search recipes or products consistently**
- The header global search (`#global-search-input`) may not cover recipes and products
- Impact: inconsistent search UX

**❌ MISSING — Search suggestions / autocomplete on global search**
- No typeahead; must press enter
- Should: dropdown with top 5 results as user types

### 7.2 Reporting

**❌ MISSING — Product profitability report**
- `/reportes/top-productos` exists but is a simple table; needs: margin by product, trend over time, comparison to previous period
- Should: add revenue, cost, gross profit, margin % columns with period-over-period comparison

**❌ MISSING — Recipe cost evolution over time**
- No chart showing how recipe cost has changed as ingredient prices change
- Should: line chart of unit_cost_gs over time per recipe

**❌ MISSING — ABC analysis of products (A = top revenue, C = low)**
- No Pareto analysis of products by revenue contribution
- Should: categorize products into A/B/C based on revenue contribution

**❌ MISSING — Waste / merma report**
- Merma is tracked (`/merma`) but no consolidated report: total waste value, waste as % of production, top wasted ingredients
- Impact: can't identify problem areas

**❌ MISSING — What-if scenario for price changes**
- No simulator: "if I raise all prices by 10%, what happens to margin?"
- Should: a price change simulator showing impact on each affected product

### 7.3 Data Integrity

**❌ MISSING — Product-recipe consistency checker**
- No scheduled check: products linked to recipes that have changed (ingredient costs changed, recipe was deleted)
- Should: background job marking products as "needs cost review" when their recipe changes

**❌ MISSING — Orphan ingredient detection**
- No view of ingredients that exist but are not used in any recipe line or as packaging
- Should: "Ingredientes huérfanos" report

**❌ MISSING — Duplicate product / recipe name detection**
- `name` is `unique=True` on both models so duplicates can't be created at DB level, but similar names (case differences, whitespace) could exist
- Should: fuzzy duplicate detector

### 7.4 Permissions & Multi-User

**❌ MISSING — Role-based access control**
- No user roles: admin vs staff vs viewer
- Impact: can't restrict who can edit recipes vs just view

**❌ MISSING — Activity log / audit trail**
- No record of who changed what and when
- Impact: no accountability for data changes

**❌ MISSING — Per-user recipe "favorites" or "my recipes"**
- No way to mark recipes as favorites
- Should: starred recipes per user

### 7.5 Notifications & Alerts

**❌ MISSING — Low stock notification**
- Alerts exist as KPI cards; no push/email notification when stock drops below threshold
- Should: notify when ingredient goes below its reorder point

**❌ MISSING — New product/recipe created notification**
- No notification when staff creates a new product or recipe
- Impact: owner can't track what's being added without checking daily

### 7.6 Imports & Exports

**❌ MISSING — Full data export (all entities)**
- No comprehensive backup export (products, recipes, ingredients, customers, sales)
- Should: ZIP with CSV files for all tables + images

**❌ MISSING — Recipe import from external formats**
- No import from generic recipe formats (RecipeML, Paprika, Mastercook)
- Impact: can't migrate from other systems

---

## PRIORITIZATION SUMMARY

### P0 — Production blockers (data integrity, correctness)
1. Product cost history / IngredientPriceEvent → no visible history
2. Circular sub-recipe detection missing in recipe form
3. Save-empty-recipe validation missing
4. Recipe link in productos table not clickable (data is there but link missing)
5. Pagination links missing active filter params on productos AND recetas
6. Allergen display not prominent on receta detail

### P1 — Core workflow improvements (high user impact)
1. Bulk edit products (price %, availability, category)
2. CSV import for products
3. Direct labor minutes in recipe form (completes prime cost calculation)
4. Yield percentage in recipe form (corrects cost for moisture loss)
5. Sub-recipe expansion view on recipe detail
6. Tag filter on productos list
7. Category filter on productos list
8. Recipe photo on the edit form (not separate page)
9. Inline validation errors on product/recipe forms
10. Unsaved changes warning on edit forms

### P2 — Operational completeness (medium impact)
1. "Save and create another" workflow on products and recipes
2. Wholesale / mayorista price on products
3. RSPA fields on product form
4. IVA rate selector on product form
5. CSV export for recetas
6. Stock value per row on inventario
7. Supplier column on inventario
8. Expiry filter on inventario
9. Recipe cost evolution chart
10. Waste/merma consolidated report

### P3 — Polish and UX quality (lower impact, high satisfaction)
1. Difficulty rendered as stars
2. Prep/cook time columns on recetas list
3. Product image thumbnails in productos table
4. Active filter chips below toolbar
5. Live cost preview in recipe form
6. Drag-to-reorder ingredient lines
7. "Copy recipe" action
8. Barcode rendering below SKU
9. PDF recipe card / technical sheet
10. Print-optimized recipe detail page
