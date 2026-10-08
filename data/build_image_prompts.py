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

# Per-item REAL descriptions — RESEARCHED from authoritative sources
# (Wikipedia, Dutch Cookbook, America's Test Kitchen, Serious Eats, and the
# Dutch/Belgian national recipe sites). Keyed on the recipe slug. This is
# the source of truth for "what does this actually look like" — the AI
# gets the description, not just the name.
ITEM_DESCRIPTIONS = {
    # ----- Tortas (cakes) -----
    # babka: NOT bundt-form (that's Polish babka). The Dutch/American Jewish
    # version is a TWISTED LOAF baked in a 9x5 inch loaf pan. Chocolate
    # filling visible as dark ribbons on the cut ends. Streusel top optional.
    "babka__rec_017": "a single tall twisted loaf of Polish-Jewish sweet bread (babka), about 9x5 inches (23x13 cm), baked in a loaf pan, dough enriched with eggs and butter, dark chocolate filling visible as dark ribbons spiraling through the pale golden dough on the cut end, top golden-brown and slightly crackled, sometimes dusted with coarse sugar or streusel. NOT bundt-form. NOT a ring. Slice one end to reveal the chocolate swirl.",

    # Basiscake: PLAIN Dutch sponge cake. Yellow crumb, no filling, no
    # decoration, no frosting. Tall cylinder. The 25cm and 30cm are
    # essentially identical except for pan diameter.
    "bizcocho_basico_25_cm_basiscake__rec_011": "a plain Dutch basiscake (sponge cake), round 25 cm diameter, simple and completely undecorated, no frosting no glaze no filling, golden-brown thin crust on the outside, soft pale-yellow airy crumb visible from the cut side, made of flour-eggs-sugar only with no butter in the batter, rises 5-6 cm tall, this is the cake other cakes are built on top of",
    "bizcocho_basico_30_cm_basiscake__rec_012": "a plain Dutch basiscake (sponge cake), round 30 cm diameter, identical to the 25cm version but wider, no frosting no glaze no filling, golden-brown thin crust, soft pale-yellow airy crumb visible on the cut side, simple homemade plain cake",

    # Bombones: hand-rolled dark chocolate truffles, 3-4cm balls, dusted
    # in cocoa powder, IRREGULAR hand-shaped surface (not perfectly round).
    "bombones_de_chocolate__rec_018": "4-6 small hand-rolled dark chocolate truffles about 3 cm diameter, irregular hand-shaped surface (not perfectly round), each one dusted all over with unsweetened cocoa powder giving them a matte dusty dark-brown look, sitting on a small Delft-blue ceramic plate, on aged wood, a few cocoa fingerprints on the wood",

    # Torta de zanahoria: 43x33cm rectangular sheet pan carrot cake.
    # Cream cheese frosting on top, carrot flecks visible in crumb, walnuts
    # on top.
    "torta_de_zanahoria_43x33x1_5_cm__rec_005": "a rectangular carrot cake baked in a 43x33 cm sheet pan, about 5-6 cm thick, the top fully covered with a thick layer of cream cheese frosting (slightly off-white), a single slice pulled forward showing orange grated carrot flecks throughout the moist dark-brown crumb, chopped walnuts scattered on top of the frosting, a knife and a small bowl of extra frosting beside the cake",

    # Cheesecake: tall NY-style. Pale golden top with characteristic crack,
    # graham cracker base, NO topping or fruit.
    "cheesecake_30x50__rec_002": "a tall rectangular Dutch-style cheesecake 30x50 cm, 5-6 cm thick, baked in a springform pan, the top is pale golden and slightly domed with the characteristic surface crack, no topping no fruit no glaze, sides smooth and creamy off-white, thin golden-brown graham-cracker-style crust visible on the bottom edge, a single slice already cut and pulled forward to show the dense creamy interior",

    # ----- Pastelería (pastries) -----
    # Muffin: JUMBO bakery style with TALL DOMED top rising above the liner.
    # The 20x20cm is the PAN size, not the muffin size.
    "muffin_de_chocolate_20x20_cm__rec_001": "a single jumbo bakery-style chocolate muffin, paper liner brown with crinkled sides, dark chocolate muffin with a TALL DOMED top rising well above the rim of the liner (about 8-9 cm total height), cracks and crinkles on the domed top, no frosting, dark chocolate chips visible on the surface, on a small white plate on aged wood",

    # Speculaas: thin, crispy, caramelized spice cookies. Often windmill or
    # person shape (speculaaspop). 4mm thick. Brown color, NOT chocolate.
    "galletas_de_especuloos_speculaasjes__rec_010": "3-4 thin crispy Dutch speculaas spice cookies, about 8-10 cm wide, only 4mm thick (very thin and crispy), golden-brown caramelized color with a darker brown rim, stamped with a traditional windmill or figure impression on top, the surface crackled and dry, scattered on a Delft-blue plate, the impression detail clearly visible, no chocolate",

    # Hojaldre / bladerdeeg: a stack of puff pastry squares showing the
    # LAMINATION on the cut side.
    "hojaldre_bladerdeeg__rec_008": "a square block of Dutch puff pastry (bladerdeeg), golden-brown with visible flaky LAMINATION layers on the side (thin paper-like sheets of butter and dough), cut into 4-5 visible small squares stacked loosely, crisp and dry surface, a few crumbs and flakes of pastry scattered on the wood, served simply on a wooden board",

    # Roze koek: round, flat, dense cake with hot-pink fondant top.
    # Similar to a black-and-white cookie but with pink icing.
    "pastelitos_rosados_roze_koeken__rec_009": "a single Dutch roze koek (pink cake), round and FLAT disc about 9 cm diameter, dense pound-cake-like base, the top fully covered with a thick layer of bright NEON hot-pink fondant icing that drips slightly down one side, the icing has a smooth glossy surface, the cake itself is only about 2-3 cm thick (FLAT), one corner of the icing bitten or showing the pale yellow cake underneath",

    # Tompoezen: RECTANGULAR 4.5x10cm. Two flat puff pastry sheets, thick
    # pale yellow pastry cream between, glossy PINK fondant on top. NOT round.
    "petisus_de_hojaldre_y_crema_tompoezen__rec_015": "a single Dutch tompouce (tompoes), RECTANGULAR shape 4.5x10 cm, two flat thin layers of golden puff pastry (no dome, no rise) with a TALL thick layer of pale yellow pastry cream sandwiched between them (the cream is as tall as the pastry is thin), the top covered with a smooth glossy layer of bright PINK fondant icing, on a small white plate, the cross-section visible from the side",

    # Bossche bollen: ~12cm tennis-ball choux puff filled with whipped
    # cream, coated ENTIRELY in dark chocolate.
    "proficteroles_de_den_bosch_bossche_bollen__rec_014": "a single large Dutch Bossche bol from Den Bosch, about 12 cm diameter (tennis-ball size), a round choux pastry puff with a thick coat of DARK chocolate covering the ENTIRE top half (and dripping down the sides), the bottom showing the baked golden choux pastry, the puff is split or already bitten to reveal a thick layer of barely-sweet whipped cream inside, no cherry, on a small white plate",

    # Stroop wafel: round, FLAT (NOT thick), waffle grid, syrup between.
    "stroop_wafel__rec_003": "two thin Dutch stroopwafels, each one a ROUND FLAT disc about 10 cm diameter, less than 1 cm thick (very thin, NOT puffy), classic deep waffle grid imprint on both faces (the squares clearly visible), golden-brown with darker caramelized edges, the two discs sandwiched together with a dark almost-black caramel syrup layer between them, on a small Delft-blue plate, on aged wood",

    # Appeltaart: TALL deep-dish, lattice top, SUGAR-COOKIE shortcrust (not
    # flaky). Cinnamon apples + raisins.
    "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013": "a Dutch appeltaart (moeder's apple pie), round 25-28 cm, very TALL deep-dish (8-10 cm high) baked in a springform pan, the crust is a thick CRUMBLY sugar-cookie-like shortcrust (not flaky, not puff), the top has a WOVEN LATTICE of pastry strips revealing the dark cinnamon-spiced apple filling underneath, golden-brown crust, the apples have shrunk during baking so the lattice is now slightly concave, served at room temperature, one slice cut and pulled forward showing the layers of soft apple and raisins inside",

    # Ontbijtkoek: dense, moist, LIGHT-BROWN (not mahogany/black) rye-honey
    # spice cake. Eaten at breakfast.
    "ontbijtkoek_700g_de_harina__rec_004": "a Dutch ontbijtkoek (breakfast cake), dense rectangular loaf about 20x10x6 cm, color is LIGHT BROWN not dark mahogany (the inside is a warm tan color from rye and honey), close moist crumb visible on the cut end, no frosting no glaze, the surface is slightly sticky from the honey and the apple syrup used in the batter, this is a BREAKFAST bread not a dessert, on a wooden cutting board",

    # ----- Salados (savory) -----
    # Frikandel: cylindrical, skinless, 20cm long x 2cm diameter, deep-fried.
    "frikandel_100_unidades__rec_022": "exactly 2 Dutch frikandellen (not a pile, not a pyramid, just 2 side by side), each one a long thin CYLINDRICAL skinless minced-meat sausage about 20 cm long and 2 cm diameter (like a fat finger), deep-fried to a dark reddish-brown crispy color on the outside, the surface is slightly irregular from deep-frying, no casing visible, served simply on a piece of butcher paper or small Delft plate, with a tiny bowl of curry ketchup or mayonnaise on the side",

    # Goulash crockettes = KROKETTEN (oblong 8-10cm x 3cm) with goulash
    # filling. Panko + double-breaded.
    "goulash_crockettes__rec_019": "2-3 Dutch kroketten (goulash filling), each one an OBLONG CYLINDER about 8-10 cm long and 3 cm diameter, double-breaded in fine panko breadcrumbs, deep-fried to a deep golden-brown crispy shell, one bitten or cut in half lengthwise to reveal the thick dark brown goulash-style beef ragout filling that almost runs out, on butcher paper, a small ramekin of mustard on the side",

    # Oliebollen: tennis-ball (6-7cm), IRREGULAR with tails, light golden
    # brown, powdered sugar. NOT perfect round, NOT dark brown.
    "oliebollen_bunuelos_tradicionales_holandeses__rec_016": "3-4 Dutch oliebollen, each one an IRREGULAR round deep-fried dough ball about 6-7 cm diameter (tennis-ball size) with characteristic wild uneven edges and small crispy TAILS sticking out (NOT perfectly round), light golden-brown color (not dark), the surface is slightly bumpy and dry, dusted heavily with powdered white sugar, served in a small paper bag or on a small white plate, a little powdered sugar spilled on the wood",

    # Bitterballen (regular beef): 3-4cm ROUND balls, panko breaded.
    "bitterballen_vegetariano__rec_020": "3-4 Dutch vegetarian bitterballen, each one a perfect ROUND ball about 3-4 cm diameter, double-breaded in fine panko breadcrumbs, deep-fried to a golden-brown crispy shell, one bitten open to reveal a thick dark brown vegetable ragout filling that almost runs out, on a small Delft-blue plate, a tiny ramekin of mustard on the side",

    "bitterballen__rec_006": "3-4 Dutch beef bitterballen, each one a perfect ROUND ball about 3-4 cm diameter, double-breaded in fine panko breadcrumbs, deep-fried to a deep golden-brown crispy shell, one bitten open to reveal a thick dark brown beef-ragout filling that almost runs out (the gooey interior is the whole point), on a small Delft-blue plate, a tiny ramekin of mustard on the side",

    # Supplì: ELONGATED OVAL (not round, not cone), 7cm long, breaded,
    # one bitten showing mozzarella cheese pull.
    "suppli_cacio_e_pepe__rec_021": "2-3 Italian Roman supplì al telefono, each one a small ELONGATED OVAL shape about 7 cm long and 3 cm thick (NOT round, NOT cone-shaped), breaded in fine breadcrumbs, deep-fried to a deep golden-brown color, one bitten or pulled apart in half to reveal the stretchy MOZZARELLA CHEESE PULL inside (the cheese should be stretching like telephone wires), on a small white plate, the cheese pull visible and dramatic",

    # ----- Especialidades -----
    # Ketjap manis: thick dark syrupy soy sauce, in jar.
    "ketjap_manis_version_rapida__rec_007": "a small glass jar of Indonesian ketjap manis (sweet soy sauce), the sauce inside is very THICK and almost black-brown (much darker than regular soy sauce), syrupy molasses-like consistency visible through the glass, the jar is plain glass with no label or a faded paper label on the back (not facing camera), sitting on aged wood, a small spoon with a drop of the sauce on it beside the jar",
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
ANGLE: {style['angle']}. FRAME: {style['frame']}.
ASPECT: {aspect_line}.
COLOR: warm, slightly desaturated (-10%), wood/cream/brown + Delft-blue accent. No filter, no oversaturation.
MOOD: homemade, lived-in, just-baked.
STYLE: photoreal, f/2.5, mild film grain, no AI-gloss, no CGI, no miniature.
NEGATIVE: {NEGATIVE}."""

    # Truncate the subject (if needed) to fit the 1500-char limit.
    # We trim from the end of the SUBJECT line first, preserving the
    # rest of the template structure intact.
    if len(full_prompt) > 1490:
        # Find the SUBJECT line and trim it
        subject_marker = f"SUBJECT: {subject}."
        # Replace long subject with a shorter form
        # (use a marker the user can see)
        target_len = 1450
        excess = len(full_prompt) - target_len
        # Truncate the subject at the closest sentence boundary before
        # the excess, then append "..." to mark the cut
        shorter_subject = subject[: max(20, len(subject) - excess - 5)]
        if "." in shorter_subject[:-10]:
            # Cut at last sentence boundary
            shorter_subject = shorter_subject.rsplit(".", 1)[0] + "."
        shorter_subject = shorter_subject.rstrip(",") + " (see template)"
        full_prompt = full_prompt.replace(
            f"SUBJECT: {subject}.",
            f"SUBJECT: {shorter_subject}.",
        )

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
