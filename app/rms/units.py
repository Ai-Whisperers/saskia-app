"""Unit enum for HEREBUS recipes and inventory.

Per docs/operations/2026-09-fase-1-specs.md §B and the
04_foodbiz/AGENTS.md hard rule (Guaraní integers + canonical unit set).

Free-text units (e.g., "gramos" vs "g" vs "gram") are a bug factory.
This enum constrains all units to 5 values with fuzzy matching on aliases.

Why not use pint or unit-system libraries:
- Pint supports any unit but doesn't enforce the canonical set we need.
- Storing "g/kg/ml/l/und" as a string lets typos through.
- Coercion via alias map is 30 lines of code; library is overkill.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum


class Unit(Enum):
    """Canonical units for HEREBUS ops.

    To add a new unit: append a member AND add aliases to `coerce()` below.
    Do not add units without operator review.
    """

    G = "g"  # grams
    KG = "kg"  # kilograms
    ML = "ml"  # milliliters
    L = "l"  # liters
    UNIT = "und"  # countable items (eggs, muffins, packages)

    @property
    def display(self) -> str:
        """Canonical display string."""
        return self.value

    @classmethod
    def coerce(cls, value) -> "Unit":
        """Parse free-text input into canonical Unit. Fuzzy on aliases.

        Examples:
            >>> Unit.coerce("gramos")
            <Unit.G: 'g'>
            >>> Unit.coerce("kilo")
            <Unit.KG: 'kg'>
            >>> Unit.coerce("mililitros")
            <Unit.ML: 'ml'>
            >>> Unit.coerce("litros")
            <Unit.L: 'l'>
            >>> Unit.coerce("porcion")
            <Unit.UNIT: 'und'>
            >>> Unit.coerce("u")
            <Unit.UNIT: 'und'>
            >>> Unit.coerce("stones")
            Traceback (most recent exception being shown): ...
            ValueError: unknown unit: 'stones'. Allowed: g, kg, ml, l, und
        """
        if value is None:
            raise ValueError("empty unit")
        s = str(value).strip().lower()
        # Alias map: free-text input -> canonical Unit
        aliases = {
            # grams
            "g": cls.G,
            "gramo": cls.G,
            "gramos": cls.G,
            "gram": cls.G,
            # kilograms
            "kg": cls.KG,
            "kilo": cls.KG,
            "kilos": cls.KG,
            "kilogramo": cls.KG,
            "kilogramos": cls.KG,
            # milliliters
            "ml": cls.ML,
            "mililitro": cls.ML,
            "mililitros": cls.ML,
            # liters
            "l": cls.L,
            "litro": cls.L,
            "litros": cls.L,
            # countable
            "und": cls.UNIT,
            "unidad": cls.UNIT,
            "unidades": cls.UNIT,
            "u": cls.UNIT,
            "porcion": cls.UNIT,
            "bandeja": cls.UNIT,
            "bandejas": cls.UNIT,
            "torta": cls.UNIT,
            "tortas": cls.UNIT,
            "muffin": cls.UNIT,
            "muffins": cls.UNIT,
            "galleta": cls.UNIT,
            "galletas": cls.UNIT,
            "porción": cls.UNIT,  # with accent
            "porciones": cls.UNIT,
        }
        if s in aliases:
            return aliases[s]
        # Try direct enum value match
        for member in cls:
            if member.value == s:
                return member
        # Allow list of allowed values in the error message
        allowed = ", ".join(m.value for m in cls)
        raise ValueError(f"unknown unit: {value!r}. Allowed: {allowed}")

    @classmethod
    def allowed_values(cls) -> list[str]:
        """List of canonical values for documentation / API responses."""
        return [m.value for m in cls]


# Conversion factor table: from_unit -> to_unit -> Decimal
# Only intra-family conversions (g↔kg, ml↔l). Cross-family is forbidden
# because density matters (g→ml needs the ingredient's density).
_CONVERSION_FACTORS = {
    (Unit.G, Unit.KG): Decimal("0.001"),
    (Unit.KG, Unit.G): Decimal("1000"),
    (Unit.ML, Unit.L): Decimal("0.001"),
    (Unit.L, Unit.ML): Decimal("1000"),
}


def can_convert(from_unit: Unit, to_unit: Unit) -> bool:
    """True if from_unit can be converted to to_unit.

    Same-family conversions are allowed (g↔kg, ml↔l).
    Cross-family conversions are forbidden (would need ingredient-specific
    density; out of scope for fase 1).
    """
    if from_unit == to_unit:
        return True
    return (from_unit, to_unit) in _CONVERSION_FACTORS


def convert_qty(qty, from_unit: Unit, to_unit: Unit):
    """Convert quantity from one unit to another within the same family.

    Examples:
        >>> convert_qty(Decimal("1500"), Unit.G, Unit.KG)
        Decimal('1.5')
        >>> convert_qty(Decimal("1.5"), Unit.KG, Unit.G)
        Decimal('1500')
        >>> convert_qty(Decimal("100"), Unit.G, Unit.L)
        Traceback (most recent exception being shown): ...
        ValueError: Cannot convert g to l (cross-family)
    """
    from app.rms.money import to_decimal

    if not can_convert(from_unit, to_unit):
        raise ValueError(f"Cannot convert {from_unit.value} to {to_unit.value} (cross-family)")
    qty_dec = to_decimal(qty)
    if from_unit == to_unit:
        return qty_dec
    factor = _CONVERSION_FACTORS[(from_unit, to_unit)]
    return qty_dec * factor


__all__ = ["Unit", "can_convert", "convert_qty"]
