"""Parametrized pure-helper tests for tests/test_production_demand.py.

Phase 2 increment #3 (S1 batch2 parametrize expansion): demo the dedup
pattern on the 2nd-largest file in the suite (914 lines). The most repeated
pure-helper shape is `compute_demand_qty(qty_forecast=..., qty_pedidos=...,
seasonal_multiplier=...) → assert total == ... and evento == ...` (5
cases) plus `split_pedidos_status(pending_qty, confirmed_qty, ready_qty) →
assert total == ... and confirmed == ...` (3 cases). This file subsumes
them into two parametrized drivers.

ADDITIVE only — the originals in test_production_demand.py remain
untouched. If a future batch confirms identical behavior across N runs, the
originals can be deleted in a follow-up commit.

Hypothesis property tests, integration tests (session_factory), and HTTP
tests (authed_client) are intentionally NOT parametrized here — they have
unique fixture setups and don't benefit from the simple data-table driver.
"""

from __future__ import annotations

import pytest

from app.rms.production_demand import compute_demand_qty, split_pedidos_status

# ─── Parametrize rows ─────────────────────────────────────────────
#
# Each row is one complete spec for one originally hand-written
# `(total, evento) == compute_demand_qty(...)` or
# `(total, confirmed) == split_pedidos_status(...)` assertion.
_COMPUTE_CASES: list[dict] = [
    {
        "id": "compute_basic_no_multiplier",
        "qty_forecast": 10.0,
        "qty_pedidos": 5.0,
        "seasonal_multiplier": 1.0,
        "expected_total": 15.0,
        "expected_evento": 0.0,
        "description": "plain sum: forecast=10, pedidos=5 → total=15, evento=0",
    },
    {
        "id": "compute_with_multiplier",
        "qty_forecast": 10.0,
        "qty_pedidos": 5.0,
        "seasonal_multiplier": 2.0,
        "expected_total": 25.0,
        "expected_evento": 10.0,
        "description": "seasonal_multiplier=2 boosts forecast (10*2=20), total=25, evento=10",
    },
    {
        "id": "compute_zero_forecast",
        "qty_forecast": 0.0,
        "qty_pedidos": 7.5,
        "seasonal_multiplier": 1.0,
        "expected_total": 7.5,
        "expected_evento": 0.0,
        "description": "zero forecast + pedidos → total=pedidos",
    },
    {
        "id": "compute_zero_pedidos",
        "qty_forecast": 8.0,
        "qty_pedidos": 0.0,
        "seasonal_multiplier": 1.5,
        "expected_total": 12.0,
        "expected_evento": 4.0,
        "description": "zero pedidos, multiplier=1.5 boosts forecast (8*1.5=12), evento=4",
    },
    {
        "id": "compute_negative_inputs_clamped",
        "qty_forecast": -5.0,
        "qty_pedidos": -3.0,
        "seasonal_multiplier": 0.5,
        "expected_total": 0.0,
        "expected_evento": 0.0,
        "description": "negative inputs clamped to 0, multiplier<=0 → 1.0",
    },
]


_SPLIT_CASES: list[dict] = [
    {
        "id": "split_basic_pending_confirmed_ready",
        "pending_qty": 3.0,
        "confirmed_qty": 5.0,
        "ready_qty": 2.0,
        "expected_total": 10.0,
        "expected_confirmed": 7.0,
        "description": "pending=3 + confirmed=5 + ready=2 → total=10, confirmed=7",
    },
    {
        "id": "split_only_pending",
        "pending_qty": 5.0,
        "confirmed_qty": 0.0,
        "ready_qty": 0.0,
        "expected_total": 5.0,
        "expected_confirmed": 0.0,
        "description": "all pending → confirmed=0, total=pending",
    },
    {
        "id": "split_only_confirmed_and_ready",
        "pending_qty": 0.0,
        "confirmed_qty": 4.0,
        "ready_qty": 6.0,
        "expected_total": 10.0,
        "expected_confirmed": 10.0,
        "description": "no pending → total == confirmed (riesgo gap 0)",
    },
]


@pytest.mark.parametrize("spec", _COMPUTE_CASES, ids=lambda s: s["id"])
def test_compute_demand_qty_returns_expected(spec: dict) -> None:
    """Subsumes 5 originally hand-written compute_demand_qty_* tests."""
    total, evento = compute_demand_qty(
        qty_forecast=spec["qty_forecast"],
        qty_pedidos=spec["qty_pedidos"],
        seasonal_multiplier=spec["seasonal_multiplier"],
    )
    assert total == spec["expected_total"], (
        f"{spec['description']!r}: total={total} != {spec['expected_total']}"
    )
    assert evento == spec["expected_evento"], (
        f"{spec['description']!r}: evento={evento} != {spec['expected_evento']}"
    )


@pytest.mark.parametrize("spec", _SPLIT_CASES, ids=lambda s: s["id"])
def test_split_pedidos_status_returns_expected(spec: dict) -> None:
    """Subsumes 3 originally hand-written split_pedidos_status_* tests."""
    total, confirmed = split_pedidos_status(
        pending_qty=spec["pending_qty"],
        confirmed_qty=spec["confirmed_qty"],
        ready_qty=spec["ready_qty"],
    )
    assert total == spec["expected_total"], (
        f"{spec['description']!r}: total={total} != {spec['expected_total']}"
    )
    assert confirmed == spec["expected_confirmed"], (
        f"{spec['description']!r}: confirmed={confirmed} != {spec['expected_confirmed']}"
    )
