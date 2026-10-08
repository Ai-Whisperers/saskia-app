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
    "flat-lay, overhead top-down, white seamless studio backdrop, neon, "
    "dark moody, 3D render, CGI, miniature, cartoon, anime, hands holding food, "
    "chef in background, branded packaging facing camera, text overlay, "
    "Instagram filter, motion blur, lens flare, tilt-shift, fisheye, B&W, sepia, "
    "perfect cross-section reveal, oversaturated, AI-glossy"
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
    """Build the SUBJECT line — what the AI should draw. Kept short."""
    name = item["name"]
    type_ = item["type"]
    slug = item["slug"]
    cat = category_for(slug, type_)

    if type_ == "ingredient":
        return f'single "{name}" in home-pantry form (1kg bag, jar, or fresh). Container muted, brand not facing camera'

    if cat == "docena":
        return f'a "{name}" arranged for sale: 6 in front, 6 fading into soft bokeh'

    # Default product subject — use display name, not slug
    display = item.get("name", slug)
    return f'a finished "{display}" portion, ready to eat, on a small plate'


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
        aspect_line = "3:2 landscape aspect ratio, 1500×1000 px, image occupies 55-70% of frame width"
    else:  # 4:3 default
        aspect_line = "4:3 landscape aspect ratio, 1200×900 px, image occupies 55-70% of frame width"

    # The big prompt — must stay under 1500 chars for MiniMax image-01.
    # Full template with all rules lives in
    # docs/operations/2026-10-08-vaquita-image-template.md.
    full_prompt = f"""{item['type'].upper()} image for {BRAND}

SUBJECT: {subject}.

SURFACE: {style['surface']}. BG: soft-bokeh home-kitchen hint, f/2.0-2.8 lived-in kitchen in blur. No studio sweep.
LIGHT: single warm window ~4500K, camera-left at ~30°, warm cast shadow camera-right. No flash, no rig.
PROPS: {style['props']}. No people, hands, chef, or branding.
TEXTURE: {style['texture']}.
ANGLE: {style['angle']}. FRAME: {style['frame']}. Some crumbs/sugar-dust is GOOD.
ASPECT: {aspect_line}.
COLOR: warm, slightly desaturated (-10%), wood/cream/brown + Delft-blue accent. No filter, no oversaturation.
MOOD: homemade, warm, just-baked, lived-in. Not studio, not Michelin.
STYLE: photoreal, f/2.0-2.8, mild ISO-400-800 film grain, no AI-gloss, no CGI, no miniature, no cartoon.
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
