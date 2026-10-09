"""tests/test_haccp_seed.py — Phase 1.C HACCP defaults per category."""

from __future__ import annotations

from app.rms.haccp_seed import CATEGORY_HACCP, apply_haccp_defaults
from app.rms.models import Ingredient


def _make_ingredient(session, name, category=None, **overrides):
    defaults = dict(
        name=name,
        unit="kg",
        stock_qty=0.0,
    )
    defaults.update(overrides)
    if category:
        defaults["category"] = category
    ing = Ingredient(**defaults)
    session.add(ing)
    session.commit()
    session.refresh(ing)
    return ing


class TestHacpCategoryTable:
    def test_all_categories_covered(self):
        """Every product category used in the inference engine has HACCP defaults."""
        from app.rms.ingredient_intel import _CATEGORY_KEYWORDS

        for cat in _CATEGORY_KEYWORDS.keys():
            assert cat in CATEGORY_HACCP, f"Category {cat!r} missing from HACCP defaults"

    def test_perishable_categories_need_lot_tracking(self):
        """Lácteos, carnes, huevos, frutas require FIFO lot tracking."""
        for cat in ("lácteos", "carnes", "huevos", "frutas"):
            _t_min, _t_max, _hum, _aw, lot = CATEGORY_HACCP[cat]
            assert lot is True, f"{cat} should require lot tracking"

    def test_dry_goods_dont_need_lot_tracking(self):
        """Dry categories (flour, sugar, salt, spices) don't need lot tracking."""
        for cat in ("harinas", "endulzantes", "grasas", "leudantes", "especias"):
            _t_min, _t_max, _hum, _aw, lot = CATEGORY_HACCP[cat]
            assert lot is False, f"{cat} should NOT require lot tracking"

    def test_refrigerated_temp_range(self):
        """Refrigerated categories must have temp_max_c <= 8°C."""
        for cat in ("lácteos", "carnes", "huevos", "frutas"):
            _t_min, t_max, _hum, _aw, _lot = CATEGORY_HACCP[cat]
            assert t_max <= 8.0, f"{cat} refrigerated threshold > 8°C: {t_max}"

    def test_ambient_temp_range(self):
        """Ambient categories must have temp_min_c >= 10°C."""
        for cat in ("harinas", "endulzantes", "grasas", "leudantes", "especias", "decoración"):
            t_min, _t_max, _hum, _aw, _lot = CATEGORY_HACCP[cat]
            assert t_min >= 10.0, f"{cat} ambient temp_min should be >= 10°C: {t_min}"


class TestApplyHaccpDefaults:
    def test_applies_defaults_when_category_known(self, session_factory):
        Session = session_factory
        with Session() as s:
            ing = _make_ingredient(s, "Leche entera test", category="lácteos")
            n = apply_haccp_defaults(s)
            assert n >= 1
            s.refresh(ing)
            assert ing.temp_min_c == 0.0
            assert ing.temp_max_c == 5.0
            assert ing.lot_required is True

    def test_infers_category_from_name_when_missing(self, session_factory):
        Session = session_factory
        with Session() as s:
            ing = _make_ingredient(s, "Huevos de gallina", category=None)
            apply_haccp_defaults(s)
            s.refresh(ing)
            assert ing.category == "huevos"
            assert ing.lot_required is True

    def test_idempotent_skips_populated_rows(self, session_factory):
        Session = session_factory
        with Session() as s:
            ing = _make_ingredient(
                s,
                "Harina especial",
                category="harinas",
                temp_min_c=10.0,
                temp_max_c=20.0,
                humidity_max_pct=50.0,
                water_activity_aw=0.5,
                lot_required=False,
            )
            original_temp_min = ing.temp_min_c
            n = apply_haccp_defaults(s)
            assert n == 0
            s.refresh(ing)
            assert ing.temp_min_c == original_temp_min  # unchanged

    def test_unknown_category_no_op(self, session_factory):
        Session = session_factory
        with Session() as s:
            ing = _make_ingredient(s, "mystery ingredient xyz", category="unknown_category_xyz")
            n = apply_haccp_defaults(s)
            assert n == 0
            s.refresh(ing)
            assert ing.temp_min_c is None

    def test_partial_population_only_fills_missing(self, session_factory):
        """If only temp_min is set, the rest get filled."""
        Session = session_factory
        with Session() as s:
            ing = _make_ingredient(
                s,
                "Azúcar test",
                category="endulzantes",
                temp_min_c=20.0,  # only temp_min populated
            )
            n = apply_haccp_defaults(s)
            assert n >= 1
            s.refresh(ing)
            # temp_min stays at operator value
            assert ing.temp_min_c == 20.0
            # others get filled
            assert ing.temp_max_c == 25.0
            assert ing.humidity_max_pct == 70.0
            assert ing.water_activity_aw == 0.5
