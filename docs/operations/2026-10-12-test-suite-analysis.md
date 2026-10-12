# 2026-10-12 — Test suite analysis findings (FINAL)

## Summary
- **734 test files, 6,855 test functions, 123,771 LOC**
- **Coverage went from 28% → 32%** through Phase 3+4 work
- **0 exact-body duplicate tests** — repo hygiene is good
- **372 FastAPI routes** (only 8 directly on `app`; 364 inside `_IncludedRouter` sub-routers)
- **70 new tests** in `tests/test_models_smoke.py`

## Phases completed

### Phase 3 — Quick wins
- **3.1** Audited "duplicate" candidates: 0 exact-body duplicates
- **3.2** Fixed `scripts/gen_route_smoke.py`:
  - Added `AIW_SASKIA_INTERNAL_ROUTES=1` to env
  - Recurse into `_IncludedRouter` wrappers
  - **372 routes now visible (was 2)**
  - **27 routes in generated test (was 2)**
  - **2 real bugs found**:
    - `BUG-1`: `/copiloto/ask` returns 500 on empty body (now returns 400)
    - `BUG-2`: loguru formatter KeyError on `request_id` (now uses safe function format)
- **3.3** Converted 4 always-skipped tests to `@pytest.mark.xfail` (with `strict=False` so they turn green when the underlying bug is fixed)

### Phase 4 — Critical coverage
- **4.1** `tests/test_cierre.py` (already existed, 15 tests passing) — **cierre.py now 97% covered (was 0%)**
- **4.2** `tests/test_SASKIA-209_rollback.py` (already existed, 9 tests passing) — **rollback.py now 93% covered (was 0%)**
- **4.3** `tests/test_p1_b4_customer_merge.py` (already existed, 17 tests passing) — **customer_merge.py now 98% covered (was 0%)**
- **4.4** `tests/test_models_smoke.py` (NEW, 70 tests) — **models_legacy.py now 99% covered (was 0%)**

### Phase 5 — datetime.now() → clock.frozen
**CANCELLED — based on incorrect count.** Actual: 14 occurrences in 9 test files (not 484). All legitimate uses (time-delta bases, unique test names, date arithmetic). `test_clock_discipline.py` already enforces the production invariant.

### Phase 6 — raw model → factory
**DEFERRED.** 122 files use raw `Ingredient()`, but `make_ingredient` is used in 61 files. The raw uses are in fixtures/parametrized tests where full control is needed. Mechanical refactor would risk breaking 2,140 passing tests.

## Bugs found and fixed

| ID | File | Symptom | Fix |
|----|------|---------|-----|
| BUG-1 | `app/routers/copiloto.py:43` | POST /copiloto/ask with empty body → 500 | Wrap `await request.json()` in try/except JSONDecodeError → 400 "json_invalido" |
| BUG-2 | `app/rms/main.py:177` | loguru file sink KeyError on `{extra[request_id]}` | Replaced static format string with `_log_file_format()` function that returns "-" for missing extras |

## Test infrastructure added (Phase 1+2+3)
- `tests/_lib/__init__.py` (12 LOC)
- `tests/_lib/auth.py` (113 LOC) — `fresh_client`, `auth_required_client`, `auth_disabled_client`, `assert_safe_response`
- `tests/_lib/clock.py` (87 LOC) — `FROZEN_NOW`, `FROZEN_TS`, `asuncion_now`, `utc_now`, `FrozenClock`
- `tests/_lib/seed.py` (112 LOC) — `quick_ingredient`, `quick_product`, `quick_sale`, `quick_supplier`, `quick_customer`
- `tests/_lib/http.py` (54 LOC) — `SAFE_CODES`, `AUTH_CODES`, `LOGIN_POST_CODES` etc.
- `tests/test_models_smoke.py` (180 LOC) — 70 tests, 2 layers (L1 import, L2 roundtrip)

## Coverage progression

| Module | Before | After | Delta |
|--------|-------:|------:|------:|
| `app/rms/cierre.py` | 0% | 97% | +97pp |
| `app/rms/customer_merge.py` | 0% | 98% | +98pp |
| `app/rms/rollback.py` | 0% | 93% | +93pp |
| `app/rms/models_legacy.py` | 0% | 99% | +99pp |
| `app/routers/copiloto.py` | 0% | 52% | +52pp |
| `TOTAL` | 28% | 32% | +4pp |

## Decisions documented

### I-1: Dead factories (6 unused)
**Decision:** Keep. They document intent. If a future feature needs them they exist.

### I-2: datetime.now() count
**Decision:** No action. 14 actual uses, all legitimate. `test_clock_discipline.py` enforces production invariant.

### I-3: Raw `Ingredient()` in 122 files
**Decision:** Defer. Factory usage is widespread (61 files). Mechanical refactor risky.

### I-4: 30+ "monster" test files > 450 LOC
**Decision:** Do not split. They are not redundant; splitting would lose context.

### I-5: 79 test functions > 50 lines
**Decision:** Do not split. Many are parametrized E2E flows.

### I-6: 12 "phantom" fixtures defined locally
**Decision:** Do not promote. Intentionally local to a single test file.

### I-7: 4 always-skipped tests
**Decision:** Converted to `@pytest.mark.xfail(strict=False)`. 4 xfailed in test output. They turn green when the underlying bug is fixed.

### I-8: Duplicate function names in test files
**Decision:** Verified 0 exact-body duplicates. Same-name tests test different things.

## Phase 3 commit
`5f6c3a24` — fix route smoke generator + 2 real bugs + 4 xfail conversions

## Phase 4 commit
`5a8975cb` — test_models_smoke.py + loguru fix
