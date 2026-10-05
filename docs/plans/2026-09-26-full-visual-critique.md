# Sazón — Full Visual Critique (2026-09-26)

Consolidated from vision critique agents over the 2026-09-26c screenshot capture (HEAD 7100bbc).
Status: ✅ compras/reposición | ✅ operaciones (13 pages — full report in redesign-2026-09-26/03-critique-operaciones-full.txt) | ⏳ catálogo (queued) | ⏳ finanzas/long-tail (queued)

---

## SECTION: Compras & Reposición (8 pages) ✅

### Cross-page issues
1. English breadcrumbs on Spanish pages — "Inicio › Suppliers", "Inicio › Supplier form", "Inicio › Reorder", "Inicio › Wishlist" — crumb text never matches the sidebar label or H1.
2. "Clientes" is filed under COMPRAS though it is a sales/CRM concern; also breaks the sidebar's icon/indent pattern (Proveedores indented without icon).
3. "KPIs (mensual)" mixes English acronym + Spanish, grammatically wrong (should be "KPIs mensuales"); oddly under SISTEMA.
4. Top-bar "≡ Nuevo" doesn't say what it creates; stray "?" chip next to "⌘K" in search is unexplained; ⌘K hint is Mac-only.
5. Mixed date formats across screens (top bar "26 sep 2026" vs table "26/09/2026").
6. Voseo/neutral register inconsistent: "Guardá"/"Agregá" vs neutral "Guardar"/"No hay proveedores todavía"/"va a aparecer acá".

### Clientes (list)
- Issues: loyalty-tier badge shows English "Bronze" (should be "Bronce"). Both seed clients share phone 0981112222 and the filter searches by phone → duplicate lookups break. Filters stacked full-width (search + level select + full-width "Filtrar" + unstyled "Limpiar") — wasteful, ambiguous live-vs-button filtering. Loyalty explainer sits in the same row as action buttons. "Ver" action column has no header.
- Redesign: inline filter row (search grows, selects fixed width, Limpiar as link); "Bronce/Plata/Oro" tiers; dedupe phone on create.

### Cliente detalle
- Issues: "Nivel: Bronze" untranslated. Two stacked conflicting breadcrumbs ("Inicio › Cliente detalle" and "Clientes › María López"); name appears 3×. Clock mismatch: header 17:48 vs activity log 20:47 same day. Empty email/CI-RUC/última compra as ragged "—". Nine fields stacked in one narrow column wasting ~70% width. "Editar" uses external-link icon. Notes box ("alergia: gluten") looks editable without save affordance; allergies as free-text notes is a data-modeling smell for a food business.
- Redesign: 2-column info grid; single breadcrumb; structured allergy field (checkboxes like the allergen taxonomy); purchase history chart.

### Cliente editar
- Issues: breadcrumb "Cliente editar" unnatural word order, duplicates second crumb trail. Only Nombre marked required, no "* = obligatorio" legend, no placeholders/format examples for Email or CI/RUC. "CI / RUC" jargon without helper text. Label "Notas" but helper says "Notas internas". No delete/deactivate action. Form card uses half the width.
- Redesign: labels + helpers consistent; CI/RUC format hint ("Ej: 1234567-8"); danger zone at bottom; max-width 720px form.

### Proveedores (empty state; /suppliers and /proveedores render identically)
- Issues: breadcrumb "Inicio › Suppliers" untranslated. Empty state references "la página de reorden" while sidebar calls it "Reponer" — same feature, two names. Two simultaneous CTAs ("+ Nuevo proveedor" and "+ Agregar el primero") using different verbs (Nuevo vs Agregar). Empty state sits high in a large blank area. Duplicate route (/suppliers ≡ /proveedores) should be merged.
- Redesign: single canonical /proveedores route with redirect; one CTA verb; centered empty state with illustration.

### Supplier nuevo
- Issues: breadcrumb "Inicio › Supplier form" untranslated, skips parent level. Save button "Guardá" is the only voseo imperative on the page. Placeholders inconsistent (name/email/phone have good Ej: examples; Dirección and Notas have none). Missing RUC/tax-ID field for the Paraguayan market. Full-width single-line inputs too long.
- Redesign: breadcrumb "Inicio › Proveedores › Nuevo"; "Guardar proveedor"; RUC field with format hint; constrained form width.

### Reponer stock (/reorder)
- Issues: breadcrumb "Inicio › Reorder" untranslated. Grammar: "Mostrando 1-1 de 1 ingredientes" → "1 ingrediente". REPONER column stacks qty/unit/price/button vertically, tripling row height; green-bordered unit input looks like a validation state. Price "1800" lacks thousands separator (should be "Gs. 18.000"); "Gs." unit inconsistent between subtitle and cells. Total row misaligned (under tendencia/proveedor, not under costo est.) and total appears twice. "Ver como JSON" is a developer artifact exposed to users. "Reponer" overloaded as nav item + column + row button. Disabled "Generar pedido por WhatsApp" gives no reason. Unlabeled checkbox column. Pale-yellow "Bajo mínimo" badge weak.
- Redesign: inline row layout (qty input × price × subtotal, button right); JSON link behind ?debug; tooltip on disabled WhatsApp button ("seleccioná proveedor primero"); singular/plural fix.

### Wishlist
- Worst page. KPIs all 0 while the info note claims the source sheet has 28 items / Gs. 61M — data fetch failed silently, no table, no error, no loading state. Breadcrumb "Wishlist" vs title "Lista de deseos". Note leaks internal artifact "HEREBUS_Lista de deseos sheet" (raw sheet name + English "sheet"). KPI labels inconsistent: "Inversión total" (no currency) vs "Pendiente Gs." (currency crammed into label, wraps); "61M" informal vs full Gs. formatting elsewhere; "Items totales" anglicism. Storefront emoji with "24" badge in H1 ambiguous (24 vs 28 mismatch). No actions on the page (no add/import/sync).
- Redesign: fix the data fetch (or show an explicit error state); label as "Equipamiento" (matches sidebar); strip sheet-name leak; "Artículos totales"; add "Agregar artículo" CTA.

### Top fixes by severity (section)
1. Wishlist data not rendering despite claimed 28-item source
2. Untranslated breadcrumbs (Suppliers, Supplier form, Reorder, Wishlist) and "Bronze" tier
3. Detail-page clock/timestamp contradiction
4. REPONER column layout + number formatting
5. Terminology unification (Reponer vs reorden, Nuevo vs Agregar, Guardá vs Guardar)
6. Move Clientes out of COMPRAS
7. Form validation hints and CI/RUC helper text
