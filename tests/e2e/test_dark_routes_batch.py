"""tests/e2e/test_dark_routes_batch.py — the 5 true dark routes (expansion
item 1): routes that had NO test of any kind until now.

  POST /produccion-planner/compute   — core planning workflow + auto
                                       shopping-list materialization
  POST /vs-mercado/{id}/save         — competitor price save
  POST /wishlist/{id}/send-to-shopping-list — equipment → buy-list handoff
  POST /productos/upload-image       — incl. upload bombs (size/type)
  POST+GET /recetas/{id}/set-photo   — photo picker (was: hardcoded dev path)
"""

from __future__ import annotations

import pytest

from app.rms.models import MarketBenchmark, ShoppingListItem, WishlistItem
from tests.factories import (
    ing_line,
    make_ingredient,
    make_product,
    make_recipe,
)

pytestmark = [pytest.mark.smoke]


# ─── production planner ────────────────────────────────────────────────


def test_planner_compute_shows_shortage_and_materializes_shopping_list(client, session_factory):
    with session_factory() as s:
        ing = make_ingredient(s, name="Harina planner", stock_qty=1.0, purchase_price_gs=5000)
        rec = make_recipe(s, name="Pan planner", lines=[ing_line(ing, qty=2.0)])
        rec.yield_qty = 1.0
        s.commit()
        rid = rec.id

    # 5 batches × 2 kg = 10 needed vs 1 in stock → 9 short
    r = client.post("/produccion-planner/compute", data={"recipe_id": rid, "batches": 5})
    assert r.status_code == 200
    assert "Harina planner" in r.text
    assert "9" in r.text  # shortage qty

    # shortfall auto-materialized into the shopping list
    with session_factory() as s:
        items = s.query(ShoppingListItem).filter_by(ingredient_id=ing.id).all()
        assert items, "planner did not materialize shopping-list items"
        assert abs(items[0].qty_to_buy - 9.0) < 1e-6


def test_planner_compute_sufficient_stock_no_shopping_rows(client, session_factory):
    with session_factory() as s:
        ing = make_ingredient(s, name="Sal planner", stock_qty=100.0)
        rec = make_recipe(s, name="Chipa planner", lines=[ing_line(ing, qty=0.1)])
        s.commit()
        rid = rec.id
        iid = ing.id
    r = client.post("/produccion-planner/compute", data={"recipe_id": rid, "batches": 2})
    assert r.status_code == 200
    with session_factory() as s:
        assert s.query(ShoppingListItem).filter_by(ingredient_id=iid).count() == 0


def test_planner_compute_bad_input_redirects(client):
    r = client.post("/produccion-planner/compute", data={"recipe_id": 999999, "batches": 1})
    assert str(r.url).endswith("/produccion-planner")  # redirected
    r2 = client.post("/produccion-planner/compute", data={"recipe_id": 1, "batches": 0})
    assert str(r2.url).endswith("/produccion-planner")


# ─── vs-mercado benchmark save ─────────────────────────────────────────


def test_vs_mercado_save_persists_prices(client, session_factory):
    with session_factory() as s:
        b = MarketBenchmark(product_label="Chipa grande", our_retail_gs=5000)
        s.add(b)
        s.commit()
        bid = b.id
    r = client.post(
        f"/vs-mercado/{bid}/save",
        data={
            "our_wholesale_gs": 4000,
            "our_retail_gs": 5500,
            "comp_min_gs": 5000,
            "comp_avg_gs": 6000,
            "market_avg_gs": 5800,
            "source": "relevamiento local",
        },
    )
    assert r.status_code == 200
    with session_factory() as s:
        b2 = s.get(MarketBenchmark, bid)
        assert b2.our_retail_gs == 5500
        assert b2.comp_avg_gs == 6000
        assert b2.source == "relevamiento local"


def test_vs_mercado_save_unknown_redirects(client):
    r = client.post(
        "/vs-mercado/999999/save",
        data={
            "our_wholesale_gs": 0,
            "our_retail_gs": 0,
            "comp_min_gs": 0,
            "comp_avg_gs": 0,
            "market_avg_gs": 0,
            "source": "",
        },
    )
    assert str(r.url).endswith("/vs-mercado")  # redirected (unknown id)


# ─── wishlist → shopping list ──────────────────────────────────────────


def test_wishlist_send_to_shopping_list_creates_equipment_row(client, session_factory):
    with session_factory() as s:
        w = WishlistItem(
            name="Batidora industrial", priority="must_have", quantity=1, unit_price_gs=1_500_000
        )
        s.add(w)
        s.commit()
        wid = w.id
    r = client.post(f"/wishlist/{wid}/send-to-shopping-list")
    assert "shopping-list" in str(r.url)  # redirected to the list
    with session_factory() as s:
        sl = (
            s.query(ShoppingListItem)
            .filter(ShoppingListItem.purpose_text.like(f"Wishlist #{wid}%"))
            .all()
        )
        assert sl, "wishlist handoff did not create a shopping row"
        assert sl[0].qty_to_buy == 1


def test_wishlist_send_twice_idempotent_no_dupes(client, session_factory):
    with session_factory() as s:
        w = WishlistItem(
            name="Freezer", priority="nice_to_have", quantity=1, unit_price_gs=3_000_000
        )
        s.add(w)
        s.commit()
        wid = w.id
    client.post(f"/wishlist/{wid}/send-to-shopping-list")
    client.post(f"/wishlist/{wid}/send-to-shopping-list")
    with session_factory() as s:
        n = (
            s.query(ShoppingListItem)
            .filter(ShoppingListItem.purpose_text.like(f"Wishlist #{wid}%"))
            .count()
        )
        assert n == 1, f"double-send created {n} rows — equipment ingredient dupes"


def test_wishlist_mark_purchased_flow(client, session_factory):
    with session_factory() as s:
        w = WishlistItem(name="Moldes", priority="must_have", quantity=2, unit_price_gs=80_000)
        s.add(w)
        s.commit()
        wid = w.id
    client.post(f"/wishlist/{wid}/mark-purchased")
    with session_factory() as s:
        assert s.get(WishlistItem, wid).purchased is True
    # purchased item refuses re-send
    r2 = client.post(f"/wishlist/{wid}/send-to-shopping-list")
    assert "comprado" in str(r2.url).lower() or "wishlist" in str(r2.url)


# ─── product image upload — happy + bombs ──────────────────────────────

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c626001000000ffff030000060005"
    "57bfabd40000000049454e44ae426082"
)


def _upload(client, path, content, ctype, filename="img.png"):
    return client.post(path, files={"file": (filename, content, ctype)})


def test_product_upload_image_happy_path(client, session_factory):
    with session_factory() as s:
        make_product(s, name="Subida img")
        s.commit()
    r = _upload(client, "/productos/upload-image", PNG_1X1, "image/png")
    assert r.status_code == 200
    assert r.json()["url"].startswith("/static/uploads/")


def test_product_upload_rejects_oversized(client):
    bomb = b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024)  # 6 MB > 5 MB
    r = _upload(client, "/productos/upload-image", bomb, "image/png", filename="bomb.png")
    assert r.status_code == 413


def test_product_upload_rejects_wrong_type(client):
    svg_xss = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'
    r = _upload(client, "/productos/upload-image", svg_xss, "image/svg+xml", filename="evil.svg")
    assert r.status_code == 415


def test_product_upload_rejects_empty(client):
    r = _upload(client, "/productos/upload-image", b"", "image/png", filename="empty.png")
    assert r.status_code in (400, 422)


# ─── recipe set-photo (picker + persist) ───────────────────────────────


def test_recipe_set_photo_picker_and_save(client, session_factory):
    with session_factory() as s:
        rec = make_recipe(s, name="Con foto")
        s.commit()
        rid = rec.id
    r = client.get(f"/recetas/{rid}/set-photo")
    assert r.status_code == 200
    # POST persists the chosen photo (photo comes from the curated dir —
    # only the filename is stored, never a client path)
    r2 = client.post(f"/recetas/{rid}/set-photo", data={"photo": "pan.jpg"})
    assert "set-photo" in str(r2.url)  # redirected back to the picker
    with session_factory() as s:
        from app.rms.models import Recipe

        assert s.get(Recipe, rid).image_url == "/static/recipes/pan.jpg"


def test_pedidos_export_csv_route_ordering(client):
    """Bug #16: /pedidos/export-csv was declared AFTER /{pedido_id}, so the
    path param route swallowed 'export-csv' → 400 'pedido_id debe ser un
    número entero' for EVERY user. Static routes must precede param routes."""
    r = client.get("/pedidos/export-csv?status_filter=todos")
    assert r.status_code == 200, f"export-csv broken again: {r.status_code}"
    assert "pedido_id" not in r.text[:200] or "text/csv" in r.headers.get("content-type", "")
