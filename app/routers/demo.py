"""app/routers/demo.py — demo seed endpoint (phase 2 of 4).

Exposes POST /demo/seed which builds the complete Kyrian demo customer
via app.seed.kyrian.seed_kyrian().

GATED by env var AIW_DEMO_SEED_ENABLED. Default OFF. Operator flips it
in /opt/build-apps/sazon-rms/.env to enable the demo on a specific
environment. Production must never set this flag.

Why a flag and not an admin role:
- The seed is destructive: it deletes prior Kyrian data by phone.
- Operators need to be aware they're invoking it; the env flag forces
  the deployment to opt-in (visible in version control + .env diff).
- A future admin role check is a small follow-up; out of scope here.

Response shape:
  {
    "ok": true,
    "customer_id": 9,
    "pedidos_created": 6,
    "sales_created": 17,
    "loyalty_ledger_rows": 19,
    "addresses_created": 2,
    "subscription_created": true,
    "lifetime_spent_gs": 720000,
    "duration_ms": 234
  }
"""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.rms.dependencies import get_session
from app.seed.kyrian import seed_kyrian

router = APIRouter(prefix="/demo", tags=["demo"])


def _is_enabled() -> bool:
    """Feature flag check. Default OFF — must be explicitly enabled."""
    return os.getenv("AIW_DEMO_SEED_ENABLED", "").strip().lower() in ("1", "true", "yes")


@router.post("/seed")
def demo_seed(session: Any = Depends(get_session)) -> JSONResponse:
    """Build the Kyrian demo customer. Idempotent.

    Returns a JSON summary of what was created/replaced. Errors with
    403 when the feature flag is not set; 500 on any DB-level failure.
    """
    if not _is_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Demo seed is disabled. Set AIW_DEMO_SEED_ENABLED=true "
                "in /opt/build-apps/sazon-rms/.env to enable."
            ),
        )

    t0 = time.perf_counter()
    try:
        bundle = seed_kyrian(session)
        session.commit()
    except Exception as exc:
        # Roll back first so the session is clean for the next request.
        session.rollback()
        # Don't leak the exception repr back to the client — it includes
        # file paths and stack info (OWASP ZAP rule 110009, "Full Path
        # Disclosure"). Log server-side for the operator; return a
        # generic message.
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Demo seed failed for /demo/seed")
        raise HTTPException(status_code=500, detail="Demo seed failed. See server logs.") from exc

    return JSONResponse(
        {
            "ok": True,
            "customer_id": bundle.customer.id,
            "customer_name": bundle.customer.name,
            "pedidos_created": len(bundle.pedidos),
            "sales_created": len(bundle.sales),
            "loyalty_ledger_rows": len(bundle.loyalty_ledger),
            "addresses_created": len(bundle.addresses),
            "subscription_created": bundle.suscripcion is not None,
            "lifetime_spent_gs": bundle.lifetime_spent_gs,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        }
    )


@router.get("/seed/status")
def demo_seed_status() -> dict[str, Any]:
    """Tell the operator whether the demo seed endpoint is reachable.

    Returns:
      {"enabled": bool, "endpoint": "POST /demo/seed"}

    Never raises — used by the /inicio dashboard or the user-guide to
    show "Demo seed is enabled" vs greyed out.
    """
    return {"enabled": _is_enabled(), "endpoint": "POST /demo/seed"}
