"""Tests for app/rms/upload_limits.validate_upload."""

from __future__ import annotations

import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.rms.upload_limits import (
    CSV_LIMIT_2MB,
    CSV_MIME_TYPES,
    RECEIPT_LIMIT_5MB,
    validate_upload,
)


def _make_upload(
    content: bytes, *, content_type: str = "text/csv", filename: str = "test.csv"
) -> UploadFile:
    return UploadFile(
        filename=filename, file=io.BytesIO(content), headers={"content-type": content_type}
    )


def test_accepts_csv_under_limit():
    raw = _make_upload(b"a,b,c\n1,2,3\n", content_type="text/csv")
    out = validate_upload(raw, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    assert out is raw


def test_rejects_empty_file():
    raw = _make_upload(b"", content_type="text/csv")
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    assert exc.value.status_code == 400


def test_rejects_wrong_mime_type():
    raw = _make_upload(b"<?xml ...", content_type="application/xml")
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    assert exc.value.status_code == 415
    assert "no permitido" in exc.value.detail


def test_rejects_oversize_file():
    raw = _make_upload(b"x" * (CSV_LIMIT_2MB + 1))
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    assert exc.value.status_code == 413
    assert "demasiado grande" in exc.value.detail


def test_accepts_text_plain_for_csv():
    """Some browsers send text/plain when the file has no extension."""
    raw = _make_upload(b"name,price\npan,5000\n", content_type="text/plain")
    out = validate_upload(raw, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    assert out is raw


def test_rejects_non_upload_object():
    with pytest.raises(HTTPException) as exc:
        validate_upload({"not": "a file"}, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    assert exc.value.status_code == 400


def test_receipt_limit_accepts_5mb():
    """5MB is the receipt cap (PDF + images)."""
    raw = _make_upload(
        b"x" * (RECEIPT_LIMIT_5MB - 1), content_type="application/pdf", filename="comprobante.pdf"
    )
    out = validate_upload(
        raw,
        allowed_types=("application/pdf", "image/png", "image/jpeg"),
        max_size=RECEIPT_LIMIT_5MB,
    )
    assert out is raw


def test_receipt_limit_rejects_5mb_plus_one():
    raw = _make_upload(b"x" * (RECEIPT_LIMIT_5MB + 1), content_type="application/pdf")
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=("application/pdf",), max_size=RECEIPT_LIMIT_5MB)
    assert exc.value.status_code == 413


def test_file_pointer_rewound_after_validation():
    """validate_upload consumes the body to check size — must rewind so
    the caller can read it again."""
    raw = _make_upload(b"a,b\n1,2\n", content_type="text/csv")
    validate_upload(raw, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    assert raw.file.read() == b"a,b\n1,2\n"
