# Saskia RMS — Atomic Jinja Macro Contracts

**Author:** Designer drop — subagent 2026-09-27
**Scope:** 10 atomic Jinja macros forming the canonical UI vocabulary across the Saskia RMS bakery management app.
**Inputs consumed (read once, not re-analyzed):**

- `/tmp/designer-drop/cross-page-wishlist-consolidation.md` — lists the 10 macros, their roles, and rollout matrix
- `/tmp/designer-drop/audit-batch2-prod.md` — 14 pages (Inventario, Producción, Pedidos, Receta)
- `/tmp/designer-drop/audit-batch3-reports.md` — 14 pages (Proveedores, Reponer, Lista de compras, Wishlist, Pricing, Vs-mercado, Bank, Riesgos, Auditoría, Reportes)

**Spec conventions**

- Type hints use Python syntax (`str`, `int`, `float`, `bool`, `list[str]`, `dict`, `None`).
- "required" means the macro must be passed a value (default is `None`/missing).
- All `datetime` / `date` arguments are ISO-8601 strings (`"2026-09-27"`) unless noted.
- All money arguments are **integer Guaraní** (no decimals) — render as `Gs. 1.234.567` (period thousands separator). When the caller passes a float, the macro rounds to the nearest integer.
- All currency formatting respects locale (`es_PY`) — never show `.00` for integer values, never show four-digit thousands (`Gs. 1234` is wrong, use `Gs. 1.234`).
- Spanish-first copy throughout. Latin American voseo is used **only** in CTA buttons where it matches existing pages ("Guardá", "Cancelá" stay; "Editar", "Filtrar" stay as infinitives). Pick what the source page already uses; the macro neither adds nor strips accent marks.
- 4px severity stripe convention: `ok`, `info`, `warn`, `danger` — order matters for left-to-right visual triage.
- Web Components are namespaced `<saskia-*>` (custom elements).
- Icons are referenced by `lucide` name (e.g., `alert-triangle`); the macro injects the SVG via the `<saskia-icon>` component, never inline SVG.

---

# Macro 1: `kpi_tile(label, value, delta=None, delta_direction=None, severity='neutral', icon=None, href=None, tooltip=None, count=None, sublabel=None)`

## Purpose

Render a single-card KPI metric (label + big number + optional Δ vs prior period + optional sparkline) for use in dashboard strips, list-page headers, and report summary tiles.

## Arguments

| Argument          | Type                          | Default       | Required | Notes |
|-------------------|-------------------------------|---------------|----------|-------|
| `label`           | `str`                         | —             | ✅       | Short sentence-case label (e.g., "Stock crítico", "Ventas del día"). |
| `value`           | `str \| int \| float \| None` | —             | ✅       | Pre-formatted display string OR numeric value (auto-format). `None` → renders `—`. |
| `delta`           | `str \| float \| None`        | `None`        | ❌       | Change vs prior period. Numeric → auto-formatted with sign; string → raw. |
| `delta_direction` | `str \| None`                 | `None`        | ❌       | One of `up` / `down` / `flat`. Auto-inferred from numeric `delta` sign; pass explicitly when `delta` is a pre-built string. |
| `severity`        | `str`                         | `"neutral"`   | ❌       | One of `ok` / `info` / `warn` / `danger` / `neutral` / `muted`. Drives the left-border color + icon tint. |
| `icon`            | `str \| None`                 | `None`        | ❌       | Lucide icon name (e.g., `"alert-triangle"`, `"trending-up"`). |
| `href`            | `str \| None`                 | `None`        | ❌       | If present, whole tile becomes an `<a>`. |
| `tooltip`         | `str \| None`                 | `None`        | ❌       | Hover explainer (max 140 chars). Rendered as `<abbr title>` + `<saskia-tooltip>`. |
| `count`           | `int \| None`                 | `None`        | ❌       | Sub-count (e.g., "3 ingredientes"). Shows below the value in muted text. |
| `sublabel`        | `str \| None`                 | `None`        | ❌       | Right-aligned micro-context (e.g., "esta semana", "mes pasado"). |
| `sparkline`       | `list[float] \| None`         | `None`        | ❌       | 8-30 numeric points → renders a 56×18 sparkline. |

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/kpi_tile.html #}
{% macro kpi_tile(
     label,
     value,
     delta=None,
     delta_direction=None,
     severity='neutral',
     icon=None,
     href=None,
     tooltip=None,
     count=None,
     sublabel=None,
     sparkline=None
) %}
  {% set eff_dir = delta_direction %}
  {% if eff_dir is none and delta is not none %}
    {% if delta is number %}
      {% set eff_dir = ('up' if delta > 0 else ('down' if delta < 0 else 'flat')) %}
    {% endif %}
  {% endif %}
  {% set display_value = '—' if value is none else (value if value is string else '{:,.0f}'.format(value) if value == value|int else '{:,.2f}'.format(value)) %}
  {% set display_delta = delta %}
  {% if delta is number %}
    {% set display_delta = ('+' ~ '{:,.0f}'.format(delta) if delta > 0 else '{:,.0f}'.format(delta)) %}
  {% endif %}

  <article class="kpi-tile kpi-tile--{{ severity }}"
           {% if href %}tabindex="0" role="link"{% endif %}
           {% if tooltip %}aria-describedby="kpi-tt-{{ label|lower|replace(' ', '-') }}"{% endif %}>
    {% if href %}<a class="kpi-tile__link" href="{{ href }}" aria-label="{{ label }}: {{ display_value }}">{% endif %}
      <header class="kpi-tile__head">
        {% if icon %}<saskia-icon name="{{ icon }}" class="kpi-tile__icon" aria-hidden="true"></saskia-icon>{% endif %}
        <span class="kpi-tile__label"{% if tooltip %} title="{{ tooltip }}"{% endif %}>{{ label }}</span>
        {% if tooltip %}<span id="kpi-tt-{{ label|lower|replace(' ', '-') }}" hidden>{{ tooltip }}</span>{% endif %}
      </header>
      <div class="kpi-tile__value" aria-live="polite">{{ display_value }}</div>
      <footer class="kpi-tile__foot">
        {% if display_delta is not none %}
          <span class="kpi-tile__delta kpi-tile__delta--{{ eff_dir or 'flat' }}"
                aria-label="{{ 'Subió' if eff_dir == 'up' else ('Bajó' if eff_dir == 'down' else 'Sin cambio') }} {{ display_delta }}">
            {% if eff_dir == 'up' %}<saskia-icon name="arrow-up" aria-hidden="true"></saskia-icon>
            {% elif eff_dir == 'down' %}<saskia-icon name="arrow-down" aria-hidden="true"></saskia-icon>
            {% else %}<saskia-icon name="minus" aria-hidden="true"></saskia-icon>{% endif %}
            {{ display_delta }}
          </span>
        {% endif %}
        {% if sublabel %}<span class="kpi-tile__sublabel">{{ sublabel }}</span>{% endif %}
        {% if count is not none %}<span class="kpi-tile__count">{{ count }}</span>{% endif %}
      </footer>
      {% if sparkline %}
        <saskia-sparkline data-points="{{ sparkline|tojson }}" aria-hidden="true"></saskia-sparkline>
      {% endif %}
    {% if href %}</a>{% endif %}
  </article>
{% endmacro %}
```

### Rendered example 1 — Inventario list "Stock crítico"

Input:

```jinja
{{ kpi_tile(
    label='Stock crítico',
    value=1,
    delta=-1, delta_direction='down',
    severity='warn',
    icon='alert-triangle',
    href='/inventario?filter=critico',
    tooltip='Ingredientes con stock por debajo del mínimo',
    sublabel='vs semana anterior'
) }}
```

Rendered HTML (whitespace added for readability):

```html
<article class="kpi-tile kpi-tile--warn" tabindex="0" role="link"
         aria-describedby="kpi-tt-stock-crítico">
  <a class="kpi-tile__link" href="/inventario?filter=critico" aria-label="Stock crítico: 1">
    <header class="kpi-tile__head">
      <saskia-icon name="alert-triangle" class="kpi-tile__icon" aria-hidden="true"></saskia-icon>
      <span class="kpi-tile__label" title="Ingredientes con stock por debajo del mínimo">Stock crítico</span>
      <span id="kpi-tt-stock-crítico" hidden>Ingredientes con stock por debajo del mínimo</span>
    </header>
    <div class="kpi-tile__value" aria-live="polite">1</div>
    <footer class="kpi-tile__foot">
      <span class="kpi-tile__delta kpi-tile__delta--down"
            aria-label="Bajó -1">
        <saskia-icon name="arrow-down" aria-hidden="true"></saskia-icon>
        -1
      </span>
      <span class="kpi-tile__sublabel">vs semana anterior</span>
    </footer>
  </a>
</article>
```

### Rendered example 2 — Pricing "Costo total (batch)" with sparkline

```html
<article class="kpi-tile kpi-tile--neutral">
  <header class="kpi-tile__head">
    <saskia-icon name="coins" class="kpi-tile__icon" aria-hidden="true"></saskia-icon>
    <span class="kpi-tile__label">Costo total (batch)</span>
  </header>
  <div class="kpi-tile__value" aria-live="polite">Gs. 167.500</div>
  <footer class="kpi-tile__foot">
    <span class="kpi-tile__delta kpi-tile__delta--up" aria-label="Subió +12.300">
      <saskia-icon name="arrow-up" aria-hidden="true"></saskia-icon>
      +12.300
    </span>
    <span class="kpi-tile__sublabel">vs semana anterior</span>
  </footer>
  <saskia-sparkline data-points="[142000,148500,153200,160000,167500]" aria-hidden="true"></saskia-sparkline>
</article>
```

### Rendered example 3 — Empty state ("0 proveedores")

```html
<article class="kpi-tile kpi-tile--muted">
  <header class="kpi-tile__head">
    <saskia-icon name="users" class="kpi-tile__icon" aria-hidden="true"></saskia-icon>
    <span class="kpi-tile__label">Proveedores</span>
  </header>
  <div class="kpi-tile__value" aria-live="polite">0</div>
  <footer class="kpi-tile__foot"></footer>
</article>
```

## Behavior rules

| Condition                                  | Behavior |
|--------------------------------------------|----------|
| `value is None`                            | Renders `—` (em-dash), `aria-live="polite"` for screen-reader updates on later change. |
| `value` is `int`                           | Formatted with thousands separator (no decimals): `1234 → "1.234"`. |
| `value` is `float`                         | Truncated to 2 decimals: `3.14 → "3,14"`; if value rounds to integer (`3.0`), strip the decimal: `3 → "3"`. |
| `value` is `str`                           | Rendered verbatim (caller has already formatted). Pass `Gs.`-prefixed strings here. |
| `delta is None`                            | Delta slot hidden — no arrow, no number. |
| `delta` is `0`                             | Rendered as `0` with `flat` direction; icon is `minus`. |
| `delta` is negative and `delta_direction` not provided | Auto-infers `down`. |
| `delta` is a pre-formatted `str`           | Rendered verbatim; **caller must set `delta_direction`**. |
| `href` provided                            | Whole tile becomes a focusable element with `tabindex="0"`, `role="link"`, wrapped in `<a>`. |
| `href is None`                             | Renders as a `<article>` — no link, no focus ring. |
| `tooltip` longer than 140 chars            | Truncated with ellipsis at word boundary; tooltip text gets a `title` attribute (browser-native) and the longer text is also rendered in `<saskia-tooltip>` content slot for an expanded hover panel. |
| `severity` is invalid                      | Falls back to `neutral`, logs a console warning once. |
| `sparkline` length                         | 1 point renders nothing; 2-7 points renders a placeholder "—"; 8-90 points renders at full fidelity. |
| Negative `value`                           | Rendered with leading minus, **never** tinted red automatically (severity drives color). |
| Very large `value` (>999.999.999)          | Format with thin-space grouping (locale-aware). |

### Accessibility

- `aria-live="polite"` on value container so screen readers announce value updates.
- Delta has full aria-label ("Subió 12", not just "↑").
- `tabindex="0"` only when `href` is present (avoids trap of focusable non-links).
- Tooltip is exposed via both `title` (instant) and `<saskia-tooltip>` (rich). Never render critical info only inside the title attribute.
- Color is **never** the only signal: every tile has both an icon and a color.

### Locale

- Guaraní integer: `Gs. 1.234.567` (period thousands separator).
- Numbers under 1.000: no separator.
- Decimal (rare): comma, 2 digits: `Gs. 3,14`.
- Negative numbers: `Gs. -1.234` (sign before currency), not `(1.234)`.
- Date format in `sublabel`: `dd/mm/aaaa` when the sublabel contains a date.

## Used by

- **Inventario list** — `Stock crítico`, `Valor de inventario (Gs.)`, `Sin costo cargado`, `Total ingredientes` (with delta vs semana anterior).
- **Lista de compras** — `Items abiertos`, `Total estimado (Gs.)`, `Proveedores únicos`, `Comprados`.
- **Bank** — `EUR ingresos`, `EUR gastos`, `EUR neto`, `PYG balance` (with FX-rate `sublabel`).
- **Pricing** — `Recetas con pricing`, `Costo total (batch)`, `Valor minorista`.
- **Wishlist** — `Artículos totales`, `Pendientes`, `Comprados`, `Inversión total (Gs.)`, `Pendiente (Gs.)`.
- **Riesgos** — `Activos`, `Mitigados`, `Cerrados`, `Severidad total Σ`.
- **Producción** (board / planner) — `Costo estimado (Gs.)`, `Venta esperada (Gs.)`, `Margen %`, `Items para hoy`.
- **Pedidos board** — `Pedidos hoy`, `Ventas del día (Gs.)`, `Ticket promedio (Gs.)`, `Más antiguo pendiente`.
- **Pedido-detalle header** — `Total (Gs.)`, `Recibido`, `Saldo`, `Items cumplidos`.
- **Resumen diario** (Counters' home).
- **Reportes** index — last-run delta per card.

## Required Web Component / JS

- **`<saskia-icon>`** — wraps Lucide icons (`name` attribute).
- **`<saskia-tooltip>`** — rich tooltip with keyboard focus.
- **`<saskia-sparkline>`** — accepts `data-points` JSON, renders SVG inside shadow DOM. No-op when fewer than 8 points.
- No global JS required for the macro's own logic (the `arrow-up/down/minus` icons are static markup).

## Anti-patterns

- ❌ **Don't** use `<div class="kpi">` with a free-form inner HTML when this macro exists — use the macro instead.
- ❌ **Don't** pass a `delta` string without `delta_direction` if the string doesn't already contain `↑` / `↓` / `+` / `-` — the screen-reader `aria-label` will be wrong.
- ❌ **Don't** wrap the tile in a second `<a>` when `href` is set — the macro already renders an `<a>` inside.
- ❌ **Don't** set `severity='danger'` for visual emphasis when the value is **not** actually dangerous (e.g., "0 items fulfilled" should be `muted`, not `danger`). Reserve `danger` for true risks.
- ❌ **Don't** display currency inside a `kpi_tile`'s `value` AND `delta` separately — pick one or the other; `delta` should always be the delta-only number, not the running total.
- ❌ **Don't** use `kpi_tile` for table-row cells — it's a card, not a cell. Use a `<td>` with the `kpi_tile__value` styling instead.
- ❌ **Don't** rely on color alone when `severity` is `warn` — the arrow + label must also convey the message.
- ❌ **Don't** nest `kpi_tile` inside another `kpi_tile` — the layout breaks.
- ❌ **Don't** omit `label` even when "obvious from context" — screen readers can't infer it.

---

# Macro 2: `status_pill(label, tone='neutral', icon=None, tooltip=None, href=None, size='md', dot=False)`

## Purpose

Render a compact colored pill indicating a state (order status, ingredient alert, batch condition, etc.) — used everywhere a row, card, or cell needs to declare its current state.

## Arguments

| Argument   | Type            | Default     | Required | Notes |
|------------|-----------------|-------------|----------|-------|
| `label`    | `str`           | —           | ✅       | Spanish text rendered inside the pill. Capitalize first word only ("Pendiente", not "PENDIENTE"). |
| `tone`     | `str`           | `"neutral"` | ❌       | One of `ok` / `info` / `warn` / `danger` / `neutral` / `muted`. |
| `icon`     | `str \| None`   | `None`      | ❌       | Lucide name. If `dot=True`, the icon is rendered before the dot, not replacing it. |
| `tooltip`  | `str \| None`   | `None`      | ❌       | Popover explainer. |
| `href`     | `str \| None`   | `None`      | ❌       | If present, pill becomes a link. |
| `size`     | `str`           | `"md"`      | ❌       | `sm` (table-cell), `md` (default), `lg` (header banner). |
| `dot`      | `bool`          | `False`     | ❌       | Render a small colored dot before the label. Use when no icon is available. |

`tone` color tokens (do not change):

- `ok` → green (rgb 22 163 74; var `--pill-ok`)
- `info` → blue (rgb 37 99 235; var `--pill-info`)
- `warn` → amber (rgb 217 119 6; var `--pill-warn`)
- `danger` → red (rgb 220 38 38; var `--pill-danger`)
- `neutral` → gray-700 (rgb 55 65 81; var `--pill-neutral`)
- `muted` → gray-400 (rgb 156 163 175; var `--pill-muted`)

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/status_pill.html #}
{% macro status_pill(label, tone='neutral', icon=None, tooltip=None, href=None, size='md', dot=False) %}
  {% set Tag = 'a' if href else 'span' %}
  <{{ Tag }}
     class="pill pill--{{ tone }} pill--{{ size }}"
     {% if href %}href="{{ href }}"{% endif %}
     {% if tooltip %}title="{{ tooltip }}" data-tooltip="{{ tooltip }}"{% endif %}
     role="{% if href %}link{% else %}status{% endif %}"
     aria-label="{% if tone == 'ok' %}Correcto: {{ label }}{% elif tone == 'warn' %}Atención: {{ label }}{% elif tone == 'danger' %}Crítico: {{ label }}{% else %}{{ label }}{% endif %}">
    {% if dot %}<span class="pill__dot pill__dot--{{ tone }}" aria-hidden="true"></span>{% endif %}
    {% if icon %}<saskia-icon name="{{ icon }}" class="pill__icon" aria-hidden="true"></saskia-icon>{% endif %}
    <span class="pill__label">{{ label }}</span>
  </{{ Tag }}>
{% endmacro %}
```

### Rendered example 1 — Pedidos board (kanban card)

```jinja
{{ status_pill(label='Pendiente', tone='warn', icon='clock', tooltip='Aún no confirmado por el cliente', href='/pedidos/1') }}
```

```html
<a class="pill pill--warn pill--md" href="/pedidos/1"
   title="Aún no confirmado por el cliente" data-tooltip="Aún no confirmado por el cliente"
   role="link" aria-label="Atención: Pendiente">
  <saskia-icon name="clock" class="pill__icon" aria-hidden="true"></saskia-icon>
  <span class="pill__label">Pendiente</span>
</a>
```

### Rendered example 2 — Inventario list "Stock bajo" (table cell)

```jinja
{{ status_pill(label='Stock bajo', tone='danger', icon='alert-triangle', size='sm') }}
```

```html
<span class="pill pill--danger pill--sm" role="status">
  <saskia-icon name="alert-triangle" class="pill__icon" aria-hidden="true"></saskia-icon>
  <span class="pill__label">Stock bajo</span>
</span>
```

### Rendered example 3 — Risks register "Mitigado" (muted with dot)

```jinja
{{ status_pill(label='Mitigado', tone='muted', dot=True) }}
```

```html
<span class="pill pill--muted pill--md" role="status" aria-label="Mitigado">
  <span class="pill__dot pill__dot--muted" aria-hidden="true"></span>
  <span class="pill__label">Mitigado</span>
</span>
```

## Behavior rules

| Condition                | Behavior |
|--------------------------|----------|
| Empty `label`            | Raises `MacroArgumentError` at template render time. All paged need a label. |
| `tone` is not in the allowed set | Falls back to `neutral`, logs a console warning. |
| `href` provided          | Renders as `<a>`. |
| `href is None`           | Renders as `<span role="status">` — still focusable when tooltip is present (via `tabindex="0"` added automatically on hover). |
| Both `icon` and `dot` true | Both render (dot left of icon) — overflow is bounded; size `sm` may hide the dot. |
| `size='sm'`              | No tooltip trigger UI (only browser-native title), padding 2px 6px, font 11px. |
| `size='md'`              | Default. Padding 4px 10px, font 12.5px. |
| `size='lg'`              | Padding 6px 14px, font 14px, **always** with tooltip and icon. |
| English labels           | Allowed but discouraged. The macro does not translate; if a server value arrives in English ("pending"), the caller must translate before passing. |
| Truncation               | At max-width, label truncates with ellipsis; full label lives in `title` attr. |
| Status pill used as the sole indicator of an alert | **Disallowed** — pair with `inline_warning` for non-trivial risks. Status pills are read at-a-glance; warnings demand action. |

### Accessibility

- `aria-label` is enriched with the tone: "Atención: Pendiente", "Crítico: Stock bajo". Screen-reader users don't need color.
- `role="status"` (not `role="alert"`) on the non-link variant — this is an ambient indicator, not an interrupt.
- Tooltip is exposed via both `title` and `data-tooltip` (the latter picked up by `<saskia-tooltip>` for richer hover).

### Locale

- Label is user-facing Spanish; macro does not auto-uppercase or auto-lowercase.
- Date inside label: `dd/mm/aaaa`. Currency: `Gs. 1.234`.

## Used by

- **Pedidos board** — `Pendiente`, `En preparación`, `Listo para retiro`, `Cancelado`. Channel pills: `WhatsApp`, `Mostrador`, `Web`, `Delivery` (channel uses `info` tone, not `warn`).
- **Pedido-detalle** — header status pill + per-item `Cumplido` pill.
- **Inventario list** row `Estado` — `OK` (ok), `Stock bajo` (danger).
- **Inventario-movimientos** type column — `Entrada` (ok), `Salida` (info), `Merma` (warn), `Ajuste` (neutral).
- **Producción** batch `Suficiente` (ok) / `Falta` (danger).
- **Riesgos** state — `Activo` (danger), `Mitigado` (muted), `Cerrado` (neutral).
- **Wishlist** kanban — `Now`, `Next`, `Later`, `Done`.
- **Recetas** difficulty — `auto` pill in `neutral`, computed difficulty 1-5 as colored dots.
- **Proveedores** status — `Activo` (ok), `Pausado` (muted), `Sin contacto 30d` (warn).

## Required Web Component / JS

- **`<saskia-icon>`** — icons.
- **`<saskia-tooltip>`** — picks up `data-tooltip` for richer hover (optional, falls back to native `title`).

## Anti-patterns

- ❌ **Don't** use `status_pill` for free-form tags like "Alto en proteína", "Sin TACC", "Vegano" — these need the `tag_pill` macro (a different macro, out of scope here). Status pills are reserved for **state**, not classification.
- ❌ **Don't** stack two `status_pill`s on the same row that say overlapping things ("Stock bajo" + "Crítico"). Pick the loudest one.
- ❌ **Don't** use `tone='danger'` for "Pendiente" — `Pendiente` is `warn` (yellow-amber). `danger` (red) is reserved for actual emergencies: stock = 0, batch failed, pedido cancelado.
- ❌ **Don't** set both `icon` AND `dot=True` in `sm` size — the dot will be visually noisy. Pick one.
- ❌ **Don't** reuse `status_pill` for buttons. If the user clicks it and the action is non-trivial (open modal, navigate, submit), it's a button, not a pill.
- ❌ **Don't** capitalize the label with `text-transform: uppercase` via CSS — it destroys readability for Spanish accents and screen-reader pronunciation. Use the natural casing.
- ❌ **Don't** override the `tone` color in per-page CSS — the tokens are global design decisions.

---

# Macro 3: `data_table(columns, rows, row_actions=None, bulk_actions=None, pagination=None, selectable=False, sticky_header=True, empty_state=None, source_attribution=None, sort=None, on_row_click=None)`

## Purpose

Render a sortable, paginated table with multi-select rows, inline row actions, optional bulk-action bar, and a contract-defined empty state. This is the canonical list-page primitive used for every collection in the app.

## Arguments

| Argument              | Type                                 | Default     | Required | Notes |
|-----------------------|--------------------------------------|-------------|----------|-------|
| `columns`             | `list[dict]`                         | —           | ✅       | List of column definitions. See column schema below. |
| `rows`                | `list[dict]`                         | —           | ✅       | List of row dicts keyed by column `key`. Missing keys render as `—`. |
| `row_actions`         | `list[dict] \| None`                 | `None`      | ❌       | Per-row actions. See row-action schema. |
| `bulk_actions`        | `list[dict] \| None`                 | `None`      | ❌       | Passed to `bulk_action_bar` when ≥1 row is selected. |
| `pagination`          | `dict \| None`                       | `None`      | ❌       | `{page, per_page, total, sizes}`. See pagination schema. |
| `selectable`          | `bool`                               | `False`     | ❌       | Render row checkboxes + the bulk action bar. |
| `sticky_header`       | `bool`                               | `True`      | ❌       | Pin `<thead>` to top of scroll container. |
| `empty_state`         | `dict \| None`                       | `None`      | ❌       | Passed to `empty_state` macro when `rows` is empty. |
| `source_attribution`  | `dict \| None`                       | `None`      | ❌       | `{source_label, count, last_updated}`. Renders a small footer. |
| `sort`                | `dict \| None`                       | `None`      | ❌       | `{key, direction}` where direction is `asc` or `desc`. |
| `on_row_click`        | `str \| None`                        | `None`      | ❌       | JS function name; when set, clicking a row (not a control) calls it with `row.id`. |
| `row_key`             | `str`                                | `"id"`      | ❌       | The field used as the row's React-like key and checkbox value. |
| `table_id`            | `str`                                | `"data-table"` | ❌       | DOM id; must be unique per page when more than one table renders. |
| `density`             | `str`                                | `"comfortable"` | ❌    | `compact` / `comfortable` / `spacious`. Drives row padding. |
| `caption`             | `str \| None`                        | `None`      | ❌       | Short description rendered as `<caption>` (a11y). |

### Column schema

```python
{
    "key": "nombre",            # required — matches row dict key
    "label": "Nombre",          # required — header text
    "sortable": True,           # optional, default False
    "width": "30%",             # optional, CSS width or fr-unit
    "align": "left" | "right" | "center",   # optional, default "left"
    "render": "status_pill",    # optional — name of a macro to render the cell
    "render_args": {...},       # optional — args dict merged with the row dict
    "format": "money",          # optional — "money" | "date" | "datetime" | "percent" | "integer"
    "tooltip": True,            # optional — show full cell value on hover
    "truncate": 60,             # optional — max chars before ellipsis
    "hide_on_mobile": False,    # optional
    "css_class": "stock-col",   # optional
}
```

### Row-action schema

```python
{
    "label": "Ver",
    "href": "/inventario/{id}",   # supports {id} interpolation
    "icon": "eye",
    "tone": "neutral",            # neutral | danger | warn
    "confirm": False,             # if True, opens confirm_destructive on click
    "permission": "view",         # server-side guard key
}
```

### Bulk-action schema

```python
{
    "label": "Archivar",
    "action": "POST /inventario/bulk-archive",
    "method": "POST",              # POST | GET | DELETE
    "icon": "archive",
    "tone": "neutral",
    "confirm": False,
    "require_typed": None,         # optional destructive phrase
}
```

### Pagination schema

```python
{
    "page": 1,
    "per_page": 25,
    "total": 347,
    "sizes": [10, 25, 50, 100],   # optional, default [25, 50, 100]
    "param": "?page="             # optional, just for URL building hints
}
```

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/data_table.html #}
{% from "macros/empty_state.html" import empty_state %}
{% from "macros/bulk_action_bar.html" import bulk_action_bar %}
{% from "macros/source_attribution.html" import source_attribution %}

{% macro data_table(
     columns,
     rows,
     row_actions=None,
     bulk_actions=None,
     pagination=None,
     selectable=False,
     sticky_header=True,
     empty_state=None,
     source_attribution=None,
     sort=None,
     on_row_click=None,
     row_key='id',
     table_id='data-table',
     density='comfortable',
     caption=None
) %}
  {% if not rows and empty_state %}
    {{ empty_state(**empty_state) }}
  {% else %}
    <div class="data-table data-table--{{ density }}" id="{{ table_id }}-wrap">
      <table class="data-table__table"
             id="{{ table_id }}"
             {% if caption %}aria-describedby="{{ table_id }}-caption"{% endif %}>
        {% if caption %}<caption id="{{ table_id }}-caption" class="data-table__caption">{{ caption }}</caption>{% endif %}
        <thead class="data-table__thead{% if sticky_header %} data-table__thead--sticky{% endif %}">
          <tr>
            {% if selectable %}<th scope="col" class="data-table__check"><input type="checkbox" aria-label="Seleccionar todas las filas" data-table-select-all></th>{% endif %}
            {% for col in columns %}
              <th scope="col"
                  class="data-table__th data-table__th--{{ col.align or 'left' }}{% if col.sortable %} data-table__th--sortable{% endif %}{% if col.hide_on_mobile %} data-table__hide-mobile{% endif %}"
                  {% if col.width %}style="width: {{ col.width }}"{% endif %}
                  {% if col.sortable %}data-sort-key="{{ col.key }}" aria-sort="{% if sort and sort.key == col.key %}{{ sort.direction }}{% else %}none{% endif %}"{% endif %}>
                {% if col.sortable %}
                  <button class="data-table__sort-btn" data-sort-trigger="{{ col.key }}" aria-label="Ordenar por {{ col.label }}">
                    {{ col.label }}
                    {% if sort and sort.key == col.key %}
                      <saskia-icon name="arrow-{{ 'up' if sort.direction == 'asc' else 'down' }}" aria-hidden="true"></saskia-icon>
                    {% endif %}
                  </button>
                {% else %}
                  {{ col.label }}
                {% endif %}
              </th>
            {% endfor %}
            {% if row_actions %}<th scope="col" class="data-table__actions"><span class="visually-hidden">Acciones</span></th>{% endif %}
          </tr>
        </thead>
        <tbody class="data-table__tbody">
          {% for row in rows %}
            <tr class="data-table__row"
                data-row-id="{{ row[row_key] }}"
                {% if selectable %}data-selectable="true"{% endif %}
                {% if on_row_click %}data-row-click="{{ on_row_click }}" tabindex="0" role="button"{% endif %}>
              {% if selectable %}
                <td class="data-table__check">
                  <input type="checkbox" name="selected_ids" value="{{ row[row_key] }}"
                         aria-label="Seleccionar fila {{ loop.index }}" data-table-row-check>
                </td>
              {% endif %}
              {% for col in columns %}
                {% set cell_value = row.get(col.key) %}
                {% set rendered = cell_value %}
                {% if col.render == 'status_pill' %}
                  {% set tone = (col.render_args or {}).get('tone') or row.get(col.key ~ '_tone') or 'neutral' %}
                  {% set rendered %}{% include 'macros/_render_status_pill.html.j2' ignore missing %}{% endset %}
                {% endif %}
                <td class="data-table__td data-table__td--{{ col.align or 'left' }}{% if col.hide_on_mobile %} data-table__hide-mobile{% endif %} {{ col.css_class or '' }}">
                  {% if cell_value is none %}—{% else %}{{ cell_value }}{% endif %}
                </td>
              {% endfor %}
              {% if row_actions %}
                <td class="data-table__actions">
                  {% for action in row_actions %}
                    {% set href = action.href|replace('{id}', row[row_key]|string) %}
                    <a class="data-table__action data-table__action--{{ action.tone or 'neutral' }}"
                       href="{{ href }}"
                       {% if action.tooltip %}title="{{ action.tooltip }}"{% endif %}
                       aria-label="{{ action.label }}">
                      {% if action.icon %}<saskia-icon name="{{ action.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
                      <span class="data-table__action-label">{{ action.label }}</span>
                    </a>
                  {% endfor %}
                </td>
              {% endif %}
            </tr>
          {% endfor %}
        </tbody>
      </table>

      {% if source_attribution %}
        {{ source_attribution(**source_attribution) }}
      {% endif %}

      {% if pagination %}
        <nav class="data-table__pagination" aria-label="Paginación">
          <span class="data-table__pagination-summary">
            Mostrando {{ ((pagination.page - 1) * pagination.per_page) + 1 }}–{{ [pagination.page * pagination.per_page, pagination.total]|min }} de {{ pagination.total }}
          </span>
          <ul class="data-table__pagination-list">
            <li><a href="?page=1" aria-label="Primera página">«</a></li>
            {% for p in range(max(1, pagination.page - 2), min(pagination.page + 3, (pagination.total // pagination.per_page) + 2)) %}
              <li><a href="?page={{ p }}"
                     class="{% if p == pagination.page %}is-current{% endif %}"
                     {% if p == pagination.page %}aria-current="page"{% endif %}>{{ p }}</a></li>
            {% endfor %}
            <li><a href="?page={{ (pagination.total // pagination.per_page) + 1 }}" aria-label="Última página">»</a></li>
          </ul>
        </nav>
      {% endif %}
    </div>

    {% if selectable and bulk_actions %}
      <saskia-bulk-bar
         data-actions='{{ bulk_actions|tojson }}'
         data-table-id="{{ table_id }}"
         hidden></saskia-bulk-bar>
    {% endif %}
  {% endif %}
{% endmacro %}
```

> The above is the canonical contract. The actual implementation may split into partials; semantics are what matter.

### Rendered example 1 — Inventario list (compact-ish)

```jinja
{{ data_table(
     columns=[
       {"key": "nombre", "label": "Nombre", "sortable": True, "width": "30%"},
       {"key": "unidad", "label": "Unidad", "sortable": False, "width": "8%", "align": "center"},
       {"key": "stock", "label": "Stock actual", "sortable": True, "align": "right", "format": "number"},
       {"key": "precio_compra_gs", "label": "Precio compra", "sortable": True, "align": "right", "format": "money"},
       {"key": "estado_tone", "label": "Estado", "render": "status_pill"},
     ],
     rows=[
       {"id": 1, "nombre": "Harina 0000", "unidad": "kg", "stock": 100, "precio_compra_gs": 3000, "estado_tone": "ok", "estado_label": "OK"},
       {"id": 2, "nombre": "Levadura seca", "unidad": "kg", "stock": 0.4, "precio_compra_gs": 12000, "estado_tone": "danger", "estado_label": "Stock bajo"},
     ],
     row_actions=[
       {"label": "Ver", "href": "/inventario/{id}", "icon": "eye"},
       {"label": "Editar", "href": "/inventario/{id}/editar", "icon": "pencil"},
     ],
     bulk_actions=[{"label": "Archivar", "action": "POST /inventario/bulk-archive", "icon": "archive"}],
     pagination={"page": 1, "per_page": 25, "total": 347},
     selectable=True,
     empty_state={"title": "Sin ingredientes", "cta": {"label": "Agregá el primero", "href": "/inventario/nuevo"}},
     source_attribution={"source_label": "SKU maestro", "count": "347 registros", "last_updated": "2026-09-27 15:30"},
     sort={"key": "nombre", "direction": "asc"},
     caption="Inventario de ingredientes activos"
) }}
```

Rendered HTML (truncated for length):

```html
<div class="data-table data-table--comfortable" id="data-table-wrap">
  <table class="data-table__table" id="data-table" aria-describedby="data-table-caption">
    <caption id="data-table-caption" class="data-table__caption">Inventario de ingredientes activos</caption>
    <thead class="data-table__thead data-table__thead--sticky">
      <tr>
        <th scope="col" class="data-table__check"><input type="checkbox" aria-label="Seleccionar todas las filas" data-table-select-all></th>
        <th scope="col" class="data-table__th data-table__th--left data-table__th--sortable" style="width: 30%" data-sort-key="nombre" aria-sort="asc">
          <button class="data-table__sort-btn" data-sort-trigger="nombre" aria-label="Ordenar por Nombre">
            Nombre <saskia-icon name="arrow-up" aria-hidden="true"></saskia-icon>
          </button>
        </th>
        <th scope="col" class="data-table__th data-table__th--center" style="width: 8%">Unidad</th>
        <th scope="col" class="data-table__th data-table__th--right data-table__th--sortable" data-sort-key="stock" aria-sort="none">
          <button class="data-table__sort-btn" data-sort-trigger="stock" aria-label="Ordenar por Stock actual">Stock actual</button>
        </th>
        <th scope="col" class="data-table__th data-table__th--right data-table__th--sortable" data-sort-key="precio_compra_gs" aria-sort="none">
          <button class="data-table__sort-btn" data-sort-trigger="precio_compra_gs" aria-label="Ordenar por Precio compra">Precio compra</button>
        </th>
        <th scope="col" class="data-table__th data-table__th--left">Estado</th>
        <th scope="col" class="data-table__actions"><span class="visually-hidden">Acciones</span></th>
      </tr>
    </thead>
    <tbody class="data-table__tbody">
      <tr class="data-table__row" data-row-id="1" data-selectable="true">
        <td class="data-table__check"><input type="checkbox" name="selected_ids" value="1" aria-label="Seleccionar fila 1" data-table-row-check></td>
        <td class="data-table__td data-table__td--left">Harina 0000</td>
        <td class="data-table__td data-table__td--center">kg</td>
        <td class="data-table__td data-table__td--right">100</td>
        <td class="data-table__td data-table__td--right">3.000</td>
        <td class="data-table__td data-table__td--left"><span class="pill pill--ok pill--md" role="status"><saskia-icon name="check" class="pill__icon" aria-hidden="true"></saskia-icon><span class="pill__label">OK</span></span></td>
        <td class="data-table__actions">
          <a class="data-table__action data-table__action--neutral" href="/inventario/1" aria-label="Ver"><saskia-icon name="eye" aria-hidden="true"></saskia-icon><span class="data-table__action-label">Ver</span></a>
          <a class="data-table__action data-table__action--neutral" href="/inventario/1/editar" aria-label="Editar"><saskia-icon name="pencil" aria-hidden="true"></saskia-icon><span class="data-table__action-label">Editar</span></a>
        </td>
      </tr>
      <!-- second row omitted for brevity -->
    </tbody>
  </table>
  <small class="data-table__source">Fuente: SKU maestro · 347 registros · Última sync 2026-09-27 15:30</small>
  <nav class="data-table__pagination" aria-label="Paginación">
    <span class="data-table__pagination-summary">Mostrando 1–25 de 347</span>
    <ul class="data-table__pagination-list">
      <li><a href="?page=1" aria-label="Primera página">«</a></li>
      <li><a href="?page=1" class="is-current" aria-current="page">1</a></li>
      <li><a href="?page=2">2</a></li>
      <li><a href="?page=3">3</a></li>
      <li><a href="?page=14" aria-label="Última página">»</a></li>
    </ul>
  </nav>
  <saskia-bulk-bar data-actions='[{"label":"Archivar","action":"POST /inventario/bulk-archive","icon":"archive"}]' data-table-id="data-table" hidden></saskia-bulk-bar>
</div>
```

### Rendered example 2 — empty Inventario

```html
<div class="empty-state">
  <saskia-icon name="package-x" class="empty-state__icon" aria-hidden="true"></saskia-icon>
  <h3 class="empty-state__title">Sin ingredientes</h3>
  <p class="empty-state__description">Empezá cargando tu primer ingrediente.</p>
  <a class="btn btn--primary" href="/inventario/nuevo">Agregá el primero</a>
</div>
```

## Behavior rules

| Condition | Behavior |
|-----------|----------|
| `rows` is empty + `empty_state` set | Renders `empty_state` macro, **not** a `<table>`. |
| `rows` is empty + `empty_state is None` | Renders a `<table>` with `<tbody>` containing one row: `Sin resultados`. |
| Missing column key in a row | Cell renders `—`. Never raises. |
| Cell value is `None` | Renders `—`. |
| Cell value is `datetime`/`date` | Formatted via `format` directive; default `date` is `dd/mm/aaaa`. |
| Cell value is `float` with `format='money'` | Rounded to integer, formatted `Gs. 1.234.567`. |
| Column `sortable=True` | Renders a `<button>` inside `<th>` with `data-sort-trigger`; default sort behavior is full-page reload via URL (`?sort=nombre:asc`). |
| `selectable=True` | First column is checkbox. The `<saskia-bulk-bar>` is hidden until ≥1 row is selected (JS in web component). |
| `bulk_actions` provided but `selectable=False` | Macro silently ignores bulk_actions and renders a console warning. |
| `pagination` total = 0 | Pagination block is hidden. |
| `pagination` total > 10.000 | Pagination collapses to jump-to-page input + total only (no per-page numbers). |
| `on_row_click` set | Rows become focusable; Enter/Space triggers same handler. |
| `density='compact'` | Row padding 4px 8px, font 12px, hides `.data-table__action-label` (icon-only). |
| `density='comfortable'` | Default; padding 8px 12px, font 13px. |
| `density='spacious'` | Padding 14px 16px, font 14px; for accessibility-targeted screens. |
| `sticky_header=True` (default) | `<thead>` gets `position: sticky; top: 0`. Disabled on `density='compact'`. |
| `row_actions` with `confirm=True` | The action is wired to the `confirm_destructive` macro (rendered into the body via JS); the action link doesn't fire until confirmed. |
| `row_key` field missing in `rows` | Macro raises at render time (asserts). Use `"row_key='slug'"` etc. if needed. |

### Accessibility

- `<th scope="col">` always.
- `aria-sort` reflects current sort state.
- `aria-describedby` ties caption to table.
- Bulk-bar uses `role="region" aria-live="polite"` when visible (count changes are announced).
- Color-coded cells always carry a text alternative (`status_pill` already does this).
- `on_row_click` keyboard support: focusable + `Enter` and `Space` invocation.

### Locale

- All numeric formatting follows locale (`es_PY`).
- Pagination summary: `Mostrando 1–25 de 347` (en-dash, not hyphen).

## Used by

Every list page:

- **Inventario** (variantes, movimientos)
- **Proveedores** (incl. alias, duplicados)
- **Reponer**
- **Pedidos** (board uses a kanban macro; **list** uses this)
- **Pedido-detalle** items table (compact density, embedded)
- **Lista de compras**
- **Auditoría** results table
- **Bank** movimientos
- **Pricing** matrix (custom density, all cells)
- **Vs-mercado** comparativa
- **Riesgos** (P×I score column)
- **Wishlist** board list view
- **Reportes** run history
- **Inventario-movimientos**, **Inventario-variantes** listings

## Required Web Component / JS

- **`<saskia-icon>`**
- **`<saskia-bulk-bar>`** — listens to `change` events on checkboxes, slides up from bottom, hits the action endpoint.
- **`<saskia-tooltip>`**
- A small JS bootstrapper that:
  - wires `data-sort-trigger` to a URL push (`?sort=nombre:asc`).
  - wires `data-table-select-all` to check/uncheck all visible rows.
  - wires `data-row-click` to invoke the named callback with `rowId`.

## Anti-patterns

- ❌ **Don't** hand-roll a `<table>` when this macro exists. Even "just for one row" — use `density='compact'`.
- ❌ **Don't** build a `bulk_action_bar` separately as a sibling element — pass `bulk_actions` to `data_table` so the lifecycle is coordinated (it hides when selection clears).
- ❌ **Don't** put `selectable=True` AND an `on_row_click` simultaneously — clicking the row vs. the checkbox becomes ambiguous. Pick one mechanism; if both are needed, clicking the row body opens detail, checkbox toggles selection.
- ❌ **Don't** put icons from different families in `row_actions` (one lucide, one emoji). Pick lucide.
- ❌ **Don't** render the entire table inside a hidden parent and then unhide via JS without setting `aria-hidden` back to false — screen readers will miss it.
- ❌ **Don't** set `sticky_header=True` on a table inside a vertically-scrollable card AND a horizontally-scrollable card with `position: sticky` on the leftmost column — the two stickies fight. Pick horizontal or vertical scroll, not both, when sticky header is on.
- ❌ **Don't** exceed ~12 columns; collapse secondary columns into an expandable row detail.
- ❌ **Don't** omit `<caption>` if `selectable=True` — the table needs a caption for screen-reader orientation.
- ❌ **Don't** use this macro for **board layouts** (kanban, drag-drop reorder) — use a separate `kanban_board` macro.

---

# Macro 4: `filter_chips(chips, active_key=None, date_presets=None, search_input=False, saved_views=None, sync_with_url=True, target_url=None)`

## Purpose

Render a horizontal rail of toggleable filter chips (counts included), optionally paired with date presets and a search box. Used at the top of every list page.

## Arguments

| Argument         | Type            | Default     | Required | Notes |
|------------------|-----------------|-------------|----------|-------|
| `chips`          | `list[dict]`    | —           | ✅       | Chip definitions. See schema below. |
| `active_key`     | `str \| None`   | `None`      | ❌       | Currently selected chip `key`. If `None`, the first chip is treated as active. |
| `date_presets`   | `list[dict] \| None` | `None` | ❌       | See `date_range_presets` macro contract. |
| `search_input`   | `bool`          | `False`     | ❌       | Render an inline search input alongside the chips. |
| `saved_views`    | `list[dict] \| None` | `None` | ❌       | `[{label, href}]` star list. |
| `sync_with_url`  | `bool`          | `True`      | ❌       | When True, clicking a chip pushes `?filter=<key>` and reads initial state from `request.args`. |
| `target_url`     | `str \| None`   | `None`      | ❌       | Defaults to current request path. |
| `name`           | `str`           | `"filter"`  | ❌       | URL parameter name. |

### Chip schema

```python
{
    "key": "bajo_minimo",      # required, URL-safe
    "label": "Bajo mínimo",    # required, Spanish
    "count": 3,                # optional, integer — shows " (3)" suffix
    "tone": "warn",            # optional — colors the count + active state
    "icon": "alert-triangle",  # optional
    "href": "?filter=bajo_minimo"  # optional, auto-built if missing
}
```

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/filter_chips.html #}
{% macro filter_chips(
     chips,
     active_key=None,
     date_presets=None,
     search_input=False,
     saved_views=None,
     sync_with_url=True,
     target_url=None,
     name='filter'
) %}
  {% set url = target_url or request.path %}
  {% set active = active_key or request.args.get(name) or chips[0].key %}
  <section class="filter-chips" aria-label="Filtros">
    <ul class="filter-chips__list" role="tablist" aria-orientation="horizontal">
      {% for chip in chips %}
        {% set is_active = chip.key == active %}
        <li class="filter-chips__item">
          <a href="{{ chip.href or (url ~ '?' ~ name ~ '=' ~ chip.key) }}"
             class="filter-chips__chip
                    filter-chips__chip--{{ chip.tone or 'neutral' }}
                    {% if is_active %}is-active{% endif %}"
             role="tab"
             aria-selected="{{ 'true' if is_active else 'false' }}"
             aria-controls="filter-panel"
             data-filter-key="{{ chip.key }}">
            {% if chip.icon %}<saskia-icon name="{{ chip.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
            <span class="filter-chips__label">{{ chip.label }}</span>
            {% if chip.count is not none %}<span class="filter-chips__count">{{ chip.count }}</span>{% endif %}
          </a>
        </li>
      {% endfor %}
      {% if saved_views %}
        <li class="filter-chips__item filter-chips__item--saved">
          <details class="filter-chips__saved">
            <summary><saskia-icon name="star" aria-hidden="true"></saskia-icon> Vistas guardadas</summary>
            <ul>
              {% for sv in saved_views %}
                <li><a href="{{ sv.href }}">{{ sv.label }}</a></li>
              {% endfor %}
            </ul>
          </details>
        </li>
      {% endif %}
      {% if date_presets %}
        <li class="filter-chips__item filter-chips__item--presets">
          {% include "macros/date_range_presets.html" %}
          {{ date_range_presets(presets=date_presets) }}
        </li>
      {% endif %}
    </ul>
    {% if search_input %}
      <form class="filter-chips__search" method="get" action="{{ url }}" role="search">
        <saskia-icon name="search" aria-hidden="true"></saskia-icon>
        <input type="search" name="q" value="{{ request.args.get('q', '') }}"
               placeholder="Buscar…"
               aria-label="Buscar en la lista">
      </form>
    {% endif %}
  </section>
{% endmacro %}
```

### Rendered example 1 — Inventario list

```jinja
{{ filter_chips(
     chips=[
       {"key": "todos", "label": "Todos", "count": 42},
       {"key": "bajo_minimo", "label": "Bajo mínimo", "count": 3, "tone": "warn", "icon": "alert-triangle"},
       {"key": "sin_proveedor", "label": "Sin proveedor", "count": 1, "tone": "danger"},
       {"key": "caducan_pronto", "label": "Caducan pronto", "count": 2, "tone": "warn"},
       {"key": "sin_gluten", "label": "Sin gluten", "count": 5, "tone": "info"},
     ],
     active_key='bajo_minimo',
     search_input=True,
     saved_views=[{"label": "Mis críticos", "href": "?saved=criticos"}]
) }}
```

```html
<section class="filter-chips" aria-label="Filtros">
  <ul class="filter-chips__list" role="tablist" aria-orientation="horizontal">
    <li class="filter-chips__item">
      <a href="/inventario?filter=todos" class="filter-chips__chip filter-chips__chip--neutral" role="tab" aria-selected="false" aria-controls="filter-panel" data-filter-key="todos">
        <span class="filter-chips__label">Todos</span><span class="filter-chips__count">42</span>
      </a>
    </li>
    <li class="filter-chips__item">
      <a href="/inventario?filter=bajo_minimo" class="filter-chips__chip filter-chips__chip--warn is-active" role="tab" aria-selected="true" aria-controls="filter-panel" data-filter-key="bajo_minimo">
        <saskia-icon name="alert-triangle" aria-hidden="true"></saskia-icon>
        <span class="filter-chips__label">Bajo mínimo</span><span class="filter-chips__count">3</span>
      </a>
    </li>
    <!-- other chips omitted -->
    <li class="filter-chips__item filter-chips__item--saved">
      <details class="filter-chips__saved">
        <summary><saskia-icon name="star" aria-hidden="true"></saskia-icon> Vistas guardadas</summary>
        <ul>
          <li><a href="?saved=criticos">Mis críticos</a></li>
        </ul>
      </details>
    </li>
  </ul>
  <form class="filter-chips__search" method="get" action="/inventario" role="search">
    <saskia-icon name="search" aria-hidden="true"></saskia-icon>
    <input type="search" name="q" value="" placeholder="Buscar…" aria-label="Buscar en la lista">
  </form>
</section>
```

### Rendered example 2 — Auditoría with date presets

```jinja
{{ filter_chips(
     chips=[
       {"key": "all", "label": "Todos"},
       {"key": "logins", "label": "Logins"},
       {"key": "writes", "label": "Escrituras", "tone": "warn"},
     ],
     date_presets=[
       {"key": "today", "label": "Hoy", "from": "2026-09-27", "to": "2026-09-27"},
       {"key": "yesterday", "label": "Ayer", "from": "2026-09-26", "to": "2026-09-26"},
       {"key": "7d", "label": "Últimos 7d", "from": "2026-09-20", "to": "2026-09-27"},
     ],
     search_input=True
) }}
```

## Behavior rules

| Condition | Behavior |
|-----------|----------|
| `chips` empty | Macro raises `MacroArgumentError` at render. |
| `active_key` not in chip keys | Falls back to `chips[0].key` with a console warning. |
| `sync_with_url=True` and `request.args.get(name)` exists | Reads initial state from URL query param. |
| No chip selected + no URL hint | First chip is treated as `is-active`. |
| Click on a chip | Navigates to `<url>?<name>=<chip.key>` (full reload). No JS-only state. |
| `search_input=True` | Form submits on Enter; URL gets `?q=…`. Search combines with chip via `?filter=…&q=…`. |
| `saved_views` provided | A `<details>` summary "Vistas guardadas" appears last. Each saved view is a plain `<a>` (server-side route). |
| `chips[].count` is `None` | Rendered with no count badge. |
| `chips[].count` is `-1` or negative | Stripped to `0`, logged. Counts must be ≥ 0. |
| Many chips (≥ 8) | Wraps to 2 lines on mobile; on desktop they stay on one row until overflow, then horizontal scroll with edge fade. |
| `date_presets` passed | Renders the `date_range_presets` macro as the last chip in the row (it has its own contract). |

### Accessibility

- `role="tablist"` + each chip is `role="tab"` `aria-selected`.
- Active chip has visible border + background; inactive chips are outlined. Color is never the sole signal — border + bold weight too.
- Search input has both an `aria-label` and (visually-hidden) `<label>`.
- Keyboard: `Tab` moves through chips; `Enter` activates; arrow keys jump between chips (when in radio-mode).

### Locale

- Chip labels are user-facing Spanish; no auto-translation.
- Date presets follow `dd/mm/aaaa` (set by `date_range_presets`).

## Used by

- **Inventario** — Todos · Bajo mínimo · Sin proveedor · Caducan pronto · Sin gluten
- **Proveedores** — Todos · Activos · Pausados · Sin contacto · Con RUC
- **Reponer** — Bajo mínimo · Sin stock · Sin proveedor · Caducan pronto
- **Pedidos board** (compact list view) — Pendientes · En preparación · Listos · Cancelados
- **Bank** — Todas · EUR · PYG · Conciliadas · Pendientes
- **Auditoría** — All · logins · writes · deletes · config
- **Lista de compras** — Solo abiertos · Todos (incl. comprados)
- **Inventario-movimientos** — Entrada · Salida · Merma · Ajuste

## Required Web Component / JS

- **`<saskia-icon>`**
- For client-side chip counts that update without reload: a small enhancement script (out of scope — chips work without JS; this is progressive enhancement only).
- The macro emits plain `<a>` tags, so it works without any JS.

## Anti-patterns

- ❌ **Don't** render the same `filter_chips` twice on one page (e.g., once on desktop, once on mobile). The macro is responsive.
- ❌ **Don't** overload `tone` — `danger` red counts are for actual emergencies ("1 ingrediente sin stock"), not "low priority 30d".
- ❌ **Don't** animate chip background on hover with a transition longer than 150ms — it feels sluggish.
- ❌ **Don't** use chips where you need a multi-select dropdown. Single-select filters go through chips; multi-select goes through a dropdown panel (a separate pattern, not this macro).
- ❌ **Don't** set `count=0` on a non-default chip — it's clearer to omit `count` (renders no badge) or hide the chip entirely.
- ❌ **Don't** put more than one `<saskia-icon>` in a chip — too visually noisy. Pick icon OR count, not both as the dominant.
- ❌ **Don't** rely on the `search_input` clearing itself between page loads — it preserves `request.args.q`. If the page should default to "no search", keep search input out of this macro or pass `default_query=''`.

---

# Macro 5: `empty_state(icon=None, title, description=None, primary_cta=None, secondary_cta=None, tip=None, illustration=None, size='md')`

## Purpose

Render the canonical empty-state block — icon + headline + 1-2 line explainer + (optional) primary CTA + (optional) secondary CTA + (optional) tip. Replaces "no data" placeholders with on-brand onboarding blocks.

## Arguments

| Argument          | Type            | Default     | Required | Notes |
|-------------------|-----------------|-------------|----------|-------|
| `title`           | `str`           | —           | ✅       | Headline (sentence case, no period). |
| `icon`            | `str \| None`   | `None`      | ❌       | Lucide name. Defaults to a context-appropriate icon when omitted (e.g., "package" for lists). |
| `description`     | `str \| None`   | `None`      | ❌       | 1-2 sentences, Spanish. Plain text only — no HTML allowed here. |
| `primary_cta`     | `dict \| None`  | `None`      | ❌       | `{label, href?, action?, icon?}`. Either `href` (link) or `action` (JS function name). |
| `secondary_cta`   | `dict \| None`  | `None`      | ❌       | Same schema, lower visual weight (ghost button). |
| `tip`             | `str \| None`   | `None`      | ❌       | Small italic micro-tip at the bottom ("💡 Tip: ..."). |
| `illustration`    | `str \| None`   | `None`      | ❌       | SVG filename from `/static/illustrations/`. Overrides `icon` if both are present. |
| `size`            | `str`           | `"md"`      | ❌       | `sm` (compact, in-card), `md` (default, full-panel), `lg` (hero). |
| `illustration_alt`| `str \| None`   | `None`      | ❌       | Alt text for the SVG; defaults to `title`. |

### CTA schema

```python
{
    "label": "Agregá el primero",
    "href": "/inventario/nuevo",     # either href OR action
    "action": "openWhatsAppPaste",   # either href OR action
    "icon": "plus",                  # optional
    "tone": "primary",               # primary | secondary | tertiary
}
```

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/empty_state.html #}
{% macro empty_state(
     title,
     icon=None,
     description=None,
     primary_cta=None,
     secondary_cta=None,
     tip=None,
     illustration=None,
     size='md',
     illustration_alt=None
) %}
  <section class="empty-state empty-state--{{ size }}" role="region" aria-labelledby="es-title-{{ title|lower|replace(' ', '-') }}">
    {% if illustration %}
      <img class="empty-state__illustration" src="/static/illustrations/{{ illustration }}" alt="{{ illustration_alt or title }}" loading="lazy" decoding="async">
    {% elif icon %}
      <div class="empty-state__icon-wrap">
        <saskia-icon name="{{ icon }}" class="empty-state__icon" aria-hidden="true"></saskia-icon>
      </div>
    {% endif %}
    <h3 id="es-title-{{ title|lower|replace(' ', '-') }}" class="empty-state__title">{{ title }}</h3>
    {% if description %}<p class="empty-state__description">{{ description }}</p>{% endif %}
    {% if primary_cta %}
      {% if primary_cta.href %}
        <a class="btn btn--{{ primary_cta.tone or 'primary' }}" href="{{ primary_cta.href }}">
          {% if primary_cta.icon %}<saskia-icon name="{{ primary_cta.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
          {{ primary_cta.label }}
        </a>
      {% elif primary_cta.action %}
        <button class="btn btn--{{ primary_cta.tone or 'primary' }}" data-action="{{ primary_cta.action }}" type="button">
          {% if primary_cta.icon %}<saskia-icon name="{{ primary_cta.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
          {{ primary_cta.label }}
        </button>
      {% endif %}
    {% endif %}
    {% if secondary_cta %}
      {% if secondary_cta.href %}
        <a class="btn btn--{{ secondary_cta.tone or 'secondary' }}" href="{{ secondary_cta.href }}">
          {% if secondary_cta.icon %}<saskia-icon name="{{ secondary_cta.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
          {{ secondary_cta.label }}
        </a>
      {% elif secondary_cta.action %}
        <button class="btn btn--{{ secondary_cta.tone or 'secondary' }}" data-action="{{ secondary_cta.action }}" type="button">
          {% if secondary_cta.icon %}<saskia-icon name="{{ secondary_cta.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
          {{ secondary_cta.label }}
        </button>
      {% endif %}
    {% endif %}
    {% if tip %}<p class="empty-state__tip"><saskia-icon name="lightbulb" aria-hidden="true"></saskia-icon> {{ tip }}</p>{% endif %}
  </section>
{% endmacro %}
```

### Rendered example 1 — Proveedores (master list)

```jinja
{{ empty_state(
     icon='truck',
     title='No hay proveedores todavía',
     description='Agregá proveedores para poder contactarlos desde la página de reorden.',
     primary_cta={'label': 'Agregá el primero', 'href': '/proveedores/nuevo', 'icon': 'plus'},
     secondary_cta={'label': 'Pegar lista de WhatsApp', 'action': 'openWhatsAppPaste', 'icon': 'message-circle'},
     tip='Después podés asignarles categorías, RUC y horarios de entrega.'
) }}
```

```html
<section class="empty-state empty-state--md" role="region" aria-labelledby="es-title-no-hay-proveedores-todavía">
  <div class="empty-state__icon-wrap">
    <saskia-icon name="truck" class="empty-state__icon" aria-hidden="true"></saskia-icon>
  </div>
  <h3 id="es-title-no-hay-proveedores-todavía" class="empty-state__title">No hay proveedores todavía</h3>
  <p class="empty-state__description">Agregá proveedores para poder contactarlos desde la página de reorden.</p>
  <a class="btn btn--primary" href="/proveedores/nuevo">
    <saskia-icon name="plus" aria-hidden="true"></saskia-icon>
    Agregá el primero
  </a>
  <button class="btn btn--secondary" data-action="openWhatsAppPaste" type="button">
    <saskia-icon name="message-circle" aria-hidden="true"></saskia-icon>
    Pegar lista de WhatsApp
  </button>
  <p class="empty-state__tip">
    <saskia-icon name="lightbulb" aria-hidden="true"></saskia-icon>
    Después podés asignarles categorías, RUC y horarios de entrega.
  </p>
</section>
```

### Rendered example 2 — compact (in-card) empty state

```jinja
{{ empty_state(
     title='Sin variantes registradas',
     description='Podés agregar variantes (marcas o tamaños) y marcar una como preferida.',
     primary_cta={'label': 'Agregar variante', 'href': '#agregar-variante', 'icon': 'plus'},
     size='sm'
) }}
```

### Rendered example 3 — Riesgos with hero illustration

```jinja
{{ empty_state(
     illustration='risk-register-empty.svg',
     illustration_alt='Ilustración de un libro de riesgos',
     title='No hay riesgos registrados',
     description='Identificá, puntuá y mitigá los riesgos de tu panadería. Empezá con los más comunes.',
     primary_cta={'label': 'Cargar riesgos comunes', 'action': 'seedCommonRisks', 'icon': 'sparkles'},
     tip='Una pyme típica tiene 8-15 riesgos operacionales activos.',
     size='lg'
) }}
```

## Behavior rules

| Condition | Behavior |
|-----------|----------|
| `title` is empty | Macro raises (title is the only required arg for a reason). |
| Both `illustration` and `icon` | `illustration` wins; `icon` is suppressed. |
| `primary_cta` is `None`, no link/action | Stripped from output — empty state has no CTA. |
| Both `primary_cta.href` and `primary_cta.action` | `href` wins; `action` ignored. |
| `description` longer than 240 chars | Truncated at sentence boundary with `…`. Emits a console warning. Description should be 1-2 sentences. |
| `tip` starts with `"💡"` or `"Tip:"` | Leading "💡" / "Tip:" is stripped (the icon handles that). |
| `size='sm'` | Compact height (max 240px), no description (only title + CTA). |
| `size='lg'` | Padding 48px, title 28px, illustration up to 280px wide. |
| `role="region"` vs `aria-live` | Region (not live). Empty state is not an alert; it just exists in the DOM. |
| `illustration` given but file not found | Falls back to icon; logs warning. |
| Empty state inside a `<form>` | Allowed; CTAs are real buttons or links. |
| Multiple empty states on one page | Allowed; required unique `aria-labelledby` IDs (macro auto-disambiguates by appending an index — verify). |

### Accessibility

- `role="region" aria-labelledby="es-title-…"` ties the block to its title.
- `<h3>` for the title inside a `<section>` is the right outline level (page sections often wrap in `<h2>` already).
- Illustration always has `alt`.
- Buttons (not `<a href="#">`) for action-only CTAs — keyboard and screen-reader friendly.

### Locale

- All text is user-facing Spanish.
- Money, dates, numbers rendered elsewhere — this macro doesn't format content.

## Used by

- **Inventario list** (no rows)
- **Inventario-variantes** (empty Variantes card — `size='sm'`)
- **Inventario-movimientos** (no movements yet — `size='md'`)
- **Proveedores** (master, `size='md'`; aliases, `size='md'`)
- **Proveedores-duplicados** (no duplicates found)
- **Reponer** (everything above mínimo — celebration variant: `tone='success'` would be nice but is currently just descriptive; future-proofing)
- **Pedidos** (list)
- **Pedido-stock-preview** (when 500 happens, this empty-state should be replaced with `inline_warning` instead — out of scope here)
- **Lista de compras** (empty)
- **Wishlist** (no items)
- **Riesgos** (no risks recorded — worst in the app per batch 3 audit)
- **Bank** (no transactions)
- **Auditoría** (no entries yet)
- **Recetas list / Receta-detalle** sub-empty (sub-recetas, etiquetas)
- **Vs-mercado** (no benchmarks)
- **Reportes** (in-context when a card has never been run)

## Required Web Component / JS

- **`<saskia-icon>`**
- For `data-action` CTAs: an event-delegation script on `document.body` that picks up `click` on `[data-action]` and invokes the named function.

## Anti-patterns

- ❌ **Don't** use this for **error** states. `inline_warning` covers failures. `empty_state` is for "intentionally empty — here's how to start."
- ❌ **Don't** render `empty_state` inside a `<table>` cell as the only content — wrap it in a `<div>` above the table.
- ❌ **Don't** make `description` longer than 2 sentences; if you need more, it's a `<details>` disclosure instead.
- ❌ **Don't** pass both primary and secondary CTA with the same visual style — primary is `primary`, secondary should always be `secondary` (or `ghost`).
- ❌ **Don't** render emoji in `title` (e.g., "📋 No hay registros") — the icon slot is for that. Title stays plain text.
- ❌ **Don't** use `size='lg'` on a per-page basis if you have many empty states — `lg` is for full-page onboarding moments only.
- ❌ **Don't** omit `title` and rely on `description` alone — screen readers and SEO need a heading.
- ❌ **Don't** put a `data-action` button without verifying the named function exists in `window` — silent no-op on the client. Compile-time lint would catch this in CI.

---

# Macro 6: `bulk_action_bar(selected_count, actions, on_clear=None, label_fmt=None)`

## Purpose

Render the bottom toolbar that slides up when ≥1 row in a `data_table` is selected. Lists the current selection count, available bulk actions, and a "Clear" button.

## Arguments

| Argument         | Type            | Default     | Required | Notes |
|------------------|-----------------|-------------|----------|-------|
| `selected_count` | `int`           | —           | ✅       | Number of currently selected rows. Hidden when 0. |
| `actions`        | `list[dict]`    | —           | ✅       | Bulk actions (typically forwarded from `data_table`'s `bulk_actions`). |
| `on_clear`       | `str \| None`   | `None`      | ❌       | JS function name called when the user clears selection (default behavior is auto-cleared by `<saskia-bulk-bar>`). |
| `label_fmt`      | `str \| None`   | `None`      | ❌       | Custom copy template with `{count}` placeholder, e.g., `"{count} pedidos seleccionados"`. Default: `"{count} seleccionados"`. |
| `position`       | `str`           | `"bottom"`  | ❌       | `bottom` (default) or `top`. |

### Action schema (same as `data_table.bulk_actions`)

```python
{
    "label": "Archivar",
    "action": "POST /inventario/bulk-archive",
    "method": "POST",
    "icon": "archive",
    "tone": "neutral",
    "confirm": False,
    "require_typed": None,
}
```

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/bulk_action_bar.html #}
{% macro bulk_action_bar(selected_count, actions, on_clear=None, label_fmt=None, position='bottom') %}
  {% set fmt = label_fmt or '{count} seleccionados' %}
  {% if selected_count > 0 %}
    <saskia-bulk-bar
       role="region"
       aria-live="polite"
       aria-label="Acciones en lote"
       class="bulk-action-bar bulk-action-bar--{{ position }}"
       data-on-clear="{{ on_clear or 'clearSelection' }}"
       data-selected-count="{{ selected_count }}"
       data-actions='{{ actions|tojson }}'>
      <div class="bulk-action-bar__inner">
        <span class="bulk-action-bar__count" aria-live="polite">
          <saskia-icon name="check-square" aria-hidden="true"></saskia-icon>
          {{ fmt|replace('{count}', selected_count|string) }}
        </span>
        <button type="button" class="bulk-action-bar__clear" data-bulk-clear>
          <saskia-icon name="x" aria-hidden="true"></saskia-icon>
          <span>Limpiar selección</span>
        </button>
        <div class="bulk-action-bar__actions">
          {% for action in actions %}
            <button type="button"
                    class="bulk-action-bar__action bulk-action-bar__action--{{ action.tone or 'neutral' }}"
                    data-bulk-action
                    data-action="{{ action.action }}"
                    data-method="{{ action.method or 'POST' }}"
                    data-confirm="{{ 'true' if action.confirm else 'false' }}"
                    data-require-typed="{{ action.require_typed or '' }}">
              {% if action.icon %}<saskia-icon name="{{ action.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
              {{ action.label }}
            </button>
          {% endfor %}
        </div>
      </div>
    </saskia-bulk-bar>
  {% endif %}
{% endmacro %}
```

> The macro renders nothing when `selected_count == 0`. The `<saskia-bulk-bar>` web component owns the show/hide animation.

### Rendered example 1 — selected 3 inventario items

```jinja
{{ bulk_action_bar(
     selected_count=3,
     actions=[
       {"label": "Archivar", "action": "POST /inventario/bulk-archive", "icon": "archive"},
       {"label": "Eliminar", "action": "POST /inventario/bulk-delete", "icon": "trash", "tone": "danger", "confirm": True},
       {"label": "Exportar CSV", "action": "GET /inventario/bulk-export.csv", "method": "GET", "icon": "download"},
     ]
) }}
```

```html
<saskia-bulk-bar role="region" aria-live="polite" aria-label="Acciones en lote"
   class="bulk-action-bar bulk-action-bar--bottom"
   data-on-clear="clearSelection"
   data-selected-count="3"
   data-actions='[{"label":"Archivar",...}, ...]'>
  <div class="bulk-action-bar__inner">
    <span class="bulk-action-bar__count" aria-live="polite">
      <saskia-icon name="check-square" aria-hidden="true"></saskia-icon>
      3 seleccionados
    </span>
    <button type="button" class="bulk-action-bar__clear" data-bulk-clear>
      <saskia-icon name="x" aria-hidden="true"></saskia-icon>
      <span>Limpiar selección</span>
    </button>
    <div class="bulk-action-bar__actions">
      <button type="button" class="bulk-action-bar__action bulk-action-bar__action--neutral"
              data-bulk-action data-action="POST /inventario/bulk-archive" data-method="POST"
              data-confirm="false" data-require-typed="">
        <saskia-icon name="archive" aria-hidden="true"></saskia-icon>
        Archivar
      </button>
      <button type="button" class="bulk-action-bar__action bulk-action-bar__action--danger"
              data-bulk-action data-action="POST /inventario/bulk-delete" data-method="POST"
              data-confirm="true" data-require-typed="">
        <saskia-icon name="trash" aria-hidden="true"></saskia-icon>
        Eliminar
      </button>
      <button type="button" class="bulk-action-bar__action bulk-action-bar__action--neutral"
              data-bulk-action data-action="GET /inventario/bulk-export.csv" data-method="GET"
              data-confirm="false" data-require-typed="">
        <saskia-icon name="download" aria-hidden="true"></saskia-icon>
        Exportar CSV
      </button>
    </div>
  </div>
</saskia-bulk-bar>
```

### Rendered example 2 — destructive with typed confirmation

```jinja
{{ bulk_action_bar(
     selected_count=1247,
     label_fmt='{count} entradas de auditoría seleccionadas — esta acción es irreversible',
     actions=[
       {"label": "Eliminar 1.247 entradas", "action": "POST /auditoria/purge-old", "tone": "danger", "confirm": True, "require_typed": "ELIMINAR"},
     ]
) }}
```

## Behavior rules

| Condition | Behavior |
|-----------|----------|
| `selected_count == 0` | Macro emits **nothing** (and `<saskia-bulk-bar>` remains hidden). |
| `selected_count == 1` | Pluralization shifts to singular ("1 seleccionado"). The macro doesn't enforce this — `label_fmt` must handle it. Default template uses "{count} seleccionados" which is fine for n≥2. |
| `selected_count > 999` | Renders with thousands separator (`1.247`). |
| Action with `confirm=True` | Click opens the `confirm_destructive` modal; if `require_typed` is set, the modal requires the typed phrase. |
| Action with `method='GET'` | Triggers a normal download (the `<saskia-bulk-bar>` builds `<a download>` and clicks it). No confirmation. |
| Action with `method='DELETE'` | Web component sends a fetch with the DELETE method; handles CSRF token automatically. |
| User clears selection | `data-on-clear` fires; default `clearSelection()` clears DOM checkboxes and toggles bar hidden. |
| Bar appears above keyboard-fold | Visible viewport reach — `<saskia-bulk-bar>` listens for `IntersectionObserver` to fade in from below. |
| `selected_count > 0` + `actions is empty` | Macro renders count + clear button, no actions section. |
| Bar overlaps page footer | `padding-bottom: 80px` is set on `<body>` while bar is open. |
| Multiple `bulk_action_bar` on one page | Only one may be visible at a time; later instances take precedence (they're typically one per page anyway). |

### Accessibility

- `role="region" aria-live="polite" aria-label="Acciones en lote"`.
- Count updates are announced (`aria-live="polite"` on count span).
- Focus is moved to the first action button when the bar appears — but only if focus was just on the table (avoids stealing focus from a modal/menu).
- Destructive actions are **last** in the action list, with a visual separator.
- `confirm_destructive` modal traps focus when shown.

### Locale

- Default `label_fmt` is `"{count} seleccionados"`. Singular override: `"{count} seleccionado"`.
- Spanish gendered plurals work: callers may pass `"{count} pedidos seleccionados"`, `"{count} entradas"`, etc.

## Used by

- **Inventario** list
- **Proveedores** list
- **Reponer** (already had partial version; needs full integration)
- **Bank** transacciones (planned)
- **Auditoría** results
- **Pedidos** list (when present)
- **Lista de compras** items

## Required Web Component / JS

- **`<saskia-bulk-bar>`** — custom element that listens to checkbox events from `<saskia-data-table>`, animates itself in/out, fires `data-action` URLs with CSRF, and pipes destructive clicks through `confirm_destructive`.
- The web component runs entirely client-side; the macro itself emits declarative markup.
- The web component also handles the body padding shift.

## Anti-patterns

- ❌ **Don't** render `bulk_action_bar` if `selected_count == 0` — call sites just shouldn't include it; the macro's empty-render is a safety net.
- ❌ **Don't** put primary destructive actions first (e.g., "Eliminar 1.247 entradas") — they should be **last**, after safe ones like "Export".
- ❌ **Don't** rely on `confirm=True` without providing a destructive phrase in `require_typed` for irreversible ops (purge, delete user, etc.).
- ❌ **Don't** use `tone='primary'` on `Eliminar` — destructive actions always get `tone='danger'`.
- ❌ **Don't** render this macro outside of a `<saskia-data-table>` context without care — the `<saskia-bulk-bar>` web component expects checkboxes named `selected_ids` on the same page (it dispatches `bulk:collect` and listens for `bulk:count` events).
- ❌ **Don't** set `position='top'` if there's already a sticky table header — the two will fight in the viewport.
- ❌ **Don't** create per-page copies of this macro — it must remain identical across every list page for muscle memory.

---

# Macro 7: `date_range_presets(presets, target_input_from='#date_from', target_input_to='#date_to', custom_enabled=True, custom_label='Personalizado', on_apply=None, active_key=None)`

## Purpose

Render a chip rail of date-range presets (Hoy, Ayer, Esta semana, etc.) that auto-fill two date inputs in a paired form. Used above date pickers on Auditoría, Bank, Inventario-movimientos, Reponer, Pedidos board.

## Arguments

| Argument             | Type            | Default     | Required | Notes |
|----------------------|-----------------|-------------|----------|-------|
| `presets`            | `list[dict]`    | —           | ✅       | See schema. |
| `target_input_from`  | `str`           | `"#date_from"` | ❌    | CSS selector for the "from" input. |
| `target_input_to`    | `str`           | `"#date_to"` | ❌    | CSS selector for the "to" input. |
| `custom_enabled`     | `bool`          | `True`      | ❌       | If True, appends a "Personalizado" chip that toggles manual editing of the inputs. |
| `custom_label`       | `str`           | `"Personalizado"` | ❌ | Override for the custom chip. |
| `on_apply`           | `str \| None`   | `None`      | ❌       | JS function name called after a preset is applied (default: submit the closest `<form>`). |
| `active_key`         | `str \| None`   | `None`      | ❌       | Preset key currently active (read from URL or server-side state). |
| `name`               | `str`           | `"period"`  | ❌       | URL parameter name on submit. |

### Preset schema

```python
{
    "key": "today",
    "label": "Hoy",
    "from": "2026-09-27",   # ISO-8601, server-computed
    "to": "2026-09-27",
}
```

`from` / `to` may also be `_today`, `_yesterday`, `_this_week_start`, `_this_week_end`, `_this_month_start`, `_this_month_end`, `_last_7d_start`, `_last_30d_start`, `_quarter_start`, `_quarter_end`, `_year_start`, `_year_end`. The macro resolves these relative to `now()` on the server at render time.

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/date_range_presets.html #}
{% macro date_range_presets(
     presets,
     target_input_from='#date_from',
     target_input_to='#date_to',
     custom_enabled=True,
     custom_label='Personalizado',
     on_apply=None,
     active_key=None,
     name='period'
) %}
  {% set active = active_key or request.args.get(name) %}
  <fieldset class="date-range-presets" aria-label="Período rápido">
    <legend class="visually-hidden">Período rápido</legend>
    <ul class="date-range-presets__list" role="radiogroup">
      {% for preset in presets %}
        {% set is_active = preset.key == active %}
        <li class="date-range-presets__item">
          <button type="button"
                  class="date-range-presets__chip
                         {% if is_active %}is-active{% endif %}"
                  data-date-preset
                  data-from="{{ preset.from }}"
                  data-to="{{ preset.to }}"
                  data-target-from="{{ target_input_from }}"
                  data-target-to="{{ target_input_to }}"
                  data-key="{{ preset.key }}"
                  data-on-apply="{{ on_apply or '' }}"
                  role="radio"
                  aria-checked="{{ 'true' if is_active else 'false' }}">
            {{ preset.label }}
          </button>
        </li>
      {% endfor %}
      {% if custom_enabled %}
        <li class="date-range-presets__item">
          <button type="button"
                  class="date-range-presets__chip date-range-presets__chip--custom
                         {% if not active %}is-active{% endif %}"
                  data-date-preset-custom
                  data-target-from="{{ target_input_from }}"
                  data-target-to="{{ target_input_to }}"
                  role="radio"
                  aria-checked="{{ 'false' if active else 'true' }}">
            {{ custom_label }}
          </button>
        </li>
      {% endif %}
    </ul>
  </fieldset>
{% endmacro %}
```

### Rendered example 1 — Auditoría

```jinja
{{ date_range_presets(
     presets=[
       {"key": "today", "label": "Hoy", "from": "_today", "to": "_today"},
       {"key": "yesterday", "label": "Ayer", "from": "_yesterday", "to": "_yesterday"},
       {"key": "7d", "label": "Últimos 7d", "from": "_last_7d_start", "to": "_today"},
       {"key": "30d", "label": "Últimos 30d", "from": "_last_30d_start", "to": "_today"},
       {"key": "month", "label": "Este mes", "from": "_this_month_start", "to": "_this_month_end"},
       {"key": "quarter", "label": "Trimestre", "from": "_quarter_start", "to": "_quarter_end"},
     ],
     target_input_from='#audit-desde',
     target_input_to='#audit-hasta',
     active_key='7d'
) }}
```

```html
<fieldset class="date-range-presets" aria-label="Período rápido">
  <legend class="visually-hidden">Período rápido</legend>
  <ul class="date-range-presets__list" role="radiogroup">
    <li class="date-range-presets__item">
      <button type="button" class="date-range-presets__chip" data-date-preset data-from="2026-09-27" data-to="2026-09-27" data-target-from="#audit-desde" data-target-to="#audit-hasta" data-key="today" data-on-apply="" role="radio" aria-checked="false">Hoy</button>
    </li>
    <li class="date-range-presets__item">
      <button type="button" class="date-range-presets__chip" data-date-preset data-from="2026-09-26" data-to="2026-09-26" data-target-from="#audit-desde" data-target-to="#audit-hasta" data-key="yesterday" data-on-apply="" role="radio" aria-checked="false">Ayer</button>
    </li>
    <li class="date-range-presets__item">
      <button type="button" class="date-range-presets__chip is-active" data-date-preset data-from="2026-09-20" data-to="2026-09-27" data-target-from="#audit-desde" data-target-to="#audit-hasta" data-key="7d" data-on-apply="" role="radio" aria-checked="true">Últimos 7d</button>
    </li>
    <!-- ... -->
    <li class="date-range-presets__item">
      <button type="button" class="date-range-presets__chip date-range-presets__chip--custom" data-date-preset-custom data-target-from="#audit-desde" data-target-to="#audit-hasta" role="radio" aria-checked="false">Personalizado</button>
    </li>
  </ul>
</fieldset>
```

### Rendered example 2 — Bank

```jinja
{{ date_range_presets(
     presets=[
       {"key": "7d", "label": "Últimos 7d", "from": "_last_7d_start", "to": "_today"},
       {"key": "30d", "label": "Últimos 30d", "from": "_last_30d_start", "to": "_today"},
       {"key": "month", "label": "Este mes", "from": "_this_month_start", "to": "_this_month_end"},
       {"key": "year", "label": "Año", "from": "_year_start", "to": "_year_end"},
     ],
     custom_label='Otro rango'
) }}
```

## Behavior rules

| Condition | Behavior |
|-----------|----------|
| `presets` empty | Macro raises `MacroArgumentError`. |
| `from`/`to` uses placeholder tokens | Server resolves at render time using the Python `datetime` module's locale-aware helpers, anchored to `now()` in the server timezone (`America/Asuncion`). |
| `_today` / `_yesterday` | Single-day range, `from = to`. |
| `_last_7d_start` | `today - 7 days`, inclusive. |
| `_this_week_start` / `_this_week_end` | Monday-Sunday week (Paraguayan business norm). |
| `_quarter_start` / `_quarter_end` | Calendar quarter containing `now()`. |
| `from > to` after resolution | Swapped silently, with a console warning. |
| `custom_enabled=False` | No "Personalizado" chip is appended; users must use the input fields directly. |
| Click on a preset | Writes ISO date strings into the target inputs, marks the chip `is-active`, clears others, fires `on_apply()` (or submits the form). |
| Click on "Personalizado" | Clears active state of all presets; users can edit the inputs directly. |
| Inputs not found via CSS selector | Logs console error; does not throw. The chip click becomes a no-op. |
| `active_key` not in `presets` | Falls back to "Personalizado" (if enabled) or no active chip. |

### Accessibility

- `<fieldset>` + visually-hidden `<legend>` for the group label.
- `role="radiogroup"` + each chip is `role="radio"` with `aria-checked`.
- Arrow-key navigation moves between chips; `Space`/`Enter` activates.
- The macro doesn't manipulate focus — the page form's submission flow takes over.

### Locale

- Date formatting in labels is handled by `date_range_presets` server-side and shown as ISO in `data-from`/`data-to` (machine-friendly). The user sees the inputs render `dd/mm/aaaa` via `<input type="date">` styling override.
- Preset labels are Spanish ("Hoy", "Ayer", "Últimos 7d") — passed by the caller, not auto-translated.

## Used by

- **Auditoría** (top of the filter card)
- **Bank** movements (paired with date inputs)
- **Inventario-movimientos** (planned)
- **Reponer** (period overlay for trend)
- **Pedidos board** (compact: "Hoy · Esta semana" — no manual inputs needed)
- **Reportes** (per-card date pickers — small variant, `size='sm'`)
- **Lista de compras** KPI tile "Sincronizados en últimos 7d"
- **Resumen diario** filter bar

## Required Web Component / JS

- A small enhancement script (or inline in a base layout) that:
  - Listens for `click` on `[data-date-preset]` and writes to `data-target-from` / `data-target-to` inputs.
  - Toggles `is-active` class.
  - Calls `data-on-apply()` if set, else dispatches a `change` event on the form so `<form>` submission triggers naturally.
- No `<saskia-*>` element strictly required (declarative attribute handlers are enough).
- Falls back gracefully with no JS: chips are just `<button type="button">`, do nothing — keyboard users still get the visual chips but must use the inputs.

## Anti-patterns

- ❌ **Don't** use `date_range_presets` for **time-of-day** ranges (e.g., "Esta tarde", "Ahora") — that's a different macro (out of scope).
- ❌ **Don't** bake a fixed `now()` into the HTML — `_today` etc. must be resolved server-side per request to stay accurate.
- ❌ **Don't** change the placeholder token set ad-hoc — add new tokens in the schema first.
- ❌ **Don't** pass `from > to` — the macro will swap them. Validate upstream.
- ❌ **Don't** set `custom_label='Personalizado'` (the default) **and** put inputs above the chips — chips should come first; inputs become "Edit these freely."
- ❌ **Don't** assume a particular date input library. The macro just writes strings into any `<input>` matching the selector.
- ❌ **Don't** use `active_key` set to a key not in `presets` — it should be set by the server based on the resolved URL state.

---

# Macro 8: `severity_left_stripe(severity, thickness='4px')`

## Purpose

Render a 4px colored vertical stripe on the left edge of a card or row to indicate severity at a glance. Pairs with `card`, `data_table` rows, and `inline_warning`.

## Arguments

| Argument    | Type   | Default | Required | Notes |
|-------------|--------|---------|----------|-------|
| `severity`  | `str`  | —       | ✅       | One of `ok` / `info` / `warn` / `danger` / `neutral` / `muted`. |
| `thickness` | `str`  | `"4px"` | ❌       | CSS width. `2px`, `3px`, `4px`, `6px`. |
| `extra_class` | `str` | `""`   | ❌       | Additional CSS class for layout (e.g., `severity_left_stripe--rounded`). |
| `sr_label`  | `str \| None` | `None` | ❌ | Screen-reader text (e.g., "Crítico: requiere atención inmediata"). |

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/severity_left_stripe.html #}
{% macro severity_left_stripe(severity, thickness='4px', extra_class='', sr_label=None) %}
  <span class="severity-stripe severity-stripe--{{ severity }} {{ extra_class }}"
        style="width: {{ thickness }}"
        role="{% if sr_label %}img{% else %}presentation{% endif %}"
        {% if sr_label %}aria-label="{{ sr_label }}"{% else %}aria-hidden="true"{% endif %}></span>
{% endmacro %}
```

> In practice, this macro is rarely called directly — `card-with-stripe` and `data_table` rows include the stripe as a built-in modifier. The standalone macro exists for ad-hoc card chromes and custom containers.

### Rendered example 1 — inside a card

```jinja
<article class="card-with-stripe card-with-stripe--{{ severity }}">
  {{ severity_left_stripe(severity='danger', sr_label='Crítico') }}
  <div class="card-with-stripe__body">
    <h3>Stock crítico</h3>
    <p>1 ingrediente requiere compra inmediata.</p>
  </div>
</article>
```

```html
<article class="card-with-stripe card-with-stripe--danger">
  <span class="severity-stripe severity-stripe--danger" style="width: 4px"
        role="img" aria-label="Crítico"></span>
  <div class="card-with-stripe__body">
    <h3>Stock crítico</h3>
    <p>1 ingrediente requiere compra inmediata.</p>
  </div>
</article>
```

### Rendered example 2 — embedded into a `data_table` row

```html
<tr class="data-table__row severity-stripe--warn" data-row-id="3">
  <!-- stripe is rendered via CSS `border-left`, not as a DOM element, when applied to a table row -->
  <td>…</td>
</tr>
```

> Table rows use a CSS border-left approach for layout reasons; the macro form is for cards/standalone panels.

## Behavior rules

| Condition | Behavior |
|-----------|----------|
| `severity` not in allowed set | Falls back to `neutral`, logs warning. |
| `thickness` not a valid CSS length | Falls back to `4px`. |
| `sr_label` provided | Sets `role="img" aria-label="…"`; otherwise `aria-hidden="true"`. |
| Used inside a `<table>` | **Prefer CSS `border-left`** on the `<tr>` instead of inserting the `<span>` — table layout collapses if cells get a sibling element. |
| Used inside a flex/grid card | The `<span>` sits left of content; the card uses `display: flex; align-items: stretch`. |
| Used inside an inline element | **Disallowed** — the stripe is a block-level element. |

### Accessibility

- Without `sr_label`: `aria-hidden="true"` (decorative).
- With `sr_label`: `role="img" aria-label="…"` so screen readers announce severity at the start of the card.
- Color is **never** the only signal — every card with a stripe should also have a title, tone-colored icon, or `inline_warning`.

### Locale

- N/A (no text).

## Used by

- **Riesgos** cards (severity P×I)
- **Auditoría** rows (action type — Destructive = danger, etc.)
- **Bank** transactions (large negative → danger)
- **Inventario** list rows (stock bajo → danger)
- **Reponer** rows
- **Pedidos board** cards (overdue orders → danger)
- **Lista de compras** rows (caducan pronto → warn)

## Required Web Component / JS

- None. Pure CSS + a tiny `<span>` (or `border-left` on `<tr>`).
- Token CSS variables must be defined globally: `--stripe-ok`, `--stripe-info`, `--stripe-warn`, `--stripe-danger`, `--stripe-neutral`, `--stripe-muted`.

## Anti-patterns

- ❌ **Don't** use a stripe for visual decoration alone — pick a real severity.
- ❌ **Don't** stack stripes (a card with two stripes loses meaning).
- ❌ **Don't** make the stripe wider than `6px` — it competes with the card title for visual weight.
- ❌ **Don't** use `severity='danger'` as a default — it's the loudest option. Reserve for actual criticals.
- ❌ **Don't** apply the stripe via `border-left` on a card AND via `box-shadow: inset 4px 0 0 red` — the macro's `<span>` and the shadow both render in the same place on some browsers. Pick one mechanism per card.
- ❌ **Don't** use this inside a `<table>` — table-cell rows need `border-left` on `<tr>`, not an in-cell element.

---

# Macro 9: `inline_warning(tone, title=None, message=None, action=None, dismissible=False, tooltip=None, icon=None, expand=None)`

## Purpose

Render an inline callout that flags a derived condition the user should know about — silent-failure warning, compliance flag (HACCP, allergen, expiry), or contextual nudge.

## Arguments

| Argument      | Type            | Default     | Required | Notes |
|---------------|-----------------|-------------|----------|-------|
| `tone`        | `str`           | —           | ✅       | `info` / `warn` / `danger` / `success`. |
| `title`       | `str \| None`   | `None`      | ❌       | Short heading (sentence case). |
| `message`     | `str \| None`   | `None`      | ❌       | 1-3 sentences explaining. Required if `title` is None. Plain text or limited markdown (bold, code). |
| `action`      | `dict \| None`  | `None`      | ❌       | `{label, href?, action?, tone?}`. The remediation CTA. |
| `dismissible` | `bool`          | `False`     | ❌       | Show a close (×) button; state persists in localStorage by `id`. |
| `tooltip`     | `str \| None`   | `None`      | ❌       | Extra explainer on hover. |
| `icon`        | `str \| None`   | `None`      | ❌       | Override the default tone icon. |
| `expand`      | `dict \| None`  | `None`      | ❌       | `{summary, body}` for a `<details>` disclosure appended below the message. |
| `id`          | `str \| None`   | `None`      | ❌       | Stable id for dismiss state persistence. Required when `dismissible=True`. |

### Action schema

```python
{
    "label": "Registrá consumo",
    "href": "/inventario/{id}/movimientos/nuevo",   # supports {id} interpolation
    "action": None,                                  # alternative: JS function name
    "tone": "primary"                                # primary | secondary | tertiary
}
```

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/inline_warning.html #}
{% from "macros/severity_left_stripe.html" import severity_left_stripe %}
{% macro inline_warning(
     tone,
     title=None,
     message=None,
     action=None,
     dismissible=False,
     tooltip=None,
     icon=None,
     expand=None,
     id=None
) %}
  {% set default_icon = {'info': 'info', 'warn': 'alert-triangle', 'danger': 'alert-octagon', 'success': 'check-circle'}[tone] %}
  <aside class="inline-warning inline-warning--{{ tone }}"
         {% if id %}id="iw-{{ id }}"{% endif %}
         {% if tone == 'danger' %}role="alert"{% else %}role="status"{% endif %}
         aria-live="{% if tone == 'danger' %}assertive{% else %}polite{% endif %}">
    <span class="inline-warning__icon" aria-hidden="true">
      <saskia-icon name="{{ icon or default_icon }}"></saskia-icon>
    </span>
    <div class="inline-warning__body">
      {% if title %}<h4 class="inline-warning__title"{% if tooltip %} title="{{ tooltip }}"{% endif %}>{{ title }}</h4>{% endif %}
      {% if message %}<p class="inline-warning__message">{{ message }}</p>{% endif %}
      {% if expand %}
        <details class="inline-warning__expand">
          <summary>{{ expand.summary }}</summary>
          <div>{{ expand.body }}</div>
        </details>
      {% endif %}
      {% if action %}
        {% if action.href %}
          <a class="btn btn--{{ action.tone or 'primary' }} btn--sm" href="{{ action.href }}">
            {% if action.icon %}<saskia-icon name="{{ action.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
            {{ action.label }}
          </a>
        {% elif action.action %}
          <button type="button" class="btn btn--{{ action.tone or 'primary' }} btn--sm" data-action="{{ action.action }}">
            {% if action.icon %}<saskia-icon name="{{ action.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
            {{ action.label }}
          </button>
        {% endif %}
      {% endif %}
    </div>
    {% if dismissible %}
      <button type="button" class="inline-warning__dismiss" aria-label="Cerrar advertencia" data-inline-warning-dismiss="{{ id }}">
        <saskia-icon name="x" aria-hidden="true"></saskia-icon>
      </button>
    {% endif %}
  </aside>
{% endmacro %}
```

### Rendered example 1 — Inventario-detalle "Sin consumo reciente"

```jinja
{{ inline_warning(
     tone='warn',
     title='Sin consumo reciente',
     message='No hay registros de consumo para este ingrediente en los últimos 14 días. El pronóstico requiere al menos 3 días de historial.',
     action={'label': 'Registrá consumo', 'href': '/inventario/1/movimientos/nuevo', 'icon': 'plus'},
     tooltip='El pronóstico requiere al menos 3 días de historial.',
     dismissible=True,
     id='ing-1-no-consumo',
     icon='alert-triangle'
) }}
```

```html
<aside class="inline-warning inline-warning--warn" id="iw-ing-1-no-consumo"
       role="status" aria-live="polite">
  <span class="inline-warning__icon" aria-hidden="true">
    <saskia-icon name="alert-triangle"></saskia-icon>
  </span>
  <div class="inline-warning__body">
    <h4 class="inline-warning__title" title="El pronóstico requiere al menos 3 días de historial.">Sin consumo reciente</h4>
    <p class="inline-warning__message">No hay registros de consumo para este ingrediente en los últimos 14 días. El pronóstico requiere al menos 3 días de historial.</p>
    <a class="btn btn--primary btn--sm" href="/inventario/1/movimientos/nuevo">
      <saskia-icon name="plus" aria-hidden="true"></saskia-icon>
      Registrá consumo
    </a>
  </div>
  <button type="button" class="inline-warning__dismiss" aria-label="Cerrar advertencia" data-inline-warning-dismiss="ing-1-no-consumo">
    <saskia-icon name="x" aria-hidden="true"></saskia-icon>
  </button>
</aside>
```

### Rendered example 2 — Receta-editar "Costo Gs. 0"

```jinja
{{ inline_warning(
     tone='danger',
     title='Costo del lote en Gs. 0',
     message='No se puede calcular el costo estimado porque al menos un ingrediente no tiene precio de compra cargado.',
     action={'label': 'Ir al ingrediente', 'href': '/inventario/1/editar'},
     icon='alert-octagon',
     expand={'summary': '¿Por qué pasa esto?', 'body': 'Cada línea de ingrediente necesita un <code>precio_compra_gs</code> distinto de null o 0. Verificá los insumos marcados en gris.'}
) }}
```

### Rendered example 3 — Pedido-detalle stock-preview 500 risk warning

```jinja
{{ inline_warning(
     tone='warn',
     title='Verificar stock antes de cumplir',
     message='Antes de marcar este pedido como cumplido, verificá que tenés los ingredientes necesarios.',
     action={'label': 'Ver stock', 'href': '/pedidos/1/stock'},
     tooltip='Si el endpoint de stock-preview responde con error, esta página seguirá funcionando.'
) }}
```

## Behavior rules

| Condition | Behavior |
|-----------|----------|
| `tone='danger'` | `role="alert" aria-live="assertive"` (interrupts screen readers). |
| `tone` other | `role="status" aria-live="polite"`. |
| `dismissible=True` and `id=None` | Macro raises `MacroArgumentError` — id is required for persistence. |
| `dismissible=True` + previously dismissed (via `localStorage`) | Renders nothing. Server-side rendering bypasses this — the dismiss state is client-only. |
| `action.href` with `{id}` placeholder | Interpolated with the macro's caller — pass `id` as kwarg or use a static path. |
| `action.action` provided | Renders `<button data-action>`. |
| `message` longer than 600 chars | Truncated at sentence boundary with `…`. Emits a warning. Use `expand` for longer content. |
| `tone='success'` | Allowed (e.g., "Migración exitosa", "Backup completo"). Renders green with `check-circle`. |
| Two adjacent warnings of the same `tone`+`title` | Consider merging — duplicate warnings are noise. |
| `expand.summary` longer than 80 chars | Truncated at word boundary with `…`. |
| Warning placed inline in a card | Card needs `display: flex` and the warning replaces one of its rows. |
| Warning placed inline in a form | Form input styles must coexist (border, padding) — the warning is itself a `<aside>`. |

### Accessibility

- `role="alert"` for danger, `role="status"` for everything else.
- `aria-live` matches the role's tone.
- Dismiss button has an `aria-label` ("Cerrar advertencia"), not just an icon.
- Tooltip via `title` (browser-native), readable.

### Locale

- Title/message Spanish; macro doesn't auto-translate.
- Action labels follow the same voseo/infinitive convention as the rest of the app.

## Used by

- **Inventario-detalle** — "Sin consumo reciente", "Precio faltante"
- **Inventario-movimientos** — "Sin movimientos registrados" overlap with `empty_state` (use one or the other)
- **Receta-editar** — "Costo Gs. 0", "Sin sub-recetas"
- **Vs-mercado** — cells with "—" → "Completar"
- **Pedido-detalle** — "Verificar stock antes de cumplir" (warn before 500 page)
- **Reponer** — "Sin proveedor" cells (action: "Asignar proveedor")
- **Producción** — "qty override" warnings
- **Bank** — "Sin categorizar" (auto-categorize CTA)
- **HACCP check** components
- **Allergen cross-contamination** callouts
- **Expiry approaching** warnings on Inventario-detalle

## Required Web Component / JS

- **`<saskia-icon>`**
- A small enhancement script for `data-inline-warning-dismiss` — toggles `hidden` and writes `localStorage['iw-dismissed:<id>'] = '1'`. On page load, reads and hides matching warnings.
- `data-action` handler (shared with `empty_state`).

## Anti-patterns

- ❌ **Don't** use this macro for happy-path info that doesn't require action ("Su sesión está por expirar" — use a toast instead).
- ❌ **Don't** use `tone='success'` for celebration moments ("¡Listo!") — that's a toast.
- ❌ **Don't** repeat the same warning on every page load — `dismissible=True id=…` lets users suppress it. Use it.
- ❌ **Don't** omit `action` when there is a real remediation path. A warning without an action is just complaint.
- ❌ **Don't** use `role="alert"` unless the user must hear it now (`danger`-only). Anything else is `role="status"` to avoid screen-reader interruptions.
- ❌ **Don't** wrap a warning inside another warning — it's a contradiction.
- ❌ **Don't** reuse this for **destructive confirmations** — that's `confirm_destructive`. Warnings are *informational*; confirms are *gates*.
- ❌ **Don't** set `dismissible=True` for compliance/HACCP warnings — those must persist per audit policy.

---

# Macro 10: `confirm_destructive(trigger_label, title, body, confirm_label, cancel_label='Cancelar', confirm_action=None, confirm_method='POST', require_typed_confirmation=False, typed_phrase='ELIMINAR', icon='alert-triangle', trigger_tone='danger', trigger_icon='trash', trigger_variant='button', size='md', secondary_action=None)`

## Purpose

Render a modal confirmation gate for destructive actions (delete, purge, cancel, archive-many) — prevents accidental irreversible operations. Reuses the `<saskia-confirm-modal>` web component behind the scenes.

## Arguments

| Argument                     | Type            | Default       | Required | Notes |
|------------------------------|-----------------|---------------|----------|-------|
| `trigger_label`              | `str`           | —             | ✅       | Text on the trigger button. |
| `title`                      | `str`           | —             | ✅       | Modal title (sentence case, no period). |
| `body`                       | `str`           | —             | ✅       | Detailed body; HTML allowed (escaped via `\|safe` is the caller's responsibility). |
| `confirm_label`              | `str`           | —             | ✅       | Text on the confirm button. |
| `cancel_label`               | `str`           | `"Cancelar"`  | ❌       | Cancel button text. |
| `confirm_action`             | `str \| None`   | `None`        | ❌       | URL of the destructive endpoint. Required if not using `confirm_action_js`. |
| `confirm_action_js`          | `str \| None`   | `None`        | ❌       | JS function name called on confirm instead of fetching `confirm_action`. |
| `confirm_method`             | `str`           | `"POST"`      | ❌       | `POST` / `DELETE`. |
| `require_typed_confirmation` | `bool`          | `False`       | ❌       | If True, user must type `typed_phrase` to enable the confirm button. |
| `typed_phrase`               | `str`           | `"ELIMINAR"`  | ❌       | The exact phrase required. Case-insensitive match. |
| `icon`                       | `str`           | `"alert-triangle"` | ❌   | Icon in the modal header. |
| `trigger_tone`               | `str`           | `"danger"`    | ❌       | `danger` / `warn` / `neutral` — drives trigger button color. |
| `trigger_icon`               | `str`           | `"trash"`     | ❌       | Icon on the trigger button. |
| `trigger_variant`            | `str`           | `"button"`    | ❌       | `button` (full button) / `icon` (icon-only, with tooltip) / `link` (text link). |
| `size`                       | `str`           | `"md"`        | ❌       | `sm` / `md` / `lg`. |
| `secondary_action`           | `dict \| None`  | `None`        | ❌       | A non-destructive action offered alongside ("Ver historial", "Exportar antes"). |
| `csrf_token`                 | `str \| None`   | `None`        | ❌       | When set, included as `X-CSRF-Token` header on the destructive fetch. |

## Emitted HTML (Jinja source)

```jinja
{# templates/macros/confirm_destructive.html #}
{% macro confirm_destructive(
     trigger_label,
     title,
     body,
     confirm_label,
     cancel_label='Cancelar',
     confirm_action=None,
     confirm_action_js=None,
     confirm_method='POST',
     require_typed_confirmation=False,
     typed_phrase='ELIMINAR',
     icon='alert-triangle',
     trigger_tone='danger',
     trigger_icon='trash',
     trigger_variant='button',
     size='md',
     secondary_action=None,
     csrf_token=None
) %}
  {% if not confirm_action and not confirm_action_js %}
    {% set raise_msg = 'confirm_destructive requires confirm_action or confirm_action_js' %}
    {# Render error in the template (not Python raise) so partial-page renders still surface it #}
    {{ raise_msg }}
  {% endif %}

  <saskia-confirm-modal
     data-modal-id="confirm-{{ title|lower|replace(' ', '-') }}-{{ trigger_label|lower|replace(' ', '-')|trim }}"
     data-size="{{ size }}"
     data-icon="{{ icon }}"
     data-trigger-tone="{{ trigger_tone }}">

    {% if trigger_variant == 'button' %}
      <button type="button" class="btn btn--{{ trigger_tone }}" data-confirm-trigger
              aria-haspopup="dialog">
        {% if trigger_icon %}<saskia-icon name="{{ trigger_icon }}" aria-hidden="true"></saskia-icon>{% endif %}
        {{ trigger_label }}
      </button>
    {% elif trigger_variant == 'icon' %}
      <button type="button" class="btn btn--icon btn--{{ trigger_tone }}" data-confirm-trigger
              aria-label="{{ trigger_label }}" title="{{ trigger_label }}" aria-haspopup="dialog">
        {% if trigger_icon %}<saskia-icon name="{{ trigger_icon }}" aria-hidden="true"></saskia-icon>{% endif %}
      </button>
    {% elif trigger_variant == 'link' %}
      <a href="#" class="link link--{{ trigger_tone }}" data-confirm-trigger
         role="button" aria-haspopup="dialog">{{ trigger_label }}</a>
    {% endif %}

    <template data-confirm-content>
      <div class="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-body">
        <header class="confirm-modal__head">
          <saskia-icon name="{{ icon }}" class="confirm-modal__icon" aria-hidden="true"></saskia-icon>
          <h2 id="confirm-title" class="confirm-modal__title">{{ title }}</h2>
        </header>
        <div id="confirm-body" class="confirm-modal__body">{{ body|safe }}</div>
        {% if require_typed_confirmation %}
          <div class="confirm-modal__typed-confirm">
            <label for="confirm-typed" class="confirm-modal__typed-label">
              Escribí <code>{{ typed_phrase }}</code> para confirmar:
            </label>
            <input type="text" id="confirm-typed" data-confirm-typed
                   data-typed-phrase="{{ typed_phrase }}"
                   autocomplete="off"
                   autocapitalize="characters"
                   spellcheck="false">
          </div>
        {% endif %}
        <footer class="confirm-modal__foot">
          <button type="button" class="btn btn--secondary" data-confirm-cancel>{{ cancel_label }}</button>
          {% if secondary_action %}
            {% if secondary_action.href %}
              <a class="btn btn--tertiary" href="{{ secondary_action.href }}">
                {% if secondary_action.icon %}<saskia-icon name="{{ secondary_action.icon }}" aria-hidden="true"></saskia-icon>{% endif %}
                {{ secondary_action.label }}
              </a>
            {% endif %}
          {% endif %}
          <button type="button"
                  class="btn btn--{{ trigger_tone }} confirm-modal__confirm"
                  data-confirm-ok
                  {% if confirm_action %}data-action="{{ confirm_action }}"{% endif %}
                  {% if confirm_action_js %}data-action-js="{{ confirm_action_js }}"{% endif %}
                  data-method="{{ confirm_method }}"
                  {% if require_typed_confirmation %}data-require-typed="true"{% endif %}
                  {% if csrf_token %}data-csrf="{{ csrf_token }}"{% endif %}
                  {% if require_typed_confirmation %}disabled{% endif %}>
            {{ confirm_label }}
          </button>
        </footer>
      </div>
    </template>
  </saskia-confirm-modal>
{% endmacro %}
```

### Rendered example 1 — Auditoría purge

```jinja
{{ confirm_destructive(
     trigger_label='Eliminar entradas de más de 1 año',
     trigger_tone='danger',
     title='Eliminar entradas antiguas de auditoría',
     body='Vas a eliminar <strong>1.247 entradas</strong> con más de 1 año de antigüedad. Esta acción es irreversible y compromete la cadena de auditoría.',
     confirm_label='Sí, eliminar 1.247 entradas',
     confirm_action='POST /auditoria/purge-old',
     require_typed_confirmation=True,
     typed_phrase='ELIMINAR',
     icon='alert-triangle',
     secondary_action={'label': 'Exportar antes', 'href': '/auditoria/export.csv?older=1y', 'icon': 'download'},
     csrf_token=csrf_token()
) }}
```

```html
<saskia-confirm-modal data-modal-id="confirm-eliminar-entradas-antiguas-de-auditoría-eliminar-entradas-de-más-de-1-año"
   data-size="md" data-icon="alert-triangle" data-trigger-tone="danger">
  <button type="button" class="btn btn--danger" data-confirm-trigger aria-haspopup="dialog">
    <saskia-icon name="trash" aria-hidden="true"></saskia-icon>
    Eliminar entradas de más de 1 año
  </button>
  <template data-confirm-content>
    <div class="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-body">
      <header class="confirm-modal__head">
        <saskia-icon name="alert-triangle" class="confirm-modal__icon" aria-hidden="true"></saskia-icon>
        <h2 id="confirm-title" class="confirm-modal__title">Eliminar entradas antiguas de auditoría</h2>
      </header>
      <div id="confirm-body" class="confirm-modal__body">Vas a eliminar <strong>1.247 entradas</strong> con más de 1 año de antigüedad. Esta acción es irreversible y compromete la cadena de auditoría.</div>
      <div class="confirm-modal__typed-confirm">
        <label for="confirm-typed" class="confirm-modal__typed-label">Escribí <code>ELIMINAR</code> para confirmar:</label>
        <input type="text" id="confirm-typed" data-confirm-typed data-typed-phrase="ELIMINAR" autocomplete="off" autocapitalize="characters" spellcheck="false">
      </div>
      <footer class="confirm-modal__foot">
        <button type="button" class="btn btn--secondary" data-confirm-cancel>Cancelar</button>
        <a class="btn btn--tertiary" href="/auditoria/export.csv?older=1y">
          <saskia-icon name="download" aria-hidden="true"></saskia-icon>
          Exportar antes
        </a>
        <button type="button" class="btn btn--danger confirm-modal__confirm"
                data-confirm-ok data-action="POST /auditoria/purge-old" data-method="POST"
                data-require-typed="true" data-csrf="abc123…" disabled>
          Sí, eliminar 1.247 entradas
        </button>
      </footer>
    </div>
  </template>
</saskia-confirm-modal>
```

### Rendered example 2 — Pedido cancel (icon trigger, smaller modal)

```jinja
{{ confirm_destructive(
     trigger_label='Cancelar pedido',
     trigger_icon='x-circle',
     trigger_variant='icon',
     title='Cancelar el pedido #1',
     body='El pedido quedará marcado como cancelado. Se conserva en el historial para auditoría.',
     confirm_label='Sí, cancelar',
     confirm_action='POST /pedidos/1/cancel',
     icon='alert-circle',
     size='sm',
     secondary_action={'label': 'Duplicar en su lugar', 'href': '/pedidos/1/duplicar', 'icon': 'copy'}
) }}
```

## Behavior rules

| Condition | Behavior |
|-----------|----------|
| Neither `confirm_action` nor `confirm_action_js` provided | Macro renders an inline error string in the template instead of silent failure. Caller fix: always supply an action. |
| `require_typed_confirmation=True` and the user types `typed_phrase` (case-insensitive) | Confirm button enables. |
| `require_typed_confirmation=True` and the field is empty | Confirm button stays disabled. |
| `confirm_action` is `GET` (`method='GET'`) | The web component navigates the browser to the URL — confirmations don't make sense for GET; warn the caller (logs). |
| User confirms | Web component fires a fetch (CSRF-included) to `confirm_action`; on success, it dispatches a `confirm:success` event and closes the modal; on failure, it surfaces the error inline. |
| User cancels | Closes modal; focus returns to the trigger button; no fetch. |
| User presses `Escape` | Closes modal (same as cancel). |
| User clicks backdrop | Closes modal. |
| Trigger button is inside a `<form>` | Default `type="button"` prevents accidental submit. |
| `secondary_action` provided | Renders as a non-destructive third button between Cancel and Confirm. |
| `csrf_token=None` | Web component reads from `<meta name="csrf-token">` in document head (set by base template). |
| `body` contains user-supplied data | Caller **must** escape — the macro uses `\|safe`. Document this clearly. |
| Modal open state | The page background scrolls are locked (`body { overflow: hidden }`). |
| Multiple modals on the same page | Each gets a unique `data-modal-id`. Only one is open at a time. |
| `trigger_variant='link'` rendered as `<a href="#">` | Default `#` is intercepted; nothing navigates. |

### Accessibility

- Modal has `role="dialog" aria-modal="true"`.
- `aria-labelledby` → title; `aria-describedby` → body.
- Focus trap: when modal opens, focus moves to the first focusable element (typed input or cancel button). `Tab` cycles within the modal. `Shift+Tab` works.
- `Escape` closes (with `aria-label="Cerrar"` on a close button as well — both routes are available).
- Trigger button has `aria-haspopup="dialog"`.
- For typed confirmation: button stays disabled while the typed value doesn't match — disabled state is announced.
- Body content includes a count or count-link so screen-reader users get the same context as sighted users ("Vas a eliminar 1,247 entradas...").

### Locale

- All copy is Spanish; macro doesn't translate.
- Numbers in `body` are formatted in Spanish locale (`1.247`); callers must pre-format.

## Used by

- **Auditoría** purge (typed confirmation)
- **Proveedor** delete (typed confirmation)
- **Pedido** cancel / refund
- **Receta** archive
- **Riesgo** close (without mitigation)
- **Bank** transaction reverse
- **Inventario** bulk delete (per-row via `data_table`)
- **Lista de compras** clear-all
- **Pricing** channel margin reset
- **Riesgos** mass-delete (typed confirmation)

## Required Web Component / JS

- **`<saskia-confirm-modal>`** — a custom element that:
  - Listens for `click` on `[data-confirm-trigger]` and opens the modal template content.
  - Wires `[data-confirm-cancel]` to close.
  - Wires `[data-confirm-ok]` to fire the fetch with CSRF.
  - Implements focus trap and `aria-modal` semantics.
  - Restores focus to the trigger on close.
- **`<saskia-icon>`** for header/trigger icons.
- The web component lazy-loads on first use.

## Anti-patterns

- ❌ **Don't** use this for **non-destructive** actions ("Save", "Submit"). It's reserved for irreversible operations.
- ❌ **Don't** omit `confirm_action` — every destructive confirm must point somewhere concrete.
- ❌ **Don't** use `require_typed_confirmation=True` for routine deletes ("Delete this comment"). Reserve for high-stakes ops (purge audit log, delete user, mass-archive).
- ❌ **Don't** put `confirm_destructive` inside another modal — modals don't stack.
- ❌ **Don't** set `trigger_variant='link'` for high-stakes operations where the link could be mistaken for navigation — use `button`.
- ❌ **Don't** render `body` with `|safe(user_input)` — caller escapes. If the caller can't guarantee escaping, use a non-HTML `body`.
- ❌ **Don't** forget a CSRF token on cookie-authenticated POSTs — the modal will silently 419. Always pass `csrf_token=...`.
- ❌ **Don't** rely on `confirm_action_js` for things that could be a real URL — server-side enforcement is the source of truth. JS-only handlers are for prototype states only.
- ❌ **Don't** use the same `data-modal-id` (auto-generated from title+label) twice on one page — the modal-id collision opens the wrong one. Use unique phrasing.
- ❌ **Don't** decorate the trigger with `target="_blank"` or other anchor attributes that imply navigation when `trigger_variant='link'` — the `<a>` is decorative; opening is JS-driven.

---

## Cross-macro rules

These rules apply across all 10 macros and resolve overlap, naming, and stylistic conventions.

### Naming & file location

All macros live in `templates/macros/` (or `templates/_macros/` — pick one for the codebase). Filenames match the macro name (`kpi_tile.html`, `status_pill.html`). Import as:

```jinja
{% from "macros/kpi_tile.html" import kpi_tile %}
```

### Color tokens

All tones reference the same set of CSS variables so tokens are global:

```css
:root {
  --tone-ok:        #16a34a;
  --tone-info:      #2563eb;
  --tone-warn:      #d97706;
  --tone-danger:    #dc2626;
  --tone-neutral:   #374151;
  --tone-muted:     #9ca3af;
  --pill-ok:        #16a34a;
  --pill-info:      #2563eb;
  --pill-warn:      #d97706;
  --pill-danger:    #dc2626;
  --pill-neutral:   #374151;
  --pill-muted:     #9ca3af;
  --stripe-ok:      var(--tone-ok);
  --stripe-info:    var(--tone-info);
  --stripe-warn:    var(--tone-warn);
  --stripe-danger:  var(--tone-danger);
  --stripe-neutral: var(--tone-neutral);
  --stripe-muted:   var(--tone-muted);
}
```

### Density scale

Three densities — `compact`, `comfortable` (default), `spacious`. Macros that have density: `data_table`, `bulk_action_bar` (via outer spacing only). Macros that don't: `kpi_tile`, `status_pill`, `empty_state`, `inline_warning`, `confirm_destructive`, `filter_chips`, `date_range_presets`, `severity_left_stripe`.

### Icon family

All icons come from **Lucide** (lucide.dev). Names are kebab-case (`alert-triangle`, `arrow-up`). Macros never embed inline SVG — always use `<saskia-icon>`.

### Spanish copy

- Use sentence case ("Pendiente", "Sin consumo reciente", "Sin variantes registradas"), not Title Case.
- For CTA buttons, match the page's existing voseo/infinitive convention (the macro does not decide; the page decides).
- Currency: `Gs. 1.234.567` (period thousands separator). Always prefix `Gs.`.
- Dates: `dd/mm/aaaa`.
- Numbers under 1.000: no separator.
- Never translate tokens — pass Spanish strings from the caller.

### Accessibility

- Every interactive macro has a focus ring visible at 200% zoom.
- Every interactive macro works without JS (or has a `<noscript>` fallback note).
- Color is never the only signal.
- ARIA roles are explicit (no implicit semantic HTML reliance).

### Where each macro is forbidden

| Macro | Cannot be used for |
|-------|---------------------|
| `kpi_tile` | Cell content (use a styled `<td>`); inline alerts (use `inline_warning`) |
| `status_pill` | Free-form tags ("Sin gluten", "Alto en proteína") — that's a different macro |
| `data_table` | Kanban / board layouts (different macro) |
| `filter_chips` | Multi-select dropdowns |
| `empty_state` | Errors (use `inline_warning`); celebratory toasts (use `<saskia-toast>`) |
| `bulk_action_bar` | Persistent action strips unrelated to multi-select |
| `date_range_presets` | Time-of-day pickers; absolute date range with no presets |
| `severity_left_stripe` | Standalone visual decoration without a card |
| `inline_warning` | Happy-path info, destructive confirmations |
| `confirm_destructive` | Non-destructive confirmations ("Are you sure you want to save?") |

### File budget (per-macro)

| Macro | Approx. lines | Notes |
|-------|---------------|-------|
| `kpi_tile` | 60 | Most logic |
| `status_pill` | 30 | Trivial |
| `data_table` | 180 | Largest by far |
| `filter_chips` | 60 | |
| `empty_state` | 60 | |
| `bulk_action_bar` | 50 | Thin wrapper around web component |
| `date_range_presets` | 50 | |
| `severity_left_stripe` | 8 | Trivial |
| `inline_warning` | 80 | |
| `confirm_destructive` | 120 | Web component does the heavy lifting |

Total: ~700 lines of Jinja + ~50KB JS for the web components (`saskia-icon`, `saskia-tooltip`, `saskia-sparkline`, `saskia-bulk-bar`, `saskia-confirm-modal`).

### Web component contract

Each web component:

- Lives in `/static/js/saskia/<name>.js` (or under a CDN subpath).
- Uses custom-element registry guarded with `customElements.define(name, …)` only once.
- Accepts data via `data-*` attributes or JSON in attribute values.
- Emits CustomEvents (`bulk:count`, `confirm:success`, `inline-warning:dismissed`, etc.) on itself.
- Shadow-DOM encapsulated styles (no global CSS leaks).
- Works without a build step (ES2022 + native modules).

### Test contract

Per macro, there must be:

1. **Snapshot tests** for ≥3 rendered examples documented here.
2. **Edge-case tests** for every "Behavior rule" row.
3. **Accessibility tests** (axe-core, with focus on `role`, `aria-live`, color contrast).
4. **Visual regression** per density + tone combination.

### Migration path (from current templates)

The current codebase uses ad-hoc HTML in each page (per `audit-batch2` and `audit-batch3`). The 10 macros here are the canonical replacement. Migration order:

1. **`empty_state`** — first (replaces scattered empty cases; high visibility, low risk).
2. **`status_pill`** — second (already partially in use; collapse inconsistencies).
3. **`kpi_tile`** — third (replaces the floating label-and-number rows everywhere).
4. **`inline_warning`** — fourth (turns silent "—" and "sin proveedor" into actionable).
5. **`severity_left_stripe`** — fifth (additive).
6. **`confirm_destructive`** — sixth (fixes the unbounded destructive buttons in Auditoría, etc.).
7. **`date_range_presets`** — seventh (formalizes Auditoría chips, replaces elsewhere).
8. **`filter_chips`** — eighth (multi-page rollout; needs URL-state coordination).
9. **`data_table`** — ninth (largest; needs the web component + tests).
10. **`bulk_action_bar`** — tenth (paired with `data_table`).

Per the consolidation sprint plan, the **2-week quick-win** covers all 10:

- **Week 1:** ship 5 small macros (`kpi_tile`, `status_pill`, `empty_state`, `inline_warning`, `severity_left_stripe`) and apply to Riesgos, Wishlist, Bank, Proveedores aliases/dedup, Inventario list, Inventario-detalle, Receta-editar, Auditoría purge.
- **Week 2:** ship the 5 larger macros (`filter_chips`, `data_table`, `bulk_action_bar`, `date_range_presets`, `confirm_destructive`) and apply to Inventario, Proveedores, Bank, Auditoría, Reponer, Pedidos board.

Outcome: ~70% of P0+P1 wishlist items addressed without per-page rewrites.

---

## Glossary (terms used in this spec)

- **Atomic macro** — a Jinja macro that emits a self-contained block of markup with a single UI purpose; no cross-references to other macros for behavior (only for composition, like `data_table` wrapping `empty_state`).
- **Card / panel** — a bordered container that holds related content (`<article class="card">`).
- **Tone** — the semantic color category (`ok` / `info` / `warn` / `danger` / `neutral` / `muted`) used by every macro for consistent visual semantics.
- **Sparkline** — a small inline line/bar chart without axes, used inside `kpi_tile`.
- **Bulk action** — an operation that affects ≥2 selected rows at once.
- **Preset (date)** — a named range shortcut that fills in date inputs.
- **Modal** — a focus-trapped overlay blocking the rest of the page; only `<saskia-confirm-modal>` uses one.
- **Web Component** — a custom element with shadow-DOM encapsulation; the `<saskia-*>` namespace.
- **Lucide icon** — open-source icon library; all icons in this spec use Lucide.

---

*End of contract specification.*
