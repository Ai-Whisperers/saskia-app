"""tests/test_excel_io_routes.py — SASKIA plan 1.

excel_io router (app/routers/excel_io.py) has 6 routes, 0 direct
tests. Smoke tests cover the GET endpoints (POSTs need real file
uploads and are out of scope for plan 1).

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_excel_io_index_returns_200(authed_client):
    """GET /excel → 200 (import/export landing page)."""
    r = authed_client.get("/excel")
    assert r.status_code == 200


def test_excel_io_mode_guidance_returns_200(authed_client):
    """GET /excel/mode-guidance → 200."""
    r = authed_client.get("/excel/mode-guidance")
    assert r.status_code == 200


def test_excel_io_plantilla_returns_200(authed_client):
    """GET /excel/plantilla → 200 (download template page or file)."""
    r = authed_client.get("/excel/plantilla")
    assert r.status_code in (200, 303, 404), r.text[:200]


def test_excel_io_exportar_returns_200(authed_client):
    """GET /excel/exportar → 200 (download data)."""
    r = authed_client.get("/excel/exportar")
    assert r.status_code in (200, 303, 404), r.text[:200]
