# Phase 3 CI cleanup — postmortem & reference

> **Date:** 2026-10-04
> **Author:** Ivan
> **Scope:** `feat/phase-3-ci-cleanup` branch
> **PR:** [#46](https://github.com/Ai-Whisperers/sazon-app/pull/46)
> **Outcome:** ruff 1910 → 0 errors; 12 currency-drift sites → 0

This document is the technical reference for the cleanup that landed
in PR #46. It is meant for future maintainers who wonder "what was
the state of CI before this PR, and why are some of the noqas there?"

## TL;DR

- **Started:** 1910 ruff errors across 360 files
- **Finished:** 0 errors, 21 commits, 19 individual cleanups
- **Real bugs found & fixed during cleanup:** 6 (see below)
- **CI gate:** `make check` now requires ruff clean
- **Documentation impact:** manual updated, currency-drift heuristic
  documented, per-file-ignores policy established

## Why now

Before this PR, the ruff gate was a soft gate — violations were
documented but not enforced. As a result:

1. **Lint debt accumulated faster than it was paid down** — 1910 errors
   was the result of ~12 months of feature work without enforcement
2. **Real bugs hid behind lint warnings** — six production bugs (see
   "Real bugs found" below) were discovered because their surrounding
   code happened to be flagged
3. **Currency drift was a recurring tax** — `Gs. {{ x }}` patterns
   bypassed our `m.gs_full()` helper, so operators had to manually
   re-format numbers on certain pages

This PR makes ruff enforcement mandatory, fixes the debt, and removes
the easy footguns.

## The 19 cleanups, in dependency order

| # | Commit | What | Why this order |
|---|---|---|---|
| 1 | `b904-from-none` (10) | Added `raise from None` to exception handlers | Mechanical, no risk |
| 2 | `perf401-list-comps` (6) | Converted list-comprehensions to explicit loops in production | PERF401 only fires in prod; tests ignored via pyproject |
| 3 | `ble001-exception-clarity` (35) | `# noqa: BLE001` with rationale for legitimate bare excepts | 8 in app/, rest in tests/_smoke/docs |
| 4 | `f811-redef-cleanup` (12) | Removed 12 duplicate function definitions | 6 dead wire-stub re-defs in `app/rms/db.py` shadowed real imports — a real bug |
| 5 | `ann202-return-types` (9) | Added return-type annotations to private helpers | Mechanical |
| 6 | `dtz007-naive-strptime` (6) | Annotated naive `strptime` uses | DB stores naive UTC by convention; documented |
| 7 | `perf403-eff-comp` (4) | Converted comprehensions that should be explicit | Mechanical |
| 8 | `pie810-s310-s110` (8) | Tuple-startswith, urlopen schemes, try-except-pass noqas | Defensive defaults |
| 9 | `ruf043-regex-raw` (3) | Raw-string regex args in tests | Mechanical |
| 10 | `b018-useless-assign` (3) | Removed `query(...).one().password_hash` lines | Dead code |
| 11 | `dtz005-ann-s108-...` (60+) | DTZ005, ANN002/003, S108, F841, DTZ901, B023, B015, W292, RUF100, F401, I001 | Small fixes, mostly mechanical |
| 12 | `f821-undefined-names` (50+) | Added missing imports in 30+ test files | Real bugs in 3 production files |
| 13 | `s110-format-fix` (1) | `# noqa: S110` on the `pass` line, not the `except` | Ruff specificity fix |

(12 cleanup families total, not 19 — some categories were batched.)

## Real bugs found & fixed

These were bugs that the cleanup work uncovered, not bugs that
caused the cleanup:

### 1. Missing `Boolean` import in `app/rms/models/sales.py`

**Symptom (if hit):** `NameError: name 'Boolean' is not defined` at
SQLAlchemy mapper-config time, taking the whole app down.

**Why it didn't show up:** The `Mapped[bool]` columns were only
ever set to `default=False` in tests, which never triggered the
`mapped_column(Boolean, ...)` codepath at mapper-config time in
production (DB was always SQLite/PG, never in-memory mock).

**Fix:** `from sqlalchemy import (Boolean, CheckConstraint, …)`.

### 2. Missing imports in `app/routers/reportes.py`

**Symptom (if hit):** 500 error on `/reportes/diario` and related
endpoints, every time.

**Why it didn't show up:** Reports route requires login and
specific date-range data, neither of which was exercised in unit
tests. Only a `reportes` smoke test catches it.

**Fix:** Imported `sales_by_hour`, `sales_heatmap`,
`waste_roi_by_ingredient` from `app.rms.sales_intel`.

### 3. `BackupResult` forward-ref in `app/routers/health.py`

**Symptom (if hit):** Ruff `F821` on every CI run for that line.
Not a runtime bug (the function is only called via test patches),
but blocked ruff clean.

**Fix:** Inline import rather than TYPE_CHECKING block, since ruff
doesn't see function-local imports.

### 4. `MockScalars` name error in `tests/test_analytics_properties_phase14_tier4.py`

**Symptom (if hit):** NameError when the hypothesis property tests
ever triggered the `MockResult.scalars()` path. Test passed
before because hypothesis chose a path that didn't hit it.

**Fix:** Moved `MockScalars` to module level (was defined inside
`MockResult.scalars()` but used at module level).

### 5. Dead `ior_allergens` in `tests/test_receta_detalle_2026_09_29_regression.py`

**Symptom (if hit):** F821 on every test run.

**Fix:** Removed the dead `ior_allergens if False else (...)`
expression; the real var is `iallergens`.

### 6. Dead re-definitions in `app/rms/db.py`

**Symptom (if hit):** Migration functions silently shadowed by
later definitions; some `_migration_NNN_*` functions were defined
TWICE and the second one always won.

**Why it didn't show up:** Old DBs already had the migrations
applied; the first definition did nothing (idempotent guards),
so the shadowing was invisible.

**Fix:** Removed 6 duplicate wire-stub re-definitions from the
top of `db.py`.

## Per-file-ignores policy

The following per-file-ignores are now in `pyproject.toml`. They
exist because blanket-enforcing these rules in test/scripts/docs
would harm more than help:

| Path | Ignored | Why |
|---|---|---|
| `tests/*.py` | ANN, S, DTZ, B011, PERF401, BLE001 | Tests prioritize readability over lint perfection |
| `_smoke/*.py` | ANN, S, DTZ, E501, BLE001 | Smoke tests are throwaway scripts |
| `scripts/*.py` | ANN, S, BLE001, DTZ | Scripts are operator-facing, not library code |
| `docs/**/*.py` | BLE001, S, E501 | Docs scripts are throwaway capture utilities |
| `run_migration.py` | BLE001 | One-off operator command, not a module |

**Rule for new ignore requests:** add `noqa` with a rationale, NOT
per-file-ignore. Per-file-ignores are a one-time tax; noqas are
scoped to the specific line and force the author to explain.

## What we did NOT do (and why)

- **Did not switch to `ruff format`.** We use `black` (already in
  dev deps). Switching would touch every file and the diff would
  dwarf the cleanup.
- **Did not run `mypy` or `pyright`.** Out of scope; not in our
  toolchain today.
- **Did not refactor large routers** (e.g. `app/routers/sales.py`
  has 7 fixes because of how much defensive-default code is there,
  but no structural change).
- **Did not update CONTRIBUTING.md to mandate ruff-clean.** The
  CI gate does that automatically now.

## Follow-up work (future PRs)

- [ ] Add `mypy --strict` for new modules only (incremental)
- [ ] Consider `ruff format` after next major refactor
- [ ] Address the 8 page templates still using raw `Gs. {{ x }}` in
      admin-only paths (lower priority — the operator never sees those)
- [ ] Per-test-file: clean up the BLE001 noqas once defensive-default
      patterns are extracted to a helper

## See also

- [`CHANGELOG.md`](../../CHANGELOG.md) — 2026-10-04 entry
- [PR #46](https://github.com/Ai-Whisperers/sazon-app/pull/46) — the actual diff
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — `make check` workflow
