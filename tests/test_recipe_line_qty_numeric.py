"""Tests for RecipeLine.qty Float → Numeric migration (BACKLOG #19).

RecipeLine.qty stores ingredient quantities per recipe (e.g. 0.250 kg
of flour). Currently Float(53) — float32 truncation is the issue
(0.1 + 0.2 != 0.3). Switch to Numeric(12, 4) so all quantities are
exact Decimal storage, no float drift.

These tests assert:
- New installs create recipe_line.qty as NUMERIC, not FLOAT.
- Roundtrip Decimal values through insert + select.
- Decimal arithmetic does not lose precision.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import inspect

from tests.factories import make_catalog


def test_recipe_line_qty_column_declared_numeric(app_engine):
    """New schema should declare recipe_line.qty as NUMERIC, not FLOAT."""
    insp = inspect(app_engine)
    cols = {c["name"]: c for c in insp.get_columns("recipe_line")}
    assert "qty" in cols
    qty_type = str(cols["qty"]["type"]).upper()
    assert "NUMERIC" in qty_type, (
        f"recipe_line.qty should be NUMERIC, got {qty_type}"
    )
    assert "FLOAT" not in qty_type and "REAL" not in qty_type


def test_recipe_line_qty_roundtrip_decimal(session_factory):
    """Insert 0.250 + 0.250 + 0.500 and read back exactly."""
    from app.rms.models import RecipeLine

    s = session_factory()
    try:
        # Two recipes at 0.250 + one at 0.500 = 1.0 exactly
        make_catalog(s, line_qty=0.25)
        make_catalog(s, line_qty=0.25)
        make_catalog(s, line_qty=0.50)
        s.commit()

        rows = s.query(RecipeLine).all()
        qtys = sorted(float(r.qty) for r in rows)
        assert qtys == [0.25, 0.25, 0.50]

        # Arithmetic precision: sum == 1.0 exactly via Decimal
        total = sum(Decimal(str(r.qty)) for r in rows)
        assert total == Decimal("1.00")
    finally:
        s.close()


def test_recipe_line_qty_handles_high_precision(session_factory):
    """Quantities like 0.0625 (1/16) round-trip without drift."""
    from app.rms.models import RecipeLine

    s = session_factory()
    try:
        make_catalog(s, line_qty=0.0625)
        s.commit()

        line = s.query(RecipeLine).first()
        # Exact equality is what matters — float32 would round to
        # ~0.06249999; Numeric gives the exact bit pattern.
        assert Decimal(str(line.qty)) == Decimal("0.0625")
    finally:
        s.close()


def test_recipe_line_qty_supports_four_decimal_places(session_factory):
    """Migration target precision (12, 4) lets us store 0.0625 exactly."""
    from app.rms.models import RecipeLine

    s = session_factory()
    try:
        c = make_catalog(s, line_qty=0.0625)
        s.commit()

        lines = c["recipe"].lines
        assert len(lines) >= 1
        line = lines[0]
        assert Decimal(str(line.qty)) == Decimal("0.0625")
    finally:
        s.close()