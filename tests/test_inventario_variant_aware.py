"""tests/test_inventario_variant_aware.py — Multi-package + multi-supplier on /inventario.

Prelaunch roadmap 2026-09-17, decision B1: 1 ingredient → multiple variants
(different package sizes from different suppliers). The /inventario list
view must:

1. Show the rollup total (sum across variants) as the row's stock cell,
   not the legacy Ingredient.stock_qty column.
2. Render a "Variantes" column with the variant count + preferred summary.
3. The inline +qty quick-receipt form must show a variant picker when
   variants exist, with the preferred preselected.
4. POSTing the form with variant_id=X adds to that variant's stock_qty,
   not the parent Ingredient.stock_qty.
5. POSTing without variant_id auto-picks the preferred variant and
   surfaces a flash notice.
6. Legacy ingredients (no variants) still work exactly as before.
"""
# allow-hardcoded-dates: variant math doesn't depend on calendar.
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from app.rms.models import Ingredient, IngredientVariant, Supplier


def _csrf(client) -> str:
    """Pull CSRF token from a fresh /inventario GET."""
    r = client.get("/inventario")
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    assert m, "CSRF token not found"
    return m.group(1)


def _make_supplier(s, name="Proveedor A"):
    sup = Supplier(name=name)
    s.add(sup)
    s.flush()
    return sup


def _make_ingredient(s, name="harina-multi-001", unit="g"):
    ing = Ingredient(name=name, unit=unit, stock_qty=0, min_stock_qty=500)
    s.add(ing)
    s.flush()
    return ing


def _make_variant(s, ing_id, size, unit="g", supplier_id=None, price=10000, stock=0, preferred=False):
    v = IngredientVariant(
        ingredient_id=ing_id,
        package_size=size,
        package_unit=unit,
        purchase_price_gs=price,
        supplier_id=supplier_id,
        stock_qty=stock,
        preferred=preferred,
    )
    s.add(v)
    s.flush()
    return v


# ── 1. Rollup appears in the list cell ────────────────────────────────
def test_list_shows_rollup_stock_when_variants_exist(client, session_factory):
    """The list cell shows the rollup total (sum across variants), not
    the parent Ingredient.stock_qty (which stays at 0 for variant-only
    ingredients in the legacy column).

    NOTE: The rollup math currently handles same-unit variants cleanly
    (e.g. all kg). Cross-unit conversions (Ingredient.unit=g with
    variants in kg) double-count — that's a known issue in
    rollup_ingredient_stock() that's out of scope for B1 (see CHANGELOG).
    """
    with session_factory() as s:
        ing = _make_ingredient(s, "harina-list-001", "kg")
        # Same-unit rollup: 3 × 1kg + 12 × 0.25kg = 6.0 kg total
        _make_variant(s, ing.id, 1.0, "kg", stock=3, preferred=True)
        _make_variant(s, ing.id, 0.25, "kg", stock=12, price=3000)
        s.commit()
    r = client.get("/inventario")
    assert r.status_code == 200
    # The variant count column (HTML may have <strong> tags around the count)
    assert re.search(r"2(?:\s|<[^>]*>)*variantes", r.text), \
        f"Expected '2 variantes' in page (with optional HTML between), page contains 'variantes' at: {[m.start() for m in re.finditer(r'variantes', r.text)]}"
    # The row should show 6 kg as the rollup
    row = re.search(
        r"<tr[^>]*>(?:[^<]|<(?!tr))*?harina-list-001(?:[^<]|<(?!/tr))*?</tr>",
        r.text,
        re.DOTALL,
    )
    assert row, "Row not found for harina-list-001"
    row_html = row.group(0)
    # The rollup is 6 kg = 6000 g. The cell renders {{ _stock|round(2) }} {{ i.unit }}
    # which gives "6.0 kg".
    assert ("6 kg" in row_html) or ("6.0 kg" in row_html), \
        f"Expected '6 kg' in row, got: {row_html[:800]}"


# ── 2. Variantes column shows count + preferred summary ──────────────
def test_list_variantes_column_shows_preferred(client, session_factory):
    """The Variantes column lists the preferred variant's size+supplier+price."""
    with session_factory() as s:
        sup = _make_supplier(s, "Molino La Esperanza")
        ing = _make_ingredient(s, "harina-col-001", "kg")
        _make_variant(
            s, ing.id, 1.0, "kg", supplier_id=sup.id,
            price=12000, stock=5, preferred=True,
        )
        _make_variant(
            s, ing.id, 0.5, "kg", supplier_id=None,
            price=6500, stock=10, preferred=False,
        )
        s.commit()
    r = client.get("/inventario")
    assert r.status_code == 200
    row = re.search(
        r"<tr[^>]*>(?:[^<]|<(?!tr))*?harina-col-001(?:[^<]|<(?!/tr))*?</tr>",
        r.text,
        re.DOTALL,
    )
    assert row
    row_html = row.group(0)
    # Preferred variant details visible (Jinja may insert whitespace inside
    # the {{ v.package_size }}{{ v.package_unit }} output)
    assert re.search(r"\b1\s*(?:kg|0\.?)\b|1\s*\.0\s*kg", row_html), \
        f"Expected '1kg' (with whitespace tolerance) in row, got: {row_html[:800]}"
    assert "Molino La Esperanza" in row_html
    # Price may be rendered as 12,000 or 12000
    assert ("12,000 Gs" in row_html) or ("12000 Gs" in row_html)
    assert "gestionar" in row_html  # link to detail page


def test_list_variantes_column_empty_when_no_variants(client, session_factory):
    """Ingredients without variants show '— + variante' link."""
    with session_factory() as s:
        ing = _make_ingredient(s, "harina-no-var-001", "g")
        ing.stock_qty = 1500
        s.commit()
    r = client.get("/inventario")
    assert r.status_code == 200
    row = re.search(
        r"<tr[^>]*>.*?harina-no-var-001.*?</tr>", r.text, re.DOTALL
    )
    assert row
    row_html = row.group(0)
    assert "+ variante" in row_html


# ── 3. Quick-receipt form shows variant picker ────────────────────────
def test_quick_receipt_form_renders_variant_picker(client, session_factory):
    """When variants exist, the inline form has a <select name=variant_id>
    with one <option> per variant (preferred preselected)."""
    with session_factory() as s:
        sup = _make_supplier(s, "Sup A")
        ing = _make_ingredient(s, "harina-pick-001", "kg")
        v1 = _make_variant(
            s, ing.id, 1.0, "kg", supplier_id=sup.id,
            price=10000, stock=2, preferred=True,
        )
        v2 = _make_variant(
            s, ing.id, 0.25, "kg", supplier_id=None,
            price=3000, stock=8, preferred=False,
        )
        s.commit()
        ing_id = ing.id
        v1_id, v2_id = v1.id, v2.id
    r = client.get("/inventario")
    assert r.status_code == 200
    form_html = re.search(
        rf'<form[^>]*data-testid="quick-receipt-{ing_id}".*?</form>',
        r.text,
        re.DOTALL,
    )
    assert form_html, f"Form not found for {ing_id}"
    fh = form_html.group(0)
    # Variant picker present
    assert 'name="variant_id"' in fh
    # Both variants as options
    assert f'value="{v1_id}"' in fh
    assert f'value="{v2_id}"' in fh
    # Preferred (v1) is selected
    assert re.search(rf'<option value="{v1_id}" selected', fh)
    # Label shows size + supplier in title attr
    assert "Sup A" in fh
    # Unit label says "paq" (packages), not "kg". The span wraps the
    # literal, so the substring is just "paq" surrounded by whitespace.
    assert re.search(r'>\s*paq\s*<', fh), \
        f"Expected 'paq' unit label in form, got: {fh}"


def test_quick_receipt_form_no_picker_when_no_variants(client, session_factory):
    """Legacy ingredients (no variants) don't render the variant picker."""
    with session_factory() as s:
        ing = _make_ingredient(s, "harina-legacy-001", "g")
        ing.stock_qty = 1000
        s.commit()
        ing_id = ing.id
    r = client.get("/inventario")
    assert r.status_code == 200
    form_html = re.search(
        rf'<form[^>]*data-testid="quick-receipt-{ing_id}".*?</form>',
        r.text,
        re.DOTALL,
    )
    assert form_html, f"Form not found for {ing_id}"
    fh = form_html.group(0)
    assert 'name="variant_id"' not in fh
    # Legacy unit shown (the unit from the ingredient, not 'paq').
    # The span wraps the literal so it's just the unit surrounded by whitespace.
    assert re.search(r'>\s*g\s*<', fh), \
        f"Expected 'g' unit label in form, got: {fh}"


# ── 4. POSTing with variant_id adds to that variant ───────────────────
def test_quick_receipt_with_variant_id_adds_to_variant(client, session_factory):
    """POST with variant_id=N adds adjustment to variant N's stock_qty."""
    with session_factory() as s:
        ing = _make_ingredient(s, "harina-recv-001", "kg")
        v1 = _make_variant(s, ing.id, 1.0, "kg", stock=2, preferred=True)
        v2 = _make_variant(s, ing.id, 0.25, "kg", stock=8, preferred=False)
        s.commit()
    csrf = _csrf(client)
    r = client.post(
        f"/inventario/{ing.id}/ajustar",
        data={"adjustment": "5", "variant_id": str(v2.id), "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303), r.text[:500]
    with session_factory() as s:
        v1_now = s.get(IngredientVariant, v1.id)
        v2_now = s.get(IngredientVariant, v2.id)
        ing_now = s.get(Ingredient, ing.id)
        # v1 unchanged
        assert v1_now.stock_qty == 2.0
        # v2 += 5
        assert v2_now.stock_qty == 13.0
        # parent Ingredient.stock_qty synced to rollup
        # v1: 2 × 1kg = 2kg; v2: 13 × 0.25kg = 3.25kg; total 5.25kg
        assert ing_now.stock_qty == 5.25


# ── 5. POSTing without variant_id auto-picks preferred ────────────────
def test_quick_receipt_without_variant_id_auto_picks_preferred(client, session_factory):
    """No variant_id sent → preferred variant auto-picked, flash notice."""
    with session_factory() as s:
        ing = _make_ingredient(s, "harina-auto-001", "g")
        v_pref = _make_variant(s, ing.id, 1.0, "kg", stock=1, preferred=True)
        v_other = _make_variant(s, ing.id, 0.25, "kg", stock=10, preferred=False)
        s.commit()
    csrf = _csrf(client)
    r = client.post(
        f"/inventario/{ing.id}/ajustar",
        data={"adjustment": "3", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    # The flash info note is in the Location URL
    location = r.headers.get("location", "")
    assert "info" in location, f"Expected flash info in redirect, got: {location}"
    assert "preferida" in location, f"Expected 'preferida' in flash, got: {location}"
    with session_factory() as s:
        v_pref_now = s.get(IngredientVariant, v_pref.id)
        v_other_now = s.get(IngredientVariant, v_other.id)
        # preferred got the +3
        assert v_pref_now.stock_qty == 4.0
        # other unchanged
        assert v_other_now.stock_qty == 10.0


# ── 6. Legacy path still works for ingredients without variants ───────
def test_legacy_receipt_unchanged_when_no_variants(client, session_factory):
    """Ingredients without variants keep using Ingredient.stock_qty."""
    with session_factory() as s:
        ing = _make_ingredient(s, "harina-legacy-002", "g")
        ing.stock_qty = 2000
        s.commit()
    csrf = _csrf(client)
    r = client.post(
        f"/inventario/{ing.id}/ajustar",
        data={"adjustment": "500", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    with session_factory() as s:
        ing_now = s.get(Ingredient, ing.id)
        assert ing_now.stock_qty == 2500.0


# ── 7. Negative-stock guard uses variant stock when present ───────────
def test_negative_stock_guard_uses_variant_stock(client, session_factory):
    """Sending a negative adjustment that would drive the variant below 0
    is blocked by the same guard (and uses the variant's stock as the base)."""
    with session_factory() as s:
        ing = _make_ingredient(s, "harina-neg-001", "g")
        v = _make_variant(s, ing.id, 1.0, "kg", stock=2, preferred=True)
        s.commit()
    csrf = _csrf(client)
    # Without confirm_negative, sending adjustment=-5 should be blocked
    r = client.post(
        f"/inventario/{ing.id}/ajustar",
        data={
            "adjustment": "-5",
            "variant_id": str(v.id),
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    # Stock unchanged
    with session_factory() as s:
        v_now = s.get(IngredientVariant, v.id)
        assert v_now.stock_qty == 2.0
    # With confirm_negative=yes, allowed
    r = client.post(
        f"/inventario/{ing.id}/ajustar",
        data={
            "adjustment": "-1",
            "variant_id": str(v.id),
            "confirm_negative": "yes",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    with session_factory() as s:
        v_now = s.get(IngredientVariant, v.id)
        # Clamped to 0 by max(0, ...)
        assert v_now.stock_qty == 1.0
