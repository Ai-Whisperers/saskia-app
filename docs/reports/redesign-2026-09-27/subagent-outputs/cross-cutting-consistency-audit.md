# Cross-Cutting Consistency Audit — Sazón (2026-09-27)

**Scope:** 46 pages across three audit documents
- **Batch 1** — `design-plans-2026-09-27.md` (18 personal pages, ~76-page master plan)
- **Batch 2** — `audit-batch2-prod.md` (14 pages: inventario family + producción + pedidos family + receta-editar)
- **Batch 3** — `audit-batch3-reports.md` (14 pages: suppliers + compras + bank + riesgos + reportes)

**Method:** Programmatic pattern mining across all 46 page sections, cross-referenced with per-page observations in the source audits. Severity scale: **P0** (breaks core flow / violates core spec) · **P1** (high-friction / inconsistent in obvious way) · **P2** (polish / nuancing).

---

## Executive summary

The three audit documents describe a **functionally wide** system that nonetheless suffers from a handful of systemic **terminology, formatting, and interaction drift** issues that should be fixed *before* more pages get built. The top 10 systemic findings, ranked:

| # | Issue | Severity | Pages affected |
|---|---|---|---|
| 1 | **No canonical glossary** — product/receta, cliente/customer/comprador, mostrar/pickup/counter are used interchangeably across pages | **P0** | 28 of 46 |
| 2 | **Date format drift** — `dd/mm/yyyy` vs `yyyy-mm-dd` vs US `mm/dd/yyyy` placeholders, sometimes mixed within a single form | **P0** | 13 of 46 |
| 3 | **Voseo vs infinitive button labels** — "Guardá" / "Guardar" / "Editá" / "Editar" mixed randomly | **P1** | 17 of 46 |
| 4 | **English status pills on Spanish page** — `pending`, `confirmed`, `cancelled` appear inline alongside `Pendiente`, `Confirmado`, `Cancelado` | **P0** | 5 of 46 |
| 5 | **No toast/feedback component** — every form submission is silent, no "Saved ✓" feedback | **P1** | 14 of 46 |
| 6 | **Currency placement inconsistent** — `Gs. 20.000` (dot thousand sep) is dominant but `$ Gs.` and `Gs ` (no period) appear | **P1** | 36 of 46 |
| 7 | **Slug-as-display-name bug** — "415de24c", "0da4ca66", "cfaf4b47" leak from DB into UI in 9 pages | **P0** | 9 of 46 |
| 8 | **Empty states are inconsistent** — some pages have rich CTAs ("Sin movimientos registrados" + CTA), others show nothing (Riesgos), some duplicate the parent page (suppliers-dup is byte-identical to suppliers) | **P1** | 26 of 46 |
| 9 | **No keyboard shortcut map** — `⌘K` and `⌘N` are documented for some pages but `⌘S`, `⌘E`, `Enter`, `Esc` are mentioned inconsistently | **P2** | 16 of 46 |
| 10 | **No required-field marker standard** — `*` appears on Nombre but not on Stock mínimo; receta-editar has `*` on Nombre but not on Familia | **P1** | 11 of 46 |

---

## 1 · TERMINOLOGY DRIFT (same concept, multiple names)

This is the **biggest single issue** — pages use different words for the same business concept. Below: every concept that drifts, with affected pages and the strings used on each.

### 1.1 Save / Cancel / Edit actions — voseo vs infinitive

| Variant | Pages |
|---|---|
| **"Guardá"** (voseo imperative) | `supplier-nuevo.png` (Save button — noted as P0 typo), `inventario-nuevo.png`, `inventario-editar.png`, `receta-editar.png` |
| **"Guardar"** (infinitive) | all other forms |
| **"Editá"** (voseo) | `inventario-detalle.png` ("Editá ingrediente" button), Spanish-language CSV action |
| **"Editar"** (infinitive) | `pedido-detalle.png` ("Editar" implied via Editar items), most other pages |

- **Severity:** P1 (Polish defect, but breaks trust)
- **Affected pages (17):** inventario, inventario-nuevo, inventario-editar, inventario-detalle, productos-nuevo, producto-editar, receta-editar, recetas-nueva, supplier-nuevo, eod, settings, reportes-iva, vs-mercado-editar, pedido-detalle, pedidos-nuevo, ventas, pedidos-board
- **Recommended canonical pattern:** Use **infinitive** for every primary action button ("Guardar", "Editar", "Cancelar", "Eliminar", "Confirmar", "Crear") everywhere. Voseo is conversational and reads like a bug in a system label.
- **Effort:** ~2 hours. Find-and-replace in templates + manual audit of any screen recorded in 3rd person.
- **Reference:** `audit-batch3-reports.md §3 supplier-nuevo (defect line 191)`, `audit-batch2-prod.md §4 inventario-detalle QoL line 266`.

### 1.2 "Cliente" / "Cliente" / "Customer" / "Comprador"

| Term | Pages |
|---|---|
| **"cliente"** (lowercase, ES) | `ventas.png` (18 mentions), `pedidos-nuevo.png` (14), `pedido-detalle.png` (7), `pedidos.png` (5), `auditoria.png`, `dashboard.png`, `eod.png`, `inventario.png`, `ops-status.png`, `pedido-duplicate.png` (5), `pedidos-board.png`, `produccion.png`, `producto-editar.png`, `productos-nuevo.png`, `productos.png`, `receta-editar.png`, `reportes-iva.png`, `reportes-top-productos.png`, `settings-catalog.png`, `supplier-nuevo.png`, `reportes.png` |
| **"Comprador"** | not seen in primary UI copy (mentioned only as a synonym candidate in the wishlist of `reportes-top-productos.png`) |
| **English "customer"** | not seen in primary labels, but English / Spanish code-mixing on auditor labels: `'product'`, `'sale'`, `'customer …'` in the placeholder text of `auditoria.png` ("Tipo de registro (placeholder \"product, sale, customer …\")") |

- **Severity:** P0 (definitional inconsistency)
- **Affected pages:** 22 pages use "cliente"; 1 (`auditoria.png`) leaks English in placeholder
- **Recommended canonical pattern:** "cliente" everywhere in ES UI. English only in developer-facing audit event names ("supplier.merge"), which is fine.
- **Effort:** <1 hour for the 1 wrong placeholder; cosmetic-only at this point.

### 1.3 "Producto" vs "Receta" (and what they represent)

The system has two parallel concepts that get conflated:
- **Receta** = a recipe (ingredients + steps + yield)
- **Producto** = the sellable item (linked to a recipe optionally)

| Page | Uses | When "product" is intended but "receta" is shown |
|---|---|---|
| `receta-editar.png` | Receta × 39 | Expected — editing recipes |
| `recetas-nueva.png` | Receta × 33 | Expected |
| `recetas.png` | Receta × 19 | Expected |
| `pricing.png` | receta × 19, producto × 0 | Title says "Precios por receta" — good. But cells mix "Receta" (good) |
| `reportes-top-productos.png` | producto × 13, receta × 0 | Title "Top productos" — but Top-productos report card lives in `reportes.png` alongside "Recetas" items; unclear whether you sell "products" or "recipes" |
| `productos.png` | producto × 17, receta × 17 | Title and column headers both — **confused** |
| `productos-nuevo.png` | producto × 15, receta × 15 | "Después de guardar, crear producto" toggle next to "receta" — semantic drift |
| `pedidos-board.png` | producto (n/a in writeup), but uses producto descriptions from production | — |
| `produccion.png` | producto × 9, receta × 9 | "Productos a producir" with sub-card showing "Receta cfaf4b47" — **the product display name contains the recipe slug** |

- **Severity:** P0 (definitional)
- **Affected pages:** 26 pages mention "producto"; 25 mention "receta"; **8 pages use both interchangeably** in the same UI (`productos.png`, `productos-nuevo.png`, `producto-editar.png`, `pedido-detalle.png`, `pedido-duplicate.png`, `produccion.png`, `receta-editar.png`, `reportes-iva.png`)
- **Recommended canonical pattern:**
  - **Producto** = the item on the shelf or in the menu (sellable, with price).
  - **Receta** = the recipe that may or may not back a producto.
  - On `pedido-detalle.png`: show **producto name** in the items table, not the receta slug.
  - On `produccion.png`: keep the production plan grouped by producto; show the linked receta as a secondary line ("para la receta X").
- **Effort:** ~1 day (touches model display logic + UI strings).

### 1.4 "Mostrador" / "Pickup" / "Counter" (sales channel)

| Term | Pages / context |
|---|---|
| **"mostrador"** (lowercase ES) | `inicio.png`, `pedidos.png` (×7), `pedidos-board.png` (×4), `pedidos-nuevo.png`, `dashboard.png`, `productos.png` (column header), `receta-editar.png`, `reportes-top-productos.png` — used as the in-person sales channel name |
| **"Pickup"** | "Listos para **retiro**" (`pedidos-board.png`) — uses "retiro" not "pickup" |
| **"Counter" / "counter staff"** | *never* in primary UI; only in the audit's persona analysis |
| **"Listos para despacho"** | wishlist-only on `pedidos-board.png` (delivery alternative) |

- **Severity:** P2 (cosmetic, mostly consistent internally)
- **Affected pages:** 8 pages
- **Recommended canonical pattern:** Use **"Mostrador"** capitalized when it's a sales channel name ("Canal: Mostrador / WhatsApp / Web"), and **"retiro"** for the pickup-side action ("Listos para retiro"). No English "pickup" or "counter" in UI labels.
- **Effort:** <2 hours.

### 1.5 "Cerrar día" / "Cierre" / "EOD"

| Term | Pages |
|---|---|
| **"Cierre"** (la EOD) | `eod.png` (×10), `inicio.png` (×4), `reportes-iva.png` (×3), `ventas.png`, `pedidos.png` |
| **"Cerrar día"** (verb) | `inicio.png` ("Cierre de ayer" tile label), `eod.png` |
| **"EOD"** (English acronym) | **Not seen in UI copy** (good — consistent Spanish) |

- **Severity:** P2 (consistency good)
- **Affected pages:** 5
- **Recommended canonical pattern:** **"Cierre diario"** as the noun (the page). **"Cerrar día"** as the verb (the action). Audit action tags stay English (`eod.close`) for developer logs.
- **Effort:** <1 hour.

### 1.6 "Comprobante fiscal" / "Boleta" / "Factura" / "Recibo"

| Term | Pages |
|---|---|
| **"comprobante"** | `inventario-nuevo.png` (×3 — "Comprobante de origen"), `pedido-detalle.png` (×5 — "comprobante" copy mentions), `bank.png` (×2) |
| **"factura"** | `inventario-nuevo.png`, `inventario-movimientos.png`, `settings.png`, `shopping-list.png`, `supplier-nuevo.png`, `ventas.png` (×8) |
| **"recibo"** | mentioned only in `ventas.png` |
| **"boleta"** | **Not seen**, but `reportes-iva.png` and `eod.png` imply "Libro de Ventas" structure that is fiscal-document-flavored |

- **Severity:** P1 (Paraguayan tax compliance requires exact terminology — "factura" vs "boleta" affects IVA classification)
- **Affected pages:** 9
- **Recommended canonical pattern:** Define one wrapper ("Comprobante") with subtypes `Factura | Boleta | Recibo | Nota de crédito`. Required for PARAGUAY tax compliance since 2023.
- **Effort:** ~2 hours for spec; ~1 day for implementation given SET/IVA reporting.

### 1.7 "ingrediente" / "Insumo"

| Term | Pages |
|---|---|
| **"ingrediente"** | most pages (`inventario.png`, `inventario-nuevo.png`, `inventario-detalle.png`, `recipe-editar.png`, `produccion.png`, etc.) |
| **"insumo"** | `receta-editar.png` ingredients table column header is "INSUMO/SUB-RECETA" |
| **"Insumos"** (as a category) | `settings-catalog.png` ×3 |

- **Severity:** P2
- **Affected pages:** 2 in primary UI (`receta-editar.png` table header) + 1 (`settings-catalog.png`)
- **Recommended canonical pattern:** **"Ingrediente"** for the raw material; **"Insumo"** as a *category* (Categoría: Insumos / Insumos secos / Insumos húmedos). Update `receta-editar.png` column header from "INSUMO/SUB-RECETA" to "INGREDIENTE/SUB-RECETA" for consistency.
- **Effort:** <1 hour.

### 1.8 "Ver" / "Abrir" / "Ver detalle" / "Detalle"

Different verbs on different row-level actions:

| Term | Pages |
|---|---|
| **"Ver"** | `inventario.png`, `inventario-detalle.png` (Ver movimientos), `proveedores.png` (used as `aliases` shortcut link), `recetas.png` |
| **"Abrir"** | `pedidos-board.png` (card action — "Abrir"), `pedido-detalle.png` (`Open` implied) |
| **"Detalle"** | used as a noun ("Pedido #1 — Detalle") in routes |
| **"Vista previa"** | `pedido-detalle.png` (link preview button) |

- **Severity:** P2
- **Affected pages:** 5
- **Recommended canonical pattern:** **"Abrir"** for the primary row action (already used on pedidos-board); **"Vista previa"** for read-only previews; **"Ver historial"** for time-ordered logs. Drop "Ver" as a button label.
- **Effort:** ~2 hours.

### 1.9 "Categoría" vs "Familia" vs "Etiqueta" vs "Tag"

| Term | Pages |
|---|---|
| **"Categoría"** | inventario (`inventario-nuevo.png` field), `proveedores.png` (filter chip "Sin categoría") |
| **"Familia"** | `receta-editar.png` ("Familia/Categoría" — *both* used as the same field label) |
| **"Etiqueta"** | `inventario-nuevo.png` ("Etiquetas dietéticas"), `receta-editar.png` ("Etiquetas dietarias") |
| **"Tag"** (English) | not seen in UI copy (good) |

- **Severity:** P2
- **Affected pages:** 4
- **Recommended canonical pattern:**
  - **Categoría** = high-level grouping (panificados, pastelería, packaging, etc.)
  - **Etiqueta** = free-form label (Sin TACC, Vegano, alto-costo, temporada, sub-receta).
  - **Familia** = synonym of Categoría in recipes, but → drop "Familia" — keep only "Categoría".
- **Effort:** <1 hour.

---

## 2 · CURRENCY FORMAT INCONSISTENCY

The system uses Paraguayan Guaraní (`Gs.`) as primary currency. Counts of each pattern across all 46 pages:

| Pattern | Pages | Notes |
|---|---|---|
| **`Gs. 20.000`** (period as thousand sep, period after Gs) | 25 pages | **Dominant** — accepted Paraguayan / most-LATAM convention |
| **`Gs 20.000`** (no period after Gs) | 1 page (`receta-editar.png` ×1) | Likely transcription inconsistency |
| **`Gs.5.000.000`** (some larger amounts use ISO-grouping) | seen in some KPI tiles | inconsistent |
| **`$ `** (US-dollar sign used in pricing context) | `pricing.png` (×1 — appears in Wholesale margin cell header as if percentage) | Should not appear — Paraguay uses `Gs.`, not `$` |
| **`₲` (Unicode Naira-ish)** | **not seen** | good |
| **`.000` dot-grouping alone (no Gs.)** | 16 pages | unlabeled amounts in many defects |

**Specific concerns:**

- **Severity:** P1 (locale risk; financial reporting consequences)
- **Affected pages:** 36 of 46 mention currency in some form
- **Recommended canonical pattern:**
  1. Always `Gs. 1.234.567` with thousands separator and final period.
  2. Right-align all currency columns.
  3. For amounts <100 (e.g., Gs. 60 cost) show without separator: `Gs. 60`.
  4. Two-decimal precision: `Gs. 20.000,50` (European/LATAM convention used in PY accounting).
  5. Implement an `i18n.formatMoney(n)` helper in the frontend; one source of truth.
  6. The `$` in `pricing.png` "Wholesale Gs. (+40%)" header is a bug — `Gs.` only.
- **Effort:** ~4 hours (find/replace + introduce `formatMoney` helper).

**Notable currency-content drift:**
- `pricing.png` shows tip text "Labor: Gs.25,000/h, Packaging: Gs.1,500/unit (configurable)" — that uses *comma* as thousand separator (US convention), inconsistent with the rest of the same page ("Cost total Gs." which uses *period*). Within-page inconsistency.
- `wishlist.png` KPI "Inversión total Gs. 0 · Pendiente Gs. 0" — currency attached to label, not amount. Cosmetic inconsistency.

---

## 3 · DATE FORMAT INCONSISTENCY

| Format | Pages | Notes |
|---|---|---|
| **`dd/mm/yyyy`** (e.g., `27/09/2026`) | `eod.png`, `inicio.png`, `pedido-detalle.png` (×2), `pedido-duplicate.png` (×2), `pedidos-nuevo.png` (×2 in placeholder), `pedidos.png` (×2), `reportes-top-productos.png` (×2) | **Dominant in display** |
| **`yyyy-mm-dd`** (e.g., `2026-09-27`) | `inventario-editar.png`, `ops-status.png` (×2), `pedido-detalle.png` (×1 — internal use), `pedido-duplicate.png` (×1), `pedidos-board.png` (×1 — channel pill), `pedidos-nuevo.png` (×1 — placeholder default), `produccion.png` (×1) | Dominant in *internal* state and channel pills |
| **`mm/dd/yyyy`** (US placeholders) | `inventario-nuevo.png` (×2) | **Bug** — Paraguay is `dd/mm/yyyy` |
| **`dd/mm/aaaa`** (Spanish placeholder) | `inventario-nuevo.png` (×2) | Subset's Spanish placeholders match Paraguayan expectation; consistent with display |
| **`Sep 27, 2026`** | not seen in UI copy | Good |
| **`27 de sep`** | seen in `inicio.png` subtitle ("domingo 27 sep 2026") |
| **`ui-date`** | `reportes-iva.png` (×3), `reportes-top-productos.png` (×2), `settings.png`, `ventas.png` — implementation reference to the shared date-picker component |

- **Severity:** P0 (internationalization bug + `--` placeholder mix)
- **Affected pages:** 17 of 46
- **Recommended canonical pattern:**
  1. **Display:** `dd/mm/aaaa` (matches Paraguayan norm).
  2. **Form inputs:** use `ui-date` component (already in use) with the Spanish locale bundle.
  3. **API / database:** ISO 8601 `yyyy-mm-dd` (internally — not visible to user).
  4. Update all HTML `<input type="date">` placeholder text from `mm/dd/yyyy` (browser default) to `dd/mm/aaaa`.
  5. Add an E2E test that submits a form with each supported format and verifies it parses correctly.
- **Effort:** ~4 hours for placeholder + format helper; <1 hour for ui-date locale.

**Specific bugs:**
- **`inventario-nuevo.png` Fecha de apertura placeholder is `mm/dd/yyyy`** but other form fields around it use `dd/mm/aaaa`. In-page inconsistency.
- **`pedido-detalle.png` mixes** `27/09/2026` in the card header with `2026-09-27` in the helper text "Transiciones permitidas". Pick one.
- **`pedidos-board.png` uses `27/09`** in the main row but `2026-09-27` in "para" date. Within-page inconsistency.

---

## 4 · STATUS PILLS — vocabulary + color

Five pages mix Spanish and English status labels:

| Page | Spanish labels | English labels (BUG) |
|---|---|---|
| `pedido-detalle.png` | Pendiente, Confirmado, Cancelado, Entregado | **"pending"** (×5), **"confirmed"** (×4), **"cancelled"** (×3) |
| `pedidos-board.png` | Pendiente, En preparación, Listos para retiro, Cancelado, En entrega, Entregado | **"pending"** (×1) |
| `pedidos.png` | Pendiente, Listo, Entregado | **"pending"** (×1), **"confirmed"** (×1) |
| `produccion.png` | Pendiente, En curso, Listo, Cancelado, Suficiente | **"pending"** (×2), **"confirmed"** (×1) |
| `receta-editar.png` | — | **"pending"** (×1) |

**Note:** in several cases the English word appears in the *helper text* of an otherwise Spanish UI ("Transiciones permitidas: pending → cancelled, confirmed"), which is the worst kind of leak because the helper is supposed to clarify, not confuse.

- **Severity:** P0 (i18n, brand trust)
- **Affected pages:** 5
- **Recommended canonical vocabulary:**

| State | Label | Color | Icon |
|---|---|---|---|
| Initial state (waiting for confirmation) | **Pendiente** | amber/yellow | clock |
| Ready to produce | **Confirmado** | blue | check-circle |
| In progress | **En preparación** | purple | loading |
| Ready for pickup | **Listo para retiro** | green | package |
| Picked up / delivered | **Entregado** | gray | check |
| Cancelled | **Cancelado** | red | x-circle |

- **Effort:** ~2 hours for label replacement; ~4 hours for icon library + color tokens (already in design system).

---

## 5 · EMPTY STATES — three buckets

| Quality | Pages | Pattern |
|---|---|---|
| **Good** (clear + actionable) | `suppliers.png`, `recetas.png` ("Aún no tenés recetas"), `inventario-movimientos.png` ("Sin movimientos registrados" + Reg. CTA), `pedidos-board.png` board, `shopping-list.png` ("Lista vacía" + Plan link + tip), `auditoria.png` ("No hay entradas" + retention card), `ventas.png`, `dashboard.png` ("Aún no tenés ventas" + Reg. primera venta), `inventario-detalle.png` Variantes ("Sin variantes registradas"), `inventario.png` ("Aún no tenés ingredientes" implied) | Icon + headline + subcopy + primary CTA (orange) + secondary tip |
| **Mediocre** (some copy, weak CTA) | `inventario.png` (just table is empty, no banner), `wishlist.png` ("Cargá o sincronizá artículos" — not a button), `riesgos.png` (4 zeros only), `bank.png` ("+ Agregar movimiento manualmente" collapsed by default), `pricing.png` (rows show 0 with no message), `reportes-iva.png` (empty state but no card), `reportes-top-productos.png` (no card), `proveedores-alias.png` (no card) | Caption or one-line CTA only; not a card |
| **Broken** | `proveedores-alias.png` and `suppliers-dup.png` are **byte-identical to `suppliers.png`** empty state (P0 — the orphan routes render the wrong page), `vs-mercado.png` ("—" cells 3 of 5), `reorder.png` (Tendencia column shows "—" — silent failure, not empty state), `inventario-editar.png` (Nombre shown as slug — not empty but data-quality bug) | Wrong page renders |

**Notable cross-page inconsistencies:**
- Same concept "sin proveedores" has **3 different visual treatments** (`suppliers.png` rich, `suppliers-dup.png` rich but copy identical to suppliers, `proveedores-alias.png` rich but copy identical to suppliers). All three are essentially the same page render.
- "—" appears as silent failure in 7+ pages (`reorder.png`, `inventario-movimientos.png`, `produccion.png`, `receta-editar.png`, `vs-mercado.png`, `vs-mercado-editar.png`, `reportes-iva.png`).
- `start a new flujo` empty state appears in `productos.png` only with sub-card "Primeros pasos" — good pattern, but not reused.

- **Severity:** P1 (becomes P0 for proveedores-dup/proveedores-alias — broken routes)
- **Affected pages:** 26 of 46
- **Recommended canonical pattern:**
  ```html
  <EmptyState
    icon="package"
    title="Sin proveedores todavía"
    description="Agregá proveedores para poder contactarlos desde la página de reorden."
    primaryAction={{ label: "Agregar el primero", href: "/proveedores/nuevo" }}
    secondaryAction={{ label: "Importar desde CSV", href: "/proveedores/importar" }}
    tip="Los proveedores te permiten recibir cotizaciones y registrar compras." />
  ```
  Centered card, 320px max-width, vertical CTA stack on mobile, inline-H on desktop. Replace `—` with explicit `No hay datos` in muted text + a "Generar" CTA when computation is needed.
- **Effort:** ~6 hours to build `<EmptyState>` + audit all 26.

---

## 6 · LOADING / SKELETON STATES

Pages that document a loading state somewhere:

| Page | Loading affordance |
|---|---|
| `dashboard.png` | "Loading" + "skeleton" (table skeleton tiles) |
| `inventario-nuevo.png` | "loading state" (mentioned in defects) |
| `inventario.png` | "cargando" (Save button caption while saving) |
| `login.png` | Loading state + spinner |
| `pedidos-nuevo.png` | spinner + loading (no specific placement) |
| `productos-nuevo.png` | spinner (no specific placement) |
| `settings.png` | spinner |

Pages with **NO** loading state mentioned: 39 of 46 — most pages either don't have async actions or rely on browser default rendering.

- **Severity:** P1
- **Affected pages:** 7 explicit, 39 missing
- **Recommended canonical pattern:** Adopt a `<Skeleton>` component with named slots (`<SkeletonRow>`, `<SkeletonCard>`, `<SkeletonTable>`). Reduce to bar with subtle shimmer animation (no live spinner for >500ms — research shows spinner-by-itself feels broken after 1s).
- **Effort:** ~4 hours (component + audit 39 pages).

---

## 7 · ERROR STATES — 500/404/validation

500 references: 13 pages mention "500" or "Algo salió mal":

| Page | 500 mentions | Comment |
|---|---|---|
| `pedido-stock-preview.png` | 7 | **The page IS the 500** — entire feature unusable (P0) |
| `vs-mercado-editar.png` | 7 | P0 — same pattern |
| `ops-status.png` | 4 | Diagnostic page (expected to show 500s in a list, ok) |
| `pricing.png` | 2 | Edit form has validation |
| `reportes-iva.png` | 2 | Edit form |
| `receta-editar.png` | 2 | Edit form |
| `pedido-detalle.png` | 2 | P0 — "Ver stock antes de cumplir" leads to 500 (already documented) |
| `auditoria.png` | 1 | — |
| `bank.png` | 1 | — |
| `inicio.png` | 1 | — |
| `inventario-editar.png` | 1 | — |
| `pedidos-nuevo.png` | 1 | — |
| `productos.png` | 1 | — |
| `wishlist.png` | 1 | — |

**Only `eod.png` and `reportes-iva.png` mention "404"** explicitly (1 each). Most pages have no defined 404 — they probably reuse 500.

**Validation mentions:** 9 pages (`excel.png`, `inventario-nuevo.png`, `pedidos-nuevo.png`, `produccion-planner.png`, `productos-nuevo.png` × 2, `recetas-nueva.png`, `reportes-top-productos.png`, `settings.png` × 5, `supplier-nuevo.png`).

- **Severity:** P0 (silent failures dominate)
- **Affected pages:** 13
- **Recommended canonical pattern:**
  - Build `<ErrorState code="500">` with slots: `title`, `description`, `referenceCode` (system-rendered hash), `primaryAction` (Retry), `secondaryAction` (Go home), `devDetails` (collapsible stack trace in non-prod).
  - Build `<ErrorState code="404">` with `primaryAction: "Volver al inicio"`.
  - Validation errors rendered as inline red border + text below field (not toast) + form-level summary at top.
  - All error paths go through Sentry/equivalent with reference code shown to the user.
- **Effort:** ~1 day (component + retry wrapper).

---

## 8 · CONFIRMATION PATTERNS — destructive actions

Pages with destructive actions: 17 of 46 (Cancelar, Archivar, Eliminar, remove, delete).

| Action | Pages | Confirmation? |
|---|---|---|
| "Cancelar" pedido | `pedido-detalle.png` (×3), `pedidos.png` (×4), `pedidos-nuevo.png` (×2), `pedidos-board.png` (×2 implied), `pedido-duplicate.png` (×1), `productos-nuevo.png` (×1), `receta-editar.png`, `supplier-nuevo.png` (×2) | **None documented** — P1 (most don't confirm before canceling) |
| "Eliminar" data | `auditoria.png` ("Eliminar entradas de más de 1 año" — red button, no count), `inventario.png` (Archivar/Eliminar bulk), `settings-catalog.png` (×6 — delete operations) | Only `auditoria.png` mentions "confirm modal" was needed (current: no modal). All others: **no confirmation** |
| "remove" (English) | `proveedores-alias.png` (×3), `reportes-iva.png`, `recetas.png`, `pedidos-board.png`, `productos.png` | **English word in destructive button label** — should be "Quitar" or "Eliminar" |
| "delete" (English) | `auditoria.png` (×5), `dashboard.png`, `inventario-editar.png`, `inventario.png`, `receta-editar.png`, `reportes-iva.png`, `settings-catalog.png` (×6), `supplier-nuevo.png` | Same — mixed with the Spanish ones |

- **Severity:** P0 (destructive actions without confirm = data loss risk)
- **Affected pages:** 17 with destructive actions, 2 with `confirm modal` mentioned (only `auditoria.png` and `suppliers-dup.png`)
- **Recommended canonical pattern:**
  1. **Destructive actions** (Cancel pedido, Eliminar, Archivar, merge suppliers) → **modal confirm** with: title, description (what happens), the entity name in plain language, "Cancelar" / "Confirmar" buttons. Modal must require a deliberate second click — no dismissable-by-clicking-outside for "Eliminar entradas de más de 1 año".
  2. **Soft destructive** ("Quitar fila" in items table, "Cerrar este canal") → inline confirm with countdown button ("Confirmar (3s)").
  3. **Non-destructive** (close modal, cancel form) → no confirm.
  4. Bulk actions → multi-row modal listing each row + "Confirmar N eliminaciones".
  5. The "Eliminar entradas de más de 1 año" red button (auditoria) MUST show: "Vas a eliminar X entradas de auditoría de más de 1 año. Esta acción es irreversible. [Escribí ELIMINAR para confirmar]"
- **Effort:** ~6 hours (component + audit + update all 17 pages).

---

## 9 · NAVIGATION PATTERNS

**Breadcrumbs appear in only 4 pages** that explicitly mention them:
- `inventario-editar.png` — "Inicio › Inventario › #1 › Editar"
- `inventario-movimientos.png` — "Inicio › Inventario › #1 › Movimientos"
- `reportes-iva.png` — yes
- `suppliers.png` — "Inicio › Proveedores"

**No breadcrumbs documented on the other 42 pages.**

**Active nav state:** consistent (mentioned for `proveedores` and `produccion` only). Other pages inherit the sidebar, so likely consistent but unverified in the audits.

**Back-links / "Volver" links:**
- `inventario-detalle.png` has "Volver al inventario"
- `pedido-detalle.png` has "Volver al listado"
- `pedidos-board.png` has "← Volver a pedidos"
- `produccion-planner.png` has "← Volver a Producción"
- `pedidos.png` — implied
- `excel.png`, `guia.png`, `login.png`, `dashboard.png` — no back-link (probably intentionally)

- **Severity:** P2 (navigation works without breadcrumb on small systems, but at 46 pages the cost of disorientation grows)
- **Affected pages:** 4 with explicit breadcrumbs, 42 without
- **Recommended canonical pattern:**
  1. **Always render breadcrumbs** on detail/edit/secondary pages.
  2. Format: `Inicio › Sección › Subsección › [Entidad]`.
  3. Last segment is **not** a link (current page).
  4. Sticky on scroll.
  5. Use the same pattern from `inventario-editar.png` and `inventario-movimientos.png` (those two are good examples to copy).
- **Effort:** ~3 hours (template + audit).

---

## 10 · BUTTON HIERARCHY

| Pattern | Pages documented | Visual treatment |
|---|---|---|
| Orange filled (primary) | Most pages — primary CTA uses orange fill (e.g., "Calcular necesidad", "Reponer", "Confirmar", "Crear pedido", "✓ Crear pedido", "Guardar receta", "+ Guardar movimiento", "Generar pedido por WhatsApp", "+ Agregar variante") | **Strong consistency** ✅ |
| Outline / ghost (secondary) | `inventario-movimientos.png`, `pedido-detalle.png`, `pedido-stock-preview.png`, `pedidos-nuevo.png`, `supplier-nuevo.png` | Generally consistent ✅ |
| Text-only / link (tertiary) | `pedido-detalle.png` ("Duplicar"), `pedidos.png` ("Volver"), `proveedores-alias.png` | Used for low-priority actions |
| Red outline (destructive) | Only seen on `pedido-detalle.png` ("Cancelar") and `pedidos-nuevo.png` ("Quitar") — **2 of 17 pages with destructive actions** | **Inconsistent** — most destructive actions are not visually marked |
| **Danger / "Eliminar" / "Delete"** | `auditoria.png` (red button), `inventario.png` (delete row action — visual treatment not documented), `settings-catalog.png` (×6) | Mostly neutral — **bug**: should be red outline |
| **Filled orange primary** at bottom-right | `inventario-nuevo.png`, `receta-editar.png`, `reportes-iva.png`, `settings.png` | Bottom-right (consistent) |

- **Severity:** P1
- **Affected pages:** 17 with destructive actions, ~36 with primary CTAs
- **Recommended canonical pattern (3 tiers + 1 destructive):**
  | Tier | Style | Examples |
  |---|---|---|
  | **Primary** | orange fill (orange-500), white text, shadow-sm | Guardar, Crear, Confirmar, Generar pedido |
  | **Secondary** | white fill, orange-500 border, orange-500 text | Cancelar (when alongside primary), Vista previa, Filtrar |
  | **Tertiary** | transparent, orange-500 text, hover underline | Volver, Duplicar, Ver detalle, Edit |
  | **Destructive** | transparent fill, red-500 border, red-500 text (red-500 fill when <10% chance of accidental click) | Eliminar, Archivar, Cancelar pedido |
  | **Destructive primary** | red-500 fill, white text | "Eliminar entradas de más de 1 año" (auditoria) — only when the action is irreversible AND the button is visually loud |

  Add `data-variant="primary|secondary|tertiary|destructive"` attribute for scanning.
- **Effort:** ~6 hours (define tokens + audit + design system update).

---

## 11 · KEYBOARD SHORTCUTS — fragmentary

| Shortcut | Pages documented | Notes |
|---|---|---|
| **`⌘K` / `Cmd+K`** (global search) | `reportes.png`, `suppliers.png`, `ventas.png` | Most likely the global command palette — mentioned as visible badge |
| **`⌘N` / `Cmd+N` (new entity)** | `receta-editar.png`, `reportes.png`, `suppliers.png`, `inventario.png` | Wishlist on `wishlist.png`; documented as "new item from anywhere" |
| **`⌘S` (save)** | `inventario-editar.png`, `receta-editar.png` | Only form-saving |
| **`Esc` (close modal)** | not documented | presumably default browser behavior |
| **`/` (focus search)** | `wishlist.png`, `recetas.png` (wishlist only) | not global |
| **`Space` (toggle checkbox)** | `shopping-list.png` | page-local only |
| **`Cmd+Enter` (mark all)** | `shopping-list.png` | page-local |
| **`j`/`k` (row nav)** | only in the wishlist of `inventario.png` | not implemented |
| **`?` (keyboard shortcut palette)** | seen in `?` placeholder text in `inventario.png` ("Buscar por nombre…") — implies help | not implemented |

- **Severity:** P2 (annoyance, not breaking)
- **Affected pages:** 16 with shortcut mentions, but no single master map
- **Recommended canonical pattern:** Publish a single `/ayuda/atajos` page with the full map:

  | Shortcut | Action | Scopes |
  |---|---|---|
  | **`⌘K`** | Open command palette | Global |
  | **`⌘N`** | New entity (context-aware) | Global |
  | **`⌘S`** | Save current form | When form is focused |
  | **`Esc`** | Close modal/cancel edit | Modal context |
  | **`/`** | Focus search | List pages |
  | **`j` / `k`** | Next/prev row | Kanban (pedidos-board) |
  | **`Enter`** | Submit / advance | Form / KDS |
  | **`?`** | Show shortcut palette | Global |
  | **`g i`** / **`g p`** / **`g r`** | Jump to Inicio / Pedidos / Recetas | Global (Gmail-style) |

  Hint badge on every primary action button: `Guardar [⌘S]`.
- **Effort:** ~1 day (palette component + scope wiring + shortcut map page).

---

## 12 · ACCESSIBILITY

| Concern | Pages documented | Notes |
|---|---|---|
| Color contrast on dark backgrounds | not measured | most CTA labels in white-on-orange need to be tested ≥ 4.5:1 |
| Focus indicators | not visible in any page audit | **Likely missing** — no `:focus-visible` rings documented |
| `aria-live` on empty-state CTA | only `suppliers.png` | 1 of 46 |
| Screen-reader labels on icon-only buttons | mentioned for `wishlist.png`, but not audited | unclear how many icon buttons lack `aria-label` |
| Status pills with color-only encoding | present on every page (green/red/amber) | **Color-only** — needs redundant text/icon for color-blind users |
| Kanban keyboard navigation | `pedidos-board.png` has zero keyboard affordance documented | drag-and-drop alone is inaccessible |
| Table `<th scope>` | stated as "assumed; flag if missing" in batch3 cross-cutting | not verified |
| Form `<label for>` associations | "all fields have associations" (batch2 cross-cutting) | good if true, but not verified per-page |
| Required-field `aria-required` | only `inventario-nuevo.png` mentions; other forms don't | inconsistent |

- **Severity:** P1 (a11y is law in many markets; Latin America trending)
- **Affected pages:** all 46 (systemic concern)
- **Recommended canonical pattern:**
  1. **`:focus-visible` ring** on every interactive element — 2px solid orange-500, 2px offset.
  2. **`aria-label`** on every icon-only button (Magnifier, Plus, Pencil).
  3. **Status pills** = color + icon + text. Never color alone.
  4. **`aria-live="polite"`** on empty-state success and on toast.
  5. **`aria-required="true"`** + `<span class="req" aria-hidden="true">*</span>` for required fields.
  6. **Keyboard support** on KDS: arrow keys move focus across cards, Space picks up, arrow drops.
  7. **Skip-to-content** link at the top of every page (latent WCAG 2.4.1).
- **Effort:** ~2 weeks (audit + tokens + design-system updates + per-page fixes). **Do as a dedicated sprint.**

---

## SUMMARY OF EFFORT

| Priority | Item | Effort | Risk if deferred |
|---|---|---|---|
| **P0** | 1 (terminology product/receta) | ~1 day | Users confuse product/receta — orders get wrong price |
| **P0** | 2 (date format) | ~4 hours | Compliance reports ingest wrong dates |
| **P0** | 4 (status pill i18n) | ~2 hours label + 4h icons | Brand breaks on first demo |
| **P0** | 7 (slug-as-display-name) | ~1 day (model + 9 pages) | Internal screenshots leak DB ids |
| **P0** | 8 empty state (suppliers-dup/alias) | ~2 hours | Orphan routes render wrong page |
| **P1** | 3 (voseo vs infinitive) | ~2 hours | Cosmetic but signals quality |
| **P1** | 5 (toast/feedback) | ~6 hours | Silent failures across 14 pages |
| **P1** | 6 (currency format) | ~4 hours | Financial reporting wrong-format |
| **P1** | 8 empty states (canonical) | ~6 hours | Inconsistent UX, drop-off on first-run |
| **P1** | 10 (button hierarchy) | ~6 hours | Destructive actions without red |
| **P1** | 12 a11y | ~2 weeks | Legal exposure; broken KDS for some users |
| **P2** | 9 (breadcrumbs) | ~3 hours | Disorientation on 42 pages |
| **P2** | 11 (shortcut map) | ~1 day | Power users complain |
| **P2** | Other terminology (mostrador, cierre, comprobante, ingrediente, etc.) | ~2 hours each | Minor brand dilution |

**Total critical-path: ~1.5 weeks of focused design + dev work** to bring 46 pages into a consistent, accessible state.

---

## Recommended order of operations

1. **Week 1 — quick wins (P1)**: define glossary + currency helper + status pill vocab; commit code; replace strings in templates (touches ~36 pages automatically).
2. **Week 1 cont. — P0 defects**: slug-as-display-name (model fix), date format (placeholder + component), proveedores-dup/alias (verify routes), and product/receta distinction.
3. **Week 2 — structural**: `<EmptyState>`, `<ErrorState>`, `<ConfirmModal>`, `<Toast>`, design tokens for buttons.
4. **Week 3 — a11y sprint**: focus rings, ARIA, KDS keyboard, contrast audit.

After this 3-week pass the 46 pages should be in a publishable state; further pages added afterwards inherit the canonical patterns.

---

*Cross-cutting audit generated 2026-09-27 from*
- `/tmp/designer-drop/design-plans-2026-09-27.md` (18 pages)
- `/tmp/designer-drop/audit-batch2-prod.md` (14 pages)
- `/tmp/designer-drop/audit-batch3-reports.md` (14 pages)

*46 pages total. All severity assignments are based on cross-page patterns, not per-page defects (those are documented in the source audits).*
