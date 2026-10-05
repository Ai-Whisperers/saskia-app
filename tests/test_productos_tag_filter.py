"""tests/test_productos_tag_filter.py — tag filter chip group functionality."""


def test_productos_tag_filter_chip_group_exists(client):
    """/productos returns 200 and contains tag filter UI elements."""
    response = client.get("/productos")
    assert response.status_code == 200
    body = response.text

    assert "tag-filter-options" in body, "Missing tag filter chip group container"
    assert "tag-chip-group" in body, "Missing tag chip group class"
    assert "Filtrar por etiqueta" in body, "Missing Spanish label for tag filter"


def test_productos_api_returns_tags(client):
    """/productos/api/tags returns tag data."""
    response = client.get("/productos/api/tags")
    assert response.status_code == 200
    data = response.json()
    assert "tags" in data, "Missing tags key in response"


def test_existing_functionality_still_works(client):
    """Regression test - ensure existing filter functionality still works."""
    response = client.get("/productos")
    assert response.status_code == 200
    body = response.text

    # Existing filter patterns must remain
    assert "mf-pop" in body, "Missing existing filter wrapper"
    assert "Estado" in body, "Missing existing estado filter"