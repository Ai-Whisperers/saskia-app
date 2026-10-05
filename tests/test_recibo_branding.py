"""tests/test_recibo_branding.py — recibo branding business_name + RUC from settings.

Covers:
- /ventas/{id}/recibo renders branding.business_name from settings
- RUC shows only when non-empty in branding settings
"""

from datetime import datetime

import pytest

from app.rms.config import ASUNCION_TZ
from app.rms.models import Product, Sale


@pytest.fixture
def seeded_sales(session_factory):
    """Seed 2 sales for the recibo branding tests."""
    with session_factory() as s:
        p1 = Product(name="Pan dulce", sku="PAN-DUL", sale_price_gs=5000, recipe_id=None)
        p2 = Product(name="Torta", sku="TOR-001", sale_price_gs=10000, recipe_id=None)
        s.add_all([p1, p2]); s.flush()

        now = datetime.now(ASUNCION_TZ)
        s.add_all([
            Sale(product_id=p1.id, qty=1, unit_price_gs=5000, sold_at=now, voided_at=None),
            Sale(product_id=p2.id, qty=2, unit_price_gs=10000, sold_at=now, voided_at=None),
        ])
        s.commit()
        return {"p1": p1, "p2": p2}


# ---- branding tests ----

def test_recibo_renders_branding_business_name(client, seeded_sales, session_factory):
    """/ventas/{id}/recibo renders branding.business_name from settings."""
    with session_factory() as s:
        first = s.query(Sale).filter_by(voided_at=None).first()
        sale_id = first.id

    resp = client.get(f"/ventas/{sale_id}/recibo")
    assert resp.status_code == 200
    body = resp.text

    # Should contain the business name from branding
    assert "Saskia RMS" in body


def test_recibo_shows_ruc_when_set(client, session_factory):
    """RUC shows only when non-empty in branding settings."""
    with session_factory() as s:
        # Set branding with RUC
        from app.rms.settings_runtime import set_branding
        branding = set_branding(s, business_name="Mi Panadería", ruc="123456789")
        s.commit()

        # Create a sale
        p = Product(name="Test", sku="TEST", sale_price_gs=1000, recipe_id=None)
        s.add(p); s.flush()
        sale = Sale(product_id=p.id, qty=1, unit_price_gs=1000, sold_at=datetime.now(ASUNCION_TZ), voided_at=None)
        s.add(sale); s.commit()
        sale_id = sale.id

    resp = client.get(f"/ventas/{sale_id}/recibo")
    assert resp.status_code == 200
    body = resp.text

    # Should contain the business name and RUC
    assert "Mi Panadería" in body
    assert "RUC: 123456789" in body


def test_recibo_hides_ruc_when_empty(client, session_factory):
    """RUC is not shown when empty in branding settings."""
    with session_factory() as s:
        # Set branding with empty RUC
        from app.rms.settings_runtime import set_branding
        branding = set_branding(s, business_name="Mi Panadería", ruc="")
        s.commit()

        # Create a sale
        p = Product(name="Test", sku="TEST", sale_price_gs=1000, recipe_id=None)
        s.add(p); s.flush()
        sale = Sale(product_id=p.id, qty=1, unit_price_gs=1000, sold_at=datetime.now(ASUNCION_TZ), voided_at=None)
        s.add(sale); s.commit()
        sale_id = sale.id

    resp = client.get(f"/ventas/{sale_id}/recibo")
    assert resp.status_code == 200
    body = resp.text

    # Should contain the business name but not RUC
    assert "Mi Panadería" in body
    assert "RUC:" not in body
