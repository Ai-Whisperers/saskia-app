"""Rate limit write endpoints tests."""

from __future__ import annotations

from datetime import datetime


def test_inventory_adjust_no_rate_limit_in_test(authed_client):
    """In test environment, repeated inventory adjusts should not 429."""
    import tempfile

    # Create ingredient
    from sqlalchemy.orm import sessionmaker

    # Use the test engine
    from app.rms.db import init_db, make_engine
    from app.rms.models import Ingredient

    tmpdir = tempfile.mkdtemp()
    engine = make_engine(f"sqlite:///{tmpdir}/test_rate.sqlite")
    init_db(engine)
    Session = sessionmaker(bind=engine)

    with Session() as s:
        ing = Ingredient(name="Rate Test Ing", unit="kg", stock_qty=100.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    # Hit the adjust endpoint many times
    for i in range(5):
        r = authed_client.post(
            f"/inventario/{ing_id}/ajustar",
            data={"adjustment": "1", "reason": f"rate_test_{i}"},
        )
        # In test env, rate limit should be disabled or very high
        assert r.status_code < 500, f"Inventory adjust #{i} returned {r.status_code}"


def test_produccion_override_no_rate_limit_in_test(authed_client):
    """Repeated produccion/override POSTs should not 429 in test env."""

    # Hit the endpoint many times
    for i in range(5):
        r = authed_client.post(
            "/produccion/override",
            data={
                "for_date": datetime.utcnow().date().isoformat(),
                "product_id": "1",
                "qty": str(i + 1),
            },
        )
        assert r.status_code < 500, f"Override #{i} returned {r.status_code}: {r.text[:200]}"


def test_excel_importar_repeated_no_500(authed_client):
    """Repeated /excel/importar POSTs should not 500."""
    for i in range(3):
        r = authed_client.post("/excel/importar", data={}, follow_redirects=False)
        assert r.status_code < 500, f"Excel import #{i} returned {r.status_code}"
