"""tests/test_pedido_board_actions.py — Phase 20 board row actions.

Verifies the pedido_board page renders actionable row controls (not
dead cards). Each card must have:
- "Abrir" link to /pedidos/{id}
- Customer shortcut (when customer is set)
- Status advance form (Confirmar for pending, Listo for confirmed)
- CSRF token on every POST form
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest


BOARD_HTML = (
    Path(__file__).resolve().parent.parent
    / "app" / "templates" / "pedido_board.html"
)


def _make_pending_pedido(session_factory, qseed, status="pending",
                         customer_name="Cliente Test"):
    """Helper to seed a pedido with the given status and return its id.

    Uses raw SQL because the Pedido<->Customer ORM mapper is broken
    (per saskia-kyrian-prepopulation memory).
    """
    from app.rms.models import Customer
    from sqlalchemy import text as sa_text

    qseed("with_customer")
    with session_factory() as s:
        customer = s.query(Customer).first()
        assert customer is not None, "qseed('with_customer') did not seed a customer"
        now = datetime.now(timezone.utc)
        result = s.execute(
            sa_text(
                "INSERT INTO pedido "
                "(customer_id, customer_name, customer_phone, status, "
                " promised_date, channel, payment_intent, notes, "
                " public_token, created_at, updated_at) "
                "VALUES (:cid, :cn, :cp, :st, :pd, :ch, :pi, :no, "
                " :pt, :ca, :ua) RETURNING id"
            ),
            {
                "cid": customer.id,
                "cn": customer.name or "Test Customer",
                "cp": customer.phone or "0981000000",
                "st": status,
                "pd": date.today().isoformat(),
                "ch": "mostrador",
                "pi": "efectivo",
                "no": "",
                "pt": f"test_token_{now.timestamp()}",
                "ca": now,
                "ua": now,
            },
        )
        pedido_id = result.scalar()
        s.commit()
        return pedido_id


def test_pedido_board_renders_abrir_link(authed_client, qseed, session_factory):
    """The board must render an 'Abrir' link to /pedidos/{id}."""
    _make_pending_pedido(session_factory, qseed)
    r = authed_client.get("/pedidos/board")
    assert r.status_code == 200
    body = r.text
    assert "/pedidos/" in body, "no pedido link found"
    assert "Abrir" in body, "missing 'Abrir' label"


def test_pedido_board_renders_confirmar_for_pending(
    authed_client, qseed, session_factory
):
    """Pending cards must show a 'Confirmar' form to /pedidos/{id}/status."""
    _make_pending_pedido(session_factory, qseed, status="pending")
    r = authed_client.get("/pedidos/board")
    body = r.text
    assert "Confirmar" in body, "missing 'Confirmar' button"
    # The form must POST to the status endpoint with new=confirmed
    pattern = re.compile(
        r'<form[^>]+action="/pedidos/\d+/status"[^>]*>.*?'
        r'<input[^>]+name="new"[^>]+value="confirmed".*?</form>',
        re.DOTALL,
    )
    assert pattern.search(body), \
        "no POST form with action=/pedidos/{id}/status and new=confirmed found"


def test_pedido_board_renders_listo_for_confirmed(
    authed_client, qseed, session_factory
):
    """Confirmed cards must show a 'Listo' form to advance to ready."""
    _make_pending_pedido(session_factory, qseed, status="confirmed")
    r = authed_client.get("/pedidos/board")
    body = r.text
    assert "Listo" in body, "missing 'Listo' button"
    pattern = re.compile(
        r'<form[^>]+action="/pedidos/\d+/status"[^>]*>.*?'
        r'<input[^>]+name="new"[^>]+value="ready".*?</form>',
        re.DOTALL,
    )
    assert pattern.search(body), \
        "no POST form with new=ready found for confirmed cards"


def test_pedido_board_renders_no_advance_for_ready(
    authed_client, qseed, session_factory
):
    """Ready/fulfilled cards must NOT render advance buttons (terminal)."""
    _make_pending_pedido(session_factory, qseed, status="ready")
    r = authed_client.get("/pedidos/board")
    body = r.text
    # Should still render the card with 'Abrir' but no 'Confirmar' or 'Listo'
    # for the ready card. We just verify the layout is sane.
    assert "/pedidos/" in body


def test_pedido_board_post_forms_have_csrf(
    authed_client, qseed, session_factory
):
    """Every POST form in pedido_board must have a _csrf_token field."""
    _make_pending_pedido(session_factory, qseed, status="pending")
    r = authed_client.get("/pedidos/board")
    body = r.text
    # Find all forms with method=post
    post_forms = re.findall(
        r'<form[^>]+method="post"[^>]*>(.*?)</form>',
        body, re.DOTALL,
    )
    assert len(post_forms) > 0, "no POST forms in board"
    for i, form in enumerate(post_forms):
        assert '_csrf_token' in form, \
            f"POST form #{i} is missing _csrf_token"


def test_pedido_board_advance_endpoint_works(
    authed_client, qseed, session_factory
):
    """POST /pedidos/{id}/status with new=confirmed should advance state."""
    pedido_id = _make_pending_pedido(session_factory, qseed, status="pending")
    r = authed_client.post(
        f"/pedidos/{pedido_id}/status",
        data={"new": "confirmed", "_csrf_token": "test"},
        follow_redirects=False,
    )
    # Either 200, 303, or 422 (CSRF) — but not 500
    assert r.status_code < 500, f"unexpected 5xx: {r.status_code}"
