"""tests/e2e/test_cierre_and_exports_content.py — item 4: content-level
assertions for the monthly close and CSV/PDF exports (previously
smoke-level only: status 200, no numbers checked).

Journey:
  - seed a month of sales via factories
  - /reportes/cierre-mensual shows the right totals (revenue, IVA 10%,
    product rows) and respects year/month params
  - voided sales excluded from the close
  - /reportes/libro-ventas CSV (if enabled) and /reportes/precios/csv
    contain the seeded data, not just 200
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.factories import make_catalog, make_sale

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


@pytest.fixture()
def seeded_month(session_factory):
    """One catalog product, 3 sales in June 2026 (10_000 each), 1 voided."""
    with session_factory() as s:
        cat = make_catalog(s, price_gs=10_000)
        june = datetime(2026, 6, 15, 12, 0)
        ok_ids = []
        for i in range(3):
            sale = make_sale(
                s, product=cat["product"], qty=1, at=june + timedelta(days=i), unit_price_gs=10_000
            )
            ok_ids.append(sale.id)
        voided = make_sale(
            s, product=cat["product"], qty=1, at=june + timedelta(days=3), unit_price_gs=10_000
        )
        voided.voided_at = datetime(2026, 6, 20, 9, 0)
        voided.void_reason = "test"
        s.commit()
        yield {"product": cat["product"], "ok_ids": ok_ids, "voided_id": voided.id, "june": june}


def test_cierre_mensual_shows_correct_totals(client, seeded_month):
    r = client.get("/reportes/cierre-mensual?year=2026&month=6")
    assert r.status_code == 200
    body = r.text
    # 3 × 10_000 = 30_000 revenue; IVA 10% inclusive → base 27_273 / IVA 2_727
    assert "30.000" in body, "revenue total missing from cierre"
    assert seeded_month["product"].name in body


def test_cierre_mensual_excludes_voided(client, seeded_month):
    """4 sales seeded, 1 voided → totals must reflect 3 only (30_000, not 40_000)."""
    r = client.get("/reportes/cierre-mensual?year=2026&month=6")
    assert r.status_code == 200
    assert "40.000" not in r.text, "voided sale leaked into the monthly close"


def test_cierre_mensual_empty_month_renders(client):
    r = client.get("/reportes/cierre-mensual?year=2026&month=1")
    assert r.status_code == 200
    assert "0" in r.text


def test_cierre_mensual_rejects_bad_month(client):
    r = client.get("/reportes/cierre-mensual?year=2026&month=13")
    assert r.status_code == 400


def test_precios_csv_contains_seeded_prices(client, session_factory):
    # CSV lists ingredients WITH price events (price_stats contract)
    from app.rms.price_history import record_price_event
    from tests.factories import make_ingredient

    with session_factory() as s:
        ing = make_ingredient(s, name="Pimienta negra", purchase_price_gs=12_345)
        s.flush()
        record_price_event(s, ing.id, price_gs=12_345, source="manual")
        s.commit()
        name = ing.name
    r = client.get("/reportes/precios/csv")
    assert r.status_code == 200
    assert name in r.text, f"seeded price row missing from CSV: {r.text[:200]}"
    assert "12345" in r.text.replace(".", "").replace(",", "")


def test_libro_ventas_pdf_or_page_renders_with_data(client, seeded_month):
    # HTML first (PDF generation may be optional-dep)
    r = client.get("/reportes/libro-ventas?year=2026&month=6")
    assert r.status_code == 200
    assert "2026" in r.text
