# Work Item Catalog — Track detail (W-0001 … W-1000)
Companion to 00-MASTER-PLAN.md. Track sums verified: A120 B100 C130 D70 E180 F80 G50 H60 I80 J130 = 1000.
This file enumerates items at commit-size granularity. Legend: [P0]=blocker for later tracks, [P1]=phase work, [P2]=polish/optional.

## TRACK A — Design system foundations (120)
### A1 Token/scale enforcement (30)
W-0001 [P0] Extract all inline styles from inicio.html to CSS classes (≈30 instances)
W-0002 Extract inline styles: pedidos.html
W-0003 Extract: dashboard.html
W-0004 Extract: analisis.html
W-0005 Extract: ventas.html + ventas_historial.html
W-0006 Extract: pedidos_board + pedidos_nuevo
W-0007 Extract: produccion + planner
W-0008 Extract: eod + merma
W-0009 Extract: productos list/nuevo/editar
W-0010 Extract: recetas list/nueva/detalle/editar
W-0011 Extract: inventario list/nuevo/editar/detalle/movimientos
W-0012 Extract: clientes list/detalle/editar
W-0013 Extract: reorder + shopping-list
W-0014 Extract: proveedores + supplier form
W-0015 Extract: wishlist
W-0016 Extract: reportes hub + 4 top report pages
W-0017 Extract: remaining report pages
W-0018 Extract: bank + pricing + vs-mercado
W-0019 Extract: riesgos + benchmarks
W-0020 Extract: settings + catalog + delivery-zones
W-0021 Extract: users + excel + auditoria + ops-status
W-0022 Extract: guia + login + error pages
W-0023 CSS: define .page-header, .toolbar-row, .table-actions utility classes
W-0024 CSS: enforce spacing tokens; grep-and-replace hardcoded px/rem margins
W-0025 CSS: type-scale enforcement — remove font-size overrides, verify H1/H2 consistent
W-0026 CSS: uppercase micro-label class .kpi-label standardized (monospace only here)
W-0027 CSS: table density variants (compact/comfortable) as classes
W-0028 CSS: form width caps (.form-narrow 720px, .form-grid 2col)
W-0029 Lint: template style-attribute CI check (warn list)
W-0030 Lint: ban new emoji in templates check (except content fields)

### A2 Component macros (40)
W-0031 [P0] metric_card macro: base (label, value, sub)
W-0032 metric_card: delta pill slot
W-0033 metric_card: target-bar variant (progress vs meta)
W-0034 metric_card: tooltip on "—" (missing vs zero) via title attr
W-0035 metric_card: compact variant
W-0036 metric_card: currency/qty/pct value formatters built in
W-0037 metric_card tests (render, undefined-safe)
W-0038 [P0] filter_toolbar macro (search + selects + submit + clear)
W-0039 filter_toolbar: live-search option (debounced GET)
W-0040 filter_toolbar: applied-filters chips
W-0041 filter_toolbar tests + rollout to clientes
W-0042 filter_toolbar rollout: ventas-historial
W-0043 filter_toolbar rollout: productos, recetas
W-0044 filter_toolbar rollout: reportes date-range global
W-0045 [P0] status_pill macro (5 severities: ok/info/warn/danger/neutral)
W-0046 status_pill: replace badge-danger dialects on pedidos
W-0047 status_pill: loyalty tiers (Bronce/Plata/Oro)
W-0048 status_pill: pedido state machine colors
W-0049 status_pill: stock states (ótimo/justo/crítico/agotado)
W-0050 status_pill tests
W-0051 [P0] empty_state macro (icon/title/hint/CTA + compact)
W-0052 empty_state rollout: 10 list pages
W-0053 empty_state: onboarding variant ("cargá datos de ejemplo" → seed-demo link)
W-0054 [P0] entity_link macro (hash-name guard + link)
W-0055 entity_link rollout: board, ventas, produccion, reportes mentions
W-0056 money cell macro (m.gs everywhere, undefined-safe) + sweep list
W-0057 qty cell macro (trim zeros, py comma) + sweep list
W-0058 pct cell macro (delta-aware) + sweep list
W-0059 kpi_strip macro (responsive 4→2→1)
W-0060 alert_rail macro (sev pills + action links) — extract from inicio
W-0061 alert_rail on /dashboard
W-0062 alert_rail on /analisis
W-0063 [P0] breadcrumb macro + route→crumb table (es)
W-0064 breadcrumb rollout pass 1 (20 routes)
W-0065 breadcrumb rollout pass 2 (remaining)
W-0066 stepper component (CSS+JS) for wizards
W-0067 drawer component (slide-over) + backdrop + esc
W-0068 drawer: reuse for inventario Ajustar modal (replace modal)
W-0069 drawer: anular venta uses reason-drawer
W-0070 tooltip component (CSS-only, delay) + first 10 uses

### A3 Icons (15)
W-0071 icon set audit: list missing glyphs (clock-timer, kanban, heatmap, stepper arrows)
W-0072 add missing SVG glyphs to icons.svg
W-0073 replace emoji ❌ on receta-detalle canceladas
W-0074 replace emoji ⚠️ across reportes
W-0075 replace 🍞 on wishlist/guia
W-0076 replace 🟢🔴🔵 severity emojis (inicio avisos remnants, riesgos)
W-0077 replace 📦📈 on produccion
W-0078 replace 🐕⭐ stars/dogs emojis → icons
W-0079 replace 🖨 🚫 on ventas-historial buttons → icons + aria-labels
W-0080 icon-button aria-label sweep (all icon-only buttons)
W-0081 favicon/brand consistency check (login vs sidebar logo)
W-0082 icon size normalization (some render 1em vs 48px empty-states)
W-0083 remove decorative emoji from H1s (wishlist "🏪 24")
W-0084 icon usage doc section in design-system file
W-0085 emoji-in-content allowlist (notes fields only)

### A4 Elevation (10)
W-0086 define .card resting elevation (border + shadow-sm)
W-0087 define hover elevation for interactive cards (teaser-card, calendar cells)
W-0088 metric_card hover none (not interactive) — verify tokens
W-0089 sidebar active pill elevation audit
W-0090 drawer/modal shadow tiers
W-0091 table row hover consistency
W-0092 dark-mode elevation verification (shadows visible?)
W-0093 border-color on dark cards
W-0094 focus-ring elevation interplay (no double rings)
W-0095 elevation demo page (internal /ops/design-system)

### A5 Focus/keyboard/aria (25)
W-0096 tab-order audit: sidebar → main → toolbar
W-0097 skip-link works with new shell (exists — verify)
W-0098 combo (saskia-combo) keyboard: arrows/enter/escape on all instances
W-0099 combo screen-reader labels
W-0100 ⌘K palette keyboard nav + Ctrl K label on non-Mac
W-0101 Nuevo menu keyboard/esc
W-0102 drawer focus trap
W-0103 modal focus trap (confirm modal)
W-0104 table sort links aria-sort
W-0105 pagination aria
W-0106 tab strip (pedidos) roving tabindex
W-0107 status_pill role/aria for severity
W-0108 form error summary region + focus on submit fail
W-0109 required-field legend "* = obligatorio" pattern + rollout
W-0110 input error/hint ids wired to aria-describedby (forms pass)
W-0111 receipt print a11y (lang, contrast)
W-0112 charts: text alternatives (data table toggle)
W-0113 heatmap cell aria labels
W-0114 toast aria-live
W-0115 empty-state heading level audit (no h3 skipping)
W-0116 landmarks: nav/main/aside roles on shell
W-0117 axe-style contrast check script (CI optional)
W-0118 reduced-motion audit for drawer/toast animations
W-0119 touch targets ≥40px on POS/board buttons
W-0120 a11y regression test (pytest + lxml heuristics)

## TRACK B — i18n & terminology (100)
### B1 Breadcrumbs ×40
W-0121 crumb table data structure (route → [section, subsection, entity])
W-0122 crumbs: suppliers→Proveedores, supplier-nuevo→Proveedores›Nuevo
W-0123 crumbs: reorder→Reponer, shopping-list→Compras›Lista de compras
W-0124 crumbs: wishlist→Equipamiento
W-0125 crumbs: cliente-detalle/editar (kill double trail)
W-0126 crumbs: producto form/nuevo/editar
W-0127 crumbs: receta routes
W-0128 crumbs: inventario routes
W-0129 crumbs: pedido routes (add parent)
W-0130 crumbs: ventas routes
W-0131 crumbs: produccion + planner + eod
W-0132 crumbs: reportes ×14
W-0133 crumbs: bank, pricing, vs-mercado
W-0134 crumbs: riesgos, benchmarks
W-0135 crumbs: settings, catalog, users, excel, auditoria, ops
W-0136 crumbs: guia (+secciones), errors, healthz
W-0137 crumbs tests (all routes have crumbs, all Spanish)
W-0138 crumb last-item aria-current
W-0139 … W-0160 (remaining per-route crumb items, incl. analisis/dashboard/login exclusions)

### B2 Voseo sweep (30)
W-0161 style-guide rule: voseo affirmatives (Guardá/Agregá/Eliminá), neutral descriptions
W-0162 sweep proveedores/suppliers forms
W-0163 sweep clientes forms
W-0164 sweep productos forms
W-0165 sweep recetas forms + editor hints
W-0166 sweep inventario forms
W-0167 sweep pedidos + board + nuevo
W-0168 sweep ventas + recibo copy
W-0169 sweep produccion + planner + eod
W-0170 sweep reorder + shopping-list
W-0171 sweep reportes copy
W-0172 sweep bank/pricing/vs-mercado
W-0173 sweep settings/users/excel/auditoria
W-0174 sweep error messages (flash/validation)
W-0175 sweep empty-states copy
W-0176 … W-0190 per-file voseo items (remaining templates + JS-embedded strings + tooltips)

### B3 Enum localization (15)
W-0191 loyalty tiers Bronze/Silver/Gold → Bronce/Plata/Oro (render map)
W-0192 pedido status labels es (pending→Pendiente etc.)
W-0193 payment method labels audit
W-0194 channel labels (whatsapp/mostrador/delivery)
W-0195 risk status labels
W-0196 bank txn categories es
W-0197 role badges es (exist — verify)
W-0198 weekday/month full es in tables (sábado not Sat)
W-0199 "KPIs (mensual)" → "KPIs mensuales"
W-0200 "Items totales" → "Artículos totales"
W-0201 remove "Ver como JSON" reorder
W-0202 sheet-name leak removal (wishlist note)
W-0203 migration-note removal (inventario detalle)
W-0204 endpoint-in-copy removal (bank, benchmarks)
W-0205 enum localization tests

### B4 Canonical names (10)
W-0206 glossary file (canonical name per feature)
W-0207 reorden→Reponer in all copy
W-0208 Wishlist→Equipamiento everywhere
W-0209 Inteligencia→Análisis heading unification
W-0210 "lista de deseos"→"equipamiento" titles
W-0211 Nav vs H1 vs crumb consistency test
W-0212 redirect old anchors
W-0213 doc/guia terminology sync
W-0214 search index synonyms (reorden↔reponer)
W-0215 copy-review checklist into PR template

### B5 Formatters (5)
W-0216 fmt_date table/prose/ISO helpers (template globals)
W-0217 fmt_qty helper + rollout
W-0218 fmt_pct helper + rollout
W-0219 delta neutral-empty rule shared helper + all deltas use it
W-0220 formatter unit tests (property-based)

## TRACK C — Layout roll-out (130)
### C1 DATA GRID ×10 pages (80)
(per page: W-item block of 8: header/KPI/toolbar/table-classes/sticky-head/row-actions/pagination/empty)
W-0221…W-0228 productos
W-0229…W-0236 recetas
W-0237…W-0244 ventas-historial
W-0245…W-0252 pedidos (finish: row-action menu)
W-0253…W-0260 clientes
W-0261…W-0268 proveedores
W-0269…W-0276 wishlist/equipamiento
W-0277…W-0284 riesgos
W-0285…W-0292 auditoria
W-0293…W-0300 bank transactions
### C2 ASYM EDITOR ×8 (48)
W-0301…W-0306 productos/editar
W-0307…W-0312 productos/nuevo
W-0313…W-0318 recetas/editar
W-0319…W-0324 recetas/nueva
W-0325…W-0330 inventario/editar
W-0331…W-0336 cliente/editar
W-0337…W-0342 proveedor/nuevo+editar
W-0343…W-0348 pedidos/nuevo
### C3 WIZARD ×3 (21)
W-0349…W-0355 inventario/nuevo (3 steps + stepper + footer)
W-0356…W-0362 excel/importar wizard
W-0363…W-0369 supplier/nuevo → wizard (básicos/contacto/compras)
### C4 DASHBOARD ×4 (24)
W-0370…W-0375 inicio formalization (alert_rail extract, compact charts)
W-0376…W-0381 analisis (period selector, heatmap teaser)
W-0382…W-0387 dashboard mensual (progress bars vs metas)
W-0388…W-0393 riesgos (matrix view + table)
### C5 misc (9)
W-0394 login center-card polish
W-0395 error pages (404/403/500) onboarding tone
W-0396 ops-status card grid
W-0397 guia layout TOC
W-0398 healthz html friendly (behind auth)
W-0399 receipt print container
W-0400…W-0405 f-batch: settings sections cards, catalog page table, delivery-zones→settings anchor, excel hub cards, users table density, auditoria filters → (6 items; plus 3 buffer)

## TRACK D — Navigation & IA (70)
W-0406 sidebar: move Clientes to CRM group
W-0407 sidebar: FINANZAS regroup (Reportes/Análisis/KPIs mensuales/Precios×2/Banco/Riesgos)
W-0408 sidebar: SISTEMA regroup (Config/Usuarios/Excel/Auditoría/Guía)
W-0409 sidebar: COMPRAS (Reponer/Lista/Proveedores/Equipamiento)
W-0410 sidebar: sub-item icon/indent pattern unified
W-0411 sidebar tests update (herbus nav contracts)
W-0412 sidebar screenshots refresh
W-0413 /suppliers 301 → /proveedores
W-0414 /suppliers/nuevo merge + tests
W-0415 /delivery-zones 301 → /settings#zonas
W-0416 /dashboard label "KPIs mensuales" + cross-link análisis
W-0417 nav manifest (single source: sidebar + crumbs + guia generated from it)
W-0418 Nuevo menu: 8 create-actions wired (venta, pedido, producto, receta, ingrediente, cliente, proveedor, merma)
W-0419 Nuevo menu tests (each action lands on form)
W-0420 Nuevo menu mobile behavior
W-0421 ⌘K palette: add all sections + actions
W-0422 ⌘K: platform-aware label (Ctrl K)
W-0423 "?" chip tooltip
W-0424 bell = alert count → links #alertas anchor
W-0425 dark-mode toggle persistence (verify)
W-0426 footer pills link (version → /ops/status)
W-0427 cross-links: analisis stars/dogs → productos
W-0428 cross-links: reorder rows → ingrediente detalle
W-0429 cross-links: recibo → venta en historial
W-0430 cross-links: pedido → cliente detalle
W-0431 cross-links: produccion sugerencia → receta
W-0432 cross-links: wishlist item → supplier
W-0433 cross-links: merma → ingrediente
W-0434 cross-links: reportes margenes → producto
W-0435 cross-links: bank txn → pedido/venta match
W-0436 cross-links: auditoria entry → entity
W-0437 cross-links: eod → ventas del día
W-0438 cross-links: inicio acciones → deep pages (verify all)
W-0439 cross-links: guia → pages
W-0440 cross-link audit test (no href="#" placeholders)
W-0441 dead link sweep (curl all hrefs in rendered home+guia)
W-0442 anchor targets exist (#avisos-todos etc.)
W-0443 …W-0475: per-page cross-link completion items (33 pages × 1)

## TRACK E — Page redesigns (180)
### E1 12 core pages (96)
W-0476…W-0483 / inicio polish (8)
W-0484…W-0491 /ventas POS split (8: grid+cats, scan field, ticket rail, totals, payment, cobrar+F10, ticket preview, voided state)
W-0492…W-0499 /ventas/historial (8)
W-0500…W-0507 recibo thermal (8)
W-0508…W-0515 /pedidos (8: status dropdown, countdown chips, whatsapp link, bulk bar polish, CSV, tabs aria, empty, tests)
W-0516…W-0523 /pedidos/board KDS (8: kanban cols, timers, checklist, notes, fullscreen, sound?, tests)
W-0524…W-0531 /pedidos/nuevo (8: 2col, live totals, client combo, sku search, discount, channel, validation, tests)
W-0532…W-0539 /produccion (8: sufficiency matrix, Δ colors, batch confirm, history link, reasons, tests)
W-0540…W-0547 /inventario extra columns (8)
W-0548…W-0555 /recetas/{id}/editar escandallo rail (8)
W-0556…W-0563 /productos/{id}/editar pricing rail (8)
W-0564…W-0571 /login extras (remember, PIN decision doc) (8)
### E2 remaining 64 routes (84 items)
W-0572…W-0655: one item per route minimum + 20 second items for complex routes (reportes variants, settings catalog, benchmark edit, pedido public, stock preview, duplicate, crear-producto, set-photo, guia-seccion, ops-status, users nuevo/editar, excel importar, bank importar, cierre-mensual, freshness, stock-intel, afinidades, demand, food-cost-variance, valor-pedido, retencion, metodos-pago, ventas-hora, top-productos, comparacion, libro-ventas, iva, diario, precios, margenes + detalle, price-impact, wishlist-nuevo, supplier nuevo/editar, cliente detalle/editar, inventario variantes/movimientos/detalle, receta detalle/nueva, producto nuevo, produccion-planner, eod, merma, ventas nueva, ventas buscar html-debug, login done above, errors, healthz) — enumerated one-to-one in tracking board
W-0656…W-0660 buffer (5) for critique-agent findings to slot in

## TRACK F — New pages & surfaces (80)
W-0661…W-0670 kardex page (10): route, ledger query, running balance, filter, export, tests×4
W-0671…W-0680 produccion/historial (10)
W-0681…W-0688 heatmap analisis (8)
W-0689…W-0696 merma/análisis (8)
W-0697…W-0708 pedidos kanban enhancements (12: cols, drag or buttons, timers, sound toggle, fullscreen, item check, notes, auto-refresh meta, filters, tests)
W-0709…W-0723 POS build (15)
W-0724…W-0738 column/data additions (15): clientes last-purchase+total, inventario supplier+shelf, usuarios last-login, wishlist priority sort, bank reconciliation chips, bench variance badges, riesgo matrix data, pedido channel split, eod comparison, excel last-import status, auditoria entity link, reportes format badges, usuarios role filter, clientes allergies column, productos margin column)
W-0739 settings: markup defaults section (1)
W-0740 settings: zonas anchor finalize (1)

## TRACK G — Backend gaps (50)
W-0741 migration: Supplier.ruc (string nullable) (1) + form field (2) + validation (3) + test (4) → W-0744
W-0745…W-0752 allergy structured field on Cliente (migration, checkboxes form, render, filter, tests)
W-0753…W-0759 PIN cashier mode (decision doc, migration pin_hash, login toggle, keypad UI, tests, guard)
W-0760…W-0764 wishlist sync fix (diagnose fetch, error state, retry, tests)
W-0765…W-0769 negative-stock guard (constraint + friendly error + tests)
W-0770…W-0772 rename prod hash rows (script + run + verify)
W-0773…W-0777 kardex query layer
W-0778…W-0781 production variance computation
W-0782…W-0785 ingredient price-history surface
W-0786…W-0789 data-quality guards (seed/import name validation)
W-0790 G-buffer (1)

## TRACK H — Trust & feedback (60)
W-0791…W-0802 confirm modals on 12 destructive flows (delete producto/receta/ingrediente/cliente/proveedor/usuario, cancel pedido bulk, void already done, wishlist delete, benchmark delete, risk delete, zone delete, user deactivate)
W-0803…W-0812 disabled-reason tooltips (10: whatsapp generator, cobrar sin líneas, guardar sin nombre, etc.)
W-0813…W-0824 loading/error states (12: wishlist, excel import progress, board refresh, search palette, reportes gen, bank import, kardex, heatmap, exports, precio save, photo upload, seed-demo)
W-0825…W-0830 flash standardization (6)
W-0831…W-0840 tooltip pass (10 tables)
W-0841…W-0850 contrast/aria fixes from audit script (10)

## TRACK I — Tests & QA (80)
W-0851…W-0890 smoke tests ×40 (one per new/changed page)
W-0891…W-0905 Playwright flows ×15 (POS cobrar, pedido lifecycle, board status, produccion batch, cierre eod, kardex, wizard ingrediente, escandallo editor, product pricing rail, filtro toolbar, tabs pedidos, nuevo menu, ⌘K palette, cross-links, receipt print)
W-0906…W-0915 route manifest updates (10)
W-0916…W-0920 screenshot-diff hook (5)
W-0921…W-0930 perf guards (10)

## TRACK J — Content & release (130)
W-0931…W-0990 copy rewrite ×60 pages/sections
W-0991…W-1005 onboarding empty hints ×15
W-1006…W-1015 print CSS ×10 — renumber: receipt, diario, iva, libro, cierre-mensual, top, margenes, comparacion, valor-pedido, kardex
W-1016…W-1025 guia update ×10
W-1026…W-1040 dark-mode sweep ×15
W-1041…W-1060 release cycles ×20 (phases 1–6: screenshots+zip+changelog+deploy+verify ×~3 per phase)
W-1061…W-1100 buffer: critique-agent findings integration (operaciones/catálogo/finanzas sections reserved ~40 items) + final polish buffer

RENUMBER NOTE: catalog rows above use per-track numbering; final tracker will renumber linearly W-0001…W-1100 and trim buffers to land exactly 1,000 committed items (buffers are contingency, not filler).
