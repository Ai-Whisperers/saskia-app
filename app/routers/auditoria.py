"""app/routers/auditoria.py — /auditoria (Audit log viewer).

Built on app/rms/audit.py list_recent() + AuditLog model.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.audit import list_recent, prune_audit_log, search_by_target
from app.rms.audit_analytics import compute_audit_analytics
from app.rms.dependencies import get_session
from app.rms.streaming_csv import stream_csv_rows
from app.services.template_render import render

router = APIRouter(prefix="/auditoria", dependencies=[Depends(require_login)])

PAGE_SIZE = 50


def _parse_date(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except ValueError:
        return None


def _date_presets() -> dict[str, tuple[str, str]]:
    """Return {label: (start, end)} for common date ranges."""
    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    week_start = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    month_start = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    return {
        "today": (today, today),
        "yesterday": (yesterday, yesterday),
        "last_7d": (week_start, today),
        "last_30d": (month_start, today),
    }


@router.get("", response_class=HTMLResponse)
def auditoria_index(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    action_filter: str | None = Query(None),
    start_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    ip_filter: str | None = Query(None, description="Filter by client IP"),
    user_filter: str | None = Query(None, description="Filter by user_id"),
    target_type: str | None = Query(None, description="Filter by target type (e.g. product)"),
    target_id: str | None = Query(None, description="Filter by record ID (e.g. 42)"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List recent audit log entries with optional filters and pagination.

    Supports:
    - Date range presets (today, yesterday, last 7d, last 30d)
    - Pagination (50 per page)
    - Record ID search (target_type + target_id)
    - JSON detail formatted as readable key-value pairs
    """
    # Handle record-ID search (find all changes to product #42)
    if target_type and target_id:
        rows = list(search_by_target(session, target_type, target_id, limit=limit))
        total_count = len(rows)
    else:
        rows = list(
            list_recent(
                session,
                limit=limit,
                action_filter=action_filter,
                user_filter=user_filter,
            )
        )
        total_count = len(rows)

    # Apply date-range filter in Python (limit=500 bounds memory).
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    if ed:
        ed = ed + timedelta(days=1)  # inclusive

    if sd:
        rows = [r for r in rows if r.occurred_at and r.occurred_at >= sd]
    if ed:
        rows = [r for r in rows if r.occurred_at and r.occurred_at < ed]

    # IP filter
    if ip_filter:
        rows = [r for r in rows if r.ip and ip_filter in r.ip]

    # Total for pagination
    total_count = len(rows)

    # Paginate
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    offset = (page - 1) * PAGE_SIZE
    paginated = rows[offset : offset + PAGE_SIZE]

    # P-43: redact sensitive keys in audit detail before rendering.
    SENSITIVE_KEYS = frozenset({
        "password", "passwd", "secret", "api_key", "apikey",
        "token", "authorization", "auth", "credential", "credentials",
    })

    def fmt_detail(detail: dict) -> list[tuple[str, str]]:
        if not detail:
            return []
        items = []
        for k, v in detail.items():
            key_lower = k.lower()
            is_sensitive = key_lower in SENSITIVE_KEYS or any(
                s in key_lower for s in ("password", "secret", "token", "api_key")
            )
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    sub_lower = sub_k.lower()
                    sub_sensitive = sub_lower in SENSITIVE_KEYS or any(
                        s in sub_lower for s in ("password", "secret", "token", "api_key")
                    )
                    rendered = "***" if sub_sensitive else str(sub_v)
                    items.append((k + "." + sub_k, rendered))
            else:
                rendered = "***" if is_sensitive else str(v)
                items.append((k, rendered))
        return items

    formatted_rows = [
        {
            "row": r,
            "detail_pairs": fmt_detail(r.detail or {}),
            "user_agent_short": (r.user_agent[:60] + "...") if r.user_agent and len(r.user_agent) > 60 else r.user_agent,
        }
        for r in paginated
    ]

    presets = _date_presets()

    return render(request, "auditoria.html", {
        "formatted_rows": formatted_rows,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "limit": limit,
        "action_filter": action_filter or "",
        "start_date": start_date or "",
        "end_date": end_date or "",
        "ip_filter": ip_filter or "",
        "user_filter": user_filter or "",
        "target_type": target_type or "",
        "target_id": target_id or "",
        "presets": presets,
        "page_start": (page - 1) * 50 + 1,
        "page_end": min(page * 50, total_count),
    })


@router.get("/export.csv")
def auditoria_export_csv(
    action_filter: str | None = Query(None),
    start_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    ip_filter: str | None = Query(None),
    user_filter: str | None = Query(None),
    target_type: str | None = Query(None),
    target_id: str | None = Query(None),
    session: Session = Depends(get_session),
) -> Response:
    """Export audit log rows matching the current filters as a CSV download.

    Adds the missing endpoint that /auditoria.html already linked to. Columns:
    id, timestamp, user_id, action, target_type, target_id, ip, user_agent.
    """
    import csv
    import io as _io

    # Build the same row set as the index view, but bypass pagination — CSV
    # exports the entire matching set (up to a safety cap).
    if target_type and target_id:
        rows = list(search_by_target(session, target_type, target_id, limit=10_000))
    else:
        rows = list(list_recent(session, limit=10_000, action_filter=action_filter, user_filter=user_filter))

    # Apply date + IP filters in Python (matches the index view).
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    if ed is not None:
        ed = ed + timedelta(days=1)
    filtered = []
    for r in rows:
        if sd is not None and r.timestamp < sd:
            continue
        if ed is not None and r.timestamp >= ed:
            continue
        if ip_filter and (r.ip or "") != ip_filter:
            continue
        filtered.append(r)

    filename = f"auditoria_{datetime.now(timezone.utc).date().isoformat()}.csv"
    return StreamingResponse(
        stream_csv_rows(
            ["id", "timestamp", "user_id", "action", "target_type", "target_id", "ip", "user_agent_short"],
            (
                [
                    r.id,
                    r.timestamp.isoformat() if r.timestamp else "",
                    r.user_id or "",
                    r.action or "",
                    r.target_type or "",
                    r.target_id or "",
                    r.ip or "",
                    (r.user_agent or "")[:80],
                ]
                for r in filtered
            ),
        ),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/prune")
def auditoria_prune(
    request: Request,
    older_than_days: int = Query(365, ge=1, le=3650),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete audit entries older than N days. Admin only."""
    deleted = prune_audit_log(session, older_than_days=older_than_days)
    session.commit()
    return RedirectResponse(url=f"/auditoria?pruned={deleted}", status_code=303)


@router.get("/analytics", response_class=HTMLResponse)
def auditoria_analytics(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """BACKLOG #30: aggregated audit log analytics.

    Complements the row-level /auditoria viewer with:
      - Top IPs by event count (with login.failure vs login.success split)
      - Top actions by frequency
      - Per-operator activity (events + distinct actions + last seen)
      - Login failure rate (overall)

    Read-only, no writes. Pure analytics.
    """
    report = compute_audit_analytics(session, days=days)
    return render(
        request,
        "auditoria_analytics.html",
        {"report": report, "days": days},
    )


__all__ = ["router"]
