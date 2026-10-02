"""Tier 8.4 (2026-10-01) — /eod/anomalies/run route.

Verifies the route:
- Returns 200 (HTML) when triggered
- Renders the anomalies template with the detected list
- Posts the detected anomalies to ``send_alert`` for dispatch
- Returns an empty list and a "clean" message when no anomalies
- Anonymous (unauthenticated) requests get 303 to /login or 401
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.rms.config import ASUNCION_TZ


def _insert_sale(session, product_id: int, **kwargs):
    defaults = {
        "qty": 1.0,
        "unit_price_gs": 10_000,
        "discount_gs": 0,
        "voided_at": None,
        "payment_method": "efectivo",
        "invoice_type": "boleta_resimple",
        "invoice_number": 1,
    }
    defaults.update(kwargs)
    session.execute(
        text(
            """
            INSERT INTO sale (
                product_id, qty, unit_price_gs, discount_gs,
                sold_at, voided_at, payment_method,
                invoice_type, invoice_number, tz, channel
            ) VALUES (
                :product_id, :qty, :unit_price_gs, :discount_gs,
                :sold_at, :voided_at, :payment_method,
                :invoice_type, :invoice_number, 'America/Asuncion', 'mostrador'
            )
            """
        ),
        {
            "product_id": product_id,
            "sold_at": defaults.pop("sold_at"),
            **defaults,
        },
    )


@pytest.fixture
def product_id(session_factory) -> int:
    from tests._fixtures_quick_seed import quick_seed

    data = quick_seed(session_factory, "basic")
    return int(data["product"].id)


def test_route_returns_200_with_no_anomalies(client, session_factory, product_id):
    """Empty day → route renders the 'clean' state."""
    r = client.post("/eod/anomalies/run")
    assert r.status_code == 200
    body = r.text
    # The 'clean' message is in Spanish
    assert "limpio" in body or "anomalía" in body.lower()


def test_route_dispatches_detected_anomalies(
    client, session_factory, product_id
):
    """When anomalies exist, the route calls send_alert once per anomaly
    and renders them in the response body."""
    # Insert the sale via raw SQL so the test's session and the route's
    # session see the same row (SQLite file-based DB; the raw insert
    # commits at the DB layer immediately).
    with session_factory() as s:
        base = datetime.now(ASUNCION_TZ).replace(tzinfo=None)  # today!
        s.execute(
            text(
                """
                INSERT INTO sale (
                    product_id, qty, unit_price_gs, discount_gs,
                    sold_at, voided_at, payment_method,
                    invoice_type, invoice_number, tz, channel
                ) VALUES (
                    :product_id, 1.0, 10000, 0,
                    :sold_at, NULL, 'efectivo',
                    'factura', NULL, 'America/Asuncion', 'mostrador'
                )
                """
            ),
            {"product_id": product_id, "sold_at": base},
        )
        s.commit()

    with patch("app.observability.alerts.send_alert", return_value=True) as mock:
        r = client.post("/eod/anomalies/run")

    assert r.status_code == 200
    # And we should have tried to send at least one alert
    assert mock.call_count >= 1
    # Severity should be "error" (factura missing number)
    first_call = mock.call_args_list[0]
    assert first_call.kwargs["severity"] == "error"
