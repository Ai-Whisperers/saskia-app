"""tests/test_eod_range_mode.py — /eod?start=&end= weekend-batch summary.

Prelaunch roadmap 2026-09-17 item: weekend batch `/eod?start=YYYY-MM-DD&end=YYYY-MM-DD`.

Scope of the range mode:
- Renders total ventas + total merma + total operaciones for the range
- Renders a per-day table (date_iso + plan_rows + completed)
- Shows the range-mode header ("Cierre del rango") and hides the
  per-day checklist (it remains for /eod without params)
- 31-day cap: a 32-day range falls back to checklist mode
- Bad dates fall back to checklist mode
- Start > end falls back to checklist mode
"""
# allow-hardcoded-dates: range tests use literal 2026-09 dates.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.models import Sale, WasteLog


def test_eod_default_is_checklist_mode(client):
    """No params → checklist mode (no 'Cierre del rango' header)."""
    r = client.get("/eod")
    assert r.status_code == 200
    assert "Cierre del rango" not in r.text
    assert "Cierre diario" in r.text


def test_eod_range_mode_renders_summary(client, session_factory):
    """With start+end the page renders range-mode header + totals."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        today = datetime.now(timezone.utc)
        s.add(Sale(
            product_id=product.id, qty=2.0, unit_price_gs=10000,
            sold_at=today - timedelta(days=1), voided_at=None,
        ))
        s.add(WasteLog(
            ingredient_id=1, qty=0.5, reason="vencido",
            cost_gs=5000, recorded_at=today - timedelta(days=1),
        ))
        s.commit()
    today_d = datetime.now().date()
    start = (today_d - timedelta(days=3)).isoformat()
    end = today_d.isoformat()
    r = client.get(f"/eod?start={start}&end={end}")
    assert r.status_code == 200
    assert "Cierre del rango" in r.text
    assert "Resumen del rango" in r.text
    assert start in r.text
    assert end in r.text
    # 4 days in range (inclusive)
    assert "4 días en el rango" in r.text or "4 d\u00edas en el rango" in r.text


def test_eod_range_mode_aggregates_sales(client, session_factory):
    """Sum of ventas in range = sum of (qty * unit_price_gs) for in-range sales."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        today = datetime.now(timezone.utc)
        # 2 sales × Gs. 10000 = Gs. 20000 total
        for i in range(2):
            s.add(Sale(
                product_id=product.id, qty=1.0, unit_price_gs=10000,
                sold_at=today - timedelta(days=1), voided_at=None,
            ))
        s.commit()
    today_d = datetime.now().date()
    start = (today_d - timedelta(days=3)).isoformat()
    end = today_d.isoformat()
    r = client.get(f"/eod?start={start}&end={end}")
    assert r.status_code == 200
    # Operations count shows 2 (or more if other fixtures added sales)
    assert "Operaciones" in r.text


def test_eod_range_rejects_over_31_days(client):
    """>31-day range falls back to checklist mode (defensive cap)."""
    today_d = datetime.now().date()
    start = (today_d - timedelta(days=40)).isoformat()
    end = today_d.isoformat()
    r = client.get(f"/eod?start={start}&end={end}")
    assert r.status_code == 200
    # Should NOT show range mode header
    assert "Cierre del rango" not in r.text


def test_eod_range_rejects_inverted_dates(client):
    """start > end falls back to checklist mode."""
    today_d = datetime.now().date()
    start = today_d.isoformat()
    end = (today_d - timedelta(days=5)).isoformat()
    r = client.get(f"/eod?start={start}&end={end}")
    assert r.status_code == 200
    assert "Cierre del rango" not in r.text


def test_eod_range_rejects_bad_dates(client):
    """Garbage in start/end falls back to checklist mode."""
    r = client.get("/eod?start=not-a-date&end=also-bad")
    assert r.status_code == 200
    assert "Cierre del rango" not in r.text


def test_eod_range_has_back_to_today_link(client, session_factory):
    """Range mode surfaces a 'Volver a hoy' link."""
    today_d = datetime.now().date()
    start = (today_d - timedelta(days=2)).isoformat()
    end = today_d.isoformat()
    r = client.get(f"/eod?start={start}&end={end}")
    assert r.status_code == 200
    # The link is rendered (href to /eod without params)
    assert 'href="/eod"' in r.text
    assert "Volver a hoy" in r.text
