# Plan 4 — Harden weak test patterns (4h, MEDIUM)

> **Master plan:** `docs/plans/2026-10-11-round-5-6-master-plan.md`

## Scope
Several existing tests use weak patterns that pass but don't
catch regressions. Targeted refactor across ~10 files.

## Issues

### 4.1 — `assert True` / `pass$` (LOW)
**Search:** `grep -l 'assert True\|pass$' tests/test_*.py`
**Action:** replace with real assertion.
**Effort:** 15min.

### 4.2 — Manual `MIGRATIONS` dict mutation (DONE round 4)
**Status:** fixed in round 4 with `monkeypatch.delitem`.
**Action:** verify it's still using `monkeypatch.delitem`.
**Effort:** 5min.

### 4.3 — `print()`-as-assertion
**File:** `tests/test_no_silent_excepts.py:test_full_audit_summary`
**Symptom:** uses `print` to show audit summary but never asserts.
**Action:** keep as regression sanity check, mark explicitly with
`# regression sanity, never fails`.
**Effort:** 5min.

### 4.4 — Tests that don't actually test what they say (3 fixed in round 5)
1. `test_SASKIA-301_register.py:test_no_salva_in_button_text` (renamed)
2. `test_monthly_closure_and_expense_model.py:test_current_schema_version_is_117` (renamed)
3. `test_security_zap_workflow.py:test_zap_workflow_action_version` (fixed)

**Action:** verify all 3 are now correctly named.
**Effort:** 10min.

### 4.5 — Tests that share global state (2 verified round 5)
1. `tests/test_haccp_seed.py` uses `_CATEGORY_KEYWORDS` (re-exported)
2. `tests/test_migration_safety.py` mutates migrations registry

**Action:** verify both still work after the round-5 fixes.
**Effort:** 10min.

### 4.6 — Tests with no assertions (audit)
**Search:** `grep -L 'assert' tests/test_*.py | xargs grep -L 'pytest'`
**Action:** audit each. If a test is intentionally sanity-only
(`pytest.skip` based on env), add `# regression sanity` comment.
**Effort:** 30min.

### 4.7 — Tests with too many assertions (smell, not bug)
**Search:** `grep -c 'assert' tests/test_*.py | sort -t: -k2 -n -r | head -20`
**Action:** review the top 20 for tests that have 50+ asserts in
one function. Split into smaller test functions if they have
multiple unrelated concerns. Likely 1-2 candidates.
**Effort:** 1h.

### 4.8 — Tests that don't reset fixtures (medium)
**Action:** audit the autouse chain in `tests/conftest.py` for
missing teardowns. ~30min.

### 4.9 — Tests with magic numbers (low)
**Search:** `grep -E '\b[0-9]{5,}\b' tests/test_*.py | grep -v '#' | head -20`
**Action:** replace with named constants.
**Effort:** 30min.

### 4.10 — Tests that depend on test ordering (medium)
**Action:** verify with `pytest -p randomly` that the full suite
passes with shuffled order. Fix any tests that fail in different
order.
**Effort:** 1h.

## Acceptance
- All tests have meaningful assertions
- No `assert True` / `pass$` patterns remain
- 0 new pollution (verify with random order)
- All 4 round-5 fixes still hold

## How to verify

```bash
# Random order
uv run pytest tests/ -p randomly --no-cov -p no:cacheprovider
# Expected: all pass

# Sequential
uv run pytest tests/ --no-cov -p no:cacheprovider
# Expected: all pass
```

## Ship-blocked-by
None (independent of other plans).

## Risk
Low. Refactor with safety net of running full suite after.
