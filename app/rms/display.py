"""app/rms/display.py — F-track formatters (redesign base layer 2026-09-26).

One implementation each for money / quantity / percent / date / delta /
entity-name guards / enum labels. Registered as Jinja globals `fmt.*`.

Contracts (02-REUSE-ABSTRACTION.md §2):
  fmt_money(v)       int-ish → "Gs. 18.000"; None/undefined/str → "—"; 0 → "Gs. 0"
  fmt_qty(v, unit)   trims zeros, py decimal comma, unit attached
  fmt_pct(v, delta)  ≥10 → 0 dec; <10 → 1 dec; delta adds +/−
  fmt_date(d, mode)  table="26/09/2026" · prose="sáb 26 sep 2026" · iso
  delta(v, prior)    {pct, direction, empty} — neutral-empty rule, ONE impl
  entity_name(x)     guards "Producto 9ab34f11"-style hash names
  status_es(v)       re-exported from nav.SS-3
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_HASH_NAME = re.compile(r"^(Producto|Ingrediente|Receta|Proveedor|Cliente)\s+[0-9a-f]{8}$", re.IGNORECASE)

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _is_numberish(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fmt_money(v: Any) -> str:
    """Money → 'Gs. 18.000'. Tolerates None/undefined/strings (drift guard)."""
    if v is None or not _is_numberish(v):
        return "—"
    sign = "-" if v < 0 else ""
    return f"{sign}Gs. {int(abs(v)):,}".replace(",", ".")


def fmt_qty(v: Any, unit: str = "") -> str:
    """Quantity → '0,4 kg' / '2 u.' — trimmed zeros, py comma."""
    if v is None or not _is_numberish(v):
        return "—" if not unit else f"— {unit}"
    if float(v) == int(v):
        s = str(int(v))
    else:
        s = f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{s} {unit}".strip()


def fmt_pct(v: Any, delta: bool = False) -> str:
    """Percent → '68%' / '0,8%' (1 dec <10). delta=True prefixes +/−."""
    if v is None or not _is_numberish(v):
        return "—"
    if abs(v) >= 10:
        s = f"{v:.0f}%"
    else:
        s = f"{v:.1f}%".replace(".", ",")
    if delta:
        s = f"{'+' if v >= 0 else '−'}{s[1:] if s.startswith('-') else s}"
        if v < 0:
            s = f"−{abs(v):.0f}%" if abs(v) >= 10 else f"−{abs(v):.1f}%".replace(".", ",")
    return s


def fmt_date(d: Any, mode: str = "table") -> str:
    """Date → table '26/09/2026' · prose 'sáb 26 sep 2026' · iso '2026-09-26'."""
    if d is None:
        return "—"
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d[:10])
        except ValueError:
            return d
    if isinstance(d, datetime):
        d = d.date()
    if not isinstance(d, date):
        return str(d)
    if mode == "iso":
        return d.strftime("%Y-%m-%d")
    if mode == "prose":
        return f"{_DIAS[d.weekday()][:3]} {d.day} {_MESES[d.month-1]} {d.year}"
    return d.strftime("%d/%m/%Y")


def delta(current: Any, prior: Any) -> dict:
    """ONE implementation of the delta neutral-empty rule.

    Returns {pct: float|None, direction: 'up'|'down'|'neutral', empty: bool}.
    empty=True when current==0 and prior>0 → UI shows 'sin ventas en el período',
    never '↓ 100% abajo'.
    """
    if not _is_numberish(current) or not _is_numberish(prior):
        return {"pct": None, "direction": "neutral", "empty": False}
    if current == 0 and prior > 0:
        return {"pct": None, "direction": "neutral", "empty": True}
    if prior == 0:
        if current == 0:
            return {"pct": None, "direction": "neutral", "empty": True}
        return {"pct": None, "direction": "up", "empty": False}  # new: no base
    pct = (current - prior) / prior * 100
    return {
        "pct": pct,
        "direction": "up" if pct > 0 else "down" if pct < 0 else "neutral",
        "empty": False,
    }


def entity_name(x: Any) -> str:
    """Guard hash-suffixed seed names: 'Producto 99b78b3b' → 'Producto sin nombre'."""
    if x is None:
        return "—"
    name = x if isinstance(x, str) else (x.get("name") if isinstance(x, dict) else getattr(x, "name", None)) or ""
    name = name.strip()
    if not name:
        return "Sin nombre"
    if _HASH_NAME.match(name):
        return f"{name.split()[0]} sin nombre"
    return name


__all__ = [
    "fmt_money",
    "fmt_qty",
    "fmt_pct",
    "fmt_date",
    "delta",
    "entity_name",
]
