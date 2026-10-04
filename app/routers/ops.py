"""app/routers/ops.py — operator-side routes for diagnosis.

These are intentionally NOT user-facing for the bakery operator —
they're for the system operator (Iván) and Kiki (developer). They
give one-page views of system health and quick links to investigate.

Mounted at /ops/* with the standard require_login dependency.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth import current_user_id
from app.auth import require_login_or_disabled as require_login
from app.services.demo_reset import reset_demo_data
from app.services.template_render import render

router = APIRouter(prefix="/ops", dependencies=[Depends(require_login)])


_OPERATIONAL_ENDPOINTS = [
    # (path, purpose label)
    ("/healthz", "Liveness"),
    ("/healthz/summary", "Vista consolidada del sistema"),
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
    # BACKLOG #35 (2026-10-02): surface reorder stats on the operator
    # dashboard so they can spot loyalty trends at a glance. Pure read —
    # no auth gates beyond the route's require_login dependency.
    reorder_stats: dict = {
        "total_customers": 0,
        "customers_with_2plus_orders": 0,
        "reorder_rate": 0.0,
        "avg_days_between_orders": 0.0,
        "median_days_between_orders": 0.0,
        "top_repeaters": [],
    }
    try:
        from app.rms.sales_intel import customer_reorder_rates

        with request.app.state.session_factory() as _s:
            reorder_stats = customer_reorder_rates(_s, since_days=90, top_n=5)
    except Exception:  # noqa: BLE001, S110 — defensive default; failures re-rendered as zeros in template
        # Reorder stats are a dashboard feature, not critical path.
        # If the query fails, the dashboard still renders with zeros.
        pass

    return render(
        request,
        "ops_status.html",
        {
            "endpoints": _OPERATIONAL_ENDPOINTS,
            "reorder_stats": reorder_stats,
        },
    )


@router.post("/reset-demo-data")
async def ops_reset_demo_data(request: Request) -> JSONResponse:
    """Wipe synthetic demo state. Operator-only (requires login).

    Idempotent: re-running deletes 0 rows. Records itself as
    audit_log action='system.demo_reset' so we have a paper trail.

    Returns JSON with deleted-row counts so the operator can confirm
    what happened. Browsers won't navigate to this (it's a POST); we
    always return JSON regardless of Accept header.
    """
    user_id = current_user_id(request) or "anonymous"
    from fastapi import HTTPException
    from sqlalchemy.orm import Session

    # Re-derive session from app.state (avoids Depends(get_session)
    # which would tie us into the global sessionmaker; we want the
    # operator endpoint to be usable from /ops/status link clicks too).
    session_factory = request.app.state.session_factory
    session: Session = session_factory()
    try:
        counts = reset_demo_data(session)
        # Annotate the audit detail with the caller's user id
        # (reset_demo_data already recorded a row, so just log here).
        from loguru import logger

        logger.info(f"demo_reset invoked by user_id={user_id} counts={counts}")
    except Exception as exc:
        session.close()
        raise HTTPException(status_code=500, detail=f"reset_demo_data failed: {exc}") from exc
    finally:
        try:
            session.close()
        except Exception as exc:  # noqa: BLE001 — defensive default
            # Session may already be closed by dependency cleanup; not fatal.
            logger.debug("ops session close failed: {}", exc)

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "deleted": counts,
            "invoked_by": user_id,
        },
    )


__all__ = ["router"]
