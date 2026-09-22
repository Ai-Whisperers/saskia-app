"""Health endpoints — /healthz and /healthz/db.

Per docs/operations/2026-09-fase-1-specs.md §C.

When her browser shows a blank page, the diagnostic chain is:
1. Is uvicorn running? -> /healthz returns 200
2. Is the DB reachable? -> /healthz/db returns 200
3. Is the page route broken? -> look at browser devtools

Without this, debugging takes 10 minutes of "is it Python? is it the
browser? is it Windows Defender?"

Security: these endpoints return no PII, no DB content, no internal
state. They only report liveness and DB mode. Safe to hit.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

router = APIRouter()


def _healthz_payload() -> dict[str, Any]:
    """Shared payload for GET and HEAD (HEAD strips the body at transport level)."""
    return {
        "status": "ok",
        "service": "aiw-saskia-rms",
    }


@router.get("/healthz", response_model=None)
def healthz(request: Request) -> JSONResponse | dict:
    """Cheap health check.

    Returns 200 if the app finished startup. Returns 503 if the lifespan
    is still running (cold-start window). Returns 200 with body if
    startup completed successfully.

    Why gate on app.state.ready: during the cold-start window, uvicorn
    accepts requests before our lifespan calls create_all()/init_db().
    Any request that hits the dashboard during this window returned
    raw 500s with no info. /healthz returning 503 lets the operator
    see "warming up" instead of broken.
    """
    ready = getattr(request.app.state, "ready", False)
    if not ready:
        # Cold-start window — return 503 with structured payload so the
        # operator's UptimeRobot monitor shows "warming up".
        return JSONResponse(
            status_code=503,
            content={
                "status": "warming_up",
                "service": "aiw-saskia-rms",
                "detail": "App is still initializing; retry in a few seconds.",
            },
        )
    return _healthz_payload()


@router.head("/healthz", name="healthz-head")
def healthz_head(request: Request) -> Response:
    """HEAD variant for uptime monitors (UptimeRobot) that probe with HEAD.

    Same 503/200 logic as GET — body is stripped by the transport layer.
    """
    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return Response(status_code=503, media_type="application/json")
    return Response(status_code=200, media_type="application/json")


@router.get("/healthz/errors", response_model=None)
def healthz_errors(request: Request) -> JSONResponse:
    """Quick error-rate snapshot for the operator.

    Counts how many `action="http.500"` rows are in audit_log over the
    last 24h and last 1h. Operators hit this when the user sees "page
    not loading" — instantly know if there were recent server errors.

    Read-only public endpoint (sanitized: no PII, just counts).
    """
    from datetime import datetime, timedelta

    from sqlalchemy import func, select

    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up"},
        )

    from app.rms.models import AuditLog

    now = datetime.now()
    last_1h = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)

    with request.app.state.session_factory() as s:
        n_1h = s.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "http.500", AuditLog.occurred_at >= last_1h)
        ).scalar() or 0
        n_24h = s.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "http.500", AuditLog.occurred_at >= last_24h)
        ).scalar() or 0

    return JSONResponse(
        content={
            "http_500_count": {
                "last_1h": int(n_1h),
                "last_24h": int(n_24h),
            },
            "hint": "If last_1h > 0, check Render deploy logs or /auditoria?action_filter=http.500",
        }
    )


@router.get("/healthz/deps", response_model=None)
def healthz_deps(request: Request) -> JSONResponse | dict:
    """Dependency fingerprint for debugging env mismatches on Render.

    Reports presence + sha256 prefix of key env vars (never the values)
    and importable package versions. Public: safe metadata only.

    Gated on app.state.ready: returns 503 if app is still warming up,
    so probes during the cold-start window correctly distinguish
    "broken" from "warming up".
    """
    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up", "detail": "App still initializing."},
        )
    import hashlib
    import importlib.metadata as md

    def fp(name: str) -> str | None:
        v = os.environ.get(name)
        if v is None:
            return None
        return f"len={len(v)} sha={hashlib.sha256(v.encode()).hexdigest()[:12]}"

    pkgs = {}
    for pkg in ("supabase", "supabase-auth", "fastapi", "starlette"):
        try:
            pkgs[pkg] = md.version(pkg)
        except Exception:
            pkgs[pkg] = "NOT INSTALLED"
    return {
        "SUPABASE_URL": fp("SUPABASE_URL"),
        "SUPABASE_PUBLISHABLE_KEY": fp("SUPABASE_PUBLISHABLE_KEY"),
        "SUPABASE_SECRET_KEY": fp("SUPABASE_SECRET_KEY"),
        "packages": pkgs,
    }


@router.get("/healthz/db")
def healthz_db(request: Request) -> JSONResponse:
    """DB health check.

    Returns 200 if the database is reachable; 503 otherwise.
    Reports:
    - journal_mode on SQLite (must be 'wal' for concurrent-safe writes)
    - server version on Postgres
    - schema_version + migrations_pending (drift detector)
    - last_audit_at (timestamp of most recent audit log row)
    """
    from app.rms.db import (
        CURRENT_SCHEMA_VERSION,
        schema_version,
        schema_version_mismatch,
    )

    engine = request.app.state.engine
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result != 1:
                return JSONResponse(
                    {"db": "unreachable", "detail": "SELECT 1 failed"},
                    status_code=503,
                )
            payload: dict[str, Any] = {"db": "ok"}
            dialect = engine.dialect.name
            if dialect == "sqlite":
                mode = conn.execute(text("PRAGMA journal_mode")).scalar()
                payload["journal_mode"] = mode
                payload["dialect"] = "sqlite"
            elif dialect == "postgresql":
                ver = conn.execute(text("SHOW server_version")).scalar()
                payload["server_version"] = ver
                payload["dialect"] = "postgresql"
            else:
                payload["dialect"] = dialect
        # Schema drift + audit freshness — second roundtrip. Don't fail the
        # 200 just because these queries fail; report them in the body.
        try:
            with engine.connect() as conn:
                actual = schema_version(conn)
                payload["schema_version"] = actual
                payload["code_schema_version"] = CURRENT_SCHEMA_VERSION
                payload["migrations_pending"] = schema_version_mismatch(conn)
                # Most recent audit row — diagnostic for "is anything being
                # written?" without exposing content. SQLite returns the
                # timestamp as a string; Postgres returns a datetime.
                last = conn.execute(
                    text("SELECT MAX(occurred_at) FROM audit_log")
                ).scalar()
                if last is None:
                    payload["last_audit_at"] = None
                elif hasattr(last, "isoformat"):
                    payload["last_audit_at"] = last.isoformat()
                else:
                    payload["last_audit_at"] = str(last)
        except Exception as inner_exc:
            # Don't 503 the whole endpoint — DB is reachable, the metadata
            # queries aren't. Surface the detail so the operator can tell
            # the difference between "DB down" and "audit table missing".
            payload["db"] = "ok_no_metadata"
            payload["metadata_error"] = str(inner_exc)
        return payload
    except Exception as exc:
        return JSONResponse({"db": "error", "detail": str(exc)}, status_code=503)


__all__ = ["router"]


@router.get("/healthz/schema", response_model=None)
def healthz_schema(request: Request) -> JSONResponse:
    """Drift detector: returns code_version, db_version, drift.

    drift > 0 = DB behind code (CRITICAL — production will 500 on
    new columns). Operator action: redeploy to apply pending migrations
    (init_db() auto-runs as of 2026-09-08 by default).

    Returns 500 when drift > 0 so monitoring tools (UptimeRobot) alert.
    """
    from app.rms.db import (
        CURRENT_SCHEMA_VERSION,
        schema_version,
        schema_version_mismatch,
    )

    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up"},
        )

    with request.app.state.session_factory() as s:
        actual = schema_version(s.connection())
        drift = schema_version_mismatch(s.connection())

    body: dict[str, Any] = {
        "code_version": CURRENT_SCHEMA_VERSION,
        "db_version": actual,
        "drift": drift,
    }
    if drift > 0:
        body["hint"] = (
            f"DB schema v{actual}, code expects v{CURRENT_SCHEMA_VERSION}. "
            "Redeploy to apply pending migrations automatically."
        )
        body["status"] = "schema_drift"
        return JSONResponse(status_code=500, content=body)
    body["status"] = "in_sync"
    return JSONResponse(status_code=200, content=body)


@router.get("/healthz/debug-ventas-v3", response_model=None)
def healthz_debug_ventas_v3(request: Request) -> JSONResponse:
    """Render ventas.html with REAL data from the live DB to find the error."""
    import traceback
    from sqlalchemy import select, func
    from datetime import datetime, timedelta
    from app.rms.models import Product, Sale
    from app.rms.config import ASUNCION_TZ
    from app.services.template_render import render

    try:
        session = get_session(request)
        # Mimic EXACT actual ventas route code
        products = session.scalars(select(Product).order_by(Product.name)).all()
        sales_page = session.scalars(
            select(Sale)
            .options(selectinload(Sale.product), selectinload(Sale.customer))
            .order_by(Sale.sold_at.desc())
            .limit(20)
        ).all()
        
        # Mimic _decorated exactly as in app/routers/sales.py
        from app.routers.sales import _decorated
        decorated = [_decorated(s) for s in sales_page]
        
        # Mimic rest of context
        since = datetime.now(ASUNCION_TZ) - timedelta(days=14)
        quick_sell_q = (
            select(Sale.product_id, func.sum(Sale.qty), func.sum(Sale.qty * Sale.unit_price_gs))
            .where(Sale.sold_at >= since, Sale.voided_at.is_(None))
            .group_by(Sale.product_id)
            .order_by(func.sum(Sale.qty * Sale.unit_price_gs).desc())
            .limit(5)
        )
        quick_rows = session.execute(quick_sell_q).all()
        product_by_id = {p.id: p for p in products}
        quick_sell = []
        for pid, units, rev in quick_rows:
            p = product_by_id.get(pid)
            if p is not None:
                quick_sell.append({
                    "product_id": pid,
                    "name": p.name,
                    "sale_price_gs": p.sale_price_gs,
                    "units": float(units),
                    "revenue_gs": int(rev or 0),
                    "is_available": p.is_available,
                    "stock_qty": getattr(p, "stock_qty", None),
                })
        
        # Try to render
        try:
            render(request, "ventas.html", {
                "products": [{"id": p.id, "name": p.name, "portion_label": p.portion_label,
                              "sale_price_gs": p.sale_price_gs, "is_available": p.is_available, "sku": p.sku}
                             for p in products],
                "sales": decorated,
                "quick_sell": quick_sell,
                "payment_methods": ["efectivo"],
                "payment_method_default": "efectivo",
                "channels": ["mostrador"],
                "channel_default": "mostrador",
                "now_local": datetime.now().strftime("%Y-%m-%dT%H:%M"),
                "totals": {"count": len(sales_page), "total_gs": 0, "avg_ticket_gs": 0, "filters": "test"},
                "has_more": False,
                "current_offset": 0,
                "current_page_size": 20,
                "page_start": 1,
                "page_end": len(sales_page),
                "total_count": len(sales_page),
            })
            return JSONResponse({"status": "ok", "products": len(products), "sales": len(sales_page)})
        except Exception as template_exc:
            return JSONResponse({
                "status": "template_error",
                "exception_type": type(template_exc).__name__,
                "message": str(template_exc)[:500],
                "traceback": traceback.format_exc()[:2000],
            }, status_code=500)
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "exception_type": type(e).__name__,
            "message": str(e)[:500],
            "traceback": traceback.format_exc()[:1500],
        }, status_code=500)
