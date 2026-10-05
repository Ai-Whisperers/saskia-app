"""PROD-MERMA-2: Close-the-loop on the modal + /merma source chip + a11y.

Tests:
- /merma eventos table shows the source chip (📍 Producción vs ✍️ Manual)
- audit source='production' renders as the colored chip
- audit source='manual' (or absent) renders as the muted chip
- /produccion modal carries role="dialog" + aria-modal + aria-labelledby
- deficit-prompt JS section + data-shift-saved marker both present
"""
from __future__ import annotations


def test_merma_eventos_table_has_origen_column(authed_client, session_factory):
    """Eventos table now has an 'Origen' column showing the entrypoint."""
    from app.rms.models import Ingredient, WasteLog

    # Need at least one event so the table renders (else empty_state wins)
    with session_factory() as s:
        ing = Ingredient(name="Origen Col Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.flush()
        waste = WasteLog(
            ingredient_id=ing.id,
            qty=0.5,
            reason="vencida",
            cost_gs=1000,
            recorded_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            recorded_by="operator",
        )
        s.add(waste)
        s.commit()

    r = authed_client.get("/merma")
    assert r.status_code == 200
    body = r.text
    # Header cell — Jinja strips inter-tag whitespace, so use a regex-tolerant check
    assert ">Origen<" in body, "Eventos table missing Origen column header"


def test_merma_source_chip_renders_for_known_event(authed_client, session_factory):
    """An event with audit detail {source: 'production'} renders the colored chip.

    Uses the real /merma/registrar endpoint to write the audit (so the
    detail field is the canonical path the route actually uses).
    """
    from app.rms.models import AuditLog, Ingredient

    with session_factory() as s:
        ing = Ingredient(name="Chip Test Ing 2", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    # Real route → real audit detail with source='production'
    r = authed_client.post(
        "/merma/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": "0.5",
            "qty_unit": "kg",
            "reason": "vencida",
            "notes": "smoke test",
            "source": "production",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    r2 = authed_client.get("/merma")
    body = r2.text
    assert "📍 Producción" in body, "📍 Producción chip text missing"
    assert "badge-info" in body, "badge-info not rendered — chip CSS class missing"


def test_merma_source_chip_renders_manual_for_legacy_event(authed_client, session_factory):
    """An event without audit detail.source renders the muted chip."""
    from app.rms.models import Ingredient, WasteLog

    with session_factory() as s:
        ing = Ingredient(name="Manual Test Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.flush()
        ing_id = ing.id
        waste = WasteLog(
            ingredient_id=ing_id,
            qty=0.3,
            reason="quemada",
            cost_gs=500,
            recorded_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            recorded_by="operator",
        )
        s.add(waste)
        s.commit()

    r = authed_client.get("/merma?days=30")
    body = r.text
    # No audit row → source defaults to 'manual' → muted chip
    assert "✍️ Manual" in body, "✍️ Manual chip text missing"


def test_quick_merma_modal_a11y_attributes(authed_client):
    """The modal carries role='dialog' + aria-modal + aria-labelledby for AT."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    assert 'id="quick-merma-modal"' in body
    assert 'role="dialog"' in body
    assert 'aria-modal="true"' in body
    assert 'aria-labelledby="qm-title"' in body
    # Title element exists with the referenced id
    assert 'id="qm-title"' in body


def test_quick_merma_modal_max_width_responsive(authed_client):
    """The modal uses min(540px, 95vw) so it fits small viewports."""
    r = authed_client.get("/produccion?view=day")
    body = r.text
    assert "min(540px, 95vw)" in body, "Modal max-width not responsive"


def test_data_shift_saved_marker_present(authed_client):
    """The shift-saved flash banner carries data-shift-saved=1 so the
    deficit-prompt JS knows when to run."""
    # Render a page where shift_saved context flag would normally be set —
    # in a unit test we can't easily trigger the save flow, but we can confirm
    # the attribute is emitted on the flash banner conditional by reading the
    # template directly.
    import pathlib
    tpl = pathlib.Path("/opt/data/work/saskia-app/app/templates/produccion.html").read_text()
    assert 'data-shift-saved="1"' in tpl, (
        "data-shift-saved marker missing from produccion.html — deficit-prompt JS won't fire"
    )


def test_deficit_prompt_js_present(authed_client):
    """The deficit-prompt JS block is present on /produccion."""
    r = authed_client.get("/produccion?view=day")
    body = r.text
    # The IIFE that scans production-row + checks data-shift-saved + builds the prompt
    assert 'querySelector(\'[data-shift-saved]\')' in body
    assert "shift-deficit-prompt" in body