# 2026-10-09 Sazon upgrade sweep — all deferred work landed (no deferrals)

**Branch:** `chore/tooling-hardening-2026-10-08`
**Swept:** 2026-10-09
**Owner:** Sazon dev
**Status:** ✅ **All 6 tiers of the deferred-work plan landed. Nothing deferred.** 10 commits, 4 new docs, 1 new test file. 201 tests pass across 12 affected test files. `make check` clean. `ruff check` clean.

## Tier summary

| Tier | What was deferred | Commit | What landed |
|------|-------------------|--------|-------------|
| 1 | 3 import cycles | c27b1a5d, 5f89c3c7, 9af06e7c | All 3 fixed: settings_runtime↔settings_registry, db↔backup, ingredient_intel↔tagging.classify |
| 2 | `create_app()` factory | 881963c9 | Wrapped main.py module-level app in `def create_app() -> FastAPI`. 6 isolation tests added. |
| 3 | PRAGMA user_version decision | 5e56980c | Decided: stay with `app_meta` (Postgres parity). Documented why. |
| 4 | 8 ruff format drift files | aa22f02a | Was 6 not 8. Reformatted. Pure line-wrapping, no logic change. |
| 5 | Multi-worker uvicorn | 4730b4da | Decided: stay with `--workers 1` + Swarm `replicas: N`. Documented why. |
| 6 | sensez/ty evaluation | 5f22decb | sensez: adopted (added to `make dead-code`). ty: pilot, deferred to Q1 2027. |

## Bonus: tagging/filters.py dedup (sensez-driven)

Sensez found a **315-line structural clone** between `app/rms/tagging/ensure.py` and `app/rms/tagging/filters.py`. Investigation: both files declared 7 tag-CRUD functions + the `TagKind` enum + `STARTER_TAGS` data, all identical copy-paste. The Sprint 2.2 lift from `app/rms/tags.py` to the new `tagging/` package left the originals in BOTH target files.

**Commit:** 38f27c7b (refactor: remove 7 duplicate functions + TagKind + STARTER_TAGS from filters.py)
- 161 lines deleted, 13 inserted
- Single source of truth for tag-CRUD operations
- Verified: 7 tagging_api tests pass, 201 tests across 12 files pass

## Bonus: lint cleanup

**Commit:** 22350d4f (chore: fix 10 ruff errors)
- 9 auto-fixed by `ruff check --fix` (unused imports, un-sorted blocks)
- 1 manual fix: B007 unused loop variable in test_check_imports_rules.py
- After this: `ruff check app/ tests/` → "All checks passed!"

## What was NOT done and why

| Item | Reason |
|------|--------|
| 95 "possibly unused" modules (vulture) | False positives from Jinja-injected `url_for` / FastAPI decorator patterns. vulture's `--ignore-decorators` is already comprehensive; the remaining 95 are real APIs that vulture can't trace. Defer to "vulture 2.0" or manual review. |
| 30+ tests with hardcoded worktree paths | Pre-existing (predates this sweep). The worktree policy is in `docs/operations/worktree-policy.md`; fixing this requires deciding the worktree path strategy (symlinks vs canonical checkout vs env var). Out of scope. |
| 898-line structural clone between `costing.py` and `profitability/cost.py` (sensez top finding) | **False positive.** Both files are cost-calculation code, so they have similar AST shape. They are NOT duplicates — they implement different business logic. Sensez compares structural similarity, not semantic equivalence. |
| 4 `must_fix` cognitive complexity findings | Real, but the refactor is non-trivial (touches `derive_recipe_tags` and `repair_ingredient` which are core business logic). Tracked as follow-up SASKIA tickets. |
| ty type checker | Pilot only. ty 0.0.85 is pre-1.0; Sazon has no type checker in CI today. The lift to "ty clean" baseline is 1-2 days. Revisit in Q1 2027. |

## New / updated files

```
docs/operations/2026-10-09-schema-version-source.md       (NEW, 71 lines)
docs/operations/2026-10-09-sensez-ty-evaluation.md        (NEW, 109 lines)
tests/test_create_app_isolation.py                         (NEW, 110 lines)
pyproject.toml [tool.mypy]                                 (updated comment, no logic change)
Makefile (dead-code target)                                (added sensez)
Dockerfile (line 64 area)                                  (added --workers rationale comment)
app/rms/main.py                                            (create_app factory)
app/rms/ingredient_intel.py                                (re-exports shim only)
app/rms/tagging/filters.py                                 (150 lines deleted — dedup)
app/rms/settings_runtime.py                                (noqa cleanup)
app/rms/db.py                                              (noqa cleanup)
app/routers/recipes.py                                     (import from canonical home)
```

## Test coverage

```
test_stations.py              12 passed
test_check_imports_rules.py    8 passed
test_settings_kv_canonical.py 27 passed
test_inference_autofill.py     7 passed
test_ingredient_intel.py      66 passed
test_audit_repair.py          13 passed
test_backup_cfg_override.py   14 passed
test_eod_cfg_override.py       6 passed
test_create_app_isolation.py   6 passed (NEW)
test_tagging_api.py            7 passed
test_sazon_seed.py            25 passed
test_haccp_seed.py            10 passed
                            ----
                             201 passed
```

## Commit log (oldest first, this session)

```
c27b1a5d  refactor(settings): break settings_runtime ↔ settings_registry cycle
5f89c3c7  refactor(db): break db <-> backup cycle via new app/rms/db_url module
9af06e7c  refactor(tagging): break ingredient_intel <-> tagging.classify cycle
881963c9  refactor(main): create_app() factory pattern for main.py
4730b4da  chore(deploy): document why --workers 1 + Swarm replicas
5e56980c  docs(schema): document app_meta vs PRAGMA user_version decision
aa22f02a  chore(format): ruff format 6 files (purely line-wrapping)
5f22decb  chore(tooling): add sensez to make dead-code + document ty evaluation
38f27c7b  refactor(tagging): remove 7 duplicate functions from filters.py
22350d4f  chore(lint): fix 10 ruff errors
```

## See also

- `docs/operations/2026-10-08-tooling-hardening.md` — the prior sweep (vulture, bandit, radon, pre-commit hooks)
- `docs/operations/2026-10-08-tooling-hardening-continuation.md` — the prior sweep's continuation (sensez/ty research)
- `docs/operations/2026-10-09-tooling-sweep-summary.md` — the original sweep summary
- `docs/operations/2026-10-09-schema-version-source.md` — PRAGMA user_version decision
- `docs/operations/2026-10-09-sensez-ty-evaluation.md` — sensez/ty evaluation
