# SASKIA-311: Restore main CI green — merma.py format + hardcoded-date sweep

**Date:** 2026-10-08
**Owner:** Hermes (autonomous)
**Estimate:** 2h
**Status:** in_progress

## What

Main CI is red on `Lint (ruff)` + `test` for two independent causes:
1. `app/routers/merma.py` landed unformatted via 6568f6b3 (night triage).
2. `tests/test_no_hardcoded_dates.py` fails 59× across ~60 test files — siblings put
   date literals in comments/docstrings (e.g. `test_P35_sidebar_visibility_breakpoint.py:89`).

## Why

Every open PR inherits red CI from main's state; the date-lint guard (anti test-rot,
Pitfall #8) is being drowned out by provenance comments. Restore the guard's signal.

## Tasks

- [x] Verified 59 failures reproduce on clean origin/main checkout
- [x] Sized: ~60 files; split Tier-1 (comment prose) vs Tier-2 (load-bearing fixtures → allow-marker)
- [ ] Format merma.py
- [ ] Sweep date literals
- [ ] test_no_hardcoded_dates 0 failed locally
- [ ] PR merged, main CI green (except smoke/ZAP baseline)

## Acceptance

- `ruff format --check .` clean
- `tests/test_no_hardcoded_dates.py` 0 failed
- `ruff check .` 0
