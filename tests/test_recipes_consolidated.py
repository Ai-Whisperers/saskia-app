"""UI-V2 Sprint tests: allergy fix-at-source links + consolidated recipe view.

Covers:
  - TagDerivation.undeclared_ids parallels undeclared names (fix-at-source).
  - explode_recipe(): sub-recipe explosion, duplicate summing, unit
    normalization, cycle guard, missing-yield error rows.
"""

from __future__ import annotations

import pytest

# ───────────────────────── helpers ─────────────────────────

def _mk_ingredient(session, name: str, unit: str = "g", allergens=None, **kw):
    from app.rms.models import Ingredient

    ing = Ingredient(name=name, unit=unit, allergens=allergens, **kw)
    session.add(ing)
    session.flush()
    return ing


def _mk_recipe(session, name: str, yield_qty: float, yield_unit: str = "und"):
    from app.rms.models import Recipe

    r = Recipe(name=name, yield_qty=yield_qty, yield_unit=yield_unit)
    session.add(r)
    session.flush()
    return r


def _mk_line(session, recipe_id: int, kind: str, ref_id: int, qty: float, line_unit: str = ""):
    from app.rms.models import RecipeLine

    ln = RecipeLine(
        recipe_id=recipe_id, line_kind=kind, line_ref_id=ref_id,
        qty=qty, line_unit=line_unit,
    )
    session.add(ln)
    session.flush()
    return ln


# ───────────────────────── fix-at-source ─────────────────────────

def test_derivation_includes_undeclared_ids(session_factory):
    """undeclared_ids runs parallel to undeclared names."""
    from app.rms.tagging.derive import derive_recipe_tags

    with session_factory() as session:
        harina = _mk_ingredient(session, "Harina 000", "g", allergens="gluten")
        azucar = _mk_ingredient(session, "Azúcar", "g", allergens=None)
        r = _mk_recipe(session, "Masabase", 10)
        _mk_line(session, r.id, "ingredient", harina.id, 500, "g")
        _mk_line(session, r.id, "ingredient", azucar.id, 100, "g")
        session.commit()

        d = derive_recipe_tags(session, r.id)
        assert d.undeclared == ["Azúcar"]
        assert d.undeclared_ids == [azucar.id]
        # Parallel lengths even with several undeclared
        canela = _mk_ingredient(session, "Canela", "g", allergens=None)
        _mk_line(session, r.id, "ingredient", canela.id, 5, "g")
        session.flush()
        d2 = derive_recipe_tags(session, r.id)
        assert len(d2.undeclared) == len(d2.undeclared_ids) == 2


def test_derivation_no_undeclared_when_all_declared(session_factory):
    from app.rms.tagging.derive import derive_recipe_tags

    with session_factory() as session:
        harina = _mk_ingredient(session, "Harina 000", "g", allergens="gluten")
        r = _mk_recipe(session, "SoloHarina", 1)
        _mk_line(session, r.id, "ingredient", harina.id, 500, "g")

        d = derive_recipe_tags(session, r.id)
        assert d.undeclared == []
        assert d.undeclared_ids == []


# ───────────────────────── explode_recipe ─────────────────────────

def test_explode_sums_duplicates_across_base_and_subrecipe(session_factory):
    """Azúcar in both the base and the glaseado consolidates into one row."""
    from app.rms.recipes_consolidated import explode_recipe

    with session_factory() as session:
        # Glaseado: 200 g azúcar + 100 g queso, yields 300 g
        azucar = _mk_ingredient(session, "Azúcar", "g", allergens=None)
        queso = _mk_ingredient(session, "Qeso crema", "g", allergens="lacteos")
        glaseado = _mk_recipe(session, "Glaseado", 300, "g")
        _mk_line(session, glaseado.id, "ingredient", azucar.id, 200, "g")
        _mk_line(session, glaseado.id, "ingredient", queso.id, 100, "g")

        # Base carrot cake: 250 g azúcar + 300 g zanahoria + 150 g glaseado
        zanahoria = _mk_ingredient(session, "Zanahoria", "g")
        cake = _mk_recipe(session, "Carrot Cake", 1, "und")
        _mk_line(session, cake.id, "ingredient", azucar.id, 250, "g")
        _mk_line(session, cake.id, "ingredient", zanahoria.id, 300, "g")
        _mk_line(session, cake.id, "sub_recipe", glaseado.id, 150, "g")

        rows = explode_recipe(session, cake.id)
        by_name = {r.name: r for r in rows}

        # Azúcar: 250 (base) + (150/300)*200 = 250 + 100 = 350
        assert by_name["Azúcar"].qty == pytest.approx(350.0)
        assert by_name["Azúcar"].unit == "g"
        # Sub-recipe traceability
        assert "Glaseado" in by_name["Azúcar"].sources
        # Queso only from sub-recipe: (150/300)*100 = 50
        assert by_name["Qeso crema"].qty == pytest.approx(50.0)
        # No sub-recipe rows in the output — everything is raw ingredients
        assert all("Glaseado" != r.name for r in rows)


def test_explode_respects_line_unit_conversion(session_factory):
    """Line typed in kg converts into the ingredient's g unit."""
    from app.rms.recipes_consolidated import explode_recipe

    with session_factory() as session:
        azucar = _mk_ingredient(session, "Azúcar kg", "g")
        r = _mk_recipe(session, "Conversion", 1)
        _mk_line(session, r.id, "ingredient", azucar.id, 0.5, "kg")

        rows = explode_recipe(session, r.id)
        assert rows[0].qty == pytest.approx(500.0)
        assert rows[0].unit == "g"


def test_explode_scale_multiplies_root_batch(session_factory):
    from app.rms.recipes_consolidated import explode_recipe

    with session_factory() as session:
        harina = _mk_ingredient(session, "Harina scale", "g")
        r = _mk_recipe(session, "Pan scale", 2, "und")
        _mk_line(session, r.id, "ingredient", harina.id, 1000, "g")

        rows = explode_recipe(session, r.id, scale=2.0)
        assert rows[0].qty == pytest.approx(2000.0)


def test_explode_flags_missing_subrecipe_yield(session_factory):
    from app.rms.recipes_consolidated import explode_recipe

    with session_factory() as session:
        azucar = _mk_ingredient(session, "Azúcar ny", "g")
        sub = _mk_recipe(session, "Sub sin rendimiento", None)
        _mk_line(session, sub.id, "ingredient", azucar.id, 100, "g")
        base = _mk_recipe(session, "Base con sub rota", 1)
        _mk_line(session, base.id, "sub_recipe", sub.id, 50, "g")

        rows = explode_recipe(session, base.id)
        assert any("rendimiento" in (r.error or "") for r in rows)


def test_explode_cycle_guard(session_factory):
    """A→B→A cycle terminates and surfaces an error row instead of hanging."""
    from app.rms.recipes_consolidated import explode_recipe

    with session_factory() as session:
        a_ing = _mk_ingredient(session, "Ing A", "g")
        ra = _mk_recipe(session, "Ciclo A", 100, "g")
        rb = _mk_recipe(session, "Ciclo B", 100, "g")
        _mk_line(session, ra.id, "sub_recipe", rb.id, 50, "g")
        _mk_line(session, rb.id, "sub_recipe", ra.id, 50, "g")
        _mk_line(session, rb.id, "ingredient", a_ing.id, 30, "g")

        rows = explode_recipe(session, ra.id)  # must not recurse forever
        # Ing A still appears (30g * 50/100 = 15 from B) and a cycle error row exists
        by_name = {r.name: r for r in rows}
        assert by_name["Ing A"].qty == pytest.approx(15.0)
        assert any("ciclo" in (r.error or "") for r in rows)


# ───────────────────────── route integration ─────────────────────────

def _seed_recipe_tree(session_factory):
    """Seed azúcar+glaseado carrot cake; returns (recipe_id, azucar_id)."""
    with session_factory() as session:
        azucar = _mk_ingredient(session, "Azúcar RT", "g", allergens=None)
        queso = _mk_ingredient(session, "Qeso crema RT", "g", allergens="lacteos")
        glaseado = _mk_recipe(session, "Glaseado RT", 300, "g")
        _mk_line(session, glaseado.id, "ingredient", azucar.id, 200, "g")
        _mk_line(session, glaseado.id, "ingredient", queso.id, 100, "g")
        cake = _mk_recipe(session, "Carrot Cake RT", 1, "und")
        _mk_line(session, cake.id, "ingredient", azucar.id, 250, "g")
        _mk_line(session, cake.id, "sub_recipe", glaseado.id, 150, "g")
        session.commit()
        return cake.id, azucar.id


def test_recipe_detail_consolidada_view_renders(client, session_factory):
    """?vista=consolidada renders the exploded list; default is estructural."""
    r_id, _azucar_id = _seed_recipe_tree(session_factory)

    resp = client.get(f"/recetas/{r_id}?vista=consolidada")
    assert resp.status_code == 200
    body = resp.text
    # Toggle present with both modes
    assert "Vista Estructural" in body
    assert "Vista Consolidada" in body
    # Consolidada heading + exploded azúcar total (250 + 100 = 350)
    assert "Ingredientes consolidados" in body
    assert "350.00" in body

    resp2 = client.get(f"/recetas/{r_id}")
    assert resp2.status_code == 200
    # Default mode: assembly table with sub-recipe as a single line
    assert "Ingredientes y sub-recetas" in resp2.text
    assert "Sub-receta" in resp2.text


def test_recipe_detail_undeclared_warning_links_to_edit(client, session_factory):
    """Warning renders a link to /inventario/{id}/editar per undeclared item."""
    r_id, azucar_id = _seed_recipe_tree(session_factory)

    resp = client.get(f"/recetas/{r_id}")
    assert resp.status_code == 200
    # Azúcar RT has allergens=None → warning with fix-at-source link
    assert "Sin alérgenos declarados" in resp.text
    assert f'/inventario/{azucar_id}/editar' in resp.text
    assert "/inventario/None" not in resp.text
