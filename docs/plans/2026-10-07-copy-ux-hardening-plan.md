# Sazon Copy & UX Hardening — Implementation Plan v1

**Date:** 2026-10-07
**Branch:** `feat/SASKIA-3xx-copy-ux-hardening` (new)
**Status:** Ready to start
**Owner:** Iván (operator + reviewer), Hermes (impl)
**Ticket format:** SASKIA-3xx (per repo convention)
**Reference docs:**
- `docs/ux/text-inventory.md` (index)
- `docs/ux/text-critique.md` (high-level critique)
- `docs/ux/copy-fix-list.md` (290+ specific items)
- `app/docs/copy-vos.md` (canonical style guide)

---

## Why this plan exists

The `copy-fix-list.md` documents 290+ specific copy/UX issues across 110 templates. Most are 1-line fixes, but they touch the entire app surface. Without a phased plan, the work would either:
- Get done in one giant messy PR (impossible to review, hard to bisect)
- Get done ad-hoc with regressions slipped in between unrelated changes

This plan:
- **Tests-first** for every change that affects user-facing copy
- **Phased by blast radius** — global fixes first (low risk, high leverage), then per-section
- **Batched by PR** so each PR is reviewable in 30 min and revertable in 30 sec
- **Bilingual lock-in** — fixes must follow `app/docs/copy-vos.md` to avoid regression

---

## Hard rules (from AGENTS.md)

These apply throughout the plan:
- Money: `Gs. 729.167` (period thousands sep, no decimals) — per `copy-vos.md`
- Date: `DD/MM/AAAA` (Paraguayan year, not `YYYY`) — per `copy-vos.md`
- Buttons: infinitive verbs (`Registrar`, `Ingresar`) — not `Guardá`
- Empty states: Paraguayan voseo (`Tocá`, `Cargá`) — not Argentine `Guardá`
- Code identifiers: English (no change)
- All money math: `Decimal` → `to_int_gs()` — already enforced, don't break
- No new deps (Hard Rule 26) — only Jinja2 template edits + small CSS/JS
- CHANGELOG.md updated for every PR touching `app/` (Hard Rule 35)

---

## Test conventions (per existing `ux-hardening-plan.md`)

- File naming: `tests/test_SASKIA-3XX_<slug>_regression.py`
- One `client` fixture per test (httpx TestClient)
- `assert` over `unittest.TestCase`
- Spanish copy: check substrings, not exact strings (so future copy tweaks don't break tests)
- Coverage gate: 35% (current floor per `efe77e5`)

**Each ticket MUST have at least one regression test that fails on the OLD code and passes on the NEW code.** No tests = no merge.

---

## Phasing strategy

```
Phase 0  ──  GLOBALS (8 fixes, applies everywhere)         ~1 day    PR-1
Phase 1  ──  LOGIN + INICIO (most-visited pages)           ~1.5 days PR-2
Phase 2  ──  POS (ventas + ventas_detalle + ventas_hist)   ~2 days   PR-3
Phase 3  ──  CLIENTES + PRODUCTOS + RECETAS               ~2 days   PR-4
Phase 4  ──  INVENTARIO + PRODUCCIÓN                       ~3 days   PR-5
Phase 5  ──  PEDIDOS + PROVEEDORES + MENUS                 ~1.5 days PR-6
Phase 6  ──  REPORTES + INSIGHTS + DASHBOARD               ~2 days   PR-7
Phase 7  ──  SETTINGS + EOD + AUDITORIA + OPS              ~1.5 days PR-8
Phase 8  ──  AUTH/ERRORS/HELP + MISC                       ~0.5 day  PR-9
Phase 9  ──  RE-AUDIT + GLOSSARY                           ~1 day    PR-10
                                                                            Total ~16 days (3.2 weeks)
```

Each phase = 1 PR. Each PR = 1 reviewable unit.

---

## Phase 0 — Global Fixes (PR-1)

**Ticket:** SASKIA-301
**Effort:** 4-6 hours
**Files:** 8 templates
**Risk:** Low (well-tested patterns, doc-driven)
**PR title:** `SASKIA-301: standardize currency, register, and severity labels`

### Tasks

#### 0.1 Currency symbol (G.1) 🟠 P1
- **Fix:** Replace `₲` and bare `Gs` with `Gs.` everywhere
- **Files:** `reportes_mermas_cost.html`, `ops_status.html`, `suppliers_volatility.html`, `riesgos.html`
- **Test:** `tests/test_SASKIA-301_currency_gs.py`
  - `GET /reportes/mermas-cost` returns body containing `Gs.` (not `₲`)
  - `GET /riesgos` returns body containing `Gs.` (not `Gs `)
  - At least 1 occurrence of `Gs.` in each affected page

#### 0.2 English band labels (G.2) 🟠 P1
- **Fix:** `Loyalty` → `Fidelización` on `inicio.html` line 87
- **Test:** `tests/test_SASKIA-301_loyalty_label.py`
  - `GET /inicio` body contains `Fidelización` and does NOT contain `Loyalty`

#### 0.3 English loan words (G.3) 🟠 P1
- **Fix per the table in `copy-fix-list.md` G.3:**
  - `KPI` → `Indicadores` (inicio, dashboard)
  - `COGS` → `Costo de Mercadería Vendida` (reportes_diario)
  - `Revenue` → `Ingresos` (reportes_top_productos)
  - `Batches` → `Tandas` (insight_demand)
  - `Override` → `Ajuste manual` (produccion_manana, inventario_form)
  - `Forecast` → `Pronóstico` (insight_demand, produccion_manana)
  - `Lotes` → `Tandas` (cotizador, planner)
  - `Lead time` → `Tiempo de reposición` (inventario_form)
  - `Δ` → `Cambio` (analisis, insight_margenes) — only in column headers
  - `Counterparty` → `Contraparte` (bank)
  - `Status` → `Estado` (planner, suppliers, riesgos, etc.)
  - `Owner` → `Responsable` (riesgos, riesgos)
  - `Endpoint` → `Ruta` (ops_status)
  - `Diff` → `Diferencia` (caja, caja_z)
  - `Qty` → `Cant.` (wishlist, etc.)
  - `Diff` → `Diferencia`
  - `Accuracy` → `Precisión` (only on `produccion_accuracy.html` page title)
  - `IP` → `Dirección IP` (auditoria_analytics)
  - `Log OK/FAIL` → `Login exitoso/fallido` (auditoria_analytics)
  - `Reorder rate` → `Tasa de reposición` (ops_status)
  - `Login OK/FAIL` → already covered above
  - `Login OK / Login FAIL` already covered
- **Keep with tooltip explanation:** `Prime Cost`, `AOV`, `Override` (now `Ajuste manual`)
- **Test:** `tests/test_SASKIA-301_loan_words.py`
  - For each loan word in the source, `grep` the `app/templates/` tree after fix returns 0 occurrences
  - At least one assertion per replacement

#### 0.4 Register consistency (G.4) 🟠 P1
- **Fix:** Replace `Guardá` with `Guardar` in buttons (not empty states)
- **Where:**
  - `produccion_manana.html` line 56: `Guardá plan de mañana` → `Guardar plan de mañana`
  - `produccion_manana.html` line 54: `aria-label="Guardá los ajustes..."` → `Guardar los ajustes...`
  - Audit all other `Guardá` in templates
- **Fix:** Replace Argentine voseo `Decí` (produccion.html `Decí por qué abajo`) → `Indicá por qué abajo`
- **Test:** `tests/test_SASKIA-301_register.py`
  - `grep` for `Guardá` in `app/templates/*.html` returns 0 matches (outside copy-vos.md reference)
  - `grep` for `Decí por qué` returns 0 matches

#### 0.5 Severity pill naming (G.7) 🟠 P1
- **Fix:** `saludable` → `OK` in `inicio.html` line 228
- **Test:** `tests/test_SASKIA-301_severity.py`
  - `GET /inicio` body does NOT contain `saludable`

#### 0.6 Column header abbreviations (G.8) 🟡 P2
- **Fix per the table in `copy-fix-list.md` G.8**
- **Test:** `tests/test_SASKIA-301_columns.py`
  - Specific tests for each affected column header

#### 0.7 Redundant tooltips (G.5) 🟠 P1
- **Fix:** Remove `aria-label` where it duplicates visible text on close buttons (`"Cerrar"`)
- **Test:** `tests/test_SASKIA-301_tooltips.py`
  - For each close button, the `aria-label` either is absent OR adds context beyond the visible text

#### 0.8 Update CHANGELOG.md and copy-vos.md
- **CHANGELOG:** Add entry under `[Unreleased]`
- **copy-vos.md:** Note that some terms were added (e.g. `Fidelización`, `Ajuste manual`)

### Acceptance
- All tests in `tests/test_SASKIA-301_*.py` pass
- `ruff check .` passes
- `make smoke` (or equivalent) passes
- The "old" copy doesn't appear in the dev server anymore (manual check)

### Demo
- `uv run sazon serve` and visit each page; verify the changes are visible

---

## Phase 1 — Login + Inicio (PR-2)

**Ticket:** SASKIA-302
**Effort:** 1.5 days
**Files:** 3 templates (`login.html`, `inicio.html`, plus any CSS)
**Risk:** Medium (login is critical UX)

### Tasks

#### 1.1 LOGIN.1 — Remove duplicate checkbox 🔴 P0
- **Fix:** Keep `Recordar este dispositivo` (line 135). Remove `stay_logged_in` checkbox (line 124-131) and the helper text.
- **Test:** `tests/test_SASKIA-302_login_checkbox.py`
  - `GET /login` body contains `Recordar este dispositivo` (exactly 1 checkbox)
  - Body does NOT contain `Mantener sesión abierta`
  - Body does NOT contain `No uses esto en equipos compartidos.`

#### 1.2 LOGIN.2 — Translate accessibility statement 🟠
- **Fix:** Line 156: `Sazón strives to conform to WCAG 2.1 Level AA.` → `Sazón apunta a cumplir con WCAG 2.1 Nivel AA.`
- **Test:** assert the Spanish sentence is in body; English is not.

#### 1.3 LOGIN.4 — Tagline fallback 🟡
- **Fix:** `{{ branding.tagline }}` → `{{ branding.tagline or "Sistema de gestión para panadería" }}`
- **Test:** N/A (only matters with empty tagline; visual smoke test)

#### 1.4 INICIO.1 — "Operaciones" → "Ventas" 🟠
- **Fix:** Line 52: `label="Operaciones"` → `label="Ventas"`
- **Test:** `GET /inicio` body contains `>Ventas<` (KPI card label)

#### 1.5 INICIO.5 — Split "Acciones del día" into two cards 🟡
- **Fix:** Restructure inicio.html: extract informational items (`Merma del día — registrada ✓`) into a separate `Hecho hoy` card below `Acciones del día`.
- **Test:** `tests/test_SASKIA-302_acciones_split.py`
  - Body contains `Acciones del día`
  - Body contains `Hecho hoy` (the new card)
  - Both have distinct visual classes (e.g. `.card-acciones` vs `.card-hecho`)

#### 1.6 INICIO.6 — Pronóstico empty state 🟡
- **Fix:** `Necesitamos ~4 semanas de ventas en este día para pronosticar.` → `Necesitamos ~4 semanas de ventas de este día de la semana para pronosticar.`
- **Test:** substring check

#### 1.7 INICIO.17 — Loyalty sub-text 🟠
- **Fix:** `{{enrollment_with_today}} de {{enrollment_total_today}} ventas` → `{{enrollment_total_today}} ventas · {{enrollment_with_today}} con cliente`
- **Test:** substring check

#### 1.8 INICIO.15 — Delta direction for new business 🟠
- **Fix:** Add `{% if direction == 'new' %}` branch that shows `—` instead of an arrow.
- **Test:** When `delta_ventas.direction == 'new'`, body should contain `—` (not an arrow `↑` or `▼`).

### Acceptance
- All tests in `tests/test_SASKIA-302_*.py` pass
- Manual: log in, verify no second checkbox; verify home KPIs are clear

### Demo
- Screenshot the login page with the fix
- Screenshot the home page on a fresh DB (empty state) and with data (KPI cards)

---

## Phase 2 — POS (PR-3)

**Ticket:** SASKIA-303
**Effort:** 2 days
**Files:** 3 templates (`ventas.html`, `ventas_detalle.html`, `ventas_historial.html`)
**Risk:** Medium-High (POS is daily-use)

### Tasks

#### 2.1 VENTAS.1 — Page H1/H2 mismatch 🟠
- **Fix:** H1 = `Ventas` → `Nueva venta` (matches H2). `/ventas/historial` keeps H1 = `Historial de ventas`.
- **Test:** substring check

#### 2.2 VENTAS.2 — Split customer/RUC fields 🟠
- **Fix:** Add a separate `RUC del cliente` field below the customer picker. Hint: `Completá el RUC solo si emitís Factura.`
- **Test:** Body contains `RUC del cliente` as a distinct input

#### 2.3 VENTAS.3 — "Lotes" → "Tandas" 🟠 (global fix in Phase 0, but verify POS uses it)
- **Already done in Phase 0** — verify with grep

#### 2.4 VENTAS.4 — Always-show Pausar button 🟡
- **Fix:** Remove `style="display:none"`, add `disabled` until cart is non-empty
- **Test:** Body contains `id="btn-hold-cart"` without `style="display:none"`

#### 2.5 VENTAS.5 — Specify Cancelar button 🟡
- **Fix:** `Cancelar` → `Cancelar (vacía el carrito)`
- **Test:** substring check

#### 2.6 VENTAS.13 — Add Proveedor to Nuevo dropdown 🟢
- **Fix:** Add `<a href="/proveedores/nuevo">Proveedor</a>` to the dropdown in `base.html` line 132-144
- **Test:** Body contains `<a href="/proveedores/nuevo"` (substring)

#### 2.7 VENTAS.22 — "Atendido por" → "Operador" 🟠
- **Fix:** In `ventas_historial.html`, rename column header to `Operador`
- **Test:** Body contains `<th>Operador</th>` and does NOT contain `<th>Atendido por</th>`

#### 2.8 VENTAS.17 — "Rango de días" → "Últimos N días" 🟠
- **Fix:** Rename label
- **Test:** substring check

#### 2.9 VENTAS.18 — "Ver anuladas" → "Incluir anuladas" 🟠
- **Fix:** Rename toggle label
- **Test:** substring check

### Acceptance
- All tests pass
- Manual: walk through a sale, verify Cancelar behavior, verify held-sale is visible

### Demo
- Screenshot the POS in idle state, mid-sale state, with held cart

---

## Phase 3 — Clientes + Productos + Recetas (PR-4)

**Ticket:** SASKIA-304
**Effort:** 2 days
**Files:** 8 templates

### Tasks (per the fix list)

| # | File | Item | Priority |
|---|---|---|---|
| 3.1 | `clientes.html` | `Sub · Ped` → `Pedidos abiertos` | 🟡 |
| 3.2 | `clientes_duplicados.html` | Drop `(id=X)` from H1 | 🟠 |
| 3.3 | `cliente_editar.html` | Merge `Tipo de operación` + `Tipo de documento` into one field | 🟠 |
| 3.4 | `cliente_editar.html` | Date placeholder `DD-MM o DD-MM-AAAA` → `DD/MM/AAAA` | 🟡 |
| 3.5 | `cliente_editar.html` | `Restricciones alimentarias` and `Preferencias de orden` (clarify) | 🟠 |
| 3.6 | `pedidos_nuevo.html` | Collapse 7 address fields to 1 textarea + structured fallback | 🟠 |
| 3.7 | `pedidos_nuevo.html` | `Cliente seleccionado` label rework | 🟡 |
| 3.8 | `pedidos_nuevo.html` | `En una franja horaria (preferida, no es garantía)` → `Franja horaria preferida (no es garantía)` | 🟠 |
| 3.9 | `productos.html` | `Porción` → `Tamaño`; `Mayorista` → `Precio mayorista (Gs.)`; `% Costo` → `Costo %`; `Costo act.` → `Costo actual`; `Disp.` → `Disponible` | 🟠 |
| 3.10 | `producto_form.html` | `SKU / Código de barras` → `SKU o código de barras` | 🟠 |
| 3.11 | `producto_form.html` | `Etiqueta de porción` → `Tamaño de la porción` | 🟠 |
| 3.12 | `producto_form.html` | `IVA%` → `IVA (%)` | 🟠 |
| 3.13 | `producto_form.html` | `RSPA` tooltip: add `Registro Sanitario (INAN)` explanation | 🟠 |
| 3.14 | `recetas.html` | `Foto` column → `Imagen` | 🟠 |
| 3.15 | `recetas.html` | `Dificultad` aria: add `(1-5)` | 🟠 |
| 3.16 | `receta_form.html` | `Prep.`, `Cocción` → `Tiempo de prep.`, `Tiempo de cocción` | 🟠 |
| 3.17 | `receta_form.html` | `Rinde` → `Rinde (porciones)` | 🟠 |
| 3.18 | `receta_form.html` | `costo × 3` → `costo + 200% de margen` in the helper text | 🟠 |
| 3.19 | `receta_detalle.html` | Remove duplicate `Secuencia Completa de Preparación` H2 | 🟠 |
| 3.20 | `receta_detalle.html` | `Re-petir este pedido` tooltip → `Repetir este pedido` | 🟠 |

### Tests
- `tests/test_SASKIA-304_clientes.py` (3.1-3.5)
- `tests/test_SASKIA-304_pedidos_address.py` (3.6)
- `tests/test_SASKIA-304_productos.py` (3.9-3.13)
- `tests/test_SASKIA-304_recetas.py` (3.14-3.20)

### Acceptance
- All tests pass
- Visual: confirm the duplicate H2 is gone from `receta_detalle.html`

---

## Phase 4 — Inventario + Producción (PR-5)

**Ticket:** SASKIA-305
**Effort:** 3 days (largest phase due to 16+ templates)
**Files:** 16 templates

### Tasks (highest-impact subset)

| # | File | Item | Priority |
|---|---|---|---|
| 4.1 | `inventario_form.html` | `Lead time` → `Tiempo de reposición` (per Phase 0, verify) | 🟠 |
| 4.2 | `inventario_form.html` | `Punto de reorden (override)` → `Punto de reorden (ajuste manual)` | 🟠 |
| 4.3 | `inventario_form.html` | `Stock de apertura` / `Fecha de apertura` — clarify "apertura" (rewrite to `Fecha de primera compra`) | 🟠 |
| 4.4 | `inventario_form.html` | Long label `Posible contaminación cruzada con trigo (bloquea "sin TACC")` — split into label + hint | 🟠 |
| 4.5 | `ingrediente_detalle.html` | `Stock inicial (en und. del paquete)` → `Stock inicial (en unidades del paquete)` | 🟠 |
| 4.6 | `ingrediente_detalle.html` | `Horizonte (días)` → `Pronóstico para los próximos N días` | 🟠 |
| 4.7 | `inventario.html` | `¿Llenar todos los ingredientes a 2× el mínimo?` → `... al doble del mínimo?` | 🟠 |
| 4.8 | `inventario_movimientos.html` | `Balance antes / después` → `Stock antes / después` | 🟠 |
| 4.9 | `produccion_manana.html` | `Guardá` → `Guardar` (button + aria) | 🟠 |
| 4.10 | `produccion_manana.html` | `Ingreso estimado mañana` sub: `precio catálogo × cantidad` → `Basado en precio de carta` | 🟠 |
| 4.11 | `produccion_manana.html` | **BUG: Remove duplicate `🧾 Pedidos para mañana` H2 (line 86 and 95)** | 🔴 P0 |
| 4.12 | `produccion_manana.html` | `Confianza media` label → `Confianza promedio (%)` | 🟠 |
| 4.13 | `produccion.html` | `Aún no hay ventas registradas` → `Todavía no hay ventas registradas` | 🟠 |
| 4.14 | `produccion.html` | `Plan frío (datos insuficientes)` → `Plan estimado (datos insuficientes)` | 🟠 |
| 4.15 | `produccion.html` | `No horneado: Cero unidades. Decí por qué abajo.` → `Indicá por qué abajo` | 🟠 |
| 4.16 | `produccion.html` | Translate English tooltip `Set every row's qty to its target and check 'done'` | 🟠 |
| 4.17 | `produccion_accuracy.html` | `Accuracy` column → `Precisión (%)` (with tooltip) | 🟠 |
| 4.18 | `produccion_haccp.html` | `AM (apertura) / PM (cierre)` — clarify (this is the only field, not a subset) | 🟠 |
| 4.19 | `planner.html` | `Lotes perdidos` → `Tandas perdidas` | 🟠 |
| 4.20 | `planner.html` | `Unit Gs.` → `Precio unit. (Gs.)`; `Status` → `Estado` | 🟠 |
| 4.21 | `produccion_prep.html` | `Falta = no alcanza; Justo = alcanza justo; Suficiente = sobra` — keep, but ensure visible | 🟢 |
| 4.22 | All produccion pages | Audit and remove redundant `Elegí un producto y la cantidad a producir hoy` tooltips | 🟠 |

### Tests
- `tests/test_SASKIA-305_inventario.py` (4.1-4.8)
- `tests/test_SASKIA-305_produccion.py` (4.9-4.22)
- `tests/test_SASKIA-305_dup_h2.py` (4.11 — specifically tests for single `Pedidos para mañana` heading)

### Acceptance
- All tests pass
- **Critical:** `produccion_manana.html` no longer has the duplicate H2 (visual smoke test)
- Manual: walk through a production plan and verify the labels are clear

---

## Phase 5 — Pedidos + Proveedores + Menus (PR-6)

**Ticket:** SASKIA-306
**Effort:** 1.5 days
**Files:** 14 templates

### Tasks

| # | File | Item | Priority |
|---|---|---|---|
| 5.1 | `pedido_detalle.html` | (covered in 3.20) | 🟠 |
| 5.2 | `pedido_stock_preview.html` | `Forzar cumplimiento a pesar del faltante` → `Forzar cumplimiento aunque falte stock` | 🟠 |
| 5.3 | `reorder.html` | Typo `rapido` → `rápido` in `Marcar comprado rapido` aria | 🟠 |
| 5.4 | `reorder.html` | Long tooltip `Marca ingredientes arriba para marcarlos como comprados en 1 click` → split | 🟠 |
| 5.5 | `reorder.html` | `Llena a 2x min con un click...` → `Llená al doble del mínimo con 1 click...` | 🟠 |
| 5.6 | `shopping_list.html` | `Cant a comprar` → `Cantidad` | 🟠 |
| 5.7 | `wishlist.html` | `Qty` → `Cant.`; `Unit Gs.` → `Unitario (Gs.)`; `Status` → `Estado` | 🟠 |
| 5.8 | `suppliers_volatility.html` | `Mín ₲ / Máx ₲ / Promedio ₲` → `Mín (Gs.) / Máx (Gs.) / Promedio (Gs.)` (per G.1) | 🟠 |
| 5.9 | `suppliers_volatility.html` | `Último hace` → `Último cambio` | 🟠 |
| 5.10 | `supplier_precios.html` | `Ahorro potencial si comprás al más barato` — verify voseo | 🟢 |
| 5.11 | `menus.html` | `25000` placeholder → `25.000` | 🟠 |
| 5.12 | `menu_import_ocr.html` | `Precio (Gs)` → `Precio (Gs.)` | 🟠 |
| 5.13 | All pedidos pages | Verify `Compras últimos 30 días` consistency | 🟢 |
| 5.14 | `delivery_zones.html` | (mostly OK) | 🟢 |

### Tests
- `tests/test_SASKIA-306_pedidos.py`
- `tests/test_SASKIA-306_proveedores.py`
- `tests/test_SASKIA-306_menus.py`

---

## Phase 6 — Reportes + Insights + Dashboard (PR-7)

**Ticket:** SASKIA-307
**Effort:** 2 days
**Files:** 25 templates (largest count, but mostly small fixes)

### Tasks (most are global fixes from Phase 0 already applied — verify + add a few new ones)

| # | File | Item | Priority |
|---|---|---|---|
| 6.1 | All `insight_*.html` | Verify Phase 0 loan-word fixes landed | 🟠 |
| 6.2 | `analisis.html` | `Δ Margen` column → `Cambio (margen)` | 🟠 |
| 6.3 | `insight_demand.html` | `Batches` → `Tandas` (verify) | 🟠 |
| 6.4 | `insight_price_impact.html` | `Food cost %` → `Costo / venta %` (or similar) | 🟠 |
| 6.5 | `insight_price_impact.html` | `Productos bajo objetivo (33%)` — make 33% configurable per product | 🟠 |
| 6.6 | `benchmarks.html` | `Mercado avg Gs.` → `Mercado promedio (Gs.)` | 🟠 |
| 6.7 | `benchmarks.html` | `Δ Gs.` column → `Cambio (Gs.)` | 🟠 |
| 6.8 | `benchmark_edit.html` | Verify emoji H3s are intentional (`💰`, `🏪`, `📦`) | 🟢 |
| 6.9 | `cotizador.html` | `Lotes` column → `Tandas` | 🟠 |
| 6.10 | `reportes_mermas_cost.html` | `Costo total ₲ / Costo promedio / evento ₲` → `... (Gs.)` | 🟠 |
| 6.11 | `reportes_top_productos.html` | `Revenue` → `Ingresos` | 🟠 |
| 6.12 | `reportes_diario.html` | `COGS` → `Costo de Mercadería Vendida` | 🟠 |
| 6.13 | `dashboard.html` | `KPI` loan word (verify) | 🟠 |
| 6.14 | `reportes_comparacion.html` | (mostly OK) | 🟢 |
| 6.15 | `evidencia_mercado.html` | (mostly OK) | 🟢 |

### Tests
- `tests/test_SASKIA-307_reportes.py`
- `tests/test_SASKIA-307_insights.py`
- `tests/test_SASKIA-307_dashboard.py`

### Special note
- 6.5 (configurable food cost % per product) is the only **functional** change. May need a DB migration if stored per-product, or a settings field. Decide: settings field (simpler, scope-creep) vs per-product override (right, but bigger). Recommend settings field for v1.

---

## Phase 7 — Settings + EOD + Auditoria + Ops (PR-8)

**Ticket:** SASKIA-308
**Effort:** 1.5 days
**Files:** 10 templates

### Tasks

| # | File | Item | Priority |
|---|---|---|---|
| 7.1 | `settings.html` | `Costeo (Fase 1.D)` — drop `(Fase 1.D)` (internal phase) | 🟠 |
| 7.2 | `settings.html` | `Usa la configuración de su sistema operativo` → `... de tu sistema operativo` | 🟠 |
| 7.3 | `auditoria_analytics.html` | `Top IPs` → `Direcciones IP más frecuentes` | 🟠 |
| 7.4 | `auditoria_analytics.html` | `Login OK / Login FAIL` → `Login exitoso / Login fallido` | 🟠 |
| 7.5 | `ops_status.html` | `Reorder rate` → `Tasa de reposición` | 🟠 |
| 7.6 | `ops_status.html` | `Endpoint` → `Ruta` | 🟠 |
| 7.7 | `ops_status.html` | `Total ₲` → `Total (Gs.)` | 🟠 |
| 7.8 | `bank.html` | `Currency` → `Moneda` | 🟠 |
| 7.9 | `bank.html` | `Counterparty` → `Contraparte` | 🟠 |
| 7.10 | `riesgos.html` | `Prob.` → `Probabilidad`; `Impact Gs.` → `Impacto (Gs.)`; `Sev Gs.` → `Severidad (Gs.)`; `Status` → `Estado`; `Owner` → `Responsable` | 🟠 |
| 7.11 | `eod_print.html` | (mostly OK) | 🟢 |
| 7.12 | `eod.html` | (mostly OK) | 🟢 |
| 7.13 | `auditoria.html` | (mostly OK) | 🟢 |
| 7.14 | `users.html` | (mostly OK) | 🟢 |
| 7.15 | `settings_catalog.html` | (mostly OK) | 🟢 |

---

## Phase 8 — Auth/Errors/Help/Misc (PR-9)

**Ticket:** SASKIA-309
**Effort:** 0.5 day
**Files:** 6 templates

### Tasks

| # | File | Item | Priority |
|---|---|---|---|
| 8.1 | `errors/404.html` | Review and standardize error messages | 🟠 |
| 8.2 | `errors/4xx.html` | Same | 🟠 |
| 8.3 | `errors/500.html` | Same — should NOT leak stack trace to user | 🔴 P0 (security) |
| 8.4 | `guia.html` | Add a "How to use this guide" intro section | 🟡 |
| 8.5 | `dev_combo_smoke.html` | Should NOT be linked from operator UI (only dev-accessible) | 🟠 |
| 8.6 | `copiloto.html` | `Preguntale algo al copiloto...` (verify voseo) | 🟢 |

### Critical security check (8.3)
- Read `errors/500.html` and verify:
  - No stack trace visible to user
  - No DB schema or query visible
  - Generic apology + reference ID + "tell Iván" contact
  - AGENTS.md Hard Rule 34 (no leaked secrets)

---

## Phase 9 — Re-audit + Glossary (PR-10)

**Ticket:** SASKIA-310
**Effort:** 1 day
**Files:** docs only

### Tasks

#### 9.1 Re-audit pass
- **Goal:** Verify all 290+ fixes actually landed
- **Method:** Re-run the same `extract_text.py` script against templates and diff with the pre-fix output
- **Tool:** `scripts/audit_remaining_issues.py` (to be written) — grep for known bad patterns

#### 9.2 Build terminology glossary
- **File:** `app/docs/glossary.md` (new)
- **Content:**
  - Each major concept (cliente, pedido, producto, venta, receta, ingrediente, lote/tanda, etc.) with the canonical Spanish term and acceptable synonyms
  - English equivalents (for developers)
  - "Don't use" list
- **Format:** Same table style as `copy-vos.md`

#### 9.3 Update `copy-vos.md`
- **Add** the new terms introduced (e.g. `Fidelización`, `Ajuste manual`, `Indicadores`)
- **Mark** the existing entries as "audited 2026-10-07"

#### 9.4 Add CI gate
- **File:** `tests/test_terminology_consistency.py` (new)
- **What:** Grep templates for the "don't use" list from glossary.md
- **Failure:** CI fails if any of these terms appear
- **Pattern:** Same approach as the existing anti-rule enforcement (per AGENTS.md "13 of 20 anti-rules enforced via grep in CI")

#### 9.5 Final smoke test
- `make smoke` (or equivalent)
- All tests pass
- `ruff check .` clean
- Visual: walk through every page on a fresh DB + seeded DB

---

## Ticket convention (SASKIA-3xx)

| Ticket | Title | Phase | Effort | PR |
|---|---|---|---|---|
| SASKIA-301 | Standardize currency, register, severity labels | 0 | 4-6h | PR-1 |
| SASKIA-302 | Login + home copy and KPI fixes | 1 | 1.5d | PR-2 |
| SASKIA-303 | POS copy and layout fixes | 2 | 2d | PR-3 |
| SASKIA-304 | Clientes + Productos + Recetas copy | 3 | 2d | PR-4 |
| SASKIA-305 | Inventario + Producción copy | 4 | 3d | PR-5 |
| SASKIA-306 | Pedidos + Proveedores + Menus copy | 5 | 1.5d | PR-6 |
| SASKIA-307 | Reportes + Insights + Dashboard | 6 | 2d | PR-7 |
| SASKIA-308 | Settings + EOD + Auditoria + Ops | 7 | 1.5d | PR-8 |
| SASKIA-309 | Errors + Help + Misc | 8 | 0.5d | PR-9 |
| SASKIA-310 | Re-audit + glossary + CI gate | 9 | 1d | PR-10 |
| **Total** | | | **~16 days** | 10 PRs |

---

## Worktree policy (per AGENTS.md)

- All work on `feat/SASKIA-3xx-copy-ux-hardening` branch (or sub-branches if parallelized)
- Per `docs/operations/worktree-policy.md`: use git worktrees if multiple AI sessions
- Don't commit to main until PR is reviewed
- Per `docs/operations/2026-10-04-sibling-session-coordination.md`: coordinate with any sibling sessions

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Regression in a critical page (POS, login) | High | Tests-first + manual smoke test per PR |
| `copy-vos.md` not in sync with templates | Medium | SASKIA-310 adds CI gate + glossary enforcement |
| Worker's fix breaks AGENTS.md money/date rules | High | Every PR includes `grep` for `Gs\.` (no `Gs `), `YYYY` (no — use `AAAA`), and `Decimal`/`int_gs` (don't introduce floats) |
| Duplicate H2 in produccion_manana.html goes unnoticed | Medium | SASKIA-305.4.11 has a dedicated test |
| Translation drift after launch (if launched now) | Critical | Plan must complete before launch, OR the high-impact fixes (Phase 0-2) before launch |
| Translation costs more after launch | Critical | Same as above — finish the plan |

---

## What I'm NOT doing in this plan

These are explicitly out of scope (deferred or anti-rules):

- **Multi-language support** (English version of the UI) — would require i18n framework, not just copy changes
- **A full design-system rewrite** — the copy fixes don't require changing CSS or design tokens
- **New features** — this is copy/UX, not functionality
- **Refactoring macro calls** (`ui.empty_state` parameters, etc.) — the macro is fine
- **Adding new components** (e.g. `ui-kpi-card` v2) — the existing ones work
- **Migrating to React/Vue** — explicitly anti-rule #1 per AGENTS.md

---

## Definition of done

For the entire plan to be DONE:

1. ✅ All 10 PRs merged to main
2. ✅ All tests in `tests/test_SASKIA-3*.py` pass
3. ✅ `make smoke` (or equivalent) passes
4. ✅ `ruff check .` passes
5. ✅ CHANGELOG.md updated per PR (per Hard Rule 35)
6. ✅ New CI gate (`test_terminology_consistency.py`) added and passing
7. ✅ Glossary doc (`app/docs/glossary.md`) written
8. ✅ Visual smoke test: every page renders without broken text or layout
9. ✅ Demo recorded: walk through login → home → sale → production → report

---

## Open questions for Iván before starting

Before I begin Phase 0, please confirm:

1. **Branch name:** `feat/SASKIA-3xx-copy-ux-hardening` — or do you prefer a different name? Per existing convention (`feat/phase-3-m1-product-detail`), the format is `feat/<scope>`.
2. **Test framework:** existing tests use `pytest` + `httpx` TestClient. Should I follow that exactly? (I will, unless you say otherwise.)
3. **CHANGELOG format:** is there a preferred format beyond "list the ticket + a few bullets"? (I'll match whatever's in `[Unreleased]` now.)
4. **Glossary approval:** for the new terms I'm introducing (`Fidelización`, `Ajuste manual`, `Indicadores`, `Moneda`, `Contraparte`, `Tasa de reposición`, `Dirección IP más frecuentes`, `Login exitoso/fallido`) — do these match what you (and Saskia) would actually say? These are my best guesses; a 5-min review would prevent rework.
5. **Scope of the food cost % fix (6.5):** is the configurable per-product threshold a real ask, or am I over-scoping? If settings field is fine, that's 30 min. If per-product, that's a DB migration (~2-3 days).
6. **Backup encryption & D.5 (recently shipped):** unrelated to this plan, but I want to confirm I shouldn't touch the recent D.5 backup encryption work while doing this.
7. **Parallel sessions:** are you running any other AI sessions on this repo right now? Per AGENTS.md worktree policy, I need to coordinate.

---

## What I would do first (when I get the green light)

1. Create the branch and base ticket:
   ```
   git checkout -b feat/SASKIA-3xx-copy-ux-hardening
   mkdir -p docs/intake
   cp docs/ux/copy-fix-list.md docs/intake/SASKIA-301-...md
   ```
2. Write `tests/test_SASKIA-301_currency_gs.py` (the simplest test) and watch it fail
3. Make the 4-file fix
4. Watch the test pass
5. Repeat for the other Phase 0 tests
6. Commit + push + open PR

Estimated first PR ready in 4-6 hours of focused work.

---

*Plan ready. Awaiting green light from Iván.*
