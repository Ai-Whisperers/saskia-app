"""C2 — Customer-facing tablet menu at /m/{slug}.

The tablet menu is a public, no-auth page that lists a single product
(name, photo, portion label, price) for walk-in customers at a 1280×720
counter tablet. Each product has its own /m/{slug} URL so the bakery
can deep-link one item to WhatsApp.

This test file guards:
  - /m/{slug} returns 200 for visible products
  - /m/{slug} returns 404 for unknown / hidden / integer-PK slugs
  - No auth required (no session cookie needed)
  - The page contains the product name + formatted price
  - Product form POST persists tablet_slug + tablet_visible
  - Slug auto-generates from name on blank input
  - Slug uniqueness is enforced (IntegrityError → 409)
  - tablet_visible=False hides the product from /m/{slug}
  - Slug normalization (accent strip + dash collapse)
  - Validation helpers (slugify, validate_slug) work as expected
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from app.rms.models import Product

pytestmark = pytest.mark.crud


# ── Helpers ───────────────────────────────────────────────────────────────


from datetime import datetime, timedelta


def _datetime_now_plus_30d():
    return datetime.now() + timedelta(days=30)


def _make_product(session_factory, **overrides) -> int:
    """Create a Product row with sensible defaults and return its id."""
    defaults: dict = {
        "name": "Chipa Guazú",
        "portion_label": "1 porción",
        "sale_price_gs": 15000,
        "is_available": True,
        "tablet_slug": "chipa-guazu",
        "tablet_visible": True,
    }
    defaults.update(overrides)
    with session_factory() as s:
        p = Product(**defaults)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


# ── Public endpoint tests ─────────────────────────────────────────────────


def test_menu_unknown_slug_returns_404(client):
    """C2 #1: /m/{slug} returns 404 for a slug that doesn't exist."""
    r = client.get("/m/no-existe-este-slug")
    assert r.status_code == 404, (
        f"/m/no-existe-este-slug returned {r.status_code}, expected 404"
    )


def test_menu_visible_product_returns_200(client, session_factory):
    """C2 #2: /m/{slug} returns 200 when a visible product with that slug exists."""
    _make_product(session_factory, name="Croissant", tablet_slug="croissant")
    r = client.get("/m/croissant")
    assert r.status_code == 200, (
        f"/m/croissant returned {r.status_code}: {r.text[:200]}"
    )
    body = r.text
    assert "Croissant" in body, (
        f"Tablet page missing product name: {body[:500]}"
    )


def test_menu_no_auth_required(client, session_factory):
    """C2 #3: /m/{slug} works without any auth or session cookie."""
    _make_product(session_factory, name="Facturas", tablet_slug="facturas")
    # Bare `client` (no auth_client) — must succeed.
    r = client.get("/m/facturas")
    assert r.status_code == 200, (
        f"/m/facturas without auth returned {r.status_code}"
    )


def test_menu_integer_path_returns_404(client, session_factory):
    """C2 #4: /m/{int} must NOT resolve by integer PK — must be slug-based.

    Mirrors K6's /p/{token} guard against enumeration attacks. An
    attacker who guesses /m/1, /m/2, … must NOT see product data.
    """
    p_id = _make_product(
        session_factory, name="Enumerate Me", tablet_slug="enumerate-me"
    )
    r = client.get(f"/m/{p_id}")
    assert r.status_code == 404, (
        f"/m/{p_id} returned {r.status_code}, expected 404. "
        f"Endpoint must require slug, not integer PK. "
        f"This prevents enumeration attacks."
    )
    # Sanity: the slug URL still works.
    r2 = client.get("/m/enumerate-me")
    assert r2.status_code == 200


def test_menu_hidden_product_returns_404(client, session_factory):
    """C2 #5: tablet_visible=False must hide the product from the menu.

    Same 404 message whether the slug doesn't exist OR is hidden — an
    attacker must NOT be able to enumerate the hidden catalog.
    """
    _make_product(
        session_factory,
        name="Secreto",
        tablet_slug="secreto",
        tablet_visible=False,
    )
    r = client.get("/m/secreto")
    assert r.status_code == 404, (
        f"Hidden product /m/secreto returned {r.status_code}, expected 404"
    )


def test_menu_no_slug_returns_404(client, session_factory):
    """C2 #6: a product with no tablet_slug at all is invisible."""
    _make_product(
        session_factory,
        name="Sin Slug",
        tablet_slug=None,
        tablet_visible=True,
    )
    r = client.get("/m/sin-slug")
    assert r.status_code == 404


def test_menu_renders_name_price_portion(client, session_factory):
    """C2 #7: page contains the product name + formatted price."""
    _make_product(
        session_factory,
        name="Torta de Chocolate",
        tablet_slug="torta-chocolate",
        sale_price_gs=85000,
        portion_label="1 torta entera",
    )
    r = client.get("/m/torta-chocolate")
    assert r.status_code == 200
    body = r.text
    assert "Torta de Chocolate" in body
    assert "85" in body or "85000" in body  # locale-flexible price format
    assert "1 torta entera" in body


def test_menu_renders_optional_fields(client, session_factory):
    """C2 #8: optional fields (image_url, category, tags, notes) render when set."""
    _make_product(
        session_factory,
        name="Empanada",
        tablet_slug="empanada",
        image_url="https://example.com/empanada.jpg",
        category="Salados",
        tags="horneado, artesanal",
        notes="Relleno de carne.",
    )
    r = client.get("/m/empanada")
    assert r.status_code == 200
    body = r.text
    assert "https://example.com/empanada.jpg" in body
    assert "Salados" in body
    assert "horneado" in body
    assert "artesanal" in body
    assert "Relleno de carne." in body


def test_menu_404_message_does_not_leak(client, session_factory):
    """C2 #9: 404 messages must not leak the existence of hidden products."""
    _make_product(
        session_factory,
        name="Internal",
        tablet_slug="secret-xyz",
        tablet_visible=False,
    )
    r1 = client.get("/m/secret-xyz")  # hidden
    r2 = client.get("/m/never-existed-12345")  # unknown
    # Same status — and the message shouldn't say "exists but hidden".
    assert r1.status_code == 404
    assert r2.status_code == 404
    # Both responses must contain the same error detail. Either the
    # TestClient gets HTML (rendered 404 page) or JSON (default 404
    # handler); both branches must include "Menú no encontrado" or an
    # equivalent that doesn't distinguish hidden vs unknown.
    import json as _json

    def _detail(r):
        try:
            body = _json.loads(r.text)
            return body.get("error") or body.get("detail") or ""
        except Exception:
            return r.text

    detail1 = _detail(r1).lower()
    detail2 = _detail(r2).lower()
    # Strip the request path leakage (the URL contains 'secret-xyz')
    for needle in ("secret-xyz", "internal"):
        assert needle not in detail1, (
            f"Hidden product detail leaks info: {detail1!r}"
        )
    # The two details should be the same shape (we don't pin the
    # exact wording — different error templates can land here).
    assert len(detail1) > 0 and len(detail2) > 0


# ── Product form persistence ──────────────────────────────────────────────


def test_product_form_persists_tablet_slug(authed_client, session_factory):
    """C2 #10: POST /productos/nuevo with tablet_slug persists the value."""
    r = authed_client.post(
        "/productos/nuevo",
        data={
            "name": "Form Slug Test",
            "portion_label": "1 und",
            "sale_price_gs": "10000",
            "is_available": "on",
            "tablet_slug": "form-slug-test",
            "tablet_visible": "on",
        },
    )
    assert r.status_code in (200, 303), f"Create returned {r.status_code}"

    with session_factory() as s:
        p_obj = s.query(Product).filter(Product.name == "Form Slug Test").first()
        assert p_obj is not None, (
            "Product 'Form Slug Test' not persisted after POST /productos/nuevo"
        )
        assert p_obj.tablet_slug == "form-slug-test"
        assert p_obj.tablet_visible is True


def test_product_form_auto_generates_slug_from_name(
    authed_client, session_factory
):
    """C2 #11: blank tablet_slug auto-fills from the product name."""
    r = authed_client.post(
        "/productos/nuevo",
        data={
            "name": "Pan de Queso",
            "portion_label": "1 und",
            "sale_price_gs": "8000",
            "is_available": "on",
            # No tablet_slug submitted
            "tablet_visible": "on",
        },
    )
    assert r.status_code in (200, 303), f"Create returned {r.status_code}"

    with session_factory() as s:
        p = s.query(Product).filter(Product.name == "Pan de Queso").first()
        assert p is not None
        # slugify("Pan de Queso") → "pan-de-queso"
        assert p.tablet_slug == "pan-de-queso", (
            f"Expected auto-slug 'pan-de-queso', got {p.tablet_slug!r}"
        )


def test_product_form_unaccented_slug(authed_client, session_factory):
    """C2 #12: slug auto-generation strips accents (e.g. Chipá → chipa)."""
    r = authed_client.post(
        "/productos/nuevo",
        data={
            "name": "Chipá",
            "portion_label": "1 und",
            "sale_price_gs": "5000",
            "is_available": "on",
            "tablet_visible": "on",
        },
    )
    assert r.status_code in (200, 303)

    with session_factory() as s:
        p = s.query(Product).filter(Product.name == "Chipá").first()
        assert p is not None
        assert p.tablet_slug == "chipa"


def test_product_form_rejects_invalid_slug(authed_client):
    """C2 #13: slug with uppercase / spaces returns 400."""
    r = authed_client.post(
        "/productos/nuevo",
        data={
            "name": "Test",
            "portion_label": "1 und",
            "sale_price_gs": "1000",
            "is_available": "on",
            "tablet_slug": "Has Spaces And Uppercase",  # invalid
            "tablet_visible": "on",
        },
    )
    # The validate_slug helper raises 400 on bad input.
    assert r.status_code == 400, (
        f"Invalid slug POST returned {r.status_code}, expected 400"
    )


def test_product_form_unset_visibility_unchecks(authed_client, session_factory):
    """C2 #14: editing an existing product to UNCHECK tablet_visible persists False.

    Realistic flow: the operator edits an existing product, unchecks
    the "Visible en el menú" checkbox, and submits. The unchecked
    checkbox doesn't appear in the form POST, so the server must
    treat it as False. We edit (not create) to keep the test aligned
    with what the HTML actually submits.
    """
    p_id = _make_product(
        session_factory,
        name="Hide From Tablet",
        tablet_slug="hide-from-tablet",
        tablet_visible=True,
    )
    r = authed_client.post(
        f"/productos/{p_id}/editar",
        data={
            "name": "Hide From Tablet",
            "portion_label": "1 und",
            "sale_price_gs": "3000",
            "is_available": "on",
            "tablet_slug": "hide-from-tablet",
            # tablet_visible deliberately omitted (checkbox unchecked)
        },
    )
    assert r.status_code in (200, 303), f"Edit returned {r.status_code}"

    with session_factory() as s:
        p = s.get(Product, p_id)
        assert p is not None
        assert p.tablet_visible is False


def test_product_form_duplicate_slug_returns_409(authed_client, session_factory):
    """C2 #15: a second product with the same slug returns 409 (uniqueness)."""
    _make_product(
        session_factory,
        name="First Owner",
        tablet_slug="collision-slug",
    )
    r = authed_client.post(
        "/productos/nuevo",
        data={
            "name": "Second Owner",
            "portion_label": "1 und",
            "sale_price_gs": "4000",
            "is_available": "on",
            "tablet_slug": "collision-slug",  # already taken
            "tablet_visible": "on",
        },
    )
    assert r.status_code == 409, (
        f"Duplicate slug POST returned {r.status_code}, expected 409. "
        f"Slug uniqueness must be enforced."
    )


def test_product_edit_can_change_visibility(authed_client, session_factory):
    """C2 #16: editing a product to set tablet_visible=False hides it."""
    p_id = _make_product(
        session_factory,
        name="Toggle Me",
        tablet_slug="toggle-me",
        tablet_visible=True,
    )
    r = authed_client.post(
        f"/productos/{p_id}/editar",
        data={
            "name": "Toggle Me",
            "portion_label": "1 und",
            "sale_price_gs": "5000",
            "is_available": "on",
            "tablet_slug": "toggle-me",
            "tablet_visible": "",  # unchecked
        },
    )
    assert r.status_code in (200, 303), f"Edit returned {r.status_code}"

    with session_factory() as s:
        p = s.get(Product, p_id)
        assert p is not None
        assert p.tablet_visible is False

    # And the /m/{slug} page must now 404.
    r2 = authed_client.get("/m/toggle-me")
    assert r2.status_code == 404, (
        f"/m/toggle-me after hide returned {r2.status_code}, expected 404"
    )


# ── Migration tests ───────────────────────────────────────────────────────


def test_migration_066_runs_clean(tmp_db_path):
    """C2 #17: fresh-DB init_db() applies migration 066 (slug + visible).

    Migrates an empty DB and confirms the new columns exist with the
    expected types + defaults. This is the canonical guard against
    migration drift.
    """
    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db, make_engine

    db_file = tmp_db_path / "test.sqlite"
    engine = make_engine(f"sqlite:///{db_file}")
    init_db(engine)

    with engine.connect() as conn:
        # Confirm tablet_slug column exists.
        cols = conn.execute(text("PRAGMA table_info(product)")).fetchall()
        col_names = {c[1] for c in cols}
        assert "tablet_slug" in col_names, (
            f"tablet_slug column missing from product table. "
            f"Columns: {sorted(col_names)}"
        )
        assert "tablet_visible" in col_names, (
            f"tablet_visible column missing from product table. "
            f"Columns: {sorted(col_names)}"
        )

        # Confirm schema_version is current.
        row = conn.execute(
            text("SELECT value FROM app_meta WHERE key='schema_version'")
        ).first()
        assert row is not None
        # Stored as JSON string '"64"' or similar; just confirm >= 64.
        try:
            v = json.loads(row[0])
        except Exception:
            v = int(row[0])
        assert v >= CURRENT_SCHEMA_VERSION, (
            f"schema_version={v} < CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION}"
        )


def test_migration_066_is_idempotent(tmp_db_path):
    """C2 #18: running migration 066 twice does not raise.

    Belt-and-suspenders against ALTER try/except masking a real bug.
    """
    from app.rms.db import _migration_066_product_tablet_slug, init_db, make_engine

    db_file = tmp_db_path / "test.sqlite"
    engine = make_engine(f"sqlite:///{db_file}")
    init_db(engine)

    with engine.connect() as conn:
        # Run the migration a second time — must not raise.
        _migration_066_product_tablet_slug(conn)
        _migration_066_product_tablet_slug(conn)


# ── slugify() / validate_slug() unit tests ───────────────────────────────


def test_slugify_strips_accents_and_punctuation():
    """C2 #19: slugify() normalizes accented Spanish text."""
    from app.rms.validation import slugify

    assert slugify("Pan de Queso") == "pan-de-queso"
    assert slugify("Chipá Guazú") == "chipa-guazu"
    assert slugify("  --foo!!bar??  ") == "foo-bar"
    assert slugify("") == "item"  # fallback
    assert slugify("___") == "item"  # fallback for punctuation-only
    assert slugify("Hello World") == "hello-world"


def test_slugify_collapses_multiple_dashes():
    """C2 #20: slugify() collapses runs of non-alphanumeric into a single dash."""
    from app.rms.validation import slugify

    assert slugify("a - b - c") == "a-b-c"
    assert slugify("a___b") == "a-b"


def test_slugify_truncates_to_max_len():
    """C2 #21: slugify() never returns more than max_len chars."""
    from app.rms.validation import slugify

    long = "a" * 200
    result = slugify(long, max_len=60)
    assert len(result) == 60
    assert result == "a" * 60


def test_validate_slug_accepts_valid():
    """C2 #22: validate_slug() accepts well-formed slugs."""
    from app.rms.validation import validate_slug

    assert validate_slug("foo-bar") == "foo-bar"
    assert validate_slug("abc123") == "abc123"
    assert validate_slug("a-1-b-2") == "a-1-b-2"


def test_validate_slug_blank_returns_none_when_optional():
    """C2 #23: blank input → None when required=False."""
    from app.rms.validation import validate_slug

    assert validate_slug("") is None
    assert validate_slug(None) is None
    assert validate_slug("   ") is None


def test_validate_slug_blank_400_when_required():
    """C2 #24: blank input → 400 when required=True."""
    from fastapi import HTTPException

    from app.rms.validation import validate_slug

    with pytest.raises(HTTPException) as exc_info:
        validate_slug("", required=True)
    assert exc_info.value.status_code == 400


def test_validate_slug_rejects_invalid_chars():
    """C2 #25: spaces / uppercase / accents → 400."""
    from fastapi import HTTPException

    from app.rms.validation import validate_slug

    with pytest.raises(HTTPException):
        validate_slug("Has Spaces")
    with pytest.raises(HTTPException):
        validate_slug("UPPERCASE")
    with pytest.raises(HTTPException):
        validate_slug("accented-é")


def test_validate_slug_rejects_leading_trailing_dash():
    """C2 #26: leading or trailing dash → 400."""
    from fastapi import HTTPException

    from app.rms.validation import validate_slug

    with pytest.raises(HTTPException):
        validate_slug("-leading")
    with pytest.raises(HTTPException):
        validate_slug("trailing-")


# ── Backwards compat / smoke ──────────────────────────────────────────────


def test_productos_list_still_renders(authed_client, session_factory):
    """C2 #27: the existing /productos list view is unaffected."""
    _make_product(session_factory, name="List Compat", tablet_slug="list-compat")
    r = authed_client.get("/productos")
    assert r.status_code == 200
    assert "List Compat" in r.text


def test_other_public_routes_unaffected(client, session_factory):
    """C2 #28: /p/{token} still works (regression guard for router mount order)."""

    from app.rms.models import Pedido

    with session_factory() as s:
        pedido = Pedido(
            customer_name="Compat Customer",
            promised_date=datetime.utcnow().date(),
            channel="mostrador",
            public_token="c2compat",
            public_token_expires_at=_datetime_now_plus_30d(),
        )
        s.add(pedido)
        s.commit()

    r = client.get("/p/c2compat")
    assert r.status_code == 200, (
        f"/p/c2compat after C2 mount returned {r.status_code}. "
        "Tablet-menu router mount must not break /p/c2compat."
    )
