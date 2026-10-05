# Sazón — UX/UI Principal Audit (Batch 2: Inventory, Production, Orders, Recipes)

**Auditor role:** Senior UX/UI Principal + Lead QA Architect
**Scope:** 14 canonical pages from `docs/user-guide/screenshots/all-pages/`
**Personas analyzed per page:** counter staff · owner-finance · production-baker · new user · auditor
**Methodology:** Each persona gets Now / Missing / Top add. Plus a complete design wishlist, QoL touches, and a P0/P1/P2 defect log per page.

> Anomalies noted up front:
> - `inventario-variantes.png` actually renders the **ingredient detail** page (variants section is just the empty-state card inside it). Analysis covers it as the detail page with the empty Variantes card.
> - `pedido-stock-preview.png` renders a **500 "Algo salió mal"** page instead of the stock preview. The wishlist describes what the page *should* be; the defect log captures what actually shipped.
> - `pedido-duplicate.png` shows the **duplicate order's detail page** (Pedido #2) after duplication, not the pre-filled "duplicate" form — i.e. the user has already clicked through. Audit covers it as the duplicated-order landing page.
> - All timestamps in the screenshots show `domingo 27 sep 2026 · 15:24` (Sunday 3:24 PM) which is fine, but the **promised date** in orders shows `27/09/2026` (today). Side note: production board targets `2026-09-28` (tomorrow). Worth flagging consistency.

---

## Page index
1. [inventario.png — Inventario de ingredientes](#1-inventariopng)
2. [inventario-nuevo.png — Nuevo ingrediente](#2-inventario-nuevopng)
3. [inventario-editar.png — Editar ingrediente](#3-inventario-editarpng)
4. [inventario-detalle.png — Ingrediente #1](#4-inventario-detallepng)
5. [inventario-movimientos.png — Movimientos de stock](#5-inventario-movimientospng)
6. [inventario-variantes.png — Variantes (page actually = ingredient detail)](#6-inventario-variantespng)
7. [produccion.png — Producción (board)](#7-produccionpng)
8. [produccion-planner.png — Plan manual](#8-produccion-plannerpng)
9. [pedidos-board.png — Cocina KDS / pedidos del día](#9-pedidos-boardpng)
10. [pedidos-nuevo.png — Nuevo pedido](#10-pedidos-nuevopng)
11. [pedido-detalle.png — Pedido #1](#11-pedido-detallepng)
12. [pedido-stock-preview.png — Vista de stock (500 error in screenshot)](#12-pedido-stock-previewpng)
13. [pedido-duplicate.png — Pedido #2 (post-duplicate)](#13-pedido-duplicatepng)
14. [receta-editar.png — Editar receta](#14-receta-editarpng)

---

## 1. inventario.png
**Route:** Inventario de ingredientes (Ingredient Inventory list)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Top header strip with global search (`?`), dark/light toggle, "+ Nuevo" FAB. Left rail with Operación / Catálogo / Compras / Ventas y Clientes / Finanzas sections. Page title "Inventario de ingredientes" with subtitle "Gestión de stock, costos unitarios y control de alérgenos". 4 KPI tiles: Total ingredientes (2 activos), Stock crítico (1 requiere compra), Valor de inventario (Gs. 307.200 a precio de compra), Sin costo cargado (0). Filter bar: text search "Buscar por nombre…" + Categoría / Estado / Alérgenos dropdowns + orange "Filtrar" button. Table with columns Nombre (with category pill), Unidad, Stock actual, Stock mínimo, Precio compra (Gs.), Estado (OK bar or "Stock bajo" warning), per-row actions: Ver / Ajustar / Editar / Movimientos. Counter sees a clean, scannable layout.
- **Missing:** No bulk action (select rows + adjust/delete/export). No "Quick adjust" inline cell editor (must open modal). No "last purchase price" reference next to current price. No supplier column. No "expiring soon" indicator. No photo/thumbnail. No row-level "this ingredient is in N active recipes" hint.
- **Top add:** A **"Stock bajo" filter chip pre-applied** when any ingredient is critical, plus a one-click "Generar pedido de compra" CTA on the Stock crítico tile that drops the user into the Lista de compras with these SKUs pre-filled. This converts a passive count ("1 requiere compra") into an action.

### Owner-finance (hat 2)
- **Now:** Total inventory value tile (Gs. 307.200), "Sin costo cargado" tile (0 — good). Stock crítico count visible. Per-row precio compra column.
- **Missing:** No cost-trend chart. No "valor por categoría" breakdown. No "consumo semanal en Gs." running counter. No FX or "precio vs mercado" tile inline. No "margen perdido por merma" tile. No CSV/excel download for the cost view (only generic CSV export). No cost-alert threshold ("este ingrediente subió > X% esta semana").
- **Top add:** A **"Costo total semanal" sparkline tile** (last 8 weeks) and a **"Variación % vs semana anterior"** beside it. Owner needs to *feel* cost drift without opening Reports.

### Production-baker (hat 3)
- **Now:** Stock actual vs mínimo is exactly what they need at a glance. Estado column shows OK / Stock bajo as text + a thin green/red progress bar. "Ajustar" and "Movimientos" per row.
- **Missing:** No unit conversion hint (kg ↔ g). No "duración estimada" (how many days the current stock will last based on avg daily usage). No "usado en producción hoy" indicator. No quick "+entrada / -salida" tap target. The bar chart under Estado is nice but tiny and hard to read at 100% zoom.
- **Top add:** A **"Días restantes"** column computed from average daily consumption. The detail page already has this forecast; surfacing it on the list lets the baker triage in one glance.

### New user (hat 4)
- **Now:** Clear page title + subtitle. Subtitle "Gestión de stock, costos unitarios y control de alérgenos" frames what the page is for. Search + filter affordances are obvious.
- **Missing:** No onboarding tooltip explaining "Stock crítico = por debajo del mínimo, requiere compra". No "?" help link on the tile definitions. No sample data preview ("así se ve con datos reales"). The "Sin costo cargado" tile is opaque — new user doesn't know what "costo cargado" means.
- **Top add:** A **first-run empty-state banner** ("Empezá cargando tu primer ingrediente" + CTA) when the list is empty, instead of just an empty table.

### Auditor (hat 5)
- **Now:** Each row shows current stock + minimum + price. Estado badge.
- **Missing:** No "last modified" timestamp. No "created by / modified by" column. No "reorder point" vs "stock mínimo" visibility. No audit trail link from the row. No "porcentaje de stock" (current/min). No history of price changes.
- **Top add:** A **"Última modificación · por"** column with relative timestamp and avatar/initials — instantly gives auditor a chain of custody.

### Complete design wishlist
- **KPI tiles:** add "Valor total", "Consumo 7d (Gs.)", "Días de cobertura promedio", "Ingredientes con alerta de vencimiento".
- **Quick actions:** "+ Reposición rápida" (numeric input + reason + submit, inline row), "Duplicar ingrediente", "Marcar como archivado".
- **Bulk select** with toolbar (Ajustar / Archivar / Exportar / Eliminar).
- **Saved views** ("Mis críticos", "Sin gluten", "Alto costo", "Sin foto").
- **Inline alerts** when an ingredient used in active recipes drops below safety stock (link to "Ver recetas afectadas").
- **Density toggle** (compact / comfortable / spacious).
- **Mini sparkline** per row showing 30-day consumption.
- **Tag chips** (alérgeno, categoría, proveedor) visible inline.
- **Hover preview** with thumbnail + last 5 movements + recipes using it.
- **Sticky filter bar** that collapses on scroll.
- **URL-state persistence** of filters (so you can bookmark "Stock crítico").
- **Keyboard hints** (j/k to navigate rows, / to focus search, ⌘N = new ingredient).
- **Export PDF** for compliance (price list signed).

### Quality-of-life touches
- Counter pill on "Stock crítico" tile in soft red border instead of just number.
- Status bar under Estado column should be thick enough to read — current 4px is too thin.
- Right-click row → context menu (Editar, Ajustar, Ver historial, Duplicar).
- Inline rename of Nombre cell (double-click → edit).
- Tooltip on "Sin costo cargado" tile explaining what it means.
- Subtle row hover highlight.
- Smooth count-up animation on KPI tiles.
- Filter chips show "Filtros activos: … ×" with one-click clear.
- "Exportar CSV" respects current filters (doesn't dump everything).
- Microcopy: "requieren compra →" already has the arrow — great.

### Defects (P0/P1/P2)
- **P1** — "Ingredientes 415de24c" is shown as a name (looks like a slug was used as the display name). Either show the friendly name or fix the seed.
- **P1** — The SKU/name truncation: "Levadura seca" wraps awkwardly below the pill, while "Ingrediente 415de24c" wraps below its pill too. Two-line wrapping on the Nombre cell is visually noisy.
- **P1** — "Estado" column for the OK row shows a tiny green bar with **no label** (no "OK" text). The pill "OK" sits separately above the bar — redundant. For "Stock bajo" the label sits on top of the bar — inconsistent.
- **P2** — "Ajustar" / "Ver" / "Editar" / "Movimientos" all use different leading icon styles (magnifier, plus, pencil-outside, none). Pick one icon family.
- **P2** — The progress bar under "Stock bajo: 0.40" shows red but has no axis/percentage (what's 100%?). A min/max bar would be more useful than a stock-level bar.
- **P2** — Subtitle "Gestión de stock, costos unitarios y control de alérgenos" mixes Spanish/English "stock". Use "existencias" or "inventario".
- **P2** — Filter dropdowns "Categoría / Estado / Alérgenos" all close after selecting — would prefer to keep open for multi-select.

---

## 2. inventario-nuevo.png
**Route:** Nuevo ingrediente (Create ingredient form)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Two-column layout. Left: Datos básicos (Nombre, Categoría, Unidad, Stock actual, Stock de apertura, Fecha de apertura, Notas). Right: Operación y cumplimiento (Stock mínimo, Punto de reorder override, Precio de compra) + a boxed "Clasificación y conservación" panel (Vida útil, Alérgenos chips, Etiquetas dietéticas chips, Cross-contamination TACC checkbox, Lead time proveedor). Save/Cancel in footer.
- **Missing:** No barcode/SKU field (auto-generated?). No "frecuencia de conteo" (cuántas veces al mes lo cuentan). No "ubicación física" (estantería A-3). No "favorito" or "destacado" toggle.
- **Top add:** A **"Ubicación física"** field (text or grid) so a counter knows exactly where to look on the shelf. Right now there's no way to know if the flour is in A-3 or B-1.

### Owner-finance (hat 2)
- **Now:** Precio de compra (Gs., por unidad) with placeholder "Dejarlo vacío si no se sabe — el sistema te avisa en Inicio". Punto de reorder (override) with helper "Si lo configuras, el sistema usa este valor en lugar del stock mínimo para las sugerencias de reorder." Lead time proveedor (días).
- **Missing:** No "último precio pagado" autofill from previous purchases. No "precio en USD" field (guaraníes vs dollar). No "IVA incluido" toggle. No "costo logístico / flete" line. No "tiempo de pago" (contado vs crédito 30d).
- **Top add:** A **"Histórico de precios" mini panel** on the right (last 3 purchases, with date and supplier) — invaluable for spotting creeping supplier costs.

### Production-baker (hat 3)
- **Now:** Unidad dropdown ("g, kg, ml, l, und") — exactly what they need. Stock de apertura ("Stock inicial cuando se cargó este ingrediente por primera vez"). Fecha de apertura. Vida útil (días). Alérgenos chips (Gluten, Lácteos, Huevos, Frutos secos, Soja, Sésamo, Sulfitos). Cross-contamination checkbox "Posible contaminación cruzada con trigo (bloquea 'sin TACC')". Lead time proveedor.
- **Missing:** No "temperatura de almacenamiento" / "humedad" fields (HACCP panel shows them on detail but not here — confusing). No "formato de empaque" (bolsa 25kg, bolsa 1kg, granel). No "rendimiento" (% merma esperada). No "fase de uso" (masa, decoración, relleno).
- **Top add:** A **"HACCP mini" collapsible section** with Temperatura / Humedad / Almacenamiento inline (otherwise bakers have to leave the form to set them later).

### New user (hat 4)
- **Now:** Every field has a helpful placeholder or example ("Ej: Harina de trigo", "Ej: Harinas, Lácteos, Aceites"). Helper text under each field ("Opcional. Para agrupar ingredientes en el inventario.", "Fecha en que se registró el stock de apertura."). Inline help ("Si no marcás ninguno queda sin declarar.").
- **Missing:** No "?" popovers with deeper explanations. No progress indicator (Step 1 of 3). No required-field markers (no asterisks anywhere — but Stock mínimo has no * either, and Name has no *). New users won't know what's required.
- **Top add:** Required-field asterisks (`*`) on Nombre, Unidad, and Stock mínimo — at minimum — plus a tiny "Required fields" footnote at the bottom.

### Auditor (hat 5)
- **Now:** Fecha de apertura captures when the ingredient was first registered. Notas is freeform. Stock de apertura creates an audit anchor.
- **Missing:** No "created by" capture (single-user system so this might be implicit). No "origen del stock" (compra, producción interna, donación). No "lote obligatorio" toggle (detail page shows it; creation form doesn't). No document attachment (factura PDF).
- **Top add:** A **"Comprobante de origen"** file input (PDF/JPG) — attach the first purchase invoice for traceability.

### Complete design wishlist
- **Tabbed layout** for 4 categories: Datos / Operación / Conservación / Proveedor. Right now everything jams into 2 columns.
- **Inline suggestions** as you type Nombre ("¿Quisiste decir 'Harina 0000'?") with one-click add.
- **"Duplicar desde existente"** button at top (clone an ingredient with similar properties).
- **Barcode scan** field (USB scanner input) with auto-fill of code + recent matches.
- **Photo upload** (camera or file) — visual identification matters in a kitchen.
- **Required-field summary** at the top of the page.
- **Save & add another** button (vs just Save) — common workflow when seeding inventory.
- **Live cost preview**: as you type Precio de compra × Stock actual = Valor total (shown live in header).
- **Cross-link** to recipes this ingredient will appear in once saved.
- **Validation feedback** in real time (red border on required but empty fields before submit).
- **"Setting reminders"** for Vida útil (auto-warn when batch approaches expiry).

### Quality-of-life touches
- The "Fecha de apertura" placeholder is `mm/dd/yyyy` — but the audience is Paraguayan (Gs. currency). Use `dd/mm/aaaa`.
- "Stock de apertura" helper ends in a colon with no value visible — looks like truncation bug.
- The "Etiquetas dietéticas" section has 7 chips but only 1 row of 6 — "Alto en proteína" sits orphaned on its own row. Reorder or wrap evenly.
- Save button says "Guardá" (with accent) — page title uses "ingrediente" (no accent on first i). Spanish uses "Guardar" (infinitive) or "Guardá" (vos) — pick one and stick to it.
- "Operación y cumplimiento" header has no border/separator from the boxed "Clasificación y conservación" — visually they merge.
- Right column ends with Lead time proveedor way down at y=1018 — the page is unbalanced. Box border under the HACCP section but nothing on left column.
- Inline question-mark icons next to technical terms (TACC, HACCP).
- Show character count next to Notas.
- Tab order: Tab should flow Nombre → Categoría → Unidad → Stock actual → Stock de apertura → Fecha → Stock mínimo → Reorder → Precio → Vida útil, not the current random order.

### Defects (P0/P1/P2)
- **P1** — **No visible required-field markers anywhere on the form.** Name is required to save, but there's no `*`, no red border on empty submit. A new user will submit and silently fail or get a generic error.
- **P1** — **No submit feedback.** "Guardá" button just sits there. No loading state, no "Saved ✓" toast, no redirect to the detail page.
- **P1** — **Stock de apertura input shows placeholder but no helper text visible at first glance** — the helper "El stock inicial cuando se cargó este ingrediente por primera vez." is faint and easy to miss.
- **P2** — **Date format `mm/dd/yyyy` for a Paraguayan audience.** Should be `dd/mm/aaaa`.
- **P2** — **"Operación y cumplimiento" + "Clasificación y conservación" both as right-column headers** with no visual hierarchy — looks like two unrelated sections.
- **P2** — **"Lead time proveedor (días)"** field is buried at the bottom of the right column with no helper text explaining how it differs from Punto de reorder.
- **P2** — **Cross-contamination checkbox label is multi-line and visually heavy** — "Posible contaminación cruzada con trigo (bloquea 'sin TACC')" wraps awkwardly.

---

## 3. inventario-editar.png
**Route:** Editar ingrediente (same form as create, pre-filled)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Same form as `inventario-nuevo`, pre-filled. Breadcrumb shows "Inicio › Inventario › #1 › Editar". Name shows "Ingrediente 415de24c" (the slug leak).
- **Missing:** No "history" sidebar showing who changed what when. No "compare to previous version". No revert. No quick "duplicate" action.
- **Top add:** A **"Cambios recientes"** collapsible at top showing diffs vs the last save (with timestamps). Counter can confirm "did I just bump the price?".

### Owner-finance (hat 2)
- **Now:** Precio de compra pre-filled with 3000. Lead time proveedor pre-filled with 3. Punto de reorder left blank (using auto).
- **Missing:** No "previous price" reference. No "this price is X% higher than last purchase" warning.
- **Top add:** An **inline "Δ vs última compra"** badge next to Precio de compra ("+12% vs 2026-08-15") — surfaces creeping costs without forcing an audit.

### Production-baker (hat 3)
- **Now:** Unidad dropdown still empty ("Seleccioná unidad") despite a record existing — suggests data quality bug. Stock actual = 100.00 (live data).
- **Missing:** No "last used in recipe" indicator.
- **Top add:** Show **"Usado en 1 receta activa"** link under the Categoría dropdown, with a one-click jump.

### New user (hat 4)
- **Now:** Same form, same helpful placeholders, but pre-filled values give a model of what good data looks like.
- **Missing:** No "What's locked vs editable" hint. A new user might wonder if changing the Name breaks linked recipes.
- **Top add:** A **"Renombrar no rompe recetas vinculadas — sólo cambia cómo se muestra"** reassurance hint near the Nombre field.

### Auditor (hat 5)
- **Now:** Fecha de apertura is empty in this record. Stock de apertura is empty.
- **Missing:** No "who created this, when" footer. No "audit log" link. No diff history.
- **Top add:** A **"Log de auditoría"** drawer showing every change with timestamp + user (even if user = owner).

### Complete design wishlist
- **All of inventario-nuevo's wishlist**, plus:
- **Diff view** before save ("Stock actual: 100 → 105, Precio: 3000 → 3500").
- **Archive / Soft-delete** button in danger zone at bottom.
- **"View as JSON"** for power users / auditors.
- **Confirm dialog** for Nombre change (warns about impact on recipes).
- **Inline stock adjust** at the top ("Ajustar stock sin guardar el resto").

### Quality-of-life touches
- "Save and stay on this page" (instead of redirect to detail) — common edit pattern.
- Show keyboard shortcut to save (⌘S).
- Highlight fields that were modified in this session (subtle yellow tint).
- "Save & duplicate as new ingredient" for variants.
- Undo button (last 5 edits).
- Show "Last saved at HH:MM" near Guardá.
- Warn on navigation if unsaved changes (browser beforeunload).

### Defects (P0/P1/P2)
- **P1** — **Unidad dropdown is empty for an existing ingredient.** The data shows stock and price, but Unidad is blank. Either data-integrity bug or display bug.
- **P1** — **Name "Ingrediente 415de24c" is the slug, not a human name.** Confirms P1 from inventario list — the same record is shown with its database ID as its display name.
- **P2** — **Stock actual shows `100.00` but Stock de apertura is empty** — the "first stock on creation" concept is broken for this record. Either auto-fill from Stock actual or accept that Stock de apertura is optional.
- **P2** — **No "modified by / modified at"** anywhere on the page.
- **P2** — **No diff visualization** when editing — easy to overwrite without realizing.

---

## 4. inventario-detalle.png
**Route:** Ingrediente #1 (Ingredient detail)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Header "Ingrediente 415de24c" with "Volver al inventario" link. Right-aligned actions: "+ Ajustá stock" (orange) and "Editá ingrediente" (filled orange). Three info cards top row: **Stock actual** (Stock 100.00 kg, Stock mínimo 1.00 kg, Unidad kg, Categoría otros); **Clasificación y etiquetas** (Alérgenos "sin declarar", Dietéticas —); **Conservación (HACCP)** (Almacenamiento —, Vida útil —, Temperatura 15.0 a 25.0 °C, Humedad máx 70.0%, Lead time 3 días, Lote obligatorio No). Second row: **Precio** (Precio de compra Gs. 3.000) + **Usado en recetas** (Receta, Cantidad por batch table — 1 recipe "Receta 0da4ca66" uses 0.30 kg, with "Ver receta" link). "Ver movimientos de stock" link at right. Variantes card: empty state "Sin variantes registradas. Podés agregar variantes (marcas o tamaños) y marcar una como preferida." + "▶ Agregar variante" toggle. Pronóstico card: Stock actual 100.00 kg, Consumo promedio diario "(sin consumo reciente)", Días restantes —, Horizonte 14 días, Estado "SIN CONSUMO" badge, "▶ Ajustar horizonte de pronóstico".
- **Missing:** No usage chart over time. No "next predicted restock" date. No supplier info / last purchase date. No "share with colleague" or "print label" actions. The Variantes and Pronóstico cards are great but feel orphaned below the fold.
- **Top add:** A **"Reposición recomendada"** inline card next to Precio, with a one-click "Crear pedido de compra" button that pre-fills this SKU.

### Owner-finance (hat 2)
- **Now:** Precio de compra Gs. 3.000, Lead time 3 días, Stock actual 100 kg = Gs. 300.000 sitting in this one ingredient.
- **Missing:** No "valor en stock" computed (price × stock). No cost trend. No supplier comparison (cheaper variant from another supplier?). No "costo por porción/unidad producida" downstream link.
- **Top add:** **"Valor en stock: Gs. 300.000"** directly under Precio de compra, with sparkline of last 30 days.

### Production-baker (hat 3)
- **Now:** Stock actual + mínimo + unidad + categoría is exactly what they need. Variantes card explains brands/sizes. Pronóstico card forecasts when they'll run out. Usado en recetas shows which recipes consume this — extremely useful.
- **Missing:** No "phase" indicator (when in the day is this consumed). No "preferred variant" highlighted. The Pronóstico says "sin consumo reciente" — but there's a recipe using 0.30 kg; that should count.
- **Top add:** A **"Hoy se va a usar"** indicator at the top: "Este ingrediente se va a consumir en 1 batch hoy (0.30 kg). Stock después: 99.70 kg." Tied to today's production plan.

### New user (hat 4)
- **Now:** Page explains itself through section labels. Empty-state copy for Variantes ("Podés agregar variantes…") is friendly and instructive.
- **Missing:** No tooltips on technical fields (HACCP, TACC, Lote obligatorio). No "?" links to a glossary. The "sin declarar" badge for Alérgenos is alarming but not explained.
- **Top add:** **Inline "?" icons** with popovers: "¿Qué es TACC?" "¿Por qué importa la humedad máx?" "¿Qué significa Lote obligatorio?".

### Auditor (hat 5)
- **Now:** Conservación (HACCP) card with Almacenamiento, Vida útil, Temperatura, Humedad máx, Lead time, Lote obligatorio. Used-in-recipes table.
- **Missing:** No "last modified by / when". No "created by". No audit log of stock adjustments (have to navigate to Movimientos). No "compliance docs attached".
- **Top add:** An **"Auditoría"** section at the bottom (collapsed by default) listing every change to this ingredient with timestamp + actor.

### Complete design wishlist
- **Sticky header** with name + main actions (currently "Volver al inventario" pushes you back, but a sub-nav within the ingredient would help).
- **"Comprá más" CTA** with one-click Lista de compras entry.
- **Movimientos recent strip** — show last 3 movements inline (not just a "Ver movimientos" link).
- **Variantes quick toggle** to set "preferida" inline.
- **Recipe impact panel** — clicking a recipe name should show its full cost & yield.
- **Alérgeno banner** at top if any recipe using this ingredient claims "sin X" — explicit warning.
- **Print label** action (ZPL or PDF) for the shelf.
- **QR code** for the ingredient (scan to open this page).
- **Comments / notes thread** (collaboration).
- **Dark-mode-friendly** cards (the orange-themed Pronóstico card already hints at this).

### Quality-of-life touches
- The orange "SIN CONSUMO" badge in Pronóstico is visually loud but informative. Good.
- Pronóstico card collapsible ("▶ Ajustar horizonte de pronóstico") is a nice progressive disclosure.
- HACCP values are dash em-dashes for empty — slightly heavy visually; use lighter gray.
- Copy "Ver movimientos de stock" right-aligned to Precio card looks orphaned — should be a button.
- "Editá ingrediente" button uses "Editá" (vos) but other pages say "Editar" (infinitive). Inconsistent.
- Hover state on "Ver receta" link should be more obvious.
- Pronóstico's "Horizonte de pronóstico: 14 días" with "▶ Ajustar horizonte de pronóstico" suggests there's a control — but it's a disclosure, not a number input. Could be confusing.

### Defects (P0/P1/P2)
- **P1** — **Slug "415de24c" as the display name.** Confirms the slug-as-name bug from earlier pages. This is the **canonical detail page for this ingredient** — the bug is jarring.
- **P1** — **Pronóstico says "(sin consumo reciente)" but the ingredient IS used in a recipe (Receta 0da4ca66 uses 0.30 kg per batch).** Either the forecast is broken or it's not pulling from recipe BOMs. Either way, the value is misleading.
- **P1** — **Días restantes shows "—" but Horizonte shows 14 días.** Inconsistent states — should show "se agotaría en ~14 días" or similar.
- **P2** — **No "Ajustar stock" link in the Stock actual card itself** — the "+ Ajustá stock" lives in the page header, but a counter looking at the Stock card would expect the action inline.
- **P2** — **No "supplier" or "última compra"** anywhere. An ingredient detail page without a purchase history is incomplete.
- **P2** — **No "imagen" placeholder.** A photo helps a new baker find the right bag.
- **P2** — **Pronóstico's "(sin consumo reciente)" copy is passive** — should be actionable: "No hay consumo reciente. ¿Registrá tu primera merma?" or "Consumí este ingrediente manualmente para activar el pronóstico".

---

## 5. inventario-movimientos.png
**Route:** Movimientos de stock (Stock movements) — empty state
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Breadcrumb "Inicio › Inventario › #1 › Movimientos". Sub-header "Ingrediente 415de24c — Stock actual: 100.00 kg". Body is an empty state: bag-with-plus icon, headline "Sin movimientos registrados", subcopy "Cada entrada, salida, merma y ajuste queda asentado acá.", orange CTA "Registrá el primer ajuste".
- **Missing:** No filters (date range, type: entrada/salida/merma/ajuste, user). No export. No KPI tiles (entries this week, total merma in Gs., net change). No "recent adjustments" hint for adjacent ingredients.
- **Top add:** A **"+ Registrar movimiento"** floating action button (always visible) + a **filter strip** ("Esta semana", "Tipo", "Por usuario") that shows even on empty state.

### Owner-finance (hat 2)
- **Now:** Empty state, no financial context.
- **Missing:** No "valor perdido en mermas YTD" tile. No "consumo semanal en Gs." trend.
- **Top add:** Even on empty state, show a **mini "0 mermas · 0 ajustes · 0 entradas esta semana"** summary so the page feels alive.

### Production-baker (hat 3)
- **Now:** Empty state with friendly copy "Cada entrada, salida, merma y ajuste queda asentado acá."
- **Missing:** No "registrar consumo de producción" shortcut. No "registrar merma por desperdicio" template.
- **Top add:** A **template picker** in the empty-state CTA: "Registrá: Entrada por compra / Salida por consumo / Merma / Ajuste de conteo" — pick the common path.

### New user (hat 4)
- **Now:** Empty state is genuinely good — explains what the page is for and gives one clear action.
- **Missing:** No example of what a filled state looks like. No "registrá tu primer movimiento" tutorial walkthrough.
- **Top add:** A **"Ver ejemplo"** link that opens a screenshot/mock of a filled state for orientation.

### Auditor (hat 5)
- **Now:** Empty. No history.
- **Missing:** No way to see who made which adjustment (this will be filled in once data exists, but the audit should be visible from day 1).
- **Top add:** A **"Log completo con usuario y timestamp"** column visible from the start (column header shown even on empty state as a contract).

### Complete design wishlist
- **KPI strip** at top: Entradas · Salidas · Mermas · Ajustes (with delta vs last period).
- **Type filter chips** (Entrada, Salida, Merma, Ajuste, Transferencia).
- **Date range picker** with presets (Hoy, Esta semana, Este mes, Trimestre, Custom).
- **Per-row actions:** Edit (with audit trail), Reverse (creates compensating entry), Print receipt.
- **Bulk export** as CSV / PDF.
- **Reason/motivo** required field (currently may not be enforced).
- **User filter** (so a manager can audit a specific baker).
- **Movements linked to source** (which order consumed this? which recipe?).
- **Merma categorization** (Vencimiento, Error de producción, Robo, Desperdicio).
- **Charts**: net change over time, merma breakdown pie.

### Quality-of-life touches
- Empty-state icon (briefcase-with-plus) is generic — could be a more specific illustration (clipboard with arrow).
- "Sin movimientos registrados" is good but could be warmer: "Todavía no hay movimientos — registrá tu primer ajuste para empezar".
- The "+ Registrá el primer ajuste" CTA is in the center of an empty viewport — looks fine, but on a wide screen it'll feel lonely. Add ghost rows / example rows below the empty state.
- "100.00 kg" current stock is green — good visual reinforcement.
- The ingredient name in the sub-header is clickable (probably), but no chevron. Add one.

### Defects (P0/P1/P2)
- **P1** — **Slug "415de24c" as display name**, again. This is the 4th page in a row with the same bug.
- **P1** — **No filters / type selector on the empty state.** When the user adds their first movement, there's no UI to filter later.
- **P2** — **"Stock actual: 100.00 kg" appears twice** (once in sub-header, once at top of detail). When clicking into Movimientos, user sees the same number in two places.
- **P2** — **No "Exportar" button even on empty state.** Even an empty export is a feature.

---

## 6. inventario-variantes.png
> ⚠️ **Filename note:** the file at this path is actually the **same as the ingredient detail page** (with a sidebar overlap). The "Variantes" section is just the empty-state card within the detail page. I'm treating it as the Variantes section of the ingredient detail.

**Route:** Variantes (Variants — section of ingredient detail)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Variantes card with "Sin variantes registradas. Podés agregar variantes (marcas o tamaños) y marcar una como preferida." + "▶ Agregar variante" disclosure.
- **Missing:** No "Agregar variante" inline form visible — it's collapsed. No example of what a variant looks like. No way to quickly distinguish brands when buying.
- **Top add:** When "Agregar variante" is clicked, expand **inline** with fields Marca, Tamaño, Precio, Proveedor, Preferencia — no modal.

### Owner-finance (hat 2)
- **Now:** Empty state, no cost context.
- **Missing:** No "compare prices across variants" UI even on empty state.
- **Top add:** A teaser CTA **"¿Comprás la misma harina de dos marcas? Cargá las dos y comparamos precios"** when the section is empty.

### Production-baker (hat 3)
- **Now:** Copy explains "Podés agregar variantes (marcas o tamaños) y marcar una como preferida."
- **Missing:** No "favorite variant for this recipe" pick (would let different recipes prefer different variants).
- **Top add:** Per-recipe-variant preference (later); for now, a clear "marca preferida" toggle on the variant row.

### New user (hat 4)
- **Now:** Friendly empty-state copy. Section is discoverable.
- **Missing:** No tooltip explaining "qué es una variante" vs the parent ingredient.
- **Top add:** Inline "?" with one-sentence explainer: "Una variante es la misma harina pero de otra marca o tamaño — útil para comprar y comparar".

### Auditor (hat 5)
- **Now:** Empty.
- **Missing:** No "preferred variant audit history" (which variant was preferred when, and why changed).
- **Top add:** Audit log on the variant table once data exists.

### Complete design wishlist
- **Inline add-variant form** (no modal).
- **"Set as preferred"** radio on each variant row.
- **Price-per-unit normalized** across variants (so a 25kg bag at Gs. 150.000 is comparable to a 1kg bag at Gs. 7.000).
- **Packaging type** (bolsa, saco, botella, lata).
- **Supplier per variant** (already supported at the ingredient level? not sure — would help).
- **Stock split by variant** (variant A: 30kg, variant B: 70kg).
- **Variant photo** (helps the baker grab the right one).
- **Variant barcode**.
- **Active/archived** toggle per variant.

### Quality-of-life touches
- The disclosure "▶ Agregar variante" should animate on hover.
- Empty-state copy could be more visual — illustrate a card mockup.
- When a variant is preferred, show a star badge in the list.

### Defects (P0/P1/P2)
- **P1** — **Sidebar appears to overlap the page content** in this screenshot (the floating sidebar is mid-page, between the HACCP and Precio cards). This looks like a **z-index / sticky positioning bug**. Either the sidebar should be permanently pinned left or shouldn't appear over content. This is a P1 visual defect.
- **P2** — **Empty-state copy is good but the disclosure arrow "▶" looks old-fashioned.** Modern apps use "Add" / "+" buttons.
- **P2** — **The Variantes card is buried at the bottom** of the detail page — variants are arguably more important than Pronóstico for day-to-day work.

---

## 7. produccion.png
**Route:** Producción (Production board — single-day view)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Page title "Producción" with sub-CTA "▶ Plan manual (elegí receta + tandas)" in a soft dashed box. Tab toggle Día / Semana / Mes. Section "Para el día 2026-09-28" with a card "Pedidos pendientes para hoy (1) — US 4.4 — El cocinero ve estos pedidos antes que el plan automático. Click para abrir el detalle." Inside the card: "Pedido #1 — María López · 0981112222" with a "whatsapp" channel pill and "pending" status, item "2.0 × Producto cfaf4b47 (Gs. 10.000)". Section "Productos a producir" table with columns Producto / Cantidad / Cómo se calcula / [qty input] / [Usar] [Ver receta] — row "Producto cfaf4b47", qty 1, source "Sugerido por ventas". Section "Ingredientes necesarios" table: Ingrediente / Cantidad / Stock actual / A comprar — row "Ingrediente 415de24c" with "Suficiente" badge (green), 0.02 kg needed, 100.00 kg stock, "—" to buy.
- **Missing:** No "Drag to reschedule" / calendar grid. No per-hour timeline. No "assigned baker" column. No "time needed" estimate. No "in progress / done / hold" status on each batch.
- **Top add:** A **timeline grid** (Day / Week / Month toggle implies one — but Día shows a list, not a grid). Make Día show a vertical hour-by-hour schedule.

### Owner-finance (hat 2)
- **Now:** Suggested qty "Sugerido por ventas" gives finance traceability. Implicit link to Pedidos pendientes.
- **Missing:** No "production cost estimate" tile. No "labor cost" tile. No "expected revenue" from these batches.
- **Top add:** A **summary tile** at top: "Producción hoy: 1 batch · costo estimado Gs. 60 · venta esperada Gs. 10.000 · margen 99%". Closes the loop to revenue.

### Production-baker (hat 3)
- **Now:** This page is essentially **built for them**. Pedidos pendientes first, then Productos a producir, then Ingredientes necesarios. Sufficient / short badges are exactly what they need to triage.
- **Missing:** No "tiempo total estimado" (how long will this take?). No "asignar cocinero". No "orden sugerido" (do recipe A before B because it has longer prep time).
- **Top add:** A **"Marcar como hecho"** checkbox + **"Notificar al cliente"** link per batch. And a **start/end time estimate** per batch ("7:30 → 8:15").

### New user (hat 4)
- **Now:** Subtle onboarding: "▶ Plan manual (elegí receta + tandas)" is a discoverable CTA. The "Pedidos pendientes" card explains "El cocinero ve estos pedidos antes que el plan automático. Click para abrir el detalle."
- **Missing:** No first-run tooltip explaining "qué es producción automática vs plan manual".
- **Top add:** A **first-run modal** explaining the flow: "Producción mira qué se vendió, sugiere qué cocinar, y te dice qué ingredientes necesitás. ¿Arrancamos?"

### Auditor (hat 5)
- **Now:** No actor / timestamp on the suggestions.
- **Missing:** No "decision log" (why was this qty chosen?). No "deviation log" (when actual differed from planned).
- **Top add:** A **"Ver auditoría"** link that opens a drawer with every production decision + execution log.

### Complete design wishlist
- **Day-grid timeline view** (vertical, hours on Y-axis, recipes on X-axis).
- **Week view** (7-day calendar with batches per day).
- **Month view** (capacity planning).
- **Drag-to-reschedule**.
- **Per-batch timer** ("Started at 7:32, ETA 8:15").
- **Status pill per batch**: Pendiente / En curso / Listo / En espera / Cancelado.
- **Assigned cook** field.
- **Photos** of expected output (for QC).
- **Yield tracking** (planned vs actual).
- **Printable prep sheet** per day.
- **Recipe version** indicator (if recipe changed mid-day, flag it).
- **Comments thread** per batch.
- **"Notificar al cliente"** button (WhatsApp deep-link).

### Quality-of-life touches
- The "Plan manual" CTA in a soft dashed box is unusual but eye-catching. Could be a regular button instead.
- Tab toggle Día / Semana / Mes works but only "Día" has content; Semana/Mes should show placeholder grids.
- The Suficiente badge is the perfect size and color.
- Channel pill "whatsapp" is lowercase — others might say "WhatsApp". Pick a casing convention.
- "Pending" status in English on a Spanish page — "Pendiente".
- "US 4.4" — what is US? Probably "Urgencia Score" or some hidden score. **Needs a tooltip**.
- Item line "2.0 × Producto cfaf4b47 (Gs. 10.000)" — the "(Gs. 10.000)" is the line total, not unit price. Easy to misread.
- "Cantidad" input field shows "1.0" — but how does the user know what to type? Should auto-fill from "Sugerido por ventas" or have a "Auto" toggle.
- "Usar" / "Ver receta" buttons inline next to the qty input — looks cramped. Move "Ver receta" to the Producto cell as a chevron.

### Defects (P0/P1/P2)
- **P1** — **"US 4.4" with no explanation.** A floating abbreviation in the Pedidos pendientes card is confusing.
- **P1** — **"pending" in English** on a Spanish page. Other Spanish-language status strings exist (Pendiente). Pick one.
- **P1** — **No way to actually schedule a batch.** The page is informational only — no "Start at 8:00" or "Add to production queue". Where does the production happen?
- **P1** — **Suficiente badge is good but the "A comprar" column is `—` for all rows.** If the column is going to be empty, hide it until needed.
- **P2** — **Sidebar "Producción" is highlighted** even though the page is the production page — but the active state could be more visually confirmed.
- **P2** — **"Producto cfaf4b47" / "Ingrediente 415de24c"** — same slug-as-name issue. Production pages should absolutely show friendly names.
- **P2** — **The "qty" input "1.0" in Productos a producir has no label** — user has to guess it's the number of batches.

---

## 8. produccion-planner.png
**Route:** Planificador (Manual production planner)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Title "Plan manual de producción". Subtitle "Elegí receta + cantidad de tandas y calculamos cuánto necesitás cocinar — y qué ingredientes faltan". "← Volver a Producción" link. Form: Receta (combo "Buscar receta…") + Tandas (numeric "1") + orange "Calcular necesidad" button. Helper card: "Elegí una receta + cantidad de tandas para ver qué ingredientes necesitás y dónde falta stock. Probá con tu receta más vendida y 10 tandas."
- **Missing:** No presets ("mi receta más vendida", "10 tandas"). No multi-recipe plan (add several rows). No save as plan / load saved plan.
- **Top add:** A **"Guardar plan"** button (save the receta+qty combo for reuse) and a **"Cargar plan guardado"** dropdown.

### Owner-finance (hat 2)
- **Now:** Can compute ingredient needs for a batch. Implicit cost.
- **Missing:** No cost preview in the form. No "this batch will cost Gs. X" preview.
- **Top add:** Show **"Costo estimado: Gs. —"** next to the "Calcular necesidad" button (computed from recipe × qty).

### Production-baker (hat 3)
- **Now:** Two-field form: Receta + Tandas + Calcular. Helper copy suggests "Probá con tu receta más vendida y 10 tandas."
- **Missing:** No "show recipe" preview before calculating. No "show last time this recipe was produced" reference. No "tiempo estimado" preview.
- **Top add:** A **preview pane** that opens as soon as you pick a Receta (shows yield, time, ingredient list — no need to click "Calcular" first).

### New user (hat 4)
- **Now:** The form is self-explanatory: 2 inputs + 1 button. The empty helper card explains the contract.
- **Missing:** No "?" tooltip explaining "qué es una tanda" (vs unidad, vs batch).
- **Top add:** A one-line tooltip **"1 tanda = el rendimiento base de la receta (ej. 12 unidades si la receta rinde 12)"**.

### Auditor (hat 5)
- **Now:** Nothing to audit yet (calculation hasn't happened).
- **Missing:** No log of past calculations.
- **Top add:** A **"Historial de planes"** panel below the form listing past receta + tandas + who planned it.

### Complete design wishlist
- **Multi-row planner** (add receta + tandas many times, see total ingredients needed at the bottom).
- **Date picker** (plan for tomorrow's production).
- **Save plan as template** (name it "Lunes de medialunas" and reuse).
- **Compare to last week's plan** (deviation view).
- **Print prep sheet** with quantities per ingredient + steps.
- **Share with baker** (deep-link to the production page).
- **Auto-fill "mi receta más vendida"** as a one-click preset.
- **Cost preview** as soon as receta is picked.
- **"Stock after this plan"** preview.

### Quality-of-life touches
- "Calcular necesidad" CTA is a vivid orange — good.
- The helper card has nice emphasis ("Probá con tu receta más vendida y 10 tandas.").
- Numeric input "Tandas" with no +/- buttons. Add stepper.
- Receta combobox shows "Buscar receta…" placeholder — but no autocomplete visible. Should dropdown on focus.
- The page is mostly empty below the form (only 1 viewport) — feels lonely. Add a "Planes recientes" list or "Atajos" section.

### Defects (P0/P1/P2)
- **P1** — **No inline result panel.** Click "Calcular necesidad" → what happens? In the screenshot it does nothing because Receta is empty. But even with values, the lack of any preview state below is jarring.
- **P1** — **No "fecha objetivo" picker.** Is this plan for today, tomorrow, next Monday? Bake shops plan by day.
- **P2** — **Tandas input has no min/max constraint.** Tandas = 0? Tandas = 1000? No validation hints.
- **P2** — **Receta combobox is wide enough but lacks icons** (categories, thumbnails). A picker with thumbnails would help.

---

## 9. pedidos-board.png
**Route:** Cocina — pedidos del día (Kitchen Display System)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Title "Cocina — pedidos del día" with "← Volver a pedidos", "Auto-refresh cada 30s · 15:24:06", and "🔊 Probar sonido" button. Three columns: **Pendientes (1)**, **En preparación (0)**, **Listos para retiro (0)**. One card in Pendientes: "#1", "María López", "para 2026-09-27", item "• 2× Producto cfaf4b47", "Abrir" button. "Hoy 1" section below repeats the order in a more verbose format: "#1", "Pendiente", "27/09 · whatsapp", "María López", "• 2× Producto cfaf4b47", "⏱ 0 min". (This is duplication.)
- **Missing:** No "Entregados" column. No "Cancelados" column. No "En entrega" column for delivery orders. No "Cliente esperando" indicator. No "tiempo estimado" for the cook.
- **Top add:** **Drag-and-drop** between columns (kanban-native). The current KDS is read-only — it should be touch-friendly for the kitchen team.

### Owner-finance (hat 2)
- **Now:** Sees total orders today and breakdown by status.
- **Missing:** No "ingresos del día" tile. No "ticket promedio". No "orden por canal" (whatsapp % vs mostrador %).
- **Top add:** Top KPI strip: **"Pedidos hoy: 1 · Ventas: Gs. 20.000 · Ticket prom: Gs. 20.000"**.

### Production-baker (hat 3)
- **Now:** Pendientes / En preparación / Listos columns are exactly what they need. Card shows order #, customer, due date, item summary, "Abrir" button. The "Hoy" list below adds time-elapsed.
- **Missing:** No recipe / batch summary per order (baker needs to know what to cook). No "tiempo en este estado" (5 min en pendiente → alerta). No "priorizar" flag.
- **Top add:** **Aging alerts** on each card (>15min en pendiente = yellow, >30min = red border). And a **"⏱ hace X min"** timer that updates live.

### New user (hat 4)
- **Now:** "Cocina — pedidos del día" is self-explanatory. "Auto-refresh cada 30s" explains the live nature. "🔊 Probar sonido" is a hint that alerts exist.
- **Missing:** No "qué hace el botón Probar sonido" tooltip.
- **Top add:** A first-run toast: "Esta vista se actualiza sola cada 30 segundos. Si la pantalla está inactiva, los pedidos nuevos sonarán."

### Auditor (hat 5)
- **Now:** Time shown (15:24:06) and "Auto-refresh cada 30s" — implicit timing data.
- **Missing:** No "who moved this card to En preparación" / "who delivered" attribution.
- **Top add:** Click on a card to open its detail with the full audit trail (already exists at pedido-detalle — but make it more obvious).

### Complete design wishlist
- **5 columns**: Nuevo / En preparación / Listo / Entregado / Cancelado.
- **Drag-and-drop** status changes.
- **Live timer** on each card (5m, 15m, 30m thresholds).
- **Color coding** by channel (whatsapp = green, mostrador = blue, web = purple).
- **KPI strip**: total orders, total sales, avg ticket, oldest pending.
- **Filter**: channel, payment status, date.
- **Sound alert** toggle (already implied with "Probar sonido").
- **Fullscreen mode** (kitchen TVs).
- **Print/pull ticket** action (thermal printer).
- **Customer name search** within the board.
- **"Marcar como entregado"** with timestamp + optional delivery note.
- **Group by delivery zone** (delivery orders).
- **Multi-language** copy toggle.

### Quality-of-life touches
- "Pendientes / En preparación / Listos para retiro" naming — "Listos para retiro" is great (clarifies it's pickup, not delivery). Make sure delivery orders have "Listos para despacho" as alternative.
- "Hoy 1" section below the kanban is **redundant** — same order shown twice. Either remove the kanban card or remove the Hoy list.
- "Abrir" button on each card is the only action — would prefer a kebab menu (⋯) for archive, duplicate, contact.
- ⏱ 0 min looks broken (it should show "ahora" or "hace 0s"). Use a friendlier format.
- The "Probar sonido" button uses 🔊 emoji — works, but a proper icon (lucide Volume2) would be cleaner.
- Card "Pendiente" badge in yellow is good. Add green (Listo) and red (Cancelado) variants.

### Defects (P0/P1/P2)
- **P1** — **The same order appears twice** — once as a kanban card and once as a "Hoy 1" expanded row below. Pick one representation; today it's confusing.
- **P1** — **No way to change status.** There's no "En preparación → Listo" path visible. The page is read-only; the worker needs to actively advance state.
- **P1** — **"Probar sonido" is the only feedback channel shown.** If sounds don't work, the worker is blind. Add a visual flash option.
- **P2** — **"whatsapp" lowercase channel pill** in the second card but the first doesn't show it. Pick one position.
- **P2** — **No delivery vs pickup indicator** — affects how the cook plates (different packaging).
- **P2** — **Auto-refresh every 30s** with no manual "Refresh now" button. Add it.

---

## 10. pedidos-nuevo.png
**Route:** Nuevo pedido (New order form)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Title "+ Nuevo pedido". Customer block: Cliente (combobox "María González — escribí para buscar"), Teléfono (opcional +595 9XX XXXXX), "Cliente seleccionado" panel (currently "Ninguno — se crea al guardar"). Fecha prometida (date picker, 09/28/2026 default) + Hora (opcional, time picker). Canal (dropdown "Seleccioná canal…") + Forma de pago esperada (dropdown). Notas (textarea "Sin TACC, retirar antes de las 17h, etc."). Ítems del pedido block: helper copy "Tocá «+ Agregar ítem» para sumar líneas. El precio queda guardado al crear el pedido." Table header: PRODUCTO · CANTIDAD · PRECIO UNIT. (GS.) · (actions). One row: "Escribí para buscar (muffin, factura, pan…)" combobox + "1" + "0" + "Quitar" button (red outline). "+ Agregar ítem" button. Submit: "✓ Crear pedido" (orange) + "Cancelar".
- **Missing:** No "duplicate from previous order" quick action. No "frequently ordered" presets. No "discount" field. No "tip / propína" field. No "split payment" UI.
- **Top add:** A **"Pedidos frecuentes del cliente"** autocomplete panel that appears when a customer is selected — one-click re-order.

### Owner-finance (hat 2)
- **Now:** Forma de pago esperada dropdown. Notas freeform. Total computed at submit (not visible yet because items haven't been priced).
- **Missing:** No "discount" line. No "tax breakdown". No "cost vs sale price" preview. No "this customer has outstanding balance" warning. No "abono / seña" partial payment field.
- **Top add:** A **"Total preview"** sticky footer (subtotal · descuento · total · pago esperado · saldo) — finance needs to see this as items are added.

### Production-baker (hat 3)
- **Now:** Items table has columns Producto / Cantidad / Precio Unit. — they see what's ordered and how many. Fecha prometida + Hora set the deadline.
- **Missing:** No "recipe / batch impact" preview (will this order consume 2 kg of flour?). No "needed by" priority.
- **Top add:** A **"Impacto en producción"** inline panel below the items: "Esta orden requiere 1 batch de Producto cfaf4b47 — suma al plan de producción del 28-09."

### New user (hat 4)
- **Now:** Helpful placeholders and copy ("María González — escribí para buscar", "Sin TACC, retirar antes de las 17h, etc."). Helper text under each field.
- **Missing:** No first-run guide. No required-field markers.
- **Top add:** A subtle **"?" tour** the first time: "1) Elegí el cliente · 2) Elegí los productos · 3) Asigná fecha/canal/pago · 4) Creá el pedido".

### Auditor (hat 5)
- **Now:** Canal and Forma de pago captured.
- **Missing:** No "created by" (single-user system, but the channel can be a proxy). No source attribution (where did this order originate?).
- **Top add:** A **"Canal de origen"** detail (WhatsApp thread ID, mostrador shift, web session).

### Complete design wishlist
- **Sticky total bar** at bottom (subtotal · descuento · total · saldo).
- **Discount codes / line discounts**.
- **Tip / propína**.
- **Recurring orders** ("every Monday for 3 months").
- **Customer balance warning** ("Este cliente debe Gs. 50.000 — ¿cobrá antes?").
- **Quick add presets** (sells-most-lugar + last 5 orders).
- **Multi-currency** display (USD for tourists).
- **Stock preview** button (the 500-error page exists for this; should work).
- **"Guardar como cotización"** mode (draft that doesn't decrement stock).
- **Scheduled orders** with cron-like recurrence.
- **Internal notes vs customer notes** (different visibility).
- **Print kitchen ticket** auto-generated on submit.

### Quality-of-life touches
- The "Quitar" button on the only item row is red outline — looks like danger. Use neutral or "✕" icon button.
- "Cliente seleccionado" panel is grayed out and says "Ninguno — se crea al guardar" — could be more encouraging: "Tip: dejá vacío para crear un cliente nuevo al guardar".
- Combobox for Cliente shows "María González — escribí para buscar" but in the actual screenshot it's empty (placeholder).
- The form has no visible submit feedback (loading spinner, toast on success, redirect).
- "Forma de pago esperada" and "Canal" are dropdowns but show no icons. Pick visual indicators.
- Notes placeholder is excellent — gives a real-world example ("Sin TACC, retirar antes de las 17h, etc.").
- "+ Agregar ítem" button is below the items table — would prefer inline at the end of the items list (more obvious).
- "+ Nuevo pedido" title icon "+" is redundant with the page being new — drop it.

### Defects (P0/P1/P2)
- **P1** — **No required-field validation visible.** Submit "Crear pedido" with empty Cliente + empty items → silent fail or generic error.
- **P1** — **The single item row already shows "Quitar" — but it's the only item.** Quitting the only item leaves the order empty. Either disable Quitar when only one row exists, or auto-remove it.
- **P1** — **No total / subtotal / saldo anywhere on the form.** Counter needs to know the running total as items are added.
- **P2** — **"Fecha prometida" defaults to 09/28/2026 (tomorrow) — but Pedido #1 in the kanban shows "para 2026-09-27" (today).** Inconsistent default vs example.
- **P2** — **"Hora (opcional)" placeholder "--:--"** is unclear; use "Sin hora definida".
- **P2** — **Two parallel date controls:** Fecha prometida + Hora, but Hora is "optional". Should be a unified datetime picker with an "All day" toggle.

---

## 11. pedido-detalle.png
**Route:** Pedido #1 (Order detail)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Header "📋 Pedido #1" + status pill "Pendiente". Two top cards: Cliente (María López · 0981112222) and Prometido (27/09/2026 · WhatsApp · pago: efectivo). Items card with table: Producto / Cantidad / Precio unit. / Subtotal / Cumplido — row "Producto cfaf4b47 · 2.00 · Gs. 10.000 · Gs. 20.000 · —", Total row "Gs. 20.000". "Link para el cliente" card: "Compartí este link por WhatsApp para que vea su pedido sin login." — path `/p/igYDzMdP` + "Vista previa" button. Acciones card: orange "Ver stock antes de cumplir", "🕐 Cancelar", "✓ Confirmar", "Duplicar" (text-only). Helper text "Transiciones permitidas: pending → cancelled, confirmed". "Volver al listado" link at bottom.
- **Missing:** No edit items button (must duplicate to change). No "mark ready" status. No "delivered" status. No "send to WhatsApp" deep-link button (just shows the link). No print receipt.
- **Top add:** A **"Enviar por WhatsApp"** button next to the link — opens wa.me/<phone>?text=<order summary> with the link pre-attached.

### Owner-finance (hat 2)
- **Now:** Total Gs. 20.000. Forma de pago "efectivo". Subtotal = Total (no discount, no tax line).
- **Missing:** No "costo" / "margen" column on items. No "pagos recibidos" / "saldo" tile. No "factura" / "recibo" action. No payment recording.
- **Top add:** A **"Pagos"** card: "Recibido: Gs. 0 · Saldo: Gs. 20.000 · [Registrar pago]" with payment methods (efectivo, transferencia, tarjeta).

### Production-baker (hat 3)
- **Now:** Items table shows recipe (Producto cfaf4b47) × 2. Cumplido column shows "—" (not yet produced). Prometido 27/09/2026 with WhatsApp channel.
- **Missing:** No recipe details / batch instructions inline. No "tiempo estimado". No "asignar cocinero". No "marcar como producido" toggle.
- **Top add:** A **"Producción"** mini-card with a "Marcar producido" / "Cumplido" checkbox per line + a "Notificar al cliente cuando esté listo" toggle.

### New user (hat 4)
- **Now:** Clear status pill. Helpful "Link para el cliente" card with the link ready to copy.
- **Missing:** No explanation of what "Pendiente" / "Confirmado" / "Cancelado" mean.
- **Top add:** A **status legend tooltip**: "🟡 Pendiente = aún no confirmado · 🟢 Confirmado = en preparación · ✅ Entregado".

### Auditor (hat 5)
- **Now:** Transiciones permitidas documented ("pending → cancelled, confirmed").
- **Missing:** No "by whom" attribution. No timestamp on transitions. No "items changed after confirmation" warning.
- **Top add:** A **"Historial"** timeline below Acciones: "2026-09-27 15:24: Pedido creado · 15:25: Confirmado por Iván".

### Complete design wishlist
- **Payment recording** (efectivo, transferencia, tarjeta, mixto).
- **Status legend** (color-coded pills with tooltips).
- **Status transition buttons** gated by current state ("Confirmar" only when pending, "Entregar" only when ready, "Cancelar" only when pending/confirmed).
- **WhatsApp deep-link** to share order.
- **Print receipt** (thermal printer or PDF).
- **"Marcar items producidos"** per line.
- **Internal notes** vs customer notes.
- **Comments thread**.
- **Status timeline** (vertical).
- **Production impact summary** ("Esta orden requiere 2 batches · 0.60 kg de Ingrediente 415de24c").
- **Edit items** with audit trail.
- **Refund / partial cancel** flow.

### Quality-of-life touches
- "Ver stock antes de cumplir" is the right CTA — but at this stage in the user journey it's a 500 error (see pedido-stock-preview). Fix the dependency.
- "Link para el cliente" path `/p/igYDzMdP` is monospaced — looks like a hash. Make it a click-to-copy pill with "Copiado ✓" toast.
- "Vista previa" button under the link could be a QR code (kiosk-friendly).
- "Duplicar" button has no icon and no color — visually weakest of the action buttons. Make it secondary style.
- Status pill "Pendiente" is yellow — good. Where's the green "Confirmado", red "Cancelado"?
- Subtotal column header doesn't say "(Gs.)" but the values say "Gs. 20.000". Inconsistent currency placement.
- "Cumplido" column shows "—" for both not-yet-produced and not-applicable. Use empty state or "Pendiente" label.
- "Volver al listado" at bottom is small; consider a sticky footer with primary action (Confirmar) + secondary (Volver).

### Defects (P0/P1/P2)
- **P1** — **"Transiciones permitidas: pending → cancelled, confirmed" is in English.** Should be in Spanish (and fully translated): "Estados permitidos: pendiente → cancelado, confirmado".
- **P1** — **"Ver stock antes de cumplir" leads to a 500 error** (see pedido-stock-preview). This is a P1 broken-link defect.
- **P1** — **No payment / balance UI.** Cash-only counter can't record receipt of Gs. 20.000.
- **P2** — **"Duplicar" and "Cancelar" actions live side-by-side with "Confirmar"** with no visual hierarchy (all text + outline except orange Confirmar). Cancel should be destructive-styled (red outline or icon).
- **P2** — **Status pill "Pendiente" is the only state shown.** No template for what "Confirmado" or "Cancelado" looks like.
- **P2** — **Cliente phone "0981112222" shown without "+595 country code.** Inconsistent with new-order form which uses "+595 9XX XXXXX".

---

## 12. pedido-stock-preview.png
> ⚠️ **Screenshot is a 500 error page**, not the actual stock preview. This is itself the most important defect.

**Route:** Vista de stock (intended: per-order stock check before fulfillment)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** A 500 error page titled "500 / Algo salió mal" with subcopy "Tuvimos un problema procesando tu pedido. El equipo técnico ya tiene el reporte." Reference code `f02e6716d4db` (click-to-copy). Type "NoInspectionAvailable". Two CTAs: orange "🏠 Volver al inicio" and outline "🔍 Reintentar". Expandable "¿Qué pasó?" disclosure.
- **Missing:** EVERYTHING — the actual stock preview feature.
- **Top add:** Fix the 500. The intended page should show: per-recipe ingredient breakdown, "Suficiente / Faltan X kg" badges, total cost, "Confirmar y consumir stock" CTA, "Volver" link.

### Owner-finance (hat 2)
- **Now:** Error page.
- **Missing:** No cost-of-fulfillment preview. No "¿esto impacta el costo unitario?" view.
- **Top add:** Show **"Costo de ingredientes para cumplir: Gs. 600 · Margen: Gs. 19.400"** once the page renders.

### Production-baker (hat 3)
- **Now:** Error page.
- **Missing:** No ingredient availability for each recipe in the order.
- **Top add:** Per-item table: **Producto · Necesita · Stock actual · A reponer · Suficiente/Faltan badge**.

### New user (hat 4)
- **Now:** Error page with friendly copy and a reference code.
- **Missing:** No "what you can do" guidance.
- **Top add:** A **"Pedí ayuda"** link that opens WhatsApp with the reference code pre-attached: "Hola, mi código de error es f02e6716d4db".

### Auditor (hat 5)
- **Now:** Reference code is captured (good for debugging).
- **Missing:** No user-action log around the failure.
- **Top add:** Server-side: when this error fires, log user_id, route, params, stack trace. Client-side: show "Si el problema persiste, contactá a soporte con este código: f02e6716d4db".

### Complete design wishlist (for the **intended** page once it works)
- **Per-item table** with Producto, Necesita, Stock actual, Suficiente / Falta X badge.
- **Subtotal summary** (cost of ingredients consumed if order is fulfilled).
- **"Consumir stock y marcar cumplido"** primary CTA.
- **"Solo verificar"** secondary mode (read-only check).
- **"Reportar faltante"** inline link (auto-creates a "A comprar" entry).
- **Visual heatmap** (green = ok, yellow = borderline, red = short).
- **"Ver plan de producción"** link to add to today's batch plan.

### Quality-of-life touches
- The 500 page itself is well-designed (clear icon, friendly copy, reference code, retry button). The "¿Qué pasó?" disclosure is a thoughtful touch.
- Reference code is shown in monospace — perfect. The "click to copy" hint is good UX even on an error page.
- Type "NoInspectionAvailable" is technical — hide behind the disclosure or humanize ("Servicio de inspección de stock no disponible").

### Defects (P0/P1/P2)
- **P0** — **The page is a 500 error.** This is the highest-priority defect in the entire batch. The "Ver stock antes de cumplir" CTA from pedido-detalle leads here and dead-ends. Counter cannot fulfill an order with stock awareness.
- **P1** — **Type "NoInspectionAvailable" is shown to the user.** Hide it; show "Servicio no disponible · código: f02e6716d4db".
- **P1** — **No offline-friendly fallback.** Even without backend, the page could show cached stock for the items in this order.

---

## 13. pedido-duplicate.png
> Screenshot is the **post-duplicate order detail** (Pedido #2), not the duplication form. I'll cover both — what the duplicate should look like, and what the duplicate-landing page currently shows.

**Route:** Duplicar pedido → nuevo pedido (Duplicate order flow)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Header "📋 Pedido #2" with status "Pendiente" — same template as #1 but with a new ID and link (`/p/dFPIsjeE`). Cliente María López · 0981112222. Prometido 27/09/2026 · WhatsApp · pago: efectivo. Same items: Producto cfaf4b47 · 2.00 · Gs. 10.000 · Gs. 20.000. Same Acciones card: Ver stock, Cancelar, Confirmar, Duplicar.
- **Missing:** No indication this is a duplicate. No "based on Pedido #1" link. No "edit before saving" intermediate step. No "comparison" view vs source.
- **Top add:** A **"Basado en Pedido #1 · creado 27/09/2026"** tag under the header with a link back to the source. Also a **"Ver diferencias"** disclosure that shows what was copied vs what's editable.

### Owner-finance (hat 2)
- **Now:** Same totals, same payment method as source.
- **Missing:** No "this customer ordered the same thing X times this month" insight.
- **Top add:** A **"Historial del cliente"** mini-strip: "Pedidos este mes: 4 · Total: Gs. 80.000 · Última: 2026-09-27".

### Production-baker (hat 3)
- **Now:** Same items as source.
- **Missing:** No "is this the same physical batch as last time?" hint.
- **Top add:** A **"Misma receta que Pedido #1 · podés reusar la producción"** badge.

### New user (hat 4)
- **Now:** The duplicate lands on what looks like a regular order detail page. No clue it's a duplicate.
- **Missing:** No onboarding for "Duplicar" workflow.
- **Top add:** First-time use of Duplicar: a brief explanation "Duplicar crea un pedido nuevo basado en uno existente. Podés cambiar la fecha, los productos o el cliente antes de confirmar."

### Auditor (hat 5)
- **Now:** No "derived from" link.
- **Missing:** No lineage trail (this order → from Pedido #1 → from Pedido #0…).
- **Top add:** A **"Origen: Pedido #1"** line in the Historial timeline.

### Complete design wishlist
- **Pre-filled form** (route to pedidos-nuevo with items + customer prefilled) — let user edit before submit.
- **Side-by-side diff** (source vs duplicate) on the intermediate step.
- **"Duplicar y reagendar"** smart default (set Fecha prometida to tomorrow +1 week).
- **"Duplicar como cotización"** mode.
- **Lineage view** (every order shows its source/parent).
- **Bulk duplicate** (select N orders → duplicate all).
- **"Duplicar lo más vendido"** preset.
- **Suggested adjustments** ("Pedido #1 fue para 27/09 — ¿querés reagendar a 28/09?").

### Quality-of-life touches
- The post-duplicate order looks identical to a regular order. Add a subtle "Duplicado de Pedido #1" badge under the title.
- Same link-sharing UX ("/p/...") — good consistency.
- Acciones card layout is exactly the same — predictable.

### Defects (P0/P1/P2)
- **P1** — **No "Duplicado de..." indicator on the post-duplicate page.** A user might think this is a brand-new order and miss the link to the source.
- **P1** — **No intermediate edit step.** The current "Duplicar" workflow apparently creates the duplicate and lands you on its detail page — but you can't edit before saving. Should be a pre-filled form.
- **P2** — **The phone "0981112222" doesn't show +595** (same as Pedido #1 detail).
- **P2** — **Same Total "Gs. 20.000"** with no indication whether prices were re-fetched or snapshotted from source. Use current prices? Source prices?

---

## 14. receta-editar.png
**Route:** Editar receta (Recipe edit form)
**Personas:** counter staff, owner-finance, production-baker, new user, auditor

### Counter staff (hat 1)
- **Now:** Title "Editar receta". Left column: Identificación (Nombre "Receta 0da4ca66" * Familia/Categoría "Elegí o escribí una familia…"). Right column: Producción (Rinde 12.00 und, Escalar rendimiento 1.0x dropdown, Rinde escalado: 12.00 und, Tiempos Prep 15 min + Cocción 30 min, Dificultad auto /5). Below: Ingredientes y sub-recetas block with helper "Cada línea es un ingrediente o sub-receta. Para sub-recetas (masa choux usada en pastel), usá el tipo 'Sub-receta'." Table TIPO / INSUMO/SUB-RECETA / CANTIDAD / UNIDAD / COSTO / NOTA — row shows "Insumo" type, "Bu" autocomplete, "0.300", "kg" (highlighted green border), "Gs. 0", "opcion…" nota. Sub-block "Ninguna etiqueta dietética se cumple en todas las líneas. ▶ ✕ Canceladas (8)". "+ Agregar línea" button. Instrucciones de preparación block: "Pasos, técnica, tips, notas internas" + textarea with placeholder "Pasos de la receta (Markdown básico soportado): 1. Mezclar ingredientes secos · 2. Combinar con húmedos sin batir de más · 3. Hornear a 180°C por 22 min". Right column continued: Escandallo panel (orange-bordered) "Costo estimado basado en precios de compra" with Costo del lote Gs. 0, Costo por unidad Gs. 0, Precio sugerido (×3) Gs. 0, helper "Actualizado en tiempo real al cambiar ingredientes o rinde". Etiquetas dietarias block with chips (alto-costo, sub-receta, temporada) and "Agregar etiqueta personalizada…" + "+ Agregar". After saving toggle: "Después de guardar, crear producto" toggle off, helper "Genera un Producto vinculado a esta receta, con precio sugerido (costo × 3)". Footer: Cancelar + "Guardar receta".
- **Missing:** No "fotos" upload. No "rendimiento real vs planificado" tracker. No "costo histórico" trend.
- **Top add:** A **"Foto" upload** (drag-and-drop) at top of Identificación — recipes with photos get used more.

### Owner-finance (hat 2)
- **Now:** Escandallo panel with Costo del lote / Costo por unidad / Precio sugerido (×3 multiplier). "Después de guardar, crear producto" toggle for downstream monetization.
- **Missing:** No "margen objetivo" (×3 is hardcoded; owner may want ×2.5 or ×4). No "precio por canal" (mostrador vs delivery may have different prices).
- **Top add:** **"Margen objetivo"** input replacing the hardcoded ×3: "Quiero ganar Gs. X por unidad" or "Multiplicador: ×3.0".

### Production-baker (hat 3)
- **Now:** Tiempos (Prep 15 min + Cocción 30 min), Dificultad (auto /5), Instrucciones textarea with markdown steps. Escalar rendimiento (1.0x dropdown). Etiquetas (alto-costo, sub-receta, temporada). Tipo "Sub-receta" support. Sub-recetas (masa choux usada en pastel) — thoughtful.
- **Missing:** No "temperatura del horno" field. No "tamaño de bandeja / molde". No "porciones". No "fase (amasado, fermentado, formado, horneado, decoración)".
- **Top add:** **"Equipamiento necesario"** chip-list (horno convector, batidora, balanza, molde 24cm).

### New user (hat 4)
- **Now:** Helper copy everywhere. Markdown placeholder shows a 3-step example. Helper "Cada línea es un ingrediente o sub-receta." explains the Tipo column.
- **Missing:** No "?" tooltip on Dificultad ("auto" — based on what?). No first-run guide for the recipe workflow.
- **Top add:** A **tooltip on "Dificultad auto"**: "Calculada en base a cantidad de ingredientes, tiempos y técnica".

### Auditor (hat 5)
- **Now:** "Costo del lote Gs. 0" (because ingredient prices haven't been linked yet — defect?). "Canceladas (8)" toggle — implies 8 deleted lines are kept for audit.
- **Missing:** No "created by / modified by / when". No diff history.
- **Top add:** An **"Auditoría"** expandable at bottom showing recipe changes.

### Complete design wishlist
- **Photo upload** with crop / rotate.
- **Video embed** for technique (YouTube/Loom).
- **Version history** (v1, v2, v3) with diff.
- **Fork** a recipe (clone with modifications).
- **Yield scaling** beyond the dropdown (free input).
- **Equipment list** with checkbox presets.
- **HACCP fields** (temperatura interna mínima, alérgenos).
- **Linked products** panel — which Productos use this recipe?
- **Print spec sheet** (PDF with photo + ingredients + steps + cost).
- **"Used in production"** history (how many times last month).
- **Sub-recipe hierarchy** (visual tree: this recipe → sub-recetas → ingredients).

### Quality-of-life touches
- "Escandallo" panel is orange-bordered — stands out beautifully. Good visual hierarchy.
- "Costo del lote" updates in real time per helper — excellent UX.
- "Canceladas (8)" disclosure is great for audit but the ✕ icon looks like "delete all" — make it more like "see deleted".
- Inline green border on "kg" unit is good (indicates it's been touched).
- Helper copy "Cada línea es un ingrediente o sub-receta. Para sub-recetas (masa choux usada en pastel), usá el tipo 'Sub-receta'." — perfect, gives a concrete example.
- Difficulty "/5" without a visual indicator (dots, stars) — add.
- The "auto" Dificultad could show its calculation tooltip.
- Markdown placeholder with 3 numbered steps is a great example — new users instantly know what to write.

### Defects (P0/P1/P2)
- **P1** — **"Costo del lote Gs. 0" despite having 0.300 kg of an ingredient with no price set.** The ingredient "Bu" / 0.300 kg has Costo "Gs. 0" — but the linked ingredient (Receta 0da4ca66 is the one this recipe uses as an ingredient? actually it's the recipe being edited, and the ingredient on the row is "Bu" — autocomplete unresolved). Cost calc shows 0 — could be correct (no linked ingredient) or a bug.
- **P1** — **"Nombre *" has a required asterisk but Familia/Categoría does not** — inconsistent.
- **P1** — **Dificultad says "auto /5" but no value or hint** — what does auto compute? Empty?
- **P2** — **"Ins…" truncated for "Insumo" type** — column too narrow.
- **P2** — **"opcio…" truncated in Nota column** — column too narrow for any meaningful note.
- **P2** — **"Después de guardar, crear producto" toggle is a great feature but lives at the bottom** — easy to miss. Should be a checkbox in the Identificación card.
- **P2** — **"Precio sugerido (×3)"** — the ×3 is a magic number. Make it editable.
- **P2** — **Sub-receta support is great but undocumented** — there's no link to the actual sub-recipes library.

---

## Cross-cutting recommendations (across all 14 pages)

### Brand & voice
- **Slug-as-name bug** ("415de24c", "0da4ca66", "cfaf4b47", "dFPIsjeE") appears in **at least 9 pages**. This is the #1 systemic defect.
- **English/Spanish mixing**: "Stock", "pending", "transiciones permitidas", "link", "preview" all untranslated. Define a Spanish-first glossary and apply it.
- **Vos vs infinitive**: "Editá", "Guardá" (vos) vs "Editar", "Guardar" (infinitive). Pick one for the whole product.
- **Currency placement**: "Gs. 20.000" vs "Gs 20.000" vs "20.000 Gs" — unify.

### Layout primitives
- **Sidebar** is consistent across all pages (good). Active state is clear.
- **KPI tile pattern** is consistent (Inventario, Producción). Reuse for Pedidos, Recetas.
- **Two-column form pattern** is consistent (Inventario, Receta). Reuse for Pedido new.

### Patterns to introduce
- **Sticky action bar** at bottom of forms (currently Save is at the bottom of a long scroll).
- **Toast / snackbar** for "Saved ✓" / "Error" feedback.
- **Required-field markers** (`*`) consistently across all forms.
- **Inline help / tooltips** for jargon (TACC, HACCP, Escandallo).
- **Audit trail drawer** on every entity (Inventario, Pedido, Receta, Cliente).
- **Keyboard shortcuts** (⌘S save, ⌘N new, j/k row navigation, / search).

### Performance & reliability
- **500 errors must not be silent** — the pedido-stock-preview case shows that the system can silently fail at critical moments. Add client-side retry with exponential backoff and a banner.

### Accessibility
- All form fields have `<label>` associations (good).
- Status pills are color-coded only — add icons/text alternatives.
- Tables need `<th scope>` for screen readers (assumed; flag if missing).
- Keyboard navigation for kanban board (pedidos-board) needs work — currently no obvious drag-drop or arrow-key affordance.

---

## Top 10 defects prioritized

| # | Severity | Page | Defect |
|---|---|---|---|
| 1 | **P0** | pedido-stock-preview | 500 error — entire feature unusable |
| 2 | **P1** | all | Slug-as-display-name ("415de24c") appears in 9 pages |
| 3 | **P1** | inventario-editar | Required-field markers missing on all forms |
| 4 | **P1** | pedido-detalle | No payment recording / balance UI |
| 5 | **P1** | pedidos-board | No way to advance order status (read-only KDS) |
| 6 | **P1** | inventario-detalle | Pronóstico says "(sin consumo reciente)" while a recipe uses the ingredient |
| 7 | **P1** | pedido-detalle | "Transiciones permitidas" in English |
| 8 | **P1** | pedidos-nuevo | No running total / subtotal on the form |
| 9 | **P1** | inventario-variantes | Sidebar appears to overlap page content (z-index bug) |
| 10 | **P1** | pedido-duplicate | No "Duplicado de Pedido #1" indicator after duplication |

---

## Persona-by-persona quick wins

### Counter staff (hat 1)
- One-click "Ajustar stock" inline on every row in inventario list.
- Sticky total on new-order form.
- Status advance buttons on KDS board.

### Owner-finance (hat 2)
- "Valor en stock: Gs. X" next to Precio de compra on detail.
- Payment recording on pedido-detalle.
- Cost trend sparkline on receta edit.

### Production-baker (hat 3)
- "Días restantes" column on inventario list.
- Live timer + aging alerts on KDS cards.
- "Hoy se va a usar este ingrediente" indicator on ingrediente detail.

### New user (hat 4)
- Required-field markers everywhere.
- Glossary tooltips (TACC, HACCP, Escandallo, Lote obligatorio).
- First-run empty states with explainer CTAs.

### Auditor (hat 5)
- "Modified by / when" on every entity.
- "Transiciones permitidas" translated and clickable.
- Audit log drawer / timeline on every detail page.

---

*End of audit.*