# Sazón — Visual Revolution Plan

**Date:** 2026-09-17
**Author:** Hermes (research + plan)
**Status:** Proposal — for operator review
**Goal:** Transform Sazón from bottom-10% visual quality to top-20% in the restaurant management software category, while staying locked to the Fase1 tech stack (no Tailwind, no React, server-rendered HTML, single CSS file, zero new deps without OK).

---

## Executive Summary

Sazón has a tight, well-tested Fase1 backend (54 routes, 992 tests, 13 locked hotfixes). What it lacks is **visual identity, modern interaction, and at-a-glance information design**. Every competitor we benchmarked — Toast, Square, Lightspeed, SpotOn, Clover, Apicbase, MarketMan, Restaurant365, Forkiva — invests heavily in visual polish because **operators who feel in control of their software make better decisions** and **stay with the product longer**.

This plan proposes a 5-phase visual rebuild that ships in 8-12 focused days of work, **adds zero production dependencies** (only one optional CDN for chart hydration), and **respects every locked rule** in `AGENTS.md` (no Tailwind, no async, no React, server-rendered Jinja2, integer Gs, Paraguayan Spanish *vos*, no silent overwrite, CSP-safe, no PII).

The work is staged so each phase is independently shippable, has a visual diff the operator can verify in the live Render deploy, and is fail-closed by at least one test. The plan **does not require** rewriting any backend code beyond template/asset changes — the routes, models, services, money/units code stay untouched.

---

## 1. What we learned from the research

Sources consulted (all citations in §11):

### 1.1 Visual design fundamentals
From *19 Web Design Principles for User-Centric Sites* (UX Pilot) and *Web Design Best Practices* (Hostinger):
- **Clarity & simplicity** — one primary action per view, no jargon, one brand color + one neutral + one accent
- **Visual hierarchy** — 3 size tiers only (body 14-16px, subhead 18-22px, heading 24-32px); WCAG contrast 4.5:1 normal / 3:1 large
- **Grid-based layout** — 12-col grid, 24px gutters, 32-40px outer margins, max width 1200-1280px
- **White space as a feature** — 8/16/24/32px spacing scale, never decorative borders
- **Mobile-first** — 44×44pt touch targets, hamburger menu below 768px, primary CTA center-of-fold on mobile
- **Core Web Vitals** — LCP ≤ 2.5s, CLS ≤ 0.1, INP ≤ 200ms (we're well inside this on Render)

### 1.2 Design tokens & Tailwind v4 philosophy
From *Design tokens vs CSS variables vs Tailwind* (Adam Arant, 2026) and *Tailwind v4 design system* (Redline Soft):
- The W3C DTCG token format (`$.value`, `.tokens.json`) reached **stable status Oct 28 2025** — we can adopt the *runtime layer only* (CSS custom properties) without a build pipeline
- The 2-layer token model: **primitive → semantic → component**
  - Primitive: `--orange-500: #f97316`
  - Semantic: `--color-accent: var(--orange-500)`
  - Component: `--button-bg: var(--color-accent)`
- **CSS variables win the runtime** — they are the only sane way to ship dark mode, brand themes, per-tenant skins without a rebuild
- We don't need Style Dictionary, Tailwind, or any build step. We can declare the same primitive/semantic/component chain directly in `app/static/app.css` — and we already have 17 CSS variables in `:root`. We just need to **rename, regroup, and extend them**.

### 1.3 POS industry lessons
From *POS UX Benchmarking 2026* (Creative Navy + Interface Design — 4 verified practitioners across 2023-2026):
- **Toast scores highest on *conditioning stability*** — preserved core navigation structure through additive releases. **Don't overhaul nav.**
- **Square scores on *taxonomy alignment*** via AI search — we don't need this yet
- **Lightspeed has accumulated "sense decay"** — features overlaid without restructuring. **Lesson: when adding features, keep the original transaction model legible**
- The single most-cited POS UX failure is **unresolved error recovery paths** (Toast's 2-year printer-routing bug). Our 500 leaks the DNS error message — that's a sense-decay-class bug
- **All four major platforms are still text-heavy on operational screens.** Visual hierarchy, color-coded status, and at-a-glance metrics is where we can leapfrog them
- **Reigel Design's Toast Web Refresh 2.5** (case study): chunkier brand elements, rounded corners, bento-style layouts, orange CTA pills, simplified iconography, better color contrast. **Direct precedent for our approach.**

### 1.4 Data visualization for restaurants
From *Metabase Restaurant Dashboard*, *Restaurant365 Operations*, *Forkiva*:
- **The 7 standard restaurant dashboard cards** (industry consensus):
  1. Net sales today vs. yesterday (this period vs. last year)
  2. Average check size by location and daypart
  3. Hourly sales chart (line, by hour)
  4. Top items by revenue and by units
  5. Discounts/comp/void percentages as separate lines (Metabase explicit warning: do NOT mix comps and voids)
  6. Low-stock alerts (ingredient near depletion)
  7. Cash movements overview (pie/donut)
- Plus **inventory KPIs**: Soft reserved, Onhand, Sell rate, Out-of-stock
- **Refresh cadence**: daily after close; hourly during service
- **Data freshness visible on the dashboard** — every viewer should see by how much it lags
- **Chart library recommendation**: **ApexCharts** — has server-side rendering (`apexcharts/ssr`) that returns hydration-ready HTML+SVG, tree-shakable, 18+ chart types, 30-60% smaller bundles if we only ship what we use. We don't have to use the SSR feature — we can hand-render SVG server-side and never need a JS library at all.

### 1.5 Accessibility is non-negotiable
From *WCAG 2.1 AA Developer Checklist*, *PageGuard 2026*, *Web Accessibility ARIA and Semantic HTML* (Grizzly Peak):
- **The 5 most common WCAG failures** (per 78 audited projects):
  1. Keyboard navigation (2,410 violations) — every interactive element reachable via Tab/Shift+Tab/Enter/Space/arrow keys
  2. Color contrast (1,431 violations) — 4.5:1 normal text, 3:1 large text, 3:1 UI components
  3. Image alt text (301 violations)
  4. Form labels (238 violations)
  5. Heading structure (228 violations)
- **EU EAA took effect June 2025** — digital products sold in the EU must meet WCAG 2.1 AA. Paraguay doesn't have this yet but we should comply anyway because the EAA covers SaaS sold into the EU and we're aiming at premium positioning
- **Semantic HTML first** — "Do not use ARIA if native HTML can do the job." Use `<main>`, `<nav>`, `<aside>`, `<header>`, `<footer>` landmarks. Use `<button>` for actions, `<a>` for navigation. Use `<label for=...>` for every input.
- **Live regions** — `aria-live="polite"` for status messages (sale created, merma logged). Already partially implemented.
- **Focus management** — modals trap focus, return focus to trigger on close. Forms focus first invalid field on submit error.

### 1.6 Micro-interactions that feel premium
From *Micro-Interactions: Timing, CSS, and INP* (Social Animal) and *prefers-reduced-motion Architecture* (css-animation.com):
- **Timing matters more than animation**: 100-150ms hover, 100ms button press, 150-200ms toggle, 200-250ms modal open (exits faster than entrances)
- **ease-out for entrances, ease-in for exits** — matches how physical objects move
- **Animate only `transform` and `opacity`** — stays on the compositor thread, doesn't tank INP
- **Skeleton screens for >100ms loads** — user sees the shape of content before content arrives
- **Two-layer reduced-motion cascade**:
  - Layer 1 (global reset): `@media (prefers-reduced-motion: reduce)` → `animation-duration: 0.01ms !important` on every element
  - Layer 2 (restoration): re-enable essential animations (loading spinner → opacity pulse instead of rotation) inside the same media query
- **Default to reduced motion in SSR** — "fail safe toward less motion"
- **WCAG 2.3.3** (AAA) and **2.2.2** (A) both apply — pause/stop/hide for auto-updating content >5s; disableable motion unless essential

### 1.7 The Square Market design system (the most relevant reference)
From *Market — Square (Block) Design System Breakdown* (DesignSystems.one) and *N/A — Square DESIGN.md* (shadcn.io):
- **Three-tier typography** (this is the key insight for us):
  - Display serif (Exact Block, 40-81px / weight 400 / negative tracking) — used for hero/landing pages
  - Sub-heading sans (Square Sans Display VF, 24px / weight 500) — section titles
  - Body sans (Cash Sans + Square Sans Text VF, 14-18px / weight 400-500) — content
  - Eyebrow mono (Cash Sans Mono, 14px / uppercase / 1.4px tracking) — labels
- **Dual corner radii**: 50px for cards (16 uses), 10000px for nav pills (full pill), 10px for inputs, 4px for hairline tags — no rounded-rectangle middle
- **Sparing, CTA-only voltage** — blue (#006aff) appears only 19 times page-wide, every use is outline/focus, never a filled CTA. Black is the workhorse.
- **Cream canvas (#f7f6f5)** for feature bands, not pure white
- **Merchant photography** as the visual hero
- **Two-layer token model** at runtime (CSS variables), no build pipeline
- **Component library is on GitHub** — but we don't need their React, just the *principles*

### 1.8 Iconography
From *Inline SVG vs Icon Fonts* (CSS-Tricks) and *SVG Sprites and Icon Systems* (Lincoln Loop):
- **SVG sprites win over icon fonts**: scalable, currentColor support, can have multiple colors, accessible via `<use href="#icon-id">`, no font-loading FOIT
- **Pattern**: hidden `<svg>` block at the top of `base.html` containing all `<symbol id="icon-...">` definitions, then `<svg class="icon"><use href="#icon-home"/></svg>` everywhere
- We don't need an icon library — we can hand-author ~20 icons in pure SVG paths (~50 lines total)

---

## 2. Visual gap audit (current Sazón)

From my live audit of the deployed site (`app/static/app.css`, `app/templates/base.html`):

### What's already good
- ✅ Sticky topnav with brand, 14 nav links, right-side controls
- ✅ Theme toggle (light/dark) — `[data-theme="dark"]` rules exist and work
- ✅ Skip-link to `#main-content`
- ✅ `:focus-visible` outline using `--primary`
- ✅ WCAG-compliant font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui`)
- ✅ Container max-width 1100px
- ✅ `.btn`, `.btn-primary`, `.btn-danger` base classes
- ✅ `.badge-ok`, `.badge-warn`, `.badge-danger` colored badges
- ✅ Security headers (CSP, HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff)
- ✅ Semantic `<nav>`, `<main>`, `<table>`, `<form>` already in templates

### What's missing or weak
- 🟠 **No icons anywhere** — all nav is plain text
- 🟠 **No visual hierarchy beyond font weight** — H1 and H2 sizes are defined but never reinforced with color/spacing
- 🟠 **Primary color #b45309 is a brown-orange** — feels dated (1980s), not the energetic 2025 orange (#f97316 or #ea580c)
- 🟠 **No status color coding beyond 3 badge types** — sale states, inventory levels, production states have no visual distinction
- 🟠 **No data visualization** — dashboard is text-only numbers in `<table>`
- 🟠 **Tables have no hover, no striping, no compact mode**
- 🟠 **No cards** — everything is direct page content
- 🟠 **No loading states** — clicking submit gives no feedback
- 🟠 **No empty states** — fresh accounts see empty tables
- 🟠 **No skeleton screens**
- 🟠 **No animation/micro-interactions** (except `:focus-visible`)
- 🟠 **Buttons are flat rectangles** — no hover lift, no shadow
- 🟠 **404/500 returns raw JSON** — should be styled HTML
- 🟠 **Settings page has 30 inputs in one table** — no grouping, no help tooltips
- 🟠 **Theme toggle works but only has `--bg` / `--card-bg` overrides** — borders, badges, flash messages don't fully re-theme
- 🟠 **No reduced-motion handling** — once we add animations, this matters
- 🟠 **No keyboard shortcuts** — power-user gap
- 🟠 **No focus trap on modals** — once we add modals (e.g., confirm destructive actions), this matters

---

## 3. The plan — 5 phases, 8-12 working days

Each phase is independently shippable. We do Phase 0 first (foundation), then visual phases in any order. Each ships as a PR with:
- Visual diff (screenshots before/after)
- ≥1 regression test
- Updated `app/CHANGELOG.md`

### Phase 0 — Token foundation + dark mode hardening (1 day)

**Goal:** Replace the 17 raw color variables with the primitive/semantic/component token chain. Make dark mode complete.

**Tasks:**
1. Rename and regroup tokens in `app/static/app.css`:
   - **Primitives** (raw values): `--orange-50..900`, `--gray-50..900`, `--green-500..700`, `--amber-500..700`, `--red-500..700`, `--blue-500..700`
   - **Semantic** (decisions): `--color-bg`, `--color-surface`, `--color-surface-raised`, `--color-text`, `--color-text-muted`, `--color-text-inverse`, `--color-border`, `--color-border-strong`, `--color-accent`, `--color-accent-hover`, `--color-accent-soft`, `--color-success`, `--color-warn`, `--color-danger`, `--color-info`
   - **Component** (local): `--btn-primary-bg`, `--btn-primary-text`, `--badge-ok-bg`, `--badge-warn-bg`, `--badge-danger-bg`, `--topnav-bg`, `--card-bg`, `--card-border`, `--table-row-hover`, `--table-row-stripe`, `--input-border`, `--input-focus-ring`
2. Pick the brand orange: **`--orange-500: #f97316`** (matches Tailwind's `orange-500`, used by Replit, Vercel, Linear). Hover: `#ea580c`. Soft: `#fff7ed`.
3. Define `:root[data-theme="dark"]` overrides for every semantic token — no more partial dark mode.
4. Add `[data-color-scheme="high-contrast"]` variant for accessibility (Paraguayan government clients may need this).
5. Add `prefers-reduced-motion` reset (global Layer 1 from §1.6).
6. Add typography tokens: `--font-display`, `--font-sans`, `--font-mono`, `--text-xs..4xl`, `--leading-tight/normal/loose`, `--tracking-tight/normal/wide`. Keep system fonts (no new deps).
7. Add spacing scale: `--space-1..12` on a 4px grid (`--space-1: 4px`, `--space-2: 8px`, `--space-3: 12px`, `--space-4: 16px`, `--space-6: 24px`, `--space-8: 32px`, `--space-12: 48px`).
8. Add radius scale: `--radius-sm: 4px`, `--radius: 6px`, `--radius-md: 10px`, `--radius-lg: 14px`, `--radius-xl: 20px`, `--radius-pill: 9999px`.
9. Add elevation scale: `--shadow-sm`, `--shadow-md`, `--shadow-lg` (each: `0 1px 2px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.05)` etc.).
10. Update every existing rule to reference the new semantic tokens (no behavior change).
11. **Tests:**
    - `tests/test_css_tokens.py` — assert every primitive, semantic, and component token is defined on `:root` and on `[data-theme="dark"]`
    - `tests/test_dark_mode.py` — assert every page that was already dark-mode-correct still is (regression)
12. **Visual diff:** screenshot the login page in light + dark, before/after. Diff <5% per pixel on existing pages.

**Estimated time:** 6-8 hours of focused CSS work + 2 hours of test writing.

**Operator checkpoint:** Live deploy, navigate every page, confirm nothing visually changed (only token names). Confirm dark mode is now actually complete.

---

### Phase 1 — Component library: buttons, cards, badges, forms, tables (3-4 days)

**Goal:** Replace inline `<button>` and `<table>` styling with reusable, accessible component classes that every template can use.

**Tasks:**
1. **Buttons** — full state machine:
   - `.btn` (base), `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`, `.btn-danger-ghost`
   - Hover: background shift + `transform: translateY(-1px)` + `--shadow-sm` (compositor-only, reduced-motion safe via Layer 1)
   - Active: `transform: translateY(0)` + `--shadow-none`
   - Focus-visible: 2px outline using `--color-accent` + 2px offset
   - Disabled: 50% opacity, `cursor: not-allowed`, no hover transform
   - Loading state: `.btn.is-loading` → adds spinner + disables interaction, `aria-busy="true"`
   - Sizes: `.btn-sm` (28px), default (36px), `.btn-lg` (44px — meets WCAG 2.5.5 target size)
   - Icon-only: `.btn-icon` with mandatory `aria-label`
2. **Cards** — the foundational layout primitive:
   - `.card` — `--surface`, `--card-border`, `--radius-lg`, `--shadow-sm`, `padding: --space-6`
   - `.card-header` with optional title + actions slot
   - `.card-body` (default padding) / `.card-body--compact` (for dense data)
   - `.card-footer` for actions
   - Hover variant: `.card.is-interactive` (links/buttons inside)
3. **Badges** — extend existing:
   - `.badge` (base), `.badge-ok`, `.badge-warn`, `.badge-danger`, `.badge-info`, `.badge-neutral`
   - Sizes: `.badge-sm`, default, `.badge-lg`
   - Optional `.badge-dot` for compact status indicators (e.g., online/offline)
4. **Forms** — full WCAG 2.4.6 + 3.3.2 compliant:
   - `.form-row` (existing) — but now with proper `<label>` association audit
   - Floating labels OR top-aligned labels (pick one — top-aligned is more accessible per WCAG)
   - `.form-help` for hint text, paired via `aria-describedby`
   - `.form-error` for validation errors, paired via `aria-describedby`, with `aria-invalid="true"` on the input
   - `.form-row--required` adds a visible "obligatorio" marker + `aria-required="true"`
   - `.input` (text/email/password), `.input-search`, `.textarea`, `.select`, `.checkbox`, `.radio`
   - All inputs: 44px min-height, 1px border `--color-border`, focus border `--color-accent` + 2px ring
   - `.input.is-invalid` red border + red focus ring + error message below
   - `.input-group` for compound inputs (e.g., quantity + unit)
5. **Tables** — semantic, accessible, beautiful:
   - `.table` (base) — 100% width, `--color-border` between rows
   - `.table.is-striped` — alternate row backgrounds
   - `.table.is-hoverable` — row hover background
   - `.table--compact` — 8px padding instead of 12px (for dense data)
   - `.table--comfortable` — 16px padding (default for reports)
   - Sticky header: `.table thead th { position: sticky; top: 0; background: var(--surface); }`
   - Right-align numerics (`.num`), center-align actions (`.actions`)
   - Empty state row: `<tr class="empty"><td colspan="N">No hay datos todavía.</td></tr>` with subtle illustration + helpful CTA
6. **Alerts / flash messages** — `.alert`, `.alert-success`, `.alert-warn`, `.alert-danger`, `.alert-info`. Auto-dismiss option for success only. `role="status"` and `aria-live="polite"` for non-blocking; `role="alert"` for blocking.
7. **Modal** — `.modal`, `.modal-backdrop`, `.modal-dialog`, focus-trap JS (≤30 lines), Esc-to-close, click-backdrop-to-close (with confirm if form is dirty).
8. **Empty states** — `.empty-state` with icon slot + title + body + CTA. Used in every list page when 0 rows.
9. **Loading states** — `.skeleton` (block, line, circle variants) + `.spinner` (CSS-only conic-gradient ring, reduced-motion → opacity pulse per §1.6).
10. **Tests:**
    - `tests/test_components.py` — render each component in isolation, assert required ARIA attributes, contrast ratio (axe-core-style checks), keyboard tab order
    - `tests/test_keyboard_nav.py` — Tab through every page, assert focus never gets lost
    - `tests/test_reduced_motion.py` — Playwright test (we'd add Playwright as a *dev-only* dep — already on wishlist, OK per AGENTS.md)
11. **Visual diff:** before/after screenshots of /login, /, /ventas, /productos, /settings. Side-by-side comparison.

**Estimated time:** 16-20 hours.

**Operator checkpoint:** Live deploy, click through every page, confirm buttons feel responsive, cards give content breathing room, tables are scannable, form errors are obvious, keyboard-only navigation works (unplug mouse).

---

### Phase 2 — Iconography (1 day)

**Goal:** Hand-author 20 SVG icons in a single sprite, integrated via `<use href="#icon-id">`. No font dependency, no JS dependency.

**Tasks:**
1. Author 20 icons in pure SVG (24×24 viewBox, stroke 2px, currentColor):
   - `icon-home`, `icon-box` (productos), `icon-recipe` (recetas), `icon-inventory`, `icon-sale` (ventas), `icon-customer`, `icon-production`, `icon-close` (eod), `icon-waste` (merma), `icon-report`, `icon-audit`, `icon-ops`, `icon-excel`, `icon-config`, `icon-reorder`, `icon-search`, `icon-plus`, `icon-edit`, `icon-delete`, `icon-check`
2. Add the sprite `<svg style="display:none">…</svg>` block to `base.html` right after `<body>`
3. Define `.icon` base class: `width: 1em; height: 1em; fill: currentColor; flex-shrink: 0;`
4. Replace text-only nav links with `<svg class="icon"><use href="#icon-home"/></svg> Inicio` (icon + text, both visible — accessibility)
5. Replace text-only action buttons where appropriate (search, +, edit, delete) with icon buttons (with `aria-label`)
6. **Tests:**
    - `tests/test_icons.py` — assert every icon referenced in templates exists in the sprite, every icon button has `aria-label`
    - Lighthouse/Playwright audit: zero missing-icon console errors
7. **Visual diff:** before/after of every nav.

**Estimated time:** 4-6 hours.

**Operator checkpoint:** Live deploy, confirm every nav item has its icon. Confirm icons inherit text color (theme toggle changes them too).

---

### Phase 3 — Dashboard data visualization (2-3 days)

**Goal:** Replace the text-only `/` dashboard with the 7 industry-standard cards (per §1.4). Server-rendered SVG charts. No JS chart library required.

**Tasks:**
1. **Add a new template partial** `app/templates/_components/chart_line.html` — server-rendered SVG line chart (~150 lines of Jinja2 + Python helpers in `app/rms/charts.py`). Features:
   - Pure SVG output, no JS
   - Responsive (uses `viewBox` + 100% width)
   - Accessible: `<title>` + `<desc>` + `role="img"` + `aria-label`
   - Hover state via CSS (`:hover .data-point { fill: var(--color-accent); }`)
   - Reduced-motion safe (no animations)
   - Falls back to a simple `<table>` for screen readers via `aria-describedby`
2. **Add the 7 cards to `/`**:
   - **Card 1 — Ventas hoy**: big number + comparison to yesterday (delta with ↑/↓ icon + percentage)
   - **Card 2 — Ticket promedio**: big number + comparison
   - **Card 3 — Ventas por hora**: line chart (today, last 7 days overlay)
   - **Card 4 — Top productos**: horizontal bar list (top 5 by revenue, with sales count)
   - **Card 5 — Alertas de stock**: badge list (items below reorder point, color-coded by severity)
   - **Card 6 — Estado de inventario**: pie/donut chart (in stock / low / out of stock)
   - **Card 7 — Movimientos del día**: small line/area chart (sales vs. costs)
3. **Build the data layer** in `app/routers/dashboard.py` (new queries, all aggregations done in Postgres):
   - Use the existing SQLAlchemy 2 sync models
   - Query today, yesterday, last 7 days
   - All money in integer Gs (per AGENTS.md hard rule #4)
   - Format with existing money/units helpers
4. **Show data freshness** — every chart has a `<small>Actualizado HH:MM:SS</small>` timestamp, refreshes on page load
5. **Empty states** — if 0 sales today, show "Hoy todavía no registramos ventas. Probá cargar una venta →" with a CTA to /ventas/nueva
6. **Tests:**
    - `tests/test_dashboard_data.py` — assert aggregations match raw SQL for fixture data
    - `tests/test_dashboard_svg.py` — assert SVG output is valid, has required ARIA, no JavaScript
    - `tests/test_dashboard_freshness.py` — assert timestamp is present
7. **Visual diff:** before/after screenshot of /.

**Estimated time:** 12-16 hours.

**Operator checkpoint:** Live deploy, visit `/` on the production data, confirm all 7 cards render, charts look beautiful, empty states are friendly.

---

### Phase 4 — Polish: empty states, 404/500 pages, settings reorganization, mobile (1-2 days)

**Goal:** Close the remaining UX gaps that don't fit cleanly into other phases.

**Tasks:**
1. **404 page** — new `app/templates/errors/404.html` with the same nav, friendly message, "Volver al inicio" CTA. Wire a `StarletteHTTPException` handler in `app/rms/main.py`.
2. **500 page** — same treatment but with a sanitized message (no leaking the `[Errno -2] Name or service not known` exception — log it, show "Algo salió mal. Pasale este código al operador: <request_id>"). Wire the `Exception` handler.
3. **Settings page** — group the 30 settings into 4 sections: General · Inventario · Notificaciones · Impuestos. Add `<small>` help text under each input. Add "Restablecer valores predeterminados" CTA per section.
4. **Confirmation dialogs** — for destructive actions (anular venta, eliminar cliente, reimportar Excel). Reusable modal component.
5. **Mobile breakpoints** — audit all templates at 375px width (iPhone SE). Fix any horizontal overflow. Hamburger menu below 768px (CSS-only via `<details>` or `<input type="checkbox">` trick — no JS).
6. **Keyboard shortcuts** (stretch, only if Phase 1-3 done first):
   - `g i` → Inicio, `g v` → Ventas, `g p` → Productos, `?` → Show shortcuts modal
   - ~50 lines of vanilla JS in a new `app/static/shortcuts.js`
7. **Tests:**
    - `tests/test_error_pages.py` — assert 404/500 return HTML with required nav links
    - `tests/test_error_sanitization.py` — assert raw exception text never reaches the response body
    - `tests/test_settings_groups.py` — assert every setting belongs to exactly one group
    - `tests/test_mobile_responsive.py` — Playwright test at 375px, 768px, 1280px viewports
8. **Visual diff:** before/after of 404 page, settings page, mobile menu.

**Estimated time:** 8-12 hours.

**Operator checkpoint:** Live deploy, mistype a URL (test 404), check the message is friendly. Visit /settings on mobile.

---

### Phase 5 — Accessibility audit + Lighthouse pass (1 day)

**Goal:** Hit Lighthouse 95+ on all four categories (Performance, Accessibility, Best Practices, SEO) on every page. Catch every WCAG AA issue.

**Tasks:**
1. **Run axe-core** on every page via Playwright. Fix every violation.
2. **Keyboard audit** — unplug mouse, navigate every page with Tab/Shift+Tab/Enter/Space/arrow. Document every trap.
3. **Screen reader audit** — VoiceOver (macOS) or NVDA (Windows) on /, /ventas, /ventas/nueva, /inventario, /settings. Document every weird announcement.
4. **Color contrast audit** — every text element passes 4.5:1 normal / 3:1 large in both light and dark mode. Fix any that fail.
5. **Form label audit** — every input has a `<label for=...>` programmatically associated. Fix any that don't.
6. **Heading hierarchy audit** — no skipped levels (h1 → h2 → h3, never h1 → h3). Fix any.
7. **Skip-link audit** — first Tab on every page lands on the skip-link. Fix any.
8. **Lighthouse CI** — add a `lighthouse` step to CI (we already have Playwright planned for Phase 1). Fail if any page drops below 95.
9. **Reduced-motion audit** — toggle OS setting, confirm all animations stop or fall back to opacity-only.
10. **High-contrast mode audit** — Windows High Contrast / `forced-colors: active` media query. Add explicit overrides where needed.
11. **Tests:**
    - `tests/test_a11y.py` — axe-core integration, fail if any violation
    - `tests/test_lighthouse.py` — Lighthouse CI integration
12. **Report:** Markdown file `docs/operations/2026-09-XX-a11y-audit.md` with score per page, list of fixes, before/after screenshots.

**Estimated time:** 6-8 hours (audit) + 2-4 hours (fixes) = 8-12 hours.

**Operator checkpoint:** Lighthouse report attached to PR. Every page ≥95. No axe-core violations.

---

## 4. Stack discipline — what we are NOT doing

Per `AGENTS.md` hard rules + Fase1 tech review (`docs/operations/2026-09-tech-stack-review.md`):

- ❌ **No Tailwind, no PostCSS, no Vite, no bundler.** Pure hand-written CSS in `app/static/app.css`. The token system lives entirely in `:root` declarations.
- ❌ **No React, no Vue, no Svelte, no htmx.** Server-rendered Jinja2 only.
- ❌ **No async route handlers.** Sync FastAPI. The chart partial is pure Jinja2 + Python helpers.
- ❌ **No new production dependencies.** Zero. The Phase 3 charts are hand-rolled SVG. The modal in Phase 1 is ≤30 lines of vanilla JS. The keyboard shortcuts in Phase 4 are ≤50 lines.
- ❌ **No client-side router, no SPA shell.** Every nav is a full page reload.
- ❌ **No Alembic, no migrations.** Existing schema stays; dashboard queries are read-only.
- ❌ **No floating-label forms.** Top-aligned labels (better WCAG compliance per §1.5).
- ❌ **No third-party icons, no icon font.** Hand-authored SVG sprites in `base.html`.
- ❌ **No chart JS library.** Hand-rolled SVG. If we hit a limit, we evaluate Chart.js or ApexCharts in a separate PR with operator OK.
- ⚠️ **Optional dev dep:** Playwright for visual diffs + a11y tests. This is on the wishlist; needs operator OK.

---

## 5. Hard rules checklist (from AGENTS.md)

| Rule | How this plan complies |
|---|---|
| #1 No new deps without operator OK | Zero prod deps. Playwright dev dep flagged. |
| #2 Decimal for money, never float | All dashboard aggregations stay in integer Gs in the DB. |
| #3 Round half-up at persistence sites only | No changes to money handling. |
| #4 Integer Gs in DB | No schema changes. |
| #5 Paraguayan Spanish only | All UI strings continue in vos. New copy added in vos. |
| #6 Vos form for verbs | All button labels ("Guardá", "Anulá", "Marcá"). |
| #7 Bind to 127.0.0.1 / 0.0.0.0 | No changes to `main.py` binding. |
| #8 WAL mode + secure_delete = ON | No DB changes. |
| #9 No live customer PII | Dashboard shows aggregated sales only. |
| #10 No silent overwrite | Confirmation dialogs in Phase 4. |
| #11 Never commit credentials | No new credentials touched. |

---

## 6. Backwards compatibility

The CSS token rename in Phase 0 is purely an internal refactor — no template changes required to keep the app looking identical. Every existing template continues to work; we add new component classes (`card`, `table`, `badge-dot`, `alert`, etc.) without removing the old inline patterns. Templates can be migrated to use the new classes one-by-one across future PRs.

No route changes. No model changes. No migration. No API change. The `app/CHANGELOG.md` discipline applies — each phase updates the changelog.

---

## 7. Testing strategy

- **Unit tests** (pytest): token definitions, component ARIA attributes, money formatting, dashboard aggregations
- **Regression tests** (pytest): every existing test continues to pass (986 currently passing)
- **Visual diff** (Playwright + screenshot): before/after for every changed page
- **Accessibility** (axe-core via Playwright): zero violations on every page
- **Keyboard** (Playwright with `keyboard.press`): Tab order, focus trap, Esc-to-close
- **Reduced motion** (Playwright with `colorScheme` and `reducedMotion`): confirm animations respect the OS setting
- **Mobile** (Playwright with viewport): 375px, 768px, 1280px
- **Lighthouse CI**: Performance ≥95, Accessibility ≥95, Best Practices ≥95, SEO ≥95

The hotfix regression test discipline (`tests/test_hotfix_regressions.py`) is extended to include visual regressions — if a CSS change breaks any of the locked hotfix paths (login form, CSRF, security headers, audit log), the test fails.

---

## 8. Operator decision points

Before starting any phase, confirm with operator:

1. **Phase 0**: Are you OK with the brand color being `#f97316` (orange-500)? Alternatives: `#ea580c` (deeper orange, more like Toast), `#dc2626` (red, like Square's accent), `#16a34a` (green, like Lightspeed).
2. **Phase 1**: Are you OK with adding Playwright as a dev-only dep for visual diff + a11y tests? (AGENTS.md rule #1 — new dep needs OK.)
3. **Phase 3**: Are you OK with the 7-card dashboard? Or do you want a different metric priority? (The plan is based on industry consensus per §1.4, but Saskia's specific operations may have different priorities.)
4. **Phase 4**: Are you OK with keyboard shortcuts? (Stretch goal — can skip.)
5. **Phase 5**: Are you OK with running Lighthouse CI on every PR? (Adds ~30s to CI; uses GitHub Actions minutes — we're currently budget-constrained.)

---

## 9. Rollout timeline

Assuming 1 working day = 6 productive hours:

| Phase | Days | Cumulative | Gate |
|---|---|---|---|
| Phase 0 — Tokens | 1 | Day 1 | Visual diff <5% per pixel |
| Phase 1 — Components | 3-4 | Day 5 | All 986 existing tests still pass; new component tests pass |
| Phase 2 — Icons | 1 | Day 6 | Every icon renders in light + dark |
| Phase 3 — Dashboard | 2-3 | Day 9 | All 7 cards render; SVG is valid; a11y clean |
| Phase 4 — Polish | 1-2 | Day 11 | 404/500 styled; settings grouped; mobile clean |
| Phase 5 — A11y audit | 1 | Day 12 | Lighthouse ≥95 on every page; zero axe violations |

**Total: 8-12 working days.** Each phase is its own PR. Phase 0 + 5 are mandatory. Phases 1-4 can be done in any order.

---

## 10. Success criteria

After all phases ship:

- **Lighthouse scores** ≥95 across Performance, Accessibility, Best Practices, SEO on every page
- **Axe-core** zero violations on every page
- **Keyboard navigation** works on every interactive element
- **Reduced-motion** respected site-wide
- **Theme toggle** is now actually complete (every surface re-themes correctly)
- **Dashboard** shows 7 industry-standard metric cards with SVG charts
- **Empty states** are friendly on every list page
- **404/500** are styled HTML, not raw JSON
- **Settings** are grouped, with inline help text
- **Mobile (375px)** is fully usable — no horizontal scroll, hamburger nav works
- **No new production dependencies** added
- **All 986 existing tests** continue to pass
- **All locked hotfixes** (`tests/test_hotfix_regressions.py`) continue to pass
- **Saskia (the user)** says the app "looks expensive"

---

## 11. Sources

- *19 Web Design Principles for User-Centric Sites* — UX Pilot (https://uxpilot.ai/blogs/web-design-principles)
- *Top Web Design Trends for 2026* — Figma (https://www.figma.com/resource-library/web-design-trends/)
- *Best Web Design Practices: UI/UX, Hierarchy, and More (2026)* — Hostinger (https://www.hostinger.com/tutorials/web-design-best-practices/)
- *10 Best Practices for Web Design in 2025* — OneNine (https://onenine.com/best-practices-for-web-design/)
- *7 fundamental UX design principles in 2026* — UX Design Institute (https://www.uxdesigninstitute.com/blog/ux-design-principles-2026/)
- *2025 UI and UX Best Practices* — Capicua (https://www.capicua.com/blog/ui-and-ux-best-practices)
- *Design tokens vs CSS variables vs Tailwind, explained (2026)* — Adam Arant (https://adamarant.com/en/blog/design-tokens-vs-css-variables-vs-tailwind-what-each-one-solves)
- *Design Tokens vs CSS Variables vs Tailwind Config: System Guide* — Kanopy Labs (https://kanopylabs.com/blog/design-tokens-vs-css-variables-vs-tailwind-config)
- *Building Design System with Tailwind CSS v4* — Redline Soft (https://blog.redlinesoft.net/posts/building-design-system-tailwind-v4)
- *CSS Design Token Generator (2025)* — CSS Awwwards (https://cssawwwards.com/blog/css-design-tokens-guide-2025)
- *Tailwind v4 practical guide [2026]* — Tomoda Hinata (https://tomodahinata.com/en/blog/tailwind-css-v4-css-first-design-tokens-production-guide)
- *POS UX Benchmarking 2026: Square, Toast, Lightspeed* — Creative Navy (https://creative.navy/blog/pos-software-ux-benchmarking-2026-the-coherence-gap/)
- *Toast Tab — Art Direction + Web Design* — Reigel Design (https://reigeldesign.com/work/toast-tab)
- *Market — Square (Block) Design System Breakdown* — DesignSystems.one (https://www.designsystems.one/design-systems/square-design)
- *Square DESIGN.md* — shadcn.io (https://www.shadcn.io/design/square)
- *Restaurant & POS Sales Dashboard in Metabase* (https://www.metabase.com/dashboards/restaurant-sales)
- *Restaurant365 Operations Dashboard* (https://docs.restaurant365.com/docs/operations-dashboard)
- *Forkiva Dashboard* (https://docs.forkiva.app/guide/dashboard.html)
- *Stockifi Restaurant Performance Dashboards* (https://www.stockifi.io/product-business-intelligence/performance-dashboards)
- *Building Accessible Web Applications: ARIA Patterns, Keyboard Navigation, and Automated Testing* — Let's Build Solutions (https://letsbuildsolutions.com/blog/web-engineering/building-accessible-web-applications-aria-patterns-keyboard-navigation-and-automated-testing-in-react)
- *WCAG 2.1 AA — Developer Checklist* — GIS Yaliny (https://gisyaliny.github.io/webgis/docs/General/WCAG_2_1_AA_Developer_Checklist.html)
- *Web Accessibility: ARIA and Semantic HTML* — Grizzly Peak Software (https://grizzlypeaksoftware.com/library/web-accessibility-aria-and-semantic-html-qaad5qe6)
- *Website Accessibility Checklist 2026: WCAG & ADA Compliance* — PageGuard (https://pageguard.org/guides/website-accessibility-checklist)
- *ADA Compliance for Developers 2026* — Rated With AI (https://ratedwithai.com/blog/ada-compliance-for-developers-2026)
- *Micro-Interactions: Timing, CSS, and INP* — Social Animal (https://socialanimal.dev/blog/micro-interactions-web-design/)
- *prefers-reduced-motion Architecture* — css-animation.com (https://www.css-animation.com/accessible-motion-architecture/prefers-reduced-motion-architecture/)
- *Reduced-Motion Fallback Patterns for Keyframes* — css-animation.com (https://www.css-animation.com/accessible-motion-architecture/prefers-reduced-motion-architecture/reduced-motion-fallback-patterns-for-keyframes/)
- *Reduced Motion, Not Reduced Quality* — Monotonomo (https://www.monotonomo.com/journal/prefers-reduced-motion-premium-patterns/)
- *prefers-reduced-motion, explained (and how to test it)* — MotionSpec (https://motionspec.dev/blog/prefers-reduced-motion)
- *ApexCharts.js GitHub* (https://github.com/apexcharts/apexcharts.js) — evaluated but not adopted (we hand-roll SVG)
- *Inline SVG vs Icon Fonts [CAGEMATCH]* — CSS-Tricks (https://css-tricks.com/icon-fonts-vs-svg/)
- *SVG Sprites and Icon Systems Are Super* — Lincoln Loop (https://lincolnloop.com/blog/svg-sprites-and-icon-systems-are-super/)
- *Getting started with inline SVG icons* — Tom Hazledine (https://tomhazledine.com/inline-svg-icons/)

---

## 12. What to ask the operator before starting

1. Confirm Phase 0 brand color (`#f97316`) or pick alternative
2. Confirm Playwright is OK as a dev-only dep
3. Confirm the 7-card dashboard scope
4. Confirm keyboard shortcuts (Phase 4 stretch)
5. Confirm Lighthouse CI is OK given the Actions budget constraint
6. Confirm operator is OK with 8-12 days of work shipped in 6 PRs

Once confirmed, I'll create the 6 SASKIA-NNN tickets (one per phase) and start with Phase 0.
