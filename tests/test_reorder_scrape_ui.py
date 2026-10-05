"""tests/test_reorder_scrape_ui.py — Phase 4 UI surface for /reorder scraper.

The /reorder page now includes a "Ver precios" trigger button + a hidden
results panel for each row. This test confirms the markup is wired so the
scraper JS has its DOM hooks.
"""

from __future__ import annotations


def _ensure_seed(authed_client, session_factory, qseed):
    """Make sure /reorder has at least one ingredient row to render.

    The conftest's authed_client is a bare TestClient with no DB seed by
    default, so we use qseed (cheap, ~50ms) when the page is empty.
    """
    r = authed_client.get("/reorder")
    assert r.status_code == 200, r.text
    if "scrape-trigger" in r.text and '<ui-combo id="rsup-' in r.text:
        return r
    qseed("with_low_stock")
    return authed_client.get("/reorder")


def test_reorder_renders_scrape_trigger_per_row(authed_client, session_factory, qseed):
    """Each reorder row must have one scrape-trigger button with the
    ingredient name as data-ingredient-name."""
    r = _ensure_seed(authed_client, session_factory, qseed)
    body = r.text
    triggers = body.count('class="btn btn-sm btn-ghost scrape-trigger"')
    assert triggers >= 1, "expected at least one scrape-trigger button"
    assert "Ver precios" in body
    assert "data-ingredient-name=" in body
    # Panel id matches the ingredient id format used in the template.
    assert 'id="scrape-results-' in body
    # JS bootstrap is present.
    assert "scrape-trigger" in body
    assert "/reorder/scrape" in body


def test_reorder_triggers_count_matches_saskia_combos(authed_client, session_factory, qseed):
    """One trigger per ui-combo supplier picker — that's the row."""
    r = _ensure_seed(authed_client, session_factory, qseed)
    body = r.text
    # Count only the actual button DOM, not JS that references the class.
    n_triggers = body.count('class="btn btn-sm btn-ghost scrape-trigger"')
    n_combos = body.count('<ui-combo id="rsup-')
    assert n_triggers == n_combos, (
        f"trigger count ({n_triggers}) must match combo count ({n_combos})"
    )
