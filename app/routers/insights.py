"""app/routers/insights.py — API endpoints for actionable insights.

GET /api/insights/ — retrieve actionable insights for dashboard
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.insights import build_actionable_insights

router = APIRouter(dependencies=[Depends(require_login)])


@router.get("/")
async def get_insights(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Get actionable insights for the dashboard.

    Returns up to 3 actionable insights that operators should act on.
    """
    try:
        insights = build_actionable_insights(session)
        return JSONResponse({"insights": insights})
    except Exception as e:
        # Insights engine fallback — log + return a typed 500 so the operator
        # sees the failure without losing the JSON contract.
        logger.warning("insights engine failed: {}", e, exc_info=True)
        return JSONResponse(
            {"error": "Failed to retrieve insights", "detail": str(e)}, status_code=500
        )


__all__ = ["router"]
