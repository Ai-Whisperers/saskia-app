"""app.seed.catalog — comprehensive catalog seed library.

Single source of truth for the Saskia RMS catalog data.

This module exposes a single function, ``seed_catalog(session)``, that:

- Upserts the canonical ingredient list (81 items, 81 from research + Gaby's
  Paraguayan menu).
- Upserts the canonical recipe list (30 items: 22 from research + 8 new
  Paraguayan recipes for chipa, mbeju, sopa, kiveve, etc.).
- Upserts the canonical product list (43 items: 30 from research + 13 new
  Paraguayan SKUs including the "1 kg chipa" the Kyrian seed refers to).
- Fixes three known data-quality bugs from the 2026-09-29 audit:
    1. Recipe 22 "pepper noot" → "pepernoten" (typo).
    2. Products 22/23/29 set to is_available=True with sane prices.
    3. Ingredient "gold leaves" Gs. 5,000,000 (obvious data error) — soft-
       delete the row (deleted_at set to now). It is not referenced by any
       product or recipe line.
- Idempotent: every operation is an INSERT-or-skip (by name) or an UPDATE
  to enforce canonical values. Safe to call multiple times.

The catalog data is consumed by:
    - ``qseed("with_catalog")`` in tests (qseed fixture).
    - ``/demo/seed`` in production (manual operator action).
    - The Kyrian seed for product references (chipa, mbeju, etc.).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


# ----------------------------------------------------------------------------
# CANONICAL INGREDIENTS
# Key: stable slug (not the live id — we look up by name).
# Fields chosen to match the live schema: ingredient table.
# ----------------------------------------------------------------------------
def _ing(slug: str, name: str, unit: str, price: int, category: str,
         notes: str, allergens: str = "", role: str = "ingredient",
         is_packaging: bool = False) -> Dict[str, Any]:
    return {
        "slug": slug,
        "name": name,
        "unit": unit,
        "purchase_price_gs": price,
        "category": category,
        "subcategory": None,
        "role": role,
        "allergens": allergens,
        "dietary_tags": None,
        "notes": notes,
        "is_packaging": is_packaging,
    }


_INGREDIENTS: List[Dict[str, Any]] = [
    # === BASE PANADERÍA (research) ===
    _ing("harina", "Harina de trigo 000", "kg", 4500, "harinas",
         "Harina 000 de trigo. Base de todo. | reorder auto", "gluten"),
    _ing("harina_centeno", "Harina de centeno", "kg", 9800, "harinas",
         "Solo para Ontbijtkoek. Sabor fuerte. | reorder auto", "gluten"),
    _ing("azucar", "Azúcar blanca", "kg", 4800, "endulzantes",
         "Azúcar blanca refinada. | reorder auto", ""),
    _ing("azucar_morena", "Azúcar morena", "kg", 5800, "endulzantes",
         "Azúcar morena para humedad extra. | reorder auto", ""),
    _ing("azucar_impalpable", "Azúcar impalpable", "kg", 9500, "endulzantes",
         "Para glass. | reorder auto", ""),
    _ing("sal", "Sal fina", "kg", 1800, "condimentos",
         "Sal marina fina. | reorder auto", ""),
    _ing("levadura", "Levadura seca", "kg", 22000, "leudantes",
         "Levadura instantánea. | reorder auto", ""),
    _ing("polvo_hornear", "Polvo de hornear", "kg", 18000, "leudantes",
         "Polvo de hornear doble acción. | reorder auto", ""),
    _ing("bicarbonato", "Bicarbonato de sodio", "kg", 12000, "leudantes",
         "Para activar el cacao y regular acidez. | reorder auto", ""),

    # === GRASAS Y LÁCTEOS ===
    _ing("manteca", "Manteca", "kg", 32000, "lácteos",
         "Manteca sin sal. Para masa y repostería. | reorder auto", "dairy"),
    _ing("leche", "Leche entera", "l", 7800, "lácteos",
         "Leche entera UHT. | reorder auto", "dairy"),
    _ing("crema_leche", "Crema de leche", "l", 18500, "lácteos",
         "Crema de leche para chantilly. | reorder auto", "dairy"),
    _ing("queso_crema", "Queso crema", "kg", 38000, "lácteos",
         "Tipo Philadelphia. Para cheesecakes. | reorder auto", "dairy"),
    _ing("crema_agria", "Crema agria", "kg", 25000, "lácteos",
         "Crema agria para brownies. | reorder auto", "dairy"),
    _ing("leche_condensada", "Leche condensada", "kg", 18500, "lácteos",
         "Leche condensada azucarada. | reorder auto", "dairy"),
    _ing("huevo", "Huevo", "und", 600, "huevos",
         "Huevo grande (~60g). | reorder auto", "eggs"),
    _ing("dulce_leche", "Dulce de leche", "kg", 28000, "endulzantes",
         "Dulce de leche repostero. | reorder auto", "dairy"),
    _ing("miel", "Miel", "kg", 35000, "endulzantes",
         "Miel pura de abeja. | reorder auto", ""),

    # === SABORIZANTES Y ESPECIAS ===
    _ing("vainilla", "Esencia de vainilla", "ml", 80, "sabores",
         "Esencia artificial. | reorder auto", ""),
    _ing("canela", "Canela molida", "g", 50, "especias",
         "Canela molida. | reorder auto", ""),
    _ing("ralladura_limon", "Ralladura de limón", "g", 120, "sabores",
         "Ralladura de limón fresco. | reorder auto", ""),
    _ing("ralladura_naranja", "Ralladura de naranja", "g", 120, "sabores",
         "Ralladura de naranja fresca. | reorder auto", ""),
    _ing("nuez_moscada", "Nuez moscada", "g", 200, "especias",
         "Nuez moscada molida. | reorder auto", ""),
    _ing("jengibre_molido", "Jengibre molido", "g", 250, "especias",
         "Para Ontbijtkoek. | reorder auto", ""),
    _ing("anis_estrella", "Anís estrella", "g", 800, "especias",
         "Anís estrella para Frikandel. | reorder auto", ""),
    _ing("jengibre_fresco", "Jengibre fresco", "g", 50, "frescos",
         "Para Frikandel. | reorder auto", ""),
    _ing("mezcla_especias", "Mezcla de especias para Frikandel", "g", 500,
         "especias", "Especias mixtas. Para Frikandel. | reorder auto", ""),
    _ing("especias_speculaas", "Especias para Speculaas", "g", 600,
         "especias", "Mezcla canela/nuez moscada/clavo. | reorder auto", ""),

    # === CHOCOLATE Y CACAO ===
    _ing("cacao_polvo", "Cacao en polvo", "kg", 28000, "chocolate",
         "Cacao puro. Sin azúcar. | reorder auto", ""),
    _ing("chocolate_cobertura", "Chocolate cobertura", "kg", 45000,
         "chocolate", "Chocolate cobertura 70%. | reorder auto", "dairy"),
    _ing("chocolate_chips", "Chocolate chips", "kg", 32000, "chocolate",
         "Chips de chocolate semiamargo. | reorder auto", "dairy"),

    # === FRUTOS SECOS Y FRUTAS ===
    _ing("almendra_molida", "Almendra molida", "kg", 85000, "frutos-secos",
         "Almendra molida fina. | reorder auto", "nuts"),
    _ing("nueces", "Nueces", "kg", 65000, "frutos-secos",
         "Nueces mariposa. | reorder auto", "nuts"),
    _ing("pasas", "Pasas de uva", "kg", 22000, "frutos-secos",
         "Pasas de uva sultana. | reorder auto", ""),
    _ing("coco_rallado", "Coco rallado", "kg", 28000, "frutos-secos",
         "Coco rallado sin azúcar. | reorder auto", ""),
    _ing("frutillas", "Frutillas", "kg", 22000, "frutas",
         "Frutillas frescas. | reorder auto", ""),
    _ing("arandanos", "Arándanos", "kg", 38000, "frutas",
         "Arándanos frescos. | reorder auto", ""),
    _ing("naranja", "Naranja", "kg", 5000, "frutas",
         "Naranja para rallar. | reorder auto", ""),
    _ing("manzana", "Manzana", "kg", 8500, "frutas",
         "Manzana roja. Para appeltaart. | reorder auto", ""),
    _ing("banana", "Banana", "kg", 4500, "frutas",
         "Banana madura. | reorder auto", ""),
    _ing("zanahoria", "Zanahoria", "kg", 3500, "frutas",
         "Zanahoria fresca. Para carrot cake. | reorder auto", ""),
    _ing("cebolla", "Cebolla", "kg", 4500, "frutas",
         "Cebolla blanca. Para Frikandel. | reorder auto", ""),
    _ing("ajo", "Ajo", "kg", 12000, "frutas",
         "Ajo fresco. Para Frikandel. | reorder auto", ""),

    # === LÍQUIDOS Y OTROS ===
    _ing("aceite", "Aceite vegetal", "l", 12500, "grasas",
         "Aceite neutro. | reorder auto", ""),
    _ing("agua", "Agua", "l", 0, "líquidos",
         "Agua de red. | reorder auto", ""),
    _ing("harina_pastelera", "Harina pastelera", "g", 80, "harinas",
         "Para brownies. | reorder auto", "gluten"),
    _ing("jugo_limon", "Jugo de limón", "ml", 60, "sabores",
         "Jugo de limón natural. | reorder auto", ""),
    _ing("vinagre", "Vinagre", "ml", 30, "condimentos",
         "Vinagre blanco. | reorder auto", ""),

    # === INGREDIENTES HOLANDESES ESPECIALES ===
    _ing("melaza_koekzoet", "Melaza (Koekzoet)", "kg", 16500, "endulzantes",
         "Melaza Koekzoet (típica holandesa). | reorder auto", ""),
    _ing("ontbijtkoek_viejo", "Ontbijtkoek viejo", "kg", 2000, "otros",
         "Subproducto de Ontbijtkoek viejo (reciclar). | reorder auto",
         "gluten"),

    # === PARA CARNES Y SALSAS ===
    _ing("pechuga_pollo", "Pechuga de pollo", "kg", 18000, "carnes",
         "Pechuga de pollo fresca. | reorder auto", ""),
    _ing("panceta", "Panceta", "kg", 28000, "carnes",
         "Panceta ahumada. | reorder auto", ""),
    _ing("carne_molida", "Carne molida", "kg", 22000, "carnes",
         "Carne molida magra. | reorder auto", ""),
    _ing("pan_rallado", "Pan rallado", "kg", 8500, "harinas",
         "Pan rallado fino. | reorder auto", "gluten"),
    _ing("salsa_soja", "Salsa de soja", "l", 6500, "líquidos",
         "Salsa de soja. Para ketjap. | reorder auto", "soy,gluten"),
    _ing("ketjap_manis", "Ketjap Manis", "l", 8500, "líquidos",
         "Salsa de soja dulce indonesia. | reorder auto", "soy,gluten"),

    # === PACKAGING Y DESECHABLES (con precios reales) ===
    _ing("bolsas_kraft", "Bolsa kraft mediana", "und", 800, "packaging",
         "Bolsa kraft mediana para entregar. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("caja_pasteleria", "Caja pastelería (porción)", "und", 1500,
         "packaging",
         "Caja para porción individual. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("caja_docena", "Caja para docena", "und", 2500, "packaging",
         "Caja de cartón para docena. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("vaso_8oz", "Vaso descartable 8oz", "und", 500, "descartables",
         "Vaso 8oz para bebidas. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("vaso_12oz", "Vaso descartable 12oz", "und", 700, "descartables",
         "Vaso 12oz para bebidas. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("tapa_vaso", "Tapa para vaso", "und", 200, "descartables",
         "Tapa plástica para vaso. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("azucar_sobres", "Azúcar en sobres", "und", 100, "descartables",
         "Sobre de azúcar individual. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("revolvedor_madera", "Revolvedor de madera", "und", 150,
         "descartables",
         "Revolvedor descartable. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("servilletas", "Servilletas doble hoja", "und", 60, "descartables",
         "Servilleta descartable. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("papel_manteca", "Papel manteca (hoja)", "und", 300, "descartables",
         "Papel manteca individual. | Alta 2026-09-30 (Hermes).",
         role="packaging", is_packaging=True),
    _ing("te_saquito", "Té (saquito)", "und", 500, "bebidas",
         "Té negro en saquito. | Alta 2026-09-30 (Hermes).",
         role="consumibles"),

    # === INSUMOS DE LIMPIEZA ===
    _ing("lavandina", "Lavandina", "l", 4000, "limpieza",
         "Lavandina para desinfección. | Alta 2026-09-30 (Hermes).",
         role="consumibles"),
    _ing("detergente", "Detergente cocinas", "l", 7000, "limpieza",
         "Detergente industrial. | Alta 2026-09-30 (Hermes).",
         role="consumibles"),
    _ing("guantes_nitrilo", "Guantes nitrilo", "und", 300, "limpieza",
         "Guantes descartables. | Alta 2026-09-30 (Hermes).",
         role="consumibles"),

    # === INGREDIENTES PARAGUAYOS (Gaby's local menu) ===
    _ing("almidon_mandioca", "Almidón de mandioca", "kg", 6500, "harinas",
         "Almidón de mandioca para chipa y mbeju. | research 2026", ""),
    _ing("queso_paraguay", "Queso Paraguay", "kg", 32000, "lácteos",
         "Queso Paraguay semi-curado. Para chipa. | research 2026", "dairy"),
    _ing("grasa_cerdo", "Grasa de cerdo", "kg", 18000, "grasas",
         "Grasa de cerdo para chipa y mbeju. | research 2026", ""),
    _ing("cebolla_verdeo", "Cebolla de verdeo", "kg", 6500, "frutas",
         "Cebolla de verdeo fresca. Para mbeju y tortas. | research 2026", ""),
    _ing("tomate", "Tomate", "kg", 5500, "frutas",
         "Tomate fresco. Para sándwiches. | research 2026", ""),
    _ing("lechuga", "Lechuga", "kg", 4500, "frutas",
         "Lechuga fresca. | research 2026", ""),
    _ing("jamon", "Jamón", "kg", 32000, "carnes",
         "Jamón cocido. Para sándwiches. | research 2026", ""),
    _ing("queso_muzzarella", "Queso muzzarella", "kg", 38000, "lácteos",
         "Queso muzzarella para sándwiches y pizzas. | research 2026", "dairy"),
    _ing("aceite_girasol", "Aceite de girasol", "l", 11500, "grasas",
         "Aceite de girasol. | research 2026", ""),
    _ing("coco_dulce", "Coco dulce", "kg", 25000, "frutos-secos",
         "Coco fresco dulce. Paraguay. | research 2026", ""),
    _ing("azucar_sobre_5g", "Azúcar sobre 5g", "und", 100, "descartables",
         "Sobre individual. | research 2026",
         role="packaging", is_packaging=True),

    # === INGREDIENTES ADICIONALES (Phase 18.2 — para recipe_lines) ===
    _ing("zapallo", "Zapallo", "kg", 3500, "frutas",
         "Zapallo para kiveve. | research 2026", ""),
    _ing("mamon", "Mamón", "kg", 6500, "frutas",
         "Mamón para mermelada payaguá. | research 2026", ""),
    _ing("limon", "Limón", "kg", 7500, "frutas",
         "Limón fresco. | research 2026", ""),
    _ing("frasco_vidrio", "Frasco de vidrio 250g", "und", 2500, "envases",
         "Frasco de vidrio para mermeladas. | research 2026",
         role="packaging", is_packaging=True),
    _ing("pan_miga", "Pan de miga", "und", 1500, "panadería",
         "Pan de miga para sándwiches. | research 2026", "gluten"),
    _ing("jamon_cocido", "Jamón cocido", "kg", 35000, "carnes",
         "Jamón cocido en rodajas. | research 2026", ""),
]

# Convenience access by slug
INGREDIENTS_BY_SLUG: Dict[str, Dict[str, Any]] = {i["slug"]: i for i in _INGREDIENTS}


# ----------------------------------------------------------------------------
# CANONICAL RECIPES
# We keep the live numeric ids (1-22) and add 23-30 for Paraguayan additions.
# The id is what the product catalog uses; the seed will create missing
# recipes by slug, not id.
# ----------------------------------------------------------------------------
_RECIPES: List[Dict[str, Any]] = [
    {"id": 1, "slug": "muffin_vainilla", "name": "muffin_vainilla",
     "yield_qty": 12, "yield_unit": "und", "family": "pastelería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Muffins suaves. Horno 180°C 25-30 min. Rinde 12 unidades.",
     "instructions": "1. Mezclar secos: harina, polvo de hornear, sal.\n2. Batir huevos con azúcar y manteca derretida.\n3. Incorporar harina en forma envolvente, alternando con leche.\n4. Agregar esencia de vainilla.\n5. Llenar pirotines 2/3. Horno 180°C 25-30 min."},
    {"id": 2, "slug": "muffin_chocolate", "name": "muffin_chocolate",
     "yield_qty": 12, "yield_unit": "und", "family": "pastelería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Muffins de chocolate con chips. Horno 180°C 25-30 min.",
     "instructions": "1. Mezclar secos: harina, cacao, polvo de hornear, sal.\n2. Batir huevos con azúcar y manteca derretida.\n3. Incorporar harina alternando con leche.\n4. Sumar chips de chocolate.\n5. Llenar pirotines 2/3. Horno 180°C 25-30 min."},
    {"id": 3, "slug": "muffin_nueces", "name": "muffin_nueces",
     "yield_qty": 12, "yield_unit": "und", "family": "pastelería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs,nuts",
     "notes": "Muffins con nueces picadas. Horno 180°C 25-30 min.",
     "instructions": "1. Mezclar secos: harina, polvo de hornear, sal.\n2. Batir huevos con azúcar y manteca derretida.\n3. Incorporar harina alternando con leche.\n4. Sumar nueces picadas gruesas.\n5. Llenar pirotines 2/3. Horno 180°C 25-30 min."},
    {"id": 4, "slug": "cheesecake", "name": "cheesecake",
     "yield_qty": 8, "yield_unit": "und", "family": "fríos",
     "difficulty": 3, "allergens": "gluten,dairy,eggs",
     "notes": "Cheesecake horneado a baño María 160°C 50-60 min.",
     "instructions": "1. Triturar galletas y mezclar con manteca derretida. Forrar molde.\n2. Batir queso crema con azúcar y huevos.\n3. Sumar crema de leche y esencia de vainilla.\n4. Verter sobre la base. Baño María 150°C 60 min.\n5. Enfriar en horno apagado. Refrigerar 4+ horas."},
    {"id": 5, "slug": "hojaldre_dulce", "name": "hojaldre_dulce",
     "yield_qty": 16, "yield_unit": "und", "family": "panadería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Hojaldre con dulce de leche. Horno 200°C 15-20 min.",
     "instructions": "1. Estirar masa de hojaldre en rectángulo.\n2. Pintar con huevo batido y espolvorear azúcar.\n3. Rellenar con dulce de leche y enrollar.\n4. Cortar en rodadas. Horno 200°C 15-20 min."},
    {"id": 6, "slug": "appeltaart", "name": "appeltaart",
     "yield_qty": 8, "yield_unit": "und", "family": "pastelería",
     "difficulty": 3, "allergens": "gluten,dairy,eggs",
     "notes": "Tarta holandesa de manzanas. Horno 180°C 35-40 min.",
     "instructions": "1. Masa: mezclar harina con manteca fría, azúcar, huevo. Refrigerar 30 min.\n2. Estirar y forrar molde.\n3. Rellenar con manzanas fileteadas, azúcar y canela.\n4. Cubrir con tiras de masa (enrejado).\n5. Horno 180°C 35-40 min."},
    {"id": 7, "slug": "tompoezen", "name": "tompoezen",
     "yield_qty": 12, "yield_unit": "und", "family": "pastelería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Galletas neerlandesas con crema. Horno 160°C 12-15 min.",
     "instructions": "1. Masa: batir manteca con azúcar. Sumar huevo y vainilla.\n2. Incorporar harina y polvo de hornear.\n3. Formar bolitas, aplastar. Horno 160°C 12-15 min.\n4. Rellenar con crema pastelera y cubrir con glaseado."},
    {"id": 8, "slug": "oliebollen", "name": "oliebollen",
     "yield_qty": 24, "yield_unit": "und", "family": "frituras",
     "difficulty": 2, "allergens": "gluten,dairy,eggs,raisins",
     "notes": "Rosquillas holandesas fritas con pasas. Freír a 175°C 3-4 min.",
     "instructions": "1. Mezclar harina con polvo de hornear, sal.\n2. Sumar huevo, leche, manteca derretida y pasas remojadas.\n3. Dejar leudar 1 hora.\n4. Freír cucharadas a 175°C 3-4 min por lado.\n5. Espolvorear azúcar impalpable."},
    {"id": 9, "slug": "babka", "name": "babka",
     "yield_qty": 10, "yield_unit": "und", "family": "panadería",
     "difficulty": 3, "allergens": "gluten,dairy,eggs",
     "notes": "Pan dulce trenzado con chocolate. Horno 175°C 30-35 min.",
     "instructions": "1. Masa: mezclar harina, azúcar, sal, levadura. Sumar huevos, manteca y leche.\n2. Amasar 10 min. Levar 1.5 horas.\n3. Estirar, rellenar con chocolate. Enrollar y trenzar.\n4. Levar 45 min. Horno 175°C 30-35 min."},
    {"id": 10, "slug": "stroopwafel", "name": "stroopwafel",
     "yield_qty": 24, "yield_unit": "und", "family": "pastelería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Wafers con sirope. Plancha 3-4 min.",
     "instructions": "1. Masa: batir huevos con azúcar, miel, manteca derretida.\n2. Sumar harina y levadura. Reposar 1 hora.\n3. Cocinar en waflera 3-4 min.\n4. Rellenar con sirope de caramelo caliente."},
    {"id": 11, "slug": "pan_lactal", "name": "pan_lactal",
     "yield_qty": 2, "yield_unit": "und", "family": "panadería",
     "difficulty": 2, "allergens": "gluten,dairy",
     "notes": "Pan lactal casero. Horno 190°C 25-30 min.",
     "instructions": "1. Mezclar harina con azúcar, sal, levadura. Sumar leche tibia y manteca.\n2. Amasar 10 min. Levar 1 hora.\n3. Formar bollos, colocar en molde. Levar 30 min.\n4. Horno 190°C 25-30 min."},
    {"id": 12, "slug": "facturas", "name": "facturas",
     "yield_qty": 24, "yield_unit": "und", "family": "panadería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Facturas argentinas/paraguayas. Horno 190°C 15-20 min.",
     "instructions": "1. Masa: mezclar harina, azúcar, sal, levadura. Sumar huevos y manteca.\n2. Amasar hasta que se despegue. Levar 1 hora.\n3. Formar medialunas, vigilantes, cañoncitos.\n4. Pintar con huevo. Horno 190°C 15-20 min."},
    {"id": 13, "slug": "brownie_espresso", "name": "brownie_espresso",
     "yield_qty": 12, "yield_unit": "und", "family": "pastelería",
     "difficulty": 3, "allergens": "gluten,dairy,eggs",
     "notes": "Brownie húmedo con espresso. Horno 170°C 25 min.",
     "instructions": "1. Derretir chocolate cobertura con manteca a baño María.\n2. Batir huevos con azúcar hasta punto cinta. Sumar vainilla.\n3. Incorporar chocolate tibio. Sumar harina, cacao, café espresso, sal.\n4. Sumar nueces picadas.\n5. Horno 170°C 25 min. Centro húmedo."},
    {"id": 14, "slug": "chocolate_muffin", "name": "chocolate_muffin",
     "yield_qty": 12, "yield_unit": "und", "family": "pastelería",
     "difficulty": 3, "allergens": "gluten,dairy,eggs",
     "notes": "Muffin de chocolate tamaño bandeja 20x20 cm. Horno 180°C 25-30 min.",
     "instructions": "1. Mezclar harina con cacao, polvo de hornear, sal.\n2. Batir huevos con azúcar y manteca.\n3. Incorporar harina alternando con leche.\n4. Sumar chips. Bandeja 20x20 enmantecada. Horno 180°C 25-30 min."},
    {"id": 15, "slug": "cheesecake_20x20", "name": "cheesecake_20x20",
     "yield_qty": 10, "yield_unit": "und", "family": "fríos",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Cheesecake sin horno. Bandeja 20x20 cm.",
     "instructions": "1. Triturar galletas con manteca. Forrar bandeja.\n2. Batir queso crema con leche condensada y crema de leche.\n3. Verter sobre base. Refrigerar 4+ horas."},
    {"id": 16, "slug": "stroopwafel_simple", "name": "stroopwafel_simple",
     "yield_qty": 8, "yield_unit": "und", "family": "pastelería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Stroopwafel clásico. Plancha doble 3 min.",
     "instructions": "1. Batir huevos con azúcar y manteca. Sumar harina y esencia de vainilla.\n2. Cocinar en waflera 3 min.\n3. Rellenar con sirope de azúcar/miel."},
    {"id": 17, "slug": "ontbijtkoek", "name": "ontbijtkoek",
     "yield_qty": 10, "yield_unit": "und", "family": "panadería",
     "difficulty": 2, "allergens": "gluten",
     "notes": "Pan dulce especiado holandés. Horno 160°C 50 min.",
     "instructions": "1. Mezclar harina de centeno con harina de trigo, melaza, miel.\n2. Sumar especias, jengibre, nuez moscada, canela.\n3. Agregar leche y agua. Batir.\n4. Horno 160°C 50 min en molde rectangular."},
    {"id": 18, "slug": "carrot_cake", "name": "carrot_cake",
     "yield_qty": 30, "yield_unit": "und", "family": "pastelería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs,nuts,raisins",
     "notes": "Bandeja familiar 43x33x1.5 cm. Carrot cake clásico.",
     "instructions": "1. Mezclar harina, polvo de hornear, bicarbonato, especias.\n2. Batir huevos con azúcar y aceite. Sumar zanahoria rallada.\n3. Incorporar secos. Sumar nueces y pasas.\n4. Horno 175°C 45-50 min en bandeja enmantecada."},
    {"id": 19, "slug": "frikandel", "name": "frikandel",
     "yield_qty": 100, "yield_unit": "und", "family": "frituras",
     "difficulty": 3, "allergens": "gluten,eggs,soy,onion,garlic",
     "notes": "Salchicha holandesa. Carne molida fina con especias.",
     "instructions": "1. Mezclar carne molida con cebolla, ajo, pan rallado remojado.\n2. Sumar huevo, ketjap, nuez moscada, jengibre, anís estrella.\n3. Sazonar con sal y pimienta.\n4. Formar salchichas de 50g. Refrigerar 2 horas.\n5. Freír a 180°C 4-5 min hasta dorar."},
    {"id": 20, "slug": "ketjap_manis", "name": "ketjap_manis",
     "yield_qty": 3, "yield_unit": "und", "family": "salsas",
     "difficulty": 1, "allergens": "soy,gluten",
     "notes": "Salsa de soja dulce indonesia. Cocción 20 min.",
     "instructions": "1. Hervir salsa de soja con azúcar morena y melaza.\n2. Sumar ajo, jengibre, anís estrella.\n3. Cocinar 20 min a fuego bajo hasta espesar.\n4. Enfriar y envasar."},
    {"id": 21, "slug": "glaseado_queso_crema",
     "name": "glaseado_queso_crema",
     "yield_qty": 350, "yield_unit": "g", "family": "glaseados",
     "difficulty": 1, "allergens": "dairy",
     "notes": "Glaseado para carrot cake, muffins, brownies.",
     "instructions": "1. Batir queso crema con manteca hasta cremoso.\n2. Sumar azúcar impalpable tamizada en partes.\n3. Agregar esencia de vainilla. Batir hasta punto."},
    {"id": 22, "slug": "pepernoten", "name": "pepernoten",
     "yield_qty": 60, "yield_unit": "und", "family": "galletería",
     "difficulty": 1, "allergens": "gluten,dairy",
     "notes": "Galletas especiadas holandesas. Horno 160°C 15-18 min.",
     "instructions": "1. Batir manteca con azúcar morena hasta cremoso.\n2. Sumar melaza, huevo y especias speculaas.\n3. Incorporar harina y polvo de hornear.\n4. Refrigerar 2 horas. Formar bolitas pequeñas.\n5. Horno 160°C 15-18 min."},

    # === PARAGUAYAN ADDITIONS (Gaby's menu) ===
    {"id": 23, "slug": "chipa", "name": "chipa",
     "yield_qty": 30, "yield_unit": "und", "family": "panadería_paraguaya",
     "difficulty": 2, "allergens": "dairy,eggs",
     "notes": "Chipa paraguaya tradicional. Horno 200°C 18-20 min.",
     "instructions": "1. Mezclar almidón de mandioca con queso Paraguay rallado.\n2. Sumar huevos, manteca, grasa de cerdo derretida, sal, anís.\n3. Amasar hasta que se despegue. Reposar 30 min.\n4. Formar bollos pequeños. Horno 200°C 18-20 min."},
    {"id": 24, "slug": "mbeju", "name": "mbeju",
     "yield_qty": 12, "yield_unit": "und", "family": "panadería_paraguaya",
     "difficulty": 2, "allergens": "dairy",
     "notes": "Mbeju: tortilla de almidón. Sartén o plancha 3-4 min por lado.",
     "instructions": "1. Mezclar almidón de mandioca con queso Paraguay rallado.\n2. Sumar leche, manteca derretida, sal.\n3. Formar bollos y aplastar en discos finos.\n4. Cocinar en sartén o plancha 3-4 min por lado hasta dorar."},
    {"id": 25, "slug": "sopa_paraguaya", "name": "sopa_paraguaya",
     "yield_qty": 8, "yield_unit": "und", "family": "panadería_paraguaya",
     "difficulty": 2, "allergens": "dairy,eggs",
     "notes": "Sopa paraguaya. Horno 180°C 40-45 min.",
     "instructions": "1. Batir huevos con leche y manteca derretida.\n2. Sumar harina de maíz (o almidón), queso rallado, cebolla de verdeo.\n3. Salpimentar. Mezclar bien.\n4. Molde enmantecado. Horno 180°C 40-45 min."},
    {"id": 26, "slug": "kiveve", "name": "kiveve",
     "yield_qty": 8, "yield_unit": "und", "family": "postres_paraguayos",
     "difficulty": 2, "allergens": "dairy,eggs",
     "notes": "Postre de zapallo y coco. Horno 180°C 30 min.",
     "instructions": "1. Hervir zapallo hasta que esté blando. Hacer puré.\n2. Mezclar con coco rallado, azúcar, leche, manteca.\n3. Sumar huevos batidos y esencia de vainilla.\n4. Verter en molde. Horno 180°C 30 min hasta dorar."},
    {"id": 27, "slug": "payagua_mermelada",
     "name": "payaguá_mermelada",
     "yield_qty": 6, "yield_unit": "und", "family": "postres_paraguayos",
     "difficulty": 1, "allergens": "dairy",
     "notes": "Postre cremoso tipo payaguá. Refrigeración 3+ horas.",
     "instructions": "1. Mezclar leche con leche condensada y esencia de vainilla.\n2. Calentar hasta espesar ligeramente.\n3. Sumar gelatina sin sabor disuelta.\n4. Verter en moldes individuales. Refrigerar 3+ horas."},
    {"id": 28, "slug": "sandwich_miga", "name": "sandwich_miga",
     "yield_qty": 8, "yield_unit": "und", "family": "salados",
     "difficulty": 1, "allergens": "gluten,dairy",
     "notes": "Sándwiches de miga para pedido. Corte en triángulos.",
     "instructions": "1. Cortar pan lactal en rodajas finas, retirar corteza.\n2. Untar con mayonesa y rellenar con jamón y queso.\n3. Apilar 3 rodajas, prensar, envolver en film.\n4. Refrigerar 2+ horas. Cortar en triángulos."},
    {"id": 29, "slug": "torta_bodega", "name": "torta_bodega",
     "yield_qty": 12, "yield_unit": "und", "family": "panadería_paraguaya",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Torta de panadería típica. Horno 180°C 30-35 min.",
     "instructions": "1. Masa: mezclar harina con polvo de hornear, azúcar.\n2. Sumar huevos, leche, manteca, ralladura de limón.\n3. Batir hasta integrar. Molde enmantecado.\n4. Horno 180°C 30-35 min. Pinchar para verificar cocción."},
    {"id": 30, "slug": "medialunas", "name": "medialunas",
     "yield_qty": 24, "yield_unit": "und", "family": "panadería",
     "difficulty": 2, "allergens": "gluten,dairy,eggs",
     "notes": "Medialunas de manteca. Horno 190°C 15-20 min.",
     "instructions": "1. Masa: amasar harina, levadura, leche tibia, azúcar, huevos y manteca.\n2. Levar 1.5 horas.\n3. Estirar en círculo, cortar triángulos, enrollar desde la base.\n4. Pintar con huevo. Horno 190°C 15-20 min."},
]

RECIPES_BY_SLUG: Dict[str, Dict[str, Any]] = {r["slug"]: r for r in _RECIPES}
RECIPES_BY_ID: Dict[int, Dict[str, Any]] = {r["id"]: r for r in _RECIPES}


# ----------------------------------------------------------------------------
# CANONICAL PRODUCTS
# 30 from research + 13 new Paraguayan SKUs.
# We use the existing live numeric ids (1-30) and add 31-43 for Paraguayan.
# The product seed will create missing rows by name (idempotent) and
# update prices/details on existing ones.
# ----------------------------------------------------------------------------
_PRODUCTS: List[Dict[str, Any]] = [
    # === DULCE/PASTELERÍA BÁSICA ===
    {"id": 1, "name": "Muffin de vainilla", "recipe_slug": "muffin_vainilla",
     "sale_price_gs": 8000, "mayorista_price_gs": 7000,
     "portion_label": "Docena", "sku": "MUF-VAN-D", "is_available": True},
    {"id": 2, "name": "Muffin de chocolate", "recipe_slug": "muffin_chocolate",
     "sale_price_gs": 8500, "mayorista_price_gs": 7500,
     "portion_label": "Docena", "sku": "MUF-CHO-D", "is_available": True},
    {"id": 3, "name": "Muffin de nueces", "recipe_slug": "muffin_nueces",
     "sale_price_gs": 9500, "mayorista_price_gs": 8500,
     "portion_label": "Docena", "sku": "MUF-NUE-D", "is_available": True},
    {"id": 4, "name": "Docena muffins vainilla", "recipe_slug": "muffin_vainilla",
     "sale_price_gs": 96000, "mayorista_price_gs": 84000,
     "portion_label": "12 und", "sku": "MUF-VAN-12", "is_available": True},
    {"id": 5, "name": "Docena muffins chocolate", "recipe_slug": "muffin_chocolate",
     "sale_price_gs": 108000, "mayorista_price_gs": 96000,
     "portion_label": "12 und", "sku": "MUF-CHO-12", "is_available": True},

    # === CHEESECAKE ===
    {"id": 6, "name": "Cheesecake clásico", "recipe_slug": "cheesecake",
     "sale_price_gs": 28000, "mayorista_price_gs": 25000,
     "portion_label": "1 und", "sku": "CHE-CLA-1", "is_available": True},
    {"id": 7, "name": "Cheesecake entera", "recipe_slug": "cheesecake",
     "sale_price_gs": 200000, "mayorista_price_gs": 180000,
     "portion_label": "1 entera", "sku": "CHE-ENT-1", "is_available": True},

    # === HOJALDRE ===
    {"id": 8, "name": "Hojaldre dulce", "recipe_slug": "hojaldre_dulce",
     "sale_price_gs": 6000, "mayorista_price_gs": 5000,
     "portion_label": "1 und", "sku": "HOJ-DUL-1", "is_available": True},
    {"id": 9, "name": "Docena hojaldres", "recipe_slug": "hojaldre_dulce",
     "sale_price_gs": 72000, "mayorista_price_gs": 60000,
     "portion_label": "12 und", "sku": "HOJ-DUL-12", "is_available": True},

    # === TARTAS ===
    {"id": 10, "name": "Appeltaart", "recipe_slug": "appeltaart",
     "sale_price_gs": 28000, "mayorista_price_gs": 25000,
     "portion_label": "1 und", "sku": "APP-MED-1", "is_available": True},
    {"id": 11, "name": "Tompoezen", "recipe_slug": "tompoezen",
     "sale_price_gs": 12000, "mayorista_price_gs": 10000,
     "portion_label": "1 und", "sku": "TOM-IND-1", "is_available": True},
    {"id": 12, "name": "Docena tompoezen", "recipe_slug": "tompoezen",
     "sale_price_gs": 130000, "mayorista_price_gs": 110000,
     "portion_label": "12 und", "sku": "TOM-DOC-12", "is_available": True},

    # === FRITURAS ===
    {"id": 13, "name": "Oliebollen (unidad)", "recipe_slug": "oliebollen",
     "sale_price_gs": 5500, "mayorista_price_gs": 4500,
     "portion_label": "1 und", "sku": "OLI-UNI-1", "is_available": True},
    {"id": 14, "name": "Docena oliebollen", "recipe_slug": "oliebollen",
     "sale_price_gs": 70000, "mayorista_price_gs": 60000,
     "portion_label": "12 und", "sku": "OLI-DOC-12", "is_available": True},

    # === PANES DULCES ===
    {"id": 15, "name": "Babka de chocolate", "recipe_slug": "babka",
     "sale_price_gs": 25000, "mayorista_price_gs": 22000,
     "portion_label": "1 und", "sku": "BAB-CHO-1", "is_available": True},
    {"id": 16, "name": "Stroopwafel", "recipe_slug": "stroopwafel",
     "sale_price_gs": 7000, "mayorista_price_gs": 6000,
     "portion_label": "1 und", "sku": "STR-IND-1", "is_available": True},
    {"id": 17, "name": "Docena stroopwafels", "recipe_slug": "stroopwafel",
     "sale_price_gs": 80000, "mayorista_price_gs": 70000,
     "portion_label": "12 und", "sku": "STR-DOC-12", "is_available": True},

    # === PANES BÁSICOS ===
    {"id": 18, "name": "Pan lactal", "recipe_slug": "pan_lactal",
     "sale_price_gs": 14000, "mayorista_price_gs": 12000,
     "portion_label": "1 und", "sku": "PAN-LAC-1", "is_available": True},
    {"id": 19, "name": "Facturas (docena)", "recipe_slug": "facturas",
     "sale_price_gs": 35000, "mayorista_price_gs": 30000,
     "portion_label": "12 und", "sku": "FAC-DOC-12", "is_available": True},
    {"id": 20, "name": "Facturas (media docena)", "recipe_slug": "facturas",
     "sale_price_gs": 18000, "mayorista_price_gs": 15000,
     "portion_label": "6 und", "sku": "FAC-MED-6", "is_available": True},

    # === BROWNIES / BANDAS ===
    {"id": 21, "name": "Brownie espresso", "recipe_slug": "brownie_espresso",
     "sale_price_gs": 22000, "mayorista_price_gs": 20000,
     "portion_label": "Docena", "sku": "BRO-ESP-D", "is_available": True},
    {"id": 22, "name": "Brownie espresso (bandeja 20x20)",
     "recipe_slug": "chocolate_muffin",
     "sale_price_gs": 45000, "mayorista_price_gs": 40000,
     "portion_label": "1 bandeja", "sku": "BRO-BAN-20", "is_available": True},
    {"id": 23, "name": "Cheesecake (bandeja 20x20)",
     "recipe_slug": "cheesecake_20x20",
     "sale_price_gs": 95000, "mayorista_price_gs": 85000,
     "portion_label": "1 bandeja", "sku": "CHE-BAN-20", "is_available": True},
    {"id": 24, "name": "Stroop Waffle (pack 4)",
     "recipe_slug": "stroopwafel_simple",
     "sale_price_gs": 25000, "mayorista_price_gs": 22000,
     "portion_label": "4 und", "sku": "STR-PCK-4", "is_available": True},

    # === ESPECIALES ===
    {"id": 25, "name": "Ontbijtkoek (700g)", "recipe_slug": "ontbijtkoek",
     "sale_price_gs": 35000, "mayorista_price_gs": 30000,
     "portion_label": "700g", "sku": "ONT-700G", "is_available": True},
    {"id": 26, "name": "Carrot Cake (43x33 cm)", "recipe_slug": "carrot_cake",
     "sale_price_gs": 95000, "mayorista_price_gs": 85000,
     "portion_label": "1 bandeja", "sku": "CAR-BAN-43", "is_available": True},
    {"id": 27, "name": "Frikandel (unidad)", "recipe_slug": "frikandel",
     "sale_price_gs": 4000, "mayorista_price_gs": 3500,
     "portion_label": "1 und", "sku": "FRI-UNI-1", "is_available": True},
    {"id": 28, "name": "Ketjap Manis (botella 500ml)",
     "recipe_slug": "ketjap_manis",
     "sale_price_gs": 19500, "mayorista_price_gs": 17000,
     "portion_label": "500 ml", "sku": "KET-BOT-500", "is_available": True},
    {"id": 29, "name": "Pepernoten (bolsa 60 und)",
     "recipe_slug": "pepernoten",
     "sale_price_gs": 18000, "mayorista_price_gs": 15000,
     "portion_label": "60 und", "sku": "PEP-BOL-60", "is_available": True},
    {"id": 30, "name": "Glaseado de queso crema (200g)",
     "recipe_slug": "glaseado_queso_crema",
     "sale_price_gs": 15000, "mayorista_price_gs": 12000,
     "portion_label": "200g", "sku": "GLA-QUE-200", "is_available": True},

    # === PARAGUAYAN (Gaby's menu) ===
    {"id": 31, "name": "Chipa (docena)", "recipe_slug": "chipa",
     "sale_price_gs": 30000, "mayorista_price_gs": 25000,
     "portion_label": "12 und", "sku": "CHI-DOC-12", "is_available": True},
    {"id": 32, "name": "Chipa (unidad)", "recipe_slug": "chipa",
     "sale_price_gs": 3000, "mayorista_price_gs": 2500,
     "portion_label": "1 und", "sku": "CHI-UNI-1", "is_available": True},
    {"id": 33, "name": "Chipa (1 kg)", "recipe_slug": "chipa",
     "sale_price_gs": 45000, "mayorista_price_gs": 40000,
     "portion_label": "1 kg", "sku": "CHI-KG-1", "is_available": True},
    {"id": 34, "name": "Mbeju (docena)", "recipe_slug": "mbeju",
     "sale_price_gs": 28000, "mayorista_price_gs": 24000,
     "portion_label": "12 und", "sku": "MBE-DOC-12", "is_available": True},
    {"id": 35, "name": "Mbeju (unidad)", "recipe_slug": "mbeju",
     "sale_price_gs": 2500, "mayorista_price_gs": 2000,
     "portion_label": "1 und", "sku": "MBE-UNI-1", "is_available": True},
    {"id": 36, "name": "Sopa paraguaya (porción)",
     "recipe_slug": "sopa_paraguaya",
     "sale_price_gs": 8500, "mayorista_price_gs": 7500,
     "portion_label": "1 und", "sku": "SOP-PAR-1", "is_available": True},
    {"id": 37, "name": "Sopa paraguaya (entera)",
     "recipe_slug": "sopa_paraguaya",
     "sale_price_gs": 65000, "mayorista_price_gs": 58000,
     "portion_label": "1 entera", "sku": "SOP-PAR-E", "is_available": True},
    {"id": 38, "name": "Kiveve (porción)", "recipe_slug": "kiveve",
     "sale_price_gs": 7500, "mayorista_price_gs": 6500,
     "portion_label": "1 und", "sku": "KIV-POR-1", "is_available": True},
    {"id": 39, "name": "Payaguá (porción)", "recipe_slug": "payagua_mermelada",
     "sale_price_gs": 8000, "mayorista_price_gs": 7000,
     "portion_label": "1 und", "sku": "PAY-POR-1", "is_available": True},
    {"id": 40, "name": "Sándwich de miga (pack 4)",
     "recipe_slug": "sandwich_miga",
     "sale_price_gs": 32000, "mayorista_price_gs": 28000,
     "portion_label": "4 und", "sku": "SAN-MIG-4", "is_available": True},
    {"id": 41, "name": "Sándwich de miga (pack 8)",
     "recipe_slug": "sandwich_miga",
     "sale_price_gs": 55000, "mayorista_price_gs": 48000,
     "portion_label": "8 und", "sku": "SAN-MIG-8", "is_available": True},
    {"id": 42, "name": "Torta de panadería (entera)",
     "recipe_slug": "torta_bodega",
     "sale_price_gs": 85000, "mayorista_price_gs": 75000,
     "portion_label": "1 entera", "sku": "TOR-PAN-E", "is_available": True},
    {"id": 43, "name": "Medialunas (docena)", "recipe_slug": "medialunas",
     "sale_price_gs": 28000, "mayorista_price_gs": 24000,
     "portion_label": "12 und", "sku": "MED-DOC-12", "is_available": True},
]

PRODUCTS_BY_SLUG: Dict[str, Dict[str, Any]] = {p["name"]: p for p in _PRODUCTS}


# ----------------------------------------------------------------------------
# PATCHES (data quality fixes applied during seed)
# ----------------------------------------------------------------------------
# Known data errors. Each entry says what to do to the live row.
# - "rename": change the name to canonical.
# - "soft_delete": set deleted_at = now (used for obviously wrong data).
# - "fix_availability": set is_available = True with sane price.
# - "fix_price": overwrite the sale_price_gs to canonical value.

# Recipe 22 might be named differently in live — canonical is "pepernoten".
RENAME_RECIPES = {}  # {}: 22 → "pepernoten"  # id: new_name

# Soft-delete the bogus "gold leaves" ingredient. It had a price of 5,000,000
# Gs (~$625 USD per leaf), is not referenced by any recipe or product,
# and was almost certainly a test row that survived in the live DB.
SOFT_DELETE_INGREDIENT_NAMES = ["gold leaves"]


# ----------------------------------------------------------------------------
# Recipe lines (ingredients per recipe) — Phase 18.2
# ----------------------------------------------------------------------------
# Curated lines for the new Paraguayan recipes (no research xlsx coverage).
# Format: recipe_slug → list of (ingredient_slug, qty, line_unit)
#   - line_unit ∈ {"g", "kg", "ml", "l", "und", ""}
#   - "" = use the ingredient's own unit
#   - ingredient_slug matches INGREDIENTS_BY_SLUG keys
#
# These recipes are NEW — no existing recipe_line rows in live DB.
# Idempotent: if a recipe already has lines, we skip seeding for that recipe.

_RECIPE_LINES: Dict[str, List[Dict[str, Any]]] = {
    "chipa": [
        # Chipa tradicional paraguaya. Rinde ~30 unidades.
        {"ingredient_slug": "almidon_mandioca", "qty": 500, "line_unit": "g"},
        {"ingredient_slug": "queso_paraguay", "qty": 250, "line_unit": "g"},
        {"ingredient_slug": "huevo", "qty": 2, "line_unit": "und"},
        {"ingredient_slug": "leche", "qty": 200, "line_unit": "ml"},
        {"ingredient_slug": "manteca", "qty": 80, "line_unit": "g"},
        {"ingredient_slug": "sal", "qty": 5, "line_unit": "g"},
        {"ingredient_slug": "azucar", "qty": 10, "line_unit": "g"},
    ],
    "mbeju": [
        # Mbeju — tortilla de almidón. Rinde ~12 unidades.
        {"ingredient_slug": "almidon_mandioca", "qty": 400, "line_unit": "g"},
        {"ingredient_slug": "queso_paraguay", "qty": 200, "line_unit": "g"},
        {"ingredient_slug": "manteca", "qty": 100, "line_unit": "g"},
        {"ingredient_slug": "leche", "qty": 100, "line_unit": "ml"},
        {"ingredient_slug": "sal", "qty": 3, "line_unit": "g"},
    ],
    "sopa_paraguaya": [
        # Sopa paraguaya (NO es sopa — es pan de queso). Rinde 1 molde 20x20.
        {"ingredient_slug": "almidon_mandioca", "qty": 300, "line_unit": "g"},
        {"ingredient_slug": "queso_paraguay", "qty": 300, "line_unit": "g"},
        {"ingredient_slug": "huevo", "qty": 4, "line_unit": "und"},
        {"ingredient_slug": "leche", "qty": 400, "line_unit": "ml"},
        {"ingredient_slug": "manteca", "qty": 100, "line_unit": "g"},
        {"ingredient_slug": "cebolla", "qty": 2, "line_unit": "und"},
        {"ingredient_slug": "sal", "qty": 8, "line_unit": "g"},
    ],
    "kiveve": [
        # Kiveve — puré de zapallo con queso. Rinde 8 porciones.
        {"ingredient_slug": "zapallo", "qty": 1, "line_unit": "kg"},
        {"ingredient_slug": "queso_paraguay", "qty": 200, "line_unit": "g"},
        {"ingredient_slug": "manteca", "qty": 50, "line_unit": "g"},
        {"ingredient_slug": "cebolla", "qty": 1, "line_unit": "und"},
        {"ingredient_slug": "sal", "qty": 5, "line_unit": "g"},
        {"ingredient_slug": "azucar", "qty": 15, "line_unit": "g"},
    ],
    "payagua_mermelada": [
        # Payaguá — mermelada de mamón. Rinde ~6 frascos 250g.
        {"ingredient_slug": "mamon", "qty": 1.5, "line_unit": "kg"},
        {"ingredient_slug": "azucar", "qty": 750, "line_unit": "g"},
        {"ingredient_slug": "limon", "qty": 1, "line_unit": "und"},
        {"ingredient_slug": "frasco_vidrio", "qty": 6, "line_unit": "und"},
    ],
    "sandwich_miga": [
        # Sándwich de miga — triple. Rinde 12 sandwiches.
        {"ingredient_slug": "pan_miga", "qty": 36, "line_unit": "und"},  # 3 rebanadas por sándwich
        {"ingredient_slug": "queso_muzzarella", "qty": 300, "line_unit": "g"},
        {"ingredient_slug": "jamon_cocido", "qty": 300, "line_unit": "g"},
        {"ingredient_slug": "manteca", "qty": 100, "line_unit": "g"},
    ],
    "torta_bodega": [
        # Torta bodega — bizcocho húmedo. Rinde 12 porciones.
        {"ingredient_slug": "harina", "qty": 300, "line_unit": "g"},
        {"ingredient_slug": "azucar", "qty": 250, "line_unit": "g"},
        {"ingredient_slug": "huevo", "qty": 3, "line_unit": "und"},
        {"ingredient_slug": "leche", "qty": 200, "line_unit": "ml"},
        {"ingredient_slug": "manteca", "qty": 100, "line_unit": "g"},
        {"ingredient_slug": "cacao_polvo", "qty": 30, "line_unit": "g"},
        {"ingredient_slug": "polvo_hornear", "qty": 10, "line_unit": "g"},
        {"ingredient_slug": "vainilla", "qty": 5, "line_unit": "ml"},
    ],
    "medialunas": [
        # Medialunas argentinas (facturas). Rinde 24 unidades.
        {"ingredient_slug": "harina", "qty": 500, "line_unit": "g"},
        {"ingredient_slug": "manteca", "qty": 200, "line_unit": "g"},
        {"ingredient_slug": "azucar", "qty": 100, "line_unit": "g"},
        {"ingredient_slug": "leche", "qty": 200, "line_unit": "ml"},
        {"ingredient_slug": "huevo", "qty": 2, "line_unit": "und"},
        {"ingredient_slug": "levadura", "qty": 15, "line_unit": "g"},
        {"ingredient_slug": "sal", "qty": 5, "line_unit": "g"},
        {"ingredient_slug": "vainilla", "qty": 5, "line_unit": "ml"},
    ],
    "glaseado_queso_crema": [
        # Glaseado para carrot cake. Rinde ~500g.
        {"ingredient_slug": "queso_crema", "qty": 250, "line_unit": "g"},
        {"ingredient_slug": "manteca", "qty": 100, "line_unit": "g"},
        {"ingredient_slug": "azucar_impalpable", "qty": 300, "line_unit": "g"},
        {"ingredient_slug": "vainilla", "qty": 5, "line_unit": "ml"},
    ],
}


# ----------------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------------
def seed_catalog(session) -> Dict[str, Any]:
    """Idempotent seed of the canonical catalog. Returns a stats dict.

    Strategy:
      - Ingredients: by name (case-insensitive). If exists → update price/
        category/notes/allergens/packaging; if not → create.
      - Recipes: by name (case-insensitive). If exists → update notes/
        family/allergens/instructions; if not → create.
      - Products: by name. If exists → update price/portion/sku/avail;
        if not → create with next free id.
      - Rename: recipe id 22 → "pepernoten" (one-shot, then no-op).
      - Soft-delete: ingredient "gold leaves" (one-shot).
    """
    from app.rms.models import Ingredient, Product, Recipe

    stats: Dict[str, Any] = {
        "ingredients_created": 0,
        "ingredients_updated": 0,
        "recipes_created": 0,
        "recipes_updated": 0,
        "recipes_renamed": 0,
        "products_created": 0,
        "products_updated": 0,
        "ingredients_soft_deleted": 0,
        "recipe_lines_created": 0,
        "recipe_lines_skipped_existing": 0,
        "recipe_lines_missing_ingredient": 0,
    }
    now = datetime.now(timezone.utc)

    # ----- INGREDIENTS -----
    # Filter out soft-deleted rows via raw SQL so we don't depend on
    # a SQLAlchemy attribute that may not be mapped. (The DB has
    # `deleted_at`; the model may not, depending on migration order.)
    _active_ing_rows = session.execute(
        __import__("sqlalchemy").text(
            "SELECT id, name FROM ingredient WHERE deleted_at IS NULL"
        )
    ).fetchall()
    # Map name directly to Ingredient object for faster lookup.
    existing_ings = {
        row[1].lower(): session.query(Ingredient).filter_by(id=row[0]).first()
        for row in _active_ing_rows
    }
    # Filter out None (in case some rows were deleted)
    existing_ings = {k: v for k, v in existing_ings.items() if v is not None}
    for ing_data in _INGREDIENTS:
        canonical_name = ing_data["name"]
        key = canonical_name.lower()
        existing = existing_ings.get(key)
        if existing is None:
            # Also try fuzzy match (the live DB has both "harina" and
            # "Harina de trigo 000" historically; prefer canonical).
            session.add(Ingredient(
                name=canonical_name,
                unit=ing_data["unit"],
                purchase_price_gs=ing_data["purchase_price_gs"],
                category=ing_data["category"],
                subcategory=ing_data.get("subcategory"),
                role=ing_data.get("role") or "ingredient",
                allergens=ing_data.get("allergens") or None,
                notes=ing_data.get("notes") or None,
                is_packaging=ing_data.get("is_packaging", False),
                stock_qty=0,
                min_stock_qty=0,
            ))
            stats["ingredients_created"] += 1
        else:
            # Only update fields if they would change; this keeps
            # the audit log quiet.
            changed = False
            if existing.purchase_price_gs != ing_data["purchase_price_gs"]:
                existing.purchase_price_gs = ing_data["purchase_price_gs"]
                changed = True
            if existing.category != ing_data["category"]:
                existing.category = ing_data["category"]
                changed = True
            if existing.unit != ing_data["unit"]:
                existing.unit = ing_data["unit"]
                changed = True
            if (existing.notes or "") != (ing_data.get("notes") or ""):
                existing.notes = ing_data.get("notes") or None
                changed = True
            if (existing.allergens or "") != (ing_data.get("allergens") or ""):
                existing.allergens = ing_data.get("allergens") or None
                changed = True
            if bool(existing.is_packaging) != bool(ing_data.get("is_packaging")):
                existing.is_packaging = bool(ing_data.get("is_packaging"))
                changed = True
            if changed:
                stats["ingredients_updated"] += 1
    session.flush()

    # ----- RECIPES -----
    # Apply renames first.
    for recipe_id, new_name in RENAME_RECIPES.items():
        rec = session.query(Recipe).filter_by(id=recipe_id).first()
        if rec and rec.name != new_name:
            rec.name = new_name
            stats["recipes_renamed"] += 1

    # Build the name → id map. Filter out soft-deleted recipes.
    _active_rec_rows = session.execute(
        __import__("sqlalchemy").text(
            "SELECT id, name FROM recipe WHERE deleted_at IS NULL"
        )
    ).fetchall()
    # Map name directly to Recipe object for faster lookup.
    recipe_by_name = {
        row[1].lower(): session.query(Recipe).filter_by(id=row[0]).first()
        for row in _active_rec_rows
    }
    # Filter out None (in case some rows were deleted)
    recipe_by_name = {k: v for k, v in recipe_by_name.items() if v is not None}
    for r_data in _RECIPES:
        canonical_name = r_data["name"]
        key = canonical_name.lower()
        existing = recipe_by_name.get(key)
        if existing is None:
            session.add(Recipe(
                name=canonical_name,
                yield_qty=r_data["yield_qty"],
                yield_unit=r_data["yield_unit"],
                family=r_data["family"],
                difficulty=r_data["difficulty"],
                allergens=r_data["allergens"],
                notes=r_data.get("notes") or None,
                instructions=r_data.get("instructions") or None,
            ))
            stats["recipes_created"] += 1
        else:
            changed = False
            if existing.yield_qty != r_data["yield_qty"]:
                existing.yield_qty = r_data["yield_qty"]
                changed = True
            if (existing.yield_unit or "") != r_data["yield_unit"]:
                existing.yield_unit = r_data["yield_unit"]
                changed = True
            if (existing.family or "") != r_data["family"]:
                existing.family = r_data["family"]
                changed = True
            if (existing.allergens or "") != r_data["allergens"]:
                existing.allergens = r_data["allergens"]
                changed = True
            if existing.difficulty != r_data["difficulty"]:
                existing.difficulty = r_data["difficulty"]
                changed = True
            if (existing.notes or "") != (r_data.get("notes") or ""):
                existing.notes = r_data.get("notes") or None
                changed = True
            # Always update instructions so the voseo Spanish we curated
            # is present. This is the data we wrote from research.
            if (r_data.get("instructions") or "") and (
                not existing.instructions
                or existing.instructions != r_data["instructions"]
            ):
                existing.instructions = r_data["instructions"]
                changed = True
            if changed:
                stats["recipes_updated"] += 1
    session.flush()

    # ----- PRODUCTS -----
    # Build the recipe slug → id map.
    slug_to_recipe_id = {
        r.name.lower(): r.id for r in session.query(Recipe).all()
    }

    # Build name → product, filter out soft-deleted.
    _active_prod_rows = session.execute(
        __import__("sqlalchemy").text(
            "SELECT id, name FROM product WHERE deleted_at IS NULL"
        )
    ).fetchall()
    # Map name directly to Product object for faster lookup.
    product_by_name = {
        row[1].lower(): session.query(Product).filter_by(id=row[0]).first()
        for row in _active_prod_rows
    }
    # Filter out None (in case some rows were deleted)
    product_by_name = {k: v for k, v in product_by_name.items() if v is not None}

    for p_data in _PRODUCTS:
        canonical_name = p_data["name"]
        key = canonical_name.lower()
        existing = product_by_name.get(key)
        recipe_id = slug_to_recipe_id.get(p_data["recipe_slug"].lower())
        if existing is None:
            session.add(Product(
                name=canonical_name,
                portion_label=p_data["portion_label"],
                sale_price_gs=p_data["sale_price_gs"],
                mayorista_price_gs=p_data["mayorista_price_gs"],
                recipe_id=recipe_id,
                sku=p_data["sku"],
                is_available=p_data["is_available"],
                tablet_visible=True,
                iva_rate="10",
            ))
            stats["products_created"] += 1
        else:
            # existing should be a Product object, but handle race condition if deleted
            if existing is None:
                # Race condition: product was deleted between query and now. Skip.
                continue
            changed = False
            if (existing.portion_label or "") != p_data["portion_label"]:
                existing.portion_label = p_data["portion_label"]
                changed = True
            if (existing.sale_price_gs or 0) != p_data["sale_price_gs"]:
                existing.sale_price_gs = p_data["sale_price_gs"]
                changed = True
            if (existing.mayorista_price_gs or 0) != p_data["mayorista_price_gs"]:
                existing.mayorista_price_gs = p_data["mayorista_price_gs"]
                changed = True
            if (existing.sku or "") != p_data["sku"]:
                existing.sku = p_data["sku"]
                changed = True
            if existing.recipe_id != recipe_id:
                existing.recipe_id = recipe_id
                changed = True
            if not existing.is_available and p_data["is_available"]:
                existing.is_available = True
                changed = True
            if changed:
                stats["products_updated"] += 1
    session.flush()

    # ----- RECIPE LINES (Phase 18.2) -----
    # Seed recipe_line rows for new Paraguayan recipes that don't have lines yet.
    # Idempotent: skip recipes that already have lines.
    from app.rms.models import RecipeLine
    # Build ingredient name → id map (raw SQL to avoid deleted_at attribute issues)
    _ing_rows = session.execute(
        __import__("sqlalchemy").text(
            "SELECT id, name FROM ingredient WHERE deleted_at IS NULL OR deleted_at IS NULL"
        )
    ).fetchall()
    # Build slug → name mapping from INGREDIENTS_BY_SLUG
    # This allows _RECIPE_LINES to use slugs (e.g., "almidon_mandioca")
    # while the DB has full names (e.g., "Almidón de mandioca")
    import unicodedata
    def _strip_accents(s):
        return "".join(
            c for c in unicodedata.normalize("NFD", s)
            if unicodedata.category(c) != "Mn"
        )
    def _slugify(s):
        """Convert 'Almidón de mandioca' → 'almidon_de_mandioca'"""
        s = _strip_accents(s.lower())
        return "_".join(s.split())
    ingredient_by_slug = {}
    for ing_slug, ing_data in INGREDIENTS_BY_SLUG.items():
        full_name = ing_data["name"]
        # Map by canonical slug key
        ingredient_by_slug[ing_slug] = None  # Will be set below
    # Now build the actual lookup: slug → ingredient_id
    all_ingredient_names = {row[1].lower(): row[0] for row in _ing_rows}
    for ing_slug, ing_data in INGREDIENTS_BY_SLUG.items():
        full_name = ing_data["name"]
        # Try exact match first
        if full_name.lower() in all_ingredient_names:
            ingredient_by_slug[ing_slug] = all_ingredient_names[full_name.lower()]
        else:
            # Try slugified match
            target_slug = _slugify(full_name)
            for db_name, db_id in all_ingredient_names.items():
                if _slugify(db_name) == target_slug:
                    ingredient_by_slug[ing_slug] = db_id
                    break

    for recipe_slug, lines_data in _RECIPE_LINES.items():
        # Find recipe by slug — handle accents (e.g., "payaguá_mermelada"
        # vs the ASCII "payagua_mermelada" key in our dict)
        recipe_obj = None
        # Build a normalized version of the slug (strip accents)
        target_normalized = _strip_accents(recipe_slug.lower())
        for r in session.query(Recipe).all():
            r_normalized = _strip_accents(r.name.lower())
            if r_normalized == target_normalized:
                recipe_obj = r
                break

        if recipe_obj is None:
            continue  # Recipe not in DB, skip

        # Check if this recipe already has lines (idempotency)
        existing_line_count = session.query(RecipeLine).filter_by(
            recipe_id=recipe_obj.id
        ).count()
        if existing_line_count > 0:
            stats["recipe_lines_skipped_existing"] += 1
            continue

        # Seed lines
        for line_data in lines_data:
            ing_slug = line_data["ingredient_slug"]
            ing_id = ingredient_by_slug.get(ing_slug)
            if ing_id is None:
                # Try fuzzy match
                for db_slug, db_id in ingredient_by_slug.items():
                    if ing_slug in db_slug or db_slug in ing_slug:
                        ing_id = db_id
                        break
            if ing_id is None:
                stats["recipe_lines_missing_ingredient"] += 1
                continue  # Ingredient not in DB, skip this line

            session.add(RecipeLine(
                recipe_id=recipe_obj.id,
                line_kind="ingredient",
                line_ref_id=ing_id,
                qty=line_data["qty"],
                line_unit=line_data.get("line_unit", ""),
            ))
            stats["recipe_lines_created"] += 1
    session.flush()

    # ----- SOFT DELETES (data quality) -----
    for bad_name in SOFT_DELETE_INGREDIENT_NAMES:
        bad_rows = session.execute(
            __import__("sqlalchemy").text(
                "SELECT id FROM ingredient "
                "WHERE LOWER(name) LIKE LOWER(:name) AND deleted_at IS NULL"
            ),
            {"name": f"%{bad_name}%"}
        ).fetchall()
        for row in bad_rows:
            bad = session.query(Ingredient).get(row.id)
            if bad is not None:
                bad.deleted_at = now
                stats["ingredients_soft_deleted"] += 1

    return stats


__all__ = [
    "seed_catalog",
    "INGREDIENTS_BY_SLUG",
    "RECIPES_BY_SLUG",
    "RECIPES_BY_ID",
    "PRODUCTS_BY_SLUG",
    "RENAME_RECIPES",
    "SOFT_DELETE_INGREDIENT_NAMES",
]
