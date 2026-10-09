# Saskia-App (Sazón RMS) Deduplication Report

> Raw analysis from the 2026-10-07 survey subagent
> (deleg_36925dc5, 49 tool calls, 4m52s). The actionable plan lives
> in [DEDUP_PLAN.md](DEDUP_PLAN.md). This file is the survey data;
> the plan is the work plan.

## 1. Top-15 Largest Templates (Path, Lines, Last Touched)

| Template Path | Lines | Last Touched |
|---------------|-------|--------------|
| `app/templates/produccion.html` | 2,355 | 2026-10-07 |
| `app/templates/ventas.html` | 1,094 | 2026-10-06 |
| `app/templates/receta_form.html` | 888 | 2026-10-06 |
| `app/templates/settings_catalog.html` | 887 | 2026-10-06 |
| `app/templates/cliente_editar.html` | 701 | 2026-10-06 |
| `app/templates/pedidos_nuevo.html` | 666 | 2026-10-06 |
| `app/templates/reorder.html` | 625 | 2026-10-06 |
| `app/templates/productos.html` | 592 | 2026-10-06 |
| `app/templates/settings.html` | 550 | 2026-10-06 |
| `app/templates/cliente_detalle.html` | 521 | 2026-10-06 |
| `app/templates/producto_form.html` | 520 | 2026-10-06 |
| `app/templates/inicio.html` | 488 | 2026-10-06 |
| `app/templates/_components/atoms.html` | 426 | 2026-10-06 |
| `app/templates/receta_detalle.html` | 403 | 2026-10-06 |
| `app/templates/pedido_detalle.html` | 393 | 2026-10-06 |

## 2. Route Inventory: URL → Template → Page Title (h1) → First Section (h2)

| URL | Template | Page Title (h1) | First Section (h2) |
|-----|----------|-----------------|---------------------|
| `/` | `inicio.html` | Inicio | Hoy (KPI cards) |
| `/inicio` | `inicio.html` | Inicio | Hoy (KPI cards) |
| `/produccion` | `produccion.html` | Producción · [date] | Sin producción planificada |
| `/produccion/manana` | `produccion_manana.html` | Producción · Mañana | Pedidos para mañana |
| `/produccion/prep` | `produccion_prep.html` | Plan de preparación — semana | Resumen |
| `/produccion/prep-recipes` | `produccion_prep_recipes.html` | Recetas para preparar hoy | — |
| `/produccion/haccp` | `produccion_haccp.html` | Producción · HACCP | — |
| `/produccion/accuracy` | `produccion_accuracy.html` | Precisión del Forecast | — |
| `/eod` | `eod.html` | Cierre diario | Resumen del rango |
| `/shopping-list` | `shopping_list.html` | 🛒 Lista de Compras | — |
| `/ventas` | `ventas.html` | Ventas | — |
| `/pedidos` | `pedidos.html` | Pedidos | — |
| `/clientes` | `clientes.html` | Clientes | — |
| `/productos` | `productos.html` | Productos | — |
| `/inventario` | `inventario.html` | Inventario | — |
| `/proveedores` | `proveedores.html` | Proveedores | — |
| `/recetas` | `recetas.html` | Recetas | — |
| `/reorder` | `reorder.html` | Reordenar stock | — |
| `/merma` | `merma.html` | Merma | — |

## 3. Repeated Section Headings

| Heading Text | Files Where It Appears | Frequency |
|--------------|------------------------|-----------|
| **Stock** | 17 templates (see plan §1.5) | 17 |
| **Resumen** | `produccion_prep.html`, `supplier_precios.html`, `merma.html`, `produccion_prep_recipes.html`, `ventas_historial.html`, `eod.html`, `settings_catalog.html`, `reportes_diario.html` | 8 |
| **Ingredientes necesarios** | `produccion_manana.html` ×2, `produccion.html` | 3 |
| **Notificaciones** | `base.html` ×2, `produccion.html`, `settings.html` | 4 |
| **Merma** | `eod.html`, `insight_food_cost.html`, `inicio.html`, `dashboard.html`, `produccion.html`, `merma.html` | 6 |
| **Ingrediente** | 19 templates (column header) | 19 |
| **Producción** | `produccion_manana.html` (title), `eod.html`, `ingrediente_detalle.html`, `inventario.html`, `merma.html` | 5 |
| **Pedidos para mañana** | `produccion_manana.html` | 1 (single-source — was the source of the 10-07 enhancement) |
| **Plan semanal** | `produccion_manana.html` | 1 (single-source — future §2.2 candidate) |

## 4. Ingredient Table Duplication Analysis

| Page | Purpose | Columns Displayed | Data Scope | Uniqueness | Recommended Canonical |
|------|---------|-------------------|------------|------------|----------------------|
| `/produccion` | Daily/weekly/monthly production plan | Ingrediente, Requerido, Stock actual, A comprar | Plan lines aggregated by week, stock status | **Most comprehensive** | ✓ PRIMARY |
| `/produccion/prep` | Weekly preparation sheet | Ingrediente, Semana, Cant. prevista, Cant. comprada, Para qué | Weekly aggregated, sorted by severity | Adds "Para qué" | Secondary view |
| `/produccion/prep-recipes` | Recipe-by-recipe daily prep | Ingrediente, Cant. a comprar, Para qué | Per-recipe breakdown for one day | Recipe-specific | Tertiary view |
| `/shopping-list` | Purchase tracking | Ingrediente, Cant a comprar, Unidad, Para qué, Subtotal Gs. | Missing-to-buy items | **Most actionable** | Filtered view of primary |
| `/produccion/manana` | Tomorrow's automated plan | Ingrediente, Requerido, Stock, Comprar | 14d rolling forecast | Overlaps with primary | **Duplicate** (10-07 fix: hide the table, link to primary) |

**Key Overlap:** All 5 render ingredient quantities + stock status.
`/shopping-list` is the "A comprar" subset of `/produccion`.
`/produccion/manana` ingredient table is a duplicate of `/produccion` and
should link out (the link card already shipped in 87496de8).

## 5. Notification/Alert Duplication

| Notification Type | `/inicio` | `/produccion` | `/eod` | Frequency |
|-------------------|-----------|---------------|--------|-----------|
| Pending orders | ✗ | ✓ (pedidos pendientes) | ✗ | 1 |
| Stock warnings | ✗ | ✓ (ingredientes bajo mínimo) | ✗ | 1 |
| HACCP alerts | ✗ | ✗ | ✗ | 1 |
| Daily target vs actual | ✗ | ✓ (bulto) | ✓ (EOD card) | 2 |
| Merma del día | ✗ | ✓ | ✗ | 1 |
| Loyalty enrollment | ✓ | ✗ | ✗ | 1 |
| Anomalías | ✗ | ✓ (3fc95515) | ✓ | 2 |
| Forecast confidence | ✗ | ✓ (low_confidence_count) | ✗ | 1 |

**Finding:** Each template has mostly unique notifications. The 8 bundled
notifications in `/produccion` (lines 243-290) are specific to production
context. Future: extract to `notifications_bundle` partial.

## 6. KPI Tile Duplication

| KPI Label | `/inicio` | `/produccion/manana` | Other Pages | Frequency |
|-----------|-----------|----------------------|-------------|-----------|
| Ventas de hoy | ✓ | ✗ | — | 1 |
| Ticket promedio | ✓ | ✗ | — | 1 |
| Margen estimado | ✓ | ✗ | — | 1 |
| Stock | ✓ | ✓ | — | 2 |
| Stock bajo | ✗ | ✓ | — | 1 |
| Producción de hoy | ✗ | ✓ | — | 1 |
| Merma del día | ✗ | ✓ | — | 1 |
| Ingredientes únicos | ✓ | ✗ | — | 1 |
| Loyalty enrollment | ✓ | ✗ | — | 1 |
| Capital en inventario | ✗ | ✗ | `analisis.html` | 2 |
| Hora/Día pico | ✗ | ✗ | `analisis.html` | 2 |

**Overlap:** `Capital en inventario` and peak-sales analytics appear in
both `/inicio` and `/analisis.html`. Centralize to `kpi_grid` partial.

## 7. Top 5 Deduplication Recommendations (ROI Ranked)

### 🥇 HIGH ROI (2-4 hrs/week saved)

1. **Ingredient Table Consolidation** — `/produccion` is canonical;
   3 other views render as filtered/sorted modes of it.
   *Cost:* Medium (template refactor — 4 templates to update).
2. **Shared Notification Component** — extract `notifications_bundle`
   partial used by 4 templates. *Cost:* Low.
3. **KPI Tile Centralization** — `kpi_grid` partial with context-based
   filtering. *Cost:* Low.

### 🥈 MEDIUM ROI (1-2 hrs/week saved)

1. **Production View Navigation Unification** — `proday_nav` partial
   across `/produccion` + `/manana` + `/prep` + `/prep-recipes`.
   *Cost:* Medium.
2. **Stock Status Indicators** — `stock_status_indicator` macro across
   17 templates. *Cost:* Low (mostly formatting).

## Bottom line

8-12 hours/week saved by centralizing. The 5-PR plan in
[DEDUP_PLAN.md](DEDUP_PLAN.md) is the executable roadmap.
