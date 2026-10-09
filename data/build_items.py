"""
data/build_items.py — Build the canonical items.json from the sazon seed.

Reads the real product names + categories + recipe slugs from
app/rms/seed/sazon.py (PRODUCTS block), and the ingredients from
data/herebus_seed_canonical.json (inventory). Produces
data/images/items.json with 3 types of items:
  - product::base       (22 items, 1 per recipe, has recipe_slug)
  - product::variant    (9 items, package variants that reuse the base image)
  - ingredient          (94 items, from the workbook inventory)

Each product::base item carries its `recipe_slug` so the prompt builder
can look up its real description from ITEM_DESCRIPTIONS.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "app" / "rms" / "seed" / "sazon.py"
INGREDIENTS = ROOT / "data" / "herebus_seed_canonical.json"
OUT_PATH = ROOT / "data" / "images" / "items.json"


def parse_products() -> list[dict]:
    """Parse the PRODUCTS tuple list from the seed.

    Rules:
    - Skip rows where the "name" is a number/quantity or "libre" (Venta libre)
    - Detect package variants by DUPLICATE recipe_slug (e.g. Babka entera
      and Babka both share babka__rec_017; the first one is the base).
    """
    src = SEED.read_text()
    m = re.search(r"PRODUCTS:\s*list\[tuple\]\s*=\s*\[(.*?)\n\s*\]", src, re.DOTALL)
    if not m:
        sys.exit("PRODUCTS block not found in seed")
    block = m.group(1)

    products = []
    seen_recipes: set[str] = set()
    depth, start = 0, None
    for i, ch in enumerate(block):
        if ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                tup_src = block[start : i + 1]
                strs = re.findall(r'"([^"]+)"', tup_src)
                if len(strs) >= 5:
                    name = strs[0]
                    recipe_slug = strs[1]
                    sku = strs[5] if len(strs) > 5 else ""
                    category = strs[4]
                    # Skip rows where the "name" looks like a number/quantity
                    # or the recipe_slug doesn't look like a real slug
                    if not name or name[0].isdigit() or "libre" in name.lower():
                        continue
                    is_variant = recipe_slug in seen_recipes
                    seen_recipes.add(recipe_slug)
                    products.append(
                        {
                            "name": name,
                            "recipe_slug": recipe_slug,
                            "unit": strs[2],
                            "price_gs": strs[3],
                            "category": category,
                            "sku": sku,
                            "is_variant": is_variant,
                        }
                    )
    return products


def parse_ingredients() -> list[dict]:
    """Get the canonical 94 ingredients from the workbook's inventory."""
    if not INGREDIENTS.exists():
        sys.exit(f"missing {INGREDIENTS}")
    canonical = json.loads(INGREDIENTS.read_text())
    inv = canonical.get("inventory", [])
    if not inv or not isinstance(inv, list):
        sys.exit(f"inventory missing from {INGREDIENTS}")
    return [
        {
            "ing_id": x.get("ing_id"),
            "slug": re.sub(r"[^a-z0-9]+", "_", x.get("name", "").lower()).strip("_"),
            "name": x.get("name"),
            "grupo": x.get("grupo"),
            "pkg_qty": x.get("pkg_qty"),
            "pkg_unit": x.get("pkg_unit"),
        }
        for x in inv
    ]


def slug_from_name(name: str) -> str:
    """'Babka' -> 'babka', 'Bizcocho b\u00e1sico 25 cm' -> 'bizcocho_basico_25_cm'."""
    import unicodedata

    clean = re.sub(r"\s*\([^)]*\)", "", name).strip()
    clean = unicodedata.normalize("NFKD", clean)
    clean = "".join(c for c in clean if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", clean.lower()).strip("_")


def main():
    products = parse_products()
    ingredients = parse_ingredients()
    print(f"Parsed {len(products)} products, {len(ingredients)} ingredients")

    items = []

    # 1. Products
    for p in products:
        slug = slug_from_name(p["name"])
        item = {
            "id": f"product::{slug}",
            "slug": slug,
            "name": p["name"],
            "type": "product",
            "category": p["category"],
            "recipe_slug": p["recipe_slug"],
            "unit": p["unit"],
            "price_gs": p["price_gs"],
            "sku": p["sku"],
            "is_variant": p["is_variant"],
            "aspect_ratio": "4:3",
            "size_px": "1200x900",
        }
        if p["is_variant"]:
            item["outputs"] = []  # Variants reuse the base image
        else:
            item["outputs"] = [
                {"path": f"app/static/products/{slug}.jpg"},
                {"path": f"app/static/recipes/receta-{slug}.jpg"},
            ]
        items.append(item)

    # 2. Ingredients
    for ing in ingredients:
        items.append(
            {
                "id": f"ingredient::{ing['slug']}",
                "slug": ing["slug"],
                "name": ing["name"],
                "type": "ingredient",
                "category": ing.get("grupo"),
                "ing_id": ing.get("ing_id"),
                "aspect_ratio": "1:1",
                "size_px": "1024x1024",
                "outputs": [{"path": f"app/static/ingredients/{ing['slug']}.jpg"}],
            }
        )

    # Write
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(items, indent=2, ensure_ascii=False))

    bases = [i for i in items if i["type"] == "product" and not i["is_variant"]]
    variants = [i for i in items if i["type"] == "product" and i["is_variant"]]
    ings = [i for i in items if i["type"] == "ingredient"]
    print(f"Wrote {len(items)} items to {OUT_PATH}")
    print(f"  - {len(bases)} base products (image generated)")
    print(f"  - {len(variants)} package variants (reuse base image, no separate gen)")
    print(f"  - {len(ings)} ingredients (image generated)")
    print(f"  - TOTAL images to generate: {len(bases) + len(ings)}")
    print(
        f"  - TOTAL jpg files published: "
        f"{len(bases) * 2 + len(ings)} (2 per base product + ingredients)"
    )


if __name__ == "__main__":
    main()
