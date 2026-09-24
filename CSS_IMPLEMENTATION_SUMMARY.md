# CSS Implementation — Final Status (2026-09-23)

## ✅ What was implemented (Phase 1 + 2 + part of 4)

### app-improvements.css (new, 6 KB)
- **`--z-*` stacking variables**: --z-base(0), --z-raised(1), --z-dropdown(100), --z-sticky(200), --z-overlay(300), --z-modal(400), --z-toast(500), --z-tooltip(600)
- **`@media (prefers-color-scheme: dark)`**: auto-activates dark theme when OS pref is dark (unless user explicitly set light)
- **`:focus-visible` ring**: orange outline + soft halo, applied to buttons, links, inputs, textareas, selects, role="button", tabindex elements
- **`@media (hover: none)`**: 44px min tap targets on touch devices (buttons), 36px for `.btn-sm`
- **`.bulk-actions` class**: extracted from 2 inline-style divs (productos.html, clientes.html)
- **`.flex-center`, `.flex-between`, `.flex-col`, `.flex-wrap`**: utility flex classes
- **`.gap-1` through `.gap-4`**: utility gap classes
- **`.col-checkbox`, `.col-sku`, `.col-portion`, `.col-price`, `.col-recipe`, `.col-cost`, `.col-margin`, `.col-marginpct`, `.col-available`, `.col-actions`**: table column width utilities (extracted from productos.html)
- **`.pagination`, `.pagination-info`, `.pagination-links`, `.table-controls`, `.table-info`**: extracted from inline `<style>` blocks
- **`@supports (backdrop-filter)`** with `-webkit-` prefix: Safari support
- **Comprehensive `@media print`**: hides nav, buttons, modals, notifications, etc.
- **Aggressive `prefers-reduced-motion`**: kills ALL animations/transitions when set

### Templates updated
- **base.html**: added `<link rel="stylesheet" href="/static/app-improvements.css">`
- **productos.html**: 
  - `<div id="bulk-actions" style="...">` → `<div id="bulk-actions" class="bulk-actions">`
  - Removed redundant inline `.col-*`, `.pagination`, `.table-controls` rules (now in app-improvements.css)
- **clientes.html**:
  - `<div id="bulk-actions-clients" style="...">` → `<div id="bulk-actions-clients" class="bulk-actions">`

### Documentation
- **CSS_AUDIT.md**: 20-issue audit + 5-phase plan

## ⏳ Still pending (Phases 3, 5, parts of 4)

### Phase 3 — Refactor (2-4 hours)
- Split `app.css` (43.5 KB single line) into logical modules:
  - `base/reset.css`, `base/variables.css`, `base/typography.css`
  - `layout/topnav.css`, `layout/container.css`, `layout/grid.css`
  - `components/btn.css`, `components/card.css`, `components/table.css`, `components/badge.css`
  - `components/form.css`, `components/modal.css`, `components/tooltip.css`
  - `features/calendar.css`, `features/combos.css`, `features/charts.css`
  - `themes/light.css`, `themes/dark.css`, `themes/print.css`
- Add build step that concatenates and minifies

### Phase 4 — Quality (1-2 hours)
- Convert 51 ID selectors to classes
- Add Autoprefixer / vendor prefixes (currently 1 missing -webkit-backdrop-filter)
- Audit each animation for `prefers-reduced-motion` coverage
- Add `:focus-visible` for all interactive elements (DONE in this commit)
- Comprehensive print rules (DONE in this commit)
- `@layer` cascade order (modern CSS)

### Phase 5 — Mobile polish
- `@media (hover: none)` tap target audit (DONE basics, needs full audit)
- Test all pages at 375px viewport
- Fix horizontal overflow on mobile
- Replace remaining 350+ inline styles (focus on dashboard.html: 14, recibo.html: 14, users.html: 22)

## Verification

All 9 critical routes still 200 after changes:
- /healthz, /healthz/db, /productos, /clientes, /recetas, /dashboard
- /productos/nuevo, /recetas/nueva, /

app-improvements.css loads with 5,508 bytes.

## Impact

- **Browser-side dark mode**: now automatic (was opt-in only)
- **Keyboard accessibility**: focus ring now consistent (was inconsistent/invisible)
- **Mobile touch targets**: 44px minimum on touch devices (was 24px)
- **Print output**: cleaner (no nav, buttons, etc. in printed reports)
- **Code maintainability**: 2 inline styles → reusable class; ~15 CSS lines deduplicated
