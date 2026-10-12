"""Meta-tests for tests/seeders.py — the consolidated seed helper registry.

Each seed_* function should:
- Be importable from tests.seeders
- Accept a session_factory + kwargs
- Return a dict with the created entity's id
- Write to the DB (so a follow-up query can read the row back)

These are the Phase 1 acceptance tests for the registry itself.
Locks the contract so future refactors can't silently break the
seeders used by 58+ previously-scattered test files.

Convention: each test seeds one entity, then reads it back through the
canonical ORM class to verify the row actually exists in the DB.
"""

from __future__ import annotations

import pytest

# ─── import contract ──────────────────────────────────────────────────────────


def test_seeders_module_imports_cleanly():
    """tests.seeders must import without side effects or hidden imports."""
    import importlib

    mod = importlib.import_module("tests.seeders")
    assert mod is not None
    # Spot-check the public API
    for name in (
        "seed_basic",
        "seed_simple",
        "seed_customer",
        "seed_product",
        "seed_ingredient",
        "seed_catalog",
        "seed_sale",
        "seed_sub_recipe",
        "seed_with_low_stock",
        "seed_with_sales_history",
        "qseed",
    ):
        assert hasattr(mod, name), f"tests.seeders missing {name}"
        assert callable(getattr(mod, name)), f"tests.seeders.{name} is not callable"


# ─── per-entity seed round-trip ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "seed_fn,seed_kwargs,orm_model,id_key",
    [
        # Customer
        ("seed_customer", {"name": "QA Customer A"}, "Customer", "customer_id"),
        # Ingredient
        ("seed_ingredient", {"name": "harina QA", "stock_qty": 5.0}, "Ingredient", "ingredient_id"),
        # Product
        ("seed_product", {"name": "Brownie QA", "sale_price_gs": 10_000}, "Product", "product_id"),
        # Catalog (multiple)
        ("seed_catalog", {"name": "qa_cat", "count": 3}, "Product", "product_ids"),
    ],
)
def test_seed_writes_to_db(seed_fn, seed_kwargs, orm_model, id_key, session_factory):
    """Each seed_X function must persist the row to the DB and return the id."""
    from app.rms.models import Customer, Ingredient, Product
    from tests import seeders

    fn = getattr(seeders, seed_fn)
    result = fn(session_factory, **seed_kwargs)
    assert isinstance(result, dict), f"{seed_fn} must return a dict, got {type(result)}"
    assert id_key in result, f"{seed_fn} must include {id_key!r} in result"

    model_cls = {"Customer": Customer, "Ingredient": Ingredient, "Product": Product}[orm_model]
    with session_factory() as s:
        if id_key.endswith("_ids"):
            ids = result[id_key]
            assert isinstance(ids, list) and len(ids) > 0
            for eid in ids:
                obj = s.get(model_cls, eid)
                assert obj is not None, f"{seed_fn} id {eid} not in DB"
        else:
            eid = result[id_key]
            obj = s.get(model_cls, eid)
            assert obj is not None, f"{seed_fn} id {eid} not in DB"


def test_seed_simple_returns_customer_and_product(session_factory):
    """seed_simple must create a customer + product and link them via IDs."""
    from tests import seeders

    result = seeders.seed_simple(session_factory, name="Brownie Simple QA")
    assert "customer_id" in result
    assert "product_id" in result

    from app.rms.models import Customer, Product

    with session_factory() as s:
        c = s.get(Customer, result["customer_id"])
        p = s.get(Product, result["product_id"])
        assert c is not None
        assert p is not None
        assert p.name == "Brownie Simple QA"


def test_seed_basic_creates_minimal_db(session_factory):
    """seed_basic is the all-purpose entrypoint — at minimum it must create SOMETHING."""
    from tests import seeders

    result = seeders.seed_basic(session_factory, name="qa-basic")
    assert isinstance(result, dict)
    assert len(result) >= 1, "seed_basic must return at least one id key"


def test_qseed_basic_scenario(session_factory):
    """qseed('basic') is the canonical entrypoint for test files."""
    from tests import seeders

    result = seeders.qseed(session_factory, "basic")
    assert isinstance(result, dict)


# ─── guard rails ──────────────────────────────────────────────────────────────


def test_seeders_module_no_test_dunder_polycollect():
    """tests/seeders.py must not pollute pytest collection (no test_* funcs)."""
    import tests.seeders as s

    test_names = [n for n in dir(s) if n.startswith("test_")]
    assert test_names == [], f"tests.seeders has test_* names that pollute collection: {test_names}"


def test_seeders_have_no_async_def():
    """AGENTS.md rule 32: no async def in app code. seeders aren't app, but be consistent."""
    import inspect

    import tests.seeders as s

    bad = [name for name, obj in inspect.getmembers(s, inspect.iscoroutinefunction)]
    assert bad == [], f"tests.seeders has async functions: {bad}"


# ─── CC ceiling ───────────────────────────────────────────────────────────────


def test_seeders_cc_within_budget():
    """AGENTS.md rule 40: CC ≤ 10. Spot-check seeders — they're trivial wrappers,
    so CC should be far below the ceiling. Failure here = a helper grew too complex."""
    import shutil
    import subprocess

    if not shutil.which("radon"):
        pytest.skip("radon not installed (optional dev tool)")
    res = subprocess.run(
        ["radon", "cc", "-s", "-n", "C", "tests/seeders.py"],
        capture_output=True,
        text=True,
    )
    # radon returns non-zero when it finds ratings at-or-above the threshold
    # (-n C means CC >= C is bad). For CC, "C" = 11-20 (above our 10 ceiling).
    assert "C " not in res.stdout and "D " not in res.stdout and "F " not in res.stdout, (
        f"tests/seeders.py has functions exceeding CC=10:\n{res.stdout}"
    )
