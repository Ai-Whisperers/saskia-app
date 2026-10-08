"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
tests/test_merma_trend_card.py — BACKLOG #34 template wiring.

Verifies the /merma (merma_list) route:
1. Passes trend_rows + amplified_rows into the template context.
2. Renders the "⚠ Merma amplificada (precio subiendo)" card when
   amplified_rows is non-empty.
3. Hides the card when amplified_rows is empty.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _seed_ingredient_with_history(s, *, name, price_recent, price_prior, days_ago_waste=1):
    """Seed an ingredient with a stable recent price, prior price, and waste."""
    from app.rms.models import Ingredient, IngredientPriceEvent, WasteLog

    ing = Ingredient(
        name=name,
        unit="kg",
        stock_qty=10.0,
        purchase_price_gs=price_recent,
    )
    s.add(ing)
    s.flush()

    # Prior half: at day 40-50 ago
    for d in (50, 45, 40):
        s.add(
            IngredientPriceEvent(
                ingredient_id=ing.id,
                price_gs=price_prior,
                recorded_at=NOW - timedelta(days=d),
                source="manual",
            )
        )
    # Recent half: at day 5-25 ago
    for d in (25, 15, 5):
        s.add(
            IngredientPriceEvent(
                ingredient_id=ing.id,
                price_gs=price_recent,
                recorded_at=NOW - timedelta(days=d),
                source="manual",
            )
        )

    s.add(
        WasteLog(
            ingredient_id=ing.id,
            qty=1.0,
            reason="vencida",
            cost_gs=price_recent,
            recorded_at=NOW - timedelta(days=days_ago_waste),
        )
    )
    s.flush()
    return ing


def test_merma_page_renders_amplified_card_when_present(client, session_factory):
    """When at least one ingredient has rising price + waste, the
    'Merma amplificada' card appears on /merma."""
    s = session_factory()
    try:
        _seed_ingredient_with_history(
            s,
            name="harina",
            price_recent=5000,
            price_prior=4000,  # +25%
        )
        s.commit()
    finally:
        s.close()

    r = client.get("/merma?days=30")
    assert r.status_code == 200
    assert "Merma amplificada" in r.text, (
        "expected the trend card to render when amplified_rows is non-empty"
    )
    # The ingredient name should appear
    assert "harina" in r.text
    # The trend percentage should appear (formatted "+25.0%" or similar)
    assert "+25.0%" in r.text or "25.0%" in r.text


def test_merma_page_omits_amplified_card_when_empty(client, session_factory):
    """When no ingredient has rising price + waste, the card is hidden."""
    s = session_factory()
    try:
        # Stable price (no trend) + waste
        _ing = _seed_ingredient_with_history(
            s,
            name="azúcar",
            price_recent=4000,
            price_prior=4000,
        )
        s.commit()
    finally:
        s.close()

    r = client.get("/merma?days=30")
    assert r.status_code == 200
    # Card text should NOT appear when there are no amplified rows.
    assert "Merma amplificada" not in r.text, "expected the card to be hidden when trend is 0%"
