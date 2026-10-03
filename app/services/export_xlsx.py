"""app/services/export_xlsx.py — SQLite → .xlsx (HEREBUS format).

Per dev plan §9 Task 6 + v2 §6 (Excel export).

Writes a symmetric mirror of import_xlsx: same 6 sheets, same column order.
Roundtrip-safe: import(export(X)) ≡ X for non-derived state.

Money discipline: integer Gs. values written via the canonical format
(Gs. 1.234.567) so the resulting file is human-readable in Excel.

What we DON'T write here:
- StockMoves (derived; see import_xlsx note on why we ignore them on read)
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ
from app.rms.models import Customer, Ingredient, Product, Recipe, Sale
from app.rms.money import format_gs

# Sheet column definitions — single source of truth for import + export.
INGREDIENTES_COLS = [
    "id",
    "name [REQUIRED]",
    "unit [REQUIRED]",
    "stock_qty [OPTIONAL]",
    "purchase_price_gs [OPTIONAL]",
    "min_stock_qty [OPTIONAL]",
    "notes [OPTIONAL]",
]
RECETAS_COLS = [
    "id",
    "name [REQUIRED]",
    "yield_qty [OPTIONAL]",
    "yield_unit [OPTIONAL]",
    "notes [OPTIONAL]",
]
LINEAS_COLS = [
    "id",
    "recipe_id [REQUIRED]",
    "recipe_name [REQUIRED]",
    "line_kind [REQUIRED]",
    "line_ref_id [REQUIRED]",
    "target_name [REQUIRED]",
    "qty [REQUIRED]",
    "notes [OPTIONAL]",
]
PRODUCTOS_COLS = [
    "id",
    "name [REQUIRED]",
    "portion_label [OPTIONAL]",
    "sale_price_gs [REQUIRED]",
    "recipe_id [OPTIONAL]",
    "recipe_name [OPTIONAL]",
    "notes [OPTIONAL]",
]
CLIENTES_COLS = [
    "id",
    "telefono [REQUIRED]",
    "nombre [REQUIRED]",
    "email [OPTIONAL]",
    "cedula [OPTIONAL]",
    "notes [OPTIONAL]",
]
VENTAS_COLS = [
    "id",
    "sold_at [REQUIRED]",
    "product_id [REQUIRED]",
    "product_name [REQUIRED]",
    "qty [REQUIRED]",
    "unit_price_gs [REQUIRED]",
    "notes [OPTIONAL]",
    "voided_at [OPTIONAL]",
]
STOCKMOVES_COLS = [
    "id",
    "sale_id",
    "affected_recipe_id",
    "ingredient_id",
    "qty_delta",
]


def _write_header(ws: object, cols: list[str]) -> None:
    for i, col in enumerate(cols, start=1):
        ws.cell(row=1, column=i, value=col)


def _money_cell(value: int | None) -> str | None:
    """Format integer Gs. for export. None stays None (Excel sees empty)."""
    if value is None:
        return None
    return format_gs(value)


def _autosize(ws: object, max_width: int = 40) -> None:
    """Set column widths from content. Capped at max_width."""
    for col_idx in range(1, ws.max_column + 1):
        max_len = 0
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=True):
            for cell in row:
                if cell is None:
                    continue
                s = str(cell)
                if len(s) > max_len:
                    max_len = len(s)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, max_width)


def _resolve_export_range(
    period: str | None, today: date | None = None
) -> tuple[datetime | None, datetime | None]:
    """Map an export period preset to (start_utc, end_utc) for Sale.sold_at.

    Returns ``(None, None)`` for no filter. Both bounds are UTC-naive
    (matching how Sale.sold_at is stored). The caller applies them as
    half-open interval filters: ``Sale.sold_at >= start`` and
    ``Sale.sold_at <= end``.
    """
    if period in (None, "", "all", "full"):
        return None, None
    today = today or date.today()
    if period == "today":
        local_start = datetime.combine(today, time.min)
        local_end = datetime.combine(today, time.max)
    elif period == "30d":
        local_start = datetime.combine(today - timedelta(days=29), time.min)
        local_end = datetime.combine(today, time.max)
    elif period == "current_month":
        first = today.replace(day=1)
        local_start = datetime.combine(first, time.min)
        local_end = datetime.combine(today, time.max)
    elif period == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        local_start = datetime.combine(last_prev.replace(day=1), time.min)
        local_end = datetime.combine(last_prev, time.max)
    else:
        raise ValueError(f"unknown export period: {period!r}")

    # Convert Asunción local → UTC-naive
    start_utc = (
        local_start.replace(tzinfo=ASUNCION_TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    end_utc = (
        local_end.replace(tzinfo=ASUNCION_TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    return start_utc, end_utc


def to_file(
    session: Session,
    path: str | Path,
    period: str | None = None,
    today: date | None = None,
) -> Path:
    """Export current DB state to a HEREBUS-format .xlsx.

    ``period`` controls whether the Ventas + StockMoves sheets are filtered
    to a date range:

    - ``None`` or ``"all"`` — full history (default, same as before).
    - ``"current_month"`` — sales in the current month.
    - ``"last_month"`` — sales in the previous calendar month.
    - ``"30d"`` — last 30 days rolling.
    - ``"today"`` — today only (Asunción local).

    Non-sales sheets (Ingredientes, Recetas, Productos, Clientes) are
    always full state — close-out at month-end needs the catalog, not just
    the month's movements.

    Returns the absolute Path of the written file.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sale_start, sale_end = _resolve_export_range(period, today=today)

    wb = Workbook()
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    # --- Ingredientes ---
    ws = wb.create_sheet("Ingredientes")
    _write_header(ws, INGREDIENTES_COLS)
    for ing in session.scalars(select(Ingredient).order_by(Ingredient.id)).all():
        ws.append(
            [
                ing.id,
                ing.name,
                ing.unit,
                ing.stock_qty,
                _money_cell(ing.purchase_price_gs),
                ing.min_stock_qty,
                ing.notes,
            ]
        )
    _autosize(ws)

    # --- Recetas ---
    ws = wb.create_sheet("Recetas")
    _write_header(ws, RECETAS_COLS)
    for rec in session.scalars(select(Recipe).order_by(Recipe.id)).all():
        ws.append([rec.id, rec.name, rec.yield_qty, rec.yield_unit, rec.notes])
    _autosize(ws)

    # --- Lineas (with denormalized names for human readability + import) ---
    ws = wb.create_sheet("Lineas")
    _write_header(ws, LINEAS_COLS)
    ingredients_by_id = {ing.id: ing for ing in session.scalars(select(Ingredient)).all()}
    recipes_by_id = {rec.id: rec for rec in session.scalars(select(Recipe)).all()}
    for recipe in recipes_by_id.values():
        for line in recipe.lines:
            if line.line_kind == "ingredient":
                target_name = ingredients_by_id.get(line.line_ref_id)
                target_name_str = target_name.name if target_name else None
            elif line.line_kind == "sub_recipe":
                target_name = recipes_by_id.get(line.line_ref_id)
                target_name_str = target_name.name if target_name else None
            else:
                target_name_str = None
            ws.append(
                [
                    line.id,
                    line.recipe_id,
                    recipe.name,
                    line.line_kind,
                    line.line_ref_id,
                    target_name_str,
                    line.qty,
                    line.notes,
                ]
            )
    _autosize(ws)

    # --- Productos ---
    ws = wb.create_sheet("Productos")
    _write_header(ws, PRODUCTOS_COLS)
    for prod in session.scalars(select(Product).order_by(Product.id)).all():
        recipe_name = recipes_by_id.get(prod.recipe_id)
        ws.append(
            [
                prod.id,
                prod.name,
                prod.portion_label,
                _money_cell(prod.sale_price_gs),
                prod.recipe_id,
                recipe_name.name if recipe_name else None,
                prod.notes,
            ]
        )
    _autosize(ws)

    # --- Clientes ---
    ws = wb.create_sheet("Clientes")
    _write_header(ws, CLIENTES_COLS)
    for cust in session.scalars(select(Customer).order_by(Customer.id)).all():
        ws.append([
            cust.id,
            cust.phone,
            cust.name,
            getattr(cust, "email", None),
            getattr(cust, "cedula", None),
            cust.notes,
        ])
    _autosize(ws)

    # --- Ventas ---
    ws = wb.create_sheet("Ventas")
    _write_header(ws, VENTAS_COLS)
    products_by_id = {prod.id: prod for prod in session.scalars(select(Product)).all()}
    sales_q = select(Sale).order_by(Sale.id)
    if sale_start is not None and sale_end is not None:
        sales_q = sales_q.where(
            Sale.sold_at >= sale_start, Sale.sold_at <= sale_end
        )
    for sale in session.scalars(sales_q).all():
        product = products_by_id.get(sale.product_id)
        ws.append(
            [
                sale.id,
                sale.sold_at,
                sale.product_id,
                product.name if product else None,
                sale.qty,
                _money_cell(sale.unit_price_gs),
                sale.notes,
                sale.voided_at,
            ]
        )
    _autosize(ws)

    # NOTE: BACKLOG #1 (2026-10-02): SaleStockMove table dropped (migration 092).
    # StockMoves are now derived from SaleStockMovement (via affected_recipe_id /
    # ingredient_id) rather than Sale.stock_moves relationship. The StockMoves
    # export sheet is no longer derivable from sales alone; nothing to do here.

    wb.save(str(path))
    return path.resolve()


def to_bytes(session: Session) -> bytes:
    """Same as to_file but returns bytes (for streaming downloads).

    Uses openpyxl's BytesIO-friendly save.
    """
    from io import BytesIO

    path = BytesIO()
    # We can save to BytesIO directly with openpyxl
    wb = Workbook()
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    ws = wb.create_sheet("Ingredientes")
    _write_header(ws, INGREDIENTES_COLS)
    for ing in session.scalars(select(Ingredient).order_by(Ingredient.id)).all():
        ws.append(
            [
                ing.id,
                ing.name,
                ing.unit,
                ing.stock_qty,
                _money_cell(ing.purchase_price_gs),
                ing.min_stock_qty,
                ing.notes,
            ]
        )

    ws = wb.create_sheet("Recetas")
    _write_header(ws, RECETAS_COLS)
    for rec in session.scalars(select(Recipe).order_by(Recipe.id)).all():
        ws.append([rec.id, rec.name, rec.yield_qty, rec.yield_unit, rec.notes])

    ws = wb.create_sheet("Lineas")
    _write_header(ws, LINEAS_COLS)
    ingredients_by_id = {ing.id: ing for ing in session.scalars(select(Ingredient)).all()}
    recipes_by_id = {rec.id: rec for rec in session.scalars(select(Recipe)).all()}
    for recipe in recipes_by_id.values():
        for line in recipe.lines:
            if line.line_kind == "ingredient":
                target_name = ingredients_by_id.get(line.line_ref_id)
                target_name_str = target_name.name if target_name else None
            elif line.line_kind == "sub_recipe":
                target_name = recipes_by_id.get(line.line_ref_id)
                target_name_str = target_name.name if target_name else None
            else:
                target_name_str = None
            ws.append(
                [
                    line.id,
                    line.recipe_id,
                    recipe.name,
                    line.line_kind,
                    line.line_ref_id,
                    target_name_str,
                    line.qty,
                    line.notes,
                ]
            )

    ws = wb.create_sheet("Productos")
    _write_header(ws, PRODUCTOS_COLS)
    for prod in session.scalars(select(Product).order_by(Product.id)).all():
        recipe_name = recipes_by_id.get(prod.recipe_id)
        ws.append(
            [
                prod.id,
                prod.name,
                prod.portion_label,
                _money_cell(prod.sale_price_gs),
                prod.recipe_id,
                recipe_name.name if recipe_name else None,
                prod.notes,
            ]
        )

    ws = wb.create_sheet("Ventas")
    _write_header(ws, VENTAS_COLS)
    products_by_id = {prod.id: prod for prod in session.scalars(select(Product)).all()}
    for sale in session.scalars(select(Sale).order_by(Sale.id)).all():
        product = products_by_id.get(sale.product_id)
        ws.append(
            [
                sale.id,
                sale.sold_at,
                sale.product_id,
                product.name if product else None,
                sale.qty,
                _money_cell(sale.unit_price_gs),
                sale.notes,
                sale.voided_at,
            ]
        )

    # NOTE: BACKLOG #1 (2026-10-02): SaleStockMove dropped (migration 092).
    # See to_file() comment for context.

    wb.save(path)
    return path.getvalue()


__all__ = ["patch_plantilla_bytes", "to_bytes", "to_file", "write_patch_plantilla"]


# ---------------------------------------------------------------------------
# PATCH plantilla — Stream C, prelaunch roadmap 2026-09-17
# ---------------------------------------------------------------------------

# Column shapes for the PATCH plantilla workbook. These are intentionally
# narrower than the FULL export columns — the plantilla is a "what to edit"
# sheet, not a "what the system tracks" sheet.
PLANTILLA_PRODUCTOS_COLS = ["name", "sku", "sale_price_gs", "portion_label", "notes"]
PLANTILLA_CLIENTES_COLS = ["phone", "name", "email", "cedula", "notes"]
PLANTILLA_INGREDIENTES_COLS = [
    "name",
    "stock_qty",
    "min_stock_qty",
    "max_stock_qty",
    "purchase_price_gs",
    "lead_time_days",
    "notes",
]
PLANTILLA_RECETAS_COLS = ["name", "yield_qty", "prep_minutes", "notes"]


def _autosize_simple(ws: object, max_width: int = 40) -> None:
    """Same as `_autosize` but operates on a fresh workbook without relying
    on the helper being defined earlier in the module flow."""
    for col_idx in range(1, ws.max_column + 1):
        max_len = 0
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=True):
            for cell in row:
                if cell is None:
                    continue
                s = str(cell)
                if len(s) > max_len:
                    max_len = len(s)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, max_width)


def _build_patch_plantilla_wb(session: Session) -> "Workbook":
    """Construct a PATCH plantilla workbook in memory.

    Sheets:
      Productos     — ALL existing products pre-populated with current data.
        Operator edits cells in-place; empty cells = "leave unchanged".
      Clientes      — HEADER ONLY. Empty rows for new customers. Existing
        customers NOT listed (the operator finds them by phone in their
        own system). Setting this empty avoids "did I just overwrite an
        old customer?" surprise.
      Ingredientes  — ALL existing ingredients pre-populated.
      Recetas       — ALL existing recipes pre-populated.

    The plantilla ships pre-populated so a one-time import → edit → upload
    cycle lets the operator change one product price and re-upload.
    """
    from openpyxl import Workbook

    wb = Workbook()
    default = wb.active
    if default is not None:
        wb.remove(default)

    # --- Productos ---
    ws = wb.create_sheet("Productos")
    ws.append(PLANTILLA_PRODUCTOS_COLS)
    for prod in session.scalars(select(Product).order_by(Product.name)).all():
        ws.append(
            [
                prod.name,
                prod.sku,
                _money_cell(prod.sale_price_gs),
                prod.portion_label,
                prod.notes,
            ]
        )
    _autosize_simple(ws)

    # --- Clientes (header only) ---
    ws = wb.create_sheet("Clientes")
    ws.append(PLANTILLA_CLIENTES_COLS)
    _autosize_simple(ws)

    # --- Ingredientes ---
    ws = wb.create_sheet("Ingredientes")
    ws.append(PLANTILLA_INGREDIENTES_COLS)
    for ing in session.scalars(select(Ingredient).order_by(Ingredient.name)).all():
        ws.append(
            [
                ing.name,
                ing.stock_qty,
                ing.min_stock_qty,
                ing.max_stock_qty,
                _money_cell(ing.purchase_price_gs),
                ing.lead_time_days,
                ing.notes,
            ]
        )
    _autosize_simple(ws)

    # --- Recetas ---
    ws = wb.create_sheet("Recetas")
    ws.append(PLANTILLA_RECETAS_COLS)
    for rec in session.scalars(select(Recipe).order_by(Recipe.name)).all():
        ws.append([rec.name, rec.yield_qty, rec.prep_minutes, rec.notes])
    _autosize_simple(ws)

    return wb


def write_patch_plantilla(session: Session, path: str | Path) -> Path:
    """Write a PATCH plantilla workbook to disk and return the absolute Path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = _build_patch_plantilla_wb(session)
    wb.save(str(path))
    return path.resolve()


def patch_plantilla_bytes(session: Session) -> bytes:
    """Return the PATCH plantilla workbook as bytes (for streaming downloads)."""
    from io import BytesIO

    wb = _build_patch_plantilla_wb(session)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Backwards-compat note: customers are intentionally NOT exported in FULL
# mode. Customers are managed via PATCH on /excel/importar only — see
# Stream C prelaunch roadmap 2026-09-17. If we later decide to also export
# customers in FULL, add a Clientes sheet here AND import handling in
# import_xlsx._import_full.

