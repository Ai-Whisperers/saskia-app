"""app/rms/schemas.py — Pydantic 2 request models for state-changing endpoints.

Why: raw form parsing lets bad data through (negative discounts, huge
quantities, missing fields). Pydantic rejects at the validation layer
(FastAPI returns 422) before any business logic runs.

Each model is a thin wrapper over FastAPI's `Form(...)` constraints.
We *could* use full Pydantic BaseModels with `as_form()` parsing, but
that adds complexity. FastAPI's parameter-level `Form(..., gt=0)`
constraints are simpler and explicit.
"""

from __future__ import annotations

from app.rms.models.channels import Channel

MAX_QTY = 1_000_000  # sanity cap — never selling a million of anything
MAX_DISCOUNT_GS = 100_000_000  # 100M Gs. = $14,000 USD discount upper bound
ALLOWED_PAYMENT_METHODS = frozenset(
    {
        "efectivo",
        "fiado",
        "transferencia",
        "qr",
        "tarjeta",
        "otro",
    }
)

# Display order for the /ventas form-select. `efectivo` is the most
# common sale type for the operator (per her Ciudad del Este workflow) so
# it sits at the top.
PAYMENT_METHODS_DISPLAY: tuple[str, ...] = (
    "efectivo",
    "transferencia",
    "qr",
    "tarjeta",
    "otro",
)
PAYMENT_METHOD_DEFAULT = "efectivo"

# Stream A prelaunch: which sales channel produced this sale.
# P43 (2026-10-07): source from Channel enum to stay in sync with the
# DB CHECK constraint (migration 111). Previously this set omitted
# "other" — meaning a sale with channel="other" would pass the DB
# CHECK but be rejected by sales.py:970/1486 with HTTP 400.
ALLOWED_CHANNELS = frozenset(Channel.allowed_values())
# P43: source from enum so display order stays in sync with allowed set.
CHANNELS_DISPLAY: tuple[str, ...] = Channel.display_order()
CHANNEL_DEFAULT = Channel.MOSTRADOR.value


# Re-export common constants. Routers import these for validation.
__all__ = [
    "ALLOWED_CHANNELS",
    "ALLOWED_PAYMENT_METHODS",
    "CHANNELS_DISPLAY",
    "CHANNEL_DEFAULT",
    "MAX_DISCOUNT_GS",
    "MAX_QTY",
    "PAYMENT_METHODS_DISPLAY",
    "PAYMENT_METHOD_DEFAULT",
]
