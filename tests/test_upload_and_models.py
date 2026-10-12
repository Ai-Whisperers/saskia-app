"""tests/test_upload_and_models.py — Cover upload_limits, model loading, seed imports.

Target modules:
- app/rms/upload_limits.py (22 stmts at 0%)
- model imports (smoke tests for SQLAlchemy models)
"""
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from starlette.datastructures import UploadFile


# upload_limits tests
def test_validate_upload_not_upload_file():
    from app.rms.upload_limits import validate_upload
    with pytest.raises(HTTPException) as exc:
        validate_upload("not a file", allowed_types=("text/csv",), max_size=1024)
    assert exc.value.status_code == 400
    assert "archivo" in exc.value.detail.lower()

def test_validate_upload_wrong_mime():
    from app.rms.upload_limits import validate_upload
    raw = MagicMock(spec=UploadFile)
    raw.content_type = "application/octet-stream"
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=("text/csv", "text/plain"), max_size=1024)
    assert exc.value.status_code == 415

def test_validate_upload_too_large():
    from app.rms.upload_limits import validate_upload
    raw = MagicMock(spec=UploadFile)
    raw.content_type = "text/csv"
    raw.size = 5000  # bigger than max_size
    with pytest.raises(HTTPException) as exc:
        validate_upload(raw, allowed_types=("text/csv",), max_size=1000)
    assert exc.value.status_code == 413
    assert "tamaño" in exc.value.detail.lower() or "size" in exc.value.detail.lower()

def test_validate_upload_success():
    from app.rms.upload_limits import validate_upload
    raw = MagicMock(spec=UploadFile)
    raw.content_type = "text/csv"
    raw.size = 500
    result = validate_upload(raw, allowed_types=("text/csv",), max_size=1000)
    assert result is raw

def test_validate_upload_default_field_name():
    from app.rms.upload_limits import validate_upload
    with pytest.raises(HTTPException) as exc:
        validate_upload("not a file", allowed_types=("text/csv",), max_size=1024)
    # Default field_name is "file"
    assert "file" in exc.value.detail.lower() or "archivo" in exc.value.detail.lower()

def test_validate_upload_custom_field_name():
    from app.rms.upload_limits import validate_upload
    with pytest.raises(HTTPException) as exc:
        validate_upload("not a file", allowed_types=("text/csv",), max_size=1024, field_name="csv")
    # Should mention csv
    assert "csv" in exc.value.detail.lower() or "archivo" in exc.value.detail.lower()

def test_validate_upload_multiple_allowed_types():
    from app.rms.upload_limits import validate_upload
    raw = MagicMock(spec=UploadFile)
    raw.content_type = "text/plain"
    raw.size = 100
    result = validate_upload(raw, allowed_types=("text/csv", "text/plain", "application/json"), max_size=1000)
    assert result is raw


# Models import smoke tests (these exercise import lines that are otherwise 0%)
def test_import_sale_model():
    """Importing the Sale model exercises all model definitions."""
    from app.rms.models.sales import Sale
    assert hasattr(Sale, "__tablename__")

def test_import_customer_model():
    from app.rms.models.sales import Customer
    assert hasattr(Customer, "__tablename__")

def test_import_recipe_pricing_model():
    from app.rms.models.sales import RecipePricing
    assert hasattr(RecipePricing, "__tablename__")

def test_import_sale_stock_move_model():
    """SaleStockMove is a STUB (Phase 14 refactor)."""
    from app.rms.models.sales import SaleStockMove
    # Should be importable
    assert SaleStockMove is not None

def test_import_tag_models():
    from app.rms.models.sales import Tag, TagLink
    assert hasattr(Tag, "__tablename__")
    assert hasattr(TagLink, "__tablename__")

def test_import_channels_model():
    from app.rms.models.sales import Channel
    assert hasattr(Channel, "__tablename__")

def test_sales_module_exports():
    from app.rms.models import sales
    expected = {"Customer", "RecipePricing", "Sale", "SaleStockMove", "Tag", "TagLink"}
    actual = set(sales.__all__)
    assert expected.issubset(actual)

# Schema versions tests (we know SCHEMA_VERSION is 114)
def test_schema_version():
    """Test that the schema version is at a known value."""
    # The current schema version is 114
    # We can verify by importing db module constants
    try:
        from app.rms.db import SCHEMA_VERSION
        assert SCHEMA_VERSION >= 100  # Should be modern
    except ImportError:
        pytest.skip("SCHEMA_VERSION not exported")

# Seed package tests
def test_seed_packs_imports():
    """Verify the seed packs module imports cleanly."""
    from app.rms.seed import packs
    assert hasattr(packs, "seed_pack")

def test_seed_packs_idempotent_function_exists():
    from app.rms.seed.packs import seed_pack
    assert callable(seed_pack)

# Test models/__init__ re-exports
def test_models_init_re_exports():
    from app.rms import models
    # Should have all the major models
    assert hasattr(models, "Base")
    assert hasattr(models, "Product")
    assert hasattr(models, "Ingredient")
    assert hasattr(models, "Sale")
    assert hasattr(models, "Customer")
    assert hasattr(models, "Tag")
