"""Static asset versioned query tests."""
from __future__ import annotations

import pytest


def test_app_css_has_version_query_string(client):
    """app.css must be referenced with ?v= cache-busting query."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert 'app.css?v=' in body, (
        f"app.css missing cache-busting version. Body: {body[:500]}"
    )


def test_app_js_has_version_query_string(client):
    """app.js must be referenced with ?v= cache-busting query."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert 'app.js?v=' in body, (
        f"app.js missing cache-busting version. Body: {body[:500]}"
    )


def test_static_asset_cache_control_header(client):
    """/static/app.css must have Cache-Control header."""
    r = client.get("/static/app.css")
    if r.status_code == 200:
        cc = r.headers.get("cache-control", "")
        # Either max-age or no-cache directive
        assert "max-age" in cc.lower() or "no-cache" in cc.lower() or "public" in cc.lower(), (
            f"Static asset missing Cache-Control: '{cc}'"
        )


def test_static_asset_accessible(client):
    """/static/app.css must be accessible without auth."""
    r = client.get("/static/app.css")
    assert r.status_code == 200, (
        f"/static/app.css returned {r.status_code}"
    )


def test_favicon_served(client):
    """/favicon.ico or /static/favicon.ico must be served."""
    for path in ("/favicon.ico", "/static/favicon.ico"):
        r = client.get(path)
        if r.status_code == 200:
            return
    # Either path must work
    pytest.fail("No favicon endpoint served (200)")
