"""Multi-line pre-billing checklist.

Extends app/rms/sales/pre_sale_check.py with a CartLine dataclass
and a validate_cart_intent() function that runs the pre-sale checks
across a whole multi-line cart (e.g., a POS sale with 5 different
products).

Key design choices:
- Aggregates per-line checks; per-line warnings surface with the
  line_index so the UI can highlight the offending cart row.
- Sale-level checks (closed day, customer allergen, payment method)
  run once and apply to the whole cart.
- Stock shortages are aggregated per-ingredient across the cart
  (so if the same ingredient is used in 2 products, the shortage
  is reported once with the total demand).
- A cart-level blocker (e.g., closed day) blocks the entire sale,
  even if individual lines would have been clean.

The /ventas/nueva/multi flow (the cart in ventas.html) calls
POST /ventas/nueva/preflight/multi with a JSON body, gets the
aggregated checklist back, and either blocks submit or shows
yellow banners per line.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from app.rms.models.channels import Channel
from app.rms.sales.pre_sale_check import (
    PreSaleChecklist,
    PreSaleIntent,
    PreSaleWarning,
    validate_sale_intent,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class CartLine:
    """One line in a multi-line cart.

    line_index is the 0-based position in the cart; the checklist
    includes it on per-line warnings so the UI can highlight the
    right row.
    """

    line_index: int
    product_id: int
    qty: float
    discount_gs: int = 0
    unit_price_gs_override: int | None = None
    packaging_item_id: int | None = None
    packaging_qty: float | None = None


@dataclass(frozen=True)
class CartIntent:
    """The aggregated intent for a multi-line cart.

    Mirrors PreSaleIntent but with a list of CartLine instead of a
    single product. The cart-level fields (customer, payment, etc.)
    apply to all lines.
    """

    lines: tuple[CartLine, ...]
    customer_id: int | None = None
    payment_method: str = ""
    channel: str = Channel.MOSTRADOR.value
    sold_at: date | None = None
    points_to_redeem: int = 0

    @property
    def is_empty(self) -> bool:
        return len(self.lines) == 0

    @property
    def total_qty(self) -> float:
        return sum(line.qty for line in self.lines)


def validate_cart_intent(
    session: "Session",
    cart: CartIntent,
    *,
    today: date | None = None,
) -> PreSaleChecklist:
    """Run the pre-billing checklist on a multi-line cart.

    Strategy:
    1. Per-line checks (qty, product, recipe, stock, packaging) for
       each line — each produces a PreSaleWarning with line_index set
       in the code (e.g. "QTY_TOO_LARGE:3" for line 3).
    2. Aggregated stock check: walk all lines, sum demand per
       ingredient, compare to current stock. One warning per shortage.
    3. Cart-level checks (customer, payment, day-closed) — run once.
    """
    from datetime import datetime as _datetime
    from zoneinfo import ZoneInfo

    _ASUNCION = ZoneInfo("America/Asuncion")

    if today is None:
        today = _datetime.now(_ASUNCION).date()

    checklist = PreSaleChecklist()

    # ---- Cart-empty: blocker -----------------------------------------
    if cart.is_empty:
        _add_cart_empty_blocker(checklist)
        return checklist

    # ---- Per-line checks ---------------------------------------------
    _run_per_line_checks(session, cart, checklist, today)

    # ---- Aggregated stock check --------------------------------------
    _run_aggregated_stock_check(session, cart, checklist)

    # ---- Cart-level checks (run once) --------------------------------
    _run_cart_level_checks(session, cart, checklist)

    return checklist


def _add_cart_empty_blocker(checklist: PreSaleChecklist) -> None:
    """Add a CART_EMPTY blocker.

    Extracted from validate_cart_intent to reduce complexity.
    """
    checklist.blockers.append(
        PreSaleWarning(
            code="CART_EMPTY",
            severity="blocker",
            message="El carrito está vacío. Agregá al menos un producto.",
        )
    )


def _run_per_line_checks(
    session: "Session",
    cart: CartIntent,
    checklist: PreSaleChecklist,
    today: date,
) -> None:
    """Run per-line validation checks and append warnings/blockers.

    Extracted from validate_cart_intent to reduce complexity.
    """
    for line in cart.lines:
        intent = PreSaleIntent(
            product_id=line.product_id,
            sku="",
            qty=line.qty,
            discount_gs=line.discount_gs,
            customer_id=None,  # customer is cart-level, not per-line
            payment_method="",  # same
            channel=cart.channel,
            sold_at=cart.sold_at,
            unit_price_gs_override=line.unit_price_gs_override,
            packaging_item_id=line.packaging_item_id,
            packaging_qty=line.packaging_qty,
            points_to_redeem=cart.points_to_redeem,
        )
        per_line = validate_sale_intent(session, intent, today=today)
        for w in per_line.all_items:
            # Skip per-line info messages (we re-emit cart-level info)
            if w.severity == "info":
                continue
            suffixed = PreSaleWarning(
                code=f"{w.code}@{line.line_index}",
                severity=w.severity,
                message=f"Línea {line.line_index + 1}: {w.message}",
            )
            if w.is_blocker():
                checklist.blockers.append(suffixed)
            else:
                checklist.warnings.append(suffixed)


def _run_aggregated_stock_check(
    session: "Session",
    cart: CartIntent,
    checklist: PreSaleChecklist,
) -> None:
    """Walk all lines, sum demand per ingredient, compare to stock.

    Extracted from validate_cart_intent to reduce complexity.
    """
    from app.rms.models import Ingredient

    ingredient_demand, ingredient_names = _compute_cart_ingredient_demand(session, cart)
    shortages: list[tuple[str, float, float]] = []
    for ing_id, demand in ingredient_demand.items():
        ing = session.get(Ingredient, ing_id)
        if ing is None:
            continue
        projected = (ing.stock_qty or 0) - demand
        if projected < 0:
            shortages.append((ing.name, ing.stock_qty or 0, demand))
    if shortages:
        _add_stock_shortage_warning(checklist, shortages)


def _compute_cart_ingredient_demand(
    session: "Session",
    cart: CartIntent,
) -> tuple[dict[int, float], dict[int, str]]:
    """Compute total ingredient demand across all cart lines.

    Extracted from validate_cart_intent to reduce complexity.
    Returns (demand_by_ingredient, name_by_ingredient).
    """
    from app.rms.models import Ingredient, Product, Recipe
    from app.rms.sales.lifecycle import _compute_stock_moves

    ingredient_demand: dict[int, float] = defaultdict(float)
    ingredient_names: dict[int, str] = {}
    for line in cart.lines:
        product = session.get(Product, line.product_id)
        if product is None or product.recipe_id is None:
            continue
        recipe = session.get(Recipe, product.recipe_id)
        if recipe is None or recipe.yield_qty is None or recipe.yield_qty <= 0:
            continue
        try:
            moves = _compute_stock_moves(session, recipe, line.qty, set())
        except Exception:  # noqa: S112
            continue
        for _rid, ing_id, qty_delta in moves:
            ingredient_demand[ing_id] += abs(qty_delta)
            ing = session.get(Ingredient, ing_id)
            if ing is not None:
                ingredient_names[ing_id] = ing.name
    return ingredient_demand, ingredient_names


def _add_stock_shortage_warning(
    checklist: PreSaleChecklist,
    shortages: list[tuple[str, float, float]],
) -> None:
    """Add a CART_STOCK_SHORTAGE warning based on shortage list.

    Extracted from validate_cart_intent to reduce complexity.
    """
    severity = "blocker" if len(shortages) > 1 else "warning"
    names = ", ".join(s[0] for s in shortages[:3])
    more = f" (+{len(shortages) - 3} más)" if len(shortages) > 3 else ""
    checklist.warnings.append(
        PreSaleWarning(
            code="CART_STOCK_SHORTAGE",
            severity=severity,
            message=(
                f"Carrito: stock insuficiente para: {names}{more}. "
                f"Demanda total excede stock actual."
            ),
        )
    )


def _run_cart_level_checks(
    session: "Session",
    cart: CartIntent,
    checklist: PreSaleChecklist,
) -> None:
    """Run cart-level checks (allergen, day-closed, payment).

    Extracted from validate_cart_intent to reduce complexity.
    """
    _check_cart_customer_allergen(session, cart, checklist)
    _check_cart_day_closed(session, cart, checklist)
    _check_cart_payment_method(cart, checklist)


def _check_cart_customer_allergen(
    session: "Session",
    cart: CartIntent,
    checklist: PreSaleChecklist,
) -> None:
    """Check customer allergen against each product in the cart.

    Extracted from validate_cart_intent to reduce complexity.
    """
    from app.rms.derived_intel import check_customer_risk

    if cart.customer_id is None:
        return
    for line in cart.lines:
        risk = check_customer_risk(session, cart.customer_id, line.product_id)
        if not risk.safe:
            checklist.blockers.append(
                PreSaleWarning(
                    code=f"CART_CUSTOMER_ALLERGEN@{line.line_index}",
                    severity="blocker",
                    message=(
                        f"Línea {line.line_index + 1}: ⚠️ ALÉRGENO: "
                        f"{risk.matched}. El cliente es alérgico."
                    ),
                )
            )
            # One hit is enough to block the cart; no need to
            # check the other products.
            break


def _check_cart_day_closed(
    session: "Session",
    cart: CartIntent,
    checklist: PreSaleChecklist,
) -> None:
    """Check if the sold_at day is closed.

    Extracted from validate_cart_intent to reduce complexity.
    """
    from app.rms.eod_closed import eod_is_day_closed

    if cart.sold_at is None:
        return
    if eod_is_day_closed(session, cart.sold_at):
        checklist.blockers.append(
            PreSaleWarning(
                code="CART_DAY_CLOSED",
                severity="blocker",
                message=(
                    f"El día {cart.sold_at.isoformat()} está cerrado. "
                    f"Reabrilo desde /eod antes de registrar ventas."
                ),
            )
        )


def _check_cart_payment_method(
    cart: CartIntent,
    checklist: PreSaleChecklist,
) -> None:
    """Check if payment method is set; emit info warning if not.

    Extracted from validate_cart_intent to reduce complexity.
    """
    if not cart.payment_method:
        checklist.warnings.append(
            PreSaleWarning(
                code="CART_PAYMENT_METHOD_MISSING",
                severity="info",
                message="Sin forma de pago: la venta quedará como pendiente.",
            )
        )
