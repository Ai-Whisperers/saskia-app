# Sazon/Saskia Reports + Analytics + Insights + Dashboard + Benchmarks + Cotizador Content Audit

**Generated:** 2026-10-07
**Scope:** Dashboard (2 pages) + Analisis (1) + Reports (16 pages) + Insights (8 pages) + Board (1) + Mercado (1) + Fiscal/Variance (2) + Benchmarks (2) + Cotizador (1) = 34 pages
**Source templates:** `app/templates/dashboard.html`, `inicio.html`, `analisis.html`, `reportes*.html`, `insight_*.html`, `board.html`, `evidencia_mercado.html`, `fiscal.html`, `food-cost-variance.html`, `benchmarks.html`, `benchmark_edit.html`, `cotizador.html`

---

## dashboard.html — Operator dashboard

### 1. Identity
- **URL/route**: `/` (root, also `/inicio`)
- **Page title**: `Dashboard — {{month_label}}`
- **Section**: BI / overview
- **User persona**: Operator, manager

### 2. Structure
- H1 (with svg icon): `Dashboard — {{month_label}}`
- Subtitle: `KPIs en vivo · datos del local`
- Empty state (when no data):
  - `<h2>Sin datos este mes todavía</h2>`
  - `<p>Registrá tu primera venta o cargá el catálogo para ver los KPIs en vivo.</p>`
  - Actions: `Registrar venta`, `Ver catálogo`
- KPI group sections (3): `Dinero`, `Actividad`, `Costos`
- Margin-deriva link: `<a href="/reportes/margenes">{{product_name}}</a>`
- Full-deriva link: `Ver deriva completa →`
- H2: `Recetas`
- H2 (with svg icon): `Receta más vendida`
- H2 (with svg icon): `Por canal de venta`
- Sales-by-channel table (headers: `Canal`, `Ingresos Gs.`)
- Empty: `Sin ventas este mes aún.`
- H2 (with svg icon): `Operación`
- Operation KPI cards: `Lista de Compras abiertas`, `Equipamiento pendiente`, `Riesgos activos`, `Comparativas de mercado` (with sub `vs competencia`)

### 3. All visible user-facing text

**Page-level messages:**
- `KPIs en vivo · datos del local`
- `Sin datos este mes todavía — Registrá tu primera venta o cargá el catálogo para ver los KPIs en vivo.`
- `Sin ventas este mes aún.`

**Button + link text:**
- `Registrar venta` (link to /ventas)
- `Ver catálogo` (link to /productos)
- `Ver deriva completa →` (link to /reportes/margenes)
- `Ver` (link to /reportes/margenes/{id})

**Section headings (h2):**
- `Recetas`
- `Receta más vendida` (with svg icon `#icon-recipe`)
- `Por canal de venta` (with svg icon `#icon-sale`)
- `Operación` (with svg icon `#icon-ops`)

**KPI group headings (h3):**
- `Dinero`
- `Actividad`
- `Costos`

**KPI card labels (with sub):**
- `Lista de Compras abiertas`
- `Equipamiento pendiente`
- `Riesgos activos`
- `Comparativas de mercado` (sub: `vs competencia`)

**Empty state aria:**
- `<section class="empty-state" role="status" aria-live="polite">` — semantic empty state

**Sample data display:**
- Sales-by-channel: `Canal` + `Ingresos Gs.` columns

### 4. Displayed data

**KPI cards (3 groups × N):**
- Dinero (cards)
- Actividad (cards)
- Costos (cards)

**Sales by channel:**
| Column | Semantics |
|---|---|
| `Canal` | channel name |
| `Ingresos Gs.` | Gs. revenue |

### 6. UX/copy audit — flags

- Empty state has CTAs (`Registrar venta` + `Ver catálogo`) — good.
- `Comparativas de mercado` with sub `vs competencia` — clear.
- `KPI` is English loan word used freely.
- Three KPI groups are color-coded via class names.

---

## inicio.html — Operator landing page

### 1. Identity
- **URL/route**: `/inicio` (also `/` redirect)
- **Page title**: (dynamic `{{ greeting() }}`)
- **Section**: Home / day overview
- **User persona**: Operator

### 2. Structure
- H1: `{{ greeting() }}` (Spanish greeting based on time of day)
- Band label: `Hoy`, `Loyalty`
- Insight cards (with `title="{{ insight.title }}"`)
- Card: `Acciones del día` (aria-label)
- H2: `Acciones del día`
- Per-action title: `Pedidos por confirmar`, `Reposiciones urgentes`, `Insumos por vencer (48 h)`, `Cierre de ayer`, `Merma del día`
- Action sub-status: `pendiente`, `registrada ✓`
- Card: `Plan de mañana` (aria-label)
- H2: `Plan de mañana`
- Small: `sugerido por ventas`
- Link: `Detalles y ajustes en <a href="/produccion">Producción →</a>`
- Empty: `Sin plan todavía — Se calcula con tus ventas.`
- Card CTA: `Ver Producción`
- Card: `Pronóstico — {{label}} {{date}}`
- Confidence pills: `alta` (sev-pill saludable), `media` (aviso), `baja` (critico)
- Metric labels: `Unidades estimadas`, `Ingreso estimado`
- Forecast table (headers: `Producto`, `Cant. estimada`, `Ingreso`)
- Link: `Ver plan completo de mañana →`
- Empty: `Sin datos suficientes — Necesitamos ~4 semanas de ventas en este día para pronosticar.`
- Card CTA: `Ver producción`
- Card: `Clientes habituales` (aria-label)
- H2: `Clientes habituales`
- Small: `últimos 30 días · 2+ visitas`
- Per row title: `Crear pedido nuevo para {{name}}`
- Link: `Ver los {{regulars_count_total}} habituales →`
- Empty: `Sin habituales aún — Aparecen acá cuando un cliente vuelve 2+ veces en 30 días.`
- Card CTA: `Ver clientes`
- Card: `Alertas` (aria-label)
- H2: `Alertas`
- Severity pills: `Crítico` (sev-pill critico), `Aviso` (sev-pill aviso)
- Alert links: `Reponer →`, `Renovar →`, `Completar →`
- Link: `Ver todos los avisos ({{avisos_total}}) →`
- Period label: `Período:`
- Empty: `Los gráficos aparecen con tu primera venta — Ventas por hora, tendencia de 30 días y formas de pago se dibujan solos.`
- CTA: `Registrar venta`
- Band label: `Análisis · últimos 30 días`
- Teaser labels: `Clasificación de productos`, `Márgenes a la baja`, `Reportes completos`
- Teaser sub-labels: `Stars y Dogs por margen y volumen →`, `Productos perdiendo margen por costos →`, `Fiscales, ventas, costos e inventario →`
- H2: `Ranking de productos · período seleccionado`
- Ranking table (headers: `Producto`, `Ventas (Gs.)`, `Margen (Gs.)`, `Margen %`, `Cantidad vendida`)
- Empty: `Sin ventas todavía — registrá tu primera venta`
- H2 (with svg icon): `Operación (cola de tareas)`
- Small: `Lo que necesita tu atención`
- Metric labels: `Lista de compras abierta`, `Equipamiento pendiente`, `Riesgos activos`
- Links: `Ver lista` (×2), `Ver riesgos`
- Section: `Todos los avisos` (aria-label)
- H2: `Avisos`
- Per-aviso text: `Receta sin precio de ingrediente: <strong>{{name}}</strong>. Cargá los precios para ver el costo — editar receta →`
- Av ellipsis: `… y {{more}} recetas más sin costo — ver recetas`
- Per-aviso: `Venta sin receta: <strong>{{product_name}}</strong> ({{sold_at_str}}). Asignale una receta para ver el margen — ver productos →`

### 3. Displayed data

**Acciones del día:**
| Action | Sub-status |
|---|---|
| `Pedidos por confirmar` | (count) |
| `Reposiciones urgentes` | (count) |
| `Insumos por vencer (48 h)` | (count) |
| `Cierre de ayer` | `pendiente` |
| `Merma del día` | `registrada ✓` |

**Pronóstico:**
| Metric | Semantics |
|---|---|
| `Unidades estimadas` | forecast qty |
| `Ingreso estimado` | forecast Gs. |

**Forecast table:**
| Column | Semantics |
|---|---|
| `Producto` | product name |
| `Cant. estimada` | forecast units |
| `Ingreso` | forecast Gs. |

**Ranking de productos:**
| Column | Semantics |
|---|---|
| `Producto` | product name |
| `Ventas (Gs.)` | revenue |
| `Margen (Gs.)` | margin Gs. |
| `Margen %` | margin % |
| `Cantidad vendida` | total qty |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Insight cards | `{{ insight.title }}` |
| Cliente habitual crear pedido | `Crear pedido nuevo para {{name}}` |

### 6. UX/copy audit — flags

- `greeting()` function — dynamic Spanish greeting (Buenos días / Buenas tardes / Buenas noches).
- Multiple empty states — each with CTA.
- Severity pills: `Crítico` (red), `Aviso` (yellow), `saludable` (green) — 3-tier system.
- Teaser cards link to deeper reports — good navigation.

---

## analisis.html — Análisis overview

### 1. Identity
- **URL/route**: `/analisis`
- **Page title**: `Análisis · los últimos 30–90 días`
- **Section**: BI / analysis
- **User persona**: Manager, owner

### 2. Structure
- H1: `Análisis · los últimos 30–90 días`
- Band label: `Costo de materia prima (Semáforo)`
- Semaforo title: `{{ semaforo_title }}` (h5)
- Empty: `No hay suficientes ventas en el período`
- Band label: `Panorama`
- H2 (with svg icon `#icon-warn`): `Alerta: margen cayendo`
- Small: `Productos cuyo margen cayó por suba de precio de ingredientes`
- Table (headers: `Producto`, `Ingrediente`, `Precio viejo`, `Precio nuevo`, `Δ Margen`)
- Per-row badge: `↓ {{pct}}%` (badge-danger) or `—`
- H2 (with svg icon `#icon-sale`): `Productos más rentables (últimos 30 días)`
- Small: `Ordenados por ganancia absoluta`
- Table (headers: `Producto`, `Cantidad vendida`, `Ventas (Gs.)`, `Margen (Gs.)`, `Margen %`)
- Per-row badge: 3-tier based on pct
- H2 (with svg icon `#icon-inventory`): `Costo concentrado en pocos ingredientes`
- Small: `Últimos 90 días · donde se va tu plata`
- Description: `Los 5 ingredientes más usados representan {{share}}% del costo total (90 días).`
- Table (headers: `Ingrediente`, `Costo anualizado (Gs.)`, `% del total`)
- H2 (with svg icon `#icon-chart`): `Promedio de ventas por día de la semana`
- Small: `Últimos 90 días · para planificar producción`
- Table (headers: `Día`, `Ventas promedio (Gs.)`, `Pedidos`)
- H2 (with svg icon `#icon-reorder`): `Rotación de stock (últimos 30 días)`
- Small: `Cuántas veces se renovó el stock de los ingredientes más activos`
- Table (headers: `Ingrediente`, `Consumido`, `Rotación`, `Días de stock`)
- Per-row badges: `{{days}} días` (badge-danger if ≤3, badge-warn if ≤7)
- H2 (with svg icon `#icon-recipe`): `Recetas más complejas`
- Small: `Más ingredientes y más tiempo de preparación`
- Table (headers: `Receta`, `Ingredientes`, `Costo/porción (Gs.)`, `Prep (min)`)

### 3. Displayed data

**Alerta: margen cayendo:**
| Column | Semantics |
|---|---|
| `Producto` | product name + link |
| `Ingrediente` | ingredient |
| `Precio viejo` | old price Gs. |
| `Precio nuevo` | new price Gs. |
| `Δ Margen` | margin delta + badge |

**Productos más rentables:**
| Column | Semantics |
|---|---|
| `Producto` | product name + link |
| `Cantidad vendida` | qty |
| `Ventas (Gs.)` | revenue |
| `Margen (Gs.)` | margin Gs. |
| `Margen %` | pct (3-tier badge: ok/warn/danger) |

**Costo concentrado:**
| Column | Semantics |
|---|---|
| `Ingrediente` | name + link |
| `Costo anualizado (Gs.)` | annualized cost |
| `% del total` | share % |

**Ventas por día de la semana:**
| Column | Semantics |
|---|---|
| `Día` | weekday |
| `Ventas promedio (Gs.)` | avg |
| `Pedidos` | count |

**Rotación de stock:**
| Column | Semantics |
|---|---|
| `Ingrediente` | name + link |
| `Consumido` | qty consumed |
| `Rotación` | ratio |
| `Días de stock` | days + badge |

### 6. UX/copy audit — flags

- 3-tier margin badges use thresholds 50% / 25% — operator can see at a glance.
- 3-tier stock-days badges use ≤3 / ≤7 — clear thresholds.
- Semaforo title (`semaforo_title`) is dynamic.
- `donde se va tu plata` — colloquial Spanish; friendly.
- `Δ` symbol used in column header — operator must know what it means.

---

## reportes.html — Reports index

### 1. Identity
- **URL/route**: `/reportes`
- **Page title**: `Reportes`
- **Section**: BI / index
- **User persona**: Manager, owner

### 2. Structure
- H1
- Subtitle: `Reportes financieros y operativos. Cada reporte tiene un botón de exporte PDF y filtros por fecha.`
- Per-report H3: `{{ entity_name }}`

### 3. Displayed data

(Reports index — links to all reports)

### 6. UX/copy audit — flags

- The index has H3 entries per report card.

---

## reportes_diario.html — Daily report

### 1. Identity
- **URL/route**: `/reportes/diario`
- **Page title**: `Reporte diario`
- **Section**: BI / finance
- **User persona**: Manager

### 2. Structure
- H1
- Metric labels: `Ingresos netos (Gs.)`, `IVA`, `COGS`, `Gastos`, `Ventas`, `Margen bruto`
- Filter: `Fecha`

### 4. Displayed data

| Metric | Semantics |
|---|---|
| `Ingresos netos (Gs.)` | net revenue |
| `IVA` | tax |
| `COGS` | cost of goods sold |
| `Gastos` | expenses |
| `Ventas` | sale count |
| `Margen bruto` | gross margin |

### 6. UX/copy audit — flags

- `COGS` is English (Cost of Goods Sold) — not localized.
- Standard daily P&L summary.

---

## reportes_metricas.html — Metrics overview

### 1. Identity
- **URL/route**: `/reportes/metricas`
- **Page title**: `Métricas`
- **Section**: BI
- **User persona**: Manager

### 2. Structure
- H1
- Filter form: `Desde`, `Hasta`, submit `Ver métricas`, link `Últimos 30 días`
- H2: `Métodos de pago`
- Table (headers: `Método`, `Ventas`, `Total (Gs.)`, `%`)
- Card: `Hora pico`
- Empty: `Sin datos`
- Card: `Día pico`
- Empty: `Sin conteo específico`
- Card: `Retención de clientes`
- Metric labels: `Total`, `Nuevos`, `Recurrentes`
- Empty: `Sin datos`

### 4. Displayed data

**Métodos de pago:**
| Column | Semantics |
|---|---|
| `Método` | payment method |
| `Ventas` | count |
| `Total (Gs.)` | total Gs. |
| `%` | share |

**Retención:**
| Metric | Semantics |
|---|---|
| `Total` | total customers |
| `Nuevos` | new customers |
| `Recurrentes` | recurring |

### 6. UX/copy audit — flags

- "Hora pico" / "Día pico" — operator-friendly terms.
- 3 retention metrics cover basic CRM.

---

## reportes_top_productos.html — Top products ranking

### 1. Identity
- **URL/route**: `/reportes/top-productos`
- **Page title**: `Top productos`
- **Section**: BI / products
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Ranking de productos por revenue en el período seleccionado.`
- Filter: `Desde`, `Hasta`, `Cantidad`, submit `Ver`
- Table (headers: `Producto`, `Unidades vendidas`, `Revenue (Gs.)`)
- Empty: `No hay ventas registradas — Cuando registres ventas van a aparecer acá.`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Producto` | product name |
| `Unidades vendidas` | qty |
| `Revenue (Gs.)` | revenue |

### 6. UX/copy audit — flags

- "Revenue" English loan word.

---

## reportes_precios.html — Price events

### 1. Identity
- **URL/route**: `/reportes/precios`
- **Page title**: `Precios`
- **Section**: BI / pricing
- **User persona**: Manager

### 2. Structure
- H1
- Export button: `Exportar CSV`
- Back link: `← Todos los ingredientes`
- Per-ingredient detail: H2 `{{ ingredient.name }}`
- Metric label: `Actual`
- H3: `Eventos`
- Table (headers: `Fecha`, `Precio`, `Origen`)
- Empty: `Sin eventos de precio en los últimos {{days}} días.`
- Top-level table (headers: `Ingrediente`, `Actual`, `Mínimo`, `Máximo`, `Promedio`, `Último cambio`)
- Action: `Ver detalle`
- Empty: `Todavía no hay precios cargados. Registrá una reposición desde Reponer stock o editá un ingrediente en el inventario.`

### 4. Displayed data

**Eventos table:**
| Column | Semantics |
|---|---|
| `Fecha` | event date |
| `Precio` | price Gs. |
| `Origen` | source |

**Aggregate table:**
| Column | Semantics |
|---|---|
| `Ingrediente` | name + link |
| `Actual` | current price |
| `Mínimo` | min over period |
| `Máximo` | max over period |
| `Promedio` | avg |
| `Último cambio` | date of last change |

### 6. UX/copy audit — flags

- CSV export button is explicit.
- Empty state guides operator to /reorder or /inventario.

---

## reportes_ventas_hora.html — Sales by hour

### 1. Identity
- **URL/route**: `/reportes/ventas-hora`
- **Page title**: `Ventas por hora`
- **Section**: BI / time-of-day
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Cantidad de ventas por cada hora (0–23). Útil para planificar personal y producción.`
- Highlight: `Hora pico: <strong>{{peak_hour}}</strong>`
- H2: heatmap grid (`role="table"`, `aria-label="Mapa de calor ventas por día y hora"`)
- Per-cell title: `{{weekday}} {{hour}} — {{count}} venta(s)`
- H2: `Detalle por hora`
- Table (headers: `Hora`, `Ventas`, `Barra`)
- Empty: `No hay ventas registradas`

### 4. Displayed data

**Heatmap:**
- Rows = weekdays, Cols = hours
- Cell color = intensity (heatmap)
- Tooltip shows count

**Tabla:**
| Column | Semantics |
|---|---|
| `Hora` | HH:00 |
| `Ventas` | count |
| `Barra` | bar chart |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Heatmap cell | `{{weekday}} {{hour}} — {{count}} venta(s)` |

### 6. UX/copy audit — flags

- Heatmap is highly visual — accessible via aria-label + per-cell tooltips.
- "Hora pico" — operator-friendly summary.

---

## reportes_valor_pedido.html — AOV (average order value)

### 1. Identity
- **URL/route**: `/reportes/valor-pedido`
- **Page title**: `Valor promedio del pedido (AOV)`
- **Section**: BI / KPIs
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Revenue total dividido por cantidad de ventas. Indicador clave para entender el ticket promedio.`
- Filter: `Desde`, `Hasta`, `Ver`
- Metric label: `Valor promedio del pedido (AOV)`
- Sub-label: `Gs. por venta en el período`
- Empty: `No hay ventas registradas — Cuando registres ventas va a aparecer el promedio.`

### 4. Displayed data

| Metric | Semantics |
|---|---|
| `Valor promedio del pedido (AOV)` | average Gs. per sale |

### 6. UX/copy audit — flags

- `AOV` acronym explained inline (`Revenue total dividido por cantidad de ventas`).
- Good explanatory copy.

---

## reportes_retencion.html — Customer retention

### 1. Identity
- **URL/route**: `/reportes/retencion`
- **Page title**: `Retención`
- **Section**: BI / CRM
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Clientes nuevos vs recurrentes en el período seleccionado.`
- Filter: `Desde`, `Hasta`, `Ver`
- Metric labels: `Total clientes`, `Nuevos`, `Recurrentes`
- Empty: `No hay datos — No hay clientes con ventas en este período.`

### 4. Displayed data

| Metric | Semantics |
|---|---|
| `Total clientes` | total in period |
| `Nuevos` | new customers |
| `Recurrentes` | returning |

### 6. UX/copy audit — flags

- Three-metric retention summary.

---

## reportes_cierre_mensual.html — Monthly close

### 1. Identity
- **URL/route**: `/reportes/cierre-mensual?year=YYYY&month=MM`
- **Page title**: `Cierre mensual — {{period_label}}`
- **Section**: BI / finance
- **User persona**: Manager, accountant

### 2. Structure
- H1
- Pagination nav (aria-label `Navegación de mes`): `← Mes anterior`, `Mes siguiente →`
- Metric labels: `Ventas totales`, `IVA ventas`, `Prime Cost`, `Margen neto`
- Top product highlight: `<strong>Producto estrella:</strong> {{top_product}}`
- H2: `Detalle por línea`
- Table (headers: `Línea`, `Cantidad`, `Ventas (Gs.)`, `IVA (Gs.)`, `Materiales`, `Mano de obra`, `Overhead`, `Prime Cost`, `Margen`, `Margen %`)
- Total row: `TOTAL`
- Notes (explanation block):
  - `<em>Mano de obra</em> es 0 para recetas sin tiempo declarado (la mayoría). Configurá en cada receta cuando lo sepas.`
  - `<em>Overhead</em> es {{pct}}% del costo de materiales (config en Configuración).`
  - `IVA incluye solo Facturas (no Boletas Resimple). Para el IVA débito fiscal completo, usá /reportes/iva.`
  - `Margen saludable: > 30% del precio de venta. Por debajo de 15%, el producto no cubre sus costos reales.`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Línea` | product line |
| `Cantidad` | qty |
| `Ventas (Gs.)` | revenue |
| `IVA (Gs.)` | VAT |
| `Materiales` | material cost |
| `Mano de obra` | labor cost |
| `Overhead` | overhead cost |
| `Prime Cost` | sum of materials + labor |
| `Margen` | margin Gs. |
| `Margen %` | margin % |

### 6. UX/copy audit — flags

- 4 explanation blocks clarify the report — operator can interpret.
- `Boleta Resimple` (Paraguayan tax) referenced — appropriate.
- "Margen saludable > 30%" — operator-friendly thresholds.
- "Prime Cost" English loan word used freely.

---

## reportes_iva.html — IVA report

### 1. Identity
- **URL/route**: `/reportes/iva`
- **Page title**: `IVA`
- **Section**: BI / tax (Paraguay)
- **User persona**: Manager, accountant

### 2. Structure
- H1
- Subtitle: `IVA 10% (Paraguay) — todos los precios son IVA incluido.`
- Metric label: `Acumulado del año (YTD)`
- Display: `Ventas: {{n}}`, `Base imponible: {{m.gs(total_base)}}`, `IVA 10%: {{m.gs(total_iva)}}`, `Total: <strong>{{m.gs(total_gross)}}</strong>`
- Table (headers: `Mes`, `Ventas`, `Gravado (Gs.)`, `IVA 10% (Gs.)`, `Total (Gs.)`)
- Empty: `No hay ventas registradas — Cuando registres ventas van a aparecer acá mes por mes.`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Mes` | month label |
| `Ventas` | sale count |
| `Gravado (Gs.)` | taxable base |
| `IVA 10% (Gs.)` | VAT |
| `Total (Gs.)` | gross total |

### 6. UX/copy audit — flags

- Clear subtitle: `IVA 10% (Paraguay) — todos los precios son IVA incluido.`
- YTD summary + per-month table.
- Uses Paraguay-specific terminology: `Gravado`, `Base imponible`.

---

## reportes_libro_ventas.html — Sales ledger (SET format)

### 1. Identity
- **URL/route**: `/reportes/libro-ventas`
- **Page title**: `Libro de ventas`
- **Section**: BI / accounting
- **User persona**: Manager, accountant

### 2. Structure
- H1
- Subtitle: `Libro registro cronológico de ventas conforme al formato SET (Paraguay).`
- Filter form: `Desde`, `Hasta`, label `&nbsp;`
- Quick links label: `Accesos rápidos:`
- Buttons: `Hoy`, `Esta semana`, `Este mes`, `Mes pasado`
- Table (headers: `Fecha`, `Cliente`, `Producto`, `Cant.`, `Gravado (Gs.)`, `IVA (Gs.)`, `Total (Gs.)`, `Comprobante`, `RUC`, `Reembolso (Gs.)`, `Neto (Gs.)`)
- Per-row: invoice_type badge (badge-info), refund cell (text-warning title `{{n}} reembolso(s)`)
- Total row: `<strong>Total periodo</strong>`
- Empty: `No hay ventas en este período — Probá con un rango de fechas más amplio.`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Fecha` | sale date |
| `Cliente` | customer name |
| `Producto` | product name |
| `Cant.` | qty |
| `Gravado (Gs.)` | taxable base |
| `IVA (Gs.)` | VAT |
| `Total (Gs.)` | gross |
| `Comprobante` | invoice_type |
| `RUC` | customer RUC |
| `Reembolso (Gs.)` | refund amount |
| `Neto (Gs.)` | net |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Reembolso warning | `{{n}} reembolso(s)` |

### 6. UX/copy audit — flags

- `SET` acronym = Servicio de Impuestos Internos (Paraguayan tax authority).
- Quick presets (`Hoy`, `Esta semana`, `Este mes`, `Mes pasado`) — operator-friendly.
- 11 columns — wide table.

---

## reportes_metodos_pago.html — Payment methods

### 1. Identity
- **URL/route**: `/reportes/metodos-pago`
- **Page title**: `Métodos de pago`
- **Section**: BI
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Cantidad de ventas y total facturado por cada método de pago.`
- Filter: `Desde`, `Hasta`, `Ver`
- Metric label: `Total general`
- Table (headers: `Método de pago`, `Cantidad de ventas`, `Total facturado (Gs.)`, `Reembolsos (Gs.)`, `Neto (Gs.)`)
- Empty: `No hay ventas registradas`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Método de pago` | method |
| `Cantidad de ventas` | count |
| `Total facturado (Gs.)` | gross |
| `Reembolsos (Gs.)` | refunds |
| `Neto (Gs.)` | net |

### 6. UX/copy audit — flags

- Per-method breakdown with refunds and net.

---

## reportes_consumo.html — Consumption report

### 1. Identity
- **URL/route**: `/reportes/consumo?days=N`
- **Page title**: `Consumo`
- **Section**: BI / inventory
- **User persona**: Manager

### 2. Structure
- H1
- Day filters: `{{d}}d` buttons (7d, 14d, 30d, etc.)
- Export: `Exportar CSV`
- Table (headers: `Ingrediente`, `Cantidad neta`, `Ventas`, `Movimientos`)
- Per-row: `<a href="/inventario/{id}">{{name}}</a>`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Ingrediente` | name + link |
| `Cantidad neta` | net qty consumed |
| `Ventas` | sale count |
| `Movimientos` | stock movements |

### 6. UX/copy audit — flags

- Quick day filters in toolbar.
- CSV export.

---

## reportes_mermas_cost.html — Waste cost report

### 1. Identity
- **URL/route**: `/reportes/mermas-cost`
- **Page title**: `Costo de mermas`
- **Section**: BI / waste
- **User persona**: Manager

### 2. Structure
- H1
- Hint paragraph
- Filter label
- Hint paragraph
- Table (headers: `Ingrediente`, `Unidad`, `Eventos`, `Costo total ₲`, `Costo promedio / evento ₲`, `Acción`)
- Empty: `No hay mermas en este período`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Ingrediente` | name |
| `Unidad` | unit (kg, l, und) |
| `Eventos` | event count |
| `Costo total ₲` | total cost |
| `Costo promedio / evento ₲` | avg cost per event |
| `Acción` | link to detail |

### 6. UX/copy audit — flags

- Uses `₲` Unicode symbol (inconsistent with `Gs.` in most reports).

---

## reportes_comparacion.html — Period comparison

### 1. Identity
- **URL/route**: `/reportes/comparacion`
- **Page title**: `Comparación de períodos`
- **Section**: BI
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Compara ventas, cantidad de operaciones y margen entre dos períodos.`
- Form legends: `Período 1 (más reciente)`, `Período 2 (anterior)`
- Labels: `Desde`, `Hasta` (×2)
- Submit: `Comparar`
- Metric labels: `Período 1 — Ingresos`, `Período 2 — Ingresos`
- H3: `Cambios`
- Table (headers: `Métrica`, `Período 1`, `Período 2`, `Cambio %`)
- Per-row metric: `Ingresos`, `Cantidad de ventas`, `Margen bruto`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Métrica` | metric name |
| `Período 1` | recent value |
| `Período 2` | prior value |
| `Cambio %` | delta % |

### 6. UX/copy audit — flags

- Comparison form has two periods with legends.
- Clear which period is "más reciente" (Period 1).

---

## insight_afinidades.html — Product affinity

### 1. Identity
- **URL/route**: `/reportes/afinidades` or `/insight/afinidades`
- **Page title**: `Afinidades de productos`
- **Section**: AI insights
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Productos que se venden juntos (misma canasta: ventas dentro de 2 horas). Útil para combos y para el pedido sugerido.`
- Table (headers: `#`, `Producto A`, `Producto B`, `Canastas juntas`)
- Per-row: link to product
- Empty: `Todavía no hay canastas con 2+ productos. Registrá ventas de combos para ver afinidades.`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `#` | rank |
| `Producto A` | product A + link |
| `Producto B` | product B + link |
| `Canastas juntas` | count |

### 6. UX/copy audit — flags

- Methodology in subtitle: `ventas dentro de 2 horas`.
- Empty state guides them to register combo sales.

---

## insight_demand.html — Demand forecast

### 1. Identity
- **URL/route**: `/insight/demand`
- **Page title**: `Demanda prevista (mañana)`
- **Section**: AI insights
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Promedio 56d × factor del día × tendencia 14d. Batches = unidades ÷ rinde de receta.`
- Table (headers: `Producto`, `Prom/día`, `Factor día`, `Tendencia`, `Previsto`, `Batches`)
- Empty: `Sin historial suficiente (mínimo 3 ventas por producto en 56 días).`
- H2: `Lista de compras sugerida`
- Table (headers: `Insumo`, `Necesario`, `Stock`, `Comprar`, `Costo est.`)
- Empty: `Stock cubre la producción prevista. 🎉`

### 4. Displayed data

**Forecast table:**
| Column | Semantics |
|---|---|
| `Producto` | product name |
| `Prom/día` | 56d avg |
| `Factor día` | day-of-week factor |
| `Tendencia` | 14d trend |
| `Previsto` | forecast qty |
| `Batches` | units ÷ recipe yield |

**Shopping list:**
| Column | Semantics |
|---|---|
| `Insumo` | name |
| `Necesario` | needed |
| `Stock` | on hand |
| `Comprar` | gap |
| `Costo est.` | cost Gs. |

### 6. UX/copy audit — flags

- Methodology in subtitle explains math.
- `🎉` emoji in empty success state.

---

## insight_food_cost.html — Theoretical vs actual cost

### 1. Identity
- **URL/route**: `/insight/food-cost`
- **Page title**: `Costo teórico vs real ({{days}} días)`
- **Section**: AI insights
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Teórico = ventas × costo de receta. Real = movimientos de stock + merma. La brecha = porciones extra, merma no registrada o faltantes.`
- Metric cards: `Teórico`, `Uso real`, `Merma`, `Varianza`
- Filter: `Días` (number input, min=1, max=365)
- Submit: `Recalcular`
- Table (headers: `Producto`, `Cant. vendida`, `Costo teórico`)

### 4. Displayed data

| Metric | Semantics |
|---|---|
| `Teórico` | theoretical cost Gs. |
| `Uso real` | actual usage Gs. |
| `Merma` | waste cost Gs. |
| `Varianza` | gap Gs. |

### 6. UX/copy audit — flags

- Methodology clearly explained.
- Variance card surfaces the actionable insight.

---

## insight_freshness.html — Ingredient freshness

### 1. Identity
- **URL/route**: `/insight/freshness`
- **Page title**: `Frescura de insumos`
- **Section**: AI insights
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Días hasta vencer según vida útil − fecha del último registro de precio (aprox. sin lotes).`
- H2: `🔥 Cociná HOY para rescatar`
- Table (headers: `Insumo`, `Estado`, `Días`, `Valor en riesgo`)
- Per-row badges: `PRONTO` (badge), `sin datos` (text-muted)

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Insumo` | name |
| `Estado` | urgency |
| `Días` | days remaining |
| `Valor en riesgo` | Gs. at risk |

### 6. UX/copy audit — flags

- "🔥 Cociná HOY para rescatar" — emotive CTA to reduce waste.

---

## insight_margenes.html — Margin drift

### 1. Identity
- **URL/route**: `/insight/margenes`
- **Page title**: `Deriva de márgenes`
- **Section**: AI insights
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Precio de venta observado (primera vs última venta del período) contra el costo de receta actual. Márgenes que bajan = costo subiendo más rápido que el precio.`
- Filter label: `Período` (sr-only)
- Options: `Últimos 7 días`, `Últimos 30 días`, `Últimos 90 días`, `Últimos 180 días`
- Sort label: `Ordenado: peor margen primero`
- Table (headers: `Producto`, `Precio inicial`, `Precio actual`, `Margen inicial`, `Margen actual`)
- Per-row: badge-danger or badge-ok for margin change

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Producto` | product name + link |
| `Precio inicial` | first-sale price |
| `Precio actual` | last-sale price |
| `Margen inicial` | first-period margin |
| `Margen actual` | current margin |

### 6. UX/copy audit — flags

- Methodology in subtitle.
- 4 period options — common set.
- Per-row badges (badge-danger/badge-ok).

---

## insight_margenes_detalle.html — Margin detail (per product)

### 1. Identity
- **URL/route**: `/insight/margenes/{product_id}`
- **Page title**: `{{name}} — historial de precios`
- **Section**: AI insights
- **User persona**: Manager

### 2. Structure
- H1
- Subtitle: `Precio de venta observado por día (última venta del día).`
- Filter label: `Período` (sr-only)
- Options: `Últimos 30 días`, `Últimos 60 días`, `Últimos 90 días`, `Últimos 180 días`, `Último año`
- Back link: `← Todos los márgenes`
- Table (headers: `Día`, `Precio de venta`)
- Empty: `Sin ventas registradas en el período.`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Día` | date |
| `Precio de venta` | price Gs. |

### 6. UX/copy audit — flags

- 5 period options including yearly.

---

## insight_price_impact.html — Price impact analysis

### 1. Identity
- **URL/route**: `/insight/price-impact?ingredient=...`
- **Page title**: `Impacto: {{ingredient_name}}`
- **Section**: AI insights
- **User persona**: Manager

### 2. Structure
- H1
- H2: `Recetas afectadas ({{count}})`
- Table (headers: `Receta`, `Δ costo por unidad`)
- Per-row: link to recipe
- Empty: `Ninguna receta cambia de forma significativa.`
- H2: `Productos bajo objetivo (33%)`
- Table (headers: `Producto`, `Food cost %`, `Precio sugerido`)
- Empty: `Ningún producto cruza el objetivo. ✅`

### 4. Displayed data

**Recetas afectadas:**
| Column | Semantics |
|---|---|
| `Receta` | name + link |
| `Δ costo por unidad` | delta Gs. |

**Productos bajo objetivo:**
| Column | Semantics |
|---|---|
| `Producto` | name |
| `Food cost %` | % |
| `Precio sugerido` | suggested price Gs. |

### 6. UX/copy audit — flags

- Goal is `33%` (industry-standard food cost) — fixed threshold.
- ✅ emoji in empty success state.

---

## insight_stock.html — Dead stock / rotation

### 1. Identity
- **URL/route**: `/insight/stock`
- **Page title**: `Rotación y stock muerto`
- **Section**: AI insights
- **User persona**: Manager

### 2. Structure
- H1
- H2: `💀 Stock muerto`
- Table (headers: `Insumo`, `Stock`, `Días sin consumo`, `Último consumo`)
- Per-row: link to ingredient
- H2: `🔄 Rotación (más lento primero)`
- Table (headers: `Insumo`, `Consumo {{days}}d`, `Stock prom.`, `Rotación`, `Días de stock`)
- Per-row: link to ingredient
- Empty: `Sin consumo registrado en el período.`

### 4. Displayed data

**Stock muerto:**
| Column | Semantics |
|---|---|
| `Insumo` | name + link |
| `Stock` | on hand |
| `Días sin consumo` | days idle |
| `Último consumo` | last used date |

**Rotación:**
| Column | Semantics |
|---|---|
| `Insumo` | name + link |
| `Consumo {{days}}d` | qty consumed |
| `Stock prom.` | avg stock |
| `Rotación` | ratio |
| `Días de stock` | days remaining |

### 6. UX/copy audit — flags

- Two tables: dead stock vs slow rotation.
- `💀` and `🔄` emojis in H2.

---

## board.html — Kanban board

### 1. Identity
- **URL/route**: `/board`
- **Page title**: (block title)
- **Section**: Operational kanban
- **User persona**: Operator, manager

### 2. Structure
- (Light — content is dynamic from JS)

### 6. UX/copy audit — flags

- Minimal template; content is JS-rendered.

---

## evidencia_mercado.html — Market evidence

### 1. Identity
- **URL/route**: `/vs-mercado/evidencia`
- **Page title**: `Evidencia de mercado`
- **Section**: Market research
- **User persona**: Manager, owner

### 2. Structure
- Download button: `📥 CSV` (downloads `evidencia-mercado.csv`)
- Back link: `← Volver a /vs-mercado`
- H2: `Rangos por familia (unidad)`
- Table (headers: `Familia`, `n`, `Mínimo`, `p25`, `Mediana`, `p75`, `Máximo`)
- Empty row: `Todavía no hay evidencia cargada — usá el seed del research repo o importá un CSV.`
- H2: `Importar CSV`
- Format hint: `Columnas: competidor,tipo,ciudad,producto,familia,unidad,precio_gs,as_of,fuente (familia se deduce si falta; fuente obligatoria).`
- Label: `Confirmo la importación` (checkbox required)
- Submit: `Importar`
- H2: `Observaciones recientes`
- Table (headers: `Competidor`, `Ciudad`, `Producto`, `Familia`, `Gs.`, `Fecha`, `Fuente`)
- Per-row: source link (truncated to 48 chars)

### 4. Displayed data

**Rangos table:**
| Column | Semantics |
|---|---|
| `Familia` | family name |
| `n` | observation count |
| `Mínimo` | min Gs. |
| `p25` | 25th percentile |
| `Mediana` | median Gs. |
| `p75` | 75th percentile |
| `Máximo` | max Gs. |

**Observaciones table:**
| Column | Semantics |
|---|---|
| `Competidor` | competitor |
| `Ciudad` | city |
| `Producto` | product |
| `Familia` | family |
| `Gs.` | price |
| `Fecha` | observation date |
| `Fuente` | source link |

### 6. UX/copy audit — flags

- Percentile columns (p25/p75) — technical.
- CSV format documentation in template — operator-friendly.
- Source URL truncated to 48 chars.

---

## fiscal.html — Fiscal overview

### 1. Identity
- **URL/route**: `/fiscal`
- **Page title**: `Fiscal`
- **Section**: Tax / compliance
- **User persona**: Manager, accountant

### 2. Structure
- (Light template — content is dynamic)

### 6. UX/copy audit — flags

- Minimal template.

---

## food-cost-variance.html — Food cost variance

### 1. Identity
- **URL/route**: `/food-cost-variance`
- **Page title**: `Variación de costo de alimentos`
- **Section**: Finance
- **User persona**: Manager, accountant

### 2. Structure
- (Light template — content is dynamic)

### 6. UX/copy audit — flags

- Minimal template.

---

## benchmarks.html — Benchmark table

### 1. Identity
- **URL/route**: `/vs-mercado`
- **Page title**: `Benchmarks`
- **Section**: Market positioning
- **User persona**: Manager, owner

### 2. Structure
- Sort label: `Ordenar por:`
- Sort button: `Mayor diferencia Gs. ↓` (JS `sortBenchmarks('gap')`)
- Link: `🔍 Evidencia de mercado`
- Table (headers: `Producto`, `Nuestro wholesale Gs.`, `Nuestro retail Gs.`, `Mercado avg Gs.`, `Mercado real (evidencia)`, `Posición`)
- Per-row: `📋 Ver receta` (link), `✏️ Editar` (link to edit form)
- Empty tooltip: `Sin datos de mercado cargados`

### 4. Displayed data

| Column | Semantics |
|---|---|
| `Producto` | product name + links |
| `Nuestro wholesale Gs.` | wholesale price |
| `Nuestro retail Gs.` | retail price |
| `Mercado avg Gs.` | market average |
| `Mercado real (evidencia)` | evidence-based |
| `Posición` | rank |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Empty state | `Sin datos de mercado cargados` |

### 6. UX/copy audit — flags

- JS-driven sort button.
- Links to evidence and edit per row.

---

## benchmark_edit.html — Edit one benchmark

### 1. Identity
- **URL/route**: `/vs-mercado/{id}/edit`
- **Page title**: (block title)
- **Section**: Market positioning / edit
- **User persona**: Manager, owner

### 2. Structure
- Success flash: `✅ <strong>Guardado.</strong> Ve a benchmarks.`
- H3: `💰 Nuestro precio`
- Labels: `Wholesale Gs.`, `Retail Gs.`
- H3: `🏪 Mercado`
- Labels: `Competidor A (mín) Gs.`, `Competidor B (prom) Gs.`, `Mercado promedio Gs.`, `Notas / fuente` (placeholder `MercadoPy, redes, llamadas…`)
- Submit: `💾 Guardar`
- Cancel link: `Cancelar`
- H2: `📦 Receta vinculada: {{recipe.name}}`
- Link: `Ver receta`

### 4. Displayed data

**Nuestro precio:**
| Field | Semantics |
|---|---|
| `Wholesale Gs.` | wholesale price |
| `Retail Gs.` | retail price |

**Mercado:**
| Field | Semantics |
|---|---|
| `Competidor A (mín) Gs.` | competitor A min |
| `Competidor B (prom) Gs.` | competitor B avg |
| `Mercado promedio Gs.` | market avg |
| `Notas / fuente` | source notes |

### 6. UX/copy audit — flags

- 2-column form: Nuestro vs Mercado.
- Source notes placeholder gives examples.

---

## cotizador.html — Quote generator

### 1. Identity
- **URL/route**: `/cotizador`
- **Page title**: `Cotizador`
- **Section**: Sales / quoting
- **User persona**: Operator, manager

### 2. Structure
- H1
- Callout: `No cargaste ningún producto.`
- Table (headers: `Producto`, `Precio carta`, `Cantidad`)
- Field: `Descuento por volumen (%)` (max-width 220px)
- Submit: `Cotizar`
- H2: `Cotización`
- Table (headers: `Producto`, `Cant.`, `Lotes`, `Costo`, `Carta`, `Margen`)
- Total rows: `TOTAL carta`, `Costo total`
- Submit: `Descargar PDF`
- Disclaimer: `Cotización preliminar — precios de carta sin IVA discriminado.`

### 4. Displayed data

**Quote table:**
| Column | Semantics |
|---|---|
| `Producto` | product |
| `Cant.` | qty |
| `Lotes` | batches |
| `Costo` | cost Gs. |
| `Carta` | menu price Gs. |
| `Margen` | margin Gs. |

### 6. UX/copy audit — flags

- PDF download button.
- Disclaimer about no VAT breakdown.
- Empty state: `No cargaste ningún producto.` — actionable.

---

## Section-wide issues

### Cross-page consistency

| Issue | Pages affected | Notes |
|---|---|---|
| **English loan words** | All reports / insights | `Revenue`, `AOV`, `Target`, `Override`, `Forecast`, `Rolling 14d`, `KPI`, `Accuracy`, `COGS`, `Prime Cost`, `Food cost`, `ROAS` (referenced). Spanish-localized UI but technical English everywhere. |
| **`₲` vs `Gs.`** | reportes_mermas_cost.html uses `₲`; all others use `Gs.`. | Recommend unifying to `Gs.`. |
| **Date format** | Most: `DD/MM/YYYY`; some reports: ISO `YYYY-MM-DD`. | Inconsistent; recommend one. |
| **Time periods** | Insights use `Últimos 7/30/60/90/180/365 días` — consistent. ✓ |
| **`Prom/día` abbreviation** | insight_demand.html | Spanish abbreviation OK but unexplained. |
| **`Reembolso` vs `Devolución`** | reportes_libro_ventas.html uses `Reembolso`; some other reports use `Neto`. | Spanish-localized terms. |
| **`SET` (tax authority) referenced** | reportes_libro_ventas.html | Acronym for Paraguay tax authority; appropriate. |
| **Empty state standardization** | Most reports use `ui.empty_state(title, icon, hint)`. ✓ |
| **Per-period comparisons** | reportes_comparacion uses two-period form (Period 1/Period 2). | Good pattern. |
| **Format docs in templates** | evidencia_mercado.html | Inline CSV format documentation in template. |

### Copy issues

| Page | Issue |
|---|---|
| dashboard.html | Some KPI labels (`Dinero`, `Actividad`, `Costos`) are abstract; cards themselves show values. |
| inicio.html | Many sub-sections — could overwhelm new operators. |
| reportes_diario.html | `COGS` English loan word — should be `Costo de Mercadería Vendida`. |
| reportes_top_productos.html | `Revenue` English loan word. |
| reportes_cierre_mensual.html | Multiple explanation blocks — clear but verbose. |
| reportes_libro_ventas.html | 11 columns — wide table; could use a printable view. |
| insight_freshness.html | "🔥 Cociná HOY" — emotive CTA; may not fit formal SOPs. |
| insight_margenes.html | "peor margen primero" — colloquial. |
| insight_price_impact.html | Fixed 33% goal — operators should be able to change this. |
| insight_stock.html | `💀` and `🔄` emojis in headings — may not fit formal dashboards. |
| benchmarks.html | Empty tooltip `Sin datos de mercado cargados` — needs explicit empty state. |
| cotizador.html | Disclaimer `precios de carta sin IVA discriminado` — operator-facing jargon. |

### Spanish-language quality

- Generally **excellent** Spanish throughout.
- English technical terms dominate BI section — appropriate.
- Use of `Δ` symbol in column headers — operator must know what it means (delta).
- `Promedio 56d × factor del día × tendencia 14d` — math notation in Spanish UI.
- Paraguayan tax terms (`Boleta Resimple`, `Gravado`, `Base imponible`) used correctly.

### Accessibility gaps

- Most reports have period filters with `sr-only` labels — good.
- Some tables lack `aria-label` on `<table>` element — could add.
- Color-only signals (margin % badge) — text is included alongside.
- `role="table"` on heatmap — good.

### What's missing

- **Chart axis labels and legends** — many reports embed Chart.js or similar (not in templates). Could be in JS files.
- **PDF generation** — separate library/flow; not in template.
- **Drill-down handlers** — links exist; targets are other pages.

---

*End of Section D — Reports + Analytics + Insights + Dashboard + Benchmarks + Cotizador*