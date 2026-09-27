# Saskia RMS — Batch 3 UX/UI Audit (Compras / Reportes / Admin)
*Principal review by senior UX/UI lead + QA architect. 14 pages analyzed.*

> **Reading note:** Several pages were screenshotted against an empty / newly-seeded database (Suppliers empty, Riesgos 0/0/0, Audit log "No hay entradas", Lista de compras vacía, Precios 0 recetas, vs-mercado 1 producto, Wishlist 0, Bank 0 txns). Where state is empty, the principal still scores **information architecture, navigation, density, and readiness for the populated state** — because a real bakery owner will see this UI immediately after install and judge it then. The principal's bar is "useful on Day 1 with no data", not "useful once data exists".

---

## 1. `suppliers.png` — Proveedores / Suppliers (list, empty state)

**Personas:** counter staff (low), owner-finance (high), production-baker (high), new user (high — first impression), auditor (low)

### Counter staff (hat 1)
- **Now:** Empty-state centered: bold "No hay proveedores todavía", explainer copy ("Agregá proveedores para poder contactarlos desde la página de reorden."), and a single orange CTA "Agregar el primero". Header has breadcrumb (Inicio › Proveedores), a primary "Nuevo proveedor" button, and the global "Nuevo" command-bar button at top-right. Left nav active-state on "Proveedores" rendered in soft orange.
- **Missing:** No search box, no filter chips, no import-from-CSV shortcut, no "+ Agregar desde un pedido" shortcut, no "Proveedor frecuente" quick-add. No KPI tiles (e.g., "Total: 0", "Con contacto: 0", "Sin WhatsApp: 0") — the page is just a button and a void. Counter staff doesn't normally own this list but would glance at it; nothing here to glance at.
- **Top add:** **"Pegar lista de WhatsApp"** — paste the last 10 WhatsApp messages you forwarded to suppliers and let a regex/heuristic extract names + phone numbers into draft rows. Kills a real-world 20-minute pain.

### Owner-finance (hat 2)
- **Now:** Empty page. No KPIs. No density. Just the empty-state CTA.
- **Missing:** KPI strip ("0 proveedores", "0 con RUC", "Gs. comprado en el mes", "Top proveedor por gasto"), table column list to set expectations, recent-activity feed ("Última edición por …"), bulk-actions hint, and "Duplicados" badge / link to the dedup page (which exists at `/suppliers-dup` but is not surfaced from here).
- **Top add:** **KPI strip + a "Ver posibles duplicados" pill** in the header that auto-detects Levenshtein <2 and routes to the dedup page. Finance hates duplicate suppliers because they double-pay invoices.

### Production-baker (hat 3)
- **Now:** Empty. Nothing to do here for a baker.
- **Missing:** A "Mis proveedores frecuentes" shortcut pre-filtered to the bakery's working set (the 3-5 they actually call on Monday morning). Also a "Pedidos pendientes de recibir" tile pointing at incoming shipments.
- **Top add:** **Quick-call / Quick-WhatsApp row** once populated — one tap to call the supplier whose stock is below mínimo. Today the link lives on `/reorder` but it's not surfaced here.

### New user (hat 4)
- **Now:** Clean empty-state, clear CTA, descriptive copy that explains *what suppliers are for* ("contactarlos desde la página de reorden"). This is actually one of the better empty-states in the system.
- **Missing:** No "Cómo se usa" expandable, no seeded demo data option, no video/GIF, no "Importar CSV" example download. No keyboard hint (e.g., the visible "⌘K" badge in header suggests the global command palette could open this list — but no documentation of that).
- **Top add:** **Inline 30-second "Cómo funciona" expandable** that walks the new user through: create supplier → attach to ingredient → reorder page auto-pulls it.

### Auditor (hat 5)
- **Now:** No audit visibility on this page. No "Created by / last modified / last contact" metadata anywhere visible.
- **Missing:** Creation date, last-modified-by, supplier status (active/paused/blacklisted), spend YTD, "ver en auditoría" deep link.
- **Top add:** **"Última actividad" column** (default hidden, toggled by auditor persona) showing the last action and the actor. Without it, auditors have to remember to cross-reference `/auditoria`.

### Complete design wishlist
- **KPI tiles (4):** Total proveedores · Con WhatsApp · Sin contacto hace 30d · Gs. comprado MTD
- **Filter chips:** Todos · Activos · Pausados · Sin contacto · Con RUC · Por categoría (panificados, packaging, limpieza, etc.)
- **Bulk action bar:** Pausar · Asignar categoría · Exportar CSV · Combinar duplicados
- **Smart suggestions panel:** "Posibles duplicados: 2" (chip), "Sin WhatsApp: 1" (chip), "Sin RUC: 3" (chip)
- **Search box** at the top of the list (currently absent)
- **"Pegar de WhatsApp" paste-to-parse shortcut**
- **Sort indicators** on column headers
- **Pagination + page-size selector** at the bottom
- **CSV import wizard** with column mapping preview
- **Empty-state illustration** (a stylized clipboard + truck) — current copy is good but visually flat
- **Quick-action hover menu** per row: call · WhatsApp · ver reorden · editar · archivar
- **Status dot** with semantic color (green active / amber stale / gray paused)

### Quality-of-life touches
- Tiny green dot on the "Saskia RMS v1.0" footer pill (cute, but unexplained — needs a tooltip "online")
- Add `⌘N` keyboard shortcut badge to "Nuevo proveedor" button (matches global ⌘K for search)
- "Agregar el primero" → "Agregar mi primer proveedor" (warmer, more personal)
- Hovering on a supplier row shows a subtle phone-icon with WhatsApp/call tooltip
- After creating first supplier, replace empty state with celebratory microcopy ("¡Listo! Ya podés crear tu primera lista de reorden")
- Accessibility: empty-state CTA needs `aria-live="polite"` and focus management
- Subtle confetti only on first-ever supplier (not on every navigation)

### Defects
- **P0:** No way to actually see suppliers until you create one — but the page is reachable and discoverable from the nav, so a new user might assume the system is broken.
- **P1:** No search/filter infrastructure even in code-stub form; design has to be re-architected when the first row lands.
- **P1:** Empty-state CTA label says "Agregar el primero" but the page-level CTA says "Nuevo proveedor" — inconsistency.
- **P2:** Breadcrumb shows "Inicio › Proveedores" but there's no breadcrumb on the new-supplier screen back to "Proveedores" with state preserved.
- **P2:** Left-nav "Compras › Reponer" sits as a sibling to "Proveedores" which is correct, but the sub-items (Lista de compras, Proveedores, Equipamiento) are all under "Compras" without visual grouping — they're all just flat links at the same indent.
- **P2:** Hover state on the active nav item ("Proveedores") has a soft orange background that disappears when the cursor moves — works but feels less sticky than other sidebar UIs (e.g., Notion).

---

## 2. `suppliers-dup.png` — Proveedores duplicados / Duplicate detection

**Personas:** counter staff (low), owner-finance (high), production-baker (low), new user (low), auditor (medium)

> ⚠️ **Critical observation:** This screenshot is **identical** to `suppliers.png` — the same empty state, same breadcrumb, same "No hay proveedores todavía" copy. Either (a) the page is actually a re-route to the same empty index, (b) the dedup feature ships only when ≥2 suppliers exist (which is fine — but then the URL shouldn't be exposed in docs/screens), or (c) the screenshot was mis-captured. This is itself a P0 finding.

### Counter staff (hat 1)
- **Now:** Same empty state as the main suppliers page.
- **Missing:** A real duplicate-detection table with similarity scores, side-by-side merge preview, and "Mantener A / Mantener B / Combinar" actions.
- **Top add:** **A "force-show" toggle** in the empty state that explains "Cuando tengas 2+ proveedores con nombres parecidos aparecerán acá" and links back to the regular index.

### Owner-finance (hat 2)
- **Now:** Empty.
- **Missing:** Everything. The whole reason this page exists — to prevent double-payments to what is actually one supplier — is invisible.
- **Top add:** **Side-by-side merge preview** with a checkbox matrix ("Mantener nombre de A / teléfono de B / RUC de C"). With audit trail of who merged and when.

### Production-baker (hat 3)
- **Now:** Not relevant.
- **Missing:** Not relevant.
- **Top add:** Nothing.

### New user (hat 4)
- **Now:** Confusion — "Did I land on the wrong page?"
- **Missing:** A clear "Aún no tenés duplicados" empty state that distinguishes this from the main index.
- **Top add:** **Differentiated empty state** ("✓ 0 duplicados detectados. Última revisión: nunca. [Buscar manualmente]").

### Auditor (hat 5)
- **Now:** No duplicates surfaced.
- **Missing:** Audit log entry every time a merge happens — `supplier.merge(A → B)`.
- **Top add:** **"Historial de fusiones" tab** with timestamp, actor, and the two suppliers that were combined.

### Complete design wishlist
- **Similarity scoring** (Levenshtein + token-overlap) shown as percentage badges
- **Side-by-side diff view** with field-by-field "Take from A / Take from B / Custom" controls
- **Merge preview** showing resulting supplier row before commit
- **"Bulk suggest" mode** — auto-suggest 10 likely duplicates based on phone last-7-digits, address, or RUC
- **History log** of past merges
- **Empty-state with countdown** ("Escaneando 0 proveedores…")
- **"Force a check" button** that re-runs the dedup algorithm
- **Whitelist** of known aliases that should not be flagged
- **Export** the duplicate list to CSV for offline review
- **One-click merge** with confirm modal

### Quality-of-life touches
- Toast confirmation after merge with "Deshacer (5s)" affordance
- Keyboard arrow-keys to navigate between suspected duplicate pairs
- Color-coded severity (red = 95%+ match, amber = 80-95%, gray = ignore)
- Inline "Last reviewed" timestamp
- Tooltip on the merge button explaining audit-trail implication

### Defects
- **P0:** Page screenshot is **byte-identical** to `suppliers.png` — either the route is broken, the doc author captured the wrong screen, or the dedup UI was never built. Must verify before claiming feature parity.
- **P0:** Even when working, the URL `/proveedores/duplicados` is not surfaced from `/proveedores` — there's no chip, no badge, no link. Orphan route.
- **P1:** Sidebar does not have a "Duplicados" item; this is the kind of housekeeping owners never remember to check.

---

## 3. `supplier-nuevo.png` — Nuevo proveedor / New supplier form

**Personas:** counter staff (medium), owner-finance (high), production-baker (medium), new user (high), auditor (low)

### Counter staff (hat 1)
- **Now:** Single-column form. Required "*" on `Nombre del proveedor`. Fields: Nombre · Persona de contacto · Teléfono · Email · Dirección (textarea) · Notas (textarea). All placeholders show real Paraguayan examples (Harinas del Paraguay S.A., Juan Pérez, +595 21 123 456, ventas@harinas.com.py). Save ("Guardá" — typo for "Guardar") and Cancel at bottom right.
- **Missing:** No product/category field ("¿Qué te vende?"), no RUC field (Paraguay RUC is essential for tax compliance), no website, no WhatsApp checkbox (very different from a phone in PY), no bank/cuenta corriente field, no schedule ("Lunes a Viernes 8-17"), no tags.
- **Top add:** **RUC field** with auto-format "XXXXXXX-X" and an inline "Validar en SET" button (mocked).

### Owner-finance (hat 2)
- **Now:** Same.
- **Missing:** No payment-terms field ("Contado / 7d / 15d / 30d"), no default discount, no "categoría" (insumos, packaging, servicios), no currency for purchases (Gs. vs USD), no "comprador responsable" (which staff member is the relationship owner).
- **Top add:** **Payment-terms + currency + categoría** triple. Critical for the upcoming cashflow forecast on the dashboard.

### Production-baker (hat 3)
- **Now:** Same.
- **Missing:** No "¿Qué ingredientes te vende?" multi-select. No "Día de entrega" (Monday / Wednesday / Friday). No order cutoff time. No delivery zone. No minimum order. No product catalog.
- **Top add:** **"Qué te vende + cuándo entrega" panel** — for a baker, the most-used metadata is delivery day and minimum order. Without these they call the supplier every time to ask.

### New user (hat 4)
- **Now:** Form is one column, labels above inputs (clean), placeholder examples are good (Paraguayan-flavored), required asterisk is clear.
- **Missing:** No field tooltips (e.g., "Why do we need this?"), no autosave-draft indicator, no "Import from existing pedido" button, no clear data-retention note.
- **Top add:** **Inline "guardando borrador…" indicator** so the user knows their input isn't lost if they navigate away.

### Auditor (hat 5)
- **Now:** No audit preview ("Will be logged as supplier.create by [your user] at [timestamp]"). No "Created by" field auto-population visible. No "¿Quién puede editar este proveedor?" RBAC preview.
- **Missing:** RBAC visibility — who can view/edit/delete this supplier after creation. No "log retention" hint.
- **Top add:** **Footer audit-hint**: "Esta acción quedará registrada en Auditoría."

### Complete design wishlist
- **Tabs / sections:** Información básica · Contacto · Comercial · Logística · Adjuntos · Notas internas
- **RUC field** with SET validation
- **Categoría** (Insumos · Packaging · Equipamiento · Servicios · Otros) — multi-select
- **Payment terms** dropdown (Contado, 7d, 15d, 30d, 45d, custom)
- **Moneda preferida** (Gs., USD, mixto)
- **Día de entrega** recurring weekly selector
- **Horario de atención** display
- **Mínimo de pedido** numeric
- **Zona de entrega** (multi-select: Asunción, San Lorenzo, Capiatá, …)
- **"Qué te vende"** — multi-select of productos/ingredientes
- **Adjuntos:** Contrato (PDF), RUC scan, CBU/cuenta comprobante, etc.
- **WhatsApp checkbox** separate from Teléfono (with link auto-detect "+595 9…" → wa.me/5959…)
- **Auto-tagging** from email domain
- **Inline dup-warning** as the user types the name: "⚠ Posible duplicado: Harinas del Paraguay S.A. (98% match). ¿Es el mismo proveedor?"
- **Notes section** with rich text + pin important notes
- **"Ver historial"** link once saved
- **Submit + create another** button
- **Save draft** with autosave
- **Cancel with confirm** if form is dirty

### Quality-of-life touches
- Typo on Save button: "Guardá" → "Guardar" (currently mixes imperative and voseo in a confusing way — both verbs are common, but inside the same form the inconsistency feels like a bug).
- Phone field should auto-format as the user types: `+595 21 123 456`
- Email field should validate format inline
- Address textarea could have a "📍 Pegar de Google Maps" affordance that auto-fills from a share link
- `Tab` order: Nombre → Contacto → Teléfono → Email → Dirección → Notas → Guardar (currently fine, but add visual focus ring)
- Required-field indicator: keep the asterisk but also add a tiny `* requerido` key in the form footer
- Cancel button should be a ghost-button (lighter) — currently competes visually with primary save
- After save: redirect to supplier-detail page, not back to list (so the user sees what they created)
- Sticky save-bar at the bottom on long forms
- Use `autocomplete="organization"` for browser autofill
- Mobile: stack phone + email in 1 col instead of 2 cols when viewport < 640px (currently they share a row but may overflow)

### Defects
- **P0:** Save button typo: "Guardá" — should be "Guardar". (Either standardize on voseo "Guardá" everywhere, or on neutral "Guardar" — pick one. Other buttons in the system use "Nuevo", "Cancelar", "Filtrar" which are neutral; the voseo here breaks the pattern.)
- **P1:** No RUC field — critical for Paraguay and absolutely required for B2B tax reporting.
- **P1:** Form is single-column and very long — a baker adding a supplier on a phone will scroll past 6 fields. Should collapse to 2-column on desktop ≥1024px.
- **P1:** No required-field for email or phone, even though those are the actual ways you "contact" them per the empty-state copy. The empty-state promised contact-ability, but the form makes both fields optional.
- **P2:** No back-button behavior preserved if user navigates away with dirty state — confirm-modal needed.
- **P2:** Cancel button styling competes with primary; should be a tertiary text-button.
- **P2:** Placeholder text uses voseo examples but the field labels are neutral — minor consistency issue.

---

## 4. `proveedores-alias.png` — Proveedores · Aliases / Supplier aliases

**Personas:** counter staff (low), owner-finance (medium), production-baker (medium), new user (low), auditor (low)

> ⚠️ **Same as `suppliers-dup.png`** — this screenshot is **identical** to the empty `suppliers.png`. Either the alias-management view is a future feature not yet rendered, or it lives on a sub-route that's not distinct in the current UI. Another P0 documentation/screenshot finding.

### Counter staff (hat 1)
- **Now:** Empty state identical to main suppliers index.
- **Missing:** A real aliases view: parent supplier + N aliases, alias-search, "merge into primary" action.
- **Top add:** **"Ver aliases" tab/segment** on the main suppliers index — toggles between list view and alias-network view.

### Owner-finance (hat 2)
- **Now:** Empty.
- **Missing:** The whole feature. Finance cares most — they get invoices from "Harinas del Paraguay" sometimes and "Harinas Paraguay S.A." other times and the system needs to roll them up.
- **Top add:** **Per-supplier "Aliases" sub-tab** in the supplier-detail page. Add/remove alias inline. Audit-logged.

### Production-baker (hat 3)
- **Now:** Empty.
- **Missing:** When typing in reorder page or in any selector, the system should resolve aliases to the canonical supplier. Currently no evidence this happens.
- **Top add:** **Smart resolver** in all supplier dropdowns — typing "harinas" surfaces both "Harinas del Paraguay" and "Harinas Paraguay S.A." but flags them as aliases.

### New user (hat 4)
- **Now:** Confusing — sees the suppliers empty state but the URL says "aliases".
- **Missing:** Page distinction.
- **Top add:** **Differentiated empty state** that introduces the concept: "Los aliases son nombres alternativos del mismo proveedor. Ej: 'Harinas Py' = 'Harinas del Paraguay S.A.'.".

### Auditor (hat 5)
- **Now:** Nothing.
- **Missing:** Audit of every alias add/remove/merge.
- **Top add:** **Dedicated audit filter** "supplier.alias.*" so auditor can trace all alias changes.

### Complete design wishlist
- Tab on supplier detail page: "Aliases (3)"
- Aliases shown as pills, click-to-edit, `x` to remove
- "Agregar alias" inline input
- "Alias más usado" badge (frequency-based)
- History of alias remaps with timestamps
- Cross-supplier alias detection ("these two suppliers share the same phone — maybe aliases?")
- Bulk-merge UI on the dedup page (which is also empty/missing)

### Quality-of-life touches
- Alias pills should autocomplete from existing aliases
- Hover on alias pill shows "origen del alias: WhatsApp mensaje 24/08"
- Drag-and-drop to reorder primary/alias

### Defects
- **P0:** Screenshot identical to suppliers.png — feature appears missing or doc mis-captured.
- **P1:** No discoverable UI for aliases; the URL pattern must exist but isn't reachable from main flow.

---

## 5. `reorder.png` — Reponer stock / Replenish

**Personas:** counter staff (medium), owner-finance (medium), production-baker (high), new user (high), auditor (low)

### Counter staff (hat 1)
- **Now:** Single table row for "Levadura seca". Columns: Ingrediente · Actual · Mínimo · Máximo · Sugerido · Urgencia · Costo est. · Tendencia (90d) · Días restantes · Proveedor · Reponer. Right side: editable "1.6" + unit ("kg") and orange "Reponer" CTA. Total estimado Gs. 28.800 footer. "Seleccionar todos" + "Generar pedido por WhatsApp" action bar. Below: "Administrar proveedores" link. Showing 1-1 of 1.
- **Missing:** No scan/lookup by camera (critical for warehouse — "show me the bag, I'll tell you which row"), no quick-receive action (when stock arrives, mark received), no "Last ordered" history, no supplier-filter dropdown (currently shows "sin proveedor" for the only row).
- **Top add:** **QR/barcode lookup at the top** — scan a bag, jump to its row.

### Owner-finance (hat 2)
- **Now:** Same. Gs. 28.800 total visible — useful.
- **Missing:** No budget cap ("¿Cuánto podés gastar este mes?"), no "monthly procurement trend" sparkline on the table, no export-to-CSV, no compare-to-last-month badge, no supplier-payment-terms column.
- **Top add:** **"Total vs presupuesto mensual" pill** in the header (with green/amber/red state) and a one-click export.

### Production-baker (hat 3)
- **Now:** **Excellent column set for a baker**: actual stock, mínimo, máximo, sugerido (1.6 kg computed automatically), urgency badge ("Bajo mínimo" in amber), cost estimate, 90-day trend (—), días restantes (—), proveedor. Reponer CTA in green-bordered input.
- **Missing:** The "—" cells for tendencia and días restantes are silent failures — they should say "sin datos" or "0 días" or grey out. The "sin proveedor" italic looks like a bug — it should be a red warning badge with "Asignar proveedor" link. No grouping by recipe ("todo lo que se usa en chipa" / "todo lo que se usa en pan").
- **Top add:** **Group-by-recipe accordion** + **"sin proveedor" as red badge** with one-click assignment.

### New user (hat 4)
- **Now:** Pretty clear. "Reponer stock" with breadcrumb. Subtitle "Ingredientes con stock por debajo del mínimo. Total estimado: Gs. 28.800."
- **Missing:** No "Cómo funciona" hint, no first-run tooltip walking through the columns, no glossary ("¿Qué es 'tendencia 90d'?").
- **Top add:** **Header "?" icon with onboarding overlay** explaining each column on hover.

### Auditor (hat 5)
- **Now:** Nothing.
- **Missing:** Audit trail for every "Reponer" click (which creates a `reorder.suggested` event). No diff vs last order.
- **Top add:** **"Historial" link** per ingredient with the last 5 orders and dates.

### Complete design wishlist
- **KPI strip:** Items bajo mínimo (1) · Total a reponer Gs. 28.800 · Proveedores únicos (0) · Última compra promedio
- **Group-by:** Categoría · Proveedor · Receta (requerida) · Urgencia
- **Filter chips:** Bajo mínimo · Sin stock · Sin proveedor · Caducan pronto
- **Sort indicators** on every column header
- **"Sugerido" explainer** — hover shows fórmula: `sugerido = max(mínimo, promedio_consumo_7d × lead_time) - actual`
- **Editable sugerido** with reason dropdown ("manual override", "promedio semanal", "para evento")
- **Bulk action bar:** Seleccionar todos → Generar pedido por WhatsApp · Generar pedido PDF · Exportar CSV · Asignar proveedor masivamente
- **Quick-receive modal:** When goods arrive, scan + tap "Recibí 1.6 kg" → updates stock + auto-creates inventory movement + posts to shopping list.
- **WhatsApp message preview** with line items grouped by supplier, in proper Spanish
- **Trend sparkline** (90d) inline chart
- **Days remaining** with color: green >7d, amber 3-7d, red <3d
- **Empty state** for "0 items below mínimo" celebration: "🎉 ¡Todo bajo control! Última revisión hace 3 horas"
- **Sticky total bar** at the bottom that floats while scrolling
- **"Sugerir nueva fecha de pedido"** based on consumption velocity
- **Mobile-friendly** row layout: collapsible detail
- **Search/filter input** by ingredient name

### Quality-of-life touches
- Number input ("1.6") should have stepper +/- and unit selector
- "Reponer" button should also offer "Reponer todo" or "Reponer ×2"
- The "kg" badge inside the input is a nice visual touch but should also be selectable (kg, g, L, mL, unidad)
- Color-code `urgencia`: verde (OK), amarillo (bajo mínimo), rojo (sin stock), violeta (caduca pronto)
- Subtle strikethrough on ingredients where `actual == 0` to draw the eye
- After clicking "Generar pedido por WhatsApp", show a preview modal with the formatted message before sending
- Persist last filter/sort state in localStorage
- Empty state when all rows are above mínimo should not show the table at all — show celebration card
- Tooltip on "Tendencia (90d)" — explain it's a 90-day rolling average
- Tab-key navigation through inputs is smooth; the Reponer button should be `Enter`-friendly
- Toast on success: "Pedido enviado por WhatsApp a Harinas del Paraguay" with "Ver" link

### Defects
- **P0:** "—" cells in "Tendencia (90d)" and "Días restantes" — silent failures. Should explicitly say "sin datos" or "0 días" or grey out with a "Generar histórico" button.
- **P0:** "sin proveedor" shown in *italic* gray — looks like a bug. This is actually a critical data issue: you cannot reorder if there's no supplier. Should be a red **badge** with an inline "Asignar" link.
- **P0:** The "Generar pedido por WhatsApp" button is enabled even when there's no supplier assigned — clicking it will produce an empty/broken message. Must be disabled with tooltip.
- **P1:** Only 1 row visible — no virtualized scrolling, no pagination. Will break at 50+ items.
- **P1:** No filter chips at all; user has to scroll.
- **P1:** The "Reponer" button duplicates work — the user types 1.6 AND clicks Reponer. The action should be a single "Add to cart" or "Queue for WhatsApp". The number should be pre-filled but submit-on-Enter, not split-button.
- **P2:** Column header text wraps awkwardly ("COSTO EST." on two lines, "TENDENCIA (90D)" on two lines) — need either wider columns or abbreviations tooltips.
- **P2:** "Administrar proveedores" link below the table feels orphaned — should be a header action.
- **P2:** "Mostrando 1-1 de 1" — pagination footer is fine, but with only 1 row this feels like over-engineering.

---

## 6. `shopping-list.png` — Lista de compras / Shopping list

**Personas:** counter staff (medium), owner-finance (medium), production-baker (high), new user (high), auditor (low)

### Counter staff (hat 1)
- **Now:** Header "🛒 Lista de Compras" + subtitle "Lo que necesito comprar para la operación". KPI row: Items abiertos 0 · Comprados 0 · Total estimado Gs. 0 · Ingredientes únicos 0. Tab group: "Solo abiertos (0)" (orange filled) + "Todos (incl. comprados)". Action buttons: "Crear plan" + "Sincronizar faltantes". Empty-state card with 📬 emoji: "Lista vacía. Ve a Plan Producción y creá un plan; los faltantes aparecerán acá automáticamente." Tip box at bottom: "💡 Tip: Marcar 'Comprado' no toca el inventario todavía. Cuando llegue el pedido, ajustás el stock desde la ficha del ingrediente."
- **Missing:** No add-manual-item shortcut ("anotar algo"), no photo-of-receipt upload, no share-with-staff link, no "mark as bought + add to inventory" combined action (currently requires two steps), no recent-supplier call shortcut.
- **Top add:** **"Anotar ahora" floating action button** for ad-hoc additions during the day (e.g., "we ran out of bags, add 100 to list"). The current flow forces you through Producción → Plan → wait for sync.

### Owner-finance (hat 2)
- **Now:** Same.
- **Missing:** No cost-per-supplier breakdown, no budget vs actual, no "compras recurrentes" view, no export to email/PDF for the controller.
- **Top add:** **"Costo por proveedor" mini-chart** in the header KPIs area.

### Production-baker (hat 3)
- **Now:** Pretty good. Tip explains the two-step workflow (Comprado ≠ inventory updated). Tab toggle is clear. Empty state is well-worded with a direct link to Plan Producción.
- **Missing:** No "agregar todos de una receta" shortcut (baking 100 chipas = 100 chipa ingredients), no estimate by-supplier, no ETA column, no "marcar recibido" combined action.
- **Top add:** **"Recibí este pedido" combined button** that marks items bought AND updates inventory in one tap. Today it's 4 taps minimum.

### New user (hat 4)
- **Now:** Excellent empty-state with helpful tip explaining the gotcha. Empty-state emoji (📬) is friendly.
- **Missing:** A first-run onboarding walkthrough. The link to "Plan Producción" works but assumes the user knows what that means.
- **Top add:** **Inline tooltip on "Sincronizar faltantes"** explaining what it does.

### Auditor (hat 5)
- **Now:** Nothing visible.
- **Missing:** No "view audit trail for this list" link.
- **Top add:** **Footer "Auditado por: …"** attribution.

### Complete design wishlist
- **KPI tiles (visual cards, not just labels):** Items abiertos (chip) · Gs. estimado (chip with breakdown icon) · Proveedores involucrados (chip) · Última sincronización (timestamp)
- **Group by supplier** accordion (when populated)
- **"Recibí" combined action** per row: marks bought + opens inventory-adjust modal pre-filled
- **Add manual item** floating button
- **"De una receta"** selector: "Agregar todo lo necesario para 100 chipas"
- **"Por proveedor" view** with totals
- **Progress bar** showing % comprado
- **Time-since-added** column (red >3d, amber >1d, gray today)
- **Search/filter** by ingredient, by supplier, by status
- **Bulk action:** Marcar comprado · Borrar · Imprimir · Compartir
- **Print/PDF view** for the supplier
- **WhatsApp share** with formatted message
- **Recurring items:** "Caja de bolsas" every Monday
- **Suggestion engine:** "Caja de bolsas — compraste 100 hace 7 días, ¿quedan?"
- **Sticky "Marcar todo recibido"** when ≥3 items selected
- **"Histórico"** tab with last 30 days of purchases

### Quality-of-life touches
- Tip box is great — keep it but add tooltip-explainer on "Sincronizar faltantes"
- Checkbox state with subtle animation when marking bought
- Date-picker for "recibido el" date (not just "now")
- Inline notes per item ("pedí marca X")
- Keyboard shortcut: `Space` to toggle Comprado, `Cmd+Enter` to mark all visible
- Toast on success with "Deshacer" for 5s
- Show last-purchased-price next to item name for sanity-check
- "Duplicate from last delivery" shortcut — copy previous list as starting point
- Smooth fade-in when items sync from Producción

### Defects
- **P0:** KPI numbers (0/0/0/0) all zero — fine for empty, but for a populated list this KPI row will visually overwhelm. Should be cards with iconography, not just text labels.
- **P1:** Tab "Todos (incl. comprados)" only useful when populated; for first-time user it's confusing ("what does this even mean?").
- **P1:** "Sincronizar faltantes" button has no explanation of what it does — could be a destructive-looking action if it overwrites local edits.
- **P1:** Tip box says "Marcar 'Comprado' no toca el inventario todavía" — this is the **#1 source of confusion** the user is warning about. The two-step workflow (mark bought → go to ingredient → update stock) is fragile. Should be a single action with a checkbox "También ajustar inventario".
- **P2:** Empty-state card has a 📬 emoji but no illustration or icon-set; feels under-designed.
- **P2:** "Crear plan" button is hidden behind a separate flow; consider showing it as a "+" floating action.

---

## 7. `wishlist.png` — Lista de deseos · equipamiento / Equipment wishlist

**Personas:** counter staff (none), owner-finance (high), production-baker (medium), new user (low), auditor (low)

### Counter staff (hat 1)
- **Now:** "📅 Lista de deseos — equipamiento". Subtitle "Lista priorizada para arrancar y escalar la panadería". KPI labels: Artículos totales 0 · Pendientes 0 · Comprados 0 · Inversión total Gs. 0 · Pendiente Gs. 0. Single tip line: "💡 Cargá o sincronizá artículos para planificar inversiones de equipamiento."
- **Missing:** N/A — counter staff don't use wishlists.
- **Top add:** N/A

### Owner-finance (hat 2)
- **Now:** Clean. The KPIs (inversión total, pendiente) are exactly what an owner needs for capex planning.
- **Missing:** No prioritization field (P0/P1/P2), no target purchase date, no ROI estimate ("if I buy this oven, I'll save Gs. X/month in labor"), no link to a budget scenario, no vendor comparison, no approval workflow ("needs owner sign-off >Gs. 500,000").
- **Top add:** **Priority + Target date + ROI estimate** triple per item, with a board view (Kanban-style: now/next/later/done).

### Production-baker (hat 3)
- **Now:** Pretty much just a tip line.
- **Missing:** No way to "request" equipment from the floor ("yo quiero un horno rotativo"). No "vote" or comment thread. No photo of the desired item.
- **Top add:** **"Yo quiero…" simple request form** accessible from anywhere in the app, with photo upload from phone.

### New user (hat 4)
- **Now:** Clean header and clear purpose. KPI strip sets expectations.
- **Missing:** No seeded examples ("Here's a typical wishlist for a panadería"). No template import. No integration with online suppliers for price lookup.
- **Top add:** **"Importar desde una lista de favoritos"** or "Browse catálogo de equipamiento" — pre-populated starter set.

### Auditor (hat 5)
- **Now:** Nothing.
- **Missing:** Approval audit (who approved this purchase?), source of funds, link to bank-account debit when bought.
- **Top add:** **"Ver aprobación"** deep-link to the audit log.

### Complete design wishlist
- **KPI cards with icons** (currently just labels + numbers — need visual weight)
- **Board view** (Now / Next / Later / Done) — Kanban-style
- **List view** with sortable columns
- **Timeline view** (target date on a horizontal axis)
- **"Critical path" highlight** for items blocking production
- **Per-item fields:** Nombre · Categoría (horno, amasadora, balanza, vitrina, etc.) · Precio estimado Gs. · Prioridad P0/P1/P2 · Target date · Owner (who requested) · ROI · Foto · Notas · Estado
- **Bulk import** from CSV
- **"Vote"** system for staff requests
- **Approval workflow** for items >Gs. X
- **Link to bank account** when item moves to "Comprado"
- **Comparison table** (modelo A vs B vs C)
- **Starter templates** by bakery size
- **Photo gallery** view

### Quality-of-life touches
- Drag-and-drop on the board view
- Color-code priority: P0 red, P1 amber, P2 gray
- "Próxima compra sugerida" badge based on accumulated pendiente
- "Total saved toward this wishlist" mini-chart
- Confetti when first wishlist item is added
- Toast when item moves to "Comprado" with link to register the asset in inventory
- Keyboard shortcut `N` to add new item from anywhere on the page

### Defects
- **P0:** KPI labels are floats in space — they have no border, no background, no icon. In a populated state with Gs. 50,000,000 pendiente, the visual weight is wrong. Need cards.
- **P0:** "Cargá o sincronizá artículos para planificar inversiones de equipamiento" is **the only** call to action and it's just a tip line, not a button. New users won't see this as actionable.
- **P1:** No "Agregar artículo" primary button visible at all in the empty state. Where does the user click?
- **P1:** No bulk-import or starter template — high-friction empty state.
- **P2:** The 📅 emoji in the header is decorative but inconsistent with other pages (🛒, 🏦, 💰). Pick a coherent set or none.

---

## 8. `pricing.png` — Precios por receta / Pricing by recipe

**Personas:** counter staff (low), owner-finance (high), production-baker (medium), new user (medium), auditor (medium)

### Counter staff (hat 1)
- **Now:** "💰 Precios por receta". Subtitle "Costos y precios por canal (mayorista, minorista, distribuidor, etc.)". KPI: Recetas con pricing 0 · Costo total (batch) 0 · Valor minorista 0. Sub-header "Channels & márgenes (MAESTRA):". Table headers: Receta · Cost total Gs. · Cost/unit Gs. · Wholesale Gs. (+40%) · Private label Gs. (+25%) · Distribuidor Gs. (+22%) · Retail Gs. (+50%) · Comisión Gs. (+5%). Tip: "Fuente: HEREBUS_COSTOS sheet (7 recetas × 5 canales = 35 precios). Labor: Gs.25,000/h, Packaging: Gs.1,500/unit (configurable)."
- **Missing:** No "Suggested retail" badge (just shows margin %, no computation). No price-history chart. No competitor comparison link. No "what-if" simulator ("if flour +10%, retail becomes X"). No batch-size selector.
- **Top add:** **"Simular suba de insumos"** widget — pick an ingredient and a %, see all channels recompute live.

### Owner-finance (hat 2)
- **Now:** Excellent column structure. The 5 channels × 5 margins give everything a finance person needs.
- **Missing:** No gross margin $ shown alongside %. No contribution margin. No "blended" column (weighted average across channels). No "actual sold price" vs "list price" variance. No "below cost" warning. No "channel mix" pie chart.
- **Top add:** **"Margen bruto Gs." column** next to each margin %. And a "Below cost" red flag if cost exceeds suggested retail.

### Production-baker (hat 3)
- **Now:** Margin percentages are useful ("I know I should sell 50% above cost at retail").
- **Missing:** No batch-yield adjustment ("I actually got 92 units instead of 100, real cost is higher"). No "tiempo de elaboración" column. No "difficulty premium".
- **Top add:** **"Costo real vs teórico" toggle** showing variance.

### New user (hat 4)
- **Now:** Clear title, good KPI row, channel definitions visible. The "MAESTRA" callout is helpful for understanding this is the master template.
- **Missing:** The "Channels & márgenes" is **all uppercase MAESTRA** — feels like a label that escaped from the spreadsheet. The 5-channel × 5-margin matrix needs explanation: "Why these margins?"
- **Top add:** **Inline tooltip explaining margin selection** ("40% wholesale = industry-standard margin for distributors buying in bulk").

### Auditor (hat 5)
- **Now:** No audit.
- **Missing:** Who set the margin? When was it last updated? Price-change history. Compliance with minimum-margin policy.
- **Top add:** **"Historial de cambios"** per recipe + per channel.

### Complete design wishlist
- **5 channels × N recipes matrix** with editable cells
- **Margin presets** ("Conservative", "Standard", "Aggressive")
- **Per-channel breakdown view** (one recipe, all channels vs all recipes, one channel)
- **"Sell below cost" warning** with red badge
- **"Margin floor" enforcement** (per channel, configurable)
- **What-if simulator:** Ingredient cost +X% → recalculates all channels
- **Price-change history** per recipe × channel
- **Approval workflow** for >10% price changes
- **"Sync to menu/publicar"** action that pushes prices to other modules
- **CSV/Excel export** with current and historical prices
- **Compare to last month's prices** overlay
- **Notes per recipe × channel** ("Q4 promo", "VIP client override")
- **Bulk-edit margins** ("set wholesale to 35% for all recipes")
- **Volume-tier pricing** (1-10, 11-50, 51+ units)
- **Currency selector** per channel (Gs., USD, mixto)
- **Display in selected system** as a kanban (channels as columns, recipes as rows)
- **Sticky header** showing recipe names while scrolling horizontally
- **Configurable labor cost** and packaging cost (mentioned in tip but no UI to change)
- **Visual: cost pie** showing ingredient breakdown per recipe

### Quality-of-life touches
- Sticky first column (Receta) when scrolling horizontally
- Cells should show % AND computed Gs.
- Quick-toggle "show only channels with margin below floor"
- Color-code cells: green (above floor), amber (within 5%), red (below)
- Hover any Gs. cell → tooltip showing the formula
- "Edit labor cost" inline link in the tip
- Drag-column-reorder to put the most-used channel first
- Persist last sort/filter state
- "Lock" master margin per channel so accidental edits don't propagate

### Defects
- **P0:** Margins are hard-coded as part of the column header (+40%, +25%, etc.) — **there is no UI to edit them**. To change wholesale margin from 40% to 35% the owner has to edit the database or call support. Critical.
- **P0:** "MAESTRA" label in all caps next to "Channels & márgenes" reads as a leftover spreadsheet artifact, not a UI label. Should be a sub-heading or a card.
- **P1:** Empty state for the table doesn't tell the user "to populate this, create recetas in /recetas first" — there's an implicit dependency that needs surfacing.
- **P1:** Labor Gs.25,000/h and Packaging Gs.1,500/unit are referenced in the tip but there's no link to where they're configured.
- **P2:** The 7 columns × N rows will overflow horizontally on mobile — needs responsive design (cards on mobile).
- **P2:** "Comisión Gs." with +5% is unusual to be a *channel* — typically comisión is per-transaction, not a sales channel. Naming confusion.

---

## 9. `vs-mercado.png` — Comparativa vs mercado / Price vs market

**Personas:** counter staff (low), owner-finance (high), production-baker (low), new user (medium), auditor (low)

### Counter staff (hat 1)
- **Now:** "📊 Comparativa vs mercado". Subtitle "Posicionamiento vs competencia (Asunción/San Lorenzo)". Table headers: Producto · Nuestro wholesale Gs. · Nuestro retail Gs. · Mercado avg Gs. · Posición · Editar. Only row: "Chipa grande" with — · 5.000 · — · — · ✏️ Editar. Tip: "Source: HEREBUS_Benchmarks_Market (17 productos a comparar vs Competidor A/B/Avg). Editá cada fila con el botón correspondiente."
- **Missing:** No visualization (scatter plot would tell the story instantly). No "below market" badge. No filter by category. No "add competitor" flow.
- **Top add:** **Scatter plot** with each product as a dot (X = our price, Y = market avg), color-coded by position. One chart tells more than 100 rows.

### Owner-finance (hat 2)
- **Now:** Sparse. Only 1 row visible, mostly "—".
- **Missing:** No trend over time, no aggregate metrics ("we're 12% above market on average"). No "below-cost" warning. No link to the Pricing page to adjust. No competitor comparison (Competidor A vs B vs Avg).
- **Top add:** **Aggregate KPIs at the top**: "X% above/below market avg" · "Y productos más caros" · "Z oportunidades de ajuste".

### Production-baker (hat 3)
- **Now:** Pretty much irrelevant for the baker.
- **Missing:** N/A
- **Top add:** N/A

### New user (hat 4)
- **Now:** Header is clear, but the "—" cells are confusing.
- **Missing:** No onboarding for "what is market avg?" No link to set up benchmarks. No "competitor scraper" placeholder.
- **Top add:** **Empty-state illustration** with a tiny scatter-plot showing "this is where you'd be positioned".

### Auditor (hat 5)
- **Now:** Nothing.
- **Missing:** When was the market avg last updated? Source citation per cell.
- **Top add:** **"Source" column** with citation link (MercadoPy listing URL, Facebook post, etc.)

### Complete design wishlist
- **Scatter plot visualization** (must-have)
- **Per-product competitor table** (A, B, Avg all visible at once)
- **Position indicator** with traffic-light: green (cheaper), amber (parity), red (more expensive)
- **Bulk-update from market** ("set our retail to market avg")
- **Trend over time** (price evolution vs market)
- **Suggested pricing** based on percentile
- **Per-category view** (panificados vs pastelería)
- **"Source" column** with citation
- **Auto-refresh** market data with timestamp
- **Last-updated badge** per row
- **Confidence interval** (Avg ± 10%)
- **Notes per product** ("premium positioning", "loss-leader")
- **CSV import** for market data

### Quality-of-life touches
- Hover on Posición cell → tooltip with % diff and absolute Gs.
- "Edit" should be inline (not a separate page)
- Sticky first column
- Color-coded rows (red = above market by >15%, amber = within 15%, green = below)
- Date picker for "as of [date]"

### Defects
- **P0:** "—" in three of five columns on the only visible row — looks like a bug. Should be "0" or "sin datos" or "completar" with inline edit.
- **P0:** "Editar" action goes to a full new page (per the edit screenshot) when inline-edit would be 100× faster for a 17-row table.
- **P1:** 17 productos × 5 columns is going to be cramped — no pagination, no virtualization visible.
- **P1:** No aggregate metric ("we are X% above/below market on average").
- **P2:** "Mercado avg Gs." doesn't show distribution (min, max, median) — only the avg.

---

## 10. `vs-mercado-editar.png` — Editar benchmark / Edit market comparison

**Personas:** counter staff (none), owner-finance (high), production-baker (low), new user (medium), auditor (medium)

### Counter staff (hat 1)
- **Now:** N/A
- **Missing:** N/A
- **Top add:** N/A

### Owner-finance (hat 2)
- **Now:** Two-column form. Left card "💰 Nuestro precio": Wholesale Gs. (empty) · Retail Gs. (5000). Right card "🏪 Mercado": Competidor A (mín) Gs. (4500) · Competidor B (prom) Gs. (5500) · Mercado promedio Gs. (empty). Below: Notas / fuente (textarea: "MercadoPy, redes, llamadas…"). Save/Cancel buttons.
- **Missing:** No last-update timestamp, no source URL field (only free-text notes), no currency selector, no tax-included toggle (PY IVA 10% is split-included). No "competitor C" field. No scrape-from-URL helper.
- **Top add:** **"Source URL" field** per competitor + a "Pegar link de MercadoPy" button that auto-fills price.

### Production-baker (hat 3)
- **Now:** N/A
- **Missing:** N/A
- **Top add:** N/A

### New user (hat 4)
- **Now:** Form is reasonably clean. Tip below explains how "Posición" is calculated ("se calcula automáticamente al comparar tu retail vs el promedio del mercado. -10% = 'más barato que la competencia'").
- **Missing:** The four field labels (Competidor A (mín), Competidor B (prom)) are unclear: why A and B? Why is one mín and one prom? What's the methodology?
- **Top add:** **Tooltip explaining the dual-competitor methodology**: "A = lowest competitor (worst-case), B = average competitor (typical)".

### Auditor (hat 5)
- **Now:** Nothing.
- **Missing:** No "last edited by / when" attribution, no change-log, no "this benchmark used in pricing decision #X" trail.
- **Top add:** **Footer "Edit history"** with timestamp + actor.

### Complete design wishlist
- **Source URL field** per competitor (with MercadoPy/Instagram deep-link paste)
- **Date captured** per price (not just "today")
- **Multiple competitors** (not just A and B) — expandable list
- **Confidence indicator** (how reliable is this price? low/med/high)
- **"Pegar link" paste-to-extract-price** shortcut
- **Auto-recompute "Mercado promedio"** from competitor A/B inputs
- **Currency toggle** (Gs., USD)
- **Tax-included toggle** for IVAware pricing
- **Price validity window** (valid until: …)
- **Bulk update** from a price list (paste 17 rows at once)
- **Sticky save bar**

### Quality-of-life touches
- Tab order: Wholesale → Retail → A → B → Avg → Notas → Guardar
- "Mercado promedio Gs." should auto-compute when A and B are filled
- Cancel should warn if there's a delta ("Tienes cambios sin guardar")
- After save, return to the comparison table with the row highlighted
- Numeric inputs should accept Gs. with thousands separators
- "Help" icon next to "Mercado promedio" explaining when to override manually

### Defects
- **P0:** No timestamp / source / capture-date — finance cannot rely on this benchmark for actual decisions.
- **P1:** "Mercado promedio Gs." is empty even though Competidor A (4500) and B (5500) are filled — should auto-compute (5000) and let user override.
- **P1:** Wholesale Gs. is empty on this row even though the comparison page showed Retail = 5000. Either auto-pull from Pricing or show "—" with link to set in Pricing.
- **P2:** Two-card layout puts "Mercado" on the right which is fine, but the form is otherwise wide and may feel sparse on desktop >1280px.
- **P2:** No breadcrumb showing this is `/vs-mercado/[producto]/editar` — easy to lose context.

---

## 11. `bank.png` — Movimientos bancarios / Bank movements

**Personas:** counter staff (low), owner-finance (high), production-baker (none), new user (medium), auditor (high)

### Counter staff (hat 1)
- **Now:** "🏦 Movimientos bancarios". Subtitle "Dutch EUR (JGHM VAN DER POL) + PY Guaraní (SASKIA WEISS VANDER)". KPI: EUR income 0.00 · EUR spent 0.00 · EUR net 0.00 · PYG balance 0. Collapsible "▶ + Agregar movimiento manualmente (PY savings, etc.)". Table headers: Fecha · Cuenta · Importe · Categoría · Counterparty · Descripción. Tip: "💡 Source: TXT260711013722.TAB (Dutch EUR bank, Sep'25→Jun'26, 307 txns). Categorización manual desde la propia transacción."
- **Missing:** No actual rows visible (empty). No pie-chart of spend by category. No reconciliation status. No "match to venta" indicator.
- **Top add:** **"Match to venta" badge** per transaction when an invoice/SAT number appears in the description.

### Owner-finance (hat 2)
- **Now:** Excellent layout for a finance person. Two currencies shown. KPI strip is meaningful. Source file is cited.
- **Missing:** No reconciliation workflow (bank balance vs accounting balance), no FX-rate display (EUR → PYG conversion rate is invisible), no monthly cashflow chart, no budget vs actual, no alerts (negative balance, large outflow), no split-transaction.
- **Top add:** **FX-rate badge** showing "1 EUR = Gs. 8,500 (fuente: BCP, 27/09)" and a unified-total in Gs.

### Production-baker (hat 3)
- **Now:** N/A
- **Missing:** N/A
- **Top add:** N/A

### New user (hat 4)
- **Now:** Two-account subtitle is informative. Tip explains the data source.
- **Missing:** The "Dutch EUR" + "PY Guaraní" mix is opaque without context — what is JGHM VAN DER POL? Why two accounts? Need an "About these accounts" expandable.
- **Top add:** **"About these accounts" expandable** explaining the legal-entity structure.

### Auditor (hat 5)
- **Now:** Nothing.
- **Missing:** No "last reconciled" badge, no approval workflow for transactions, no immutable hash of the source TXT file, no access log.
- **Top add:** **"Reconciliation status" panel** — last reconciled date, by whom, outstanding items count.

### Complete design wishlist
- **Multi-account selector** (today shows 2 in subtitle; needs to be a dropdown)
- **FX-rate widget** with configurable source (BCP, manual)
- **Cashflow chart** (inflow/outflow over time)
- **Reconciliation workflow** (bank balance vs expected balance)
- **"Match to venta" automation** (link txns to sales by SAT ref)
- **Category taxonomy** (currently ad-hoc; needs a configurable list)
- **Counterparty learning** ("this account = Harinas del Paraguay, remember for next time")
- **CSV import** for other bank formats
- **Bulk categorization** ("select all from HSBC, mark as 'inversión'")
- **Search/filter** by date range, amount range, text
- **"Pending review" queue** for new txns
- **Approval workflow** for txns > Gs. X
- **Export to accounting software** (SiRe, Contabilium, etc.)
- **Notes + attachments** per transaction (PDF invoice)
- **Recurring detection** ("this Gs. 250,000 from HARPALL SA comes in every 1st")

### Quality-of-life touches
- Color-code inflow (green) vs outflow (red)
- Right-align all amount columns
- Negative amounts in red
- Currency symbols clear (€ / Gs.)
- Sort indicators on every column
- Quick-filter chips (Hoy, Esta semana, Este mes, Trimestre, Año)
- Sparkline of running balance

### Defects
- **P0:** No FX-rate displayed — owner looking at the numbers can't reconcile EUR vs PYG without opening Excel.
- **P0:** "Categorización manual desde la propia transacción" implies there's no auto-categorization — should have a "Learn from history" feature ("txn from HARINAS → 'Insumos'").
- **P1:** Empty transaction list with no obvious "Importar archivo" button — how does the user actually populate this?
- **P1:** KPIs all show €0.00 / 0 — these should be hidden or replaced with "Import your first file" CTA in empty state.
- **P1:** "Dutch EUR (JGHM VAN DER POL)" — putting a person's name in an account label is unusual; bank accounts usually have IBAN/bank-name. Needs sanitization for production.
- **P2:** The "+ Agregar movimiento manualmente" is collapsed by default; should be visible above the table.
- **P2:** No account switcher — both accounts shown in subtitle but no way to filter to one.

---

## 12. `riesgos.png` — Registro de riesgos / Risk register

**Personas:** counter staff (none), owner-finance (high), production-baker (medium), new user (low), auditor (high)

### Counter staff (hat 1)
- **Now:** N/A
- **Missing:** N/A
- **Top add:** N/A

### Owner-finance (hat 2)
- **Now:** "⚠️ Registro de riesgos". Subtitle "Riesgos operacionales, externos, comerciales, legales y personales". KPI: Activos 0 · Mitigados 0 · Cerrados 0 · Severidad total Gs. 0.
- **Missing:** **Everything**. The page is a hero header + 4 zeros + a void. No table, no filter, no "Agregar riesgo" button visible, no categories, no severity scoring UI, no mitigation tracking, no owner field. This is the weakest page in the system.
- **Top add:** **Pre-populated seed risks** ("here are 8 typical bakery risks — click to add") so the empty state is productive.

### Production-baker (hat 3)
- **Now:** A baker cares about operational risks (equipment failure, supplier stockout).
- **Missing:** No category filtering (operational vs personal vs legal). No link to mitigation actions. No "this risk blocks production X" indicator.
- **Top add:** **"Operational" tab as default** + "Reported by floor" inbox.

### New user (hat 4)
- **Now:** Concept is introduced but no onboarding for the framework.
- **Missing:** No "What is a risk register?" intro, no template, no example.
- **Top add:** **3-step onboarding overlay**: "1. Identify risks · 2. Score severity × likelihood · 3. Mitigate".

### Auditor (hat 5)
- **Now:** A risk register is itself an audit/compliance artifact — and the page is empty.
- **Missing:** Heat-map visualization, risk-trend over time, mitigation-effectiveness score, residual-risk calculation.
- **Top add:** **5×5 heat-map matrix** (severity × likelihood) — industry-standard visualization.

### Complete design wishlist
- **5×5 heat-map** (severity × likelihood, color-coded)
- **Risk list** sortable by residual risk
- **Per-risk fields:** Título · Descripción · Categoría (operacional/externo/comercial/legal/personal) · Probabilidad (1-5) · Impacto (1-5) · Riesgo inherente (auto: P×I) · Mitigación · Responsable · Fecha revisión · Estado (activo/mitigado/cerrado) · Riesgo residual (auto)
- **"Agregar riesgo"** primary button
- **Seed template** ("Common bakery risks") with 8 pre-built risks
- **Filter chips:** Categoría · Estado · Responsable
- **Bulk action:** Reasignar · Cerrar · Exportar PDF
- **Heat-map click** filters list to that cell
- **Risk-trend sparkline** (severity over time)
- **"Reported by floor"** inbox
- **"Próxima revisión"** scheduled reminders
- **Approval workflow** for risk acceptance
- **Heat-map export** as PNG for board presentations
- **Linked controls** (which mitigations are in place?)
- **Cost-of-mitigation** vs **cost-of-impact** decision matrix

### Quality-of-life touches
- Drag-drop a risk across the heat-map to update P×I
- Color: red (high), amber (med), green (low)
- "Riesgo crítico" badge for any risk with score ≥15
- Show owner avatar/initials
- Inline "Mitigado" celebration with confetti
- "Due for review" red badge if past the next-review-date

### Defects
- **P0:** **No "Agregar riesgo" button visible**. The page is reachable from the sidebar but provides zero entry-point. New users will stare at 4 zeros and leave.
- **P0:** Empty state has no CTA, no illustration, no seed template. This is the **worst-designed empty state in the system**.
- **P0:** The "Severidad total Gs." KPI is meaningless without context — severity is usually a score, not Gs. Either rename to "Severidad total (Σ P×I)" or add a tooltip explaining.
- **P1:** The 4 categories mentioned in the subtitle (operacionales, externos, comerciales, legales y personales) are not exposed as filter chips.
- **P1:** No mitigation workflow visible.
- **P2:** ⚠️ emoji in the header is decorative; consistent with other pages.

---

## 13. `auditoria.png` — Auditoría / Audit log

**Personas:** counter staff (low), owner-finance (low), production-baker (none), new user (low), auditor (high)

### Counter staff (hat 1)
- **Now:** "📋 Auditoría". Filter card: Acción (placeholder "login.success, sale.create, …") · Desde (date) · Hasta (date) · IP (placeholder "192.168.1.1") · Usuario (placeholder "saskia") · Tipo de registro (placeholder "product, sale, customer …") · ID del registro (placeholder "42"). Quick-access: today · yesterday · last_7d · last_30d. Buttons: Filtrar (orange) · Limpiar. Below: "Retención de datos" card explaining "Las entradas de auditoría se eliminan automáticamente después de 1 año. Podés eliminar las entradas más antiguas manualmente." Red button "Eliminar entradas de más de 1 año". Empty state: "📋 No hay entradas de auditoría. Cuando haya eventos registrados van a aparecer acá." with a small "Ir al inicio" link.
- **Missing:** No export, no diff view, no "view before/after" for changes. No "I'm investigating X" session.
- **Top add:** **"Exportar a PDF/CSV"** with date-range.

### Owner-finance (hat 1)
- **Now:** Same.
- **Missing:** Owner doesn't use this page; this is for auditor/security.
- **Top add:** N/A

### Production-baker (hat 3)
- **Now:** N/A
- **Missing:** N/A
- **Top add:** N/A

### New user (hat 4)
- **Now:** Filter card is well-structured. Placeholders hint at expected formats ("login.success, sale.create, …"). Quick-access chips are useful.
- **Missing:** The filter is exhaustive but overwhelming for a first-time user. No "Most common filters" preset row, no example queries.
- **Top add:** **"Top 5 consultas" preset chips** at the top: "Logins de hoy", "Cambios de precio", "Eliminaciones", etc.

### Auditor (hat 5)
- **Now:** Filter by Acción, Desde, Hasta, IP, Usuario, Tipo de registro, ID del registro. Quick-access time chips. Manual cleanup button.
- **Missing:** **No results table visible**. Filter UI is excellent but the actual log table is missing from the screenshot (probably below the fold or also empty). No "before/after diff", no "session grouping" (group events by session_id), no "anomaly detection", no "export with signatures".
- **Top add:** **Group-by-session view** + **before/after diff per row** (e.g., "Precio changed from Gs. 5,000 → Gs. 5,500 by juan at 14:23").

### Complete design wishlist
- **Results table:** Timestamp · Usuario · IP · Acción · Tipo · ID · Diff (collapsible) · Acciones
- **Diff view** per row (before/after side-by-side)
- **Group-by:** Session · User · Action · Date
- **Quick-filters:** Top 10 queries as chips
- **Saved queries** ("My weekly login audit")
- **Real-time stream toggle** ("Tail -f" mode)
- **Anomaly detection** (highlight unusual patterns)
- **Export with signatures** (PDF + SHA-256 for compliance)
- **Compliance reports** (SOX-style trail with hash chain)
- **"Open in nueva ventana"** per row (drill-down to entity)
- **Color-code actions:** Destructive (red), Read (gray), Create (green), Update (blue)
- **Filter chips** for quick categorical filters

### Quality-of-life touches
- "Last 7d" should pre-fill Desde/Hasta and click Filtrar automatically
- Empty-state illustration (audit document with magnifying glass)
- Filter card is collapsible to give more room for results
- "Limpiar" should also clear the placeholders visually (it currently doesn't)
- "Eliminar entradas de más de 1 año" is a destructive action — needs confirm modal with count of rows to delete
- Show a small "X eventos encontrados" pill near the filter button

### Defects
- **P0:** **Red destructive button** "Eliminar entradas de más de 1 año" with no count preview — an auditor or owner could nuke compliance data accidentally. Needs confirm modal: "Vas a eliminar 1,247 entradas de auditoría de hace más de 1 año. Esta acción es irreversible. [Confirmar] [Cancelar]".
- **P0:** No visible results table — the screenshot ends at the empty-state. The actual log table is missing from this capture (might be hidden in collapsed section).
- **P1:** Quick-access chips ("today", "yesterday", "last_7d", "last_30d") are text, not buttons — they should be clickable chips that auto-fill Desde/Hasta and click Filtrar.
- **P1:** Filter inputs are placeholders only — once you type, the placeholder disappears. Should show hints persistently below the input.
- **P2:** "Tipo de registro" placeholder ("product, sale, customer …") is comma-separated text — should be a multi-select dropdown.
- **P2:** The "Ir al inicio" link in the empty state is a nice touch but competes with the global nav.

---

## 14. `reportes.png` — Reportes / Reports index

**Personas:** counter staff (medium — uses Resumen diario), owner-finance (high — most reports), production-baker (medium — Demanda prevista), new user (high — discovers all reports here), auditor (medium)

### Counter staff (hat 1)
- **Now:** "📈 Reportes". Subtitle "Reportes financieros y operativos. Cada reporte tiene un botón de exportación PDF y filtros por fecha." Grid of 14 report cards (3-column on this width): Libro IVA · Costo teórico vs real · Demanda prevista · Frescura de insumos · Libro de Ventas · Resumen diario · Comparación de períodos · Top productos · Retención de clientes · Valor promedio del pedido · Ventas por hora · Ventas por método de pago · Rotación y stock muerto · Afinidades · Deriva de márgenes · Precios. Each card has a small bar-chart icon, title, one-line description, and tip with formula.
- **Missing:** No "Run report" button on each card — the card is just informational. No filter-by-date on the card. No last-run info. No favorite/star.
- **Top add:** **"Abrir" CTA per card** with date-range picker directly.

### Owner-finance (hat 2)
- **Now:** Comprehensive list. 14 reports cover finance + operations.
- **Missing:** No categorization (financial vs operational). No "Favorites" row. No scheduled-reports (weekly email). No report-template customization.
- **Top add:** **"Programar envío semanal"** per card with email + day-of-week.

### Production-baker (hat 3)
- **Now:** Several relevant reports: Demanda prevista, Frescura de insumos, Top productos, Ventas por hora, Rotación y stock muerto, Afinidades.
- **Missing:** No "Mi turno" view (last 8 hours summary). No "Producción del día" report.
- **Top add:** **"Mi turno — Resumen"** report card for floor staff.

### New user (hat 4)
- **Now:** Cards have title + 1-line description + formula hint. Good intro.
- **Missing:** No "Which report do I need?" decision tree. No "Most popular" badges. No preview screenshot of each report.
- **Top add:** **"No sé cuál elegir" prompt** at the top with guided Q&A: "¿Querés ver ventas, gastos, o stock?"

### Auditor (hat 5)
- **Now:** Libro IVA + Libro de Ventas are the most-relevant for compliance.
- **Missing:** No "Verified by" badge. No "Last reconciled" date. No immutable-export mode.
- **Top add:** **"Modo fiscal" toggle** that locks the report and produces a signed PDF.

### Complete design wishlist
- **Categorization:** Ventas · Costos · Inventario · Clientes · Compliance · Operacional
- **Tabs or sidebar** within Reportes for categories
- **Search box** ("IVA", "stock", "cliente")
- **Favorites / Starred** with personal top-5
- **"Run" CTA per card** with date-range inline picker
- **Last-run timestamp** per card ("Corriste este reporte hace 2 días")
- **Schedule recurring** ("Cada lunes a las 8:00")
- **Email/PDF delivery** to configured recipients
- **Export formats:** PDF · CSV · Excel · Google Sheets
- **Embedded preview** (click card → see 1-page preview before opening full)
- **"Add custom report"** for power users
- **AI-suggested reports** ("Based on your sales dip last week, you might want X")
- **Compare two reports** side-by-side
- **Report bookmark** with deep link
- **Saved parameters** ("Q3 with my standard filters")
- **Print-friendly** card layout

### Quality-of-life touches
- Each card should have a subtle icon-color matching category
- Hover on card → "Ver" + "Programar" + "Favorito" actions
- Sticky search box
- "Last viewed" ordering by default
- Tag chips on cards (e.g., "📊 Gráfico", "📋 Tabla", "💸 Dinero")
- Filter chips: "Más usados" · "Recientes" · "Con IA"
- Click card → modal preview, not full navigation
- Drag-to-reorder favorites
- Empty-search state: "No hay reportes para 'XYZ'. [Sugerir uno]"

### Defects
- **P0:** **No "Run" CTA on each card**. The cards are informational only — clicking a card presumably opens the report, but there's no visible affordance (no "Abrir" button, no "Ver" link, no chevron). New users will not know the card is interactive.
- **P0:** No date-range filter on the cards — every report presumably has date filters, but they're hidden behind the click.
- **P1:** "Cada reporte tiene un botón de exportación PDF y filtros por fecha" — promised in the subtitle but not surfaced on the index.
- **P1:** No categorization. With 14 reports in a flat grid, new users will scan-and-leave.
- **P1:** No search. "Demanda prevista" and "Demanda de hoy" can both be valid queries.
- **P1:** Cards appear to be 3-column but the last card (Precios) is alone in a row of 5 columns (visible in the bottom — actually wait, it's 4 columns wide with Precios in the last cell of a partial row). Layout inconsistency.
- **P2:** Each card has an icon (bar chart) — all the same icon. Should vary by report type.
- **P2:** Card borderless with only icon + text — feels undifferentiated; would benefit from category-color stripe.
- **P2:** The header "Reportes" lacks the visual weight it deserves — it's the system-wide "all reports" hub.

---

## Cross-cutting findings

### 1. Global empty-state inconsistency
Pages fall into 3 buckets:
- **Good empty states:** Proveedores, Lista de compras (with tip), Auditoría (with sub-card explaining retention)
- **Mediocre:** Wishlist, Riesgos, Bank (no CTA)
- **Broken / missing:** Proveedores duplicados, Proveedores aliases (both byte-identical to suppliers.png empty state)

**Recommendation:** Build a `<EmptyState>` component with slots for `icon`, `title`, `description`, `primaryCTA`, `secondaryCTA`, `tip`. Reuse across the system.

### 2. KPI rows lack visual weight
Almost every page has a KPI row of "Label / Value" pairs as plain text. For a populated state with Gs. 50M values, this will look weak. Standardize as **KPI cards** with iconography, semantic color, and sparkline.

### 3. "Sin proveedor" / "—" as silent failures
Multiple pages show "—" or "sin proveedor" without explaining what the user should do. Each is a **P0 design defect** — silent failures are worse than loud errors.

### 4. "MAESTRA" and other spreadsheet artifacts
The "(MAESTRA)" label next to "Channels & márgenes" is the most obvious leak from a Google Sheets mental model. Audit the system for similar leftover spreadsheet terminology.

### 5. Documentation/screenshot drift
`suppliers-dup.png` and `proveedores-alias.png` are byte-identical to `suppliers.png`. Either:
- The features are not yet built and shouldn't be exposed in docs, OR
- The features exist on a sub-route that's not yet distinct, OR
- The screenshot author captured the wrong page
**Action:** Verify before claiming feature parity in user-guide.

### 6. Wholesale-margins hard-coded
The pricing page shows +40% / +25% / +22% / +50% / +5% as static column headers with **no UI to edit them**. This is a critical gap.

### 7. Keyboard shortcuts
`⌘K` is visible in the header. `⌘N` should also be visible (especially on Nuevo proveedor). Document the full shortcut map.

### 8. Audit log = empty table in this screenshot
The filter UI is rich but the results table is missing from the capture. Verify the table renders correctly below the fold.

### 9. Riesgos = worst empty state in the system
No "Agregar riesgo" button. No seed template. Just 4 zeros. Highest priority fix.

### 10. "Editar" should be inline
Several "Editar" CTAs (vs-mercado, supplier-nuevo) navigate to a full page. For single-row edits, inline editing is 10× faster and reduces context loss.

---

*End of audit batch 3.*