# SASKIA-312: wave 2b — state-preservation + sortable-table + search-highlight

**Date:** 2026-10-08
**Owner:** Hermes (autonomous)
**Estimate:** 2-3h
**Status:** done (closed 2026-10-09 — work landed in prior sessions)

## What

Port 3 orphan UI modules from the phase-3-m1 batch (source commits locally reachable):
state-preservation.js (5b2b3c9c), sortable-table.js/.css (28cdd2b8), search-highlight.js/.css
(9fab2fd4) + their tests, wired into base.html with ?v={{ asset_version() }}.

## Why

Phase-3-m1 orphan shipping plan (see MASTER-PLAN-2026-10-08). These modules exist, are
tested, and never landed on main.

## Acceptance

- [x] All 3 modules + CSS in app/static/, wired in base.html
  - state-preservation.js (no CSS — pure JS module), sortable-table.{js,css}, search-highlight.{js,css}
  - All 3 referenced in app/templates/base.html
- [x] test_cross_page_state, test_cross_page_state_implementation, test_sortable_tables,
  test_search_highlight — 161 passed (combined with wave 2c tests)
- [x] ruff clean; CHANGELOG updated

## Closing note (2026-10-09)

All 3 modules from wave 2b are present in `app/static/`, wired into `app/templates/base.html`,
and the 4 acceptance tests pass. state-preservation has no CSS file by design (the JS module
uses inline styles / existing app-shell classes). Ticket closed.
