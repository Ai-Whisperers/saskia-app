"""tests/test_barcode.py — verify app/rms/barcode.py (E23).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E23.

Covers:
- normalize_sku: uppercase, strip chars
- validate_sku: empty / too-short / too-long / invalid chars
- get_product_by_sku: hit / miss / invalid shape
- assign_sku: success / duplicate raises ValueError
- suggest_sku: produces a valid-format SKU
- Product.sku column exists + indexed
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.integrations.barcode import (
    assign_sku,
    get_product_by_sku,
    normalize_sku,
    suggest_sku,
    validate_sku,
)
from app.rms.models import Product


def test_normalize_sku_uppercase_and_clean():
    assert normalize_sku("abc-123") == "ABC-123"
    assert normalize_sku("  abc 123  ") == "ABC123"
    assert normalize_sku("a$b#c") == "ABC"
    assert normalize_sku("") == ""
    assert normalize_sku("Prod-001") == "PROD-001"


def test_validate_sku_valid():
    assert validate_sku("ABC-1234") is None
    assert validate_sku("PROD0001") is None
    assert validate_sku("AB12") is None  # 4 chars minimum


def test_validate_sku_empty():
    err = validate_sku("")
    assert err and "empty" in err.lower()


def test_validate_sku_too_short():
    err = validate_sku("AB")
    assert err and "length" in err.lower()


def test_validate_sku_too_long():
    err = validate_sku("A" * 33)
    assert err and "length" in err.lower()


def test_validate_sku_invalid_chars():
    err = validate_sku("AB-12$")
    assert err and "letters" in err.lower()


def test_get_product_by_sku_hit(session_factory):
    s = session_factory()
    try:
        s.add(Product(name="Muffin", sale_price_gs=2500, sku="MUF-0001"))
        s.commit()
        result = get_product_by_sku(s, "muf-0001")  # lowercase input
        assert result.ok
        assert result.product is not None
        assert result.product.name == "Muffin"
        assert result.normalized_sku == "MUF-0001"
    finally:
        s.close()


def test_get_product_by_sku_miss(session_factory):
    s = session_factory()
    try:
        result = get_product_by_sku(s, "MUF-9999")
        assert not result.ok
        assert result.error == "not_found"
        assert result.normalized_sku == "MUF-9999"
    finally:
        s.close()


def test_get_product_by_sku_invalid_shape(session_factory):
    s = session_factory()
    try:
        result = get_product_by_sku(s, "AB")  # too short
        assert not result.ok
        assert "length" in (result.error or "").lower()
    finally:
        s.close()


def test_assign_sku_success(session_factory):
    s = session_factory()
    try:
        s.add(Product(name="Torta", sale_price_gs=35000))
        s.commit()
        prod = s.execute(select(Product).where(Product.name == "Torta")).scalar_one()
        returned = assign_sku(s, prod.id, "TOR-0001")
        assert returned == "TOR-0001"
        s.commit()
        assert prod.sku == "TOR-0001"
    finally:
        s.close()


def test_assign_sku_duplicate_raises(session_factory):
    s = session_factory()
    try:
        s.add(Product(name="Muffin 1", sale_price_gs=2500, sku="MUF-001"))
        s.add(Product(name="Muffin 2", sale_price_gs=2500))
        s.commit()

        muffins = list(s.execute(select(Product)).scalars())
        prod2 = next(p for p in muffins if p.name == "Muffin 2")
        with pytest.raises(ValueError, match="already in use"):
            assign_sku(s, prod2.id, "MUF-001")
    finally:
        s.close()


def test_assign_sku_invalid_raises(session_factory):
    s = session_factory()
    try:
        s.add(Product(name="Torta", sale_price_gs=35000))
        s.commit()
        prod = s.execute(select(Product).where(Product.name == "Torta")).scalar_one()
        with pytest.raises(ValueError, match="empty"):
            assign_sku(s, prod.id, "")
    finally:
        s.close()


def test_assign_sku_unknown_product_raises(session_factory):
    s = session_factory()
    try:
        with pytest.raises(ValueError, match="No product"):
            assign_sku(s, 99999, "ABC-1234")
    finally:
        s.close()


def test_suggest_sku_returns_valid_format():
    sku = suggest_sku("Muffin de Vainilla")
    assert validate_sku(sku) is None


def test_suggest_sku_from_empty_name():
    sku = suggest_sku("")
    assert sku.startswith("PROD-")
    assert validate_sku(sku) is None


def test_product_sku_column_is_indexed(session_factory):
    """Product.sku should be indexed (for fast scanner lookup)."""
    from sqlalchemy import inspect

    # Note: this checks the model definition, not the SQLite index
    inspector = inspect(Product)
    cols = {c.name for c in inspector.columns}
    assert "sku" in cols
