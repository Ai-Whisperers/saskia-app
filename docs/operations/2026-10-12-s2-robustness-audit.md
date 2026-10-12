# S2 Robustness Lane — Audit (2026-10-12)

Scope: logging config, `app/rms/errors.py` typed exception taxonomy, request_id
middleware, healthchecks, retry/idempotency helpers, silent-except elimination,
`print()` elimination.

Verified 2026-10-12 against live repo at
`/opt/data/work/saskia-app/.worktrees/s2-robustness` (branch
`hermes/levelup-s2-robustness`).

## Headline counts

| Metric                                | Count | Source |
|---------------------------------------|------:|--------|
| `try` / `except` blocks in `app/`     |   531 | AST scan (excludes `_archive/`, `migrations/`) |
| Bare `except:` (no type)              |     0 | AST scan |
| Broad `except Exception/BaseException`|   265 | AST scan |
| &nbsp;&nbsp;– with `logger.` call     |   115 | (good — already typed/logged) |
| &nbsp;&nbsp;– with `raise` re-raise   |    13 | (good — typed re-raise) |
| &nbsp;&nbsp;– **silent** (no log, no raise) | **137** | **TARGET** |
| `print(` calls in `app/`              |    55 | grep `app/ --include='*.py'` |
| `app/` `.py` files                    |   296 | `find app/ -name '*.py'` |
| &nbsp;&nbsp;– with `logger.*`         |    49 | (only 16.5 % of files!) |
| &nbsp;&nbsp;– without any logger      |   247 | (the long tail) |
| Root-logger use (`getLogger()` / `getLogger('')`) |   0 | grep |
| `raise ... from X` chains             |    62 | grep |
| Bare `raise` re-raises                |    16 | grep |
| Healthz endpoints                     |    10 | `app/routers/health.py` (`/healthz`, `/healthz/depth`, `/healthz/errors`, `/healthz/deps`, `/healthz/db`, `/healthz/summary`, `/healthz/schema`, `/healthz/migrate`, `/healthz/backup`, plus HEAD `/healthz`) |
| request_id middleware                 |     1 | `app/rms/observability.py::RequestContextMiddleware` |
| Typed exception hierarchy             |     1 | `app/rms/errors.py` (`AppError` + 11 subclasses) |
| Naive `time.sleep` retries            |     0 | grep `time.sleep`, `retries=`, `attempt` |
| Existing tests covering this surface  |     3 | `tests/test_observability.py` (29 cases), `tests/test_observability_logs.py` (5), `tests/test_logging_config.py` (3), `tests/test_no_silent_excepts.py` (55, AST scan) |

## What's already good (do not duplicate)

- **`app/rms/errors.py`** — full typed hierarchy (`AppError`, `BadRequest`,
  `ValidationError`, `NotFound`, `AlreadyExists`, `Conflict`,
  `Unauthenticated`, `Forbidden`, `RateLimited`, `DataIntegrityError`,
  `DependencyError`, `AppInternalError`). All carry `reason_code`,
  `context`, optional `cause`. `to_http_exception()` exists.
- **`app/rms/observability.py::RequestContextMiddleware`** — request_id
  generation (12-char UUID4 hex), honors upstream `X-Request-Id`, sets
  the response header, attaches `request_id`, `user_id`, `method`, `path` to
  every loguru emission via `logger.contextualize()`. `record_audit()`
  helper auto-fills request_id.
- **Pre-commit `no-silent-excepts`** (rule 41) — AST-based scan, runs
  `tests/test_no_silent_excepts.py::test_no_silent_except_in_routers`
  against `app/routers/**/*.py`. Currently passes (55 collected, all
  green).
- **`tests/test_observability.py`** (29 tests), `test_observability_logs.py`
  (5), `test_logging_config.py` (3) — all green at HEAD.

## Gaps (the work)

### 1. `app/rms/errors.py` — extend taxonomy around REAL raises

The hierarchy is good but **doesn't cover every typed exception the
runtime raises**. Real exceptions raised elsewhere that should fold into
`AppError`:

| Exception                | Module                              | Status |
|--------------------------|-------------------------------------|--------|
| `CycleInRecipeTree`      | `app/rms/profitability/cost.py:54`  | bare `Exception`, no message/reason_code/context — should wrap into `AppError` |
| `RecipeWithoutYield`     | `app/rms/profitability/cost.py:58`  | bare `Exception` — same |
| `FiadoError`             | `app/rms/fiado.py:19`               | `ValueError` — caller can't catch `AppError` cleanly |
| `CashSessionError`       | `app/rms/cash.py:19`                | `ValueError` — same |
| `ClosureValidationError` | `app/rms/services/closures.py:28`   | `ValueError` — same |
| `ClosureConflictError`   | `app/rms/services/closures.py:32`   | `ValueError` — same |
| `ExpenseValidationError` | `app/rms/services/expenses.py:25`   | `ValueError` — same |
| `RefundError`            | `app/rms/refunds.py:59`             | bare `Exception` |
| `LLMError`               | `app/rms/llm.py:29`                 | `RuntimeError` |
| `StorageError`           | `app/services/r2_backup.py:40`      | bare `Exception` |
| `EODClosedError`         | `app/rms/eod_closed.py:100`         | `ValueError` |
| `TenantLoadError` / `UnknownTenantError` | `app/rms/tenant.py:113-117` | bare `Exception` |
| `MenuNotFound`           | `app/rms/menu_ejecutivo.py:23`      | `LookupError` — should be a `NotFound` subclass |
| `RollbackError`          | `app/rms/rollback.py:52`            | `RuntimeError` |

The plan: each gets a **subclass under `AppError`** (or a sibling that
explicitly notes it predates the hierarchy and is wrapped at call
sites). Subclasses get `status_code` + `reason_code`; the original class
can either be re-exported as an alias or wrapped. Backwards-compatible
because callers `except` the original name.

### 2. `print()` calls in `app/` — 55

Grouped:

| Path                                  | Count | Severity |
|---------------------------------------|------:|----------|
| `app/rms/main.py`                     |    ~12 | CLI smoke output / one-shot startup banner — fine to keep |
| `app/rms/otel.py`                     |    ~8  | Init banners — fine to keep (one-shot) |
| `app/rms/migrations/_084.._096..`     |    ~6  | Migration scripts — `print` is acceptable, but should be `logger.info` for consistency |
| `app/rms/safeguard.py`                |    ~6  | Standalone CLI invocation — borderline |
| `app/rms/notify.py`                   |     1  | Notification CLI invocation |
| `app/rms/seed_market_prices.py`       |     1  | CLI `--help` docstring print — fine |
| `app/rms/seed/pack_demo.py`           |     2  | CLI listing — fine |

Verdict: most `print()` calls are **legitimate CLI / one-shot init code**.
The ones in `app/rms/migrations/_084_*.py`, `_096_*.py`,
`_095_*.py` should be `logger.info` so the same message shows up in
production logs. The rest stay (they're CLI `if __name__ == "__main__"`
blocks or hardcoded banner emits). Target reduction: **6 → 0** in
migrations, **49 → 49** elsewhere (no behavior change).

### 3. Silent broad excepts — 137 across 36 files

Top offenders:

| File                                  | Silent count |
|---------------------------------------|-------------:|
| `app/rms/db.py`                       |          58 |
| `app/routers/health.py`               |          12 |
| `app/rms/main.py`                     |           8 |
| `app/services/template_render.py`     |           7 |
| `app/routers/products.py`             |           4 |
| `app/rms/gerencia_snapshot.py`        |           4 |
| `app/routers/eod.py`                  |           3 |
| `app/routers/sales.py`                |           3 |
| `app/rms/production_demand.py`        |           3 |
| (27 other files)                      |          35 |

Most of these are **degraded-but-don't-fail** paths: `session.rollback()`
catchers in `routers/`, health-check defensive guards, "fall back to
empty dict" handlers in render helpers. Each will get either a
`logger.warning("…", exc_info=True)` or an inline `# noqa: silent
intended — <one-line justification>` comment per AGENTS.md rule 41
spirit (extended beyond `routers/`). Target: **137 → 0**.

### 4. Loggers — 247 of 296 files lack any `logger`

This is the **biggest gap**. Many `app/rms/*.py` files either:
- print directly to stderr (already counted),
- swallow exceptions silently (already counted), or
- emit no observability at all when something unexpected happens.

The fix isn't to add `logger = getLogger(__name__)` to every file
(noisy). It's to: **(a)** ensure every file that does any work has a
named logger, **(b)** convert bare `print()` to `logger.info` in the
migration / init paths, **(c)** keep silent-except fixes scoped to
"expected-degraded" code paths with `logger.warning(... exc_info=...)`.

Target: **49 → 80+** modules with a logger (focus on `app/rms/` core,
`app/routers/` high-traffic, and any module that writes print to
stderr).

### 5. `raise X from Y` discipline

Only 62 of the 230 `except ... as X` blocks `raise from`. That means
~170 excepts either don't re-raise or re-raise bare (`raise` — only 16
such bare re-raises, which is fine). The gap: many handlers set a
fallback and `return`, dropping the original traceback. After our silent-
except sweep we'll add `logger.exception(...)` calls before the
fallback so the original traceback is at least in the log even when we
swallow.

### 6. request_id middleware — already in place

`app/rms/observability.py::RequestContextMiddleware` is the single
chokepoint. Confirmed:
- Generates 12-char UUID4 if no upstream `X-Request-Id`.
- Sets `request.state.request_id` + `request.state.user_id`.
- Binds `logger.contextualize(...)` so every `logger.*` during the
  request is auto-tagged.
- Sets `X-Request-Id` response header.
- Strips access log for `/static/` and `/healthz/*` (high noise).

**Gap**: doesn't bind `route` (matched route name). Has a TODO-style
comment about Loguru limitations. Worth a `bind_request_route()`
helper or moving to a `contextvars`-based scheme.

### 7. Healthcheck gaps

`app/routers/health.py` already exposes 10 endpoints:
`/healthz`, `/healthz/depth`, `/healthz/errors`, `/healthz/deps`,
`/healthz/db`, `/healthz/summary`, `/healthz/schema`, `/healthz/migrate`,
`/healthz/backup`. AGENTS rule 34 contract: all three
(`/healthz`, `/healthz/deps`, `/healthz/backup`) < 100 ms, no
sensitive data, no Sentry log on failure.

**Gaps**:
- 12 of the silent broad excepts are in `health.py` itself — by
  design (defensive), but they're not even logged. Will add
  `logger.debug(...)` so the operator can grep why a probe degraded.
- `/healthz/errors` exists but is admin/operator-only — should be
  confirmed reachable and not exposed publicly.
- No `/healthz/live` vs `/healthz/ready` split (Kubernetes-style). Not
  blocking for Sazon's Swarm + Traefik setup, but worth a note.

### 8. Retry / idempotency helpers — none exist

Searched for `time.sleep`, `retries=`, `attempt`, `while ... attempt`
inside `app/`: zero hits. There's no retry helper. The Sazon `apply_sale()`
transaction wrapper is single-shot. The HTTP integrations
(`app/integrations/scrapers.py`, `app/services/r2_backup.py`,
`app/services/backup_crypto.py`) wrap their own try/except without
backoff.

Plan: add `app/rms/retry.py` with `retry_transient(fn, *, attempts=3,
base_delay=0.2, exceptions=...)`. Use only stdlib (`time.sleep`,
`random` jitter). Wrap HTTP transient errors (`requests.RequestException`)
and DB transient errors (`OperationalError("database is locked")`,
`OperationalError("deadlock")`). Pure helper, no auto-wiring — call
sites opt in.

## Files I plan to edit (this session)

| File                                | Change |
|-------------------------------------|--------|
| `app/rms/errors.py`                 | Add `RecipeTreeError`, `RecipeValidationError`, `FiadoError` (alias), `CashSessionError` (alias), `ClosureError` (alias), `ExpenseError` (alias), `RefundError` (alias), `LLMError` (alias), `StorageError` (alias), `EODClosedError` (alias), `TenantError` (alias), `MenuNotFound` (subclass of `NotFound`). |
| `app/rms/retry.py`                  | New. `retry_transient()` helper + transient-class classifier. |
| `app/rms/db.py`                     | Fix 58 silent excepts: add `logger.warning(... exc_info=True)` before fallbacks. Preserve existing rollback semantics. |
| `app/rms/main.py`                   | 8 silent excepts → `logger.debug/warning`. Migrations banner: convert `print` to `logger.info`. |
| `app/routers/health.py`             | 12 silent excepts → `logger.debug` (defensive-probe noise). |
| `app/services/template_render.py`   | 7 silent excepts → `logger.warning`. |
| `app/routers/products.py`           | 4 silent excepts → `logger.warning`. |
| `app/rms/gerencia_snapshot.py`      | 4 silent excepts → `logger.warning`. |
| `app/routers/eod.py`                | 3 silent excepts → `logger.debug`. |
| `app/routers/sales.py`              | 3 silent excepts → `logger.warning` (rollback paths). |
| `app/rms/production_demand.py`      | 3 silent excepts → `logger.warning`. |
| (25 other files with ≤2 silent excepts) | sweep remaining 35 silent excepts in small PRs |
| `app/rms/migrations/_084_*`, `_095_*`, `_096_*` | Replace `print()` with `logger.info`. |
| `app/rms/observability.py`          | Bind `route` via `contextvars` for true per-request route binding. |
| `tests/test_errors_extended.py`     | New. Tests for the new exception subclasses + `from exc` discipline. |
| `tests/test_observability_extended.py` | New. Test that `route` is bound after dispatch, that health-probe silent excepts log at DEBUG. |
| `tests/test_retry.py`               | New. `retry_transient` happy path, transient-class retry, terminal-class no-retry, max-attempts, jitter bounds. |
| `tests/test_silent_excepts_rms.py`  | New. AST scan for silent excepts in `app/rms/**/*.py` (extending rule 41). |
| `CHANGELOG.md`                      | Add entries per PR (rule 35). |
| `docs/operations/2026-10-12-s2-robustness-audit.md` | This document. |
| `docs/operations/2026-10-12-s2-robustness-execution.md` | Execution log. |

## Sequencing (planned PRs)

1. **PR1: errors.py taxonomy extension** — adds subclasses, tests.
   Behavior-preserving.
2. **PR2: retry helper** — new module, new tests, zero call-site
   wiring yet.
3. **PR3: silent-except sweep in `app/rms/`** — `db.py` (58),
   `main.py` (8), `production_demand.py` (3),
   `gerencia_snapshot.py` (4), small files (≤2 each, 11 files).
   Adds `tests/test_silent_excepts_rms.py` as a CI gate.
4. **PR4: silent-except sweep in `app/routers/`** — extends
   `tests/test_no_silent_excepts.py` to also assert *what kind* of
   log call (warning/info) is present per site, and fixes
   `health.py` (12), `products.py` (4), `eod.py` (3), `sales.py`
   (3), and remaining.
5. **PR5: silent-except sweep in `app/services/` + `app/integrations/`**
   — `template_render.py` (7) and others.
6. **PR6: print() → logger.info** — migrations + init banners.
7. **PR7: request_id `route` binding via contextvars** — observability
   improvement.

Each PR lands ≤ 1 file-concern, ships tests, runs `make ci` green.

## Cross-session coordination

- **No edits to `app/routers/` silent-except test file** (`tests/test_no_silent_excepts.py`) without coordinating with S1 (tests lane).
- **No edits to `tests/` broadly** without S1 approval — s1 owns `tests/`.
- **CLAIMS** before touching every file above.
- **INBOX** S5 (coordinator) before each PR with: file list,
  silent-count delta, churn estimate.
- **Lock `/healthz` contract** (rule 34) — any change to `health.py`
  must keep response time < 100 ms and not expose secrets.

## Acceptance criteria

- [ ] All 137 silent broad excepts: logged or justified.
- [ ] All `app/rms/` modules that raise real exceptions use `AppError`
      subclasses (or wrap them in a single conversion site).
- [ ] `print()` in migrations converted to `logger.info`.
- [ ] `app/rms/retry.py::retry_transient()` exists, tested, no
      call-site changes yet.
- [ ] `request_id` + `route` available on every line emitted during a
      request.
- [ ] `/healthz/*` < 100 ms, no Sentry noise on failure (rule 34).
- [ ] Every fix ships its test (`pytest.raises`, `caplog`, or `httpx_mock`).
- [ ] `make ci` green at HEAD.
- [ ] Measured deltas in each commit (`silent excepts: 137 → 117`).
- [ ] `CHANGELOG.md` updated per PR.
