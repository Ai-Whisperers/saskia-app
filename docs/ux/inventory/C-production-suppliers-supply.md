# Sazon/Saskia Production + Supply Chain Content Audit

**Generated:** 2026-10-07
**Scope:** Production (8 pages) + Planner (1) + Pedidos/Orders (5) + Menus (4) + Suppliers (5) + Delivery (1) + Shopping/Reorder (2) = 26 pages
**Source templates:** `app/templates/produccion*.html`, `planner.html`, `pedido*.html`, `pedidos*.html`, `menu*.html`, `supplier*.html`, `delivery_zones.html`, `shopping_list.html`, `reorder.html`

---

## produccion.html — Production plan (day/week/month view)

### 1. Identity
- **URL/route**: `/produccion` (with `?view=day|week|month&for_date=YYYY-MM-DD`)
- **Page title**: `Producción` (block title)
- **Section**: Production / kitchen
- **User persona**: Operator (cook/baker), manager

### 2. Structure
- H1 (inline-flex with icon): `Producción`
- Hint paragraphs (3 of them — `mt-1-only`)
- View tabs (aria-label `Cambiar vista`, role `tablist`):
  - `Día`, `Semana`, `Mes`
- UI version badge (title `UI v2 (DEMANDA, META, REAL, Pedidos)`)
- Accuracy link (title `Precisión del plan vs. producción real`)
- Print link (title `Imprimí el plan de hoy para el turno`)
- "Cargar plan desde plantilla" confirm modal title: `¿Cargar plan desde plantilla?`
- Copy-from-previous-day field (placeholder `hace 7d`)
- Plan-export buttons (title `Descargá el plan de hoy en CSV...`)
- Plan-print-blank button (title `Imprimí una hoja en blanco para anotar las cantidades a mano`)
- Weekly prep button (title `Plan de preparación semanal (ingredientes agregados)`)
- Link hint: `Usá la <a href="/recetas">vista de recetas</a>... o andá a <a href="/produccion/manana">producción de mañana</a>...`
- Notifications bundle (aria-label `Notificaciones del día`):
  - Title attributes: `Alertas críticas que requieren acción`, `Avisos a revisar`, `Información general`
  - Toggle: `Ver todo`
  - Small text: `clic para ver el detalle`
- Pedidos preview: `US 4.4 — El cocinero ve estos pedidos antes que el plan automático.`
  - Per pedido: `<a href="/pedidos/{{id}}">Pedido #{{id}} — {{customer_name}}</a>`
  - Badge: `⏰ {{ promised_time }}`
  - Badge: `{{ channel }}`
  - Status badge: dynamic `pending|ready|<other>`
  - Small text: `clic para abrir`
- Reorder CTA: `Opciones: comprá lo que falta en <a href="/reorder">/reorder</a>`
- Reorder button: `Reponer ahora →`
- Daily-target card: `<strong>Meta diaria:</strong> {{daily_target}} unidades · <strong>Real:</strong> {{daily_actual}}`
- Percentage badge: `{{ "%.0f"|format(pct) }}%` (success if ≥100, warning if ≥60, danger below)
- "Editar meta" link: `<a href="/config#produccion-meta">`
- Out-of-range badge: `FUERA DE RANGO` (red bg)
- HACCP link: `<a href="/produccion/haccp?for_date={{for_date}}">Registr&aacute; ahora →</a>`
- HACCP block: `Última temperatura fuera de rango seguro`
- Conflict-banner: `<strong>Otro turno se actualizó mientras escribías.</strong>reales (columna Real) coincidan con lo que se hornó.` + `title="Recargá la página para ver los valores más recientes"`
- Extra-baked notice: `<small><strong>✓ Horneado extra agregado.</strong> Aparece abajo con badge naranja.</small>`
- Confidence pills: `{{confidence_bands.high}} alta`, `conf-medium`, `conf-low`
- Bulk action: `Set every row's qty to its target and check 'done'`, `O usá los botones +/- por fila para ajustar de a 1.`
- Keyboard hints: `<kbd>J</kbd>/<kbd>K</kbd> navegar · <kbd>O</kbd> override · <kbd>C</kbd> cerrar día`
- Filter input (placeholder `Filtrar por nombre…`, aria-label `Filtrar productos por nombre`)
- Difficulty-filter (role `tablist`, aria-label `Filtrar por dificultad`)
- Difficulty legend hint (title `Las estrellas indican la dificultad de la receta (1 = muy fácil, 5 = muy difícil). Útil para elegir qué hornear cuando estás cansado/a.`)
- Filter labels: `Alérgenos:`, `Origen:`, `Sólo:`, `Filas:`
- Rows-count: `Mostrar {{n}} filas`
- Table headers: `Listo`, `Origen`, `Receta` (with sort classes)
- Confidence-help link: `<a href="#confidence-modal" title="¿Qué significa el porcentaje?">?</a>`
- Per-row badges:
  - `Extra` (badge-warning, title `Horneado no planeado`)
  - `Fermentar {{N}}h: empezar ... para que esté lista a las {{ready_label}} (inicio del turno).`
  - `Dificultad {{n}}/5` (title)
  - Lote calculation: `{{n}} lote{{plural}} × {{qty}}{{unit}} = {{total}} und`
  - `+{{qty}}` pedido-qty badge (title `{{n}} und comprometidas por pedidos para hoy`)
  - Aria labels: `Marcar {{r.product_name}} como hecho`, `Restar 1 a {{r.product_name}}`, `Cantidad hecha de {{r.product_name}}`, `Sumar 1 a {{r.product_name}}`
  - Source badge title: `{{source_buckets[bucket]}}`
  - Confidence span title: `Confianza del cálculo: {{pct}}%. Bajo = se queda cerca de la meta; Medio = puede variar ±10%; Alto = conviene revisar`
  - Manual span title: `Producto manual: no hay cálculo automático. Marcá la cantidad a hornear a ojo.`
  - Merma title: `Registrar merma para {{r.product_name}}`
  - Lote-exact title: `Lote exacto (sin sobrante)` with `✓`

### 4. Displayed data

**Daily-target card:**
| Field | Semantics | Example | Visual |
|---|---|---|---|
| Meta diaria | daily_target | `200 unidades` | strong |
| Real | daily_actual | `150 unidades` | strong |
| Pct | completion percentage | `75%` | badge |

**Production rows (table):**
| Column | Semantics | Example | Visual |
|---|---|---|---|
| Listo | done checkbox | (checked) | checkbox |
| Origen | source badge | `forecast` `manual` `template` | badge |
| Receta | recipe name + extras | `Chipa` | td |
| (qty input) | editable qty | `40` | input |
| +/- buttons | increment/decrement qty | `- +` | buttons |
| Source pct | confidence % | `Alta 75%` | span |
| Real | actual produced qty | `40` | input |
| Merma | waste registration link | `🗑` | a |
| Lote ✓ | exact-batch indicator | `✓` | span |

### 5. Tooltips / hover text (this page is **tooltip-dense**)

| Element | Tooltip text |
|---|---|
| UI version badge | `UI v2 (DEMANDA, META, REAL, Pedidos)` |
| Accuracy link | `Precisión del plan vs. producción real` |
| Print plan link | `Imprimí el plan de hoy para el turno` |
| Copy-from-previous-day field | `Fecha fuente (default: 7 días antes)` |
| Copy button | `Copiá el plan de la fecha fuente como override para esta fecha` |
| Export CSV button | `Descargá el plan de hoy en CSV (producto, cantidad, fuente, confianza)` |
| Print blank button | `Imprimí una hoja en blanco para anotar las cantidades a mano` |
| Weekly prep button | `Plan de preparación semanal (ingredientes agregados)` |
| Notifications bundle toggle | `Ver todo` |
| Notification critical | `Alertas críticas que requieren acción` |
| Notification review | `Avisos a revisar` |
| Notification info | `Información general` |
| Pedido badge channel | `{{ channel }}` |
| Pedido badge age | `Atrasado {{ age_days }}d` |
| Out-of-range | `FUERA DE RANGO` |
| Difficulty legend | `Las estrellas indican la dificultad de la receta (1 = muy fácil, 5 = muy difícil). Útil para elegir qué hornear cuando estás cansado/a.` |
| Confidence link | `¿Qué significa el porcentaje?` |
| Per-row Extra badge | `Horneado no planeado` |
| Fermentation pill | `Fermentar {{N}}h: empezar {{start}} ({{days_before label}}) para que esté lista a las {{ready}} (inicio del turno).` |
| Difficulty pill | `Dificultad {{n}}/5` |
| Lote calc | `{{n}} lote{{plural}} × {{qty}}{{unit}} = {{total}} und` |
| Pedido-qty badge | `{{n}} und comprometidas por pedidos para hoy` |
| Source badge | `{{source_buckets[bucket]}}` |
| Confidence span | `Confianza del cálculo: {{pct}}%. Bajo = se queda cerca de la meta; Medio = puede variar ±10%; Alto = conviene revisar` |
| Manual span | `Producto manual: no hay cálculo automático. Marcá la cantidad a hornear a ojo.` |
| Merma icon | `Registrar merma para {{r.product_name}}` |
| Lote-exact span | `Lote exacto (sin sobrante)` |
| Conflict banner refresh | `Recargá la página para ver los valores más recientes` |
| "Cómo se calcula" toggle | (renders dynamic calculator) |

### 6. UX/copy audit — flags

- **English loan words**: `default`, `override`, `forecast`, `target`, `template` used freely. Production terminology is partially English.
- **`Registr&aacute; ahora →`** — uses HTML entity for `á`; correct but inconsistent with rest of template.
- `FUERA DE RANGO` is a single badge — no explanation of what range (operator must know HACPP rules).
- `Pedido` badge truncation: `{{ vt|truncate(28) }}` (Ventana preferida truncated to 28 chars).
- Confidence pill uses 4 bands (high/medium/low/none) but only 3 colors visible in template.
- `M-FLO-001` style dev comments inline — fine but adds noise.
- Empty-state via `ui.empty_state` macro (referenced but content in this template not visible).

---

## produccion_accuracy.html — Plan-vs-actual accuracy

### 1. Identity
- **URL/route**: `/produccion/accuracy`
- **Page title**: `Producción / Precisión`
- **Section**: Production / analytics
- **User persona**: Manager, owner

### 2. Structure
- H1: `Producción / Precisión`
- Hint paragraph
- KPI cards (4): `Plan total`, `Producido`, `Vendido`, `Accuracy promedio`
- Critical-attention banner: `<strong>Atención:</strong> en este período faltó hornear {{count}} unidades`
- H3: `Desvíos por fecha`
- Table 1: `Fecha`, `Plan`, `Producido` columns
- Empty state: `No hay desvíos en el período.`
- H3: `Días con plan ejecutado`
- Table 2: `Fecha`, `Plan`, `Producido`, `Accuracy` columns
- Empty state: `No hay días con plan ejecutado.`
- H3: `Por producto`
- Table 3: `Producto`, `Días plan`, `Plan`, `Producido`, `Vendido`, `Accuracy`, `Faltó hornear`, `Sobró hornear`
- Helper: `<strong>Cómo leerlo:</strong> "Accuracy" = producido ÷ plan.`

### 3. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Fecha` | date | `07/10/2026` | td |
| `Plan` | qty planned | `200` | td right |
| `Producido` | qty produced | `180` | td right |
| `Vendido` | qty sold | `160` | td right |
| `Accuracy` | ratio (producido/plan) | `90%` | td right |
| `Faltó hornear` | gap (shortage) | `20` | td right |
| `Sobró hornear` | overshoot | `20` | td right |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Empty state | `No hay datos de producción en este período` |

### 6. UX/copy audit — flags

- KPI labels in `kpi-label` class — generic; specific values are dynamic.
- "Accuracy" is an English loan word used without translation.
- `<strong>Cómo leerlo:</strong>` — clear explanation block.

---

## produccion_haccp.html — HACCP temperature log

### 1. Identity
- **URL/route**: `/produccion/haccp?for_date=YYYY-MM-DD`
- **Page title**: `HACCP` (block title)
- **Section**: Production / compliance
- **User persona**: Operator (cook)

### 2. Structure
- H1 (inline-flex): `HACCP`
- Hint paragraph (`mt-1-only`)
- Back link: `← Volver a /produccion`
- Last out-of-range banner: `<strong>Última temperatura fuera de rango seguro</strong>`
- H2: `📝 Registrar lectura`
- Form fields:
  - `Ubicación` (label `block-bold`)
  - `Turno`
  - `Temperatura` (placeholder `ej: -20.5`)
  - `Notas` (placeholder `ej: puerta quedó abierta 5 min`)
- H2: `⏰ Pendientes hoy`
- H2: `📊 Lecturas del {{for_date}}`
- H2: `📅 Últimos 7 días`
- JS hint messages:
  - `⚠️ <strong>Fuera de rango freezer</strong> (-22 a -18 °C). Verificá la lectura.`
  - `🟡 <strong>Límite de rango</strong> (esperado -22 a -18 °C).`
  - `✓ <strong>OK</strong> dentro del rango seguro (-22 a -18 °C).`
  - `⚠️ <strong>Fuera de rango heladera</strong> (0 a 8 °C).`
  - `🟡 <strong>Límite de rango</strong> (esperado 1 a 6 °C).`
  - `✓ <strong>OK</strong> dentro del rango seguro (1 a 6 °C).`

### 3. Displayed data

**Temperature-log table:**
| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Ubicación` | location | `Freezer 1` | td |
| `Turno` | AM/PM | `AM` (badge yellow), `PM` (badge indigo) | td |
| `Temperatura` | temp (°C) | `-20.5` | td right |
| `Hora` | timestamp | `08:30` | td |
| `Nota` | notes | `puerta quedó abierta 5 min` | td |
| `FUERA DE RANGO` badge | out of safe range | (red bg) | td |

### 5. Tooltips

(none explicit on static elements)

### 6. UX/copy audit — flags

- HACCP terminology is technical/specialized — operators may need training.
- Color coding for AM/PM via background colors (`#fef3c7`, `#e0e7ff`) — distinctive.
- Range values are hardcoded in JS (`-22 a -18 °C`, `1 a 6 °C`) — not configurable.
- Form labels use `block-bold` class — bold uppercase style.

---

## produccion_manana.html — Tomorrow's plan adjustment

### 1. Identity
- **URL/route**: `/produccion/manana?for_date=YYYY-MM-DD`
- **Page title**: `Producción / Mañana` (block)
- **Section**: Production / planning
- **User persona**: Operator, manager

### 2. Structure
- H1 (inline-flex): `Producción / Mañana`
- Hint: `<span class="badge badge-seasonal">{{ seasonal_note }}</span>` (when seasonal)
- Algorithm hint: `Algoritmo: <strong>rolling 14d</strong> por defecto · plantilla semanal si existe · override si está definido.`
- Link to today (title `Ir al plan de hoy`)
- Link to weekly plan (title `Ir a la planilla semanal de producción`)
- Save button (aria-label `Guardá los ajustes de cantidad para mañana`)
- H2: `Qué producir mañana`
- Hint: `Editá la columna <strong>Plan</strong> si querés cambiar la cantidad.`
- Pedido context: `Pedidos = unidades ya comprometidas vía encargos.`
- Forecast context: `Forecast = sugerencia del algoritmo.`
- Override confirm modal title: `¿Guardar plan de mañana?`
- Override confirm modal body: `Se sobrescribirán los overrides del día con los valores del plan.`

### 3. Displayed data

| Column | Semantics | Example | Visual |
|---|---|---|---|
| `Producto` | product name + "ver receta" link | `Chipa` | td |
| `Forecast` | algorithm forecast (rolling 14d / template / override) | `30` | td right |
| `Pedidos` | committed pedido units | `5` | td right |
| `Total` | final plan (forecast + pedidos, editable) | `35` | td right |
| `Fuente` | source: forecast / manual / template | `forecast` | td |
| `Confianza` | confidence pill | `Alta 75%` | span |
| `Plan ⇄` | editable plan input | `35` | input |

**Per-row badges:**
- `Ajuste manual` (badge-manual)
- `Plantilla semanal` (badge-template)
- `Sugerido por ventas` (badge-rolling)
- `📌 guardado` (small muted, when override exists)
- Commit pill: `{{ped_qty|int}}` (title `{{n}} unidades comprometidas`)

**Confidence pills:**
- `conf-high` title `Alta confianza` — green
- `conf-medium` title `Confianza media` — yellow
- `conf-low` title `Confianza baja` — red
- `conf-none` title `Sin datos` — gray, content `—`

**Ingredients table (after products):**
| Column | Semantics |
|---|---|
| `Ingrediente` | ingredient name |
| `Cantidad` | needed |
| `Stock` | on hand |
| `A comprar` | gap |

**Per-ingredient badges:**
- `¡Falta!` (badge-danger) when shortage
- `OK` (muted) when sufficient
- Empty: `No hay líneas de ingredientes (probablemente faltan recetas vinculadas a productos).`

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Forecast column | `Forecast del algoritmo (rolling 14d / plantilla / ajuste)` |
| Pedidos column | `Unidades ya comprometidas vía pedidos` |
| Total column | `Plan final (forecast + pedidos, editable)` |
| Plan column | `Editá este número; es lo que vamos a producir` |
| Commit pill | `{{n}} unidades comprometidas` |
| Override-existing small | `Ya tenías un plan guardado` |
| Confidence pills | `Alta confianza` / `Confianza media` / `Confianza baja` / `Sin datos` |

### 6. UX/copy audit — flags

- `forecast` / `override` / `rolling 14d` — English loan words used without translation.
- `Plan ⇄` column header uses ⇄ (LEFTWARDS ARROW OVER RIGHTWARDS ARROW) — visual hint that it's editable.
- `Ajuste manual` vs `Plantilla semanal` vs `Sugerido por ventas` — three source types in same row, color-coded.
- **Verify input handling**: editable plan field uses `placeholder="{{ _total }}"` so default value is the computed total.

---

## produccion_prep.html — Weekly ingredient prep view

### 1. Identity
- **URL/route**: `/produccion/prep?week=YYYY-Www`
- **Page title**: `Producción / Prep semanal`
- **Section**: Production / planning
- **User persona**: Manager

### 2. Structure
- H1 (inline-flex): `Producción / Prep semanal`
- Hint paragraph
- Week nav (aria-label `Cambiar semana`): `← Semana anterior`, `Semana siguiente →`
- Back-to-week-view link (title `Volver a la vista semana`)
- `<strong>Resumen:</strong>` with three badge counts: danger / warning / success
- Table header: `Estado` (title `Falta = no alcanza; Justo = alcanza justo; Suficiente = sobra`)
- Per-row badges: `¡Falta!`, `Justo`, `Suficiente`
- Empty state: `No hay producción planificada para esta semana todavía.`

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Estado` | severity: falta / justo / suficiente |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Estado column | `Falta = no alcanza; Justo = alcanza justo; Suficiente = sobra` |

### 6. UX/copy audit — flags

- 3-tier state colors are clear (red/yellow/green).
- Week navigation via ISO week string.
- Light page — primary content is the prep summary table.

---

## produccion_prep_recipes.html — Recipe-level prep view

### 1. Identity
- **URL/route**: `/produccion/prep-recipes?for_date=YYYY-MM-DD`
- **Page title**: `Producción / Prep recetas`
- **Section**: Production / planning
- **User persona**: Manager

### 2. Structure
- H1 (inline-flex)
- Hint
- Day nav (aria-label `Cambiar día`): `← Día anterior`, `Hoy`, `Día siguiente →`
- Back-to-day-plan link (title `Volver al plan del día`)
- Weekly-totals link (title `Ver totales agregados de la semana`)
- Shopping-list link (title `Lista de compras (lo que falta por comprar)`)
- Summary badges: count of recipes by status (danger/warning/success, with `data-testid` attributes)
- Empty: `No hay recetas en el plan para este día.` + link `Ir al plan del día`
- Per-recipe card: H2 + recipe link
- "Información faltante" link: `la lista de compras`

**Per-recipe table:**
| Column | Semantics |
|---|---|
| `Ingrediente` | name |
| `Cantidad` | needed |
| `En stock` | on hand |
| `Estado` | ok / faltante / sin stock |

**Per-ingredient badges:**
- `¡Falta!` (title `Faltante`)
- `?` (title `Sin stock registrado`)
- `✓` (title `Stock suficiente`)
- `!` (title `Stock bajo`)
- Empty: `Esta receta no tiene ingredientes en su explosión.`

**Aggregate ingredientes table:**
| Column | Semantics |
|---|---|
| `Ingrediente` | name |
| `Necesario` | needed across all recipes |
| `Stock` | on hand |
| `Aparece en` | which recipes |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| `¡Falta!` badge | `Faltante` |
| `?` badge | `Sin stock registrado` |
| `✓` badge | `Stock suficiente` |
| `!` badge | `Stock bajo` |

### 6. UX/copy audit — flags

- Uses `data-testid` attributes — good for testing.
- Empty-state CTA explicit: `Ir al plan del día`.
- 4-state ingredient badges (Falta/?/✓/!) — uses unicode glyphs instead of words for compactness.

---

## produccion_print.html — Printable production plan

### 1. Identity
- **URL/route**: `/produccion/print?for_date=YYYY-MM-DD` (and `/produccion/print/{date}`)
- **Page title**: `Producción — Plan del día`
- **Section**: Production / printable
- **User persona**: Operator (printed for the kitchen)

### 2. Structure
- H1: `📋 Producción — Plan del día`
- H2 (day context)
- Table 1 (`aria-label="Productos a hornear el {{day.date}}"`)
- Table 2 (`aria-label="Productos a hornear el {{for_date}}"`)
- Empty CTA: `Generá un plan` (link to /produccion/manana)

### 3. Displayed data

**Per-table:**
| Column | Semantics |
|---|---|
| `Listo` | checkbox |
| `Producto` | product name + "ver receta" link (print-only) |
| `A hornear` | target qty |
| `Real` | actual qty |

**Aria-labels:**
- `Marcar {{r.product_name}} como listo` (checkbox)
- `Cantidad real de {{r.product_name}}` (qty input)

### 6. UX/copy audit — flags

- Two tables with same shape; first is for `day.date`, second for `for_date` — possibly redundant.
- Uses emoji in heading (📋) — print-safe but non-standard.

---

## planner.html — Manual production planner

### 1. Identity
- **URL/route**: `/produccion/planner`
- **Page title**: `Plan manual de producción`
- **Section**: Production / manual planning
- **User persona**: Manager

### 2. Structure
- H1 (with svg icon): `Plan manual de producción`
- Hint: `Elegí receta + cantidad de tandas y calculamos cuánto necesitás cocinar — y qué ingredientes faltan`
- Back link: `← Volver a Producción`
- Form: `Receta` (combo placeholder `Buscar receta…`), `Tandas`
- Submit: `Calcular necesidad`
- Results: H2 `{{batches}}× {{recipe name}}`
- Result badges: `Faltan Gs. {{shortage}} en ingredientes` (badge-error) / `✓ Stock suficiente` (badge-success)
- Results table (after running)
- Empty state: `Elegí una receta + cantidad de tandas para ver qué ingredientes necesitás`

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Ingrediente` | name |
| `Necesario` | qty needed |
| `En stock` | on hand |
| `Faltante` | gap |
| `Unit Gs.` | unit price |
| `Costo faltante` | cost of gap |
| `Status` | ok / shortage / negative |

**Status badges:**
- `⚠ negativo` (badge-danger) — when stock is negative
- `0 {{unit}}` (title `Stock negativo — revisar ventas sin reposición`)

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Negative stock span | `Stock negativo — revisar ventas sin reposición` |

### 6. UX/copy audit — flags

- Uses `⚠` emoji for warning.
- `Tandas` is "batches" in Spanish — native word.
- After calculation, shows cost of shortage in Gs. — clear actionable signal.

---

## pedido_board.html — Kitchen display (KDS)

### 1. Identity
- **URL/route**: `/pedido_board` (or `/pedidos/board`)
- **Page title**: `Cocina — pedidos del día`
- **Section**: Orders / KDS (Kitchen Display System)
- **User persona**: Operator (cook) on tablet at the kitchen

### 2. Structure
- Back link: `← Volver a pedidos`
- Auto-refresh banner: `Auto-refresh cada 30s · Actualizado: {{now}}`
- Sound toggle button (aria-pressed `false`, aria-label `Activar sonido de nuevos pedidos`)
- Mute link: `🔇 Sin audio` (title `Desactivar audio`)
- H1 (with svg icon): `Cocina — pedidos del día`
- Filters (aria-label `Filtrar pedidos`): `Todos`, `A tiempo`, `Atrasados`
- Counter span: `<span id="rev-count">0</span> pedidos`
- Revenue span: `Gs. <strong id="rev-total">0</strong> total`
- Kanban (aria-label `Pedidos por estado`): 3 columns
- Per-state header: `<h2>{{ label }} <span class="count-badge">{{ pedidos|length }}</span></h2>`
- Per-pedido H2 (compact)
- Per-pedido action: `Abrir` (link)
- Empty per-state: `Sin pedidos en este estado.`
- Global empty: `No hay pedidos pendientes. 🍰`

### 3. Displayed data

(per pedido — data is dynamic; covered by pedido_detalle.html structure)

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Sound toggle (off) | `Activar sonido de nuevos pedidos` (aria-label) |
| Mute link | `Desactivar audio` |

### 6. UX/copy audit — flags

- Auto-refresh every 30s — operator sees live updates.
- Sound toggle is **prominent** at top — kitchen environments need audio cues.
- 3-column kanban is `repeat(3,1fr)` grid layout.
- `🍰` emoji in empty state — friendly touch.

---

## pedido_detalle.html — Single pedido detail

### 1. Identity
- **URL/route**: `/pedidos/{pedido_id}`
- **Page title**: `Pedido #{{id}}` (block)
- **Section**: Orders / detail
- **User persona**: Operator, manager

### 2. Structure
- H1 (with status badge: `Entregado`, `Cancelado`, etc.)
- Card: `Cliente` (with `Últ. 30d: Gs. {{spend}}`, title `Compras últimos 30 días`)
- Link to /clientes/{id} (title `Ver ficha del cliente`)
- Card: `Prometido`
- Channel badge: `{{channel}}`
- Payment badge: `pago: {{payment_intent}}`
- Card: `Impacto en puntos`
- Loyalty badges: `+{{earned}} pts ganados`, `-{{redeemed}} pts canjeados`
- Puntos-movimientos table (headers: `Fecha`, `Motivo`, `Δ`, `Venta`)
- Card: `Ventas generadas ({{count}})`
- Ventas table (headers: `Venta #`, `Producto`, `Cant.`, `Precio unit. (Gs.)`, `Fecha`)
- Card: `Entrega`
- Delivery zone badge: `zona #{{id}}`
- Card: pedido lines (headers: `Producto`, `Cantidad`, `Precio unit.`, `Subtotal`, `Cumplido`)
- Per-line "Cumplido" badge: `{{"%.2f"|format(fulfilled_qty)}}` (badge-good)
- Total row: `colspan="3"` + `<strong>Total</strong>`
- Notes line: `<p class="mt-2"><strong>Notas:</strong> {{ pedido.notes }}</p>`
- Cancel-reason line: `<strong>Razón de cancelación:</strong>`
- Public-link card with hint: `Compartí este link por WhatsApp para que vea su pedido sin login.`
- Status badges: `Pendiente`, `Confirmado`, `Listo`, `Entregado`, `Cancelado`
- Action: `Ver`, `Repetir` (with `from={{id}}`)
- Cancel modal:
  - H3: `Cancelar pedido`
  - Textarea placeholder: `Ej: cliente no respondió, producto agotado…`
  - Buttons: `Volver`, `Guardar`

### 3. Displayed data

**Cliente card:**
| Field | Semantics | Example |
|---|---|---|
| Nombre | customer name | `María` |
| Teléfono | phone | `0981 123 456` |
| Últ. 30d | last 30d spend | `Gs. 350.000` |

**Puntos movimientos table:**
| Column | Semantics |
|---|---|
| `Fecha` | tx.recorded_at |
| `Motivo` | reason |
| `Δ` | delta (pts) |
| `Venta` | linked sale ID |

**Ventas generadas table:**
| Column | Semantics |
|---|---|
| `Venta #` | sale.id |
| `Producto` | product name |
| `Cant.` | qty |
| `Precio unit. (Gs.)` | unit price |
| `Fecha` | sold_at |

**Pedido lines table:**
| Column | Semantics |
|---|---|
| `Producto` | product name |
| `Cantidad` | qty |
| `Precio unit.` | unit price |
| `Subtotal` | line total |
| `Cumplido` | fulfilled qty |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Cliente phone icon | `Compras últimos 30 días` |
| Cliente ficha link | `Ver ficha del cliente` |

### 6. UX/copy audit — flags

- 5 status types (Pendiente/Confirmado/Listo/Entregado/Cancelado) — clear lifecycle.
- Public link explicitly tells operator: `Compartí este link por WhatsApp`.
- `Repetir` action passes `from={{id}}` — backend handles "copy from existing".

---

## pedido_publico.html — Public pedido view (no login)

### 1. Identity
- **URL/route**: `/p/{token}` (or `/pedido_publico`)
- **Page title**: (none — public view)
- **Section**: Orders / public
- **User persona**: Customer (no auth)

### 2. Structure
- H1 (block-level style)
- Definition list: `Cliente`, `Teléfono`, `Retirar`, `Ventana preferida`, `Dirección de entrega`
- H2: `Tu pedido:`
- Total: `<strong>Total estimado</strong>`
- Notes: `Notas` (metric-label)
- Canceled banner: `<strong>Cancelado</strong> — este pedido fue anulado. Contactanos si tenés dudas.`
- Footer: `Guardá este link o esta página para revisar tu pedido.`
- `Si necesitás cambiar algo, respondé por WhatsApp.`
- Comprobante section: `Comprobante de pago`
- Buttons: `Subir nuevo comprobante`, `Subir comprobante`

### 3. Displayed data

| Field | Semantics |
|---|---|
| `Cliente` | customer name |
| `Teléfono` | phone |
| `Retirar` | pickup time |
| `Ventana preferida` | window |
| `Dirección de entrega` | delivery address |
| `Total estimado` | total Gs. |
| `Notas` | notes |

### 5. Tooltips

(none)

### 6. UX/copy audit — flags

- Public-facing copy — Spanish-only, clear.
- Canceled banner uses `<strong>Cancelado</strong>` — appropriate for customer.
- WhatsApp call-to-action in footer.

---

## pedido_stock_preview.html — Stock preview before fulfilling

### 1. Identity
- **URL/route**: `/pedido_stock_preview` (or `/pedidos/{id}/stock-preview`)
- **Page title**: `Stock preview`
- **Section**: Orders / pre-fulfillment check
- **User persona**: Operator

### 2. Structure
- Back link: `← Volver al pedido`
- H1
- Hint: `Esto es lo que se va a descontar al cumplir el pedido.`
- H2: `Ingredientes a consumir`
- Sort button: `Por faltante ↓` (calls `window.UISortTable.sortByCell(1)`)
- Hint paragraph: `Force-fulfill allow list`
- Empty state: `Sin productos con receta — No hay productos con receta para este pedido.`
- Form label: `Permitir cumplir aunque falte stock` (label class `form-check-label`, input id `force-fulfill`)

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Ingrediente` | name |
| `Producto` | product name |
| `Stock actual` | on hand |
| `A consumir` | qty needed |
| `Después` | stock after fulfill |

### 5. Tooltips

(none)

### 6. UX/copy audit — flags

- Lets operator see stock impact before committing.
- "Force fulfill" toggle — risk flag for management.

---

## pedidos.html — Pedidos list

### 1. Identity
- **URL/route**: `/pedidos`
- **Page title**: `Pedidos`
- **Section**: Orders / list
- **User persona**: Operator, manager

### 2. Structure
- H1 (inline-flex)
- Hint paragraph (`mt-1-only`)
- Search input (placeholder `Buscar por nombre o teléfono…`, aria-label `Buscar por nombre o teléfono`)
- Search button: `Buscar`
- Clear button: `✕` (aria-label `Limpiar búsqueda`)
- Filter nav: `Filtrar por estado`, `Filtrar por período`
- Severity badges (per row): dynamic class
- Export link (aria-label `Exportar pedidos a CSV`)
- Bulk-action bar: `<span id="selected-count">0</span> seleccionado(s)`
- Bulk fulfill button: `✓ Cumplir`
- Bulk cancel confirm title: `¿Cancelar pedidos?`
- Bulk cancel button: `✕ Cancelar`
- Bulk link button: `🔗 Enlace`
- Table headers: (checkbox), `Estado`, `Cliente`, `Fecha prometida`, `Canal`, `Pago`, `Líneas`, `Total`, `Acciones`
- Per-row:
  - Checkbox (aria-label `Seleccionar pedido {{customer_name}}`)
  - Status badge: `Entregado` (badge-good)
  - `últ. 30d: Gs. {{spend}}` (small, title `Compras últimos 30 días`)
  - `Atrasado {{age_days}}d` (badge-danger, title `atrasado`)
  - `Hoy` (badge-warn)
  - `{{channel}}` (badge-neutral)
  - `{{vt|truncate(28)}}` (badge-warn, title `Ventana preferida`)
  - `ASAP` (badge-neutral)
  - Action: `Ver`
  - Action confirm title: `¿Cumplir pedido?` body `Marcá este pedido como entregado.`
  - Action: `Cumplir` (button text)
  - Cancel confirm title: `¿Cancelar pedido?` body `Esta acción no se puede deshacer.`
  - Action: `Cancelar`
  - Share link title: `Compartir enlace público`, content `🔗`
- Pagination: `Mostrando {{start}}–{{end}} de {{total}} pedidos`
- Empty title: `No hay pedidos pendientes`
- Pagination links: `← Anterior`, `Siguiente →`

### 3. Displayed data

| Column | Semantics | Example |
|---|---|---|
| (checkbox) | select | `<input>` |
| `Estado` | status badge | `Entregado` |
| `Cliente` | customer + phone | `María (0981…)` |
| `Fecha prometida` | promised_date + time | `08/10 09:00` |
| `Canal` | channel | `mostrador` |
| `Pago` | payment_intent | `efectivo` |
| `Líneas` | line count | `3` |
| `Total` | total Gs. | `Gs. 80.000` |
| `Acciones` | buttons | `Ver Cumplir Cancelar 🔗` |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Cliente phone | `Compras últimos 30 días` |
| `Atrasado {{d}}d` | `atrasado` |
| Ventana preferida badge | `Ventana preferida` |
| Cumplir confirm title | `¿Cumplir pedido?` |
| Cumplir confirm body | `Marcá este pedido como entregado.` |
| Cancelar confirm title | `¿Cancelar pedido?` |
| Cancelar confirm body | `Esta acción no se puede deshacer.` |
| Share link | `Compartir enlace público` |

### 6. UX/copy audit — flags

- `🔗` share icon button is unicode — relies on title for accessibility.
- Confirm-modal copies are clear and consistent.
- `vt|truncate(28)` — Ventana preferida can be cut off mid-word.
- Status badges vary in color (good/danger/warn/neutral) — operator learns the system.

---

## pedidos_nuevo.html — New pedido form

### 1. Identity
- **URL/route**: `/pedidos/nuevo`
- **Page title**: `Nuevo pedido`
- **Section**: Orders / create
- **User persona**: Operator

### 2. Structure
- This is a **long form** with multiple fieldsets:
  - Customer picker (label `Cliente`, placeholder `Buscá por nombre o teléfono — escribí 2+ letras`)
  - Inline customer-create form:
    - `Nombre *` (placeholder `Ej: María González`)
    - `Teléfono` (placeholder `+595 9XX XXXXX`)
    - `RUC / CI (para factura)` (placeholder `80012345-6`)
    - `Email` (placeholder `cliente@correo.com`)
    - `Notas internas (alergias, preferencias…)` (textarea placeholder `Sin TACC, retira siempre antes de las 17h, etc.`)
    - Cancel button: `Cancelar`
  - Customer hint: `Teléfono (opcional)`, placeholder `+595 9XX XXXXX`
  - Customer picked hint: `Cliente seleccionado` (italic muted `Ninguno — se crea al guardar`)
  - Pedido fields:
    - `Fecha prometida`
    - `Hora (opcional)`
    - `Canal` (combo placeholder `Seleccioná canal...`)
    - `Forma de pago esperada` (combo placeholder `Seleccioná forma de pago...`)
    - `Zona de delivery` (combo placeholder `Pickup (gratis) — seleccioná zona…`)
    - `Dirección de envío (si es delivery)` (textarea placeholder `Calle, número, barrio, referencia…`)
    - Address components: `Calle principal`, `Calle secundaria / entrecalles`, `Número`, `Edificio`, `Piso`, `Unidad / Puerta`, `Barrio`, `Ciudad`, `Departamento`, `Código postal`
    - `Entregar a` (placeholder `Lucía — mamá`)
    - `Tipo de dirección` (combo, default `HOME` display `Casa`, placeholder `Elegí tipo…`)
    - `Instrucciones para el cadete` (textarea placeholder `Timbre roto, llamar antes, portero de 8 a 17…`)
  - Ventana de entrega legend:
    - Radio: `Lo antes posible`
    - Radio: `En una franja horaria (preferida, no es garantía)` → `Desde`, `Hasta`
    - Radio: `Programar para otro día` → `Fecha programada`
  - Facturación:
    - `Perfil de facturación` (select)
    - `RUC / CI (para factura)` (placeholder `80012345-6`, inputmode `numeric`)
    - `Nombre / razón social` (placeholder `Para la factura`)
    - Switch: `Guardar dirección en la ficha del cliente` (with text input placeholder `Etiqueta: casa / oficina / mamá…`)
  - `Notas` (textarea placeholder `Sin TACC, retirar antes de las 17h, etc.`)
  - Items section H2: `Ítems` (placeholder: `Tocá «+ Agregar ítem» para sumar líneas. El precio queda guardado al crear el pedido.`)
  - Items table headers: `Producto`, `Cantidad`, `Precio unit. (Gs.)`
  - Product search (placeholder `Escribí para buscar (muffin, factura, pan…)`)
  - Per-line remove button: `Quitar`
  - Cancel link: `Cancelar`

### 3. Displayed data

**Standard pedido fields:**
| Field | Semantics |
|---|---|
| `Fecha prometida` | promised_date |
| `Hora (opcional)` | promised_time |
| `Canal` | channel |
| `Forma de pago esperada` | payment_intent |
| `Zona de delivery` | zone_id |
| `Dirección de envío` | free-text address |
| Address structured fields | calle/numero/edificio/piso/unidad/barrio/ciudad/departamento/codigo_postal |
| `Entregar a` | recipient_name |
| `Tipo de dirección` | HOME / OFFICE / OTHER (combo) |
| `Instrucciones para el cadete` | delivery_instructions |

**Window legend:**
- `Lo antes posible` (ASAP)
- `En una franja horaria` (delivery_window_start / delivery_window_end)
- `Programar para otro día` (delivery_scheduled_date)

**Facturación:**
| Field | Semantics |
|---|---|
| `Perfil de facturación` | invoice profile (from customer) |
| `RUC / CI` | invoice_ruc |
| `Nombre / razón social` | invoice_name |
| `Guardar dirección` | save_address switch |

### 5. Tooltips

(none)

### 6. UX/copy audit — flags

- Form is **very long** (~666 lines). Multiple fieldsets with helper text.
- All placeholders use `Ej:` prefix with realistic Paraguayan examples.
- `Lo antes posible` / `En una franja horaria (preferida, no es garantía)` — clarification in parens is helpful.
- "Tipo de dirección" combo shows `HOME / OFFICE / OTHER` (English values); display in Spanish.
- Customer picker has its own search input with `2+ letras` hint.

---

## menus.html — Executive menus (combos)

### 1. Identity
- **URL/route**: `/menus`
- **Page title**: `Menús ejecutivos` (block)
- **Section**: Menus / combos
- **User persona**: Manager

### 2. Structure
- H1
- Description: `Combo con precio propio: se vende como una unidad y descuenta el stock de cada producto incluido.`
- H2: `Nuevo menú`
- Form: `Nombre` (placeholder `Menú ejecutivo lunes`), `Precio (Gs.)` (placeholder `25000`)
- Legend: `Productos incluidos`
- Per-product row: `Cantidad de {{name}}`
- Submit: `Crear menú`
- H2: `Activos ({{count}})`
- Empty: `Todavía no hay menús. Creá el primero arriba.`
- Table headers: `Menú`, `Precio`, `Incluye`, (action)
- Off confirm title: `¿Desactivar menú?`
- Off confirm body: `El menú dejará de mostrarse como activo.`
- Action button: `Desactivar`

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Menú` | menu name |
| `Precio` | price Gs. |
| `Incluye` | comma-separated product list |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Off confirm title | `¿Desactivar menú?` |
| Off confirm body | `El menú dejará de mostrarse como activo.` |

### 6. UX/copy audit — flags

- Description explains the model (combo with own price, stock decrements per product).
- Form has min=1000 step=1000 on price — prevents typos.

---

## menu_import_ocr.html — OCR-based menu import

### 1. Identity
- **URL/route**: `/menus/importar` or `/menus/import_ocr`
- **Page title**: `Menús / Importar` (block)
- **Section**: Menus / OCR import
- **User persona**: Manager, admin

### 2. Structure
- H1
- Warning if OCR not configured: `OCR no configurado: falta la variable de entorno <code>ZAI_API_KEY</code>.`
- Callout: `No marcaste ninguna fila para importar.`
- File field: `<span>Foto de la carta (JPG/PNG/WebP, máx 8MB)</span>`
- H2: `Revisá antes de confirmar`
- Preview table headers: (select), `Nombre`, `Precio (Gs)`, `Categoría`, `Estado`
- Per-row status badges: `existe (actualiza precio)` (badge-ok), `dudoso` (badge-warn), `nuevo` (plain badge)
- Submit: `Importar seleccionadas`
- Helper: `Preview generado por IA — revisá precios y nombres antes de confirmar.`

### 3. Displayed data

| Column | Semantics |
|---|---|
| (select) | import? |
| `Nombre` | menu name |
| `Precio (Gs)` | price |
| `Categoría` | category |
| `Estado` | status: existe / nuevo / dudoso |

### 5. Tooltips

(none)

### 6. UX/copy audit — flags

- OCR powered by ZAI (Zhipu AI) — backend env var `ZAI_API_KEY`.
- 3-state preview status (exists / new / doubtful) — operator reviews before commit.
- AI disclaimer in helper text.

---

## menu_publico.html — Public menu (no login)

### 1. Identity
- **URL/route**: `/m/{slug}` or `/menu_publico`
- **Page title**: (none — public)
- **Section**: Menus / public view
- **User persona**: Customer

### 2. Structure
- H1: `<shop_name>` (uses brand_color if set)
- Category nav: aria-label `Categorías`, links `<a href="#cat-{{key}}">{{label}}</a>`
- Per-category H2: `id="cat-{{key}}"` + label
- Per-item link: `<a href="/m/{{tablet_slug}}">{{name}}</a>`
- Empty: `El menú todavía no tiene productos publicados.`
- Hint: `Consultá disponibilidad por WhatsApp.`
- Cart counter: `<strong id="mp-cart-count">0</strong> ítems · <strong id="mp-cart-total"></strong>`
- Cart button: `Vaciar` (id `mp-cart-clear`)

### 3. Displayed data

| Field | Semantics |
|---|---|
| `<shop_name>` | business name (with brand color) |
| Category nav | anchor links |
| Per-item | product name + link to tablet view |

### 5. Tooltips

(none)

### 6. UX/copy audit — flags

- Customer-facing — Spanish.
- WhatsApp fallback when menu empty.
- Brand-color customization via tenant settings.

---

## menu_tablet.html — Tablet-mode menu view

### 1. Identity
- **URL/route**: `/m/{slug}/t` (tablet mode)
- **Page title**: (none — tablet UI)
- **Section**: Menus / tablet view
- **User persona**: Customer (at counter)

### 2. Structure
- H1: `<shop_name>` (with brand_color)
- Subtitle: `Menú del día`
- Photo fallback: `<div class="menu-tablet__photo-fallback" aria-label="Sin foto">`
- Per-product:
  - H2 (id `product-name`): `<product.name>`
  - Price div (aria-label `Precio`): `<span class="menu-tablet__price-label">Precio</span>`
  - Tags ul (aria-label `Etiquetas`)

### 5. Tooltips

(none; aria-labels only)

### 6. UX/copy audit — flags

- Tablet UI optimized for counter display — large fonts, no clutter.
- aria-labels used for icon-only/no-text elements.

---

## suppliers.html — Supplier list

### 1. Identity
- **URL/route**: `/suppliers`
- **Page title**: `Proveedores`
- **Section**: Suppliers
- **User persona**: Manager

### 2. Structure
- H1: `Proveedores`
- Table headers: `Nombre`, `Contacto`, `Teléfono`, `Email`, `RUC`, `Ingredientes`
- Per-row:
  - Inactive badge: `inactivo` (badge-muted)
  - Ingredients count: `<span class="badge badge-neutral">{{count}}</span>`
  - Empty: `<em class="muted">ninguno</em>`
- Off confirm title: `¿Desactivar proveedor?`
- Off confirm body: `¿Desactivar {{name}}? Los ingredientes vinculados conservan su referencia pero el proveedor no aparece en /reorder. Podés reactivarlo después.`
- Off button: `Desactivar` (btn-danger)
- Pagination: `Mostrando 1–25 de {{total}} proveedores`
- Empty: `No hay proveedores todavía — Agregá proveedores para poder contactarlos desde la página de reorden.`
- Empty CTA: `Agregar el primero` (link to /suppliers/nuevo)

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Nombre` | supplier name |
| `Contacto` | contact_name |
| `Teléfono` | phone |
| `Email` | email |
| `RUC` | ruc |
| `Ingredientes` | count badge |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Off confirm title | `¿Desactivar proveedor?` |
| Off confirm body | `¿Desactivar {{name}}? Los ingredientes vinculados conservan su referencia pero el proveedor no aparece en /reorder. Podés reactivarlo después.` |

### 6. UX/copy audit — flags

- Clear empty state with CTA.
- Off confirmation explains what inactive supplier means (still referenced, just hidden from /reorder).

---

## supplier_form.html — New/edit supplier form

### 1. Identity
- **URL/route**: `/suppliers/nuevo` or `/suppliers/{id}/editar`
- **Page title**: `<Nuevo|Editar> proveedor`
- **Section**: Suppliers

### 2. Structure
- Form labels:
  - `Nombre del proveedor *` (placeholder `Ej: Harinas del Paraguay S.A.`)
  - `Persona de contacto` (placeholder `Ej: Juan Pérez`)
  - `Teléfono` (placeholder `Ej: +595 21 123 456`)
  - `Email` (placeholder `Ej: ventas@harinas.com.py`)
  - `Dirección`
  - `RUC / Cédula` (placeholder `Ej: 12345678-9`)
  - `Notas`
- Buttons: `Guardá` (submit), `Cancelar` (link to /suppliers)

### 6. UX/copy audit — flags

- `Guardá` (Spanish voseo, Paraguay) — culturally correct, consistent with Paraguayan audience.
- All placeholders use `Ej:` prefix.

---

## supplier_orders.html — Order to one supplier

### 1. Identity
- **URL/route**: `/suppliers/{id}/orders`
- **Page title**: `Pedido a {{name}}`
- **Section**: Suppliers / orders
- **User persona**: Manager

### 2. Structure
- H1: `Pedido a {{supplier_name}}`
- H3: `Datos de contacto`
- Per-field: `Contacto: {{contact_name}}`, `Teléfono: {{phone}}`, `Email: {{email}}`
- H2: (orders / message area)
- Hint: `El mensaje incluye todos los ingredientes bajo mínimo de este proveedor.`
- Card: `Ingredientes bajo mínimo`
- Empty: `No hay ingredientes de este proveedor que estén bajo el mínimo de stock.`
- H2: `Ingredientes para reponer`
- Table headers: `Ingrediente`, `Stock actual`, `Mínimo`, `Sugerido`, `Costo est.`, `Total estimado`
- Back link: `← Volver a proveedores`

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Ingrediente` | name |
| `Stock actual` | on hand |
| `Mínimo` | min threshold |
| `Sugerido` | suggested order qty |
| `Costo est.` | unit cost |
| `Total estimado` | line total |

### 5. Tooltips

(none)

### 6. UX/copy audit — flags

- "Datos de contacto" repeats supplier info — operator has full context.
- Empty state message is clear.

---

## supplier_precios.html — Supplier price comparison

### 1. Identity
- **URL/route**: `/suppliers/precios` or `/suppliers/{id}/precios`
- **Page title**: `Comparación de precios`
- **Section**: Suppliers / pricing
- **User persona**: Manager

### 2. Structure
- H1: `Comparación de precios`
- H2: `Resumen`
- KPI cards (3): `Proveedores comparados`, `Ingredientes con más de un proveedor`, `Ahorro potencial por unidad`
- H2: `Precios por ingrediente`
- Table 1 headers: `Ingrediente`, `Unidad`, `Proveedor más barato`, `Diferencia`, `Ahorro / unidad`
- Per-row: `el más barato` badge (badge-ok), `+{{delta_pct}}%` badge (badge-danger)
- Table 2 headers: `Proveedor`, `Precio`, `vs. más barato`
- H2: `¿Cómo está posicionado {{supplier_name}}?`
- Table 3 headers: `Ingrediente`, `Precio`, `Posición`, `Estado`
- Empty tooltip: `Sin datos de comparación todavía`
- Back link: `← Volver a proveedores`

### 3. Displayed data

**Price comparison table 1:**
| Column | Semantics |
|---|---|
| `Ingrediente` | ingredient name |
| `Unidad` | unit (kg, l, und) |
| `Proveedor más barato` | supplier name |
| `Diferencia` | price diff |
| `Ahorro / unidad` | savings per unit |

**Per-supplier table 2:**
| Column | Semantics |
|---|---|
| `Proveedor` | supplier name |
| `Precio` | price Gs. |
| `vs. más barato` | % diff |

**Position table 3:**
| Column | Semantics |
|---|---|
| `Ingrediente` | ingredient name |
| `Precio` | price Gs. |
| `Posición` | rank (1 = cheapest) |
| `Estado` | el más barato / más caro |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Empty | `Sin datos de comparación todavía` |

### 6. UX/copy audit — flags

- 3 tables = a lot for one page; could be condensed.
- `Ahorro potencial` KPI shows aggregate savings.
- Per-position badges use `el más barato` (badge-ok) and `+X%` (badge-danger).

---

## suppliers_volatility.html — Supplier price volatility

### 1. Identity
- **URL/route**: `/suppliers/volatility`
- **Page title**: `Volatilidad de precios` (block)
- **Section**: Suppliers / analytics
- **User persona**: Manager

### 2. Structure
- H1
- Hint paragraph
- Filter label
- Table headers: `Proveedor`, `Ingredientes`, `Eventos`, `Mín ₲`, `Máx ₲`, `Promedio ₲`, `Volatilidad`, `Tendencia`, `Último hace`, `Acción`
- Per-row:
  - Supplier link: `<a href="/suppliers/{id}/precios">{{name}}</a>`
  - Trend indicator: `<span class="hint">⚠</span>`
- Empty: `Sin datos de precios por proveedor`
- Helper: mentions `supplier_id` and `/inventario` data path

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Proveedor` | supplier name + link |
| `Ingredientes` | count |
| `Eventos` | price-change event count |
| `Mín ₲` | min price Gs. |
| `Máx ₲` | max price Gs. |
| `Promedio ₲` | avg price Gs. |
| `Volatilidad` | std dev / coefficient |
| `Tendencia` | trend indicator |
| `Último hace` | days since last event |
| `Acción` | link to detail |

### 5. Tooltips

(none; uses `hint` class for icons)

### 6. UX/copy audit — flags

- Uses `₲` (Guaraní sign) — Unicode; may not render in all fonts.
- 10-column table is wide.
- "Eventos" = price events (recorded changes).
- Helper text references `supplier_id` field — operator-friendly wording but technical.

---

## delivery_zones.html — Delivery zones

### 1. Identity
- **URL/route**: `/delivery_zones` or `/admin/delivery_zones`
- **Page title**: `Zonas de delivery`
- **Section**: Delivery
- **User persona**: Manager, admin

### 2. Structure
- Table headers: `Zona`, `Cobertura`, `Radio`, `Costo Gs.`, `Pedido mín Gs.`

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Zona` | zone name |
| `Cobertura` | coverage description |
| `Radio` | radius |
| `Costo Gs.` | delivery cost |
| `Pedido mín Gs.` | minimum order Gs. |

### 5. Tooltips

(none)

### 6. UX/copy audit — flags

- Light page — just a table.
- Add/edit presumably happens via inline forms or modal (not in this template).

---

## shopping_list.html — Shopping list

### 1. Identity
- **URL/route**: `/shopping_list`
- **Page title**: `Lista de compras`
- **Section**: Shopping
- **User persona**: Manager, operator

### 2. Structure
- Form: ingredient search filter
- Table headers: `Ingrediente`, `Cantidad`, `Unidad`, `Costo est.`, `Proveedor sugerido`, (checkbox)
- Actions: `Marcar comprado`, `Enviar a lista`
- Grouped by supplier (header per supplier)
- Empty per-supplier: `Sin ingredientes faltantes de {{supplier}}.`

### 3. Displayed data

| Column | Semantics |
|---|---|
| `Ingrediente` | name |
| `Cantidad` | needed qty |
| `Unidad` | unit |
| `Costo est.` | unit cost × qty |
| `Proveedor sugerido` | suggested supplier name |
| (checkbox) | mark purchased |

### 6. UX/copy audit — flags

- List is grouped by supplier for efficient shopping.
- Sends to /reorder when needed.

---

## reorder.html — Reorder assistant

### 1. Identity
- **URL/route**: `/reorder`
- **Page title**: `Reponer stock`
- **Section**: Shopping / reorder
- **User persona**: Manager, operator

### 2. Structure
- H1: `Reponer stock`
- Subtitle: `Lista de lo que tenés que comprar hoy`
- Status cards: `Sin stock` (count), `Bajo mínimo` (count)
- Hint: `Seleccioná los que vas a comprar y mandá el pedido por WhatsApp`
- Bulk select buttons: `Seleccionar todos bajo mínimo`, `Seleccionar todos agotados`
- Filter: `Buscar ingrediente…`
- Sort: `Ordenar por` (urgencia, alfabético, costo)
- Per-ingredient row:
  - Checkbox
  - Nombre + stock badge (`Sin stock` or `Bajo stock`)
  - Unidad
  - Cantidad actual
  - Mínimo
  - Sugerido (input)
  - Última compra
  - Costo unitario
  - Total
  - WhatsApp link per supplier
- Bottom bar: `<strong>X seleccionados</strong>`, total Gs., `Generar pedido a proveedor` button
- Summary: `Resumen de hoy (resumen)`
- Legend block explaining badges

### 3. Displayed data

| Column | Semantics |
|---|---|
| Nombre | ingredient name |
| Stock | badge (Sin stock / Bajo stock) |
| Unidad | unit |
| Actual | current qty |
| Mínimo | min threshold |
| Sugerido | suggested qty (editable) |
| Última compra | date |
| Costo unit. | unit cost Gs. |
| Total | line total Gs. |

### 5. Tooltips

| Element | Tooltip text |
|---|---|
| Última compra | (date string) |
| Sugerido | title explaining suggestion |

### 6. UX/copy audit — flags

- Color-coded status badges (red = sin stock, yellow = bajo stock).
- WhatsApp CTA per supplier.
- Generate-pedido button creates a supplier order.

---

## Section-wide issues

### Cross-page consistency

| Issue | Pages affected | Notes |
|---|---|---|
| **English loan words in production** | produccion.html, produccion_manana.html, planner.html, supplier_precios.html | `forecast`, `override`, `template`, `target`, `rolling 14d` — Paraguayan users may need glossary. |
| **Currency symbol consistency** | suppliers_volatility.html uses `₲`; most other pages use `Gs.`. | Both are valid Guaraní forms; recommend one standard. |
| **`Registr&aacute; ahora`** | produccion.html | HTML entity for `á`; correct but inconsistent. |
| **Color-only status signals** | Many | Badges use color + text (good), but some use color + emoji (⚠) without text (reorder). |
| **Confirm modal text consistency** | pedidos.html, suppliers.html, menus.html | Templates use `data-confirm-title`, `data-confirm-body`, `data-confirm-danger` consistently. |
| **`Pago` vs `Forma de pago`** | pedidos.html uses `Pago`; ventas.html uses `Forma de pago`; ventas.html POSTS as `payment_method`. | Inconsistent. |
| **`Pedido` vs `Orden`** | All use `Pedido` — consistent. ✓ |
| **`Entrega` vs `Delivery`** | pedidos_nuevo uses `Entrega` and `Delivery` interchangeably (`Dirección de envío`, `delivery_zone`). | Inconsistent. |
| **`ASAP` vs `Lo antes posible`** | pedidos.html uses `ASAP` badge; pedidos_nuevo.html uses `Lo antes posible`. | Inconsistent terminology. |

### Copy issues

| Page | Issue |
|---|---|
| produccion.html | Many tooltips are very long (`Fermentar {{N}}h...`); some operators may not read them. |
| produccion.html | `<kbd>J</kbd>/<kbd>K</kbd> navegar · <kbd>O</kbd> override · <kbd>C</kbd> cerrar día` — keyboard shortcuts documented but not on the help page. |
| produccion_haccp.html | Range values are hardcoded in JS (`-22 a -18 °C`). Not configurable. |
| pedidos_nuevo.html | 666-line form; could be split into steps/wizard. |
| pedidos_nuevo.html | Address fields structured (calle/numero/etc.) PLUS free-text `address_text` — risk of duplicate data. |
| pedido_publico.html | Footer note: `Si necesitás cambiar algo, respondé por WhatsApp` — uses WhatsApp brand name (OK for Paraguay). |
| menus.html | Description is helpful but could link to a tutorial. |
| menu_import_ocr.html | AI disclaimer in helper — good. |
| supplier_form.html | `Guardá` (voseo) — culturally correct in PY. |
| reorder.html | Many columns; could use a card-based layout on mobile. |

### Spanish-language quality

- Generally **excellent** Spanish; Paraguayan voseo (`Guardá`, `necesitás`, `buscá`) used consistently.
- Technical terms (HACCP, OCR, KPI, accuracy) are mostly English — appropriate for technical UI.
- Some emoji used (`📋`, `📝`, `📊`, `📅`, `⏰`, `🔇`, `🔗`, `✓`, `⚠`, `🍰`) — friendly but accessibility-questionable.
- Numbers format: `Gs. 8.000` (with period as thousands separator) — correct for es-PY.

### Accessibility gaps

- Most icon-only buttons have aria-label or title — good.
- Keyboard shortcuts documented but not in help page.
- `kbd` elements used for shortcuts — accessible.
- Color-only signal: `+{{delta_pct}}%` (badge-danger) on supplier_precios.html — should also have text indicator.

### What's missing

- **No template-by-template deep-dive of every modal/popup** — modals are dynamically inserted by `js-confirm-form` plugin.
- **No JS-injected DOM** audit — many pages have JS that builds filter pills, sort headers, etc.
- **No per-page router audit** — context variables (e.g. `for_date`, `pedido_id`) come from routes.
- **No audit of `_components/calendar.html`** — used in production date picker.

---

*End of Section C — Production + Supply Chain*