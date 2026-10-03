"""tests/test_invoicing.py — Phase 1.B fiscal invoice snapshot + numbering."""
from __future__ import annotations

import pytest

from app.rms.invoicing import allocate_invoice_number, compute_invoice_snapshot
from app.rms.models import ComplianceInfo, Product


@pytest.fixture
def seed_product(session_factory):
    """Seed a product for invoicing tests."""
    Session = session_factory

    def _seed(name="Muffin test", price=25000, iva_rate="10"):
        with Session() as s:
            p = Product(
                name=name,
                sale_price_gs=price,
                portion_label="1 und",
                iva_rate=iva_rate,
            )
            s.add(p)
            s.commit()
            s.refresh(p)
            return p.id

    return _seed


class TestInvoiceSnapshotResimple:
    """Boleta Resimple: IRE covered by fixed quarterly cuota — no IVA itemization."""

    def test_boleta_resimple_returns_zero_iva(self, session_factory, seed_product):
        product_id = seed_product(price=25000, iva_rate="10")
        Session = session_factory
        with Session() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=1, unit_price_gs=25000,
                discount_gs=0, invoice_type="boleta_resimple",
            )
        assert snap["iva_rate"] == "0"
        assert snap["iva_base_gs"] == 0
        assert snap["iva_amount_gs"] == 0

    def test_boleta_resimple_quantity_2(self, session_factory, seed_product):
        product_id = seed_product(price=25000, iva_rate="10")
        with session_factory() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=2, unit_price_gs=25000,
                discount_gs=0, invoice_type="boleta_resimple",
            )
        assert snap["iva_amount_gs"] == 0

    def test_boleta_resimple_ignores_product_iva_rate(self, session_factory, seed_product):
        """Even if product is iva_rate=10, RESIMPLE shows 0."""
        product_id = seed_product(price=25000, iva_rate="10")
        with session_factory() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=1, unit_price_gs=25000,
                discount_gs=0, invoice_type="boleta_resimple",
            )
        assert snap["iva_rate"] == "0"
        assert snap["iva_amount_gs"] == 0


class TestInvoiceSnapshotFactura:
    """Factura (IVA General): itemized IVA on the comprobante."""

    def test_factura_10pct_one_unit(self, session_factory, seed_product):
        """1 × 25000 = 25000 total. Base = 25000/1.10 = 22727. IVA = 2273."""
        product_id = seed_product(price=25000, iva_rate="10")
        with session_factory() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=1, unit_price_gs=25000,
                discount_gs=0, invoice_type="factura",
            )
        assert snap["iva_rate"] == "10"
        assert snap["iva_base_gs"] == 22727
        assert snap["iva_amount_gs"] == 2273
        assert snap["iva_base_gs"] + snap["iva_amount_gs"] == 25000

    def test_factura_5pct(self, session_factory, seed_product):
        """25000 at 5% → base 23810, IVA 1190."""
        product_id = seed_product(price=25000, iva_rate="5")
        with session_factory() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=1, unit_price_gs=25000,
                discount_gs=0, invoice_type="factura",
            )
        assert snap["iva_rate"] == "5"
        assert snap["iva_base_gs"] == 23810
        assert snap["iva_amount_gs"] == 1190

    def test_factura_exento(self, session_factory, seed_product):
        """exento → iva_amount=0, base=full amount."""
        product_id = seed_product(price=25000, iva_rate="exento")
        with session_factory() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=1, unit_price_gs=25000,
                discount_gs=0, invoice_type="factura",
            )
        assert snap["iva_rate"] == "exento"
        assert snap["iva_base_gs"] == 25000
        assert snap["iva_amount_gs"] == 0

    def test_factura_with_discount(self, session_factory, seed_product):
        """1 × 25000 - 1000 discount = 24000 net. Base 21818, IVA 2182."""
        product_id = seed_product(price=25000, iva_rate="10")
        with session_factory() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=1, unit_price_gs=25000,
                discount_gs=1000, invoice_type="factura",
            )
        assert snap["iva_base_gs"] == 21818
        assert snap["iva_amount_gs"] == 2182
        assert snap["iva_base_gs"] + snap["iva_amount_gs"] == 24000

    def test_factura_quantity_3(self, session_factory, seed_product):
        """3 × 10000 = 30000 at 10% → base 27273, IVA 2727."""
        product_id = seed_product(price=10000, iva_rate="10")
        with session_factory() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=3, unit_price_gs=10000,
                discount_gs=0, invoice_type="factura",
            )
        assert snap["iva_base_gs"] == 27273
        assert snap["iva_amount_gs"] == 2727

    def test_factura_uses_compliance_default_when_product_rate_empty(self, session_factory):
        """If product has iva_rate='', fall back to ComplianceInfo.iva_default_rate."""
        Session = session_factory
        with Session() as s:
            # Set the compliance default to 5%
            ci = s.get(ComplianceInfo, 1)
            ci.iva_default_rate = "5"
            p = Product(name="Default-test", sale_price_gs=10000, portion_label="1 und", iva_rate="")
            s.add(p)
            s.commit()
            pid = p.id
        with Session() as s:
            snap = compute_invoice_snapshot(
                s, product_id=pid, qty=1, unit_price_gs=10000,
                discount_gs=0, invoice_type="factura",
            )
        assert snap["iva_rate"] == "5"


class TestInvoiceSnapshotNone:
    """invoice_type='none' = no fiscal document. All zeros."""

    def test_none_returns_zeros(self, session_factory, seed_product):
        product_id = seed_product(price=25000)
        with session_factory() as s:
            snap = compute_invoice_snapshot(
                s, product_id=product_id, qty=1, unit_price_gs=25000,
                discount_gs=0, invoice_type="none",
            )
        assert snap["iva_rate"] == "0"
        assert snap["iva_base_gs"] == 0
        assert snap["iva_amount_gs"] == 0


class TestAllocateInvoiceNumber:
    """Atomic counter increment per invoice type."""

    def test_first_boleta_is_number_1(self, session_factory):
        Session = session_factory
        with Session() as s:
            n = allocate_invoice_number(s, "boleta_resimple")
            assert n == 1
            s.commit()
        with Session() as s:
            assert s.get(ComplianceInfo, 1).next_boleta_resimple_number == 2

    def test_sequential_boletas(self, session_factory):
        Session = session_factory
        numbers = []
        for _ in range(5):
            with Session() as s:
                numbers.append(allocate_invoice_number(s, "boleta_resimple"))
                s.commit()
        assert numbers == [1, 2, 3, 4, 5]

    def test_first_factura_is_number_1(self, session_factory):
        Session = session_factory
        with Session() as s:
            n = allocate_invoice_number(s, "factura")
            assert n == 1
            s.commit()
        with Session() as s:
            assert s.get(ComplianceInfo, 1).next_factura_number == 2

    def test_boleta_and_factura_counters_independent(self, session_factory):
        Session = session_factory
        with Session() as s:
            assert allocate_invoice_number(s, "boleta_resimple") == 1
            s.commit()
        with Session() as s:
            assert allocate_invoice_number(s, "factura") == 1
            s.commit()
        with Session() as s:
            assert allocate_invoice_number(s, "boleta_resimple") == 2
            s.commit()

    def test_unknown_type_raises(self, session_factory):
        with session_factory() as s:
            with pytest.raises(ValueError, match="Cannot allocate"):
                allocate_invoice_number(s, "invalid_type")


class TestSaleInvoiceFieldsRoundTrip:
    """Sale model persists all Phase 1.B fields."""

    def test_sale_persists_invoice_snapshot(self, session_factory, seed_product):
        from datetime import datetime, timezone

        from app.rms.models import Sale

        Session = session_factory
        product_id = seed_product(price=25000, iva_rate="10")
        with Session() as s:
            sale = Sale(
                product_id=product_id,
                qty=1,
                unit_price_gs=25000,
                sold_at=datetime.now(timezone.utc),
                invoice_type="factura",
                invoice_number=42,
                invoice_customer_ruc="80012345-6",
                invoice_customer_name="Test S.A.",
                iva_rate="10",
                iva_base_gs=22727,
                iva_amount_gs=2273,
            )
            s.add(sale)
            s.commit()
            s.refresh(sale)
            assert sale.invoice_type == "factura"
            assert sale.invoice_number == 42
            assert sale.invoice_customer_ruc == "80012345-6"
            assert sale.iva_base_gs == 22727
            assert sale.iva_amount_gs == 2273
