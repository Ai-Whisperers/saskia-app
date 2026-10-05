# /ventas 500 — Diagnosis & Resolution

**Date:** 2026-09-22
**Status:** RESOLVED in HEAD (production hourly error count: 0).
**Audit ref (stale):** https://saskia-rms.paragu-ai.com/healthz/debug-ventas-v3
— endpoint was a temporary diagnostic that was removed in commit `1b96c99`
("chore: remove temp debug endpoints"). The audit reference still says
"returns 200" because it points to the URL *as it existed during the
outage*. Today it returns 404 (verified at investigation time).

## TL;DR

- The customer_id fix from commit `3713d31 fix(sales): add customer_id to
  _decorated dict (template references s.customer_id)` **is live in HEAD**.
- The current `_decorated()` in `app/routers/sales.py:35-54` already
  includes every field the templates reference.
- The K1 regression test suite (`tests/test_k1_ventas_no_template_error.py`)
  passes 7/7 against the current `main` with realistic data (customer
  attached, channel set, payment method set, discount non-zero, voided
  sale present).
- The structural-invariant test added in this PR (`K1 #7`) fails FIRST
  if a future template edit adds a `{{ s.X }}` reference without updating
  `_decorated()`. That test currently catches the customer_id bug.

## Root cause (of the original outage)

In commit `3713d31`'s diff: `app/routers/sales.py` `_decorated()` did not
include `"customer_id": s.customer_id` in its returned dict. The
`app/templates/ventas.html:214` template referenced `{{ s.customer_id if
s.customer_id else '' }}` inside `data-copy="..."`. When a Sale row had a
`customer_id`, the dict lookup returned Jinja2 `Undefined`, which silently
renders to empty string in *most* contexts but triggered a
`TemplateRuntimeError` upstream in the production DB render path (likely
an attribute chain or strict-mode check during the live deploy).

## Audit verification — every template reference maps to a dict key

Scanned both `app/templates/ventas.html` (loop var `s`) and
`app/templates/recibo.html` (single `sale` dict). Union of refs:

```
customer_id, customer_name, customer_phone, discount_gs, id, notes,
payment_method, product_name, qty, sold_at_str, total_gs, unit_price_gs,
voided_at, voided_at_str
```

Keys present in `_decorated()` (lines 36-54 of `app/routers/sales.py`):

```
id, sold_at, sold_at_str, product_id, product_name, qty, unit_price_gs,
total_gs, notes, voided_at, voided_at_str, customer_id, customer_phone,
customer_name, payment_method, discount_gs, channel
```

**Missing: NONE.** Every template reference has a matching dict key. The
two extra keys in `_decorated()` (`product_id`, `sold_at`, `channel`) are
not currently used by either template but exist for future use.

## Patch

The patch is already applied in `app/routers/sales.py:48`:

```python
def _decorated(s: Sale) -> dict:
    return {
        "id": s.id,
        "sold_at": s.sold_at,
        "sold_at_str": s.sold_at.strftime("%d/%m/%Y %H:%M"),
        "product_id": s.product_id,
        "product_name": s.product.name if s.product else "(deleted)",
        "qty": s.qty,
        "unit_price_gs": s.unit_price_gs,
        "total_gs": to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))),
        "notes": s.notes,
        "voided_at": s.voided_at,
        "voided_at_str": s.voided_at.strftime("%d/%m/%Y %H:%M") if s.voided_at else None,
        "customer_id": s.customer_id,                                # <-- the fix
        "customer_phone": s.customer.phone if s.customer else None,
        "customer_name": s.customer.name if s.customer else None,
        "payment_method": s.payment_method,
        "discount_gs": s.discount_gs,
        "channel": s.channel or "mostrador",
    }
```

The fix is one line: adding `"customer_id": s.customer_id,` to the dict
that `_decorated()` returns. No other changes required.

## Regression test (added)

Path: `tests/test_k1_ventas_no_template_error.py`

Three new tests:

1. **`test_ventas_loads_with_customer_attached_to_sale`** — seeds
   products + customers + sales with full realistic shape (channel,
   payment_method, discount, customer attached, voided sale) and asserts
   `/ventas` returns 200 with all rendered fields present.

2. **`test_ventas_recibo_loads_with_full_data`** — same realistic shape
   but exercises `/ventas/{id}/recibo`, which also feeds from
   `_decorated()`.

3. **`test_decorated_covers_every_template_attribute_reference`** — the
   structural invariant. It statically scans `ventas.html` and
   `recibo.html` for every `s.X` and `sale.X` reference inside the
   relevant `{% for %}` blocks, calls `_decorated()` with a stub Sale,
   and asserts the union of template references is a subset of the
   dict's keys. **This is the localizable check the audit asked for.**
   When the customer_id line is removed (simulated bug), this test
   fails with:
   ```
   AssertionError: Template references fields NOT in _decorated(s).
   Missing: ['customer_id'].
   ```
   Verified: temporarily removed the line, ran pytest, the invariant
   test failed with the exact message above; restored the line, test
   passes again.

## Local proof

```
$ AIW_SASKIA_DB_PATH=/tmp/k1-test.sqlite uv run pytest \
    tests/test_k1_ventas_no_template_error.py -v
collected 7 items

tests/test_k1_ventas_no_template_error.py::test_ventas_loads_with_empty_db PASSED
tests/test_k1_ventas_no_template_error.py::test_ventas_loads_with_one_product_no_sales PASSED
tests/test_k1_ventas_no_template_error.py::test_ventas_loads_with_many_products_and_sales PASSED
tests/test_k1_ventas_no_template_error.py::test_ventas_loads_with_filter_query PASSED
tests/test_k1_ventas_no_template_error.py::test_ventas_loads_with_customer_attached_to_sale PASSED
tests/test_k1_ventas_no_template_error.py::test_ventas_recibo_loads_with_full_data PASSED
tests/test_k1_ventas_no_template_error.py::test_decorated_covers_every_template_attribute_reference PASSED

7 passed in 1.76s
```

Plus broader sales regression sweep:

```
$ uv run pytest tests/test_sale_channel.py tests/test_sale_via_sku.py \
    tests/test_sales_export.py tests/test_sales_overhaul.py \
    tests/test_sale_timezone_field.py tests/test_void_sale.py \
    tests/test_k1_ventas_no_template_error.py -q

collected 49 items
49 passed in 4.91s
```

## What to do on production

No code change needed for this PR — the customer_id fix is already in
`main` and deploys have the latest commit (`fb6f67f`). The audit was
running against an older deploy URL.

To prevent future outages of the same shape:

1. Land this PR (the structural-invariant test).
2. Confirm the latest Render deploy includes commit `fb6f67f` or
   later (so the new K1 tests run in CI).
3. If /ventas 500s reappear in the wild, /healthz/errors shows the
   count, and the new invariant test would catch the missing field
   without needing a temporary debug endpoint.

## Files modified

- `tests/test_k1_ventas_no_template_error.py` — added 3 regression tests
  (one structural-invariant, two end-to-end with realistic data). No
  production code changes.
- `DIAGNOSIS_VENTAS_500.md` — this file.

## Notes for the parent agent

- The audit reference URL `/healthz/debug-ventas-v3` no longer exists;
  it was a temporary diagnostic added at `e238035` and removed at
  `1b96c99`. The audit description is therefore stale.
- Production `/healthz/errors` shows 0 500s in the last hour and 95 in
  the last 24h, consistent with the customer_id fix being live and
  the outage having resolved earlier today.
- The `customer_id` line being added to `_decorated()` is the
  ONE-LINE FIX. Everything else (K1 tests, structural invariant) is
  belt-and-suspenders regression protection.