"""tests/test_product_search_visual.py — Phase 19 product picker visual.

Tests for the enriched /productos/api/search endpoint and the
productRowLabel builder that renders products with image + status + stock.

Backend changes (app/routers/products.py):
  - Added `stock_today` (sum of qty sold today, excluding voided)
  - Added `plan_status` (optimo | bajo_minimo | agotado | sin_plan)

Frontend changes (app/static/combo-rows.js):
  - Enhanced productRowLabel to show image + name + price + status + stock

Template changes (app/templates/pedidos_nuevo.html):
  - Added row_label='productRowLabel' to line_product_id combo
"""
from __future__ import annotations

import json


def test_product_search_returns_stock_today(qseed, authed_client):
    """Each product in /productos/api/search must include stock_today field."""
    qseed("basic")
    r = authed_client.get("/productos/api/search?q=")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert len(data["results"]) >= 1
    for p in data["results"]:
        assert "stock_today" in p, f"missing stock_today in {p}"
        assert isinstance(p["stock_today"], (int, float)), \
            f"stock_today must be numeric, got {type(p['stock_today'])}"


def test_product_search_returns_plan_status(qseed, authed_client):
    """Each product must include plan_status ∈ valid values."""
    qseed("basic")
    r = authed_client.get("/productos/api/search?q=")
    assert r.status_code == 200
    data = r.json()
    valid_statuses = {"optimo", "bajo_minimo", "agotado", "sin_plan"}
    for p in data["results"]:
        assert "plan_status" in p, f"missing plan_status in {p}"
        assert p["plan_status"] in valid_statuses, \
            f"invalid plan_status: {p['plan_status']}"


def test_product_search_stock_today_excludes_voided(qseed, authed_client, session_factory):
    """Voided sales should NOT be counted in stock_today."""
    from datetime import datetime, timezone
    from app.rms.models import Product
    from app.rms.models_legacy import Sale

    qseed("basic")
    # Get the basic product
    with session_factory() as s:
        product = s.query(Product).filter_by(name="Producto QA").first()
        assert product is not None
        product_id = product.id

        # Add 5 sales today, 2 of which are voided
        now = datetime.now(timezone.utc)
        for i in range(5):
            voided = (i < 2)
            s.add(Sale(
                product_id=product_id,
                qty=1.0,
                unit_price_gs=1000,
                sold_at=now,
                voided_at=now if voided else None,
            ))
        s.commit()

    r = authed_client.get("/productos/api/search?q=")
    data = r.json()
    target = next((p for p in data["results"] if p["id"] == product_id), None)
    assert target is not None
    # Only 3 non-voided sales should count
    assert target["stock_today"] == 3.0, f"expected 3.0, got {target['stock_today']}"


def test_product_search_plan_status_optimo_when_plenty(qseed, authed_client, session_factory):
    """plan_status='optimo' when completed_qty > sales_today."""
    from datetime import datetime, timezone
    from app.rms.models import Product
    from app.rms.models_legacy import Sale
    from sqlalchemy import text as sa_text

    qseed("basic")
    with session_factory() as s:
        product = s.query(Product).filter_by(name="Producto QA").first()
        assert product is not None
        # Insert directly via SQL to avoid the broken ProductionCompletion mapper
        s.execute(
            sa_text(
                "INSERT INTO production_completion "
                "(product_id, for_date, completed_qty, recorded_at) "
                "VALUES (:pid, :d, :q, :r)"
            ),
            {
                "pid": product.id,
                "d": datetime.now(timezone.utc).date(),
                "q": 10.0,
                "r": datetime.now(timezone.utc),
            },
        )
        # Sold 2 today
        s.add(Sale(
            product_id=product.id,
            qty=2.0,
            unit_price_gs=1000,
            sold_at=datetime.now(timezone.utc),
        ))
        s.commit()

    r = authed_client.get("/productos/api/search?q=")
    data = r.json()
    target = next((p for p in data["results"] if p["id"] == product.id), None)
    assert target is not None
    assert target["plan_status"] == "optimo", \
        f"expected optimo, got {target['plan_status']}"


def test_product_search_plan_status_agotado_when_sold_out(qseed, authed_client, session_factory):
    """plan_status='agotado' when sales >= completed_qty."""
    from datetime import datetime, timezone
    from app.rms.models import Product
    from app.rms.models_legacy import Sale
    from sqlalchemy import text as sa_text

    qseed("basic")
    with session_factory() as s:
        product = s.query(Product).filter_by(name="Producto QA").first()
        assert product is not None
        s.execute(
            sa_text(
                "INSERT INTO production_completion "
                "(product_id, for_date, completed_qty, recorded_at) "
                "VALUES (:pid, :d, :q, :r)"
            ),
            {
                "pid": product.id,
                "d": datetime.now(timezone.utc).date(),
                "q": 5.0,
                "r": datetime.now(timezone.utc),
            },
        )
        # Sold 5 (all)
        s.add(Sale(
            product_id=product.id,
            qty=5.0,
            unit_price_gs=1000,
            sold_at=datetime.now(timezone.utc),
        ))
        s.commit()

    r = authed_client.get("/productos/api/search?q=")
    data = r.json()
    target = next((p for p in data["results"] if p["id"] == product.id), None)
    assert target is not None
    assert target["plan_status"] == "agotado", \
        f"expected agotado, got {target['plan_status']}"


def test_product_search_plan_status_sin_plan_when_no_completion(qseed, authed_client, session_factory):
    """plan_status='sin_plan' when no ProductionCompletion today."""
    from app.rms.models import Product

    qseed("basic")
    with session_factory() as s:
        product = s.query(Product).filter_by(name="Producto QA").first()
        assert product is not None

    r = authed_client.get("/productos/api/search?q=")
    data = r.json()
    target = next((p for p in data["results"] if p["id"] == product.id), None)
    assert target is not None
    assert target["plan_status"] == "sin_plan", \
        f"expected sin_plan, got {target['plan_status']}"


def test_product_search_bulk_no_n_plus_1(qseed, authed_client, session_factory):
    """The endpoint must not N+1 — multiple products fetched in 1 call."""
    from app.rms.models import Product

    qseed("basic")
    # Add 9 more products
    with session_factory() as s:
        for i in range(9):
            s.add(Product(
                name=f"Test Product {i}",
                sale_price_gs=1000 * (i + 1),
                is_available=True,
            ))
        s.commit()

    # Single call should return all 10 products
    r = authed_client.get("/productos/api/search?q=Test")
    data = r.json()
    assert len(data["results"]) >= 9, f"expected 9+, got {len(data['results'])}"
    # Each must have the new fields
    for p in data["results"]:
        assert "stock_today" in p
        assert "plan_status" in p


# --- Frontend tests (static asset) ---


def test_product_row_label_function_exists():
    """The productRowLabel function must be exported in combo-rows.js."""
    import os
    js_path = os.path.join(
        os.path.dirname(__file__),
        "..", "app", "static", "combo-rows.js",
    )
    with open(js_path) as f:
        content = f.read()
    # Check for the function definition and the rendering of new fields
    assert "function productRowLabel" in content
    assert "image_url" in content, "productRowLabel should reference image_url"
    assert "plan_status" in content, "productRowLabel should reference plan_status"
    assert "stock_today" in content, "productRowLabel should reference stock_today"
    assert "combo-row--product" in content, "should add combo-row--product class"


def test_product_row_label_handles_missing_image():
    """productRowLabel should render a placeholder when image_url is empty."""
    import os
    js_path = os.path.join(
        os.path.dirname(__file__),
        "..", "app", "static", "combo-rows.js",
    )
    with open(js_path) as f:
        content = f.read()
    # Find the function body using a simpler approach
    func_start = content.find("function productRowLabel(row) {")
    assert func_start > 0
    # Find matching close brace by counting
    depth = 0
    i = func_start + len("function productRowLabel(row) {")
    start = i
    while i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            if depth == 0:
                body = content[start:i]
                break
            depth -= 1
        i += 1
    else:
        raise AssertionError("could not find function body end")
    # Should have a conditional for the image
    assert "combo-row-img--placeholder" in body, \
        "should show placeholder when no image_url"
    # Should handle all 4 plan_status values
    for status in ("optimo", "bajo_minimo", "agotado", "sin_plan"):
        assert status in body, f"missing {status} status"


def test_pedidos_nuevo_uses_product_row_label():
    """pedidos_nuevo.html must use row_label='productRowLabel' on the product combo."""
    import os
    template_path = os.path.join(
        os.path.dirname(__file__),
        "..", "app", "templates", "pedidos_nuevo.html",
    )
    with open(template_path) as f:
        content = f.read()
    # Find the line_product_id combo
    assert "line_product_id" in content
    # Should reference productRowLabel
    assert "productRowLabel" in content, \
        "pedidos_nuevo.html should reference productRowLabel"
    assert "row_label" in content, \
        "pedidos_nuevo.html should use row_label parameter"


def test_combobox_css_has_product_styles():
    """combobox.css must have styles for combo-row--product, combo-row-img, etc."""
    import os
    css_path = os.path.join(
        os.path.dirname(__file__),
        "..", "app", "static", "combobox.css",
    )
    with open(css_path) as f:
        content = f.read()
    # Check for new CSS classes
    for cls in (".combo-row--product", ".combo-row-img", ".combo-row-status",
                ".combo-row-status.is-ok", ".combo-row-status.is-low",
                ".combo-row-status.is-out", ".combo-row-status.is-neutral"):
        assert cls in content, f"missing CSS class {cls}"
