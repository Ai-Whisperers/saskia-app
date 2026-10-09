"""app/services/import_xlsx.py — Drive/HEREBUS .xlsx → SQLite.

Per dev plan §9 Task 6 + v2 §6 (Excel import).

Reads a HEREBUS-format Excel workbook and loads its rows into the RMS SQLite
database. The workbook layout is whatever the export_xlsx service produces
(symmetric), with these sheets:

    Ingredientes  — id, name, unit, stock_qty, purchase_price_gs, min_stock_qty, notes
    Recetas       — id, name, yield_qty, yield_unit, notes
    Lineas        — id, recipe_id, line_kind ('ingredient' | 'sub_recipe'),
                    line_ref_id (FK target id), qty, notes
    Productos     — id, name, portion_label, sale_price_gs, recipe_id, notes
    Ventas        — id, sold_at, product_id, qty, unit_price_gs, notes, voided_at
    StockMoves    — id, sale_id, affected_recipe_id, ingredient_id, qty_delta

Money discipline: money values (purchase_price_gs, sale_price_gs,
unit_price_gs) MUST come through `app.rms.money.to_int_gs`. No raw floats.

Idempotency: the import is keyed by ImportBatch. The caller passes the same
DB session; we never close or commit it. The function returns an
ImportResult dataclass with counts and warnings.

PATCH mode (Stream C, prelaunch roadmap 2026-09-17):
    Each sheet is processed independently. Per row:
    - Productos: match by name (case-insensitive) OR sku; update fields if
      matched; otherwise emit a warning (no auto-create).
    - Clientes: match by phone (exact); update fields if matched; if not
      matched and phone + name present, create new Customer.
    - Ingredientes: match by name; update fields; no auto-create.
    - Recetas: match by name; update fields; no auto-create.

    PATCH mode does not import Lineas, Ventas, or StockMoves — those are
    derived state and round-trip via FULL exports only.

Validation contract: a bad row never aborts the whole import. Each row is
validated independently; invalid rows log a warning and the rest proceed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ
from app.rms.models import (
    Customer,
    ImportBatch,
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
)
from app.rms.money import parse_gs, to_int_gs

ImportMode = Literal["FULL", "PATCH", "APPEND"]

ImportModeAll = Literal["FULL", "PATCH", "APPEND"]


@dataclass
class DryRunResult:
    """Result of a dry-run import validation."""

    errors: list[dict] = field(default_factory=list)  # [{row, field, message}]
    warnings: list[dict] = field(default_factory=list)  # [{row, field, message}]


@dataclass
class ImportResult:
    """Result of a successful import."""

    batch_id: int
    source_filename: str
    mode: str = "FULL"
    ingredients: int = 0
    recipes: int = 0
    lines: int = 0
    products: int = 0
    customers: int = 0
    sales: int = 0
    stock_moves: int = 0
    warnings: list[str | dict] = field(
        default_factory=list
    )  # mix of strings and {row,field,message} dicts

    def row_counts(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "mode": self.mode,
            "ingredients": self.ingredients,
            "recipes": self.recipes,
            "lines": self.lines,
            "products": self.products,
            "customers": self.customers,
            "sales": self.sales,
            "stock_moves": self.stock_moves,
        }
        if self.warnings:
            d["warnings"] = self.warnings
        return d


def _sheet(wb: object, name: str) -> Worksheet | None:
    """Return sheet by name, or None if missing."""
    if name in wb.sheetnames:
        return wb[name]
    return None


def _rows(sheet: Worksheet | None) -> list[dict]:
    """Convert a sheet's rows to list of dicts (header → key, cell → value)."""
    if sheet is None:
        return []
    iter_rows = sheet.iter_rows(values_only=True)
    try:
        header = next(iter_rows)
    except StopIteration:
        return []
    header = [str(h) if h is not None else "" for h in header]
    out: list[dict] = []
    for row in iter_rows:
        if row is None or all(c is None for c in row):
            continue
        out.append({header[i]: row[i] for i in range(min(len(header), len(row)))})
    return out


def _opt_str(value: object) -> str | None:
    """Cell value → optional string (None → None; empty string → None)."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _opt_float(value: object) -> float | None:
    """Cell value → optional float (None/empty → None)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    return float(s)


def _opt_int(value: object) -> int | None:
    """Cell value → optional int (None/empty → None)."""
    f = _opt_float(value)
    if f is None:
        return None
    return int(f)


def _money_int_gs(value: object, *, field_name: str, warnings: list) -> int | None:
    """Cell value → integer Gs. via parse_gs (accepts 'Gs. 5.000' format) or
    to_int_gs (accepts numeric).

    Records a warning on parse failure rather than crashing — keeps the import
    partial-success instead of all-or-nothing.

    Returns None for missing prices (None, empty string).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return to_int_gs(value)
    s = str(value).strip()
    if not s:
        return None
    # Try parse_gs first (accepts "Gs. 5.000", "1.234.567", "1234567")
    try:
        return parse_gs(s)
    except ValueError:
        pass
    # Fall back to to_int_gs (accepts "5000", "5000.5")
    try:
        return to_int_gs(s)
    except (ValueError, TypeError) as exc:
        warnings.append(f"{field_name}: no se pudo parsear {value!r}: {exc}")
        return None


# --------------------------------------------------------------------------_
# Validation (dry-run)
# --------------------------------------------------------------------------_


def _validate_workbook(wb: object, mode: str) -> tuple[list[dict], list[dict]]:
    """Validate all sheets without writing. Returns (errors, warnings)."""
    errors: list[dict] = []
    warnings: list[dict] = []

    def _err(row_num: object, field: object, msg: object):
        errors.append({"row": row_num, "field": field, "message": msg})

    def _warn(row_num: object, field: object, msg: object):
        warnings.append({"row": row_num, "field": field, "message": msg})

    # Ingredientes
    for row_num, row in enumerate(_rows(_sheet(wb, "Ingredientes")), start=2):
        name = _opt_str(row.get("name"))
        if not name:
            _err(row_num, "name", "Nombre requerido")
        stock = _opt_float(row.get("stock_qty"))
        if stock is not None and stock < 0:
            _err(row_num, "stock_qty", f"stock_qty no puede ser negativo: {stock}")
        price = row.get("purchase_price_gs")
        if price is not None:
            try:
                if isinstance(price, (int, float)):
                    to_int_gs(price)
                else:
                    parse_gs(str(price))
            except (ValueError, TypeError):
                _err(row_num, "purchase_price_gs", f"No se pudo parsear precio: {price!r}")

    # Recetas
    for row_num, row in enumerate(_rows(_sheet(wb, "Recetas")), start=2):
        name = _opt_str(row.get("name"))
        if not name:
            _err(row_num, "name", "Nombre requerido")

    # Lineas
    for row_num, row in enumerate(_rows(_sheet(wb, "Lineas")), start=2):
        recipe_name = _opt_str(row.get("recipe_name"))
        if not recipe_name:
            _warn(row_num, "recipe_name", "recipe_name vacío")
        line_kind = _opt_str(row.get("line_kind"))
        if line_kind and line_kind not in ("ingredient", "sub_recipe"):
            _err(
                row_num,
                "line_kind",
                f"line_kind debe ser 'ingredient' o 'sub_recipe', recibido: {line_kind!r}",
            )
        qty = _opt_float(row.get("qty"))
        if qty is not None and qty <= 0:
            _err(row_num, "qty", f"qty debe ser > 0, recibido: {qty}")

    # Productos
    for row_num, row in enumerate(_rows(_sheet(wb, "Productos")), start=2):
        name = _opt_str(row.get("name"))
        if not name:
            _err(row_num, "name", "Nombre requerido")
        price = row.get("sale_price_gs")
        if price is not None:
            try:
                if isinstance(price, (int, float)):
                    to_int_gs(price)
                else:
                    parse_gs(str(price))
            except (ValueError, TypeError):
                _err(row_num, "sale_price_gs", f"No se pudo parsear precio: {price!r}")

    # Ventas
    for row_num, row in enumerate(_rows(_sheet(wb, "Ventas")), start=2):
        sold_at = row.get("sold_at")
        if sold_at is None:
            _err(row_num, "sold_at", "sold_at requerido")
        elif isinstance(sold_at, datetime):
            if sold_at > datetime.now(ASUNCION_TZ):
                _warn(row_num, "sold_at", f"Fecha en el futuro: {sold_at}")
        product_id = _opt_int(row.get("product_id"))
        if product_id is None:
            _err(row_num, "product_id", "product_id requerido")
        qty = _opt_float(row.get("qty"))
        if qty is not None and qty <= 0:
            _err(row_num, "qty", "qty debe ser > 0")

    return errors, warnings


# --------------------------------------------------------------------------
# APPEND mode — insert rows without updating existing
# --------------------------------------------------------------------------


def _import_append(session: Session, wb: object, result: ImportResult) -> None:
    """APPEND mode: insert new rows without modifying existing ones.

    Matches by natural key but does NOT update — only inserts rows that
    don't already exist. Recipes/Ingredients cannot be auto-created in APPEND
    since they have no phone/name natural key for easy duplicate detection;
    they are skipped with a warning unless they already exist exactly.
    """
    # Ingredientes — no append (would create exact duplicates; skip with warning)
    ing_rows = _rows(_sheet(wb, "Ingredientes"))
    if ing_rows:
        result.warnings.append(
            f"APPEND: Ingredientes sheet tiene {len(ing_rows)} filas — "
            "se ignoran en modo APPEND (usá PATCH para actualizar)"
        )

    # Clientes — insert only if phone not already in DB
    customers_index: dict[str, int] = {}
    existing_phones = {
        r[0]
        for r in session.execute(select(Customer.phone).where(Customer.phone.isnot(None))).all()
    }
    for row in _rows(_sheet(wb, "Clientes")):
        phone = _opt_str(row.get("telefono")) or _opt_str(row.get("phone"))
        name = _opt_str(row.get("nombre")) or _opt_str(row.get("name"))
        if not phone:
            result.warnings.append("Clientes: fila sin teléfono, saltada")
            continue
        if phone in existing_phones:
            result.warnings.append(f"Clientes: {phone} ya existe, saltada")
            continue
        cust = Customer(phone=phone, name=name or "Sin nombre")
        session.add(cust)
        session.flush()
        existing_phones.add(phone)
        customers_index[phone] = cust.id
        result.customers += 1

    # Recetas / Lineas / Productos — skip in APPEND mode (too risky without natural key dedup)
    for sheet in ("Recetas", "Lineas", "Productos"):
        rows = _rows(_sheet(wb, sheet))
        if rows:
            result.warnings.append(
                f"APPEND: {sheet} sheet tiene {len(rows)} filas — "
                "se ignoran en modo APPEND (usá PATCH para actualizar)"
            )

    # Ventas — insert as-is (append-only)
    for row in _rows(_sheet(wb, "Ventas")):
        sold_at = row.get("sold_at")
        if sold_at is None:
            result.warnings.append("Ventas: fila sin sold_at, saltada")
            continue
        product_id_val = _opt_int(row.get("product_id"))
        if product_id_val is None:
            result.warnings.append("Ventas: fila sin product_id, saltada")
            continue
        qty = _opt_float(row.get("qty")) or 1.0
        unit_price = _money_int_gs(
            row.get("unit_price_gs"), field_name="Ventas.unit_price", warnings=result.warnings
        )
        if unit_price is None:
            result.warnings.append("Ventas: unit_price_gs requerido")
            continue
        sale = Sale(
            sold_at=sold_at if isinstance(sold_at, datetime) else datetime.now(ASUNCION_TZ),
            product_id=product_id_val,
            qty=qty,
            unit_price_gs=unit_price,
            notes=_opt_str(row.get("notes")),
        )
        session.add(sale)
        result.sales += 1


# --------------------------------------------------------------------------
# FULL mode — additive (legacy behavior preserved)
# --------------------------------------------------------------------------


def _import_full(session: Session, wb: object, result: ImportResult) -> None:
    warnings = result.warnings
    # 1. Ingredientes
    ingredients_index: dict[str, int] = {}  # name → id
    for row in _rows(_sheet(wb, "Ingredientes")):
        name = _opt_str(row.get("name"))
        if not name:
            warnings.append(f"Ingredientes: fila sin nombre, saltada: {row}")
            continue
        unit = _opt_str(row.get("unit")) or "und"
        stock_qty = _opt_float(row.get("stock_qty")) or 0.0
        purchase_price_gs = _money_int_gs(
            row.get("purchase_price_gs"),
            field_name=f"Ingredientes[{name}].purchase_price_gs",
            warnings=warnings,
        )
        min_stock_qty = _opt_float(row.get("min_stock_qty")) or 0.0
        notes = _opt_str(row.get("notes"))
        ing = Ingredient(
            name=name,
            unit=unit,
            stock_qty=stock_qty,
            purchase_price_gs=purchase_price_gs,
            min_stock_qty=min_stock_qty,
            notes=notes,
        )
        session.add(ing)
        session.flush()
        ingredients_index[name] = ing.id
        result.ingredients += 1

    # 2. Recetas
    recipes_index: dict[str, int] = {}  # name → id
    for row in _rows(_sheet(wb, "Recetas")):
        name = _opt_str(row.get("name"))
        if not name:
            warnings.append(f"Recetas: fila sin nombre, saltada: {row}")
            continue
        yield_qty = _opt_float(row.get("yield_qty"))
        yield_unit = _opt_str(row.get("yield_unit")) or "und"
        notes = _opt_str(row.get("notes"))
        recipe = Recipe(
            name=name,
            yield_qty=yield_qty,
            yield_unit=yield_unit,
            notes=notes,
        )
        session.add(recipe)
        session.flush()
        recipes_index[name] = recipe.id
        result.recipes += 1

    # 3. Lineas (polymorphic recipe_line)
    for row in _rows(_sheet(wb, "Lineas")):
        recipe_name = _opt_str(row.get("recipe_name"))
        line_kind = _opt_str(row.get("line_kind"))
        target_name = _opt_str(row.get("target_name"))
        qty = _opt_float(row.get("qty"))
        notes = _opt_str(row.get("notes"))

        if not recipe_name or recipe_name not in recipes_index:
            warnings.append(
                f"Lineas: recipe_name={recipe_name!r} no existe en Recetas, saltada: {row}"
            )
            continue
        if line_kind not in ("ingredient", "sub_recipe"):
            warnings.append(f"Lineas[{recipe_name}]: line_kind={line_kind!r} inválido, saltada")
            continue
        if not target_name:
            warnings.append(f"Lineas[{recipe_name}]: target_name vacío, saltada")
            continue
        if qty is None or qty <= 0:
            warnings.append(f"Lineas[{recipe_name}->{target_name}]: qty={qty!r} inválido, saltada")
            continue

        # Resolve target id by name lookup
        if line_kind == "ingredient":
            if target_name not in ingredients_index:
                warnings.append(
                    f"Lineas[{recipe_name}]: ingrediente {target_name!r} no existe, saltada"
                )
                continue
            line_ref_id = ingredients_index[target_name]
        else:  # sub_recipe
            if target_name not in recipes_index:
                warnings.append(
                    f"Lineas[{recipe_name}]: sub-receta {target_name!r} no existe, saltada"
                )
                continue
            line_ref_id = recipes_index[target_name]

        line = RecipeLine(
            recipe_id=recipes_index[recipe_name],
            line_kind=line_kind,
            line_ref_id=line_ref_id,
            qty=qty,
            notes=notes,
        )
        session.add(line)
        result.lines += 1

    # 4. Productos
    products_index: dict[str, int] = {}
    for row in _rows(_sheet(wb, "Productos")):
        name = _opt_str(row.get("name"))
        if not name:
            warnings.append(f"Productos: fila sin nombre, saltada: {row}")
            continue
        portion_label = _opt_str(row.get("portion_label")) or "1 unidad"
        sale_price_gs = _money_int_gs(
            row.get("sale_price_gs"),
            field_name=f"Productos[{name}].sale_price_gs",
            warnings=warnings,
        )
        if sale_price_gs is None:
            sale_price_gs = 0
        recipe_name = _opt_str(row.get("recipe_name"))
        recipe_id = recipes_index.get(recipe_name) if recipe_name else None
        notes = _opt_str(row.get("notes"))
        product = Product(
            name=name,
            portion_label=portion_label,
            sale_price_gs=sale_price_gs,
            recipe_id=recipe_id,
            notes=notes,
        )
        session.add(product)
        session.flush()
        products_index[name] = product.id
        result.products += 1

    # 5. Ventas
    for row in _rows(_sheet(wb, "Ventas")):
        product_name = _opt_str(row.get("product_name"))
        if not product_name or product_name not in products_index:
            warnings.append(f"Ventas: product_name={product_name!r} no existe, saltada: {row}")
            continue
        sold_at = row.get("sold_at")
        if isinstance(sold_at, datetime):
            sold_at_dt = sold_at
        elif isinstance(sold_at, str):
            try:
                sold_at_dt = datetime.fromisoformat(sold_at)
            except ValueError:
                warnings.append(f"Ventas[{product_name}]: sold_at={sold_at!r} inválido, saltada")
                continue
        else:
            warnings.append(f"Ventas[{product_name}]: sold_at={sold_at!r} vacío, saltada")
            continue
        qty = _opt_float(row.get("qty"))
        if qty is None or qty <= 0:
            warnings.append(f"Ventas[{product_name}]: qty={qty!r} inválido, saltada")
            continue
        unit_price_gs = _money_int_gs(
            row.get("unit_price_gs"),
            field_name=f"Ventas[{product_name}].unit_price_gs",
            warnings=warnings,
        )
        if unit_price_gs is None:
            unit_price_gs = 0
        notes = _opt_str(row.get("notes"))
        voided_at_raw = row.get("voided_at")
        voided_at = None
        if isinstance(voided_at_raw, datetime):
            voided_at = voided_at_raw
        elif isinstance(voided_at_raw, str) and voided_at_raw.strip():
            try:
                voided_at = datetime.fromisoformat(voided_at_raw)
            except ValueError:
                warnings.append(f"Ventas[{product_name}]: voided_at={voided_at_raw!r} inválido")
        sale = Sale(
            sold_at=sold_at_dt,
            product_id=products_index[product_name],
            qty=qty,
            unit_price_gs=unit_price_gs,
            notes=notes,
            voided_at=voided_at,
        )
        session.add(sale)
        result.sales += 1

    # 6. StockMoves (derived from sales; informational only — don't re-import)


# ---------------------------------------------------------------------------
# PATCH mode — natural-key matching, no destructive wipe
# ---------------------------------------------------------------------------


def _product_lookup(session: Session) -> tuple[dict[str, Product], dict[str, Product]]:
    """Build (name_lc → product, sku → product) index for PATCH matching."""
    products = session.scalars(select(Product)).all()
    by_name: dict[str, Product] = {p.name.strip().lower(): p for p in products if p.name}
    by_sku: dict[str, Product] = {p.sku: p for p in products if p.sku}
    return by_name, by_sku


def _ingredient_lookup(session: Session) -> dict[str, Ingredient]:
    return {i.name.strip().lower(): i for i in session.scalars(select(Ingredient)).all() if i.name}


def _recipe_lookup(session: Session) -> dict[str, Recipe]:
    return {r.name.strip().lower(): r for r in session.scalars(select(Recipe)).all() if r.name}


def _customer_lookup(session: Session) -> dict[str, Customer]:
    """phone (exact) → Customer. Multiple customers with the same phone are
    unusual (no unique constraint on phone) but possible; PATCH picks the
    first match."""
    out: dict[str, Customer] = {}
    for c in session.scalars(select(Customer)).all():
        if c.phone:
            out.setdefault(c.phone, c)
    return out


def _import_patch_productos(session: Session, wb: object, result: ImportResult) -> None:
    """PATCH Productos: match by name (case-insensitive) OR sku. Update fields."""
    warnings = result.warnings
    by_name, by_sku = _product_lookup(session)
    sheet = _sheet(wb, "Productos")
    if sheet is None:
        # PATCH mode without a Productos sheet is not an error; just skip.
        return

    for idx, row in enumerate(_rows(sheet), start=2):  # header is row 1
        name_raw, sku_raw = _extract_producto_keys(row)
        if not _validate_producto_row(row, idx, name_raw, sku_raw, warnings):
            continue
        product = _find_product_by_keys(name_raw, sku_raw, by_name, by_sku, warnings, idx)
        if product is None:
            continue
        _update_producto_fields(row, product, name_raw, sku_raw, warnings)
        result.products += 1


def _extract_producto_keys(row) -> tuple:
    """Extract name and sku from a producto row.
    
    Extracted from _import_patch_productos to reduce complexity.
    """
    name_raw = _opt_str(row.get("name"))
    sku_raw = _opt_str(row.get("sku"))
    return name_raw, sku_raw


def _validate_producto_row(
    row, idx: int, name_raw: str | None, sku_raw: str | None, warnings: list
) -> bool:
    """Validate a producto row has at least one key.
    
    Extracted from _import_patch_productos to reduce complexity.
    Returns False if the row should be skipped.
    """
    if not name_raw and not sku_raw:
        warnings.append(f"Productos: fila {idx} sin name ni sku, saltada: {row}")
        return False
    return True


def _find_product_by_keys(
    name_raw: str | None,
    sku_raw: str | None,
    by_name: dict,
    by_sku: dict,
    warnings: list,
    idx: int,
) -> Product | None:
    """Find a product by sku or name (case-insensitive).
    
    Extracted from _import_patch_productos to reduce complexity.
    Returns None if not found (and adds a warning).
    """
    name_lc = name_raw.strip().lower() if name_raw else ""
    if sku_raw and sku_raw in by_sku:
        return by_sku[sku_raw]
    if name_lc and name_lc in by_name:
        return by_name[name_lc]
    warnings.append(
        f"Productos: {name_raw or sku_raw!r} no encontrado en DB "
        f"(sin auto-create); editá un producto existente"
    )
    return None


def _update_producto_fields(
    row: dict, product: Product, name_raw: str | None, sku_raw: str | None, warnings: list
) -> None:
    """Update product fields from a row (only fields present in the row).
    
    Extracted from _import_patch_productos to reduce complexity.
    """
    _update_sale_price(row, product, name_raw, sku_raw, warnings)
    _update_optional_text_field(row, product, "notes", "notes")
    _update_portion_label(row, product)


def _update_sale_price(
    row: dict, product: Product, name_raw: str | None, sku_raw: str | None, warnings: list
) -> None:
    """Update the sale price if present in the row.
    
    Extracted from _update_producto_fields to reduce complexity.
    """
    if row.get("sale_price_gs") in (None, ""):
        return
    new_price = _money_int_gs(
        row.get("sale_price_gs"),
        field_name=f"Productos[{name_raw or sku_raw}].sale_price_gs",
        warnings=warnings,
    )
    if new_price is not None:
        product.sale_price_gs = new_price


def _update_optional_text_field(row: dict, product: Product, row_key: str, model_attr: str) -> None:
    """Update an optional text field if present in the row.
    
    Extracted from _update_producto_fields to reduce complexity.
    """
    val = _opt_str(row.get(row_key))
    if val is not None:
        setattr(product, model_attr, val)


def _update_portion_label(row: dict, product: Product) -> None:
    """Update the portion label if present in the row.
    
    Extracted from _update_producto_fields to reduce complexity.
    """
    portion_label = _opt_str(row.get("portion_label"))
    if portion_label is not None:
        product.portion_label = portion_label or "1 unidad"


def _import_patch_clientes(session: Session, wb: object, result: ImportResult) -> None:
    """PATCH Clientes: match by phone. Update or create."""
    warnings = result.warnings
    by_phone = _customer_lookup(session)
    sheet = _sheet(wb, "Clientes")
    if sheet is None:
        return
    rows = _rows(sheet)
    seen_phones: set[str] = set()

    for idx, row in enumerate(rows, start=2):
        if not _validate_cliente_row(row, idx, seen_phones, warnings):
            continue
        phone = _opt_str(row.get("phone"))
        seen_phones.add(phone)
        _process_cliente_row(session, row, by_phone, warnings, result)


def _validate_cliente_row(row, idx: int, seen_phones: set, warnings: list) -> bool:
    """Validate a cliente row and return True if it should be processed.
    
    Extracted from _import_patch_clientes to reduce complexity.
    Returns False if the row should be skipped.
    """
    phone = _opt_str(row.get("phone"))
    if not phone:
        warnings.append(f"Clientes: fila {idx} sin phone, saltada: {row}")
        return False
    if phone in seen_phones:
        warnings.append(
            f"Clientes: phone={phone!r} aparece duplicado en el archivo, "
            f"solo se procesa el primero"
        )
        return False
    return True


def _process_cliente_row(
    session: Session, row: dict, by_phone: dict, warnings: list, result: ImportResult
) -> None:
    """Process a single cliente row (update or create).
    
    Extracted from _import_patch_clientes to reduce complexity.
    """
    phone = _opt_str(row.get("phone"))
    name = _opt_str(row.get("name"))
    email = _opt_str(row.get("email"))
    cedula = _opt_str(row.get("cedula"))
    notes = _opt_str(row.get("notes"))

    existing = by_phone.get(phone)
    if existing is not None:
        _update_existing_cliente(existing, name, email, cedula, notes)
    else:
        _create_new_cliente(session, row, by_phone, warnings, phone, name, email, cedula, notes)
    result.customers += 1


def _update_existing_cliente(
    existing, name: str | None, email: str | None, cedula: str | None, notes: str | None
) -> None:
    """Update an existing cliente with new field values.
    
    Extracted from _process_cliente_row to reduce complexity.
    """
    if name is not None:
        existing.name = name
    if email is not None:
        existing.email = email
    if cedula is not None:
        existing.cedula = cedula
    if notes is not None:
        existing.notes = notes
    existing.updated_at = datetime.now(timezone.utc)


def _create_new_cliente(
    session: Session,
    row: dict,
    by_phone: dict,
    warnings: list,
    phone: str,
    name: str | None,
    email: str | None,
    cedula: str | None,
    notes: str | None,
) -> None:
    """Create a new cliente, skipping if name is missing.
    
    Extracted from _process_cliente_row to reduce complexity.
    """
    if not name:
        warnings.append(f"Clientes: phone={phone!r} nuevo pero sin name, saltada: {row}")
        return
    new = Customer(
        name=name,
        phone=phone,
        email=email,
        cedula=cedula,
        notes=notes,
    )
    session.add(new)
    session.flush()
    by_phone[phone] = new


def _import_patch_ingredientes(session: Session, wb: object, result: ImportResult) -> None:
    """PATCH Ingredientes: match by name. Update fields."""
    warnings = result.warnings
    by_name = _ingredient_lookup(session)
    sheet = _sheet(wb, "Ingredientes")
    if sheet is None:
        return

    for idx, row in enumerate(_rows(sheet), start=2):
        name_raw = _opt_str(row.get("name"))
        if not name_raw:
            warnings.append(f"Ingredientes: fila {idx} sin name, saltada: {row}")
            continue
        name_lc = name_raw.strip().lower()
        ing = by_name.get(name_lc)
        if ing is None:
            warnings.append(
                f"Ingredientes: {name_raw!r} no encontrado en DB "
                f"(sin auto-create); editá un ingrediente existente"
            )
            continue

        stock_v = row.get("stock_qty")
        if stock_v not in (None, ""):
            new_stock = _opt_float(stock_v)
            if new_stock is not None and new_stock >= 0:
                ing.stock_qty = new_stock
            elif new_stock is not None and new_stock < 0:
                warnings.append(
                    f"Ingredientes[{name_raw}]: stock_qty={stock_v!r} negativo, ignorado"
                )

        ms_v = row.get("min_stock_qty")
        if ms_v not in (None, ""):
            new_ms = _opt_float(ms_v)
            if new_ms is not None and new_ms >= 0:
                ing.min_stock_qty = new_ms

        mx_v = row.get("max_stock_qty")
        if mx_v not in (None, ""):
            mx = _opt_float(mx_v)
            if mx is not None and mx >= 0:
                ing.max_stock_qty = mx
            elif mx is None:
                ing.max_stock_qty = None

        pp_v = row.get("purchase_price_gs")
        if pp_v not in (None, ""):
            new_pp = _money_int_gs(
                pp_v,
                field_name=f"Ingredientes[{name_raw}].purchase_price_gs",
                warnings=warnings,
            )
            if new_pp is not None:
                ing.purchase_price_gs = new_pp
                ing.purchase_price_updated_at = datetime.now(timezone.utc)

        lt_v = row.get("lead_time_days")
        if lt_v not in (None, ""):
            new_lt = _opt_int(lt_v)
            if new_lt is not None and new_lt >= 0:
                ing.lead_time_days = new_lt

        notes_v = _opt_str(row.get("notes"))
        if notes_v is not None:
            ing.notes = notes_v

        result.ingredients += 1


def _import_patch_recetas(session: Session, wb: object, result: ImportResult) -> None:
    """PATCH Recetas: match by name. Update fields."""
    warnings = result.warnings
    by_name = _recipe_lookup(session)
    sheet = _sheet(wb, "Recetas")
    if sheet is None:
        return

    for idx, row in enumerate(_rows(sheet), start=2):
        name_raw = _opt_str(row.get("name"))
        if not name_raw:
            warnings.append(f"Recetas: fila {idx} sin name, saltada: {row}")
            continue
        name_lc = name_raw.strip().lower()
        rec = by_name.get(name_lc)
        if rec is None:
            warnings.append(
                f"Recetas: {name_raw!r} no encontrada en DB (sin auto-create); "
                f"editá una receta existente"
            )
            continue

        yq = row.get("yield_qty")
        if yq not in (None, ""):
            new_yq = _opt_float(yq)
            if new_yq is not None and new_yq > 0:
                rec.yield_qty = new_yq
        pm_v = row.get("prep_minutes")
        if pm_v not in (None, ""):
            new_pm = _opt_int(pm_v)
            if new_pm is not None and new_pm >= 0:
                rec.prep_minutes = new_pm
        notes_v = _opt_str(row.get("notes"))
        if notes_v is not None:
            rec.notes = notes_v

        result.recipes += 1


def _import_patch(session: Session, wb: object, result: ImportResult) -> None:
    """PATCH mode dispatcher — process sheets independently. Each sheet is
    best-effort: bad rows log warnings and the rest proceed."""
    _import_patch_productos(session, wb, result)
    session.flush()
    _import_patch_clientes(session, wb, result)
    _import_patch_ingredientes(session, wb, result)
    _import_patch_recetas(session, wb, result)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def from_file(
    session: Session,
    path: str | Path,
    *,
    mode: ImportMode = "FULL",
    dry_run: bool = False,
) -> ImportResult | DryRunResult:
    """Import a HEREBUS .xlsx into the DB via `session`.

    Caller owns the session (we commit at the end). Caller must run
    `init_db(engine)` before calling.

    mode='FULL' (default): additive — appends rows to existing tables.
    mode='PATCH': natural-key matching on Productos / Clientes / Ingredientes /
        Recetas sheets. Updates matching rows; creates new Clientes if phone
        not found. Other sheets are skipped.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")
    if path.suffix.lower() != ".xlsx":
        raise ValueError(f"Expected .xlsx, got {path.suffix}")

    wb = load_workbook(filename=str(path), data_only=True, read_only=True)

    # In dry-run mode, validate without writing
    if dry_run:
        errors, warnings = _validate_workbook(wb, str(mode).upper())
        return DryRunResult(errors=errors, warnings=warnings)

    warnings: list[str] = []
    result = ImportResult(batch_id=-1, source_filename=path.name, mode=str(mode), warnings=warnings)

    mode_upper = str(mode).upper()
    if mode_upper == "PATCH":
        _import_patch(session, wb, result)
    elif mode_upper == "APPEND":
        _import_append(session, wb, result)
    else:
        _import_full(session, wb, result)

    batch = ImportBatch(
        imported_at=datetime.now(ASUNCION_TZ),
        source_filename=path.name,
        note=f"mode={mode}",
        row_counts_json=result.row_counts(),
    )
    session.add(batch)
    session.flush()
    result.batch_id = batch.id
    session.commit()
    return result


def from_workbook(
    session: Session,
    wb: object,
    *,
    mode: ImportMode = "FULL",
    source_filename: str = "upload.xlsx",
) -> ImportResult:
    """Same as `from_file` but takes an already-opened openpyxl Workbook.

    Useful for tests and for in-memory scaffolding.
    """
    warnings: list[str] = []
    result = ImportResult(
        batch_id=-1,
        source_filename=source_filename,
        mode=str(mode),
        warnings=warnings,
    )
    if str(mode).upper() == "PATCH":
        _import_patch(session, wb, result)
    else:
        _import_full(session, wb, result)

    batch = ImportBatch(
        imported_at=datetime.now(ASUNCION_TZ),
        source_filename=source_filename,
        note=f"mode={mode}",
        row_counts_json=result.row_counts(),
    )
    session.add(batch)
    session.flush()
    result.batch_id = batch.id
    session.commit()
    return result


__all__ = ["ImportMode", "ImportResult", "from_file", "from_workbook"]
