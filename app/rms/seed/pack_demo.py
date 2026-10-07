"""Pack-native demo life: customers, pedidos, sales history for seeded packs.

Complements seed/packs.py (GENERATED — do not hand-edit): this module is
hand-written and works on whatever products the pack seeded, so a demo
tenant gets Vaquita-grade history WITHOUT demo.py's bakery-specific catalog
(muffins, appeltaart, …) leaking into a pizzería or café demo.

Usage (inside the running container):
    python -m app.rms.seed.pack_demo --pack "Pizzería"
    python -m app.rms.seed.pack_demo --list

Programmatic:
    from app.rms.seed.pack_demo import seed_pack_demo
    seed_pack_demo(session, days_of_history=90)
"""

from __future__ import annotations

import argparse
import math
import random
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal as _D

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.rms.models.channels import Channel

from app.rms.models import (
    Customer,
    DeliveryZone,
    Pedido,
    PedidoLine,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    StockMovement,
)

# --------------------------------------------------------------------------
# Name pools (Paraguay-flavored)
# --------------------------------------------------------------------------

_FIRST = [
    "Marta", "Ramón", "Lourdes", "Derlis", "Cándido", "Norma", "Blas",
    "Mirian", "Carlos", "Édgar", "Rosa", "Hugo", "Lidia", "Ariel",
    "Mirtha", "Óscar", "Perla", "Fernando", "Silvia", "Aníbal",
]
_LAST = [
    "González", "Benítez", "Villalba", "Cáceres", "Acosta", "Ferreira",
    "Ramírez", "Ortiz", "Mendoza", "Aguilar", "Franco", "Tapia",
    "Ruiz Díaz", "Espínola", "Ojeda", "Sanabria", "Domínguez", "Galeano",
]
_STREETS = [
    "Palma", "Av. Mcal. López", "Av. España", "Chile", "Yegros",
    "Sacramental", "Caaguazú", "Av. Sacramento", "Humaitá", "Benjamín Constant",
]
_NOTES = [
    "sin cebolla",
    "para llevar",
    "entrega en oficina, piso 3",
    "cumpleaños: agregar velas",
    "cliente frecuente",
    "factura con RUC",
    "pagará con QR",
    "confirmar por WhatsApp antes de salir",
    "media docena",
    "extra queso",
    "sin gluten (cel disease)",
    "dejar en recepción",
]


def _public_token(rng: random.Random) -> str:
    return secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")[:8]


# --------------------------------------------------------------------------
# seed_pack_demo
# --------------------------------------------------------------------------


def seed_pack_demo(
    session: Session,
    *,
    days_of_history: int = 90,
    sales_per_day: int = 8,
    pedidos_total: int = 28,
    customers_total: int = 42,
    seed: int | None = 42,
) -> dict:
    """Generate customers + pedidos + sales history over the pack's products.

    Idempotency: if the DB already has ANY sale, this is a no-op (returns
    ``{"skipped": True}``) — demo life is seeded once onto a fresh pack.
    Deterministic for a given ``seed``.
    """
    rng = random.Random(seed)

    existing_sale = session.execute(select(Sale.id).limit(1)).scalar_one_or_none()
    if existing_sale is not None:
        return {"skipped": True, "reason": "ya existen ventas"}

    products = list(session.execute(select(Product)).scalars())
    if not products:
        raise ValueError("No hay productos: corré seed_pack(session, pack) primero")

    recipes_by_id = {r.id: r for r in session.execute(select(Recipe)).scalars()}
    lines_by_recipe: dict[int, list[RecipeLine]] = {}
    for line in session.execute(select(RecipeLine)).scalars():
        lines_by_recipe.setdefault(line.recipe_id, []).append(line)
    zones = list(session.execute(select(DeliveryZone)).scalars())

    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    report = {"customers": 0, "sales": 0, "stock_moves": 0, "pedidos": 0, "pedido_lines": 0}

    # --- customers -------------------------------------------------------
    used_names: set[str] = set()
    customers: list[Customer] = []
    for _i in range(customers_total):
        while True:
            name = f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"
            if name not in used_names:
                used_names.add(name)
                break
        cust = Customer(
            name=name,
            phone=f"+5959{rng.randint(71000000, 99999999)}",
            zone=rng.choice(["Centro", "Villa Aurelia", "Sajonia", "Manorá", "Lambaré"]),
            preferred_channel=rng.choices(["whatsapp", "phone", "instagram"], weights=[70, 20, 10])[0],
            marketing_consent=rng.random() < 0.6,
            created_at=now - timedelta(days=rng.randint(30, 200)),
        )
        session.add(cust)
        customers.append(cust)
    session.flush()
    report["customers"] = len(customers)

    # --- sales history (weekday/payday skew, hour weights) ---------------
    sale_dates = [now - timedelta(days=d) for d in range(days_of_history, 0, -1)]
    for sale_date in sale_dates:
        weekday = sale_date.weekday()
        base = sales_per_day
        if weekday >= 5:
            base = math.ceil(base * 1.4)
        if sale_date.day in (1, 15):
            base = math.ceil(base * 1.6)
        count = max(1, int(base + rng.randint(-2, 2)))

        for _ in range(count):
            product = rng.choice(products)
            hour = rng.choices(
                [8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20],
                weights=[2, 3, 3, 3, 4, 3, 3, 3, 3, 3, 2, 1],
            )[0]
            sold_at = sale_date.replace(hour=hour, minute=rng.randint(0, 59))
            qty = rng.choices([1, 2, 3, 6, 12], weights=[65, 15, 8, 7, 5])[0]
            sale = Sale(
                sold_at=sold_at,
                product_id=product.id,
                qty=qty,
                unit_price_gs=product.sale_price_gs,
                notes=rng.choice(_NOTES) if rng.random() < 0.12 else None,
            )
            session.add(sale)
            session.flush()

            recipe_id = product.recipe_id
            if recipe_id and recipe_id in lines_by_recipe:
                recipe = recipes_by_id[recipe_id]
                yield_d = _D(str(recipe.yield_qty or 1.0))
                qty_d = _D(str(qty))
                for line in lines_by_recipe[recipe_id]:
                    need = (line.qty / yield_d) * qty_d
                    session.add(
                        StockMovement(
                            movement_type="sale",
                            ingredient_id=line.line_ref_id,
                            qty=need,
                            reference_id=sale.id,
                            reference_type="sale",
                            affected_recipe_id=recipe_id,
                            recorded_at=sold_at,
                        )
                    )
                    report["stock_moves"] += 1
            report["sales"] += 1

    # --- pedidos (pre-orders via WhatsApp etc.) --------------------------
    # P43 (2026-10-07): use Channel enum values. "phone" was a legacy
    # alias not in the canonical enum, so the migration 111 DB CHECK
    # would reject any pedido.channel="phone" write. Map the legacy
    # "phone" traffic to Channel.OTHER.value so the demo seed still
    # exercises the same volume but with valid enum values.
    channels = [
        Channel.WHATSAPP.value, Channel.WHATSAPP.value, Channel.WHATSAPP.value,
        Channel.MOSTRADOR.value, Channel.OTHER.value, Channel.PEDIDOSYA.value,
    ]
    payments = ["efectivo", "efectivo", "qr", "transferencia", "tarjeta"]
    for _i in range(pedidos_total):
        age_days = rng.randint(1, days_of_history - 1)
        promised = (now - timedelta(days=age_days)).date() if age_days > 2 else (now + timedelta(days=rng.randint(1, 3))).date()
        cust = rng.choice(customers)
        if age_days <= 2:
            status = rng.choices(["pending", "confirmed", "ready"], weights=[30, 50, 20])[0]
        elif age_days <= 7:
            status = rng.choices(["confirmed", "fulfilled"], weights=[25, 75])[0]
        else:
            status = rng.choices(["fulfilled", "cancelled"], weights=[90, 10])[0]

        token = _public_token(rng)
        while (
            session.execute(select(Pedido.id).where(Pedido.public_token == token).limit(1))
            .scalar_one_or_none()
            is not None
        ):
            token = _public_token(rng)

        pedido = Pedido(
            customer_id=cust.id,
            customer_name=cust.name,
            customer_phone=cust.phone,
            promised_date=promised,
            promised_time=rng.choice(["09:00", "11:00", "14:00", "16:00", "18:00"]),
            channel=rng.choice(channels),
            status=status,
            payment_intent=rng.choice(payments),
            notes=rng.choice(_NOTES),
            public_token=token,
            public_token_expires_at=now + timedelta(days=30),
            created_at=now - timedelta(days=age_days, hours=rng.randint(2, 20)),
            updated_at=now - timedelta(days=age_days),
            delivery_zone_id=rng.choice(zones).id if zones and rng.random() < 0.35 else None,
            address_text=f"{rng.choice(_STREETS)} {rng.choice(['casa', 'e/ calles', 'edif.'])} {rng.randint(100, 999)}"
            if rng.random() < 0.4
            else None,
        )
        if status == "fulfilled":
            pedido.fulfilled_at = pedido.created_at + timedelta(hours=rng.randint(2, 30))
        session.add(pedido)
        session.flush()

        for _ in range(rng.randint(1, 4)):
            product = rng.choice(products)
            session.add(
                PedidoLine(
                    pedido_id=pedido.id,
                    product_id=product.id,
                    qty=float(rng.choices([1, 2, 3, 6, 12], weights=[60, 18, 10, 7, 5])[0]),
                    unit_price_gs=int(product.sale_price_gs),
                )
            )
            report["pedido_lines"] += 1
        report["pedidos"] += 1

    session.flush()
    return report


# --------------------------------------------------------------------------
# reseed: wipe tenant data and re-seed with a chosen pack (CLI / demo switch)
# --------------------------------------------------------------------------

def reseed_pack(session: Session, pack: str, *, days_of_history: int = 90) -> dict:
    """Reset the demo DB (ALL data) and seed ``pack`` with full demo life.

    Wipes every table in the metadata (children first, so FKs never block)
    and rebuilds from the pack: tenant, admin user, catalog, suppliers,
    production templates + 90 days of demo life. Deterministic; NOT for a
    tenant with real data.
    """
    from app.rms.seed.packs import seed_pack

    # Wipe EVERY table (sqlite_master = DB truth; metadata misses migration-only
    # tables). FK pragma is a no-op inside a transaction → dedicated AUTOCOMMIT
    # connection, independent of the session's transaction state.
    engine = session.get_bind()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        names = [r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ))]
        for name in names:
            conn.execute(text(f'DELETE FROM "{name}"'))  # noqa: S608 - sqlite_master-derived name
        conn.execute(text("PRAGMA foreign_keys = ON"))
    session.expire_all()

    pack_report = seed_pack(session, pack)
    demo_report = seed_pack_demo(session, days_of_history=days_of_history)
    session.commit()
    return {"pack": pack_report.__dict__.get("pack", pack), "demo": demo_report}


def _norm_key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalnum())


def _resolve_pack(query: str) -> str:
    """Match 'pizzeria' / 'cafe' / 'Pizzería' → canonical PACKS key."""
    from app.rms.seed.packs import PACKS

    keys = {_norm_key(p): p for p in PACKS}
    q = _norm_key(query)
    if q in keys:
        return keys[q]
    for k, p in sorted(keys.items()):
        if q and (q in k or k.startswith(q)):
            return p
    raise ValueError(f"pack no encontrado: {query!r}")


def main() -> None:  # pragma: no cover - CLI
    import os

    from app.rms.db import make_engine, make_session_factory
    from app.rms.seed.packs import PACKS

    ap = argparse.ArgumentParser(description="Switch the demo DB to a market pack")
    ap.add_argument("--pack", help=f"one of: {', '.join(sorted(PACKS))}")
    ap.add_argument("--list", action="store_true", help="list available packs")
    ap.add_argument("--days", type=int, default=90)
    args = ap.parse_args()

    pack_arg = args.pack or os.environ.get("AIW_DEMO_PACK", "")
    if args.list or not pack_arg:
        print("\n".join(sorted(PACKS)))
        return

    pack = _resolve_pack(pack_arg)
    engine = make_engine()
    with make_session_factory(engine)() as session:
        result = reseed_pack(session, pack, days_of_history=args.days)
        print(f"demo re-seeded → {pack}: {result['demo']}")


if __name__ == "__main__":  # pragma: no cover
    main()
