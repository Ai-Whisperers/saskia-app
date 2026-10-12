"""Migration 119: auto-link photos in static/recipes/ to recipes by name.

SASKIA-213 ship: 30 photos already live in app/static/recipes/ (e.g.
receta-babka.jpg, receta-cheesecake.jpg, etc.) but no Recipe has its
image_url set. Operators had to manually pick each one in the picker.

This migration is a one-shot best-effort: for each Recipe, look for a
photo file whose name starts with `receta-<slug>` and set image_url to
`/static/recipes/<filename>`. Skips recipes that already have an
image_url (don't overwrite operator choice). Idempotent and safe to
re-run.

The photo filenames are based on the recipe name with the prefix
stripped: `bizcocho_basico_25_cm_basiscake__rec_011` → no matching
file in the current set (no `receta-bizcocho_basico_25_cm_basiscake__rec_011.jpg`).
The naming convention in static/recipes/ uses just the dish name
(`receta-babka`, `receta-cheesecake`, `receta-babka_entera`, ...).
So this migration does a CONTAINS match on the first 8+ characters of
the recipe slug.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text


def _slug_for_filename(recipe_name: str) -> str:
    """Extract the slug fragment a photo file would use.

    `bizcocho_basico_25_cm_basiscake__rec_011` → `bizcocho_basico_25_cm_basiscake`
    `babka__rec_017` → `babka`
    `cheesecake_30x50__rec_002` → `cheesecake_30x50`
    """
    # Strip the __rec_NNN suffix
    without_rec = re.sub(r"__rec_\d+$", "", recipe_name)
    return without_rec


def _migration_119_recipe_photo_autolink(conn: Any) -> None:
    """Find recipes without image_url, set it from a matching photo file.

    Strategy: get all photos in static/recipes/, parse the slug from the
    filename, and for each Recipe compute its slug. If any photo's slug
    STARTS WITH the recipe's slug (or the recipe's slug starts with the
    photo's slug, allowing `receta-babka.jpg` to match `babka__rec_017`)
    — set the first match.

    This is intentionally loose because the photo filename convention is
    the human-readable dish name, not the slug.
    """
    from app.rms.static_paths import recipes_dir

    photo_dir = recipes_dir()
    if not photo_dir.is_dir():
        # No photos — nothing to do
        from app.rms.db import _bump_schema_version
        _bump_schema_version(conn, 119)
        return

    # Build a list of (slug-from-filename, filename) pairs.
    photos: list[tuple[str, str]] = []
    for p in sorted(photo_dir.iterdir()):
        if not p.is_file():
            continue
        name = p.name
        # Only consider image files
        if not re.search(r"\.(jpg|jpeg|png|webp|gif)$", name, re.IGNORECASE):
            continue
        # Strip the "receta-" prefix and the extension to get the slug
        slug = re.sub(r"^receta-", "", name)
        slug = re.sub(r"\.(jpg|jpeg|png|webp|gif)$", "", slug, flags=re.IGNORECASE)
        # Strip any __rec_NNN suffix in the filename too
        slug = re.sub(r"__rec_\d+$", "", slug)
        photos.append((slug.lower(), name))

    # Get all recipes
    recipes = conn.execute(
        text("SELECT id, name, image_url FROM recipe")
    ).fetchall()

    written = 0
    skipped_already_linked = 0
    skipped_no_match = 0
    for recipe_id, recipe_name, current_image_url in recipes:
        if current_image_url:
            skipped_already_linked += 1
            continue
        recipe_slug = _slug_for_filename(recipe_name).lower()
        if not recipe_slug:
            skipped_no_match += 1
            continue
        # Look for a photo whose slug matches the recipe slug
        # (allow either "recipe_slug" ⊆ "photo_slug" or vice versa to
        # tolerate dish-name vs slug differences)
        match = None
        for photo_slug, filename in photos:
            if (
                photo_slug == recipe_slug
                or photo_slug.startswith(recipe_slug + "_")
                or photo_slug.startswith(recipe_slug)
                or recipe_slug.startswith(photo_slug + "_")
            ):
                match = filename
                break
        if not match:
            skipped_no_match += 1
            continue
        conn.execute(
            text("UPDATE recipe SET image_url = :url WHERE id = :rid"),
            {"url": f"/static/recipes/{match}", "rid": recipe_id},
        )
        written += 1

    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 119)
