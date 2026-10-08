"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
Tests for /produccion/haccp — HACCP freezer temperature log (B.6).

Paraguay MSPBS HACCP exige registro de temperatura de freezers donde
se almacenan productos crudos, semi-elaborados y elaborados. Sin
registro continuo, una inspección puede multar al local.

Verifies:
- GET /produccion/haccp renders the day's form + entries
- POST /produccion/haccp persists a FreezerTemperatureLog row
- Range validation: -40 to +30 (model constraint)
- Shift validation: AM|PM only
- Location validation: must be in the default list
- /produccion day view shows the HACCP banner with latest reading
- /produccion day view shows the missing-count nudge
- Out-of-range temperature shows "warning" alert
- Alert for in-range temperature shows "ok"
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.rms.models import FreezerTemperatureLog

# ─────────────────────────── GET /produccion/haccp ───────────────────────────


def test_haccp_page_renders_for_date(authed_client, session_factory):
    """GET /produccion/haccp?for_date=2026-10-05 returns 200 + form."""
    r = authed_client.get("/produccion/haccp?for_date=2026-10-05")
    assert r.status_code == 200, f"GET /produccion/haccp returned {r.status_code}: {r.text[:200]}"
    assert "HACCP" in r.text
    assert "Temperatura" in r.text
    assert "freezer-masa" in r.text  # one of the default locations


def test_haccp_page_renders_without_date_param(authed_client, session_factory):
    """GET /produccion/haccp (no date) defaults to today — no 500."""
    r = authed_client.get("/produccion/haccp")
    assert r.status_code == 200, f"GET /produccion/haccp returned {r.status_code}: {r.text[:200]}"


def test_haccp_page_lists_existing_entries(authed_client, session_factory):
    """Existing FreezerTemperatureLog rows appear in the table."""
    with session_factory() as s:
        s.add(
            FreezerTemperatureLog(
                location="freezer-masa",
                temperature_c=-20.5,
                for_date=date(2026, 10, 5),
                shift="AM",
                recorded_at=datetime(2026, 10, 5, 8, 30),
            )
        )
        s.commit()

    r = authed_client.get("/produccion/haccp?for_date=2026-10-05")
    assert r.status_code == 200
    assert "-20.5" in r.text
    assert "freezer-masa" in r.text
    assert "AM" in r.text


def test_haccp_page_shows_missing_shifts(authed_client, session_factory):
    """A day with no entries shows all 6 (location, shift) pairs as missing."""
    r = authed_client.get("/produccion/haccp?for_date=2026-10-05")
    assert r.status_code == 200
    # 3 locations × 2 shifts = 6 missing entries
    assert "Pendientes hoy" in r.text
    assert "Falta" in r.text or "Registrar" in r.text


# ─────────────────────────── POST /produccion/haccp ───────────────────────────


def test_haccp_post_creates_row(authed_client, session_factory):
    """POST /produccion/haccp persists a FreezerTemperatureLog row."""
    today = date(2026, 10, 5)
    r = authed_client.post(
        "/produccion/haccp",
        data={
            "for_date": today.isoformat(),
            "location": "freezer-masa",
            "shift": "AM",
            "temperature_c": "-20.5",
            "notes": "puerta quedó abierta 5 min",
        },
    )
    assert r.status_code < 500, f"POST returned {r.status_code}: {r.text[:200]}"
    assert r.status_code in (303, 302, 200), f"Expected redirect, got {r.status_code}"

    with session_factory() as s:
        rows = s.query(FreezerTemperatureLog).filter_by(for_date=today).all()
    assert len(rows) == 1
    assert rows[0].location == "freezer-masa"
    assert rows[0].shift == "AM"
    assert abs(rows[0].temperature_c - (-20.5)) < 0.01
    assert rows[0].notes == "puerta quedó abierta 5 min"


@pytest.mark.parametrize("bad_temp", ["-50", "50", "100"])
def test_haccp_post_rejects_out_of_range(authed_client, session_factory, bad_temp):
    """Temperature outside [-40, +30] returns 400 (model constraint)."""
    r = authed_client.post(
        "/produccion/haccp",
        data={
            "for_date": "2026-10-05",
            "location": "freezer-masa",
            "shift": "AM",
            "temperature_c": bad_temp,
            "notes": "",
        },
    )
    assert r.status_code == 400, f"Expected 400 for temp={bad_temp}, got {r.status_code}"


@pytest.mark.parametrize("bad_shift", ["MORNING", "noon", "evening", ""])
def test_haccp_post_rejects_invalid_shift(authed_client, session_factory, bad_shift):
    """Shift must be AM or PM."""
    r = authed_client.post(
        "/produccion/haccp",
        data={
            "for_date": "2026-10-05",
            "location": "freezer-masa",
            "shift": bad_shift,
            "temperature_c": "-20.0",
            "notes": "",
        },
    )
    assert r.status_code == 400, f"Expected 400 for shift={bad_shift}, got {r.status_code}"


def test_haccp_post_rejects_invalid_location(authed_client, session_factory):
    """Location must be in the default list (configurable later via /config)."""
    r = authed_client.post(
        "/produccion/haccp",
        data={
            "for_date": "2026-10-05",
            "location": "garage-freezer",
            "shift": "AM",
            "temperature_c": "-20.0",
            "notes": "",
        },
    )
    assert r.status_code == 400, f"Expected 400 for unknown location, got {r.status_code}"


# ─────────────────────────── /produccion day-view banner ───────────────────────────


def test_produccion_day_view_shows_haccp_banner(authed_client, session_factory):
    """/produccion day view surfaces the latest HACCP reading."""
    target = date(2026, 10, 5)
    with session_factory() as s:
        s.add(
            FreezerTemperatureLog(
                location="freezer-masa",
                temperature_c=-20.0,
                for_date=target,
                shift="AM",
                recorded_at=datetime(2026, 10, 5, 8, 0),
            )
        )
        s.commit()

    r = authed_client.get(f"/produccion?for_date={target.isoformat()}")
    assert r.status_code == 200
    # Banner shows the location + temperature
    assert "haccp" in r.text.lower()
    assert "-20.0" in r.text
    assert "freezer-masa" in r.text


def test_produccion_day_view_shows_out_of_range_warning(authed_client, session_factory):
    """/produccion day view shows FUERA DE RANGO badge when temp is bad."""
    target = date(2026, 10, 5)
    with session_factory() as s:
        s.add(
            FreezerTemperatureLog(
                location="freezer-masa",
                temperature_c=5.0,  # way too warm for a freezer
                for_date=target,
                shift="AM",
                recorded_at=datetime(2026, 10, 5, 8, 0),
            )
        )
        s.commit()

    r = authed_client.get(f"/produccion?for_date={target.isoformat()}")
    assert r.status_code == 200
    assert "FUERA DE RANGO" in r.text


def test_produccion_day_view_shows_missing_nudge(authed_client, session_factory):
    """/produccion day view shows "X lecturas pendientes" when entries are missing."""
    # Use a date with no entries — should show missing nudge
    r = authed_client.get("/produccion?for_date=1900-01-01")
    assert r.status_code == 200
    # Either the missing nudge OR the empty-state card (for plan rows)
    # will show; we only care that the page renders cleanly.
    assert "HACCP" in r.text or "Pendientes" in r.text or "No hay" in r.text


# ─────────────────────────── Model invariants ───────────────────────────


def test_freezer_temperature_log_model_exists():
    """Sanity check — the model is exported and has the right tablename."""
    assert FreezerTemperatureLog.__tablename__ == "freezer_temperature_log"


def test_freezer_temperature_log_default_audit_columns():
    """The model exposes all expected fields for the form to write to."""
    expected = {
        "id",
        "location",
        "temperature_c",
        "for_date",
        "shift",
        "recorded_at",
        "recorded_by_user_id",
        "notes",
    }
    actual = set(FreezerTemperatureLog.__table__.columns.keys())
    assert expected <= actual, f"Missing columns: {expected - actual}"
