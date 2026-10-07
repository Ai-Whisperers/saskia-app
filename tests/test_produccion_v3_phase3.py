"""Tests for PRODUCCION-V3 Phase 3 — hero stats (4 cards).

The audit flagged that /produccion had no at-a-glance summary of
today's bake. The cook has to scan the whole table to know "how
much are we making, how much is pedidos, how confident is the plan?"

Phase 3 spec: 4 stat cards (Productos / Lote / Pedidos / Confianza)
above the table, each with a 1-line subtitle. Cards are
read-only — clicking them filters the table (deferred to a later
phase).
"""
from __future__ import annotations

# Spanish copy is part of the contract — typo = useless UI.
EXPECTED_LABELS = ("Productos", "Lote", "Pedidos", "Confianza")


def test_hero_stats_render_in_day_view(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # The 4 stat cards must all be present in the day view.
    for label in EXPECTED_LABELS:
        assert f">{label}</" in body, f"hero stat missing: {label!r}"


def test_hero_stats_have_subtitles(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    # Each card has a 1-line Spanish subtitle below the value.
    assert "productos en el plan" in body or "productos a hornear" in body, (
        "productos subtitle missing"
    )
    assert "unidades a hornear" in body or "lote final" in body, (
        "lote subtitle missing"
    )


def test_hero_stats_dont_render_in_week_view(client, qseed):
    """Hero stats are day-view only — week/month views use a different
    summary block. Rendering in week would mislead the cook."""
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=week")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # None of the 4 hero labels should appear in week view.
    # (We allow "Productos" if it appears elsewhere in nav/etc.,
    # so we just check the hero card wrapper is absent.)
    assert "hero-stats" not in body, (
        "hero stats leaked into week view"
    )
