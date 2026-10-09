# Produccion day-view table overhaul (2026-10-07)

Operator feedback on `/produccion` (43 rows):
- max 20 rows visible at once (user-settable via `?rows=` or cookie `prod_rows`)
- rows should have less height (denser padding)
- order by any column up/down
- columns should always be visible when scrolling (sticky thead)
- scrolling the table card vertically (not the whole page) so the header
  and section context stay put
- filter chips above the table (the project's standard place)

## Constraints

- Follow the existing `sort_th` macro pattern in `app/templates/_components/macros.html`
  (sortable header link with ▲▼ arrow + dir toggle + preserves query params).
- Default page size: 20. Cookie override `prod_rows`. URL override `?rows=N`.
  Allowed values: 10, 15, 20, 30, 50, 100. Anything else → 20.
- Sort keys (white-list to prevent crashes):
  - `product` (product_name asc default)
  - `difficulty` (recipe_difficulty asc)
  - `demand` (qty_demand_total desc)
  - `meta` (qty_to_produce desc)
  - `pedidos` (pending_pedido_qty desc)
  - `lote` (qty_to_produce + pedidos desc) — DEFAULT
  - `hecho` (completed_qty desc)
  - `sobrante` (batch_surplus_qty desc)
  - `closure` (closure_status asc)
  - Ad-hoc rows always last (regardless of sort).
- Sticky thead clears the topbar (`top: var(--topbar-height, 48px)`).
- Densify rows: `td` padding 0.35rem 0.5rem (down from the .table default
  ~0.75rem). Row height ~32px, so 20 rows + thead ≈ 700px → fits in viewport
  with the banner + footer above/below.
- Filter chips (above table, alongside the existing difficulty tabs):
  - Allergen chips (gluten / dairy / eggs / nuts) — multi-select toggle.
  - Source chips (Historial / Receta / Override / Horneado extra).
  - "Con pedidos" / "Sin pedidos" toggle.
  - "Hecho > 0" toggle.
  - "Sobrante alto" (batch_surplus_pct >= 30) toggle.
- All filters combine as AND; active filters surface as small chips with X
  to clear. Counter "X / Y productos" reflects active filters.
- All filter state lives in URL query params for deep-link / share-ability.

## Files

- `app/routers/produccion/_full.py` — accept `sort`, `dir`, `rows`, `filter_*`
  query params; sort and slice `primary_rows` + `zero_demand_rows` accordingly.
- `app/templates/produccion.html` — use `sort_th` for headers, add sticky
  wrapper, add filter toolbar, update row loop to honor sorted/sliced rows.
- `app/templates/_components/macros.html` — extend `sort_th` if needed for
  right-aligned numeric columns (the existing macro emits a link that flexes
  align-self; the produccion <th class="num"> overrides).
- `app/static/app-components.css` — `.production-table-scroll.is-scrollable`
  with `max-height: calc(100vh - var(--topbar-height) - 240px)`; sticky thead;
  `.production-row td` denser padding; filter-chip styles.
- `tests/test_produccion_polish.py` — append ~10 tests.

## Tests

1. `test_produccion_sort_default_by_lotte` — `/produccion` with no `?sort=`
   sorts by lote_final desc (highest first, ad-hoc at bottom).
2. `test_produccion_sort_product_asc` — `?sort=product&dir=asc` → alphabetical
   by product_name.
3. `test_produccion_sort_unknown_key_falls_back_to_default` — `?sort=hacker`
   does not 500; falls back to `lote desc`.
4. `test_produccion_rows_default_is_20` — without `?rows=` first 20 of
   primary_rows rendered, rest available via... no pagination (user said
   "max 20" not "paginated 20"). Rows beyond 20 = `hidden` in HTML, "Mostrar
   todos" link toggles `?rows=100`.
5. `test_produccion_rows_query_param` — `?rows=10` shows 10, `?rows=999`
   clamps to 100.
6. `test_produccion_sticky_thead_css` — CSS contains
   `.production-table-scroll thead th { position: sticky; top: var(--topbar-height, 48px); }`.
7. `test_produccion_dense_rows_css` — CSS for `.production-row td` denser
   than `.table td` default (≤0.5rem vertical padding).
8. `test_produccion_filter_toolbar` — toolbar above table contains
   `data-filter-group="allergen"` chips and a clear-all control.
9. `test_produccion_filter_allergen_persists_in_query` — `?filter_allergen=gluten`
   includes rows with that allergen only.
10. `test_produccion_sort_header_uses_macro` — at least one `<th>` uses
    `sort_th(...)` macro (verifiable by aria-label="Ordenar por …").