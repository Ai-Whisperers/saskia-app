# Sazón — Designer Page Report

**Generated:** 2026-09-27 (auto-generated from repo at HEAD `/opt/data/profiles/ivan/scratch/sazon-app-work/.git/HEAD`)
**Pages covered:** 66 routes (all 84 from `scripts/shoot_all_pages.py`, with 66 page routes + 18 export endpoints)
**Designer audience:** UI/UX, QA, and frontend reviewers

---

## How to read this report

Each section is **one page (one URL)** and gives you everything a designer needs:

- **Route** — the URL, HTTP method, and the Python handler that serves it
- **Template** — the Jinja2 file rendered, with line count and which `_components/` it pulls in
- **UI primitives** — class signals (`metric-card`, `pos-layout`, `form-grid-2col`, …), ui-combo count, charts, modals, empty-state, aria-current, currency refs
- **Context keys** — every variable passed to the template by the handler (`{{ ventas_gs }}`, `{{ ranking }}`, etc.)
- **Data sources** — which SQLAlchemy models the route queries (Ingredient, Sale, Pedido, …)
- **Forms** — `<form action=...>` POST endpoints reachable from this page
- **Browser contract** — the `tests/browser/pages.py` page object class that owns this route's selectors (restyles change only that file)
- **Design constraints** — anything specific to this page from `AGENTS.md`, the sazon-rms-development skill, or recent commits
- **Screenshot** — `docs/user-guide/screenshots/all-pages/<name>.png` (1280×900, regenerated today)

### Global constraints (apply to every page)

- **No native `<select>`** — every dropdown must use `<ui-combo>` or `.ui-combo` markup
- **Paraguayan Spanish, voseo** — "Guardá", "Registrá", "Cancelá" (never "Salvar" Argentine or "Guardar" Mexican)
- **Money = integer Guaraníes** — `Gs. 12.000` formatted via `format_gs()` macro / `gs`/`gs_full` Jinja helpers; never float, never decimals
- **Times in `ASUNCION_TZ`** — DB returns naive datetimes; the template globals `now_str` / `greeting` handle display-side TZ
- **Active nav state** must emit BOTH `aria-current="page"` AND `.active` class
- **Empty states are first-class** — every list/board/KPI has a `Sin datos` / `No hay …` empty state with an action CTA
- **Form discipline** — inputs sized to data (`max-width: 180px` for numbers, `220px` for dates, `260px` for combos, `420px` for names); no full-width inputs for small data
- **POS / fast-action screens** must use split-pane (form left / quick-actions right sticky)
- **Money paths** — never `int()` cast on Decimal in business logic; only at persistence sites

---

## Table of contents

### Operaciones (POS + inventario + recetas)
- [`/dashboard`](#dashboard) — Dashboard
- [`/`](#root) — Dashboard
- [`/ventas`](#ventas) — Sales
- [`/ventas/historial`](#ventas-historial) — Sales history
- [`/ventas/buscar`](#ventas-buscar) — Sale lookup by sku
- [`/pedidos`](#pedidos) — Pedidos
- [`/pedidos/board`](#pedidos-board) — Pedidos board
- [`/pedidos/nuevo`](#pedidos-nuevo) — Pedidos new
- [`/inventario`](#inventario) — Inventory
- [`/inventario/nuevo`](#inventario-nuevo) — Inventory
- [`/recetas`](#recetas) — Recipes
- [`/recetas/nueva`](#recetas-nueva) — Recipe

### Catálogo (productos + clientes + proveedores)
- [`/productos`](#productos) — Products
- [`/productos/nuevo`](#productos-nuevo) — Product
- [`/clientes`](#clientes) — Clientes
- [`/suppliers`](#suppliers) — Suppliers
- [`/suppliers/nuevo`](#suppliers-nuevo) — Supplier
- [`/wishlist`](#wishlist) — Wishlist

### Producción
- [`/produccion`](#produccion) — Produccion worksheet
- [`/produccion-planner`](#produccion-planner) — Planner
- [`/eod`](#eod) — Eod
- [`/merma`](#merma) — Merma
- [`/reorder`](#reorder) — Reorder
- [`/shopping-list`](#shopping-list) — Shopping list

### Reportes
- [`/analisis`](#analisis) — Analisis
- [`/reportes`](#reportes) — Reportes
- [`/reportes/iva`](#reportes-iva) — Reportes iva
- [`/reportes/libro-ventas`](#reportes-libro-ventas) — Reportes libro ventas
- [`/reportes/diario`](#reportes-diario) — Reportes diario
- [`/reportes/comparacion`](#reportes-comparacion) — Reportes comparacion
- [`/reportes/top-productos`](#reportes-top-productos) — Reportes top productos
- [`/reportes/retencion`](#reportes-retencion) — Reportes retencion
- [`/reportes/valor-pedido`](#reportes-valor-pedido) — Reportes valor pedido
- [`/reportes/ventas-hora`](#reportes-ventas-hora) — Reportes ventas hora
- [`/reportes/metodos-pago`](#reportes-metodos-pago) — Reportes metodos pago
- [`/reportes/precios`](#reportes-precios) — Reportes precios
- [`/reportes/cierre-mensual`](#reportes-cierre-mensual) — Reportes cierre mensual
- [`/reportes/food-cost-variance`](#reportes-food-cost-variance) — Food cost variance
- [`/reportes/demand`](#reportes-demand) — Demand
- [`/reportes/freshness`](#reportes-freshness) — Freshness
- [`/reportes/stock-intel`](#reportes-stock-intel) — Stock intel
- [`/reportes/afinidades`](#reportes-afinidades) — Afinidades
- [`/reportes/margenes`](#reportes-margenes) — Margenes

### Pricing + Mercado
- [`/pricing`](#pricing) — Pricing
- [`/vs-mercado`](#vs-mercado) — Benchmarks
- [`/bank`](#bank) — Bank

### Operaciones internas
- [`/auditoria`](#auditoria) — Auditoria
- [`/ops/status`](#ops-status) — Ops status
- [`/settings`](#settings) — Settings page
- [`/settings/catalog`](#settings-catalog) — Settings catalog page
- [`/users`](#users) — Users
- [`/guia`](#guia) — Guia
- [`/riesgos`](#riesgos) — Risk
- [`/delivery-zones`](#delivery-zones) — Delivery zones
- [`/excel`](#excel) — Excel home
- [`/login`](#login) — Login

---

### `/dashboard`

**Dashboard** — GET → `herebus.dashboard_index` → `dashboard.html`

**Template:** `5,830 chars / 111 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `page-header`, `warning`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **4**

**Context keys (25):** `revenue_gs`, `portions`, `unique_customers`, `repeat_customers`, `repeat_pct`, `food_cost_pct`, `gross_margin_pct`, `waste_gs`, `waste_pct`, `recipe_count`, `recipes_cooked`, `avg_order_gs`, `by_channel`, `top_recipe_name`, `top_recipe`, `top_recipe_revenue_gs`, `top_recipe`, `month_label`, `tx_count_this_month`, `sl_open_count`, `sl_total_gs`, `wishlist_count`, `wishlist_total_gs`, `risk_count`, `risk_severity_gs`

**Data sources (SQLAlchemy models):** `Ingredient`, `Recipe`, `RecipePricing`, `Sale`, `WasteLog`

**Browser-test contract:** `DashboardPage` in `tests/browser/pages.py` — restyle must update selectors there only

**Screenshot:** `docs/user-guide/screenshots/all-pages/dashboard.png`

---

### `/`

**Dashboard** — GET → `dashboard.dashboard` → `inicio.html`

**Template:** `14,601 chars / 346 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `metric-card`, `empty-state`, `danger`, `chip`, `pill`, `metric`, `success`
- Empty-state: ✓ · Chart: ✓ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **8**

**Context keys (64):** `period`, `start_date_val`, `end_date_val`, `ventas_gs`, `cogs_gs`, `margen_gs`, `margen_pct_fmt`, `delta_ventas`, `delta_cogs`, `delta_margen`, `prior_label`, `ranking`, `stock_low`, `name`, `stock_qty`, `min_stock_qty`, `unit`, `recipes_no_cost`, `sales_no_recipe`, `dow_buckets`, `turnover`, `top_margin`, `concentration`, `erosion_alerts`, `complexity`, `compliance_alerts`, `insights`, `chart_hourly`, `chart_30day`, `chart_payment_methods` … (+34 more)

**Data sources (SQLAlchemy models):** `Ingredient`, `Pedido`, `Recipe`, `RiskItem`, `Sale`, `ShoppingListItem`, `WasteLog`, `WishlistItem`

**Browser-test contract:** `DashboardPage` in `tests/browser/pages.py` — restyle must update selectors there only

**Screenshot:** `docs/user-guide/screenshots/all-pages/inicio.png`

---

### `/ventas`

**Sales** — GET → `sales.sales_list` → `ventas.html`

**Template:** `10,539 chars / 245 lines` — extends `base.html`
- Includes: `_components/_customer_picker.html`
- Forms POST to: `/ventas/nueva`
- the operator-combo count: **4**
- Class signals: `pos-layout`, `danger`, `pos-quick`, `form-row`, `pos-form`, `success`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **1**

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** `PosPage` in `tests/browser/pages.py` — restyle must update selectors there only

**Screenshot:** `docs/user-guide/screenshots/all-pages/ventas.png`

---

### `/ventas/historial`

**Sales history** — GET → `sales.sales_history` → `ventas_historial.html`

**Template:** `7,789 chars / 185 lines` — extends `base.html`
- Forms POST to: `/ventas/{{ s.id }}/anular`
- the operator-combo count: **3**
- Class signals: `info`, `empty-state`, `danger`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **4**

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/ventas-historial.png`

---

### `/ventas/buscar`

**Sale lookup by sku** — GET → `sales.sale_lookup_by_sku` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/ventas-buscar.png`

---

### `/ventas/`

_(Route not parsed — handler not found in any router file)_

### `/pedidos`

**Pedidos** — GET → `pedidos.pedidos_list` → `pedidos.html`

**Template:** `12,338 chars / 296 lines` — extends `base.html`
- Forms POST to: `/pedidos`, `/pedidos/bulk-fulfill`, `/pedidos/bulk-cancel`
- the operator-combo count: **0**
- Class signals: `info`, `empty-state`, `danger`, `success`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✓
- Currency refs (Gs./gs_full): **2**

**Context keys (12):** `groups`, `today_iso`, `today_human`, `status_filter`, `search`, `group_labels`, `hoy_manana`, `esta_semana`, `pendientes_viejos`, `pagination`, `page_start`, `page_end`

**Data sources (SQLAlchemy models):** `Pedido`

**Browser-test contract:** `PedidosPage` in `tests/browser/pages.py` — restyle must update selectors there only

**Screenshot:** `docs/user-guide/screenshots/all-pages/pedidos.png`

---

### `/pedidos/board`

**Pedidos board** — GET → `pedidos.pedidos_board` → `pedido_board.html`

**Template:** `61,134 chars / 209 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: _(none)_
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (8):** `pedidos_hoy`, `pedidos_manana`, `pedidos_semana`, `kanban_pending`, `kanban_confirmed`, `kanban_ready`, `today`, `now`

**Data sources (SQLAlchemy models):** `Pedido`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/pedidos-board.png`

---

### `/pedidos/nuevo`

**Pedidos new** — GET → `pedidos.pedidos_new_form` → `pedidos_nuevo.html`

**Template:** `8,930 chars / 249 lines` — extends `base.html`
- Forms POST to: `/pedidos/nuevo`
- the operator-combo count: **6**
- Class signals: `combobox`, `danger`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **1**

**Context keys (7):** `products`, `customers`, `channels`, `payment_methods`, `delivery_zones`, `today_iso`, `default_promised_date`

**Data sources (SQLAlchemy models):** `Customer`, `DeliveryZone`, `Product`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/pedidos-nuevo.png`

---

### `/inventario`

**Inventory** — GET → `inventory.inventory_list` → `inventario.html`

**Template:** `16,211 chars / 286 lines` — extends `base.html`
- Includes: `_components/adjust_modal.html`
- the operator-combo count: **0**
- Class signals: `metric-card`, `info`, `empty-state`, `danger`, `pill`, `metric`, `success`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✓
- Currency refs (Gs./gs_full): **5**

**Context keys (26):** `ingredients`, `price_info`, `market_refs`, `sort`, `dir`, `page`, `total_pages`, `total`, `per_page`, `page_start`, `page_end`, `kpi_total`, `kpi_critical`, `kpi_value_gs`, `kpi_no_cost`, `estado`, `categorias`, `alergenos_sel`, `almacen`, `categories`, `storages`, `allergen_codes`, `total_filtered`, `duplicates`, `suspicious_prices`, `total_all`

**Data sources (SQLAlchemy models):** `Ingredient`, `IngredientPriceEvent`, `MarketPriceReference`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/inventario.png`

---

### `/inventario/nuevo`

**Inventory** — GET → `inventory.inventory_new` → `inventario_form.html`

**Template:** `8,701 chars / 161 lines` — extends `base.html`
- Forms POST to: `/inventario{{ `
- the operator-combo count: **4**
- Class signals: `form-grid-2col`, `chip`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **2**

**Context keys (4):** `mode`, `ingredient`, `action`, `units`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/inventario-nuevo.png`

---

### `/recetas`

**Recipes** — GET → `recipes.recipes_list` → `recetas.html`

**Template:** `10,310 chars / 229 lines` — extends `base.html`
- Forms POST to: `/recetas`
- the operator-combo count: **1**
- Class signals: `pill`, `info`, `empty-state`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✓ · aria-current: ✗
- Currency refs (Gs./gs_full): **2**

**Context keys (21):** `recipes`, `familias_sel`, `dif_sel`, `diet_sel`, `all_families`, `all_recipe_tags`, `total_all`, `ingredient_id`, `ing_id_ints`, `ingredient_ids`, `sort`, `dir`, `ingredients`, `total`, `pagination`, `total_count`, `page`, `page_size`, `total_pages`, `page_start`, `page_end`

**Data sources (SQLAlchemy models):** `Ingredient`, `Recipe`, `RecipeLine`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/recetas.png`

---

### `/recetas/nueva`

**Recipe** — GET → `recipes.recipe_new` → `receta_form.html`

**Template:** `46,035 chars / 1,200 lines` — extends `base.html`
- Forms POST to: `/recetas{{ `
- the operator-combo count: **12**
- Class signals: `danger`, `pill`, `form-row`, `metric`, `form-section`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **7**

**Context keys (9):** `mode`, `recipe`, `action`, `lines`, `units`, `ingredients`, `other_recipes`, `recipe_families`, `dietary_tags`

**Data sources (SQLAlchemy models):** `Ingredient`, `Recipe`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/recetas-nueva.png`

---

### `/productos`

**Products** — GET → `products.products_list` → `productos.html`

**Template:** `16,952 chars / 319 lines` — extends `base.html`
- Forms POST to: `/productos`
- the operator-combo count: **0**
- Class signals: `info`, `empty-state`, `danger`, `pill`, `success`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✓
- Currency refs (Gs./gs_full): **5**

**Context keys (13):** `products`, `has_recipe`, `margen_sel`, `disp_sel`, `total_all`, `sort`, `dir`, `page`, `total_pages`, `total`, `per_page`, `page_start`, `page_end`

**Data sources (SQLAlchemy models):** `Product`, `Sale`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/productos.png`

---

### `/productos/nuevo`

**Product** — GET → `products.product_new` → `producto_form.html`

**Template:** `15,440 chars / 424 lines` — extends `base.html`
- Forms POST to: `/productos{{ `
- the operator-combo count: **2**
- Class signals: `info`, `danger`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **2**

**Context keys (7):** `mode`, `product`, `action`, `recipes`, `product_categories`, `dietary_tags`, `pricing_markup`

**Data sources (SQLAlchemy models):** `Recipe`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/productos-nuevo.png`

---

### `/clientes`

**Clientes** — GET → `customers.clientes_list` → `clientes.html`

**Template:** `8,987 chars / 200 lines` — extends `base.html`
- Includes: `_components/_customer_picker.html`
- Forms POST to: `/clientes`
- the operator-combo count: **0**
- Class signals: `info`, `empty-state`, `danger`, `success`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **3**

**Context keys (10):** `customers`, `tier`, `tiers`, `sort`, `dir`, `page`, `total_pages`, `total`, `page_start`, `page_end`

**Data sources (SQLAlchemy models):** `Customer`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/clientes.png`

---

### `/suppliers`

**Suppliers** — GET → `suppliers.suppliers_list` → `suppliers.html`

**Template:** `2,554 chars / 80 lines` — extends `base.html`
- Forms POST to: `/suppliers/{{ s.id }}/eliminar`
- the operator-combo count: **0**
- Class signals: `info`, `empty-state`, `danger`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (4):** `suppliers`, `total`, `page_start`, `page_end`

**Data sources (SQLAlchemy models):** `Supplier`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/suppliers.png`

---

### `/suppliers/nuevo`

**Supplier** — GET → `suppliers.supplier_new` → `supplier_form.html`

**Template:** `1,986 chars / 40 lines` — extends `base.html`
- Forms POST to: `{{ `
- the operator-combo count: **0**
- Class signals: `form-row`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (2):** `mode`, `supplier`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/supplier-nuevo.png`

---

### `/wishlist`

**Wishlist** — GET → `herebus.wishlist_list` → `wishlist.html`

**Template:** `3,253 chars / 70 lines` — extends `base.html`
- Forms POST to: `/wishlist/{{ item.id }}/send-to-shopping-list`, `/wishlist/{{ item.id }}/mark-purchased`
- the operator-combo count: **0**
- Class signals: `page-header`, `warning`, `success`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **4**

**Context keys (6):** `items`, `by_priority`, `total_pending_gs`, `total_all_gs`, `purchased_count`, `pending_count`

**Data sources (SQLAlchemy models):** `WishlistItem`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/wishlist.png`

---

### `/produccion`

**Produccion worksheet** — GET → `produccion.produccion_worksheet` → `produccion.html`

**Template:** `16,306 chars / 410 lines` — extends `base.html`
- Forms POST to: `/produccion-planner/compute`, `/produccion/template/fork-week`, `/produccion/override`
- the operator-combo count: **0**
- Class signals: `info`, `metric-card`, `danger`, `metric`, `success`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✓
- Currency refs (Gs./gs_full): **2**

**Context keys (9):** `view`, `week_start`, `weekdays`, `week_plan`, `rows`, `week_ingredients`, `prev_week_iso`, `next_week_iso`, `week_sales`

**Data sources (SQLAlchemy models):** `Pedido`, `Recipe`, `Sale`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/produccion.png`

---

### `/produccion-planner`

**Planner** — GET → `herebus.planner_form` → `planner.html`

**Template:** `4,859 chars / 122 lines` — extends `base.html`
- Forms POST to: `/produccion-planner/compute`
- the operator-combo count: **1**
- Class signals: `page-header`, `warning`, `success`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **2**

**Context keys (2):** `recipes`, `results`

**Data sources (SQLAlchemy models):** `Recipe`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/produccion-planner.png`

---

### `/eod`

**Eod** — GET → `eod.eod_view` → `eod.html`

**Template:** `6,438 chars / 181 lines` — extends `base.html`
- Forms POST to: `/eod/check`, `/eod/completar`
- the operator-combo count: **0**
- Class signals: `success`, `danger`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (9):** `items`, `progress`, `today_plan`, `completions`, `today_iso`, `saved_notes`, `reorder_items`, `reorder_count`, `reorder_total_gs`

**Data sources (SQLAlchemy models):** `AppMeta`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/eod.png`

---

### `/merma`

**Merma** — GET → `merma.merma_list` → `merma.html`

**Template:** `11,449 chars / 303 lines` — extends `base.html`
- Forms POST to: `/merma`, `/merma/registrar`, `/merma/receta`
- the operator-combo count: **6**
- Class signals: `metric-card`, `empty-state`, `info`, `form-row`, `metric`
- Empty-state: ✓ · Chart: ✓ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **4**

**Context keys (19):** `items`, `impact`, `pct`, `reasons`, `selected_reason`, `ingredients`, `recipes`, `top_ingredients`, `days`, `since`, `until`, `preset_url_7`, `preset_url_30`, `preset_url_90`, `available_units`, `default_unit`, `total`, `page_start`, `page_end`

**Data sources (SQLAlchemy models):** `Ingredient`, `Recipe`, `Sale`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/merma.png`

---

### `/reorder`

**Reorder** — GET → `reorder.reorder_view` → `reorder.html`

**Template:** `8,914 chars / 194 lines` — extends `base.html`
- Forms POST to: `/reorder/generate-po`, `/reorder/registrar`
- the operator-combo count: **1**
- Class signals: `info`, `danger`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **1**

**Context keys (8):** `items`, `total_cost_gs`, `count`, `supplier_map`, `price_stats`, `forecast_map`, `page_start`, `page_end`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reorder.png`

---

### `/shopping-list`

**Shopping list** — GET → `shopping.shopping_list_index` → `shopping_list.html`

**Template:** `5,069 chars / 123 lines` — extends `base.html`
- Forms POST to: `/shopping-list/{{ item.id }}/delete`, `/shopping-list/{{ item.id }}/mark-purchased`, `/shopping-list/sync-low-stock`, `/shopping-list/{{ item.id }}/unmark`
- the operator-combo count: **0**
- Class signals: `success`, `page-header`, `danger`, `warning`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **2**

**Context keys (6):** `items`, `total_gs`, `show_purchased`, `by_ingredient`, `open_count`, `purchased_count`

**Data sources (SQLAlchemy models):** `ShoppingListItem`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/shopping-list.png`

---

### `/analisis`

**Analisis** — GET → `analisis.analisis_view` → `analisis.html`

**Template:** `10,663 chars / 233 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `metric-card`, `metric`, `danger`
- Empty-state: ✗ · Chart: ✓ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **6**

**Context keys (8):** `insights`, `top_margin`, `concentration`, `erosion_alerts`, `dow_buckets`, `turnover`, `complexity`, `data_freshness`

**Data sources (SQLAlchemy models):** `Ingredient`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/analisis.png`

---

### `/reportes`

**Reportes** — GET → `reportes.reportes_index` → `reportes.html`

**Template:** `845 chars / 28 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: _(none)_
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (1):** `reports`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes.png`

---

### `/reportes/iva`

**Reportes iva** — GET → `reportes.reportes_iva` → `reportes_iva.html`

**Template:** `2,078 chars / 63 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `metric-card`, `empty-state`, `metric`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **3**

**Context keys (2):** `rows`, `ytd`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-iva.png`

---

### `/reportes/libro-ventas`

**Reportes libro ventas** — GET → `reportes.reportes_libro_ventas` → `reportes_libro_ventas.html`

**Template:** `3,236 chars / 95 lines` — extends `base.html`
- Forms POST to: `/reportes/libro-ventas`
- the operator-combo count: **0**
- Class signals: `info`, `empty-state`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **3**

**Context keys (4):** `rows`, `start_date`, `end_date`, `preset`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-libro-ventas.png`

---

### `/reportes/diario`

**Reportes diario** — GET → `reportes.reportes_diario` → `reportes_diario.html`

**Template:** `2,076 chars / 60 lines` — extends `base.html`
- Forms POST to: `/reportes/diario`
- the operator-combo count: **0**
- Class signals: `metric-card`, `metric`, `form-row`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **1**

**Context keys (2):** `summary`, `for_date`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-diario.png`

---

### `/reportes/comparacion`

**Reportes comparacion** — GET → `reportes.reportes_comparacion` → `reportes_comparacion.html`

**Template:** `3,674 chars / 98 lines` — extends `base.html`
- Forms POST to: `/reportes/comparacion`
- the operator-combo count: **0**
- Class signals: `metric-card`, `metric`, `form-row`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (5):** `comparison`, `start1`, `end1`, `start2`, `end2`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-comparacion.png`

---

### `/reportes/top-productos`

**Reportes top productos** — GET → `reportes.reportes_top_productos` → `reportes_top_productos.html`

**Template:** `1,743 chars / 62 lines` — extends `base.html`
- Forms POST to: `/reportes/top-productos`
- the operator-combo count: **0**
- Class signals: `empty-state`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **1**

**Context keys (4):** `rows`, `start_date`, `end_date`, `limit`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-top-productos.png`

---

### `/reportes/retencion`

**Reportes retencion** — GET → `reportes.reportes_retencion` → `reportes_retencion.html`

**Template:** `2,198 chars / 63 lines` — extends `base.html`
- Forms POST to: `/reportes/retencion`
- the operator-combo count: **0**
- Class signals: `metric-card`, `empty-state`, `metric`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (3):** `stats`, `start_date`, `end_date`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-retencion.png`

---

### `/reportes/valor-pedido`

**Reportes valor pedido** — GET → `reportes.reportes_valor_pedido` → `reportes_valor_pedido.html`

**Template:** `1,425 chars / 43 lines` — extends `base.html`
- Forms POST to: `/reportes/valor-pedido`
- the operator-combo count: **0**
- Class signals: `metric-card`, `empty-state`, `metric`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **1**

**Context keys (3):** `aov`, `start_date`, `end_date`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-valor-pedido.png`

---

### `/reportes/ventas-hora`

**Reportes ventas hora** — GET → `reportes.reportes_ventas_hora` → `reportes_ventas_hora.html`

**Template:** `1,322 chars / 49 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `empty-state`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (2):** `by_hour`, `peak_hour`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-ventas-hora.png`

---

### `/reportes/metodos-pago`

**Reportes metodos pago** — GET → `reportes.reportes_metodos_pago` → `reportes_metodos_pago.html`

**Template:** `1,795 chars / 62 lines` — extends `base.html`
- Forms POST to: `/reportes/metodos-pago`
- the operator-combo count: **0**
- Class signals: `metric-card`, `empty-state`, `metric`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **1**

**Context keys (4):** `breakdown`, `total_gs`, `start_date`, `end_date`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-metodos-pago.png`

---

### `/reportes/precios`

**Reportes precios** — GET → `reportes.reportes_precios` → `reportes_precios.html`

**Template:** `3,193 chars / 104 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `metric-card`, `metric`
- Empty-state: ✓ · Chart: ✓ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **5**

**Context keys (4):** `rows`, `days`, `detail`, `detail_events`

**Data sources (SQLAlchemy models):** `IngredientPriceEvent`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-precios.png`

---

### `/reportes/cierre-mensual`

**Reportes cierre mensual** — GET → `reportes.reportes_cierre_mensual` → `reportes_cierre_mensual.html`

**Template:** `5,280 chars / 122 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `metric-card`, `metric`, `danger`, `success`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **2**

**Context keys (7):** `close`, `year`, `month`, `prev_year`, `prev_month`, `next_year`, `next_month`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-cierre-mensual.png`

---

### `/reportes/food-cost-variance`

**Food cost variance** — GET → `insights_derived.food_cost_variance` → `insight_food_cost.html`

**Template:** `1,662 chars / 32 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `metric-card`, `metric`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (1):** `days`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-food-cost-variance.png`

---

### `/reportes/demand`

**Demand** — GET → `insights_derived.demand_view` → `insight_demand.html`

**Template:** `1,647 chars / 42 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: _(none)_
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (2):** `forecasts`, `shopping`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-demand.png`

---

### `/reportes/freshness`

**Freshness** — GET → `insights_derived.freshness_view` → `insight_freshness.html`

**Template:** `1,555 chars / 39 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `danger`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (2):** `flags`, `cook_today`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-freshness.png`

---

### `/reportes/stock-intel`

**Stock intel** — GET → `insights_stock.stock_intel_view` → `insight_stock.html`

**Template:** `1,978 chars / 47 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: _(none)_
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (4):** `turnover`, `dead`, `days`, `dead_days`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-stock-intel.png`

---

### `/reportes/afinidades`

**Afinidades** — GET → `insights_stock.afinidades_view` → `insight_afinidades.html`

**Template:** `954 chars / 25 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: _(none)_
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (1):** `pairs`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-afinidades.png`

---

### `/reportes/margenes`

**Margenes** — GET → `insights_stock.margenes_view` → `insight_margenes.html`

**Template:** `1,711 chars / 29 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `danger`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (2):** `drift`, `days`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/reportes-margenes.png`

---

### `/pricing`

**Pricing** — GET → `herebus.pricing_list` → `pricing.html`

**Template:** `2,508 chars / 56 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `page-header`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **9**

**Context keys (4):** `rows`, `channels_margins`, `total_cost_gs`, `total_retail_gs`

**Data sources (SQLAlchemy models):** `RecipePricing`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/pricing.png`

---

### `/vs-mercado`

**Benchmarks** — GET → `herebus.benchmarks_list` → `benchmarks.html`

**Template:** `1,591 chars / 49 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `page-header`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **3**

**Context keys (1):** `benchmarks`

**Data sources (SQLAlchemy models):** `MarketBenchmark`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/vs-mercado.png`

---

### `/bank`

**Bank** — GET → `herebus.bank_list` → `bank.html`

**Template:** `5,622 chars / 127 lines` — extends `base.html`
- Forms POST to: `/bank/add`
- the operator-combo count: **2**
- Class signals: `page-header`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (7):** `transactions`, `eur_income`, `eur_spent`, `eur_net`, `pyg_balance_gs`, `categories`, `active_category`

**Data sources (SQLAlchemy models):** `BankTransaction`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/bank.png`

---

### `/auditoria`

**Auditoria** — GET → `auditoria.auditoria_index` → `auditoria.html`

**Template:** `6,769 chars / 163 lines` — extends `base.html`
- Forms POST to: `/auditoria`, `/auditoria/prune`
- the operator-combo count: **0**
- Class signals: `info`, `empty-state`, `danger`, `form-row`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (15):** `formatted_rows`, `page`, `total_pages`, `total_count`, `limit`, `action_filter`, `start_date`, `end_date`, `ip_filter`, `user_filter`, `target_type`, `target_id`, `presets`, `page_start`, `page_end`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/auditoria.png`

---

### `/ops/status`

**Ops status** — GET → `ops.ops_status` → `ops_status.html`

**Template:** `1,498 chars / 45 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: _(none)_
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (1):** `endpoints`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/ops-status.png`

---

### `/settings`

**Settings page** — GET → `settings.settings_page` → `settings.html`

**Template:** `23,833 chars / 666 lines` — extends `base.html`
- Forms POST to: `/settings/business`, `/settings/seed-demo`, `/settings/theme`, `/settings/fiscal`
- the operator-combo count: **2**
- Class signals: `info`, `success`
- Empty-state: ✓ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **1**

**Context keys (11):** `business_name`, `business_ruc`, `business_address`, `business_phone`, `timbrado`, `punto_expedicion`, `invoice_sequence`, `theme`, `current_user`, `delivery_zones`, `compliance`

**Data sources (SQLAlchemy models):** `AppMeta`, `DeliveryZone`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/settings.png`

---

### `/settings/catalog`

**Settings catalog page** — GET → `settings.settings_catalog_page` → `settings_catalog.html`

**Template:** `45,113 chars / 950 lines` — extends `base.html`
- the operator-combo count: **7**
- Class signals: `page-header`, `danger`, `data-table`, `form-row`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **3**

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/settings-catalog.png`

---

### `/users`

**Users** — GET → `users.users_list` → `users.html`

**Template:** `12,518 chars / 379 lines` — extends `base.html`
- Forms POST to: `/users/crear`
- the operator-combo count: **2**
- Class signals: `info`, `empty-state`, `danger`, `success`
- Empty-state: ✓ · Chart: ✗ · Modal: ✓ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (5):** `users`, `current_user_id`, `total`, `page_start`, `page_end`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/users.png`

---

### `/guia`

**Guia** — GET → `help.guia_index` → `guia.html`

**Template:** `337 chars / 13 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: _(none)_
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (3):** `title`, `body_html`, `section`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/guia.png`

---

### `/riesgos`

**Risk** — GET → `herebus.risk_list` → `riesgos.html`

**Template:** `1,898 chars / 46 lines` — extends `base.html`
- the operator-combo count: **0**
- Class signals: `success`, `page-header`, `warning`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **3**

**Context keys (6):** `items`, `by_category`, `severity_total_gs`, `active_count`, `mitigated_count`, `closed_count`

**Data sources (SQLAlchemy models):** `RiskItem`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/riesgos.png`

---

### `/delivery-zones`

**Delivery zones** — GET → `herebus.delivery_zones_list` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/delivery-zones.png`

---

### `/excel`

**Excel home** — GET → `excel_io.excel_home` → `excel.html`

**Template:** `5,812 chars / 140 lines` — extends `base.html`
- Forms POST to: `/excel/importar`, `/excel/validar`
- the operator-combo count: **0**
- Class signals: `form-row`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (1):** `import_history`

**Data sources (SQLAlchemy models):** `ImportBatch`

**Browser-test contract:** `ExcelPage` in `tests/browser/pages.py` — restyle must update selectors there only

**Screenshot:** `docs/user-guide/screenshots/all-pages/excel.png`

---

### `/login`

**Login** — GET → `auth.login_form` → `login.html`

**Template:** `6,490 chars / 165 lines` — extends `base.html`
- Forms POST to: `/login`
- the operator-combo count: **0**
- Class signals: `pill`, `info`, `form-row`
- Empty-state: ✗ · Chart: ✗ · Modal: ✗ · aria-current: ✗
- Currency refs (Gs./gs_full): **0**

**Context keys (5):** `next`, `error`, `message`, `using_supabase`, `last_username`

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** `LoginPage` in `tests/browser/pages.py` — restyle must update selectors there only

**Screenshot:** `docs/user-guide/screenshots/all-pages/login.png`

---

### `/excel/exportar`

**Excel export** — GET → `excel_io.excel_export` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/export-excel.xlsx.png`

---

### `/inventario/export.csv`

**Inventory export csv** — GET → `inventory.inventory_export_csv` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources (SQLAlchemy models):** `Ingredient`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/export-inventario.csv.png`

---

### `/pedidos/export-csv?status_filter=todos`

**Pedidos export csv** — GET → `pedidos.pedidos_export_csv` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources (SQLAlchemy models):** `Pedido`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/export-pedidos.csv.png`

---

### `/productos/export.csv`

**Products export csv** — GET → `products.products_export_csv` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources (SQLAlchemy models):** `Product`

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/export-productos.csv.png`

---

### `/proveedores`

**Proveedores alias** — GET → `main.proveedores_alias` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/proveedores-alias.png`

---

### `/reportes/diario/pdf`

**Reportes diario pdf** — GET → `reportes.reportes_diario_pdf` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/export-reportes-diario.pdf.png`

---

### `/reportes/iva/pdf`

**Reportes iva pdf** — GET → `reportes.reportes_iva_pdf` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/export-reportes-iva.pdf.png`

---

### `/reportes/precios/csv`

**Reportes precios csv** — GET → `reportes.reportes_precios_csv` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/export-reportes-precios.csv.png`

---

### `/ventas/export.csv`

**Sales export csv** — GET → `sales.sales_export_csv` → `(no template)`

**Template:** _(missing — route returns redirect / JSON / no template)_

**Context keys:** _(none parsed)_

**Data sources:** _(no model imports detected in handler body — likely pulls via session.execute or inline)_

**Browser-test contract:** _(no automated browser test for this route — visual review only)_

**Screenshot:** `docs/user-guide/screenshots/all-pages/export-ventas.csv.png`

---
