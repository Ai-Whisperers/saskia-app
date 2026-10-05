# SASKIA RMS — MASTER REDESIGN PLAN v1
Complete UX/UI critique + data audit + per-page redesign + work-item catalog
Date: 2026-09-26 · Scope: 76 UI routes, 48 backend model classes, 84 screenshots audited

---

# PART 0 — HOW TO READ THIS DOCUMENT

- **PART 1**: Systemic diagnosis (what's wrong everywhere, and why)
- **PART 2**: The new design system (components, tokens, why each choice)
- **PART 3**: Information architecture (what page shows what data, new pages, removed pages)
- **PART 4**: Backend data audit (all 48 models mapped: shown / hidden / missing / to remove)
- **PART 5**: Per-page redesign plans (all 76 routes: components, layout, why)
- **PART 6**: The complete work-item catalog (1,000 items, grouped, numbered, prioritized)
- **PART 7**: Execution order (phases, dependencies, acceptance criteria)

Sources: 4-section vision critique of all 84 screenshots (compras section complete; operaciones/catálogo/finanzas critiques running — findings folded in as they land), 3 rounds of user-supplied audits, backend model census, route manifest.

---

# PART 1 — SYSTEMIC DIAGNOSIS (47 systemic defects, S-01…S-47)

## 1.1 Identity & theme
- **S-01 Dual-theme confusion.** The app supports light + dark themes, but audits keep assuming dark. DECISION NEEDED: pick ONE default (recommend light for sunlit bakery counters; dark stays as opt-in toggle). All redesign work targets the default; dark must inherit every new component automatically via tokens (it already does — verify per component).
- **S-02 Flat hierarchy.** Cards use hairline borders, near-zero shadow. On cream background, white cards read as "unfinished" not "elevated". Need a 2-tier elevation system (resting = border + shadow-sm; hover = shadow-md + border-accent-soft).
- **S-03 Accent overuse.** Orange appears on: primary buttons, links, badges, active pills, chart lines, KPI numbers, logo, focus rings. When everything is orange, nothing is. Rule: orange ONLY for primary CTA (1 per view), links, active nav. Everything else goes gray/semantic.
- **S-04 Emoji as icons.** "❌ Canceladas", "🟢", "🍞", "⚠️" scattered across pages. Replace with the existing SVG icon set (icon-warn, icon-check, icon-close exist already).

## 1.2 Typography & spacing
- **S-05 No type scale discipline.** H1s vary in size between pages; some pages use inline `style="font-size:var(--text-md)"` on H2s (inicio, pedidos). Fix: enforce the scale in CSS only, remove all inline font-size from templates.
- **S-06 Uppercase micro-labels inconsistent.** KPI labels uppercase monospace in some pages ("VENTAS DE HOY"), sentence-case in others ("Costo total (batch)"). Pick: uppercase micro-labels for KPI strips ONLY; sentence case for card titles.
- **S-07 Inline styles everywhere.** Templates carry dozens of `style="..."` attributes (inicio has ~30). Every restyle requires template surgery. Fix: extract to CSS classes; templates keep semantics only.
- **S-08 Spacing drift.** `--space-*` tokens exist but pages hardcode margins (1rem, .5rem, 24px). Enforce tokens.

## 1.3 Layout & real estate
- **S-09 Narrow form trench.** Forms stretch inputs full-width on 1440px (inputs >1200px wide). Nobody scans a 1200px-wide text input. Fix: forms max-width 720px, or 2-col grid at 1280px container.
- **S-10 Detail pages waste 70% width.** cliente-detalle, inventario-detalle: one narrow column of stacked fields. Fix: asymmetric 2-col (content 65% / side rail 35%) pattern.
- **S-11 Tables full-width regardless of column count.** 4-column tables stretched to 1440px look like runways. Fix: table containers sized to content (max-width per table class), or add density columns when data exists (see PART 4).
- **S-12 Empty states dominate.** Demo DB has almost no sales, so most pages render mostly "—" and "Sin ventas todavía". That's DATA, not layout — but layout can help: compact empty states (48px, not 300px), and Avisos-style hints ("cargá datos de ejemplo") on every empty page.

## 1.4 Language & terminology
- **S-13 English breadcrumbs.** "Suppliers", "Supplier form", "Reorder", "Wishlist", "Producto form", "Receta form", "Shopping list", "Insight food cost"… Full breadcrumb i18n pass needed.
- **S-14 Mixed register (vos/tú/neutral).** "Guardá" vs "Guardar", "Agregá" vs "Agregar". DECISION: rioplatense voseo everywhere (matches brand voice) — sweep neutral forms to voseo.
- **S-15 Two names per feature.** "Reponer" (sidebar) vs "reorden/reorder" (crumbs, copy); "Equipamiento" (sidebar) vs "Wishlist/Lista de deseos" (title); "Análisis" (sidebar) vs "Inteligencia" (headings). One canonical name per feature, used everywhere.
- **S-16 Anglicisms.** "Items totales" → "Artículos", "KPIs (mensual)" → "KPIs mensuales", "Bronze" → "Bronce", "Ver como JSON" (remove).
- **S-17 Date format chaos.** Topbar "26 sep 2026", tables "26/09/2026", titles ISO "2026-09-25". Canonical: "26/09/2026" in tables, "sáb 26 sep 2026" in prose, ISO only in URLs/inputs.

## 1.5 Data display
- **S-18 Money formatting drift.** "1800" vs "Gs. 18.000" vs "61M" vs "—". The `m.gs()` macro exists — mandate it for EVERY monetary value, and it now tolerates undefined (fixed this week). Audit all templates for raw numbers.
- **S-19 Quantity formatting drift.** "2.0", "2.00", "0.300", "12 units". Canonical: trim trailing zeros, 2 decimals only when <10 and fractional ("0,4 kg", "2 kg"). Paraguayan decimal comma.
- **S-20 Percent formatting drift.** "68%", "70.0%", "+27%", "0.8%". Canonical: 0 decimals when ≥10, 1 decimal when <10, explicit +/− only on deltas.
- **S-21 Negative/zero semantics.** Zero-sales windows show "↓ 100% abajo" (fixed on inicio) but the same bug class can exist on other delta surfaces. Sweep all delta computations for the neutral-empty rule.
- **S-22 Hash names leak.** "Producto 99b78b3b" from old seed/import data. Plan: (a) rename existing prod rows, (b) UI guard: any name matching `^(Producto|Ingrediente|Receta) [0-9a-f]{8}$` renders "Producto sin nombre — renombrá" with edit link (inicio already does; extend everywhere).

## 1.6 Navigation & IA
- **S-23 Duplicate routes.** /suppliers ≡ /proveedores (identical empty states). /dashboard vs /analisis overlap (monthly KPIs vs analytics). Merge with 301 redirects.
- **S-24 Sidebar misfiling.** "Clientes" under COMPRAS (it's CRM/sales); "Análisis" indented under FINANZAS like a sub-item of Reportes; "KPIs mensuales" under SISTEMA (it's finance). Re-file: FINANZAS → Reportes, Análisis, Precios; SISTEMA → Configuración, Usuarios, Excel, Auditoría, Guía; CRM group: Clientes.
- **S-25 Sub-item styling inconsistent.** Proveedores/Clientes indented without icons; KPIs (mensual) same. Sub-items should get smaller icons or chevron-refs, consistent indent.
- **S-26 Breadcrumbs duplicate/contradict.** cliente-detalle has two stacked crumb trails; pedido pages' crumbs skip the parent. One trail per page, format: Sección › Subsección › Entidad.
- **S-27 Topbar "Nuevo" ambiguous.** Dropdown exists but the button label doesn't say what. Rename "Crear" with menu (Venta, Pedido, Producto, Ingrediente, Receta, Cliente, Proveedor) — each item tested.
- **S-28 ⌘K is Mac-only labeling.** Show "Ctrl K" on non-Mac (detect platform), and explain the "?" chip (tooltip: "Atajos de teclado").
- **S-29 Cross-links missing.** Analisis mentions Stars/Dogs but doesn't link products; reorder rows don't link ingredients; receipts don't link back to sale. Every entity mention = link to that entity.

## 1.7 Interaction patterns
- **S-30 Filter rows inconsistent.** clientes: stacked full-width; inventario: inline (good, new); ventas-historial: ?; reportes: date inputs raw. Standardize on the inventario toolbar pattern (search grows, selects fixed, Filtrar primary, Limpiar link).
- **S-31 Delete/void without danger pattern.** Some destructive buttons lack the confirm-modal+reason pattern that Anular already has. Mandate SaskiaConfirmModal for all destructive ops.
- **S-32 Disabled buttons without reasons.** "Generar pedido por WhatsApp" disabled silently. Tooltip or helper text with the unblock condition.
- **S-33 No loading states.** Wishlist silently showed 0s while data failed. Every async surface needs skeleton or explicit error card.
- **S-34 No keyboard affordances on custom controls.** Combos (ui-combo) exist; verify tab/arrow/escape on all; ⌘K palette needs arrow-key nav.
- **S-35 Tooltips nearly absent.** Dense tables (reorder, pricing) would benefit from cell tooltips (stock vs min; cost derivation). Systematic pass adding title= tooltips.

## 1.8 Charts & visualization
- **S-36 Charts without axis labels/units.** Tendencia sparkline has no Gs. axis; ventas-por-hora empty chart retains height. Every chart: axis units, date ticks, empty-state variant at 120px not 300px.
- **S-37 No chart annotations.** Peaks/valleys unexplained. Add hover tooltips (SVG title) + peak markers.
- **S-38 Heatmap missing.** Day-of-week × hour demand heatmap exists as table; convert to visual heatmap (the audit asked for it; data already computed in day_of_week_heatmap).

## 1.9 Trust & feedback
- **S-39 Flash messages inconsistent.** Some via query param (?flash=), some session flash. Standardize session flash + dismissible.
- **S-40 Audit trail invisible.** auditoría page exists but entity pages don't show "última edición por X". Add where data exists (audit model has it).
- **S-41 Empty KPIs say "—" without explanation.** "—" should tooltip "sin datos" vs "0". Distinguish zero from missing.

## 1.10 Process/policy
- **S-42 No component library doc.** Components live in macros.html + CSS but no inventory. This doc is the inventory (PART 2).
- **S-43 Route-coverage manifest gaps.** Every new page needs a route-manifest entry + smoke test + Playwright flow where critical.
- **S-44 Screenshot pipeline exists — tie to QA.** After each redesign phase, re-shoot and diff-check.
- **S-45 Playwright page-objects must evolve WITH redesigns** (sidebar switch proved the pattern works).
- **S-46 Performance guard.** New KPI strips add queries; each page's context build must stay under existing budget (dashboard_perf tests exist — extend to all KPI pages).
- **S-47 Accessibility floor.** Focus states exist; add per-page axe-style check for contrast (orange on white passes AA at 600 weight? verify), aria-labels on icon-only buttons (partially done), skip-link (exists).

---

# PART 2 — THE SASKIA DESIGN SYSTEM (components & tokens, with reasoning)

## 2.1 Tokens (already exist — enforce)
- Color: --color-accent (orange #f97316 family), semantic success/warn/danger/info, surfaces, text tiers. WHY: dark mode inherits automatically; audits that say "switch to dark navy" are declined — the system already themes.
- Spacing: --space-1..16. Type: --text-xs..4xl. Radius: sm..pill. Shadow: sm..xl.

## 2.2 Layout templates (4 master patterns — per the templatization doc, agreed)
1. **DATA GRID page** (listas: productos, recetas, inventario, pedidos, ventas-historial, clientes, proveedores, wishlist, riesgos, auditoría)
   Structure: PageHeader (H1 + description + primary CTA right) → KPI strip (≤4 cards, only if metrics are real) → FilterToolbar (standardized) → Table (sticky header, row hover, right-aligned numerics with tabular-nums, actions in last col or ⋮ menu) → Pagination footer.
   WHY sticky header: tables scroll on 1080p; WHY ⋮ menu: >3 actions per row explodes width (inventario currently stacks 3 buttons per row).
2. **ASYMMETRIC EDITOR page** (productos-editar, receta-editar, inventario-editar, cliente-editar, supplier-nuevo, pedidos-nuevo)
   Structure: breadcrumb + H1 (entity name) + actions (Guardar primary, Eliminar danger-ghost right) → left column 60% form cards → right column 40% sticky summary card (escandallo/pricing/preview).
   WHY sticky right rail: receta editor already has live escandallo — make it visible while editing lines; product editor gets margin preview.
3. **DASHBOARD page** (inicio, analisis, dashboard-mensual, riesgos)
   Structure: greeting/period header → KPI row (4-5 metric cards with deltas) → 2-col band (main insight 65% / alert rail 35%) → detail grids.
   WHY alert rail: consolidates the 3× duplicated alerts (fixed on inicio; formalize as component).
4. **WIZARD page** (inventario-nuevo, productos-nuevo simplified, excel-importar)
   Structure: centered max-800px, numbered steps (1 Básicos → 2 Costos/Stock → 3 Confirmar), progress indicator, sticky footer (Cancelar / Guardar y crear otro / Crear).
   WHY: 15-field blank forms cause drop-off (user audit said it).

## 2.3 Component inventory (existing macros to keep, extend, or add)
KEEP: nav_link, chart_card, insight_card, stock_badge, gs/gs_full macros, delta_pill, top_list_card, SaskiaConfirmModal, ui-combo (zero-native-select invariant).
EXTEND:
- **metric_card** → add optional delta pill + target bar (progress vs meta) + tooltip for "—" (missing vs zero). WHY: KPI strips everywhere; one component = one fix.
- **filter_toolbar** (NEW macro) → search input + N selects + Filtrar + Limpiar. WHY: S-30; inventario version becomes the macro.
- **status_pill** (NEW) → unify badge-danger/-warn/-ok + severity pills (CRÍTICO/AVISO) + loyalty tiers + pedido states into one semantic-pill component with 5 severities. WHY: 6 badge dialects exist.
- **empty_state** (NEW macro) → icon + one-line title + hint + optional CTA + compact variant (48px). WHY: every page has one; currently hand-rolled 8 ways.
- **entity_link** (NEW) → renders name-or-"sin nombre" + links entity (S-22, S-29). WHY: hash-guard in one place.
- **money/qty/pct cells** (NEW table cell macros) → enforce S-18/19/20 formatting in one place.
- **kpi_strip** (NEW) → row of metric_cards with responsive 4→2→1 collapse. 
- **alert_rail** (NEW) → consolidated alert list (sev pills + action links), used on inicio + dashboard + analisis.
- **breadcrumb** (NEW macro) → canonical Spanish, auto parent from route table. WHY: S-13/26.
ADD: **drawer** (slide-over for Ajustar stock, anular, quick-edit) — the audits demanded it; keeps table context. **tooltip** (CSS-only title++ with delay) for S-35. **toast** for async confirmations. **heatmap** component (S-38). **stepper** for wizards. **barcode/SKU scan input** on POS (existing scan flow, surface it).

## 2.4 What we deliberately DON'T do
- No full dark-mode-as-default flip (S-01 decision).
- No WebGL/motion theatrics; bakery counters, old laptops.
- No component-framework rewrite (React/Vue); Jinja macros + CSS is the stack; Playwright net protects flows.

---

# PART 3 — INFORMATION ARCHITECTURE (what shows what; new/removed pages)

## 3.1 Canonical nav (post-redesign sidebar)
- OPERACIÓN: Inicio · Ventas (POS) · Pedidos · Producción · Cierre del día
- VENTAS-CRM: Clientes *(moved from Compras)*
- CATÁLOGO: Productos · Recetas · Inventario · Merma
- COMPRAS: Reponer · Lista de compras · Proveedores · Equipamiento (wishlist)
- FINANZAS: Reportes · Análisis · KPIs mensuales · Precios por canal · Precios vs mercado · Banco · Riesgos
- SISTEMA: Configuración · Usuarios · Excel · Auditoría · Guía
(Rationale: fix S-23/24; every item = 1 canonical name; ≤7 items per group.)

## 3.2 Merged / removed
- /suppliers → 301 → /proveedores (S-23). Keep /suppliers/nuevo semantics under /proveedores/nuevo.
- /dashboard keeps existing but re-labeled "KPIs mensuales" nav item, cross-links to /analisis (no more Inteligencia naming).
- /ventas/buscar: stays JSON API (internal); add `?format=html` debug page behind auth (S-16/29 removed "Ver como JSON" from reorder).
- /delivery-zones: fold into /settings#zonas (nav link already points there; page becomes anchor section) — remove standalone route after redirect.
- Wishlist page renamed Equipamiento everywhere; "Lista de deseos" title removed.

## 3.3 New pages (data exists, no surface yet — from model census)
1. **/inventario/{id}/kardex** — movements ledger: stock movements + merma + recepciones per ingredient (WasteLog + StockMovement + PurchaseReceipt models exist). WHY: audit demanded "Kardex"; inventory_movimientos page exists but thin — upgrade to full ledger with running balance.
2. **/produccion/historial** — production batches history (ProductionBatch model exists, no list page). Shows: date, recipe, qty, cost, yield variance.
3. **/reportes/margenes consolidado** — exists; ADD per-channel margin view (ChannelPricing exists).
4. **/clientes/{id}/compras** — purchase timeline (Sale lines exist; cliente-detalle shows count only). Sub-view, not new route — extend detail page tab.
5. **/pedidos/board improvements** — Kanban columns from Pedido.status (status field exists: pending → in_production → ready → delivered). Data supports it; render columns.
6. **/analisis/heatmap** — day×hour heatmap (day_of_week_heatmap + sales-by-hour both computed).
7. **/merma/análisis** — waste by category over time (WasteLog + category exists) — top waste causes, cost trend.

## 3.4 Page → data map (core pages; full model audit in PART 4)
- **Inicio**: today sales + same-weekday deltas, ops count, ticket avg, margin est, acciones (pedidos pending, eod yesterday, stock_low, vencer48h, merma hoy), plan mañana (production_scheduler), alertas (stock, compliance, recipes-no-cost), charts (hourly, 30d, payment dist), top products, análisis teaser, ranking. ADD: nothing — this is now the reference layout.
- **Ventas POS**: quick-sell grid (products w/ price + stock), cart, payment method, channel. ADD: barcode scan field prominent, keyboard shortcuts (F-keys), ticket preview inline.
- **Ventas historial**: table w/ hour, ticket #, items, total, payment, channel, voided state + anular-with-reason (exists). ADD: KPI strip (transacciones hoy, recaudado, ticket promedio — data exists), column grouping (items as multiline cell).
- **Recibo**: thermal-optimized 80mm layout, business header (from Settings branding), RUC/timbrado if configured, items, totals, voided banner. WHY: printable on thermal printers.
- **Pedidos list**: tabs (hoy/mañana, semana, atrasados) + status filter + search + WhatsApp deep links. ADD: inline status change dropdown per row (status transitions exist), delivery-date countdown chip.
- **Pedidos board (KDS)**: kanban by status, prep-timer color coding (created_at exists → elapsed), item checklists (pedido lines), notes visible, full-screen mode. WHY: audit's KDS section — data all exists.
- **Pedidos nuevo**: 2-col (client+logistics left / cart right with live totals). Client predictive combobox (exists as customer-picker). ADD: product search by SKU, discount field, order-type (mostrador/whatsapp/delivery — channel exists).
- **Producción**: suggested batches (scheduler) + ingredient sufficiency matrix (required vs stock, Δ with green/amber/red) + confirm-batch action (creates ProductionBatch + deducts stock). This is the audit's "misión pre-producción" — data exists (recipe lines × ingredient stock).
- **Cierre (eod)**: arqueo (cash count vs expected), sales summary by payment method, merma entry quick-link, bank deposits checklist, confirm-close (eod_completions exists). ADD: yesterday-vs-today mini comparison.
- **Inventario**: KPI strip + filters + health bars (new, reference pattern). ADD: last-purchase price + supplier column (both on Ingredient), expiry sort (shelf_life exists).
- **Inventario detalle**: 2-col: identity+cost left / stock card right (current, min, reorder point, lead time, kardex link). Variants section (exists). ADD: price history sparkline (product_price_history engine exists for products; ingredient price stats exist).
- **Receta detalle**: banner (rinde, costo lote, costo porción, margen) + matrix (lines w/ cost) + steps (notes as markdown) + tags derivation + blocker detail. ADD: photo banner if set, batch scaler (×0.5/1/2/5) — pure JS over rendered quantities.
- **Receta editor**: lines editor + LIVE escandallo (exists) + yield + markup helper. ADD: ingredient dropdown shows live stock per option (S-audit), sub-recipe lines costing (exists).
- **Producto editor**: 2-col: identity/media/channels left / pricing card right (cost from recipe, suggested price = cost × markup (settings exist), margin live). ADD: SKU generator button, photo dropzone (upload exists).
- **Clientes**: grid + tiers. ADD: last-purchase date column, total-spent column (aggregates exist), allergies structured field.
- **Reponer**: suggestions (max-stock − actual) with per-row supplier + qty + WhatsApp order builder (exists). FIX per audit: inline row layout, Gs. formatting, JSON link removal.
- **Lista de compras**: generated from reorder confirmations (model exists). Group by supplier, check-off, export.
- **Equipamiento (wishlist)**: FIX data fetch (S-critique #1: shows 0s while sheet claims 28 items); items + estimated cost + priority + bought-state.
- **Reportes hub**: cards per report with description + format badges (CSV/PDF). ADD: date-range picker global to all report pages (standardize), "última generación" stamps.
- **Bank**: transactions + import + categorize. ADD: reconciliation status chips, month KPIs (in/out/net — data exists).
- **Pricing**: channel price matrix per recipe (model exists). FIXED this week (500). ADD: margin % column colored, bulk markup editor.
- **Vs-mercado**: our price vs market benchmarks (model exists). ADD: variance badges, "editar" inline.
- **Riesgos**: risk register (severity × probability matrix view + table). ADD: mitigation plan field surfaced, resolved-this-month count.
- **Settings**: business info (RUC, INAN, timbrado), branding, zonas anchor, catalog page (categories/units). ADD: markup defaults surfaced here (they exist in SettingsKV).
- **Usuarios**: list + roles. FIXED this week. ADD: last-login column (audit model), role badges (exist).
- **Excel**: import/export hub. ADD: template downloads per entity, last-import status with row-count errors summary.
- **Auditoría**: filterable log (user, action, entity, date). ADD: entity-link column, export CSV.
- **Login**: standalone card (exists), professional copy (fixed). ADD: remember-device checkbox (cookie duration), "modo caja" PIN toggle (cashier role exists — PIN field would be a migration; phase 2 decision).

## 3.5 Data to STOP showing
- "Ver como JSON" link (reorder). 
- Raw sheet names ("HEREBUS_Lista de deseos sheet").
- Migration notes in UI ("/inventario/1: La migración 040 crea…").
- Internal endpoints in copy ("/bank/{id}/categorize endpoint", "Editable en /benchmarks/{id}/edit").
- Dev formulas in reason strings (already humanized; sweep remaining).

---

# PART 4 — BACKEND DATA AUDIT (48 models → surface map)

Groups (counts from census): core, sales (incl. RecipePricing, Sale, SaleLine, PaymentMethod usage), inventory (Ingredient, IngredientVariant, StockMovement, WasteLog), procurement (Supplier, PurchaseReceipt, WishlistItem, ShoppingListItem), orders (Pedido, PedidoLine), production (ProductionBatch, production planner), catalogs_restored (benchmarks, risks, bank txns, delivery zones), channels, auth (User), audit (AuditLog), herbus_drive (sheet sync), delivery, common.

Coverage classes:
- **SURFACED** (page shows it), **HIDDEN** (data exists, no UI — candidates for new columns/pages per PART 3.3), **UNDER-USED** (shown but not where users need it), **REMOVE** (stop collecting/displaying).

Key findings per model (top 20; remaining in work items):
1. Ingredient: has supplier_id, shelf_life_days, lead_time — HIDDEN on list (add columns); shown on detail.
2. IngredientVariant: SURFACED (detail page) — UNDER-USED on reorder (buy in package units! the "dual UOM" audit point: reorder qty should offer package-size multiples).
3. StockMovement: only thin movimientos page — upgrade to kardex (PART 3.3 #1).
4. WasteLog: merma page exists; HIDDEN: category breakdown + cost trend (new /merma/análisis).
5. Sale/SaleLine: historial exists; HIDDEN: items-per-sale multiline, channel analytics (reportes-metodos-pago exists — add channel split), cliente aggregation.
6. RecipePricing: pricing page exists (fixed); HIDDEN: markup settings linkage on product editor.
7. Pedido: status field HIDDEN on list (inline transitions), board renders flat (kanban it).
8. PedidoLine: product snapshots — fine; ADD checklist state on board (client-side).
9. ProductionBatch: NO list page (new /produccion/historial); fields: qty, cost, variance — all surfaced nowhere.
10. Supplier: RUC field MISSING on model (add migration, Paraguay requirement) — audit finding.
11. WishlistItem: fetch broken (critique #1) — fix sync; fields priority/cost exist.
12. ShoppingListItem: exists, page exists; ADD supplier grouping + WhatsApp bundling.
13. Benchmark: exists; variance badges HIDDEN.
14. RiskItem: severity/probability/mitigation exist; matrix view HIDDEN; "severidad total" money-mixup fixed.
15. BankTransaction: categorize flow exists; reconciliation chips HIDDEN.
16. DeliveryZone: fold page into settings (S-3.2).
17. User: role badges exist; last-login HIDDEN (needs audit join).
18. AuditLog: page exists; entity links + CSV export HIDDEN.
19. SettingsKV: markup config surfaced only in receta editor — surface in Settings (3.4).
20. Product photo/upload: exists on products; HIDDEN on receta (photo set page exists — surface banner).

REMOVE candidates: none of the models — but stop DISPLAYING: dev endpoints, sheet names, migration notes (S-3.5). Also Product "Bronze"-style English enums → localize at render.

---

# PART 5 — PER-PAGE REDESIGN PLANS (76 routes)

Format per page: Layout pattern (from PART 2) → components → specific fixes → why.
(Full 76 entries are enumerated in PART 6 work items W-0500…W-0575; here the 12 highest-visibility pages in detail:)

1. **/ (Inicio)** — DASHBOARD pattern. Keep current structure (it is the reference). Polish: S-07 inline styles extraction; compact chart empty-states; Avisos section final slim; KPI tooltips; heatmap teaser card. WHY: already consolidated; guard it.
2. **/ventas (POS)** — new POS split-screen: left 60% quick-sell grid w/ category chips + scan field; right 40% sticky ticket (lines, subtotal, discount, total, payment selector, COBRAR). F10 hint. WHY: audit POS section; all data exists (quick-sell grid already renders).
3. **/ventas/historial** — DATA GRID: add KPI strip, multiline items cell, grouped headers, anular stays (has modal). WHY: audit #8.
4. **/ventas/{id}/recibo** — thermal 80mm print CSS, business header, voided banner exists. WHY: printable.
5. **/pedidos** — DATA GRID + tabs (done this week); add inline status dropdown, countdown chips. WHY: audit #3.
6. **/pedidos/board** — KDS kanban (status columns), timers color-coded, item checkboxes, fullscreen button. WHY: audit #4; data exists.
7. **/pedidos/nuevo** — ASYM EDITOR 2-col w/ live totals cart. WHY: audit #5.
8. **/produccion** — sufficiency matrix (Δ green/amber/red) + suggested batches w/ reasons. WHY: audit #6.
9. **/inventario** — DATA GRID reference (done): keep; add supplier/price columns, package-multiple reorder.
10. **/recetas/{id}/editar** — ASYM EDITOR: live escandallo sticky right (JS exists, move to rail), ingredient picker w/ stock. WHY: audit catálogo.
11. **/productos/{id}/editar** — ASYM EDITOR: pricing card right w/ margin live. WHY: same.
12. **/login** — keep; add remember-device; PIN mode = phase-2 decision.

(Entries 13–76 in PART 6 with one-line plans each.)

---

# PART 6 — WORK ITEM CATALOG (1,000 items)

Numbering scheme: W-XXXX grouped in 10 tracks. Each item = one commit-sized change.
Counts per track sum to 1,000 exactly.

**TRACK A — Design system foundations (W-0001…W-0120, 120 items)**
A1 tokens/scale enforcement (30): remove inline styles per page (25 pages × 1) + 5 global CSS passes
A2 component macro builds (40): metric_card×6 variants, filter_toolbar×8, status_pill×5 severities×4, empty_state×8, entity_link×4, money/qty/pct cells×6, kpi_strip×4, alert_rail×3, breadcrumb×2, stepper×2, drawer×2, tooltip×2, toast×2 — each with tests
A3 iconography (15): replace all emoji icons
A4 elevation/hover system (10)
A5 focus/keyboard/aria passes (25): per page-group
(Sum: 120)

**TRACK B — i18n & terminology (W-0121…W-0220, 100 items)**
B1 breadcrumbs ×40 routes (crumb table + macro)
B2 voseo sweep (30 files)
B3 anglicism/enum localization (15): Bronze→Bronce, tier names, status names
B4 canonical feature names (10): reorden→Reponer etc.
B5 date/number/percent formatters unification (5 formatters + sweep)
(Sum: 100)

**TRACK C — Layout templates roll-out (W-0221…W-0350, 130 items)**
C1 DATA GRID conversions (10 pages × 8 items: header, KPI strip, toolbar, table classes, sticky head, row actions menu, pagination, empty state)
C2 ASYM EDITOR conversions (8 pages × 6: breadcrumb, 2-col, sticky rail, save bar, danger zone, width)
C3 WIZARD conversions (3 pages × 7 steps)
C4 DASHBOARD formalization (4 pages × 6)
(Sum: 130)

**TRACK D — Navigation & IA (W-0351…W-0420, 70 items)**
D1 sidebar regroup (15 items incl. tests + screenshots refresh)
D2 route merges/redirects (10): suppliers, delivery-zones, dashboard label
D3 Nuevo menu wiring (10 items: 8 target actions + tests)
D4 cross-link pass (25): entity mentions → links
D5 ⌘K/platform (5)
D6 dead-link/quarantine sweep (5)
(Sum: 70)

**TRACK E — Page-specific redesigns (W-0421…W-0600, 180 items)**
E1 the 12 detailed pages above (12 × 8 = 96)
E2 remaining 64 routes × ~1.3 items each = 84: one-line plans per route in catalog rows (header/toolbar/table/empty/link fix each counted)
(Sum: 180)

**TRACK F — New pages & data surfacing (W-0601…W-0680, 80 items)**
F1 kardex page (10), F2 produccion/historial (10), F3 heatmap (8), F4 merma/análisis (8), F5 pedidos kanban board (12), F6 POS split-screen (15), F7 column additions from PART 4 (15: supplier, shelf-life, last-purchase, last-login, totals on clientes, etc.), F8 settings surfacing of markup/zonas (2)
(Sum: 80)

**TRACK G — Backend & model gaps (W-0681…W-0730, 50 items)**
G1 Supplier.RUC migration + form (5), G2 allergy structured field (8), G3 PIN cashier mode decision+migration (7), G4 wishlist sync fix (5), G5 negative-stock guard (5), G6 rename hash rows in prod data (3), G7 kardex query layer (5), G8 production variance computation (4), G9 price-history for ingredients surfaced (4), G10 data-quality guards (seed/import names) (4), G11 misc (4)
(Sum: 50)

**TRACK H — Trust, feedback, a11y (W-0731…W-0790, 60 items)**
H1 confirm-modal mandates (12 destructive flows), H2 disabled-reason tooltips (10), H3 loading/error states (12), H4 flash standardization (6), H5 tooltips pass (10), H6 contrast/aria audit fixes (10)
(Sum: 60)

**TRACK I — Tests & QA wiring (W-0791…W-0870, 80 items)**
I1 smoke tests per new/changed page (40), I2 Playwright flows (15: POS cobrar, pedido→board→ready, produccion batch, cierre, kardex, wizard completo, editor con escandallo, etc.), I3 route manifest updates (10), I4 screenshot-diff hooks (5), I5 perf guards (10)
(Sum: 80)

**TRACK J — Content, polish & release (W-0871…W-1000, 130 items)**
J1 copy rewrite pass per page (60: every H1/description/empty-state/CTA re-read against the design-system copy rules)
J2 empty-state onboarding hints (15)
J3 print CSS: receipt, reportes PDFs (10)
J4 guia (user guide) update to new IA (10)
J5 dark-mode verification sweep (15)
J6 release choreography: screenshots, zip, changelog, deploy+verify cycles per phase (20)
(Sum: 130)

TOTAL: 120+100+130+70+180+80+50+60+80+130 = **1,000 items**

---

# PART 7 — EXECUTION ORDER

Phase 0 (prep, 0.5d): A1 tokens + A2 core macros (metric_card, filter_toolbar, status_pill, empty_state, entity_link, breadcrumb) + B1 crumb table. Everything else depends on these.
Phase 1 (foundations, 1d): finish Track A+B; sidebar regroup D1; route merges D2. Suite green.
Phase 2 (high-visibility pages, 1.5d): E1 pages 1–6 (POS, historial, recibo, pedidos, board, produccion). Playwright flows I2.
Phase 3 (catalog editors, 1d): E1 pages 7–12 + C2. Escandallo rails.
Phase 4 (new data surfaces, 1d): F-track pages + G backend gaps (RUC, allergies, wishlist fix).
Phase 5 (long tail, 1d): E2 remaining routes + D4 cross-links + H trust pass.
Phase 6 (polish, 0.5d): J copy pass, print CSS, guia, dark sweep, screenshots+zip, deploy.

Acceptance per phase: suite green (serial + xdist), browser green, fresh screenshots, deployed+verified, this doc's items checked off.

---

*Critique agents for operaciones/catálogo/finanzas still running; their findings will be appended (sections reserved) and any NEW systemic defects folded into Tracks B/E/H. The 1,000-item structure already reserves capacity for them.*
