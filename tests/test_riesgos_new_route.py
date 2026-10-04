"""Tests for the new /riesgos/new POST endpoint.

Closes Phase-14 TODO #nav:11 — previously the "+ Agregar riesgo" button
on /riesgos was disabled because the add-risk endpoint didn't exist.
Operators had to go through Settings to add risks, which was friction.
"""

from __future__ import annotations

import pytest

from app.rms.models_legacy import RiskItem

pytestmark = pytest.mark.crud


def test_riesgos_list_renders_form(authed_client):
    """GET /riesgos must render the form (now wired, not disabled)."""
    r = authed_client.get("/riesgos")
    assert r.status_code == 200
    assert "Agregar riesgo" in r.text
    # The form is hidden by default but its <form id="add-risk-form">
    # element must be present.
    assert 'id="add-risk-form"' in r.text
    # Action target.
    assert 'action="/riesgos/new"' in r.text


def test_riesgos_new_post_creates_risk(authed_client, session_factory):
    """POST /riesgos/new must create a RiskItem row + 303 to /riesgos."""
    payload = {
        "description": "Suba de harina +20% mensual",
        "probability": "4",
        "impact_gs": "1500000",
        "category": "externo",
        "mitigation": "Buscar molino alternativo; contrato a 6 meses",
        "owner": "Iván",
        "notes": "Revisar mensualmente",
    }
    r = authed_client.post("/riesgos/new", data=payload, follow_redirects=False)
    assert r.status_code == 303, r.text[:400]
    assert r.headers.get("location") == "/riesgos"
    # Row exists with expected fields.
    with session_factory() as s:
        items = (
            s.query(RiskItem).filter(RiskItem.description == "Suba de harina +20% mensual").all()
        )
        assert len(items) == 1
        item = items[0]
        assert item.probability == 4
        assert item.impact_gs == 1500000
        assert item.category == "externo"
        assert item.status == "activo"  # default for new risks
        assert item.owner == "Iván"


def test_riesgos_new_rejects_empty_description(authed_client, session_factory):
    """POST with empty description must NOT create a row (and stays on /riesgos)."""
    n_before = session_factory().__enter__().query(RiskItem).count()
    r = authed_client.post(
        "/riesgos/new",
        data={"description": "", "probability": "3", "impact_gs": "1000"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers.get("location") == "/riesgos"
    n_after = session_factory().__enter__().query(RiskItem).count()
    assert n_after == n_before, "no row should be created on validation failure"


def test_riesgos_new_rejects_invalid_probability(authed_client, session_factory):
    """POST with probability out of 1..5 range must not create."""
    for bad_prob in ("0", "6", "-1", "100"):
        r = authed_client.post(
            "/riesgos/new",
            data={
                "description": f"Bad prob {bad_prob}",
                "probability": bad_prob,
                "impact_gs": "1000",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
    # No "Bad prob" rows in DB.
    with session_factory() as s:
        n = s.query(RiskItem).filter(RiskItem.description.like("Bad prob%")).count()
        assert n == 0


def test_riesgos_new_rejects_negative_impact(authed_client, session_factory):
    """POST with negative impact_gs must not create (CHECK ck_risk_impact_nonneg)."""
    r = authed_client.post(
        "/riesgos/new",
        data={"description": "Negative impact risk", "probability": "2", "impact_gs": "-100"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    with session_factory() as s:
        n = s.query(RiskItem).filter(RiskItem.description == "Negative impact risk").count()
        assert n == 0


def test_riesgos_new_accepts_minimal_payload(authed_client, session_factory):
    """Only description is required; everything else has defaults."""
    r = authed_client.post(
        "/riesgos/new",
        data={"description": "Riesgo mínimo"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    with session_factory() as s:
        item = s.query(RiskItem).filter(RiskItem.description == "Riesgo mínimo").one()
        assert item.probability == 2  # default
        assert item.impact_gs == 0  # default
        assert item.status == "activo"  # default


def test_riesgos_new_redirected_to_list(authed_client):
    """Successful POST must always 303 to /riesgos (PRG pattern)."""
    r = authed_client.post(
        "/riesgos/new",
        data={"description": "X", "probability": "1", "impact_gs": "0"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers.get("location") == "/riesgos"


def test_riesgos_list_shows_new_risk_after_submit(authed_client, session_factory):
    """After POST → GET /riesgos, the new risk must appear in the rendered list."""
    payload = {
        "description": "Riesgo visible",
        "probability": "3",
        "impact_gs": "500000",
        "category": "operacional",
        "owner": "Gaby",
    }
    authed_client.post("/riesgos/new", data=payload, follow_redirects=False)
    r = authed_client.get("/riesgos")
    assert r.status_code == 200
    assert "Riesgo visible" in r.text
