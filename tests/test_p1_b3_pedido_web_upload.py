"""P1-B3 — Pedido web upload (comprobante de pago).

Closes the catering flow. Today /p/{token} shows the pedido info but
has no way for the customer to upload the receipt — they have to
WhatsApp it, and the operator manually attaches it. Now:
  - If payment_intent is transferencia/qr/tarjeta, the page shows a
    file input.
  - POST /p/{token}/comprobante saves the file under
    {DATA_DIR}/payment_receipts/{pedido_id}/{timestamp}_{name}.jpg
  - pedido.payment_receipt_path + payment_receipt_uploaded_at are set.
  - The page re-renders with a flash banner.

Run: cd /opt/data/profiles/ivan/scratch/sazon-app-work && ./.venv/bin/python -m pytest tests/test_p1_b3_pedido_web_upload.py -v
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta


def _make_pedido(session, *, payment_intent: str = "transferencia") -> int:
    """Create a customer + pedido with public_token. Returns pedido_id."""
    from app.rms.models import Customer, Pedido

    cust = Customer(name="Test Cust", phone="0981123456")
    session.add(cust)
    session.flush()

    import secrets

    p = Pedido(
        customer_id=cust.id,
        customer_name="Test Cust",
        customer_phone="0981123456",
        promised_date=datetime.utcnow().date(),
        promised_time="15:00",
        channel="whatsapp",
        status="pending",
        payment_intent=payment_intent,
        notes="",
        public_token=secrets.token_urlsafe(6)[:8],
        # P1-2: tests must set a future expiry so the public_pedido
        # route doesn't 410-expire the link. Default to "30 days from now".
        public_token_expires_at=datetime.utcnow() + timedelta(days=30),
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p.id


def test_pedido_publico_page_shows_comprobante_form_when_transfer(client, session_factory) -> None:
    """GET /p/{token} renders the upload form when payment_intent != efectivo."""
    from app.rms.models import Pedido

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="transferencia")
        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    r = client.get(f"/p/{token}")
    assert r.status_code == 200
    body = r.text
    assert "Comprobante de pago" in body
    assert f"/p/{token}/comprobante" in body
    assert 'enctype="multipart/form-data"' in body


def test_pedido_publico_page_hides_form_when_efectivo(client, session_factory) -> None:
    """When payment_intent == efectivo, no upload form (cash payment)."""
    from app.rms.models import Pedido

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="efectivo")
        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    r = client.get(f"/p/{token}")
    assert r.status_code == 200
    assert "Comprobante de pago" not in r.text


def test_upload_comprobante_saves_file(client, session_factory) -> None:
    """POST /p/{token}/comprobante saves the file + updates the row."""
    from app.rms.config import DATA_DIR
    from app.rms.models import Pedido

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="qr")
        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    fake_bytes = b"fake jpg bytes for testing"
    r = client.post(
        f"/p/{token}/comprobante",
        files={"file": ("comprobante.jpg", io.BytesIO(fake_bytes), "image/jpeg")},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
    assert "Comprobante recibido" in r.text

    # DB updated
    with session_factory() as s:
        pedido = s.get(Pedido, pid)
        assert pedido.payment_receipt_path is not None
        assert pedido.payment_receipt_path.startswith(f"payment_receipts/{pid}/")
        assert pedido.payment_receipt_path.endswith(".jpg")
        assert pedido.payment_receipt_uploaded_at is not None

    # File on disk
    relative = pedido.payment_receipt_path
    file_on_disk = DATA_DIR / relative
    assert file_on_disk.exists()
    assert file_on_disk.read_bytes() == fake_bytes

    # Cleanup
    file_on_disk.unlink()


def test_upload_rejects_disallowed_extension(client, session_factory) -> None:
    """Only JPG/PNG/WEBP/PDF are accepted."""
    from app.rms.models import Pedido

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="transferencia")
        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    r = client.post(
        f"/p/{token}/comprobante",
        files={"file": ("hack.exe", io.BytesIO(b"exe bytes"), "application/octet-stream")},
    )
    assert r.status_code == 200
    assert "Formato no permitido" in r.text

    with session_factory() as s:
        pedido = s.get(Pedido, pid)
        assert pedido.payment_receipt_path is None


def test_upload_rejects_oversized_file(client, session_factory) -> None:
    """Files over 8 MB are rejected with a clear error."""
    from app.rms.models import Pedido

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="tarjeta")
        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    # 9 MB file
    big = b"\0" * (9 * 1024 * 1024)
    r = client.post(
        f"/p/{token}/comprobante",
        files={"file": ("huge.jpg", io.BytesIO(big), "image/jpeg")},
    )
    assert r.status_code == 200
    assert "demasiado grande" in r.text.lower()


def test_upload_invalid_token_returns_404(client) -> None:
    """Bogus token → 404."""
    r = client.post(
        "/p/notarealtoken/comprobante",
        files={"file": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")},
    )
    assert r.status_code == 404


def test_upload_pdf_accepted(client, session_factory) -> None:
    """PDFs are accepted (bank transfer PDFs)."""
    from app.rms.models import Pedido

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="transferencia")
        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    pdf_bytes = b"%PDF-1.4\nfake pdf body\n%%EOF"
    r = client.post(
        f"/p/{token}/comprobante",
        files={"file": ("transfer.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert r.status_code == 200
    assert "Comprobante recibido" in r.text
    with session_factory() as s:
        pedido = s.get(Pedido, pid)
        assert pedido.payment_receipt_path is not None
        assert pedido.payment_receipt_path.endswith(".pdf")


def test_upload_overwrites_previous(client, session_factory) -> None:
    """Re-uploading replaces the previous path (timestamp prefix disambiguates)."""
    from app.rms.config import DATA_DIR
    from app.rms.models import Pedido

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="transferencia")
        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    # First upload
    client.post(
        f"/p/{token}/comprobante",
        files={"file": ("a.jpg", io.BytesIO(b"first"), "image/jpeg")},
    )
    with session_factory() as s:
        first_path = s.get(Pedido, pid).payment_receipt_path

    # Second upload
    client.post(
        f"/p/{token}/comprobante",
        files={"file": ("b.jpg", io.BytesIO(b"second"), "image/jpeg")},
    )
    with session_factory() as s:
        second_path = s.get(Pedido, pid).payment_receipt_path

    assert first_path != second_path
    # Both files exist on disk (timestamp prefix avoids collision)
    assert (DATA_DIR / first_path).exists()
    assert (DATA_DIR / second_path).exists()

    # Cleanup
    (DATA_DIR / first_path).unlink()
    (DATA_DIR / second_path).unlink()


# ════════════════════════════════════════════════════════════════════
# P0-1: CSRF gap coverage for the public comprobante upload endpoint.
#
# The endpoint is reachable by an unauthenticated customer from
# WhatsApp. Without CSRF protection, an attacker on evil.com could
# craft a form that POSTs to /p/{token}/comprobante using the token
# captured from a referer header. The fix adds a form-field CSRF
# check (verify_form_csrf dependency) that requires the form to
# include a hidden _csrf_token whose signed value matches the
# cookie's signed value.
# ════════════════════════════════════════════════════════════════════


def _make_pedido_with_csrf_token(session) -> tuple[int, str, str]:
    """Create a pedido and return (pedido_id, public_token, csrf_cookie)."""
    from app.rms.models import Pedido

    pid = _make_pedido(session, payment_intent="qr")
    token = session.execute(
        __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
    ).scalar_one()

    # Hit a non-exempt GET to prime the CSRF cookie via the middleware.
    from starlette.testclient import TestClient

    from app.rms.main import app

    with TestClient(app, raise_server_exceptions=False) as tmp:
        tmp.get("/")
        csrf = tmp.cookies.get("csrf_token") or ""

    return pid, token, csrf


def test_comprobante_rejects_post_without_csrf_cookie(client, session_factory) -> None:
    """POST without a CSRF cookie → 403 (middleware blocks)."""
    from starlette.testclient import TestClient

    from app.rms.main import app

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="qr")
        from app.rms.models import Pedido

        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    # Fresh client (no cookie jar)
    fresh = TestClient(app, raise_server_exceptions=False)
    r = fresh.post(
        f"/p/{token}/comprobante",
        files={"file": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")},
        data={"_csrf_token": "doesnt_matter"},
    )
    assert r.status_code == 403, f"Expected 403 without cookie, got {r.status_code}"


def test_comprobante_rejects_post_with_mismatched_csrf_form_field(client, session_factory) -> None:
    """POST with valid cookie but WRONG _csrf_token form field → 403.

    The verify_form_csrf dependency compares the signed payloads, not
    raw nonces. A wrong token fails the signature check.
    """
    from starlette.testclient import TestClient

    from app.rms.main import app

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="qr")
        from app.rms.models import Pedido

        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    fresh = TestClient(app, raise_server_exceptions=False)
    fresh.get("/")  # prime cookie
    csrf = fresh.cookies.get("csrf_token")
    assert csrf

    r = fresh.post(
        f"/p/{token}/comprobante",
        files={"file": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")},
        data={"_csrf_token": csrf + "tampered"},
    )
    assert r.status_code == 403, f"Expected 403 with tampered token, got {r.status_code}"


def test_comprobante_rejects_post_missing_csrf_form_field(client, session_factory) -> None:
    """POST with valid cookie but NO _csrf_token field → 403.

    The verify_form_csrf dependency requires the form field explicitly.
    """
    from starlette.testclient import TestClient

    from app.rms.main import app

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="qr")
        from app.rms.models import Pedido

        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    fresh = TestClient(app, raise_server_exceptions=False)
    fresh.get("/")  # prime cookie
    assert fresh.cookies.get("csrf_token")

    r = fresh.post(
        f"/p/{token}/comprobante",
        files={"file": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")},
        # intentionally NO data= kwarg
    )
    assert r.status_code == 403, f"Expected 403 with no _csrf_token field, got {r.status_code}"


def test_comprobante_accepts_post_with_matching_csrf_form_field(client, session_factory) -> None:
    """POST with valid cookie AND matching _csrf_token → 200 (happy path)."""
    from starlette.testclient import TestClient

    from app.rms.main import app

    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="qr")
        from app.rms.models import Pedido

        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    fresh = TestClient(app, raise_server_exceptions=False)
    fresh.get("/")
    csrf = fresh.cookies.get("csrf_token")
    assert csrf

    fake = b"valid jpg bytes"
    r = fresh.post(
        f"/p/{token}/comprobante",
        files={"file": ("comprobante.jpg", io.BytesIO(fake), "image/jpeg")},
        data={"_csrf_token": csrf},
    )
    assert r.status_code == 200, (
        f"Expected 200 with valid CSRF, got {r.status_code}: {r.text[:300]}"
    )
    assert "Comprobante recibido" in r.text

    # Cleanup
    from app.rms.config import DATA_DIR
    from app.rms.models import Pedido

    with session_factory() as s:
        path = s.get(Pedido, pid).payment_receipt_path
    if path:
        (DATA_DIR / path).unlink(missing_ok=True)


def test_pedido_publico_form_includes_csrf_field(client, session_factory) -> None:
    """The /p/{token} page MUST render the _csrf_token hidden input.

    Belt-and-braces: even though verify_form_csrf is enforced server-side,
    verify the template actually emits the field so a non-JS user can
    submit a valid form.
    """
    with session_factory() as s:
        pid = _make_pedido(s, payment_intent="qr")
        from app.rms.models import Pedido

        token = s.execute(
            __import__("sqlalchemy").select(Pedido.public_token).where(Pedido.id == pid)
        ).scalar_one()

    r = client.get(f"/p/{token}")
    assert r.status_code == 200
    assert 'name="_csrf_token"' in r.text, (
        "pedido_publico.html must include hidden _csrf_token field on every "
        "upload form (P0-1 fix). Without it, the verify_form_csrf dependency "
        "rejects all uploads with 403."
    )
    # The value attribute should also be populated with a token from the cookie
    assert 'value="' in r.text
