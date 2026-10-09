# Tables overhaul (round 2) — 2026-10-07

Operator feedback (Ivan, after first overhaul shipped):
1. The produccion day-view table MUST allow loading **all** products, not hard-cap. Cap is per-page only. (Default 20, URL ?page=N. Hidden rows below the fold show "Mostrar 23 más".)
2. Apply the same smart-table pattern (sortable, sticky thead, filters, row-expansion, density) to:
   - `/produccion/prep` "Ingredientes necesarios" table
   - `/inventario` "Ingredientes" table
3. Critique every cell + header text and improve:
   - **Origen column**: replace `?` help-link with the actual confidence score (`67%` etc.), color-coded by band (green ≥70%, yellow 50-69%, red <50%). Move the "what is this?" tooltip into the column header.
   - **Sobrante column**: better color (current red looks alarmist for "we over-baked 11 muffins"). Use gray for tolerable (0-20%), amber for moderate (20-100%), orange (NOT red) for excessive (>100%). Add a tiny stacked-box icon so operators skim density without reading numbers.
   - **Headers**: shorter, plainer, less repetition.
   - **Color of text inside cells**: also tone down red usage.

## Decisions

- **Page-load pattern**: server-side pagination + "Mostrar todos los 43" link. URL-driven. ?page=N (?rows= now means per-page; ?show_all=1 bypasses).
- **Origen**: show the number, color by band, keep the `?` icon as a header-level helper (one tooltip explains all bands).
- **Sobrante**: graduated gray→amber→orange (never red); stacked-box icon (▪▪▪▫ etc.).
- **Color inside cells**: switch from `color: var(--color-danger)` to `--color-warning-soft` or `--color-text-muted`; reserve red strictly for "system error" / "you're missing money."

## Critique — current produccion day-view thead + cells

| Col | Header now | Better header | Why |
|---|---|---|---|
| 0 | `Listo` | (no header — checkbox only) | "Listo" implies "the row is complete"; rename label to `Hecho` for clarity. Header = aria-label only. |
| 1 | `Producto` | ✅ | OK |
| 2 | `Dificultad` | ✅ | OK (already added in v2) |
| 3 | `Demanda` | `Demanda` (with helper: "lo que se espera vender hoy") | Header is OK but operators keep asking "what does this number mean?" |
| 4 | `Lotes` | `Lotes a hornear` | "Lotes" alone is ambiguous: lote=batch but meta=meta. `Lotes a hornear` is clearer |
| 5 | `Pedidos` | `Pedidos confirmados` | `Pedidos` alone = any order; clarify these are CONFIRMED for today |
| 6 | `Lote final` | `Lote final` | OK but add helper "Meta + Pedidos" |
| 7 | `Hecho` | `Hecho` | OK |
| 8 | `Origen` | `Origen` (header has tooltip) | Drop the in-cell `?` help-link; put tooltip in header |
| 9 | `Receta` | `Receta` | OK |
| 10 | `Sobrante` | `Sobrante est.` (with helper "unidades extra que probablemente sobrarán") | Avoid `+11` ambiguity (is +11 good or bad?) |
| 11 | `Cierre` | `Cierre` | OK |

## Critique — current produccion_prep thead + cells

| Col | Header now | Better header | Why |
|---|---|---|---|
| 0 | `Ingrediente` | ✅ | OK |
| 1 | `Requerido` | `Necesario` | "Requerido" sounds like a request, not a need |
| 2 | `Stock actual` | `En stock` | Shorter, plainer |
| 3 | `A comprar` | `A reponer` | "Comprar" implies you always buy; "reponer" includes "ya tenés de otro lote" |
| 4 | `Estado` | `Estado` (chip) | OK but add helper "Falta = no alcanza; Justo = justo; Si = suficiente" |

## Critique — current inventario thead

Looks mature. Issue: "Estado" column header sits next to "Stock actual" without explaining. Add helper: "Estado = comparación stock vs. mínimo".

## Scope of code changes

- `app/routers/produccion/_full.py`: remove hard-cap, add ?page=, ?show_all=; remove `hidden_count` logic.
- `app/routers/inventory.py`: no change — already paginated at 50, supports ?page=.
- `app/routers/produccion/print_export.py`: add ?sort/?dir/?rows to `produccion_prep`.
- `app/templates/produccion.html`: replace `hidden_count` block with "Mostrar 20 más" + "Mostrar todos" buttons; replace `?` help-link with confidence score; update sobrante colors; rewrite headers.
- `app/templates/produccion_prep.html`: add sort_th + sticky + filter chips; new headers; colored to_buy.
- `app/templates/inventario.html`: tighten color of "A comprar" cell; upgrade Estado helper.
- `app/static/app-improvements.css`: add `.load-more` / `.load-all` button styles; add `.confidence-band--numeric` (numeric score in chip); add `.surplus-tier-*` color tiers; add sticky `prep-table`.

## Tests

Add to `test_produccion_polish.py`:
- `test_no_total_row_cap` — `?show_all=1` returns all rows, not just first 20.
- `test_page_param_loads_next_window` — `?page=2` returns rows 21..40.
- `test_origen_shows_score_not_help_link`
- `test_sobrante_uses_graduated_color`
- `test_prep_table_sticky_thead`
- `test_prep_table_sortable`
- `test_prep_filters`