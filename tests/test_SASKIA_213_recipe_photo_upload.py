"""SASKIA-213 — recipe photo upload endpoint.

Builds on the existing /recetas/{r_id}/set-photo picker (which already
saves image_url from a chosen file in /static/recipes/) by adding a
multipart/form-data upload route so operators can drop a JPG onto a
recipe page instead of scp'ing it to the server first.
"""

from __future__ import annotations

import io
import re

from PIL import Image


def _make_image(format_: str = "JPEG", color: str = "white") -> bytes:
    """Build a 1x1 in-memory image as bytes."""
    img = Image.new("RGB", (1, 1), color=color)
    buf = io.BytesIO()
    img.save(buf, format=format_)
    return buf.getvalue()


# ── 1. POST /recetas/{r_id}/set-photo/upload accepts a JPG ──────────


def test_upload_recipe_photo_accepts_jpg(client, session_factory, tmp_path, monkeypatch):
    """Operator uploads a JPG; file lands in static/recipes/."""
    from app.rms import static_paths

    monkeypatch.setattr(static_paths, "recipes_dir", lambda: tmp_path)

    from app.rms.models import Recipe

    with session_factory() as s:
        r = Recipe(
            name="upload_test__rec_900",
            yield_qty=1,
            yield_unit="und",
        )
        s.add(r)
        s.commit()
        rid = r.id

    files = {"file": ("my_pic.jpg", _make_image("JPEG"), "image/jpeg")}
    resp = client.post(f"/recetas/{rid}/set-photo/upload", files=files, follow_redirects=False)
    assert resp.status_code in (200, 303), f"got {resp.status_code} {resp.text[:300]}"

    saved = list(tmp_path.glob("*.jpg")) + list(tmp_path.glob("*.jpeg"))
    assert saved, f"no file saved to {tmp_path}"


# ── 2. Wrong MIME type → 415 ────────────────────────────────────────


def test_upload_recipe_photo_rejects_non_image(client, session_factory, tmp_path, monkeypatch):
    from app.rms import static_paths

    monkeypatch.setattr(static_paths, "recipes_dir", lambda: tmp_path)

    from app.rms.models import Recipe

    with session_factory() as s:
        r = Recipe(
            name="bad_type__rec_901",
            yield_qty=1,
            yield_unit="und",
        )
        s.add(r)
        s.commit()
        rid = r.id

    files = {"file": ("evil.exe", b"\x00\x00not-an-image", "application/octet-stream")}
    resp = client.post(f"/recetas/{rid}/set-photo/upload", files=files, follow_redirects=False)
    assert resp.status_code == 415, f"expected 415, got {resp.status_code}"


# ── 3. Oversize file → 413 ──────────────────────────────────────────


def test_upload_recipe_photo_rejects_oversize(client, session_factory, tmp_path, monkeypatch):
    from app.rms import static_paths

    monkeypatch.setattr(static_paths, "recipes_dir", lambda: tmp_path)

    from app.rms.models import Recipe

    with session_factory() as s:
        r = Recipe(
            name="big__rec_902",
            yield_qty=1,
            yield_unit="und",
        )
        s.add(r)
        s.commit()
        rid = r.id

    # 6 MB of zeros (limit is 5 MB)
    big = b"\x00" * (6 * 1024 * 1024)
    files = {"file": ("huge.jpg", big, "image/jpeg")}
    resp = client.post(f"/recetas/{rid}/set-photo/upload", files=files, follow_redirects=False)
    assert resp.status_code == 413, f"expected 413, got {resp.status_code}"


# ── 4. Empty file → 400 ─────────────────────────────────────────────


def test_upload_recipe_photo_rejects_empty(client, session_factory, tmp_path, monkeypatch):
    from app.rms import static_paths

    monkeypatch.setattr(static_paths, "recipes_dir", lambda: tmp_path)

    from app.rms.models import Recipe

    with session_factory() as s:
        r = Recipe(
            name="empty__rec_903",
            yield_qty=1,
            yield_unit="und",
        )
        s.add(r)
        s.commit()
        rid = r.id

    files = {"file": ("nothing.jpg", b"", "image/jpeg")}
    resp = client.post(f"/recetas/{rid}/set-photo/upload", files=files, follow_redirects=False)
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}"


# ── 5. Uploaded file is then pickable ───────────────────────────────


def test_uploaded_photo_appears_in_picker(client, session_factory, tmp_path, monkeypatch):
    """After upload, /recetas/{r_id}/set-photo should list the new file."""
    from app.rms import static_paths

    monkeypatch.setattr(static_paths, "recipes_dir", lambda: tmp_path)

    from app.rms.models import Recipe

    with session_factory() as s:
        r = Recipe(
            name="picker__rec_904",
            yield_qty=1,
            yield_unit="und",
        )
        s.add(r)
        s.commit()
        rid = r.id

    files = {"file": ("red.jpg", _make_image("JPEG", color="red"), "image/jpeg")}
    resp_upload = client.post(
        f"/recetas/{rid}/set-photo/upload", files=files, follow_redirects=False
    )
    assert resp_upload.status_code in (200, 303)

    # The server renames uploaded files to <date>-<hex>.<ext> so we can't
    # match by client filename. Instead, check the picker now lists at
    # least one .jpg.
    resp_pick = client.get(f"/recetas/{rid}/set-photo")
    assert resp_pick.status_code == 200
    jpg_names = re.findall(r'value="([^"]+\.jpg)"', resp_pick.text)
    assert any(name.endswith(".jpg") for name in jpg_names), (
        f"no .jpg in picker, got: {jpg_names[:5]}"
    )


# ── 6. Picker filters non-image files ───────────────────────────────


def test_picker_filters_non_image_files(client, session_factory, tmp_path, monkeypatch):
    """When tmp_path has a .sqlite sidecar (e.g. from a dev environment),
    the picker must NOT show it — only image files."""
    from app.rms import static_paths

    monkeypatch.setattr(static_paths, "recipes_dir", lambda: tmp_path)

    # Drop a .sqlite-junk file in there
    (tmp_path / "junk.sqlite").write_bytes(b"junk")

    from app.rms.models import Recipe

    with session_factory() as s:
        r = Recipe(
            name="filter__rec_905",
            yield_qty=1,
            yield_unit="und",
        )
        s.add(r)
        s.commit()
        rid = r.id

    resp = client.get(f"/recetas/{rid}/set-photo")
    assert resp.status_code == 200
    assert "junk.sqlite" not in resp.text
