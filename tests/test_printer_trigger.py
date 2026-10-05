"""tests/test_printer_trigger.py — auto-fire printer on sale create.

After every successful sale, the system should attempt to send a
receipt to the configured printer. Failures are logged but do NOT
block the sale (the printer is operational, not transactional).
"""

from __future__ import annotations


def test_sale_creation_triggers_printer(client, session_factory, monkeypatch):
    """Successful POST /ventas/nueva fires the printer."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="Printer_flour", unit="kg", stock_qty=10, purchase_price_gs=5000)
        s.add(ing)
        s.flush()
        recipe = Recipe(name="PrinterRecipe", yield_qty=10, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add(RecipeLine(recipe_id=recipe.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.1))
        p = Product(name="PrintProd", sale_price_gs=5000, sku="PRN-001", recipe_id=recipe.id)
        s.add(p)
        s.commit()
        pid = p.id

    # Patch send_to_printer to record calls
    calls = []

    def fake_send(payload, config):
        calls.append((payload, config))
        return {"sent": True, "sink": "test"}

    # Patch the symbol at the source module path (where the
    # _fire_printer_for_sale helper imports it from).
    monkeypatch.setattr("app.integrations.printer.send_to_printer", fake_send)

    resp = client.post(
        "/ventas/nueva",
        data={"product_id": str(pid), "qty": "1", "discount_gs": "0"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert len(calls) == 1, f"Expected 1 printer call, got {len(calls)}"


def test_sale_failure_does_not_trigger_printer(client, monkeypatch):
    """Failed POST (validation) does NOT fire the printer."""
    calls = []

    def fake_send(payload, config):
        calls.append(payload)
        return {"sent": True}

    monkeypatch.setattr("app.integrations.printer.send_to_printer", fake_send)

    # Missing product_id → 422
    resp = client.post(
        "/ventas/nueva",
        data={"qty": "1", "discount_gs": "0"},
    )
    assert resp.status_code == 400
    assert len(calls) == 0


def test_printer_failure_does_not_break_sale(client, session_factory, monkeypatch):
    """If the printer fails, the sale still completes."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="PrintFail_flour", unit="kg", stock_qty=10, purchase_price_gs=5000)
        s.add(ing)
        s.flush()
        recipe = Recipe(name="PrintFail_recipe", yield_qty=10, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add(RecipeLine(recipe_id=recipe.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.1))
        p = Product(name="PrintFail", sale_price_gs=5000, sku="FAIL-001", recipe_id=recipe.id)
        s.add(p)
        s.commit()
        pid = p.id

    def fake_fail(payload, config):
        raise RuntimeError("Printer offline")

    monkeypatch.setattr("app.integrations.printer.send_to_printer", fake_fail)

    resp = client.post(
        "/ventas/nueva",
        data={"product_id": str(pid), "qty": "1", "discount_gs": "0"},
        follow_redirects=False,
    )
    # Sale should still succeed (printer error is best-effort)
    assert resp.status_code == 303
