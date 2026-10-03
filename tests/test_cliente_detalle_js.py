"""Smoke test for the cliente_detalle.js + suggestion-form JS wiring.

T-2026-10-01: cliente_detalle.html gained a new <script> tag and the
'js-suggestion-form' / 'js-subscription-form' hooks. This test pins
the contract so a future refactor doesn't silently strip the JS
handlers (which would cause the suggestion telemetry to lose its
instant-feedback UX).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "app" / "templates" / "cliente_detalle.html"
JS_FILE = REPO_ROOT / "app" / "static" / "js" / "cliente_detalle.js"


def test_template_loads_cliente_detalle_js():
    """The page must include the JS file via defer so the suggestion-
    form handlers attach on DOMContentLoaded."""
    assert TEMPLATE.exists(), f"template missing: {TEMPLATE}"
    body = TEMPLATE.read_text(encoding="utf-8")
    assert '/static/js/cliente_detalle.js' in body, (
        "cliente_detalle.js must be <script>-included from the template; "
        "otherwise the suggestion-CTA button never disables on click."
    )
    assert 'defer' in body, "the cliente_detalle.js tag should use defer"


def test_template_uses_semantic_grid_class():
    """T-2026-10-01: replaced the fragile 'div[style*=grid-template-cols...]'
    media-query selector with a semantic class so the mobile stack
    isn't broken by future whitespace edits."""
    body = TEMPLATE.read_text(encoding="utf-8")
    assert "cliente-detalle-grid" in body, (
        "Expected semantic class 'cliente-detalle-grid' on the dashboard "
        "grid wrapper so the @media (max-width: 900px) override targets it."
    )
    # Confirm the brittle selector is gone
    assert 'div[style*="grid-template-columns:1fr 2fr"]' not in body


def test_cliente_detalle_js_exists_and_exports_no_globals():
    """The file must exist and not pollute window.* with shared state.
    Pure IIFE keeps it self-contained."""
    assert JS_FILE.exists(), f"missing JS file: {JS_FILE}"
    body = JS_FILE.read_text(encoding="utf-8")
    # IIFE wrapper
    assert re.search(r"\(function\s*\(\s*\)\s*\{", body), (
        "expected cliente_detalle.js to wrap its body in an IIFE so it "
        "doesn't pollute window.*"
    )
    # Handlers we promise
    assert "js-suggestion-form" in body
    assert "js-subscription-form" in body


def test_subscription_form_has_js_class():
    """The active-subscription form must carry js-subscription-form so
    cliente_detalle.js can attach the confirm() guard."""
    html = TEMPLATE.read_text(encoding="utf-8")
    # The class is added only inside the for-loop body — verify it's there
    assert "js-subscription-form" in html


@pytest.fixture
def seeded_customer(session_factory):
    """Seed a customer + an active subscription so the form renders."""
    from app.rms.models import Suscripcion
    from tests.factories import make_customer
    with session_factory() as s:
        c = make_customer(s, name="DetailJs UX", phone="0981112222")
        s.flush()
        s.add(Suscripcion(
            customer_id=c.id,
            cadence="semanal",
            status="activa",
            product_summary="2 kg pan + 1 torta",
            price_gs=250000,
            preferred_day_of_week=2,
            preferred_time="08:30",
            notes="Entrega por la mañana",
        ))
        s.commit()
        return c.id


def test_subscription_form_present_when_activa(
    client, seeded_customer
):
    """End-to-end: with one active subscription, the page renders the
    js-subscription-form with the customer_id query string."""
    r = client.get(f"/clientes/{seeded_customer}")
    assert r.status_code == 200
    body = r.text
    # The form must POST to /pedidos/nuevo with customer_id and carry
    # the JS class so the confirm() handler fires.
    assert 'action="/pedidos/nuevo?customer_id=' in body
    assert "js-subscription-form" in body
    # And it must carry the subscription notes payload
    assert "[Suscripción]" in body
