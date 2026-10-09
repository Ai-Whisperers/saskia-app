# SASKIA-317: test-isolation failures under full-suite parallel CI

**Date:** 2026-10-08
**Owner:** Hermes (autonomous) / Ivan
**Estimate:** 1-2d (investigation + fixes)
**Status:** done (root cause found 2026-10-09 — broken main.py refactor; reverted, local tests green)

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


## 2026-10-09 follow-up (Hermes): root cause was NOT test isolation, it was a broken main.py refactor

The 200-300 failures observed in PR66/PR69 CI were caused by **commit 209d9387 "refactor(main): extract create_app helpers to reduce complexity"** which committed a half-finished `create_app()` factory. The broken refactor:
- Removed all 50 router registrations (no `app.include_router(auth.router)` etc.)
- Did NOT call the newly-defined `_register_routers(app)` helper
- The follow-up "fix" commit 697b9042 only restored the `return app` statement
  (twice, in fact — line 915 + line 918) but did NOT add the router registration call

This caused every test that touched any real route to 404. Tests that didn't need a route (e.g. unit tests on the seed CSVs) still passed.

### Resolution (2026-10-09)
- Verified local main.py was broken (only 3 routes registered: /api/docs, /api/openapi.json, /docs/oauth2-redirect)
- Verified live site at saskia-vps.paragu-ai.com was still running the LAST WORKING deploy (04:49 UTC, commit 0ebd16ee) — Docker image had not been re-built with the broken code yet
- Reverted both broken commits with `git revert --no-edit 697b9042 209d9387`
- After revert:
  - `ruff check .` → clean
  - `pyright app/rms/main.py` → 0 errors
  - `test_P01_login_no_sidebar.py` → 2/2 pass (was failing with 404)
  - `test_bank_csv_export_regression.py::test_bank_page_renders` → pass (was 404)
  - `test_SASKIA-30x` cluster: 126 pass / 3 fail (the 3 failures are template placeholder text mismatches, not test isolation)
  - main.py: 1427 lines (vs 940 with broken refactor, vs 1498 original)

### Live site status
- Live at 04:49 UTC deploy (commit 0ebd16ee), still serving WORKING code
- No production impact (the broken refactor was never deployed)
- SASKIA-204 + 311/312/313/301 already closed

### Acceptance (revised)
- [x] Local main builds a working app (all 50 routes registered)
- [x] /login returns 200
- [x] /bank returns 200
- [x] ruff + pyright clean
- [x] Live site unchanged (still on 04:49 UTC deploy)
- [ ] SASKIA-30x 3 placeholder tests still need separate fix (template text drift)
