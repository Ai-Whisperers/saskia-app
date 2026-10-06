"""Tests for PRODUCCION-V3 Phase 2 — source badges & confidence modal.

Audit (H3, M4, M11, M16, M17) findings: source badges were 3 mushy grays
with no legend; confidence was an opaque "72%" number with no context.

Phase 2 spec: 4 distinguishable source badges (receta, historial,
override, horneado-extra) with a legend; confidence is a `?` link
that opens a <dialog> with a 5-band explanation.

Implementation lives in app/routers/produccion.py (FORECAST_SOURCE_LABELS,
bucket helper) and app/templates/produccion.html (legend, badge, modal).
"""
from __future__ import annotations

import re
import pytest
from fastapi.testclient import TestClient  # noqa: F401 (type hint only)


# 4 source buckets per the design spec. `is_ad_hoc` is a row-level
# flag, `forecast_source` is one of 5 strings, so the route groups them.
_FOUR_BUCKETS = {"receta", "historial", "override", "horneado-extra"}


def _login(client) -> None:
    r = client.post(
        "/login",
        data={"username": "demo", "password": "demo"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 302, 200), f"login failed: {r.status_code} {r.text[:200]}"


def test_route_exposes_4_source_buckets():
    """The route must expose a `source_buckets` map (canonical 4 names →
    Spanish labels) for the legend + badges."""
    from app.routers.produccion import SOURCE_BUCKETS
    assert set(SOURCE_BUCKETS) == _FOUR_BUCKETS, (
        f"expected 4 source buckets, got {set(SOURCE_BUCKETS)}"
    )
    # Every value is a non-empty Spanish label
    for k, v in SOURCE_BUCKETS.items():
        assert isinstance(v, str) and v, f"empty label for {k!r}"


def test_route_exposes_5_band_confidence():
    """Confidence has 5 bands: Muy baja / Baja / Media / Alta / Muy alta.
    Each band has a copy string (the modal text) and a CSS modifier."""
    from app.routers.produccion import CONFIDENCE_BANDS
    assert len(CONFIDENCE_BANDS) == 5, f"expected 5 bands, got {len(CONFIDENCE_BANDS)}"
    names = [b[0] for b in CONFIDENCE_BANDS]
    assert names == ["Muy baja", "Baja", "Media", "Alta", "Muy alta"]


def test_forecast_source_to_bucket_mapping():
    """Each granular `forecast_source` value maps to exactly one of the
    4 buckets. `is_ad_hoc=True` is the horneado-extra bucket regardless."""
    from app.routers.produccion import source_to_bucket
    assert source_to_bucket("rolling_14d_avg") == "historial"
    assert source_to_bucket("template") == "receta"
    assert source_to_bucket("manual") == "receta"
    assert source_to_bucket("seasonal_event") == "receta"
    assert source_to_bucket("override") == "override"
    # Ad-hoc always wins over forecast_source
    assert source_to_bucket("anything", is_ad_hoc=True) == "horneado-extra"
    # Unknown source falls back to historial (auto-suggested default)
    assert source_to_bucket("never_seen_value") == "historial"


def test_production_page_renders_source_legend(client, qseed):
    # Seed a product + enough sales to generate a plan row. Without
    # sales, plan_production() returns no rows and the day-view table
    # block (which contains the legend) is gated off.
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200, f"got {r.status_code}: {body[:500]}"
    # The 4 Spanish bucket labels appear in the legend.
    assert "Sugerido por receta" in body or "receta" in body
    assert "historial" in body.lower() or "ventas" in body.lower()
    assert "override" in body.lower() or "Ajuste" in body
    assert "horneado-extra" in body or "Extra" in body or "Horneado" in body


def test_production_page_renders_confidence_help_link(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    assert 'class="confidence-help"' in body or "data-confidence-help" in body, (
        "confidence help link not rendered"
    )


def test_production_page_includes_confidence_modal(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    assert "id=\"confidence-modal\"" in body, "confidence modal not in DOM"
    for band in ("Muy baja", "Baja", "Media", "Alta", "Muy alta"):
        assert band in body, f"confidence band missing: {band}"
