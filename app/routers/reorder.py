"""app/routers/reorder.py — operator reorder suggestions.

GET /reorder                — HTML view
GET /reorder?format=json    — machine-readable for future /scripts integrations
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.reorder import compute_reorder_list
from app.services.template_render import render

router = APIRouter(prefix="/reorder", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse, response_model=None)
def reorder_view(
    request: Request,
    format: str = Query("html", pattern="^(html|json)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse | JSONResponse:
    """Show ingredients that need reordering.

    HTML mode: ranked table grouped by urgency.
    JSON mode: structured payload for tooling.
    """
    items = compute_reorder_list(session)
    total_cost = sum(i.estimated_cost_gs for i in items)

    if format == "json":
        return JSONResponse({
            "items": [
                {
                    "ingredient_id": i.ingredient_id,
                    "name": i.name,
                    "unit": i.unit,
                    "current_stock": i.current_stock,
                    "min_stock": i.min_stock,
                    "max_stock": i.max_stock,
                    "suggested_qty": i.suggested_qty,
                    "estimated_cost_gs": i.estimated_cost_gs,
                    "urgency": i.urgency,
                }
                for i in items
            ],
            "total_estimated_cost_gs": total_cost,
            "count": len(items),
        })

    return render(request, "reorder.html", {
        "items": items,
        "total_cost_gs": total_cost,
        "count": len(items),
    })


__all__ = ["router"]
