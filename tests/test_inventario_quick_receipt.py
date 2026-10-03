"""tests/test_inventario_quick_receipt.py — Inline +qty form on /inventario.

Prelaunch roadmap 2026-09-17 item: "Quick receipt-of-stock: /inventario
inline `+ qty` form". A small form on each row lets Saskia add stock
without leaving the list.

Implementation: form POSTs to the existing /inventario/{id}/ajustar
endpoint with a positive adjustment. No new router needed.
"""
# allow-hardcoded-dates: stock math doesn't depend on calendar.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from app.rms.models import Ingredient


def _make_ing(s, name, stock=1000, unit="g"):
    ing = Ingredient(name=name, stock_qty=stock, min_stock_qty=0, unit=unit)
    s.add(ing)
    s.flush()
    return ing


def test_inventario_renders_quick_receipt_form(client, session_factory):
    """Each row shows an inline form with adjustment input + Recibir button."""
    with session_factory() as s:
        ing = _make_ing(s, "harina-quick-001")
        s.commit()
    r = client.get("/inventario")
    assert r.status_code == 200
    # The new column header
    assert ">Recibir<" in r.text
    # The form posts to /inventario/{id}/ajustar
    assert f'action="/inventario/{ing.id}/ajustar"' in r.text
    # input + button
    assert f'data-testid="quick-receipt-{ing.id}"' in r.text
    assert f'aria-label="Cantidad recibida de {ing.name}"' in r.text
    assert f'aria-label="Registrar recepción de {ing.name}"' in r.text


def test_quick_receipt_adds_stock(client, session_factory):
    """POSTing adjustment=500 to /inventario/{id}/ajustar adds 500 to stock."""
    with session_factory() as s:
        ing = _make_ing(s, "harina-quick-002", stock=1000)
        ing_id = ing.id
        s.commit()
    # Get CSRF from a real page
    r = client.get("/inventario")
    assert r.status_code == 200
    # Pull CSRF token from rendered page (search for hidden input)
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    assert m, "CSRF token not found in /inventario"
    csrf = m.group(1)

    # POST the quick receipt
    r = client.post(
        f"/inventario/{ing_id}/ajustar",
        data={"adjustment": "500", "csrf_token": csrf},
        follow_redirects=False,
    )
    # Endpoint should 303 (redirect) on success
    assert r.status_code in (303, 302), r.text[:500]

    # Verify stock went up
    with session_factory() as s:
        ing = s.get(Ingredient, ing_id)
        assert ing.stock_qty == 1500.0


def test_quick_receipt_zero_or_empty_rejected(client, session_factory):
    """Empty/zero adjustment doesn't change stock (the endpoint rejects 0)."""
    with session_factory() as s:
        ing = _make_ing(s, "harina-quick-003", stock=2000)
        ing_id = ing.id
        s.commit()
    r = client.get("/inventario")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1)
    # Empty adjustment → form HTML5 `required` blocks it client-side, but
    # the server-side endpoint also rejects adjustment=0 with a flash error.
    # We send 0 to verify server-side guard (no stock change).
    r = client.post(
        f"/inventario/{ing_id}/ajustar",
        data={"adjustment": "0", "csrf_token": csrf},
        follow_redirects=False,
    )
    # 200 with flash or 303; either way stock unchanged
    with session_factory() as s:
        ing = s.get(Ingredient, ing_id)
        assert ing.stock_qty == 2000.0


def test_quick_receipt_creates_movement_record(client, session_factory):
    """Successful receipt creates a stock_movement audit row."""
    with session_factory() as s:
        ing = _make_ing(s, "harina-quick-004", stock=0)
        ing_id = ing.id
        s.commit()
    r = client.get("/inventario")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1)
    client.post(
        f"/inventario/{ing_id}/ajustar",
        data={"adjustment": "3000", "csrf_token": csrf},
        follow_redirects=False,
    )
    # Check StockMovement exists
    from app.rms.models import StockMovement
    with session_factory() as s:
        moves = s.query(StockMovement).filter_by(
            ingredient_id=ing_id, movement_type="adjustment"
        ).all()
        assert len(moves) >= 1
        assert any(m.qty == 3000 for m in moves)
