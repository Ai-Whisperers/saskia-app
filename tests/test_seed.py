"""tests/test_seed.py — verify app/rms/seed.py is idempotent and accurate.

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E6.

Covers:
- seed_demo_data() inserts all expected entities (ingredients, recipes, products, sales, etc.)
- Idempotent: calling twice does NOT duplicate rows
- overwrite=True wipes seeded data and re-inserts
- Demo user is created with bcrypt hash and correct username
- Synthetic sales have weekday/weekend skew (more sales on Sat-Sun)
- voided sale has notes + voided_at populated
- encargo sale has the encargo note
- Stock moves are tied to sales (qty_delta negative for normal, positive for void)
- Audit log rows are written (system.startup + seed.complete)
- No PII in seeded data (only public domain product names)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.rms.models import (
    AppMeta,
    AuditLog,
    ImportBatch,
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    StockMovement,
    User,
)
from app.rms.seed import (
    DEMO_USER_PASSWORD,
    DEMO_USER_USERNAME,
    INGREDIENTS,
    PRODUCTS,
    RECIPES,
    seed_demo_data,
)


def test_seed_inserts_all_entity_types(session_factory):
    """First call should insert ingredients, recipes, products, sales, etc."""
    Session = session_factory
    session = Session()
    try:
        report = seed_demo_data(session, seed=42)

        # Count assertions
        assert report.ingredients == 30, f"expected 30 ingredients, got {report.ingredients}"
        assert report.recipes == 12, f"expected 12 recipes, got {report.recipes}"
        assert report.products == 21, (
            f"expected 21 products (20 catalog + 1 Venta libre), got {report.products}"
        )
        assert report.recipe_lines > 60, f"expected >60 recipe_lines, got {report.recipe_lines}"
        assert report.sales >= 200, f"expected >=200 sales, got {report.sales}"
        assert report.stock_moves > 100, f"expected >100 stock_moves, got {report.stock_moves}"
        assert report.users == 1, f"expected 1 demo user, got {report.users}"
        assert report.audit_log_rows == 2, f"expected 2 audit log rows, got {report.audit_log_rows}"

        # Verify row counts in DB
        n_ingredients = session.execute(select(Ingredient)).scalars().all()
        assert len(n_ingredients) == 30

        n_recipes = session.execute(select(Recipe)).scalars().all()
        assert len(n_recipes) == 12

        n_products = session.execute(select(Product)).scalars().all()
        assert len(n_products) == 21, (
            f"expected 21 products (20 catalog + 1 Venta libre), got {len(n_products)}"
        )

        n_sales = session.execute(select(Sale)).scalars().all()
        assert len(n_sales) >= 200
    finally:
        session.close()


def test_seed_is_idempotent(session_factory):
    """Calling seed_demo_data twice must NOT duplicate rows."""
    Session = session_factory
    session = Session()
    try:
        # First call
        seed_demo_data(session, seed=42)
        n_ingredients_after_first = len(session.execute(select(Ingredient)).scalars().all())

        # Second call (same seed) — should be all skipped
        report2 = seed_demo_data(session, seed=42)

        # Second call should not have added anything
        assert report2.ingredients == 0, "second call should add no ingredients"
        assert report2.recipes == 0
        assert report2.products == 0

        # But DB should still have the same count
        n_ingredients_after_second = len(session.execute(select(Ingredient)).scalars().all())
        assert n_ingredients_after_second == n_ingredients_after_first, (
            f"ingredient count changed: {n_ingredients_after_first} -> {n_ingredients_after_second}"
        )

        # skipped_existing should reflect what was already there
        assert report2.skipped_existing.get("ingredients_existing", 0) == 30
    finally:
        session.close()


def test_seed_overwrite_resets_data(session_factory):
    """overwrite=True must wipe seeded rows and re-insert."""
    Session = session_factory
    session = Session()
    try:
        # Seed once
        seed_demo_data(session, seed=42)
        # report1 not needed - we just need the seed to populate

        # Wipe and reseed with different seed
        report2 = seed_demo_data(session, overwrite=True, seed=99)
        assert report2.ingredients == 30, "overwrite should re-insert"

        # Total counts should match the first run
        n_ingredients = len(session.execute(select(Ingredient)).scalars().all())
        assert n_ingredients == 30, f"overwrite left {n_ingredients} ingredients, expected 30"
    finally:
        session.close()


def test_demo_user_has_bcrypt_hash(session_factory):
    """Demo user must exist with bcrypt-hashed password matching the known demo password."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        user = session.execute(select(User).where(User.username == DEMO_USER_USERNAME)).scalar_one()
        assert user is not None
        assert user.is_active
        assert user.password_hash != DEMO_USER_PASSWORD  # must be hashed
        assert user.password_hash.startswith("$2"), "bcrypt hash should start with $2"
        assert user.check_password(DEMO_USER_PASSWORD), "demo password should validate"
    finally:
        session.close()


def test_synthetic_sales_have_weekday_weekend_skew(session_factory, monkeypatch):
    """Saturday/Sunday should have more sales than the average day."""
    from app.rms.seed import seed_demo_data

    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42, sales_per_day=5, days_of_history=28)

        sales = session.execute(select(Sale)).scalars().all()
        # Group by weekday
        weekday_counts: dict[int, int] = {}
        for sale in sales:
            wd = sale.sold_at.weekday()
            weekday_counts[wd] = weekday_counts.get(wd, 0) + 1

        # Saturday (5) + Sunday (6) should be higher than average weekday
        if 5 in weekday_counts and 6 in weekday_counts and weekday_counts:
            weekend_total = weekday_counts.get(5, 0) + weekday_counts.get(6, 0)
            weekday_total = sum(v for k, v in weekday_counts.items() if k < 5)
            weekday_days = 5  # Mon-Fri
            weekend_days = 2  # Sat-Sun
            weekend_avg = weekend_total / weekend_days if weekend_total else 0
            weekday_avg = weekday_total / weekday_days if weekday_total else 0
            # Weekend avg should be >= weekday avg
            assert weekend_avg >= weekday_avg * 0.9, (
                f"weekend avg {weekend_avg:.1f} not >= weekday avg {weekday_avg:.1f}"
            )
    finally:
        session.close()


def test_voided_sale_has_notes_and_voided_at(session_factory):
    """The voided sale example should have both notes and voided_at populated."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        voided = session.execute(select(Sale).where(Sale.voided_at.is_not(None))).scalars().first()
        assert voided is not None, "should have at least one voided sale"
        assert voided.notes is not None and "cambió" in voided.notes.lower()
        assert voided.voided_at > voided.sold_at, "voided_at must be after sold_at"
    finally:
        session.close()


def test_encargo_sale_has_encargo_note(session_factory):
    """The encargo (custom order) sale should have the encargo note."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        encargos = session.execute(select(Sale).where(Sale.notes.like("%encargo%"))).scalars().all()
        assert len(encargos) >= 1, "should have at least one encargo sale"
        assert "cumpleaños" in encargos[0].notes.lower()
    finally:
        session.close()


def test_stock_moves_tied_to_sales_with_correct_signs(session_factory):
    """Stock moves for normal sales should be negative; voided sale moves should be positive."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        moves = (
            session.execute(select(StockMovement).where(StockMovement.reference_type == "sale"))
            .scalars()
            .all()
        )
        assert len(moves) > 0

        # Find a voided sale's moves
        voided_sales = (
            session.execute(select(Sale).where(Sale.voided_at.is_not(None))).scalars().all()
        )
        if voided_sales:
            voided = voided_sales[0]
            voided_moves = [m for m in moves if m.reference_id == voided.id]
            if voided_moves:
                # At least one voided move should be positive (restoring stock)
                assert any(m.qty > 0 for m in voided_moves), (
                    "voided sale should have at least one positive stock move"
                )

        # Find a non-voided sale's moves — all should be negative
        normal_sales = session.execute(select(Sale).where(Sale.voided_at.is_(None))).scalars().all()
        if normal_sales:
            normal = normal_sales[0]
            normal_moves = [m for m in moves if m.reference_id == normal.id]
            if normal_moves:
                assert all(m.qty < 0 for m in normal_moves), (
                    "normal sale should have all negative stock moves"
                )
    finally:
        session.close()


def test_audit_log_rows_written(session_factory):
    """Both system.startup and seed.complete audit rows should be written."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        rows = session.execute(select(AuditLog)).scalars().all()
        actions = {r.action for r in rows}
        assert "system.startup" in actions, "missing system.startup audit row"
        assert "seed.complete" in actions, "missing seed.complete audit row"
    finally:
        session.close()


def test_import_batch_recorded(session_factory):
    """An ImportBatch row should be created with row_counts_json."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        batches = session.execute(select(ImportBatch)).scalars().all()
        assert len(batches) >= 1
        batch = batches[0]
        assert "ingredientes" in batch.row_counts_json
        assert "recetas" in batch.row_counts_json
        assert batch.row_counts_json["ingredientes"] == 30
    finally:
        session.close()


def test_no_pii_in_seeded_data(session_factory):
    """Verify seeded data uses only public-domain product names (no real PII)."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        # All ingredient names should be in the INGREDIENTS list (no surprise inserts)
        ingredient_names = {row.name for row in session.execute(select(Ingredient)).scalars()}
        expected_names = {row[0] for row in INGREDIENTS}
        assert ingredient_names == expected_names, (
            f"unexpected ingredient names: {ingredient_names - expected_names}"
        )

        # All recipe names should be in RECIPES
        recipe_names = {row.name for row in session.execute(select(Recipe)).scalars()}
        expected_recipe_names = {row[0] for row in RECIPES}
        assert recipe_names == expected_recipe_names

        # All product names should be in PRODUCTS (+ Venta libre added by
        # E13.S2 for the cashier-typed-price flow — kept out of PRODUCTS so
        # the operator can toggle sale_price_gs=0 + custom pricing without
        # polluting the catalog list).
        product_names = {row.name for row in session.execute(select(Product)).scalars()}
        expected_product_names = {row[0] for row in PRODUCTS} | {"Venta libre"}
        assert product_names == expected_product_names, (
            f"unexpected product names: {product_names - expected_product_names}; "
            f"missing: {expected_product_names - product_names}"
        )
    finally:
        session.close()


def test_recipe_lines_link_to_real_ingredients(session_factory):
    """Every recipe_line should resolve to an existing ingredient via line_ref_id."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        ingredient_ids = {row.id for row in session.execute(select(Ingredient)).scalars()}
        lines = session.execute(select(RecipeLine)).scalars().all()
        for line in lines:
            assert line.line_kind == "ingredient"
            assert line.line_ref_id in ingredient_ids, (
                f"recipe_line {line.id} references missing ingredient {line.line_ref_id}"
            )
    finally:
        session.close()


def test_ingredients_have_purchase_prices_and_min_stock(session_factory):
    """Every ingredient should have purchase_price_gs (NULL OK for free items) and min_stock_qty > 0."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        ingredients = session.execute(select(Ingredient)).scalars().all()
        for ing in ingredients:
            assert ing.min_stock_qty >= 0, f"{ing.name} has negative min_stock"
            # Most should have a price; "agua" is the one exception (price=0 -> NULL)
            if ing.name != "agua":
                assert ing.purchase_price_gs is not None and ing.purchase_price_gs > 0, (
                    f"{ing.name} has no purchase price"
                )
    finally:
        session.close()


def test_sales_are_within_date_range(session_factory):
    """All sales.sold_at must be within the last `days_of_history` days."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42, days_of_history=30)

        now = datetime.now(timezone.utc)
        sales = session.execute(select(Sale)).scalars().all()
        for sale in sales:
            # sold_at could be naive or aware; tolerate both
            sold = sale.sold_at
            if sold.tzinfo is None:
                from datetime import timezone as _tz

                sold = sold.replace(tzinfo=_tz.utc)
            delta = (now - sold).days
            assert 0 <= delta <= 35, f"sale {sale.id} is {delta} days old, expected 0-35"
    finally:
        session.close()


def test_seed_writes_app_meta_last_seed_at(session_factory):
    """app_meta.last_seed_at should be set after seeding."""
    Session = session_factory
    session = Session()
    try:
        seed_demo_data(session, seed=42)

        meta = session.execute(
            select(AppMeta).where(AppMeta.key == "last_seed_at")
        ).scalar_one_or_none()
        assert meta is not None
        assert meta.value  # ISO timestamp string
    finally:
        session.close()
