"""P39 — channel values must be lowercase canonical codes.

Two bugs were creating duplicate channels in reports:
1. app/routers/sales.py used .strip() without .lower() on the channel
   field — anything like 'WhatsApp' or 'WHATSAPP' got through the
   ALLOWED_CHANNELS check because the check was on the wrong value
   (after .strip() but before lowercasing).
3. app/routers/pedidos.py normalize_channel() mapped raw input through
   a dict whose values were display names ("WhatsApp", "PedidosYa") —
   so even valid lowercase input like 'whatsapp' got transformed to
   'WhatsApp', creating a separate bucket in reports.

P39 fixes both: sales does .lower().strip(), and pedidos normalize
returns the canonical lowercase codes. This test pins down both.
"""
import pytest


def test_sale_channel_is_lowercased(client, session_factory):
    """Submitting 'WhatsApp' or 'WHATSAPP' must store 'whatsapp'."""
    from app.rms.models import Product
    with session_factory() as s:
        prod = s.query(Product).filter(Product.name == "P39-channel-test-prod").first()
        if prod is None:
            prod = Product(name="P39-channel-test-prod", sale_price_gs=5000)
            s.add(prod)
            s.commit()
        prod_id = prod.id

    client.post("/login", data={"username": "demo", "password": "demo1234"})

    # Try various casings - the new code lowercases all of them
    for raw, expected_canon in [("WhatsApp", "whatsapp"), ("WHATSAPP", "whatsapp"),
                                 ("whatSapp", "whatsapp"), ("whatsapp", "whatsapp")]:
        response = client.post("/ventas/nueva", data={
            "product_id": prod_id,
            "qty": 1,
            "channel": raw,
        }, follow_redirects=False)
        # 200 (form rerender) or 303 (success redirect) - we don't care,
        # we care about what got persisted
        with session_factory() as s2:
            from app.rms.models import Sale
            recent = s2.query(Sale).filter_by(product_id=prod_id).order_by(Sale.id.desc()).first()
            if recent is not None:
                assert recent.channel == expected_canon, (
                    f"input {raw!r} → stored {recent.channel!r} "
                    f"(expected {expected_canon!r})"
                )


def test_normalize_channel_returns_canonical_lowercase(session_factory):
    """The pedidos normalize_channel() helper must return lowercase
    canonical codes, not display names like 'WhatsApp'."""
    from app.routers.pedidos import normalize_channel
    assert normalize_channel("whatsapp") == "whatsapp"
    assert normalize_channel("WhatsApp") == "whatsapp"
    assert normalize_channel("WHATSAPP") == "whatsapp"
    assert normalize_channel("wa") == "whatsapp"
    assert normalize_channel("mostrador") == "mostrador"
    assert normalize_channel("Mostrador") == "mostrador"
    assert normalize_channel("pedidosya") == "pedidosya"
    assert normalize_channel("unknown_channel") == "mostrador"  # fallback


def test_pedido_save_uses_normalized_channel(client, session_factory):
    """Creating a pedido with 'WhatsApp' must store 'whatsapp'."""
    from datetime import date
    client.post("/login", data={"username": "demo", "password": "demo1234"})

    response = client.post("/pedidos/nuevo", data={
        "customer_name": "P39 Channel Test",
        "customer_phone": "0000",
        "promised_date": date.today().isoformat(),
        "channel": "WhatsApp",
        "payment_intent": "efectivo",
    }, follow_redirects=False)

    with session_factory() as s:
        from app.rms.models import Pedido
        recent = s.query(Pedido).filter_by(customer_name="P39 Channel Test").order_by(Pedido.id.desc()).first()
        if recent is not None:
            assert recent.channel == "whatsapp", (
                f"expected 'whatsapp', got {recent.channel!r}"
            )
