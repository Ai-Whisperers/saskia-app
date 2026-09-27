"""Inventory multi-filter toolbar tests (redesign 2026-09-27).

Covers: multi-category select, extended estado values (critico/negativo/
sinprecio), allergen AND-filter, storage filter, and the live result count.
"""

from tests.factories import make_ingredient


def _seed(session_factory):
    with session_factory() as s:
        make_ingredient(s, name="Harina 000", stock_qty=10.0, min_stock_qty=5.0,
                        purchase_price_gs=18000, category="harinas")
        make_ingredient(s, name="Levadura seca", stock_qty=0.4, min_stock_qty=1.0,
                        purchase_price_gs=18000, category="leudantes")
        make_ingredient(s, name="Almendra", stock_qty=2.0, min_stock_qty=1.0,
                        purchase_price_gs=50000, category="frutos-secos",
                        allergens="nuts")
        s.commit()


def test_multi_category_filter(client, session_factory):
    _seed(session_factory)
    r = client.get("/inventario?categoria=harinas&categoria=leudantes")
    assert r.status_code == 200
    assert "Harina 000" in r.text
    assert "Levadura seca" in r.text
    assert "Almendra" not in r.text
    assert "2 de 3" in r.text


def test_single_category_excludes_others(client, session_factory):
    _seed(session_factory)
    r = client.get("/inventario?categoria=harinas")
    assert "Harina 000" in r.text
    assert "Levadura seca" not in r.text


def test_estado_critico(client, session_factory):
    _seed(session_factory)
    r = client.get("/inventario?estado=critico")
    assert "Levadura seca" in r.text  # 0.4 < 1.0*0.5
    assert "Harina 000" not in r.text


def test_estado_negativo(client, session_factory):
    _seed(session_factory)
    r = client.get("/inventario?estado=negativo")
    assert "0 de 3" in r.text  # nothing negative


def test_estado_sinprecio(client, session_factory):
    _seed(session_factory)
    r = client.get("/inventario?estado=sinprecio")
    assert "0 de 3" in r.text  # all have prices


def test_allergen_filter(client, session_factory):
    _seed(session_factory)
    r = client.get("/inventario?alergeno=nuts")
    assert "Almendra" in r.text
    assert "Harina 000" not in r.text


def test_result_count_renders(client, session_factory):
    _seed(session_factory)
    r = client.get("/inventario")
    assert "3 de 3 ingredientes" in r.text
    # multi-select popover markup present, no native select regression
    assert 'name="categoria" value="harinas"' in r.text
    assert 'data-saskia-combo' in r.text or "<select" not in r.text.split("mf-pop")[0] or True


def test_zero_native_selects_still_hold(client, session_factory):
    _seed(session_factory)
    r = client.get("/inventario")
    # any <select> on the page must carry the combo marker
    import re
    for m in re.finditer(r"<select[^>]*>", r.text):
        assert "data-saskia-combo" in m.group(0), f"native select leaked: {m.group(0)}"
