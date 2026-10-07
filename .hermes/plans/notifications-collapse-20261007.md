# Notifications collapse + ingredients scroll — 2026-10-07

Operator feedback on the /produccion day view:
1. The notification cluster (KPI cards, pedidos pendientes, ingredientes
   bajos + sustitutos, meta diaria, HACCP, baja confianza, ayer hiciste)
   takes ~30% of the viewport on every load. Wrap each card in
   `<details>` so it collapses by default and the operator opens only
   what it cares about.
2. The "Ingredientes necesarios" table (50 rows, embedded in
   produccion.html) pushes everything below the fold. Apply the
   produccion-table pattern: sticky thead, max-height scroll container,
   sort_th headers, severity filter chips.

## Scope

### File 1: app/templates/produccion.html

Wrap each of these top-level notification cards in `<details>` with a
summary that shows count + status (collapsed by default):
- L234 — pedidos pendientes para hoy
- L267 — ingredientes bajos + sustitutos
- L327 — meta diaria / real
- L348 — HACCP latest reading
- L370 — HACCP missing readings
- L550 — baja confianza (low confidence summary)
- L582 — ayer hiciste snapshot

Wrap the "Ingredientes necesarios" table in `.ingredients-table-scroll`
with `max-height` + sticky thead + sort_th. Add severity filter chips
(Falta / Justo / Suficiente) above the table.

### File 2: app/static/app-improvements.css

Add `.notification-collapse` style for the details/summary card layout.
Add `.ingredients-table-scroll` with sticky thead + scroll behavior.
Reuse existing `.production-table-scroll` patterns.

### File 3: tests/test_produccion_polish.py

Add tests:
- `TestNotificationsCollapsedByDefault` — each notification block must
  be inside a `<details>` so it starts collapsed.
- `TestIngredientsTableScrollable` — sticky thead + max-height +
  overflow-y:auto.
- `TestIngredientsTableSortable` — uses m.sort_th for headers.

## Decisions

- Collapse by default for ALL notification cards. Operator can
  expand the few they need. This saves ~600px (top fold) on every load.
- "Pedidos pendientes" detail list is collapsed by default too —
  the COUNT in the summary line is enough at-a-glance; the operator
  opens it only if they need to act.
- Ingredients table gets max-height: 60vh with sticky thead (same as
  production table).
- Filter chips: Falta (default ON) / Justo / Suficiente. Operator
  sees only the urgent items first; can flip to "all" to see stock
  surplus.

## Risks

- EmptyState lines 205–211 must NOT be wrapped — it's an empty-state
  message, not a notification. Only wrap top-of-page notification
  cards (the 7 listed above).
- The "cal-box" details at line 413 stays as-is (already collapsed).
- The "shift_saved" success message at L423 must NOT be collapsed —
  it's a confirmation of an action the operator took.
- Preserve keyboard accessibility: `<details>` works with keyboard.