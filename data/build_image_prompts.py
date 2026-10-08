"""
data/build_image_prompts.py — Generate per-item image prompts for AI image gen.

Reads data/images/items.json, applies the La Vaquita Holandesa visual
template (docs/operations/2026-10-08-vaquita-image-template.md), and
emits data/images/prompts.jsonl — one JSON line per image with the
fields the dispatcher needs.

Usage:
    .venv/bin/python data/build_image_prompts.py
    .venv/bin/python data/build_image_prompts.py --out data/images/prompts.jsonl
    .venv/bin/python data/build_image_prompts.py --only-type product
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS_PATH = ROOT / "data" / "images" / "items.json"
OUT_PATH = ROOT / "data" / "images" / "prompts.jsonl"

# ---------------------------------------------------------------------------
# Visual template constants (from docs/operations/2026-10-08-vaquita-image-template.md)
# ---------------------------------------------------------------------------

BRAND = "La Vaquita Holandesa home bakery, Dutch heritage, Asunción Paraguay."

# Per-category visual style. Keyed on a keyword we look for in the item name.
CATEGORY_STYLES = {
    "cake": {
        "surface": "aged light-oak counter, visible grain, slight wear",
        "props": "Delft-blue ceramic plate, red gingham napkin",
        "angle": "45° three-quarter, slightly above",
        "frame": "55-70% width, single whole cake with one slice gap visible",
        "texture": "golden-brown crust, cinnamon-sugar crystals, sugar-glossy surface",
    },
    "cookie": {
        "surface": "aged light-oak counter, visible grain",
        "props": "Delft-blue cup of coffee, small paper napkin",
        "angle": "45° three-quarter, slightly above",
        "frame": "55-70% width, 1-2 cookies on a small saucer",
        "texture": "crisp imprint pattern, caramelization on the edges",
    },
    "bread": {
        "surface": "aged light-oak counter",
        "props": "linen napkin, small curl of butter",
        "angle": "45° three-quarter, slightly above",
        "frame": "55-70% width, single loaf or 2-3 slices",
        "texture": "flake layers, soft crumb interior, glossy crust",
    },
    "muffin": {
        "surface": "aged light-oak counter",
        "props": "gingham napkin, small fork",
        "angle": "45° three-quarter, slightly above",
        "frame": "55-70% width, 2-3 muffins in a row",
        "texture": "frosting drip, sugar crystals, paper liner crinkled",
    },
    "fried": {
        "surface": "dark walnut counter, visible grain",
        "props": "small paper bag, dusting of powdered sugar",
        "angle": "45° three-quarter, slightly above",
        "frame": "55-70% width, 4-6 pieces in a pyramid",
        "texture": "slight oil-gloss, sugar-dust, irregular hand-shaped forms",
    },
    "docena": {
        "surface": "aged light-oak counter",
        "props": "small Delft-blue ceramic plate, paper napkin",
        "angle": "45° three-quarter, slightly above",
        "frame": "6 in front, 6 fading into soft bokeh background",
        "texture": "see also the underlying cookie/cake/fried style",
    },
    "ingredient": {
        "surface": "aged light-oak counter",
        "props": "no extra props; a small handwritten paper label in a corner is OK",
        "angle": "3/4 angle, slightly above",
        "frame": "60% width, the container or raw item is the hero",
        "texture": "natural, untouched, no styled flour burst, packaging unbrushed",
    },
    "default": {
        "surface": "aged light-oak counter",
        "props": "Delft-blue ceramic plate, red gingham napkin",
        "angle": "45° three-quarter, slightly above",
        "frame": "55-70% width",
        "texture": "homemade, natural, just-baked",
    },
}

# Per-item REAL descriptions — sourced from the sazon seed (app/rms/seed/sazon.py)
# + Dutch heritage knowledge. Keyed on the recipe slug (which is shared between
# the base product and its package variants). This is the source of truth for
# "what is this thing" — the AI gets the description, not just the name.
ITEM_DESCRIPTIONS = {
    # Tortas (cakes)
    "babka__rec_017": "traditional Polish-Jewish sweet braided bread, ring-shaped (bundt form), dark chocolate and cinnamon filling visible in the spiral, golden-brown crust, dusted with coarse sugar",
    "bizcocho_basico_25_cm_basiscake__rec_011": "plain Dutch basiscake (sponge cake), round 25 cm, golden crust, soft pale-yellow crumb visible from the side, simple and undecorated",
    "bizcocho_basico_30_cm_basiscake__rec_012": "plain Dutch basiscake (sponge cake), round 30 cm, golden crust, soft pale-yellow crumb visible from the side, simple and undecorated",
    "torta_de_zanahoria_43x33x1_5_cm__rec_005": "rectangular carrot cake 43x33 cm, thick cream cheese frosting on top, visible orange carrot flecks in the crumb, chopped walnuts on top",
    "cheesecake_30x50__rec_002": "rectangular Dutch-style cheesecake 30x50 cm, tall (5+ cm), pale golden top with characteristic crack, graham-cracker-style crust on the bottom, no topping or fruit",
    # Pastelería (pastries)
    "muffin_de_chocolate_20x20_cm__rec_001": "single jumbo chocolate muffin in a crinkled brown paper liner, dark chocolate top with white chocolate chips visible, domed top rising above the liner, no frosting",
    "galletas_de_especuloos_speculaasjes__rec_010": "Dutch speculaas cookies, thin crisp brown spice cookies (~6-8 cm), traditional windmill or farmer shape stamped into them, deeply caramelized, slight crackle pattern",
    "hojaldre_bladerdeeg__rec_008": "Dutch puff pastry (bladerdeeg), golden flaky rectangular block cut into 4-5 visible squares, visible paper-thin lamination on the side, buttery crisp",
    "pastelitos_rosados_roze_koeken__rec_009": "Dutch roze koeken, small round pink-glazed puff pastry, flat disc shape (~8 cm), bright pink fondant icing on top, one layer visible from the side, glaze dripping slightly over the edge",
    "petisus_de_hojaldre_y_crema_tompoezen__rec_015": "Dutch tompoezen, two flat round discs of puff pastry with a tall THICK layer of pale yellow custard cream between them, dusted with powdered sugar on top",
    "proficteroles_de_den_bosch_bossche_bollen__rec_014": "Bossche bollen from Den Bosch, large round profiterole (~8 cm), split in half horizontally with a thick layer of whipped cream and chocolate glaze dripping on top, no cherry",
    "stroop_wafel__rec_003": "Dutch stroopwafel, two thin round flat waffle discs (~10 cm diameter) with a dark caramel syrup layer sandwiched between, classic deep waffle grid imprint on both faces, golden-brown edges",
    "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013": "Dutch appeltaart (moeder's appeltaart), round 25 cm, lattice pastry strips on top revealing cooked apple filling beneath, golden crust, rustic homemade look, no powdered sugar",
    "ontbijtkoek_700g_de_harina__rec_004": "Dutch ontbijtkoek (breakfast cake), dense rectangular loaf, dark brown almost mahogany color from rye and honey, sliced ~1 cm thick showing tight dark crumb, no frosting",
    "bombones_de_chocolate__rec_018": "small hand-rolled dark chocolate truffles, 4-6 round balls (~3 cm), dusted with cocoa powder, irregular hand-shaped surface, on a small Delft plate",
    # Salados (savory)
    "frikandel_100_unidades__rec_022": "Dutch frikandel, 3-4 elongated skinless minced-meat sausages (~12 cm long, ~2 cm diameter), dark brown crispy outside from deep-frying, deep golden color, no bread roll",
    "goulash_crockettes__rec_019": "Dutch kroketten, 3-4 cylindrical breaded croquettes (~6 cm long), crispy golden panko coating, oozing thick brown beef-ragout filling visible where one is bitten",
    "oliebollen_bunuelos_tradicionales_holandeses__rec_016": "Dutch oliebollen, 3-4 round irregular deep-fried dough balls (~6-8 cm), dusted heavily with powdered sugar, dark golden-brown crispy surface, no filling",
    "bitterballen_vegetariano__rec_020": "Dutch vegetarian bitterballen, 3-4 round breaded croquettes (~3-4 cm diameter), crispy golden panko coating, one bitten open showing thick brown vegetable ragout filling",
    "bitterballen__rec_006": "Dutch bitterballen, 3-4 round breaded croquettes (~3-4 cm diameter), crispy golden panko coating, one bitten open showing thick brown beef-ragout filling",
    "suppli_cacio_e_pepe__rec_021": "Italian suppli al telefono, 2-3 oval rice balls (~7 cm), crispy golden breadcrumb coating, one bitten showing stretchy mozzarella cheese pull inside, cacio e pepe flavor",
    # Especialidades
    "ketjap_manis_version_rapida__rec_007": "small glass jar of Indonesian ketjap manis (sweet soy sauce), thick dark brown syrupy liquid, no label facing camera, on aged wood",
}

# Per-name overrides / recipes
NAME_OVERRIDES = {
    "babka": "cake",
    "bizcocho": "cake",
    "cheesecake": "cake",
    "torta_de_zanahoria": "cake",
    "tarta_de_manzana": "cake",
    "muffin": "muffin",
    "stroop_wafel": "cookie",
    "stroop": "cookie",
    "tompoezen": "cake",
    "bossche_bollen": "cake",
    "oliebollen": "fried",
    "frikandel": "fried",
    "hojaldre": "bread",
    "pan_lactal": "bread",
    "appeltaart": "cake",
    "speculoos": "cookie",
    "ontbijtkoek": "bread",
    "pastelitos": "muffin",
    "bombones": "default",
    "ketjap": "default",
    "goulash": "fried",
    "suppli": "fried",
}

# Universal negative prompt (from §4 of the template) — kept short; the full
# list lives in the template doc. The MiniMax API caps prompts at 1500 chars,
# so we ship a tight version that covers the worst offenders.
NEGATIVE = (
    "flat-lay, overhead top-down, white studio backdrop, neon, dark moody, "
    "3D render, CGI, miniature, cartoon, anime, hands holding food, chef, "
    "branding facing camera, text overlay, Instagram filter, motion blur, "
    "lens flare, tilt-shift, fisheye, B&W, sepia, oversaturated, AI-glossy"
)
# Full version for reference / non-API use (ComfyUI etc. that accept longer)
NEGATIVE_FULL = (
    "aerial flat-lay infographic, overhead 90° top-down, stock photo center framing, "
    "white seamless studio backdrop, floating crumbs, neon colors, dark moody "
    "chiaroscuro, dramatic two-point studio lighting, hard flash, AI-glossy "
    "hyperrealism, 3D render, CGI, miniature toy-like, miniature figurine, "
    "claymation, stop-motion, soap opera lighting, hands holding the food, "
    "chef in background, chef hat, customer in background, branded packaging "
    "facing camera, social-media text overlay, recipe blog watermark, hard "
    "shadows, crushed blacks, oversaturated colors, Instagram filter, matte "
    "painterly, oil painting, watercolor, anime, cartoon, low-poly, isometric "
    "illustration, product mockup with price tag, label on product, sliced "
    "cross-section revealing a perfect interior, motion blur, steam, wispy "
    "effects, lens flare, tilt-shift miniature effect, fisheye distortion, "
    "extreme wide angle, strong vignette, B&W, sepia, infrared"
)


def category_for(slug: str, type_: str) -> str:
    """Pick the right visual style for this item."""
    if type_ == "ingredient":
        return "ingredient"
    # Check overrides
    for k, v in NAME_OVERRIDES.items():
        if k in slug:
            return v
    # Heuristics
    if any(s in slug for s in ("docena", "docena_", "caja_", "entera", "_entero")):
        return "docena"
    return "default"


def build_subject(item: dict) -> str:
    """Build the SUBJECT line — what the AI should draw. Kept short.

    Uses the real per-item description from ITEM_DESCRIPTIONS when available
    (keyed on the recipe slug, which is the same for the base product and
    its package variants like "docena_..." or "X_entera"). Falls back to a
    generic name-based subject if the slug isn't in the table.
    """
    name = item["name"]
    type_ = item["type"]
    slug = item["slug"]
    cat = category_for(slug, type_)

    if type_ == "ingredient":
        return f'single "{name}" in home-pantry form (1kg bag, jar, or fresh). Container muted, brand not facing camera'

    # Prefer the real description from the catalog
    recipe_slug = item.get("recipe_slug") or slug
    description = ITEM_DESCRIPTIONS.get(recipe_slug)
    if description:
        if cat == "docena":
            return f"a dozen of these, freshly baked and arranged for sale. 6 in front, 6 fading into soft bokeh. Item: {description}"
        return description

    # Fallback: name + category hint
    if cat == "docena":
        return f'a dozen of "{name}", arranged for sale: 6 in front, 6 fading into soft bokeh'
    return f'a finished "{name}" portion, ready to eat, on a small plate'


def build_prompt(item: dict) -> dict:
    """Return a dict with the full prompt structure for one item."""
    cat = category_for(item["slug"], item["type"])
    style = CATEGORY_STYLES[cat]
    subject = build_subject(item)
    aspect = item.get("aspect_ratio", "4:3")

    # Aspect-ratio guidance
    if aspect == "1:1":
        aspect_line = "1:1 square aspect ratio, 1024×1024 px, image occupies 60% of frame width"
    elif aspect == "3:2":
        aspect_line = (
            "3:2 landscape aspect ratio, 1500×1000 px, image occupies 55-70% of frame width"
        )
    else:  # 4:3 default
        aspect_line = (
            "4:3 landscape aspect ratio, 1200×900 px, image occupies 55-70% of frame width"
        )

    # The big prompt — must stay under 1500 chars for MiniMax image-01.
    # Full template with all rules lives in
    # docs/operations/2026-10-08-vaquita-image-template.md.
    full_prompt = f"""{item["type"].upper()} image for {BRAND}

SUBJECT: {subject}.

SURFACE: {style["surface"]}. BG: soft-bokeh home-kitchen hint, f/2.0-2.8 lived-in kitchen in blur. No studio sweep.
LIGHT: single warm window ~4500K, camera-left at ~30°, warm cast shadow camera-right. No flash, no rig.
PROPS: {style["props"]}. No people, hands, chef, or branding.
TEXTURE: {style["texture"]}.
ANGLE: {style["angle"]}. FRAME: {style["frame"]}.
ASPECT: {aspect_line}.
COLOR: warm, slightly desaturated (-10%), wood/cream/brown + Delft-blue accent. No filter, no oversaturation.
MOOD: homemade, lived-in, just-baked.
STYLE: photoreal, f/2.5, mild film grain, no AI-gloss, no CGI, no miniature.
NEGATIVE: {NEGATIVE}."""

    return {
        "id": item["id"],
        "slug": item["slug"],
        "name": item["name"],
        "type": item["type"],
        "category": cat,
        "aspect_ratio": aspect,
        "size_px": item.get("size_px", "1200x900"),
        "outputs": item["outputs"],
        "prompt": full_prompt.strip(),
        "negative_prompt": NEGATIVE,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT_PATH))
    parser.add_argument("--only-type", choices=["product", "ingredient"], default=None)
    parser.add_argument("--only-slug", default=None, help="single item by slug (for testing)")
    args = parser.parse_args()

    if not ITEMS_PATH.exists():
        sys.exit(f"missing {ITEMS_PATH} — run the items builder first")

    items = json.loads(ITEMS_PATH.read_text())
    if args.only_type:
        items = [i for i in items if i["type"] == args.only_type]
    if args.only_slug:
        items = [i for i in items if i["slug"] == args.only_slug]
        if not items:
            sys.exit(f"no item with slug={args.only_slug!r}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Skip variant products (they reuse the base image)
    items = [i for i in items if i.get("outputs")]
    with out_path.open("w") as f:
        for item in items:
            row = build_prompt(item)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(items)} prompts to {out_path}")


if __name__ == "__main__":
    main()
