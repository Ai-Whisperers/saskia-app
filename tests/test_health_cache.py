"""tests/test_health_cache.py — /healthz* responses are edge-cacheable."""

from __future__ import annotations


def test_healthz_response_has_cache_control_header(client):
    """/healthz must include Cache-Control: public, max-age=10, s-maxage=10.

    Per docs/operations/2026-09-09-performance-analysis.md improvement #5.
    """
    resp = client.get("/healthz")
    assert resp.status_code in (200, 503)
    cc = resp.headers.get("cache-control", "")
    assert "public" in cc, f"Cache-Control missing 'public': {cc!r}"
    assert "max-age=" in cc, f"Cache-Control missing max-age: {cc!r}"


def test_healthz_db_response_has_cache_control_header(client):
    """/healthz/db must also include Cache-Control headers."""
    resp = client.get("/healthz/db")
    assert resp.status_code in (200, 503)
    cc = resp.headers.get("cache-control", "")
    assert "public" in cc
    assert "max-age=" in cc


def test_healthz_schema_response_has_cache_control_header(client):
    """/healthz/schema must also include Cache-Control headers."""
    resp = client.get("/healthz/schema")
    assert resp.status_code in (200, 503)
    cc = resp.headers.get("cache-control", "")
    assert "public" in cc


def test_healthz_errors_response_has_cache_control_header(client):
    """/healthz/errors must also include Cache-Control headers."""
    resp = client.get("/healthz/errors")
    assert resp.status_code in (200, 503)
    cc = resp.headers.get("cache-control", "")
    assert "public" in cc


def test_non_healthz_response_has_no_cache_control_from_middleware(client):
    """/login should NOT have the /healthz cache header."""
    resp = client.get("/login")
    cc = resp.headers.get("cache-control", "")
    # /login has no cache header by default.
    assert "s-maxage=10" not in cc, f"/login incorrectly got the /healthz cache header: {cc!r}"


def test_healthz_cache_middleware_registered():
    """The middleware must be registered in main.py."""
    from app.rms.main import app

    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert any("HealthCache" in c for c in middleware_classes), (
        f"HealthCacheMiddleware not registered. Found: {middleware_classes}"
    )
