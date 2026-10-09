"""Generate new seeder data for sazon.py from the HEREBUS canonical JSON."""

import json
import os
import re
import sys

WT = "/opt/data/profiles/ivan/cache/scratch/saskia-workbook-reconcile"
os.chdir(WT)


def to_float(x: object) -> float:
    """Tolerant float: accepts numbers, '2kg', '5,5', '-', None."""
    if x in (None, "", 0):
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return 0.0
    m = re.match(r"^([\d.,]+)", s)
    return float(m.group(1).replace(",", ".")) if m else 0.0


def to_grams(qty: object, unit: str) -> tuple[float, str]:
    n = to_float(qty)
    if unit == "kg":
        return n, "kg"
    if unit == "g":
        return n / 1000.0, "kg"
    if unit == "l":
        return n, "l"
    if unit == "ml":
        return n / 1000.0, "l"
    if unit == "und":
        return n, "und"
    return n if n > 0 else 1.0, unit or "kg"


# Load canonical workbook data
with open("data/herebus_seed_canonical.json") as f:
    canon = json.load(f)

inv = canon["inventory"]
recipes = canon["recipes"]


def infer_storage(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("leche", "crema", "queso", "huevo", "manteca")):
        return "refrigerated"
    if any(k in n for k in ("congelad", "masa congelada", "fruta congelada")):
        return "frozen"
    if any(k in n for k in ("harina", "azúcar", "sal", "cacao", "levadura", "polvo")):
        return "dry"
    if any(k in n for k in ("frutilla", "fruta", "banana", "limón", "naranja")):
        return "fresh"
    if any(k in n for k in ("aceite", "vainilla", "esencia", "vinagre", "salsa", "ketjap")):
        return "ambient"
    return "dry"


_ALLERGEN_MAP = [
    (
        "gluten",
        [
            "harina",
            "trigo",
            "centeno",
            "patentada",
            "pan rallado",
            "bizcocho",
            "galleta",
            "pastelitos",
        ],
    ),
    ("leche", ["leche", "crema", "manteca", "queso", "yogur", "suero", "nata"]),
    ("huevo", ["huevo"]),
    ("nueces", ["nuez moscada", "almendra", "avellana"]),
    ("soja", ["soja", "ketjap"]),
    ("mostaza", ["mostaza"]),
]

_DIETARY_VEGAN = [
    "fruta",
    "verdura",
    "harina",
    "azúcar",
    "aceite",
    "sal",
    "vinagre",
    "levadura",
    "garbanzo",
    "mango",
    "pasas",
    "frutilla",
    "manzana",
    "frambuesa",
    "pimentón",
    "perejil",
    "tomillo",
    "jengibre",
    "anis",
]
_MEAT = [
    "pechuga",
    "panceta",
    "bola de lomo",
    "carnaza",
    "falda",
    "carne",
    "pollo",
    "cerdo",
    "jamón",
    "mortadela",
]
_DAIRY_EGG = ["leche", "crema", "huevo", "queso", "manteca", "yogur"]


def infer_allergens(name: str) -> str:
    n = name.lower()
    found = []
    for tag, kws in _ALLERGEN_MAP:
        if any(k in n for k in kws):
            found.append(tag)
    return ",".join(found) if found else ""


def infer_dietary(name) -> str | None:
    n = name.lower()
    if any(k in n for k in _MEAT):
        return None
    if any(k in n for k in _DAIRY_EGG) or "huevo" in n:
        return "vegetariano"
    if any(k in n for k in _DIETARY_VEGAN):
        return "vegano"
    return "vegetariano"


def default_shelf_days(grupo: str, name: str) -> int:
    if "Lácteos" in grupo or "huevos" in name.lower():
        return 14
    if "Carnes" in grupo:
        return 7
    if "Frutas" in grupo or "Verduras" in grupo:
        return 10
    return 90


def pick_supplier_idx(grupo: str, name: str) -> int:
    g = grupo.lower()
    if "harina" in g:
        return 0
    if "lácteos" in g or "huevo" in g.lower():
        return 1
    if "frutas" in g or "verduras" in g or "carnes" in g or "especias" in g:
        return 2
    if "endulzantes" in g or "café" in g or "cacao" in g or "chocolate" in name.lower():
        return 3
    return 0


# ────────────────────────────────────────────────────────────────────
# Compile INGREDIENTS (94)
# ────────────────────────────────────────────────────────────────────
def build_ingredient_tuple(ing: dict) -> tuple:
    ing["ing_id"]
    name = ing["name"]
    grupo = ing["grupo"]
    pkg_qty = to_float(ing["pkg_qty"])
    pkg_unit = ing["pkg_unit"] or "kg"
    bulk_price = to_float(ing["bulk_price"])
    stock = to_float(ing["stock_qty"])

    base_qty, base_unit = to_grams(pkg_qty, pkg_unit)
    unit_for_db = base_unit

    price_per_unit = round(bulk_price / base_qty, 0) if (bulk_price and base_qty > 0) else 0

    package_size = base_qty if base_qty > 0 else 1.0
    package_unit = base_unit
    package_price = bulk_price if bulk_price else 0

    storage = infer_storage(name)
    shelf_days = default_shelf_days(grupo, name)

    stock_qty = round(stock / 1000.0, 3) if pkg_unit == "g" else stock
    min_stock = max(0.5, round(stock * 0.1, 2))

    allergens = infer_allergens(name)
    dietary = infer_dietary(name)
    supplier_idx = pick_supplier_idx(grupo, name)

    water_aw = 0.45 if storage == "dry" else (0.85 if "fruta" in name.lower() else 0.7)
    humidity_max = 70 if storage == "dry" else (40 if storage == "refrigerated" else 80)
    temp_min = -18 if storage == "frozen" else (0 if storage == "refrigerated" else 10)
    temp_max = 4 if storage == "refrigerated" else (-12 if storage == "frozen" else 25)

    return (
        name,
        unit_for_db,
        float(stock_qty),
        int(price_per_unit) if price_per_unit > 0 else 0,
        float(min_stock),
        int(shelf_days),
        storage,
        grupo.lower(),
        allergens,
        dietary,
        int(supplier_idx),
        float(package_size),
        package_unit,
        int(package_price) if package_price > 0 else 0,
        False,
        ("gluten" in allergens),
        float(water_aw),
        int(humidity_max),
        int(temp_min),
        int(temp_max),
    )


ingredients_out = []
ing_name_by_id = {}
for ing in inv:
    tup = build_ingredient_tuple(ing)
    if tup[0] in ing_name_by_id.values():
        print(f"  WARN dup-ingredient: {tup[0]}", file=sys.stderr)
        continue
    ingredients_out.append(tup)
    ing_name_by_id[ing["ing_id"]] = tup[0]


# ────────────────────────────────────────────────────────────────────
# Compile RECIPES (22)
# ────────────────────────────────────────────────────────────────────
def slugify(name: str) -> str:
    s = name.lower()
    repl = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
    for k, v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# Note: slugs must uniquely identify recipes — the workbook has two with
# the same name-level slug ("Petisus de hojaldre y crema Tompoezen" and
# anything else); we keep rec_id-suffixed slugs to avoid mapping issues.
YIELD_ESTIMATES = {
    "REC-001": (12, "und", "Muffin de chocolate — 12 und estándar (molde 20x20 cm)"),
    "REC-002": (170, "g", "Cheesecake 30x50 → ~170 porciones de 27g"),
    "REC-003": (12, "und", "Stroop wafel — 12 und"),
    "REC-004": (12, "und", "Ontbijtkoek 700g harina → ~12 und"),
    "REC-005": (24, "und", "Torta de zanahoria 43x33x1.5cm → 24 und"),
    "REC-006": (100, "und", "bitterballen — 100 und"),
    "REC-007": (250, "ml", "Ketjap manis — 250 ml rinde base"),
    "REC-008": (8, "und", "Hojaldre (Bladerdeeg) — 8 und"),
    "REC-009": (12, "und", "Pastelitos rosados (Roze koeken) — 12 und"),
    "REC-010": (40, "und", "Galletas de especuloos — 40 und"),
    "REC-011": (12, "und", "Bizcocho básico 25 cm — 12 porciones"),
    "REC-012": (16, "und", "Bizcocho básico 30 cm — 16 porciones"),
    "REC-013": (12, "und", "Tarta de manzana — 12 und"),
    "REC-014": (12, "und", "Proficteroles Den Bosch — 12 und"),
    "REC-015": (12, "und", "Petisús (Tompoezen) — 12 und"),
    "REC-016": (24, "und", "Oliebollen — 24 und"),
    "REC-017": (10, "und", "Babka — 10 und"),
    "REC-018": (20, "und", "Bombones de chocolate — 20 und"),
    "REC-019": (100, "und", "goulash crockettes — 100 und"),
    "REC-020": (100, "und", "bitterballen vegetariano — 100 und"),
    "REC-021": (12, "und", "suppli cacio e pepe — 12 und"),
    "REC-022": (100, "und", "Frikandel — 100 und"),
}


def remap_rec_id(rec_id: str, sheet: str) -> str:
    """Fix workbook's duplicate REC-006 (Frikandel gets bumped to REC-022)."""
    if rec_id == "REC-006" and sheet == "Recipe_Frikandel_100_pcs":
        return "REC-022"
    return rec_id


_PREP_COOK = {
    "muffin": (15, 25, 1),
    "cheesecake": (20, 60, 3),
    "babka": (40, 40, 3),
    "hojaldre": (60, 25, 4),
    "stroop": (20, 12, 2),
    "wafel": (20, 12, 2),
    "appeltaart": (35, 50, 2),
    "tompoezen": (60, 25, 3),
    "petisus": (60, 25, 3),
    "oliebollen": (20, 6, 2),
    "buñuelo": (20, 6, 2),
    "pastelitos": (45, 22, 3),
    "rosados": (45, 22, 3),
    "especuloos": (30, 14, 2),
    "speculaas": (30, 14, 2),
    "ontbijtkoek": (15, 60, 1),
    "bizcocho": (15, 30, 1),
    "torta": (20, 40, 2),
    "zanahoria": (20, 40, 2),
    "mazana": (35, 50, 2),
    "manzana": (35, 50, 2),
    "profic": (60, 25, 4),
    "bossche": (60, 25, 4),
    "bombones": (30, 0, 3),
    "chocolate": (30, 0, 3),
    "bitterbal": (45, 0, 4),
    "frikandel": (45, 0, 4),
    "goulash": (45, 0, 4),
    "crocket": (45, 0, 4),
    "suppli": (30, 6, 3),
    "ketjap": (5, 45, 1),
    "manis": (5, 45, 1),
}


def guess_prep_cook(name: str) -> tuple[str, str]:
    n = name.lower()
    for kw, vals in _PREP_COOK.items():
        if kw in n:
            return vals
    return (30, 30, 2)


_MEAT_REC = {"frikandel": None, "goulash": None, "bitterbal": None, "suppli": "vegetariano"}

recipes_out = []
recipes_lines_out = []

for rec in recipes:
    rec_id_orig = rec["rec_id"]
    rec_id = remap_rec_id(rec_id_orig, rec["sheet"])
    rec_name = rec["rec_name"]
    if not rec_id or not rec_name:
        print(f"  SKIP recipe no id/name: {rec.get('sheet')}", file=sys.stderr)
        continue

    yq = rec["yield_qty"]
    yu = (rec["yield_unit"] or "").lower()
    if not yq:
        est = YIELD_ESTIMATES.get(rec_id)
        if est:
            yq, yu, _ = est
        else:
            yq, yu = 1, "und"

    yield_qty = float(yq)
    # Map yield_unit variants to the 5 allowed values: g, kg, ml, l, und
    _UNIT_MAP = {
        "und": "und",
        "unidad": "und",
        "unidades": "und",
        "u": "und",
        "un": "und",
        "unid": "und",
        "porcion": "und",
        "porciones": "und",
        "porción": "und",
        "porciones ": "und",
        "g": "g",
        "gr": "g",
        "gramo": "g",
        "gramos": "g",
        "kg": "kg",
        "kilo": "kg",
        "kilos": "kg",
        "kilogramo": "kg",
        "kilogramos": "kg",
        "ml": "ml",
        "mililitro": "ml",
        "mililitros": "ml",
        "l": "l",
        "lt": "l",
        "litro": "l",
        "litros": "l",
    }
    yield_unit = _UNIT_MAP.get(yu.strip(), "und" if yield_qty else "g")

    prep, cook, diff = guess_prep_cook(rec_name)

    n_low = rec_name.lower()
    slug_base = slugify(rec_name)
    # Tag slug with rec_id for safety against slug collisions across recs
    # (e.g. "Tarta de manzana" would clash if workbook had another). For
    # this workbook, no collisions exist but we suffix to be future-proof.
    slug = f"{slug_base}__{rec_id.lower().replace('-', '_')}"

    # Pick dietary hint by name keyword
    dietary = "vegetariano"
    for kw, val in _MEAT_REC.items():
        if kw in n_low:
            dietary = val
            break

    notes_text = (
        f"Heredado del workbook (id {rec_id_orig}). "
        f"Rinde estimada — el operador ajusta B4 después de hornear."
    )

    recipes_out.append(
        (
            slug,
            yield_qty,
            yield_unit,
            prep,
            cook,
            diff,
            "",  # family — auto-classified at seed time
            "",  # menu_tags
            dietary,
            notes_text,
        )
    )

    # Recipe lines
    for line in rec["ingredients"]:
        ing_id = line["ing_ref"]
        ing_name = ing_name_by_id.get(ing_id)
        if not ing_name:
            print(f"  MISSING ing ref {ing_id} in {rec_name}", file=sys.stderr)
            continue
        qty = to_float(line["qty"])
        if qty is None or qty <= 0:
            # Workbook has rows for empty quantity cells (intentional or not).
            # Recipe line constraint requires qty > 0, so skip these.
            continue
        unit = (line["unit"] or "g").lower()
        if unit == "g":
            qty_norm, unit_norm = qty / 1000.0, "kg"
        elif unit == "ml":
            qty_norm, unit_norm = qty / 1000.0, "l"
        else:
            qty_norm, unit_norm = qty, unit
        recipes_lines_out.append((slug, ing_name, qty_norm, unit_norm, None))


# ────────────────────────────────────────────────────────────────────
# Compile PRODUCTS
# ────────────────────────────────────────────────────────────────────
def pick_category(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("bitterbal", "frikandel", "goulash", "suppli")):
        return "Salados"
    if "ketjap" in n:
        return "Especiales"
    if any(k in n for k in ("torta", "cheesecake", "babka")):
        return "Tortas"
    if "muffin" in n or "galleta" in n or "bizcocho" in n or "speculaas" in n:
        return "Panadería"
    if any(k in n for k in ("hojaldre", "tompoezen", "petisus", "stroop", "wafel")):
        return "Pastelería"
    if any(k in n for k in ("oliebollen", "buñuelo", "pastelitos", "bombones")):
        return "Especiales"
    return "Panadería"


def sku_cat(cat: str) -> str:
    return {
        "Panadería": "PA",
        "Pastelería": "PS",
        "Salados": "SA",
        "Bebidas": "BE",
        "Especiales": "ES",
        "Tortas": "TO",
    }[cat]


# Price points (retail single-unit, Gs) - Sazon's seed uses round thousands
_PRICE = {
    "muffin": 8000,
    "cheesecake": 16000,
    "babka": 12000,
    "hojaldre": 7000,
    "stroop": 6000,
    "wafel": 6000,
    "appeltaart": 22000,
    "mazana": 22000,
    "manzana": 22000,
    "tompoezen": 6000,
    "petisus": 6000,
    "oliebollen": 4000,
    "buñuelo": 4000,
    "pastelitos": 5000,
    "rosados": 5000,
    "especuloos": 3000,
    "speculaas": 3000,
    "ontbijtkoek": 8000,
    "bizcocho": 14000,
    "torta": 14000,
    "zanahoria": 15000,
    "profic": 9000,
    "bossche": 9000,
    "bombones": 15000,
    "chocolate": 15000,
    "bitterbal": 3000,
    "frikandel": 3000,
    "goulash": 3000,
    "crocket": 3000,
    "suppli": 4000,
    "ketjap": 12000,
    "manis": 12000,
}


def price_for_recipe(name: str) -> int:
    n = name.lower()
    for kw, base in _PRICE.items():
        if kw in n:
            return base
    return 10000


products_out = []
product_names_indexed = []
seen_names = set()

# slug_to_rec_name mapping
slug_to_rec_name = {}
for (slug, *_), rec in zip(recipes_out, recipes, strict=False):
    # find name by rec_id
    slug_to_rec_name[slug] = rec["rec_name"]


for i, recipe_tuple in enumerate(recipes_out):
    slug = recipe_tuple[0]
    rec_name = slug_to_rec_name.get(slug, slug.replace("__", " - ").replace("_", " ").title())
    cat = pick_category(rec_name)
    base_price = price_for_recipe(rec_name)
    sku = f"{sku_cat(cat)}{i + 1:03d}-U"

    products_out.append(
        (
            rec_name,
            slug,
            "1 unidad",
            base_price,
            cat,
            sku,
            "10",
            None,
            True,  # default favorite
            None,
            None,
            None,
        )
    )
    product_names_indexed.append(rec_name)
    seen_names.add(rec_name)


# Bulk variants (Docena X, Bizcocho entero, Cheesecake entera, Babka entera, Caja bombones)
# These reference recipe names AFTER the canonical-JSON renames (Spanish lead).
_BULK_VARIANTS = [
    ("Babka", "Babka entera", 110000),
    ("Cheesecake (30x50)", "Cheesecake entera", 140000),
    ("Stroop wafel", "Docena gofres de sirope", 60000),
    ("Petisús de hojaldre y crema (Tompoezen)", "Docena petisús", 60000),
    ("Oliebollen (Buñuelos tradicionales holandeses)", "Docena buñuelos", 40000),
    ("Bizcocho básico 25 cm (Basiscake)", "Bizcocho 25 cm entero", 130000),
    ("Bizcocho básico 30 cm (Basiscake)", "Bizcocho 30 cm entero", 160000),
    ("Bombones de chocolate", "Caja bombones", 15000),
    ("Muffin de chocolate (20x20 cm)", "Docena muffins chocolate", 75000),
]

for rec_name, bulk_name, price in _BULK_VARIANTS:
    if bulk_name in seen_names:
        continue
    slug = next((s for s, n in slug_to_rec_name.items() if n == rec_name), None)
    if not slug:
        print(f"  BULK: recipe '{rec_name}' slug not found", file=sys.stderr)
        continue
    cat = pick_category(rec_name)
    products_out.append(
        (
            bulk_name,
            slug,
            "Lote completo",
            price,
            cat,
            f"{sku_cat(cat)}{len(products_out) + 1:03d}-L",
            "10",
            None,
            False,
            None,
            None,
            None,
        )
    )
    product_names_indexed.append(bulk_name)
    seen_names.add(bulk_name)


# Venta libre
products_out.append(
    (
        "Venta libre",
        None,
        "1 unidad",
        0,
        "Especiales",
        "VAR-001",
        "10",
        None,
        False,
        None,
        None,
        "Venta libre — definí el precio en el carrito.",
    )
)
product_names_indexed.append("Venta libre")


idx_of = {n: i for i, n in enumerate(product_names_indexed)}
print(f"PRODUCTS: {len(products_out)}")
print(f"PRODUCT names sample: {product_names_indexed[:6]}")

# ────────────────────────────────────────────────────────────────────
# BENCHMARKS
# ────────────────────────────────────────────────────────────────────
BENCHMARKS = [
    ("Muffin de chocolate (20x20 cm)", 5500, 8500, 9500, 7500),
    ("Docena muffins chocolate", 55000, 85000, 88000, 75000),
    ("Cheesecake (30x50)", 14000, 25000, 26000, 20000),
    ("Cheesecake entera", 130000, 220000, 210000, 170000),
    ("Stroop wafel", 4500, 7000, 8000, 5500),
    ("Docena gofres de sirope", 55000, 85000, 88000, 75000),
    ("Hojaldre (Bladerdeeg)", 6000, 8500, 9000, 7000),
    ("Tarta de manzana de mi madre (Mijn moeders appeltaart)", 14000, 22000, 23000, 18000),
    ("Petisús de hojaldre y crema (Tompoezen)", 5000, 7500, 8000, 6000),
    ("Docena petisús", 50000, 75000, 80000, 60000),
    ("Oliebollen (Buñuelos tradicionales holandeses)", 3500, 5500, 5500, 4000),
    ("Docena buñuelos", 35000, 55000, 55000, 40000),
    ("Babka", 12000, 18000, 17000, 14000),
    ("Babka entera", 100000, 150000, 140000, 110000),
    ("Bizcocho 25 cm entero", 120000, 180000, 170000, 140000),
    ("Bizcocho 30 cm entero", 150000, 220000, 210000, 170000),
]


# ────────────────────────────────────────────────────────────────────
# PRODUCTION_TEMPLATES (using product indexes)
# ────────────────────────────────────────────────────────────────────
def pidx(name: str) -> int:
    if name in idx_of:
        return idx_of[name]
    return -1


PRODUCTION_TEMPLATES = [
    (0, pidx("Muffin de chocolate (20x20 cm)"), 24, "Lunes base"),
    (0, pidx("Petisús de hojaldre y crema (Tompoezen)"), 12, None),
    (0, pidx("Babka"), 6, "Lunes base"),
    (1, pidx("Muffin de chocolate (20x20 cm)"), 18, "Martes"),
    (1, pidx("Stroop wafel"), 12, None),
    (1, pidx("Babka"), 8, None),
    (2, pidx("Muffin de chocolate (20x20 cm)"), 24, "Miércoles"),
    (2, pidx("Stroop wafel"), 12, None),
    (2, pidx("Babka"), 8, None),
    (3, pidx("Muffin de chocolate (20x20 cm)"), 30, "Jueves popular"),
    (3, pidx("Cheesecake (30x50)"), 18, None),
    (3, pidx("Tarta de manzana de mi madre (Mijn moeders appeltaart)"), 10, None),
    (4, pidx("Muffin de chocolate (20x20 cm)"), 36, "Viernes — día pico"),
    (4, pidx("Cheesecake (30x50)"), 24, "Viernes — día pico"),
    (4, pidx("Stroop wafel"), 12, None),
    (4, pidx("Petisús de hojaldre y crema (Tompoezen)"), 12, "Petisú fin de semana"),
    (5, pidx("Muffin de chocolate (20x20 cm)"), 24, "Sábado"),
    (5, pidx("Cheesecake (30x50)"), 18, None),
    (5, pidx("Oliebollen (Buñuelos tradicionales holandeses)"), 12, None),
    (6, pidx("Muffin de chocolate (20x20 cm)"), 18, "Domingo"),
    (6, pidx("Babka"), 4, None),
]
PRODUCTION_TEMPLATES = [(wd, p, q, n) for (wd, p, q, n) in PRODUCTION_TEMPLATES if p >= 0]
print(f"PRODUCTION_TEMPLATES: {len(PRODUCTION_TEMPLATES)}")

# ────────────────────────────────────────────────────────────────────
# PEDIDOS (using new product names)
# ────────────────────────────────────────────────────────────────────
PEDIDOS_RAW = [
    (
        0,
        -30,
        10,
        0,
        "fulfilled",
        "efectivo",
        0,
        "Cliente habitual, viernes",
        [("Muffin de chocolate (20x20 cm)", 6), ("Docena gofres de sirope", 1)],
    ),
    (
        1,
        -28,
        14,
        30,
        "fulfilled",
        "transferencia",
        1,
        "Pedido con factura",
        [("Cheesecake entera", 1)],
    ),
    (2, -21, 9, 0, "fulfilled", "efectivo", 0, None, [("Cheesecake (30x50)", 6)]),
    (5, -14, 16, 0, "fulfilled", "efectivo", 0, "Cliente celíaca", [("Cheesecake entera", 1)]),
    (6, -7, 11, 0, "fulfilled", "tarjeta", 0, "Factura con RUC", [("Babka", 2)]),
    (8, -5, 8, 30, "fulfilled", "efectivo", 0, "Para la oficina", [("Hojaldre (Bladerdeeg)", 4)]),
    (
        2,
        -2,
        10,
        30,
        "fulfilled",
        "tarjeta",
        0,
        "Ya retirado",
        [("Petisús de hojaldre y crema (Tompoezen)", 2)],
    ),
    (
        4,
        -1,
        15,
        0,
        "ready",
        "efectivo",
        1,
        "Llamó por WhatsApp. Listo para retirar.",
        [("Muffin de chocolate (20x20 cm)", 6)],
    ),
    (
        9,
        0,
        11,
        0,
        "ready",
        "transferencia",
        1,
        "Opciones vegetarianas",
        [("Tarta de manzana de mi madre (Mijn moeders appeltaart)", 1)],
    ),
    (
        12,
        0,
        18,
        0,
        "confirmed",
        "transferencia",
        1,
        "Para evento mañana a las 20h",
        [("Cheesecake entera", 1)],
    ),
    (
        11,
        1,
        9,
        0,
        "confirmed",
        "efectivo",
        0,
        "Pedido diario",
        [("Muffin de chocolate (20x20 cm)", 12)],
    ),
    (
        13,
        2,
        16,
        0,
        "pending",
        "efectivo",
        3,
        "Llamó por teléfono. Para lunes 16h.",
        [("Docena gofres de sirope", 1)],
    ),
    (
        10,
        1,
        14,
        0,
        "pending",
        "efectivo",
        0,
        "Vino a la tienda a preguntar",
        [("Docena galletas de especias", 1)],
    ),
    (
        7,
        1,
        11,
        0,
        "confirmed",
        "transferencia",
        1,
        "Decorada con flores",
        [("Cheesecake entera", 1)],
    ),
]

# Filter
PEDIDOS = []
for cust_idx, d_ago, hr, mn, st, pay, ch, notes, lines in PEDIDOS_RAW:
    valid = [(pn, q) for pn, q in lines if pn in idx_of and q > 0]
    if valid:
        PEDIDOS.append((cust_idx, d_ago, hr, mn, st, pay, ch, notes, valid))
print(f"PEDIDOS (after prod filter): {len(PEDIDOS)}")

# ────────────────────────────────────────────────────────────────────
# WASTE_LOG
# ────────────────────────────────────────────────────────────────────
existing_ing_names = {t[0] for t in ingredients_out}
WASTE_LOG_RAW = [
    ("Leche", 0.5, "vencimiento", 12, "lucia", "Caja próxima a vencer"),
    ("Frutilla congelada", 0.3, "descongelado", 8, "diego", "Descongelada por corte eléctrico"),
    ("Manteca", 0.2, "mal_estado", 5, "lucia", "Rancio"),
    ("Huevos", 6, "rotura", 4, "saskia", "Caja rota al recibir del proveedor"),
    ("Harina de trigo", 0.5, "derrame", 2, "diego", "Bolsa rota"),
    ("Queso crema", 0.3, "vencimiento", 1, "saskia", "Una vez abierto dura poco"),
    ("Chocolate", 0.2, "mal_estado", 15, "lucia", "Bolsa mal cerrada"),
    ("Leche condensada", 0.4, "mal_estado", 20, "saskia", "Lata hinchada"),
]
WASTE_LOG = [w for w in WASTE_LOG_RAW if w[0] in existing_ing_names]
print(f"WASTE_LOG (after ing filter): {len(WASTE_LOG)}")

# Production completions product list
PROD_COMPLETION_PRODUCTS_RAW = [
    "Muffin de chocolate (20x20 cm)",
    "Cheesecake (30x50)",
    "Petisús de hojaldre y crema (Tompoezen)",
    "Babka",
    "Stroop wafel",
    "Tarta de manzana de mi madre (Mijn moeders appeltaart)",
    "Babka entera",
    "Cheesecake entera",
]
PROD_COMPLETION_PRODUCTS = [p for p in PROD_COMPLETION_PRODUCTS_RAW if p in idx_of]
print(f"PROD_COMPLETION_PRODUCTS: {len(PROD_COMPLETION_PRODUCTS)}")


# ────────────────────────────────────────────────────────────────────
# Render as Python code snippets
# ────────────────────────────────────────────────────────────────────
def render_tuple_lines(
    name_decl: str, out_list: list[tuple], comment: str = "AUTO-GENERATED", per_tuple: bool = True
) -> list[str]:
    """Render a list of tuples as a python snippet. Uses double quotes + trailing commas to match the existing sazon.py style."""
    lines = [f"# {comment}", name_decl + " = ["]
    if per_tuple:
        for t in out_list:
            lines.append("    (")
            for _j, v in enumerate(t):
                v_repr = repr(v).replace("'", chr(34))  # match existing double-quote style
                # Add trailing comma to every line including the last (existing style has `25,`)
                lines.append(f"        {v_repr},")
            lines.append("    ),")
    else:
        for t in out_list:
            lines.append(f"    {t!r},")
    lines.append("]")
    return "\n".join(lines)


os.makedirs("data/seed_pieces", exist_ok=True)

# Write pieces
with open("data/seed_pieces/ingredients.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED from data/herebus.xlsx — 94 ingredients\n")
    f.write("# Patch target: app/rms/seed/sazon.py INGREDIENTS section (lines 476-1682)\n")
    f.write(
        render_tuple_lines(
            "INGREDIENTS",
            ingredients_out,
            comment=f"# {len(ingredients_out)} ingredients (one per workbook row)",
            per_tuple=True,
        )
    )

with open("data/seed_pieces/recipes.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED — 22 recipes keyed by slug\n")
    f.write(
        render_tuple_lines(
            "RECIPES",
            recipes_out,
            comment=f"# {len(recipes_out)} recipes from workbook",
        )
    )

with open("data/seed_pieces/recipe_lines.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED — recipe ingredient lines\n")
    cur_slug = None
    body_lines = [
        "# AUTO-GENERATED",
        "RECIPE_LINES: list[tuple[str, str, float, str, str | None]] = [",
    ]
    for slug, ing, qty, unit, notes in recipes_lines_out:
        if slug != cur_slug:
            cur_slug = slug
            body_lines.append(f"    # === {slug} ===")
        body_lines.append(
            f"    ({repr(slug).replace(chr(39), chr(34))}, {repr(ing).replace(chr(39), chr(34))}, {qty}, {repr(unit).replace(chr(39), chr(34))}, None),"
        )
    body_lines.append("]")
    f.write("\n".join(body_lines))

with open("data/seed_pieces/products.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED — products derived from kept recipes\n")
    f.write(
        render_tuple_lines(
            "PRODUCTS",
            products_out,
            comment=f"# {len(products_out)} products",
        )
    )

with open("data/seed_pieces/benchmarks.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED — market benchmarks\n")
    body = ["BENCHMARKS: list[tuple[str, int, int, int, int]] = ["]
    for t in BENCHMARKS:
        body.append(f"    {t!r},")
    body.append("]")
    f.write("\n".join(body))

with open("data/seed_pieces/pedidos.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED — pedidos with new product names\n")
    body = ["PEDIDOS: list[tuple] = ["]
    for t in PEDIDOS:
        body.append(f"    {t!r},")
    body.append("]")
    f.write("\n".join(body))

with open("data/seed_pieces/production_templates.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED — production templates using new product indexes\n")
    body = ["PRODUCTION_TEMPLATES: list[tuple[int, int, float, str | None]] = ["]
    for t in PRODUCTION_TEMPLATES:
        body.append(f"    {t!r},")
    body.append("]")
    f.write("\n".join(body))

with open("data/seed_pieces/waste_log.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED — waste log filtered to workbook ingredients\n")
    body = ["WASTE_LOG: list[tuple[str, float, str, int, str, str | None]] = ["]
    for t in WASTE_LOG:
        body.append(f"    {t!r},")
    body.append("]")
    f.write("\n".join(body))

with open("data/seed_pieces/prod_completion_products.py", "w", encoding="utf-8") as f:
    f.write("# AUTO-GENERATED — products tracked daily in production_completion loop\n")
    f.write("PROD_COMPLETION_PRODUCTS = " + repr(PROD_COMPLETION_PRODUCTS))

print("\nPieces generated:")
for p in sorted(os.listdir("data/seed_pieces")):
    size = os.path.getsize(f"data/seed_pieces/{p}")
    nlines = sum(1 for _ in open(f"data/seed_pieces/{p}"))
    print(f"  {p}: {size} bytes, {nlines} lines")
