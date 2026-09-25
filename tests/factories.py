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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.rms.models import (
    Customer,
    Ingredient,
    Pedido,
    PedidoLine,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    Supplier,
)


def _uniq(prefix: str) -> str:
    return f"{prefix} {_uuid.uuid4().hex[:8]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    **kw,
) -> Ingredient:
    """Defaults mirror quick_seed's 'harina QA'. **kw passes any other column
    (allergens='gluten,lacteos', dietary_tags='sin tacc', shelf_life_days=30 …)."""
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
    sale_price_gs: int = 25000,
    **kw,
) -> Product:
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

        promised_date = _dt.now(timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo("America/Asuncion")
        ).date()
    ped = Pedido(
        customer_id=customer.id if customer else None,
        customer_name=(customer.name if customer else kw.pop("customer_name", None) or _uniq("Cliente")),
        customer_phone=kw.pop("customer_phone", getattr(customer, "phone", None)),
        promised_date=promised_date,
        promised_time=promised_time,
        channel=channel,
        status=status,
        payment_intent=kw.pop("payment_intent", "efectivo"),
        # Unique token — the unique index rejects duplicates when seeding N pedidos.
        public_token=kw.pop("public_token", None) or secrets.token_urlsafe(8)[:8],
        **kw,
    )
    s.add(ped)
    s.flush()
    for item in items or []:
        s.add(PedidoLine(pedido_id=ped.id, **item.resolve()))
    s.flush()
    return ped
