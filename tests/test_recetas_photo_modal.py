"""Tests for US 1.1: Recipe photos must hide behind a button, open in a modal.

The second review flagged that recipe photos were a 60x60 thumbnail always
visible in the /recetas table — visual noise. The fix: replace the inline
<img> with a button that opens a native <dialog> modal showing the full
photo on click. This keeps the list clean and matches the product form
pattern (image behind a control, modal on demand).

Acceptance criteria (from docs/operations/2026-09-23-second-review-stories-2.md
US 1.1):
- Recipe list shows a button per row that has a photo (not an inline image)
- Recipe list rows without a photo show a dash placeholder
- The button opens a modal with the full image
- The modal has a close button + aria-label
- The modal empties its <img src> when closed (no stale image leak)
"""

import pytest
from sqlalchemy import select


@pytest.fixture
def recipes_with_and_without_photos(session_factory):
    """Seed two recipes: one WITH image_url, one WITHOUT.

    Round-trip verified before returning so test failures get a clear
    'seed didn't persist' error rather than a confusing template diff.
    """
    from app.rms.models import Recipe

    sf = session_factory
    with sf() as s:
        s.add(
            Recipe(
                name="Brownie con foto",
                yield_qty=12,
                yield_unit="und",
                image_url="/static/recipes/brownie.jpg",
            )
        )
        s.add(Recipe(name="Galleta sin foto", yield_qty=24, yield_unit="und", image_url=None))
        s.commit()
    # Verify image_url really persisted (catches the "_decorate drops it" bug)
    with sf() as s:
        rows = s.execute(select(Recipe).order_by(Recipe.name)).scalars().all()
        names = {r.name: r.image_url for r in rows}
        assert names.get("Brownie con foto") == "/static/recipes/brownie.jpg", (
            f"image_url didn't persist in seed: {names}"
        )
    return sf


def test_recetas_list_no_inline_image_tag(authed_client):
    """Recipe list must NOT contain the old 60x60 inline <img> thumbnail.

    No recipe data needed — the inline 60x60 style was hardcoded in
    the template, so its absence is a template-only check.
    """
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    assert "width:60px;height:60px" not in body, (
        "Inline 60x60 thumbnail still in /recetas. Image must be hidden "
        "behind a button that opens a modal."
    )


def test_recetas_modal_is_present(authed_client):
    """The recipe-photo modal scaffold is rendered on every /recetas page."""
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    assert '<dialog id="recipe-photo-modal"' in body
    assert 'aria-modal="true"' in body
    assert 'aria-labelledby="recipe-photo-title"' in body
    assert 'id="recipe-photo-close"' in body
    assert 'aria-label="Cerrar"' in body


def test_recetas_modal_script_resets_src_on_close(authed_client):
    """The modal JS must reset img.src on close (memory hygiene)."""
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    assert "img.src = ''" in body, (
        "Modal script must reset <img src> on close to avoid stale image leak"
    )
    assert "modal.showModal()" in body
    assert "modal.close()" in body
    assert "e.target === modal" in body
    assert "data-recipe-photo" in body
    assert "querySelectorAll('[data-recipe-photo]')" in body


def test_recetas_template_no_legacy_image_inline(authed_client):
    """The legacy `<img ... style="width:60px;height:60px...">` must be gone."""
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    assert "object-fit:cover;border-radius:6px" not in body


def test_recetas_with_photo_row_renders_button(authed_client, recipes_with_and_without_photos):
    """Recipe with image_url renders a [data-recipe-photo] button per row.

    Regression guard for the bug where _decorate() in app/routers/recipes.py
    omitted 'image_url' from its returned dict — so the template couldn't
    see the photo URL even when the DB row had one set.
    """
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    assert "data-recipe-photo" in body, (
        "Photo button not rendered for the seeded recipe with image_url. "
        "Check that _decorate() in app/routers/recipes.py includes 'image_url'."
    )
    assert 'data-src="/static/recipes/brownie.jpg"' in body
    assert 'data-name="Brownie con foto"' in body
    assert 'aria-label="Ver foto de Brownie con foto"' in body


def test_recetas_without_photo_row_shows_dash(authed_client, recipes_with_and_without_photos):
    """Recipe without image_url renders the em-dash placeholder, not a button.

    The placeholder <span aria-label="Sin foto">—</span> must appear in
    the row for 'Galleta sin foto', and that row must NOT contain a
    [data-recipe-photo] button.
    """
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    assert "Galleta sin foto" in body
    assert 'aria-label="Sin foto"' in body
    # Button elements (not the JS querySelector that references the same
    # attribute) — count occurrences of `<button ... data-recipe-photo`.
    body.count("<button") - body.count('<button type="submit"')
    body.count(" data-recipe-photo")
    # The opener script also references the attribute once, but it's inside
    # a JS string (querySelectorAll('[data-recipe-photo]')). We count
    # button elements specifically by looking for the full button pattern.
    actual_button_count = body.count('class="recipe-thumb" data-recipe-photo')
    assert actual_button_count == 1, (
        f"Expected exactly 1 photo BUTTON element (Brownie only), "
        f"found {actual_button_count}. Note: querySelectorAll('[data-recipe-photo]') "
        f"appears once in JS (intentional)."
    )
