# SASKIA-317: test-isolation failures under full-suite parallel CI

**Date:** 2026-10-08
**Owner:** Hermes (autonomous) / Ivan
**Estimate:** 1-2d (investigation + fixes)
**Status:** open

## What

Full-suite pytest runs in CI (`-n 2`, entire tests/ tree) fail ~200-300 tests that all pass
when their files run individually (even with `-n 2`). Observed clusters:
- SASKIA-30x suites (loan_words, 303/304/305/306/307/308): ~90 failures
- test_ci_anti_rules (13), test_P43_channel_enum_central (8), test_P23_analisis_empty_state,
  test_produccion_* (mobile/empty/bulk), test_mobile_ux — spread of ~120 more.

Runs observed: PR66 CI run 37718329122 (300 FAILED then cancelled), PR69 CI run
37727599544 (214 FAILED then cancelled at 84%). Both verified: same commits pass locally
per-file, and pass with `-n 2` on a clean checkout when run as a subset.

## Why

Test-order/state pollution: a session-scoped fixture (likely the shared sqlite DB in
conftest or a settings/env mutation without teardown) leaks across files in full-suite runs.
Every CI run of every PR is currently red from this, drowning real signal.

## Suspects (in order)
1. `tests/conftest.py` session fixtures: shared sqlite path reused across workers
2. `SettingsKV`/`settings_registry` module-level caches mutated by mig114 tests
3. `Channel` enum vs ORM model shadowing games in seed code (fixed for seed_sazon in #66,
   but test-order may still flip them)
4. loguru `request_id` binder KeyError noise (seen in logs) failing unrelated asserts

## Suggested approach
- Bisect with `pytest --lx` / `-p no:randomly`, run the SASKIA-30x cluster after suspected
  polluter files (test_settings_audit, mig114) in the same process.
- Add `-p xdist` group scheduling (pytest-xdist `--dist loadscope` by directory) as a stopgap.

## Acceptance

- One fully-green CI run (full suite, -n 2) on main.
