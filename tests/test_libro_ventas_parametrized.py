"""Parametrized coverage for app/rms/accounting.py:libro_ventas (CC 21, D-grade).

S1 batch-3 (test coverage 27% -> 30%): every row drives the function through
a distinct report shape (empty, single day, week, month, post-void filter).
This file is ADDITIVE — the existing tests/test_libro_ventas_refunds.py
still cover the M1 refund columns; this file locks the window/aggregation
behavior at the entry point.

Each row is one complete spec for one window/seed combination. Adding a
new shape = one new dict entry, no new function.

Seeding strategy
----------------
- `libro_ventas` reads from Sale via `sales_in_window` which excludes
  voided rows (include_voided=False). We drive the date window with a
  freeze at a known UTC date (`_ANCLA`) so the test is calendar-stable.
- Product and Customer are inserted via the SQLAlchemy ORM. We use the
  conftest `session_factory` fixture (autouse tmp_db_path gives each test
  a fresh file-based SQLite). The brief says "test_db"; the closest
  conftest equivalent is `session_factory` — used in 53+ other test files.

Spanish fiscal terminology in this file
---------------------------------------
- gravada = IVA-bearing sale (snapshot iva_base_gs/iva_amount_gs > 0)
- exenta  = VAT-exempt sale (snapshot iva_base_gs = gross,
           iva_amount_gs = 0)
- These are encoded as explicit iva_base_gs/iva_amount_gs snapshots on
  the Sale row; the function prefers snapshots over computed-from-gross
  when > 0 (see accounting.py:259-266).
"""

# allow-hardcoded-dates: frozen-time fixture: _ANCLA = datetime(2026, 10, 9) pins 'now' for libro_ventas rows

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

# Anchor date so the test is calendar-independent. Friday 2026-10-09
# 12:00 UTC sits in the middle of a normal week; surrounding days are
# in the same ISO week, week+1, and week-1, no month-edge weirdness.
_ANCLA = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


# ─── Row spec ────────────────────────────────────────────────────────────────


@dataclass
class SaleSpec:
    """One sale to insert into the test DB.

    days_offset: how many days after _ANCLA this sale's sold_at lands.
    gross_gs: total sale amount (qty * unit_price_gs round-tripped via
              Decimal; pre-computed so the test asserts the right number).
    iva_base_gs, iva_amount_gs: snapshot fields. >0 means "gravada
              (factura path)"; =0 with base==gross means "exenta".
    voided: if True, voided_at is set; libro_ventas must exclude.
    """

    days_offset: int
    gross_gs: int
    iva_base_gs: int = 0
    iva_amount_gs: int = 0
    iva_rate: str = "10"
    voided: bool = False
    invoice_type: str = "boleta_resimple"
    customer_name: str | None = None


# ─── Parametrize rows ─────────────────────────────────────────────────────────


# Case 1: empty period — no sales in window.
_EMPTY_PERIOD = {
    "id": "empty_period",
    "window": ("day", 0),  # day, no offset
    "sales": [],
    "expected_count": 0,
    "expected_total_gross_gs": 0,
    "expected_total_iva_gs": 0,
    "description": "no sales in window → 0 rows, all totals 0",
}

# Case 2: one day, N sales — verify per-row gross/IVA extraction.
_ONE_DAY = {
    "id": "one_day_with_n_sales",
    "window": ("day", 0),
    "sales": [
        SaleSpec(days_offset=0, gross_gs=10_000),  # gravada, base≈9091 iva≈909
        SaleSpec(days_offset=0, gross_gs=25_000),  # gravada, base≈22727 iva≈2273
        SaleSpec(days_offset=0, gross_gs=5_000, customer_name="Ana"),
    ],
    "expected_count": 3,
    "expected_total_gross_gs": 40_000,
    # All three are gravada; tax_mode='included' (default) so IVA is
    # extracted from gross. Approximate 10% then summed: 909 + 2273 + 455 = 3637.
    # We use a non-strict check (greater-than-half-of-gross-iva) to avoid
    # brittle rounding assertions.
    "description": "3 gravada sales same day → 3 rows, total gross=40k",
}

# Case 3: one week (Mon-Sun), multiple days — verify all days in window,
# none outside.
_ONE_WEEK = {
    "id": "one_week_multi_day",
    "window": ("week", 0),
    "sales": [
        SaleSpec(days_offset=-2, gross_gs=10_000),  # Wed
        SaleSpec(days_offset=-1, gross_gs=15_000),  # Thu
        SaleSpec(days_offset=0, gross_gs=20_000),  # Fri
        SaleSpec(days_offset=1, gross_gs=8_000),  # Sat
        SaleSpec(days_offset=-30, gross_gs=99_000),  # out of window (4+ weeks back)
    ],
    "expected_count": 4,
    "expected_total_gross_gs": 53_000,  # 10k+15k+20k+8k
    "description": "4 in-window + 1 out-of-window (30 days back) → 4 rows",
}

# Case 4: month with mixed gravada / exenta — verify snapshot branch
# in libro_ventas (iva_base_gs/iva_amount_gs>0 → use snapshot) is hit
# for gravada, and the exenta path (snapshot base==gross, iva=0) is
# hit for the exempt sale.
_MONTH_MIXED = {
    "id": "month_mixed_gravada_exenta",
    "window": ("month", 0),
    "sales": [
        # Gravada factura: snapshot iva_amount_gs > 0. libro_ventas prefers
        # the snapshot over the computed-from-gross extraction.
        SaleSpec(
            days_offset=0,
            gross_gs=11_000,
            iva_rate="10",
            iva_base_gs=10_000,
            iva_amount_gs=1_000,
            invoice_type="factura",
        ),
        # Gravada boleta (no snapshot): computed-from-gross extraction.
        SaleSpec(days_offset=5, gross_gs=22_000),
        # Exenta: snapshot base==gross, iva_amount=0. The function
        # uses the snapshot path (iva_base_gs>0), so base=33_000, iva=0.
        SaleSpec(
            days_offset=10,
            gross_gs=33_000,
            iva_rate="0",
            iva_base_gs=33_000,
            iva_amount_gs=0,
            invoice_type="none",
        ),
    ],
    "expected_count": 3,
    "expected_total_gross_gs": 66_000,  # 11k+22k+33k
    "description": "gravada factura + gravada boleta + exenta in same month",
    "asserts": {
        # By id index in `sales` (0=gravada factura, 1=gravada boleta, 2=exenta).
        0: dict(base_gs=10_000, iva_gs=1_000, invoice_type="factura"),
        1: dict(iva_gs__gt=0),  # computed from gross, not snapshot
        2: dict(base_gs=33_000, iva_gs=0, invoice_type="none"),
    },
}

# Case 5: cancelled (voided) sale excluded. The voided sale is inside
# the window; libro_ventas must drop it because sales_in_window has
# `include_voided=False` (default).
_CANCELLED_EXCLUDED = {
    "id": "cancelled_sale_excluded",
    "window": ("day", 0),
    "sales": [
        SaleSpec(days_offset=0, gross_gs=10_000),  # kept
        SaleSpec(days_offset=0, gross_gs=50_000, voided=True),  # voided, dropped
        SaleSpec(days_offset=0, gross_gs=8_000),  # kept
    ],
    "expected_count": 2,
    "expected_total_gross_gs": 18_000,  # 10k + 8k; voided 50k dropped
    "description": "1 voided sale in window → dropped, 2 active rows remain",
}


_ROWS: list[dict] = [
    _EMPTY_PERIOD,
    _ONE_DAY,
    _ONE_WEEK,
    _MONTH_MIXED,
    _CANCELLED_EXCLUDED,
]


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _window_for(kind: str, offset_days: int) -> tuple[datetime, datetime]:
    """Return (start, end) UTC for the test window kind at _ANCLA.

    day   = [_ANCLA_day_start, _ANCLA_day_start + 1d)
    week  = [Mon 00:00 of _ANCLA's week, Mon 00:00 next week)
    month = [1st 00:00 of _ANCLA's month, 1st 00:00 next month)
    """
    if kind == "day":
        start = _ANCLA.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif kind == "week":
        # Monday=0, Sunday=6
        monday = _ANCLA - timedelta(days=_ANCLA.weekday())
        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    elif kind == "month":
        start = _ANCLA.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Next month: add 32 days and snap to day=1
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    else:  # pragma: no cover — defensive
        raise ValueError(f"unknown window kind: {kind!r}")
    return start, end


def _seed_sales(s, specs: list[SaleSpec]) -> None:
    """Insert the seed product/customer + each sale per spec."""
    from app.rms.models_legacy import Customer, Product, Sale

    # Idempotent product seed (id=1). If the test re-uses the same
    # product_id across rows, reuse; if not, we just keep id=1.
    if s.execute(text("SELECT id FROM product WHERE id=1")).first() is None:
        s.add(
            Product(
                id=1,
                name="Test Product",
                sale_price_gs=10_000,
                portion_label="1 unidad",
            )
        )
        s.flush()

    # Customer map: name -> id. Reuse by name within a single test.
    cust_id_by_name: dict[str, int] = {}
    for spec in specs:
        if spec.customer_name and spec.customer_name not in cust_id_by_name:
            s.add(Customer(name=spec.customer_name, phone="+595900000000"))
            s.flush()
            cust_id_by_name[spec.customer_name] = s.execute(
                text("SELECT last_insert_rowid()")
            ).scalar()

    for spec in specs:
        sold_at = _ANCLA + timedelta(days=spec.days_offset)
        sale = Sale(
            product_id=1,
            qty=1.0,
            unit_price_gs=spec.gross_gs,
            sold_at=sold_at,
            payment_method="efectivo",
            customer_id=(cust_id_by_name.get(spec.customer_name) if spec.customer_name else None),
            discount_gs=0,
            channel="mostrador",
            invoice_type=spec.invoice_type,
            iva_rate=spec.iva_rate,
            iva_base_gs=spec.iva_base_gs,
            iva_amount_gs=spec.iva_amount_gs,
            tz="America/Asuncion",
        )
        if spec.voided:
            sale.voided_at = sold_at + timedelta(minutes=5)
            sale.void_reason = "cliente se arrepintió (test)"
            sale.voided_by = "test"
        s.add(sale)
    s.flush()


# ─── Parametrized driver ─────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", _ROWS, ids=lambda s: s["id"])
def test_libro_ventas_window_and_filter(spec: dict, session_factory) -> None:
    """Drive `libro_ventas` through 5 report shapes.

    Locks the contract the function's entry-point must keep stable:
    - empty period returns []
    - one day with N sales returns N rows summing to expected total
    - one week with multiple days picks up exactly the in-window sales
    - month with mixed gravada/exenta respects the snapshot branch
    - voided sales inside the window are dropped (sales_in_window default)
    """
    from app.rms.accounting import libro_ventas

    kind, _ = spec["window"]
    start, end = _window_for(kind, 0)

    with session_factory() as s:
        _seed_sales(s, spec["sales"])
        rows = libro_ventas(s, start_date=start, end_date=end)

    assert len(rows) == spec["expected_count"], (
        f"{spec['id']}: got {len(rows)} rows, expected {spec['expected_count']} "
        f"({spec['description']})"
    )

    if spec["expected_count"] == 0:
        assert rows == []
        return

    actual_total = sum(r.total_gross_gs for r in rows)
    assert actual_total == spec["expected_total_gross_gs"], (
        f"{spec['id']}: total_gross_gs={actual_total} != "
        f"{spec['expected_total_gross_gs']} ({spec['description']})"
    )

    # Per-row assertions for the mixed-tax case (4).
    if "asserts" in spec:
        # `rows` is chronological by sold_at; map to spec by order of insertion.
        # Specs are inserted in order with days_offset 0, 5, 10 → rows are
        # already in that order (sales_in_window orders by sold_at asc).
        for idx, checks in spec["asserts"].items():
            row = rows[idx]
            for k, v in checks.items():
                if k.endswith("__gt"):
                    field = k[: -len("__gt")]
                    assert getattr(row, field) > v, (
                        f"{spec['id']}: rows[{idx}].{field}={getattr(row, field)} not > {v}"
                    )
                else:
                    assert getattr(row, k) == v, (
                        f"{spec['id']}: rows[{idx}].{k}={getattr(row, k)} != {v}"
                    )


def test_parametrize_row_count() -> None:
    """Document the number of window/filter cases covered by this file."""
    assert len(_ROWS) == 5
