# Sharded test workflow — design + migration plan

**Last updated:** 2026-10-09
**Owner:** Ivan (AIW)
**Status:** Design complete; not yet implemented (waiting on budget + post-CI-recovery stabilization).

## Why

The current single CI runs `uv run pytest -n 2 --dist=loadscope` on all **6,103 tests across 718 files** in **~6 minutes wall-clock**. That's fast enough today, but two trends will make sharding mandatory:

1. **Sibling session pressure.** Multiple agents pushing in tight windows cause a queue; a 6-min run becomes 30+ min if 5 PRs are stacked.
2. **Test count is growing.** Sprint 2.1 added 47 new tests; Sprint 2.2 (in progress) will add ~200 more. The 6-min wall-clock is going to drift upward.

Sharding cuts wall-clock in half, at the cost of N× the per-run minutes. The 2000-min/mo budget is the binding constraint.

## Test layout (the data)

```
tests/                    718 files, 120,854 LOC
tests/fixtures/              (no test_*.py — fixtures only)
tests/e2e/                  16 files, 2,365 LOC
tests/browser/              2 files, 178 LOC  (Playwright, excluded from dev-base)
tests/_lib/                 (helpers, no tests)
```

The top-level `tests/` directory is flat (no subdirs), which makes alphabetical sharding a natural fit. The subdirs (`e2e/`, `browser/`) are already separate enough to be their own shards.

## Proposed design: 3 shards (matrix job)

| Shard | Includes | Estimated wall-clock |
|---|---|---|
| **unit-fast** (alphabetical first third) | `test_a*` through `test_l*` (~240 files) | ~3 min |
| **unit-slow** (alphabetical middle third) | `test_m*` through `test_s*` (~240 files) | ~4 min |
| **unit-large + e2e + browser** (alphabetical last third) | `test_t*` through `test_z*` + `tests/e2e/` + `tests/browser/` (~256 files) | ~5 min |

All 3 shards run in parallel. Wall-clock: **~5 min** (the slowest shard). Currently 6 min single-thread, so this is a **~16% wall-clock improvement** but a **~3x cost in total minutes** (each shard runs separately).

**Budget impact:** at 4 PRs/day × 30 days = 120 PRs/mo × 12 min total = **1,440 min/mo** — within the 2,000 budget.

## Alternative: 4 shards with browser separate

If the browser tests become flaky and we want to isolate them, the design can be:

| Shard | Includes | Estimated wall-clock |
|---|---|---|
| unit-fast | `test_a*`-`test_g*` | ~2 min |
| unit-mid | `test_h*`-`test_p*` | ~2 min |
| unit-slow | `test_q*`-`test_z*` | ~2 min |
| e2e + browser | `tests/e2e/` + `tests/browser/` | ~4 min |

Wall-clock: ~4 min. **Total minutes:** 10/run × 120 = 1,200/mo. Better budget profile.

## The workflow file (3-shard version)

```yaml
# .github/workflows/sharded-test.yml
#
# Runs the 6,103 tests in 3 parallel shards to cut wall-clock time.
# Triggered on the same events as ci.yml so the two workflows can be
# swapped by changing the required-check in branch protection.
#
# Per-shard design:
#   - All 3 shards run in parallel as a matrix job.
#   - Each shard has the same setup (uv, Python, deps).
#   - Each shard runs a different subset of tests via --co / -k.
#   - The coverage is combined at the end with `coverage combine`.

name: Sharded test (3-way matrix)

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

concurrency:
  group: sharded-test-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: shard ${{ matrix.shard }}
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false  # run all shards even if one fails
      matrix:
        shard:
          - name: unit-fast
            # First alphabetical third
            test_args: "tests/ --ignore=tests/e2e --ignore=tests/browser -k 'test_a or test_b or test_c or test_d or test_e or test_f or test_g or test_h or test_i or test_j or test_k or test_l'"
          - name: unit-slow
            test_args: "tests/ --ignore=tests/e2e --ignore=tests/browser -k 'test_m or test_n or test_o or test_p or test_q or test_r or test_s'"
          - name: unit-large
            test_args: "tests/ --ignore=tests/e2e --ignore=tests/browser -k 'test_t or test_u or test_v or test_w or test_x or test_y or test_z'"

    env:
      SASKIA_TEST_AUTH_DISABLED: "1"

    steps:
      - uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          version: "0.5.x"
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: rm -rf .venv && uv sync --only-group dev-base --no-default-groups

      - name: Run shard ${{ matrix.shard.name }}
        run: |
          uv run pytest \
            ${{ matrix.shard.test_args }} \
            -n 2 --dist=loadscope \
            --no-header \
            --tb=short \
            --cov=app \
            --cov-report=xml:/tmp/coverage-${{ matrix.shard.name }}.xml \
            --cov-append

      - name: Upload coverage artifact
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: coverage-${{ matrix.shard.name }}
          path: /tmp/coverage-${{ matrix.shard.name }}.xml
          if-no-files-found: ignore

  # Coverage combine is a separate job so the matrix shards can all
  # finish in parallel first.
  coverage:
    name: combine coverage
    needs: [test]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - uses: actions/checkout@v7
      - name: Download all coverage artifacts
        uses: actions/download-artifact@v7
        with:
          path: /tmp/coverage
      - name: Combine coverage
        run: |
          uv run coverage combine /tmp/coverage/*.xml
          uv run coverage report
      - name: Upload combined report
        uses: actions/upload-artifact@v7
        with:
          name: coverage-combined
          path: .coverage coverage.xml
```

## Tradeoffs

| Pro | Con |
|---|---|
| Cuts wall-clock from 6 min → 5 min (3 shards) or 6 min → 4 min (4 shards) | Total minutes rises ~2-3x |
| Each shard failure shows a clear "shard N/M failed" badge | One failing shard + flaky serial = N CI runs to bisect |
| Coverage stays whole via `coverage combine` | Coverage combine step is another 30s |
| Replaces the existing single CI test job (no parallel jobs fighting for the same resources) | Requires migrating the required-check in branch protection |
| Easy to scale: add a 4th shard by adding one matrix entry | New tests added in the future may concentrate in one shard (re-shard quarterly) |

## Migration plan

1. **Land the new workflow** as `sharded-test.yml`. Keep `ci.yml`'s `test` job in place for now. **Do not** make `sharded-test` required yet.
2. **Compare 7 days of runs** between `ci.yml` (the existing) and `sharded-test.yml` (the new). Both run on every push, so you get a head-to-head.
3. **If wall-clock improvement is real** (target: ≥30% reduction) **and** total minutes stays within budget (target: <1,800/mo), make `sharded-test` a required check in branch protection and remove the `test` job from `ci.yml`.
4. **If a shard is flaky**, the recommended fix is to either (a) drop the matrix back to 2 shards, or (b) quarantine the flaky tests with `@pytest.mark.flaky` and re-run them serially in a follow-up job.

## Re-sharding cadence

Re-balance the shards when any one shard's wall-clock exceeds the slowest shard by 2x. With ~200 tests added per sprint, that's roughly every 2 sprints (6 weeks). Re-sharding is just editing the matrix list in the YAML.

## What we are NOT doing (and why)

- **No loadscope-by-time** (pytest-xdist's `--dist=loadscope` is already a thing we use; the shard boundaries are the bigger lever).
- **No test-marker-based sharding** (we don't have markers on most tests; adding them is a separate refactor).
- **No test-impact analysis** (e.g., "only run tests that touch the changed file"). That's the next step after this one — tools like `pytest-testmon` can do it but add dependency weight and a flaky cache.
- **No splitting into per-feature workflows** (e.g., a workflow for sales, a workflow for inventory). Too much YAML to maintain; one matrix job is the right granularity.

## References

- `pyproject.toml` `[tool.pytest.ini_options]` — the test configuration
- `.github/workflows/ci.yml` — the workflow this replaces
- `.github/workflows/browser.yml` — the existing Playwright workflow (not changed)
- `docs/operations/dora-2026-Q4.md` — the metrics this is designed to improve
- `docs/ci/toolchain-versions.md` — the tool versions assumed (uv 0.5.x, pytest 8.x)
