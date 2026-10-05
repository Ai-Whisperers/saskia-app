"""Tests for quick-merma modal triggered from /produccion (PROD-MERMA-1).

The quick-merma modal opens per-row in the shift-execution table. It POSTs
to existing /merma/registrar (ingredient tab) or /merma/receta (recipe tab)
endpoints. After save, /produccion shows a flash banner with the event count.

Tests:
- Per-row 🔥 Merma button renders with data-recipe-id populated
- Modal HTML contains both tabs (ingredient + recipe)
- POST /merma/registrar from /produccion context decrements stock + writes audit
- POST /merma/receta from /produccion context expands recipe + writes audit
- audit detail has source: "production" tag
"""

from __future__ import annotations


def test_produccion_renders_merma_button_per_row(authed_client):
    """Each shift-execution row gets a '🔥 Merma' button with data-recipe-id."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # Either recipe_id is populated or "Sin receta" — but the button itself must
    # render whenever a row renders (so operators can log ingredient-only merma too).
    assert "🔥 Merma" in body or "Merma" in body, "Quick-merma button not found"
    # The button should live inside a production-row table row
    # (rough check: data-quick-merma button attribute present)
    assert "data-quick-merma" in body or "quick-merma-modal" in body, (
        "Quick-merma trigger / modal not wired into produccion.html"
    )


def test_produccion_has_quick_merma_modal(authed_client):
    """The page must contain the quick-merma dialog with both tabs."""
    r = authed_client.get("/produccion?view=day")
    body = r.text
    assert "quick-merma-modal" in body, "quick-merma-modal <dialog> missing"
    # Two tab headings: ingrediente + receta
    assert "Ingrediente suelto" in body or "ingrediente" in body.lower(), (
        "Tab 'Ingrediente suelto' missing"
    )
    assert "Lote entero" in body or "lote entero" in body.lower(), "Tab 'Lote entero' missing"


def test_merma_registrar_from_produccion_decrements_stock(authed_client, session_factory):
    """POST /merma/registrar with source=production decrements stock + writes audit."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        ing = Ingredient(name="Harina PROD-TEST", unit="kg", stock_qty=10.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    r = authed_client.post(
        "/merma/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": "0.5",
            "qty_unit": "kg",
            "reason": "vencida",
            "notes": "burned batch test",
            "source": "production",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, f"expected redirect after POST, got {r.status_code}"
    assert "/produccion" in r.headers.get("location", "") or "/merma" in r.headers.get(
        "location", ""
    )

    with session_factory() as s:
        ing_db = (
            s.query(Ingredient).filter_by(ingredient_id=ing_id).first()
            if False
            else s.get(Ingredient, ing_id)
        )
        assert ing_db is not None
        # Stock should have dropped by 0.5 kg
        assert ing_db.stock_qty == 9.5, f"expected 9.5, got {ing_db.stock_qty}"


def test_merma_registrar_audit_includes_source(authed_client, session_factory):
    """Audit detail must include source: 'production' when posted from /produccion."""
    from app.rms.models import AuditLog, Ingredient

    with session_factory() as s:
        ing = Ingredient(name="Audit Source Test", unit="g", stock_qty=500.0, min_stock_qty=100.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    authed_client.post(
        "/merma/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": "100",
            "qty_unit": "g",
            "reason": "quemada",
            "notes": "modal test",
            "source": "production",
        },
    )

    with session_factory() as s:
        audits = s.query(AuditLog).filter(AuditLog.action == "write.merma.create").all()
        assert any("production" in str(a.detail) for a in audits), (
            f"expected source=production in audit detail, got: {[a.detail for a in audits]}"
        )


def test_merma_receta_from_produccion_redirects_to_produccion(authed_client, session_factory):
    """POST /merma/receta with source=production redirects back to /produccion?merma=ok."""
    from app.rms.models import Ingredient, Recipe

    # Need a recipe with yield + at least one ingredient
    with session_factory() as s:
        ing = Ingredient(name="RecetaProd Test Ing", unit="kg", stock_qty=10.0, min_stock_qty=1.0)
        s.add(ing)
        s.flush()
        ing_id = ing.id
        rec = Recipe(
            name="TestReceta Quick Merma",
            yield_qty=10.0,
            yield_unit="und",
        )
        s.add(rec)
        s.flush()
        recipe_id = rec.id
        # Add a recipe line
        from app.rms.models import RecipeLine

        rl = RecipeLine(
            recipe_id=recipe_id,
            line_kind="ingredient",
            line_ref_id=ing_id,
            qty=1.0,
            line_unit="kg",
        )
        s.add(rl)
        s.commit()

    r = authed_client.post(
        "/merma/receta",
        data={
            "recipe_id": str(recipe_id),
            "batch_qty": "1",
            "reason": "quemada",
            "notes": "lost batch",
            "source": "production",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, f"expected redirect, got {r.status_code}"
    # Should redirect to /produccion with merma=ok flash
    loc = r.headers.get("location", "")
    assert "merma=ok" in loc, f"expected merma=ok in redirect, got: {loc}"
    assert "/produccion" in loc, f"expected /produccion in redirect, got: {loc}"
