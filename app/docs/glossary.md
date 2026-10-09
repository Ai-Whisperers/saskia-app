# Sazón — Terminology Glossary (SASKIA-310)

> **For agents and developers.** This is the canonical Spanish (Paraguayan voseo)
> terminology bank. When writing user-facing copy, use these terms. When
> reading code (variable names, comments), use the English equivalents.

This file is the **concept-level** glossary (one row per concept). The
**string-level** bank (button labels, error messages, etc.) lives in
[`copy-vos.md`](copy-vos.md). The two complement each other: glossary
= "what to call a *concept*", copy-vos = "how to phrase a *sentence*".

## Canonical terms

| Concept | Spanish (UI) | English (code) | Don't use in UI |
|---|---|---|---|
| Customer | `cliente` | `customer` | `comprador`, `consumidor` |
| Order (preorder / anticipado) | `pedido` | `pedido` / `order` | `orden`, `encargo` |
| Product | `producto` | `product` | `ítem`, `artículo` |
| Recipe | `receta` | `recipe` | `preparación` |
| Ingredient | `ingrediente` | `ingredient` | `insumo` (use sparingly) |
| Sale | `venta` | `sale` | `operación`, `transacción`, `ticket` |
| Stock level (the field) | `stock` | `stock` | `existencia` |
| Stock page (the screen) | `inventario` | `inventory` | — |
| Batch (production unit) | `tanda` | `batch` | `lote` (in production context) |
| Cancel (UI button) | `cancelar` | `cancel` | — |
| Anular (reverse a posted sale) | `anular` | `void` | `cancelar` (UI button only) |
| Save | `guardar` | `save` | `grabar` |
| Open | `abrir` | `open` | — |
| Close | `cerrar` | `close` | — |
| Money amount | `Gs. 729.167` | `int` (Gs.) | `₲`, `Gs ` (no period), `Gs` |
| Date | `31/10/2026` | `datetime` | `31-10-2026`, `10/31/2026` |
| Operator (user) | `operador` | `user` / `operator` | `usuario` (casual UI only) |
| Severity OK | `OK` | `severity="ok"` | `saludable` (loan) |
| Severity warning | `Aviso` | `severity="warn"` | `Advertencia` |
| Severity critical | `Crítico` | `severity="critical"` | `Crítica` |
| Forecast | `pronóstico` | `forecast` | `predicción` |
| COGS | `Costo de Mercadería Vendida` | `cogs` | `COGS` (in UI) |
| Revenue | `ingresos` | `revenue` | `Revenue` (in UI) |
| Manual override | `ajuste manual` | `override` | `Override` (in UI) |
| Status | `estado` | `status` | `Status` (in UI) |
| Owner | `responsable` | `owner` | `Owner` (in UI) |
| Endpoint | `ruta` | `endpoint` | `Endpoint` (in UI) |
| Counterparty | `contraparte` | `counterparty` | `Counterparty` (in UI) |
| Quantity (column header) | `Cantidad` | `quantity` | `Qty` (in headers) |
| Difference (column header) | `Diferencia` | `difference` | `Diff` (in headers) |
| Accuracy (column header) | `Precisión` | `accuracy` | `Accuracy` (in headers) |
| Loyalty program | `fidelización` | `loyalty` | `Loyalty` (in UI) |
| KPI | `Indicadores` | `kpi` | `KPI` (in subtitles) |
| Lead time | `tiempo de reposición` | `lead_time` | `Lead time` (in UI) |
| Login success | `login exitoso` | `login_success` | `Login OK` |
| Login failure | `login fallido` | `login_failure` | `Login FAIL` |
| Reorder rate | `tasa de reposición` | `reorder_rate` | `Reorder rate` |
| Δ (delta) | `Cambio` | `delta` | `Δ` (in column headers) |
| Wishlist (equipment) | `lista de deseos` | `wishlist` | — |
| EOD check | `cierre diario` | `eod` | `EOD` (in UI subtitles) |
| Merma (waste) | `merma` | `waste` | — |

## Currency rules

- **Display:** `Gs. 729.167` (period thousands separator, NO decimals)
- **Input:** `729167` (no separator, integer)
- **Negative:** `Gs. -1.500` (sign BEFORE `Gs.`)

The single source of truth is `app/templates/_components/atoms.html`'s
`m.gs()` / `m.gs_full()` macros. **Never write `Gs. {{ ... }}` raw** —
that pattern is locked by `scripts/check_currency_drift.sh` in CI.

## Date rules

- **Display:** `31/10/2026` (DD/MM/AAAA — Paraguayan year)
- **Input:** accept `DD/MM/AAAA` and `DD/MM/AA`
- **ISO in code:** `2026-10-31` (only in logs, never in UI)

## Register rules

- **Buttons:** infinitive (`Registrar`, `Ingresar`, `Guardar`)
- **Empty states / hints:** Paraguayan voseo (`Tocá`, `Cargá`, `Cociná`, `Hacé`)
- **NEVER** Argentine voseo (`Guardá` → use `Guardar`; `Decí` → use `Indicá`)
- **NEVER** formal `vosotros` (not used in PY)

## Out of style (do NOT translate literally)

- `Batches` → `Tandas` (don't use "Lotes" in production context)
- `Override` → `Ajuste manual`
- `Status` → `Estado`
- `Owner` → `Responsable`
- `Endpoint` → `Ruta`
- `Delta` → `Cambio`
- `Forecast` → `Pronóstico`

## Severity badges (canonical pill colors)

| Severity | Color token | Class |
|---|---|---|
| OK | `--color-ok` | `.badge-severity-ok` |
| Warn | `--color-warn` | `.badge-severity-warn` |
| Critical | `--color-danger` | `.badge-severity-critical` |

## See also

- [`copy-vos.md`](copy-vos.md) — the string-level UI copy bank (button labels, error messages, form labels). This glossary is the **concept-level** supplement; both are needed.
- [`docs/ux/copy-fix-list.md`](../../docs/ux/copy-fix-list.md) — every specific instance fixed by the SASKIA-301..308 hardening work.
- [`docs/ux/copy-ux-decisions.md`](../../docs/ux/copy-ux-decisions.md) — phase-by-phase audit decisions.
- [`scripts/check_currency_drift.sh`](../../scripts/check_currency_drift.sh) — CI gate for raw `Gs. {{ ... }}` violations.

## History

- **2026-10-07** (SASKIA-310): Created. Locks the 308-fix program against regression via `tests/test_terminology_consistency.py`.