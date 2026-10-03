"""tests/test_pedidos_kpi_strip.py — Phase 21 pedidos KPI strip.

Verifies the pedidos list page now leads with a KPI strip showing
status counts, derived from the already-grouped pedidos. The strip
is the at-a-glance summary a cashier wants on entry to /pedidos.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fastapi.testclient import TestClient


TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


def test_pedidos_html_has_kpi_strip():
    """The pedidos template must contain a kpi-strip block."""
    text = (TEMPLATES / "pedidos.html").read_text()
    assert "kpi-strip" in text, "pedidos.html: missing kpi-strip container"
    assert "kpi-strip__value" in text, "pedidos.html: missing KPI value spans"
    assert "kpi-strip__label" in text, "pedidos.html: missing KPI label spans"


def test_pedidos_html_kpi_strip_has_four_kpis():
    """The KPI strip should have 4 cards (pending, confirmed, ready, hoy)."""
    text = (TEMPLATES / "pedidos.html").read_text()
    # Count kpi-strip__item occurrences
    items = re.findall(r'class="kpi-strip__item[^"]*"', text)
    assert len(items) == 4, f"expected 4 KPI items, found {len(items)}"


def test_pedidos_html_kpi_strip_has_status_counts():
    """Each KPI label should match a known status name."""
    text = (TEMPLATES / "pedidos.html").read_text()
    for label in ("Pendientes", "Confirmados", "Listos", "Hoy / Mañana"):
        assert label in text, f"pedidos.html: missing KPI label {label}"


def test_pedidos_html_kpi_derives_from_groups():
    """The KPI strip should compute counts from the groups (no extra round-trip)."""
    text = (TEMPLATES / "pedidos.html").read_text()
    # selectattr("status", "equalto", "...") means derived from groups
    assert 'selectattr("status", "equalto", "pending")' in text
    assert 'selectattr("status", "equalto", "confirmed")' in text
    assert 'selectattr("status", "equalto", "ready")' in text


def test_combobox_css_has_kpi_strip_styles():
    """The CSS must define the kpi-strip rules."""
    css = (TEMPLATES.parent / "static" / "combobox.css").read_text()
    assert ".kpi-strip" in css
    assert ".kpi-strip__item" in css
    assert ".kpi-strip__item--warn" in css
    assert ".kpi-strip__item--info" in css
    assert ".kpi-strip__item--success" in css
    assert ".kpi-strip__item--danger" in css


def test_pedidos_page_renders_kpi_strip_in_browser(client: TestClient):
    """GET /pedidos must return HTML containing the kpi-strip container."""
    resp = client.get("/pedidos")
    assert resp.status_code == 200, f"unexpected status: {resp.status_code}"
    body = resp.text
    assert "kpi-strip" in body
    assert "Pendientes" in body
    assert "Confirmados" in body
    assert "Listos" in body
    assert "Hoy / Mañana" in body
