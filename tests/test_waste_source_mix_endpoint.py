"""PROD-MERMA-2 (Batch I follow-up): /api/smoke/waste-source-mix endpoint.

Powers the operator-facing source-mix dashboard and the upcoming
watchbrief cron that tracks /produccion quick-merma modal adoption.
"""
from datetime import datetime, timezone

from app.rms.waste import record_waste
from app.rms.waste import WasteReason
from app.rms.models import Ingredient


def _make_ingredient(session_factory, name):
    with session_factory() as s:
        ing = Ingredient(
            name=name,
            unit="kg",
            stock_qty=10.0,
            purchase_price_gs=1000,
        )
        s.add(ing)
        s.commit()
        return ing.id


def test_endpoint_returns_empty_mix_when_no_waste(authed_client, session_factory):
    """No waste in DB → n_total=0, share=0, empty mix dict."""
    r = authed_client.get("/api/smoke/waste-source-mix")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["window_days"] == 14
    assert data["n_total"] == 0
    assert data["production_share_pct"] == 0.0
    assert data["mix"] == {}


def test_endpoint_groups_by_source(authed_client, session_factory):
    """2 manual + 3 production events → mix dict splits correctly."""
    ing = _make_ingredient(session_factory, "WSMIX Ing")
    with session_factory() as s:
        for _ in range(2):
            record_waste(
                s,
                ingredient_id=ing,
                qty=0.1,
                reason=WasteReason.OTRA,
                source="manual",
            )
        for _ in range(3):
            record_waste(
                s,
                ingredient_id=ing,
                qty=0.1,
                reason=WasteReason.OTRA,
                source="production",
            )
        s.commit()

    r = authed_client.get("/api/smoke/waste-source-mix")
    assert r.status_code == 200
    data = r.json()
    assert data["n_total"] == 5
    assert data["mix"]["manual"]["n_events"] == 2
    assert data["mix"]["production"]["n_events"] == 3
    # 3/5 = 60.0%
    assert data["production_share_pct"] == 60.0
    # Cost: 5 × (0.1 kg × 1000 Gs/kg) = 500 Gs total, 200 manual, 300 production.
    assert data["mix"]["manual"]["cost_gs"] == 200
    assert data["mix"]["production"]["cost_gs"] == 300


def test_endpoint_excludes_waste_older_than_14_days(authed_client, session_factory):
    """Old waste should NOT count toward the 14-day window."""
    ing = _make_ingredient(session_factory, "WSMIX Old Ing")
    with session_factory() as s:
        log = record_waste(
            s,
            ingredient_id=ing,
            qty=0.5,
            reason=WasteReason.OTRA,
            source="manual",
        )
        # Backdate recorded_at to 30 days ago — outside the window.
        from datetime import timedelta
        log.recorded_at = datetime.now(timezone.utc) - timedelta(days=30)
        s.commit()

    r = authed_client.get("/api/smoke/waste-source-mix")
    data = r.json()
    assert data["n_total"] == 0, "old waste should be excluded from 14d window"


def test_endpoint_handles_legacy_rows_backfilled_to_manual(authed_client, session_factory):
    """Legacy rows inserted before migration 072 had no `source` and got
    backfilled to 'manual'. Verify the endpoint counts them as manual —
    we simulate this by inserting a row directly with source='manual'
    (which is what the migration backfill writes) and confirming it
    groups correctly.
    """
    ing = _make_ingredient(session_factory, "WSMIX Legacy Ing")
    with session_factory() as s:
        record_waste(
            s,
            ingredient_id=ing,
            qty=0.1,
            reason=WasteReason.OTRA,
            source="manual",  # what the backfill writes
        )
        s.commit()

    r = authed_client.get("/api/smoke/waste-source-mix")
    data = r.json()
    assert data["mix"].get("manual", {}).get("n_events") == 1, (
        f"manual row missing; got {data['mix']}"
    )
    # Endpoint should never produce a NULL-source bucket thanks to the
    # COALESCE in the SQL.
    assert None not in data["mix"], (
        f"endpoint should COALESCE NULL to 'manual'; got {data['mix']}"
    )


def test_merma_page_renders_source_mix_dashboard(authed_client, session_factory):
    """The /merma 'Hoy' card should surface 14-day source counts inline.

    Operators need to see at-a-glance whether the /produccion quick-merma
    modal is being used. The chips render even when there's no waste in
    the window (showing zeros) so operators know the dashboard is alive.
    """
    ing = _make_ingredient(session_factory, "WSMIX Dashboard Ing")
    with session_factory() as s:
        record_waste(
            s,
            ingredient_id=ing,
            qty=0.1,
            reason=WasteReason.OTRA,
            source="production",
        )
        s.commit()

    r = authed_client.get("/merma")
    assert r.status_code == 200
    body = r.text
    # Both source chips must appear in the "Hoy" card footer.
    assert "Manual:" in body, "Manual source chip missing from /merma dashboard"
    assert "Producción:" in body, "Producción source chip missing from /merma dashboard"
    assert "Últimos 14 días" in body, "14-day window label missing"
