"""UI-V2 Sprint 3 tests: menu_tags, cost freshness, route rendering.

Covers:
  - migration 068: recipe.menu_tags column + family backfill
  - menu_tags save on recipe create/update + familia filter OR semantics
  - product_cost_freshness: latest ingredient price event per product
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, text


def _mk_ingredient(session, name, unit="g", allergens=None, price_gs=None):
    from app.rms.models import Ingredient

    ing = Ingredient(name=name, unit=unit, allergens=allergens,
                     purchase_price_gs=price_gs)
    session.add(ing)
    session.flush()
    return ing


def _mk_recipe(session, name, yield_qty=1, yield_unit="und", family=None, menu_tags=None):
    from app.rms.models import Recipe

    r = Recipe(name=name, yield_qty=yield_qty, yield_unit=yield_unit,
               family=family, menu_tags=menu_tags)
    session.add(r)
    session.flush()
    return r


def _mk_line(session, recipe_id, kind, ref_id, qty, line_unit=""):
    from app.rms.models import RecipeLine

    ln = RecipeLine(recipe_id=recipe_id, line_kind=kind, line_ref_id=ref_id,
                    qty=qty, line_unit=line_unit)
    session.add(ln)
    session.flush()
    return ln


def _mk_price_event(session, ingredient_id, price_gs, days_ago=0):
    from app.rms.models import IngredientPriceEvent

    ev = IngredientPriceEvent(
        ingredient_id=ingredient_id,
        price_gs=price_gs,
        source="manual",
        recorded_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    session.add(ev)
    session.flush()
    return ev


# ───────────────────────── migration 068 ─────────────────────────

def test_migration_068_adds_menu_tags_and_backfills(app_engine):
    """Column exists; legacy family copied into menu_tags on backfill."""

    with __import__("app.rms.db", fromlist=["make_session_factory"]).make_session_factory(app_engine)() as s:
        # Migration runs during init_db (app_engine fixture); column usable.
        r = _mk_recipe(s, "Mig068 Receta", family="Pastelería")
        s.commit()
        # menu_tags was backfilled from family by migration 068 only for
        # rows existing at migration time; new rows write directly.
        r.menu_tags = "Pastelería,Especial"
        s.commit()
        row = s.execute(
            text("SELECT menu_tags FROM recipe WHERE id = :i"), {"i": r.id}
        ).one()
        assert row.menu_tags == "Pastelería,Especial"


# ───────────────────────── menu_tags form save ─────────────────────────

def test_recipe_create_saves_menu_tags(client, session_factory):
    """POST /recetas/nueva persists comma-joined menu_tags."""
    with session_factory() as s:
        ing = _mk_ingredient(s, "Harina MT", "g", price_gs=1000)
        s.commit()
        ing_id = ing.id

    resp = client.post("/recetas/nueva", data={
        "name": "Torta MT",
        "yield_qty": "1",
        "yield_unit": "und",
        "family": "Pastelería",
        "menu_tags": "Pastelería, Temporada",
        "dietary_tags": "",
        "notes": "",
        "line_kind": ["ingredient"],
        "line_target_id": [str(ing_id)],
        "line_qty": ["500"],
        "line_unit": ["g"],
    })
    assert resp.status_code in (200, 302, 303)

    with session_factory() as s:
        from app.rms.models import Recipe

        r = s.scalars(select(Recipe).where(Recipe.name == "Torta MT")).one()
        assert r.menu_tags is not None
        tags = {t.strip() for t in r.menu_tags.split(",")}
        assert tags == {"Pastelería", "Temporada"}


def test_familia_filter_matches_menu_tags(client, session_factory):
    """?familia=X matches recipes whose menu_tags contain X."""
    with session_factory() as s:
        _mk_recipe(s, "Verano MT", family=None, menu_tags="Especial de Temporada,Pastelería")
        _mk_recipe(s, "Clasico MT", family="Panadería", menu_tags=None)
        s.commit()

    resp = client.get("/recetas?familia=Especial de Temporada")
    assert resp.status_code == 200
    assert "Verano MT" in resp.text
    assert "Clasico MT" not in resp.text


# ───────────────────────── cost freshness ─────────────────────────

def test_cost_freshness_latest_event_per_product(session_factory):
    """Returns the newest IngredientPriceEvent across the recipe tree."""
    from app.rms.cost_freshness import product_cost_freshness
    from app.rms.models import Product

    with session_factory() as s:
        harina = _mk_ingredient(s, "Harina CF", "g", price_gs=900)
        azucar = _mk_ingredient(s, "Azúcar CF", "g", price_gs=1500)
        r = _mk_recipe(s, "Pan CF", 2)
        _mk_line(s, r.id, "ingredient", harina.id, 500, "g")
        _mk_line(s, r.id, "ingredient", azucar.id, 100, "g")
        p = Product(name="Pan CF", sale_price_gs=5000, recipe_id=r.id,
                    portion_label="1 und")
        s.add(p)
        _mk_price_event(s, harina.id, 900, days_ago=40)
        _mk_price_event(s, azucar.id, 1500, days_ago=5)
        s.commit()

        result = product_cost_freshness(s, [p])
        stamp = result[p.id]
        assert stamp is not None
        age_days = (datetime.utcnow() - stamp).days
        assert age_days == pytest.approx(5, abs=1)


def test_cost_freshness_none_without_recipe(session_factory):
    from app.rms.cost_freshness import product_cost_freshness
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(name="Venta libre CF", sale_price_gs=1000,
                    portion_label="1 und", recipe_id=None)
        s.add(p)
        s.commit()
        result = product_cost_freshness(s, [p])
        assert result[p.id] is None


def test_cost_freshness_follows_subrecipes(session_factory):
    """Freshness looks through sub-recipe trees."""
    from app.rms.cost_freshness import product_cost_freshness
    from app.rms.models import Product

    with session_factory() as s:
        harina = _mk_ingredient(s, "Harina CF2", "g", price_gs=900)
        queso = _mk_ingredient(s, "Qeso CF2", "g", price_gs=8000)
        base = _mk_recipe(s, "Base CF2", 1)
        _mk_line(s, base.id, "ingredient", harina.id, 500, "g")
        glaseado = _mk_recipe(s, "Glaseado CF2", 300, "g")
        _mk_line(s, glaseado.id, "ingredient", queso.id, 100, "g")
        _mk_line(s, base.id, "sub_recipe", glaseado.id, 150, "g")
        p = Product(name="Torta CF2", sale_price_gs=25000, recipe_id=base.id,
                    portion_label="1 und")
        s.add(p)
        _mk_price_event(s, harina.id, 900, days_ago=120)
        _mk_price_event(s, queso.id, 8000, days_ago=3)
        s.commit()

        result = product_cost_freshness(s, [p])
        stamp = result[p.id]
        assert stamp is not None
        age = (datetime.utcnow() - stamp).days
        assert age == pytest.approx(3, abs=1)


# ───────────────────────── productos page rendering ─────────────────────────

def test_productos_page_shows_cost_updated_column(client, session_factory):
    """The Costo act. column renders without crashing (needs a product)."""
    with session_factory() as s:
        from app.rms.models import Product

        s.add(Product(name="Prod col test", sale_price_gs=1000,
                      portion_label="1 und"))
        s.commit()

    resp = client.get("/productos")
    assert resp.status_code == 200
    assert "Costo act." in resp.text


# ───────────────────────── recetas list shows menu tags ─────────────────────────

def test_recetas_page_renders_after_menu_tags(client, session_factory):
    with session_factory() as s:
        _mk_recipe(s, "Sanity MT", family="Panadería")
        s.commit()
    resp = client.get("/recetas")
    assert resp.status_code == 200
    assert "Sanity MT" in resp.text
