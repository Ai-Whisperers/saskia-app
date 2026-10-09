# SASKIA-202: Back-to-top floating button (Phase 22 polish)

**Date:** 2026-10-07
**Epic / Story:** E26.S22 (Phase 22 — frontend polish)
**Owner:** Iván
**Estimate:** 1h
**Status:** shipped

## What

Floating "Volver arriba" button that appears in the bottom-right corner
of every page once the user scrolls more than 400px. Click smoothly
scrolls to top; respects `prefers-reduced-motion` (instant scroll).
Keyboard-accessible via `aria-label` and `:focus-visible` outline.

## Why

Long pages (insight dashboards, bank, cotizador) require the operator
to scroll all the way back to the top to reach the nav. This is a
quality-of-life polish from the phase-3-m1 branch that's been sitting
orphan since the Sazón rebrand.

## Tasks

- [x] Extract `app/static/back-to-top.js` from `feat/phase-3-m1-product-detail`
- [x] Add `.back-to-top` + `.back-to-top.is-visible` CSS rules to `app/static/combobox.css`
- [x] Add `<button class="back-to-top">` + `<script>` tag to `app/templates/base.html`
- [x] Add `tests/test_back_to_top.py` (17 tests, locked)
- [x] Update `app/CHANGELOG.md`

## Acceptance

- [x] All 17 back-to-top tests pass
- [x] Existing tests still pass (no regressions in main suite)
- [x] No new dependencies
- [x] Button invisible until scroll > 400px (per spec, not "only on long pages" —
      the JS handles visibility; the button is always in DOM)

## Source

Branch: `feat/phase-3-m1-product-detail`
Worktree: `saskia-app-phase3m1-wave1` (one-off, removed after merge)
