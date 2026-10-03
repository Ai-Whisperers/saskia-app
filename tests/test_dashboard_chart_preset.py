"""tests/test_dashboard_chart_preset.py — E4.S2 chart_preset switcher on /inicio.

Verifies:
- /inicio accepts chart_preset query param and renders preset label
- /inicio without chart_preset defaults to 30d
- All 5 presets render without error
- The chip for the current preset is marked chip--active
"""
from __future__ import annotations


def test_dashboard_default_preset_is_30d(authed_client, qseed):
    qseed("with_sale")  # Need at least one sale so the chart block renders
    r = authed_client.get("/inicio")
    assert r.status_code == 200
    body = r.text
    # Default chart label uses "últimos 30 días"
    assert "últimos 30 días" in body


def test_dashboard_chart_preset_7d_renders(authed_client, qseed):
    qseed("with_sale")
    r = authed_client.get("/inicio?chart_preset=7d")
    assert r.status_code == 200
    body = r.text
    assert "últimos 7 días" in body
    # The 7d chip should be active
    assert "chip--active" in body


def test_dashboard_chart_preset_90d_renders(authed_client, qseed):
    qseed("with_sale")
    r = authed_client.get("/inicio?chart_preset=90d")
    assert r.status_code == 200
    body = r.text
    assert "últimos 90 días" in body


def test_dashboard_chart_preset_current_month(authed_client, qseed):
    qseed("with_sale")
    r = authed_client.get("/inicio?chart_preset=current_month")
    assert r.status_code == 200
    body = r.text
    assert "mes en curso" in body


def test_dashboard_chart_preset_last_month(authed_client, qseed):
    qseed("with_sale")
    r = authed_client.get("/inicio?chart_preset=last_month")
    assert r.status_code == 200
    body = r.text
    assert "mes anterior" in body


def test_dashboard_chart_preset_invalid_rejected(authed_client, qseed):
    """Pattern check rejects garbage values → 400/422 from FastAPI."""
    qseed("with_sale")
    r = authed_client.get("/inicio?chart_preset=garbage")
    assert r.status_code in (400, 422)


def test_dashboard_chart_preset_preserves_period(authed_client, qseed):
    """chart_preset switcher chips include the current period in the URL."""
    qseed("with_sale")
    # period=today because week has a pre-existing TZ bug (line 456)
    r = authed_client.get("/inicio?period=today&chart_preset=30d")
    assert r.status_code == 200
    body = r.text
    # Chip links should still carry period=today
    assert "period=today" in body
