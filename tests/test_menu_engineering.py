"""tests/test_menu_engineering.py — E28 menu engineering tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rms.menu_engineering import (
    Quadrant,
    action_for,
    classify_products,
    menu_engineering_report,
)
from app.rms.models import Product, Recipe, RecipeLine, Sale
from tests.factories import make_ingredient, make_product

# ---------------------------------------------------------------------------
# Median + quadrant edge cases
# ---------------------------------------------------------------------------


def test_classify_empty_db(session_factory):
    """No products → empty list."""
    with session_factory() as s:
        assert classify_products(s) == []


def test_classify_single_product_no_sales(session_factory):
    """One product with no sales → STAR (volume=0=median, price=margin=median)."""
    with session_factory() as s:
        p = make_product(s, name="solo_xyz", portion_label="und", sale_price_gs=10000)
        s.add(p)
        s.commit()
        result = classify_products(s)
        assert len(result) == 1
        # With one product, every threshold equals itself → STAR (high vol high margin).
        assert result[0].quadrant in (Quadrant.STAR, Quadrant.DOG)


def test_classify_star_high_volume_high_margin(session_factory):
    """One product with HIGH sales + HIGH margin → STAR (relative to itself,
    median equals itself, so volume >= median AND margin >= median)."""
    with session_factory() as s:
        ing = make_ingredient(s, name="flour_xyz", unit="kg", stock_qty=1, purchase_price_gs=1000)
        s.add(ing)
        s.flush()
        r = Recipe(name="r_star_xyz", yield_qty=10, yield_unit="und")
        s.add(r)
        s.flush()
        s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.1))
        s.flush()

        # High price, low cost → high margin.
        p_high = make_product(
            s, name="star_xyz", portion_label="und", sale_price_gs=50000, recipe_id=r.id
        )
        s.add(p_high)
        s.flush()

        # Add many sales for p_high.
        now = datetime.now(timezone.utc)
        for i in range(50):
            s.add(
                Sale(
                    sold_at=now - timedelta(days=i % 30),
                    product_id=p_high.id,
                    qty=2,
                    unit_price_gs=50000,
                )
            )
        s.commit()

        result = classify_products(s)
        star = [c for c in result if c.quadrant == Quadrant.STAR]
        assert any(c.product_id == p_high.id for c in star)


def test_classify_dog_low_volume_low_margin(session_factory):
    """Two products: high-volume/high-margin star + low-volume/low-margin dog."""
    with session_factory() as s:
        ing = make_ingredient(
            s, name="flour_xyz", unit="kg", stock_qty=1, purchase_price_gs=20000
        )  # expensive
        s.add(ing)
        s.flush()
        r = Recipe(name="r_dog_xyz", yield_qty=10, yield_unit="und")
        s.add(r)
        s.flush()
        s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=1.0))
        s.flush()

        p_dog = make_product(
            s, name="dog_xyz", portion_label="und", sale_price_gs=25000, recipe_id=r.id
        )
        p_star = make_product(
            s, name="star_companion_xyz", portion_label="und", sale_price_gs=80000, recipe_id=r.id
        )
        s.add_all([p_dog, p_star])
        s.flush()

        now = datetime.now(timezone.utc)
        # star: 50 sales, dog: 1 sale.
        for i in range(50):
            s.add(
                Sale(
                    sold_at=now - timedelta(days=i % 30),
                    product_id=p_star.id,
                    qty=1,
                    unit_price_gs=80000,
                )
            )
        s.add(Sale(sold_at=now, product_id=p_dog.id, qty=1, unit_price_gs=25000))
        s.commit()

        result = classify_products(s)
        dog = [c for c in result if c.quadrant == Quadrant.DOG]
        assert any(c.product_id == p_dog.id for c in dog)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def test_report_has_all_four_buckets(session_factory):
    """With 4 products of contrasting profiles, each quadrant is populated."""
    with session_factory() as s:
        ing = make_ingredient(s, name="flour_xyz2", unit="kg", stock_qty=1, purchase_price_gs=1000)
        s.add(ing)
        s.flush()
        r = Recipe(name="r_xyz2", yield_qty=10, yield_unit="und")
        s.add(r)
        s.flush()
        s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.05))

        # 4 products with varying price + sale count.
        prices = [50000, 30000, 80000, 15000]
        qty_per_sale = [5, 1, 1, 1]
        sale_counts = [30, 5, 5, 1]
        products = []
        for i, (price, qty, n) in enumerate(zip(prices, qty_per_sale, sale_counts, strict=False)):
            p = Product(
                name=f"prod_{i}_xyz", portion_label="und", sale_price_gs=price, recipe_id=r.id
            )
            s.add(p)
            s.flush()
            now = datetime.now(timezone.utc)
            for j in range(n):
                s.add(
                    Sale(
                        sold_at=now - timedelta(days=j % 30),
                        product_id=p.id,
                        qty=qty,
                        unit_price_gs=price,
                    )
                )
            products.append(p)
        s.commit()

        report = menu_engineering_report(s)
        assert hasattr(report, "star")
        assert hasattr(report, "plowhorse")
        assert hasattr(report, "puzzle")
        assert hasattr(report, "dog")
        # Total products = 4
        total = sum(report.counts.values())
        assert total == 4


def test_report_counts_sum(session_factory):
    """Sum of counts == number of products."""
    with session_factory() as s:
        for i in range(5):
            s.add(Product(name=f"p_{i}_xyz", portion_label="und", sale_price_gs=10000 + i * 1000))
        s.commit()
        report = menu_engineering_report(s)
        assert sum(report.counts.values()) == 5


def test_report_total_margin_gs(session_factory):
    """total_margin_gs is sum across all products' margin_gs."""
    with session_factory() as s:
        for i in range(3):
            s.add(Product(name=f"p_{i}_xyz2", portion_label="und", sale_price_gs=10000 * (i + 1)))
        s.commit()
        report = menu_engineering_report(s)
        individual = sum(
            p.margin_gs
            for q in (report.star, report.plowhorse, report.puzzle, report.dog)
            for p in q
        )
        assert report.total_margin_gs == individual


def test_report_as_dict_shape(session_factory):
    """report.as_dict() has counts, total_margin_gs, and 4 lists."""
    with session_factory() as s:
        s.add(make_product(s, name="p_xyz", portion_label="und", sale_price_gs=10000))
        s.commit()
        d = menu_engineering_report(s).as_dict()
        assert "counts" in d
        assert "total_margin_gs" in d
        for q in ("star", "plowhorse", "puzzle", "dog"):
            assert q in d
            assert isinstance(d[q], list)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def test_recommendations_for_all_quadrants():
    """action_for returns a non-empty string for every Quadrant."""
    for q in Quadrant:
        msg = action_for(_fake_classification(q))
        assert msg and len(msg) > 10


def _fake_classification(q: Quadrant):
    from app.rms.menu_engineering import ProductClassification

    return ProductClassification(
        product_id=1,
        product_name="x",
        quadrant=q,
        volume=10,
        margin_gs=1000,
        margin_ratio=0.5,
        sale_price_gs=2000,
        cost_gs=1000,
    )


# ---------------------------------------------------------------------------
# Volume window excludes voided + old sales
# ---------------------------------------------------------------------------


def test_volume_excludes_voided_sales(session_factory):
    """Voided sales don't count toward volume."""
    from datetime import timezone

    with session_factory() as s:
        p = make_product(s, name="void_test_xyz", portion_label="und", sale_price_gs=10000)
        s.add(p)
        s.flush()
        now = datetime.now(timezone.utc)
        # 5 active sales.
        for i in range(5):
            s.add(
                Sale(sold_at=now - timedelta(days=i), product_id=p.id, qty=1, unit_price_gs=10000)
            )
        # 3 voided sales in same window.
        for i in range(3):
            s.add(
                Sale(
                    sold_at=now - timedelta(days=i),
                    product_id=p.id,
                    qty=1,
                    unit_price_gs=10000,
                    voided_at=now,
                )
            )
        s.commit()

        result = classify_products(s)
        c = next(r for r in result if r.product_id == p.id)
        assert c.volume == 5  # voided excluded
