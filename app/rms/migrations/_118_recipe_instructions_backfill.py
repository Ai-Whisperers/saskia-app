"""Migration 118: backfill Recipe.instructions for the 21 known recipes.

SASKIA-212: the schema column `recipe.instructions` was added in
migration 057 but the live DB never had a follow-up backfill for the
existing 22 recipes — they all show the "Procedimiento pendiente"
fallback. This migration looks up each Recipe by exact name match
against `_RECIPE_INSTRUCTIONS` and writes the structured phases JSON.

The migration is idempotent: it UPDATEs the column, so re-running it
overwrites the placeholder with the same content. The contaminated
imported row ("1.0"/"RECETA"/"test" with 25+ lines) is left untouched
and stays flagged in the UI.

Reference: scripts/seed_full_recipe_data.py is the source of truth for
the per-recipe procedure content. It was run once on 2026-09-29 but
the partial failure was never turned into a proper migration.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

# ── Per-recipe instructions (SASKIA-212 backfill) ──────────────────────
# Each value is a list of phases; each phase has phase/title/steps
# matching the JSON shape receta_detalle.html iterates over.
_RECIPE_INSTRUCTIONS: dict[str, list[dict]] = {
    "appeltaart": [
        {
            "phase": "Sub-receta",
            "title": "Relleno de manzana",
            "steps": [
                "Pela y fileteá las manzanas en láminas finas.",
                "Mezclá con azúcar, canela y unas gotas de limón.",
                "Reservá 15 minutos para que largue jugo.",
            ],
        },
        {
            "phase": "Base",
            "title": "Masa brisée",
            "steps": [
                "Mezclá la harina con la manteca fría hasta formar un arenado.",
                "Agregá el azúcar y los huevos; uní sin trabajar de más.",
                "Reservá en heladera 30 minutos envuelta en film.",
            ],
        },
        {
            "phase": "Ensamblaje",
            "title": "Tarta de manzanas",
            "steps": [
                "Estirá la masa y forrá un molde enmantecado.",
                "Disponé las láminas de manzana en forma concéntrica.",
                "Cubrí con tiras de masa formando un enrejado.",
                "Horneá a 200 °C durante 35 a 40 minutos hasta dorar.",
            ],
        },
    ],
    "tarta de manzana": [
        {
            "phase": "Base",
            "title": "Masa",
            "steps": [
                "Mezclá harina, manteca fría, azúcar y huevo hasta unir.",
                "Reservá en heladera 30 minutos envuelta en film.",
            ],
        },
        {
            "phase": "Relleno",
            "title": "Manzanas",
            "steps": [
                "Pela y cortá las manzanas en láminas finas.",
                "Mezclá con azúcar, canela y jugo de limón.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Terminación",
            "steps": [
                "Forrá el molde con la masa estirada.",
                "Distribuí las láminas de manzana en forma de espiral.",
                "Horneá a 200 °C por 35 a 40 minutos hasta dorar.",
            ],
        },
    ],
    "brownie de chocolate": [
        {
            "phase": "Preparación",
            "title": "Mise en place",
            "steps": [
                "Precalentá el horno a 180 °C.",
                "Enmantecá y enhariná un molde cuadrado de 20 cm.",
            ],
        },
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Derretí el chocolate con la manteca a baño María.",
                "Batí los huevos con el azúcar hasta punto letra.",
                "Incorporá el chocolate derretido sin batir de más.",
                "Agregá la harina y la sal tamizadas con movimientos envolventes.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá la mezcla en el molde y nivelá.",
                "Horneá 25 a 30 minutos; el centro debe quedar húmedo.",
                "Enfriá en el molde antes de cortar en porciones.",
            ],
        },
    ],
    "pan de banana": [
        {
            "phase": "Preparación",
            "title": "Mise en place",
            "steps": [
                "Precalentá el horno a 180 °C.",
                "Enmantecá y enhariná un molde de budín.",
            ],
        },
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Aplastá las bananas maduras con un tenedor.",
                "Mezclá con los huevos, el azúcar y la manteca derretida.",
                "Incorporá la harina, el polvo de hornear y la canela tamizados.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en el molde y nivelá.",
                "Horneá 45 a 55 minutos hasta que al insertar un palillo salga seco.",
                "Dejá enfriar 10 minutos antes de desmoldar.",
            ],
        },
    ],
    "cheesecake": [
        {
            "phase": "Base",
            "title": "Costra de galleta",
            "steps": [
                "Triturá las galletas y mezclá con la manteca derretida.",
                "Presioná la mezcla en el fondo de un molde desmontable.",
                "Llevá a heladera 15 minutos.",
            ],
        },
        {
            "phase": "Relleno",
            "title": "Crema",
            "steps": [
                "Batí el queso crema con el azúcar hasta alisar.",
                "Incorporá los huevos uno a uno, integrando sin batir.",
                "Agregá la crema y la vainilla; mezclá hasta uniforme.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Horno a baño María",
            "steps": [
                "Volcá sobre la base de galleta.",
                "Horneá a 160 °C a baño María durante 50 a 60 minutos.",
                "Apagá el horno y dejá enfriar dentro con la puerta entreabierta.",
                "Llevá a heladera al menos 4 horas antes de servir.",
            ],
        },
    ],
    "galletas de avena": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Batí la manteca con el azúcar hasta cremoso.",
                "Incorporá el huevo y la esencia de vainilla.",
                "Mezclá la avena, la harina, el polvo de hornear y la sal.",
            ],
        },
        {
            "phase": "Armado",
            "title": "Porciones",
            "steps": [
                "Formá bolitas del tamaño de una nuez.",
                "Disponé en una placa enmantecada separadas entre sí.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Horneá a 180 °C por 12 a 15 minutos hasta dorar los bordes.",
                "Dejá enfriar 5 minutos en la placa antes de moverlas.",
            ],
        },
    ],
    "galletas de chocolate": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Batí la manteca con los azúcares hasta cremoso.",
                "Incorporá el huevo y la vainilla.",
                "Agregá la harina, el cacao, el polvo de hornear y la sal.",
            ],
        },
        {
            "phase": "Armado",
            "title": "Porciones",
            "steps": [
                "Agregá los chips de chocolate a la masa.",
                "Formá bolitas y disponé en placa enmantecada.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Horneá a 180 °C por 10 a 12 minutos.",
                "Las galletas deben quedar tiernas en el centro; se endurecen al enfriar.",
            ],
        },
    ],
    "empanada de carne": [
        {
            "phase": "Relleno",
            "title": "Picada",
            "steps": [
                "Rehogá la cebolla, el pimiento y el ajo picados en aceite.",
                "Agregá la carne molida y cociná hasta dorar.",
                "Incorporá el comino, el pimentón, la sal y la pimienta.",
                "Sumá las aceitunas picadas y dejá enfriar.",
            ],
        },
        {
            "phase": "Armado",
            "title": "Repulgue",
            "steps": [
                "Estirá la masa y cortá discos de 12 cm.",
                "Rellená con una cucharada de la picada.",
                "Cerrá formando un repulgue por los bordes.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Horno",
            "steps": [
                "Disponé en placa enmantecada.",
                "Pintá con huevo batido.",
                "Horneá a 200 °C por 20 a 25 minutos hasta dorar.",
            ],
        },
    ],
    "budín de pan": [
        {
            "phase": "Base",
            "title": "Remojo",
            "steps": [
                "Cortá el pan en rebanadas y remojá en la leche con la vainilla.",
                "Dejá reposar 20 minutos hasta que absorba todo el líquido.",
            ],
        },
        {
            "phase": "Mezcla",
            "title": "Crema",
            "steps": [
                "Batí los huevos con el azúcar y la ralladura de limón.",
                "Incorporá la crema y mezclá con el pan remojado hasta alisar.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Horno a baño María",
            "steps": [
                "Volcá en molde acaramelado.",
                "Horneá a 160 °C a baño María por 50 a 60 minutos.",
                "Dejá enfriar antes de desmoldar.",
            ],
        },
    ],
    "crêpes": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Batí los huevos con la leche, la harina tamizada y una pizca de sal.",
                "Incorporá la manteca derretida y dejá reposar 30 minutos en heladera.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Panquequera",
            "steps": [
                "Calentá una sartén antiadherente a fuego medio.",
                "Verté una porción fina y cociná 1 minuto de cada lado.",
                "Reservá en un plato cubierto.",
            ],
        },
        {
            "phase": "Servicio",
            "title": "Relleno",
            "steps": [
                "Rellená al gusto: dulce de leche, frutas, queso y jamón.",
                "Doblá en triángulos o enrollá.",
            ],
        },
    ],
    "tarta de chocolate": [
        {
            "phase": "Base",
            "title": "Masa",
            "steps": [
                "Mezclá la harina con la manteca fría hasta arenar.",
                "Agregá azúcar, huevo y esencia; uní sin trabajar de más.",
                "Reservá 30 minutos en heladera.",
            ],
        },
        {
            "phase": "Relleno",
            "title": "Ganache",
            "steps": [
                "Herví la crema y verté sobre el chocolate picado.",
                "Dejá reposar 2 minutos y mezclá hasta alisar.",
            ],
        },
        {
            "phase": "Armado",
            "title": "Terminación",
            "steps": [
                "Estirá la masa y forrá un molde.",
                "Pre-horneá la base 15 minutos a 180 °C.",
                "Volcá la ganache y llevá a heladera 4 horas.",
            ],
        },
    ],
    "muffin de chocolate": [
        {
            "phase": "Mezcla",
            "title": "Ingredientes secos",
            "steps": [
                "Tamizá harina, cacao, polvo de hornear, bicarbonato y sal.",
            ],
        },
        {
            "phase": "Mezcla",
            "title": "Ingredientes húmedos",
            "steps": [
                "Batí los huevos con el azúcar y la manteca derretida.",
                "Incorporá la leche y la vainilla.",
            ],
        },
        {
            "phase": "Armado",
            "title": "Muffins",
            "steps": [
                "Uní secos y húmedos con movimientos envolventes.",
                "Agregá los chips de chocolate.",
                "Distribuí en pirotines y horneá 20 minutos a 180 °C.",
            ],
        },
    ],
    "pasta fresca": [
        {
            "phase": "Masa",
            "title": "Amasado",
            "steps": [
                "Hacé un volcán con la harina en la mesada.",
                "Agregá los huevos y una pizca de sal en el centro.",
                "Incorporá de a poco la harina con un tenedor.",
                "Amasá 10 minutos hasta obtener una masa lisa y elástica.",
                "Reservá envuelta en film 30 minutos en heladera.",
            ],
        },
        {
            "phase": "Estirado",
            "title": "Laminado",
            "steps": [
                "Estirá con palo hasta 2 mm de espesor.",
                "Espolvoreá sémola para evitar que se pegue.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Hervido",
            "steps": [
                "Cortá en la forma deseada (tallarines,ravioles,etc).",
                "Herví en abundante agua con sal 2 a 4 minutos.",
                "Serví con tu salsa favorita.",
            ],
        },
    ],
    "frikandel": [
        {
            "phase": "Mezcla",
            "title": "Carne",
            "steps": [
                "Mezclá la carne molida con el pan remojado en leche, los huevos, la sal y las especias.",
                "Amasá hasta obtener una pasta homogénea.",
            ],
        },
        {
            "phase": "Armado",
            "title": "Rollos",
            "steps": [
                "Formá rollos alargados de unos 15 cm.",
                "Pasá por harina, huevo batido y pan rallado.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Fritura",
            "steps": [
                "Fritá en aceite bien caliente hasta dorar de todos lados.",
                "Escurrí sobre papel absorbente.",
            ],
        },
    ],
    "pan ciabatta": [
        {
            "phase": "Pre-fermento",
            "title": "Poolish",
            "steps": [
                "Mezclá 100 g de harina con 100 ml de agua y 1 g de levadura.",
                "Dejá fermentar 12 horas a temperatura ambiente.",
            ],
        },
        {
            "phase": "Masa",
            "title": "Amasado",
            "steps": [
                "Mezclá el resto de la harina, el agua, la sal y el poolish.",
                "Amasá 10 minutos; la masa debe quedar blanda y húmeda.",
                "Dejá levar 2 horas con dobleces cada 30 minutos.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá la masa en placa enharinada, estirando con los dedos.",
                "Horneá a 230 °C con vapor los primeros 10 minutos.",
                "Retirá el vapor y continuá 15 minutos hasta dorar.",
            ],
        },
    ],
    "bizcocho de chocolate": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Batí los huevos con el azúcar hasta punto letra.",
                "Incorporá el aceite y la vainilla.",
                "Tamizá la harina, el cacao y el polvo de hornear; agregá a la mezcla alternando con la leche.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en molde enmantecado y enharinado.",
                "Horneá a 180 °C por 35 a 40 minutos.",
                "Dejá enfriar antes de desmoldar.",
            ],
        },
    ],
    "bizcocho marmolado": [
        {
            "phase": "Mezcla",
            "title": "Masa base",
            "steps": [
                "Batí la manteca con el azúcar hasta cremoso.",
                "Incorporá los huevos uno a uno.",
                "Agregá la harina tamizada con el polvo de hornear y la leche alternando.",
            ],
        },
        {
            "phase": "Armado",
            "title": "Efecto marmolado",
            "steps": [
                "Dividí la masa en dos partes.",
                "A una parte agregá el cacao disuelto en agua caliente.",
                "Verté alternadamente en el molde y mezclá con un palillo en forma de ocho.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Horneá a 180 °C por 45 a 50 minutos.",
                "Verificá con palillo antes de retirar del horno.",
            ],
        },
    ],
    "queque de yogur": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "En un bowl, mezclá el yogur con los huevos y el azúcar.",
                "Agregá el aceite y la esencia de vainilla.",
                "Tamizá la harina con el polvo de hornear e incorporá a la mezcla.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en molde enmantecado y enharinado.",
                "Horneá a 180 °C por 35 a 40 minutos.",
                "Dejá enfriar sobre rejilla.",
            ],
        },
    ],
    "queque de vainilla": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Batí la manteca con el azúcar hasta cremoso.",
                "Incorporá los huevos y la vainilla.",
                "Tamizá la harina con el polvo de hornear y agregá alternando con la leche.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en molde enmantecado.",
                "Horneá a 180 °C por 30 a 35 minutos.",
                "Decorá con glasé o espolvoreá con azúcar impalpable.",
            ],
        },
    ],
}


def _migration_118_recipe_instructions_backfill(conn: Any) -> None:
    """Write structured instructions for every recipe whose name is in
    the seed dictionary. Idempotent: re-running overwrites the column
    with the same content. Recipes with contaminated lines (>=25) are
    skipped to match the manual curation in seed_full_recipe_data.py.
    """
    # Contaminated row guard (matches scripts/seed_full_recipe_data.py
    # _CONTAMINATED_NAMES: "1.0", "1", "RECETA", "test")
    contaminated = conn.execute(
        text(
            "SELECT name FROM recipe "
            "WHERE name IN ('1.0', '1', 'RECETA', 'test') "
            "AND (SELECT COUNT(*) FROM recipe_line WHERE recipe_id = recipe.id) >= 25"
        )
    ).first()
    contaminated_names: set[str] = set()
    if contaminated is not None:
        contaminated_names.add(contaminated[0])

    written = 0
    skipped = 0
    for name, phases in _RECIPE_INSTRUCTIONS.items():
        # Skip if this exact name is the contaminated row
        if name in contaminated_names:
            skipped += 1
            continue
        payload = json.dumps(phases, ensure_ascii=False)
        result = conn.execute(
            text("UPDATE recipe SET instructions = :payload WHERE name = :name"),
            {"payload": payload, "name": name},
        )
        if result.rowcount and result.rowcount > 0:
            written += 1

    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 118)
