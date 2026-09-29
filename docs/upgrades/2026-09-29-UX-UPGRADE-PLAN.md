# Saskia RMS — Complete UX/UI Upgrade Plan

**Generated:** 2026-09-29
**Author:** UX/UI Principal review (multi-hat analysis + cross-page consolidation)
**Source audits:**
- `/tmp/designer-drop/audit-batch2-prod.md` (78 KB · 948 lines · 14 pages — Inventario/Producción/Pedidos/Receta)
- `/tmp/designer-drop/audit-batch3-reports.md` (69 KB · 950 lines · 14 pages — Compras/Reportes/Admin/Bank/Riesgos/Auditoría)
- `/tmp/designer-drop/cross-page-wishlist-consolidation.md` (37 KB · 602 lines — top 30 patterns + top 10 macros)
- `/tmp/designer-drop/cross-cutting-consistency-audit.md` (38 KB · 544 lines — 12 naming/consistency dimensions)
- `/tmp/designer-drop/ux-audit-2026-09-27.md` (34 KB — 6 universal defects, 12 cross-cutting patterns)
- `/tmp/designer-drop/REPORT.md` (52 KB — route → router → template → context-keys reference)
- `/tmp/saskia-ux-audit-drop-2026-09-27.zip` (9.5 MB — full bundle + 82 screenshots)

**Repo state:** 77 page templates, 88 with components, 32 routers, 292 test files, 647 commits.

---

## TL;DR

The app has **strong bones but inconsistent UX**. Three priorities:

1. **Extract 10 atomic macros** from `inventario.html` (list) + `inventario_form.html` (form) — the gold-standard pages — and roll them out across every other page.
2. **Fix the 6 universal defects** (D1–D6) — currency format drift is the worst (recurring finance bug).
3. **Fix the 5 broken/empty pages** (`dashboard` → delete+redirect, `pedido_stock_preview` → 500 error, `riesgos` → empty-state CTA, `benchmarks` (vs-mercado) → shows 1 row, `bank` → import CSV CTA).

**Estimated total effort for full top-15 priority plan:** ~58 hours (~7 working days).
**Highest-leverage 3 things:** Fix currency drift + empty states + seed names = 8 hours for biggest perceived quality jump.

---

## 1. The 77 page templates — full inventory

| Router | Page template | LOC | Bytes | Tests touching it |
|---|---|---:|---:|---:|
| analisis | `analisis.html` | 250 | 12.6 KB | 2 |
| auditoria | `auditoria.html` | 167 | 7.7 KB | 2 |
| auth | `login.html` | 163 | 6.4 KB | 1 |
| credits | `creditos.html` | 35 | 1.3 KB | — |
| customers | `clientes.html` | 199 | 8.9 KB | 1 |
| customers | `cliente_detalle.html` | 137 | 5.7 KB | — |
| customers | `cliente_editar.html` | 54 | 2.1 KB | — |
| dashboard | `inicio.html` | 333 | 15.2 KB | 1 |
| dev | `dev_combo_smoke.html` | 73 | 2.4 KB | — |
| eod | `eod.html` | 184 | 6.7 KB | 1 |
| excel_io | `excel.html` | 140 | 5.9 KB | 3 |
| excel_io | `excel_mode_guidance.html` | 36 | 1.4 KB | — |
| excel_io | `excel_validate.html` | 68 | 1.7 KB | — |
| help | `guia.html` | 13 | 0.4 KB | — |
| herebus | `bank.html` | 274 | 12.0 KB | **4 (61 tests)** |
| herebus | `benchmark_edit.html` | 97 | 4.0 KB | — |
| herebus | `benchmarks.html` | 108 | 4.2 KB | — |
| herebus | `dashboard.html` | 152 | 6.8 KB | 1 |
| herebus | `planner.html` | 115 | 4.6 KB | 1 |
| herebus | `pricing.html` | 54 | 2.4 KB | — |
| herebus | `riesgos.html` | 63 | 2.7 KB | — |
| herebus | `wishlist.html` | 71 | 3.2 KB | 1 |
| insights_derived | `insight_demand.html` | 45 | 1.9 KB | — |
| insights_derived | `insight_food_cost.html` | 35 | 1.9 KB | — |
| insights_derived | `insight_freshness.html` | 42 | 1.8 KB | — |
| insights_derived | `insight_price_impact.html` | 43 | 1.8 KB | — |
| insights_stock | `insight_afinidades.html` | 28 | 1.2 KB | — |
| insights_stock | `insight_margenes.html` | 63 | 3.7 KB | — |
| insights_stock | `insight_margenes_detalle.html` | 40 | 2.0 KB | — |
| insights_stock | `insight_stock.html` | 50 | 2.2 KB | — |
| inventory | `inventario.html` | 292 | 17.9 KB | 4 |
| inventory | `inventario_form.html` | 144 | 7.9 KB | 2 |
| inventory | `ingrediente_detalle.html` | 387 | 14.7 KB | — |
| inventory | `inventario_movimientos.html` | 82 | 2.8 KB | — |
| merma | `merma.html` | 264 | 9.8 KB | 1 |
| ops | `ops_status.html` | 48 | 1.7 KB | — |
| pedidos | `pedidos.html` | 297 | 12.5 KB | 3 |
| pedidos | `pedidos_nuevo.html` | 213 | 7.1 KB | 1 |
| pedidos | `pedido_detalle.html` | 196 | 8.1 KB | — |
| pedidos | `pedido_board.html` | 335 | **66.5 KB** | — |
| pedidos | `pedido_stock_preview.html` | 91 | 3.6 KB | 1 |
| pedidos | `pedido_publico.html` | 128 | 5.6 KB | — |
| produccion | `produccion.html` | 452 | 18.8 KB | 1 |
| products | `productos.html` | 579 | 28.9 KB | — |
| products | `producto_form.html` | 508 | 19.5 KB | — |
| products | `productos_importar.html` | 113 | 5.0 KB | — |
| recipes | `recetas.html` | 270 | 12.7 KB | 6 (53 tests) |
| recipes | `receta_form.html` | **1,149** | **44.0 KB** | — |
| recipes | `receta_detalle.html` | 329 | 13.6 KB | — |
| recipes | `recipe_photos.html` | 39 | 1.7 KB | — |
| reorder | `reorder.html` | 184 | 8.5 KB | 2 |
| reportes | `reportes.html` | 30 | 1.1 KB | — |
| reportes | `reportes_diario.html` | 67 | 2.6 KB | 1 |
| reportes | `reportes_iva.html` | 65 | 2.4 KB | — |
| reportes | `reportes_retencion.html` | 62 | 2.4 KB | 1 |
| reportes | `reportes_metricas.html` | 143 | 5.7 KB | — |
| reportes | `reportes_top_productos.html` | 62 | 1.9 KB | 1 |
| reportes | `reportes_libro_ventas.html` | 95 | 3.4 KB | — |
| reportes | `reportes_cierre_mensual.html` | 164 | 7.5 KB | 1 |
| reportes | `reportes_precios.html` | 113 | 3.7 KB | — |
| reportes | `reportes_comparacion.html` | 109 | 4.7 KB | — |
| reportes | `reportes_metodos_pago.html` | 65 | 2.1 KB | — |
| reportes | `reportes_ventas_hora.html` | 50 | 1.5 KB | — |
| reportes | `reportes_valor_pedido.html` | 49 | 2.0 KB | — |
| sales | `ventas.html` | 656 | 28.8 KB | 3 |
| sales | `ventas_historial.html` | 180 | 7.8 KB | 1 |
| sales | `recibo.html` | 144 | 5.9 KB | — |
| settings | `settings.html` | 747 | 27.3 KB | 1 |
| settings | `settings_catalog.html` | 956 | 46.1 KB | 1 |
| shopping | `shopping_list.html` | 124 | 5.3 KB | 1 |
| suppliers | `suppliers.html` | 77 | 2.8 KB | 1 |
| suppliers | `supplier_form.html` | 48 | 2.4 KB | — |
| suppliers | `supplier_orders.html` | 85 | 3.0 KB | — |
| users | `users.html` | 211 | 7.5 KB | — |

**Orphans (no router):** `base.html` (309 LOC, parent template), `delivery_zones.html` (38 LOC, dead route?), `produccion_calendario.html` (25 LOC, dead route?).

**Heaviest 10 by LOC:**
1. `receta_form.html` — 1,149 LOC, 44 KB
2. `settings_catalog.html` — 956 LOC, 46 KB
3. `settings.html` — 747 LOC, 27 KB
4. `ventas.html` — 656 LOC, 29 KB (POS)
5. `productos.html` — 579 LOC, 29 KB
6. `producto_form.html` — 508 LOC, 20 KB
7. `produccion.html` — 452 LOC, 19 KB
8. `ingrediente_detalle.html` — 387 LOC, 15 KB
9. `pedido_board.html` — 335 LOC, **66 KB** (largest by bytes — minified inline)
10. `inicio.html` — 333 LOC, 15 KB

---

## 2. Universal defects (apply app-wide)

| # | Defect | Affected pages | Fix | Priority |
|---|---|---|---|---|
| **D3** | **Currency format drift** — same data renders as `Gs. 75` / `75` / `Gs. 75,00` depending on context | All `/reportes/*`, `/productos`, `/recetas/{id}`, `/bank` | **Mandate `format_gs` Jinja filter everywhere**; add CI grep rule that fails if `Gs\. {{` or `Gs. {{` appears without the filter | **P0** |
| **D6** | **Seed-name identifiers leak** — "Producto cfaf4b47", "Receta 0da4ca66" | `/reportes/top-productos`, `/analisis`, `/vs-mercado` | Seeder should generate Spanish bakery names ("Pan de queso", "Chipa grande") | P0 |
| **D1** | **Native date picker still visible** — white-on-white triangle, English "mm/dd/yyyy" | `/reportes/top-productos`, `/merma`, `/inventario/nuevo`, `/settings` | `<saskia-date>` web component with voseo placeholders + dark-mode tokens | P1 |
| **D4** | **"Cargando..." spinner never replaced** on slow routes | `/reportes/*`, `/analisis` | Confirm mutation observer attached to async elements | P1 |
| **D5** | **0 vs — ambiguity** — "no data" vs "zero data" | `/clientes`, `/ventas/historial`, `/merma`, `/analisis` rotación | Server passes `value=None` vs `value=0`; renderer maps to "—" vs "0" | P1 |
| **D2** | **"Editar"/"Ver" button too far right** on wide tables | `/clientes`, `/suppliers`, `/inventario`, `/productos` | Sticky-right action column or row-leading chevron | P2 |

---

## 3. Naming consistency — 12 dimensions to fix

From `cross-cutting-consistency-audit.md`. Pick a canonical term for each and grep-replace across all templates + copy:

| # | Current drift | Canonical choice |
|---|---|---|
| 1 | "Guardá" / "Salvar" / "Guardar" | **"Guardá"** (voseo imperative, per AGENTS.md) |
| 2 | "Cliente" / "Comprador" / "Customer" | **"Cliente"** |
| 3 | "Producto" / "Receta" | **"Receta"** is the production entity; **"Producto"** is the commercial entity. Don't conflate. |
| 4 | "Mostrador" / "Pickup" / "Counter" | **"Mostrador"** |
| 5 | "Cerrar día" / "Cierre" / "EOD" | **"Cerrar día"** |
| 6 | "Comprobante fiscal" / "Boleta" / "Factura" / "Recibo" | **"Comprobante"** |
| 7 | "ingrediente" / "Insumo" | **"Ingrediente"** |
| 8 | "Ver" / "Abrir" / "Ver detalle" / "Detalle" | **"Ver"** |
| 9 | "Categoría" / "Familia" / "Etiqueta" / "Tag" | **"Categoría"** (ingredient), **"Etiqueta"** (dietary/allergen) |

---

## 4. The 30 reusable UX patterns (the "abstract and reuse" list)

**Legend:** ✅ already a reusable component in `_components/` · ⚠ partially implemented · ❌ missing everywhere

| # | Pattern | Pages needing it | Effort | Priority | Status |
|---|---|---|---|---|---|
| 1 | **KPI delta strip** (vs prior period) | 9 (Inventario list, Lista compras, Bank, Pricing, Resumen diario, Riesgos, Producción, Pedidos board, Reportes per-card) | M | P1 | ❌ |
| 2 | **Filter chip rail** | 6 (Inventario, Proveedores, Pedidos board, Bank, Auditoría, Auditoría quick-access needs to be clickable) | M | **P0** (defect: chips non-clickable) | ⚠ |
| 3 | **Severity color bar** (left-edge stripe) | 7 (Riesgos, Auditoría, Bank, Inventario list, Reponer, Pedidos board cards, Lista compras) | S | P1 | ❌ |
| 4 | **Empty state with onboarding CTA** | 8 (Proveedores subpages, Riesgos, Wishlist, Bank, Pricing, Vs-mercado, Auditoría, Inventario-movimientos) | S | **P0** (Riesgos empty state is worst in system) | ⚠ |
| 5 | **In-page "derived tags" block** | 6 (Inventario-detalle, Inventario list, Producción, Pedido-nuevo, Pedido-detalle, Receta-editar) | M | P1 | ⚠ |
| 6 | **Side-rail live preview panel** | 5 (Receta-editar, Pedidos-nuevo, Produccion-planner, Inventario-nuevo, Inventario-editar) | M | P1 | ⚠ |
| 7 | **Source attribution at table footer** | 5 (Pedidos board, Inventario list, Reponer, Producción, Reportes per-card) | S | P2 | ⚠ |
| 8 | **Sticky top action cluster** | 8 long forms (Inventario-nuevo, Inventario-editar, Proveedor-nuevo, Pedidos-nuevo, Receta-editar, Vs-mercado-editar, list pages with bulk actions) | S | P1 | ❌ |
| 9 | **Tab nav with active underline** | 5 (Producción, Lista compras, Reportes index, Proveedor-detail, Inventario-detalle) | S | P1 | ⚠ |
| 10 | **Collapsible "ejemplo" callout** | 5 (Proveedor-nuevo, Receta-editar, Riesgos, Pedidos-nuevo, Inventario-nuevo) | S | P2 | ❌ |
| 11 | **Inline derived pill cluster** (dietary, allergen, status, channel) | 6 (Inventario-nuevo, Inventario list, Pedido-detalle, Receta-editar, Pedidos board, Receta-editar detail) | S | P2 | ⚠ |
| 12 | **Aggregated KPI strip** (real cards, not plain labels) | 9 (Inventario, Lista compras, Bank, Pricing, Wishlist, Riesgos, Pedidos board, Producción, Reportes index) | S | **P0** (Wishlist `Gs. 50,000,000` in plain text is broken) | ⚠ |
| 13 | **Inline warnings** (margin<30%, no recipe, price=0, "sin consumo") | 5+ (Receta-editar, Vs-mercado, Pedido-detalle, Reponer, Inventario-detalle) | S | P1 | ⚠ |
| 14 | **Bulk action bar** | 6 (Inventario, Proveedores, Reponer, Pedidos, Auditoría, Clientes) | S | P1 | ❌ |
| 15 | **Inline row actions** (Mark Done, Edit, Duplicate, View) | 7 (Pedidos board, Auditoría, Bank, Lista compras, Reponer, Proveedores, Inventario) | S | P2 | ⚠ |
| 16 | **Date range presets** (Hoy/Ayer/Esta semana/Mes/Trimestre/Año) | 8 (Inventario-movimientos, Reponer, Bank, Auditoría, Reportes/*, Pedidos board, Producción, Merma) | S | **P0** | ❌ |
| 17 | **Bar chart visualization** | 7 (Inventario, Producción, Lista compras, Reportes per-card, Pricing, Wishlist, Análisis) | M | P1 | ⚠ |
| 18 | **Period comparison overlay** | 4 (Inicio, Análisis, Reportes/*, Dashboard) | M | P2 | ❌ |
| 19 | **Drill-down (click row → detail)** | 9 | S | P2 | ✅ |
| 20 | **Print preview** | 5 (Recibo, Reportes/*, Producción prep sheet, Auditoría, Inventario-movimientos) | S | P2 | ⚠ |
| 21 | **Source attribution footer** | (same as #7) | — | — | — |
| 22 | **Search bar** (page-local, not just global) | 8 (Inventario, Productos, Recetas, Clientes, Auditoría, Bank, Reportes index, Wishlist) | S | **P0** | ⚠ |
| 23 | **Saved filters per user** | 6 | M | P2 | ❌ |
| 24 | **Sortable column headers with active highlight** | 7 (Inventario, Productos, Recetas, Clientes, Pedidos, Bank, Auditoría) | S | P2 | ⚠ |
| 25 | **Sticky header** | 9 (long table pages) | S | P1 | ❌ |
| 26 | **Pagination + jump-to-page** | 6 (Inventario, Productos, Clientes, Pedidos, Bank, Auditoría) | S | **P0** (Bank already does this) | ⚠ |
| 27 | **Tooltip glossary (?) on technical terms** | all | S | P2 | ❌ |
| 28 | **Photo placeholder** (initials in colored box) | 5 (Inventario, Productos, Recetas, Clientes, Proveedores) | S | P2 | ❌ |
| 29 | **Drag-drop reorder** | 3 (Receta-editar líneas, Producción day cards, Pedido board) | L | P2 | ❌ |
| 30 | **Required-field markers (*) + Save feedback (toast/inline)** | all | S | **P0** | ⚠ |

---

## 5. The 10 architectural macros to extract

These are the atoms to extract from `inventario.html` and `inventario_form.html` (the gold-standard pages) into `app/components/atoms.html`. Use them as the canonical template for every other list/form page.

| # | Macro | Pattern(s) it covers | Already exists? |
|---|---|---|---|
| 1 | `<KpiStrip>` | #1 (delta) + #12 (aggregated cards) | ⚠ partial (`.dashboard-grid`) |
| 2 | `<FilterChipRail>` | #2 | ⚠ partial (chips on auditoría but non-clickable — defect) |
| 3 | `<SeverityStripe>` | #3 | ❌ |
| 4 | `<EmptyState>` | #4 | ⚠ partial (`_components/atoms.html` has one but inconsistent across pages) |
| 5 | `<DerivedTagsBlock>` | #5 + #11 (pill cluster) | ⚠ partial (`_components/ingredient_tags.html` for one use case) |
| 6 | `<LivePreviewPanel>` | #6 | ⚠ partial (receta_form has inline one) |
| 7 | `<StickyActionCluster>` | #8 | ❌ |
| 8 | `<TabNav>` | #9 | ⚠ partial (used inconsistently) |
| 9 | `<EjemploCallout>` | #10 | ⚠ partial (merma has one) |
| 10 | `<PillCluster>` | #11 | ⚠ partial (tags macro has one) |

---

## 6. Per-page upgrade worklist (77 pages, grouped by family)

Each entry has: **Current LOC / Tests** / **Top 3 wishlist items** / **Defects (P0/P1)** / **Patterns to apply** / **Estimated effort**.

### 6.1 OPERATIONAL (counter, day-to-day)

#### `/` → `inicio.html` (333 LOC, 1 test)
**Top wishlist (5):**
1. "Para revisar" widget surfacing 1-2 insights from `/analisis`
2. Quick-action FAB: "+ Nueva venta" / "+ Nuevo pedido" / "+ Ajustar stock"
3. Bottom-of-day-close countdown: "Faltan 3 ventas para cerrar el día"
5. Recent customer strip
**Defects:** no delta arrows on KPIs (P1)
**Patterns to apply:** #1 (KPI delta), #12 (aggregated cards)
**Effort:** M

#### `/ventas` → `ventas.html` (656 LOC, 3 tests — POS, the most-used page)
**Top wishlist (5):**
1. Category labels on quick-action chips (currently unlabeled)
2. Customer repeat indicator ("Repeat customer: 5 visits")
3. Discount/coupon support
4. Refund/void flow with audit trail
5. Receipt email/SMS after sale
**Defects:** category labels missing on chips (P1)
**Patterns to apply:** #13 (inline warnings for out-of-stock), #16 (date presets), #20 (print receipt)
**Effort:** M

#### `/pedidos` → `pedidos.html` (297 LOC, 3 tests)
**Top wishlist (5):**
1. Status filter chips (currently dropdown)
2. Bulk actions: confirm/cancel/print
3. Calendar view of orders
4. Channel color-coding (whatsapp=green, mostrador=blue, web=purple)
5. KPI strip: orders today, total sales, avg ticket, oldest pending
**Defects:** no filter chip rail (P0)
**Patterns to apply:** #2 (filter chips), #3 (severity stripe), #14 (bulk action bar)
**Effort:** M

#### `/pedidos/nuevo` → `pedidos_nuevo.html` (213 LOC, 1 test)
**Top wishlist (5):**
1. Sticky total bar at bottom (subtotal · descuento · total · saldo)
2. Customer balance warning ("Este cliente debe Gs. 50.000 — ¿cobrá antes?")
3. Recurring orders
4. Quick-add presets (sells-most-lugar + last 5 orders)
5. Production impact preview (running total)
**Defects:** no live total preview (P1)
**Patterns to apply:** #6 (live preview panel), #8 (sticky action cluster)
**Effort:** M

#### `/pedidos/{id}` → `pedido_detalle.html` (196 LOC, 0 tests)
**Top wishlist (5):**
1. Payment recording (efectivo, transferencia, tarjeta, mixto)
2. Status transition buttons gated by current state
3. WhatsApp deep-link to share order
4. Print receipt (thermal printer or PDF)
5. Production impact mini-card
**Defects:** "Ver stock antes de cumplir" leads to 500 error (P0)
**Patterns to apply:** #7 (source attribution), #13 (inline warnings)
**Effort:** M

#### `/pedidos/board` → `pedido_board.html` (335 LOC, 66 KB, 0 tests) — kanban
**Top wishlist (5):**
1. 5 columns: Nuevo / En preparación / Listo / Entregado / Cancelado
2. Drag-and-drop status changes
3. Live timer on each card (5m, 15m, 30m thresholds)
4. Color coding by channel
5. KPI strip on top
**Defects:** missing drag-drop, no live timer (P1)
**Patterns to apply:** #29 (drag-drop), #12 (KPI strip)
**Effort:** L

#### `/pedidos/{id}/stock-preview` → `pedido_stock_preview.html` (91 LOC, 1 test) — **500 ERROR (P0)**
**Top fix:** fix the 500 error when clicking "Ver stock antes de cumplir"
**Defects:** 500 error (P0)
**Patterns to apply:** #13 (inline warning before navigation)
**Effort:** S

#### `/eod` → `eod.html` (184 LOC, 1 test)
**Top wishlist (5):**
1. Progress bar for checklist
2. Visual celebration when all items checked
3. Mini-waste-summary widget
4. Sign-off history
5. Undo last close
**Defects:** no progress bar (P1)
**Patterns to apply:** #13 (inline warnings)
**Effort:** S

#### `/dashboard` → `dashboard.html` (152 LOC, 1 test) — **REDUNDANT with / (P0)**
**Top fix:** delete or rescope — currently duplicates `/` and `/analisis`. Recommend delete + redirect.
**Defects:** duplicate of / and /analisis (P0)
**Effort:** S

### 6.2 CATALOG (ingredients, products, recipes)

#### `/inventario` → `inventario.html` (292 LOC, 4 tests) — **GOLD STANDARD**
**Top wishlist (5):**
1. KPI tiles: Valor total, Consumo 7d (Gs.), Días de cobertura promedio, Ingredientes con foto
2. Quick actions: "+ Reposición rápida" (inline row), "Duplicar ingrediente"
3. Bulk select toolbar (Ajustar/Archivar/Exportar/Eliminar)
4. Saved views ("Mis críticos", "Sin gluten", "Alto costo", "Sin foto")
5. Inline alerts when ingredient drops below safety stock
**Defects:** "Ingredientes 415de24c" slug shown as name (P1); inconsistent icon family in row actions (P2)
**Patterns to apply:** this IS the reference — extract macros from here
**Effort:** M

#### `/inventario/nuevo` and `/inventario/{id}/editar` → `inventario_form.html` (144 LOC, 2 tests) — **GOLD STANDARD**
**Top wishlist (5):**
1. Diff view before save ("Stock actual: 100 → 105, Precio: 3000 → 3500")
2. Archive / Soft-delete button in danger zone
3. "View as JSON" for power users
4. Confirm dialog for Nombre change (warns about recipe impact)
5. Live cost preview "precio × stock = valor total"
**Defects:** native date picker still visible (D1)
**Patterns to apply:** #1, #6 (live preview), #7 (source attribution)
**Effort:** M

#### `/inventario/{id}` → `ingrediente_detalle.html` (387 LOC, 0 tests) — 4-quadrant pattern (GOLD STANDARD)
**Top wishlist (5):**
1. Sticky header with name + main actions
2. "Comprá más" CTA with one-click Lista de compras entry
3. Movimientos recent strip (last 3 inline, not just link)
4. Variantes quick toggle to set "preferida" inline
5. Recipe impact panel — click name to see full cost & yield
**Defects:** "Pronóstico" block shows `(sin consumo reciente)` with no CTA to fix (P0); Pronóstico block has `—` for días restantes when no data (P0)
**Patterns to apply:** #5 (derived tags block — already good)
**Effort:** M

#### `/inventario/{id}/movimientos` → `inventario_movimientos.html` (82 LOC, 0 tests)
**Top wishlist (5):**
1. KPI strip at top (Entradas/Salidas/Mermas/Ajustes + delta vs last period)
2. Type filter chips
3. Date range picker with presets
4. Per-row actions: Edit (with audit trail), Reverse, Print receipt
5. Bulk export as CSV/PDF
**Defects:** empty state has CTA but no entries currently
**Patterns to apply:** #1, #2, #16
**Effort:** M

#### `/productos` → `productos.html` (579 LOC, 0 tests)
**Top wishlist (5):**
1. Sin-TACC pill in row
2. Filter chip rail
3. Currency format unification (D3 — major)
4. Prime cost > 100% should be RED, not amber
5. Edit button column too far right (D2)
**Defects:** currency drift (D3, P0); prime cost color severity (P1)
**Patterns to apply:** #2, #11, #12
**Effort:** M

#### `/productos/nuevo` and `/productos/{id}/editar` → `producto_form.html` (508 LOC, 0 tests)
**Top wishlist:** margin live preview as price changes; "Etiquetas derivadas de receta" block; filter chip rail
**Defects:** no live margin preview (P1)
**Patterns to apply:** #6, #5
**Effort:** M

#### `/productos/importar` → `productos_importar.html` (113 LOC, 0 tests) — Excel import
**Patterns to apply:** #4 (empty state), #30 (save feedback)
**Effort:** S

#### `/recetas` → `recetas.html` (270 LOC, 6 tests, 53 tests passing) — **JUST SHIPPED Foto + Dificultad fix**
**Top wishlist (5):**
1. Filter chip rail
2. Sort headers with active highlight (P1)
3. Sin-TACC pill cluster
4. Yield column with "por porción" unit hint tooltip
5. Saved views
**Defects:** none currently open — recently hardened
**Patterns to apply:** #2, #24
**Effort:** M

#### `/recetas/nueva` and `/recetas/{id}/editar` → `receta_form.html` (1,149 LOC, 0 tests) — **MOST COMPLEX FORM**
**Top wishlist (5):**
1. Photo upload with crop/rotate
2. Video embed for technique (YouTube/Loom)
3. Version history with diff
4. Fork a recipe (clone with modifications)
5. Yield scaling beyond dropdown (free input)
**Defects:** P1 items include Escandallo total = Gs. 0 (server-side fix needed), CSRF token missing in form
**Patterns to apply:** #6 (live preview — already implemented but needs formalization)
**Effort:** L

#### `/recetas/{id}` → `receta_detalle.html` (329 LOC, 0 tests)
**Top wishlist (5):**
1. Pill cluster consistent with edit form
2. Print prep sheet
3. Fork from detail page
4. Scale by N
5. Cost-vs-yield trend chart
**Patterns to apply:** #5, #20
**Effort:** M

### 6.3 PRODUCTION

#### `/produccion` → `produccion.html` (452 LOC, 1 test)
**Top wishlist (5):**
1. Day-grid timeline view
2. Week view (7-day calendar)
3. Drag-to-reschedule
4. Per-batch timer
5. "Suficiente/Falta" already exists — formalize
**Defects:** day cards show only one recipe per day by default (P1)
**Patterns to apply:** #29, #12
**Effort:** L

#### `/produccion-planner` → `planner.html` (115 LOC, 1 test)
**Top wishlist (5):**
1. Multi-row planner (add receta many times, see total ingredients needed)
2. Date picker for tomorrow's production
3. Save plan as template ("Lunes de medialunas")
4. Compare to last week's plan
5. Print prep sheet
**Patterns to apply:** #6 (preview panel), #20
**Effort:** M

#### `/reorder` → `reorder.html` (184 LOC, 2 tests)
**Top wishlist (5):**
1. Supplier pre-fill from ingredient
2. PO auto-generation
3. Price comparison across suppliers
4. Source attribution ("Sugerido = max(mínimo, promedio_consumo_7d × lead_time) − actual")
5. Bulk create POs
**Defects:** "sin proveedor" should be red badge not italic (P1)
**Patterns to apply:** #3, #7, #14
**Effort:** M

### 6.4 ORDERS (additional)

#### `/pedidos/publico/{token}` → `pedido_publico.html` (128 LOC, 0 tests)
**Patterns to apply:** minimal — read-only view, customer-facing
**Effort:** S

#### `/wishlist` → `wishlist.html` (71 LOC, 1 test)
**Top wishlist:** aggregated KPI strip ("Gs. 50,000,000" in plain text is broken — P0); empty state CTA
**Defects:** plain-text KPIs (P0)
**Patterns to apply:** #4, #12
**Effort:** S

#### `/shopping-list` → `shopping_list.html` (124 LOC, 1 test)
**Top wishlist:** already has excellent empty state (preserve); add date range presets; source attribution
**Patterns to apply:** #1 (KPI delta), #7, #16
**Effort:** S

### 6.5 BANK / FINANZAS

#### `/bank` → `bank.html` (274 LOC, 4 test files, 61 tests) — **HARDENED (date, currency, CSV, pagination, reconciliation)**
**Top wishlist (5):**
1. Auto-matching (suggest matches by amount + counterparty)
2. Bulk reconciliation
3. Reconciliation reports
4. Reverse matching (orders without bank txns)
5. PDF export
**Defects:** source attribution OK; format_gs needs audit
**Patterns to apply:** #1 (KPI delta on top stats), #14 (bulk action bar)
**Effort:** M

#### `/reportes` → `reportes.html` (30 LOC, 0 tests) — index page
**Top wishlist:** category tabs (Ventas/Costos/Inventario/Clientes/Compliance/Operacional); search bar; per-card source attribution
**Defects:** 14 cards in flat grid (P1)
**Patterns to apply:** #9 (tabs), #22 (search), #7 (source)
**Effort:** M

#### All 12 `/reportes/*` sub-routes — list each:

| Page | LOC | Currency drift D3 | Other defects | Effort |
|---|---:|---|---|---|
| `reportes_diario.html` | 67 | ✅ | none | S |
| `reportes_iva.html` | 65 | ✅ | source attribution | S |
| `reportes_retencion.html` | 62 | ✅ | none | S |
| `reportes_metricas.html` | 143 | ✅ | none | M |
| `reportes_top_productos.html` | 62 | ✅ | "Producto cfaf4b47" leak (D6) | M |
| `reportes_libro_ventas.html` | 95 | ✅ | none | M |
| `reportes_cierre_mensual.html` | 164 | ✅ | label consistency | M |
| `reportes_precios.html` | 113 | ✅ | none | S |
| `reportes_comparacion.html` | 109 | ✅ | none | S |
| `reportes_metodos_pago.html` | 65 | ✅ | none | S |
| `reportes_ventas_hora.html` | 50 | ✅ | missing bar chart | S |
| `reportes_valor_pedido.html` | 49 | ✅ | none | S |

**Patterns to apply (all):** D3 (format_gs), #16 (date presets), #7 (source attribution), #22 (search)

#### `/analisis` → `analisis.html` (250 LOC, 2 tests)
**Top wishlist:** "Estrellas"/"Para revisar" cards need more contrast; "Promedio de ventas" needs bar chart; rotation block shows `0.0 kg / 0.0× / —` without explanation (P0)
**Defects:** rotation block empty state without CTA (P0)
**Patterns to apply:** #4 (empty state with CTA), #17 (bar chart), #3 (severity stripe)
**Effort:** M

#### `/riesgos` → `riesgos.html` (63 LOC, 0 tests) — **WORST EMPTY STATE IN SYSTEM (P0)**
**Top fix:** add list view + "Agregar riesgo" CTA + filter chips
**Defects:** renders only summary strip — no list (P0)
**Patterns to apply:** #4 (empty state), #2 (chips), #14 (bulk action bar)
**Effort:** M

#### `/auditoria` → `auditoria.html` (167 LOC, 2 tests)
**Top wishlist:** date range presets (already has chips but they're non-clickable — defect); IP/user filter; CSV/PDF export; severity stripe per row
**Defects:** chips non-clickable (P0); no export (P1)
**Patterns to apply:** #2 (chips — fix defect), #3 (severity), #7 (source), #20 (export)
**Effort:** M

### 6.6 CUSTOMERS / SUPPLIERS

#### `/clientes` → `clientes.html` (199 LOC, 1 test)
**Top wishlist:** filter chip rail; "0 visitas" vs "—" distinction (D5); action button too far right (D2); last-purchase-date column
**Defects:** D2 (P2), D5 (P1)
**Patterns to apply:** #2, #5 (0 vs —), #24 (sortable headers)
**Effort:** S

#### `/clientes/{id}` → `cliente_detalle.html` (137 LOC, 0 tests)
**Top wishlist:** four-quadrant card pattern (visitas / gasto total / puntos / tier); "Tier sugerido basado en visitas" derived block; sticky action cluster
**Defects:** no action buttons (Ver only) (P1)
**Patterns to apply:** #5, #8
**Effort:** S

#### `/clientes/{id}/editar` → `cliente_editar.html` (54 LOC, 0 tests)
**Patterns to apply:** #8 (sticky actions), #30 (save feedback)
**Effort:** S

#### `/suppliers` → `suppliers.html` (77 LOC, 1 test)
**Top wishlist:** filter chip rail (categoría + estado); bulk actions; KPI strip (total proveedores / activas / con deudas)
**Defects:** D2 action button placement (P2)
**Patterns to apply:** #2, #12, #14
**Effort:** S

#### `/supplier/nuevo` → `supplier_form.html` (48 LOC, 0 tests)
**Top wishlist:** RUC example callout; sticky action cluster
**Patterns to apply:** #8, #10 (ejemplo)
**Effort:** S

#### `/supplier/{id}/orders` → `supplier_orders.html` (85 LOC, 0 tests)
**Patterns to apply:** #22 (search), #16 (date presets)
**Effort:** S

### 6.7 PRICING / BENCHMARKS

#### `/pricing` → `pricing.html` (54 LOC, 0 tests)
**Top wishlist:** KPI strip with delta; "create a recipe first" cross-link empty state; channel filter chips
**Patterns to apply:** #4 (empty state), #12, #2
**Effort:** S

#### `/vs-mercado` → `benchmarks.html` (108 LOC, 0 tests) — **SHOWS 1 ROW INSTEAD OF 17 (P0)**
**Top fix:** fix data showing 1 row instead of 17
**Defects:** data display bug (P0)
**Patterns to apply:** #3 (severity stripe for above/below market), #4 (empty state)
**Effort:** M

#### `/vs-mercado/{id}/editar` → `benchmark_edit.html` (97 LOC, 0 tests)
**Patterns to apply:** #8 (sticky actions), #30
**Effort:** S

### 6.8 INSIGHTS (4 sub-pages in insights_stock, 4 in insights_derived)

All 8 insight pages are minimal placeholders. Pattern applies (different target each):
- `insight_stock.html` (50 LOC) — agregated KPI for stock health
- `insight_margenes.html` (63 LOC) — margin analysis
- `insight_margenes_detalle.html` (40 LOC) — per-product margin drill-down
- `insight_afinidades.html` (28 LOC) — product affinity matrix
- `insight_demand.html` (45 LOC) — demand forecasting
- `insight_food_cost.html` (35 LOC) — food cost variance
- `insight_freshness.html` (42 LOC) — ingredient freshness
- `insight_price_impact.html` (43 LOC) — price impact simulation

**Patterns to apply (all):** #12 (KPI cards), #17 (bar chart), #18 (period comparison)
**Effort:** M (per page)

### 6.9 WASTE / SETTINGS / USERS / MISC

#### `/merma` → `merma.html` (264 LOC, 1 test) — exemplary ejemplo callout (preserve)
**Top wishlist:** COSTE TOTAL tile needs breakdown by motivo; "Por receta / Por ingrediente" tab nav; KPI delta strip
**Patterns to apply:** #9 (tabs), #1, #3
**Effort:** M

#### `/settings` → `settings.html` (747 LOC, 1 test) — 4 tabs
**Top fix:** **P0 — first 3 tabs make the page 3125px tall on 1280px viewport** (worst scrolling in app). Add sticky in-page TOC.
**Defects:** long page (P0); Save button at bottom (P1); tooltip on placeholder-only fields (P1)
**Patterns to apply:** #8 (sticky actions), #27 (tooltips)
**Effort:** M

#### `/settings/catalog` → `settings_catalog.html` (956 LOC, 1 test) — biggest template by bytes
**Top fix:** same as /settings — add sticky TOC; more tabs to split
**Defects:** very long (P1)
**Effort:** M

#### `/users` → `users.html` (211 LOC, 0 tests)
**Patterns to apply:** #2 (filter chips), #8 (sticky)
**Effort:** S

#### `/login` → `login.html` (163 LOC, 1 test)
**Patterns to apply:** minimal — just a11y
**Effort:** S

#### `/forgot-password` → part of `auth.py` (no template)
**Effort:** S

#### `/excel` → `excel.html` (140 LOC, 3 tests)
**Patterns to apply:** #16 (date presets), #22 (search)
**Effort:** S

#### `/excel/mode-guidance` and `/excel/validate` → 36 + 68 LOC
**Effort:** S

#### `/guia` → `guia.html` (13 LOC) — VERY MINIMAL
**Top fix:** section anchors, search, "Cuándo leerla" column expansion
**Defects:** no search (P1)
**Patterns to apply:** #22 (search)
**Effort:** M

#### `/recibo` → `recibo.html` (144 LOC, 0 tests)
**Top wishlist:** thermal printer format; PDF export; email/SMS send
**Patterns to apply:** #20 (print)
**Effort:** S

#### `/ventas/historial` → `ventas_historial.html` (180 LOC, 1 test)
**Top wishlist:** filter chips (cliente / fecha / método de pago / producto); 0 vs — fix (D5); bulk actions (void / reprint)
**Patterns to apply:** #2, #5
**Effort:** M

#### `/creditos` → `creditos.html` (35 LOC, 0 tests)
**Patterns to apply:** #12 (KPI), #16 (date presets)
**Effort:** S

#### `/combo-smoke` → `dev_combo_smoke.html` (73 LOC, 0 tests) — dev page
**Effort:** — (skip)

#### `/ops/status` → `ops_status.html` (48 LOC, 0 tests)
**Effort:** S

#### `/healthz`, `/healthz/*`, `/admin/migrate` — backend infra, skip

### 6.10 ORPHAN / DEAD TEMPLATES

- `base.html` (309 LOC) — parent template, NOT orphan, just not in any `render()` call directly
- `delivery_zones.html` (38 LOC) — referenced in menu but no router? Investigate
- `produccion_calendario.html` (25 LOC) — referenced in menu but no router? Investigate

---

## 7. Priority ranking — top 15 actions (effort + impact)

| # | Action | Effort | Impact |
|---|---|---|---|
| 1 | **Extract 10 atomic macros** from `/inventario` + `/inventario/nuevo` into `app/components/atoms.html` | 3 days | High — unlocks everything else |
| 2 | **Fix D3 — currency format drift** with `format_gs` filter + CI lint | 0.5 day | P0 — recurring finance bug |
| 3 | **Fix the 5 broken/empty pages** (dashboard delete, ped stock-preview 500, riesgos, benchmarks, bank import) | 1 day | P0 — these are unusable |
| 4 | **Fix D6 — seed-name identifiers** (Spanish bakery names) | 0.5 day | P0 — designers stop tripping |
| 5 | **Roll out EmptyState macro** to 8 pages (Proveedores subpages, Riesgos, Wishlist, Bank, Pricing, Vs-mercado, Auditoría) | 1 day | High |
| 6 | **Roll out FilterChipRail macro** to 6 pages + **fix defect** on Auditoría | 1 day | P0 + defect |
| 7 | **Roll out AggregatedKpi macro** to 9 pages (fix Wishlist `Gs. 50,000,000` broken display) | 0.5 day | P0 |
| 8 | **Roll out DateRangePresets** to 8 pages | 0.5 day | High |
| 9 | **Roll out SideRailLivePreview** to 5 pages (Receta-editar already good, formalize) | 1 day | High |
| 10 | **Roll out StickyActionCluster** to 8 long forms | 0.5 day | High |
| 11 | **Roll out SeverityStripe** to 7 pages | 0.5 day | High |
| 12 | **Fix D5 — 0 vs — ambiguity** | 0.5 day | P1 |
| 13 | **Fix D1 — native date picker** (`<saskia-date>` web component) | 1 day | P1 — system prompt violation |
| 14 | **Apply 12 naming consistency dimensions** (voseo, Cliente, etc.) | 1 day | High |
| 15 | **Fix `/dashboard`** — delete and redirect to `/` | 0.25 day | P0 |

**Total: ~10 days for the top 15. Highest leverage first 4 = 5 days for biggest perceived quality jump.**

---

## 8. Personas — quick wins by hat

### Counter staff (speed)
- Wishlist page-local search (#22)
- Quick-action chips with category labels (`/ventas`)
- Filter chip rail (every list page)
- Sticky total bar (`/pedidos/nuevo`)
- Keyboard shortcuts

### Owner-finance (KPIs)
- Currency format unification (D3)
- KPI delta strip on every summary page
- Aggregated KPI cards (no plain-text `Gs. 50,000,000`)
- Margin > 100% should be RED not amber (`/productos`)
- Source attribution on every report

### Production-baker (planning)
- Multi-row planner (`/produccion-planner`)
- Day-grid timeline (`/produccion`)
- Recipe impact panel (`/ingrediente/{id}`)
- Print prep sheet (`/recetas/{id}`)
- Drag-to-reschedule

### New user (orientation)
- Empty state with onboarding CTA (every empty page — Riesgos is worst)
- Ejemplo callout on forms (Proveedor-nuevo, Receta-nueva, Clientes-nuevo)
- Help link in topnav
- First-time tooltip tour

### Auditor (traceability)
- Source attribution line on every table
- 0 vs — ambiguity fix (D5)
- Date range presets
- CSV/PDF export
- Audit log on every action

---

## 9. Open questions (for Ivan before next sprint)

1. **Should `/dashboard` be deleted?** Redundant with `/` and `/analisis`. Recommend: **delete + redirect**.
2. **Where should "today" KPIs live?** `/` (actionable) vs `/analisis` (strategic). Recommend: **split** — `/` = actionable, `/analisis` = strategic.
3. **Should recipes be the primary entity?** Currently productos + recetas are siblings under Catálogo. Recommend: **make recetas primary** in v2.
4. **Canonical filter rail pattern?** Currently 2 different patterns (`/inventario` = chips, `/productos` = dropdown). Recommend: **chips everywhere**.
5. **Should `/riesgos` ship before production?** Currently renders nothing. Recommend: **gate behind flag** if v1 is launching.
6. **`/delivery-zones` and `/produccion-calendario` are orphan templates** — are these dead routes or active but unlinked from menu?
7. **CI gate for format_gs?** Add `.github/workflows/ci.yml` lint step that fails if `Gs\. {{` appears in any template without the filter?

---

## 10. Lessons / pitfalls to apply

From the existing work + today's deploy:

1. **Docker build cache gotcha** — `app/` changes may be served from cached COPY layer. Always `docker build --no-cache` + verify by exec'ing into container. (Saved to `saskia-rms-deploy-flow` skill.)
2. **SQLite rejects `ADD COLUMN IF NOT EXISTS`** — use inspector-based try/except helpers.
3. **Tag algebra EN→ES** — `CANONICAL_DIETARY_TAGS` is Spanish, data sources emit English. Normalize at the read boundary + on the data path (migration).
4. **Migration data steps need fresh code** — if migration's recompute-via-inference ran before its code change shipped, the data is stale. Re-run the data step manually.
5. **`receta_form.html` is 1,149 LOC** — the single biggest template. Any change needs local manual QA + e2e `test_e2e_un_dia_en_la_panaderia.py` (287 LOC).
6. **Test investment correlates with audit depth** — bank has 61 tests (full regression), `recetas` has 53 tests, but `pedido_board` (the most complex list page at 335 LOC) has 0 tests.
7. **Format drift is invisible in unit tests** — D3 (Gs. 75 vs 75) only catches in screenshot review or end-to-end. Add a CI lint rule.

---

## Appendix A — File locations

- This document: `/opt/data/profiles/ivan/scratch/saskia-app-work/docs/upgrades/2026-09-29-UX-UPGRADE-PLAN.md`
- Source audits (still on disk):
  - `/tmp/designer-drop/README.md` — overview
  - `/tmp/designer-drop/REPORT.md` — route→template reference (52 KB)
  - `/tmp/designer-drop/audit-batch2-prod.md` — 14 pages
  - `/tmp/designer-drop/audit-batch3-reports.md` — 14 pages
  - `/tmp/designer-drop/cross-page-wishlist-consolidation.md` — top 30 patterns + top 10 macros
  - `/tmp/designer-drop/cross-cutting-consistency-audit.md` — 12 dimensions
  - `/tmp/designer-drop/ux-audit-2026-09-27.md` — 6 universal defects
  - `/tmp/saskia-ux-audit-drop-2026-09-27.zip` — full bundle + 82 screenshots

## Appendix B — Test coverage by page (heuristic — grep test files for URL paths)

Test files (143 found) were matched against their primary URL path. Pages without tests: `cliente_detalle`, `cliente_editar`, `inventario_movimientos`, `pedido_detalle`, `pedido_board`, `pedido_publico`, `recetas/{id}/editar`, `productos/*`, `settings_catalog`, `suppliers`, `supplier_form`, `supplier_orders`, `pricing`, `benchmarks`, `benchmark_edit`, `wishlist`, `riesgos`, `reportes/*` (most), `insight_*` (all 8), `recibo`, `creditos`, `login`, `users`, `dev_combo_smoke`, `ops_status`, `guia`, `reportes.html`.

**Heaviest tested pages:**
- `bank` — 4 test files, 61 tests
- `recetas` — 6 test files, 53 tests
- `inventario` — 4 test files, ~620 LOC of tests
- `pedidos` — 3 test files, ~340 LOC

**Pages with 0 test coverage** (gaps to address as part of upgrade):
- `pedido_board.html` — the most complex list page (335 LOC, 66 KB)
- `receta_form.html` — the most complex form (1,149 LOC)
- `receta_detalle.html` — recipe detail page
- `settings_catalog.html` — biggest template by bytes
- All 8 `insight_*` pages

---

*End of plan. 77 pages inventoried, 30 patterns catalogued, 10 macros identified, 6 universal defects flagged, 15-action priority list with effort estimates.*