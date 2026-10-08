"""SASKIA-207 — stock_ledger contract tests.

apply_stock_delta() + qty_to_stock_unit() are now the single path for
non-sale stock changes (purchase paths via SASKIA-205, waste via
merma). These tests lock the helper contract so future flows reuse it
instead of re-growing 22 copies of the boilerplate.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.rms.db import init_db
from app.rms.models import Ingredient, StockMovement
from app.rms.stock_ledger import apply_stock_delta, qty_to_stock_unit


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/ledger.sqlite")
    init_db(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    ing = Ingredient(name="Harina ledger", unit="kg", stock_qty=10.0, purchase_price_gs=5000)
    s.add(ing)
    s.commit()
    yield s
    s.close()


class TestQtyToStockUnit:
    def test_same_unit_passthrough(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        assert qty_to_stock_unit(7.5, "kg", ing) == 7.5

    def test_none_or_empty_unit_passthrough(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        assert qty_to_stock_unit(3.0, None, ing) == 3.0
        assert qty_to_stock_unit(3.0, "", ing) == 3.0

    def test_convertible_units_convert(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        # 500 g → 0.5 kg
        assert qty_to_stock_unit(500, "g", ing) == pytest.approx(0.5)

    def test_cross_family_raw_policy_lands_raw(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        # 'und' vs 'kg': cross-family. raw = land unconverted (kitchen reality).
        assert qty_to_stock_unit(2.0, "und", ing, on_mismatch="raw") == 2.0

    def test_cross_family_raise_policy_raises(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        with pytest.raises(ValueError, match="convertir"):
            qty_to_stock_unit(2.0, "und", ing, on_mismatch="raise")

    def test_unknown_unit_raw_policy_passthrough(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        assert qty_to_stock_unit(4.0, "baldes", ing, on_mismatch="raw") == 4.0

    def test_unknown_unit_raise_policy_raises(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        with pytest.raises(ValueError, match="desconocida"):
            qty_to_stock_unit(4.0, "baldes", ing, on_mismatch="raise")


class TestApplyStockDelta:
    def test_positive_delta_bumps_and_writes_movement(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        mv = apply_stock_delta(
            session,
            ing,
            5.0,
            movement_type="reorder",
            reason="Compra test",
            reference_id=42,
            reference_type="reorder",
            created_by="tester",
        )
        session.flush()
        assert ing.stock_qty == pytest.approx(15.0)
        assert mv.id is not None
        assert mv.movement_type == "reorder"
        assert mv.qty == pytest.approx(5.0)
        assert mv.reference_id == 42

    def test_negative_delta_decrements(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        apply_stock_delta(session, ing, -4.0, movement_type="merma", reason="Merma test")
        session.flush()
        assert ing.stock_qty == pytest.approx(6.0)

    def test_negative_below_floor_surfaces_db_integrity_error(self, session):
        # The ingredient table CHECK (stock_qty >= 0) is the floor — the
        # helper doesn't mask it; the route decides how to surface it.
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            apply_stock_delta(session, ing, -25.0, movement_type="merma", reason="over")
            session.flush()

    def test_does_not_commit_caller_owns_transaction(self, session):
        ing = session.query(Ingredient).filter_by(name="Harina ledger").one()
        apply_stock_delta(session, ing, 1.0, movement_type="reorder", reason="x")
        session.rollback()
        session.refresh(ing)
        assert ing.stock_qty == pytest.approx(10.0)  # bump rolled back
        assert session.query(StockMovement).count() == 0

    def test_null_stock_qty_treated_as_zero(self, session):
        ing = Ingredient(name="Null stock item", unit="und", stock_qty=None)
        session.add(ing)
        session.flush()
        apply_stock_delta(session, ing, 3.0, movement_type="initial", reason="seed")
        session.flush()
        assert ing.stock_qty == pytest.approx(3.0)
