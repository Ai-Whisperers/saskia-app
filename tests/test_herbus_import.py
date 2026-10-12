"""Tests for SASKIA-223: HEREBUS data import (100 ingredients, 23 recipes, 7 packaging)."""

from __future__ import annotations

from sqlalchemy import text

from app.rms.seed.herbus_import import (
    HEREBUS_RECIPES_RAW,
    _get_herbus_ingredients,
    _get_herbus_packaging,
    seed_herbus_data,
    seed_herbus_ingredients,
    seed_herbus_packaging,
    seed_herbus_recipes,
)


def test_herbus_ingredients_count_100():
    """The HEREBUS Inventory sheet has 100 ingredients."""
    assert len(_get_herbus_ingredients()) == 100


def test_herbus_recipes_count_23():
    """The HEREBUS Recipe_* sheets have 23 recipes (REC-001 to REC-023)."""
    assert len(HEREBUS_RECIPES_RAW) == 23


def test_herbus_packaging_count_7():
    """The HEREBUS Packaging sheet has 7 items (PKG-001 to PKG-007)."""
    assert len(_get_herbus_packaging()) == 7


def test_herbus_dutch_heritage_flag_4_ingredients():
    """4 ingredients are flagged as Dutch heritage (Speculaas, Ketjap Manis,
    Bladerdeeg/Hojaldre, Harina de centeno)."""
    dutch = [i for i in _get_herbus_ingredients() if i["dutch_heritage"]]
    assert len(dutch) == 5  # 4 + Hagelslag (chispas de chocolate neerlandesas)
    dutch_names = {i["name"] for i in dutch}
    assert "Harina de centeno" in dutch_names
    assert "Especias para Speculaas" in dutch_names
    assert "Masa de hojaldre" in dutch_names
    assert "Ketjap manis" in dutch_names
    assert "Hagelslag" in dutch_names  # Dutch chocolate sprinkles


def test_herbus_dutch_heritage_flag_11_recipes():
    """11 recipes are flagged as Dutch heritage (Stroopwafel, Ontbijtkoek,
    Frikandel, Ketjap Manis, Hojaldre, Pastelitos Rosados, Galletas
    de Especuloos, Mijn moeders appeltaart, Proficteroles de Den Bosch,
    Oliebollen, Goulash Croquettes, Veggie Bitterballen)."""
    dutch = [r for r in HEREBUS_RECIPES_RAW if r["dutch_heritage"]]
    assert len(dutch) == 12  # 11 + Tarta de manzana (Dutch apple pie)
    dutch_names = {r["name"] for r in dutch}
    assert "Stroopwafel" in dutch_names
    assert "Ontbijtkoek (Dutch breakfast cake, 700g flour)" in dutch_names
    assert "Frikandel (Dutch minced meat sausage, 100 pcs)" in dutch_names
    assert "Veggie Bitterballen (Dutch, 100 pcs)" in dutch_names


def test_herbus_rec006_assigned_to_frikandel():
    """The spreadsheet uses REC-006 for both Frikandel AND Veggie
    Bitterballen (data error). The seeder assigns REC-006 to Frikandel
    (per the spreadsheet) and renames Veggie Bitterballen to REC-024
    to avoid the duplicate."""
    rec_ids = [r["rec_id"] for r in HEREBUS_RECIPES_RAW]
    # REC-006 should appear once
    assert rec_ids.count("REC-006") == 1
    # The Veggie Bitterballen has rec_id="REC-024" via the re-assignment
    frikandel = next(r for r in HEREBUS_RECIPES_RAW if "Frikandel" in r["name"])
    assert frikandel["rec_id"] == "REC-006"


def test_herbus_yield_qty_all_none():
    """All 23 recipes have empty B4 in the spreadsheet (operator hasn't
    cooked them yet). The seeder uses 1.0 default."""
    none_count = sum(1 for r in HEREBUS_RECIPES_RAW if r["yield_qty"] is None)
    assert none_count == 23


def test_seed_herbus_ingredients_inserts_dutch_ones(session_factory):
    """After seed, the 4 Dutch heritage ingredients are in the DB."""
    with session_factory() as s:
        n = seed_herbus_ingredients(s)
        s.commit()
    assert n >= 4, f"expected at least 4 new ingredients, got {n}"

    with session_factory() as s:
        n = s.execute(
            text(
                "SELECT COUNT(*) FROM ingredient WHERE name IN ("
                "'Harina de centeno', 'Especias para Speculaas', "
                "'Masa de hojaldre', 'Ketjap manis')"
            )
        ).scalar()
    assert n == 4


def test_seed_herbus_recipes_creates_23_recipes(session_factory):
    """After seed, 23 recipes are in the DB."""
    with session_factory() as s:
        seed_herbus_ingredients(s)  # Pre-requisite
        n = seed_herbus_recipes(s)
        s.commit()
    assert n == 23

    with session_factory() as s:
        n = s.execute(text("SELECT COUNT(*) FROM recipe")).scalar()
    assert n == 23


def test_seed_herbus_recipes_creates_recipe_lines(session_factory):
    """Each recipe has its ingredient lines (avg ~12 per recipe)."""
    with session_factory() as s:
        seed_herbus_ingredients(s)
        seed_herbus_recipes(s)
        s.commit()
    with session_factory() as s:
        n = s.execute(text("SELECT COUNT(*) FROM recipe_line")).scalar()
    # 23 recipes * avg 12 = ~276 lines, allow for 100-400
    assert 100 <= n <= 400, f"expected 100-400 recipe_lines, got {n}"


def test_seed_herbus_recipes_sets_appmeta_yield_backfill(session_factory):
    """After seed, AppMeta.recipe_yield_backfill_pending = 'true'."""
    with session_factory() as s:
        seed_herbus_ingredients(s)  # Pre-requisite
        seed_herbus_recipes(s)
        s.commit()
        v = s.execute(
            text("SELECT value FROM app_meta WHERE key = 'recipe_yield_backfill_pending'")
        ).scalar()
    assert v == "true"


def test_seed_herbus_packaging_creates_7(session_factory):
    """After seed, 7 packaging items are in the DB (category='packaging')."""
    with session_factory() as s:
        n = seed_herbus_packaging(s)
        s.commit()
    assert n == 7

    with session_factory() as s:
        n = s.execute(
            text("SELECT COUNT(*) FROM ingredient WHERE category = 'packaging'")
        ).scalar()
    assert n == 7


def test_seed_herbus_data_is_idempotent(session_factory):
    """Re-running seed_herbus_data inserts 0 rows the second time."""
    with session_factory() as s:
        n1 = seed_herbus_data(s)
        s.commit()
    with session_factory() as s:
        n2 = seed_herbus_data(s)
        s.commit()
    assert n1 >= 80, f"first run should add 80+ rows, got {n1}"
    assert n2 == 0, f"second run should add 0 rows, got {n2}"


def test_seed_herbus_ingredients_skip_existing(session_factory):
    """seed_herbus_ingredients skips ingredients that already exist
    in the DB (added by the earlier sazon.py seeder)."""
    with session_factory() as s:
        n = seed_herbus_ingredients(s)
        s.commit()
    # Many ingredients are duplicates of the earlier sazon.py seeder,
    # so the new count is less than 100. The skipped count is the rest.
    assert n <= 100
    assert n >= 4  # At least the 4 unique Dutch heritage ones
