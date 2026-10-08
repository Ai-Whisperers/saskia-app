"""PROD-MERMA-2 (Batch F): /merma "Hoy" stock-impact summary card.

Adds a 'Hoy' panel that shows what moved TODAY only (event count,
cost, top 3 ingredients). Closes the loop between /merma (where waste
is logged) and /inventario (where stock is verified).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rms.models import Ingredient, WasteLog


def _waste_row(
    session,
    ing_id: int,
    qty: float,
    reason: str = "vencida",
    cost: int = 100,
    when: datetime | None = None,
):
    row = WasteLog(
        ingredient_id=ing_id,
        qty=qty,
        reason=reason,
        cost_gs=cost,
        recorded_at=when or datetime.now(timezone.utc),
        recorded_by="tester",
    )
    session.add(row)
    session.commit()
    return row


def _make_ingredient(session_factory, name: str) -> int:
    """Create a minimal ingredient and return its id. cost_per_unit + price
    are NOT constructor kwargs on the live Ingredient model; the row above
    carries cost_gs explicitly so we don't need them on the ingredient."""
    with session_factory() as s:
        ing = Ingredient(name=name, unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        s.refresh(ing)
        return ing.id


def test_hoy_card_renders_when_today_has_events(authed_client, session_factory):
    """A waste event recorded today → 'Hoy' panel renders with event count + cost."""
    ing_id = _make_ingredient(session_factory, "HoyTest Ing")
    _waste_row(session_factory(), ing_id=ing_id, qty=0.5, cost=200)

    r = authed_client.get("/merma")
    assert r.status_code == 200
    body = r.text
    import re

    # Heading "<h2 ...><svg...><use.../></svg>\n      Hoy\n    </h2>"
    assert re.search(r"<h2[^>]*>\s*<svg[^>]*>.*?</svg>\s*Hoy\s*</h2>", body), (
        "Hoy card heading missing"
    )
    assert "1 evento" in body, "Event count '1 evento' missing from card subtitle"
    assert "Gs. 200" in body, "Today's cost missing from card subtitle"
    # Top ingredient link
    assert "/inventario/" + str(ing_id) in body, "Top ingredient link missing"
    # Pointer to /inventario
    assert "Ver stock actual" in body, "CTA to /inventario missing"


def test_hoy_card_shows_empty_state_when_no_events_today(authed_client, session_factory):
    """No events today → card renders the empty-state copy."""
    r = authed_client.get("/merma")
    assert r.status_code == 200
    body = r.text
    import re

    assert re.search(r"<h2[^>]*>\s*<svg[^>]*>.*?</svg>\s*Hoy\s*</h2>", body), (
        "Hoy card heading missing"
    )
    assert "No registraste merma hoy" in body, "Empty-state copy missing when no events today"


def test_hoy_card_ignores_events_from_yesterday(authed_client, session_factory):
    """Yesterday's events do NOT count toward today's summary."""
    ing_id = _make_ingredient(session_factory, "Yesterday Ing")
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    _waste_row(session_factory(), ing_id=ing_id, qty=0.5, cost=999, when=yesterday)

    r = authed_client.get("/merma")
    body = r.text
    import re

    m = re.search(r'<small class="text-muted">(\d+) evento', body)
    assert m is not None, "Hoy card subtitle missing"
    assert int(m.group(1)) == 0, (
        f"Hoy card should show 0 events when only yesterday had events, got {m.group(1)}"
    )


def test_hoy_card_singular_event_label(authed_client, session_factory):
    """Singular '1 evento' (not '1 eventos') for a single event."""
    ing_id = _make_ingredient(session_factory, "Singular Ing")
    _waste_row(session_factory(), ing_id=ing_id, qty=0.3, cost=50)

    r = authed_client.get("/merma")
    body = r.text
    assert "1 evento ·" in body, "Should use singular 'evento' for count==1"


def test_hoy_card_plural_event_label(authed_client, session_factory):
    """Plural '2 eventos' for two events."""
    ing_id = _make_ingredient(session_factory, "Plural Ing")
    _waste_row(session_factory(), ing_id=ing_id, qty=0.3, cost=50)
    _waste_row(session_factory(), ing_id=ing_id, qty=0.4, cost=80, reason="quemada")

    r = authed_client.get("/merma")
    body = r.text
    assert "2 eventos ·" in body, "Should use plural 'eventos' for count>1"
