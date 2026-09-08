"""tests/test_phase4_routes.py — smoke tests for the 6 Phase-4 routes."""
from __future__ import annotations


def test_eod_renders(client):
    resp = client.get("/eod")
    assert resp.status_code == 200
    assert "Cierre" in resp.text or "checklist" in resp.text.lower()


def test_merma_renders(client):
    resp = client.get("/merma")
    assert resp.status_code == 200
    assert "Merma" in resp.text or "desperdicio" in resp.text


def test_reportes_index_renders(client):
    resp = client.get("/reportes")
    assert resp.status_code == 200
    assert "Reportes" in resp.text


def test_reportes_iva_renders(client):
    resp = client.get("/reportes/iva")
    assert resp.status_code == 200
    assert "IVA" in resp.text


def test_reportes_libro_ventas_renders(client):
    resp = client.get("/reportes/libro-ventas")
    assert resp.status_code == 200
    assert "Libro de Ventas" in resp.text


def test_reportes_diario_renders(client):
    resp = client.get("/reportes/diario")
    assert resp.status_code == 200
    assert "Resumen diario" in resp.text


def test_auditoria_renders(client):
    resp = client.get("/auditoria")
    assert resp.status_code == 200
    assert "Auditor" in resp.text
