"""app/routers/insights.py — API endpoints for actionable insights.

GET /api/insights/ — retrieve actionable insights for dashboard
POST /api/insights/{id}/dismiss — dismiss an insight for today
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.dependencies import get_session
from app.rms.insights import build_actionable_insights
from app.rms.models import Sale  # for type imports

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
        return JSONResponse(
            {"error": "Failed to retrieve insights", "detail": str(e)}, 
            status_code=500
        )


@router.post("/{insight_id}/dismiss")
async def dismiss_insight(
    request: Request,
    insight_id: str,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Dismiss an actionable insight for today.
    
    Audits the dismissal with action="insight.dismissed".
    """
    # Verify CSRF token is present in form (should match the one in the template)
    if not csrf_token:
        return JSONResponse(
            {"error": "CSRF token required"}, 
            status_code=400
        )
    
    # Record the dismissal in audit log
    try:
        audit_record(
            session,
            user_id=str(request.state.user.id) if hasattr(request.state, 'user') and request.state.user else None,
            action="insight.dismissed",
            target_type="insight",
            target_id=insight_id,
            detail={
                "insight_id": insight_id,
                "day": str(session.execute("SELECT CURRENT_DATE").scalar())
            }
        )
        session.commit()
    except Exception as e:
        # Audit failures shouldn't break the UI, but we log them
        from loguru import logger
        logger.warning(f"Failed to record insight dismissal: {e}")
        session.rollback()
    
    return JSONResponse({"success": True})


__all__ = ["router"]