# Sazon/Saskia — Full Page Text Inventory

**Generated:** 2026-10-07
**Scope:** 127 HTML templates across 5 functional sections
**Audit goal:** Translation readiness + UX audit of every page in the Sazon/Saskia RMS

---

## Index by section

| Section | Pages | File | Lines | Size |
|---|---|---|---|---|
| **A** — Sales / POS / Cash / Customers / Credit / Fiado | 22 | [A-sales-customers.md](./inventory/A-sales-customers.md) | 1,478 | 60KB |
| **B** — Products / Recipes / Inventory / Mermas / Pricing | 14 | [B-products-recipes-inventory.md](./inventory/B-products-recipes-inventory.md) | 480 | 17KB |
| **C** — Production / Pedidos / Menus / Suppliers / Delivery / Shopping | 26 | [C-production-suppliers-supply.md](./inventory/C-production-suppliers-supply.md) | 1,442 | 54KB |
| **D** — Reports / Analytics / Insights / Dashboard / Benchmarks / Cotizador | 34 | [D-reports-analytics-insights.md](./inventory/D-reports-analytics-insights.md) | 1,399 | 43KB |
| **E** — Admin / Settings / EOD / Auditoria / Excel / Ops / Auth / Errors / Help | 23 | [E-admin-ops-system.md](./inventory/E-admin-ops-system.md) | 1,878 | 65KB |
| **TOTAL** | **119** |  | **6,677** | **240KB** |

*Note: 8 templates are missing from the count because they were not located in the audit pass — see "Gaps" below.*

---

## How to use this inventory

Each section file follows the same schema:

- **Per page (##)**: Identity (URL, title, persona), Structure (headings, tabs, breadcrumb), All visible text (grouped by element type), Displayed data (column semantics table), Tooltips (table), UX/copy audit flags.
- **End of section**: "Section-wide issues" — cross-page patterns and recurring problems.

For **translation readiness**, search each file for backtick-wrapped strings (`like this`) — these are verbatim user-facing copy.

For **UX audit**, each section ends with three tables:
- **Cross-page consistency** — repeated patterns or inconsistencies
- **Copy issues** — page-specific problems
- **Spanish-language quality** — grammar, loan words, regional terms
- **Accessibility gaps** — aria-label, sr-only, color-only signals
- **What's missing** — implicit content (charts, JS state, drill-downs)

---

## Cross-section patterns

### Empty states

Almost every page uses the `ui.empty_state(title, icon, hint, cta_href, cta_label)` macro. Patterns observed:
- Always includes an icon name (e.g. `icon-sale`, `icon-report`).
- Often includes a CTA — operator-friendly.
- Examples:
  - `Sin datos este mes todavía — Registrá tu primera venta o cargá el catálogo para ver los KPIs en vivo.`
  - `Todavía no hay evidencia cargada — usá el seed del research repo o importá un CSV.`
  - `Stock cubre la producción prevista. 🎉` (success state with emoji)
  - `Ningún producto cruza el objetivo. ✅`

### Period filters

Many reports and insights use a consistent set of time-period options:
- `Últimos 7 días`
- `Últimos 30 días`
- `Últimos 60 días`
- `Últimos 90 días`
- `Últimos 180 días`
- `Último año`

Filter labels are usually `Desde` and `Hasta` with a `Ver` or `Filtrar` submit. Some pages also offer day-quick-filters (e.g. `7d`, `14d`, `30d`).

### Severity pills (sev-pill)

Three-tier system:
- `Crítico` (red) — needs immediate action
- `Aviso` (yellow) — heads up
- `saludable` (green) — all good

### Margin % badges

Three-tier system based on margin percentage:
- ≥50%: `badge-ok` (green)
- 25–49%: `badge-warn` (yellow)
- <25%: `badge-danger` (red)

### Tooltip attributes

Three attribute patterns used interchangeably:
- `title="..."`
- `data-bs-title="..."`
- `data-tooltip="..."` (some pages, sparingly)

### Bilingual conventions

- Currency: `Gs.` (guaraníes) is the standard; one page (`reportes_mermas_cost`) uses `₲` Unicode symbol — **inconsistent**.
- Date formats: Mostly `DD/MM/YYYY` in tables; some `YYYY-MM-DD` in subtitles.
- Times: `HH:00` in heatmaps and hourly reports.
- Decimal separator: `,` (Spanish locale).

### English loan words

These appear throughout but are not translated:
- `Revenue` (used in: reportes_top_productos, insight_affinities indirectly)
- `AOV` (Average Order Value) — but **explained inline** in reportes_valor_pedido.
- `COGS` (Cost of Goods Sold) — reportes_diario uses this. **Should be** `Costo de Mercadería Vendida`.
- `Prime Cost` — reportes_cierre_mensual uses this.
- `Food cost` — insight_price_impact.
- `KPI` — used in dashboard subtitle (`KPIs en vivo · datos del local`).
- `Forecast`, `Batches`, `Trend`, `Accuracy` — used in insights.
- `Insight` — in section nav and page titles.

### Spanish-language patterns

- **Imperative for actions**: `Registrar`, `Cargá`, `Cociná`, `Reponer`, `Editar`, `Ver`, `Cancelar`. Mixes `tú` (Cargá, Cociná) and `vos` (Cargá, Cociná) — informal Paraguayan register.
- **Operator-friendly tone**: `donde se va tu plata`, `Mirá acá`, `sugerido por ventas`.
- **Formal terms**: tax / fiscal sections use proper Paraguayan Spanish (`Gravado`, `Base imponible`, `Boleta Resimple`, `Factura`, `RUC`).

### Empty state vs success state

- Empty states: `Sin datos...`, `No hay...`, `Todavía no hay...`
- Success states: `Stock cubre la producción prevista. 🎉`, `Ningún producto cruza el objetivo. ✅`

### Section-wide issues

| Issue | Sections | Notes |
|---|---|---|
| **English loan words (KPI, AOV, COGS, etc.)** | All | Operator-friendly but untranslated. |
| **`₲` vs `Gs.` currency symbol** | reportes_mermas_cost vs all others | Should unify to `Gs.`. |
| **Date format inconsistencies** | Some reports | `DD/MM/YYYY` vs `YYYY-MM-DD`. |
| **Mixed `tú` / `vos` register** | Throughout | Use a consistent one for tone. |
| **Period filter inconsistency** | Some pages have `<select>` with options, others have `<a href="?days=N">` link filters. | Standardize. |
| **Wide tables (10+ columns)** | reportes_libro_ventas (11 cols) | Consider printable view. |
| **Charts not in templates** | All BI pages | JS-rendered; missing from inventory. |

---

## Gaps / templates not located

The following templates were referenced in route maps but **not found** in the audit pass — they may have been renamed, removed, or never existed:

- `pedido_publico.html` — was supposed to be in Section C
- Several `insight_*` variants may have been consolidated

If you need these, please run a fresh route-map scan or check `app/routers/*.py` for current `@router.get` declarations.

---

## Recommendations

1. **Standardize currency display** — pick `Gs.` or `₲` and use everywhere.
2. **Replace `COGS`** with `CMV` (Costo de Mercadería Vendida) or full Spanish term.
3. **Standardize period filters** — use `<select>` consistently.
4. **Add `aria-label` to all tables** for screen readers.
5. **Document the empty_state macro** — it's a key UX pattern.
6. **Add chart label coverage** — currently JS-only.
7. **Use `Prom/día` consistently** — consider `Promedio diario`.
8. **Consider tooltip audit** — section A has 30+ tooltips; section B has fewer; may be under-documented.

---

*Generated by Sazon/Saskia text audit. For each individual page, see the linked section file.*
