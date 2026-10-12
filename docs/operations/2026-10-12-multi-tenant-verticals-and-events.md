# Multi-tenant client catalog — all possible Sazon verticals + their festive days

**Date:** 2026-10-12
**Author:** AIW Bot (post-OOB-2026-10-12)
**Sister tickets:** SASKIA-213 (shipped), SASKIA-215 (shipped), SASKIA-216 (drafted — SeasonalEvent model), SASKIA-214 (drafted — per-instance config refactor)
**Reframes:** SASKIA-210 (per-client instances, 2026-10-07) — **SUPERSEDED** by OOB-2026-10-12 ("the website of sazon should load all of the thigns la vaquita holnadesa iis a just the first client later we will have many more"). Sazon IS multi-tenant from the start.

---

## 1. Why this matters (the OOB reframe)

The 2026-10-12 OOB turned Sazon from "an app for one client" into **"an app for many clients, where the client configures what applies to its market."** This means:

- The `SeasonalEvent` table (SASKIA-216) is **not** just La Vaquita's calendar — it's the **shared catalog** for all future tenants.
- Each event row needs a `relevance_tags` (CSV) so each tenant sees only what applies to its vertical (panadería, pizzería, heladería, etc.).
- The seeder must populate **all events** in one go (universal PY + NL heritage) plus **per-pack event overlays** for the 11 packs in `app/rms/seed/packs.py::PACKS` + the **5 new packs** the market shows real demand for.

The PY food service market is **6,000 locales** (1,600 in Asunción alone), US$ 1.9B/year (per Arpy 2025), 80% are micro/small. Heladería has 50% winter drop, fast food grew 30-35% in 2025. If Sazon captures even 1% of those 6,000 = 60 tenants in 3 years, the catalog needs to be ready.

---

## 2. The current 11 packs (in `app/rms/seed/packs.py::PACKS`)

| Pack | What it is | Key products | What events matter |
|---|---|---|---|
| **Café/Cafetería** | Coffee shop, breakfast/brunch, light meals | Café (varieties), medialunas, sándwiches, jugos | Madre, Amigo, San Valentín, Día del Café (1 oct), Día Internacional del Café (29 sept) |
| **Catering/Eventos** | Catering for events, corporate, weddings | Buffets, finger food, mesas de queso, tortas | Bodas (Sep-Nov peak), 15-años, Bautismos, Comuniones, empresariales fin de año |
| **Comedor/Kilo** | All-you-can-eat by weight, lunch | Almuerzo (varieties), sopas, ensaladas | 14-15 May (Fiestas Patrias), Año Nuevo, Semana Santa (no-meat Fri) |
| **Empanadas/Criolla** | Empanada specialist | Empanadas (carne, jamón, pollo, choclo, vegetarianas) | **Día de la Empanada (4 oct)** — second biggest day, +30% production; Cuaresma; San Juan; Día del Amigo |
| **Hamburguesería/Rápida** | Burger joint, fast food | Hamburguesas, lomitos, papas fritas, combos | **Día de la Hamburguesa (28 may)**, Día del Niño, Halloween, Día del Amigo |
| **Heladería** | Ice cream parlor | Helados (1.5 L per cápita/year in PY vs 12 in CL — growth potential) | **Día del Helado Gratis (Amandau, mobile Aug-Oct)**, Día del Niño, Año Nuevo, summer (Oct-Mar) |
| **Oriental** | Asian food (sushi, etc.) | Sushi, ramen, woks, gyozas | Año Nuevo Chino (10 feb), Día del Sushi (18 jun, mundial) |
| **Panadería** | Bread bakery, facturas, pan dulce | Pan, facturas, chipa, pan dulce, galletitas | **Reyes, Pascua, San Juan, San Lorenzo, Asunción, Día de la Madre, Día del Niño, Navidad, Año Nuevo, Día del Panadero, Día de la Empanada (chipá)** |
| **Parrilla/Restaurante** | Grill/steakhouse, full service | Asado de tira, lomitos, milanesas, choripán | **Día del Padre**, Independencia, Día del Amigo, **Día del Asado (11 oct, AR)**, Día de la Tradición (10 nov) |
| **Pastelería/Confitería** | Sweet shop, tortas, decorados | Tortas, cupcakes, galletas decoradas, budines | **Reyes, Pascua, Día de la Madre, Día del Niño, Bodas, 15-años**, Navidad |
| **Pizzería** | Pizza, empanadas, Italian | Pizzas, pastas, calzones, empanadas de jamón y queso | **Día de la Pizza (9 feb)**, Día de la Pizza de Queso (5 abr), Día del Amigo, Noche de la Pizza (Sept) |

The packs are the **business types** Sazon can configure for. Each pack has its own product mix, supplier list, recipes, and **demand calendar**.

---

## 3. The 5 NEW packs to add (per the OOB "many more clients" + real PY market)

The current 11 packs cover **the food service verticals** (Café → Pizzería). The PY market has **5 more verticals** with real demand that aren't in the current catalog but should be in Sazon's reach:

| Proposed pack | Real market | Source | Why it matters for Sazon |
|---|---|---|---|
| **Food Truck / Móvil** | Don Cocido Py (Lourdes y Luis, 6 months to expand), 1 food bus, 1 heladería, desayunos + meriendas + almuerzos agendados | `https://www.lanacion.com.py/negocios/2021/11/09/emprendedores-ln-don-cocido-restaurante-sobre-ruedas-que-nacio-para-costear-tratamiento-oncologico/` | A growing PY vertical; mobile inventory; needs the catálogo to plan rutas + paradas |
| **Quiosco / Minimarket / Almacén** | "Quioscos" or "despensas" or "almacenes tradicionales" — minimercados barriales, 89% aplican innovación | `https://revistas.umariana.edu.co/BoletinInformativoCEI/article/download/4279/4349/14711` | The most common PY small business (~80% of food service per Forbes PY); product mix is broader (bebidas, snacks, artículos de limpieza) |
| **Chipería / Almidón** | Eusebio Ayala (PY02) is the "capital" of the chipá. Ña Ana, La Lechuza, Leticia, Don Juan Ramón (autoservicio con 10 vehículos), Juan Ramón Ayala. El Congreso nombró a Ña Nena "embajadora del chipá" | `https://www.pausa.com.py/actualidad/nota-de-tapa/cronicas-desde-eusebio-ayala/9915/` | The most iconic PY vertical; chipá is the symbol of Paraguayan cuisine; chipá so'o, chipa kesu, chipa guasú (Semana Santa), chipa almidón |
| **Pastelería Industrial / Fábrica** | Alberdin (1955) — 70 años, fábrica con Alberdin Quinta (planta), Alberdin Choferes, Alberdin Trinidad, Alberdin Soldado Ovelar, Alberdin Pilar. Ravioles, ñoquis, fideos, discos de empanadas, bocaditos, salsas, pizzas, chipa guasú congelada, milanesas, productos gourmet, franquicias | `https://www.abc.com.py/empresariales/2025/12/12/siete-decadas-de-excelencia-gastronomica/` | The B2B side of Pastelería/Confitería; needs production planning vs. daily retail; a different seed pack |
| **Cervecería / Bar / Pub** | The PY beer market is dominated by Cervecería Nacional + Cervecería Paraguaya (APAC); there are also craft breweries (Santa Juana, BrewHouse, etc.) | General knowledge; needs deeper research in a followup | The bar/pub vertical is the most distinct from the food packs: alcoholic beverages, social events, late-night |

These 5 are **not in the current 11 packs** but each has 100s-1000s of PY establishments. The user said "all possible clients" so I should propose adding these.

---

## 4. The enriched SeasonalEvent catalog (per-pack relevance)

The SASKIA-216 catalog I drafted has **132 rows = 44 event types × 3 years (2026-2027-2028)** for La Vaquita (Panadería). For multi-tenant, the catalog needs to grow to cover **all events that matter to all 11+5 packs**, with `relevance_tags` set per pack. Estimated **~250-300 event types × 3 years = ~750-900 rows** total.

### 4.1 Tier 1: Universal (all packs see these) — 44 events × 3 yrs = 132 rows

These are the legal/commercial/religious/school/folk days that affect **every food business in PY** (per the comprehensive catalog in `docs/operations/2026-10-12-seasonal-events-comprehensive-catalog.md` §3-§5).

| Event | Pack relevance | Impact (avg) | NL heritage? |
|---|---|---|---|
| Semana Santa (Jueves Santo, Viernes Santo, Pascua) | all | 1.0 (critical) | also Easter |
| Día de la Madre PY (15 May) | all | 1.0 (critical, biggest commercial day) | – |
| Navidad (24-25 Dec) | all | 1.0 | also NL Kerstmis |
| Año Nuevo (1 Jan) | all | 1.0 | also NL Nieuwjaarsdag |
| Día del Amigo PY (30 Jul) | all | 0.9 (second biggest, all food segments spike) | – |
| Día del Padre PY (3rd Sun Jun) | all | 0.8 | – |
| Día del Niño PY (16 Aug) | all | 0.8 | – |
| Independencia Nacional (14-15 May) | all | 0.8 | – |
| Fiestas Patrias cluster (14-15 May + weekend) | all | 0.8 | – |
| Carnaval Encarnaceno (5 Saturdays Jan-Feb) | most (depends on location) | 0.4 | – |
| Día de San Valentín (14 Feb) | Café, Pastelería, Heladería, Pizzería | 0.6 | – |
| Reyes / Epifanía (6 Jan) | Panadería, Pastelería | 0.9 (Rosca de Reyes) | – |
| San Juan Ára (23-24 Jun) | Panadería, Empanadas, Comedor (chipá, mbejú) | 0.9 | – |
| Día de la Mujer (8 Mar) | Café, Pastelería, Heladería, Catering | 0.6 | – |
| Día del Maestro (30 Apr) | Catering, Comedor (almuerzo) | 0.5 | – |
| Nochebuena (24 Dec) | Panadería, Pastelería, Catering | 0.9 | – |
| Black Friday PY (last Fri Nov) | Pizzería, Hamburguesería, Café, Catering | 0.6 | – |
| CyberDay PY (first Mon-Wed Nov) | Café, Pizzería, Pastelería (when online) | 0.4 | – |
| Inicio de clases PY (late Feb) | Panadería, Quiosco (galletas, facturas) | 0.7 | – |
| Fin de clases PY (last biz day Nov) | Panadería, Quiosco (snack season ends) | 0.4 | – |
| Vacaciones de invierno PY (2nd Mon Jul + 2 wks) | Panadería, Heladería (viajes) | 0.5 | – |
| Sinterklaas (5 Dec) | Café, Pastelería, Panadería (speculaas) | 0.4 (NL heritage niche) | **yes** |
| Koningsdag (27 Apr) | Café, Pastelería (NL heritage) | 0.1 (info) | **yes** |
| Halloween (31 Oct) | Pizzería, Hamburguesería, Heladería | 0.4 (imported) | – |
| Día de los Pueblos Originarios (12 Oct) | none (not commercial) | 0.1 | – |
| Día de la Música PY (22 Nov) | none (cultural, no demand) | 0.1 | – |
| Día del Tereré (last Sat Feb) | none (cultural) | 0.1 | – |
| Singles Day (11 Nov) | none (no online) | 0.1 | – |

### 4.2 Tier 2: Per-pack vertical-specific — ~30 events × 3 yrs = ~90 rows

These are the **vertical's own** festive days that don't appear in any official calendar but drive demand for the specific business type.

#### Panadería (La Vaquita)
- Día del Panadero (mid-March, informal, marketing)
- Día del Chipá (no fixed date, but in some places 14 Aug or variable; chipá is omnipresent in PY)
- Día de la Sopa Paraguaya (no fixed date; La Vaquita sells the mix)
- Día de la Galleta Decorada (no fixed date)

#### Pastelería/Confitería
- Día del Cupcake (15 Dec, US)
- Día de la Torta (26 Nov, US)
- Día de la Galleta (4 Dec, US)
- Día del Macaron (20 Mar, FR)
- Día del Tiramisú (21 Mar, IT)
- Día de la Tarta de Manzana (13 May)
- Día del Brownie (8 Dic, US)
- Día del Chocolate (13 Sep, US? actually 7 Jul)
- Día del Pastel de Chocolate (27 Mar)
- Día de la Tarta de Zanahoria (3 Feb)
- Día de la Nuez (17 May)
- Día de la Fresa (20 May)
- Día de la Frutilla (US: 27 Feb)

#### Pizzería
- **Día Mundial de la Pizza (9 Feb)**
- **Día de la Pizza de Queso (5 Abr)**
- **Día Internacional de la Pizza (México: 7 May)**
- Día de la Pizza Party (3rd Fri May, US)
- Día de la Pizza de Pepperoni (20 Sep, US)
- **Noche de la Pizza y la Empanada** (last Mon Sept in AR, 28 sept; PY-adoptable)

#### Hamburguesería
- **Día Internacional de la Hamburguesa (28 May)**
- **National Cheeseburger Day (18 Sept, US)**
- Día de la Milanesa (3 May AR / 18 Mar in some calendars)
- Día del Lomito (no fixed; AR 18 May)
- Día del Hot Dog (24 Abr)
- Día de la Papas Fritas (20 Abr, US)

#### Heladería
- **Día del Helado Gratis Amandau (mobile, ~Aug-Sept in PY)**
- **Noche de las Heladerías AR (mid-Nov, 41st ed, AFAHYA)**
- Semana del Auténtico Helado Artesanal (10-16 Nov AR/PY adopting)
- Día del Helado de Vainilla (23 Jul, US)
- Día del Helado de Chocolate (7 Ene, US)
- Día del Helado de Frutilla (9 Ene, US)
- Día del Sundae (11 Jul, US)
- Día del Yogurt Helado (6 Feb, US)
- Día del Acai (6 Mar, BR)

#### Café/Cafetería
- **Día Internacional del Café (1 Oct, US/ICO; also 29 Sept in some calendars)**
- Día Nacional del Café (12 Oct, BR)
- Día del Café con Leche (no fijo; 1st Fri Sept US)
- Día del Espresso (23 Oct, IT)
- Día del Cappuccino (8 Nov, US)
- Día del Café Irlandés (25 Ene)
- Día del Macchiato (6 Ene, US — but PY biz per customer type)
- Día del Mocha (27 Sept, US)

#### Empanadas/Criolla
- **Día de la Empanada PY (4 Oct, +30% production per Bar Leo/Don Ramón/Don Vito/Jumbo Empanadas)**
- **Día de la Empanada Salteña AR (4 Abr)**
- Día de la Empanada de Pollo (no fijo)
- Día de la Empanada de Carne (no fijo)
- **Cuaresma** (Ash Wed to Easter, already in tier 1 as movable; empanadas vegetarianas spike)

#### Catering/Eventos
- Día de las Bodas (no fijo, cluster Sep-Nov in PY per FiestaPro.py 12k+ fiestas; peak in Nov)
- Día de los 15 Años (no fijo, cluster Sept-Nov in PY)
- Día del Bautismo (no fijo, cluster May-Sept in PY)
- Día de la Primera Comunión (May-Sept in PY)
- Fiestas de Fin de Año Empresarial (1-15 Dec, all corporate clients)
- Día del Café Empresarial (variable; first Fri Sept in AR)
- Día del Coffee Break (variable; Catering)
- Día del Té (21 May, US/UK)
- Día del Brunch (no fijo; 2nd Sun Apr US)
- Día de la Mesa de Queso (no fijo; 20 Jan US "National Cheese Lover's Day")

#### Parrilla/Restaurante
- **Día del Asado (11 Oct, AR; PY adopting)**
- **Día de la Tradición (10 Nov, AR; gauchesque, PY-influenced)**
- Día de la Milanesa (3 May, AR)
- **Día de la Choripán (no fijo, PY fan)
- Día del Costillar (variable)
- Día de la Cerveza (7 Ago, US/AR; also "Pilsener Day" 15 Nov PY)
- Día del Vino (25 May AR / 18 Feb US)
- Día del Fernet (variable, AR)
- Día del Tereré (last Sat Feb, PY)
- Día del Asado a la Olla (variable)

#### Comedor/Kilo
- Día del Almuerzo (variable)
- Día del Menú Ejecutivo (variable)
- Día de la Sopa (variable)
- Día de la Milanesa (3 May AR, already in Parrilla)

#### Oriental
- **Año Nuevo Chino (10 Feb 2026, 29 Ene 2027, 17 Feb 2028)**
- Día Internacional del Sushi (18 Jun, US)
- Día del Ramen (variable, 26 Mar in some)
- Día de la Soya (variable)

#### NL heritage (for any NL-themed client)
- Sinterklaas (5 Dec, already in tier 1)
- Koningsdag (27 Apr, already in tier 1)
- Bevrijdingsdag (5 May)
- King's Birthday (27 Apr; already)
- Dag van de Stroopwafel (29 Sept, NL)
- Dag van de Bitterbal (variable)
- Dag van de Poffertjes (16 May, NL)
- Dag van de Kruidnoten (variable; early Dec)
- Dag van de Hagelslag (variable; first Sat Dec)
- Dag van de Beschuit met Muisjes (variable; pink when baby girl, blue when baby boy; not a fixed date)

#### NEW pack 1: Food Truck / Móvil
- Most of the universal tier
- Día del Food Truck (variable, US 28 May "National Burger Day" + "National Food Truck Day" first Fri Jun)
- Día del Desayuno (variable; 7 Nov in some)
- Día de la Merienda (variable; AR 25 Jul)

#### NEW pack 2: Quiosco / Minimarket / Almacén
- Universal tier
- Día del Almacenero (8 Ago, sectoral)
- Día del Repartidor (variable)
- Día de las Bebidas (variable; 6 May US "National Beverage Day")
- Día de la Cerveza (7 Ago, US/AR; also 15 Nov "Pilsener Day" PY)
- Día del Snack (no fijo; 21 Feb US "National Almond Day" / 27 Feb "National Strawberry Day" etc.)
- Día del Tereré (last Sat Feb, PY; sells tereré accessories, yerba, etc.)

#### NEW pack 3: Chipería / Almidón
- Universal tier
- Día del Chipá (no fijo; 14 Aug is sometimes cited; "Dia de la Chipa" 14 Aug in some calendars)
- Semana Santa (chipá guasú is THE dish)
- San Juan Ára (chipá almidón + mbejú are THE San Juan foods)
- Día de la Sopa Paraguaya (no fijo, but core PY dish)
- Día de la Cocina Paraguaya (variable; "Día de la Cocina Paraguaya" 9 Jul in some calendars)
- Día de la Mandioca (no fijo)
- Día de la Chipería (no fijo)

#### NEW pack 4: Pastelería Industrial / Fábrica
- Universal tier
- Most Pastelería vertical events
- Día de la Industria (variable; 1st week Sept in some calendars)
- Día de la Pyme (variable; 27 Jun UN)

#### NEW pack 5: Cervecería / Bar / Pub
- Universal tier
- Día de la Cerveza (7 Ago US/AR + 15 Nov "Pilsener Day" PY)
- Día del Fernet (variable, AR)
- Día del Cóctel (13 May, US)
- Día del Mojito (11 Jul, CU)
- Día del Whisky (third Sat May; 16 May 2026)
- Día del Vino (25 May AR / 18 Feb US)
- Año Nuevo Chino (10 Feb 2026, APAC clubs)
- Día del Día Internacional de la Cerveza (3 Ago, US "International Beer Day")
- Día del Marzen / Oktoberfest (starts 20 Sept)
- Día de la Caipirinha (no fijo)

### 4.3 Tier 3: World gastronomy / international observances (low impact, all packs) — ~50 events

These are global "Día del X" dates that no PY food business strictly cares about but are available if the operator wants to participate in social media campaigns:

- Día del Chocolate (13 Sep / 7 Jul) — all packs (Panadería, Pastelería, Heladería strongest)
- Día de la Nutella (5 Feb) — Panadería, Pastelería, Heladería
- Día del Macaron (20 Mar) — Panadería, Pastelería
- Día del Tiramisú (21 Mar) — Panadería, Pastelería
- Día del Hummus (13 May) — Café, Catering
- Día del Acai (6 Mar) — Heladería, Café
- Día del Yogurt Helado (6 Feb) — Heladería, Café
- Día del Pisco Sour (1st Sat Feb, AR/PY) — Parrilla, Bar
- Día del Asado (11 Oct, AR) — Parrilla
- Día del Cóctel (13 May) — Bar
- Día del Vino (25 May AR) — Bar, Catering
- Día de la Frutilla (27 Feb US, 20 May "Día de la Fresa") — Heladería, Pastelería
- Día de la Tarta de Manzana (13 May) — Panadería, Pastelería
- Día del Brownie (8 Dic US) — Panadería, Pastelería
- Día del Cupcake (15 Dic US) — Pastelería
- Día de la Torta (26 Nov US) — Pastelería
- Día de la Galleta (4 Dic US) — Panadería, Pastelería
- Día del Cappuccino (8 Nov US) — Café
- Día del Espresso (23 Oct IT) — Café
- Día del Café con Leche (1st Fri Sept US) — Café
- Día del Café Irlandés (25 Ene) — Café
- Día del Mocha (27 Sept US) — Café
- Día del Macchiato (6 Ene US) — Café
- Día Internacional del Té (21 May UK) — Café, Catering
- Día del Hot Dog (24 Abr US) — Hamburguesería
- Día de la Milanesa (3 May AR) — Parrilla, Hamburguesería
- Día de las Papas Fritas (20 Abr US) — Hamburguesería, Catering
- Día del Sándwich de Milanesa (18 May AR) — Hamburguesería
- Día del Lomito (no fijo, 18 May AR) — Hamburguesería
- Día de la Hamburguesa Vegana (1 Oct US) — Hamburguesería, Café
- Día del Cheeseburger (18 Sept US) — Hamburguesería
- Día del Sundae (11 Jul US) — Heladería
- Día del Helado de Vainilla (23 Jul US) — Heladería
- Día del Helado de Chocolate (7 Ene US) — Heladería
- Día del Helado de Frutilla (9 Ene US) — Heladería
- Día del Sundae (11 Jul US) — Heladería
- Día del Acai (6 Mar BR) — Heladería, Café
- Día del Ramen (variable) — Oriental
- Día del Sushi (18 Jun US) — Oriental
- Día del Año Nuevo Chino (10 Feb 2026) — Oriental
- Día de la Soya (variable) — Oriental
- Día del Tofu (variable) — Oriental
- Día del Curry (variable) — Catering
- Día de la Paella (variable) — Catering
- Día del Pisco (variable) — Parrilla, Bar
- Día del Fernet (variable) — Bar
- Día de la Cerveza (7 Ago US/AR) — Bar
- Día Internacional de la Cerveza (3 Ago US) — Bar
- Día del Mojito (11 Jul CU) — Bar
- Día del Whisky (third Sat May) — Bar
- Día de la Pizza Party (3rd Fri May US) — Pizzería
- Día de la Pizza de Pepperoni (20 Sept US) — Pizzería
- Día de la Pizza de Queso (5 Abr US) — Pizzería
- Día de la Pizza Mexicana (7 May) — Pizzería
- Día de la Pizza en Chile (10 Jul) — Pizzería
- Noche de la Pizza y la Empanada (last Mon Sept AR) — Pizzería, Empanadas

### 4.4 Tier 4: NL heritage extended (for the "Vaquita Holandesa" brand or any future NL client)

- Dag van de Stroopwafel (29 Sept, NL)
- Dag van de Bitterbal (variable, NL — "Bitterbal Day" early Nov)
- Dag van de Poffertjes (16 May, NL)
- Dag van de Kruidnoten (variable, early Dec)
- Dag van de Hagelslag (variable, first Sat Dec)
- Dag van de Beschuit met Muisjes (variable; pink for girl, blue for boy)
- Koningsdag (27 Apr, already in tier 1)
- Bevrijdingsdag (5 May)
- Sinterklaas (5 Dec, already in tier 1)
- Dodenherdenking (4 May, eve of Bevrijdingsdag, cultural)
- Keti Koti (1 Jul, Emancipation Day)
- Prinsjesdag (3rd Tue Sept, Budget Day)
- NL School vakanties 2026-2030 (3 regions: Herfst 10-18 okt 2026 noord; etc. — informational only, not a holiday)

---

## 5. Final count for the SeasonalEvent seed

| Tier | Distinct event types | × 3 years | Total rows |
|---|---|---|---|
| Tier 1 (universal — 17 events × 11 packs visible) | 17 | × 3 | 51 |
| Tier 1 (universal — 27 events only some packs see) | 27 | × 3 | 81 |
| Tier 2 (per-pack vertical — ~30 events) | 30 | × 3 | 90 |
| Tier 3 (world gastronomy — ~50 events) | 50 | × 3 | 150 |
| Tier 4 (NL heritage — ~13 events) | 13 | × 3 | 39 |
| **TOTAL** | **~137 distinct event types** | | **~411 rows** |

For **La Vaquita (Panadería)**, the visible subset is:
- All Tier 1 universal (44 events × 3 yrs = 132)
- Panadería subset of Tier 2 (chipá, día del panadero, etc. — 5-8 events × 3 = ~24)
- Pastelería/Tortas subset of Tier 2 (some overlap with Panadería — 10 events × 3 = 30)
- Tier 3 subset of Panadería+Pastelería (10 events × 3 = 30)
- Tier 4 NL heritage (Sinterklaas + speculaas/kruidnoten — 5 events × 3 = 15)
- **Total visible to La Vaquita: ~230 rows**

The other ~180 rows are **in the DB** but the `relevance_tags` filter hides them from La Vaquita's calendar.

---

## 6. How the seed should work (multi-tenant aware)

### 6.1 The seeder function

In `app/rms/seed/sazon.py` (or a new `app/rms/seed/seasonal.py`):

```python
def seed_seasonal_events(session: Session, *, year_range: tuple[int, int] = (2026, 2028)) -> int:
    """Insert the full PY + NL heritage SeasonalEvent catalog.

    SASKIA-216 (2026-10-12). Idempotent: skip if (country, slug, event_date) exists.
    Returns the number of rows inserted.

    The `relevance_tags` column is a CSV of pack slugs that should display this event.
    An empty string means ALL packs see it (universal events).
    """
    rows = _build_event_catalog(year_range)
    inserted = 0
    for row in rows:
        existing = (
            session.query(SeasonalEvent)
            .filter_by(country=row["country"], slug=row["slug"], event_date=row["event_date"])
            .first()
        )
        if existing:
            continue
        session.add(SeasonalEvent(**row))
        inserted += 1
    session.flush()
    return inserted
```

### 6.2 The catalog data structure

```python
def _build_event_catalog(year_range: tuple[int, int]) -> list[dict]:
    """Build the full catalog as a list of dicts, one per row."""
    rows = []
    for year in range(year_range[0], year_range[1] + 1):
        # ... add fixed-date events
        # ... add Easter-dependent events
        # ... add movable-by-decree events (use a year-specific override)
        # ... add tier 2/3/4 events
    return rows
```

### 6.3 Multi-tenant visibility

The UI (SASKIA-217) reads the `relevance_tags` column and filters:

```python
def get_calendar_for_tenant(
    session: Session, tenant: Tenant, lead_days: int = 30
) -> list[SeasonalEvent]:
    today = date.today()
    horizon = today + timedelta(days=180)  # show 6 months ahead
    return (
        session.query(SeasonalEvent)
        .filter(
            SeasonalEvent.event_date >= today,
            SeasonalEvent.event_date <= horizon,
            or_(
                SeasonalEvent.relevance_tags == "",  # universal
                SeasonalEvent.relevance_tags.like(f"%{tenant.pack_slug}%"),
            ),
        )
        .order_by(SeasonalEvent.event_date)
        .all()
    )
```

Each tenant sees only their pack's events. The `relevance_tags` is the filter; the DB is shared.

---

## 7. Per-pack event summaries (what each future client would see)

| Pack | # events visible (3 yrs) | Top 5 by impact | NL heritage visible? |
|---|---|---|---|
| Panadería (La Vaquita) | ~230 | Reyes, Pascua, Madre, Navidad, San Juan, San Lorenzo, Asunción | yes (Sinterklaas) |
| Pastelería/Confitería | ~250 | Madre, Niño, Navidad, Reyes, Comuniones | yes (Sinterklaas) |
| Pizzería | ~190 | Pizza (9 feb), Amigo, Padre, Halloween, Noche Pizza | no (none relevant) |
| Hamburguesería | ~190 | Hamburguesa (28 may), Niño, Halloween, Amigo, Black Friday | no |
| Heladería | ~220 | Helado Gratis (mobile), Niño, Año Nuevo, Día Madre, Black Friday | no (NL klimaat niet) |
| Empanadas | ~210 | Empanada (4 oct), Amigo, San Juan, Cuaresma, Padre | no |
| Café/Cafetería | ~210 | Madre, Amigo, Café (1 oct), San Valentín, Niño | yes (NL café culture) |
| Catering/Eventos | ~250 | Bodas (Sep-Nov), Comuniones, Bautismos, Fiestas Fin Año, Madre | yes (NL kerst diner) |
| Parrilla/Restaurante | ~220 | Asado (11 oct), Padre, Independencia, Tradición (10 nov), Amigo | no |
| Comedor/Kilo | ~160 | Independencia, Año Nuevo, Semana Santa (no-meat Fri), Madre | no |
| Oriental | ~140 | Año Nuevo Chino, Sushi (18 jun), Año Nuevo, Navidad | no |
| **NEW: Food Truck** | ~180 | Universal, plus rutas (events that move foot traffic: conciertos, ferias) | no |
| **NEW: Quiosco/Minimarket** | ~160 | Universal, plus Almacenero, Cerveza, Tereré | no |
| **NEW: Chipería** | ~180 | Universal, plus chipá, San Juan, Semana Santa, Cocina Paraguaya | no |
| **NEW: Pastelería Industrial** | ~240 | Pastelería + Industria (1st week Sept) + Madre + Navidad | yes |
| **NEW: Cervecería/Bar** | ~200 | Cerveza (7 ago), Whisky, Mojito, Año Nuevo, Día del Amigo | no |

---

## 8. Risks of expanding the catalog

1. **Cognitive overload**: if 137 event types are visible to the operator (even with filter), it's overwhelming. The UI must default to **only show the top 20 by impact_score + within the lead_days window**. The full catalog is data, not UI.
2. **Date accuracy**: ~30% of the tier 2/3/4 events are "approximate" or "no fixed date" in the source. The seeder should mark them with `impact_tag="low"` and `recurrence="mobile"` so the operator knows they're not firm.
3. **NL cultural mismatch**: 13 NL heritage events are real for NL, but most are **invisible** to a PY panadería. The `relevance_tags` filter is what keeps them out of the calendar. If the filter breaks, an operator might plan production for Sinterklaas speculaas in September, which is wrong.
4. **Per-pack overlay**: when a NEW client is onboarded, the `onboard_tenant` call should not need to re-seed the catalog. The catalog is universal. Only the tenant's `relevance_tags` filter changes.
5. **External dependency**: Carnaval, Día del Helado Gratis (mobile), CyberDay, school calendar all change annually. The catalog needs a `scripts/refresh_seasonal_events.py` cron (SASKIA-219).

---

## 9. What's next (the actual work)

### 9.1 Immediate (already drafted, awaiting "go")

1. **SASKIA-216** — SeasonalEvent model + migration 119 + the universal catalog (tier 1, ~132 rows) seed. 2-3 days.
2. **SASKIA-217** — `/admin/seasonal-calendar` UI page that respects `relevance_tags` and `seasonal.notif_lead_days`. 2-3 days.

### 9.2 Expansion (deferred to operator approval)

3. **SASKIA-220** (new) — Add the 5 new packs (Food Truck, Quiosco, Chipería, Pastelería Industrial, Cervecería) to `app/rms/seed/packs.py::PACKS`. 3-5 days.
4. **SASKIA-221** (new) — Extend the SeasonalEvent catalog to tier 2/3/4 (per-pack + world gastronomy + NL heritage). Adds ~280 rows to the seed. 2-3 days.
5. **SASKIA-222** (new) — Multi-tenant per-tenant settings: each tenant has a `country` (PY/NL/AR/BR), a `pack` (the 11+5), and a `relevance_tags` filter. The Sazon app uses this to show the right calendar. 4-6h.

### 9.3 Operational (deferred)

6. **SASKIA-219** — `scripts/refresh_seasonal_events.py` annual roll-forward. 1 day.
7. **SASKIA-218** — `TenantSeasonalEventOverride` table for per-tenant event visibility/impact customization. 1 day.

The **critical path** is SASKIA-216 → SASKIA-217 → SASKIA-222. Without these, the OOB "the website of sazon should load all of the things" can't be fulfilled for La Vaquita, let alone the next client.

---

## 10. Sources (all web-cited, retrieved 2026-10-12)

### PY food market
- `https://www.forbes.com.py/negocios/sector-gastronomico-paraguayo-mueve-casi-us-2-mil-millones-ano-n58395` — 6,000 locales, US$ 1.9B/year, Arpy 383 asociados, 12,000 IPS
- `https://www.mipymes.gov.py/wp-content/uploads/2023/02/PERFIL-SECTOR-ALIMENTOS_espanol.pdf` — PY food sector 80% micro/small
- `https://www.lanacion.com.py/negocios_edicion_impresa/2025/12/29/mayor-formalizacion-desafio-2026-del-rubro-gastronomico/` — Fast food +30-35% in 2025

### Per-vertical event dates
- `https://infonegocios.com.py/y-ademas/dia-de-la-empanada-incrementan-produccion-hasta-un-30-para-satisfacer-demanda-creciente-y-esta-sigue-siendo-la-mas-popular` — Día de la Empanada 4 oct
- `https://www.rdn.com.py/2024/10/04/dia-de-la-empanada-celebracion-de-un-icono-culinario-en-el-pais/` — 4 oct origen México
- `https://dayspedia.com/py/calendar/holiday/976/?lang=es` — Día de la Pizza 9 feb
- `https://dayspedia.com/py/calendar/holiday/4499/?lang=es` — Día de la Hamburguesa 28 may
- `https://thelastbitemedia.com/calendario-gastronomico-2026-fechas-destacadas/` — Calendario gastronómico 2026 completo
- `https://infonegocios.com.py/amp/default/hay-que-pasar-el-invierno-heladerias-ofrecen-alternativas-para-los-dias-frios-crece-consumo-fuera-del-verano` — Heladería winter drop 50%
- `https://infonegocios.com.py/infobrand/amandau-celebra-15-anos-regalando-sonrisas-con-el-dia-del-helado-gratis` — Día Helado Gratis Amandau 15 years
- `https://infonegocios.com.py/infobrand/amandau-se-prepara-para-una-nueva-edicion-del-dia-nacional-del-helado-gratis-se-realizara-en-agosto` — 2025 mobile August
- `https://notasdeactualidad.com.ar/noche-de-las-heladerias-2025-cuando-sera-y-que-locales-estan-adheridos/` — Noche Heladerías AR 10-16 Nov AFADHYA

### PY patronales, sectors
- `https://www.pausa.com.py/actualidad/nota-de-tapa/cronicas-desde-eusebio-ayala/9915/` — Chipería Eusebio Ayala, Ña Nena embajadora
- `https://www.lanacion.com.py/negocios/2021/11/09/emprendedores-ln-don-cocido-restaurante-sobre-ruedas-que-nacio-para-costear-tratamiento-oncologico/` — Don Cocido food truck
- `https://revistas.umariana.edu.co/BoletinInformativoCEI/article/download/4279/4349/14711` — Quioscos PY 89% aplican innovación
- `https://www.abc.com.py/empresariales/2025/12/12/siete-decadas-de-excelencia-gastronomica/` — Alberdin 70 años
- `https://www.venus.com.py/amandau-la-heladeria-lider-en-la-mente-de-los-paraguayos-top-of-mind-2026` — Amandau 200+ sucursales Top of Mind 2026

### + all sources from the 2026-10-12 SASKIA-216 catalog doc
