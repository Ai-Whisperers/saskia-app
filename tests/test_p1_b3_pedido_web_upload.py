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

Run: cd /opt/data/profiles/ivan/scratch/saskia-app-work && ./.venv/bin/python -m pytest tests/test_p1_b3_pedido_web_upload.py -v
"""
from __future__ import annotations

import io
from datetime import datetime

import pytest


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
