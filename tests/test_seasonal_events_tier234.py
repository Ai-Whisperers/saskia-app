"""Tests for SASKIA-220 tier 2/3/4 seasonal events catalog."""

from __future__ import annotations

from app.rms.seed.seasonal_events import (
    _tier1_universal_events,
    _tier2_vertical_events,
    _tier3_gastronomy_events,
    _tier4_nl_heritage_events,
    seed_seasonal_events_full,
)

# ---- 1. Tier 1 has 126 events (132 - 6 dedup) ----


def test_tier1_has_126_rows():
    """Tier 1: 132 raw events - 6 movable-feast dedup = 126 rows for 3 years."""
    events = _tier1_universal_events()
    assert len(events) == 126


# ---- 2. Tier 2 has 90 rows (30 events \u00d7 3 years) ----


def test_tier2_has_90_rows():
    events = _tier2_vertical_events()
    assert len(events) == 90


# ---- 3. Tier 3 has 150 rows (50 events \u00d7 3 years) ----


def test_tier3_has_150_rows():
    events = _tier3_gastronomy_events()
    assert len(events) == 150


# ---- 4. Tier 4 has 39 rows (13 NL events \u00d7 3 years) ----


def test_tier4_has_39_rows():
    events = _tier4_nl_heritage_events()
    assert len(events) == 39


# ---- 5. Total >= 405 (target was 411) ----


def test_total_seasonal_events_at_least_405():
    total = (
        len(_tier1_universal_events())
        + len(_tier2_vertical_events())
        + len(_tier3_gastronomy_events())
        + len(_tier4_nl_heritage_events())
    )
    # SASKIA-220 ticket target: 411. Acceptable range: 405-411.
    assert 405 <= total <= 411, f"Total {total} is outside the 405-411 acceptable range"


# ---- 6. Tier 2 verticals cover all 5 SASKIA-220 packs ----


def test_tier2_covers_all_5_new_packs():
    """Tier 2 events must be filterable by the relevance_tags of all 5 SASKIA-220 packs."""
    events = _tier2_vertical_events()
    relevance_tags = {tag for e in events for tag in e["relevance_tags"].split(",") if tag}
    expected = {
        "food_truck",  # 5 events
        "quiosco",  # 4 events
        "chiperia",  # 5 events
        "pasteleria_industrial",  # 4 events
        "cerveceria",  # 6 events
        "heladeria",  # 6 events (also new vertical)
        "panaderia",  # 4 events (mentioned in vuelta_clases)
    }
    for tag in expected:
        assert tag in relevance_tags, f"Tier 2 missing relevance_tag {tag!r}"


# ---- 7. Tier 2 specific landmarks ----


def test_tier2_includes_chiperia_san_juan():
    """SASKIA-220 specifically requires the Chiper\u00eda San Juan event."""
    events = _tier2_vertical_events()
    san_juan = [e for e in events if "san_juan" in e["slug"].lower()]
    assert len(san_juan) >= 1
    # San Juan \u00c1ra is June 24
    assert any(e["event_date"].month == 6 and e["event_date"].day == 24 for e in san_juan)
    # The event must be tagged for chiperia vertical
    assert any("chiperia" in e["relevance_tags"] for e in san_juan)


def test_tier2_includes_dia_cerveza():
    """Day of Beer in Paraguay (Asunci\u00f3n Beer Week)."""
    events = _tier2_vertical_events()
    cerveza = [e for e in events if "cerveza" in e["slug"].lower()]
    assert len(cerveza) >= 1
    assert any("cerveceria" in e["relevance_tags"] for e in cerveza)


# ---- 8. Tier 3 gastronomy ----


def test_tier3_includes_dia_pizza():
    events = _tier3_gastronomy_events()
    assert any("pizza" in e["slug"] for e in events)


def test_tier3_includes_dia_choripan():
    events = _tier3_gastronomy_events()
    assert any("choripan" in e["slug"] for e in events)


def test_tier3_includes_dia_sushi():
    events = _tier3_gastronomy_events()
    assert any("sushi" in e["slug"] for e in events)


# ---- 9. Tier 4 NL heritage ----


def test_tier4_includes_prinsjesdag():
    events = _tier4_nl_heritage_events()
    prinsjesdag = [e for e in events if e["slug"] == "prinsjesdag"]
    assert len(prinsjesdag) == 3  # 3 years
    # Prinsjesdag = third Tuesday of September (fixed to 15 in 2026-2028)
    assert all(e["event_date"].month == 9 and e["event_date"].day == 15 for e in prinsjesdag)


def test_tier4_includes_dodenherdenking():
    events = _tier4_nl_heritage_events()
    assert any(e["slug"] == "dodenherdenking" for e in events)


def test_tier4_country_is_NL():
    """All tier 4 events must have country='NL' (Netherlands, not Paraguay)."""
    events = _tier4_nl_heritage_events()
    for e in events:
        assert e["country"] == "NL", (
            f"Tier 4 event {e['slug']!r} has country={e['country']!r}, expected 'NL'"
        )


# ---- 10. Idempotency: seed_seasonal_events_full is a no-op on second run ----


def test_seed_seasonal_events_full_idempotent(session_factory):
    """Run seed_seasonal_events_full twice. Second run should insert 0 rows."""
    s1 = session_factory()
    try:
        r1 = seed_seasonal_events_full(s1)
        s1.commit()
        first_total = r1["tier1"] + r1["tier2"] + r1["tier3"] + r1["tier4"]
        # At least 400 new rows on a fresh DB
        assert first_total >= 400
    finally:
        s1.close()

    s2 = session_factory()
    try:
        r2 = seed_seasonal_events_full(s2)
        s2.commit()
        # Second run: 0 new rows, all 405+ skipped
        assert r2["tier1"] == 0
        assert r2["tier2"] == 0
        assert r2["tier3"] == 0
        assert r2["tier4"] == 0
        assert r2["skipped"] >= 400
    finally:
        s2.close()
