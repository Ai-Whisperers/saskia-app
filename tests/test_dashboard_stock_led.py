"""tests/test_dashboard_stock_led.py — Stock-confidence LED on /inicio.

Prelaunch roadmap 2026-09-17 item: aggregate ingredient health into a
single green/amber/red signal rendered on the HOY band.

Severity rules:
- danger: any ingredient with negative stock (data integrity issue)
- warn:   1+ ingredients below min_stock_qty (but none negative)
- success: all tracked ingredients at or above min (or none tracked)

The signal appears as a 5th <saskia-kpi-card> in the HOY band with
severity + value + href=/reorder.
"""

# allow-hardcoded-dates: stock math doesn't depend on the calendar.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from app.rms.models import Ingredient


def _make_ing(s, name, stock, min_stock):
    ing = Ingredient(name=name, stock_qty=stock, min_stock_qty=min_stock, unit="g")
    s.add(ing)
    s.flush()
    return ing


def test_led_success_when_all_above_min(client, session_factory):
    """No negative, no below-min → success / 'todo OK'."""
    with session_factory() as s:
        _make_ing(s, "harina-led-ok1", 5000, 1000)
        _make_ing(s, "azúcar-led-ok1", 3000, 500)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert 'severity="success"' in r.text
    assert "todo OK" in r.text


def test_led_warn_when_one_below_min(client, session_factory):
    """1 ingredient below min → warn / '1 bajo mínimo'."""
    with session_factory() as s:
        _make_ing(s, "harina-led-warn1", 500, 1000)  # below
        _make_ing(s, "azúcar-led-warn1", 3000, 500)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert 'severity="warn"' in r.text
    assert "1 bajo mínimo" in r.text


def test_led_danger_when_negative_stock(client, session_factory):
    """Negative stock overrides below-min → danger."""
    with session_factory() as s:
        _make_ing(s, "harina-led-neg1", -100, 1000)
        _make_ing(s, "azúcar-led-neg1", 3000, 500)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "en negativo" in r.text


def test_led_success_when_no_min_tracked(client, session_factory):
    """No ingredients with min_stock_qty set → success."""
    with session_factory() as s:
        _make_ing(s, "harina-led-nomin1", 100, 0)  # min=0 means not tracked
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert 'severity="success"' in r.text


def test_led_card_links_to_reorder(client, session_factory):
    """The LED card must be clickable to /reorder."""
    with session_factory() as s:
        _make_ing(s, "harina-led-link1", -50, 1000)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert 'href="/reorder"' in r.text
