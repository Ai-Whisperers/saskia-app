# Sazón — Complete Image & Asset Plan (2026-09-27)

**Current state:** Recipe + Product models have `image_url` fields. **7 of 20 recipes** have photos (uploaded via the set-photo feature). **0 of 28 products** have images. **Ingredients have no image field at all.** Icon sprite has 38 symbols. No og/social images, no empty-state illustrations, no login branding beyond favicon.

---

## A. Entity photos (the big one — 108 items)

### A1. Product photos — 28 needed (0 have one)
Highest-value assets: products face the customer (future menu/QR). Recommended: square 800×800 JPG/WebP, neutral background, shot on the counter.

| # | Product | Shot notes |
|---|---------|-----------|
| 1 | Muffin de vainilla | single muffin + crumb |
| 2 | Muffin de chocolate | glaze visible |
| 3 | Muffin de nueces | nut pieces on top |
| 4 | Docena muffins vainilla | box of 12 |
| 5 | Docena muffins chocolate | box of 12 |
| 6 | Cheesecake clásico | one slice, fork |
| 7 | Cheesecake entera | whole cake, 8-portion mark |
| 8 | Hojaldre dulce | sugar dust |
| 9 | Docena hojaldres | tray |
| 10 | Appeltaart | slice showing apple lattice |
| 11 | Tompoezen | cross-section cream |
| 12 | Docena tompoezen | tray |
| 13 | Oliebollen (unidad) | powdered sugar |
| 14 | Docena oliebollen | bag/box |
| 15 | Babka de chocolate | swirl slice |
| 16 | Stroopwafel | stacked pair, syrup pull |
| 17 | Docena stroopwafels | stack |
| 18 | Pan lactal | loaf + slice |
| 19 | Facturas (docena) | assorted tray |
| 20 | Facturas (media docena) | half tray |
| 21 | Brownie espresso | square, espresso cup beside |
| 22 | Chocolate Muffin (20x20) | full tray cut |
| 23 | Cheesecake (20x20 cm) | sheet cut |
| 24 | Stroop Waffle | (reuse #16 if same item) |
| 25 | Ontbijtkoek | sliced loaf |
| 26 | Carrot Cake | slice showing carrot/nuts |
| 27 | Frikandel (100 pcs) | portion on paper |
| 28 | Ketjap Manis (Quick) | bottle + brush |

**Shortcut:** products 22–28 map 1:1 to recipes 14–20 — one photo per recipe can serve both (code: fall back to recipe image when product has none → small template change, worth doing).

### A2. Recipe photos — 13 missing (7 have photos)
muffin_vainilla, muffin_chocolate, muffin_nueces, cheesecake, hojaldre_dulce, appeltaart, tompoezen, oliebollen, babka, stroopwafel, pan_lactal, facturas, brownie_espresso — **process shots** (mixing, proofing, baked batch) rather than product glamour shots; these are for the kitchen, not the customer.

### A3. Ingredient photos — 60 items, **schema change required**
Ingredient model has NO `image_url` column (migration 55). Recommendation: **do NOT photograph all 60.** Instead:
- Photograph ~15 hero ingredients (flours, manteca, queso crema, chocolate cobertura, nueces, frutillas, frutos secos display bins)
- For the rest: **category-based fallback tile** (harinas/frutas/lácteos/especias…) — 12 tiles cover everything
- Where shown: inventario list `Más info` disclosure + ingredient detail header (small 64px thumb, never bloating rows)

---

## B. UI chrome assets (page by page)

| Page | Asset needed | Priority |
|------|-------------|----------|
| **Login** | Brand wordmark/logo (SVG, 2 variants: light/dark), subtle hero background or bakery illustration | HIGH — first thing everyone sees |
| **Base/all** | 192px `apple-touch-icon.png`, `manifest.webmanifest` + 192/512 maskable icons, `og-image.png` (1200×630) for link sharing | HIGH, cheap |
| **Empty states (25 templates)** | 3–4 reusable SVG illustrations (empty box, empty tray, no-data chart, empty cart) tinted with CSS `currentColor` | MED |
| **Error pages (4xx/5xx)** | 1 illustration (burnt croissant — on-brand humor) | LOW |
| **Inicio/dashboard** | KPI sparkline already CSS; optional hero banner photo of the bakery counter (1 wide 1600×400 WebP) | LOW |
| **Pedido board (KDS)** | None needed (density page) | — |
| **Recetas index/detail** | Fallback tile when `image_url` empty (batter bowl SVG placeholder — currently raw broken layout risk) | MED |
| **Productos index** | 28px category thumb column once A1 lands + "sin foto" placeholder tile | MED (after A1) |
| **Ventas POS** | Product thumbs inside Venta rápida tiles (32px, from A1) — big usability win for counter staff | HIGH (after A1) |
| **Cliente picker modal** | Avatar initials (already colored) — no photo needed | — |
| **Merma/waste form** | None | — |
| **Reportes/analisis** | Chart colors only, no bitmaps | — |
| **Email/WhatsApp templates** (message_template) | Header logo PNG if any customer-facing comms go out | LOW |
| **User guide** | Screenshots already exist (84 PNGs in docs/user-guide/screenshots/all-pages) — keep regenerating after big UI changes | ongoing |

## C. Icon sprite gaps (38 symbols today)
Missing and referenced by upcoming work: `icon-filter`, `icon-tag`, `icon-clock`, `icon-calendar`, `icon-print`, `icon-download`, `icon-external`, `icon-alert` (distinct from warn), `icon-offline`, `icon-sync`, `icon-scan` (barcode), `icon-qr`. Cost: ~12 inline SVG paths.

## D. Favicon/PWA
Current: favicon.ico (170 bytes — ancient) + favicon.svg. Needed: proper SVG favicon using final logo mark, apple-touch-icon, maskable PWA icons if we ever want "install to home screen" at the counter (we might — POS-as-app).

## E. Sourcing options (decision needed)
1. **the operator shoots them** (phone, daylight, white board) — authentic, free, best for food
2. **Stock/pack: freepik-style bundles** — fast, generic, license care needed
3. **AI-generated** (ComfyUI/diffusion — we have the skill) — consistent style, ~free, but "fake food" risk on a real menu
4. **Hybrid (recommended):** AI for placeholders now + swap in real photos as the operator shoots; category tiles AI-generated, entity photos real

## F. Recommended execution order
1. Logo/wordmark + favicon/PWA + og-image (branding foundation, half-day)
2. Fallback tiles + recipe placeholder + empty-state illustrations (pure code+SVG, no photos)
3. Product↔recipe image fallback (tiny template change)
4. AI-placeholder batch for 28 products → POS thumbs + productos column
5. Ingredient category tiles (+ optional migration for hero ingredient photos)
6. Real-photo swap program as photos arrive (upload UI already exists for recipes; needs one for products)
7. Sprite gap icons
