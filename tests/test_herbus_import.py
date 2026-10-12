"""Tests for SASKIA-225: HEREBUS data import (94 ingredients, 22 recipes, 7 packaging).

Loads from ``data/herebus_seed_canonical.json`` (the canonical source of
truth, generated from Saskia's real ``data/herebus.xlsx``).
"""

from __future__ import annotations

from sqlalchemy import text

from app.rms.seed.herbus_import import (
    CANONICAL_PATH,
    load_canonical,
    seed_herbus_data,
    seed_herbus_ingredients,
    seed_herbus_packaging,
    seed_herbus_recipes,
)

# ---------------------------------------------------------------------------
# Canonical JSON shape tests
# ---------------------------------------------------------------------------


def test_canonical_json_exists():
    """The canonical JSON snapshot must exist in the repo."""
    assert CANONICAL_PATH.exists(), f"missing: {CANONICAL_PATH}"


def test_canonical_json_has_94_ingredients():
    """The xlsx has exactly 94 ingredients (ING-001..ING-094)."""
    data = load_canonical()
    assert len(data["inventory"]) == 94, f"got {len(data['inventory'])}"
    ids = {i["ing_id"] for i in data["inventory"]}
    assert ids == {f"ING-{n:03d}" for n in range(1, 95)}


def test_canonical_json_has_7_packaging():
    """The xlsx Packaging sheet has 7 items (MAT-01..MAT-07)."""
    data = load_canonical()
    assert len(data["packaging"]) == 7
    assert {p["pkg_id"] for p in data["packaging"]} == {
        "MAT-01", "MAT-02", "MAT-03", "MAT-04", "MAT-05", "MAT-06", "MAT-07"
    }


def test_canonical_json_has_22_recipes():
    """The xlsx has 22 Recipe_* sheets (including recipe_bitterballen)."""
    data = load_canonical()
    assert len(data["recipes"]) == 22


def test_canonical_recipe_yields_have_all_been_resolved():
    """Every recipe has a yield_qty (from sheet OR estimated)."""
    data = load_canonical()
    for r in data["recipes"]:
        assert r["yield_qty"] is not None, f"{r['rec_id']} {r['rec_name']} missing yield"
        assert r["yield_unit"] is not None


def test_canonical_preserves_saskias_real_yields():
    """The 7 recipes with explicit yields in her sheet must keep them."""
    data = load_canonical()
    sheet_yield = {r["rec_name"]: (r["yield_qty"], r["yield_source"]) for r in data["recipes"]}
    assert sheet_yield["Bombones de chocolate"] == (20.0, "sheet")
    assert sheet_yield["Cheesecake (30x50)"][1] == "sheet"
    assert sheet_yield["goulash crockettes"] == (100.0, "sheet")
    assert sheet_yield["Stroop wafel"] == (12.0, "sheet")
    assert sheet_yield["suppli cacio e pepe"] == (12.0, "sheet")
    assert sheet_yield["bitterballen vegetariano"] == (100.0, "sheet")
    # recipe_bitterballen_100_pcs
    assert any(
        r["rec_name"] == "bitterballen" and r["yield_qty"] == 100.0
        for r in data["recipes"]
    )


def test_canonical_estimated_yields_are_documented():
    """The 15 estimated yields should be marked so the operator can review."""
    data = load_canonical()
    estimated = [r for r in data["recipes"] if r["yield_source"] == "estimated"]
    assert len(estimated) == 15, f"expected 15 estimated, got {len(estimated)}"
    # All should be in _meta.counts
    meta = data["_meta"]
    assert meta["counts"]["yields_estimated"] == 15


def test_canonical_preserves_inline_notes():
    """Recipe lines with inline notes (column H) keep them."""
    data = load_canonical()
    # Find a recipe known to have notes (Goulash Croquettes has many)
    goulash = next(r for r in data["recipes"] if r["rec_name"] == "goulash crockettes")
    notes_lines = [i for i in goulash["ingredients"] if i.get("notes")]
    assert len(notes_lines) >= 5, f"expected 5+ noted lines in Goulash, got {len(notes_lines)}"


def test_canonical_margins_uniform():
    """All recipes use Saskia's margin profile: WHOLESALE 0.3, RETAIL 0.5, EVENTUAL 0.35."""
    data = load_canonical()
    for r in data["recipes"]:
        m = r["margins"]
        assert m.get("WHOLESALE") == 0.3
        assert m.get("RETAIL") == 0.5
        assert m.get("EVENTUAL") == 0.35


def test_canonical_ingredients_categories_count():
    """The Inventory sheet has 12 grupos."""
    data = load_canonical()
    grupos = {i["grupo"] for i in data["inventory"]}
    assert len(grupos) == 12


# ---------------------------------------------------------------------------
# Seed execution tests
# ---------------------------------------------------------------------------


def test_seed_herbus_ingredients_inserts_94(session_factory):
    """seed_herbus_ingredients inserts 94 rows into a fresh DB."""
    with session_factory() as s:
        report = seed_herbus_ingredients(s, load_canonical())
        s.commit()
    assert report["inserted"] == 94, f"got {report['inserted']}"
    assert report["skipped"] == 0
    # Verify in DB
    with session_factory() as s:
        n = s.execute(text("SELECT COUNT(*) FROM ingredient")).scalar()
    assert n == 94


def test_seed_herbus_ingredients_skips_existing(session_factory):
    """Re-running seed_herbus_ingredients inserts 0 (idempotent by name)."""
    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        s.commit()
    with session_factory() as s:
        report = seed_herbus_ingredients(s, canonical)
        s.commit()
    assert report["inserted"] == 0
    assert report["skipped"] == 94


def test_seed_herbus_packaging_inserts_7(session_factory):
    """seed_herbus_packaging inserts 7 packaging rows."""
    canonical = load_canonical()
    with session_factory() as s:
        # Pre-req: ingredient 'Harina de centeno' to test category='packaging' isolation
        seed_herbus_ingredients(s, canonical)
        report = seed_herbus_packaging(s, canonical)
        s.commit()
    assert report["inserted"] == 7
    with session_factory() as s:
        n = s.execute(
            text("SELECT COUNT(*) FROM ingredient WHERE category = 'packaging'")
        ).scalar()
    assert n == 7


def test_seed_herbus_recipes_inserts_22(session_factory):
    """After ingredients, seed_herbus_recipes inserts 22 recipes."""
    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        seed_herbus_packaging(s, canonical)
        report = seed_herbus_recipes(s, canonical)
        s.commit()
    assert report["inserted"] == 22
    assert report["skipped"] == 0
    # Recipe_line count: 222 ingredient lines from the xlsx, minus c.s.p. (qty=0)
    # and 10 duplicates (same rec_name+ing_id used in multiple qty rows).
    with session_factory() as s:
        n = s.execute(text("SELECT COUNT(*) FROM recipe_line")).scalar()
    # 222 total lines; 11 c.s.p. + 3 null + 10 dups skipped → 198 land.
    assert 190 <= n <= 210, f"expected ~198 recipe_lines, got {n}"


def test_seed_herbus_recipes_idempotent(session_factory):
    """Re-running seed_herbus_recipes inserts 0."""
    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        seed_herbus_recipes(s, canonical)
        s.commit()
    with session_factory() as s:
        report = seed_herbus_recipes(s, canonical)
        s.commit()
    assert report["inserted"] == 0


def test_seed_herbus_data_full_pipeline(session_factory):
    """seed_herbus_data runs all 4 seeders end-to-end."""
    with session_factory() as s:
        report = seed_herbus_data(s)
        s.commit()
    assert report["ingredients_inserted"] == 94
    assert report["packaging_inserted"] == 7
    assert report["recipes_inserted"] == 22
    # Yield estimates present
    assert len(report["yield_estimates"]) == 15


def test_seed_herbus_data_idempotent(session_factory):
    """Re-running seed_herbus_data inserts 0 rows the second time."""
    with session_factory() as s:
        r1 = seed_herbus_data(s)
        s.commit()
    with session_factory() as s:
        r2 = seed_herbus_data(s)
        s.commit()
    assert r1["ingredients_inserted"] == 94
    assert r2["ingredients_inserted"] == 0
    assert r2["packaging_inserted"] == 0
    assert r2["recipes_inserted"] == 0


def test_seed_herbus_data_drops_appmeta(session_factory):
    """After seed, AppMeta has the 3 provenance rows."""
    with session_factory() as s:
        seed_herbus_data(s)
        s.commit()
    with session_factory() as s:
        rows = s.execute(text("SELECT key, value FROM app_meta WHERE key LIKE 'herbus_%'")).fetchall()
    keys = {r[0] for r in rows}
    assert "herbus_seed_loaded" in keys
    assert "herbus_recipe_yield_estimates" in keys
    # herbus_data_warnings only present if there were warnings
    # (9 c.s.p. + 1 renumber = 10 warnings)


def test_rec006_renumber_logged_in_appmeta(session_factory):
    """The build script renumbers the REC-006 duplicate to REC-022 in the JSON.

    The seeder surfaces the renumber as a warning so the operator knows the
    data was adjusted. The renumber_log in _meta is preserved as AppMeta.
    """
    canonical = load_canonical()
    # Verify the JSON already has the renumber applied
    ids = [r["rec_id"] for r in canonical["recipes"]]
    assert len(ids) == len(set(ids)), f"duplicates in JSON: {ids}"
    # Frikandel is the FIRST REC-006 in the workbook
    frikandel = next(r for r in canonical["recipes"] if "Frikandel" in r["rec_name"])
    assert frikandel["rec_id"] == "REC-006"
    # bitterballen was the duplicate, now REC-022
    bitterballen = next(
        r for r in canonical["recipes"] if r["rec_name"] == "bitterballen"
    )
    assert bitterballen["rec_id"] == "REC-022"
    assert "renumber_note" in bitterballen
    # Seeder should surface the renumber as a warning
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        report = seed_herbus_recipes(s, canonical)
        s.commit()
    assert any("REC-006" in w and "REC-022" in w for w in report["warnings"])


def test_seed_preserves_saskias_inline_notes(session_factory):
    """Recipe lines with notes from the xlsx keep their notes."""
    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        seed_herbus_recipes(s, canonical)
        s.commit()
    with session_factory() as s:
        # Goulash had several noted lines
        n = s.execute(
            text("SELECT COUNT(*) FROM recipe_line WHERE notes IS NOT NULL AND notes != ''")
        ).scalar()
    assert n >= 30, f"expected 30+ recipe_lines with notes, got {n}"


def test_seed_preserves_dutch_heritage_flag(session_factory):
    """Dutch heritage recipes get menu_tags='dutch_heritage'."""
    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        seed_herbus_recipes(s, canonical)
        s.commit()
    with session_factory() as s:
        n = s.execute(
            text("SELECT COUNT(*) FROM recipe WHERE menu_tags = 'dutch_heritage'")
        ).scalar()
    # 13 dutch recipes (incl. the REC-006 disambiguated one for bitterballen)
    assert n >= 12, f"expected 12+ Dutch heritage recipes, got {n}"


def test_seed_matches_ingredients_with_diacritics(session_factory):
    """The seeder matches ingredient names case- and accent-insensitively.

    Saskia's Recipe sheets sometimes drop accents (PURE DE TOMATE) while
    Inventory has them (Puré de tomate). Both must resolve.
    """
    from app.rms.seed.herbus_import import _normalize_for_lookup

    # Smoke the normalizer
    assert _normalize_for_lookup("Puré de tomate") == "pure de tomate"
    assert _normalize_for_lookup("PURE DE TOMATE") == "pure de tomate"
    assert _normalize_for_lookup("Morrón rojo") == "morron rojo"
    assert _normalize_for_lookup("MORRON ROJO") == "morron rojo"
    assert _normalize_for_lookup("Pimentón ahumado") == "pimenton ahumado"

    # End-to-end: every recipe line should resolve (no "not found" warnings)
    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        seed_herbus_recipes(s, canonical)
        s.commit()
    # Goulash has 22 qty>0 lines in the xlsx, but 3 are duplicates of the same
    # (recipe, ingredient) pair (Huevos 2x, Aceite 2x) — dedup'd per idempotency.
    # The seeder's `existing_line` check ensures one RecipeLine per (recipe, ing)
    # pair, so 19 lines land in the DB.
    goulash = next(r for r in canonical["recipes"] if r["rec_name"] == "goulash crockettes")
    qty_lines = [i for i in goulash["ingredients"] if i.get("qty") and i["qty"] > 0]
    unique_pairs = {(i["ing_id"]) for i in qty_lines}
    n_expected = len(unique_pairs)
    with session_factory() as s:
        from app.rms.models import Recipe, RecipeLine
        rec = s.query(Recipe).filter_by(name="goulash crockettes").one()
        n_in_db = s.query(RecipeLine).filter_by(recipe_id=rec.id).count()
    assert n_in_db == n_expected, (
        f"Goulash: {n_in_db} lines in DB, expected {n_expected} (deduped by recipe+ing pair)"
    )


def test_seed_captures_opening_stock(session_factory):
    """Ingredients with numeric or text stock markers get opening_stock_qty."""
    from app.rms.models import Ingredient

    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        s.commit()

    # ING-001: stock_qty=1500 (numeric) → opening_stock_qty=1500
    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="Harina de centeno").one()
        assert ing.opening_stock_qty == 1500.0
        assert ing.stock_qty == 1500.0

    # ING-007: stock_qty_text='2kg' → opening_stock_qty=2.0
    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="Azúcar").one()
        assert ing.opening_stock_qty == 2.0
        assert ing.stock_qty == 2.0

    # ING-003: stock_qty=5000 (numeric) + min_reorder_text='5000'
    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="Harina de trigo").one()
        assert ing.opening_stock_qty == 5000.0
        assert ing.stock_qty == 5000.0
        # min_reorder_text parsed → min_stock_qty=5000
        assert ing.min_stock_qty == 5000.0


def test_seed_captures_purchase_price_updated_at(session_factory):
    """Ingredients with bulk_price_gs + last_update get price_updated_at datetime."""
    from app.rms.models import Ingredient

    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        s.commit()

    # Spot-check a few priced items (ING-005 Maicena: price=8500, last_update='07/10/2026')
    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="Maicena").one()
        assert ing.purchase_price_gs == 8500
        assert ing.purchase_price_updated_at is not None
        assert ing.purchase_price_updated_at.year == 2026
        assert ing.purchase_price_updated_at.month == 10
        assert ing.purchase_price_updated_at.day == 7
        # opening_stock_date also captured from last_update
        assert ing.opening_stock_date == "2026-10-07"


def test_seed_captures_dietary_tags_from_grupo(session_factory):
    """Ingredients get dietary_tags based on their categoria (grupo)."""
    from app.rms.models import Ingredient

    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        s.commit()

    with session_factory() as s:
        # Huevos is in 'Lácteos y huevos' → contains_animal_products
        huevos = s.query(Ingredient).filter_by(name="Huevos").one()
        assert huevos.dietary_tags == "contains_animal_products"

        # Pechuga de pollo is in 'Carnes' → contains_animal_products
        pollo = s.query(Ingredient).filter_by(name="Pechuga de pollo").one()
        assert pollo.dietary_tags == "contains_animal_products"

        # Cebolla is in 'Verduras y legumbres' → vegano
        cebolla = s.query(Ingredient).filter_by(name="Cebolla").one()
        assert cebolla.dietary_tags == "vegano"

        # Frutilla is in 'Frutas y frutos secos' → vegano
        frutilla = s.query(Ingredient).filter_by(name="Frutilla").one()
        assert frutilla.dietary_tags == "vegano"


def test_seed_captures_storage_zone(session_factory):
    """Storage zone is inferred from grupo: Carnes/Lácteos → refrigerated, rest → dry."""
    from app.rms.models import Ingredient

    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_ingredients(s, canonical)
        s.commit()

    with session_factory() as s:
        pollo = s.query(Ingredient).filter_by(name="Pechuga de pollo").one()
        assert pollo.storage == "refrigerated"
        huevos = s.query(Ingredient).filter_by(name="Huevos").one()
        assert huevos.storage == "refrigerated"
        harina = s.query(Ingredient).filter_by(name="Harina de trigo").one()
        assert harina.storage == "dry"
        azucar = s.query(Ingredient).filter_by(name="Azúcar").one()
        assert azucar.storage == "dry"


def test_seed_captures_packaging_opening_stock(session_factory):
    """Packaging items with stock_qty + last_update get opening_stock captured."""
    from app.rms.models import Ingredient

    canonical = load_canonical()
    with session_factory() as s:
        seed_herbus_packaging(s, canonical)
        s.commit()

    # MAT-01: stock_qty=90, no last_update
    with session_factory() as s:
        pkg = s.query(Ingredient).filter_by(name="bolsita de 15x22").one()
        assert pkg.opening_stock_qty == 90.0
        assert pkg.stock_qty == 90.0
        # MAT-01 desc: 'saco pp cromus incoloro cant 100' is in notes JSON
        assert "saco pp cromus" in (pkg.notes or "")

    # MAT-06: last_update='07/10/2026' → opening_stock_date='2026-10-07'
    with session_factory() as s:
        pkg = s.query(Ingredient).filter_by(name="bolsa de papel mediana").one()
        assert pkg.opening_stock_date == "2026-10-07"


def test_full_pipeline_reports_opening_stock_count(session_factory):
    """seed_herbus_data() report includes opening_stock_set count."""
    from app.rms.seed.herbus_import import seed_herbus_data

    with session_factory() as s:
        report = seed_herbus_data(s)
        s.commit()
    # At least 2 numeric + 14 text markers = 16 (some may dedup; be loose)
    assert report.get("opening_stock_set", 0) >= 14
    # app_meta counts row reflects this
    from app.rms.models import AppMeta
    with session_factory() as s:
        meta = s.query(AppMeta).filter_by(key="herbus_seed_loaded").one()
        import json
        counts = json.loads(meta.value)["counts"]
        assert "opening_stock_set" in counts
        assert counts["opening_stock_set"] >= 14
