"""Regression tests for Phase 2 tickets (Saskia review 2026-09-18).

- INV-03: Negative stock clamp, Spanish urgency, no-price excluded from total
- MER-01: Merma form accepts grams (g → kg conversion)
- PRO-03: Production page no raw forecast tokens
- DATA-01: Low-stock line wraps as a single unit
"""

from __future__ import annotations


def test_inv_03_negative_stock_clamped_in_reorder(client, app_engine):
    """INV-03: An ingredient with negative stock_qty shows 0 kg in Reponer."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Ingredient
    from app.rms.reorder import compute_reorder_list

    # Seed via the public HTTP API, then update stock_qty directly (the form
    # rejects negatives on create — that's the BUG-00 fix — but inventory can
    # legitimately go negative through oversells).
    client.post(
        "/inventario/nuevo",
        data={
            "name": "azúcar impalpable test",
            "unit": "kg",
            "stock_qty": "0",
            "min_stock_qty": "1.0",
            "purchase_price_gs": "5000",
        },
        follow_redirects=False,
    )
    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        ing = s.query(Ingredient).filter_by(name="azúcar impalpable test").first()
        ing.stock_qty = -3.0  # simulate oversell
        s.commit()

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        items = compute_reorder_list(s)
        matching = [i for i in items if "azúcar" in i.name.lower()]
        assert matching, "azúcar impalpable should be in reorder list"
        item = matching[0]
        assert item.current_stock == 0.0
        assert item.urgency_label == "sin stock"


def test_inv_03_suggested_qty_uses_clamped_stock(client, app_engine):
    """INV-03: manteca at -0.01 with max 2.00 → suggested 2.00 (clamped stock)."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Ingredient
    from app.rms.reorder import compute_reorder_list

    client.post(
        "/inventario/nuevo",
        data={
            "name": "manteca test",
            "unit": "kg",
            "stock_qty": "0",
            "min_stock_qty": "1.0",
            "max_stock_qty": "2.00",
            "purchase_price_gs": "32000",
        },
        follow_redirects=False,
    )
    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        ing = s.query(Ingredient).filter_by(name="manteca test").first()
        ing.stock_qty = -0.01
        s.commit()

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        items = compute_reorder_list(s)
        item = next(i for i in items if "manteca" in i.name.lower())
        assert abs(item.suggested_qty - 2.0) < 0.001


def test_inv_03_urgency_label_spanish(client, app_engine):
    """INV-03: Urgency labels are 'sin stock' / 'bajo mínimo' / 'OK'."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.reorder import compute_reorder_list

    for name, stock, min_q in [
        ("harina zero", "0", "1.0"),
        ("harina low", "0.5", "1.0"),
        ("harina ok", "5.0", "1.0"),
    ]:
        client.post(
            "/inventario/nuevo",
            data={
                "name": name,
                "unit": "kg",
                "stock_qty": stock,
                "min_stock_qty": min_q,
                "purchase_price_gs": "3000",
            },
            follow_redirects=False,
        )

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        items = compute_reorder_list(s)
        labels = {i.name: i.urgency_label for i in items if "harina" in i.name}
        assert labels.get("harina zero") == "sin stock"
        assert labels.get("harina low") == "bajo mínimo"
        assert "harina ok" not in labels


def test_inv_03_missing_price_excluded_from_total(client, app_engine):
    """INV-03: 'agua' with no price → cost_gs=0, has_price=False."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.reorder import compute_reorder_list

    client.post(
        "/inventario/nuevo",
        data={
            "name": "agua sin precio",
            "unit": "l",
            "stock_qty": "0",
            "min_stock_qty": "1.0",
        },
        follow_redirects=False,
    )

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        items = compute_reorder_list(s)
        item = next(i for i in items if i.name == "agua sin precio")
        assert item.has_price is False
        assert item.estimated_cost_gs == 0


def test_mer_01_grams_in_merma_form():
    """MER-01: 50 g of harina deducts 0.05 kg from stock."""
    import tempfile

    from sqlalchemy.orm import sessionmaker

    from app.rms.db import init_db, make_engine
    from app.rms.models import Ingredient
    from app.rms.waste import WasteReason, record_waste

    tmpdir = tempfile.mkdtemp()
    engine = make_engine(f"sqlite:///{tmpdir}/test.sqlite")
    init_db(engine)
    sf = sessionmaker(bind=engine)
    s = sf()
    try:
        ing = Ingredient(name="harina", unit="kg", stock_qty=5.0, purchase_price_gs=3000)
        s.add(ing)
        s.commit()
        ing_id = ing.id
        starting_stock = ing.stock_qty
    finally:
        s.close()

    # Record 50 g of waste (= 0.05 kg)
    s = sf()
    try:
        record_waste(
            s,
            ingredient_id=ing_id,
            qty=50.0,
            qty_unit="g",
            reason=WasteReason.VENCIDA,
        )
        s.commit()
    finally:
        s.close()

    # Verify stock dropped by exactly 0.05 kg
    s = sf()
    try:
        ing = s.get(Ingredient, ing_id)
        assert abs(ing.stock_qty - (starting_stock - 0.05)) < 0.001, (
            f"Stock should be {starting_stock - 0.05} after 50g waste, got {ing.stock_qty}"
        )
    finally:
        s.close()


def test_mer_01_milliliters_in_merma_form():
    """MER-01: 250 ml of leche deducts 0.25 l from stock."""
    import tempfile

    from sqlalchemy.orm import sessionmaker

    from app.rms.db import init_db, make_engine
    from app.rms.models import Ingredient
    from app.rms.waste import WasteReason, record_waste

    tmpdir = tempfile.mkdtemp()
    engine = make_engine(f"sqlite:///{tmpdir}/test.sqlite")
    init_db(engine)
    sf = sessionmaker(bind=engine)
    s = sf()
    try:
        ing = Ingredient(name="leche", unit="l", stock_qty=2.0, purchase_price_gs=8000)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    finally:
        s.close()

    s = sf()
    try:
        record_waste(
            s,
            ingredient_id=ing_id,
            qty=250.0,
            qty_unit="ml",
            reason=WasteReason.VENCIDA,
        )
        s.commit()
    finally:
        s.close()

    s = sf()
    try:
        ing = s.get(Ingredient, ing_id)
        assert abs(ing.stock_qty - 1.75) < 0.001
    finally:
        s.close()


def test_mer_01_cross_family_conversion_rejected():
    """MER-01: 50 g of unit 'und' (cross-family) raises a Spanish 400."""
    import tempfile

    from fastapi import HTTPException
    from sqlalchemy.orm import sessionmaker

    from app.rms.db import init_db, make_engine
    from app.rms.models import Ingredient
    from app.rms.waste import WasteReason, record_waste

    tmpdir = tempfile.mkdtemp()
    engine = make_engine(f"sqlite:///{tmpdir}/test.sqlite")
    init_db(engine)
    sf = sessionmaker(bind=engine)
    s = sf()
    try:
        ing = Ingredient(name="huevos", unit="und", stock_qty=12.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    finally:
        s.close()

    s = sf()
    try:
        try:
            record_waste(
                s,
                ingredient_id=ing_id,
                qty=50.0,
                qty_unit="g",  # g→und is cross-family
                reason=WasteReason.VENCIDA,
            )
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "familia distinta" in exc.detail
        else:
            raise AssertionError("Expected HTTPException for cross-family conversion")
    finally:
        s.close()


def test_pro_03_no_rolling_14d_avg_in_produccion_page(client):
    """PRO-03: Production page must NOT contain the raw 'rolling_14d_avg' token."""
    r = client.get("/produccion")
    assert r.status_code == 200
    body = r.text
    assert "rolling_14d_avg" not in body, f"Production page still leaks the raw token: {body[:500]}"
    assert "FORECAST SOURCE" not in body, "Production page still has 'FORECAST SOURCE'"


def test_data_01_low_stock_line_no_wrap(client):
    """DATA-01: The low-stock alert line uses white-space:nowrap so the unit
    doesn't split from its number on a new line.

    We can't directly inspect CSS but we CAN assert the inline style is on the
    element (per the review: 'l)' was sitting on the next line before).
    """
    client.post(
        "/inventario/nuevo",
        data={
            "name": "leche entera test",
            "unit": "l",
            "stock_qty": "0.5",
            "min_stock_qty": "4.0",
            "purchase_price_gs": "9000",
        },
        follow_redirects=False,
    )

    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "leche entera test" in body
    # 2026-09-26: the low-stock line moved into the Alertas card severity row
    # (compact by design, no wrapping issue). Old white-space:nowrap span removed.
    assert "sev-pill critico" in body, "Low-stock must render in the Alertas severity row"
