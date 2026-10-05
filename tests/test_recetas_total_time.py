"""Tests for T-9: recetas list total time column (prep_minutes + cook_minutes)."""
from app.routers.recipes import _format_total_minutes
from app.rms.models import Recipe


def test_recetas_list_shows_total_time_column(authed_client, session_factory):
    """T-9 — /recetas with at least 1 recipe must show 'Tiempo total' column."""
    with session_factory() as s:
        s.add(Recipe(name="T9-Test", yield_qty=10, yield_unit="und",
                     prep_minutes=15, cook_minutes=20))
        s.commit()

    r = authed_client.get("/recetas")
    assert r.status_code == 200
    assert "Tiempo total" in r.text, (
        "T-9 missing: 'Tiempo total' column header not in /recetas"
    )
    # The formatted value '35m' confirms total_minutes_fmt is wired
    assert "35m" in r.text, (
        "T-9 missing: formatted total_minutes value not rendered"
    )


def test_recetas_total_time_formatting(authed_client, session_factory):
    """T-9 — prep+cook sums to '1h 35m' when 60+35 min."""
    with session_factory() as s:
        s.add(Recipe(name="T9-Tortuga", yield_qty=8, yield_unit="und",
                     prep_minutes=60, cook_minutes=35))
        s.commit()

    r = authed_client.get("/recetas")
    assert r.status_code == 200
    assert "1h 35m" in r.text


def test_format_total_minutes_helper():
    """T-9 — _format_total_minutes formatting function unit tests."""
    assert _format_total_minutes(None) == "Sin definir"
    assert _format_total_minutes(0) == "0m"
    assert _format_total_minutes(45) == "45m"
    assert _format_total_minutes(60) == "1h 0m"
    assert _format_total_minutes(90) == "1h 30m"
    assert _format_total_minutes(125) == "2h 5m"