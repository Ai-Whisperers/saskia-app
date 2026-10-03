"""Phase 22 — Design system atoms verification.

The design system already has:
- metric_card
- kpi_strip
- status_pill
- empty_state
- loading_state
- skeleton_section
- filter_toolbar
- data_table
- row_actions
- stepper

These tests verify each macro is importable from _components/atoms.html
and renders sensible HTML.
"""
from __future__ import annotations

from app.services.template_render import templates


def test_stepper_renders_3_steps():
    """stepper macro should render ordered list with numbered steps."""
    stepper_macro = templates.env.get_template("_components/atoms.html")
    # Render the macro by including it in a tiny wrapper
    src = (
        '{% import "_components/atoms.html" as ui %}'
        '{{ ui.stepper(["Cliente", "Items", "Confirmar"]) }}'
    )
    out = templates.env.from_string(src).render()
    assert '<ol class="stepper">' in out
    assert "Cliente" in out
    assert "Items" in out
    assert "Confirmar" in out
    # First step should be current (default current=0)
    assert "is-current" in out


def test_stepper_marks_done_steps():
    """Steps before current should be marked is-done."""
    src = (
        '{% import "_components/atoms.html" as ui %}'
        '{{ ui.stepper(["A", "B", "C"], current=1) }}'
    )
    out = templates.env.from_string(src).render()
    assert "is-done" in out
    # Step at index 1 is current
    assert "is-current" in out


def test_metric_card_basic():
    """metric_card macro should render a card with label + value."""
    src = (
        '{% import "_components/atoms.html" as ui %}'
        '{{ ui.metric_card(label="Ventas", value="Gs. 100.000") }}'
    )
    out = templates.env.from_string(src).render()
    assert "metric-card" in out
    assert "Ventas" in out
    assert "Gs. 100.000" in out


def test_kpi_strip_renders_items():
    """kpi_strip macro should render multiple metric cards."""
    src = (
        '{% import "_components/atoms.html" as ui %}'
        '{{ ui.kpi_strip(cards=[{"label": "A", "value": "1"}, {"label": "B", "value": "2"}]) }}'
    )
    out = templates.env.from_string(src).render()
    assert "kpi-strip" in out
    assert "A" in out
    assert "B" in out


def test_status_pill_renders_severity():
    """status_pill macro should render colored pill."""
    src = (
        '{% import "_components/atoms.html" as ui %}'
        '{{ ui.status_pill("Día cerrado", sev="ok") }}'
    )
    out = templates.env.from_string(src).render()
    assert "status-pill" in out
    assert "Día cerrado" in out
    assert "ok" in out


def test_empty_state_renders_cta():
    """empty_state macro should render title + optional CTA."""
    src = (
        '{% import "_components/atoms.html" as ui %}'
        '{{ ui.empty_state(title="Sin datos", hint="No hay items", cta_href="/register", cta_label="Nuevo") }}'
    )
    out = templates.env.from_string(src).render()
    assert "Sin datos" in out
    assert "No hay items" in out
    assert "/register" in out


def test_skeleton_section_renders():
    """skeleton_section macro should render a placeholder."""
    src = (
        '{% import "_components/atoms.html" as ui %}'
        '{{ ui.skeleton_section(id="x", label="Cargando") }}'
    )
    out = templates.env.from_string(src).render()
    assert "skeleton" in out.lower() or "Cargando" in out


def test_filter_toolbar_renders():
    """filter_toolbar macro should render a toolbar structure."""
    src = (
        '{% import "_components/atoms.html" as ui %}'
        '{{ ui.filter_toolbar(items=[{"label": "30d", "href": "/foo?days=30"}]) }}'
    )
    out = templates.env.from_string(src).render()
    assert "filter-toolbar" in out