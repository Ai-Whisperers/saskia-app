# SASKIA-314: wave 2d — print-area + form-validator + saskia-tooltip (+ touch-targets)

**Date:** 2026-10-08
**Owner:** Hermes (autonomous)
**Status:** shipped

## What

Port the last 3 orphan modules (final wave) from phase-3-m1, recovered from tree 59565ed8
(source branches deleted; objects reachable locally):
- print-area.js + print.css (media="print") — print scoping for list/detail pages
- form-validator.js + form-validator.css — client-side validation hooks
- saskia-tooltip.js + .css — accessible tooltips (rebrand of ui-tooltip)
- touch-targets.css — ≥44px touch targets (same orphan batch; test Touch suite requires it)

All wired in base.html with ?v={{ asset_version() }}.

## Tests

102 passed (test_form_validator, test_print_area, test_print_stylesheet, test_touch_and_tooltip).
