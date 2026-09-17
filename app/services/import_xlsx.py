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
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session

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

ImportMode = Literal["FULL", "PATCH"]


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
    warnings: list[str] = field(default_factory=list)

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


def _sheet(wb, name: str) -> Worksheet | None:
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


def _opt_str(value) -> str | None:
    """Cell value → optional string (None → None; empty string → None)."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _opt_float(value) -> float | None:
    """Cell value → optional float (None/empty → None)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    return float(s)


def _opt_int(value) -> int | None:
    """Cell value → optional int (None/empty → None)."""
    f = _opt_float(value)
    if f is None:
        return None
    return int(f)


def _money_int_gs(value, *, field_name: str, warnings: list[str]) -> int | None:
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


# ---------------------------------------------------------------------------
# FULL mode — additive (legacy behavior preserved)
# ---------------------------------------------------------------------------


def _import_full(session: Session, wb, result: ImportResult) -> None:
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
    return {
        i.name.strip().lower(): i
        for i in session.scalars(select(Ingredient)).all()
        if i.name
    }


def _recipe_lookup(session: Session) -> dict[str, Recipe]:
    return {
        r.name.strip().lower(): r
        for r in session.scalars(select(Recipe)).all()
        if r.name
    }


def _customer_lookup(session: Session) -> dict[str, Customer]:
    """phone (exact) → Customer. Multiple customers with the same phone are
    unusual (no unique constraint on phone) but possible; PATCH picks the
    first match."""
    out: dict[str, Customer] = {}
    for c in session.scalars(select(Customer)).all():
        if c.phone:
            out.setdefault(c.phone, c)
    return out


def _import_patch_productos(session: Session, wb, result: ImportResult) -> None:
    """PATCH Productos: match by name (case-insensitive) OR sku. Update fields."""
    warnings = result.warnings
    by_name, by_sku = _product_lookup(session)
    sheet = _sheet(wb, "Productos")
    if sheet is None:
        # PATCH mode without a Productos sheet is not an error; just skip.
        return

    for idx, row in enumerate(_rows(sheet), start=2):  # header is row 1
        name_raw = _opt_str(row.get("name"))
        sku_raw = _opt_str(row.get("sku"))
        if not name_raw and not sku_raw:
            warnings.append(f"Productos: fila {idx} sin name ni sku, saltada: {row}")
            continue
        name_lc = name_raw.strip().lower() if name_raw else ""

        product: Product | None = None
        if sku_raw and sku_raw in by_sku:
            product = by_sku[sku_raw]
        elif name_lc and name_lc in by_name:
            product = by_name[name_lc]
        else:
            warnings.append(
                f"Productos: {name_raw or sku_raw!r} no encontrado en DB "
                f"(sin auto-create); editá un producto existente"
            )
            continue

        # Update only fields present in the row.
        if row.get("sale_price_gs") not in (None, ""):
            new_price = _money_int_gs(
                row.get("sale_price_gs"),
                field_name=f"Productos[{name_raw or sku_raw}].sale_price_gs",
                warnings=warnings,
            )
            if new_price is not None:
                product.sale_price_gs = new_price

        notes_in = _opt_str(row.get("notes"))
        if notes_in is not None:
            product.notes = notes_in

        portion_label = _opt_str(row.get("portion_label"))
        if portion_label is not None:
            product.portion_label = portion_label or "1 unidad"

        result.products += 1


def _import_patch_clientes(session: Session, wb, result: ImportResult) -> None:
    """PATCH Clientes: match by phone. Update or create."""
    warnings = result.warnings
    by_phone = _customer_lookup(session)
    sheet = _sheet(wb, "Clientes")
    if sheet is None:
        return
    rows = _rows(sheet)
    seen_phones: set[str] = set()

    for idx, row in enumerate(rows, start=2):
        phone = _opt_str(row.get("phone"))
        name = _opt_str(row.get("name"))
        if not phone:
            warnings.append(f"Clientes: fila {idx} sin phone, saltada: {row}")
            continue
        if phone in seen_phones:
            warnings.append(
                f"Clientes: phone={phone!r} aparece duplicado en el archivo, "
                f"solo se procesa el primero"
            )
            continue
        seen_phones.add(phone)

        email = _opt_str(row.get("email"))
        cedula = _opt_str(row.get("cedula"))
        notes = _opt_str(row.get("notes"))

        existing = by_phone.get(phone)
        if existing is not None:
            if name is not None:
                existing.name = name
            if email is not None:
                existing.email = email
            if cedula is not None:
                existing.cedula = cedula
            if notes is not None:
                existing.notes = notes
            existing.updated_at = datetime.utcnow()
        else:
            if not name:
                warnings.append(
                    f"Clientes: phone={phone!r} nuevo pero sin name, saltada: {row}"
                )
                continue
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

        result.customers += 1


def _import_patch_ingredientes(session: Session, wb, result: ImportResult) -> None:
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
                ing.purchase_price_updated_at = datetime.utcnow()

        lt_v = row.get("lead_time_days")
        if lt_v not in (None, ""):
            new_lt = _opt_int(lt_v)
            if new_lt is not None and new_lt >= 0:
                ing.lead_time_days = new_lt

        notes_v = _opt_str(row.get("notes"))
        if notes_v is not None:
            ing.notes = notes_v

        result.ingredients += 1


def _import_patch_recetas(session: Session, wb, result: ImportResult) -> None:
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


def _import_patch(session: Session, wb, result: ImportResult) -> None:
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
) -> ImportResult:
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
    warnings: list[str] = []
    result = ImportResult(
        batch_id=-1, source_filename=path.name, mode=str(mode), warnings=warnings
    )

    if str(mode).upper() == "PATCH":
        _import_patch(session, wb, result)
    else:
        _import_full(session, wb, result)

    batch = ImportBatch(
        imported_at=datetime.now(),
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
    wb,
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
        imported_at=datetime.now(),
        source_filename=source_filename,
        note=f"mode={mode}",
        row_counts_json=result.row_counts(),
    )
    session.add(batch)
    session.flush()
    result.batch_id = batch.id
    session.commit()
    return result


__all__ = ["from_file", "from_workbook", "ImportResult", "ImportMode"]
