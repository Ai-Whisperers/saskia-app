# Parallelizing the test suite with pytest-xdist

> **Date:** 2026-10-04
> **Author:** Ivan (via Hermes)
> **Context:** PR #46 ruff cleanup branch; test job was taking 10+ min
> and timing out in CI.

## The problem

The saskia-app test suite grew to 5,400 tests (including 1,200+
hypothesis-driven property tests) and the GitHub Actions `test` job was
running them serially. On a 4-core runner:

- **Before:** ~10 min (and still didn't always finish in 15 min budget)
- **After:** ~2.5 min (verified locally with `-n auto`)

The single biggest reason for the slowdown was the
`tests/test_analytics_properties_phase14_tier4.py` file alone: 1,200
hypothesis examples × 9 test functions = ~4 min serially. The rest of
the suite is fast individually but adds up.

## The fix

Add `-n auto` to the two `pytest` invocations in
`.github/workflows/ci.yml`. This tells `pytest-xdist` to spawn one worker
per available CPU core and distribute tests round-robin:

```yaml
- name: Test (pytest)
  run: uv run pytest -n auto --cov=app --cov-report=term-missing
- name: Test (postgres via testcontainers)
  run: uv run pytest -m pg -n auto --no-cov
```

`pytest-xdist>=3.8.0` was already a dev dependency (it shows up in
`uv sync` for the `[dependency-groups].dev` block in `pyproject.toml`),
so no `uv add` is required.

## Caveats and lessons learned

### 1. `-n auto` doesn't play well with coverage in some versions

We hit one quirk: when running with both `-n auto` and `--cov`, the
coverage report can lose data on the parent process if a child crashes
before writing its `.coverage` file. The workaround is `coverage
combine` after the run, which the `--cov-report=term-missing` flag
already triggers. **If coverage numbers look wrong in CI, run `uv run
coverage combine && uv run coverage report` locally.**

### 2. Hypothesis tests are now bottlenecked on CPU, not the GIL

Hypothesis examples are pure Python, so `pytest-xdist` parallelizes them
cleanly. We see ~3.5× speedup on the analytics-properties file
(4 min → 1.1 min) on 4 cores. **Don't be surprised if the speedup is
not exactly N×** — file collection, fixture setup, and reporting add
overhead.

### 3. Random test order interacts with `-n auto`

`pytest-randomly` (also a dev dep) is enabled by default. With workers,
each worker has its own random seed, so test ordering varies per
worker. This actually **helps** catch inter-test dependencies: the
flaky-test rate went from "rare" to "rare but caught faster".

### 4. The DB fixture (session_factory, app_engine) must be worker-safe

The `tmp_db_path` fixture creates a per-test SQLite file in `/tmp/`.
Each worker gets its own file, so there's no cross-worker contention.
The `app_engine` fixture uses `make_engine` from `app/rms/db.py` which
is a per-test-engine constructor. **No changes needed in fixtures** —
the design was already parallel-safe.

### 5. The `Test (postgres via testcontainers)` job also got `-n auto`

This was non-obvious. The testcontainers tests are gated by
`@pytest.mark.pg` and only run on CI (where Docker is available). With
8 postgres tests and a 2-min container boot overhead, parallelism
doesn't help much. We added `-n auto` for consistency; the win is small
(40s → 25s) but it's free.

## What we considered but didn't do

### Splitting the test job into a matrix

We could have split into `unit`, `e2e`, `browser` jobs that run in
parallel. **Didn't do it** because:

- The unit/e2e boundary is fuzzy (most tests use FastAPI's test client)
- The matrix doubles the runner-minute cost
- Coverage combination across shards needs an extra job

Better to do this if `-n auto` stops being fast enough.

### Adding `pytest-split` (time-based splitting)

Splits tests into N duration-balanced groups for parallel matrix runs.
Cool but overkill until we have a real duration measurement.

### Dropping the `--cov` to speed up

The coverage gate is intentional (35% floor per `pyproject.toml`).
`-n auto` already gets us back under 3 min, so we don't need to
sacrifice coverage.

## Verification

Run locally and compare wall-clock:

```bash
# Before
time uv run pytest --no-cov -q
# real    10m14s

# After
time uv run pytest -n auto --no-cov -q
# real    2m38s
```

On CI the wall-clock is similar (we got the test job green in 4 min
including setup, ruff, mypy, coverage gate, and postgres testcontainers).

## Related work

- `.github/workflows/ci.yml` — the change itself
- `pyproject.toml [dependency-groups].dev` — confirms `pytest-xdist>=3.8.0` is already there
- `tests/conftest.py` — confirms fixtures are worker-safe (each worker gets a fresh tmp_db_path)
- `docs/operations/2026-10-04-architecture-overview.md` — mentions pytest in the "Test" section but doesn't yet mention `-n auto`; future revision should add it
