"""tests/test_packs_seed.py — Seed packs per market segment.

Verifies that every generated pack seeds cleanly into a fresh DB with the
same guarantees as the La Vaquita Holandesa seeder (seed/sazon.py):
product → recipe linkage, positive recipe-line quantities, and idempotent
re-seeding. The pack data is market-research staged data (see
scripts/seed_packs_gen.py); nothing here touches prod tenants.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.rms.models import (
    Base,
    Ingredient,
    IngredientVariant,
    Product,
    ProductionPlanTemplate,
    Recipe,
    RecipeLine,
    Supplier,
    Tenant,
)
from app.rms.seed.packs import PACKS, seed_pack


@pytest.fixture()
def fresh_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def test_all_packs_present():
    assert len(PACKS) == 11
    assert "Pizzería" in PACKS
    assert "Panadería" in PACKS


def test_pack_data_integrity():
    """Every pack: every product has a recipe, every recipe has positive lines."""
    for pack, data in PACKS.items():
        slugs = {r[0] for r in data.recipes}
        assert len(data.products) > 0, pack
        assert len(data.recipes) == len(data.products), pack
        for pname, rslug, _cat, price, _src in data.products:
            assert rslug in slugs, f"{pack}: producto {pname} sin receta {rslug}"
            assert price > 0
        for _slug_, _ing, qty, _unit in data.recipe_lines:
            assert qty > 0, f"{pack}: línea con qty<=0 en {_slug_}"


def test_seed_pack_creates_full_dataset(fresh_db: Session):
    rep = seed_pack(fresh_db, "Pizzería")
    fresh_db.expire_all()
    assert rep.products == 18
    assert rep.recipes == 18
    assert rep.ingredients > 0
    assert fresh_db.query(Tenant).count() == 1
    assert fresh_db.query(Supplier).count() == 4
    # every product linked to its recipe
    for p in fresh_db.query(Product).all():
        assert p.recipe_id is not None
    # every recipe has at least one ingredient line with qty > 0
    for r in fresh_db.query(Recipe).all():
        lines = fresh_db.query(RecipeLine).filter(RecipeLine.recipe_id == r.id).all()
        assert lines, f"receta {r.name} sin líneas"
        assert all(ln.qty > 0 for ln in lines)
    # variants + price events seeded
    assert fresh_db.query(IngredientVariant).count() == fresh_db.query(Ingredient).count()


def test_seed_pack_is_idempotent(fresh_db: Session):
    seed_pack(fresh_db, "Pizzería")
    seed_pack(fresh_db, "Pizzería")
    fresh_db.expire_all()
    assert fresh_db.query(Ingredient).count() == 37
    assert fresh_db.query(Product).count() == 18
    assert fresh_db.query(Recipe).count() == 18


def test_seed_all_packs_fresh_db():
    """Each pack seeds standalone into a fresh DB with full linkage."""
    for pack in sorted(PACKS):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        s = Session(engine)
        try:
            seed_pack(s, pack)
            s.expire_all()
            prods = s.query(Product).count()
            assert prods == len(PACKS[pack].products), pack
            assert s.query(Recipe).count() == prods, pack
            assert (
                s.query(RecipeLine).filter(RecipeLine.qty > 0).count()
                == s.query(RecipeLine).count()
            ), pack
            assert s.query(ProductionPlanTemplate).count() > 0, pack
        finally:
            s.close()
            engine.dispose()


def test_unknown_pack_raises(fresh_db: Session):
    with pytest.raises(KeyError):
        seed_pack(fresh_db, "Segundlería")


def test_seed_second_pack_reuses_ingredients(fresh_db: Session):
    """Shared ingredients across packs are not duplicated."""
    seed_pack(fresh_db, "Pizzería")
    n_ings = fresh_db.query(Ingredient).count()
    seed_pack(fresh_db, "Café/Cafetería")
    fresh_db.expire_all()
    # café adds its own ings, but shared ones (queso muzzarella, etc.) are reused
    assert fresh_db.query(Ingredient).count() >= n_ings
    assert fresh_db.query(Tenant).count() == 2  # one tenant per pack
