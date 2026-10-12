# KNOWN-BYPASSES — abstraction-layer violations currently in the repo

**Last probed:** 2026-10-12 (post-SASKIA-211d)
**Why this exists:** so the next session doesn't re-discover the same sites from scratch (~10-15 min saved per session).

---

## 1. `int(Decimal(...))` direct coercion (rule 2)

The ONLY path that converts Decimal → int is `to_int_gs()` in `app/rms/money.py`. Raw `int(Decimal(...))` is a rule-2 violation.

| File | Line | Code | Fix |
|---|---|---|---|
| `app/routers/dashboard.py` | 909 | `total = sum(int(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in sales)` | swap to `to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs)))` |
| `app/rms/seed/menu_import.py` | 47 | `return int(Decimal(cleaned))` | swap to `return to_int_gs(Decimal(cleaned))` (note: needs `to_int_gs` import) |
| `app/rms/prime_cost.py` | 61 | `return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))` | swap to `return to_int_gs(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))` |
| `app/rms/analytics.py` | 448 | `cost_per_unit = int(product.sale_price_gs * Decimal("0.4"))` | swap to `cost_per_unit_gs = to_int_gs(...)` |
| `app/rms/money.py` | 82 | `return int(to_decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))` | **EXEMPT** — this is the body of `to_int_gs()` itself |
| `app/rms/ingredient_margins.py` | 95 | `return to_int_gs(per_portion * (Decimal(int(high_price)) - Decimal(int(last_price))))` | Already uses `to_int_gs`. The inner `int(...)` is a `Decimal → int` for an arithmetic operation, NOT money. May need a different abstraction. |

**Enforcement:** `tests/test_abstraction_usage.py::test_no_int_decimal_in_tests` (3 sites in tests).

---

## 2. `datetime.utcnow()` in app/ (rule 20)

`datetime.utcnow()` is **deprecated in Python 3.12** and produces naive UTC. The replacement is `clock.utcnow()` from `app/rms/clock.py` (returns tz-aware UTC) or `clock.now()` (returns tz-aware Asuncion).

| File | Line | Code | Fix |
|---|---|---|---|
| `app/rms/seed/packs.py` | 4450 | `created_at=datetime.utcnow().isoformat()` | swap to `clock.utcnow().isoformat()` |
| `app/rms/seed/packs.py` | 4460 | (same pattern) | same |
| `app/rms/seed/packs.py` | 4536 | `purchase_price_updated_at=datetime.utcnow()` | same |
| `app/rms/seed/packs.py` | 4548 | `opening_stock_date=datetime.utcnow().date().isoformat()` | `clock.utcnow().date().isoformat()` |
| `app/rms/seed/packs.py` | 4587 | `recorded_at=datetime.utcnow() - timedelta(days=days_ago)` | `clock.utcnow() - timedelta(...)` |
| `app/rms/seed/packs.py` | 4864 | `updated_at=datetime.utcnow()` | `clock.utcnow()` |
| `app/rms/clock.py` | 6, 19 | docstring mentions `datetime.utcnow()` | **EXEMPT** — these are explanatory text in the abstraction's own module |

All 6 violations are in `seed/packs.py`. **Single PR fixes all of them.**

**Enforcement:** `tests/test_abstraction_usage.py::test_no_datetime_utcnow_in_app` (catches 6 hits in seed/packs.py).

---

## 3. `datetime.now()` in app/ (rule 20)

All actual call sites are in the docstrings of `app/rms/clock.py`, `app/rms/sales/lifecycle.py`, and `app/services/template_render.py` — explanatory text, not violations. Zero true bypass sites.

**Enforcement:** `tests/test_abstraction_usage.py::test_no_bare_datetime_now_in_app` (PASS — no real hits).

---

## 4. `apply_sale` imported from the shim (`app/rms/costing.py`)

`app/rms/costing.py` is a **1.3 KB deprecated shim** since the SASKIA-212 refactor. The canonical location is `app/rms/sales/lifecycle.py`. **All 26 shim-imports must move.** Affected routers:

| File | Approx sites | Status |
|---|---|---|
| `app/routers/dashboard.py` | 1 | imports `batch_products_cost_margin`, `batch_recipes_cost` from shim |
| `app/routers/pedidos.py` | 3 | imports `apply_sale`, `_compute_stock_moves` |
| `app/routers/recipes.py` | 5+ | imports `resolve_line_target`, `recipe_batch_cost_gs`, `recipe_unit_cost_gs`, etc. |
| (16 more) | 17 | scattered |

**Why this matters:** the shim re-exports work today, but if a new function is added to `sales/lifecycle.py` without re-exporting it, callers silently break. The 26 import sites are a hidden coupling that future PRs will trip on.

**Fix shape:** swap each `from app.rms.costing import X` to `from app.rms.sales.lifecycle import X` (and verify the function actually exists there). Some helpers (`_compute_stock_moves`) are private (underscore-prefixed) — those should move to a public name on the lifecycle module before being imported externally.

**Enforcement:** `tests/test_abstraction_usage.py::test_apply_sale_imported_from_canonical_path_in_tests` (18 hits in test files; same pattern as the 26 in `app/routers/`).

---

## 5. `StockMovement(...)` direct construction

**Zero hits in `app/` as of 2026-10-12.** All paths go through `apply_sale()` (sale path) or `apply_stock_delta()` (non-sale path). The SASKIA-207 refactor closed all 22 original sites. **Do not re-introduce direct writes.** This category is the canonical "test-the-helper-contract" success story.

---

## 6. Helper modules without `__all__`

4 of 5 abstraction modules export `__all__`:

- ✅ `app/rms/money.py`
- ✅ `app/rms/units.py`
- ✅ `app/rms/clock.py`
- ✅ `app/rms/sales/lifecycle.py`
- ❌ `app/rms/stock_ledger.py` (no `__all__`)

**Fix:** add 1 line to `app/rms/stock_ledger.py`:

```python
__all__ = ["apply_stock_delta", "qty_to_stock_unit"]
```

This is a one-line PR. Worth doing for cleanliness even though it doesn't change runtime behavior.

---

## 7. How to verify after fixing

Run the abstraction test suite:

```bash
uv run pytest tests/test_abstraction_usage.py -v --no-header 2>&1 | tail -40
```

Expected after the Tier 3 fixes (per `agents-md-deep-analysis.md` §4):

| Test | Today | After |
|---|---|---|
| `test_no_int_decimal_in_tests` | FAIL (3) | PASS |
| `test_no_datetime_utcnow_in_app` | FAIL (6) | PASS |
| `test_apply_sale_imported_from_canonical_path_in_tests` | FAIL (18) | PASS |
| `test_no_direct_stockmovement_outside_sale_path` | PASS (0) | PASS |
| 8 other tests | PASS | PASS |

**Total: 24/24 green after Tier 3.**

---

## 8. What this file deliberately does NOT cover

- **Hard-rule violations** (CHANGELOG discipline, hardcoded credentials, secret leakage) — those are CI-gated; see `.pre-commit-config.yaml` and `tests/test_prod_security_gates.py`.
- **Per-router refactor debt** (legacy-vs-new model split, `models_legacy.py` deprecation) — that's a Sprint-2.x initiative, not a one-line fix.
- **Anti-rules** (React/Vue/Tailwind, microservices, GraphQL, etc.) — covered by `tests/test_ci_anti_rules.py` (13/20 enforced).