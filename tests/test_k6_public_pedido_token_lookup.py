"""K6: Public pedido token lookup at /p/{token} must work.

The 2026-09-21 hotfix made the `/p/{public_token}` endpoint resolve by token,
NOT by integer PK (which would let users enumerate pedidos via /p/1, /p/2, ...).

This test guards against regressions:
- Valid token returns 200 with the pedido detail
- Tampered/short token returns 404
- Integer-style path (e.g., /p/123) returns 404 (must be token, not PK)
- Unknown token returns 404
"""
from __future__ import annotations

import pytest
from datetime import datetime, date
from app.rms.models import Pedido


def test_public_pedido_token_returns_200(client, session_factory):
    """K6 #1: GET /p/{valid_token} returns 200 with pedido detail."""
    # Create a pedido with a known token
    with session_factory() as s:
        pedido = Pedido(
            customer_name="K6 Test Customer",
            customer_phone="+595991234567",
            promised_date=date.today(),
            promised_time="14:00",
            channel="whatsapp",
            status="pending",
            public_token="k6test01",
        )
        s.add(pedido)
        s.commit()

    r = client.get("/p/k6test01")
    assert r.status_code == 200, (
        f"/p/k6test01 returned {r.status_code}: {r.text[:200]}"
    )
    # Body should mention the customer
    body = r.text
    assert "K6 Test Customer" in body or "k6test01" in body, (
        f"Public page missing pedido info: {body[:500]}"
    )


def test_public_pedido_unknown_token_returns_404(client):
    """K6 #2: GET /p/{unknown_token} returns 404."""
    r = client.get("/p/nonexistent_token_zzz")
    assert r.status_code == 404, (
        f"/p/nonexistent returned {r.status_code}, expected 404"
    )


def test_public_pedido_integer_path_returns_404(client, session_factory):
    """K6 #3: /p/123 must NOT resolve by integer PK — must be token-based."""
    from app.rms.models import Pedido
    # Create a pedido
    with session_factory() as s:
        pedido = Pedido(
            customer_name="K6 PK Test",
            promised_date=date.today(),
            channel="mostrador",
            public_token="k6pk01",
        )
        s.add(pedido)
        s.commit()
        pedido_id = pedido.id

    # Try /p/{id} — should NOT work (token lookup only)
    r = client.get(f"/p/{pedido_id}")
    assert r.status_code == 404, (
        f"/p/{pedido_id} returned {r.status_code}, expected 404. "
        f"Endpoint must require token, not integer PK. "
        f"This prevents enumeration attacks."
    )

    # The token route should still work
    r2 = client.get("/p/k6pk01")
    assert r2.status_code == 200, (
        f"/p/k6pk01 returned {r2.status_code}, expected 200"
    )


def test_public_pedido_tampered_token_returns_404(client, session_factory):
    """K6 #4: Tampered token (same length, different chars) returns 404."""
    from app.rms.models import Pedido
    with session_factory() as s:
        pedido = Pedido(
            customer_name="K6 Tamper Test",
            promised_date=date.today(),
            channel="mostrador",
            public_token="aaaa1111",
        )
        s.add(pedido)
        s.commit()

    # Same length as valid token but different chars
    r = client.get("/p/bbbb2222")
    assert r.status_code == 404, (
        f"/p/bbbb2222 (close-but-wrong token) returned {r.status_code}"
    )


def test_public_pedido_no_auth_required(client, session_factory):
    """K6 #5: /p/{token} must work without any auth or session cookie."""
    from app.rms.models import Pedido
    with session_factory() as s:
        pedido = Pedido(
            customer_name="K6 No Auth",
            promised_date=date.today(),
            channel="whatsapp",
            public_token="k6noauth",
        )
        s.add(pedido)
        s.commit()

    # No auth_client — use the bare client
    r = client.get("/p/k6noauth")
    assert r.status_code == 200, (
        f"/p/k6noauth without auth returned {r.status_code}"
    )
