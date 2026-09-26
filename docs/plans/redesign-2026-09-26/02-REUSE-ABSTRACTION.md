# REUSE ABSTRACTION LAYER — Implementation Contract (v1)
Derived from 00-MASTER-PLAN.md. Read before writing ANY redesign code.
Goal: every page = composition of these primitives. No page invents its own markup for a solved problem.

---

# 1. THE DEPENDENCY RULE (memorize)

```
tokens (CSS vars)
  → atoms (single-purpose macros/CSS classes)
    → molecules (macro compositions)
      → layout templates (page skeletons)
        → pages (data + composition only)
```
- A page template may ONLY call molecules/layouts + render data. If a page needs new markup twice → promote to molecule. If an atom grows logic → split.
- No inline `style=""` in pages (utility classes or molecule variants only). No inline `font-size`. No hardcoded px margins (tokens only).
- Every money/qty/pct/date goes through F-* formatters. Every entity name through `entity_name`. Every status through `status_pill`.

---

# 2. FORMATTERS (Python template globals — the base layer)

Already exist (verify before reuse): `m.gs`, `m.gs_full`, `m.unit_display`, `m.margin_pct`, `now_str()`, `now_year()`.

| ID | Function | Contract | Replaces |
|----|----------|----------|----------|
| F-1 | `fmt_money(v)` | int-ish → "Gs. 18.000"; None/undefined/str-drift → "—"; 0 → "Gs. 0" | every raw `{{
 v }}` money cell |
| F-2 | `fmt_qty(v, unit)` | trims trailing zeros; decimal comma; unit attached: "0,4 kg", "2 u." | qty cells |
| F-3 | `fmt_pct(v, delta=False)` | ≥10 → 0 dec; <10 → 1 dec; delta adds +/− and colors upstream | pct cells |
| F-4 | `fmt_date(d, mode)` | mode: `table`→"26/09/2026", `prose`→"sáb 26 sep 2026", `iso`→input value | all dates |
| F-5 | `delta(v, prior)` | returns dict {pct, direction: up/down/neutral, empty: bool}; empty when v==0 and prior>0 ("sin ventas en el período") — ONE implementation of the neutral rule | every delta surface |
| F-6 | `entity_name(obj_or_name)` | guards hash names `^(Producto|Ingrediente|Receta) [0-9a-f]{8}$` → "X sin nombre" | title/cell rendering |
| F-7 | `tier_es(t)` / `status_es(s)` | enum → Spanish map (Bronze→Bronce…) | enum badges |

Location: extend `app/services/template_render.py` (registered as Jinja globals like `m.*` today). Unit tests property-based (W-0220).

# 3. ATOMS (macros — extend `_components/macros.html` unless noted)

## 3.1 Existing — REUSE AS-IS (do not duplicate)
| Atom | Use for | Notes |
|------|---------|-------|
| `m.gs` / `m.gs_full` | money | already undefined-safe (hardened) |
| `m.stock_badge` | stock state | feed F-2 for qty text |
| `m.unit_display` | qty+unit | |
| `m.nav_link` | sidebar items | emits `.nav-item` |
| `m.chart_card` | any chart | pass freshness |
| `m.top_list_card` | ranked lists | |
| `m.delta_pill` | deltas | switch internals to F-5 |
| `m.insight_card` | insight lists | severity: ok/warn/danger |
| `m.alert_list_card` | alert lists | |
| `tag_pills` / `storage_pill` / `category_pill` / `role_pill` (ingredient_tags.html) | pills | consolidate under status_pill visually |
| `category_picker` / `tag_picker` (tags.html) | form pickers | |
| `week_grid` / `month_grid` (calendar.html) | calendar | |
| `confirm_modal` (confirm_modal.html) + `SaskiaConfirmModal.show()` JS | destructive confirms | MANDATE (H-track) |
| `saskia-combo` (JS) | selects | zero-native-select invariant |
| `customer_picker` (_customer_picker.html) | client search | reuse on pedidos-nuevo |

## 3.2 New atoms to BUILD (Phase 0 — before any page work)
| ID | Macro | Signature | Why it exists / what it kills |
|----|-------|-----------|-------------------------------|
| A-1 | `metric_card` | `metric_card(label, value, sub=None, delta=None, delta_prior=None, target=None, target_label=None, compact=False, tooltip=None)` | one KPI card everywhere; value already formatted (pass through F-*); delta → m.delta_pill; target → 40px progress bar; tooltip → title attr (S-41: "—" explained) |
| A-2 | `kpi_strip` | `kpi_strip(cards=[...])` loop wrapper | responsive 4→2→1 grid; kills 8 hand-rolled KPI rows |
| A-3 | `status_pill` | `status_pill(text, sev)` sev∈ok/info/warn/danger/neutral | kills 6 badge dialects (badge-ok/-warn/-danger/-info, sev-pill critico/aviso, tier chips) |
| A-4 | `empty_state` | `empty_state(icon, title, hint=None, cta_href=None, cta_label=None, compact=False)` | 8 empty-state dialects; compact=48px for in-card |
| A-5 | `entity_link` | `entity_link(obj, href, name=None)` | F-6 guard + link (S-22/S-29) |
| A-6 | `page_header` | `page_header(title, desc=None, crumbs=None, actions=None)` | H1 + description + breadcrumb (A-7) + right actions; standardizes every page top |
| A-7 | `breadcrumb` | data-driven from NAV_TABLE (§5) | Spanish crumbs everywhere (S-13/26) |
| A-8 | `filter_toolbar` | `filter_toolbar(items=[{type:search/select/date…}], action=path, applied=…)` | standardized toolbar; rolls out to 10 lists (S-30) |
| A-9 | `data_table` (wrapper) | `data_table(headers, rows_markup, caption, density, sticky=True)` | sticky head, density classes, numeric alignment contract; pages still write `<td>` loops (keeps flexibility, kills boilerplate) |
| A-10 | `row_actions` | `row_actions(actions=[{label,href,icon,sev,confirm?}])` | ≤2 visible + ⋮ menu for rest (kills 3-button stacked rows) |
| A-11 | `drawer_open` / drawer markup + JS | `drawer(id, title, body_markup)` + `SaskiaDrawer.open(id)` | slide-over for Ajustar/anular/quick-edit (S-drawer) |
| A-12 | `tooltip` attr helper | `tooltip(text)` → `title=… data-tip` | first 10 uses (S-35) |
| A-13 | `stepper` | `stepper(steps, current)` | wizards |
| A-14 | `alert_row` | `alert_row(sev, text, action_href, action_label)` | the severity row inside alert_rail |
| A-15 | `heatmap` | `heatmap(matrix, row_labels, col_labels, fmt)` | day×hour demand (S-38) |
| A-16 | `timer_chip` | `timer_chip(started_at)` | KDS elapsed, color thresholds via CSS | 

CSS: each atom ships with its classes in `app-shell.css` (or a new `app-components.css`) using ONLY tokens. JS (drawer, stepper, row_actions menu, timer) in one `app-components.js`, no frameworks.

# 4. MOLECULES (composed per page-type — the 4 layout templates as Jinja blocks)

| ID | Molecule | Composition | Pages |
|----|----------|-------------|-------|
| M-1 | DATA_GRID page | page_header → kpi_strip → filter_toolbar → data_table → pagination | productos, recetas, inventario, clientes, proveedores, equipamiento, ventas-historial, pedidos, riesgos, auditoría, bank |
| M-2 | ASYM_EDITOR page | page_header(entity+actions) → grid 60/40: form cards | sticky summary rail (metric_cards) | productos-editar, receta-editar (escandallo rail), inventario-editar, cliente-editar, proveedor forms, pedidos-nuevo (cart rail) |
| M-3 | DASHBOARD page | page_header(period) → kpi_strip → band 65/35 (insight cards / alert_rail) → detail grids | inicio, analisis, dashboard-mensual, riesgos-matrix |
| M-4 | WIZARD page | page_header → stepper → centered 800px step forms → sticky footer | inventario-nuevo, excel-importar, supplier-nuevo |
| M-5 | POS split | left: category chips + quick-sell grid + scan field; right: sticky ticket (lines, totals, payment, COBRAR) | /ventas |
| M-6 | KDS board | 3-4 kanban columns of pedido cards (timer_chip, checklist, notes) | /pedidos/board |

Implementation: `{% extends %}` base + named blocks per molecule region, OR importable "skeleton" macros that take `{% call %}` blocks. Decision: **skeleton macros with call blocks** (base.html already branches login/logged-in; skeletons stay composable without template-inheritance diamond problems).

# 5. SINGLE SOURCES OF TRUTH (SSOT tables in Python)

| ID | Table | Drives | Format |
|----|-------|--------|--------|
| SS-1 | `NAV_TABLE` | sidebar groups/items, breadcrumb defaults, Nuevo menu, ⌘K palette, guia TOC | route → {label, group, icon, parent} |
| SS-2 | `CRUMB_OVERRIDES` | entity crumbs ("Cliente detalle" cases) | route → [section, sub, entity_slot] |
| SS-3 | `STATUS_MAP` | status_pill texts+sevs for every enum (pedido, loyalty, risk, bank cat, channel, role) | enum → (label_es, sev) |
| SS-4 | `FILTER_SPECS` (optional later) | filter_toolbar defaults per page | page → fields |

Location: `app/rms/nav.py` (new). One edit updates nav + crumbs + menu + search + guia. Tests assert consistency (W-0211).

# 6. FORMATTER/ATOM → WORK-ITEM MAPPING (traceability)

- F-1…F-7 ← B5 (W-0216…2220) + tests W-037 etc.
- A-1…A-16 ← A2 (W-0031…0070)
- M-1…M-6 ← C track blocks (per page 6-8 items are molecule applications)
- SS-1…SS-4 ← D-track (W-0406…0417)
- Each atom's rollout to a page = the page's E-track items.
- NO E-track page item may start before its atoms are merged (dependency rule enforced by phase order).

# 7. REUSE-FIRST CHECKLIST (run per PR)

1. Did I use F-* for every number/date/name? 
2. Did I use status_pill instead of a raw badge class?
3. Is my KPI row `kpi_strip(metric_card)`?
4. Is my empty state `empty_state`?
5. Is my table inside `data_table` + `row_actions`?
6. Crumb from NAV_TABLE? Header from `page_header`?
7. Destructive → confirm_modal? Disabled → tooltip reason? Async → skeleton/error?
8. Zero inline styles? Zero new emoji? Zero English strings?
9. Page-objects updated if selectors moved (browser layer)?
10. Smoke test + route-manifest entry exists?

# 8. WHAT EXISTS TODAY AND MUST NOT BE REBUILT (avoid duplication)

- money/qty display (macros), combos (saskia-combo), confirm modal + reason field, calendar grids, tag/category pickers, customer picker, chart_card + freshness, delta_pill, insight cards, sidebar/topbar shell (app-shell.css), dark theme via tokens, ⌘K search modal (JS exists), Nuevo dropdown (JS exists), pagination pattern, quick-sell grid (ventas), escandallo live-calc JS (receta form), tabs JS (pedidos), shoot-all-pages + zip pipeline, Playwright page-object layer, factories/flows test lib, route-manifest, prod deploy flow (tag :prod + update --force).
- Every redesign PR that touches these EXTENDS them; none forks them.

# 9. BUILD ORDER (atomic PR sequence for Phase 0)

1. `app/rms/nav.py` SS-1…SS-3 (+ tests) — everything reads it
2. F-1…F-7 formatters (+ property tests)
3. A-6 page_header + A-7 breadcrumb (+ rollout to 2 pilot pages: inventario, clientes)
4. A-1 metric_card + A-2 kpi_strip (+ swap inventario/clientes KPI rows — visual diff via screenshots)
5. A-3 status_pill + SS-3 (+ swap pedidos/clientes badges)
6. A-4 empty_state (+ swap 5 pages)
7. A-8 filter_toolbar (+ swap clientes → pilot complete: page is 100% primitives)
8. A-9 data_table + A-10 row_actions (inventario pilot)
9. A-11 drawer + JS; A-12 tooltip; A-14 alert_row (+ extract inicio alert_rail → M-3 use)
10. A-13 stepper, A-15 heatmap, A-16 timer_chip (needed by F-track pages later; build when first consumed)
11. Utility CSS classes pass (kills inline styles) + lint checks W-0029/0030
→ THEN C-track rollouts proceed page-by-page with the pilot as template.
