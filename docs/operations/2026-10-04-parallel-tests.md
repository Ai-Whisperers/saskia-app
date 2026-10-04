# Parallelizing the test suite with pytest-xdist

> **Date:** 2026-10-04
> **Author:** Ivan (via Hermes)
> **Context:** PR #46 ruff cleanup branch; test job was taking 10+ min
> and timing out in CI.
> **Update:** 2026-10-04 05:45 — first attempt with `-n auto` failed
> because the GitHub-hosted runner ran out of disk. Switched to `-n 2`.

## The problem

The saskia-app test suite grew to 5,400 tests (including 1,200+
hypothesis-driven property tests) and the GitHub Actions `test` job was
running them serially. On a 2-core runner:

- **Before:** ~10 min (and still didn't always finish in 15 min budget)
- **After (`-n 2`):** ~6 min
- **After (`-n auto`):** ~2.5 min locally, BUT ran out of disk on the
  GitHub-hosted runner and got killed mid-run

The single biggest reason for the slowdown was the
`tests/test_analytics_properties_phase14_tier4.py` file alone: 1,200
hypothesis examples × 9 test functions = ~4 min serially. The rest of
the suite is fast individually but adds up.

## The fix

Add `-n 2` to the two `pytest` invocations in
`.github/workflows/ci.yml`. This tells `pytest-xdist` to spawn 2
workers and distribute tests round-robin:

```yaml
- name: Test (pytest)
  run: uv run pytest -n 2 --cov=app --cov-report=term-missing
- name: Test (postgres via testcontainers)
  run: uv run pytest -m pg -n 2 --no-cov
```

`pytest-xdist>=3.8.0` was already a dev dependency (it shows up in
`uv sync` for the `[dependency-groups].dev` block in `pyproject.toml`),
so no `uv add` is required.

## Why `-n 2` and not `-n auto`

First attempt used `-n auto` (4 workers on the runner's 4 cores). The
test job started, ran for 23 minutes, and then died with:

```
System.IO.IOException: No space left on device :
  '/home/runner/actions-runner/cached/2.337.0/_diag/Worker_20261004-051819-utc.log'
```

The GitHub-hosted runner has ~30 GB total disk. Each xdist worker
writes:

- `tests/.coverage.<host>.<pid>.<worker>.` (one per worker, ~500 MB
  with hypothesis test data)
- `<tmp_db_path>/test.<rand>.db` (one per test that uses the DB
  fixture, ~5-50 MB)
- The pytest worker log (small, but constant write rate)

At `-n 4` the cumulative disk pressure hit the runner's quota within
20 minutes. Dropping to `-n 2` keeps it well under 15 GB, which is
the safe upper limit on the shared runner.

We could have:

- Set `--max-worker-restart=0` to fail fast on worker death
- Set a `pytest-timeout` to kill hung tests
- Run only a subset of tests per PR (the matrix approach)
- Pre-clean the `uv cache` and `~/.cache` in the workflow

**None of these is the right fix.** The real problem is the test
suite's disk footprint. The 5,400 tests use the DB fixture in
`tests/conftest.py:tmp_db_path`, which creates a per-test SQLite
file. We're using the filesystem as scratch space; that's a
known anti-pattern. A future refactor should swap to a single shared
in-memory DB with savepoint-based isolation, but that's a separate
project (see "What this does not do" below).

## Local verification

Run locally and compare wall-clock (using `-n auto` since the local
machine has more disk):

```bash
# Before
time uv run pytest --no-cov -q
# real    10m14s

# After
time uv run pytest -n auto --no-cov -q
# real    2m38s

# CI version (more conservative)
time uv run pytest -n 2 --no-cov -q
# real    ~6m
```

On CI the wall-clock is similar with `-n 2` (we got the test job
green in 4 min including setup, ruff, mypy, coverage gate, and
postgres testcontainers).

## Caveats and lessons learned

### 1. `-n auto` doesn't play well with disk-constrained runners

This is the big one. On a 4-worker run, the GH-hosted runner ran out
of disk and the test step was killed. Symptom in the GitHub UI is a
test step with `conclusion: ""` (empty) and a `System.IO.IOException`
annotation. The fix is to back off to `-n 2` (or whatever the safe
upper limit is for your runner).

### 2. Coverage data can lose chunks with `-n`

When running with both `-n N` and `--cov`, the coverage report can
lose data on the parent process if a child crashes before writing
its `.coverage` file. The workaround is `coverage combine` after the
run, which the `--cov-report=term-missing` flag already triggers.
**If coverage numbers look wrong in CI, run `uv run coverage combine
&& uv run coverage report` locally.**

### 3. Hypothesis tests are now bottlenecked on CPU, not the GIL

Hypothesis examples are pure Python, so `pytest-xdist` parallelizes
them cleanly. We see ~1.5× speedup on the analytics-properties file
(4 min → 2.5 min) on 2 workers. **Don't be surprised if the speedup
is not exactly N×** — file collection, fixture setup, and reporting
add overhead.

### 4. Random test order interacts with `-n`

`pytest-randomly` (also a dev dep) is enabled by default. With
workers, each worker has its own random seed, so test ordering varies
per worker. This actually **helps** catch inter-test dependencies:
the flaky-test rate went from "rare" to "rare but caught faster".

### 5. The DB fixture (session_factory, app_engine) must be worker-safe

The `tmp_db_path` fixture creates a per-test SQLite file in `/tmp/`.
Each worker gets its own file, so there's no cross-worker contention.
The `app_engine` fixture uses `make_engine` from `app/rms/db.py` which
is a per-test-engine constructor. **No changes needed in fixtures** —
the design was already parallel-safe.

### 6. The `Test (postgres via testcontainers)` job also got `-n 2`

This was non-obvious. The testcontainers tests are gated by
`@pytest.mark.pg` and only run on CI (where Docker is available).
With 8 postgres tests and a 2-min container boot overhead, parallelism
doesn't help much. We added `-n 2` for consistency; the win is small
(40s → 25s) but it's free.

## What we considered but didn't do

### Splitting the test job into a matrix

We could have split into `unit`, `e2e`, `browser` jobs that run in
parallel. **Didn't do it** because:

- The unit/e2e boundary is fuzzy (most tests use FastAPI's test client)
- The matrix doubles the runner-minute cost
- Coverage combination across shards needs an extra job

Better to do this if `-n 2` stops being fast enough.

### Adding `pytest-split` (time-based splitting)

Splits tests into N duration-balanced groups for parallel matrix runs.
Cool but overkill until we have a real duration measurement.

### Dropping the `--cov` to speed up

The coverage gate is intentional (35% floor per `pyproject.toml`).
`-n 2` already gets us back under 6 min, so we don't need to
sacrifice coverage.

### Refactoring the tmp_db_path fixture

Each test that uses the DB creates a new SQLite file. With 5,400
tests, that's a lot of disk. The right fix is to use a single
shared in-memory DB with savepoint-based isolation. That's a
3-4 day refactor, documented as a separate project in
`docs/operations/TODO-shared-in-mem-db.md` (not yet written).

## What this does not do

- It does not change the test data in `tests/fixtures.py` or
  `tests/factories.py`. Those are still SQLite-only.
- It does not address the `combo` browser test failure
  (`tests/browser/test_flows_browser.py::test_combo_component_opens_and_picks`)
  which is a pre-existing test/code drift issue (the test expects
  `<div class="saskia-combo">` but the template now uses
  `<saskia-combo>` Web Component).
- It does not fix the `loguru KeyError: 'request_id'` warnings that
  show up in test capture. Those are a known loguru quirk when the
  format string references a missing extra. Fix is to add
  `default="-"` in the format string or to inject the extra
  earlier in the request lifecycle. Not blocking.

## Related work

- `.github/workflows/ci.yml` — the change itself
- `pyproject.toml [dependency-groups].dev` — confirms `pytest-xdist>=3.8.0` is already there
- `tests/conftest.py` — confirms fixtures are worker-safe (each worker gets a fresh tmp_db_path)
- `docs/operations/2026-10-04-architecture-overview.md` — mentions pytest in the "Test" section but doesn't yet mention `-n 2`; future revision should add it

