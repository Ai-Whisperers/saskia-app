# allow-hardcoded-dates: fixture pins one explicit for_date for the cierre-split math.
"""Cierre split, ingredient margin, cocina stock line, and station roles."""

from __future__ import annotations

from sqlalchemy import select

from app.rms.models import (
    Ingredient,
    IngredientPriceEvent,
    Product,
    ProductionCompletion,
    Recipe,
    RecipeLine,
)
from app.rms.price_history import record_price_event


def _choose(client, station: str) -> str:
    """Cookie header with the station session and the CSRF cookie the client already holds.

    The session cookie is Secure, so the HTTP test client will not store it.
    A Cookie header replaces the jar, and the test client also sends
    X-CSRF-Token from that jar, so the csrf value in the header must be
    the same one.
    """
    client.get("/puesto")
    chosen = client.post("/puesto", data={"station": station}, follow_redirects=False)
    assert chosen.status_code == 303
    session_pair = ""
    for key, value in chosen.headers.multi_items():
        if key.lower() == "set-cookie" and value.startswith("sazon_session="):
            session_pair = value.split(";", 1)[0]
    parts = []
    csrf = client.cookies.get("csrf_token")
    if csrf:
        parts.append(f"csrf_token={csrf}")
    if session_pair:
        parts.append(session_pair)
    return "; ".join(parts)


def test_cocina_cierre_shows_pieces_and_stock_without_prices(client):
    cookie = _choose(client, "cocina")
    page = client.get("/eod", headers={"cookie": cookie})
    assert page.status_code == 200
    text = page.text
    assert "Producción del día" in text
    assert "Stock bajo" in text
    assert "Mínimo" in text
    assert "Equipo y mesada limpios" not in text
    assert "Costo est." not in text
    assert "Abrir Reponer" not in text
    assert "El precio de la compra se anota en Inventario." in text


def test_cocina_cierre_refuses_desk_checkboxes(client):
    cookie = _choose(client, "cocina")
    saved = client.post(
        "/eod/check",
        data={"equipment_cleaned": "on"},
        headers={"cookie": cookie},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    # Keyed flash system (flash_toast): station refusals redirect with a
    # flash key naming the required station.
    assert "eod_wrong_station_gerencia" in saved.headers["location"]


def test_escritorio_cierre_reads_pieces_and_keeps_checkboxes(client, session_factory):
    with session_factory() as s:
        prod = Product(name="Pieza que no se pisa", sale_price_gs=1500)
        s.add(prod)
        s.commit()
        product_id = prod.id

    cookie = _choose(client, "gerencia")
    page = client.get("/eod", headers={"cookie": cookie})
    assert page.status_code == 200
    assert "Equipo y mesada limpios" in page.text
    assert "completed_qty" not in page.text
    assert "Las piezas las anota Cocina" in page.text
    assert "data-cocina-stock" not in page.text

    saved = client.post(
        "/eod/completar",
        data={"product_id": str(product_id), "for_date": "2026-10-07", "completed_qty": "4"},
        headers={"cookie": cookie},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    assert "eod_wrong_station_cocina" in saved.headers["location"]
    with session_factory() as s:
        rows = s.scalars(
            select(ProductionCompletion).where(ProductionCompletion.product_id == product_id)
        ).all()
        assert rows == []


def test_ingredient_page_shows_both_margins(session_factory):
    from app.rms.ingredient_margins import product_margins_for_ingredient

    with session_factory() as s:
        flour = Ingredient(name="Harina margen", unit="kg", stock_qty=5, purchase_price_gs=8000)
        s.add(flour)
        s.flush()
        record_price_event(s, flour.id, 10000, source="manual")
        record_price_event(s, flour.id, 8000, source="manual")
        recipe = Recipe(name="Pan margen", yield_qty=10, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=recipe.id,
                line_kind="ingredient",
                line_ref_id=flour.id,
                qty=100,
                line_unit="g",
            )
        )
        s.add(Product(name="Pan de margen", sale_price_gs=500, recipe_id=recipe.id))
        s.commit()
        flour_id = flour.id

    with session_factory() as s:
        rows = product_margins_for_ingredient(s, flour_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["sale_price_gs"] == 500
        assert row["margin_last_gs"] == 420
        assert row["margin_high_gs"] == 400
        events = s.scalars(
            select(IngredientPriceEvent).where(IngredientPriceEvent.ingredient_id == flour_id)
        ).all()
        assert len(events) == 2


def test_station_roles_are_assignable(client):
    payload = client.get("/users/api/roles").json()
    values = [row["value"] for row in payload["results"]]
    for role in ("admin", "cocina", "ventas", "inventario", "gerencia"):
        assert role in values
    assert "overview" not in values
    assert "escritorio" not in values


def test_cocina_recipe_list_hides_cost(client):
    cookie = _choose(client, "cocina")
    page = client.get("/recetas", headers={"cookie": cookie})
    assert page.status_code == 200
    assert "Costo del lote" not in page.text
