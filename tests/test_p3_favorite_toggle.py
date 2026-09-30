"""P3: ⭐ favorite toggle on /productos (POST /productos/{id}/favorito).

Favorites pin products to the ventas POS quick-sell grid (see
test_p3_delivery_addresses.py). This adds the UI toggle.
"""

from __future__ import annotations

from tests.factories import make_product


def test_favorito_toggle_on(client, session_factory):
    with session_factory() as s:
        p = make_product(s, name="FavToggle UX")
        s.commit()
        pid = p.id
    r = client.post(f"/productos/{pid}/favorito", follow_redirects=False)
    assert r.status_code == 303, r.status_code
    from app.rms.models import Product
    with session_factory() as s:
        assert s.get(Product, pid).is_favorite is True


def test_favorito_toggle_off(client, session_factory):
    with session_factory() as s:
        p = make_product(s, name="FavToggleOff UX")
        p.is_favorite = True
        s.commit()
        pid = p.id
    r = client.post(f"/productos/{pid}/favorito", follow_redirects=False)
    assert r.status_code == 303
    from app.rms.models import Product
    with session_factory() as s:
        assert s.get(Product, pid).is_favorite is False


def test_favorito_unknown_product_404(client):
    r = client.post("/productos/999999/favorito", follow_redirects=False)
    assert r.status_code == 404


def test_productos_renders_star_button(client, session_factory):
    with session_factory() as s:
        fav = make_product(s, name="StarFav UX")
        fav.is_favorite = True
        plain = make_product(s, name="StarPlain UX")
        s.commit()
    r = client.get("/productos?q=Star")  # narrow to seeded rows (list is paginated)
    assert r.status_code == 200
    body = r.text
    assert "fav-star" in body
    assert "is-fav" in body          # the favorite one is highlighted
    assert f"/productos/{fav.id}/favorito" in body
    assert f"/productos/{plain.id}/favorito" in body
    assert "aria-pressed" in body
