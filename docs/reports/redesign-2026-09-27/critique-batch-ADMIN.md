# Saskia RMS — Visual Critique Batch: Admin
**Auditor:** UX/UI Principal + QA Architect
**Scope:** 8 pages — suppliers family (4), users, delivery-zones, riesgos, wishlist
**Method:** Template + router analysis — grounded in live template inspection
**Date:** 2026-09-27

---

## `/suppliers` (suppliers.html)

### 5-Hat Analysis
**Counter staff:** Uses the "Ordenar" (WhatsApp) button to message a supplier directly — this is the primary action. Table lists all suppliers with contact info and which ingredients they supply.

**Owner-finance:** Supplier list shows RUC (now with our fix), contact name, phone, email. Shows top-3 ingredient names each supplier carries, with a count badge and "…" truncation for suppliers with many ingredients. The "ninguno" empty state for suppliers with no ingredients is shown in italic muted — clean.

**Production-baker:** Shows ingredient categories per supplier — useful for knowing who to contact for specific ingredients.

**New user:** Empty state has a CTA "Agregar el primero" pointing to `/suppliers/nuevo`. Clear. Search bar is missing — on a long list, finding a specific supplier requires scrolling.

**Auditor:** No audit log integration. No indication of last order date per supplier.

### Defects (P0/P1/P2)
- [P1] No search/filter bar — finding a specific supplier on a long list requires scrolling
- [P1] "Ordenar" button links to `/suppliers/{id}/ordenes` — but there's no `ordenes` endpoint; this 404s
- [P1] RUC column added but no sorting on it — users can't sort by RUC to find duplicates
- [P2] Ingredients column truncates at 3 items — useful context, but no hover/tooltip to see the full list
- [P2] No "Activo/Inactivo" filter — can't distinguish active from dormant suppliers
- [P2] Delete button only shown when `not s.ingredients` — risks orphaning suppliers that should be deactivated instead of deleted

### Complete Design Wishlist
1. Add search bar (filter by name/contact/ruc)
2. Fix "Ordenar" link to a real endpoint or remove it
3. Add RUC deduplication check (warn on duplicate RUC)
4. Add last-order-date column
5. Add "Ver todos los ingredientes" expand
6. Replace delete with deactivate for suppliers with no ingredients
7. Add CSV export
8. Add supplier performance metrics (avg lead time, fill rate)

---

## `/suppliers/nuevo` and `/suppliers/{id}/editar` (supplier_form.html — shared)

### 5-Hat Analysis
**Counter staff:** Simple 6-field form. Clear labels. Placeholder examples for phone (+595...) and email (.com.py). Cancel link back to `/suppliers`. "Guardá" primary CTA — standard.

**Owner-finance:** RUC/Cédula field now present (our fix). Label says "RUC / Cédula" — ambiguous for Paraguay which uses RUC for businesses and Cédula for individuals. Placeholder "12345678-9" suggests a specific format. Notes textarea present for free-text.

**Production-baker:** Contact name and phone fields — enough to place a WhatsApp order.

**New user:** No inline validation. Submitting an empty required field (name) triggers browser-native HTML5 validation — works but not styled consistently with the app design.

**Auditor:** No audit trail of changes. No version/history.

### Defects (P0/P1/P2)
- [P1] RUC label says "RUC / Cédula" — ambiguous; Paraguay uses RUC for empresas and Cédula for personas. Should be two separate fields or a single "Identificación fiscal"
- [P1] No inline validation — empty form submission shows browser default
- [P1] `maxlength="20"` on RUC — PY RUCs can be up to 20 chars including dashes; 20 is fine, but no format validation (regex)
- [P2] Address is a textarea — should be a structured address input
- [P2] No duplicate-check on RUC or name before saving
- [P2] No autosave draft

### Complete Design Wishlist
1. Split RUC/Cédula into two separate validated fields
2. Add client-side RUC format validation (PY format: `0000000-0`)
3. Add duplicate-check warning before save
4. Add address autocomplete (Google Places or similar)
5. Add inline field validation (red border + message on blur)
6. Add autosave draft
7. Add edit history / changelog

---

## `/suppliers/dup` ⚠️ TEMPLATE MISSING

### 5-Hat Analysis
**Status:** Template `suppliers_dup.html` not found. The route exists (`/suppliers/dup`) but no corresponding template. Likely unimplemented.

### Defects (P0/P1/P2)
- [P0] Template not found — page is unimplemented or uses a different path

### Complete Design Wishlist
1. Implement supplier duplication feature (pre-fill form with existing supplier data for quick cloning)

---

## `/suppliers/alias` ⚠️ TEMPLATE MISSING

### 5-Hat Analysis
**Status:** Template `proveedores_alias.html` exists as a screenshot file but no matching template found. Likely unimplemented or a settings sub-section.

### Defects (P0/P1/P2)
- [P0] Template not found

### Complete Design Wishlist
1. Clarify if this is a settings sub-page or standalone page
2. Design supplier alias/alternate-name feature

---

## `/users` (users.html)

### 5-Hat Analysis
**Counter staff:** Never accesses this page (admin only).

**Owner-finance/admin:** User management table: username, rol badge (color-coded: red for admin, amber for manager, blue for cashier), status pill, last login, created date. Inline edit via `onclick` JavaScript — no page navigation. Delete with confirmation modal. "Tú" badge on the current user row. 3 separate `<dialog>` elements for new user, edit user, delete user modals — verbose but functional.

**New user (admin):** "Solo los administradores pueden gestionar usuarios" disclaimer at top — good. Dialog-based create/edit avoids full page navigation. But the modals use raw `<dialog>` with inline styles instead of the design system.

**Auditor:** User role changes are auditable via the auditoria log. No user activity log on this page itself.

### Defects (P0/P1/P2)
- [P0] Role badge colors defined as raw CSS in a `<style>` block at the bottom (lines 266-289: `.badge-role-admin { background: #fee2e2; color: #991b1b; }`) — these should use CSS custom properties / design tokens from the design system, not ad-hoc hex values
- [P0] Role assignment in edit form uses a raw combo widget but the role is passed as `{{ u.role }}` which could be an arbitrary string — no server-side role validation visible
- [P1] 371 lines of inline JavaScript + inline CSS in the template — massive maintenance burden; should be in a separate JS file
- [P1] Dialog elements use raw inline styles (`style="border: none; border-radius: var(--card-radius); padding: 2rem; width: 400px;...") instead of using a shared modal component
- [P1] Edit user modal pre-fills role via `document.getElementById('edit-role').value = role` but there's no visible role dropdown in the edit form — user can't change role via the modal
- [P2] No pagination — if >50 users, the table gets long
- [P2] "Eliminar" button has no tooltip explaining what happens to data associated with the deleted user

### Complete Design Wishlist
1. Extract all inline `<style>` and `<script>` to external files
2. Use a shared modal component from `_components/atoms.html`
3. Add role-in-edit functionality (currently broken)
4. Add pagination
5. Add user activity summary (last 10 actions)
6. Add "deactivate instead of delete" option
7. Add role change history

---

## `/delivery-zones` (delivery_zones.html)

### 5-Hat Analysis
**Counter staff:** Used when creating a delivery order — the zones table shows coverage, radius, delivery cost, minimum order, and time. Simple read-only reference table.

**Owner-finance:** Shows delivery economics per zone: cost, minimum order, time. Useful for pricing decisions.

**Production-baker:** Knows delivery time per zone for scheduling.

**New user:** Source attribution at bottom ("HEREBUS ZONAS_DELIVERY") explains where the data comes from. No edit/add capability visible.

**Auditor:** Source documented. No edit audit.

### Defects (P0/P1/P2)
- [P1] No CRUD operations — zones are read-only; no way to add/edit/delete zones from the UI
- [P1] "Cobertura Asunción/San Lorenzo" is hardcoded in the page header description — not driven by actual data
- [P2] `m.gs()` formatting for `delivery_cost_gs` but if cost is 0, shows "gratis" — good, but inconsistent with how other zero amounts display elsewhere
- [P2] No zone map or visual representation
- [P2] No "Fuera" (out-of-coverage) handling visible in the table

### Complete Design Wishlist
1. Add CRUD for delivery zones (add/edit/delete)
2. Add zone map visualization
3. Add "out of coverage" zone with manual handling flag
4. Add zone utilization metrics (orders per zone)
5. Add minimum order threshold recommendations
6. Add delivery time estimation per zone

---

## `/riesgos` (riesgos.html)

### 5-Hat Analysis
**Counter staff:** No direct use.

**Owner-finance/risk-manager:** Risk register with 4 KPI cards: Activos, Mitigados, Cerrados, Severidad total Gs. Table grouped by category, showing: ID code, description, probability (1-5), impact Gs., severity Gs. (calculated), mitigation notes, status badge (🔴Activo/🟡Mitigado/✓Cerrado), owner. Good structure for risk management.

**Production-baker:** Relevant for operational risks (supply chain, equipment failure).

**New user:** "Arrancá cargando los riesgos más importantes" empty state CTA. Clear.

**Auditor:** Risk register is auditable. No change history.

### Defects (P0/P1/P2)
- [P0] Line 12: "Agregar riesgo" button uses `onclick="alert('Pronto: formulario para agregar un riesgo...')"` — hardcoded JS alert, placeholder feature — this is a known TODO but ships as a non-functional button
- [P1] "Mitigated" status badge uses emoji `🟡` but Spanish label says "Mitigado" — inconsistent with other status pills that use `ui.status_pill()` with `sev=` parameter
- [P1] Severity calculation (probability × impact) is stored as `r.severity` but the formula is not visible or auditable — could be calculated differently per entry
- [P2] No date tracking (when identified, when mitigated, when closed)
- [P2] Owner field is free text — no validation, no dropdown from user list

### Complete Design Wishlist
1. Wire "Agregar riesgo" to a real form/modal
2. Replace emoji status badges with `ui.status_pill()` for consistency
3. Add severity formula documentation or make it calculated on display
4. Add date fields: identified_date, mitigated_date, closed_date
5. Add owner dropdown from user list
6. Add risk action log (history of changes)
7. Add "Risk heat map" visualization

---

## `/wishlist` (wishlist.html)

### 5-Hat Analysis
**Counter staff:** No direct use.

**Owner-finance:** Equipment procurement planning tool. 5 KPI cards: Artículos totales, Pendientes, Comprados, Inversión total Gs., Pendiente Gs. Grouped by priority: 🟢 Must-have, 🟡 Nice-to-have, ⚪ Opcional. Table shows: ID code, item name, qty, unit Gs., total Gs., category, buy location, status badge (✓Comprado / Pendiente), action buttons.

**Production-baker:** May use to plan equipment purchases.

**New user:** Clear structure. "Mark as purchased" and "Send to shopping list" actions per row.

**Auditor:** Purchased items shown at 50% opacity — good visual distinction. No cost tracking history.

### Defects (P0/P1/P2)
- [P1] Priority emoji headers (🟢🟡⚪) are hardcoded in the template (lines 19-21) — if priority labels change in the data model, these will be inconsistent
- [P1] "Send to shopping list" button sends to `/wishlist/{id}/send-to-shopping-list` — this endpoint may not exist (needs verification)
- [P2] Purchased items at 50% opacity — good but no strikethrough on the name
- [P2] No filter by priority — can't show only pending items
- [P2] No total investment per priority group

### Complete Design Wishlist
1. Add priority filter tabs (All / Must-have / Nice-to-have / Optional)
2. Add "mark all must-have as purchased" bulk action
3. Add investment breakdown chart per priority group
4. Add strikethrough to purchased item names
5. Verify and wire "Send to shopping list" endpoint
6. Add vendor/Supplier link per item
7. Add "expected delivery date" per item

---

## Cross-Page Defects: Admin

| ID | Page | Severity | Issue |
|----|------|----------|-------|
| A1 | suppliers | P1 | "Ordenar" (WhatsApp) button 404s — no `/ordenes` endpoint |
| A2 | suppliers | P1 | No search/filter on supplier list |
| A3 | supplier_form | P1 | RUC/Cédula label ambiguous — should be two fields |
| A4 | users | P0 | Massive inline `<style>` + `<script>` (371 lines) — must be externalized |
| A5 | users | P1 | Role-in-edit broken — form pre-fills role but can't change it |
| A6 | users | P1 | 3 raw `<dialog>` elements with inline styles — should use shared modal component |
| A7 | delivery-zones | P1 | No CRUD — read-only, no way to add/edit zones |
| A8 | riesgos | P0 | "Agregar riesgo" button is a non-functional JS `alert()` placeholder |
| A9 | riesgos | P1 | Emoji status badges (🟡🟢) inconsistent with `ui.status_pill()` used elsewhere |
| A10 | wishlist | P1 | Priority emoji (🟢🟡⚪) hardcoded in template — not from data |
| A11 | wishlist | P1 | "Send to shopping list" endpoint unwired |
