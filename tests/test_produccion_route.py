"""tests/test_produccion_route.py — /produccion route tests."""

from __future__ import annotations


def test_produccion_renders_empty(client):
    """GET /produccion returns 200 even with no data."""
    resp = client.get("/produccion")
    assert resp.status_code == 200
    body = resp.text
    assert "Producción" in body or "Plan de producción" in body


# ---------------------------------------------------------------- P0:D.2
def test_produccion_accepts_shift_am_query_param(client):
    """GET /produccion?shift=AM renders the AM shift badge."""
    resp = client.get("/produccion?shift=AM")
    assert resp.status_code == 200
    body = resp.text
    assert "Turno AM" in body, (
        "P0:D.2 — when ?shift=AM is in the URL, page must show 'Turno AM' badge"
    )
    assert 'data-shift="AM"' in body, (
        "P0:D.2 — AM badge must carry data-shift='AM' for testability"
    )


def test_produccion_accepts_shift_pm_query_param(client):
    """GET /produccion?shift=PM renders the PM shift badge."""
    resp = client.get("/produccion?shift=PM")
    assert resp.status_code == 200
    body = resp.text
    assert "Turno PM" in body, (
        "P0:D.2 — when ?shift=PM is in the URL, page must show 'Turno PM' badge"
    )
    assert 'data-shift="PM"' in body


def test_produccion_no_shift_param_omits_badge(client):
    """GET /produccion (no shift) must NOT render the shift badge."""
    resp = client.get("/produccion")
    assert resp.status_code == 200
    body = resp.text
    # The shift-badge span is conditional on {% if shift %}.
    # If absent, neither "Turno AM" nor "Turno PM" appears in the header.
    # (Note: 'Turno' might appear elsewhere in copy — check the badge
    # data-attribute is absent.)
    assert 'data-shift="AM"' not in body, (
        "P0:D.2 — without ?shift=, no AM badge should render"
    )
    assert 'data-shift="PM"' not in body, (
        "P0:D.2 — without ?shift=, no PM badge should render"
    )


def test_produccion_rejects_invalid_shift_value(client):
    """?shift=invalid must be rejected (422 from pattern validation)."""
    resp = client.get("/produccion?shift=MIDNIGHT")
    assert resp.status_code in (400, 422), (
        f"P0:D.2 — invalid shift value must 4xx, got {resp.status_code}"
    )
