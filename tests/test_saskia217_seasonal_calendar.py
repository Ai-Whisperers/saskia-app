"""Tests for SASKIA-217: /admin/seasonal-calendar UI page (read-only).

Covers:
- Page renders (200) with the seeded catalog
- Events inside the lead window get the "inside" status
- relevance_tags filter: pack-tagged events hidden when filter set
- notif_lead_days setting is respected
- Empty DB shows the empty state, not a 500
"""

# allow-hardcoded-dates: fixture: seasonal_event catalog uses fixed calendar dates; today=date(2026, 10, 12) is the test reference

from __future__ import annotations

from datetime import date, timedelta

from app.rms.seed.seasonal_events import seed_seasonal_events_full


def _seed_catalog(session_factory) -> None:
    with session_factory() as s:
        seed_seasonal_events_full(s)
        s.commit()


def test_calendar_page_renders(client, session_factory):
    """GET /api/admin/seasonal-calendar returns 200 with the catalog table."""
    _seed_catalog(session_factory)
    resp = client.get("/api/admin/seasonal-calendar")
    assert resp.status_code == 200, resp.text[:500]
    body = resp.text
    assert "Calendario estacional" in body
    assert "data-table" in body
    # Some seeded event name must appear (tier 1 has Navidad/Año Nuevo)
    assert "Navidad" in body or "Año Nuevo" in body


def test_calendar_page_empty_db_empty_state(client):
    """No seeded events -> empty state callout, not a crash."""
    resp = client.get("/api/admin/seasonal-calendar")
    assert resp.status_code == 200
    assert "No hay eventos cargados" in resp.text


def test_calendar_page_respects_relevance_filter(client, session_factory):
    """With seasonal.relevance_tags=heladeria, pack-tagged events for other
    verticals are filtered out; universal events stay."""
    from app.rms.settings_registry import settings_set

    _seed_catalog(session_factory)
    with session_factory() as s:
        settings_set(s, "seasonal.relevance_tags", "heladeria")
        s.commit()
    resp = client.get("/api/admin/seasonal-calendar")
    assert resp.status_code == 200
    body = resp.text
    # heladeria-tagged tier 2 events must be visible
    assert "helado" in body.lower()
    # cerveceria-only event must NOT be visible
    assert "Oktoberfest" not in body


def test_calendar_page_lead_window_badging(client, session_factory):
    """Events within notif_lead_days show the 'en N d' pill."""
    from app.rms.models import SeasonalEvent

    _seed_catalog(session_factory)
    # Insert a synthetic event 5 days out with a 30-day lead window
    with session_factory() as s:
        s.add(
            SeasonalEvent(
                slug="test_s217_near",
                name_es="Evento de prueba S217",
                event_date=date.today() + timedelta(days=5),
                country="PY",
                category="commercial",
                impact_score=0.9,
                impact_tag="high",
                relevance_tags="",
                is_annual=False,
            )
        )
        s.commit()
    resp = client.get("/api/admin/seasonal-calendar")
    assert resp.status_code == 200
    body = resp.text
    assert "Evento de prueba S217" in body
    assert "en 5 d" in body


def test_calendar_helpers_lead_status():
    """Unit: lead_status classification."""
    from app.rms.seasonal import lead_status

    today = date(2026, 10, 12)
    assert lead_status(today + timedelta(days=5), 30, today) == "inside"
    assert lead_status(today + timedelta(days=45), 30, today) == "upcoming"
    assert lead_status(today - timedelta(days=1), 30, today) == "past"


def test_calendar_helpers_filter(session_factory):
    """Unit: get_calendar_events relevance filter matches tag substrings."""
    from app.rms.seasonal import get_calendar_events

    _seed_catalog(session_factory)
    with session_factory() as s:
        universal = get_calendar_events(s, relevance_tags=None, today=date(2026, 10, 12))
        heladeria = get_calendar_events(s, relevance_tags="heladeria", today=date(2026, 10, 12))
        cerveceria = get_calendar_events(s, relevance_tags="cerveceria", today=date(2026, 10, 12))
    assert len(universal) > len(heladeria) >= 1
    assert len(universal) > len(cerveceria) >= 1
    # heladeria view must not contain cerveceria-only events
    cerveceria_names = {e.slug for e in cerveceria}
    heladeria_names = {e.slug for e in heladeria}
    oktober = {"oktoberfest_py"}
    assert oktober - heladeria_names != set() or not (oktober & cerveceria_names)


def test_calendar_page_no_500_with_settings_missing(client, session_factory):
    """A DB where seasonal.notif_lead_days was never set still renders (default 30)."""
    _seed_catalog(session_factory)
    resp = client.get("/api/admin/seasonal-calendar")
    assert resp.status_code == 200
    assert "30 días" in resp.text
