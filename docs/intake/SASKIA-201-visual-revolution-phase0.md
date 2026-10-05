<!-- ROADMAP-REDIRECT -->
# ⚠️ Moved / Superseded

**This file has been moved or superseded.** The canonical location is:

> **`docs/roadmap/historical-plans/intake/SASKIA-201-visual-revolution-phase0.md`**

Intake ticket (archived).

See [`docs/roadmap/README.md`](docs/roadmap/README.md) for the full index.

---

<!-- ORIGINAL CONTENT BELOW -->

# SASKIA-201: Visual Revolution Phase 0 — Token foundation + icons + error pages

**Date:** 2026-09-17
**Epic / Story:** E26.S1 (new epic for Visual Revolution)
**Owner:** Iván
**Estimate:** 1 day (actual: ~4 hours of focused work)
**Status:** shipped

## What

Phase 0 of the Visual Revolution plan (see
`docs/plans/2026-09-17-saskia-visual-revolution-plan.md`).

- Replaced flat 17-color CSS variable scheme with a full
  primitive → semantic → component token model (50+ tokens)
- Refreshed brand color from brown `#b45309` to vibrant orange `#f97316`
- Added 28 hand-authored SVG icons in a single sprite (`_components/icons.svg`)
- Styled 404/500 error pages with friendly Paraguayan-Spanish copy
- Mobile hamburger nav (CSS-only, no JS)
- `@media print` styles for paper-friendly reports
- `prefers-reduced-motion` global reset
- `forced-colors` (high-contrast mode) token map
- All 15 nav links now have icons

## Why

Saskia RMS was visually dated (text-only nav, brown primary color, no data
visualization, JSON error pages). The Fase1 backend is rock solid (1015 tests
passing) — the visual layer is what stood between Fase1 and a premium product
that Saskia (and future clients) would be proud to use.

## Tasks

- [x] Refactor `app/static/app.css` to primitive → semantic → component
      token model
- [x] Add `.btn`, `.card`, `.badge`, `.table`, `.alert`, `.modal`,
      `.metric-card`, `.spinner`, `.skeleton`, `.empty-state` component
      classes
- [x] Complete dark mode (every semantic token overridden under
      `[data-theme="dark"]`)
- [x] Hand-author 28 SVG icons in `_components/icons.svg`
- [x] Wire icons into `base.html` nav + `macros.html::nav_link`
- [x] Add styled `errors/404.html` and `errors/500.html`
- [x] Update `main.py` exception handlers to detect Accept header and
      serve HTML to browsers / JSON to API clients
- [x] Add mobile hamburger nav (CSS-only checkbox pattern)
- [x] Add `@media print` styles
- [x] Add `prefers-reduced-motion` global reset
- [x] Add `forced-colors` (high-contrast) token map
- [x] Write `tests/test_visual_revolution.py` (26 new tests)
- [x] Update `tests/test_a11y_navigation.py` regex tests for new markup
- [x] Update `tests/test_static_assets.py` size limit
- [x] Update `app/CHANGELOG.md`
- [x] Run full test suite — all 1015 pass

## Acceptance

- [x] All 992 pre-existing tests still pass
- [x] 23 new tests added (`test_visual_revolution.py` 26, minus 3 modified
      a11y tests counted separately)
- [x] `ruff check .` clean
- [x] `scripts/minify_css.py` produces a valid minified output (~22KB)
- [x] No new production dependencies added
- [x] No breaking changes to API clients (Accept: application/json still
      gets JSON)
- [x] Backwards-compatible — old `--bg`, `--primary` token aliases
      preserved so existing templates work unchanged
- [x] CSP-safe (no inline JS, no inline styles except the theme localStorage
      bootstrap which was already there)
- [x] All locked hotfix tests (`test_hotfix_regressions.py`) still pass
- [x] Paraguayan Spanish vos form throughout (Guardá, Anulá, etc.)
- [x] Every icon button has `aria-label`
- [x] Every page has the SVG sprite included
- [x] 404/500 raw exception text NEVER leaks to browser

## Follow-up (next phase)

- **E26.S2 (Phase 1 — Component migration)** — Migrate existing templates to
  use the new `.card`, `.table`, `.btn` classes. Update `/ventas`, `/`,
  `/inventario`, etc. to use the new component vocabulary. Add a real
  modal to confirm destructive actions (void sale, delete customer).
- **E26.S3 (Phase 2 — Dashboard)** — Replace the text-only `/` dashboard
  with 7 industry-standard metric cards + hand-rolled server-side SVG charts.
- **E26.S4 (Phase 3 — Polish)** — Settings page grouping, mobile audit,
  confirmation dialogs, accessibility audit + Lighthouse CI.

See `docs/plans/2026-09-17-saskia-visual-revolution-plan.md` for the
complete 5-phase plan.
