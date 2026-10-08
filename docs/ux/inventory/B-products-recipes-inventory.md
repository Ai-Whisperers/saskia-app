# Sazon/Saskia Products + Recipes + Inventory + Mermas + Pricing Content Audit

**Generated:** 2026-10-07  
**Scope:** Products, Recipes, Inventory, Mermas, Pricing sections  
**Total pages audited:** 0

---


## Products (3 pages)

### productos.html

#### 1. Identity
- **URL/route**: `/productos`
- **Page title**: `Productos y precios`
- **Section**: Products
- **User persona**: Bakery operator/manager

#### 2. Structure
- **Main heading**: `Productos y precios`
- **Sub-headings**: None
- **Tab labels**: None
- **Breadcrumb**: None

#### 3. All visible user-facing text

**Page-level messages:**
- `{{ ui.flash_toast(request) }}` - Flash notification area

**Button + link text:**
- `Nuevo producto` - Add new product button
- `Importar CSV` - Import CSV button (appears twice)
- `Exportar CSV` - Export CSV button
- `Filtrar` - Filter button
- `Limpiar todo` - Clear all filters button
- `Edición masiva` - Bulk edit button
- `Eliminar seleccionados` - Delete selected button
- `Columnas` - Columns button
- `Producto sin ventas (muerto)` - Dead product label (hidden)
- `×` - Remove filter chip icon
- `Cancelar` - Cancel button in bulk edit modal
- `Aplicar` - Apply button in bulk edit modal

**Form labels + placeholders + help text:**
- `Buscar producto…` - Search placeholder
- `Tag` - Tag filter label
- `Categoría` - Category filter label
- `Margen` - Margin filter label
- `Margen negativo` - Negative margin filter option
- `Bajo (< 30%)` - Low margin filter option
- `Medio (30–70%)` - Medium margin filter option
- `Alto (> 70%)` - High margin filter option
- `Sin datos de margen` - No margin data filter option
- `Todos` - All filter option
- `Disponibilidad` - Availability filter label
- `Disponibles` - Available filter option
- `No disponibles` - Not available filter option
- `Receta` - Recipe filter label
- `Con receta` - With recipe filter option
- `Sin receta` - Without recipe filter option

**Table column headers:**
- `Nombre` - Name column
- `SKU` - SKU column
- `Porción` - Portion column
- `Precio venta` - Sale price column
- `Mayorista` - Wholesale price column
- `Receta` - Recipe column
- `Costo` - Cost column
- `Margen` - Margin column
- `Margen %` - Margin percentage column
- `Prime Cost` - Prime cost column
- `% Costo` - Cost percentage column
- `Costo act.` - Current cost column
- `Disp.` - Availability column
- `Producido` - Produced column

**Tooltip / title attribute text:**
- `Copiar SKU` - Copy SKU button title
- `Hace cuánto cambió el precio de algún ingrediente de la receta` - Cost freshness tooltip
- `Total horneado histórico (cierres de turno en /produccion). Últimos 30 días entre paréntesis.` - Produced tooltip
- `Vendés por debajo del costo` - Negative margin tooltip
- `Margen bajo: menos del 40%` - Low margin tooltip
- `Sin precios de ingredientes cargados` - No ingredient prices tooltip
- `Costo base con más de 90 días — revisá precios` - Cost stale >90d tooltip
- `Costo base de hace {{ days_ago }} días` - Cost stale tooltip
- `Costo actualizado hace {{ days_ago }} día(s)` - Cost updated tooltip
- `Sin cierres de turno registrados` - No production records tooltip
- `Última producción registrada` - Last production date tooltip
- `Quitar de favoritos` - Remove from favorites button title
- `Marcar como favorito` - Mark as favorite button title
- `Seleccionar {{ fmt.entity_name(p) }}` - Select product checkbox label

**Status badges + tags:**
- `Sin ventas` - Dead product badge
- `Sí` - Available status badge
- `No` - Not available status badge
- `sin SKU` - No SKU text (italic)
- `sin receta` - No recipe text (italic)
- `falta precio` - Missing price text (italic)
- `—` - Empty/dash text
- `falta datos` - Missing data text (italic)

**Error / success / warning messages:**
- Bulk edit error messages:
  - `Elegí una acción.` - Choose an action error
  - `Ingresá un porcentaje válido.` - Enter valid percentage error
  - Error messages from server responses
- Bulk delete confirmation:
  - `¿Eliminar X producto(s)?` - Delete confirmation title
  - `Esta acción no se puede deshacer.` - Delete confirmation body
  - `Sí, eliminar` - Confirm delete button

**Helper copy:**
- `Mostrando X-Y de Z productos · búsqueda "q"` - Result count text
- `✓` - Checkmark icon (CSS class)
- `★` - Star icon (CSS class)
- `☆` - Empty star icon (CSS class)

#### 4. Displayed data

**Table columns:**

| Column | Semantics | Example | Sort/Visual |
|--------|-----------|---------|-------------|
| Nombre | Product name | `Chipa Guazu` | Sortable |
| SKU | Stock keeping unit | `CHP-123` | Static |
| Porción | Portion size/unit | `1 unidad` | Static |
| Precio venta | Sale price in Gs. | `8.500` | Sortable, currency |
| Mayorista | Wholesale price | `6.000` | Static, optional |
| Receta | Linked recipe name | `Masa para chipa` | Static, link |
| Costo | Unit cost in Gs. | `2.500` | Sortable, currency |
| Margen | Absolute margin | `6.000` | Sortable, currency |
| Margen % | Margin percentage | `70.6%` | Sortable, percentage |
| Prime Cost | Prime cost (material+direct) | `4.000` | Static, currency |
| % Costo | Prime cost percentage | `47.1%` | Static, percentage |
| Costo act. | Cost freshness indicator | `15d` | Visual indicators |
| Disp. | Availability | `Sí`/`No` | Badge |
| Producido | Total produced quantity | `144 (36)` | Number, 30d in parentheses |

**Visual indicators:**
- `Sin ventas` badge for dead products
- Red badge for negative margin
- Yellow badge for low margin (<40%)
- Color-coded cost freshness (warn/stale/ok)
- Prime cost percentage color coding (green/warn/red)

#### 5. Tooltips / hover text

| Element | Tooltip text |
|---------|-------------|
| SKU copy button | `Copiar SKU` |
| Cost freshness column | `Hace cuánto cambió el precio de algún ingrediente de la receta` |
| Produced column | `Total horneado histórico (cierres de turno en /produccion). Últimos 30 días entre paréntesis.` |
| Negative margin percentage | `Vendés por debajo del costo` |
| Low margin badge | `Margen bajo: menos del 40%` |
| No cost data | `Sin precios de ingredientes cargados` |
| Cost >90d old | `Costo base con más de 90 días — revisá precios` |
| Cost 30-90d old | `Costo base de hace {{ days_ago }} días` |
| Cost recent | `Costo actualizado hace {{ days_ago }} día(s)` |
| No production | `Sin cierres de turno registrados` |
| Last production date | `Última producción registrada` |
| Favorite toggle | `Quitar de favoritos` / `Marcar como favorito` |
| Product checkbox | `Seleccionar {{ product name }}` |

#### 6. UX/copy audit flags

- **Broken Spanish or grammar issues**: None observed
- **Untranslated i18n keys**: All text appears in Spanish
- **Missing tooltips**: All interactive elements have tooltips
- **Inconsistent terminology**: `Margen` vs `Margen %` - could be clearer
- **Jargon / acronym without explanation**: RSPA mentioned but not explained in this template
- **Empty states**: Good empty state with guidance
- **Buttons labeled only with icons**: All buttons have visible text + icons

---

### producto_detalle.html

#### 1. Identity
- **URL/route**: `/productos/{id}`
- **Page title**: `Detalle del Producto - {{ product.name }}`
- **Section**: Products
- **User persona**: Bakery operator/manager

#### 2. Structure
- **Main heading**: Product name
- **Sub-headings**: "Uso en recetas", "Ventas últimos 30 días", "Ventas recientes"
- **Tab labels**: None
- **Breadcrumb**: None

#### 3. All visible user-facing text

**Page-level messages:**
- None

**Button + link text:**
- `Editar` - Edit product button
- `Favorito` / `Quitar de favoritos` - Favorite toggle button
- `Ver receta` - View recipe link

**Form labels + placeholders + help text:**
- None

**Table column headers:**
- `Fecha` - Date column (sales table)
- `Cliente` - Customer column (sales table)
- `Cantidad` - Quantity column (sales table)
- `Total (Gs.)` - Total amount column (sales table)

**Tooltip / title attribute text:**
- None

**Status badges + tags:**
- `{{ product.category }}` - Category badge
- `Sin stock` - Out of stock badge

**Error / success / warning messages:**
- `Cliente no identificado` - Unidentified customer text

**Helper copy:**
- `Stock actual` - Current stock label
- `und` - Units abbreviation
- `Costo actual (Gs.)` - Current cost label
- `Precio actual (Gs.)` - Current price label
- `Margen %` - Margin percentage label
- `Unidades vendidas` - Units sold label
- `Ingresos (Gs.)` - Revenue label

#### 4. Displayed data

**Metrics cards:**
- `Stock actual` - Current inventory quantity
- `Costo actual (Gs.)` - Current unit cost
- `Precio actual (Gs.)` - Current sale price
- `Margen %` - Current margin percentage

**Tables:**
- Sales table with date, customer, quantity, and total columns
- Recipe usage list with recipe names and view links

**Visual indicators:**
- Color-coded margin percentage (danger/warn based on values)

#### 5. Tooltips / hover text
- None observed

#### 6. UX/copy audit flags

- **Broken Spanish or grammar issues**: None observed
- **Untranslated i18n keys**: All text appears in Spanish
- **Missing tooltips**: Could use tooltips for metric definitions
- **Inconsistent terminology**: Good consistency with main products page
- **Jargon / acronym without explanation**: None
- **Empty states**: Good empty states for recipes and sales
- **Buttons labeled only with icons**: All buttons have visible text

---

### producto_form.html

#### 1. Identity
- **URL/route**: `/productos/nuevo` or `/productos/{id}/editar`
- **Page title**: `Productos — {{ action }}`
- **Section**: Products
- **User persona**: Bakery operator/manager

#### 2. Structure
- **Main heading**: `{{ action }} producto`
- **Sub-headings**: None
- **Breadcrumb**: `Productos` > `{{ action }}`
- **Sections**: Basic info, image upload, RSPA section, tablet menu section

#### 3. All visible user-facing text

**Page-level messages:**
- `Pre-llenado desde receta — revisá que el nombre no exista ya en Productos.` - Recipe pre-fill warning

**Button + link text:**
- `Guardá` - Save button
- `Cancelar` - Cancel button
- `Subir imagen` - Upload image button
- `Quitar imagen` - Remove image button
- `Regenerar SKU` - Regenerate SKU button

**Form labels + placeholders + help text:**
- `Nombre` - Name label
- `Ej: Muffin de chocolate` - Name placeholder
- `SKU / Código de barras` - SKU label
- `Se genera automáticamente al escribir el nombre` - SKU help text
- `Formato: <code>PREFIX-NNN</code> basado en el nombre. Editable.` - SKU format help
- `Categoría` - Category label
- `Elegí una de las categorías predefinidas o escribí una nueva.` - Category help text
- `Etiquetas` - Tags label
- `Tocá una etiqueta para activarla. Útil para búsquedas y filtros rápidos.` - Tags help text
- `Etiqueta de porción` - Portion label
- `Se rellena automáticamente si elegís una receta.` - Portion help text
- `Precio de venta (Gs.)` - Sale price label
- `8000` - Price placeholder
- `Precio mayorista (Gs.)` - Wholesale price label
- `Mayorista (opcional)` - Wholesale price placeholder
- `Precio B2B para ventas por cantidad. Dejá en blanco si no aplica.` - Wholesale help text
- `IVA%` - IVA label
- `Receta` - Recipe label
- `— Sin receta —` - No recipe placeholder
- `Sin receta: las ventas se registran pero no bajan stock ni calculan margen. Al elegir una receta, se sugieren precio/porción/tags.` - Recipe help text
- `Imagen del producto` - Product image label
- `Sin imagen` - No image text
- `Disponible para venta` - Availability label
- `Desactivá esto para ocultar el producto del POS sin eliminarlo.` - Availability help text
- `Notas` - Notes label
- `Certificación / RSPA` - RSPA section title
- `Requiere RSPA` - RSPA requirement label
- `Nº Registro RSPA` - RSPA number label
- `Vencimiento RSPA` - RSPA expiry label
- `Menú tablet (C2)` - Tablet menu section title
- `Visible en el menú público (tablet)` - Tablet visibility label
- `Slug URL <small style="color:var(--color-text-muted);">(opcional, se genera del nombre)</small>` - URL slug label
- `ej: chipa-guazu` - Slug placeholder

**Tooltip / title attribute text:**
- `Regenerar SKU` - Regenerate SKU button title

**Status badges + tags:**
- Category pills from tag system
- Dietary tag pills from tag system

**Error / success / warning messages:**
- Field validation errors via `field-error` elements
- Flash messages from validation

**Helper copy:**
- `Sugerido: X Gs. (costo Y × 3). Editable.` - Price suggestion text
- `URL del menú: <code>/m/<span id="tablet-slug-preview">{{ product.tablet_slug or '' }}</span></code>` - URL preview

#### 4. Displayed data

**Form fields:**
- Product name (required)
- SKU (auto-generated, editable)
- Category (with picker interface)
- Tags (with picker interface)
- Portion label (auto-populated from recipe)
- Sale price (with auto-suggestion from recipe cost)
- Wholesale price (optional B2B field)
- IVA rate (10%/5%/0%/exempt options)
- Recipe selection (with search API)
- Image upload (file or URL)
- Availability toggle
- Notes textarea
- RSPA fields (conditional)
- Tablet menu visibility and slug

**Data displays:**
- Auto-generated SKU preview
- Tablet URL preview
- Price suggestions based on recipe cost

#### 5. Tooltips / hover text

| Element | Tooltip text |
|---------|-------------|
| SKU regenerate button | `Regenerar SKU` |

#### 6. UX/copy audit flags

- **Broken Spanish or grammar issues**: None observed
- **Untranslated i18n keys**: All text appears in Spanish
- **Missing tooltips**: Could use tooltips for complex fields like RSPA
- **Inconsistent terminology**: Good consistency with other templates
- **Jargon / acronym without explanation**: RSPA mentioned without explanation (should have tooltip)
- **Empty states**: Good empty states for image upload
- **Buttons labeled only with icons**: All buttons have visible text + icons

---

### productos_importar.html

#### 1. Identity
- **URL/route**: `/productos/importar`
- **Page title**: `Importar productos desde CSV`
- **Section**: Products
- **User persona**: Bakery operator/manager

#### 2. Structure
- **Main heading**: `Importar productos`
- **Sub-headings**: "Formato del CSV", "Subir archivo"
- **Breadcrumb**: `Productos` > `Importar`
- **Sections**: Instructions, upload form, results

#### 3. All visible user-facing text

**Page-level messages:**
- `⚠️ {{ error }}` - Error display

**Button + link text:**
- `Importar` - Import button
- `Cancelar` - Cancel button
- `Ver productos` - View products button
- `Importar otro archivo` - Import another file button

**Form labels + placeholders + help text:**
- `Formato del CSV` - CSV format section title
- `El archivo debe tener las siguientes columnas (encabezados exactos):` - CSV instructions
- `Columna` - Column table header
- `Descripción` - Description table header
- `Ejemplo` - Example table header
- `name` - Column name
- `Nombre del producto (único, sensible a mayúsculas)` - Description
- `Tostadas de queso` - Example
- `sku` - Column name
- `Código SKU (opcional)` - Description
- `TRS-104` - Example
- `category` - Column name
- `Categoría (opcional)` - Description
- `Panadería` - Example
- `portion_label` - Column name
- `Etiqueta de porción (opcional)` - Description
- `1 unidad` - Example
- `sale_price_gs` - Column name
- `Precio de venta en guaraníes (opcional, 0 si se omite)` - Description
- `8500` - Example
- `yield_percentage` - Column name
- `Porcentaje de rendimiento (ignorado en importación de productos)` - Description
- `95` - Example
- `tags` - Column name
- `Etiquetas separadas por coma (opcional)` - Description
- `popular,navidad` - Example
- `<strong>Nota:</strong> Si ya existe un producto con el mismo nombre, se actualizan los campos presentes en el CSV. Los campos vacíos en el CSV no sobreescriben valores existentes.` - Import note
- `Subir archivo` - Upload section title
- `Archivo CSV` - File label
- `Archivos .csv generados por Excel, Google Sheets o exportación de otro sistema.` - File help text

**Table column headers:**
- `Fila` - Row header (error table)
- `Error` - Error header (error table)

**Tooltip / title attribute text:**
- None

**Status badges + tags:**
- `✅` - Success icon
- `🔄` - Update icon
- `❌` - Error icon

**Error / success / warning messages:**
- `⚠️ {{ error }}` - Error message
- Import success results with created/updated/error counts

**Helper copy:**
- `Resultados de la importación` - Import results title
- `Ver errores ({{ errors | length }})` - Show errors link

#### 4. Displayed data

**Table:**
- CSV format specification table with columns, descriptions, and examples

**Form:**
- File upload for CSV files
- Results display with success/error counts

**Visual indicators:**
- Green success background for results
- Error table for failed imports

#### 5. Tooltips / hover text
- None observed

#### 6. UX/copy audit flags

- **Broken Spanish or grammar issues**: None observed
- **Untranslated i18n keys**: All text appears in Spanish
- **Missing tooltips**: None needed for this page
- **Inconsistent terminology**: Good consistency with product templates
- **Jargon / acronym without explanation**: None
- **Empty states**: Good empty state for file upload
- **Buttons labeled only with icons**: All buttons have visible text

