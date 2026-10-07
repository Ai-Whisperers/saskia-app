# SASKIA-203: Format utility JS (money / date / live-time / cache)

**Date:** 2026-10-07
**Epic / Story:** E26.S22 (Phase 22 — frontend polish)
**Owner:** Iván
**Estimate:** 30 min
**Status:** shipped

## What

Four small utility scripts that expose `window.*` globals, for use
across server-rendered templates. All are pure JS, no CSS, no DOM
mutations at load time.

- `MoneyFormat` — Guaraní formatting (`Gs. 729.167` style)
- `DateFormat` — DD/MM/YYYY + relative + smart formats
- `LiveTime` — auto-updates `[data-relative-time]` every 60s
- `Cache` — TTL key/value cache for client-side memoization

## Why

Operators and templates need consistent currency / date display, and
the existing inline JS in each template was drifting. These utilities
centralize the formatting. Phase 22 work from the phase-3-m1 branch
that was sitting orphan.

## Tasks

- [x] Extract 4 JS files from `feat/phase-3-m1-product-detail`
- [x] Add 4 `<script>` tags to `app/templates/base.html`
- [x] Add 4 test files (88 tests total)
- [x] Update `app/CHANGELOG.md`

## Acceptance

- [x] 88 tests pass (24 + 24 + 25 + 15)
- [x] All 17 back-to-top tests still pass
- [x] No new dependencies
- [x] No CSS changes

## Source

Branch: `feat/phase-3-m1-product-detail`
Part of: phase-3-m1 wave 1 (alongside SASKIA-202 back-to-top).
