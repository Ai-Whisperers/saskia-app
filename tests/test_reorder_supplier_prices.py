"""PR A4 — tests for app/rms/reorder_supplier_prices.py.

Pins the read-only per-supplier price lookup contract:
  - Returns `{supplier_id: price_or_None}` for all active suppliers
  - The "effective" supplier (locked → last_purchase → parent) gets the
    ingredient's `purchase_price_gs`
  - All other suppliers get `None` (UI shows "—") until per-supplier
    history is implemented
  - Inactive suppliers are NOT included
  - An unknown ingredient returns `{}` (no error, no rows)
  - Suppliers are returned in name-ascending order (UI sorts alphabetically)
  - The history counter returns the number of price events for the ingredient
"""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from app.rms.models import IngredientPriceEvent
from app.rms.reorder_supplier_prices import (
    get_ingredient_price_history_count,
    get_supplier_price_options,
)
from tests.factories import make_ingredient, make_supplier


def _new_session(session_factory):
    """Open a new session bound to the test's engine."""
    return sessionmaker(bind=session_factory.kw["bind"])()


# ─── get_supplier_price_options ────────────────────────────────────


def test_unknown_ingredient_returns_empty_dict(session_factory) -> None:
    """No row for ingredient_id=99999 → empty dict, no exception."""
    s = _new_session(session_factory)
    try:
        assert get_supplier_price_options(s, 99_999) == {}
    finally:
        s.close()


def test_no_suppliers_returns_empty_dict(session_factory) -> None:
    """Ingredient exists but no suppliers configured → empty dict."""
    s = _new_session(session_factory)
    try:
        ing = make_ingredient(s)
        s.commit()
        assert get_supplier_price_options(s, ing.id) == {}
    finally:
        s.close()


def test_single_supplier_with_locked(session_factory) -> None:
    """One supplier, locked to that supplier → gets the price."""
    s = _new_session(session_factory)
    try:
        sup = make_supplier(s, name="Distribuidora Norte")
        ing = make_ingredient(
            s,
            purchase_price_gs=12_500,
            supplier_id=sup.id,
            locked_supplier_id=sup.id,
        )
        s.commit()
        out = get_supplier_price_options(s, ing.id)
        assert out == {sup.id: 12_500}
    finally:
        s.close()


def test_locked_supplier_wins_over_parent(session_factory) -> None:
    """If `locked_supplier_id` is set, it determines who gets the price."""
    s = _new_session(session_factory)
    try:
        locked = make_supplier(s, name="Locked Supplier")
        parent = make_supplier(s, name="Parent Supplier")
        ing = make_ingredient(
            s,
            purchase_price_gs=8_000,
            supplier_id=parent.id,
            locked_supplier_id=locked.id,
        )
        s.commit()
        out = get_supplier_price_options(s, ing.id)
        assert out == {
            locked.id: 8_000,
            parent.id: None,  # No per-supplier data yet
        }
    finally:
        s.close()


def test_last_purchase_wins_when_no_lock(session_factory) -> None:
    """No `locked_supplier_id`, but `last_purchase_supplier_id` set."""
    s = _new_session(session_factory)
    try:
        last = make_supplier(s, name="Last Purchase")
        parent = make_supplier(s, name="Parent")
        ing = make_ingredient(
            s,
            purchase_price_gs=15_000,
            supplier_id=parent.id,
            last_purchase_supplier_id=last.id,
        )
        s.commit()
        out = get_supplier_price_options(s, ing.id)
        assert out == {
            last.id: 15_000,
            parent.id: None,
        }
    finally:
        s.close()


def test_parent_supplier_wins_when_nothing_else(session_factory) -> None:
    """Only `supplier_id` set → it becomes the effective one."""
    s = _new_session(session_factory)
    try:
        parent = make_supplier(s, name="Parent")
        ing = make_ingredient(s, purchase_price_gs=20_000, supplier_id=parent.id)
        s.commit()
        out = get_supplier_price_options(s, ing.id)
        assert out == {parent.id: 20_000}
    finally:
        s.close()


def test_inactive_suppliers_excluded(session_factory) -> None:
    """Inactive suppliers do NOT appear in the options dict."""
    s = _new_session(session_factory)
    try:
        active = make_supplier(s, name="Active", is_active=True)
        inactive = make_supplier(s, name="Inactive", is_active=False)
        ing = make_ingredient(s, supplier_id=active.id, locked_supplier_id=active.id)
        s.commit()
        out = get_supplier_price_options(s, ing.id)
        assert inactive.id not in out
        assert out == {active.id: ing.purchase_price_gs}
    finally:
        s.close()


def test_suppliers_sorted_by_name_ascending(session_factory) -> None:
    """Dict iteration order is supplier.name ASC (UI alphabetical scan)."""
    s = _new_session(session_factory)
    try:
        make_supplier(s, name="Charlie")
        make_supplier(s, name="Alpha")
        make_supplier(s, name="Bravo")
        ing = make_ingredient(s, supplier_id=None)  # no effective → all None
        s.commit()
        out = get_supplier_price_options(s, ing.id)
        # With no effective supplier, every value is None — the test is the
        # order of the keys (which dict preserves in insertion order in 3.7+).
        keys = list(out.keys())
        # Look up each supplier's name via a fresh query
        from app.rms.models import Supplier

        sup_by_id = {sup.id: sup for sup in s.query(Supplier).all()}
        names_in_order = [sup_by_id[k].name for k in keys]
        assert names_in_order == ["Alpha", "Bravo", "Charlie"]
    finally:
        s.close()


def test_no_effective_supplier_returns_all_none(session_factory) -> None:
    """If no locked/last/parent supplier is set, every active supplier
    gets None. (This shouldn't happen in prod — an ingredient without
    any supplier reference is data debt — but the code shouldn't crash.)
    """
    s = _new_session(session_factory)
    try:
        sup1 = make_supplier(s, name="A")
        sup2 = make_supplier(s, name="B")
        ing = make_ingredient(s, supplier_id=None)
        s.commit()
        out = get_supplier_price_options(s, ing.id)
        assert out == {sup1.id: None, sup2.id: None}
    finally:
        s.close()


# ─── get_ingredient_price_history_count ────────────────────────────


def test_history_count_zero_when_no_events(session_factory) -> None:
    s = _new_session(session_factory)
    try:
        ing = make_ingredient(s)
        s.commit()
        assert get_ingredient_price_history_count(s, ing.id) == 0
    finally:
        s.close()


def test_history_count_reflects_events(session_factory) -> None:
    """3 IngredientPriceEvent rows → counter returns 3."""
    s = _new_session(session_factory)
    try:
        ing = make_ingredient(s)
        for new_price in (9_000, 10_000, 11_000):
            s.add(IngredientPriceEvent(ingredient_id=ing.id, price_gs=new_price))
        s.commit()
        assert get_ingredient_price_history_count(s, ing.id) == 3
    finally:
        s.close()


def test_history_count_filters_by_ingredient(session_factory) -> None:
    """Events for OTHER ingredients are NOT counted."""
    s = _new_session(session_factory)
    try:
        target = make_ingredient(s, name="Target")
        other = make_ingredient(s, name="Other")
        for ing in (target, target, other):
            s.add(IngredientPriceEvent(ingredient_id=ing.id, price_gs=1000))
        s.commit()
        assert get_ingredient_price_history_count(s, target.id) == 2
        assert get_ingredient_price_history_count(s, other.id) == 1
    finally:
        s.close()


def test_history_count_unknown_ingredient_returns_zero(session_factory) -> None:
    """ingredient_id=99999 → 0 (no row, no error)."""
    s = _new_session(session_factory)
    try:
        assert get_ingredient_price_history_count(s, 99_999) == 0
    finally:
        s.close()
