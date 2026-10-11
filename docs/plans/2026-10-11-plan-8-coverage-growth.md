# Plan 8 — Coverage gate growth path (4h, LOW)

> **Master plan:** `docs/plans/2026-10-11-round-5-6-master-plan.md`

## Scope
Move from 35% (current gate) → 50% (stretch) over 4h of work.
This is the "polish" plan — ship after plans 0-7.

## Tasks

### 8.1 — Settings_runtime deep tests (2h)

Plan 1 adds route smoke tests. This adds 10 deep tests for
the 10 most-used settings_runtime endpoints:

1. **POST /api/settings/pricing-mode** (write + verify in DB)
2. **POST /api/settings/loyalty-config** (write + verify)
3. **POST /api/settings/cost-display** (write + verify)
4. **POST /api/templates/{key}** (write + render with new template)
5. **POST /api/settings/tax-config** (write + verify in tax calc)
6. **POST /api/settings/sms-templates** (write + verify)
7. **POST /api/settings/refund-policy** (write + verify in refund flow)
8. **POST /api/settings/opening-hours** (write + verify in UI gate)
9. **POST /api/settings/print-receipt-header** (write + verify in receipt)
10. **POST /api/settings/feature-flags** (write + verify in flag check)

**Pattern:**

```python
def test_settings_pricing_mode_persists(authed_client, session_factory):
    """POST /api/settings/pricing-mode → DB row updated; subsequent GET returns new value."""
    r = authed_client.post(
        "/api/settings/pricing-mode",
        json={"mode": "markup", "value": 0.30},
    )
    assert r.status_code == 200

    r2 = authed_client.get("/api/settings/pricing-mode")
    assert r2.json()["mode"] == "markup"
    assert r2.json()["value"] == 0.30
```

**Acceptance:** +2pp.

### 8.2 — Customer/Product CRUD parametrized (1h)

`tests/test_crud_roundtrips_parametrized.py` (from plan 3.2)
gets extended with 6 more endpoints:
1. Customer soft-delete (already in plan 6.2 — but extend with
   restore/un-archive test)
2. Product soft-delete
3. Recipe soft-delete
4. Supplier soft-delete
5. Station archive (already in plan 6.5)
6. Ingredient soft-delete

**Acceptance:** +1pp.

### 8.3 — Loyalty edge cases (1h)

`tests/test_loyalty_*.py` covers happy path. Add 5 tests for
edge cases:
1. `test_loyalty_negative_balance_rejected` — operator
   attempts to deduct more points than customer has
2. `test_loyalty_expired_points_excluded` — points past
   expiry date don't count toward redemptions
3. `test_loyalty_max_redemptions_per_sale` — operator
   can only redeem up to N% of sale total
4. `test_loyalty_double_redemption_idempotent` — refresh
   page after redemption doesn't double-deduct
5. `test_loyalty_audit_row_on_redemption` — every
   redemption writes a ledger row

**Acceptance:** +1pp.

## Total: ~4h, +4pp (35% → 50%).

## Acceptance criteria
- Coverage ≥50%
- All tests pass

## How to verify

```bash
uv run pytest --cov=app --cov-fail-under=50 --cov-report=term-missing
# Expected: "Required test coverage of 50% reached. Total coverage: 50.X%"
```

## Ship-blocked-by
Plans 0, 1, 2, 3.

## Risk
Low. These are all additive tests.

## After plan 8

Once 50% is hit, the next stretch is 65% (parametrize over
all CRUD endpoints) and then 80% (per AGENTS.md §Testing).
The 80% target is the long-term goal but is multiple
weeks of work.
