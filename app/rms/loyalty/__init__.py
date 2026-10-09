"""app/rms/loyalty/__init__.py — the operator loyalty domain (E13).

Single home for everything loyalty-related:
  - ledger.py      points math, ledger writes, balance reconciliation
  - tiers.py       tier thresholds + tier_for_spend helper
  - suggestions.py suggestion-card rules engine (cumple_cerca, dormant, lapsed, vip)

Customer-directory helpers (search, stats, history) stay in
``app/rms/customers.py`` since they span loyalty + sales + customer
info. HTTP endpoints (POST /clientes/api/{id}/suggestion-applied,
GET /clientes) stay in ``app/routers/customers.py`` since they're
transport concerns.

Public re-exports preserve the old single-file import path
(``from app.rms.customers import award_points`` still works) so this
is a pure refactor — no behaviour change.
"""

from __future__ import annotations

from app.rms.loyalty.ledger import (
    POINTS_PER_GS,
    POINTS_PER_GS_EARN,
    POINTS_VALUE_GS,
    award_points,
    discount_gs_for_points,
    effective_return_rate,
    points_for_sale,
    reconcile_loyalty_balance,
    redeem_points,
    reverse_points_for_void,
)
from app.rms.loyalty.suggestions import (
    Suggestion,
    suggest_for_customer,
)
from app.rms.loyalty.tiers import (
    TIER_THRESHOLDS,
    LoyaltyTier,
    tier_for_spend,
)

__all__ = [
    "POINTS_PER_GS",
    "POINTS_PER_GS_EARN",
    "POINTS_VALUE_GS",
    "TIER_THRESHOLDS",
    "LoyaltyTier",
    "Suggestion",
    "award_points",
    "discount_gs_for_points",
    "effective_return_rate",
    "points_for_sale",
    "reconcile_loyalty_balance",
    "redeem_points",
    "reverse_points_for_void",
    "suggest_for_customer",
    "tier_for_spend",
]
