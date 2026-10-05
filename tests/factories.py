"""tests/factories.py — unique-by-construction test-data builders.

No factory_boy (AGENTS.md rule 1: no new deps). Plain functions with:

  1. Auto-unique names — every builder appends a short uuid suffix unless the
     caller passes an explicit name. Kills the UNIQUE-collision flake class
     (hit 3x in one session before this module existed).
  2. Session-first signature — `make_ingredient(s, ...)`; caller decides
     commit or flush.
  3. ``**kw`` passthrough for model columns, so tests can reach the 55
     Ingredient columns without the builder growing a parameter per column.
  4. Composable specs for recipe lines / pedido lines.

quick_seed() is reimplemented on top of these builders — one implementation,
two interfaces (see tests/_fixtures_quick_seed.py).
"""

from __future__ import annotations

import secrets
import uuid as _uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.rms.models import (
    Customer,
    DeliveryZone,
    Ingredient,
    IngredientPriceEvent,
    IngredientVariant,
    Pedido,
    PedidoLine,
    Product,
    ProductionCompletion,
    Recipe,
    RecipeLine,
    Sale,
    StockMovement,
    Supplier,
    Tag,
    TagLink,
    User,
    WasteLog,
)


def _uniq(prefix: str) -> str:
    return f"{prefix} {_uuid.uuid4().hex[:8]}"


def _now() -> datetime:
    return datetime.utcnow()


def gs(n) -> "Decimal":
    """Money helper (A4): Decimal-safe Gs. value per AGENTS.md money rules."""
    from decimal import Decimal

    return Decimal(str(n))


# ---------------------------------------------------------------------------
# Suppliers / customers
# ---------------------------------------------------------------------------


def make_supplier(s, *, name: str | None = None, **kw) -> Supplier:
    kw.setdefault("phone", "0981112222")
    sup = Supplier(name=name or _uniq("Proveedor"), **kw)
    s.add(sup)
    s.flush()
    return sup


def make_customer(s, *, name: str | None = None, allergens: str | None = None, **kw) -> Customer:
    kw.setdefault("phone", "0981112222")
    if allergens is not None:
        # Allergen guard reads Customer.notes via parse_customer_allergies
        # (app/rms/derived_intel.check_customer_risk) — there is no dedicated
        # allergen column. Free-text Spanish format: "alergia: gluten".
        kw.setdefault("notes", f"alergia: {allergens}")
    c = Customer(name=name or _uniq("Cliente"), **kw)
    s.add(c)
    s.flush()
    return c


# ---------------------------------------------------------------------------
# Ingredients
# ---------------------------------------------------------------------------


def make_ingredient(
    s,
    *,
    name: str | None = None,
    unit: str = "kg",
    stock_qty: float = 10.0,
    min_stock_qty: float = 1.0,
    purchase_price_gs: int = 3000,
    traits: list[str] | None = None,
    **kw,
) -> Ingredient:
    """Defaults mirror quick_seed's 'harina QA'. **kw passes any other column
    (allergens='gluten,lacteos', dietary_tags='sin tacc', shelf_life_days=30 …).
    traits: named presets (low_stock, near_expiry, allergen_heavy, packaging)."""
    for t in traits or []:
        if t not in _ING_TRAITS:
            raise ValueError(f"unknown trait {t!r}; known: {sorted(_ING_TRAITS)}")
        kw.update(_ING_TRAITS[t])  # trait overrides default param
    if "stock_qty" in kw:
        stock_qty = kw.pop("stock_qty")
    if "min_stock_qty" in kw:
        min_stock_qty = kw.pop("min_stock_qty")
    ing = Ingredient(
        name=name or _uniq("Ingrediente"),
        unit=unit,
        stock_qty=stock_qty,
        min_stock_qty=min_stock_qty,
        purchase_price_gs=purchase_price_gs,
        **kw,
    )
    s.add(ing)
    s.flush()
    return ing


_ING_TRAITS: dict = {
    "low_stock": {"stock_qty": 0.5, "min_stock_qty": 5.0},
    "near_expiry": {"shelf_life_days": 1},
    "allergen_heavy": {"allergens": "gluten,lacteos,huevos"},
    "packaging": {"is_packaging": True, "unit": "und"},
}


def make_ingredient_variant(
    s,
    ingredient: Ingredient,
    *,
    price_gs: int = 3500,
    package_size: float = 1.0,
    package_unit: str = "kg",
    preferred: bool = True,
    **kw,
) -> IngredientVariant:
    # NOTE: IngredientVariant has no `label` column — package identity is
    # (package_size, package_unit). `preferred` exists per variants.py.
    v = IngredientVariant(
        ingredient_id=ingredient.id,
        package_size=package_size,
        package_unit=package_unit,
        purchase_price_gs=price_gs,
        preferred=preferred,
        **kw,
    )
    s.add(v)
    s.flush()
    return v


def make_price_event(
    s,
    ingredient: Ingredient,
    *,
    price_gs: int = 3000,
    at: datetime | None = None,
    source: str = "manual",
) -> IngredientPriceEvent:
    # Auto-propagate supplier_id from the ingredient so the price-history
    # leaderboard has a complete attribution. Tests that need a different
    # supplier_id (cross-supplier test fixtures) override via kwargs.
    ev = IngredientPriceEvent(
        ingredient_id=ingredient.id,
        price_gs=price_gs,
        recorded_at=at or _now(),
        source=source,
        supplier_id=getattr(ingredient, "supplier_id", None),
    )
    s.add(ev)
    s.flush()
    return ev


def make_user(
    s,
    *,
    username: str | None = None,
    role: str = "operator",
    is_active: bool = True,
    password_hash: str | None = None,
    **kw,
) -> User:
    """Local-backend user (G3 groundwork: role param ready for authz matrix).
    password_hash None = unusable-by-password probe account."""
    from datetime import datetime
    from datetime import timezone as _tz

    u = User(
        username=username or _uniq("user"),
        role=role,
        is_active=is_active,
        password_hash=password_hash or "!",
        created_at=kw.pop("created_at", None) or datetime.now(_tz.utc),
        **kw,
    )
    s.add(u)
    s.flush()
    return u


def make_delivery_zone(
    s, *, name: str | None = None, code: str | None = None, **kw
) -> DeliveryZone:
    z = DeliveryZone(code=code or _uuid.uuid4().hex[:8].upper(), name=name or _uniq("Zona"), **kw)
    s.add(z)
    s.flush()
    return z


def make_waste_log(
    s,
    *,
    ingredient: Ingredient,
    qty: float = 0.5,
    reason: str = "vencida",
    at: datetime | None = None,
    **kw,
) -> WasteLog:
    w = WasteLog(
        ingredient_id=ingredient.id, qty=qty, reason=reason, recorded_at=at or _now(), **kw
    )
    s.add(w)
    s.flush()
    return w


def make_stock_move(
    s,
    *,
    ingredient: Ingredient,
    delta: float,
    movement_type: str = "adjustment",
    at: datetime | None = None,
    **kw,
) -> StockMovement:
    m = StockMovement(
        ingredient_id=ingredient.id,
        movement_type=movement_type,
        qty=delta,
        recorded_at=at or _now(),
        **kw,
    )
    s.add(m)
    s.flush()
    return m


def make_tag(s, *, name: str | None = None, kind: str = "dietary", **kw) -> Tag:
    t = Tag(name=name or _uniq("Tag"), kind=kind, **kw)
    s.add(t)
    s.flush()
    return t


def make_tag_link(
    s,
    *,
    tag: Tag,
    ingredient: Ingredient | None = None,
    recipe: Recipe | None = None,
    product: Product | None = None,
    **kw,
) -> TagLink:
    # TagLink is polymorphic: (target_kind, target_id) — not per-table FKs.
    if ingredient is not None:
        kind, tid = "ingredient", ingredient.id
    elif recipe is not None:
        kind, tid = "recipe", recipe.id
    elif product is not None:
        kind, tid = "product", product.id
    else:
        raise ValueError("pass one of ingredient=/recipe=/product=")
    ln = TagLink(tag_id=tag.id, target_kind=kind, target_id=tid, **kw)
    s.add(ln)
    s.flush()
    return ln


# ---------------------------------------------------------------------------
# Recipes (composable lines)
# ---------------------------------------------------------------------------


@dataclass
class ing_line:
    """Spec: an ingredient line in a recipe. Pass the Ingredient, not the id."""

    ingredient: Ingredient
    qty: float = 0.3
    unit: str = "kg"

    def resolve(self) -> dict[str, Any]:
        return {
            "line_kind": "ingredient",
            "line_ref_id": self.ingredient.id,
            "qty": self.qty,
            "line_unit": self.unit,
        }


@dataclass
class sub_line:
    """Spec: a sub-recipe line. Pass the sub Recipe."""

    recipe: Recipe
    qty: float = 1.0
    unit: str = "batch"

    def resolve(self) -> dict[str, Any]:
        return {
            "line_kind": "sub_recipe",
            "line_ref_id": self.recipe.id,
            "qty": self.qty,
            "line_unit": self.unit,
        }


def make_recipe(
    s,
    *,
    name: str | None = None,
    lines: list[ing_line | sub_line] | None = None,
    yield_qty: float = 12.0,
    yield_unit: str = "und",
    **kw,
) -> Recipe:
    rec = Recipe(
        name=name or _uniq("Receta"),
        yield_qty=yield_qty,
        yield_unit=yield_unit,
        **kw,
    )
    s.add(rec)
    s.flush()
    for spec in lines or []:
        s.add(RecipeLine(recipe_id=rec.id, **spec.resolve()))
    s.flush()
    return rec


def make_product(
    s,
    *,
    name: str | None = None,
    recipe: Recipe | None = None,
    recipe_id: int | None = None,
    sale_price_gs: int = 25000,
    **kw,
) -> Product:
    if recipe is None and recipe_id is not None:
        recipe = s.get(Recipe, recipe_id)
    p = Product(
        name=name or _uniq("Producto"),
        sale_price_gs=sale_price_gs,
        recipe_id=recipe.id if recipe else None,
        **kw,
    )
    s.add(p)
    s.flush()
    return p


# ---------------------------------------------------------------------------
# Composition sugar (A2): the 3-step preamble, one call
# ---------------------------------------------------------------------------


def make_catalog(
    s,
    *,
    price_gs: int = 25000,
    stock_qty: float = 100.0,
    line_qty: float = 0.3,
    ingredient_kwargs: dict | None = None,
) -> dict:
    """ingredient + recipe (1 line) + product wired together.

    Returns {"ingredient", "recipe", "product"}.
    """
    ing = make_ingredient(s, stock_qty=stock_qty, **(ingredient_kwargs or {}))
    rec = make_recipe(s, lines=[ing_line(ing, qty=line_qty)])
    prod = make_product(s, recipe=rec, sale_price_gs=price_gs)
    return {"ingredient": ing, "recipe": rec, "product": prod}


def make_sellable(s, *, price_gs: int = 25000, stock_qty: float = 100.0) -> Product:
    """A product backed by a stock-backed recipe — the POS-ready preamble."""
    return make_catalog(s, price_gs=price_gs, stock_qty=stock_qty)["product"]


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


def make_sale(
    s,
    *,
    product: Product,
    qty: float = 2.0,
    at: datetime | None = None,
    unit_price_gs: int | None = None,
    **kw,
) -> Sale:
    """Raw sale row (no stock movement). For a sale WITH stock application,
    use app.rms.costing.apply_sale — as quick_seed does."""
    sale = Sale(
        sold_at=at or _now(),
        product_id=product.id,
        qty=qty,
        unit_price_gs=unit_price_gs if unit_price_gs is not None else product.sale_price_gs,
        **kw,
    )
    s.add(sale)
    s.flush()
    return sale


def make_completion(
    s,
    *,
    product: Product,
    for_date: date,
    completed_qty: float = 0.0,
    status: str = "open",
    closure_notes: str | None = None,
    recorded_at: datetime | None = None,
) -> ProductionCompletion:
    """Create a ProductionCompletion row (PRODUCCION-V2 Fase 2)."""
    row = ProductionCompletion(
        product_id=product.id,
        for_date=for_date,
        completed_qty=completed_qty,
        recorded_at=recorded_at or _now(),
        status=status,
        closure_notes=closure_notes,
        updated_at=_now(),
    )
    s.add(row)
    s.flush()
    return row


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------


@dataclass
class pedido_item:
    product: Product
    qty: float = 2.0
    unit_price_gs: int | None = None

    def resolve(self) -> dict[str, Any]:
        return {
            "product_id": self.product.id,
            "qty": self.qty,
            "unit_price_gs": self.unit_price_gs
            if self.unit_price_gs is not None
            else self.product.sale_price_gs,
        }


def make_pedido(
    s,
    *,
    customer: Customer | None = None,
    items: list[pedido_item] | None = None,
    status: str = "pending",
    promised_date=None,
    promised_time: str | None = None,
    channel: str = "whatsapp",
    **kw,
) -> Pedido:
    """promised_date defaults to ASUNCION today — /produccion filters by
    Asunción local date and the old UTC-default seeding flaked near midnight."""
    if promised_date is None:
        from datetime import datetime as _dt

        promised_date = (
            _dt.utcnow().astimezone(__import__("zoneinfo").ZoneInfo("America/Asuncion")).date()
        )
    ped = Pedido(
        customer_id=customer.id if customer else None,
        customer_name=(
            customer.name if customer else kw.pop("customer_name", None) or _uniq("Cliente")
        ),
        customer_phone=kw.pop("customer_phone", getattr(customer, "phone", None)),
        promised_date=promised_date,
        promised_time=promised_time,
        channel=channel,
        status=status,
        payment_intent=kw.pop("payment_intent", "efectivo"),
        # Unique token — the unique index rejects duplicates when seeding N pedidos.
        public_token=kw.pop("public_token", None) or secrets.token_urlsafe(8)[:8],
        # P1-2: default expiry 30 days from now so /p/{token} works in tests.
        # Override with `public_token_expires_at=...` in kwargs for expiry tests.
        public_token_expires_at=kw.pop(
            "public_token_expires_at",
            datetime.utcnow() + timedelta(days=30),
        ),
        **kw,
    )
    s.add(ped)
    s.flush()
    for item in items or []:
        s.add(PedidoLine(pedido_id=ped.id, **item.resolve()))
    s.flush()
    return ped
