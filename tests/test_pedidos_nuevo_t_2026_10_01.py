"""T-2026-10-01 hardening pass for /pedidos/nuevo.

Three defensive features added together:

  - /produccion/api/forecast (GET): JSON endpoint that returns the
    production-plan rows for a date, filterable by product_id. Powers
    the in-form "Pediste N pero el plan dice M" warning.

  - Inline delivery-min preview: when a delivery zone with min_order_gs
    is selected, the form shows the gap (or surplus) vs the current
    cart total in real time — replaces the silent backend `[WARN]`
    appended to notes.

  - POST idempotency: the JS submit handler generates a client-side
    UUID and includes it in the form. If two POSTs arrive within the
    same window with the same key, the second one redirects to the
    first pedido's detail page instead of creating a duplicate.

Run: cd /opt/data/profiles/ivan/scratch/sazon-app-work \\
     && ./.venv/bin/python -m pytest tests/test_pedidos_nuevo_t_2026_10_01.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.rms.models import (
    AppMeta,
    DeliveryZone,
    Ingredient,
    Pedido,
    Product,
    Recipe,
    RecipeLine,
    Sale,
)

# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


def _seed_product(session_factory, name="Croissant", price=12000) -> int:
    with session_factory() as s:
        prod = Product(name=name, sale_price_gs=price)
        s.add(prod)
        s.commit()
        return prod.id


def _seed_zone(
    session_factory,
    *,
    code="Z1",
    name="Centro",
    min_order_gs=30000,
    delivery_cost_gs=5000,
) -> int:
    with session_factory() as s:
        z = DeliveryZone(
            code=code,
            name=name,
            min_order_gs=min_order_gs,
            delivery_cost_gs=delivery_cost_gs,
            is_active=True,
        )
        s.add(z)
        s.commit()
        return z.id


def _seed_product_with_recipe(
    session_factory,
    *,
    name="Chipa",
    price=10000,
    avg_daily_sales=20.0,
) -> int:
    """Create a product + ingredient + recipe with enough history that
    plan_production() will produce a non-zero forecast. The ingredient
    name is suffixed with the product name so two products in one test
    don't collide on the UNIQUE constraint."""
    ing_name = f"Harina-{name}"
    with session_factory() as s:
        ing = Ingredient(
            name=ing_name,
            unit="kg",
            stock_qty=100.0,
            purchase_price_gs=5000,
        )
        s.add(ing)
        s.flush()
        recipe = Recipe(name=f"R-{name}", yield_qty=10, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=recipe.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=0.5,
            )
        )
        prod = Product(name=name, sale_price_gs=price, recipe_id=recipe.id)
        s.add(prod)
        s.flush()
        # Seed enough sales history that the rolling-14-day average lands
        # near `avg_daily_sales` for tomorrow.
        for d in range(1, 15):
            sold_day = datetime.utcnow().date() - timedelta(days=d)
            s.add(
                Sale(
                    product_id=prod.id,
                    qty=avg_daily_sales,
                    unit_price_gs=price,
                    sold_at=datetime.combine(sold_day, datetime.min.time()),
                    channel="mostrador",
                    tz="America/Asuncion",
                )
            )
        s.commit()
        return prod.id


# --------------------------------------------------------------------------- #
# 1. /produccion/api/forecast endpoint
# --------------------------------------------------------------------------- #


def test_forecast_api_returns_plan_rows(client, session_factory):
    """GET /produccion/api/forecast returns qty_to_produce per product for a date."""
    pid = _seed_product_with_recipe(session_factory, name="ForecastCroissant", avg_daily_sales=10.0)
    target = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

    resp = client.get(f"/produccion/api/forecast?for_date={target}&product_id={pid}")
    assert resp.status_code == 200, resp.text[:300]
    body = resp.json()
    assert body["for_date"] == target
    rows = body["rows"]
    assert isinstance(rows, list)
    assert any(r["product_id"] == pid for r in rows), (
        f"product {pid} missing from forecast; got {[r['product_id'] for r in rows]}"
    )
    for r in rows:
        assert {
            "product_id",
            "product_name",
            "qty_to_produce",
            "forecast_source",
            "confidence_pct",
        } <= set(r)


def test_forecast_api_without_product_id_returns_all(client, session_factory):
    """No product_id filter → returns the full plan."""
    _seed_product_with_recipe(session_factory, name="ForecastMuffin", avg_daily_sales=5.0)
    target = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

    resp = client.get(f"/produccion/api/forecast?for_date={target}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rows"]) >= 1


def test_forecast_api_rejects_bad_date(client):
    """Bad date format → 400, not 500."""
    resp = client.get("/produccion/api/forecast?for_date=not-a-date")
    assert resp.status_code == 400
    assert "for_date" in resp.json().get("detail", "").lower()


def test_forecast_api_filters_to_single_product(client, session_factory):
    """product_id filter narrows to just that row."""
    p1 = _seed_product_with_recipe(session_factory, name="FiltA", avg_daily_sales=10.0)
    _seed_product_with_recipe(session_factory, name="FiltB", avg_daily_sales=20.0)
    target = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

    resp = client.get(f"/produccion/api/forecast?for_date={target}&product_id={p1}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["product_id"] == p1


# --------------------------------------------------------------------------- #
# 2. Inline delivery-min preview (template + data)
# --------------------------------------------------------------------------- #


def test_pedidos_nuevo_renders_delivery_zones_data_block(client, session_factory):
    """The template ships a <script id="delivery-zones-data"> with each zone's min_order."""
    _seed_zone(
        session_factory,
        code="Z-DP-1",
        name="Asunción Centro",
        min_order_gs=40000,
        delivery_cost_gs=5000,
    )

    resp = client.get("/pedidos/nuevo")
    assert resp.status_code == 200, resp.text[:300]
    html = resp.text
    # The data block exists and carries the zone info
    assert 'id="delivery-zones-data"' in html, "delivery-zones-data script block missing"
    assert 'id="delivery-min-preview"' in html, "delivery-min-preview div missing"
    # JSON payload contains the zone (HTML-escaped)
    assert "Asunción Centro" in html or "Asunci" in html
    assert "40000" in html  # min_order_gs


def test_pedidos_nuevo_renders_idempotency_key_field(client):
    """Hidden idempotency_key input present in the form."""
    resp = client.get("/pedidos/nuevo")
    assert resp.status_code == 200
    html = resp.text
    assert 'name="idempotency_key"' in html
    assert 'id="idempotency-key-input"' in html


def test_pedidos_nuevo_renders_line_stock_warning_row(client):
    """Per-line meta row present (hidden until JS reveals it)."""
    resp = client.get("/pedidos/nuevo")
    assert resp.status_code == 200
    html = resp.text
    assert "line-row-meta" in html
    assert "line-stock-warning" in html


# --------------------------------------------------------------------------- #
# 3. POST idempotency
# --------------------------------------------------------------------------- #


def test_post_pedido_with_idempotency_key_creates_one_pedido(client, session_factory):
    """First POST with a key creates the pedido and stamps the cache row."""
    pid = _seed_product(session_factory, name="IdemProd", price=12000)
    target = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
    idem_key = "11111111-1111-4111-8111-111111111111"

    resp = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Idem Cliente",
            "promised_date": target,
            "promised_time": "10:00",
            "channel": "whatsapp",
            "payment_intent": "efectivo",
            "idempotency_key": idem_key,
            "line_product_id": [str(pid)],
            "line_qty": ["2"],
            "line_unit_price_gs": ["12000"],
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text[:300]
    location = resp.headers.get("location", "")
    assert "/pedidos/" in location

    # Verify the pedido exists AND the cache row was stamped
    with session_factory() as s:
        pedidos = s.execute(select(Pedido)).scalars().all()
        assert len(pedidos) == 1
        pedido_id = pedidos[0].id

        cache = s.scalar(select(AppMeta).where(AppMeta.key == f"pedido_idem:{idem_key}"))
        assert cache is not None, "idempotency cache row missing"
        import json

        payload = json.loads(cache.value)
        assert payload["pedido_id"] == pedido_id

    # The redirect location matches the stamped pedido_id
    assert str(pedido_id) in location


def test_post_pedido_repeated_idempotency_key_redirects_to_original(client, session_factory):
    """Second POST with the same key → 303 to the original pedido, no new pedido."""
    pid = _seed_product(session_factory, name="IdemProd2", price=8000)
    target = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
    idem_key = "22222222-2222-4222-8222-222222222222"

    data = {
        "customer_name": "Repite",
        "promised_date": target,
        "promised_time": "10:00",
        "channel": "whatsapp",
        "payment_intent": "efectivo",
        "idempotency_key": idem_key,
        "line_product_id": [str(pid)],
        "line_qty": ["3"],
        "line_unit_price_gs": ["8000"],
    }

    # First POST
    r1 = client.post("/pedidos/nuevo", data=data, follow_redirects=False)
    assert r1.status_code in (302, 303)
    first_loc = r1.headers.get("location", "")

    # Second POST — same key, different customer_name to detect a
    # second insert
    data2 = dict(data)
    data2["customer_name"] = "REPITE — no debería ganar"
    r2 = client.post("/pedidos/nuevo", data=data2, follow_redirects=False)
    assert r2.status_code in (302, 303)
    second_loc = r2.headers.get("location", "")

    # Same target
    assert first_loc == second_loc, (
        f"second POST redirected to {first_loc!r}, expected the same {second_loc!r}"
    )

    # And exactly ONE pedido was created
    with session_factory() as s:
        pedidos = s.execute(select(Pedido)).scalars().all()
        assert len(pedidos) == 1, (
            f"expected 1 pedido, got {len(pedidos)}; second POST was not deduplicated"
        )
        # Customer name is the FIRST one, not the second
        assert pedidos[0].customer_name == "Repite"


def test_post_pedido_without_idempotency_key_still_works(client, session_factory):
    """No key → still creates (back-compat: form works without it)."""
    pid = _seed_product(session_factory, name="NoKey", price=10000)
    target = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

    resp = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Sin key",
            "promised_date": target,
            "promised_time": "10:00",
            "channel": "whatsapp",
            "payment_intent": "efectivo",
            # no idempotency_key
            "line_product_id": [str(pid)],
            "line_qty": ["1"],
            "line_unit_price_gs": ["10000"],
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text[:300]
    with session_factory() as s:
        pedidos = s.execute(select(Pedido)).scalars().all()
        assert len(pedidos) == 1


def test_post_pedido_different_idempotency_keys_create_distinct_pedidos(client, session_factory):
    """Two requests, two different keys → two pedidos (no false dedup)."""
    pid = _seed_product(session_factory, name="TwoKeys", price=5000)
    target = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

    for key in ["key-aaa-001", "key-bbb-002"]:
        resp = client.post(
            "/pedidos/nuevo",
            data={
                "customer_name": f"Cliente {key}",
                "promised_date": target,
                "promised_time": "10:00",
                "channel": "whatsapp",
                "payment_intent": "efectivo",
                "idempotency_key": key,
                "line_product_id": [str(pid)],
                "line_qty": ["1"],
                "line_unit_price_gs": ["5000"],
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

    with session_factory() as s:
        pedidos = s.execute(select(Pedido)).scalars().all()
        assert len(pedidos) == 2
