"""Pre-sale validation service — the "pre-billing checklist".

Ported from ury-erp/ury (MIT-licensed). URY's posClosing.js runs a
pre-close validation that surfaces warnings (missing payment, stock
shortage, etc.) before allowing the user to confirm. Their pattern:
collect ALL warnings (not just the first), and let the user choose
to proceed or fix.

Sazon already has some pre-sale checks scattered:
- allergen guard (check_customer_risk in derived_intel.py)
- ingredient stock check (in _compute_stock_moves)
- recipe yield check (RecipeWithoutYield)
- closed-day gate (BACKLOG #15)
- idempotency reservation

The unified checklist below consolidates these into a single
function the /ventas/nueva form can call BEFORE the operator clicks
"Confirmar" — surfacing everything in one Spanish-language list.

API:
    validate_sale_intent(session, intent) -> PreSaleChecklist

PreSaleChecklist has:
    - warnings: list[PreSaleWarning]   # non-fatal, operator can override
    - blockers: list[PreSaleWarning]   # fatal, sale cannot proceed
    - is_clean: bool                   # no warnings, no blockers
    - blocking_messages: list[str]    # Spanish strings, ready for UI

The /ventas/nueva UI calls this on form change (debounced) and shows
a yellow banner for warnings, a red banner for blockers.

Why port this? URY's pattern is correct: catch everything at once,
not one error at a time. The operator doesn't want to fix the
customer-allergen, then re-submit, then learn about the stock
shortage, then re-submit, then learn about the closed day. One
sweep, one confirmation, all info in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from app.rms import config
from app.rms.models.channels import Channel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.rms.models import Product


# Batch B6 (2026-10-07): pre-sale thresholds are now operator-tunable
# via the SettingsKV registry (keys prefixed ``pre_sale.``). The
# module-level constants below are kept as backward-compat shims that
# alias DEFAULT_PRE_SALE_CONFIG.
DEFAULT_PRE_SALE_CONFIG: dict[str, int] = {
    "max_qty_per_sale": config.SAZON_PREFLIGHT_MAX_QTY_PER_SALE,
    "max_discount_pct": config.SAZON_PREFLIGHT_MAX_DISCOUNT_PCT,
    "low_stock_warn_pct": 25,
}

# Backward-compat module-level constants. Pre-existing tests import
# these by name; they now alias DEFAULT_PRE_SALE_CONFIG.
MAX_DISCOUNT_PCT_WITHOUT_OVERRIDE = DEFAULT_PRE_SALE_CONFIG["max_discount_pct"]
MAX_QTY_PER_SALE = DEFAULT_PRE_SALE_CONFIG["max_qty_per_sale"]
LOW_STOCK_WARN_THRESHOLD_PCT = DEFAULT_PRE_SALE_CONFIG["low_stock_warn_pct"]


@dataclass(frozen=True)
class PreSaleIntent:
    """The minimum data needed to validate a sale before it happens.

    Mirrors the Form() fields on /ventas/nueva but is service-layer
    (no FastAPI / no HTTP) so the same logic can be called from
    CSV import, API, and POS keyboard.
    """

    product_id: int | None
    sku: str
    qty: float
    discount_gs: int = 0
    customer_id: int | None = None
    payment_method: str = ""
    channel: str = Channel.MOSTRADOR.value
    sold_at: date | None = None  # None = now (operator wants to sell today)
    unit_price_gs_override: int | None = None
    packaging_item_id: int | None = None
    packaging_qty: float | None = None
    points_to_redeem: int = 0


@dataclass(frozen=True)
class PreSaleWarning:
    """One item in the pre-billing checklist.

    severity:
        "blocker" — sale cannot proceed (HTTP 422 if form)
        "warning" — operator can override (form shows yellow banner)
        "info"    — FYI only (form shows gray text)

    code:
        Machine-readable code (e.g. "CUSTOMER_ALLERGEN") so the UI
        can group/filter warnings and tests can assert on specific
        cases without substring-matching Spanish text.
    """

    code: str
    severity: str  # "blocker" | "warning" | "info"
    message: str  # Spanish, ready for operator

    def is_blocker(self) -> bool:
        return self.severity == "blocker"


@dataclass
class PreSaleChecklist:
    """Result of validate_sale_intent().

    A checklist is "clean" if it has no warnings and no blockers.
    "ready" means ready to submit (no blockers, even if warnings).
    """

    warnings: list[PreSaleWarning] = field(default_factory=list)
    blockers: list[PreSaleWarning] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.warnings and not self.blockers

    @property
    def is_ready(self) -> bool:
        return not self.blockers

    @property
    def all_items(self) -> list[PreSaleWarning]:
        return self.blockers + self.warnings

    @property
    def blocking_messages(self) -> list[str]:
        return [w.message for w in self.blockers]

    @property
    def warning_messages(self) -> list[str]:
        return [w.message for w in self.warnings]


def validate_sale_intent(
    session: "Session",
    intent: PreSaleIntent,
    *,
    today: date | None = None,
    pre_sale_cfg: dict[str, int] | None = None,
) -> PreSaleChecklist:
    """Run the pre-billing checklist on a sale intent.

    Args:
        session: SQLAlchemy session.
        intent: the parsed intent to validate.
        today: for testing — the "current" date. Defaults to today's
            date in Asunción (operator's local time). Override in tests.
        pre_sale_cfg: optional override dict (Batch B6, 2026-10-07).
            Partial dicts merge with DEFAULT_PRE_SALE_CONFIG.

    Returns:
        PreSaleChecklist with all warnings and blockers surfaced.
        Empty checklist = sale is safe to commit.
    """
    cfg = dict(DEFAULT_PRE_SALE_CONFIG)
    if pre_sale_cfg is not None:
        cfg.update(pre_sale_cfg)
    max_qty = cfg["max_qty_per_sale"]
    max_discount_pct = cfg["max_discount_pct"]

    from datetime import datetime as _datetime
    from zoneinfo import ZoneInfo

    _ASUNCION = ZoneInfo("America/Asuncion")

    from app.rms.derived_intel import check_customer_risk
    from app.rms.models import Product

    if today is None:
        today = _datetime.now(_ASUNCION).date()

    checklist = PreSaleChecklist()

    # ---- Floor checks (blocker) ---------------------------------------
    if intent.qty <= 0:
        checklist.blockers.append(
            PreSaleWarning(
                code="QTY_NOT_POSITIVE",
                severity="blocker",
                message=f"La cantidad debe ser mayor a 0 (recibido: {intent.qty}).",
            )
        )
        return checklist  # Nothing else makes sense without a qty

    if intent.qty > max_qty:
        checklist.blockers.append(
            PreSaleWarning(
                code="QTY_TOO_LARGE",
                severity="blocker",
                message=(
                    f"Cantidad {intent.qty} excede el máximo por venta "
                    f"({max_qty}). Verificá el número."
                ),
            )
        )

    # ---- Product resolution (blocker if no product) -------------------
    product: Product | None = None
    if intent.product_id:
        product = session.get(Product, intent.product_id)
    elif intent.sku:
        from app.integrations.barcode import get_product_by_sku

        result = get_product_by_sku(session, intent.sku)
        if result.ok and result.product is not None:
            product = result.product

    if product is None:
        checklist.blockers.append(
            PreSaleWarning(
                code="PRODUCT_NOT_FOUND",
                severity="blocker",
                message=(
                    f"No se encontró el producto (id={intent.product_id}, "
                    f"sku='{intent.sku}'). Verificá el código o seleccioná de la lista."
                ),
            )
        )
        return checklist  # Everything else needs the product

    # ---- Customer allergen check (blocker) -----------------------------
    if intent.customer_id is not None:
        risk = check_customer_risk(session, intent.customer_id, product.id)
        if not risk.safe:
            checklist.blockers.append(
                PreSaleWarning(
                    code="CUSTOMER_ALLERGEN",
                    severity="blocker",
                    message=(
                        f"⚠️ ALÉRGENO: {risk.matched}. El cliente es alérgico. "
                        f"Confirmá con el cliente antes de vender."
                    ),
                )
            )

    # ---- Discount check (warning) --------------------------------------
    unit_price = intent.unit_price_gs_override or product.sale_price_gs
    line_total = Decimal(str(intent.qty)) * Decimal(str(unit_price))
    if line_total > 0 and intent.discount_gs > 0:
        discount_pct = (Decimal(str(intent.discount_gs)) / line_total) * 100
        if discount_pct > max_discount_pct:
            checklist.warnings.append(
                PreSaleWarning(
                    code="LARGE_DISCOUNT",
                    severity="warning",
                    message=(
                        f"Descuento del {discount_pct:.1f}% "
                        f"(Gs. {intent.discount_gs:,}). Pasó el umbral del "
                        f"{max_discount_pct}%. ¿Aplicar igual?"
                    ),
                )
            )

    # ---- Recipe / stock check (warning or blocker) ---------------------
    if product.recipe_id is None:
        # No recipe = no stock tracking. Warning, not blocker.
        checklist.warnings.append(
            PreSaleWarning(
                code="NO_RECIPE",
                severity="warning",
                message=(
                    f"El producto '{product.name}' no tiene receta. "
                    f"No se descontará stock automáticamente."
                ),
            )
        )
    else:
        # Walk recipe tree, check stock.
        # We reuse _compute_stock_moves from sales/lifecycle.py to know
        # the exact ingredient deltas this sale would create. If any
        # ingredient goes below 0, it's a warning (operator can override
        # for a hand-wave "use it anyway" — Sazon currently does allow
        # negative stock).
        from app.rms.models import Recipe
        from app.rms.sales.lifecycle import _compute_stock_moves

        recipe = session.get(Recipe, product.recipe_id)
        if recipe is None:
            checklist.warnings.append(
                PreSaleWarning(
                    code="RECIPE_MISSING",
                    severity="warning",
                    message=(
                        f"La receta del producto '{product.name}' no se encontró. "
                        f"Venta sin control de stock."
                    ),
                )
            )
        elif recipe.yield_qty is None or recipe.yield_qty <= 0:
            checklist.blockers.append(
                PreSaleWarning(
                    code="RECIPE_NO_YIELD",
                    severity="blocker",
                    message=(
                        f"La receta '{recipe.name}' no tiene rendimiento definido. "
                        f"Cargá el rendimiento antes de vender."
                    ),
                )
            )
        else:
            try:
                moves = _compute_stock_moves(session, recipe, intent.qty, set())
            except Exception as e:  # CycleInRecipeTree
                checklist.warnings.append(
                    PreSaleWarning(
                        code="RECIPE_CYCLE",
                        severity="warning",
                        message=(
                            f"La receta '{recipe.name}' tiene un ciclo. "
                            f"Venta sin control de stock. ({e})"
                        ),
                    )
                )
                moves = []

            from app.rms.models import Ingredient

            shortages: list[tuple[str, float, float]] = []
            for _affected_recipe_id, ingredient_id, qty_delta in moves:
                ing = session.get(Ingredient, ingredient_id)
                if ing is None:
                    continue
                projected_stock = (ing.stock_qty or 0) - abs(qty_delta)
                if projected_stock < 0:
                    shortages.append((ing.name, ing.stock_qty or 0, abs(qty_delta)))
            if shortages:
                # Multiple shortages = blocker (operator must fix stock first)
                # Single = warning (may be acceptable for a known quick-sell)
                severity = "blocker" if len(shortages) > 1 else "warning"
                names = ", ".join(s[0] for s in shortages[:3])
                checklist.warnings.append(
                    PreSaleWarning(
                        code="STOCK_SHORTAGE",
                        severity=severity,
                        message=(
                            f"Stock insuficiente para: {names}. Venta dejaría stock negativo."
                        ),
                    )
                )

    # ---- Packaging consistency (blocker) --------------------------------
    if intent.packaging_item_id is not None and intent.packaging_qty is None:
        checklist.blockers.append(
            PreSaleWarning(
                code="PACKAGING_QTY_MISSING",
                severity="blocker",
                message="Falta la cantidad de empaque (packaging_qty).",
            )
        )
    elif (
        intent.packaging_item_id is None
        and intent.packaging_qty is not None
        and intent.packaging_qty > 0
    ):
        checklist.blockers.append(
            PreSaleWarning(
                code="PACKAGING_ITEM_MISSING",
                severity="blocker",
                message="Falta el ingrediente de empaque (packaging_item_id).",
            )
        )

    # ---- Closed-day check (blocker) ------------------------------------
    from app.rms.eod_closed import eod_is_day_closed

    sold_at = intent.sold_at or today
    if eod_is_day_closed(session, sold_at):
        checklist.blockers.append(
            PreSaleWarning(
                code="DAY_CLOSED",
                severity="blocker",
                message=(
                    f"El día {sold_at.isoformat()} está cerrado. "
                    f"Reabrilo desde /eod antes de registrar ventas."
                ),
            )
        )

    # ---- Payment method (info only — sale can still be created) --------
    if not intent.payment_method:
        checklist.warnings.append(
            PreSaleWarning(
                code="PAYMENT_METHOD_MISSING",
                severity="info",
                message="Sin forma de pago: la venta quedará como pendiente.",
            )
        )

    return checklist
