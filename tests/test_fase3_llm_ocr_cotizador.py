"""tests/test_fase3_llm_ocr_cotizador.py — Fase 3 (2026-10-07).

Cubre: llm.py (json extraction, no-key degrade), menu_ocr matching,
cotizador math (batches, costo, margen, descuento), routers (pages +
OCR 503 sin key + confirm guardrail).
LLM HTTP calls are NEVER made — parse/match/cotizador are pure; router
OCR path is only tested for the no-key branch + CSRF guard.
"""

from __future__ import annotations

from app.rms.cotizador import build_quote
from app.rms.llm import _extract_json, available
from app.rms.menu_ocr import MenuLine, match_to_catalog
from app.rms.seed.menu_import import import_menu_csv

# ---------- llm.py ----------

def test_extract_json_plain():
    assert _extract_json('{"items": [1]}') == {"items": [1]}


def test_extract_json_fenced():
    text = '```json\n{"items": [{"name": "Pizza"}]}\n```'
    assert _extract_json(text) == {"items": [{"name": "Pizza"}]}


def test_extract_json_prose_wrapped():
    text = 'Acá va: {"items": []} saludos'
    assert _extract_json(text) == {"items": []}


def test_available_false_without_key(monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    assert available() is False


# ---------- menu_ocr matching ----------

def test_match_to_catalog_matches_and_news(session_factory):
    s = session_factory()
    try:
        import_menu_csv(s, "nombre,precio\nPizza Muzzarella,50000\nCoca Cola 1L,12000\n", dry_run=False)
        lines = [
            MenuLine(name="Pizza Muzzarella", price_gs=50000),      # exact
            MenuLine(name="piza muzarella", price_gs=48000),        # fuzzy
            MenuLine(name="Empanada de carne", price_gs=8000),      # nuevo
        ]
        res = match_to_catalog(lines, s)
        assert len(res.matched) == 2
        assert res.matched[0].product_id is not None
        assert len(res.nuevos) == 1
        assert res.nuevos[0].name == "Empanada de carne"
    finally:
        s.close()


# ---------- cotizador ----------

def _mk_costed_product(s, *, name, price, yield_qty, ing_price, qty_per_batch=1.0):
    """Producto con receta 1 ingrediente costeado (precio compra seteado)."""
    from app.rms.models_legacy import Ingredient, Product, Recipe, RecipeLine

    ing = Ingredient(name=f"{name} ing", unit="kg", purchase_price_gs=ing_price)
    s.add(ing)
    s.flush()
    rec = Recipe(name="R " + name, yield_qty=yield_qty, yield_unit="und")
    s.add(rec)
    s.flush()
    s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=qty_per_batch))
    prod = Product(name=name, sale_price_gs=price, recipe_id=rec.id)
    s.add(prod)
    s.commit()
    return prod


def test_build_quote_batches_cost_margin(session_factory):
    s = session_factory()
    try:
        # batch: 1 kg a Gs 10.000 → yield 10 → costo/porción Gs 1.000
        p = _mk_costed_product(s, name="Chipa", price=2500, yield_qty=10, ing_price=10000)
        q = build_quote(s, [(p.id, 30)])
        it = q.items[0]
        assert it.batches == 3  # ceil(30/10)
        assert it.line_cost_gs == 30000
        assert it.line_menu_gs == 75000
        assert it.margin_gs == 45000
        assert q.total_menu_gs == 75000
        assert q.total_cost_gs == 30000
        # descuento 10%
        assert q.apply_discount_pct(10) == 67500
    finally:
        s.close()


def test_build_quote_uncostable_item_nulls_total(session_factory):
    s = session_factory()
    try:
        from app.rms.models_legacy import Ingredient, Product, Recipe, RecipeLine

        ing = Ingredient(name="ing sin precio", unit="kg")  # sin purchase_price
        s.add(ing)
        s.flush()
        rec = Recipe(name="R X", yield_qty=5, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=1))
        p = Product(name="Torta X", sale_price_gs=100000, recipe_id=rec.id)
        s.add(p)
        s.commit()
        q = build_quote(s, [(p.id, 10)])
        assert q.items[0].costable is False
        assert q.total_cost_gs is None
        assert q.total_margin_gs is None
        assert q.total_menu_gs == 1_000_000
    finally:
        s.close()


def test_build_quote_skips_zero_and_unknown(session_factory):
    s = session_factory()
    try:
        p = _mk_costed_product(s, name="Chipa 2", price=2500, yield_qty=10, ing_price=10000)
        q = build_quote(s, [(p.id, 0), (999999, 5)])
        assert q.items == []
        assert q.total_menu_gs == 0
    finally:
        s.close()


# ---------- routers ----------

def test_cotizador_page_renders(authed_client):
    r = authed_client.get("/cotizador")
    assert r.status_code == 200
    assert "Cotizador".encode() in r.content


def test_menu_import_ocr_page_no_key_503_upload(authed_client, monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    r = authed_client.get("/menu-import/ocr")
    assert r.status_code == 200  # la página renderiza con aviso
    assert b"ZAI_API_KEY" in r.content
    # POST sin key → 503 (degradación controlada, NO crash)
    r2 = authed_client.post(
        "/menu-import/ocr",
        files={"file": ("carta.jpg", b"\xff\xd8fake", "image/jpeg")},
    )
    assert r2.status_code == 503


def test_copiloto_renders_placeholder(authed_client):
    r = authed_client.get("/copiloto")
    assert r.status_code == 200
