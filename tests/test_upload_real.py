"""tests/test_upload_real.py — Cover upload_limits with real UploadFile."""
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile


def _make_upload(content: bytes, content_type: str = "text/csv") -> UploadFile:
    """Create a real UploadFile for validate_upload."""
    import io
    return UploadFile(filename="test.csv", file=io.BytesIO(content), headers={"content-type": content_type})


def test_validate_upload_not_upload_file():
    from app.rms.upload_limits import validate_upload
    with pytest.raises(HTTPException) as exc:
        validate_upload("not a file", allowed_types=("text/csv",), max_size=1024)
    assert exc.value.status_code == 400

def test_validate_upload_wrong_mime():
    from app.rms.upload_limits import validate_upload
    raw = _make_upload(b"data", content_type="application/octet-stream")
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=("text/csv", "text/plain"), max_size=1024)
    assert exc.value.status_code == 415

def test_validate_upload_too_large():
    from app.rms.upload_limits import validate_upload
    big_content = b"x" * 5000
    raw = _make_upload(big_content, content_type="text/csv")
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=("text/csv",), max_size=1000)
    assert exc.value.status_code == 413

def test_validate_upload_success():
    from app.rms.upload_limits import validate_upload
    raw = _make_upload(b"col1,col2\na,b", content_type="text/csv")
    result = validate_upload(raw, allowed_types=("text/csv",), max_size=1000)
    assert result is raw

def test_validate_upload_multiple_allowed_types():
    from app.rms.upload_limits import validate_upload
    raw = _make_upload(b"plain text", content_type="text/plain")
    result = validate_upload(raw, allowed_types=("text/csv", "text/plain", "application/json"), max_size=1000)
    assert result is raw

def test_validate_upload_empty_file():
    from app.rms.upload_limits import validate_upload
    raw = _make_upload(b"", content_type="text/csv")
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=("text/csv",), max_size=1000)
    assert exc.value.status_code == 400

def test_validate_upload_custom_field_name():
    from app.rms.upload_limits import validate_upload
    with pytest.raises(HTTPException) as exc:
        validate_upload("not a file", allowed_types=("text/csv",), max_size=1024, field_name="csv")
    assert "csv" in exc.value.detail.lower()
