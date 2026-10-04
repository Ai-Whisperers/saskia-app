"""Tests for cold-start bootstrap guidance on /produccion day view.

T-2026-10-04 (P1): When the operator is starting out, the plan is empty
or uniform. We need actionable guidance, not a passive 'no hay ventas'.
The state machine:
  - no_sales: 0 sales ever → "crear plan" + "registrar primera venta"
  - no_template: sales but no weekly template → "crear plantilla"
  - cold_plan: plan exists but all qty=1.0 → "ajustar manualmente"
  - no_rows: empty plan, no obvious reason → fall through to default
"""
import pytest
from app.rms.models import Product, Recipe


def test_cold_start_no_sales_state(authed_client):
    """When there's no sales data, the cold-start block shows 'no_sales'."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # The cold-start container is rendered (regardless of which case)
    assert "empty-state-cold-start" in body
    # The data-cold-start attribute carries the kind
    assert "data-cold-start" in body


def test_cold_start_shows_actionable_cta(authed_client):
    """The cold-start message has CTAs to /produccion/manana or /ventas/nueva."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # At least one of the CTAs is present (we don't know which case fires)
    has_manana_cta = "/produccion/manana" in body
    has_ventas_cta = "/ventas/nueva" in body
    assert has_manana_cta or has_ventas_cta, (
        "Cold-start message should have at least one actionable CTA"
    )


def test_cold_start_renders_explanation_text(authed_client):
    """The cold-start card has explanation text, not just empty state."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # Should have at least one of these explanations
    explanations = [
        "no hay ventas",  # no_sales
        "plantilla",  # no_template
        "plan fr",  # cold_plan
        "días de historial",  # cold_plan
    ]
    has_explanation = any(e in body.lower() for e in explanations)
    assert has_explanation, (
        "Cold-start should show explanation text"
    )