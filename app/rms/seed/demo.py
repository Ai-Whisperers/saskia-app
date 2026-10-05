"""app/rms/seed.py — Idempotent realistic-data seeder for demos / first-run.

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E6.

Inserts:
- 30 universal bakery ingredients (standard Paraguayan panadería pantry)
- 12 standard bakery recipes (muffin, cheesecake, hojaldre, etc.)
- 20 sellable products tied to recipes
- ~80 recipe_lines (standard baking ratios)
- 200 synthetic sales over 90 days with weekday/weekend skew + payday spikes
- ~200 stock moves tied to the sales
- 1 demo user (demo@herbus.local / demo1234, bcrypt)
- 1 voided_sale example with notes
- 1 "encargo" (custom order) sale example
- 1 import_batch row with row_counts_json
- 2 audit_log rows (system.startup + seed.complete)

Idempotency:
- Default: skip rows that already exist (match by natural key)
- overwrite=True: delete all seeded rows (matched by name) and re-insert

No PII; safe to commit. Currency: Paraguayan guaraní (Gs.).
"""

from __future__ import annotations

import math
import random
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.rms.audit import record as audit_record
from app.rms.models import (
    AppMeta,
    Customer,
    ImportBatch,
    Ingredient,
    MarketBenchmark,
    Pedido,
    PedidoLine,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    StockMovement,
    User,
)
from app.rms.models.channels import Channel
from app.rms.tagging import TagKind, ensure_starter_tags, ensure_tag, tag_target

# Use UTC-naive datetime columns consistently with existing models.
# Sale.sold_at is DateTime without tz; we store UTC-naive.

DEMO_USER_EMAIL = "demo@herbus.local"
DEMO_USER_PASSWORD = "demo1234"  # noqa: S105 — seed/demo credentials, not a real password
DEMO_USER_USERNAME = "demo"

# Realistic Paraguayan bakery ingredients.
# (name, unit, stock_qty, purchase_price_gs_per_unit, min_stock_qty, shelf_life_days)
INGREDIENTS: list[tuple[str, str, float, int, float, int]] = [
    # Dry / pantry staples
    ("harina", "kg", 25.0, 4500, 5.0, 90),
    ("azúcar", "kg", 12.0, 5200, 3.0, 365),
    ("sal", "kg", 2.0, 1800, 0.5, 1825),
    ("levadura", "kg", 0.8, 22000, 0.3, 30),
    ("polvo de hornear", "kg", 0.5, 18000, 0.2, 365),
    ("bicarbonato", "kg", 0.3, 12000, 0.1, 1825),
    ("azúcar impalpable", "kg", 1.5, 9500, 0.5, 365),
    ("cacao en polvo", "kg", 0.6, 28000, 0.3, 365),
    ("almendra molida", "kg", 0.4, 85000, 0.2, 180),
    ("maicena", "kg", 1.0, 8500, 0.3, 365),
    # Dairy
    ("manteca", "kg", 4.0, 32000, 1.0, 60),
    ("leche entera", "l", 12.0, 7800, 4.0, 7),
    ("crema de leche", "l", 3.0, 18500, 1.0, 14),
    ("queso crema", "kg", 2.5, 38000, 0.8, 21),
    ("huevos", "und", 60.0, 600, 24.0, 21),
    # Sweet
    ("dulce de leche", "kg", 3.0, 28000, 0.8, 30),
    ("leche condensada", "kg", 1.5, 18500, 0.5, 180),
    ("miel", "kg", 0.5, 35000, 0.2, 1825),
    # Flavor
    ("esencia de vainilla", "ml", 250.0, 80, 50.0, 365),
    ("canela molida", "g", 100.0, 50, 20.0, 365),
    ("ralladura de limón", "g", 50.0, 120, 10.0, 30),
    ("ralladura de naranja", "g", 50.0, 120, 10.0, 30),
    # Add-ins
    ("chocolate chips", "kg", 1.5, 32000, 0.5, 180),
    ("nueces", "kg", 0.6, 65000, 0.3, 120),
    ("pasas de uva", "kg", 0.5, 22000, 0.3, 180),
    ("coco rallado", "kg", 0.4, 28000, 0.2, 180),
    ("frutillas", "kg", 1.5, 22000, 0.5, 5),
    ("arándanos", "kg", 0.8, 38000, 0.3, 7),
    # Fat / liquid
    ("aceite vegetal", "l", 5.0, 12500, 1.0, 365),
    ("agua", "l", 30.0, 0, 5.0, 365),
]

# 12 standard bakery recipes. (name, yield_qty, yield_unit, prep_minutes)
RECIPES: list[tuple[str, float, str, int]] = [
    ("muffin_vainilla", 12.0, "und", 35),
    ("muffin_chocolate", 12.0, "und", 35),
    ("muffin_nueces", 12.0, "und", 40),
    ("cheesecake", 8.0, "und", 90),
    ("hojaldre_dulce", 16.0, "und", 120),
    ("appeltaart", 8.0, "und", 90),
    ("tompoezen", 12.0, "und", 60),
    ("oliebollen", 24.0, "und", 45),
    ("babka", 10.0, "und", 180),
    ("stroopwafel", 24.0, "und", 60),
    ("pan_lactal", 2.0, "und", 180),
    ("facturas", 24.0, "und", 180),
]

# Recipe lines. (recipe_name, ingredient_name, qty, unit) — note qty is in INGREDIENT units.
# Total per recipe should yield the recipe.yield_qty.
RECIPE_LINES: list[tuple[str, str, float]] = [
    # muffin_vainilla (12 und)
    ("muffin_vainilla", "harina", 0.350),  # 350g
    ("muffin_vainilla", "azúcar", 0.180),
    ("muffin_vainilla", "manteca", 0.120),
    ("muffin_vainilla", "huevos", 2),
    ("muffin_vainilla", "leche entera", 0.180),
    ("muffin_vainilla", "polvo de hornear", 0.008),
    ("muffin_vainilla", "esencia de vainilla", 5),
    # muffin_chocolate
    ("muffin_chocolate", "harina", 0.350),
    ("muffin_chocolate", "azúcar", 0.200),
    ("muffin_chocolate", "cacao en polvo", 0.050),
    ("muffin_chocolate", "manteca", 0.120),
    ("muffin_chocolate", "huevos", 2),
    ("muffin_chocolate", "leche entera", 0.180),
    ("muffin_chocolate", "polvo de hornear", 0.008),
    ("muffin_chocolate", "chocolate chips", 0.080),
    # muffin_nueces
    ("muffin_nueces", "harina", 0.350),
    ("muffin_nueces", "azúcar", 0.180),
    ("muffin_nueces", "manteca", 0.120),
    ("muffin_nueces", "huevos", 2),
    ("muffin_nueces", "leche entera", 0.180),
    ("muffin_nueces", "polvo de hornear", 0.008),
    ("muffin_nueces", "nueces", 0.080),
    # cheesecake (8 und)
    ("cheesecake", "queso crema", 0.600),
    ("cheesecake", "azúcar", 0.200),
    ("cheesecake", "huevos", 3),
    ("cheesecake", "crema de leche", 0.200),
    ("cheesecake", "harina", 0.050),
    ("cheesecake", "esencia de vainilla", 8),
    # hojaldre_dulce (16 und)
    ("hojaldre_dulce", "harina", 0.500),
    ("hojaldre_dulce", "manteca", 0.300),
    ("hojaldre_dulce", "azúcar", 0.100),
    ("hojaldre_dulce", "huevos", 2),
    ("hojaldre_dulce", "leche entera", 0.150),
    ("hojaldre_dulce", "dulce de leche", 0.300),
    # appeltaart (8 und)
    ("appeltaart", "harina", 0.400),
    ("appeltaart", "manteca", 0.200),
    ("appeltaart", "azúcar", 0.250),
    ("appeltaart", "huevos", 2),
    ("appeltaart", "canela molida", 5),
    ("appeltaart", "frutillas", 0.400),
    # tompoezen (12 und)
    ("tompoezen", "harina", 0.300),
    ("tompoezen", "manteca", 0.150),
    ("tompoezen", "huevos", 2),
    ("tompoezen", "leche entera", 0.150),
    ("tompoezen", "crema de leche", 0.400),
    ("tompoezen", "azúcar impalpable", 0.100),
    # oliebollen (24 und)
    ("oliebollen", "harina", 0.500),
    ("oliebollen", "huevos", 3),
    ("oliebollen", "leche entera", 0.300),
    ("oliebollen", "levadura", 0.020),
    ("oliebollen", "azúcar", 0.080),
    ("oliebollen", "pasas de uva", 0.080),
    ("oliebollen", "aceite vegetal", 0.500),  # for frying
    # babka (10 und)
    ("babka", "harina", 0.600),
    ("babka", "manteca", 0.200),
    ("babka", "azúcar", 0.150),
    ("babka", "huevos", 3),
    ("babka", "leche entera", 0.200),
    ("babka", "levadura", 0.020),
    ("babka", "chocolate chips", 0.150),
    # stroopwafel (24 und)
    ("stroopwafel", "harina", 0.500),
    ("stroopwafel", "manteca", 0.250),
    ("stroopwafel", "azúcar", 0.250),
    ("stroopwafel", "huevos", 2),
    ("stroopwafel", "esencia de vainilla", 8),
    ("stroopwafel", "miel", 0.050),
    # pan_lactal (2 und loaves)
    ("pan_lactal", "harina", 1.000),
    ("pan_lactal", "agua", 0.500),
    ("pan_lactal", "levadura", 0.030),
    ("pan_lactal", "sal", 0.020),
    ("pan_lactal", "manteca", 0.050),
    ("pan_lactal", "azúcar", 0.050),
    # facturas (24 und)
    ("facturas", "harina", 0.500),
    ("facturas", "manteca", 0.150),
    ("facturas", "azúcar", 0.100),
    ("facturas", "huevos", 2),
    ("facturas", "leche entera", 0.150),
    ("facturas", "levadura", 0.020),
    ("facturas", "azúcar impalpable", 0.080),
    ("facturas", "dulce de leche", 0.200),
]

# 20 sellable products. (name, recipe_name, portion_label, sale_price_gs, category)
# category ∈ {panaderia, pasteleria, salados}
PRODUCTS: list[tuple[str, str, str, int, str]] = [
    # Muffins
    ("Muffin de vainilla", "muffin_vainilla", "1 unidad", 8000, "panaderia"),
    ("Muffin de chocolate", "muffin_chocolate", "1 unidad", 8500, "panaderia"),
    ("Muffin de nueces", "muffin_nueces", "1 unidad", 9500, "panaderia"),
    ("Docena muffins vainilla", "muffin_vainilla", "12 unidades", 85000, "panaderia"),
    ("Docena muffins chocolate", "muffin_chocolate", "12 unidades", 90000, "panaderia"),
    # Cheesecake
    ("Cheesecake clásico", "cheesecake", "1 porción", 25000, "pasteleria"),
    ("Cheesecake entera", "cheesecake", "1 torta (8 porciones)", 180000, "pasteleria"),
    # Hojaldre
    ("Hojaldre dulce", "hojaldre_dulce", "1 unidad", 6000, "pasteleria"),
    ("Docena hojaldres", "hojaldre_dulce", "12 unidades", 65000, "pasteleria"),
    # Specialty
    ("Appeltaart", "appeltaart", "1 unidad", 28000, "pasteleria"),
    ("Tompoezen", "tompoezen", "1 unidad", 12000, "pasteleria"),
    ("Docena tompoezen", "tompoezen", "12 unidades", 130000, "pasteleria"),
    ("Oliebollen (unidad)", "oliebollen", "1 unidad", 5500, "pasteleria"),
    ("Docena oliebollen", "oliebollen", "12 unidades", 60000, "pasteleria"),
    ("Babka de chocolate", "babka", "1 unidad", 22000, "pasteleria"),
    ("Stroopwafel", "stroopwafel", "1 unidad", 7000, "pasteleria"),
    ("Docena stroopwafels", "stroopwafel", "12 unidades", 75000, "pasteleria"),
    # Pan
    ("Pan lactal", "pan_lactal", "1 unidad", 12000, "panaderia"),
    # Facturas (Argentine-style pastries)
    ("Facturas (docena)", "facturas", "12 unidades", 35000, "panaderia"),
    ("Facturas (media docena)", "facturas", "6 unidades", 18000, "panaderia"),
]


@dataclass
class SeedReport:
    """Counts of rows inserted by seed_demo_data()."""

    ingredients: int = 0
    recipes: int = 0
    recipe_lines: int = 0
    products: int = 0
    sales: int = 0
    stock_moves: int = 0
    users: int = 0
    pedidos: int = 0
    pedido_lines: int = 0
    import_batches: int = 0
    audit_log_rows: int = 0
    skipped_existing: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, int]:
        return {
            "ingredients": self.ingredients,
            "recipes": self.recipes,
            "recipe_lines": self.recipe_lines,
            "products": self.products,
            "sales": self.sales,
            "stock_moves": self.stock_moves,
            "users": self.users,
            "pedidos": self.pedidos,
            "pedido_lines": self.pedido_lines,
            "import_batches": self.import_batches,
            "audit_log_rows": self.audit_log_rows,
            **self.skipped_existing,
        }


def _demo_public_token() -> str:
    """URL-safe token for /p/{token} pickup-share links (matches the
    generator in app/routers/pedidos.py:generate_public_token).

    P1-2 (2026-09-29): token length bumped from 8 to ~22 chars for
    stronger entropy (96 bits vs 48). See generate_public_token()
    docstring for rationale.
    """
    return secrets.token_urlsafe(16)


def create_demo_pedido(session: Session) -> tuple[Pedido, PedidoLine] | None:
    """Insert one demo Pedido so /pedidos/{id}/stock-preview is testable.

    Idempotent: if a Pedido for the demo customer already exists with a
    line item, this returns None and reports nothing is added. Otherwise
    it creates:
      - one Customer named 'Cliente demo' (get-or-create by email)
      - one Pedido with channel='mostrador', promised_date=today+1,
        status='confirmed', recent created_at, and a unique public_token
      - one PedidoLine for the first available Product, qty=1

    Returns the (pedido, line) pair so callers can log/report the IDs.
    """
    # --- Demo customer (get-or-create) ---
    demo_email = "demo-cliente@herbus.local"
    customer = session.execute(
        select(Customer).where(Customer.email == demo_email)
    ).scalar_one_or_none()
    if customer is None:
        customer = Customer(
            name="Cliente demo",
            email=demo_email,
            phone="+595****4567",
        )
        session.add(customer)
        session.flush()
        logger.info(f"seed: created demo customer id={customer.id}")

    # --- Idempotency: skip if this customer already has a pedido ---
    existing_pedido = session.execute(
        select(Pedido).where(Pedido.customer_id == customer.id).order_by(Pedido.id).limit(1)
    ).scalar_one_or_none()
    if existing_pedido is not None:
        existing_line = session.execute(
            select(PedidoLine).where(PedidoLine.pedido_id == existing_pedido.id)
        ).scalar_one_or_none()
        if existing_line is not None:
            logger.info(f"seed: demo pedido id={existing_pedido.id} already exists, skipping")
            return None

    # --- Pick the first available Product ---
    product = session.execute(select(Product).order_by(Product.id).limit(1)).scalar_one_or_none()
    if product is None:
        logger.warning("seed: no products available; cannot create demo pedido")
        return None

    # --- Build the Pedido with a recent created_at so it shows under
    # "Hoy/Mañana" on /pedidos ---
    now = datetime.now(timezone.utc).replace(microsecond=0)
    promised = (now + timedelta(days=1)).date()

    # Unique public_token (40-char column; token_urlsafe(16) returns
    # ~22 chars which fits well under the 40-char column ceiling).
    token = _demo_public_token()
    # Belt-and-braces: if any collision occurs (effectively zero for
    # a single bakery), regenerate until unique.
    while (
        session.execute(select(Pedido.id).where(Pedido.public_token == token)).first() is not None
    ):
        token = _demo_public_token()

    pedido = Pedido(
        customer_id=customer.id,
        customer_name=customer.name,
        customer_phone=customer.phone,
        promised_date=promised,
        promised_time="10:00",
        channel=Channel.MOSTRADOR,
        status="confirmed",
        payment_intent="efectivo",
        notes="Pedido demo: probá /stock-preview antes de cumplir.",
        public_token=token,
        # P1-2: 30-day expiry for the demo link, same policy as
        # production pedidos. Without this, the demo link would
        # become invalid after migration 067 runs (NULL = expired).
        public_token_expires_at=now + timedelta(days=30),
        created_at=now,
        updated_at=now,
    )
    session.add(pedido)
    session.flush()  # assigns pedido.id

    line = PedidoLine(
        pedido_id=pedido.id,
        product_id=product.id,
        qty=1.0,
        unit_price_gs=int(product.sale_price_gs or 0),
        fulfilled_qty=0.0,
    )
    session.add(line)
    session.flush()

    logger.info(
        f"seed: created demo pedido id={pedido.id} with {product.name} "
        f"for {customer.name}, promised {promised.isoformat()}"
    )
    return pedido, line


# Realistic Paraguayan bakery benchmarks (our_price vs market_avg)
# (label, our_wholesale_gs, our_retail_gs, market_avg_gs, market_min_gs)
BENCHMARKS: list[tuple[str, int, int, int, int]] = [
    ("Chipa grande", 4500, 7000, 6500, 5000),
    ("Muffin de vainilla", 5200, 8000, 9000, 7000),
    ("Pan de queso", 4000, 6500, 6000, 4500),
    ("Galleta de miel", 3500, 5500, 5000, 4000),
    ("Hojaldre de jamón", 12000, 18000, 18000, 15000),
    ("Empanada de carne", 5500, 8500, 8000, 6000),
    ("Croissant", 7000, 11000, 12000, 9000),
    ("Sopa paraguaya", 4000, 6500, 6000, 4500),
    ("Chocotorta", 15000, 22000, 23000, 18000),
    ("Brownie", 6000, 9500, 9000, 7000),
    ("Pão de queijo", 4500, 7000, 6500, 5000),
    ("Torta de chocolate", 20000, 30000, 30000, 25000),
    ("Medialuna", 3500, 5500, 5500, 4000),
    ("Rosca", 15000, 22000, 20000, 16000),
    ("Factura de crema", 4500, 7000, 7000, 5000),
    ("Tostado", 8000, 12500, 12000, 9500),
    ("Budín de pan", 12000, 18000, 17000, 14000),
]


def create_demo_benchmarks(session: Session) -> int:
    """Seed MarketBenchmark rows so /vs-mercado shows real data.

    Idempotent: skips LABELS that are already present (other benchmarks
    from prior imports are left untouched).
    Returns the number of rows inserted (positive) or skipped (0).
    """
    existing_labels = set(
        label for (label,) in session.execute(select(MarketBenchmark.product_label)).all()
    )
    n_new = 0
    for label, wholesale, retail, avg, min_price in BENCHMARKS:
        if label in existing_labels:
            continue
        session.add(
            MarketBenchmark(
                product_label=label,
                our_wholesale_gs=wholesale,
                our_retail_gs=retail,
                market_avg_gs=avg,
                comp_min_gs=min_price,
            )
        )
        n_new += 1
    if n_new:
        session.flush()
        logger.info(f"seed: created {n_new} additional MarketBenchmark rows")
    return n_new


def seed_demo_data(
    session: Session,
    *,
    overwrite: bool = False,
    days_of_history: int = 90,
    sales_per_day: int = 3,
    seed: int | None = 42,
) -> SeedReport:
    """Insert demo data; safe to call multiple times.

    Args:
        session: SQLAlchemy session
        overwrite: if True, delete existing seeded rows (by name match) first
        days_of_history: how many days of synthetic sales to generate
        sales_per_day: baseline number of sales per day
        seed: RNG seed for deterministic output (None = random)

    Returns:
        SeedReport with counts of inserted rows
    """
    rng = random.Random(seed)
    report = SeedReport()

    if overwrite:
        _delete_seeded_data(session)

    # --- Ingredients ---
    existing = set(session.execute(select(Ingredient.name)).scalars().all())
    for name, unit, stock, price, min_stock, _shelf in INGREDIENTS:
        if name in existing:
            report.skipped_existing["ingredients_existing"] = (
                report.skipped_existing.get("ingredients_existing", 0) + 1
            )
            continue
        session.add(
            Ingredient(
                name=name,
                unit=unit,
                stock_qty=stock,
                purchase_price_gs=price if price > 0 else None,
                min_stock_qty=min_stock,
                notes=None,
            )
        )
        report.ingredients += 1
    session.flush()

    # --- Recipes ---
    existing = set(session.execute(select(Recipe.name)).scalars().all())
    for name, yield_qty, yield_unit, _prep in RECIPES:
        if name in existing:
            report.skipped_existing["recipes_existing"] = (
                report.skipped_existing.get("recipes_existing", 0) + 1
            )
            continue
        session.add(
            Recipe(
                name=name,
                yield_qty=yield_qty,
                yield_unit=yield_unit,
                notes=None,
            )
        )
        report.recipes += 1
    session.flush()

    # --- Recipe Lines (polymorphic: line_kind='ingredient', line_ref_id=ingredient.id) ---
    ingredients_by_name = {
        row.name: row.id for row in session.execute(select(Ingredient)).scalars()
    }
    recipes_by_name = {row.name: row.id for row in session.execute(select(Recipe)).scalars()}

    existing_line_keys = {
        (r.recipe_id, r.line_kind, r.line_ref_id)
        for r in session.execute(
            select(RecipeLine.recipe_id, RecipeLine.line_kind, RecipeLine.line_ref_id)
        ).all()
    }
    for recipe_name, ingredient_name, qty in RECIPE_LINES:
        recipe_id = recipes_by_name.get(recipe_name)
        ingredient_id = ingredients_by_name.get(ingredient_name)
        if not recipe_id or not ingredient_id:
            logger.warning(f"missing ref for {recipe_name}/{ingredient_name}, skipping")
            continue
        key = (recipe_id, "ingredient", ingredient_id)
        if key in existing_line_keys:
            report.skipped_existing["recipe_lines_existing"] = (
                report.skipped_existing.get("recipe_lines_existing", 0) + 1
            )
            continue
        session.add(
            RecipeLine(
                recipe_id=recipe_id,
                line_kind="ingredient",
                line_ref_id=ingredient_id,
                qty=qty,
            )
        )
        report.recipe_lines += 1
    session.flush()

    # --- Products ---
    existing = set(session.execute(select(Product.name)).scalars().all())
    for name, recipe_name, portion_label, sale_price, _category in PRODUCTS:
        if name in existing:
            report.skipped_existing["products_existing"] = (
                report.skipped_existing.get("products_existing", 0) + 1
            )
            continue
        session.add(
            Product(
                name=name,
                recipe_id=recipes_by_name.get(recipe_name),
                portion_label=portion_label,
                sale_price_gs=sale_price,
                notes=None,
            )
        )
        report.products += 1
    session.flush()

    # E13.S2 — "Venta libre" so the cashier can sell a custom-name item at
    # a cashier-typed price. Stock-free; sale_price starts at 0 and is
    # overridden per-sale via the cart price input. Idempotent by SKU.
    existing_sku = session.execute(
        select(Product).where(Product.sku == "VAR-001")
    ).scalar_one_or_none()
    if existing_sku is None:
        venta_libre = Product(
            name="Venta libre",
            sku="VAR-001",
            sale_price_gs=0,
            is_available=True,
            notes="Venta libre — definí el precio en el carrito.",
            category="varios",
        )
        session.add(venta_libre)
        session.flush()
        report.products += 1
    else:
        report.skipped_existing["products_existing"] = (
            report.skipped_existing.get("products_existing", 0) + 1
        )

    # --- Demo user ---
    user = session.execute(
        select(User).where(User.username == DEMO_USER_USERNAME)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            username=DEMO_USER_USERNAME,
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_login_at=None,
        )
        user.set_password(DEMO_USER_PASSWORD)
        session.add(user)
        session.flush()
        report.users += 1
    else:
        report.skipped_existing["users_existing"] = (
            report.skipped_existing.get("users_existing", 0) + 1
        )

    # --- Demo pedido (so /pedidos/{id}/stock-preview is testable) ---
    pedido_result = create_demo_pedido(session)
    if pedido_result is not None:
        report.pedidos += 1
        report.pedido_lines += len(pedido_result[0].lines)
    else:
        report.skipped_existing["pedido_demo_existing"] = (
            report.skipped_existing.get("pedido_demo_existing", 0) + 1
        )

    # --- Demo benchmarks (so /vs-mercado has rows to compare) ---
    n_benchmarks = create_demo_benchmarks(session)
    if n_benchmarks > 0:
        report.skipped_existing["benchmarks_created"] = n_benchmarks
    else:
        report.skipped_existing["benchmarks_existing"] = (
            report.skipped_existing.get("benchmarks_existing", 0) + 1
        )

    # --- Import batch example (so the import history is non-empty) ---
    existing = session.execute(select(ImportBatch).limit(1)).scalar_one_or_none()
    if existing is None:
        session.add(
            ImportBatch(
                imported_at=datetime.now(timezone.utc),
                source_filename="seed_demo_data.xlsx",
                note="Seed: synthetic fixture used for demo. No PII.",
                row_counts_json={
                    "ingredientes": report.ingredients,
                    "recetas": report.recipes,
                    "lineas": report.recipe_lines,
                    "productos": report.products,
                },
            )
        )
        report.import_batches += 1

    # --- Synthetic sales + stock moves ---
    products_by_id = {p.id: p for p in session.execute(select(Product)).scalars()}
    recipes_by_id = {r.id: r for r in session.execute(select(Recipe)).scalars()}
    recipe_lines_by_recipe: dict[int, list[RecipeLine]] = {}
    for line in session.execute(select(RecipeLine)).scalars():
        recipe_lines_by_recipe.setdefault(line.recipe_id, []).append(line)

    today = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    sales_start = today - timedelta(days=days_of_history)

    # Generate sales over the period.
    sale_rows: list[Sale] = []
    stock_move_rows: list[StockMovement] = []

    BATCH_SIZE = 25  # commit every N days to avoid long-running transactions

    for day_offset in range(days_of_history):
        sale_date = sales_start + timedelta(days=day_offset)
        weekday = sale_date.weekday()  # 0=Mon, 6=Sun

        # Volume skew: weekends +40%, payday (1st, 15th) +60%, otherwise baseline
        base_count = sales_per_day
        if weekday >= 5:  # Sat-Sun
            base_count = math.ceil(base_count * 1.4)
        if sale_date.day in (1, 15):
            base_count = math.ceil(base_count * 1.6)
        # Mild noise
        count = max(1, int(base_count + rng.randint(-1, 1)))

        for _ in range(count):
            product = rng.choice(list(products_by_id.values()))
            hour = rng.choices(
                [8, 9, 10, 11, 14, 15, 16, 17, 18], weights=[2, 3, 3, 2, 3, 3, 2, 2, 1]
            )[0]
            minute = rng.randint(0, 59)
            sold_at = sale_date.replace(hour=hour, minute=minute)
            qty = rng.choices([1, 2, 3, 6, 12], weights=[70, 15, 5, 5, 5])[0]

            sale = Sale(
                sold_at=sold_at,
                product_id=product.id,
                qty=qty,
                unit_price_gs=product.sale_price_gs,
                notes=None,
            )
            session.add(sale)
            session.flush()  # to get sale.id

            if product.recipe_id and product.recipe_id in recipe_lines_by_recipe:
                recipe = recipes_by_id[product.recipe_id]
                yield_qty = recipe.yield_qty or 1.0
                # BACKLOG #19 (2026-10-02): recipe_line.qty is Numeric(12,4)
                # so line.qty is Decimal in Python. Coerce yield_qty and qty
                # to Decimal so we don't hit "Decimal / float" TypeError.
                from decimal import Decimal as _D

                yield_qty_d = _D(str(yield_qty))
                qty_d = _D(str(qty))
                for line in recipe_lines_by_recipe[product.recipe_id]:
                    need = (line.qty / yield_qty_d) * qty_d
                    move = StockMovement(
                        movement_type="sale",
                        ingredient_id=line.line_ref_id,
                        qty=-need,
                        reference_id=sale.id,
                        reference_type="sale",
                        affected_recipe_id=product.recipe_id,
                        recorded_at=sold_at,
                    )
                    session.add(move)
                    stock_move_rows.append(move)

                    ing_row = session.get(Ingredient, line.line_ref_id)
                    if ing_row is not None:
                        # BACKLOG #19: need is Decimal (recipe_line.qty is
                        # Numeric). stock_qty is Float. Coerce before the
                        # subtraction so we don't hit `float - Decimal`.
                        ing_row.stock_qty = max(0.0, float(ing_row.stock_qty) - float(need))

            sale_rows.append(sale)

        # Commit every BATCH_SIZE days to avoid one giant transaction
        # that locks Postgres for minutes (live Neon was hanging).
        if (day_offset + 1) % BATCH_SIZE == 0:
            session.commit()
            logger.info(f"seeded days {day_offset + 1}/{days_of_history}")

    report.sales = len(sale_rows)
    report.stock_moves = len(stock_move_rows)

    # --- One voided sale example (recent) ---
    last_product = next(iter(products_by_id.values()))
    voided = Sale(
        sold_at=today - timedelta(days=2, hours=4),
        product_id=last_product.id,
        qty=2,
        unit_price_gs=last_product.sale_price_gs,
        notes="cliente cambió de opinión",
        voided_at=today - timedelta(days=2, hours=3),
    )
    session.add(voided)
    session.flush()
    # Stock moves for voided sale get +qty_delta to restore
    if last_product.recipe_id and last_product.recipe_id in recipe_lines_by_recipe:
        recipe = recipes_by_id[last_product.recipe_id]
        yield_qty = recipe.yield_qty or 1.0
        # BACKLOG #19: coerce to Decimal (line.qty is Numeric).
        from decimal import Decimal as _D

        yield_qty_d = _D(str(yield_qty))
        for line in recipe_lines_by_recipe[last_product.recipe_id]:
            restore = (line.qty / yield_qty_d) * _D(2)
            session.add(
                StockMovement(
                    movement_type="sale",
                    ingredient_id=line.line_ref_id,
                    qty=+restore,
                    reference_id=voided.id,
                    reference_type="sale",
                    affected_recipe_id=last_product.recipe_id,
                    recorded_at=voided.sold_at,
                )
            )

    # --- One encargo (custom order) sale ---
    encargo_product = list(products_by_id.values())[5]
    encargo = Sale(
        sold_at=today - timedelta(days=1, hours=2),
        product_id=encargo_product.id,
        qty=1,
        unit_price_gs=encargo_product.sale_price_gs,
        notes="encargo: para cumpleaños, recoger 16h",
    )
    session.add(encargo)
    session.flush()

    report.sales += 2  # voided + encargo
    report.stock_moves += len(recipe_lines_by_recipe.get(last_product.recipe_id, []))

    # --- Tags (E9.S1) ---
    # Insert all 31 starter tags + apply a few to seed products so the demo
    # data surfaces immediately in the UI.
    ensure_starter_tags(session)
    popular_tag = ensure_tag(session, "popular", TagKind.PRODUCT.value)
    premium_tag = ensure_tag(session, "premium", TagKind.PRODUCT.value)
    individual_tag = ensure_tag(session, "individual", TagKind.PRODUCT.value)
    docena_tag = ensure_tag(session, "docena", TagKind.PRODUCT.value)
    all_products = list(session.execute(select(Product)).scalars())
    all_products_by_name = {p.name: p for p in all_products}
    for prod_name, _recipe_name, portion_label, _price, _category in PRODUCTS:
        prod = all_products_by_name.get(prod_name)
        if prod is None:
            continue
        if portion_label == "docena":
            tag_target(session, docena_tag, TagKind.PRODUCT.value, prod.id)
        elif portion_label == "1 unidad":
            tag_target(session, individual_tag, TagKind.PRODUCT.value, prod.id)
    # Mark all products with the "popular" tag (illustrative; in reality
    # this would be data-driven from sales velocity).
    for p in all_products:
        tag_target(session, popular_tag, TagKind.PRODUCT.value, p.id)
    # Premium only on the last product (highest price point)
    if all_products:
        tag_target(session, premium_tag, TagKind.PRODUCT.value, all_products[-1].id)

    # --- Audit log seed (2 rows) ---
    demo_user_id_str = str(user.id) if user else None
    try:
        audit_record(
            session,
            user_id=demo_user_id_str,
            action="system.startup",
            detail={"source": "seed_demo_data"},
        )
        audit_record(
            session,
            user_id=demo_user_id_str,
            action="seed.complete",
            detail=report.as_dict(),
        )
        report.audit_log_rows = 2
    except Exception as exc:  # noqa: BLE001 — defensive default
        logger.warning(f"audit seed failed: {exc}")

    # --- AppMeta schema_version pin (idempotent) ---
    existing_meta = session.execute(
        select(AppMeta).where(AppMeta.key == "last_seed_at")
    ).scalar_one_or_none()
    now_str = datetime.now(timezone.utc).isoformat()
    # On Postgres, app_meta.value may be JSONB (legacy column type from
    # Supabase Auth). Use dialect-aware INSERT to handle both.
    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else "sqlite"
    if existing_meta is None:
        if dialect_name == "postgresql":
            from sqlalchemy import text as sa_text

            # Build SQL in Python to avoid SQLAlchemy's :param binding
            # conflicting with Postgres' ::type casts.
            ts_q = now_str.replace("'", "''")
            session.execute(
                sa_text(
                    f"INSERT INTO app_meta (key, value, updated_at) "  # noqa: S608 — ts_q is sanitized timestamp, not user input
                    f"VALUES ('last_seed_at', '\"{ts_q}\"'::jsonb, '{ts_q}') "
                    f"ON CONFLICT (key) DO NOTHING"
                )
            )
        else:
            session.add(AppMeta(key="last_seed_at", value=now_str, updated_at=now_str))
    else:
        existing_meta.value = now_str
        existing_meta.updated_at = now_str

    session.commit()
    logger.info(f"seed complete: {report.as_dict()}")
    return report


def _delete_seeded_data(session: Session) -> None:
    """Delete all rows from the tables we manage. Used when overwrite=True."""
    # Order matters: respect FKs.
    # Wrap each deletion in try/except so a missing-table error (live DB
    # schema drift) doesn't abort the whole seed.
    for model in (
        PedidoLine,
        Pedido,
        Customer,
        StockMovement,
        Sale,
        ImportBatch,
        Product,
        RecipeLine,
        Recipe,
        Ingredient,
        User,
    ):
        try:
            session.execute(delete(model))
        except Exception as e:  # noqa: BLE001 — defensive default
            logger.warning(f"Could not wipe {model.__name__}: {e}")
            session.rollback()
    try:
        session.execute(delete(AppMeta).where(AppMeta.key == "last_seed_at"))
    except Exception as e:  # noqa: BLE001 — defensive default
        logger.warning(f"Could not delete last_seed_at: {e}")
        session.rollback()
    # AuditLog: only delete the seeded events (action='seed.complete')
    from app.rms.models import AuditLog

    try:
        session.execute(delete(AuditLog).where(AuditLog.action == "seed.complete"))
    except Exception as e:  # noqa: BLE001 — defensive default
        logger.warning(f"Could not wipe audit log: {e}")
        session.rollback()
    session.commit()


__all__ = [
    "BENCHMARKS",
    "DEMO_USER_EMAIL",
    "DEMO_USER_PASSWORD",
    "DEMO_USER_USERNAME",
    "INGREDIENTS",
    "PRODUCTS",
    "RECIPES",
    "RECIPE_LINES",
    "SeedReport",
    "create_demo_benchmarks",
    "create_demo_pedido",
    "seed_demo_data",
]
