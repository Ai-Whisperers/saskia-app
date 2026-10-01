"""app/rms/loyalty_suggestions.py — Decision C (Phase 4, 2026-10-01).

Auto-suggest rules engine for the POS customer card. Pure functions
that take a Customer + their sale history and return up to 3 actionable
suggestions to surface at the till:

  - "vuelve_pronto" — customer hasn't visited in N days; suggest
    a small discount to bring them back (LAPSED rule).
  - "cumple_cerca" — birthday within 7 days; suggest a freebie or
    small discount (BIRTHDAY rule).
  - "puntos_dormidos" — customer has ≥50 points but didn't redeem
    on the last visit; nudge a redeem (POINTS-DORMANT rule).
  - "cliente_fiel" — top-tier customer; small recognition text
    only (NO discount to avoid margin erosion on big spenders)
    (VIP rule).
  - "cross_sell" — customer has `sin gluten` (or other) dietary
    restriction; surface the top-selling sin-gluten product as a
    cross-sell (CROSS-SELL rule).

Design rules:
  - Suggestions NEVER bypass the cashier. They pre-fill the existing
    ``discount_gs`` field with a suggested amount; cashier confirms
    or ignores.
  - Maximum 3 returned per call (UI space constraint).
  - Priority order: cumpleaños → vuelve pronto → puntos dormidos →
    cross-sell → cliente fiel. Highest-priority suggestions win ties.
  - All thresholds live as module-level constants so Saskia can tune
    later (no DB-driven rules — that's C2/C3 territory).
  - Pure function: takes a Customer + sales-derived stats; no DB
    queries inside. Caller wires the data.

This module does NOT do I/O or import FastAPI. The router stitches
the inputs and includes the result in the customer detail payload
(``/clientes/api/{id}``).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.rms.models_legacy import Customer


# ──────────────────────────────────────────────────────────────────────
# Tunable thresholds
# ──────────────────────────────────────────────────────────────────────

# LAPSED thresholds by tier (days without a visit). Bronze = the
# default; silver/gold earn longer patience because they visit often.
LAPSED_DAYS_BRONZE = 21
LAPSED_DAYS_SILVER = 30
LAPSED_DAYS_GOLD = 45

# LAPSED discount percent by tier. Higher tiers get less because
# they were already loyal — we don't want to discount away margin
# on people who would have come back anyway.
LAPSED_DISCOUNT_PCT_BRONZE = 10
LAPSED_DISCOUNT_PCT_SILVER = 7
LAPSED_DISCOUNT_PCT_GOLD = 5

# BIRTHDAY window: how many days before the birthday to start showing.
BIRTHDAY_WINDOW_DAYS = 7
BIRTHDAY_DISCOUNT_PCT = 15

# POINTS-DORMANT threshold. "Dormant" means they didn't redeem on
# their last visit AND they have enough to make a meaningful dent
# on a coffee-and-chipita purchase (~50k Gs. ≈ 50 pts).
POINTS_DORMANT_THRESHOLD = 50

# CROSS-SELL min products sold to be considered "popular enough to
# recommend" (avoid suggesting one-time flukes).
CROSS_SELL_MIN_SALES = 3

# How many suggestions to return. UI card space is limited.
MAX_SUGGESTIONS = 3


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
) -> list[Suggestion]:
    """Return up to MAX_SUGGESTIONS suggestions for this customer.

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

    Returns:
      List of Suggestion objects, sorted by priority then by kind
      (stable). Empty list when no rule fires.
    """
    if today is None:
        today = _dt.date.today()

    out: list[Suggestion] = []

    # Rule: cumpleaños dentro de 7 días (BIRTHDAY)
    birthday_sugg = _maybe_birthday(customer.birthday, today=today)
    if birthday_sugg is not None:
        out.append(birthday_sugg)

    # Rule: cliente que no viene hace N días (LAPSED)
    lapsed_sugg = _maybe_lapsed(
        last_sale_at=last_sale_at,
        tier=tier,
        today=today,
    )
    if lapsed_sugg is not None:
        out.append(lapsed_sugg)

    # Rule: ≥50 puntos y no canjeó la última vez (POINTS-DORMANT)
    dormant_sugg = _maybe_points_dormant(
        loyalty_points=customer.loyalty_points,
        n_sales=n_sales,
        redeemed_on_last_visit=redeemed_on_last_visit,
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
    return out[:MAX_SUGGESTIONS]


def _maybe_birthday(
    birthday_str: Optional[str],
    *,
    today: _dt.date,
) -> Optional[Suggestion]:
    """Cumpleaños dentro de la ventana (default 7 días).

    Soporta dos formatos almacenados en ``customer.birthday``:
      - "MM-DD" — cumpleaños sin año (caso normal, recurrente).
      - "YYYY-MM-DD" — cumpleaños con año (cuando Saskia lo conoce).
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
    if days_until < 0 or days_until > BIRTHDAY_WINDOW_DAYS:
        return None

    if days_until == 0:
        body = "¡Es su cumpleaños hoy! Ofrecerle un 15% de descuento."
    else:
        body = (
            f"Cumple en {days_until} día{'s' if days_until != 1 else ''}. "
            f"Ofrecerle un 15% de descuento en su próxima compra."
        )
    return Suggestion(
        kind=KIND_CUMPLE_CERCA,
        title="🎂 Cumple cerca",
        body=body,
        priority=10,  # highest
        discount_pct=BIRTHDAY_DISCOUNT_PCT,
    )


def _candidate_recurring_birthday(
    month: int, day: int, today: _dt.date
) -> _dt.date:
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
) -> Optional[Suggestion]:
    """Customer hasn't visited in N days (where N depends on tier)."""
    if last_sale_at is None:
        # Never visited — that's a "prospect", not a lapsed customer.
        # Defer to the POS team to ask for marketing_consent instead.
        return None

    if tier == "GOLD":
        threshold = LAPSED_DAYS_GOLD
        pct = LAPSED_DISCOUNT_PCT_GOLD
    elif tier == "SILVER":
        threshold = LAPSED_DAYS_SILVER
        pct = LAPSED_DISCOUNT_PCT_SILVER
    else:
        threshold = LAPSED_DAYS_BRONZE
        pct = LAPSED_DISCOUNT_PCT_BRONZE

    last_visit_date = last_sale_at.date() if isinstance(last_sale_at, _dt.datetime) else last_sale_at
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
) -> Optional[Suggestion]:
    """Customer has ≥POINTS_DORMANT_THRESHOLD and didn't redeem on last visit."""
    if redeemed_on_last_visit:
        # Already redeeming — no need to nudge.
        return None
    if loyalty_points < POINTS_DORMANT_THRESHOLD:
        return None
    if n_sales == 0:
        # Brand-new customer with manually-credited points? Nudge anyway.
        pass

    discount_gs = loyalty_points * 1000
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
