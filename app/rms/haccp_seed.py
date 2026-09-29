"""app/rms/haccp_seed.py — Phase 1.C HACCP defaults per ingredient category.

Per Res S.G. N° 213/2019 + MERCOSUR GMC 80/96 (BPM) + Codex Alimentarius CXS
23-1999 (higiene de la carne).

This is a best-effort operator-curated baseline. The values below reflect
Paraguayan panadería operating conditions:

- Refrigerated dairy: 0–5°C, ≤70% RH
- Eggs: 0–5°C
- Fresh meat: 0–4°C
- Frozen: ≤-18°C
- Ambient dry goods: 15–25°C, ≤70% RH
- Fruits/veg (fresh): 4–8°C
- Fats (oils, manteca): ambient (15–25°C); refrigerate once opened
- Spices: ambient, dry, <60% RH

`water_activity_aw` is the dominant HACCP pathogen control:
- a_w < 0.85 = shelf-stable (no pathogens grow)
- 0.85 ≤ a_w < 0.95 = potentially hazardous refrigerated
- a_w ≥ 0.95 = perishable

`lot_required` triggers FIFO tracking per batch. True for dairy/eggs/meat/seafood.
False for dry/sugar/salt/alcohol/oils (shelf-stable).

To use:
    from app.rms.haccp_seed import apply_haccp_defaults
    apply_haccp_defaults(session)  # idempotent: sets defaults for ingredients without values
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.rms.models import Ingredient

# Defaults by category. Tweak as the operator audits each ingredient.
# Tuple order: (temp_min_c, temp_max_c, humidity_max_pct, water_activity_aw, lot_required)
CATEGORY_HACCP: dict[str, tuple[float | None, float | None, float | None, float | None, bool]] = {
    "lácteos":        (0.0,   5.0,   70.0, 0.97, True),
    "carnes":         (0.0,   4.0,   75.0, 0.97, True),
    "huevos":         (0.0,   5.0,   70.0, 0.97, True),
    "frutas":         (4.0,   8.0,   85.0, 0.97, True),
    "harinas":        (15.0,  25.0,  70.0, 0.65, False),
    "endulzantes":    (15.0,  25.0,  70.0, 0.50, False),
    "grasas":         (15.0,  25.0,  70.0, 0.40, False),
    "leudantes":      (15.0,  25.0,  70.0, 0.65, False),
    "especias":       (15.0,  25.0,  60.0, 0.40, False),
    "frutos-secos":   (10.0,  20.0,  65.0, 0.60, False),
    "decoración":     (15.0,  25.0,  70.0, 0.55, False),
    "líquidos":       (0.0,   5.0,   75.0, 0.99, False),  # water — refrigerated after open
    "semillas":       (10.0,  20.0,  65.0, 0.55, False),
    "otros":          (15.0,  25.0,  70.0, 0.70, False),
}


def apply_haccp_defaults(session: Session) -> int:
    """Set HACCP defaults for ingredients whose category is known but whose
    HACCP fields are NULL. Idempotent: skips rows that already have values.

    Returns the number of ingredients updated.
    """
    from app.rms.ingredient_intel import infer_category

    updated = 0
    for ing in session.query(Ingredient).all():
        # Skip if already populated
        if (
            ing.temp_min_c is not None
            and ing.temp_max_c is not None
            and ing.humidity_max_pct is not None
            and ing.water_activity_aw is not None
            and ing.lot_required is not None
        ):
            continue

        # Use inferred category (covers NULL category too)
        cat = ing.category or infer_category(ing.name)
        defaults = CATEGORY_HACCP.get(cat)
        if defaults is None:
            continue

        t_min, t_max, hum, aw, lot = defaults
        if ing.temp_min_c is None:
            ing.temp_min_c = t_min
        if ing.temp_max_c is None:
            ing.temp_max_c = t_max
        if ing.humidity_max_pct is None:
            ing.humidity_max_pct = hum
        if ing.water_activity_aw is None:
            ing.water_activity_aw = aw
        if not ing.lot_required:
            ing.lot_required = lot

        # Also persist the inferred category itself
        if not ing.category:
            ing.category = cat
        updated += 1

    if updated:
        session.commit()
    return updated


__all__ = ["CATEGORY_HACCP", "apply_haccp_defaults"]
