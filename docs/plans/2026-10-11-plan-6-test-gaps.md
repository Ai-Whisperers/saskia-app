# Plan 6 — Fill the test-logic audit gaps (3h, LOW)

> **Master plan:** `docs/plans/2026-10-11-round-5-6-master-plan.md`

## Scope
During round 5 I found test-logic issues across multiple test
files. Most are now addressed, but several still need work.

## Gaps

### 6.1 — Settings_runtime (DONE in plan 1)

### 6.2 — Customers soft-delete coverage (30min)

**Symptom:** `app/rms/customer.py` has a `soft_delete` function
but no test for the route that calls it.

**Action:** verify `tests/test_customers_routes.py` (added in
plan 1.2) covers the soft-delete path:

```python
def test_customers_delete_soft_deletes(authed_client, session_factory):
    """POST /clientes/{id}/delete → 303; subsequent GET → 404 or 'archivado'."""
    s = session_factory()
    c = make_customer(s, name="Delete me")
    s.commit()
    cid = c.id
    s.close()

    r = authed_client.post(f"/clientes/{cid}/delete", follow_redirects=False)
    assert r.status_code == 303

    s = session_factory()
    c2 = s.get(Customer, cid)
    assert c2.deleted_at is not None  # soft-deleted
    s.close()
```

### 6.3 — Recipe audit coverage (15min)

**Symptom:** `tests/test_recipe_audit.py` should cover create,
edit, delete audit rows.

**Action:** verify it covers all 3 actions. If not, add the
missing tests.

### 6.4 — Inventory write-path mutation tests (1h)

**Symptom:** The 43 tests in `tests/test_inventory*.py` are
mostly read-path.

**Action:** add 5 tests for write-path mutations:
1. `test_inventory_create_ingredient` (POST /inventario/new → 303)
2. `test_inventory_edit_ingredient` (POST /inventario/{id}/edit → 303)
3. `test_inventory_soft_delete_ingredient` (POST /inventario/{id}/delete → 303)
4. `test_inventory_create_recipe` (POST /recetas/new → 303)
5. `test_inventory_edit_recipe` (POST /recetas/{id}/edit → 303)

**File:** `tests/test_inventory_write_path.py`

### 6.5 — Station archive action (30min)

**Symptom:** `app/rms/stations.py` has 13 tests but doesn't
cover the `archive` action.

**Action:** add 2 tests:
1. `test_station_archive_marks_archived`
2. `test_station_unarchive_clears_archive_flag`

### 6.6 — Migration integrity edge cases (1h)

**Symptom:** `tests/test_migration_integrity.py` covers happy
path. Need negative tests.

**Action:** add 3 negative tests:
1. `test_migration_integrity_with_corrupt_archive`
2. `test_migration_integrity_with_missing_archive_file`
3. `test_migration_integrity_with_wrong_schema_version`

## Acceptance
- All 6 gaps addressed with new tests
- All tests pass in full suite

## Ship-blocked-by
Plan 1.

## Risk
Low.
