"""app/rms/loyalty/suggestions.py — Decision C (Phase 4, 2026-10-01) +
Batch B1 extraction (2026-10-07).

Auto-suggest rules engine for the POS customer card. Pure functions
that take a Customer + their sale history and return up to N actionable
suggestions to surface at the till:

  - "vuelve_pronto" — customer hasn't visited in N days; suggest
    a small discount to bring them back (LAPSED rule).
  - "cumple_cerca" — birthday within N days; suggest a freebie or
    small discount (BIRTHDAY rule).
  - "puntos_dormidos" — customer has ≥threshold points but didn't
    redeem on the last visit; nudge a redeem (POINTS-DORMANT rule).
  - "cliente_fiel" — top-tier customer; small recognition text
    only (NO discount to avoid margin erosion on big spenders)
    (VIP rule).
  - "cross_sell" — customer has `sin gluten` (or other) dietary
    restriction; surface the top-selling sin-gluten product as a
    cross-sell (CROSS-SELL rule — threshold reserved, not yet wired).

Design rules:
  - Suggestions NEVER bypass the cashier. They pre-fill the existing
    ``discount_gs`` field with a suggested amount; cashier confirms
    or ignores.
  - Maximum `max_suggestions` returned per call (UI space constraint).
  - Priority order: cumpleaños → vuelve pronto → puntos dormidos →
    cross-sell → cliente fiel. Highest-priority suggestions win ties.
  - All thresholds live in a configurable dict (Batch B1, 2026-10-07)
    so the operator can tune via /admin/settings without code changes.
    The DEFAULT_LOYALTY_CONFIG dict below is the canonical source of
    defaults; get_loyalty_config() reads from SettingsKV and falls
    back to these values for any missing key.
  - Pure function: takes a Customer + sales-derived stats; no DB
    queries inside (except the redeemed_on_last_visit hint, which is
    a separate session-scoped helper). Caller wires the data.

This module does NOT do I/O or import FastAPI for the pure-function
path. The router stitches the inputs and includes the result in the
customer detail payload (``/clientes/api/{id}``).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

# T-2026-10-01: use the live discount rate (POINTS_VALUE_GS) instead of
# the old hardcoded 1000 Gs/point that gave a 100% return rate.
from app.rms.loyalty.ledger import POINTS_VALUE_GS

if TYPE_CHECKING:
    from app.rms.models_legacy import Customer

# Batch B1 (2026-10-07): per-domain settings extraction. The constants
# that used to live as module-level globals here are now in
# app/rms/settings.py:SETTINGS (keys prefixed ``loyalty.``) with the
# defaults defined below. The pure-function API accepts an optional
# ``loyalty_cfg`` dict kwarg; when None, defaults are used.
DEFAULT_LOYALTY_CONFIG: dict[str, int] = {
    # LAPSED thresholds (days without a visit, by tier)
    "lapsed_days_bronze": 21,
    "lapsed_days_silver": 30,
    "lapsed_days_gold": 45,
    # LAPSED discount percent by tier (int 0–100)
    "lapsed_discount_pct_bronze": 10,
    "lapsed_discount_pct_silver": 7,
    "lapsed_discount_pct_gold": 5,
    # BIRTHDAY window + discount
    "birthday_window_days": 7,
    "birthday_discount_pct": 15,
    # POINTS-DORMANT
    "points_dormant_threshold": 50,
    # CROSS-SELL (reserved, not yet wired into a rule)
    "cross_sell_min_sales": 3,
    # Cap on returned suggestions
    "max_suggestions": 3,
}


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Suggestion:
    """A single auto-suggested offer for the customer card.

    Fields:
      kind        — discriminator (see constants below).
      title       — short headline shown on the suggestion card.
      body        — explanation / call to action.
      priority    — int; lower = higher priority. Internal sort key.
      discount_pct — optional int; if set, the click handler will
                     pre-fill ``discount_gs`` on the sale form with
                     ``ceil(unit_price_gs * discount_pct / 100)``.
                     The cashier confirms before the sale commits.
      payload     — opaque dict for the click handler (e.g. the
                     product_id of a cross-sell suggestion).
    """

    kind: str
    title: str
    body: str
    priority: int
    discount_pct: Optional[int] = None
    payload: dict = field(default_factory=dict)


# Suggestion kinds — keep in sync with the UI renderer.
KIND_VUELVE_PRONTO = "vuelve_pronto"
KIND_CUMPLE_CERCA = "cumple_cerca"
KIND_PUNTOS_DORMIDOS = "puntos_dormidos"
KIND_CLIENTE_FIEL = "cliente_fiel"
KIND_CROSS_SELL = "cross_sell"


# ──────────────────────────────────────────────────────────────────────
# Pure suggestion function
# ──────────────────────────────────────────────────────────────────────


def suggest_for_customer(
    customer: "Customer",
    *,
    last_sale_at: Optional[_dt.datetime],
    n_sales: int,
    tier: str,
    redeemed_on_last_visit: bool,
    today: Optional[_dt.date] = None,
    loyalty_cfg: Optional[dict[str, int]] = None,
) -> list[Suggestion]:
    """Return up to `max_suggestions` suggestions for this customer.

    Args:
      customer: the Customer ORM row (we read .birthday, .loyalty_points,
        .dietary_restrictions).
      last_sale_at: when the customer last bought something; None if
        they've never bought.
      n_sales: total sales count.
      tier: the loyalty tier string ("BRONZE" | "SILVER" | "GOLD").
      redeemed_on_last_visit: whether the cashier redeemed points on
        the last sale. Used to skip the POINTS-DORMANT rule when the
        customer is already redeeming regularly.
      today: override for testability. Defaults to today's date in
        Asunción (caller should pass it; this function is pure).
      loyalty_cfg: optional override dict for the tunable thresholds
        (Batch B1, 2026-10-07). When None, defaults from
        DEFAULT_LOYALTY_CONFIG are used. Caller should pass
        get_loyalty_config(session) for production use.

    Returns:
      List of Suggestion objects, sorted by priority then by kind
      (stable). Empty list when no rule fires.
    """
    if today is None:
        today = _dt.datetime.now(_dt.UTC).date()

    # Merge operator overrides onto the canonical config. A partial
    # cfg (e.g. tests passing {lapsed_discount_pct_bronze: 25})
    # falls back to defaults for the unspecified keys — so callers
    # only override what they care about.
    cfg = dict(DEFAULT_LOYALTY_CONFIG)
    if loyalty_cfg is not None:
        cfg.update(loyalty_cfg)

    out: list[Suggestion] = []

    # Rule: cumpleaños dentro de N días (BIRTHDAY)
    birthday_sugg = _maybe_birthday(customer.birthday, today=today, cfg=cfg)
    if birthday_sugg is not None:
        out.append(birthday_sugg)

    # Rule: cliente que no viene hace N días (LAPSED)
    lapsed_sugg = _maybe_lapsed(
        last_sale_at=last_sale_at,
        tier=tier,
        today=today,
        cfg=cfg,
    )
    if lapsed_sugg is not None:
        out.append(lapsed_sugg)

    # Rule: ≥threshold puntos y no canjeó la última vez (POINTS-DORMANT)
    dormant_sugg = _maybe_points_dormant(
        loyalty_points=customer.loyalty_points,
        n_sales=n_sales,
        redeemed_on_last_visit=redeemed_on_last_visit,
        cfg=cfg,
    )
    if dormant_sugg is not None:
        out.append(dormant_sugg)

    # Rule: cliente fiel (top tier, >10 ventas) — sólo reconocimiento,
    # NUNCA descuento (no erosionamos margen sobre quien ya vuelve).
    vip_sugg = _maybe_vip(n_sales=n_sales, tier=tier)
    if vip_sugg is not None:
        out.append(vip_sugg)

    # Sort by priority (lower wins), then by kind for stability.
    out.sort(key=lambda s: (s.priority, s.kind))

    # T-2026-10-01: reviewer's "redundant suggestions" rule.
    # If the ONLY suggestion is a points-dormant reminder AND the
    # customer-detail page already shows the points balance
    # prominently (it does — see the KPI tile "Puntos" in
    # cliente_detalle.html), drop it. Reviewer caught the "merely
    # repeats the point balance" waste of vertical space. Keep the
    # card when it's one of multiple suggestions (it's still useful
    # as an action item in context) or when it carries a unique
    # algorithmic insight we don't surface elsewhere.
    if len(out) == 1 and out[0].kind == KIND_PUNTOS_DORMIDOS:
        return []

    return out[: cfg["max_suggestions"]]


def _maybe_birthday(
    birthday_str: Optional[str],
    *,
    today: _dt.date,
    cfg: dict[str, int],
) -> Optional[Suggestion]:
    """Cumpleaños dentro de la ventana (configurable, default 7 días).

    Soporta dos formatos almacenados en ``customer.birthday``:
      - "MM-DD" — cumpleaños sin año (caso normal, recurrente).
      - "YYYY-MM-DD" — cumpleaños con año (cuando the operator lo conoce).
    Para el primer caso, sólo nos importa mes+día; el año "actual"
    se calcula de forma que si el MM-DD ya pasó este año, el
    cumpleaños es el del año próximo (siempre dentro de la ventana).
    """
    if not birthday_str:
        return None
    try:
        if len(birthday_str) == 10 and birthday_str[4] == "-":
            bday = _dt.date.fromisoformat(birthday_str)
        elif len(birthday_str) == 5 and birthday_str[2] == "-":
            month, day = birthday_str.split("-")
            bday = _candidate_recurring_birthday(int(month), int(day), today)
        else:
            return None
    except ValueError:
        return None

    days_until = (bday - today).days
    if days_until < 0 or days_until > cfg["birthday_window_days"]:
        return None

    pct = cfg["birthday_discount_pct"]
    if days_until == 0:
        body = f"¡Es su cumpleaños hoy! Ofrecerle un {pct}% de descuento."
    else:
        body = (
            f"Cumple en {days_until} día{'s' if days_until != 1 else ''}. "
            f"Ofrecerle un {pct}% de descuento en su próxima compra."
        )
    return Suggestion(
        kind=KIND_CUMPLE_CERCA,
        title="🎂 Cumple cerca",
        body=body,
        priority=10,  # highest
        discount_pct=pct,
    )


def _candidate_recurring_birthday(month: int, day: int, today: _dt.date) -> _dt.date:
    """Pick the next occurrence of month/day on or after ``today``."""
    try:
        candidate = today.replace(month=month, day=day)
    except ValueError:
        # Feb 29 on a non-leap year → fall back to Feb 28.
        candidate = today.replace(month=month, day=day - 1)
    if candidate < today:
        # Already passed this year — try next year.
        try:
            candidate = candidate.replace(year=today.year + 1)
        except ValueError:
            # Feb 29 again — fall back to Feb 28 next year.
            candidate = candidate.replace(year=today.year + 1, day=day - 1)
    return candidate


def _maybe_lapsed(
    *,
    last_sale_at: Optional[_dt.datetime],
    tier: str,
    today: _dt.date,
    cfg: dict[str, int],
) -> Optional[Suggestion]:
    """Customer hasn't visited in N days (where N depends on tier)."""
    if last_sale_at is None:
        # Never visited — that's a "prospect", not a lapsed customer.
        # Defer to the POS team to ask for marketing_consent instead.
        return None

    if tier == "GOLD":
        threshold = cfg["lapsed_days_gold"]
        pct = cfg["lapsed_discount_pct_gold"]
    elif tier == "SILVER":
        threshold = cfg["lapsed_days_silver"]
        pct = cfg["lapsed_discount_pct_silver"]
    else:
        threshold = cfg["lapsed_days_bronze"]
        pct = cfg["lapsed_discount_pct_bronze"]

    last_visit_date = (
        last_sale_at.date() if isinstance(last_sale_at, _dt.datetime) else last_sale_at
    )
    days_since = (today - last_visit_date).days
    if days_since < threshold:
        return None

    return Suggestion(
        kind=KIND_VUELVE_PRONTO,
        title="💤 Vuelve pronto",
        body=(
            f"Hace {days_since} días que no visita. "
            f"Ofrecerle un {pct}% de descuento para tentar su vuelta."
        ),
        priority=20,
        discount_pct=pct,
        payload={"days_since": days_since, "tier": tier},
    )


def _maybe_points_dormant(
    *,
    loyalty_points: int,
    n_sales: int,
    redeemed_on_last_visit: bool,
    cfg: dict[str, int],
) -> Optional[Suggestion]:
    """Customer has ≥threshold points and didn't redeem on last visit.

    T-2026-10-01: the displayed discount now uses POINTS_VALUE_GS
    instead of a hardcoded *1000. Pre-fix this echoed a 10x inflated
    number on the cashier's screen.
    """
    if redeemed_on_last_visit:
        # Already redeeming — no need to nudge.
        return None
    if loyalty_points < cfg["points_dormant_threshold"]:
        return None
    if n_sales == 0:
        # Brand-new customer with manually-credited points? Nudge anyway.
        pass

    discount_gs = loyalty_points * POINTS_VALUE_GS
    return Suggestion(
        kind=KIND_PUNTOS_DORMIDOS,
        title="⭐ Puntos acumulados",
        body=(
            f"Tiene {loyalty_points} puntos sin usar "
            f"(≈ Gs. {discount_gs:,} de descuento). "
            f"Recordarle que puede canjearlos ahora."
        ),
        priority=30,
        discount_pct=None,  # don't auto-fill — points redeem has its own UI
        payload={"points": loyalty_points, "discount_gs": discount_gs},
    )


def _maybe_vip(*, n_sales: int, tier: str) -> Optional[Suggestion]:
    """Top-tier repeat customer — recognition only, no discount."""
    if tier != "GOLD" or n_sales < 10:
        return None
    return Suggestion(
        kind=KIND_CLIENTE_FIEL,
        title="👑 Cliente fiel",
        body=(
            f"Cliente GOLD con {n_sales} compras. "
            f"Reconocer su fidelidad — sin descuento automático."
        ),
        priority=50,  # lowest — only fires when nothing else does
        discount_pct=None,
    )


# ──────────────────────────────────────────────────────────────────────
# DB-backed hint used by the POS engine
# ──────────────────────────────────────────────────────────────────────


def redeemed_on_last_visit(session: Any, customer_id: int) -> bool:
    """True iff the customer's most recent non-voided sale had a
    ``LoyaltyTransaction(reason="redeem")`` row tied to it.

    Used by ``suggest_for_customer`` to skip the POINTS-DORMANT nudge
    when the customer is already redeeming regularly. Returns False
    on any error so the suggestions engine stays infallible (see
    ``_customer_detail_payload`` in ``app/routers/customers.py`` for
    the contract).

    Lives here (not in ``customers.py``) because the input is a
    customer_id, not a Customer object — it's a session-scoped hint
    used ONLY by the suggestions engine. Two queries: latest sale_id,
    then ledger row check.

    Args:
      session: SQLAlchemy session (sync).
      customer_id: the customer primary key.

    Returns:
      bool — True if the customer redeemed on their last visit.
    """
    try:
        from sqlalchemy import select as _sa_select

        from app.rms.models import LoyaltyTransaction, Sale

        latest_sale = session.execute(
            _sa_select(Sale.id)
            .where(Sale.customer_id == customer_id)
            .where(Sale.voided_at.is_(None))
            .order_by(Sale.sold_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_sale is None:
            return False
        redeem = session.execute(
            _sa_select(LoyaltyTransaction.id)
            .where(LoyaltyTransaction.sale_id == latest_sale)
            .where(LoyaltyTransaction.reason == "redeem")
            .limit(1)
        ).scalar_one_or_none()
        return redeem is not None
    except Exception:
        return False


__all__ = [
    "DEFAULT_LOYALTY_CONFIG",
    "KIND_CLIENTE_FIEL",
    "KIND_CROSS_SELL",
    "KIND_CUMPLE_CERCA",
    "KIND_PUNTOS_DORMIDOS",
    "KIND_VUELVE_PRONTO",
    "Suggestion",
    "redeemed_on_last_visit",
    "suggest_for_customer",
]