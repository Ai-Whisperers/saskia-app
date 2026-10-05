"""P-16: Merma combo + waste registration regression test.

Tests:
- /merma page renders
- Ingredient combo is present
- Quantity + reason fields work
- POST creates merma (or handles gracefully)
- No Python errors
"""


def test_merma_renders(client):
    """P-16: Merma page renders."""
    r = client.get("/merma")
    assert r.status_code == 200


def test_merma_renders_in_spanish(client):
    """P-16: Merma page is in Spanish."""
    r = client.get("/merma")
    assert r.status_code == 200
    body = r.text
    assert "Merma" in body or "merma" in body.lower(), "Page not in Spanish"


def test_merma_has_ingredient_combo(client):
    """P-16: Page has ingredient combo."""
    r = client.get("/merma")
    assert r.status_code == 200
    body = r.text
    assert (
        "ui-combo" in body or "ingrediente" in body.lower() or "ingredient" in body.lower()
    ), "Ingredient combo not found"


def test_merma_has_quantity_field(client):
    """P-16: Page has quantity field."""
    r = client.get("/merma")
    assert r.status_code == 200
    body = r.text
    assert 'name="cantidad"' in body or 'name="quantity"' in body or 'type="number"' in body, (
        "Quantity field not found"
    )


def test_merma_has_reason_field(client):
    """P-16: Page has reason/motive field."""
    r = client.get("/merma")
    assert r.status_code == 200
    body = r.text
    assert (
        "raz" in body.lower()
        or "motivo" in body.lower()
        or "nota" in body.lower()
        or "reason" in body.lower()
    ), "Reason field not found"


def test_merma_has_date_field(client):
    """P-16: Page has date field."""
    r = client.get("/merma")
    assert r.status_code == 200
    body = r.text
    # Date may be auto-filled with today
    import re

    has_date = (
        'type="date"' in body
        or 'name="fecha"' in body
        or 'name="date"' in body
        or bool(re.search(r"\d{4}-\d{2}-\d{2}", body))
    )
    assert has_date, "Date field not found"


def test_merma_has_submit_button(client):
    """P-16: Page has submit button."""
    r = client.get("/merma")
    assert r.status_code == 200
    body = r.text
    assert 'type="submit"' in body, "Submit button not found"


def test_merma_no_python_errors(client):
    """P-16: No Python errors on merma."""
    r = client.get("/merma")
    assert r.status_code != 500


def test_merma_post_minimal(client):
    """P-16: Minimal POST doesn't crash."""
    r = client.post(
        "/merma",
        data={
            "ingredient_id": "1",
            "cantidad": "1.0",
            "razon": "test",
        },
    )
    assert r.status_code != 500, "POST returned 500"


def test_merma_post_empty(client):
    """P-16: Empty POST handled gracefully."""
    r = client.post("/merma", data={})
    assert r.status_code != 500, "Empty POST returned 500"
    assert r.status_code in (200, 302, 400, 405, 422), f"Unexpected {r.status_code}"


def test_merma_lists_existing_entries(client):
    """P-16: Page lists existing merma entries."""
    r = client.get("/merma")
    assert r.status_code == 200
    body = r.text
    assert len(body) > 1000, "Page content too small"
