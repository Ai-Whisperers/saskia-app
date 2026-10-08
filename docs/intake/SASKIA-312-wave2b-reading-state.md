# SASKIA-312: wave 2b — state-preservation + sortable-table + search-highlight

**Date:** 2026-10-08
**Owner:** Hermes (autonomous)
**Estimate:** 2-3h
**Status:** in_progress

## What

Port 3 orphan UI modules from the phase-3-m1 batch (source commits locally reachable):
state-preservation.js (5b2b3c9c), sortable-table.js/.css (28cdd2b8), search-highlight.js/.css
(9fab2fd4) + their tests, wired into base.html with ?v={{ asset_version() }}.

## Why

Phase-3-m1 orphan shipping plan (see MASTER-PLAN-2026-10-08). These modules exist, are
tested, and never landed on main.

## Acceptance

- All 3 modules + CSS in app/static/, wired in base.html
- test_cross_page_state, test_cross_page_state_implementation, test_sortable_tables,
  test_search_highlight (+ test_sprint_week1) green
- ruff clean; CHANGELOG updated
