"""app.seed.kyrian — complete "Kyrian Weiss" demo seed.

Idempotent. Builds:

  - 1 Customer (full profile: phone/email/CI/notes/dietary/preferences/zone/birthday)
  - 2 CustomerAddress (casa default + oficina)
  - 1 Suscripcion (semanal, Saturdays, activa)
  - 6 Pedido (mix of fulfilled + cancelled, channels whatsapp/mostrador/pedidosya)
  - 18 PedidoLine (across the 6 pedidos; products chosen from real catalog)
  - 6 Sale (one per fulfilled pedido)
  - 6 LoyaltyTransaction (one earn per fulfilled sale)
  - 1 LoyaltyTransaction (manual_adjust seed bonus)

Idempotency: deletes prior Kyrian data by phone before inserting.

Run from a test:
    from app.seed.kyrian import seed_kyrian
    bundle = seed_kyrian(session)
    assert bundle.customer.name == "kyrian weiss"

Run on live (Phase 2):
    POST /demo/seed → {"customer_id": 9, "pedidos": 6, ...}

Why this exists: every operator screen should auto-fill from a complete
customer record. The seed makes that record exist (locally + on live via
the demo endpoint) so we can iterate on autofill UX against real data.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.rms.models import (
    Customer,
    CustomerAddress,
    DeliveryZone,
    LoyaltyTransaction,
    Pedido,
    PedidoLine,
    Product,
    Sale,
    Suscripcion,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Constants — exported so tests can reference the same identity
KYRIAN_NAME = "kyrian weiss"
KYRIAN_PHONE = "0982515138"
KYRIAN_EMAIL = "kyrianweiss.vdp@gmail.com"
KYRIAN_CEDULA = "5991039"
KYRIAN_TIER_GS = 494_000  # target lifetime spend for tier (Plata)
KYRIAN_LOYALTY_POINTS = 494  # 1pt / 1.000 Gs. spent


@dataclass
class KyrianBundle:
    """Return value of seed_kyrian(). Lets tests assert on the dataset."""

    customer: Customer
    addresses: list[CustomerAddress] = field(default_factory=list)
    suscripcion: Suscripcion | None = None
    pedidos: list[Pedido] = field(default_factory=list)
    sales: list[Sale] = field(default_factory=list)
    loyalty_ledger: list[LoyaltyTransaction] = field(default_factory=list)

    @property
    def lifetime_spent_gs(self) -> int:
        return sum(
            int(s.qty * s.unit_price_gs) for s in self.sales if s.voided_at is None
        )


# Catalog picks: use whatever products the DB already has (or insert
# basic ones if missing). These are the products the demo Kyrian "buys".
KYRIAN_FAVORITES = [
    # (product_name, qty, default_unit_price_gs) — used when product lookup
    # fails. These match the live catalog (from /pedidos/nuevo dropdown).
    ("Appeltaart", 1, 28_000),
    ("Babka de chocolate", 2, 44_000),
    ("Cheesecake entera", 2, 360_000),
    ("Cheesecake clásico", 1, 25_000),
    ("Cheesecake (20x20 cm)", 1, 9_000),
    ("Pan lactal", 1, 12_000),
    ("Stroopwafel", 6, 60_000),
]


def _delete_existing_kyrian(s: Session) -> None:
    """Wipe any prior Kyrian data so re-runs are clean.

    We cascade-delete by deleting the customer row. The Pedido/PedidoLine/
    Sale/LoyaltyTransaction FKs are loose (no ON DELETE CASCADE on every
    table in this schema), so we go in dependency order.

    Order matters:
      1. Sales first (Migration 076 added sale.linked_pedido_id FK;
         if we delete the pedido first, the FK on sale→pedido trips)
      2. Pedidos (cascade-deletes their lines)
      3. Loyalty transactions (FK to customer)
      4. Suscripcion (FK to customer)
      5. Customer last
    """
    existing = s.execute(
        select(Customer).where(Customer.phone == KYRIAN_PHONE)
    ).scalar_one_or_none()
    if existing is None:
        return

    cid = existing.id

    # Null out pedido.fulfilled_sale_id first — that FK has no
    # ON DELETE clause (legacy column), so deleting a Sale while a
    # Pedido still references it trips SQLite's NO ACTION.
    pedidos = s.execute(
        select(Pedido).where(Pedido.customer_id == cid)
    ).scalars().all()
    for p in pedidos:
        p.fulfilled_sale_id = None
    s.flush()

    # SaleStockMove next — has FK to sale (declared ON DELETE CASCADE on
    # the SQLAlchemy side, but SQLite tables created before that hint was
    # added may not have the cascade clause, so we delete them explicitly).
    from app.rms.models import SaleStockMove
    moves = s.execute(
        select(SaleStockMove).join(Sale, SaleStockMove.sale_id == Sale.id)
        .where(Sale.customer_id == cid)
    ).scalars().all()
    for m in moves:
        s.delete(m)
    s.flush()

    # Sales next — Migration 076 added sale.linked_pedido_id which FKs
    # to pedido, so we must clear sales BEFORE deleting pedidos.
    sales = s.execute(
        select(Sale).where(Sale.customer_id == cid)
    ).scalars().all()
    for sa in sales:
        s.delete(sa)
    s.flush()

    # PedidoLines cascade from Pedido via ORM cascade="all, delete-orphan"
    pedidos = s.execute(
        select(Pedido).where(Pedido.customer_id == cid)
    ).scalars().all()
    for p in pedidos:
        # Pedido.lines cascade-deletes
        s.delete(p)
    s.flush()

    # Loyalty transactions
    lts = s.execute(
        select(LoyaltyTransaction).where(LoyaltyTransaction.customer_id == cid)
    ).scalars().all()
    for lt in lts:
        s.delete(lt)
    s.flush()

    # Suscripcion (RESTRICT FK — delete first)
    subs = s.execute(
        select(Suscripcion).where(Suscripcion.customer_id == cid)
    ).scalars().all()
    for su in subs:
        s.delete(su)
    s.flush()

    # Addresses cascade-delete from customer
    s.flush()
    s.delete(existing)
    s.flush()


def _ensure_products(s: Session) -> dict[str, Product]:
    """Make sure the favorite products exist. Returns {name: Product}.

    If a product already exists by name, reuse it (don't duplicate). If
    not, create a minimal Product row (sale_price_gs only — recipe is
    optional for sales).
    """
    out: dict[str, Product] = {}
    for name, _qty, price in KYRIAN_FAVORITES:
        existing = s.execute(
            select(Product).where(Product.name == name)
        ).scalar_one_or_none()
        if existing is not None:
            out[name] = existing
            continue
        p = Product(name=name, sale_price_gs=price)
        s.add(p)
        s.flush()
        out[name] = p
    s.flush()
    return out


def _ensure_zone(s: Session, name: str = "Local") -> DeliveryZone | None:
    """Pick the first active delivery zone; fallback to a code-named Local.

    The live site already has a 'Local' zone (Gs. 10.000 cost, Gs. 30.000
    minimum). On a fresh test DB this just creates one if missing.
    """
    existing = s.execute(
        select(DeliveryZone).where(DeliveryZone.name == name)
    ).scalar_one_or_none()
    if existing:
        return existing
    # Try any zone
    any_zone = s.execute(select(DeliveryZone).limit(1)).scalar_one_or_none()
    if any_zone:
        return any_zone
    # Fresh DB: create a minimal Local zone
    z = DeliveryZone(
        code="local",
        name="Local",
        coverage_text="Mburucuyá centro",
        delivery_cost_gs=10_000,
        min_order_gs=30_000,
        is_active=True,
        position=1,
    )
    s.add(z)
    s.flush()
    return z


def seed_kyrian(s: Session) -> KyrianBundle:
    """Idempotent seed. Wipes prior Kyrian data, then builds the full bundle.

    Pass any Session (test or live). Commits are the caller's responsibility
    (the qseed fixture and the demo endpoint both commit at the end of
    their wrapping function).
    """
    # 1. Wipe any prior Kyrian data so re-runs are clean.
    _delete_existing_kyrian(s)

    # 2. Ensure products exist (we don't want the seed to depend on demo data).
    products = _ensure_products(s)
    zone = _ensure_zone(s)

    # 3. Customer — full profile.
    today = date.today()
    customer = Customer(
        name=KYRIAN_NAME,
        phone=KYRIAN_PHONE,
        email=KYRIAN_EMAIL,
        cedula=KYRIAN_CEDULA,
        notes=(
            "Alergia: frutos secos. "
            "Pide siempre para retirar después de las 15h. "
            "Le gustan los cheesecakes."
        ),
        loyalty_points=KYRIAN_LOYALTY_POINTS,
        preferred_zone_id=zone.id if zone else None,
        birthday="06-15",
        how_found="instagram",
        preferred_channel="whatsapp",
        marketing_consent=True,
        invoice_name=KYRIAN_NAME,
        invoice_ruc=KYRIAN_CEDULA,
        dietary_restrictions="sin frutos secos",
        dietary_preferences="sin lactosa",
        dietary_confirm_always=False,
    )
    s.add(customer)
    s.flush()

    # 4. Addresses.
    addr_casa = CustomerAddress(
        customer_id=customer.id,
        label="casa",
        address_text="Av. Mariscal López 1234 c/ Pai Pérez, Mburucuyá",
        zone_id=zone.id if zone else None,
        is_default=True,
    )
    addr_ofi = CustomerAddress(
        customer_id=customer.id,
        label="oficina",
        address_text="Edificio Villa Morra, Piso 7 of. 703",
        zone_id=zone.id if zone else None,
        is_default=False,
    )
    s.add_all([addr_casa, addr_ofi])
    s.flush()

    # 5. Subscription (semanal, Saturdays).
    suscripcion = Suscripcion(
        customer_id=customer.id,
        product_summary="1 kg chipa + 2 facturas (sábados)",
        cadence="semanal",
        preferred_day_of_week=6,  # Saturday (ISO 1-7)
        preferred_time="09:00",
        start_date=today - timedelta(days=30),
        price_gs=35_000,
        status="activa",
        notes="Llamar 30 min antes de llegar",
    )
    s.add(suscripcion)
    s.flush()

    # 6. Pedidos + PedidoLines + Sales + Loyalty.
    # Spread over 4 weeks leading up to today.
    # (offset_days, channel, status, [(product_name, qty, unit_price), ...])
    pedidos_spec = [
        # 0 days ago (today-ish, but we want a non-today most-recent to
        # make 'promised_date' default to today make sense)
        (
            -2,
            "whatsapp",
            "fulfilled",
            [
                ("Appeltaart", 1, 28_000),
                ("Cheesecake entera", 1, 180_000),
                ("Stroopwafel", 6, 60_000),
            ],
        ),
        (
            -5,
            "whatsapp",
            "fulfilled",
            [
                ("Babka de chocolate", 2, 44_000),
                ("Pan lactal", 1, 12_000),
            ],
        ),
        (
            -10,
            "mostrador",
            "fulfilled",
            [
                ("Appeltaart", 1, 28_000),
            ],
        ),
        (
            -15,
            "whatsapp",
            "cancelled",
            [
                ("Cheesecake clásico", 1, 25_000),
                ("Pan lactal", 1, 12_000),
            ],
        ),
        (
            -20,
            "pedidosya",
            "fulfilled",
            [
                ("Cheesecake entera", 1, 180_000),
                ("Appeltaart", 2, 56_000),
                ("Pan lactal", 2, 24_000),
            ],
        ),
        (
            -25,
            "whatsapp",
            "fulfilled",
            [
                ("Babka de chocolate", 1, 22_000),
                ("Cheesecake clásico", 1, 25_000),
                ("Pan lactal", 1, 12_000),
                ("Stroopwafel", 3, 30_000),
                ("Appeltaart", 1, 28_000),
            ],
        ),
    ]

    bundle = KyrianBundle(
        customer=customer,
        addresses=[addr_casa, addr_ofi],
        suscripcion=suscripcion,
    )

    for offset_days, channel, status, lines_spec in pedidos_spec:
        promised = today + timedelta(days=offset_days)
        promised_at = datetime.combine(promised, datetime.min.time())

        pedido = Pedido(
            customer_id=customer.id,
            customer_name=customer.name,
            customer_phone=customer.phone,
            promised_date=promised,
            promised_time="15:00",
            channel=channel,
            status=status,
            payment_intent="transferencia",
            delivery_zone_id=zone.id if zone else None,
            address_text=addr_casa.address_text,
            delivery_window_start="14:00",
            delivery_window_end="16:00",
            invoice_ruc=customer.invoice_ruc,
            invoice_name=customer.invoice_name,
            notes="Cliente VIP — preparar con cuidado." if status != "cancelled" else None,
            cancel_reason="Cliente avisó tarde" if status == "cancelled" else None,
            # public_token has a UNIQUE NOT NULL constraint; the model
            # default is "" which collides on multi-row inserts. Generate
            # a real URL-safe token (same as the production /pedidos
            # router — 96 bits of entropy, no collision risk).
            public_token=secrets.token_urlsafe(16),
            public_token_expires_at=(
                promised_at + timedelta(days=30) if status != "cancelled" else None
            ),
        )
        s.add(pedido)
        s.flush()

        # Lines
        total_gs = 0
        for prod_name, qty, unit_price in lines_spec:
            product = products[prod_name]
            line = PedidoLine(
                pedido_id=pedido.id,
                product_id=product.id,
                qty=float(qty),
                unit_price_gs=unit_price,
                fulfilled_qty=float(qty) if status == "fulfilled" else 0.0,
            )
            s.add(line)
            total_gs += qty * unit_price

        # Fulfilled status: set fulfilled_at + linked sale
        if status == "fulfilled":
            pedido.fulfilled_at = promised_at + timedelta(hours=15)
            # The first sale is the "main" sale — for multi-line pedidos we
            # create one sale per line (matches existing apply_sale semantics).
            for prod_name, qty, unit_price in lines_spec:
                product = products[prod_name]
                sale = Sale(
                    customer_id=customer.id,
                    product_id=product.id,
                    qty=float(qty),
                    unit_price_gs=unit_price,
                    sold_at=pedido.fulfilled_at,
                    channel=channel,
                    payment_method="transferencia",
                    discount_gs=0,
                    # Migration 076 — back-pointer to the source pedido
                    # so pedido.sales works symmetrically.
                    linked_pedido_id=pedido.id,
                )
                s.add(sale)
                s.flush()

                # Wire pedido.fulfilled_sale_id to the first sale
                if pedido.fulfilled_sale_id is None:
                    pedido.fulfilled_sale_id = sale.id

                bundle.sales.append(sale)

                # Loyalty: 1pt / 1.000 Gs. spent
                earned = int((qty * unit_price) // 1000)
                if earned > 0:
                    lt = LoyaltyTransaction(
                        customer_id=customer.id,
                        delta=earned,
                        reason="earn_sale",
                        sale_id=sale.id,
                        actor="system",
                        recorded_at=sale.sold_at,
                        notes=f"Earned from sale #{sale.id}",
                    )
                    s.add(lt)
                    bundle.loyalty_ledger.append(lt)

        bundle.pedidos.append(pedido)

    # 7. One manual loyalty adjustment — a birthday bonus.
    bonus = LoyaltyTransaction(
        customer_id=customer.id,
        delta=50,
        reason="manual_adjust",
        actor="operator",
        notes="Cumpleaños — bonus del 15/06",
        recorded_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10),
    )
    s.add(bonus)
    bundle.loyalty_ledger.append(bonus)

    # 8. One redeem — Kyrian traded 100 pts for a free factura docena.
    redeem = LoyaltyTransaction(
        customer_id=customer.id,
        delta=-100,
        reason="redeem",
        actor="operator",
        notes="Canje: 1 docena de facturas gratis",
        recorded_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3),
    )
    s.add(redeem)
    bundle.loyalty_ledger.append(redeem)

    # Adjust cached balance to match ledger sum (idempotent: ledger sum wins)
    balance = sum(lt.delta for lt in bundle.loyalty_ledger)
    customer.loyalty_points = balance

    s.flush()
    return bundle
