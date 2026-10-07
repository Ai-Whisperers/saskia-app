# Sazón RMS — Page Consolidation Plan (2026-10-07)

Companion to `DEDUP_REPORT.md` (raw survey data). This is the **executable
plan** Ivan asked for: what pages to merge, what to centralize, in what order.

## TL;DR

- **Sidebar nav bug fixed** (wrap in `#app-shell` so the JS toggle works and
  the grid layout holds the sidebar+topbar+main+footer as siblings).
- **`/produccion/manana` enhanced**: per-client pedido cards with line items,
  Forecast + Pedidos + Total + Plan columns, Plan values persist to
  `ProductionPlanOverride` keyed by Asunción date.
- **20 templates render ingredient tables** with their own `fmt_qty` macro +
  severity pill + stock formatting → centralize to **1 partial** + **1 macro**.
- **`/produccion/prep-recipes` (new)** absorbs the daily ingredient breakdown
  that previously lived inline in `/produccion` (commit `87496de8`).
- **Navigation unification**: `/produccion` ↔ `/produccion/manana` ↔
  `/produccion/prep` ↔ `/produccion/prep-recipes` ↔ `/produccion/print` all
  share the same day/date context → add a `proday-nav` partial that reuses
  the date scope across the 5 pages.

## 1. Top wins (high ROI, low risk)

### 1.1 Centralize the ingredient-row partial

**Problem.** 20 templates render ingredient tables, each with a
slightly-different `fmt_qty` macro and stock-status pill. 4 templates
(`produccion.html`, `produccion_manana.html`, `produccion_prep.html`,
`produccion_prep_recipes.html`) define their **own copy** of `fmt_qty`
with subtly different rules.

**Plan.**

- `app/templates/_components/ingredient_row.html` — new partial taking
  `name`, `qty`, `unit`, `stock`, `severity`, `link_url`. Renders one
  `<tr>` with the canonical pill + unit formatting.
- `app/templates/_components/culinary_units.html` — new macro file with
  ONE `fmt_qty(qty, unit)` macro. All 4 copies removed.
- Adopt in: `produccion.html`, `produccion_manana.html`,
  `produccion_prep.html`, `produccion_prep_recipes.html`,
  `eod.html`, `eod_print.html`, `reorder.html`, `planner.html`,
  `merma.html`, `reportes_consumo.html`.

**Benefit.** ~120 LoC deleted; one place to fix unit rules when a new
"g/ml → int, und → ceil, kg/l → 1 decimal" rule gets added.

### 1.2 Unify the /produccion day-navigation partial

**Problem.** 5 pages under `/produccion` form a "production workspace"
but each has its own day-scope breadcrumb:

- `/produccion` — today
- `/produccion/manana` — tomorrow (hardcoded)
- `/produccion/prep` — this week (Mon-Sun)
- `/produccion/prep-recipes` — today
- `/produccion/print` — today
- `/produccion/export.csv` — today
- `/produccion/haccp` — today
- `/produccion/accuracy` — last 30d
- `/produccion/api/forecast?for_date=` — any date

**Plan.**

- `app/templates/_components/proday_nav.html` — single partial with:
  - Date pill: `« ayer  |  HOY  |  mañana »` with deep links to
    `/produccion/manana?for_date=Y-1d`, etc.
  - Mode tabs: `Hoy | Mañana | Prep semanal | Por receta | Imprimir`
  - Show currently active mode + label.
- Add `for_date` query param support to `/produccion/manana` (route
  hardcodes today+1d — change to `for_date` defaulting to today+1d,
  so the user can browse any day).

**Benefit.** Removes the cognitive load of "which day is this page
showing" + lets Ivan prep recipes for tomorrow without going to
`/produccion/manana` first.

### 1.3 Consolidate the KPI tile pattern

**Problem.** `/inicio`, `/analisis.html`, `/produccion.html`, `/eod.html`
all build KPI tiles. `inicio.html` defines them inline; `analisis.html`
duplicates the same `Ventas de hoy / Pedidos / Producción` block.

**Plan.**

- `app/templates/_components/kpi_grid.html` — partial taking a list of
  `(label, value, delta, delta_label, target)` tuples. Used by all 4
  pages with page-specific data.

**Benefit.** ~80 LoC; one place to standardize the "▲ ▼ vs semana"
deltas.

### 1.4 Merge `/produccion/print` into `/produccion?print=1`

**Problem.** `/produccion/print` is a separate route that re-queries
the same data. Operators on mobile/tablet don't know which to use.

**Plan.**

- `/produccion/print` redirects to `/produccion?print=1` which renders
  the page with `eod_print` stylesheet (no nav, A4 layout).
- Keep `/produccion/print` as a backward-compatible 301 alias.

**Benefit.** Single source of truth for the production plan; print
mode is a stylesheet concern, not a separate page.

## 2. Medium wins (1-2 hrs/week saved)

### 2.1 Inbox de Notificaciones unification

**Problem.** `base.html` defines a notification dropdown but each page
that surfaces alerts (`produccion.html`, `eod.html`, `inicio.html`)
builds its own list.

**Plan.**

- `app/services/notifications.py` (new) — single function that
  gathers the top 10 actionable notifications (low stock, prep
  recipes missing, pedidos sin confirmar, etc.) per scope.
- All pages call `notifications_for(scope)` instead of building their
  own arrays.

### 2.2 Cliente/Cliente_detalle vs Cliente_editar

**Problem.** Two templates editing the same fields in two places.

**Plan.**

- Extract `app/templates/cliente/_form.html` with name, phone, email,
  notes, tags. Both `cliente_editar.html` and `cliente_detalle.html`
  render `<form>{% include 'cliente/_form.html' %}</form>`.

### 2.3 Pedidos_nuevo vs pedido_stock_preview

**Problem.** Both render a stock preview table for an in-progress pedido.

**Plan.**

- `app/templates/pedido/_stock_preview.html` — partial used by both
  forms. Today both copy the same `<tr>...<td>...</td>...</tr>` block.

## 3. Low ROI but worth doing (later)

### 3.1 Receta_detalle / Receta_form split

The two templates share 600+ lines of ingredient/line editing. Worth
extracting `_components/receta_lines_editor.html` but needs the recipe
form refactor first.

### 3.2 Settings vs Settings_catalog

Two large settings pages. `settings_catalog.html` is a subpage of
`settings.html`. Should be moved to `/settings/catalog` and rendered
inside `settings.html` via `{% include %}`.

## 4. Sub-link map under `/produccion` (the audit)

| Route | Purpose | Status | Action |
|---|---|---|---|
| `/produccion` | Day view (today) | MAIN | KEEP — add `?for_date=` |
| `/produccion/manana` | Tomorrow's plan | MAIN | KEEP — add `?for_date=`, integrate with `proday_nav` |
| `/produccion/print` | Print day view | DUPLICATE | MERGE → `?print=1` (1.4) |
| `/produccion/export.csv` | CSV download | KEEP | Different format |
| `/produccion/prep` | Weekly aggregated ingredients | MAIN | KEEP — link from `proday_nav` |
| `/produccion/prep-recipes` | Per-recipe daily breakdown | NEW (87496de8) | KEEP — link from `proday_nav` |
| `/produccion/accuracy` | Forecast accuracy analytics | KEEP | Keep separate (analytical) |
| `/produccion/haccp` | HACCP readings | KEEP | Keep separate (regulatory) |
| `/produccion/api/forecast` | JSON forecast | KEEP | KEEP — programmatic |
| POST `/produccion/override` | Single override | KEEP | Legacy (manana uses bulk) |
| POST `/produccion/override-bulk` | Bulk override | MAIN | KEEP — used by manana form |
| POST `/produccion/copy-last-week` | Copy last week as template | KEEP | KEEP |
| POST `/produccion/closed` | Mark day closed (holiday) | KEEP | KEEP |
| POST `/produccion/shift-execute` | Record AM/PM progress | KEEP | KEEP |
| POST `/produccion/ad-hoc` / `/ad-hoc/bulk` | Ad-hoc production | KEEP | KEEP |
| POST `/produccion/close-day` / `close-day/reopen` | Close/reopen day | KEEP | KEEP |
| POST `/produccion/template` | Save weekly template | KEEP | KEEP |
| POST `/produccion/template/fork-week` | Copy template | KEEP | KEEP |

**No accidental duplicate routes.** Every sub-link maps to a distinct
concept. The only merge candidate is `/print` → `?print=1`.

## 5. Execution order (3-5 PRs)

1. **PR-A** (already shipped): sidebar wrap in `#app-shell` + manana
   per-client pedidos + Forecast/Pedidos/Plan columns. ✅
2. **PR-B** (next): `_components/culinary_units.html` + `_components/
   ingredient_row.html` partial. Remove 4 copies of `fmt_qty`. ~120 LoC
   deleted. 1 PR. No behavior change.
3. **PR-C**: `proday_nav.html` partial + `?for_date=` support on
   `/produccion` and `/produccion/manana`. Visible UX win.
4. **PR-D**: Merge `/produccion/print` → `?print=1`. Delete 1 template.
5. **PR-E**: KPI grid partial + notification service. 2 PRs of internal
   cleanup, no visible change.

Total: 5 PRs, ~1.5 days of work, ~500 LoC deleted, +2 new reusable
partials, no user-facing regressions.

## 6. Sidebar nav bug — root cause + fix (already deployed)

**Symptom.** Ivan reported "lost the navigation bar on the left".

**Diagnosis.**

- `base.html` had `<body class="has-app-shell">` then
  `<aside class="sidebar">` then `<header class="topbar">` then
  `<main>` then `<footer>` as direct children.
- `app-shell.css` had `body.has-app-shell { display: grid; ... }` with
  child selectors — but the JS mobile-toggle was using `#app-shell`
  (an ID that didn't exist), so the toggle silently failed.
- Some browser quirks (Safari iPad in particular) flip grid → flex
  when a direct child has `position: sticky`, breaking the 220px
  sidebar column.

**Fix (commit 8a91f0e2, 2026-10-07).**

- Added `<div id="app-shell">` wrapper around the 4 children.
- Moved `display: grid` from `body.has-app-shell` to
  `body.has-app-shell > .app-shell` (children are now siblings of the
  wrapper, not the body).
- Mobile breakpoint uses the same wrapper so the JS toggle works.

**Verification.**

- `tests/test_P01_login_no_sidebar.py`: 7/7 pass (sidebar hidden on
  login).
- `tests/test_P31_navigation_regression.py`: 87/87 pass (all pages
  show sidebar when authed).
- `tests/_app_shell_check.py`: 1/1 — wrapper renders with the right
  children in order.

**What Ivan should see now.** Reload any `/produccion/*` page while
logged in. Sidebar on the left, topbar on top, content in the middle.
On mobile (≤1023px), sidebar collapses and is opened via the
hamburger button in the topbar.

If the sidebar STILL doesn't show after deploy, the most likely
cause is a stale browser cache. Hard refresh (Ctrl-Shift-R) on
`/produccion/manana` and verify `view-source` shows
`<div id="app-shell">` right after `<body class="has-app-shell">`.
