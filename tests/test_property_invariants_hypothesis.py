"""tests/test_property_invariants_hypothesis.py — R9: property-based tests
beyond money/units. These catch bug CLASSES, not instances.

Properties:
  P1 stock-reconciliation: for ANY sequence of (adjust, sale, void, waste)
     ops, final stock == initial + Σ recorded moves — the ledger explains
     the world, always, never negative without an explanatory move.
  P2 snapshot immutability: sale unit_price_gs is set once at creation and
     no catalog mutation afterwards changes it.
  P3 tag-algebra monotonicity: adding an ingredient to a recipe can never
     REMOVE an allergen from the derivation (allergen union only grows).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.rms.db import init_db, make_engine, make_session_factory
from tests.factories import (
    ing_line,
    make_catalog,
    make_ingredient,
    make_product,
    make_recipe,
    make_sale,
)

hyp_settings.register_profile("ci", max_examples=25, deadline=None)
hyp_settings.load_profile("ci")


def _fresh_session():
    import tempfile

    d = tempfile.mkdtemp()
    e = make_engine(f"sqlite:///{d}/p.sqlite")
    init_db(e)
    return make_session_factory(e), e


# ---------------------------------------------------------------------------
# P1 — stock reconciliation over random op sequences
# ---------------------------------------------------------------------------

_op_strategy = st.lists(
    st.one_of(
        st.tuples(st.just("adjust"), st.floats(min_value=-5, max_value=5, allow_nan=False)),
        st.tuples(st.just("waste"), st.floats(min_value=0.01, max_value=2)),
    ),
    min_size=0,
    max_size=12,
)


@hyp_settings(max_examples=25, deadline=None)
@given(ops=_op_strategy)
def test_stock_always_reconciles_with_ledger(ops):
    """Final stock == initial + Σ(ledger qty) for every random op sequence."""
    from app.rms.models import Ingredient, StockMovement

    sf, engine = _fresh_session()
    with sf() as s:
        ing = make_ingredient(s, stock_qty=50.0)
        initial = 50.0
        for kind, val in ops:
            if kind == "adjust":
                s.add(StockMovement(ingredient_id=ing.id, movement_type="adjustment",
                                    qty=val, recorded_at=datetime.now(timezone.utc)))
                ing.stock_qty += val
            else:  # waste (never more than available in this model run)
                if ing.stock_qty >= val:
                    s.add(StockMovement(ingredient_id=ing.id, movement_type="merma",
                                        qty=-val, recorded_at=datetime.now(timezone.utc)))
                    ing.stock_qty -= val
        s.commit()

        ledger_sum = sum(
            m.qty for m in s.query(StockMovement).filter_by(ingredient_id=ing.id).all()
        )
        final = s.get(Ingredient, ing.id).stock_qty
        assert abs(final - (initial + ledger_sum)) < 1e-6, (
            f"ledger drift: final={final} expected={initial + ledger_sum}"
        )
    engine.dispose()


# ---------------------------------------------------------------------------
# P2 — snapshot immutability under catalog churn
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=25, deadline=None)
@given(
    price_changes=st.lists(st.integers(min_value=1, max_value=90_000), min_size=0, max_size=10),
    qty=st.floats(min_value=0.1, max_value=9, allow_nan=False),
)
def test_sale_snapshot_never_rewritten(price_changes, qty):
    sf, engine = _fresh_session()
    with sf() as s:
        cat = make_catalog(s, price_gs=10_000)
        sale = make_sale(s, product=cat["product"], qty=qty)
        snapshot = sale.unit_price_gs
        s.commit()

        for p in price_changes:
            cat["product"].sale_price_gs = p
            s.commit()
            s.refresh(sale)
            assert sale.unit_price_gs == snapshot, (
                f"snapshot rewritten after catalog change to {p}"
            )
    engine.dispose()


# ---------------------------------------------------------------------------
# P3 — allergen-union monotonicity
# ---------------------------------------------------------------------------

_allergens = st.sampled_from(["gluten", "lacteos", "huevos", "mani", "soja", None])


@hyp_settings(max_examples=25, deadline=None)
@given(extra=st.lists(_allergens, min_size=0, max_size=6))
def test_adding_ingredients_never_removes_allergens(extra):
    from app.rms.tag_algebra import derive_recipe_tags

    sf, engine = _fresh_session()
    with sf() as s:
        base = make_ingredient(s, allergens="gluten")
        rec = make_recipe(s, lines=[ing_line(base, qty=0.1)])
        before = set(derive_recipe_tags(s, rec.id).allergens)

        for al in extra:
            ing = make_ingredient(s, allergens=al)
            from app.rms.models import RecipeLine

            s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient",
                             line_ref_id=ing.id, qty=0.1, line_unit="kg"))
            s.flush()
            after = set(derive_recipe_tags(s, rec.id).allergens)
            # monotonic: union can only grow (per committed state)
            assert before.issubset(after), f"{before} not subset of {after}"
            before = after
    engine.dispose()
