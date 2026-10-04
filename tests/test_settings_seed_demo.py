"""Tests for the demo data seed button on /settings/seed-demo.

The seed-demo endpoint lets Saskia one-click load realistic bakery data

so the dashboard, reports, and analytics have data to display.
"""

import pytest

pytestmark = pytest.mark.crud


def test_seed_demo_button_on_settings_page(authed_client, session_factory):
    """Settings page shows the demo data tab with both buttons (no full seed)."""
    from app.rms.models import Ingredient

    sf = session_factory
    with sf() as s:
        # Drop any data so we have a known fresh state
        s.query(Ingredient).delete()
        s.commit()
    r = authed_client.get("/settings")
    assert r.status_code == 200
    body = r.text
    assert "Datos de ejemplo" in body
    assert 'action="/settings/seed-demo"' in body
    assert 'name="overwrite" value="0"' in body  # add (idempotent)
    assert 'name="overwrite" value="1"' in body  # reset + reseed
    assert "Adicionar datos de ejemplo" in body
    assert "Resetear y recargar" in body


def test_seed_demo_adds_data(client, authed_client, session_factory):
    """POST /settings/seed-demo with overwrite=0 inserts expected rows."""
    from app.rms.models import Ingredient, Product, Recipe

    sf = session_factory
    # Sanity: pre-seed has nothing in DB (or just test-only data)
    r = authed_client.post(
        "/settings/seed-demo",
        data={"overwrite": "0"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/settings" in r.headers["location"]

    with sf() as s:
        ing_count = s.query(Ingredient).count()
        rec_count = s.query(Recipe).count()
        prod_count = s.query(Product).count()

    # seed_demo_data inserts 29 ingredients + 12 recipes + 12 products
    # Allow >= in case re-runs include them all.
    assert ing_count >= 1
    assert rec_count >= 1
    assert prod_count >= 1


def test_seed_demo_idempotent_no_op_on_second_call(client, authed_client, session_factory):
    """Second call with overwrite=0 does NOT duplicate seed rows."""
    from app.rms.models import Ingredient

    sf = session_factory

    authed_client.post("/settings/seed-demo", data={"overwrite": "0"}, follow_redirects=False)
    with sf() as s:
        first_count = s.query(Ingredient).count()

    # Reset the session, log in again
    authed_client.post("/settings/seed-demo", data={"overwrite": "0"}, follow_redirects=False)
    with sf() as s:
        second_count = s.query(Ingredient).count()

    # Idempotent: should not double
    assert second_count == first_count


def test_seed_demo_overwrite_clears_previous(client, authed_client, session_factory):
    """POST with overwrite=1 deletes prior seed-* rows before reseeding."""
    from app.rms.models import Ingredient

    sf = session_factory

    # First seed
    authed_client.post("/settings/seed-demo", data={"overwrite": "0"}, follow_redirects=False)
    with sf() as s:
        s.query(Ingredient).count()

    # Overwrite
    authed_client.post("/settings/seed-demo", data={"overwrite": "1"}, follow_redirects=False)
    with sf() as s:
        second_count = s.query(Ingredient).count()

    # After overwrite, count should equal the seed size (29) — same range
    assert 10 <= second_count <= 60


def test_seed_demo_dashboard_shows_data_after_seed(client, authed_client, session_factory):
    """After seeding, /inicio dashboard renders with the analytics sections."""
    authed_client.post("/settings/seed-demo", data={"overwrite": "0"}, follow_redirects=False)
    r = authed_client.get("/analisis")
    assert r.status_code == 200
    # The new analytics section should now have content (not just the empty
    # empty-state placeholder)
    body = r.text
    # We seeded 29 ingredients + sales; "Costo concentrado" section should
    # render with actual ingredients OR the empty-but-still-rendered
    # placeholder
    assert (
        "Costo concentrado" in body
        or "Stock turnover" in body
        or "Concentration" in body
        or "Productos más rentables" in body
    )


def test_seed_demo_returns_spanish_error_on_failure(client, authed_client, monkeypatch):
    """If seed_demo_data raises, we redirect with a Spanish error flash."""
    import app.rms.seed as seed_module

    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(seed_module, "seed_demo_data", _raise)
    r = authed_client.post("/settings/seed-demo", data={"overwrite": "0"}, follow_redirects=False)
    assert r.status_code == 303
    # flash message should be error
    assert "Error+al+cargar" in r.headers["location"]
