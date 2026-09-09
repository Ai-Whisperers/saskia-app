"""app/routers/ops.py — operator-side routes for diagnosis.

These are intentionally NOT user-facing for the bakery operator —
they're for the system operator (Iván) and Kiki (developer). They
give one-page views of system health and quick links to investigate.

Mounted at /ops/* with the standard require_login dependency.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.auth import require_login_or_disabled as require_login
from app.services.template_render import render

router = APIRouter(prefix="/ops", dependencies=[Depends(require_login)])


_OPERATIONAL_ENDPOINTS = [
    # (path, purpose label)
    ("/healthz", "Liveness"),
    ("/healthz/db", "Database"),
    ("/healthz/deps", "Environment"),
    ("/healthz/schema", "Schema drift"),
    ("/healthz/errors", "Error counter (last 24h)"),
    ("/auditoria", "Audit log"),
    ("/ventas", "Today's sales"),
    ("/clientes", "Customers"),
    ("/produccion", "Production worksheet"),
    ("/reportes", "IVA / Libro de Ventas"),
]


@router.get("/status", response_class=HTMLResponse)
def ops_status(request: Request) -> HTMLResponse:
    """One-page operator dashboard with hot links.

    Open in browser when something looks broken. Every link here is
    a quick jump to a diagnostic page.
    """
    return render(request, "ops_status.html", {
        "endpoints": _OPERATIONAL_ENDPOINTS,
    })


__all__ = ["router"]
