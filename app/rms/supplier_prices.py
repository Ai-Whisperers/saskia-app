"""app/rms/supplier_prices.py — supplier price comparison engine (P1-B9).

Saskia buys from multiple suppliers per ingredient, but the price column in
/inventario only shows the *current* supplier's price. To answer "is
Proveedor B actually cheaper than Proveedor A for harina?", we need a side-by-
side comparison per ingredient.

The actual schema (post-S7 Decision A1) stores per-supplier prices on
``IngredientVariant``: ``supplier_id`` + ``purchase_price_gs`` per row. One
Ingredient can have many IngredientVariants (different package sizes / different
suppliers). The legacy ``IngredientPriceEvent`` model only carries an
ingredient-level price history with NO supplier_id, so it cannot answer "who
charges what".

This module exposes a single helper ``get_price_comparison(session, supplier_id=...)``
that:

  1. Reads every ``IngredientVariant`` (and falls back to ``Ingredient.purchase_price_gs``
     when no variants exist) for ingredients whose variants reference real suppliers.
  2. Groups the rows by ingredient.
  3. Sorts suppliers within each ingredient by price ASC.
  4. Computes the delta vs the cheapest supplier (and the savings per unit if
     she switched to the cheapest).
  5. Returns a list of dicts ready to be consumed by the Jinja template.

If ``supplier_id`` is passed, the returned data is filtered to ingredients where
that supplier appears — so the route can answer "is *my* supplier overpriced?".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, IngredientVariant, Supplier


# Default fallback when an Ingredient has no variants but does have a
# supplier_id + purchase_price_gs set directly on the parent row.
@dataclass
class _PriceRow:
    """Internal normalized row — one supplier's price for one ingredient."""

    ingredient_id: int
    ingredient_name: str
    unit: str
    supplier_id: int
    supplier_name: str
    price_gs: int


@dataclass
class _SupplierPrice:
    """One supplier's price entry inside a comparison group."""

    supplier_id: int
    supplier_name: str
    price_gs: int
    # Set by get_price_comparison() — never written by callers directly.
    delta_gs: int = 0
    delta_pct: float = 0.0
    is_cheapest: bool = False


@dataclass
class PriceComparisonGroup:
    """One ingredient's full supplier comparison."""

    ingredient_id: int
    ingredient_name: str
    unit: str
    suppliers: list[_SupplierPrice] = field(default_factory=list)
    savings_gs_per_unit: int = 0
    avg_price_gs: int = 0

    @property
    def name(self) -> str:
        """Aliased for template ``fmt.entity_name(...)`` which reads ``.name``."""
        return self.ingredient_name


def _rows_for(session: Session) -> list[_PriceRow]:
    """Pull every (ingredient, supplier, price) tuple from the DB.

    Primary source: ``IngredientVariant`` — each row already carries its own
    supplier_id and purchase_price_gs. Fallback: an Ingredient with no variants
    but a parent-level supplier_id + purchase_price_gs counts as a single
    "implicit" variant.
    """
    rows: list[_PriceRow] = []

    # Variants — the rich source.
    variant_rows = session.execute(
        select(
            Ingredient.id,
            Ingredient.name,
            Ingredient.unit,
            IngredientVariant.supplier_id,
            IngredientVariant.purchase_price_gs,
        )
        .join(IngredientVariant, IngredientVariant.ingredient_id == Ingredient.id)
        .where(IngredientVariant.supplier_id.is_not(None))
        .where(IngredientVariant.purchase_price_gs.is_not(None))
        .order_by(Ingredient.id, IngredientVariant.purchase_price_gs.asc())
    ).all()

    supplier_ids = {r[3] for r in variant_rows if r[3] is not None}
    suppliers_by_id: dict[int, str] = {}
    if supplier_ids:
        for sup_id, sup_name in session.execute(
            select(Supplier.id, Supplier.name).where(Supplier.id.in_(supplier_ids))
        ).all():
            suppliers_by_id[sup_id] = sup_name

    for ing_id, ing_name, ing_unit, sup_id, price in variant_rows:
        if sup_id is None or price is None:
            continue
        sup_name = suppliers_by_id.get(sup_id)
        if sup_name is None:
            # FK guarantees this, but defensive.
            continue
        rows.append(
            _PriceRow(
                ingredient_id=ing_id,
                ingredient_name=ing_name,
                unit=ing_unit,
                supplier_id=sup_id,
                supplier_name=sup_name,
                price_gs=int(price),
            )
        )

    # Fallback — ingredients with no variants but parent-level supplier_id +
    # purchase_price_gs. We only include these when no variant exists for that
    # ingredient, so we don't double-count.
    variant_ingredient_ids = {r[0] for r in variant_rows}
    fallback_rows = session.execute(
        select(
            Ingredient.id,
            Ingredient.name,
            Ingredient.unit,
            Ingredient.supplier_id,
            Ingredient.purchase_price_gs,
        )
        .where(Ingredient.supplier_id.is_not(None))
        .where(Ingredient.purchase_price_gs.is_not(None))
        .where(~Ingredient.id.in_(variant_ingredient_ids) if variant_ingredient_ids else True)
        .order_by(Ingredient.id)
    ).all()

    fallback_supplier_ids = {r[3] for r in fallback_rows if r[3] is not None}
    fallback_suppliers: dict[int, str] = {}
    if fallback_supplier_ids:
        # Only fetch ones we don't already have.
        new_ids = fallback_supplier_ids - set(suppliers_by_id.keys())
        if new_ids:
            for sup_id, sup_name in session.execute(
                select(Supplier.id, Supplier.name).where(Supplier.id.in_(new_ids))
            ).all():
                fallback_suppliers[sup_id] = sup_name
        for sid, sname in suppliers_by_id.items():
            fallback_suppliers.setdefault(sid, sname)

    for ing_id, ing_name, ing_unit, sup_id, price in fallback_rows:
        if sup_id is None or price is None:
            continue
        sup_name = fallback_suppliers.get(sup_id)
        if sup_name is None:
            continue
        rows.append(
            _PriceRow(
                ingredient_id=ing_id,
                ingredient_name=ing_name,
                unit=ing_unit,
                supplier_id=sup_id,
                supplier_name=sup_name,
                price_gs=int(price),
            )
        )

    return rows


def get_price_comparison(
    session: Session,
    *,
    supplier_id: Optional[int] = None,
) -> list[PriceComparisonGroup]:
    """Build a per-ingredient comparison of supplier prices.

    Args:
        session: SQLAlchemy session.
        supplier_id: When provided, only ingredients where this supplier
            appears are returned (used by /suppliers/{id}/precios to show
            "what does this supplier charge vs. everyone else?").

    Returns:
        A list of ``PriceComparisonGroup``, sorted by ingredient name. Each
        group's ``suppliers`` list is sorted by price ASC (cheapest first).
        ``savings_gs_per_unit`` is the spread between the cheapest and most
        expensive supplier for that ingredient (0 when only one supplier).
    """
    rows = _rows_for(session)

    # Group by ingredient.
    groups: dict[int, PriceComparisonGroup] = {}
    for r in rows:
        if supplier_id is not None and r.supplier_id != supplier_id:
            # We still need to know about other suppliers for the SAME ingredient
            # (to compute delta). Don't drop the row — let the post-filter handle it.
            pass
        if r.ingredient_id not in groups:
            groups[r.ingredient_id] = PriceComparisonGroup(
                ingredient_id=r.ingredient_id,
                ingredient_name=r.ingredient_name,
                unit=r.unit,
            )
        groups[r.ingredient_id].suppliers.append(
            _SupplierPrice(
                supplier_id=r.supplier_id,
                supplier_name=r.supplier_name,
                price_gs=r.price_gs,
            )
        )

    # Compute deltas + sort + filter to the requested supplier's ingredients.
    result: list[PriceComparisonGroup] = []
    for ing_id, g in groups.items():
        # De-dup by supplier — if the same supplier appears twice for one
        # ingredient (multiple package variants), keep the cheapest entry.
        by_supplier: dict[int, _SupplierPrice] = {}
        for sp in g.suppliers:
            if sp.supplier_id not in by_supplier or sp.price_gs < by_supplier[sp.supplier_id].price_gs:
                by_supplier[sp.supplier_id] = sp
        unique_suppliers = list(by_supplier.values())
        unique_suppliers.sort(key=lambda s: s.price_gs)
        g.suppliers = unique_suppliers

        if len(g.suppliers) > 1:
            prices = [s.price_gs for s in g.suppliers]
            cheapest = min(prices)
            most_expensive = max(prices)
            for s in g.suppliers:
                s.delta_gs = s.price_gs - cheapest
                s.delta_pct = (
                    round((s.price_gs - cheapest) / cheapest * 100, 1)
                    if cheapest > 0
                    else 0.0
                )
                s.is_cheapest = s.price_gs == cheapest
            g.savings_gs_per_unit = most_expensive - cheapest
            g.avg_price_gs = sum(prices) // len(prices)
        elif g.suppliers:
            g.suppliers[0].delta_gs = 0
            g.suppliers[0].delta_pct = 0.0
            g.suppliers[0].is_cheapest = True
            g.savings_gs_per_unit = 0
            g.avg_price_gs = g.suppliers[0].price_gs

        # Supplier filter — keep only ingredients where the selected supplier
        # actually appears.
        if supplier_id is not None:
            if not any(s.supplier_id == supplier_id for s in g.suppliers):
                continue

        result.append(g)

    result.sort(key=lambda g: g.ingredient_name)
    return result


def total_potential_savings(comparison: list[PriceComparisonGroup]) -> int:
    """Sum of per-unit savings across all multi-supplier ingredients.

    Single-supplier ingredients contribute 0 (no savings possible). The route
    multiplies this by a heuristic monthly consumption estimate to produce the
    user-facing "Gs. X / mes" figure.
    """
    return sum(g.savings_gs_per_unit for g in comparison if len(g.suppliers) > 1)


__all__ = [
    "PriceComparisonGroup",
    "get_price_comparison",
    "total_potential_savings",
]