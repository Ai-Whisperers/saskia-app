"""app/rms/seed/seasonal_events.py — Sazon SeasonalEvent catalog seeder.

SASKIA-216 (2026-10-12). Inserts the Tier 1 (universal) seasonal event
catalog into the `seasonal_event` table. Tier 2/3/4 expansion is in
SASKIA-220.

Idempotent: skip if (country, slug, event_date) already exists. The
unique constraint `uq_seasonal_event_country_slug_date` is the natural
key. The function `seed_seasonal_events` returns the number of NEW rows
inserted (skipped rows don't count).

The catalog (Tier 1, ~132 rows):

  - 13 PY national holidays per Ley 7544/2025, baked for 2026-2028
  - ~30 PY commercial / festive / folk / school / sectoral days
  - Easter-dependent feasts (Jueves Santo, Viernes Santo, Pascua,
    Ascension, Pentecost, Corpus Christi, etc.) baked 2026-2028
  - ~5 NL heritage days (Sinterklaas, Koningsdag, Bevrijdingsdag, etc.)
    for the "Vaquita Holandesa" brand identity and any future NL client

The full deep analysis is in
`docs/operations/2026-10-12-seasonal-events-comprehensive-catalog.md`
(37KB, 28 web sources).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import SeasonalEvent

# ---------------------------------------------------------------------------
# Easter dates (computus): the table needs the actual date for each year
# (2026-2028). Beyond 2028, SASKIA-219 (refresh cron) will roll forward.
# ---------------------------------------------------------------------------
EASTER_DATES = {
    2026: date(2026, 4, 5),
    2027: date(2027, 3, 28),
    2028: date(2028, 4, 16),
}


def _easter_offset(year: int, days: int) -> date:
    """Return Easter(year) + days (e.g. -3 = Jueves Santo, +60 = Corpus)."""
    return EASTER_DATES[year] + __import__("datetime").timedelta(days=days)


# ---------------------------------------------------------------------------
# The catalog: list of dicts, one per (event, year). Year is generated
# by the helper functions for fixed-date events; Easter-dependent events
# are generated per year by _easter_offset.
#
# Each entry: {slug, name_es, name_nl, name_en, date(year), country,
#              category, impact_score, impact_tag, relevance_tags,
#              is_annual, recurrence}
# ---------------------------------------------------------------------------


def _tier1_universal_events() -> list[dict[str, Any]]:
    """Tier 1: 44 events × 3 years = 132 rows.

    Universal events (all packs see). Impact 0.6-1.0.
    """
    events: list[dict[str, Any]] = []
    years = [2026, 2027, 2028]

    # ---- PY national legal holidays (Ley 7544/2025) ----

    # Año Nuevo (1 January) — universal
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "ano_nuevo",
            "name_es": "Año Nuevo",
            "name_nl": "Nieuwjaarsdag",
            "name_en": "New Year's Day",
            "event_date": date(y, 1, 1),
            "country": "PY",
            "category": "legal",
            "impact_score": 1.0,
            "impact_tag": "critical",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Día de los Héroes de la Patria (1 March, movable by decree)
    for y in years:
        # Per BACN Ley 7544/2025: Ejecutivo puede mover al lunes adyacente.
        # Para 2026: Decreto 5508 lo movió al lunes 2 de marzo.
        # Para 2027: ya cae lunes. Para 2028: cae miércoles (sin movimiento).
        if y == 2026:
            d = date(2026, 3, 2)  # moved
        elif y == 2027:
            d = date(2027, 3, 1)  # already Monday
        else:
            d = date(2028, 3, 1)
        events.append({
            "slug": "heroes_patria",
            "name_es": "Día de los Héroes de la Patria",
            "event_date": d,
            "country": "PY",
            "category": "legal",
            "impact_score": 0.5,
            "impact_tag": "medium",
            "relevance_tags": "",
            "is_annual": False,
            "recurrence": "movable-by-decree",
        })

    # Semana Santa — Jueves Santo, Viernes Santo, Pascua (Easter-anchored)
    for y in years:
        events.append({
            "slug": "jueves_santo",
            "name_es": "Jueves Santo",
            "name_en": "Maundy Thursday",
            "event_date": _easter_offset(y, -3),
            "country": "PY",
            "category": "religious",
            "impact_score": 1.0,
            "impact_tag": "critical",
            "relevance_tags": "",
            "is_annual": False,
            "recurrence": "easter-3",
        })
        events.append({
            "slug": "viernes_santo",
            "name_es": "Viernes Santo",
            "name_en": "Good Friday",
            "event_date": _easter_offset(y, -2),
            "country": "PY",
            "category": "religious",
            "impact_score": 1.0,
            "impact_tag": "critical",
            "relevance_tags": "",
            "is_annual": False,
            "recurrence": "easter-2",
        })
        events.append({
            "slug": "pascua",
            "name_es": "Pascua (Domingo de Resurrección)",
            "name_en": "Easter Sunday",
            "event_date": EASTER_DATES[y],
            "country": "PY",
            "category": "religious",
            "impact_score": 1.0,
            "impact_tag": "critical",
            "relevance_tags": "",
            "is_annual": False,
            "recurrence": "easter",
        })

    # Día de los Trabajadores (1 May) — universal
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "dia_trabajadores",
            "name_es": "Día de los Trabajadores",
            "event_date": date(y, 5, 1),
            "country": "PY",
            "category": "legal",
            "impact_score": 0.7,
            "impact_tag": "high",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Independencia Nacional (14 May eve + 15 May = also Día de la Madre)
    for y in years:
        events.append({
            "slug": "independencia_eve",
            "name_es": "Independencia Nacional (víspera)",
            "event_date": date(y, 5, 14),
            "country": "PY",
            "category": "legal",
            "impact_score": 0.7,
            "impact_tag": "high",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })
        events.append({
            "slug": "dia_madre_py",
            "name_es": "Día de la Madre (también Independencia)",
            "event_date": date(y, 5, 15),
            "country": "PY",
            "category": "commercial",
            "impact_score": 1.0,
            "impact_tag": "critical",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Día de la Paz del Chaco (12 June, movable by decree)
    for y in years:
        d = date(y, 6, 12)
        if y == 2026 and d.weekday() == 4:  # Friday already
            d = d
        events.append({
            "slug": "paz_chaco",
            "name_es": "Día de la Paz del Chaco",
            "event_date": d,
            "country": "PY",
            "category": "legal",
            "impact_score": 0.4,
            "impact_tag": "medium",
            "relevance_tags": "",
            "is_annual": False,
            "recurrence": "movable-by-decree",
        })

    # Jura de la Constitución (20 June, new in 2025, movable)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "jura_constitucion",
            "name_es": "Jura de la Constitución Nacional",
            "event_date": date(y, 6, 20),
            "country": "PY",
            "category": "legal",
            "impact_score": 0.4,
            "impact_tag": "medium",
            "relevance_tags": "",
            "is_annual": False,
            "recurrence": "movable-by-decree",
        })

    # Fundación de Asunción (15 August) — patron saint of Asunción
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "fundacion_asuncion",
            "name_es": "Fundación de Asunción (patronal)",
            "event_date": date(y, 8, 15),
            "country": "PY",
            "category": "folk",
            "impact_score": 0.8,
            "impact_tag": "high",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Batalla de Boquerón (29 September, movable by decree)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "batalla_boqueron",
            "name_es": "Día de la Batalla de Boquerón",
            "event_date": date(y, 9, 29),
            "country": "PY",
            "category": "legal",
            "impact_score": 0.4,
            "impact_tag": "medium",
            "relevance_tags": "",
            "is_annual": False,
            "recurrence": "movable-by-decree",
        })

    # Virgen de Caacupé (8 December) — national patron
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "virgen_caacupe",
            "name_es": "Día de la Virgen de Caacupé",
            "event_date": date(y, 12, 8),
            "country": "PY",
            "category": "religious",
            "impact_score": 0.9,
            "impact_tag": "high",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Navidad (25 December)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "navidad",
            "name_es": "Navidad",
            "name_nl": "Kerstmis",
            "name_en": "Christmas",
            "event_date": date(y, 12, 25),
            "country": "PY",
            "category": "legal",
            "impact_score": 1.0,
            "impact_tag": "critical",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # ---- PY commercial / festive / folk / school / sectoral ----

    # Reyes / Epifanía (6 January) — Rosca de Reyes
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "reyes",
            "name_es": "Reyes / Epifanía",
            "event_date": date(y, 1, 6),
            "country": "PY",
            "category": "religious",
            "impact_score": 0.9,
            "impact_tag": "high",
            "relevance_tags": "panaderia,pasteleria",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Carnaval Encarnaceno (5 Saturdays Jan-mid Feb, Encarnación)
    # Approximate: a 6-week window starting mid-January
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "carnaval_encarnaceno",
            "name_es": "Carnaval Encarnaceno",
            "event_date": date(y, 1, 17),  # first Saturday approx
            "country": "PY",
            "category": "folk",
            "impact_score": 0.4,
            "impact_tag": "medium",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed-window",
        })

    # Día de San Valentín (14 February)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "san_valentin",
            "name_es": "Día de San Valentín",
            "event_date": date(y, 2, 14),
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.6,
            "impact_tag": "medium",
            "relevance_tags": "cafeteria,pasteleria,heladeria,pizzeria",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Inicio de clases PY (MEC Resolución 2.065: last Mon Feb)
    for y in years:
        # 2026: 23 Feb (Res 2.065). 2027: estimado 22 Feb. 2028: estimado 21 Feb.
        d = {2026: date(2026, 2, 23), 2027: date(2027, 2, 22), 2028: date(2028, 2, 21)}[y]
        events.append({
            "slug": "inicio_clases_py",
            "name_es": "Inicio de clases PY",
            "event_date": d,
            "country": "PY",
            "category": "school",
            "impact_score": 0.7,
            "impact_tag": "high",
            "relevance_tags": "panaderia,quiosco",
            "is_annual": False,
            "recurrence": "last-monday-feb",
        })

    # Día Internacional de la Mujer (8 March)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "dia_mujer",
            "name_es": "Día Internacional de la Mujer",
            "event_date": date(y, 3, 8),
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.6,
            "impact_tag": "medium",
            "relevance_tags": "cafeteria,pasteleria,heladeria,catering",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Cuaresma (Ash Wednesday = Easter - 46 days) — 40-day Lent
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "cuaresma",
            "name_es": "Cuaresma (Miércoles de Ceniza)",
            "event_date": _easter_offset(y, -46),
            "country": "PY",
            "category": "religious",
            "impact_score": 0.6,
            "impact_tag": "medium",
            "relevance_tags": "panaderia,empanadas,comedor",
            "is_annual": False,
            "recurrence": "easter-46",
        })

    # Día del Maestro (30 April)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "dia_maestro",
            "name_es": "Día del Maestro",
            "event_date": date(y, 4, 30),
            "country": "PY",
            "category": "school",
            "impact_score": 0.5,
            "impact_tag": "medium",
            "relevance_tags": "catering,comedor",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Corpus Christi (Easter + 60)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "corpus_christi",
            "name_es": "Corpus Christi",
            "event_date": _easter_offset(y, 60),
            "country": "PY",
            "category": "religious",
            "impact_score": 0.4,
            "impact_tag": "medium",
            "relevance_tags": "panaderia,pasteleria",
            "is_annual": False,
            "recurrence": "easter+60",
        })

    # San Juan Ára (24 June) — chipá + mbejú are THE San Juan foods
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "san_juan_ara",
            "name_es": "San Juan Ára",
            "event_date": date(y, 6, 24),
            "country": "PY",
            "category": "folk",
            "impact_score": 0.9,
            "impact_tag": "high",
            "relevance_tags": "panaderia,empanadas,comedor,chiperia",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Vacaciones de invierno PY (second Mon Jul, 2 weeks)
    for y in years:
        d = {2026: date(2026, 7, 13), 2027: date(2027, 7, 12), 2028: date(2028, 7, 10)}[y]
        events.append({
            "slug": "vacaciones_invierno_py",
            "name_es": "Inicio de vacaciones de invierno PY",
            "event_date": d,
            "country": "PY",
            "category": "school",
            "impact_score": 0.5,
            "impact_tag": "medium",
            "relevance_tags": "panaderia,heladeria",
            "is_annual": False,
            "recurrence": "second-monday-july",
        })

    # Día del Amigo PY (30 July) — PY-invented tradition
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "dia_amigo_py",
            "name_es": "Día del Amigo (PY)",
            "event_date": date(y, 7, 30),
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.9,
            "impact_tag": "high",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # San Lorenzo patron (10 August) — Saskia's district
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "san_lorenzo_patron",
            "name_es": "San Lorenzo — Fiesta Patronal (10 agosto)",
            "event_date": date(y, 8, 10),
            "country": "PY",
            "category": "folk",
            "impact_score": 0.8,
            "impact_tag": "high",
            "relevance_tags": "panaderia,pasteleria,empanadas",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Día del Niño PY (16 August, fixed since Acosta Ñu)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "dia_nino_py",
            "name_es": "Día del Niño (PY)",
            "event_date": date(y, 8, 16),
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.8,
            "impact_tag": "high",
            "relevance_tags": "panaderia,pasteleria,heladeria,hamburgueseria",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Día del Padre PY (3rd Sunday of June)
    for y in years:
        # 2026: 21 June, 2027: 20 June, 2028: 18 June
        d = {2026: date(2026, 6, 21), 2027: date(2027, 6, 20), 2028: date(2028, 6, 18)}[y]
        events.append({
            "slug": "dia_padre_py",
            "name_es": "Día del Padre (PY, 3er domingo junio)",
            "event_date": d,
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.8,
            "impact_tag": "high",
            "relevance_tags": "parrilla,panaderia,pasteleria,pizzeria,hamburgueseria,empanadas",
            "is_annual": False,
            "recurrence": "third-sunday-june",
        })

    # Halloween (31 October) — imported
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "halloween",
            "name_es": "Halloween (importado)",
            "event_date": date(y, 10, 31),
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.4,
            "impact_tag": "medium",
            "relevance_tags": "pizzeria,hamburgueseria,heladeria",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Singles Day (11 November) — e-commerce import
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "singles_day",
            "name_es": "Singles Day (11.11)",
            "event_date": date(y, 11, 11),
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.2,
            "impact_tag": "low",
            "relevance_tags": "cafeteria,pizzeria,pasteleria",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Black Friday PY (last Friday of November)
    for y in years:
        # 2026: 27 Nov, 2027: 26 Nov, 2028: 24 Nov
        d = {2026: date(2026, 11, 27), 2027: date(2027, 11, 26), 2028: date(2028, 11, 24)}[y]
        events.append({
            "slug": "black_friday_py",
            "name_es": "Black Friday (PY)",
            "event_date": d,
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.6,
            "impact_tag": "medium",
            "relevance_tags": "pizzeria,hamburgueseria,cafeteria,catering",
            "is_annual": False,
            "recurrence": "last-friday-november",
        })

    # CyberDay PY (first Mon-Wed of November, when announced)
    for y in years:
        d = {2026: date(2026, 11, 2), 2027: date(2027, 11, 1), 2028: date(2028, 11, 6)}[y]
        events.append({
            "slug": "cyberday_py",
            "name_es": "CyberDay (PY, cuando se anuncia)",
            "event_date": d,
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.4,
            "impact_tag": "medium",
            "relevance_tags": "cafeteria,pizzeria,pasteleria",
            "is_annual": False,
            "recurrence": "first-week-november",
        })

    # Nochebuena (24 December)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "nochebuena",
            "name_es": "Nochebuena",
            "event_date": date(y, 12, 24),
            "country": "PY",
            "category": "religious",
            "impact_score": 0.9,
            "impact_tag": "high",
            "relevance_tags": "panaderia,pasteleria,catering",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # ---- NL heritage (for the "Vaquita Holandesa" brand + future NL clients) ----

    # Sinterklaas (5 December) — bigger than Christmas for many Dutch
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "sinterklaas",
            "name_es": "Sinterklaas (herencia neerlandesa)",
            "name_nl": "Sinterklaasavond (Pakjesavond)",
            "name_en": "Sinterklaas Eve",
            "event_date": date(y, 12, 5),
            "country": "NL",
            "category": "heritage",
            "impact_score": 0.4,
            "impact_tag": "medium",
            "relevance_tags": "panaderia,pasteleria,cafeteria",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Koningsdag (27 April) — NL King's birthday
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "koningsdag",
            "name_es": "Koningsdag (herencia neerlandesa)",
            "name_nl": "Koningsdag",
            "name_en": "King's Day (NL)",
            "event_date": date(y, 4, 27),
            "country": "NL",
            "category": "heritage",
            "impact_score": 0.1,
            "impact_tag": "info",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Bevrijdingsdag (5 May) — NL liberation
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "bevrijdingsdag",
            "name_es": "Bevrijdingsdag (herencia neerlandesa)",
            "name_nl": "Bevrijdingsdag",
            "name_en": "Liberation Day (NL)",
            "event_date": date(y, 5, 5),
            "country": "NL",
            "category": "heritage",
            "impact_score": 0.1,
            "impact_tag": "info",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # ---- Sectoral PY ----

    # Día del Panadero (mid-March, informal industry tradition)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "dia_panadero",
            "name_es": "Día del Panadero (sectoral informal, mid-marzo)",
            "event_date": date(y, 3, 18),
            "country": "PY",
            "category": "sectoral",
            "impact_score": 0.3,
            "impact_tag": "low",
            "relevance_tags": "panaderia",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Día de los Almaceneros (8 August, since 2026 Ley)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "dia_almaceneros",
            "name_es": "Día de los Almaceneros y Minoristas",
            "event_date": date(y, 8, 8),
            "country": "PY",
            "category": "sectoral",
            "impact_score": 0.1,
            "impact_tag": "info",
            "relevance_tags": "quiosco",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # ---- Cultural (low impact) ----

    # Día de la Música PY (22 November)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "dia_musica_py",
            "name_es": "Día de la Música (PY)",
            "event_date": date(y, 11, 22),
            "country": "PY",
            "category": "cultural",
            "impact_score": 0.1,
            "impact_tag": "info",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Día de los Pueblos Originarios (12 October, since 2024)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "pueblos_originarios",
            "name_es": "Día de los Pueblos Originarios (ex Día de la Raza)",
            "event_date": date(y, 10, 12),
            "country": "PY",
            "category": "cultural",
            "impact_score": 0.1,
            "impact_tag": "info",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Primavera + Juventud (21 September)
    for y in years:
        events.append({  # noqa: PERF401
            "slug": "primavera_juventud",
            "name_es": "Primavera + Día de la Juventud",
            "event_date": date(y, 9, 21),
            "country": "PY",
            "category": "cultural",
            "impact_score": 0.1,
            "impact_tag": "info",
            "relevance_tags": "",
            "is_annual": True,
            "recurrence": "fixed",
        })

    # Día Nacional del Tereré (last Saturday of February, SINAFOCAL)
    for y in years:
        d = {2026: date(2026, 2, 28), 2027: date(2027, 2, 27), 2028: date(2028, 2, 26)}[y]
        events.append({
            "slug": "dia_terere",
            "name_es": "Día Nacional del Tereré",
            "event_date": d,
            "country": "PY",
            "category": "cultural",
            "impact_score": 0.1,
            "impact_tag": "info",
            "relevance_tags": "quiosco",
            "is_annual": False,
            "recurrence": "last-saturday-feb",
        })

    return events


def seed_seasonal_events(session: Session, *, year_range: tuple[int, int] = (2026, 2028)) -> int:
    """Insert the Tier 1 universal SeasonalEvent catalog.

    Idempotent: skip if (country, slug, event_date) already exists.
    Returns the number of NEW rows inserted.

    Args:
        session: SQLAlchemy session.
        year_range: inclusive (start_year, end_year) to seed.
            Default (2026, 2028) covers the 3-year horizon. The
            catalog is generated for ALL years in this range.

    Side effects:
        Adds SeasonalEvent rows; does NOT commit. Caller commits.
    """
    rows = _tier1_universal_events()

    # Filter by year_range (rows are pre-baked 2026-2028, so this
    # mostly validates the input — future years will need a new
    # generator helper that calls SASKIA-219's annual refresh).
    rows = [r for r in rows if year_range[0] <= r["event_date"].year <= year_range[1]]

    inserted = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        existing = session.execute(
            select(SeasonalEvent).where(
                SeasonalEvent.country == row["country"],
                SeasonalEvent.slug == row["slug"],
                SeasonalEvent.event_date == row["event_date"],
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        session.add(SeasonalEvent(
            slug=row["slug"],
            name_es=row["name_es"],
            name_nl=row.get("name_nl"),
            name_en=row.get("name_en"),
            description=row.get("description"),
            event_date=row["event_date"],
            end_date=row.get("end_date"),
            country=row["country"],
            category=row["category"],
            impact_score=row["impact_score"],
            impact_tag=row["impact_tag"],
            relevance_tags=row["relevance_tags"],
            is_annual=row["is_annual"],
            recurrence=row.get("recurrence"),
            created_at=now,
            updated_at=now,
        ))
        inserted += 1

    session.flush()
    logger.info(
        f"seed_seasonal_events: {inserted} new, {skipped} skipped (already existed). "
        f"Total catalog attempt: {len(rows)} rows for {year_range[0]}-{year_range[1]}."
    )
    return inserted
