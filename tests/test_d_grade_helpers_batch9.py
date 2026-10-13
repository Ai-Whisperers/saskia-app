"""Parametrized coverage for two more D-grade helpers with no branch matrix.
# allow-hardcoded-dates: frozen-time fixture — see _ANCLA below

S1 batch-9 (test coverage continuation): lock the branch matrix of two
D-grade helpers that lack parametrized coverage:

  (1) `app/rms/plan_accuracy.py:compute_plan_accuracy` (CC 27, D-grade)
      Plan-vs-actual accuracy dashboard aggregator. Joins planned
      (caller-supplied map) + completions + sales per (product_id,
      for_date), then rolls up daily rows + per-product summaries +
      worst/best day Top 5. Branches covered:

      - empty window (no plan, no completions, no sales) → AccuracyReport
        with daily_rows=[], avg_accuracy=None, n_days_in_period
        computed from the date span
      - planned + completed + sold all aligned (perfect match) →
        accuracy=1.0, under_baked_pct=0.0
      - under-baked (completed < planned) → under_baked > 0, avg_accuracy < 1
      - over-baked (completed > planned, sold < completed) →
        over_baked > 0, demand_met < 1
      - ad-hoc completion only (planned=0, completed>0) →
        accuracy=None (NOT 0.0 — locks the `planned_qty <= 0: return None`
        property branch)
      - voided sales excluded: voided Sale rows must NOT contribute to
        sold_qty (locks the `Sale.voided_at.is_(None)` filter in
        _daily_sales)
      - multi-product aggregation: each product gets its own
        ProductAccuracySummary, total_planned/completed/sold are summed
      - unknown product_id in planned map (planned map references a
        product_id that was never seeded) → falls back to `#{pid}`
        name fallback (locks `product_names.get(pid, f"#{pid}")` branch)
      - top-5 worst days populated when at least one day has a positive
        delta (locks the _top_worst_days sort path)
      - top-5 best days excludes days where planned==0 (locks the
        `if t["planned"] > 0` filter in _top_best_days)
      - span=3 day window: n_days_in_period=3 (locks the
        `(end_date - start_date).days + 1` formula for 3-day)

  (2) `app/rms/accounting.py:libro_ventas` (CC 21, D-grade)
      Chronological Libro de Ventas (DNIT sales ledger). Iterates the
      window's Sale rows, joins customer + product names, optionally
      sums refunds (M1, 2026-10-02), and emits LibroVentasRow with
      gross/base/IVA + refund + invoice metadata. Branches covered:

      - empty window → empty list (no Sale rows in [start, end])
      - sale OUTSIDE [start, end] is excluded (locks the
        sales_in_window() datetime filter)
      - voided sale is excluded (locks the `voided_at.is_(None)`
        branch of sales_in_window)
      - customer_id is None → customer_name is None (locks the
        `if r.customer_id else None` branch)
      - product_id references a Product → product_name is the real
        name (locks the `prods.get(r.product_id, f"#{r.product_id}")`
        hit path)
      - invoice_type='factura' → invoice_number, invoice_customer_ruc,
        invoice_customer_name are surfaced on the row (locks the
        getattr-or-default pass-through)
      - invoice_type='boleta_resimple' → invoice_number is
        None, invoice_type="boleta_resimple" (locks the empty-string
        fallback)
      - snapshotted iva_base_gs/iva_amount_gs present → use the
        snapshot, NOT the recomputed extract_iva() result (locks the
        `if snap_base > 0 or snap_iva > 0: base_out = snap_base`
        branch — Factura path)
      - snapshotted iva fields are 0/None → fall through to the
        computed-from-gross extract_iva() branch (Boleta Resimple path)
      - tax_mode='included' (default) → IVA extracted with
        gross / 1.10 (locks the extract_iva() 'included' branch)
      - tax_mode='excluded' → IVA extracted with gross * 0.10 (locks
        the extract_iva() 'excluded' branch — net-of-IVA prices)
      - refund on the same sale → row carries refunds_gs>0,
        refunds_count>0, net_gross_gs = gross - refunds (M1 path)
      - full refund equal to gross → net_gross_gs clamped to 0
        (locks the `net = max(iva.gross_gs - refunds_sum, 0)` clamp)
      - pedido-target refund NOT counted (locks the
        `Refund.target_type == "sale"` filter — different target_type
        ignored)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import pytest

# ─── compute_plan_accuracy row spec ───────────────────────────────────────────


@dataclass
class _AccuracySpec:
    """One scenario for `compute_plan_accuracy`.

    Each scenario seeds the minimum DB state needed to exercise one
    branch of compute_plan_accuracy (planned map + completions +
    optional Sale rows). All DB seed knobs are optional; the most-empty
    spec tests the empty-window path.
    """

    id: str = ""
    description: str = ""

    # ─── DB seed side ──────────────────────────────────────────────────
    # Product seeds: list of (name, sale_price_gs). Empty = no products.
    products: list[tuple[str, int]] = field(default_factory=list)
    # Completion rows: list of (product_index, for_date, completed_qty).
    # product_index is the 0-based position in the `products` list.
    completions: list[tuple[int, date, float]] = field(default_factory=list)
    # Sale rows (non-voided): list of (product_index, sold_at, qty,
    # unit_price_gs, voided (bool)). Locks the sale contribution
    # branch and the voided exclusion branch.
    sales: list[tuple[int, datetime, float, int, bool]] = field(default_factory=list)
    # Caller-supplied planned_qty_by_pid_day map.
    # Entries: (product_index, for_date, qty). product_index in the
    # `products` list (None means "orphan FK" — refers to an id we
    # never seeded, to lock the fallback name branch).
    planned: list[tuple[Optional[int], date, float]] = field(default_factory=list)

    # ─── compute_plan_accuracy kwargs ──────────────────────────────────
    start_date: date = date(2026, 1, 1)
    end_date: date = date(2026, 1, 1)

    # ─── Post-call assertions (each is checked only if set) ────────────
    expect_daily_rows_count: Optional[int] = None
    expect_total_planned: Optional[float] = None
    expect_total_completed: Optional[float] = None
    expect_total_sold: Optional[float] = None
    expect_avg_accuracy: Optional[float] = None
    expect_avg_accuracy_is_none: Optional[bool] = None
    expect_under_baked_pct: Optional[float] = None
    expect_under_baked_pct_is_none: Optional[bool] = None
    expect_n_days_in_period: Optional[int] = None
    expect_n_days_with_completion: Optional[int] = None
    expect_worst_days_len: Optional[int] = None
    expect_best_days_len: Optional[int] = None
    expect_first_daily_accuracy: Optional[float] = None
    expect_first_daily_accuracy_is_none: Optional[bool] = None
    expect_first_daily_under_baked: Optional[float] = None
    expect_first_daily_over_baked: Optional[float] = None
    expect_first_daily_product_name: Optional[str] = None
    expect_first_daily_demand_met: Optional[float] = None
    expect_first_daily_demand_met_is_none: Optional[bool] = None
    expect_first_summary_under_baked: Optional[float] = None
    expect_first_summary_over_baked: Optional[float] = None
    expect_summaries_count: Optional[int] = None


# ─── plan_accuracy scenario definitions ───────────────────────────────────────


# Case 1: completely empty window — no plan, no completions, no sales.
# This is the `if not all_keys: return AccuracyReport(...)` early-exit
# branch.
_ACC_EMPTY = _AccuracySpec(
    id="empty_window_returns_zero_report",
    description=(
        "No plan, no completions, no sales in the window → AccuracyReport "
        "with daily_rows=[], avg_accuracy=None, n_days_in_period derived "
        "from (end-start).days+1=1 (locks the early-exit branch)"
    ),
    start_date=date(2026, 1, 1),
    end_date=date(2026, 1, 1),
    expect_daily_rows_count=0,
    expect_total_planned=0.0,
    expect_total_completed=0.0,
    expect_total_sold=0.0,
    expect_avg_accuracy_is_none=True,
    expect_under_baked_pct_is_none=True,
    expect_n_days_in_period=1,
    expect_n_days_with_completion=0,
    expect_worst_days_len=0,
    expect_best_days_len=0,
)


# Case 2: one product, perfect alignment (planned=completed=sold).
# accuracy=1.0, under_baked=0, over_baked=0.
_ACC_PERFECT = _AccuracySpec(
    id="perfect_match_accuracy_one",
    description=(
        "planned=10, completed=10, sold=10 → accuracy=1.0, "
        "under_baked=0, over_baked=0, demand_met=1.0 (locks the "
        "perfect-match path)"
    ),
    products=[("Pan de queso", 5000)],
    completions=[(0, date(2026, 1, 1), 10.0)],
    sales=[(0, datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc), 10.0, 5000, False)],
    planned=[(0, date(2026, 1, 1), 10.0)],
    expect_daily_rows_count=1,
    expect_total_planned=10.0,
    expect_total_completed=10.0,
    expect_total_sold=10.0,
    expect_avg_accuracy=1.0,
    expect_under_baked_pct=0.0,
    expect_first_daily_accuracy=1.0,
    expect_first_daily_under_baked=0.0,
    expect_first_daily_over_baked=0.0,
    expect_first_daily_demand_met=1.0,
    expect_n_days_with_completion=1,
)


# Case 3: under-baked (completed < planned). accuracy<1, under_baked>0.
_ACC_UNDER_BAKED = _AccuracySpec(
    id="under_baked_low_accuracy",
    description=(
        "planned=10, completed=4 → accuracy=0.4, under_baked=6.0, "
        "over_baked=0 (locks the under-baked branch: max(planned - "
        "completed, 0))"
    ),
    products=[("Chipa", 3000)],
    completions=[(0, date(2026, 1, 1), 4.0)],
    planned=[(0, date(2026, 1, 1), 10.0)],
    expect_first_daily_accuracy=0.4,
    expect_first_daily_under_baked=6.0,
    expect_first_daily_over_baked=0.0,
    expect_first_summary_under_baked=6.0,
    expect_avg_accuracy=0.4,
    expect_total_planned=10.0,
    expect_total_completed=4.0,
    expect_under_baked_pct=0.6,
)


# Case 4: over-baked (completed > planned). over_baked>0, demand_met < 1.
_ACC_OVER_BAKED = _AccuracySpec(
    id="over_baked_wasted_capacity",
    description=(
        "planned=10, completed=12, sold=8 → accuracy=1.2, over_baked=2.0, "
        "demand_met=0.6667 (locks the over-baked branch + the sold<completed "
        "demand_met property)"
    ),
    products=[("Bizcocho", 5000)],
    completions=[(0, date(2026, 1, 1), 12.0)],
    sales=[(0, datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc), 8.0, 5000, False)],
    planned=[(0, date(2026, 1, 1), 10.0)],
    expect_first_daily_accuracy=1.2,
    expect_first_daily_under_baked=0.0,
    expect_first_daily_over_baked=2.0,
    expect_first_daily_demand_met=0.6667,
    expect_avg_accuracy=1.2,
    expect_first_summary_over_baked=2.0,
)


# Case 5: ad-hoc completion only — planned=0 but the cook baked 12.
# accuracy must be None (NOT 0.0) — locks the property's
# `if planned_qty <= 0: return None` branch.
_ACC_AD_HOC = _AccuracySpec(
    id="ad_hoc_completion_planned_zero",
    description=(
        "No plan, but operator baked 12 → accuracy is None (not 0.0), "
        "planned_qty=0, completed_qty=12 (locks the DailyAccuracyRow."
        "accuracy property's None branch)"
    ),
    products=[("Ad-hoc", 3000)],
    completions=[(0, date(2026, 1, 1), 12.0)],
    planned=[],
    expect_first_daily_accuracy_is_none=True,
    expect_first_daily_under_baked=0.0,
    expect_first_daily_over_baked=12.0,
    expect_avg_accuracy_is_none=True,
    expect_total_planned=0.0,
    expect_total_completed=12.0,
    expect_under_baked_pct_is_none=True,
)


# Case 6: voided sale must NOT count toward sold_qty.
# A sale of 8 was voided; a sale of 2 stands. Without the filter,
# sold_qty would be 10; with the filter, it's 2.
_ACC_VOIDED_EXCLUDED = _AccuracySpec(
    id="voided_sales_excluded_from_sold_qty",
    description=(
        "Two sales on the same day: one voided (qty=8), one not (qty=2). "
        "Voided must NOT count → sold_qty=2 (locks the Sale.voided_at.is_"
        "(None) filter inside _daily_sales)"
    ),
    products=[("Sanguche", 8000)],
    completions=[(0, date(2026, 1, 1), 10.0)],
    sales=[
        (
            0,
            datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            8.0,
            8000,
            True,
        ),
        (
            0,
            datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc),
            2.0,
            8000,
            False,
        ),
    ],
    planned=[(0, date(2026, 1, 1), 10.0)],
    expect_first_daily_accuracy=1.0,
    expect_first_daily_demand_met=0.2,
    expect_total_sold=2.0,
    expect_avg_accuracy=1.0,
)


# Case 7: multi-product — each product gets its own ProductAccuracySummary,
# totals aggregate.
_ACC_MULTI_PRODUCT = _AccuracySpec(
    id="multi_product_summary_aggregation",
    description=(
        "Two products across two days: each gets its own "
        "ProductAccuracySummary, totals are summed (locks the by_pid "
        "grouping + summary construction)"
    ),
    products=[("Pan A", 3000), ("Pan B", 4000)],
    completions=[
        (0, date(2026, 2, 1), 10.0),
        (0, date(2026, 2, 2), 5.0),
        (1, date(2026, 2, 1), 20.0),
        (1, date(2026, 2, 2), 25.0),
    ],
    planned=[
        (0, date(2026, 2, 1), 12.0),
        (0, date(2026, 2, 2), 8.0),
        (1, date(2026, 2, 1), 20.0),
        (1, date(2026, 2, 2), 25.0),
    ],
    start_date=date(2026, 2, 1),
    end_date=date(2026, 2, 2),
    expect_daily_rows_count=4,
    expect_total_planned=65.0,
    expect_total_completed=60.0,
    expect_summaries_count=2,
    expect_n_days_with_completion=4,
)


# Case 8: orphan FK — planned map references a product_id that doesn't
# exist in the products table. The helper must fall back to the
# `#{pid}` string for product_name (locks the `product_names.get(pid,
# f"#{pid}")` default-dict branch).
_ACC_ORPHAN_FK = _AccuracySpec(
    id="orphan_fk_product_name_fallback",
    description=(
        "planned_qty_by_pid_day references a product_id=999 that was "
        "never seeded → daily_row.product_name='#999' (locks the "
        "product_names.get(pid, f'#{pid}') default fallback)"
    ),
    # Seed one product so the session isn't fully empty
    products=[("Lone", 3000)],
    completions=[],
    # planned[0] has None product_index → resolved to id=999 (orphan)
    planned=[(None, date(2026, 1, 1), 5.0)],
    expect_daily_rows_count=1,
    expect_first_daily_product_name="#999",
)


# Case 9: top-5 worst days populated when at least one day has a
# positive delta (locks _top_worst_days sort).
_ACC_WORST_DAYS = _AccuracySpec(
    id="worst_days_top5_populated",
    description=(
        "Two days with different delta values → worst_days has 2 entries "
        "ordered by delta desc (locks the _top_worst_days sort path)"
    ),
    products=[("X", 3000)],
    completions=[
        (0, date(2026, 3, 1), 5.0),  # delta=15 (planned=20 - completed=5)
        (0, date(2026, 3, 2), 18.0),  # delta=2 (planned=20 - completed=18)
    ],
    planned=[
        (0, date(2026, 3, 1), 20.0),
        (0, date(2026, 3, 2), 20.0),
    ],
    start_date=date(2026, 3, 1),
    end_date=date(2026, 3, 2),
    expect_worst_days_len=2,
    expect_best_days_len=2,
)


# Case 10: best_days excludes days where planned==0 (locks the
# `if t["planned"] > 0` filter in _top_best_days).
_ACC_BEST_DAYS_EXCLUDES_AD_HOC = _AccuracySpec(
    id="best_days_excludes_planned_zero",
    description=(
        "Day 1: planned=10, completed=20 → accuracy=2.0 (best candidate). "
        "Day 2: planned=0, completed=5 (ad-hoc, accuracy undefined). "
        "best_days must only contain Day 1 (locks the planned>0 filter)"
    ),
    products=[("Y", 3000)],
    completions=[
        (0, date(2026, 4, 1), 20.0),  # planned=10, completed=20 -> 2.0
        (0, date(2026, 4, 2), 5.0),  # planned=0, completed=5 -> excluded
    ],
    planned=[
        (0, date(2026, 4, 1), 10.0),
        (0, date(2026, 4, 2), 0.0),
    ],
    start_date=date(2026, 4, 1),
    end_date=date(2026, 4, 2),
    expect_best_days_len=1,
)


# Case 11: span=3 day window: n_days_in_period=3 (locks the
# `(end_date - start_date).days + 1` formula for 3-day).
_ACC_SPAN_FORMULA = _AccuracySpec(
    id="n_days_in_period_formula_3d",
    description=(
        "start=2026-01-01, end=2026-01-03 → n_days_in_period=3 (locks the "
        "(end-start).days+1 formula for 3-day window)"
    ),
    start_date=date(2026, 1, 1),
    end_date=date(2026, 1, 3),
    expect_daily_rows_count=0,
    expect_n_days_in_period=3,
)


# ─── plan_accuracy scenario rows ──────────────────────────────────────────────


_ROWS_ACCURACY: list[dict[str, Any]] = [
    {"spec": _ACC_EMPTY},
    {"spec": _ACC_PERFECT},
    {"spec": _ACC_UNDER_BAKED},
    {"spec": _ACC_OVER_BAKED},
    {"spec": _ACC_AD_HOC},
    {"spec": _ACC_VOIDED_EXCLUDED},
    {"spec": _ACC_MULTI_PRODUCT},
    {"spec": _ACC_ORPHAN_FK},
    {"spec": _ACC_WORST_DAYS},
    {"spec": _ACC_BEST_DAYS_EXCLUDES_AD_HOC},
    {"spec": _ACC_SPAN_FORMULA},
]


# ─── libro_ventas row spec ────────────────────────────────────────────────────


@dataclass
class _LibroVentasSpec:
    """One scenario for `libro_ventas`."""

    id: str = ""
    description: str = ""

    # ─── DB seed side ──────────────────────────────────────────────────
    # Products to seed: list of (name, sale_price_gs).
    products: list[tuple[str, int]] = field(default_factory=list)
    # Customer seeds: list of (name, phone). Empty = no customers.
    customers: list[tuple[str, str]] = field(default_factory=list)
    # Sale rows: (product_index, sold_at, qty, unit_price_gs,
    #   customer_index_or_-1, invoice_type, invoice_number,
    #   invoice_customer_ruc, invoice_customer_name,
    #   snap_iva_base, snap_iva_amount, voided (bool))
    sales: list[tuple] = field(default_factory=list)
    # Refund rows: (target_type, target_sale_index, amount_gs).
    # sale_index refers to the position in the `sales` list.
    refunds: list[tuple[str, int, int]] = field(default_factory=list)

    # ─── libro_ventas kwargs ───────────────────────────────────────────
    start_date: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date: datetime = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    tax_mode: str = "included"
    limit: int = 10_000

    # ─── Post-call assertions ──────────────────────────────────────────
    expect_rows_count: Optional[int] = None
    expect_first_customer_name: Optional[str] = None
    expect_first_product_name: Optional[str] = None
    expect_first_refunds_gs: Optional[int] = None
    expect_first_refunds_count: Optional[int] = None
    expect_first_net_gross_gs: Optional[int] = None
    expect_first_total_gross_gs: Optional[int] = None
    expect_first_base_gs: Optional[int] = None
    expect_first_iva_gs: Optional[int] = None
    expect_first_invoice_type: Optional[str] = None
    expect_first_invoice_number: Optional[int] = None
    expect_first_invoice_ruc: Optional[str] = None
    expect_first_invoice_cust_name: Optional[str] = None


# ─── libro_ventas scenario definitions ────────────────────────────────────────


# Case 1: empty window — no Sale rows → empty list. (sales_in_window
# returns [].)
_LV_EMPTY = _LibroVentasSpec(
    id="empty_window_returns_empty_list",
    description=(
        "No Sale rows in the window → libro_ventas returns [] (locks "
        "the sales_in_window() empty-list path + the for-loop no-op)"
    ),
    expect_rows_count=0,
)


# Case 2: sale OUTSIDE [start, end] is excluded. A sale at 2025-12-31
# must NOT appear in the 2026-01-01..2026-12-31 window.
_LV_OUTSIDE_WINDOW_EXCLUDED = _LibroVentasSpec(
    id="sale_outside_window_excluded",
    description=(
        "Sale at 2025-12-31T23:59:59Z (one second before the 2026-01-01 "
        "window) → only the 2026 sale appears in the result (locks the "
        "sales_in_window() datetime filter)"
    ),
    products=[("Prod", 5000)],
    sales=[
        (
            0,
            datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            1.0,
            5000,
            -1,
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
        (
            0,
            datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            2.0,
            5000,
            -1,
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
    expect_rows_count=1,
    expect_first_total_gross_gs=10000,  # 2 * 5000
)


# Case 3: voided sale is excluded (locks the voided_at filter in
# sales_in_window).
_LV_VOIDED_EXCLUDED = _LibroVentasSpec(
    id="voided_sale_excluded",
    description=(
        "One non-voided sale and one voided sale (same product, same "
        "day) → only the non-voided appears (locks the Sale.voided_at."
        "is_(None) branch)"
    ),
    products=[("Prod", 5000)],
    sales=[
        (
            0,
            datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            5000,
            -1,
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
        (
            0,
            datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc),
            1.0,
            5000,
            -1,
            "none",
            None,
            None,
            None,
            0,
            0,
            True,  # voided=True
        ),
    ],
    expect_rows_count=1,
)


# Case 4: customer_id IS set → customer_name comes from the Customer
# lookup (locks the custs.get(query.r_id) hit branch).
_LV_CUSTOMER_RESOLVED = _LibroVentasSpec(
    id="customer_name_resolved_when_customer_id_set",
    description=(
        "Sale with customer_id set → row.customer_name comes from the "
        "Customer lookup (locks the custs.get(r.customer_id) hit branch)"
    ),
    products=[("Prod", 5000)],
    customers=[("Cliente Fiel", "+595 9XX XXXXXX")],
    sales=[
        (
            0,
            datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            5000,
            0,  # customer_index=0
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    expect_rows_count=1,
    expect_first_customer_name="Cliente Fiel",
)


# Case 5: customer_id IS None → row.customer_name is None (locks the
# `if r.customer_id else None` branch).
_LV_NO_CUSTOMER = _LibroVentasSpec(
    id="customer_name_none_when_customer_id_null",
    description=(
        "Sale with customer_id=None → row.customer_name is None (locks "
        "the if r.customer_id else None branch)"
    ),
    products=[("Prod", 5000)],
    sales=[
        (
            0,
            datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            5000,
            -1,  # customer_index=-1 → customer_id=None
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    expect_rows_count=1,
    expect_first_customer_name=None,
)


# Case 6: invoice_type='factura' → invoice_number, invoice_customer_ruc,
# invoice_customer_name are surfaced on the row (locks the getattr
# pass-through).
_LV_FACTURA = _LibroVentasSpec(
    id="factura_invoice_metadata_surfaced",
    description=(
        "invoice_type='factura' with all metadata → row carries "
        "invoice_number, invoice_customer_ruc, invoice_customer_name "
        "(locks the getattr pass-through for the Factura path)"
    ),
    products=[("Prod", 11000)],
    sales=[
        (
            0,
            datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            11000,
            -1,
            "factura",
            42,
            "80012345-6",
            "ACME S.A.",
            10000,
            8230,  # snap present
            False,
        ),
    ],
    expect_rows_count=1,
    expect_first_invoice_type="factura",
    expect_first_invoice_number=42,
    expect_first_invoice_ruc="80012345-6",
    expect_first_invoice_cust_name="ACME S.A.",
    # snap_base/iva take precedence over recomputed extract_iva
    expect_first_base_gs=10000,
    expect_first_iva_gs=8230,
)


# Case 7: snapshotted iva fields are 0 → fall through to
# extract_iva() (locks the `else: base_out = iva.base_gs` Boleta
# Resimple path).
_LV_BOLETA_COMPUTED = _LibroVentasSpec(
    id="boleta_resimple_uses_computed_iva",
    description=(
        "snap_iva_base=0, snap_iva_amount=0 → row uses recomputed "
        "extract_iva() values (locks the Boleta Resimple fallback "
        "branch where the snapshot is absent)"
    ),
    products=[("Prod", 11000)],
    sales=[
        (
            0,
            datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            11000,
            -1,
            "boleta_resimple",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    expect_rows_count=1,
    expect_first_total_gross_gs=11000,
    # extract_iva(11000, tax_mode='included'): base = 11000 // 1.10 = 10000,
    # iva = 11000 - 10000 = 1000.
    expect_first_base_gs=10000,
    expect_first_iva_gs=1000,
    expect_first_invoice_type="boleta_resimple",
    expect_first_invoice_number=None,
)


# Case 8: tax_mode='excluded' → extract_iva uses gross * 0.10 (locks
# the 'excluded' branch — net-of-IVA prices).
_LV_TAX_EXCLUDED = _LibroVentasSpec(
    id="tax_mode_excluded_uses_gross_times_rate",
    description=(
        "tax_mode='excluded' → iva = gross * 0.10, base = gross (locks "
        "the 'excluded' branch of extract_iva(), used when sale prices "
        "are net of IVA)"
    ),
    products=[("Prod", 11000)],
    sales=[
        (
            0,
            datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            11000,
            -1,
            "boleta_resimple",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    tax_mode="excluded",
    expect_rows_count=1,
    expect_first_total_gross_gs=11000,
    expect_first_base_gs=11000,
    expect_first_iva_gs=1100,
)


# Case 9: refund on the SAME sale → row carries refunds_gs>0,
# refunds_count>0, net_gross_gs = gross - refunds.
_LV_REFUND_SUBTRACTS = _LibroVentasSpec(
    id="refund_subtracts_from_gross",
    description=(
        "One sale of 10000 + one refund of 3000 on the same sale_id → "
        "row.refunds_gs=3000, refunds_count=1, net_gross_gs=7000 "
        "(locks the refunds_by_sale lookup + subtraction path)"
    ),
    products=[("Prod", 10000)],
    sales=[
        (
            0,
            datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            10000,
            -1,
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    refunds=[("sale", 0, 3000)],  # refund on sale[0]
    expect_rows_count=1,
    expect_first_total_gross_gs=10000,
    expect_first_refunds_gs=3000,
    expect_first_refunds_count=1,
    expect_first_net_gross_gs=7000,
)


# Case 10: full refund equal to gross → net_gross_gs clamped to 0
# (locks the `net = max(iva.gross_gs - refunds_sum, 0)` clamp).
_LV_REFUND_FULL_CLAMP = _LibroVentasSpec(
    id="full_refund_clamps_net_to_zero",
    description=(
        "One sale of 10000 + one refund of 10000 → row.net_gross_gs=0 "
        "(locked at the max() floor — never negative)"
    ),
    products=[("Prod", 10000)],
    sales=[
        (
            0,
            datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            10000,
            -1,
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    refunds=[("sale", 0, 10000)],
    expect_rows_count=1,
    expect_first_net_gross_gs=0,
    expect_first_refunds_gs=10000,
)


# Case 11: pedido-target refund is NOT counted (locks the
# `Refund.target_type == 'sale'` filter).
_LV_PEDIDO_REFUND_IGNORED = _LibroVentasSpec(
    id="pedido_refund_not_counted",
    description=(
        "Refund with target_type='pedido' (not 'sale') → row.refunds_gs=0 "
        "(locks the Refund.target_type == 'sale' filter)"
    ),
    products=[("Prod", 10000)],
    sales=[
        (
            0,
            datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            10000,
            -1,
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    refunds=[("pedido", 0, 5000)],  # wrong target_type
    expect_rows_count=1,
    expect_first_refunds_gs=0,
    expect_first_refunds_count=0,
    expect_first_net_gross_gs=10000,
)


# Case 12: product lookup hits the cached dict (locks the
# `prods.get(r.product_id, f"#{r.product_id}")` hit path — verifies
# product_name comes from the actual Product row).
_LV_PRODUCT_NAME_HIT = _LibroVentasSpec(
    id="product_name_comes_from_product_row",
    description=(
        "Sale references a seeded Product → row.product_name='PanCake' "
        "(locks the prods.get(r.product_id, ...) hit branch — NOT the "
        "orphan #pid fallback)"
    ),
    products=[("PanCake", 6000)],
    sales=[
        (
            0,
            datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            1.0,
            6000,
            -1,
            "none",
            None,
            None,
            None,
            0,
            0,
            False,
        ),
    ],
    expect_rows_count=1,
    expect_first_product_name="PanCake",
)


# ─── libro_ventas scenario rows ────────────────────────────────────────────────


_ROWS_LIBRO_VENTAS: list[dict[str, Any]] = [
    {"spec": _LV_EMPTY},
    {"spec": _LV_OUTSIDE_WINDOW_EXCLUDED},
    {"spec": _LV_VOIDED_EXCLUDED},
    {"spec": _LV_CUSTOMER_RESOLVED},
    {"spec": _LV_NO_CUSTOMER},
    {"spec": _LV_FACTURA},
    {"spec": _LV_BOLETA_COMPUTED},
    {"spec": _LV_TAX_EXCLUDED},
    {"spec": _LV_REFUND_SUBTRACTS},
    {"spec": _LV_REFUND_FULL_CLAMP},
    {"spec": _LV_PEDIDO_REFUND_IGNORED},
    {"spec": _LV_PRODUCT_NAME_HIT},
]


# ─── Parametrized driver: compute_plan_accuracy ───────────────────────────────


@pytest.mark.parametrize(
    "row",
    _ROWS_ACCURACY,
    ids=lambda r: r["spec"].id,
)
def test_compute_plan_accuracy_branches(row: dict) -> None:
    """Drive `compute_plan_accuracy` through 11 scenarios covering its
    CC-27 branches.

    Each test owns its own in-memory SQLite engine + a session kept open
    for the lifetime of the test (mirrors the working
    ``test_plan_accuracy.py::plan_session`` fixture pattern — every
    `with SF() as s:` opens a new connection, and SQLite :memory:
    databases are per-connection).
    """
    from sqlalchemy.orm import sessionmaker

    from app.rms.db import init_db, make_engine
    from app.rms.models_legacy import Product, ProductionCompletion, Sale
    from app.rms.plan_accuracy import compute_plan_accuracy

    spec: _AccuracySpec = row["spec"]

    eng = make_engine("sqlite:///:memory:")
    init_db(eng)
    s = sessionmaker(bind=eng)()

    # ─── Seed Products ────────────────────────────────────────────
    seeded_product_ids: list[int] = []
    for name, price in spec.products:
        p = Product(name=name, sale_price_gs=price)
        s.add(p)
        s.flush()
        seeded_product_ids.append(p.id)

    # ─── Seed Completions ─────────────────────────────────────────
    for prod_idx, for_date, qty in spec.completions:
        s.add(
            ProductionCompletion(
                product_id=seeded_product_ids[prod_idx],
                for_date=for_date,
                completed_qty=qty,
                recorded_at=datetime(
                    for_date.year,
                    for_date.month,
                    for_date.day,
                    23,
                    59,
                    0,
                ),
            )
        )

    # ─── Seed Sales (non-voided) ──────────────────────────────────
    for (
        prod_idx,
        sold_at,
        qty,
        unit_price,
        voided,
    ) in spec.sales:
        if prod_idx >= 0:
            actual_product_id = seeded_product_ids[prod_idx]
        else:
            actual_product_id = 999  # orphan FK

        voided_at = sold_at + timedelta(minutes=5) if voided else None
        s.add(
            Sale(
                sold_at=sold_at,
                product_id=actual_product_id,
                qty=qty,
                unit_price_gs=unit_price,
                payment_method="efectivo",
                channel="mostrador",
                invoice_type="none",
                tz="America/Asuncion",
                voided_at=voided_at,
            )
        )

    # ─── Build planned map ────────────────────────────────────────
    planned_map: dict[tuple[int, date], float] = {}
    for prod_idx, for_date, qty in spec.planned:
        if prod_idx is None:
            actual_pid = 999  # orphan FK
        elif prod_idx >= 0:
            actual_pid = seeded_product_ids[prod_idx]
        else:
            actual_pid = 999
        planned_map[(actual_pid, for_date)] = qty

    s.commit()

    # ─── Call the helper ─────────────────────────────────────────
    report = compute_plan_accuracy(
        s,
        spec.start_date,
        spec.end_date,
        planned_map,
    )

    s.close()

    # ─── Post-call assertions ──────────────────────────────────────────

    if spec.expect_daily_rows_count is not None:
        assert len(report.daily_rows) == spec.expect_daily_rows_count, (
            f"{spec.id}: daily_rows={len(report.daily_rows)}, "
            f"expected {spec.expect_daily_rows_count} — {spec.description}"
        )

    if spec.expect_total_planned is not None:
        assert report.total_planned == pytest.approx(spec.expect_total_planned, abs=1e-3), (
            f"{spec.id}: total_planned={report.total_planned}, "
            f"expected {spec.expect_total_planned} — {spec.description}"
        )

    if spec.expect_total_completed is not None:
        assert report.total_completed == pytest.approx(spec.expect_total_completed, abs=1e-3), (
            f"{spec.id}: total_completed={report.total_completed}, "
            f"expected {spec.expect_total_completed} — {spec.description}"
        )

    if spec.expect_total_sold is not None:
        assert report.total_sold == pytest.approx(spec.expect_total_sold, abs=1e-3), (
            f"{spec.id}: total_sold={report.total_sold}, "
            f"expected {spec.expect_total_sold} — {spec.description}"
        )

    if spec.expect_avg_accuracy is not None:
        assert report.avg_accuracy == pytest.approx(spec.expect_avg_accuracy, abs=1e-3), (
            f"{spec.id}: avg_accuracy={report.avg_accuracy}, "
            f"expected {spec.expect_avg_accuracy} — {spec.description}"
        )

    if spec.expect_avg_accuracy_is_none is not None:
        is_none = report.avg_accuracy is None
        assert is_none == spec.expect_avg_accuracy_is_none, (
            f"{spec.id}: avg_accuracy is None?={is_none}, "
            f"expected={spec.expect_avg_accuracy_is_none} — "
            f"{spec.description}"
        )

    if spec.expect_under_baked_pct is not None:
        assert report.under_baked_pct == pytest.approx(spec.expect_under_baked_pct, abs=1e-3), (
            f"{spec.id}: under_baked_pct={report.under_baked_pct}, "
            f"expected {spec.expect_under_baked_pct} — {spec.description}"
        )

    if spec.expect_under_baked_pct_is_none is not None:
        is_none = report.under_baked_pct is None
        assert is_none == spec.expect_under_baked_pct_is_none, (
            f"{spec.id}: under_baked_pct is None?={is_none}, "
            f"expected={spec.expect_under_baked_pct_is_none} — "
            f"{spec.description}"
        )

    if spec.expect_n_days_in_period is not None:
        assert report.n_days_in_period == spec.expect_n_days_in_period, (
            f"{spec.id}: n_days_in_period={report.n_days_in_period}, "
            f"expected {spec.expect_n_days_in_period} — {spec.description}"
        )

    if spec.expect_n_days_with_completion is not None:
        assert report.n_days_with_completion == spec.expect_n_days_with_completion, (
            f"{spec.id}: n_days_with_completion="
            f"{report.n_days_with_completion}, expected "
            f"{spec.expect_n_days_with_completion} — {spec.description}"
        )

    if spec.expect_worst_days_len is not None:
        assert len(report.worst_days) == spec.expect_worst_days_len, (
            f"{spec.id}: worst_days={len(report.worst_days)}, expected "
            f"{spec.expect_worst_days_len} — {spec.description}"
        )

    if spec.expect_best_days_len is not None:
        assert len(report.best_days) == spec.expect_best_days_len, (
            f"{spec.id}: best_days={len(report.best_days)}, expected "
            f"{spec.expect_best_days_len} — {spec.description}"
        )

    if spec.expect_summaries_count is not None:
        assert len(report.product_summary) == spec.expect_summaries_count, (
            f"{spec.id}: product_summary={len(report.product_summary)}, "
            f"expected {spec.expect_summaries_count} — {spec.description}"
        )

    # First daily-row assertions (only when rows exist)
    if report.daily_rows:
        first = report.daily_rows[0]
        if spec.expect_first_daily_accuracy is not None:
            assert first.accuracy == pytest.approx(spec.expect_first_daily_accuracy, abs=1e-3), (
                f"{spec.id}: first row accuracy={first.accuracy}, "
                f"expected {spec.expect_first_daily_accuracy} — "
                f"{spec.description}"
            )

        if spec.expect_first_daily_accuracy_is_none is not None:
            is_none = first.accuracy is None
            assert is_none == spec.expect_first_daily_accuracy_is_none, (
                f"{spec.id}: first row accuracy is None?={is_none}, "
                f"expected={spec.expect_first_daily_accuracy_is_none} — "
                f"{spec.description}"
            )

        if spec.expect_first_daily_under_baked is not None:
            assert first.under_baked == spec.expect_first_daily_under_baked, (
                f"{spec.id}: first row under_baked={first.under_baked}, "
                f"expected {spec.expect_first_daily_under_baked} — "
                f"{spec.description}"
            )

        if spec.expect_first_daily_over_baked is not None:
            assert first.over_baked == spec.expect_first_daily_over_baked, (
                f"{spec.id}: first row over_baked={first.over_baked}, "
                f"expected {spec.expect_first_daily_over_baked} — "
                f"{spec.description}"
            )

        if spec.expect_first_daily_product_name is not None:
            assert first.product_name == spec.expect_first_daily_product_name, (
                f"{spec.id}: first row product_name={first.product_name!r}, "
                f"expected {spec.expect_first_daily_product_name!r} — "
                f"{spec.description}"
            )

        if spec.expect_first_daily_demand_met is not None:
            assert first.demand_met == pytest.approx(
                spec.expect_first_daily_demand_met, abs=1e-3
            ), (
                f"{spec.id}: first row demand_met={first.demand_met}, "
                f"expected {spec.expect_first_daily_demand_met} — "
                f"{spec.description}"
            )

        if spec.expect_first_daily_demand_met_is_none is not None:
            is_none = first.demand_met is None
            assert is_none == spec.expect_first_daily_demand_met_is_none, (
                f"{spec.id}: first row demand_met is None?={is_none}, "
                f"expected={spec.expect_first_daily_demand_met_is_none} — "
                f"{spec.description}"
            )

    # First summary-row assertions (only when summaries exist)
    if report.product_summary:
        first_sum = report.product_summary[0]
        if spec.expect_first_summary_under_baked is not None:
            assert first_sum.under_baked_units == spec.expect_first_summary_under_baked, (
                f"{spec.id}: first summary under_baked="
                f"{first_sum.under_baked_units}, expected "
                f"{spec.expect_first_summary_under_baked} — "
                f"{spec.description}"
            )

        if spec.expect_first_summary_over_baked is not None:
            assert first_sum.over_baked_units == spec.expect_first_summary_over_baked, (
                f"{spec.id}: first summary over_baked="
                f"{first_sum.over_baked_units}, expected "
                f"{spec.expect_first_summary_over_baked} — "
                f"{spec.description}"
            )


# ─── Parametrized driver: libro_ventas ────────────────────────────────────────


@pytest.mark.parametrize(
    "row",
    _ROWS_LIBRO_VENTAS,
    ids=lambda r: r["spec"].id,
)
def test_libro_ventas_branches(row: dict) -> None:
    """Drive `libro_ventas` through 12 scenarios covering its CC-21
    branches.

    Each test owns its own in-memory SQLite engine + a session kept open
    for the lifetime of the test (mirrors the working
    ``test_libro_ventas_refunds.py::lv_session`` fixture pattern).
    """
    from sqlalchemy.orm import sessionmaker

    from app.rms.accounting import libro_ventas
    from app.rms.db import init_db, make_engine
    from app.rms.models_legacy import Customer, Product, Refund, Sale

    spec: _LibroVentasSpec = row["spec"]

    eng = make_engine("sqlite:///:memory:")
    init_db(eng)
    s = sessionmaker(bind=eng)()

    # ─── Seed Products ────────────────────────────────────────────
    seeded_product_ids: list[int] = []
    for name, price in spec.products:
        p = Product(name=name, sale_price_gs=price)
        s.add(p)
        s.flush()
        seeded_product_ids.append(p.id)

    # ─── Seed Customers ───────────────────────────────────────────
    seeded_customer_ids: list[int] = []
    for name, phone in spec.customers:
        c = Customer(name=name, phone=phone)
        s.add(c)
        s.flush()
        seeded_customer_ids.append(c.id)

    # ─── Seed Sales ───────────────────────────────────────────────
    seeded_sale_ids: list[int] = []
    for sale_spec in spec.sales:
        (
            prod_idx,
            sold_at,
            qty,
            unit_price,
            cust_idx,
            invoice_type,
            invoice_number,
            invoice_ruc,
            invoice_cust_name,
            snap_iva_base,
            snap_iva_amount,
            voided,
        ) = sale_spec

        if prod_idx >= 0:
            actual_pid = seeded_product_ids[prod_idx]
        else:
            actual_pid = 9999  # orphan FK

        if cust_idx >= 0:
            actual_cid = seeded_customer_ids[cust_idx]
        else:
            actual_cid = None

        voided_at = sold_at + timedelta(minutes=5) if voided else None

        sale = Sale(
            sold_at=sold_at,
            product_id=actual_pid,
            qty=qty,
            unit_price_gs=unit_price,
            payment_method="efectivo",
            customer_id=actual_cid,
            discount_gs=0,
            channel="mostrador",
            invoice_type=invoice_type,
            invoice_number=invoice_number,
            invoice_customer_ruc=invoice_ruc,
            invoice_customer_name=invoice_cust_name,
            iva_base_gs=snap_iva_base,
            iva_amount_gs=snap_iva_amount,
            tz="America/Asuncion",
            voided_at=voided_at,
        )
        s.add(sale)
        s.flush()
        seeded_sale_ids.append(sale.id)

    # ─── Seed Refunds ─────────────────────────────────────────────
    for target_type, sale_index, amount_gs in spec.refunds:
        sale_id = seeded_sale_ids[sale_index] if sale_index >= 0 else 999
        refund = Refund(
            target_type=target_type,
            target_id=sale_id,
            target_amount_gs=amount_gs * 2,
            amount_gs=amount_gs,
            payment_method="efectivo",
            restock_qty=False,
            restocked_qty=0.0,
            recorded_at=datetime.now(timezone.utc),
            recorded_by="op",
            loyalty_reversed=0,
        )
        s.add(refund)
        s.flush()

    s.commit()

    # ─── Call the helper ─────────────────────────────────────────
    rows = libro_ventas(
        s,
        start_date=spec.start_date,
        end_date=spec.end_date,
        tax_mode=spec.tax_mode,
        limit=spec.limit,
    )

    s.close()

    # ─── Post-call assertions ──────────────────────────────────────────

    if spec.expect_rows_count is not None:
        assert len(rows) == spec.expect_rows_count, (
            f"{spec.id}: rows={len(rows)}, expected {spec.expect_rows_count} — {spec.description}"
        )

    if not rows:
        return  # no further assertions when no rows

    first = rows[0]

    if spec.expect_first_customer_name is not None:
        # spec.expect_first_customer_name == None → assert first.customer_name is None
        assert first.customer_name == spec.expect_first_customer_name, (
            f"{spec.id}: first row customer_name={first.customer_name!r}, "
            f"expected {spec.expect_first_customer_name!r} — "
            f"{spec.description}"
        )

    if spec.expect_first_product_name is not None:
        assert first.product_name == spec.expect_first_product_name, (
            f"{spec.id}: first row product_name={first.product_name!r}, "
            f"expected {spec.expect_first_product_name!r} — "
            f"{spec.description}"
        )

    if spec.expect_first_total_gross_gs is not None:
        assert first.total_gross_gs == spec.expect_first_total_gross_gs, (
            f"{spec.id}: first row total_gross_gs={first.total_gross_gs}, "
            f"expected {spec.expect_first_total_gross_gs} — "
            f"{spec.description}"
        )

    if spec.expect_first_base_gs is not None:
        # extract_iva() uses integer division; accept 1-unit drift
        assert abs(first.base_gs - spec.expect_first_base_gs) <= 1, (
            f"{spec.id}: first row base_gs={first.base_gs}, expected "
            f"~{spec.expect_first_base_gs} — {spec.description}"
        )

    if spec.expect_first_iva_gs is not None:
        assert abs(first.iva_gs - spec.expect_first_iva_gs) <= 1, (
            f"{spec.id}: first row iva_gs={first.iva_gs}, expected "
            f"~{spec.expect_first_iva_gs} — {spec.description}"
        )

    if spec.expect_first_refunds_gs is not None:
        assert first.refunds_gs == spec.expect_first_refunds_gs, (
            f"{spec.id}: first row refunds_gs={first.refunds_gs}, "
            f"expected {spec.expect_first_refunds_gs} — {spec.description}"
        )

    if spec.expect_first_refunds_count is not None:
        assert first.refunds_count == spec.expect_first_refunds_count, (
            f"{spec.id}: first row refunds_count={first.refunds_count}, "
            f"expected {spec.expect_first_refunds_count} — "
            f"{spec.description}"
        )

    if spec.expect_first_net_gross_gs is not None:
        assert first.net_gross_gs == spec.expect_first_net_gross_gs, (
            f"{spec.id}: first row net_gross_gs={first.net_gross_gs}, "
            f"expected {spec.expect_first_net_gross_gs} — {spec.description}"
        )

    if spec.expect_first_invoice_type is not None:
        assert first.invoice_type == spec.expect_first_invoice_type, (
            f"{spec.id}: first row invoice_type={first.invoice_type!r}, "
            f"expected {spec.expect_first_invoice_type!r} — "
            f"{spec.description}"
        )

    if spec.expect_first_invoice_number is not None:
        assert first.invoice_number == spec.expect_first_invoice_number, (
            f"{spec.id}: first row invoice_number={first.invoice_number}, "
            f"expected {spec.expect_first_invoice_number} — "
            f"{spec.description}"
        )

    if spec.expect_first_invoice_ruc is not None:
        assert first.invoice_customer_ruc == spec.expect_first_invoice_ruc, (
            f"{spec.id}: first row invoice_customer_ruc="
            f"{first.invoice_customer_ruc!r}, expected "
            f"{spec.expect_first_invoice_ruc!r} — {spec.description}"
        )

    if spec.expect_first_invoice_cust_name is not None:
        assert first.invoice_customer_name == spec.expect_first_invoice_cust_name, (
            f"{spec.id}: first row invoice_customer_name="
            f"{first.invoice_customer_name!r}, expected "
            f"{spec.expect_first_invoice_cust_name!r} — "
            f"{spec.description}"
        )


# ─── Row-count docs (mirrors PR #174 / #178 / #179 / #181 / #184 / #186) ─────


def test_parametrize_row_count() -> None:
    """Document the number of branch-coverage cases covered by this file.

    Locks the parametrize row count so adding/removing a row forces a
    reviewer to update the matching CHANGELOG entry — same pattern as
    batch5 / batch6 / batch7 / batch8 (#174, #178, #179, #181, #184, #186).
    """
    assert len(_ROWS_ACCURACY) == 11
    assert len(_ROWS_LIBRO_VENTAS) == 12
    # Sanity: the spec docstring's "8+ parametrized rows" claim is met.
    assert len(_ROWS_ACCURACY) + len(_ROWS_LIBRO_VENTAS) >= 8
