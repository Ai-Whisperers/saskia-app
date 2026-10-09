"""Tests for the qseed quick-seed fixture."""

import pytest

pytestmark = pytest.mark.crud


def test_qseed_basic(qseed):

    data = qseed("basic")
    assert data["ingredient"].name == "harina QA"
    assert data["recipe"].name == "Receta QA"
    assert data["product"].name == "Producto QA"


def test_qseed_with_sale_creates_stock_move(qseed, session_factory):
    """with_sale scenario calls apply_sale(), creating a StockMovement row."""
    data = qseed("with_sale")
    sale_id = data["sale"].sale_id
    with session_factory() as s:
        from app.rms.models import StockMovement

        moves = s.query(StockMovement).filter_by(reference_id=sale_id, reference_type="sale").all()
        assert len(moves) >= 1


def test_qseed_with_low_stock(qseed):
    data = qseed("with_low_stock")
    assert data["low_ingredient"].stock_qty < data["low_ingredient"].min_stock_qty


def test_qseed_with_pending_pedido(qseed):
    data = qseed("with_pending_pedido")
    assert data["pedido"].status == "pending"


def test_qseed_with_voided_sale(qseed):
    data = qseed("with_voided_sale")
    assert "voided_sale_id" in data
    assert data["voided_sale_id"] > 0


def test_qseed_with_waste(qseed):
    data = qseed("with_waste")
    assert data["waste"].cost_gs > 0


def test_qseed_is_fast(qseed):
    """Quick seed should be <200ms (vs 2s for full seed_demo_data)."""
    import time

    t0 = time.perf_counter()
    for scenario in [
        "basic",
        "with_sale",
        "with_low_stock",
        "with_pending_pedido",
        "with_voided_sale",
        "with_waste",
        "with_customer",
        "with_supplier",
        "with_audit_log",
    ]:
        qseed(scenario)
    elapsed = time.perf_counter() - t0
    # 9 scenarios in <500ms total is the target.
    assert elapsed < 0.5, f"qseed took {elapsed:.2f}s — too slow"


def test_qseed_idempotent(qseed):
    """Calling qseed('basic') twice does NOT duplicate."""
    a = qseed("basic")
    b = qseed("basic")
    # Same ingredient (idempotent)
    assert a["ingredient"].id == b["ingredient"].id
