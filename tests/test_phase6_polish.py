"""tests/test_phase6_polish.py — Phase 6 nav/logout/responsive tests."""
from __future__ import annotations


def test_nav_has_logout_link(client):
    """Top nav must include a logout link."""
    resp = client.get("/ventas")
    assert resp.status_code == 200
    assert 'href="/logout"' in resp.text


def test_css_has_mobile_media_query(client):
    """/static/app.css must include @media (max-width: 768px) for mobile."""
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    body = resp.text
    assert "@media" in body
    assert "max-width: 768px" in body


def test_css_has_print_styles(client):
    """@media print rules must be present for paper-friendly reports."""
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert "@media print" in resp.text


def test_css_has_quick_sell_grid(client):
    """Sales page CSS must include .quick-sell-grid for one-tap buttons."""
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert ".quick-sell-grid" in resp.text
