"""tests/test_rate_limit_write_endpoints.py — protect state-changing routes."""
from __future__ import annotations


def test_ventas_nueva_rate_limited_after_burst(client, session_factory):
    """After 30 rapid POSTs, the next one must hit 429.

    Default cap is 10 writes/minute per IP; we exceed it deliberately.
    """
    from starlette.testclient import TestClient

    from app.rms.csrf import generate_csrf_token
    from app.rms.main import app
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(name="RateLimitProd", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.commit()
        pid = p.id

    csrf = generate_csrf_token()
    tc = TestClient(app, raise_server_exceptions=False, cookies={"csrf_token": csrf})

    # Try 25 rapid writes. Default rate-limit cap is 10/min/IP.
    statuses = []
    for _ in range(25):
        resp = tc.post(
            "/ventas/nueva",
            data={"product_id": str(pid), "qty": "1", "discount_gs": "0"},
        )
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            return  # rate-limit kicked in, test passes

    assert 429 in statuses, f"Expected 429 in statuses, got: {statuses}"


def test_merma_registrar_rate_limited(client, session_factory):
    """Same cap on /merma/registrar."""
    from starlette.testclient import TestClient

    from app.rms.csrf import generate_csrf_token
    from app.rms.main import app
    from app.rms.models import Ingredient

    with session_factory() as s:
        ing = Ingredient(name="RL_ing", unit="g", stock_qty=1000, purchase_price_gs=1000)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    csrf = generate_csrf_token()
    tc = TestClient(app, raise_server_exceptions=False, cookies={"csrf_token": csrf})

    statuses = []
    for _ in range(20):
        resp = tc.post(
            "/merma/registrar",
            data={
                "ingredient_id": str(ing_id),
                "qty": "1",
                "reason": "vencida",
            },
        )
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            return

    assert 429 in statuses, f"Expected 429 in statuses, got: {statuses}"
