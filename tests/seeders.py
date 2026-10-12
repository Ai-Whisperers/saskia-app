"""tests/seeders.py — consolidated seed helpers for sazon-app test suite.

Previously scattered across 58 files with 18 duplicate patterns.
This centralizes all seed helpers for reuse and deduplication.

Import: from tests.seeders import *  (all functions are available)
Usage: seed_customer(name="Test") or seed_basic() for simple cases.

Each seeder returns a dict with created object IDs and metadata.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from sqlalchemy.orm import Session


# ==============================================================================
# Basic Seed Helpers (Previously scattered)
# ==============================================================================

def seed_basic(
    session_factory,
    *,
    name: str = "basic",
    **kwargs,
) -> Dict[str, Any]:
    """Basic seed helper for common test scenarios.
    
    Previously duplicated in test_excel_patch.py, test_costing.py, test_p0_audit_log_coverage.py
    """
    from tests.factories import make_product
    
    with session_factory() as s:
        # Create a basic product
        p = make_product(s, name=name, **kwargs)
        s.commit()
        return {"product_id": p.id}


def seed_simple(
    session_factory,
    *,
    name: str = "simple",
    **kwargs,
) -> Dict[str, Any]:
    """Simple seed helper for straightforward test scenarios.
    
    Previously duplicated in test_sale_create_writes_stock_movement.py, test_stock_drop.py
    """
    from tests.factories import make_product, make_customer
    
    with session_factory() as s:
        # Create customer and product
        c = make_customer(s, name="Test Customer")
        p = make_product(s, name=name, **kwargs)
        s.commit()
        return {"customer_id": c.id, "product_id": p.id}


# ==============================================================================
# Entity-Specific Seed Helpers
# ==============================================================================

def seed_customer(
    session_factory,
    *,
    name: str = "Test Customer",
    phone: str = "",
    **kwargs,
) -> Dict[str, Any]:
    """Create a customer and return ID.
    
    Previously duplicated in test_pedidos.py, test_p1_b5_suscripciones.py
    """
    from tests.factories import make_customer
    
    with session_factory() as s:
        c = make_customer(s, name=name, phone=phone, **kwargs)
        s.commit()
        return {"customer_id": c.id}


def seed_product(
    session_factory,
    *,
    name: str = "Test Product",
    sale_price_gs: int = 10_000,
    **kwargs,
) -> Dict[str, Any]:
    """Create a product and return ID.
    
    Previously duplicated in test_pedido_post_phase13_integration.py, test_pedidos.py
    """
    from tests.factories import make_product
    
    with session_factory() as s:
        p = make_product(s, name=name, sale_price_gs=sale_price_gs, **kwargs)
        s.commit()
        return {"product_id": p.id}


def seed_ingredient(
    session_factory,
    *,
    name: str = "harina",
    stock_qty: float = 100.0,
    purchase_price_gs: int = 10_000,
    avg_cost_gs: int | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """Create an ingredient and return ID.
    
    Previously duplicated in test_ingredient_avg_cost.py, test_waste_trends.py
    """
    from tests.factories import make_ingredient
    
    with session_factory() as s:
        ing = make_ingredient(
            s,
            name=name,
            stock_qty=stock_qty,
            purchase_price_gs=purchase_price_gs,
            **kwargs,
        )
        s.commit()
        return {"ingredient_id": ing.id}


def seed_catalog(
    session_factory,
    *,
    name: str = "catalog",
    count: int = 3,
    **kwargs,
) -> Dict[str, Any]:
    """Create multiple catalog items and return IDs.
    
    Previously duplicated in test_reports.py, test_saskia217_seasonal_calendar.py
    """
    from tests.factories import make_product
    
    with session_factory() as s:
        products = []
        for i in range(count):
            p = make_product(s, name=f"{name}_{i}", **kwargs)
            products.append(p)
        s.commit()
        return {"product_ids": [p.id for p in products]}


def seed_sale(
    session_factory,
    *,
    product_id: int,
    qty: float = 1,
    customer_id: int | None = None,
    payment_method: str = "efectivo",
    **kwargs,
) -> Dict[str, Any]:
    """Create a sale and return ID.
    
    Previously duplicated across 5 files: test_day_hour_heatmap.py, test_sales_history_filter.py, etc.
    """
    from app.rms.models_legacy import Sale
    from tests.factories import make_customer
    
    with session_factory() as s:
        if customer_id is None:
            c = make_customer(s, name="Test Customer")
            customer_id = c.id
        
        sale = Sale(
            product_id=product_id,
            qty=qty,
            customer_id=customer_id,
            payment_method=payment_method,
            **kwargs,
        )
        s.add(sale)
        s.commit()
        s.refresh(sale)
        return {"sale_id": sale.id, "customer_id": customer_id}


def seed_sub_recipe(
    session_factory,
    *,
    name: str = "sub_recipe",
    yield_qty: float = 12.0,
    yield_unit: str = "und",
    lines: list[dict] | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """Create a sub-recipe and return ID.
    
    Previously duplicated in test_costing.py, test_stock_drop.py
    """
    from app.rms.models import Recipe
    from tests.factories import make_product
    
    with session_factory() as s:
        recipe = Recipe(
            name=name,
            yield_qty=yield_qty,
            yield_unit=yield_unit,
            is_sub_recipe=True,
            **kwargs,
        )
        
        # Add ingredient lines if provided
        if lines:
            for line in lines:
                # Convert line data to appropriate format
                line_kind = line.get("kind", "ingredient")
                target_id = line.get("target_id")
                
                if line_kind == "ingredient" and target_id:
                    from app.rms.models_legacy import IngredientLine
                    ing_line = IngredientLine(
                        recipe_id=recipe.id,
                        line_kind="ingredient",
                        line_target_id=target_id,
                        line_qty=line.get("qty", 1),
                        line_unit=line.get("unit", "kg"),
                    )
                    recipe.ingredient_lines.append(ing_line)
                elif line_kind == "sub_recipe" and target_id:
                    from app.rms.models import RecipeLine
                    recipe_line = RecipeLine(
                        recipe_id=recipe.id,
                        line_target_id=target_id,
                        line_qty=line.get("qty", 1),
                        line_unit=line.get("unit", "und"),
                    )
                    recipe.sub_recipe_lines.append(recipe_line)
        
        s.add(recipe)
        s.commit()
        s.refresh(recipe)
        return {"recipe_id": recipe.id}


# ==============================================================================
# Scenario-Specific Seed Helpers (Previously in flows.py)
# ==============================================================================

def seed_with_low_stock(
    session_factory,
    *,
    threshold: float = 0.5,
    **kwargs,
) -> Dict[str, Any]:
    """Seed scenario: ingredients with low stock.
    
    Usage: qseed("with_low_stock") → returns dict with low_ingredient key
    """
    from tests.factories import make_ingredient
    
    with session_factory() as s:
        low_ingredient = make_ingredient(
            s,
            name="Low Stock Ingredient",
            stock_qty=threshold * 0.9,  # Just below threshold
            **kwargs,
        )
        
        normal_ingredient = make_ingredient(
            s,
            name="Normal Stock Ingredient", 
            stock_qty=threshold * 2.0,  # Well above threshold
            **kwargs,
        )
        
        s.commit()
        return {
            "low_ingredient": {"id": low_ingredient.id, "stock_qty": low_ingredient.stock_qty},
            "normal_ingredient": {"id": normal_ingredient.id, "stock_qty": normal_ingredient.stock_qty},
        }


def seed_with_sales_history(
    session_factory,
    *,
    days: int = 7,
    sales_per_day: int = 3,
    **kwargs,
) -> Dict[str, Any]:
    """Seed scenario: sales history for date-based tests.
    
    Creates historical sales data for testing date filtering and analytics.
    """
    from datetime import datetime, timedelta
    from app.rms.models_legacy import Sale
    
    with session_factory() as s:
        sales = []
        base_date = datetime.now() - timedelta(days=days)
        
        for day in range(days):
            day_date = base_date + timedelta(days=day)
            for i in range(sales_per_day):
                sale = Sale(
                    product_id=kwargs.get("product_id", 1),
                    qty=1,
                    sold_at=day_date,
                    **kwargs,
                )
                sales.append(sale)
                s.add(sale)
        
        s.commit()
        return {"sale_ids": [s.id for s in sales], "start_date": base_date}


# ==============================================================================
# Quick Seed Alias (Backward Compatibility)
# ==============================================================================

def qseed(session_factory, scenario: str = "basic") -> dict:
    """Quick-seed helper for fast targeted test setup.
    
    This is the original qseed function from conftest.py - now delegates to seeders.
    
    Usage:
        def test_x(qseed):
            data = qseed("with_low_stock")
            assert data["low_ingredient"]["stock_qty"] < 1.0
    """
    if scenario == "with_low_stock":
        return seed_with_low_stock(session_factory)
    elif scenario == "with_sales_history":
        return seed_with_sales_history(session_factory)
    elif scenario == "basic":
        return seed_basic(session_factory)
    else:
        # Default to basic for unknown scenarios
        return seed_basic(session_factory)


# Attach session_factory to qseed for backward compatibility
qseed.session_factory = None  # Will be set by conftest


# ==============================================================================
# Migration Guide
# ==============================================================================
"""
MIGRATION GUIDE for existing test files:

1. Replace direct imports:
   OLD: from tests._fixtures_quick_seed import quick_seed
   NEW: from tests.seeders import seed_basic, seed_product, etc.

2. Replace qseed usage:
   OLD: data = qseed("basic")
   NEW: data = seed_basic(session_factory)
   
3. Replace duplicate seed functions:
   OLD: def _seed_product(s, name, price): ...
   NEW: from tests.seeders import seed_product

4. Promote flows.py helpers to conftest (see next step)

Available patterns for migration:
- seed_basic() → replaces _seed_basic across multiple files
- seed_product() → replaces _seed_product in test_pedido_post_phase13_integration.py, test_pedidos.py
- seed_customer() → replaces _seed_customer in test_pedidos.py, test_p1_b5_suscripciones.py
- seed_ingredient() → replaces _seed_ingredient in test_ingredient_avg_cost.py, test_waste_trends.py
- seed_sale() → consolidates 5 files with duplicate sale seeding
- seed_catalog() → replaces _seed_catalog in test_reports.py, test_saskia217_seasonal_calendar.py
- seed_sub_recipe() → replaces _seed_sub_recipe in test_costing.py, test_stock_drop.py
"""