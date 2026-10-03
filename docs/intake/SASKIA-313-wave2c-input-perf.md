# SASKIA-313: wave 2c — stepper + lazy-load + perf-monitor + clipboard

**Date:** 2026-10-08
**Owner:** Hermes (autonomous)
**Estimate:** 2h
**Status:** in_progress

## What

Port 4 orphan JS modules from phase-3-m1 (source commits locally reachable):
- stepper.js + stepper.css (4987add0) — number input min/max steppers
- lazy-load.js (59565ed8) — IntersectionObserver image lazy-load + fallback
- perf-monitor.js (4eb6b721) — lightweight perf timing overlay
- clipboard.js (b6b4b557) — data-copy / data-copy-from buttons

## Why

Phase-3-m1 orphan shipping plan; wave 2c of MASTER-PLAN-2026-10-08.

## Acceptance

- 4 modules (+css) in app/static/, wired in base.html with ?v=
- test_stepper, test_lazy_load, test_image_lazy_loading, test_perf_monitor, test_clipboard green
- ruff clean; CHANGELOG updated
