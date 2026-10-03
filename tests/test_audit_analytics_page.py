"""tests/test_audit_analytics_page.py — BACKLOG #30 page-wire tests."""
from __future__ import annotations


def test_analytics_renders_200(client):
    r = client.get("/auditoria/analytics")
    assert r.status_code == 200
    body = r.text
    assert "Analítica de auditoría" in body


def test_analytics_days_param_works(client):
    r = client.get("/auditoria/analytics?days=7")
    assert r.status_code == 200
    r = client.get("/auditoria/analytics?days=90")
    assert r.status_code == 200


def test_analytics_invalid_days_4xx(client):
    r = client.get("/auditoria/analytics?days=0")
    assert r.status_code in (400, 422)
    r = client.get("/auditoria/analytics?days=10000")
    assert r.status_code in (400, 422)


def test_analytics_empty_db_no_crash(client):
    """Empty DB → page renders without 500."""
    r = client.get("/auditoria/analytics")
    assert r.status_code == 200
    body = r.text
    assert "Algo salió mal" not in body
    # Either shows KPIs at zero, or the empty-state copy — never a 500.
    assert ("Eventos totales" in body
            or "No hay eventos" in body)
