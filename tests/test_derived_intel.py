"""Derived-intel engine tests — allergen guard, food-cost variance,
price cascade, demand, freshness, substitutions."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.rms.config import ASUNCION_TZ
from app.rms.demand_freshness import (
    cook_today_suggestions,
    forecast_demand,
    freshness_flags,
    shopping_list_from_forecast,
    substitutes_for,
)
from app.rms.derived_intel import (
    check_customer_risk,
    parse_customer_allergies,
    price_change_impact,
    theoretical_vs_actual,
)
from app.rms.models import (
    Customer,
    Ingredient,
    IngredientPriceEvent,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    WasteLog,
)


def _ing(session, name, *, price=1000, stock=10, shelf=None, dietary=None, allergens=None):
    i = Ingredient(name=name, unit="g", stock_qty=stock, purchase_price_gs=price,
                   shelf_life_days=shelf, dietary_tags=dietary, allergens=allergens)
    session.add(i)
    session.flush()
    return i


def _recipe_with(session, name, ings, yield_qty=10):
    r = Recipe(name=name, yield_qty=yield_qty, yield_unit="und")
    session.add(r)
    session.flush()
    for ing, qty in ings:
        session.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=qty))
    session.flush()
    return r


def _product(session, name, recipe, price):
    p = Product(name=name, recipe_id=recipe.id, sale_price_gs=price, portion_label="und")
    session.add(p)
    session.flush()
    return p


def _sale(session, product, qty=1, days_ago=0):
    s = Sale(product_id=product.id, qty=qty, unit_price_gs=product.sale_price_gs,
             sold_at=datetime.now(ASUNCION_TZ) - timedelta(days=days_ago))
    session.add(s)
    session.flush()
    return s


# ── Allergen guard ─────────────────────────────────────────────────────────

def test_parse_customer_allergies_free_text():
    notes = "Alérgica al maní y a la lactosa. No gluten."
    assert set(parse_customer_allergies(notes)) == {"nuts", "dairy", "gluten"}


def test_allergen_guard_blocks_match(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina 000", allergens="gluten")
        r = _recipe_with(s, "Pan", [(h, 500)])
        r.allergens = "gluten"  # cached
        p = _product(s, "Pan de campo", r, 5000)
        p.inherited_tags = "al:gluten"
        c = Customer(name="Doña Rosa", phone="0981", notes="alérgica al gluten")
        s.add(c)
        s.commit()

        risk = check_customer_risk(s, c.id, p.id)
        assert not risk.safe
        assert risk.matched == ["gluten"]


def test_allergen_guard_allows_different_allergen(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina arroz", allergens=None, dietary="sin gluten")
        r = _recipe_with(s, "Chipá sin gluten", [(h, 400)])
        r.allergens = None
        p = _product(s, "Chipá sf", r, 3000)
        p.inherited_tags = None
        c = Customer(name="Free", phone="0982", notes="alérgico a frutos secos")
        s.add(c)
        s.commit()
        assert check_customer_risk(s, c.id, p.id).safe


def test_allergen_guard_no_customer_data_passes(session_factory):
    with session_factory() as s:
        h = _ing(s, "Nuez", allergens="nuts")
        r = _recipe_with(s, "Torta nuez", [(h, 100)])
        p = _product(s, "Torta", r, 20000)
        c = Customer(name="Sin nota", phone="0983")
        s.add(c)
        s.commit()
        assert check_customer_risk(s, c.id, p.id).safe


# ── Theoretical vs actual ──────────────────────────────────────────────────

def test_food_cost_variance_shape(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina var", price=1000)
        r = _recipe_with(s, "Pan var", [(h, 500)])  # 500g × G.1000/kg-ish
        p = _product(s, "PanV", r, 5000)
        _sale(s, p, qty=4, days_ago=2)
        s.commit()

        v = theoretical_vs_actual(s, days=30)
        assert v.theoretical_gs >= 0
        assert isinstance(v.variance_pct, float)
        assert any(row["name"] == "PanV" for row in v.by_product)


def test_food_cost_variance_waste_counts(session_factory):
    with session_factory() as s:
        h = _ing(s, "Manteca", price=2000, stock=5)
        r = _recipe_with(s, "Medialuna", [(h, 100)])
        p = _product(s, "Media", r, 4000)
        _sale(s, p, qty=2, days_ago=1)
        s.add(WasteLog(ingredient_id=h.id, qty=2, reason="vencido",
                       recorded_at=datetime.now(ASUNCION_TZ)))
        s.commit()
        v = theoretical_vs_actual(s, days=30)
        assert v.waste_gs > 0


# ── Price cascade ──────────────────────────────────────────────────────────

def test_price_impact_lists_recipes_and_products(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina impacto", price=1000)
        r = _recipe_with(s, "Pan impacto", [(h, 500)], yield_qty=10)
        p = _product(s, "PanI", r, 5000)  # unit cost ~50 → food cost 1%: plenty of headroom
        s.commit()

        impact = price_change_impact(s, h.id, 1000, 5000)
        assert impact.ingredient_name == "Harina impacto"
        assert any(rec["id"] == r.id for rec in impact.affected_recipes)
        assert any(prod["id"] == p.id for prod in impact.affected_products)
        # simulation rolled back
        s.refresh(h)
        assert h.purchase_price_gs == 1000


# ── Demand ─────────────────────────────────────────────────────────────────

def test_forecast_needs_min_history(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina dem", price=900)
        r = _recipe_with(s, "Chipá dem", [(h, 100)], yield_qty=12)
        p = _product(s, "ChipáD", r, 1500)
        _sale(s, p, qty=6, days_ago=1)
        _sale(s, p, qty=6, days_ago=2)
        s.commit()
        f = forecast_demand(s)
        assert len(f) == 0  # <3 sales → skipped


def test_forecast_with_history(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina fh", price=900)
        r = _recipe_with(s, "Pan fh", [(h, 500)], yield_qty=10)
        p = _product(s, "PanFH", r, 2000)
        for d in range(10):
            _sale(s, p, qty=5, days_ago=d)
        s.commit()
        f = forecast_demand(s)
        assert len(f) == 1
        assert f[0].recipe_id == r.id
        assert f[0].suggested_batches > 0


def test_shopping_list_shortfall(session_factory):
    with session_factory() as s:
        # stock 100g; recipe needs 500g × batches
        h = _ing(s, "Harina shop", price=1000, stock=100)
        r = _recipe_with(s, "Pan shop", [(h, 500)], yield_qty=10)
        p = _product(s, "PanS", r, 2000)
        for d in range(10):
            _sale(s, p, qty=10, days_ago=d)
        s.commit()
        forecasts = forecast_demand(s)
        shopping = shopping_list_from_forecast(s, forecasts)
        names = [x["name"] for x in shopping]
        assert "Harina shop" in names
        item = next(x for x in shopping if x["name"] == "Harina shop")
        assert item["buy_qty"] > 0
        assert item["stock_qty"] == 100


# ── Freshness ──────────────────────────────────────────────────────────────

def test_freshness_critical_flag(session_factory):
    with session_factory() as s:
        h = _ing(s, "Leche fresca test", price=1500, stock=4, shelf=5)
        # last price event 4 days ago → 1 day left → critical
        s.add(IngredientPriceEvent(
            ingredient_id=h.id, price_gs=1500,
            recorded_at=datetime.now(ASUNCION_TZ) - timedelta(days=4),
        ))
        s.commit()
        flags = freshness_flags(s)
        f = next(x for x in flags if x.name == "Leche fresca test")
        assert f.urgency == "critical"
        assert f.days_until_expiry == 1


def test_freshness_unknown_without_events(session_factory):
    with session_factory() as s:
        _ing(s, "Sal sin registro", price=500, stock=3, shelf=9999)
        s.commit()
        flags = freshness_flags(s)
        f = next(x for x in flags if x.name == "Sal sin registro")
        assert f.urgency == "unknown"


def test_cook_today_suggestion(session_factory):
    with session_factory() as s:
        h = _ing(s, "Crema cocina", price=2000, stock=4, shelf=3)
        s.add(IngredientPriceEvent(
            ingredient_id=h.id, price_gs=2000,
            recorded_at=datetime.now(ASUNCION_TZ) - timedelta(days=2),
        ))
        _recipe_with(s, "Scones crema", [(h, 200)])
        s.commit()
        cook = cook_today_suggestions(s)
        assert any(c["name"] == "Scones crema" for c in cook)


# ── Substitutions ──────────────────────────────────────────────────────────

def test_substitutes_tag_preservation_priority(session_factory):
    with session_factory() as s:
        # Build 3 recipes sharing manteca+margarina vegana (co-occurrence ≥3)
        manteca = _ing(s, "Manteca", price=3000, dietary="")
        marg_v = _ing(s, "Margarina vegana", price=2500, dietary="vegano,sin lactosa")
        for n in range(3):
            r = Recipe(name=f"Rec cooc {n}", yield_qty=5, yield_unit="und")
            s.add(r); s.flush()
            s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=manteca.id, qty=100))
            s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=marg_v.id, qty=100))
        s.commit()
        opts = substitutes_for(s, manteca.id)
        assert any(o.name == "Margarina vegana" for o in opts)
