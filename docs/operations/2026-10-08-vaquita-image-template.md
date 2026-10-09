# La Vaquita Holandesa — Product & Ingredient Image Template

**For AI image generation of products, recipes, and ingredients.**
Use this template for every image you ask an AI image model to generate. Following the template keeps the catalog visually consistent so products look like they belong together on the menu, in the catalog, in delivery photos, and in printed/PDF collateral.

> **Authoring rule:** the same template applies to products, recipes, and ingredients. The only thing that changes is the **subject** (product = finished dish / final cake; recipe = the bake-in-progress or styled hero of the same dish; ingredient = single raw item styled as if just unpacked on a counter).

---

## 1. Brand identity (read this first)

### Business
- **Name:** La Vaquita Holandesa
- **Type:** home bakery, 1 person (Saskia is the baker)
- **Home/bakery:** same place — it IS her house kitchen
- **Heritage:** Dutch parents, Paraguayan-based
- **Category overlap:** Dutch classics (appeltaart, stroopwafel, oliebollen, tompoezen, speculaas, babka) × Guaraní/Paraguayan ingredients (chipa, mbejú, cocido) × everyday panadería (facturas, muffins, pan lactal)
- **Voice:** homemade, warm, sincere, no-pretension. "Hecho en casa, con cariño."

### Mood keywords (use in every prompt)
`homemade`, `artisan`, `warm`, `sincere`, `kitchen-counter`, `wooden table`, `soft natural light`, `cinnamon dust`, `buttery`, `just-baked`, `lived-in kitchen`, `no styled studio`.

### Mood keywords (AVOID)
`plated restaurant`, `molecular gastronomy`, `neon`, `dark moody`, `white seamless backdrop with floating crumbs`, `AI-glossy`, `3D render`, `miniature`, `toy-like`, `stock-photo smiley chef`, `overhead flat-lay infographic`.

### Brand colors (La Vaquita, not Sazón the SaaS)
The **Sazón app shell** uses #3248FF deep purple / #FF6A1A warm orange — those are product UI colors, NOT client brand colors.

La Vaquita brand is **warm and earthy**:
- **Primary warm (accent):** Dutch-tile blue `#1B4D8E` (Delft blue) — used in logo accents
- **Secondary warm:** brick red `#A23E2A` (Hollandse bakkerij awning)
- **Cream / dough white:** `#F5E9D3` (off-white flour dust)
- **Brown crust:** `#7A4A1F` (cinnamon-bun crust)
- **Sazon-shell accent (UI buttons, NOT photos):** `#FF6A1A`

Use these in image generation for the **baking accent props** (a small Delft-blue plate, a red gingham napkin, a small brick-red tin), but keep the food itself the natural color it should be.

---

## 2. Scene composition template

Every image follows the same 5-element recipe:

| Element | Rule |
|---|---|
| **Subject (the food)** | Centered, occupies 55-70% of frame width. 1 portion or 1 batch visible. NEVER a full 12-bun batch unless the product IS a dozen. |
| **Surface** | Aged **light wood counter** OR **dark walnut wood** (alternate by category: light wood for sweet/cake, dark wood for chocolate/bread). Visible wood grain, slight wear, no scratches deeper than time. |
| **Background** | Soft, blurred home-kitchen hint at bokeh: a stove edge, a tile splashback, a tea-towel hanging, a wooden shelf with mason jars. NEVER a clean wall, NEVER a studio sweep. bokeh must be soft, f/2.0–2.8 look. |
| **Light** | **Single warm window light from camera-left at ~30°** (morning kitchen light, ~4500K). Soft fill from bounced light. NO flash, NO two-point studio rig, NO sunlight on the food. Cast shadow goes camera-right. |
| **Props (2-4 max)** | One of: Delft-blue ceramic plate • red gingham napkin • wooden rolling pin (partially in frame) • small bunch of wheat • a single cinnamon stick • a Dutch-tin cookie tin • parchment paper w/ dusting of flour • a small Delft-blue coffee cup with steam. NO more than 3 props, NO novelty items, NO branding stickers, NO social-media text on props. |

### Color/tonal target
- **White balance:** warm (4500K, not 5500K daylight)
- **Saturation:** natural, slightly desaturated (the food should look real, not Instagram-filtered). `-10% saturation` mental rule.
- **Contrast:** medium-low. NO crushed blacks. Shadows should read as warm brown, not gray.
- **Grain:** very mild film grain (ISO 400–800 look) to break any AI glossiness.
- **Sharpness:** subject tack sharp, background 100% bokeh.

### Aspect ratio
Two master formats:
- **Product image (catalog, menu tablet):** **4:3 landscape, 1200×900 px**, JPEG quality 85. The product image is wide enough to read on the menu tablet (1280×720 landscape) and crops well into a 1:1 thumbnail.
- **Recipe hero (recipe detail page):** **3:2 landscape, 1500×1000 px**, JPEG quality 85. Wider, more storytelling, shows the bake-in-process.

### Background hex (for AI image generators that need an exact bg)
- Wood surface: `#A07F5A` to `#7A5832` (range, not flat color)
- Bokeh blob: `#E8DCC4` (cream) or `#3A2E20` (dark walnut bokeh)

---

## 3. Per-subject style rules

### 3.1 PRODUCTS (the dish the customer buys)

**Goal:** "I'm about to eat this right now."

- **Framing:** 45° three-quarter angle, slightly above the food. Eye-level is reserved for drinks and stacks (e.g. muffins, oliebollen).
- **Quantity visible:** 1 piece for whole cakes/tarts (with a knife-served wedge gap optional), 1 stroopwafel on a saucer, 2-3 muffins in a row, 6 oliebollen in a pyramid. If the product is "docena X" (dozen), show 6 in front and 6 fading into bokeh.
- **Texture priority:** surface crispiness / syrupy glaze / sugar-dust / flake layers MUST read. If you can't see the texture, the image failed.
- **Props allowed:** one plate + one napkin + (optional) one cup. NO more.
- **People:** NEVER. No hands, no arms, no background customers.

**Anti-patterns to avoid:**
- ❌ Aerial 90° flat-lay (looks like a Pinterest infographic, not a bakery)
- ❌ Centered perfectly in frame with negative space around (looks like a stock photo)
- ❌ A single product on a huge empty white plate (looks like Michelin plating, not home bakery)
- ❌ Steam/motion blur (looks AI-generated)

### 3.2 RECIPES (the bake-in-process hero, used in recipe detail page)

**Goal:** "I can see how this is made."

- **Framing:** 50/50 split between ingredients-in-bowl AND finished product. Show both.
- **Style:** 30° angle, slightly wider shot than product. More props allowed (rolling pin, dough scraper, bowl, flour, mixer arm).
- **Storytelling:** the eye should travel: bowl of dough → hand-shaped item → finished plate. If the recipe has a signature step (filling the stroopwafel, dusting cinnamon, glazing the babka), that step should be in the foreground.
- **Quantity visible:** enough to show technique, not a full batch. 3-4 appeltaart shells, 1 open babka loaf, 6 oliebollen in oil + 6 in a paper bag.
- **Props allowed:** up to 4. Bowl + rolling pin + flour cloth + raw ingredient.

**Anti-patterns:**
- ❌ A finished product that looks identical to the product image (defeats the point)
- ❌ A perfectly clean countertop (looks like a TV cooking set, not a home kitchen)
- ❌ A recipe that hides the technique (e.g. babka shot that doesn't show the chocolate swirl)

### 3.3 INGREDIENTS (raw material, used in shopping list and recipe inputs)

**Goal:** "This is what I buy, this is what I open."

- **Framing:** 3/4 angle, slightly above. Object occupies 60% of frame. Container (bag, jar, head of garlic, etc.) must be the SUBJECT, not a prop.
- **Quantity visible:** the natural "single unit of shopping" — 1 kg bag of flour, 1 head of garlic, 1 dozen eggs in a Delft-blue bowl, 1 stick of butter on parchment, 1 bottle of milk, 1 jar of honey, 1 block of chocolate.
- **Style:** clean but warm. NO messy flour burst. The ingredient is the hero, not a chaotic still-life.
- **Props allowed:** the surface only. No extra props. A small handwritten price tag or paper label in a corner is OK for context ("Harina 0000" written in cursive on brown paper).
- **No people, no hands, no kitchen activity.**

**Anti-patterns:**
- ❌ A market-stall flat-lay with multiple unrelated items
- ❌ An ingredient with the brand logo facing camera (looks like a commercial)
- ❌ A "styled" ingredient with weird angle or sliced open to show inside (looks AI-fake)

---

## 4. The universal negative prompt (paste this into every AI image request)

```
Aerial flat-lay infographic, overhead 90° top-down, stock photo center framing,
white seamless studio backdrop, floating crumbs, neon colors, dark moody
chiaroscuro, dramatic two-point studio lighting, hard flash, AI-glossy
hyperrealism, 3D render, CGI, miniature toy-like, miniature figurine,
claymation, stop-motion, soap opera lighting, hands holding the food,
chef in background, chef hat, customer in background, branded packaging
facing camera, social-media text overlay, recipe blog watermark, hard
shadows, crushed blacks, oversaturated colors, Instagram filter, matte
painterly, oil painting, watercolor, anime, cartoon, low-poly, isometric
illustration, product mockup with price tag, label on product, sliced
cross-section revealing a "perfect" interior, motion blur, steam, wispy
effects, lens flare, tilt-shift miniature effect, fisheye distortion,
extreme wide angle, strong vignette, B&W, sepia, infrared
```

---

## 5. Subject cheat sheet (use this for any item not in the seed)

| Category | Use surface | Use prop palette | Notes |
|---|---|---|---|
| Sweet cakes (appeltaart, cheesecake, babka) | Light wood | Delft-blue plate + gingham napkin | Cake at 45°, single slice gap optional |
| Dutch cookies (stroopwafel, speculaas) | Light wood | Delft-blue cup of coffee + napkin | Show texture of the imprint |
| Fried dough (oliebollen, appelflappen) | Dark wood | Paper bag w/ powder sugar dust | Slight oil-gloss, no greasiness |
| Breads (pan lactal, hojaldre, facturas) | Light wood | Linen napkin + butter curl | Show flake/crumb texture |
| Frosted (muffins, cupcake-style) | Light wood | Gingham napkin + small fork | Show frosting drip / sugar crystals |
| Ingredients | Light wood | Surface only + optional paper label | Container faces camera, brand muted |

---

## 6. File-naming convention (already used in the repo)

- Product: `app/static/products/<slug>.jpg` where slug is the product slug (e.g. `appeltaart.jpg`, `docena-stroopwafels.jpg`)
- Recipe: `app/static/recipes/receta-<slug>.jpg` (e.g. `receta-appeltaart.jpg`)
- Ingredient: `app/static/ingredients/<slug>.jpg` (new convention; not yet used in code — see §8)

---

## 7. Per-image generation brief template

Copy-paste this block per item, fill in the bracketed parts, send to the AI image generator. Use the same master brief across all 130+ items so the look is uniform.

```
[PRODUCT / RECIPE / INGREDIENT] image for La Vaquita Holandesa home bakery.

SUBJECT: [exact name and quantity, e.g. "one whole Dutch appeltaart (apple pie) in a glass pie dish, 23 cm diameter, lattice top, no slice removed"]
SURFACE: [light wood / dark walnut] aged counter, visible grain, slight wear.
BACKGROUND: soft-bokeh home kitchen hint, [Delft tile splashback / wooden shelf with mason jars], warm morning light from camera-left.
LIGHTING: single warm window light, 4500K, from camera-left at 30° angle; soft fill; warm cast shadow camera-right.
PROPS (max 3): [Delft-blue ceramic plate / red gingham napkin / wooden rolling pin / etc.]. NO novelty, NO people, NO hands.
TEXTURE EMPHASIS: [e.g. "lattice pastry golden-brown, cinnamon-sugar crystals visible, glossy sugar glaze"].
ANGLE: 45° three-quarter, slightly above the food.
FRAME: subject occupies 55-70% width. Some crumbs/dust on surface is GOOD (homemade).
ASPECT RATIO: [4:3 1200×900 / 3:2 1500×1000].
COLOR: warm, slightly desaturated, no filter, no oversaturation. Wood/cream/brown palette.
MOOD: homemade, warm, sincere, just-baked, lived-in kitchen, not styled.
PEOPLE: zero. Hands: zero. Chef: zero.
STYLE: photoreal, f/2.0-2.8 look, mild film grain (ISO 400-800), no AI glossiness, no CGI.
NEGATIVE: aerial flat-lay, white seamless backdrop, floating crumbs, neon, dark moody, 3D render, hands, chef, branded packaging, text overlay, motion blur, lens flare, tilt-shift, fisheye, B&W, sepia, cartoon, anime, watercolor.
```

---

## 8. Implementation notes (for Iván to action)

1. **Image generator:** use the studio-quality model available to you (e.g. Imagen 4, Flux 1.1 Pro, or Recraft v3) at the highest fidelity setting. Generate 4 candidates per item, pick the one that best matches the brief.
2. **Post-processing:** no extra filter. Light crop to 4:3 or 3:2, save as JPEG q85. Optionally apply a very mild `-5 saturation` LUT to keep the catalog consistent.
3. **A/B test:** generate the stroopwafel product image FIRST using the template. If it doesn't read as "homemade Dutch bakery next door", adjust the brief and retry before generating the other 129.
4. **Coverage plan (from the current seed):**
   - **20 products** (existing slugs in `app/static/products/`)
   - **13 recipes** (existing slugs in `app/static/recipes/`)
   - **94 ingredients** (NEW — `app/static/ingredients/` directory; need to add the route/field for the seed to actually use them, see PR follow-up)
   - **7 packaging items** (boxes, ribbons, paper bags — defer; low priority for menu display)
5. **Upload path:** current code uses `app/static/products/<file>` and `app/static/recipes/<file>`. Ingredients are NOT yet rendered with images anywhere in the UI — the template is ready for when the ingredient image field is added.

---

## 9. Reference photos already in the repo (for style grounding)

These already follow the desired style and should be the visual benchmark when prompting the AI:

- `app/static/products/stroopwafel.jpg` — top-down white bg, golden, single subject, crumbs around. **ALMOST matches** but the white seamless background is too clean — needs the wood surface instead.
- `app/static/products/babka-chocolate.jpg` — chocolate babka in a loaf pan, dark background, glossy syrup. **MATCHES** the desired style almost exactly.
- `app/static/recipes/receta-appeltaart.jpg` — overhead view of the finished pie in a glass dish on a wooden table. **MATCHES** but the angle is too aerial — should be 45° instead.

Use these three as your "yes this is the look" anchors when comparing AI candidates.

---

## 10. Token efficiency note

Each image will consume 1-2 generation credits at the model used. 127 product/recipe/ingredient items × 4 candidates = ~500 credits. The brief above is designed to get a usable image on the **first** attempt for most items, so most items will need only 1-2 candidates. Budget accordingly.
