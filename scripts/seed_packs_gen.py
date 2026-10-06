#!/usr/bin/env python3
"""Generate app/rms/seed/packs.py from the staged market-research CSVs.

Input (scratch):
  sazon_pack_productos.csv        pack,categoria,producto,precio_ref_gs,fuente_precio
  sazon_pack_recetas.csv          pack,receta_de,ingrediente,cantidad,unidad
  sazon_ingredientes_maestro.csv  ingrediente,categoria,costo_ref_gs_por_unidad,unidad_base,fuente_costo

Output:
  app/rms/seed/packs.py  — PACKS dict: one La-Vaquita-grade dataset per segment
                           (ingredients w/ variants + price events, recipes + lines,
                           products w/ SKU/IVA, suppliers, production templates).
                           NOT loaded anywhere automatically: operators call
                           seed_pack(session, "Pizzería") at client onboarding.

Usage: uv run python scripts/seed_packs_gen.py
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRATCH = Path("/opt/data/profiles/ivan/scratch")
OUT = REPO / "app" / "rms" / "seed" / "packs.py"


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "_", t.lower()).strip("_")
    return re.sub(r"_+", "_", t)


def _to_int(value: str) -> int:
    try:
        return int(float(str(value).replace(",", ".").strip()))
    except ValueError:
        return 0


def _line_unit(raw: str) -> str:
    u = raw.strip().lower()
    return {"g": "kg", "ml": "l", "u": "und", "un": "und", "und": "und"}.get(u, "und")


def _to_float(value: str) -> float:
    try:
        return float(str(value).replace(",", ".").strip())
    except ValueError:
        return 0.0


def _qty(raw: str, unit: str) -> float:
    v = _to_float(raw)
    return v / 1000.0 if unit in ("g", "ml") else v  # g/ml→kg/l; und counts stay as-is


def _divisor(unit: str) -> float:
    return 1000.0 if unit in ("g", "ml") else 1.0


def main() -> None:
    prods = list(csv.DictReader(open(SCRATCH / "sazon_pack_productos.csv", encoding="utf-8")))
    lines = list(csv.DictReader(open(SCRATCH / "sazon_pack_recetas.csv", encoding="utf-8")))
    ings = list(csv.DictReader(open(SCRATCH / "sazon_ingredientes_maestro.csv", encoding="utf-8")))

    ing_cost: dict[str, tuple[int, str]] = {}
    ing_cat: dict[str, str] = {}
    for r in ings:
        name = r["ingrediente"].strip()
        ing_cost[name] = (_to_int(r["costo_ref_gs_por_unidad"]), r["unidad_base"].strip())
        ing_cat[name] = r["categoria"].strip()

    lines_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in lines:
        lines_by_key[(r["pack"].strip(), r["receta_de"].strip())].append(r)

    packs: dict[str, dict] = {}
    for p in prods:
        pack = p["pack"].strip()
        pdata = packs.setdefault(pack, {"products": [], "lines": defaultdict(list)})
        pdata["products"].append(p)

    ings_used: set[str] = set()
    for pack, pdata in packs.items():
        recipes: list[dict] = []
        for p in pdata["products"]:
            product = p["producto"].strip()
            key = (pack, product)
            rows = lines_by_key.get(key, [])
            if not rows:
                print(f"WARN: no recipe lines for {pack}/{product}", file=sys.stderr)
            slug = _slug(product)
            ing_totals: dict[str, float] = defaultdict(float)
            ing_units: dict[str, str] = {}
            for row in rows:
                ing = row["ingrediente"].strip()
                unit = row["unidad"].strip()
                ings_used.add(ing)
                ing_totals[ing] += _qty(row["cantidad"], unit)
                ing_units[ing] = _line_unit(unit)
            recipes.append(
                {
                    "slug": slug,
                    "product": product,
                    "yield_qty": 1.0,
                    "yield_unit": "und",
                    "prep": 30,
                    "cook": 20,
                    "difficulty": 2,
                    "notes": f"Receta base mercado PY 2026 — {product}",
                    "lines": [(ing, ing_totals[ing], ing_units[ing]) for ing in sorted(ing_totals)],
                }
            )
        pdata["recipes"] = recipes

    # ---- ingredients used by any pack, with paraguayan supplier buckets ----
    def supplier_for(name: str) -> int:
        if any(k in name.lower() for k in ("harina", "almidón", "almidon", "azúcar", "azucar", "sal", "levadura", "polvo", "maicena")):
            return 0
        if any(k in name.lower() for k in ("queso", "leche", "manteca", "crema", "huevo", "yogur")):
            return 1
        if any(k in name.lower() for k in ("carne", "pollo", "chorizo", "jamón", "jamon", "panceta", "lomito", "costilla")):
            return 2
        return 3

    suppliers = ["Distribuidora Secos PY", "Lácteos Central", "Frigorífico Regional", "Almacén Mayorista"]

    pack_blocks: list[str] = []
    total_ing: set[str] = set()
    for pack in sorted(packs):
        pdata = packs[pack]
        ings_used = {ing for r in pdata["recipes"] for ing, _q, _u in r["lines"]}
        total_ing |= ings_used
        ing_rows = []
        for name in sorted(ings_used & set(ing_cost)):
            cost, _unit_base = ing_cost[name]
            if cost <= 0:
                continue
            pkg = "und" if name.startswith(("Bolsa", "Caja", "Cápsula", "Vaso", "Pajita", "Film")) else "kg"
            ing_rows.append((name, ing_cat.get(name, "Otros"), cost, supplier_for(name), pkg))

        ing_tuples = "\n".join(
            f'    ("{n}", "{cat}", {c}, {si}, "{pu}"),' for n, cat, c, si, pu in ing_rows
        )
        rec_tuples = "\n".join(
            f'    ("{r["slug"]}", {r["yield_qty"]}, "{r["yield_unit"]}", {r["prep"]}, {r["cook"]}, {r["difficulty"]}, "{pack}", None, "{r["notes"]}"),'
            for r in pdata["recipes"]
        )
        line_tuples = "\n".join(
            f'    ("{r["slug"]}", "{ing}", {qty:.4f}, "{unit}"),'
            for r in pdata["recipes"]
            for ing, qty, unit in r["lines"]
            if qty > 0
        )
        cat_list = sorted({p["categoria"].strip() for p in pdata["products"]})
        prod_tuples = "\n".join(
            f'    ("{p["producto"].strip()}", "{_slug(p["producto"])}", "{p["categoria"].strip()}", {_to_int(p["precio_ref_gs"])}, "{p["fuente_precio"].strip()}"),'
            for p in pdata["products"]
        )
        fav_idx = [
            i
            for i, p in enumerate(pdata["products"])
            if i < 3
        ]
        tmpl_tuples = "\n".join(
            f"    ({wd}, {i}, {qty}, {note!r}),"
            for i in fav_idx
            for wd, qty, note in ((0, 12, "Lunes base"), (2, 12, None), (4, 18, "Viernes pico"), (5, 18, "Finde"))
        )
        block = f'''
    "{pack}": PackData(
        suppliers={suppliers!r},
        ingredients=[
{ing_tuples}
        ],
        recipes=[
{rec_tuples}
        ],
        recipe_lines=[
{line_tuples}
        ],
        products=[
{prod_tuples}
        ],
        categories={cat_list!r},
        production_templates=[
{tmpl_tuples}
        ],
    ),'''
        pack_blocks.append(block)

    header = '''"""app/rms/seed/packs.py — Seed packs per market segment ( GENERATED FILE ).

Source: scripts/seed_packs_gen.py over the staged market research CSVs
(scratch/sazon_pack_*.csv + sazon_ingredientes_maestro.csv). Do not edit by hand.

One La-Vaquita-grade dataset per segment: ingredients (with variant + price
events), recipes + lines, products (SKU/IVA), suppliers, weekly production
plan. NOT loaded anywhere automatically — operators run seed_pack() at client
onboarding:

    from app.rms.seed.packs import seed_pack
    seed_pack(session, "Pizzería")

Same idempotency contract as seed/sazon.py: existing rows matched by natural
key are reused, never duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.rms.models import (
    Category,
    Channel,
    DeliveryZone,
    Ingredient,
    IngredientPriceEvent,
    IngredientVariant,
    PaymentMethod,
    Product,
    ProductionPlanTemplate,
    Recipe,
    RecipeLine,
    Supplier,
    Tag,
    Tenant,
    User,
)
from app.rms.tagging.ensure import ensure_starter_tags
from app.rms.tagging.model import TagKind


IVA_DEFAULT = "10"


def _slug(text: str) -> str:
    """ASCII slug for tenant/sku/recipe names (same rules as generator)."""
    import re
    import unicodedata

    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "_", t.lower()).strip("_")
    return re.sub(r"_+", "_", t)


@dataclass
class PackReport:
    pack: str
    tenant: int = 0
    users: int = 0
    suppliers: int = 0
    ingredients: int = 0
    ingredient_variants: int = 0
    ingredient_price_events: int = 0
    recipes: int = 0
    recipe_lines: int = 0
    products: int = 0
    categories: int = 0
    payment_methods: int = 0
    channels: int = 0
    delivery_zones: int = 0
    production_templates: int = 0
    tags: int = 0
    skipped_existing: dict[str, int] = field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover - display helper
        parts = [f"{k}={v}" for k, v in self.__dict__.items() if k not in ("pack", "skipped_existing") and v]
        return f"PackReport({self.pack}: " + ", ".join(parts) + ")"


@dataclass
class PackData:
    suppliers: list[str]
    ingredients: list[tuple[str, str, int, int, str]]  # name, category, cost_gs, supplier_idx, package_unit
    recipes: list[tuple[str, float, str, int, int, int, str, str | None, str]]
    recipe_lines: list[tuple[str, str, float, str]]
    products: list[tuple[str, str, str, int, str]]  # name, recipe_slug, category, price_gs, price_source
    categories: list[str]
    production_templates: list[tuple[int, int, int, str | None]]

PACKS: dict[str, PackData] = {
'''

    footer = '''}


def seed_pack(session: Session, pack: str, *, tenant_name: str | None = None) -> PackReport:
    """Seed one market segment into the DB. Idempotent, mirrors seed/sazon.py."""
    from datetime import datetime, timedelta

    if pack not in PACKS:
        raise KeyError(f"pack inexistente: {pack!r}. Disponibles: {sorted(PACKS)}")
    data = PACKS[pack]
    report = PackReport(pack=pack)
    name = tenant_name or pack

    # --- tenant + operator (get-or-create) ---
    tenant = session.query(Tenant).filter(Tenant.slug == _slug(name)).one_or_none()
    if tenant is None:
        tenant = Tenant(
            slug=_slug(name),
            business_name=name,
            primary_color="#1976D2",
            currency="PYG",
            created_at=datetime.utcnow().isoformat(),
        )
        session.add(tenant)
        session.flush()
        report.tenant = 1
    user = session.query(User).filter(User.username == "admin").one_or_none()
    if user is None:
        user = User(username="admin", is_active=True, created_at=datetime.utcnow().isoformat(), last_login_at=None, role="admin")
        user.set_password("cambiar1234")
        session.add(user)
        session.flush()
        report.users = 1

    # --- suppliers ---
    supplier_objs = []
    for sname in data.suppliers:
        s = session.query(Supplier).filter(Supplier.name == sname).one_or_none()
        if s is None:
            s = Supplier(name=sname, is_active=True)
            session.add(s)
            session.flush()
            report.suppliers += 1
        supplier_objs.append(s)

    # --- ingredients (+variant +price events), full Vaquita-grade fields ---
    ing_objs: dict[str, Ingredient] = {}
    for iname, icat, cost, sidx, pkg_unit in data.ingredients:
        ing = session.query(Ingredient).filter(Ingredient.name == iname).one_or_none()
        if ing is None:
            min_stock = max(1.0, (cost or 1000) / 5000.0)
            ing = Ingredient(
                name=iname,
                unit=pkg_unit,
                stock_qty=0.0,
                purchase_price_gs=cost or None,
                purchase_price_updated_at=datetime.utcnow(),
                min_stock_qty=min_stock,
                max_stock_qty=min_stock * 3,
                shelf_life_days=None,
                storage="refrigerated" if any(k in iname.lower() for k in ("queso", "leche", "manteca", "crema", "huevo", "carne", "pollo", "jam")) else "ambient",
                notes=f"costo ref pack {pack}",
                category=icat,
                lead_time_days=3,
                supplier_id=supplier_objs[sidx].id if sidx < len(supplier_objs) else None,
                lot_required=False,
                may_contain_gluten=False,
                opening_stock_qty=0.0,
                opening_stock_date=datetime.utcnow().date().isoformat(),
                reorder_point=min_stock * 1.5,
            )
            session.add(ing)
            session.flush()
            report.ingredients += 1
            if cost > 0:
                for days_ago in (60, 30, 7):
                    session.add(
                        IngredientPriceEvent(
                            ingredient_id=ing.id,
                            price_gs=int(cost),
                            recorded_at=datetime.utcnow() - timedelta(days=days_ago),
                            source="seed-pack",
                        )
                    )
                    report.ingredient_price_events += 1
        ing_objs[iname] = ing
        if ing.id and not session.query(IngredientVariant).filter(IngredientVariant.ingredient_id == ing.id).one_or_none():
            session.add(
                IngredientVariant(
                    ingredient_id=ing.id,
                    package_size=1.0,
                    package_unit=pkg_unit,
                    purchase_price_gs=cost or None,
                    stock_qty=0.0,
                    supplier_id=supplier_objs[sidx].id if sidx < len(supplier_objs) else None,
                    preferred=True,
                    notes="Variante preferida (seed pack)",
                )
            )
            report.ingredient_variants += 1

    # --- recipes + lines ---
    rec_objs: dict[str, Recipe] = {}
    for slug, yq, yu, prep, cook, diff, family, diet, notes in data.recipes:
        rec = session.query(Recipe).filter(Recipe.name == slug).one_or_none()
        if rec is None:
            rec = Recipe(
                name=slug,
                yield_qty=yq,
                yield_unit=yu,
                prep_minutes=prep,
                cook_minutes=cook,
                difficulty=diff,
                family=family,
                dietary_tags=diet,
                notes=notes,
                yield_percentage=0.95,
                direct_labor_minutes=prep,
            )
            session.add(rec)
            session.flush()
            report.recipes += 1
        rec_objs[slug] = rec

    for slug, iname, qty, unit in data.recipe_lines:
        rec = rec_objs.get(slug)
        ing = ing_objs.get(iname)
        if rec is None or ing is None:
            continue
        exists = (
            session.query(RecipeLine)
            .filter(
                RecipeLine.recipe_id == rec.id,
                RecipeLine.line_kind == "ingredient",
                RecipeLine.line_ref_id == ing.id,
                RecipeLine.line_unit == unit,
            )
            .one_or_none()
        )
        if exists is None:
            session.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=qty, line_unit=unit))
            report.recipe_lines += 1

    # --- categories (scope=product, like sazon.py) ---
    cat_objs = {}
    for cname in data.categories:
        c = session.query(Category).filter(Category.scope == "product", Category.name == cname).one_or_none()
        if c is None:
            c = Category(name=cname, scope="product", sort_order=(len(cat_objs) + 1) * 10, is_active=True)
            session.add(c)
            session.flush()
            report.categories += 1
        cat_objs[cname] = c

    # --- payment methods + channels ---
    for sort, (code, label) in enumerate((("efectivo", "Efectivo"), ("tarjeta", "Tarjeta"), ("transferencia", "Transferencia"), ("qr", "QR")), 10):
        if not session.query(PaymentMethod).filter(PaymentMethod.code == code).one_or_none():
            session.add(PaymentMethod(code=code, label=label, sort_order=sort, is_active=True, is_default=code == "efectivo"))
            report.payment_methods += 1
    for sort, (code, label) in enumerate((("MOSTRADOR", "Mostrador"), ("WHATSAPP", "WhatsApp"), ("TELEFONO", "Teléfono")), 10):
        if not session.query(Channel).filter(Channel.code == code).one_or_none():
            session.add(Channel(code=code, label=label, sort_order=sort, is_default=code == "MOSTRADOR", is_active=True))
            report.channels += 1

    # --- delivery zones (code/name/radius_km/delivery_cost_gs) ---
    for code, zname, km, cost, min_order, mins, pos in (
        ("centro", "Zona centro", 8, 15000, 50000, 40, 10),
        ("gran-asuncion", "Gran Asunción", 15, 25000, 80000, 60, 20),
    ):
        if not session.query(DeliveryZone).filter(DeliveryZone.code == code).one_or_none():
            session.add(
                DeliveryZone(
                    code=code, name=zname, radius_km=km, delivery_cost_gs=cost,
                    min_order_gs=min_order, delivery_minutes=mins, is_active=True, position=pos,
                )
            )
            report.delivery_zones += 1

    # --- products ---
    prod_objs = []
    for pname, rslug, pcat, price, source in data.products:
        p = session.query(Product).filter(Product.name == pname).one_or_none()
        if p is None:
            p = Product(
                name=pname,
                recipe_id=rec_objs[rslug].id if rslug in rec_objs else None,
                portion_label="1 unidad",
                sale_price_gs=price,
                notes=f"precio ref: {source}",
                sku=f"{_slug(pname)[:12].upper()}-{len(prod_objs) + 1:02d}",
                is_available=True,
                category=pcat,
                iva_rate=IVA_DEFAULT,
            )
            session.add(p)
            session.flush()
            report.products += 1
        prod_objs.append(p)

    # --- tags ( Vaquita-style starter + pack tag) ---
    ensure_starter_tags(session)
    for tag_name, color in ((pack.lower(), "#1976D2"), ("precio-ref", "#FF9800")):
        t = session.query(Tag).filter(Tag.name == tag_name, Tag.kind == TagKind.PRODUCT.value).one_or_none()
        if t is None:
            session.add(Tag(name=tag_name, kind=TagKind.PRODUCT.value, color=color))
            report.tags += 1

    # --- production plan templates ---
    for wd, pidx, qty, note in data.production_templates:
        if pidx >= len(prod_objs):
            continue
        pid = prod_objs[pidx].id
        exists = (
            session.query(ProductionPlanTemplate)
            .filter(ProductionPlanTemplate.weekday == wd, ProductionPlanTemplate.product_id == pid)
            .one_or_none()
        )
        if exists is None:
            session.add(
                ProductionPlanTemplate(weekday=wd, product_id=pid, qty=qty, notes=note, updated_at=datetime.utcnow(), updated_by="seed-pack")
            )
            report.production_templates += 1

    session.commit()
    return report


def seed_pack_report(pack: str) -> str:
    data = PACKS[pack]
    return (
        f"{pack}: {len(data['products'])} productos, {len(data['recipes'])} recetas, "
        f"{len(data['recipe_lines'])} líneas, {len(data['ingredients'])} ingredientes"
    )
'''

    content = header + "\n".join(pack_blocks) + "\n" + footer
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT} ({len(content)} chars, {len(packs)} packs)")
    # self-heal formatting (import order, blank lines) so the generated file is always ruff-clean
    import subprocess

    subprocess.run(
        ["/opt/data/.local/bin/uv", "run", "ruff", "check", "--fix", str(OUT)],
        cwd=REPO, capture_output=True, text=True, timeout=60,
    )
    for pack, pdata in packs.items():
        n_lines = sum(len(r["lines"]) for r in pdata["recipes"])
        print(f"  {pack}: {len(pdata['products'])} productos / {len(pdata['recipes'])} recetas / {n_lines} líneas / {len(ings_used & set(ing_cost))} ingredientes compartidos")


if __name__ == "__main__":
    import sys

    main()
