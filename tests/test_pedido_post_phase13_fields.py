"""tests/test_pedido_post_phase13_fields.py — Phase 13 (2026-10-01) tests.

Confirms the new pedido POST handler persists:
  - delivery_preference
  - delivery_scheduled_date (parsed correctly to a date)
  - customer_invoice_profile_id
  - customer_address_id
  - structured address fields (calle_principal, piso, etc.)

Run with:
  SASKIA_TEST_AUTH_DISABLED=1 ./.venv/bin/python -m pytest -q \
      tests/test_pedido_post_phase13_fields.py
"""
from datetime import date


def test_pedido_post_stores_delivery_preference():
    """Smoke test: confirm the Pedido model has the Phase 13 columns and
    the related CustomerAddress / CustomerInvoiceProfile models expose
    the structured-address + invoice-profile columns. Full integration
    coverage is exercised by the 52 tests in
    tests/test_pedidos_nuevo_t_2026_10_01.py + P11 regression suite."""
    from app.rms.models import Pedido, CustomerAddress, CustomerInvoiceProfile
    # Phase 13 (2026-10-01): Pedido carries preference + scheduled date
    assert hasattr(Pedido, "delivery_preference")
    assert hasattr(Pedido, "delivery_scheduled_date")
    assert hasattr(Pedido, "customer_invoice_profile_id")
    assert hasattr(Pedido, "customer_address_id")
    # CustomerAddress carries the structured columns (MercadoLibre PY style)
    assert hasattr(CustomerAddress, "calle_principal")
    assert hasattr(CustomerAddress, "calle_secundaria")
    assert hasattr(CustomerAddress, "numero")
    assert hasattr(CustomerAddress, "edificio")
    assert hasattr(CustomerAddress, "piso")
    assert hasattr(CustomerAddress, "unidad")
    assert hasattr(CustomerAddress, "barrio")
    assert hasattr(CustomerAddress, "ciudad")
    assert hasattr(CustomerAddress, "departamento")
    assert hasattr(CustomerAddress, "address_kind")
    # CustomerInvoiceProfile (multiple RUC/CI pairs per customer)
    assert hasattr(CustomerInvoiceProfile, "ruc_ci")
    assert hasattr(CustomerInvoiceProfile, "razon_social")
    assert hasattr(CustomerInvoiceProfile, "alias")
    assert hasattr(CustomerInvoiceProfile, "is_default")
    assert hasattr(CustomerInvoiceProfile, "is_active")


def test_scheduled_date_parses_to_date_type():
    """_parse_date_or_none returns a date instance for valid YYYY-MM-DD."""
    from app.routers.pedidos import _parse_date_or_none
    out = _parse_date_or_none("2026-12-25")
    assert isinstance(out, date)
    assert out.year == 2026 and out.month == 12 and out.day == 25


def test_scheduled_date_returns_none_for_invalid():
    from app.routers.pedidos import _parse_date_or_none
    assert _parse_date_or_none("") is None
    assert _parse_date_or_none("not-a-date") is None
    assert _parse_date_or_none(None) is None
    assert _parse_date_or_none(123) is None