"""PROD-MERMA-2 (Batch H): collapse duplicate panels on /merma.

Removes the 'Por ingrediente (top 10)' table from the Resumen panel
because it duplicates the shape of the 'Hoy' card. Adds a CTA to
/auditoria?source=merma so operators can drill into per-ingredient
detail without re-rendering the same table on the same page.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.rms.models import Ingredient, WasteLog


def _make_ingredient(session_factory, name: str) -> int:
    with session_factory() as s:
        ing = Ingredient(name=name, unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        s.refresh(ing)
        return ing.id


def _waste_row(session_factory, ing_id: int, qty: float, cost: int = 100, when: datetime | None = None):
    with session_factory() as s:
        s.add(
            WasteLog(
                ingredient_id=ing_id,
                qty=qty,
                reason="vencida",
                cost_gs=cost,
                recorded_at=when or datetime.now(timezone.utc),
                recorded_by="tester",
            )
        )
        s.commit()


def test_top_ingredients_table_removed_from_resumen(authed_client, session_factory):
    """The /merma Resumen panel no longer renders a 'Por ingrediente' table
    (replaced by the 'Hoy' card and a CTA to /auditoria?source=merma)."""
    ing_id = _make_ingredient(session_factory, "H Test Ing")
    _waste_row(session_factory, ing_id=ing_id, qty=0.5, cost=300)

    r = authed_client.get("/merma")
    body = r.text
    # The old heading 'Por ingrediente (top 10)' must be gone.
    assert ">Por ingrediente (top 10)<" not in body, (
        "Old 'Por ingrediente (top 10)' table heading still in /merma"
    )


def test_resumen_includes_auditoria_cta_when_ingredients_present(authed_client, session_factory):
    """When at least one ingredient has waste in the window, the Resumen
    panel shows a CTA pointing to /auditoria?source=merma."""
    ing_id = _make_ingredient(session_factory, "H CTA Ing")
    _waste_row(session_factory, ing_id=ing_id, qty=0.4, cost=250)

    r = authed_client.get("/merma")
    body = r.text
    assert 'href="/auditoria?source=merma"' in body, (
        "Expected CTA to /auditoria?source=merma in Resumen panel"
    )
    assert "Ver detalle por ingrediente en /auditoria" in body, (
        "Expected CTA copy 'Ver detalle por ingrediente en /auditoria'"
    )


def test_no_cta_when_no_ingredients_in_window(authed_client):
    """Empty window: no ingredients with waste → no CTA."""
    r = authed_client.get("/merma")
    body = r.text
    # No waste was recorded, so the top_ingredients list is empty and
    # the CTA should not render.
    assert "/auditoria?source=merma" not in body, (
        "CTA should NOT render when no ingredients have waste in window"
    )


def test_resumen_card_still_renders(authed_client, session_factory):
    """The Resumen headline (cost + events) is preserved."""
    r = authed_client.get("/merma")
    body = r.text
    import re
    # Resumen heading doesn't include an svg icon; match `<h2>...Resumen...`
    assert re.search(r'<h2[^>]*>.*?Resumen', body), (
        "Resumen card heading missing"
    )
    assert "Costo total" in body, "Costo total metric label missing"
    assert "Eventos" in body, "Eventos metric label missing"


def test_hoy_card_still_present_with_resumen(authed_client, session_factory):
    """Both Hoy (today) and Resumen (N-day) cards render — different scopes."""
    ing_id = _make_ingredient(session_factory, "H Both Ing")
    _waste_row(session_factory, ing_id=ing_id, qty=0.2, cost=120)

    r = authed_client.get("/merma")
    body = r.text
    import re
    assert re.search(r'<h2[^>]*>\s*<svg[^>]*>.*?</svg>\s*Hoy\s*</h2>', body), "Hoy card missing"
    assert re.search(r'<h2[^>]*>.*?Resumen', body), "Resumen card missing"
