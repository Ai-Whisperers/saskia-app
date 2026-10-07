# SASKIA-301: Standardize currency, register, severity labels (Phase 0)

**Date:** 2026-10-07
**Branch:** `feat/SASKIA-301-copy-globals`
**Epic / Story:** Sazon copy/UX hardening (Phase 0 of 10)
**Owner:** Iván (operator + reviewer), Hermes (impl)
**Estimate:** 4-6 hours
**Status:** ready
**Plan reference:** `docs/plans/2026-10-07-copy-ux-hardening-plan.md` (Phase 0)

---

## Problem

The Sazon UI has accumulated copy/UX inconsistencies that violate `app/docs/copy-vos.md`:

1. **Currency symbol drift** — `Gs.` (correct, per style guide) coexists with `₲` (Unicode guaraní) and bare `Gs` (no period) in 6+ templates.
2. **English band labels** — `Loyalty` is the only English H2 on the most-visited page (`inicio.html`).
3. **English loan words everywhere in BI** — `KPI`, `COGS`, `Revenue`, `Batches`, `Override`, `Forecast`, `Lotes`, `Lead time`, `Counterparty`, `Status`, `Owner`, `Endpoint`, `Diff`, `Qty`, `Accuracy`, `IP`, `Login OK/FAIL`, `Reorder rate`, `Δ`.
4. **Register drift** — Argentine voseo (`Guardá`, `Decí`) where Paraguayan voseo or infinitive should be used.
5. **Severity pill naming** — `saludable` (English loan, lowercase) where `OK` should be.
6. **Column header abbreviations** — `Gs.`, `₲`, `Gs`, `(Gs.)`, `(Gs)` used inconsistently.
7. **Redundant tooltips** — `aria-label="Cerrar"` on close buttons that already say "Cerrar" (defeats the purpose of a tooltip).
8. **Money/date format** — `25000` placeholders should be `25.000` (period thousands sep per `copy-vos.md`).

**Reference:** `docs/ux/copy-fix-list.md` (the 290+ item list) and `docs/ux/text-critique.md` (high-level critique).

## Why

- **Translation cost:** every new loan word costs translation time. Lock the canonical terms now.
- **Operator trust:** mixed English/Spanish in BI pages reads as "this is for engineers, not for me".
- **AGENTS.md compliance:** Hard Rule 22 says user-facing strings should follow `copy-vos.md`; we're failing that on the BI section.

## Tasks

### 0.1 Currency symbol (G.1) 🟠 P1
- [ ] Replace `₲` and bare `Gs` with `Gs.` everywhere
- [ ] Files: `reportes_mermas_cost.html`, `ops_status.html`, `suppliers_volatility.html`, `riesgos.html`
- [ ] `grep -E '[₲]|\bGs\b' app/templates/` returns 0 matches after fix

### 0.2 English band labels (G.2) 🟠 P1
- [ ] `Loyalty` → `Fidelización` on `inicio.html` line 87
- [ ] `grep 'Loyalty' app/templates/inicio.html` returns 0 matches after fix

### 0.3 English loan words (G.3) 🟠 P1
- [ ] `KPI` → `Indicadores` (inicio, dashboard)
- [ ] `COGS` → `Costo de Mercadería Vendida` (reportes_diario)
- [ ] `Revenue` → `Ingresos` (reportes_top_productos)
- [ ] `Batches` → `Tandas` (insight_demand)
- [ ] `Override` → `Ajuste manual` (produccion_manana, inventario_form)
- [ ] `Forecast` → `Pronóstico` (insight_demand, produccion_manana)
- [ ] `Lotes` → `Tandas` (cotizador, planner)
- [ ] `Lead time` → `Tiempo de reposición` (inventario_form)
- [ ] `Counterparty` → `Contraparte` (bank)
- [ ] `Status` → `Estado` (planner, suppliers, riesgos, etc.)
- [ ] `Owner` → `Responsable` (riesgos)
- [ ] `Endpoint` → `Ruta` (ops_status)
- [ ] `Diff` → `Diferencia` (caja, caja_z)
- [ ] `Qty` → `Cant.` (wishlist)
- [ ] `Accuracy` → `Precisión` (produccion_accuracy page title)
- [ ] `IP` → `Dirección IP` (auditoria_analytics)
- [ ] `Login OK/FAIL` → `Login exitoso/fallido` (auditoria_analytics)
- [ ] `Reorder rate` → `Tasa de reposición` (ops_status)
- [ ] `Δ` → `Cambio` (analisis, insight_margenes) — only in column headers
- [ ] Keep with tooltip explanation: `Prime Cost`, `AOV`

### 0.4 Register consistency (G.4) 🟠 P1
- [ ] Replace `Guardá` with `Guardar` in buttons (not empty states)
  - `produccion_manana.html` line 56: `Guardá plan de mañana` → `Guardar plan de mañana`
  - `produccion_manana.html` line 54: `aria-label="Guardá los ajustes..."` → `Guardar los ajustes...`
- [ ] Replace Argentine voseo `Decí` (produccion.html `Decí por qué abajo`) → `Indicá por qué abajo`
- [ ] `grep -E 'Guardá|Decí por qué' app/templates/*.html` returns 0 matches

### 0.5 Severity pill naming (G.7) 🟠 P1
- [ ] `saludable` → `OK` in `inicio.html` line 228
- [ ] `grep 'saludable' app/templates/` returns 0 matches

### 0.6 Column header abbreviations (G.8) 🟡 P2
- [ ] `25000` placeholder → `25.000` in `menus.html`
- [ ] `Precio (Gs)` → `Precio (Gs.)` in `menu_import_ocr.html`
- [ ] Audit other `(Gs)` and `Gs` (no period) usages

### 0.7 Redundant tooltips (G.5) 🟠 P1
- [ ] Remove `aria-label="Cerrar"` from close buttons where visible text already says "Cerrar"
- [ ] Affected templates: `dashboard.html`, `recetas.html`, `inventario.html`, `productos.html`, `users.html`, `receta_form.html`

### 0.8 Update CHANGELOG.md and copy-vos.md
- [ ] CHANGELOG: add entry under `[Unreleased]`
- [ ] copy-vos.md: add new canonical terms (`Fidelización`, `Ajuste manual`, `Indicadores`, `Moneda`, `Contraparte`, `Tasa de reposición`, `Dirección IP más frecuentes`, `Login exitoso/fallido`)

## Acceptance tests

Create files:

- `tests/test_SASKIA-301_currency_gs.py`:
  - `GET /reportes/mermas-cost` returns body containing `Gs.` and not containing `₲`
  - `GET /riesgos` returns body containing `Gs.` (not `Gs `)
  - `GET /ops/status` returns body containing `Gs.`
  - `GET /suppliers/volatility` returns body containing `Gs.`

- `tests/test_SASKIA-301_loyalty_label.py`:
  - `GET /inicio` body contains `Fidelización` and does NOT contain `Loyalty`

- `tests/test_SASKIA-301_loan_words.py`:
  - For each replaced word, body does not contain the English form (e.g. `test_top_productos_no_revenue`)
  - `test_diario_no_cogs`
  - `test_demand_no_batches`
  - `test_cotizador_no_lotes`
  - `test_inventario_no_lead_time`
  - `test_bank_no_counterparty`
  - `test_riesgos_no_status` (and the column)
  - `test_riesgos_no_owner`
  - `test_ops_no_endpoint`
  - `test_auditoria_no_login_ok_fail`

- `tests/test_SASKIA-301_register.py`:
  - `grep -E 'Guardá plan|Decí por qué' app/templates/*.html` returns 0 matches
  - `GET /produccion/manana` body contains `Guardar plan de mañana` (not `Guardá`)

- `tests/test_SASKIA-301_severity.py`:
  - `GET /inicio` body does NOT contain `saludable`
  - `GET /inicio` body contains `OK` (or whatever green-pill text we settle on)

- `tests/test_SASKIA-301_tooltips.py`:
  - For each affected close button, the `aria-label` either is absent OR adds context beyond the visible text
  - Spot-check: `GET /recetas` has no `<button aria-label="Cerrar" data-sazon-dismiss>Cerrar</button>`

- `tests/test_SASKIA-301_columns.py`:
  - `GET /reportes/top-productos` body contains `Ingresos` (not `Revenue`)
  - `GET /reportes/mermas-cost` body contains `Gs.` (not `₲`)
  - `GET /menus` body has placeholder `25.000`

## Acceptance

- [ ] All 8 test files pass
- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `make smoke` (or equivalent) passes
- [ ] CHANGELOG.md updated per AGENTS.md rule 35
- [ ] Manual: `uv run sazon serve` and visit each page; verify the changes are visible
- [ ] The "old" copy doesn't appear in any template anymore (run `python3 scripts/audit_remaining_issues.py` if it exists, or use the existing `extract_text.py`)

## Out of scope (deferred to other tickets)

- Per-page fixes (SASKIA-302 through SASKIA-309)
- Glossary + CI gate (SASKIA-310)
- New loan-word translations introduced by per-page fixes
- Adding tooltip explanations for industry terms (Prime Cost, AOV)
- Migrating to i18n framework (explicitly anti-rule; not changing)

## Audit reference

Detailed list of every issue: `docs/ux/copy-fix-list.md` (G.1 through G.8)
High-level critique: `docs/ux/text-critique.md`
Visual audit: `docs/ux/text-inventory.md` (per-section files)
Full implementation plan: `docs/plans/2026-10-07-copy-ux-hardening-plan.md`

## Demo checklist

After merge:

- [ ] `uv run sazon serve` — show `inicio.html` with `Fidelización` band (not `Loyalty`)
- [ ] `uv run sazon serve` — show `reportes/mermas-cost` with `Gs.` (not `₲`)
- [ ] `uv run sazon serve` — show `produccion/manana` with `Guardar plan de mañana` button (not `Guardá`)
- [ ] `uv run sazon serve` — show `riesgos` with `Responsable` (not `Owner`) and `Estado` (not `Status`)
- [ ] `uv run sazon serve` — show `bank` with `Contraparte` (not `Counterparty`)

---

*Phase 0 of 10. Estimated 4-6 hours focused work, then PR-1.*
