# Produccion page — visual + UX fixes (2026-10-06)

User's directive: "fix all of them" — referring to 30 visual/UX issues
documented in the analysis of /produccion screenshot.

Grouped by priority. Tests in tests/test_produccion_polish.py.

## Critical (operator workflow blockers)

- [ ] C1. Right-edge overflow on products table — wrap `<table>` at
  produccion.html:654 in `overflow-x: auto` div, also for ingredientes
  table at line 1482. Currently LOTE FINAL + Hecho stepper + Sobrante
  + Cierre columns are clipped on viewport ≤1100px.
- [ ] C2. "Falta" badge on every ingredient — verify the badge
  logic distinguishes "no stock loaded" from "out of stock". The
  screenshot shows 30+ ingredients all `Falta` which is wrong if
  stock was seeded.
- [ ] C3. META vs batch_size number confusion — display the META
  big-number and the `8und` batch_size with clearly different
  visual hierarchy (big number is the BATCH COUNT, small grey text
  is the units-per-batch).

## Major UX

- [ ] M1. Hide "(deleted)" / "Producto eliminado" rows from active
  plan. If a product was soft-deleted but has completions, the row
  should not appear in the production table.
- [ ] M2. Collapse 0-demand products under a "Sin demanda reciente"
  toggle so they don't dominate the table.
- [ ] M3. Star rating legend — add tooltip + small legend in the
  difficulty filter area so ⭐ / ⭐⭐ / ⭐⭐⭐ are explained.
- [ ] M4. Visually separate the "X productos con baja confianza"
  banner from the "Ayer hiciste" banner below it (horizontal rule
  or distinct background).
- [ ] M5. Distinct icons for "+ Nuevo" vs "Columnas" toolbar button.
- [ ] M6. Single date-picker widget (replace 5 buttons with one).
- [ ] M7. Table pagination or "Saltar a categoría" nav for the
  45-row table.
- [ ] M8. "Ingredientes necesarios" table — make it horizontally
  scrollable, or condense the badges to a single Suficiente/Falta
  column with a "?" tooltip showing numbers.
- [ ] M9. Make the "Cómo se calcula" / "8 productos con baja
  confianza" hints collapsible (closed by default with a "?" toggle).

## Visual polish

- [ ] V1. "Cierre" column header is `9rem` but the button is
  `Cerrar turno` which doesn't fit. Wrap or shorten.
- [ ] V2. Status-pill BEM consistency — `ready` vs `confirmed` use
  different classes in the pedidos list. Standardize.
- [ ] V3. The "Marcar todos como hecho" button is solid orange
  (primary) but the more useful action is "+/- por fila". Swap
  the visual hierarchy.
- [ ] V4. Sidebar branding "Saskia RMS" vs footer "Sazón v1.0" —
  use one consistent brand.
- [ ] V5. "+ Sustitutos sugeridos (m..." button text is cut off —
  the wrap is breaking mid-word. Allow the button to wrap properly.
- [ ] V6. HACCP chip "heladera-ma[something]" cut off — add wrap.
- [ ] V7. "Horneado extra" description text cut off — add wrap.
- [ ] V8. The 30px gap between sidebar and content — remove or
  make intentional.
