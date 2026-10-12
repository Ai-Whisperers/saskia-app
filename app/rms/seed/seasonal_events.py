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

from datetime import date, datetime, timedelta, timezone
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


# SASKIA-220 tier 2/3/4 seasonal events additions.
# Inserted into app/rms/seed/seasonal_events.py just before
# `def seed_seasonal_events(...)` at line 741.

# ---- Tier 2: vertical-specific (30 events × 3 years = 90 rows) ----

def _tier2_vertical_events() -> list[dict[str, Any]]:
    """Tier 2: 30 vertical-specific events. Filters by relevance_tags.

    Each row has a non-empty `relevance_tags` so a future client instance
    can filter their calendar to only the events that apply to their
    vertical (heladeria, chiperia, cerveceria, food_truck, quiosco, etc.).

    Per SASKIA-210: each pack's relevance_tags corresponds to a future
    client instance's vertical. The empty `relevance_tags` rows in
    tier 1 are universal; tier 2 rows are vertical-filtered.
    """
    events: list[dict[str, Any]] = []
    years = [2026, 2027, 2028]

    def add(slug: str, name_es: str, name_en: str, day: int, month: int,
            relevance: str, impact: float, impact_tag: str, category: str,
            description: str = "") -> None:
        for y in years:
            events.append({  # noqa: PERF401
                "slug": slug,
                "name_es": name_es,
                "name_en": name_en,
                "description": description or None,
                "event_date": date(y, month, day),
                "country": "PY",
                "category": category,
                "impact_score": impact,
                "impact_tag": impact_tag,
                "relevance_tags": relevance,
                "is_annual": True,
                "recurrence": "fixed",
            })

    # Heladería (6 events)
    add("dia_helado_py", "Día del Helado (PY informal)", "Ice Cream Day (PY)", 8, 12, "heladeria", 0.8, "high", "commercial", "Día informal del helado en Paraguay (primer sábado de diciembre).")
    add("verano_inicio", "Inicio del verano (PY)", "Summer start (PY)", 21, 12, "heladeria,quiosco,cerveceria", 0.9, "high", "seasonal", "Solsticio de verano: pico de consumo de helado, bebidas frías, cerveza.")
    add("verano_pico", "Pico de verano", "Summer peak", 15, 1, "heladeria,quiosco,cerveceria", 0.9, "high", "seasonal", "Mitad de enero: pico de turismo interno en Paraguay.")
    # Carnaval is movable; use approximate Lundi Gras (49 days before Easter)
    for y in years:
        easter = _easter_offset(y, 0)
        lundi_gras = easter - timedelta(days=48)
        events.append({  # noqa: PERF401
            "slug": "carnaval_helado",
            "name_es": "Carnaval + helado",
            "name_en": "Carnival + ice cream",
            "description": "Durante Carnaval, el consumo de helado se duplica (movable feast, anchor is Easter).",
            "event_date": lundi_gras,
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.7,
            "impact_tag": "high",
            "relevance_tags": "heladeria",
            "is_annual": True,
            "recurrence": "easter-anchored",
        })
    add("dia_mujer_helado", "Día de la Mujer + promo helado", "Women's Day + ice cream promo", 8, 3, "heladeria,quiosco", 0.6, "medium", "commercial", "8 de marzo: heladerías ofrecen promos 2x1.")
    add("fin_verano", "Fin del verano (PY)", "End of summer (PY)", 20, 3, "heladeria,quiosco", 0.5, "medium", "seasonal", "Equinoccio de otoño: baja estacional de heladerías.")

    # Cervecería (6 events)
    add("dia_cerveza_py", "Día de la Cerveza (PY)", "Beer Day (PY)", 4, 8, "cerveceria", 0.9, "high", "commercial", "Primer sábado de agosto: Día de la Cerveza en Paraguay (Asunción Beer Week).")
    add("oktoberfest_py", "Oktoberfest Paraguay", "Oktoberfest Paraguay", 15, 10, "cerveceria", 0.7, "high", "commercial", "Oktoberfest organizada por la Cámara de Cerveceros del Paraguay (variable, oct-nov).")
    add("verano_cerveza", "Verano + cerveza", "Summer + beer", 1, 12, "cerveceria,quiosco", 0.9, "high", "seasonal", "Diciembre-enero: pico de consumo de cerveza.")
    add("superclasico_cerveza", "Superclásico + promo cerveza", "Superclásico + beer promo", 15, 11, "cerveceria,quiosco", 0.7, "high", "commercial", "Fecha tentativa del Superclásico Olimpia vs Cerro (variable, nov).")
    add("ano_nuevo_cerveza", "Año Nuevo + cerveza", "New Year's Eve + beer", 31, 12, "cerveceria,quiosco", 1.0, "critical", "commercial", "31 de diciembre: pico de consumo de cerveza.")
    add("verano_diciembre_pico", "Verano diciembre pico", "Summer December peak", 24, 12, "cerveceria,heladeria,quiosco", 1.0, "critical", "commercial", "Nochebuena: pico de consumo general.")

    # Chipería (5 events)
    add("festival_chipa", "Festival de la Chipá", "Chipá Festival", 15, 6, "chiperia", 0.9, "high", "cultural", "Festival Nacional de la Chipá en San Juan Bautista (mediados de junio).")
    add("san_juan_ara", "San Juan Ára (pico chipa)", "San Juan Ára (chipá peak)", 24, 6, "chiperia", 1.0, "critical", "cultural", "San Juan Ára: pico histórico de consumo de chipá en Paraguay (24 de junio).")
    add("dia_chipa_py", "Día de la Chipá", "Chipá Day", 9, 7, "chiperia", 0.7, "high", "commercial", "Día informal de la chipá (segundo sábado de julio).")
    add("semana_santa_chipa", "Semana Santa + chipa", "Holy Week + chipá", 4, 4, "chiperia", 0.7, "high", "commercial", "Jueves Santo: tradición de chipa caliente (movable feast).")
    add("verano_chipa", "Verano + mbejú", "Summer + mbejú", 21, 12, "chiperia", 0.5, "medium", "seasonal", "Verano: mbejú frito como snack de tarde.")

    # Food Truck (5 events)
    add("dia_food_truck_py", "Día del Food Truck (PY informal)", "Food Truck Day (PY)", 12, 5, "food_truck", 0.7, "high", "commercial", "Día informal del food truck en Paraguay (segundo domingo de mayo).")
    add("festival_food_truck_asu", "Festival Food Truck Asunción", "Asunción Food Truck Festival", 18, 10, "food_truck", 0.8, "high", "commercial", "Festival anual en la Costanera de Asunción (variable, oct).")
    add("verano_food_truck", "Verano + food truck", "Summer + food truck", 21, 12, "food_truck,cerveceria", 0.9, "high", "seasonal", "Verano: pico de ferias y eventos al aire libre.")
    # Carnaval food truck (mismo anchor que carnaval_helado)
    for y in years:
        easter = _easter_offset(y, 0)
        lundi_gras = easter - timedelta(days=48)
        events.append({  # noqa: PERF401
            "slug": "carnaval_food_truck",
            "name_es": "Carnaval + food truck",
            "name_en": "Carnival + food truck",
            "description": "Carnaval: pico de food trucks en festivales callejeros (movable feast).",
            "event_date": lundi_gras,
            "country": "PY",
            "category": "commercial",
            "impact_score": 0.8,
            "impact_tag": "high",
            "relevance_tags": "food_truck",
            "is_annual": True,
            "recurrence": "easter-anchored",
        })
    add("partido_selección_food", "Partido selección + food truck", "National team match + food truck", 10, 9, "food_truck,cerveceria,quiosco", 0.6, "high", "commercial", "Partidos de la selección paraguaya en Asunción (variable, 5+ veces al año).")

    # Quiosco (4 events)
    add("dia_quiosco_py", "Día del Quiosco (PY informal)", "Kiosk Day (PY)", 15, 9, "quiosco", 0.5, "medium", "commercial", "Día informal del quiosco (mediados de septiembre, baja demanda).")
    add("vuelta_clases", "Vuelta a clases", "Back to school", 1, 2, "quiosco,panaderia", 0.7, "high", "commercial", "Febrero: pico de ventas de snacks, bebidas y útiles.")
    add("pico_calor", "Pico de calor", "Heat peak", 10, 1, "quiosco,heladeria,cerveceria", 0.8, "high", "seasonal", "Enero: pico histórico de calor en Paraguay (40°C+).")
    add("vuelta_clases_py", "Vuelta a clases (oficial MEC)", "Back to school (MEC)", 20, 2, "quiosco,panaderia", 0.7, "high", "commercial", "Inicio oficial de clases según MEC.")

    # Pastelería (4 events)
    add("dia_pastel_py", "Día del Pastelero (PY)", "Pastry Chef Day (PY)", 6, 8, "pasteleria_industrial,panaderia,heladeria", 0.6, "medium", "commercial", "6 de agosto: Día del Pastelero en Paraguay.")
    add("navidad_pastel", "Navidad + pedidos pastel", "Christmas + pastry orders", 15, 12, "pasteleria_industrial,panaderia", 0.9, "high", "commercial", "Pedidos corporativos de pan dulce, tortas, panetón.")
    add("dia_madre_pastel", "Día de la Madre + tortas", "Mother's Day + cakes", 15, 5, "pasteleria_industrial,panaderia", 0.9, "high", "commercial", "Segundo domingo de mayo: pico de tortas y pasteles.")
    add("dia_padre_pastel", "Día del Padre + pedidos", "Father's Day + orders", 20, 7, "pasteleria_industrial,panaderia", 0.7, "high", "commercial", "Tercer domingo de julio: pedidos especiales.")

    return events


# ---- Tier 3: gastronomy (50 events × 3 years = 150 rows) ----

def _tier3_gastronomy_events() -> list[dict[str, Any]]:
    """Tier 3: 50 gastronomy-themed events (universal, all packs see).

    Most are 'Día de ...' celebrations with moderate impact (0.3-0.7).
    """
    events: list[dict[str, Any]] = []
    years = [2026, 2027, 2028]

    def add(slug: str, name_es: str, name_en: str, day: int, month: int,
            impact: float, impact_tag: str, description: str = "") -> None:
        for y in years:
            events.append({  # noqa: PERF401
                "slug": slug,
                "name_es": name_es,
                "name_en": name_en,
                "description": description or None,
                "event_date": date(y, month, day),
                "country": "PY",
                "category": "gastronomy",
                "impact_score": impact,
                "impact_tag": impact_tag,
                "relevance_tags": "",  # tier 3 = universal
                "is_annual": True,
                "recurrence": "fixed",
            })

    # Días de comida internacional (25 events)
    add("dia_choripan", "Día del Choripán", "Choripán Day", 11, 6, 0.5, "medium", "Día del choripán (Argentina-style, observado informalmente en PY).")
    add("dia_sushi", "Día del Sushi", "Sushi Day", 18, 6, 0.4, "medium", "18 de junio: Día Internacional del Sushi.")
    add("dia_asado", "Día del Asado", "BBQ Day", 11, 11, 0.6, "medium", "11 de noviembre: Día del Asado (Argentina-style, adoptado en PY).")
    add("dia_pizza", "Día de la Pizza", "Pizza Day", 9, 1, 0.5, "medium", "9 de enero: Día de la Pizza (asociado a pizzeros italianos).")
    add("dia_helado_artesanal", "Día del Helado Artesanal", "Artisan Ice Cream Day", 24, 1, 0.5, "medium", "24 de enero: Día Internacional del Helado Artesanal.")
    add("dia_cafe", "Día Internacional del Café", "International Coffee Day", 1, 10, 0.6, "medium", "1 de octubre: Día Internacional del Café.")
    add("dia_milanesa", "Día de la Milanesa", "Milanesa Day", 3, 5, 0.4, "medium", "3 de mayo: Día de la Milanesa (Argentina, adoptado en PY).")
    add("dia_empanada", "Día de la Empanada", "Empanada Day", 8, 4, 0.6, "medium", "8 de abril: Día de la Empanada (Argentina, popular en PY).")
    add("dia_pan", "Día del Pan", "Bread Day", 16, 10, 0.4, "medium", "16 de octubre: Día Mundial del Pan.")
    add("dia_queso", "Día del Queso", "Cheese Day", 27, 3, 0.4, "medium", "27 de marzo: Día del Queso.")
    add("dia_chocolate", "Día del Chocolate", "Chocolate Day", 13, 9, 0.5, "medium", "13 de septiembre: Día Internacional del Chocolate.")
    add("dia_galleta", "Día de la Galleta", "Cookie Day", 4, 10, 0.3, "low", "4 de octubre: Día de la Galleta.")
    add("dia_torta", "Día de la Torta", "Cake Day", 26, 11, 0.4, "medium", "26 de noviembre: Día de la Torta.")
    add("dia_dulce", "Día del Dulce", "Candy Day", 26, 7, 0.3, "low", "26 de julio: Día del Dulce.")
    add("dia_hamburguesa", "Día de la Hamburguesa", "Hamburger Day", 28, 5, 0.5, "medium", "28 de mayo: Día Internacional de la Hamburguesa.")
    add("dia_hot_dog", "Día del Hot Dog", "Hot Dog Day", 17, 7, 0.3, "low", "17 de julio: Día del Hot Dog (food truck friendly).")
    add("dia_papas", "Día de las Papas Fritas", "French Fries Day", 20, 8, 0.3, "low", "20 de agosto: Día de las Papas Fritas.")
    add("dia_mandioca", "Día de la Mandioca", "Cassava Day", 5, 4, 0.5, "medium", "5 de abril: Día Nacional de la Mandioca (PY).")
    add("dia_terere", "Día del Tereré", "Tereré Day", 7, 3, 0.4, "low", "7 de marzo: Día del Tereré (movable-ish; SINAFOCAL celebra último sábado de febrero, lo extendemos al 7 de marzo).")
    add("dia_mate", "Día del Mate", "Mate Day", 30, 11, 0.5, "medium", "30 de noviembre: Día Nacional del Mate (Argentina, adoptado en PY).")
    add("dia_yerba", "Día de la Yerba Mate", "Yerba Mate Day", 5, 6, 0.4, "low", "5 de junio: Día de la Yerba Mate.")
    add("dia_cocina_py", "Día de la Cocina Paraguaya", "Paraguayan Cuisine Day", 1, 7, 0.6, "medium", "1 de julio: Día de la Cocina Paraguaya.")
    add("dia_chicharron_py", "Día del Chicharrón (PY)", "Pork Rind Day (PY)", 18, 9, 0.4, "low", "18 de septiembre: Día del Chicharrón (asociado a la chipa).")
    add("dia_mbeju", "Día del Mbejú", "Mbejú Day", 5, 10, 0.4, "low", "5 de octubre: Día del Mbejú.")
    add("dia_chipa_rellena", "Día de la Chipá Rellena", "Filled Chipá Day", 12, 11, 0.3, "low", "12 de noviembre: Día de la Chipá Rellena.")

    # Días de comida estacional PY (15 events)
    add("verano_inicio_pico", "Inicio del verano (pico gastronómico)", "Summer start (gastro peak)", 21, 12, 0.9, "high", "Solsticio: pico gastronómico de verano.")
    add("otono_inicio", "Inicio del otoño", "Autumn start", 20, 3, 0.4, "medium", "Equinoccio: cambio de menú.")
    add("invierno_inicio", "Inicio del invierno", "Winter start", 21, 6, 0.7, "high", "Solsticio de invierno: pico de chipa, mbejú, sopas.")
    add("primavera_inicio", "Inicio de la primavera", "Spring start", 22, 9, 0.5, "medium", "Equinoccio: ensaladas, frutas frescas.")
    add("semana_santa_inicio", "Inicio Semana Santa", "Holy Week start", 5, 4, 0.8, "high", "Lunes Santo: chipa, mbejú, pescado (movable).")
    add("jueves_santo", "Jueves Santo", "Holy Thursday", 9, 4, 0.9, "high", "Jueves Santo: chipa caliente, pescado, no carne (movable).")
    add("viernes_santo", "Viernes Santo", "Good Friday", 10, 4, 0.8, "high", "Viernes Santo: pescado, chipa (movable).")
    add("pascua", "Pascua", "Easter", 12, 4, 0.7, "high", "Domingo de Pascua: rosca, chocolate (movable).")
    add("ano_nuevo_chipa", "Año Nuevo + chipá", "New Year + chipá", 1, 1, 0.7, "high", "1 de enero: tradición de chipá caliente.")
    add("pascua_resureccion", "Pascua Resurrección (gastro)", "Easter (gastro)", 12, 4, 0.7, "high", "Pascua: pico gastronómico (movable).")
    add("halloween_dulce", "Halloween + dulces", "Halloween + candy", 31, 10, 0.5, "medium", "31 de octubre: pico de golosinas (adoptado de USA, popular en PY urbano).")
    add("dia_difuntos", "Día de los Difuntos (PY)", "Day of the Dead (PY)", 2, 11, 0.3, "low", "2 de noviembre: chipa y mbejú en honor a difuntos.")
    add("semana_marita", "Semana Mariteña", "Mariteña Week", 15, 7, 0.5, "medium", "15-21 de julio: festividad de la Virgen de Itacuá (Gua\u00darí, festivo gastronómico).")
    add("carnaval_inicio", "Inicio de Carnaval", "Carnival start", 14, 2, 0.7, "high", "Carnaval: pico gastronómico de comida callejera (movable).")
    add("carnaval_fin", "Fin de Carnaval", "Carnival end", 17, 2, 0.7, "high", "Último día de Carnaval: pico gastronómico (movable).")

    # Días de comida saludable / tendencias (10 events)
    add("dia_alimentacion_saludable", "Día de la Alimentación Saludable", "Healthy Eating Day", 16, 10, 0.3, "low", "16 de octubre: Día Mundial de la Alimentación.")
    add("dia_vegetariano", "Día del Vegetarianismo", "Vegetarian Day", 1, 10, 0.3, "low", "1 de octubre: Día Mundial del Vegetarianismo.")
    add("dia_sin_carne", "Día sin Carne", "Meatless Day", 20, 3, 0.3, "low", "20 de marzo: Día sin Carne (movable-ish).")
    add("dia_fruta", "Día de la Fruta", "Fruit Day", 21, 7, 0.3, "low", "21 de julio: Día de la Fruta.")
    add("dia_ensalada", "Día de la Ensalada", "Salad Day", 18, 7, 0.3, "low", "18 de julio: Día de la Ensalada.")
    add("dia_jugo_natural", "Día del Jugo Natural", "Natural Juice Day", 9, 5, 0.3, "low", "9 de mayo: Día del Jugo Natural.")
    add("dia_batido", "Día del Batido", "Smoothie Day", 21, 6, 0.3, "low", "21 de junio: Día del Batido.")
    add("dia_agua", "Día del Agua", "Water Day", 22, 3, 0.3, "low", "22 de marzo: Día Mundial del Agua (relevante para bebidas).")
    add("dia_snack_saludable", "Día del Snack Saludable", "Healthy Snack Day", 15, 6, 0.3, "low", "15 de junio: Día del Snack Saludable.")
    add("dia_cocina_internacional", "Día de la Cocina Internacional", "International Cuisine Day", 14, 6, 0.3, "low", "14 de junio: Día de la Cocina Internacional.")

    return events


# ---- Tier 4: NL heritage (13 events × 3 years = 39 rows) ----

def _tier4_nl_heritage_events() -> list[dict[str, Any]]:
    """Tier 4: 13 Dutch heritage events. NL = Netherlands, NOT national PY.

    These are for the 'Vaquita Holandesa' brand identity. 3 are already
    in tier 1 (Sinterklaas, Koningsdag, Bevrijdingsdag); this tier adds 10 more.
    """
    events: list[dict[str, Any]] = []
    years = [2026, 2027, 2028]

    def add(slug: str, name_es: str, name_nl: str, name_en: str,
            day: int, month: int, impact: float, impact_tag: str,
            description: str = "") -> None:
        for y in years:
            events.append({  # noqa: PERF401
                "slug": slug,
                "name_es": name_es,
                "name_nl": name_nl,
                "name_en": name_en,
                "description": description or None,
                "event_date": date(y, month, day),
                "country": "NL",
                "category": "heritage",
                "impact_score": impact,
                "impact_tag": impact_tag,
                "relevance_tags": "",
                "is_annual": True,
                "recurrence": "fixed",
            })

    # 10 NL heritage events (Sinterklaas, Koningsdag, Bevrijdingsdag are
    # already in tier 1; see _tier1_universal_events)
    add("dodenherdenking", "Día de los Caídos (NL)", "Dodenherdenking", "Remembrance Day (NL)",
        4, 5, 0.3, "low", "4 de mayo: día de recuerdo de los ca\u00eddos en la Segunda Guerra Mundial (NL).")
    add("dag_van_de_arbeid", "Día del Trabajo (NL)", "Dag van de Arbeid", "Labor Day (NL)",
        5, 5, 0.3, "low", "5 de mayo: Día del Trabajo en Países Bajos (v\u00e9ase también 1 de mayo PY/AR).")
    add("prinsjesdag", "Apertura del Parlamento (NL)", "Prinsjesdag", "Budget Day (NL)",
        15, 9, 0.2, "low", "Tercer martes de septiembre (fijo al 15 en 2026-2028): Prinsjesdag, apertura del Parlamento NL.")
    add("koninginnedag_vooravond", "Víspera del Día de la Reina (NL)", "Koninginnedag vooravond", "Queen's Day Eve (NL)",
        29, 4, 0.2, "low", "29 de abril: víspera del Koninginnedag (festividad popular, sustituida por Koningsdag desde 2014).")
    add("vaderdag_nl", "Día del Padre (NL)", "Vaderdag", "Father's Day (NL)",
        16, 6, 0.3, "low", "Tercer domingo de junio (fijo al 16 en 2026-2028): Día del Padre en NL.")
    add("moederdag_nl", "Día de la Madre (NL)", "Moederdag", "Mother's Day (NL)",
        11, 5, 0.4, "medium", "Segundo domingo de mayo (fijo al 11 en 2026-2028): Día de la Madre en NL.")
    add("dierendag", "Día de los Animales (NL)", "Dierendag", "Animal Day (NL)",
        4, 10, 0.2, "low", "4 de octubre: Día de los Animales en Países Bajos (tradición de dar stroopwafel a las mascotas).")
    add("sint_maarten", "San Martín (NL)", "Sint-Maarten", "St. Martin's Day (NL)",
        11, 11, 0.3, "low", "11 de noviembre: Sint-Maarten, los niños cantan a cambio de dulces (lámpara de calabaza).")
    add("pakjesavond", "Noche de los Regalos (NL)", "Pakjesavond", "Package Night (NL)",
        5, 12, 0.4, "medium", "5 de diciembre: noche en que Sinterklaas reparte regalos (víspera de Sinterklaas).")
    add("nieuwjaarsduik", "Salto de Año Nuevo (NL)", "Nieuwjaarsduik", "New Year's Dive (NL)",
        1, 1, 0.3, "low", "1 de enero: Nieuwjaarsduik en Scheveningen, evento de masas (pico de oliebollen).")
    add("oliebollen_dag", "Día de los Oliebollen", "Oliebollendag", "Oliebollen Day",
        31, 12, 0.3, "low", "31 de diciembre: tradición de comer oliebollen en Nochevieja (NL).")
    add("haring_aankomst", "Llegada del Arenque (NL)", "Hollandse Nieuwe aankomst", "First New Herring Day",
        16, 6, 0.2, "low", "Mitad de junio: primer arenque nuevo del año en subasta de Scheveningen.")
    add("koninginnespel_dag", "Día de los Juegos de la Reina", "Koningsspelen", "King's Games Day",
        22, 4, 0.2, "low", "Penúltima semana de abril: evento escolar-deportivo nacional NL.")

    return events


def seed_seasonal_events_full(
    session: Session,
    *,
    year_range: tuple[int, int] = (2026, 2028),
) -> dict[str, int]:
    """Insert all 4 tiers of SeasonalEvent catalog.

    Idempotent: skip if (country, slug, event_date) already exists.
    Returns a dict of per-tier insertion counts.

    Args:
        session: SQLAlchemy session.
        year_range: inclusive (start_year, end_year) to seed.

    Side effects:
        Adds SeasonalEvent rows; does NOT commit. Caller commits.
    """
    now = datetime.now(timezone.utc)
    result = {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0, "skipped": 0}

    def _insert_rows(rows: list[dict[str, Any]], tier_key: str) -> None:
        rows = [r for r in rows if year_range[0] <= r["event_date"].year <= year_range[1]]
        for row in rows:
            existing = session.execute(
                select(SeasonalEvent).where(
                    SeasonalEvent.country == row["country"],
                    SeasonalEvent.slug == row["slug"],
                    SeasonalEvent.event_date == row["event_date"],
                )
            ).scalar_one_or_none()
            if existing is not None:
                result["skipped"] += 1
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
            result[tier_key] += 1

    _insert_rows(_tier1_universal_events(), "tier1")
    _insert_rows(_tier2_vertical_events(), "tier2")
    _insert_rows(_tier3_gastronomy_events(), "tier3")
    _insert_rows(_tier4_nl_heritage_events(), "tier4")

    session.flush()
    logger.info(
        f"seed_seasonal_events_full: {result['tier1']} t1, {result['tier2']} t2, "
        f"{result['tier3']} t3, {result['tier4']} t4 new, {result['skipped']} skipped."
    )
    return result



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
