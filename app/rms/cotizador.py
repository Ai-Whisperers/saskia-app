"""app/rms/cotizador.py — Fase 3: cotizador de catering / pedidos grandes.

Dado un pedido {(product_id, qty_portions)} calcula:
- batches necesarios (ceil(qty / yield_qty) cuando hay receta)
- costo insumos por receta (recipe_batch_cost_gs)
- precio: el de carta (product.sale_price_gs × qty) es la base; el
  cotizador aplica descuento % por volumen y muestra margen
  resultante sobre costo. Sin receta costeable, margen = None.

Puro cálculo — NO escribe nada.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.rms.costing import recipe_batch_cost_gs


@dataclass
class QuoteItem:
    product_id: int
    product_name: str = ""
    qty: int = 0  # porciones/unidades pedidas
    portion_label: str = ""
    sale_price_gs: int = 0
    yield_qty: float | None = None
    batches: float | None = None
    unit_cost_gs: int | None = None
    line_cost_gs: int | None = None
    line_menu_gs: int = 0  # precio carta × qty
    missing: list[str] = field(default_factory=list)
    costable: bool = False

    @property
    def margin_gs(self) -> int | None:
        if self.line_cost_gs is None:
            return None
        return self.line_menu_gs - self.line_cost_gs


@dataclass
class Quote:
    items: list[QuoteItem] = field(default_factory=list)
    total_menu_gs: int = 0
    total_cost_gs: int | None = 0

    def apply_discount_pct(self, pct: float) -> int:
        """Total carta con descuento por volumen (redondeado a 100)."""
        total = round(self.total_menu_gs * (1 - pct / 100.0) / 100.0) * 100
        return max(total, 0)

    @property
    def total_margin_gs(self) -> int | None:
        if self.total_cost_gs is None:
            return None
        return self.total_menu_gs - self.total_cost_gs


def build_quote(session: Session, requested: list[tuple[int, int]]) -> Quote:
    """requested: lista de (product_id, qty). Ignora qty<=0 y faltantes."""
    from app.rms.models_legacy import Product, Recipe

    q = Quote()
    for product_id, qty in requested:
        if qty <= 0:
            continue
        product = session.get(Product, product_id)
        if product is None:
            continue
        it = _build_quote_item(session, product, qty)
        if it is None:
            continue
        q.items.append(it)
        _accumulate_totals(q, it)
    return q


def _build_quote_item(session, product, qty: int):
    """Build a single QuoteItem for a product.
    
    Extracted from build_quote to reduce complexity.
    Returns the QuoteItem or None if product is invalid.
    """
    from app.rms.models_legacy import Recipe

    it = QuoteItem(
        product_id=product.id,
        product_name=product.name,
        qty=int(qty),
        portion_label=product.portion_label,
        sale_price_gs=int(product.sale_price_gs),
    )
    it.line_menu_gs = it.sale_price_gs * it.qty
    if product.recipe_id:
        _populate_recipe_info(session, it, product.recipe_id)
    return it


def _populate_recipe_info(session, it: QuoteItem, recipe_id: int) -> None:
    """Populate recipe-related fields on a QuoteItem.
    
    Extracted from build_quote to reduce complexity.
    """
    from app.rms.models_legacy import Recipe

    recipe = session.get(Recipe, recipe_id)
    if recipe is None or not recipe.yield_qty:
        return
    it.yield_qty = float(recipe.yield_qty)
    it.batches = math.ceil(it.qty / it.yield_qty) if it.yield_qty > 0 else None
    if it.batches is not None:
        _populate_cost_info(session, it, recipe_id)


def _populate_cost_info(session, it: QuoteItem, recipe_id: int) -> None:
    """Populate cost-related fields on a QuoteItem.
    
    Extracted from build_quote to reduce complexity.
    """
    res = recipe_batch_cost_gs(session, recipe_id)
    if res.batch_cost_gs is not None:
        it.costable = True
        it.line_cost_gs = round(res.batch_cost_gs * it.batches)
        per_portion = res.batch_cost_gs / it.yield_qty if it.yield_qty else 0
        it.unit_cost_gs = round(per_portion)
    it.missing = list(res.missing_ingredient_names or [])


def _accumulate_totals(q: Quote, it: QuoteItem) -> None:
    """Accumulate totals from a QuoteItem into a Quote.
    
    Extracted from build_quote to reduce complexity.
    """
    q.total_menu_gs += it.line_menu_gs
    if it.line_cost_gs is None:
        q.total_cost_gs = None  # hay ítems no costeables
    elif q.total_cost_gs is not None:
        q.total_cost_gs += it.line_cost_gs


