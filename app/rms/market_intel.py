"""app/rms/market_intel.py — estadística de evidencia de competencia.

Conecta la tabla competitor_price_observation (precios retail de terceros,
sembrados desde el research repo sazon-market-intel) con:

- /vs-mercado         → columna "mercado real" por familia de cada benchmark
- /vs-mercado/evidencia → tabla de rangos por familia + detalle reciente
- /vs-mercado/evidencia.csv → export completo para auditoría

Taxonomía de 9 familias (idéntica a consolidar_wave2.py del research repo):
facturas, tortas, brownies, muffins, cookies, panes, cafes, tes, stroopwafels.
El match benchmark↔familia es por keywords sobre product_label — es
heurístico a propósito: un benchmark sin familia simplemente no muestra
columna de mercado (None), nunca inventa un match.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import CompetitorPriceObservation

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "facturas": (
        "factura",
        "medialuna",
        "croissant",
        "cruasan",
        "caracol",
        "strudel",
        "hojaldre",
        "pastelito",
        "palmera",
        "bolleria",
        "biscocho",
    ),
    "tortas": (
        "cheesecake",
        "tarta",
        "torta",
        "carrot",
        "pie de",
        "pastafrola",
        "appeltaart",
        "mil hojas",
        "tartita",
    ),
    "brownies": ("brownie",),
    "muffins": ("muffin", "magdalena"),
    "cookies": ("cookie", "galleta", "alfajor"),
    "panes": (
        "pan lactal",
        "pan de molde",
        "molde",
        "baguette",
        "pan de campo",
        "hogaza",
        "masa madre",
        "pan blanco",
        "pan integral",
        "pan brioche",
    ),
    "cafes": (
        "espresso",
        "expreso",
        "americano",
        "latte",
        "capuchino",
        "capuccino",
        "cortado",
        "macchiato",
        "filtrado",
        "flat white",
        "mocca",
        "mocha",
    ),
    "tes": (
        "cocido",
        "chai",
        "matcha",
        "infusion",
        "te en hebras",
        "te con leche",
        "te negro",
        "te verde",
    ),
    "stroopwafels": ("stroopwafel", "stroop", "holanguayo", "waffle"),
}

# keywords de combo: un "Desayuno Del Sur" NUNCA es evidencia de precio de café
_COMBO_HINTS = ("desayuno", "combo", "promo", "merienda para", "para dos")

FAMILIES: tuple[str, ...] = tuple(FAMILY_KEYWORDS)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()


def family_of(label: str) -> str | None:
    """Familia de un label de producto (heurística por keywords)."""
    n = _norm(label)
    if any(h in n for h in _COMBO_HINTS):
        return None
    for fam, kws in FAMILY_KEYWORDS.items():
        if any(k in n for k in kws):
            return fam
    return None


@dataclass(frozen=True)
class FamilyStat:
    family: str
    unit: str
    n: int
    min_gs: int
    p25_gs: int
    median_gs: int
    p75_gs: int
    max_gs: int


def _pct(sorted_vals: list[int], q: float) -> int:
    return sorted_vals[int(q * (len(sorted_vals) - 1))]


def family_stats(session: Session, unit: str = "unidad") -> list[FamilyStat]:
    """Rangos por familia para observaciones de esa unidad.

    Solo precios 300–500.000 Gs (fuera de ahí es error de carga o un
    evento de catering, no un precio retail comparable).
    """
    rows = (
        session.execute(
            select(CompetitorPriceObservation).where(CompetitorPriceObservation.unit == unit)
        )
        .scalars()
        .all()
    )

    by_family: dict[str, list[int]] = {}
    for r in rows:
        if not r.family or not (300 <= r.price_gs <= 500_000):
            continue
        by_family.setdefault(r.family, []).append(r.price_gs)

    out: list[FamilyStat] = []
    for fam, vals in by_family.items():
        vals.sort()
        out.append(
            FamilyStat(
                family=fam,
                unit=unit,
                n=len(vals),
                min_gs=vals[0],
                p25_gs=_pct(vals, 0.25),
                median_gs=int(statistics.median(vals)),
                p75_gs=_pct(vals, 0.75),
                max_gs=vals[-1],
            )
        )
    out.sort(key=lambda s: -s.n)
    return out


def stats_by_family(session: Session, unit: str = "unidad") -> dict[str, FamilyStat]:
    """Índice familia → FamilyStat para lookup O(1) en vistas."""
    return {s.family: s for s in family_stats(session, unit=unit)}
