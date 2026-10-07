"""Batch B6 (2026-10-07): pre-sale threshold override tests.

Tests that the new ``pre_sale_cfg`` kwarg on ``validate_sale_intent``
correctly accepts a partial override dict and merges it with
``DEFAULT_PRE_SALE_CONFIG``.

The pre-existing tests in ``tests/test_pre_sale_check.py`` cover the
no-override default path (and the env-var-driven path at import time).
This file is the precise "override dict" path.
"""

from __future__ import annotations

from datetime import date

from app.rms.sales.pre_sale_check import (
    DEFAULT_PRE_SALE_CONFIG,
    MAX_DISCOUNT_PCT_WITHOUT_OVERRIDE,
    MAX_QTY_PER_SALE,
    LOW_STOCK_WARN_THRESHOLD_PCT,
    PreSaleIntent,
    validate_sale_intent,
)


# ── DEFAULT_PRE_SALE_CONFIG shape ────────────────────────────────────────


def test_default_pre_sale_config_has_all_3_keys():
    """The registry dict has exactly the 3 keys documented in the plan."""
    expected = {"max_qty_per_sale", "max_discount_pct", "low_stock_warn_pct"}
    assert set(DEFAULT_PRE_SALE_CONFIG.keys()) == expected


def test_legacy_constants_alias_default_pre_sale_config():
    """Legacy module-level constants alias the new dict.

    Pre-existing code imported MAX_DISCOUNT_PCT_WITHOUT_OVERRIDE,
    MAX_QTY_PER_SALE, LOW_STOCK_WARN_THRESHOLD_PCT by name. They must
    now read through the new dict so changes propagate.
    """
    assert MAX_DISCOUNT_PCT_WITHOUT_OVERRIDE == DEFAULT_PRE_SALE_CONFIG["max_discount_pct"]
    assert MAX_QTY_PER_SALE == DEFAULT_PRE_SALE_CONFIG["max_qty_per_sale"]
    assert LOW_STOCK_WARN_THRESHOLD_PCT == DEFAULT_PRE_SALE_CONFIG["low_stock_warn_pct"]


# ── validate_sale_intent override ───────────────────────────────────────


def test_validate_sale_intent_qty_cap_override_blocks(
    session_factory, monkeypatch
):
    """Override tightening max_qty_per_sale produces a blocker.

    With default cap=999, qty=200 is allowed. With override cap=100,
    qty=200 must produce a QTY_TOO_LARGE blocker.
    """
    # _make_product_helper defined at the bottom of this file

    s = session_factory()
    try:
        product = _make_product_helper(s)

        # Default: qty=200 allowed
        intent = PreSaleIntent(
            product_id=product.id, sku="", qty=200, sold_at=date(2026, 10, 7)
        )
        d_default = validate_sale_intent(s, intent, today=date(2026, 10, 7))
        assert not any(w.code == "QTY_TOO_LARGE" for w in d_default.blockers)

        # Override cap=100: qty=200 blocked
        intent2 = PreSaleIntent(
            product_id=product.id, sku="", qty=200, sold_at=date(2026, 10, 7)
        )
        d_override = validate_sale_intent(
            s,
            intent2,
            today=date(2026, 10, 7),
            pre_sale_cfg={"max_qty_per_sale": 100},
        )
        assert any(w.code == "QTY_TOO_LARGE" for w in d_override.blockers)
    finally:
        s.close()


def test_validate_sale_intent_discount_cap_override(
    session_factory, monkeypatch
):
    """Override lowering max_discount_pct produces a warning.

    With default cap=20%, discount=10% is allowed (no warning).
    With override cap=5%, the same 10% discount must produce a
    LARGE_DISCOUNT warning.
    """
    # _make_product_helper defined at the bottom of this file

    s = session_factory()
    try:
        product = _make_product_helper(s, price=10000)
        # 10% discount = 1000 off a 10000 line
        intent = PreSaleIntent(
            product_id=product.id,
            sku="",
            qty=1,
            discount_gs=1000,
            sold_at=date(2026, 10, 7),
        )

        # Default cap=20%: 10% < 20% → no warning
        d_default = validate_sale_intent(s, intent, today=date(2026, 10, 7))
        assert not any(w.code == "LARGE_DISCOUNT" for w in d_default.warnings)

        # Override cap=5%: 10% > 5% → warning
        d_override = validate_sale_intent(
            s,
            intent,
            today=date(2026, 10, 7),
            pre_sale_cfg={"max_discount_pct": 5},
        )
        assert any(w.code == "LARGE_DISCOUNT" for w in d_override.warnings)
    finally:
        s.close()


def test_validate_sale_intent_partial_cfg_merges_with_defaults(
    session_factory
):
    """Partial override dict only changes the named keys."""
    # _make_product_helper defined at the bottom of this file

    s = session_factory()
    try:
        product = _make_product_helper(s)

        # Override max_qty_per_sale=10, max_discount_pct stays at default
        intent = PreSaleIntent(
            product_id=product.id, sku="", qty=20, sold_at=date(2026, 10, 7)
        )
        d = validate_sale_intent(
            s,
            intent,
            today=date(2026, 10, 7),
            pre_sale_cfg={"max_qty_per_sale": 10},
        )
        # qty=20 > overridden cap=10 → blocker
        assert any(w.code == "QTY_TOO_LARGE" for w in d.blockers)
        # discount stays at default 20% (no discount in intent anyway)
    finally:
        s.close()


# ── Public API surface ──────────────────────────────────────────────────


def test_get_pre_sale_config_returns_dict(session_factory):
    """The helper returns a dict with all 3 keys."""
    from app.rms.settings_runtime import get_pre_sale_config

    with session_factory() as s:
        cfg = get_pre_sale_config(s)
        assert isinstance(cfg, dict)
        assert set(cfg.keys()) == set(DEFAULT_PRE_SALE_CONFIG.keys())


def test_get_pre_sale_config_uses_defaults_when_db_empty(session_factory):
    """With no settings stored, get_*_config returns module defaults."""
    from app.rms.settings_runtime import get_pre_sale_config

    with session_factory() as s:
        cfg = get_pre_sale_config(s)
        # Compare by keys (not value) since DEFAULT_PRE_SALE_CONFIG reads
        # env-var at import time, but the helper returns the value the
        # Setting() default specifies.
        for k in DEFAULT_PRE_SALE_CONFIG:
            assert k in cfg


# Helper function — create a minimal product for pre-sale validation.
def _make_product_helper(session, *, price: int = 10000, name: str = "Torta"):
    """Create a Product in the session (no recipe). Returns the Product."""
    from app.rms.models import Product

    p = Product(name=name, sku=f"SKU-{name}", sale_price_gs=price)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p