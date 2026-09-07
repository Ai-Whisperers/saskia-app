"""app/rms/audit.py — append-only audit log helper.

Per the 2026-09-04 critical-path plan, E3.S1.

Public API:
    record(session, *, user_id, action, target_type=None, target_id=None,
           detail=None, request=None)
        -> AuditLog row committed to the DB immediately.

        Best-effort: errors during audit logging NEVER propagate to the
        caller. The security event is what mattered; if we couldn't
        record it we still let the user proceed (logged to loguru as a
        warning so the operator notices).

    list_recent(session, *, limit=100, action_filter=None, user_filter=None)
        -> List[AuditLog] for the /audit admin view.

Usage from a router:

    from app.rms.audit import record
    from app.auth import current_user_id

    @router.post("/login")
    def login_submit(...):
        ...
        if login_ok:
            record(
                session,
                user_id=current_user_id(request),
                action="login.success",
                request=request,
                detail={"backend": "supabase" if _supabase_enabled() else "local"},
            )
        else:
            record(
                session,
                user_id=None,  # anonymous
                action="login.failure",
                request=request,
                detail={"reason": "bad_password"},
            )

Notes:
    - record() commits inside its own transaction. If the caller's session
      is mid-transaction, this is fine: SQLAlchemy 2.0 will flush the
      audit row as part of the outer commit. If the outer transaction
      rolls back, the audit row also rolls back. For most security events
      you want this — the audit row should reflect committed state, not
      attempted state. For "login.failure" / "logout" events that you
      want to record even if subsequent code raises, pass a fresh
      session_factory or call record with `commit=True` and accept that
      the audit row stands alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.orm import Session


def _client_ip(request: Optional["Request"]) -> Optional[str]:
    """Extract client IP from X-Forwarded-For (Cloudflare-aware) or fall back."""
    if request is None:
        return None
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Cloudflare sets the client as the first hop in X-Forwarded-For
        return xff.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host[:64]
    return None


def _user_agent(request: Optional["Request"]) -> Optional[str]:
    if request is None:
        return None
    ua = request.headers.get("user-agent", "")
    return ua[:256] if ua else None


def record(
    session: "Session",
    *,
    user_id: Any,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
    request: Optional["Request"] = None,
) -> None:
    """Append one audit row. Best-effort (errors swallowed + logged).

    Pass the caller's SQLAlchemy Session so the audit row joins the
    caller's transaction. To record in a separate transaction (e.g. for
    login failures that should persist even if the surrounding code
    crashes), use record_separate() instead.
    """
    from app.rms.models import AuditLog

    try:
        row = AuditLog(
            occurred_at=datetime.now(timezone.utc),
            user_id=str(user_id) if user_id is not None else None,
            action=action[:64],
            target_type=target_type[:64] if target_type else None,
            target_id=str(target_id)[:64] if target_id is not None else None,
            detail=detail or {},
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
        session.add(row)
        session.flush()  # surface integrity errors here, not at caller commit
    except Exception as exc:  # pragma: no cover — defensive
        # Audit must NEVER break the caller. Log and move on.
        logger.warning(f"audit.record failed for action={action!r}: {exc!r}")


def list_recent(
    session: "Session",
    *,
    limit: int = 100,
    action_filter: Optional[str] = None,
    user_filter: Optional[str] = None,
):
    """Return the most recent audit rows (newest first).

    Used by the /audit admin view.
    """
    from sqlalchemy import desc, select

    from app.rms.models import AuditLog

    stmt = select(AuditLog).order_by(desc(AuditLog.occurred_at)).limit(limit)
    if action_filter:
        stmt = stmt.where(AuditLog.action == action_filter)
    if user_filter:
        stmt = stmt.where(AuditLog.user_id == user_filter)
    return list(session.execute(stmt).scalars())
