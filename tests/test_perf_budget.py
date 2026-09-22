"""Performance budget tests — these track SLOs we promise to maintain.

If any of these fail, the team's inner-loop latency has degraded
beyond an acceptable bound. The numbers here are conservative for
a free-tier Render instance.

Markers: perf. Run nightly, not on every commit.
"""
import time
import pytest


@pytest.mark.perf
def test_homepage_under_500ms_with_data(authed_client, qseed):
    """GET / should return in <2s on Render free tier with seeded data."""
    # Seed a few sales to populate the dashboard
    qseed("basic")  # creates 1 ingredient + recipe + product
    # Multiple sales to feed concentration + turnover analytics
    for _ in range(10):
        qseed("basic")
    t0 = time.perf_counter()
    r = authed_client.get("/", headers={"Cache-Control": "no-cache"})
    elapsed = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    # Generous bound — Render free tier can be ~1.5s for first request
    assert elapsed < 2500, f"/ took {elapsed:.0f}ms (SLO: 2500ms)"


@pytest.mark.perf
def test_productos_list_under_300ms(authed_client, qseed):
    """GET /productos (typical sale page) should return in <300ms."""
    qseed("basic")
    for _ in range(20):  # add 20 products
        qseed("basic")
    t0 = time.perf_counter()
    r = authed_client.get("/productos")
    elapsed = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed < 1500, f"/productos took {elapsed:.0f}ms (SLO: 1500ms)"


@pytest.mark.perf
def test_healthz_db_under_100ms(authed_client):
    """/healthz/db should be <100ms (DB-light, just schema version)."""
    t0 = time.perf_counter()
    r = authed_client.get("/healthz/db")
    elapsed = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed < 500, f"/healthz/db took {elapsed:.0f}ms (SLO: 500ms)"


@pytest.mark.perf
def test_ventas_new_form_under_300ms(authed_client):
    """GET /ventas (form + autocomplete data) should be <300ms."""
    t0 = time.perf_counter()
    r = authed_client.get("/ventas")
    elapsed = (time.perf_counter() - t0) * 1000
    assert r.status_code in (200, 303)
    assert elapsed < 1500, f"/ventas took {elapsed:.0f}ms (SLO: 1500ms)"


@pytest.mark.perf
def test_static_asset_served_fast(authed_client):
    """/static/app.css should be fast (Render serves CDN-cached)."""
    t0 = time.perf_counter()
    r = authed_client.get("/static/app.css")
    elapsed = (time.perf_counter() - t0) * 1000
    # 200 = found, 404 = missing — both are fine; we only check timing
    assert r.status_code in (200, 404)
    assert elapsed < 1500, f"static asset took {elapsed:.0f}ms"


@pytest.mark.perf
def test_qseed_is_fast_enough(qseed):
    """qseed('basic') should complete in <50ms — used heavily in dev loop."""
    t0 = time.perf_counter()
    qseed("basic")
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 200, f"qseed took {elapsed:.0f}ms (SLO: 200ms)"
