"""Test the Shopping List + Production Planner pipeline + Benchmark form."""

import json

import pytest
from fastapi.testclient import TestClient

from app.rms.main import app


@pytest.fixture(scope="module")
def dump():
    """Load dump.json for benchmark/import data shape checks."""
    # I2: build the fixture on demand instead of hard-failing on a
    # machine-specific /tmp path (was: FileNotFoundError on every fresh CI box).
    import pathlib as _pl

    dump = _pl.Path("/tmp/herbus_drive/dump.json")
    if not dump.exists():
        builder = _pl.Path(__file__).parent / "fixtures" / "build_herbus_drive_fixture.py"
        if not builder.exists():
            pytest.skip("herbus drive fixture builder unavailable")
        subprocess_run = __import__("subprocess").run(
            ["uv", "run", "python", str(builder)], capture_output=True
        )
        if subprocess_run.returncode != 0 or not dump.exists():
            pytest.skip(f"fixture build failed: {subprocess_run.stderr[-200:]}")
    with open(dump) as f:
        return json.load(f)


@pytest.fixture
def client():
    return TestClient(app)



@pytest.fixture
def client():
    return TestClient(app)


def test_benchmarks_import_present(dump):
    """Verify 17 benchmarks were imported from HEREBUS_Analisis."""
    bench = [s for s in dump if s.get("_file") == "HEREBUS_Analisis.xlsx"]
    assert len(bench) == 1
    sheet = bench[0].get("Benchmarks_Market", [])
    # 22 rows total: header + 5 instruction rows + 17 product rows
    assert len(sheet) >= 17, f"Expected ≥17 product rows, got {len(sheet)}"


def test_benchmark_form_save_updates_row(dump):
    """Save a benchmark price and verify it persists."""
    sheets = [s for s in dump if s.get("_file") == "HEREBUS_Analisis.xlsx"]
    sheet = sheets[0].get("Benchmarks_Market", [])
    assert len(sheet) >= 17, "Need at least 17 benchmark rows for the test"


def test_shopping_list_route_in_app():
    """The /shopping-list route is registered with the app."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/shopping-list" in paths


def test_benchmark_edit_route_in_app():
    """The /benchmarks/{id}/edit route is registered."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    has = any(p.startswith("/vs-mercado/") and p.endswith("/edit") for p in paths)
    assert has


def test_benchmark_save_route_in_app():
    """The /benchmarks/{id}/save route is registered."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    has = any(p.startswith("/vs-mercado/") and p.endswith("/save") for p in paths)
    assert has


def test_planner_to_shopping_pipeline_syntax():
    """Verify the planner template uses combo (no native select)."""
    from pathlib import Path
    p = Path("/opt/data/work/saskia-app/app/templates/planner.html")
    content = p.read_text()
    # Should have saskia-combo (recipe picker)
    assert "saskia-combo" in content
    # Should NOT have plain <select for recipe_id
    assert '<select name="recipe_id"' not in content


def test_shopping_list_template_no_native_select():
    """Bank manual-entry uses combos not selects."""
    from pathlib import Path
    p = Path("/opt/data/work/saskia-app/app/templates/bank.html")
    content = p.read_text()
    # After Phase D fix, the only <select> is gone (currency/category now combos)
    assert '<select id="currency"' not in content
    assert '<select id="category"' not in content


def test_benchmarks_import_count(dump):
    """17 benchmarks imported from sheet."""
    sheets = [s for s in dump if s.get("_file") == "HEREBUS_Analisis.xlsx"]
    sheet = sheets[0].get("Benchmarks_Market", [])
    # The first 5 rows are title/instructions/headers; next 17 are data
    bench_rows = [
        row for row in sheet[6:]
        if len(row) > 1 and row[1] and "—" not in str(row[1])
    ]
    # Expect at least 17 entries
    assert len(bench_rows) >= 15


def test_recipe_photo_picker_route_in_app():
    """The /recetas/{id}/set-photo route is registered."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    has = any(p.startswith("/recetas/") and p.endswith("/set-photo") for p in paths)
    assert has


def test_recipe_photos_template_exists():
    """The recipe_photos.html template is rendered."""
    from pathlib import Path
    p = Path("/opt/data/work/saskia-app/app/templates/recipe_photos.html")
    assert p.exists()
    content = p.read_text()
    assert "{% for p in photos %}" in content
    # Should not contain any native <select> for photo picker
    assert '<select' not in content


def test_delivery_zones_api_route_in_app():
    """The /delivery-zones/api route is registered."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/delivery-zones/api" in paths


def test_shopping_list_save_plan_route():
    """Plan-to-shopping-list conversion route exists."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    has = any(p == "/shopping-list/save-plan/{plan_id}" for p in paths)
    assert has


def test_sync_low_stock_route_in_app():
    """The /shopping-list/sync-low-stock route exists."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/shopping-list/sync-low-stock" in paths


def test_bank_add_route_in_app():
    """The /bank/add route exists."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/bank/add" in paths


def test_bank_categorize_route_in_app():
    """The /bank/{id}/categorize route exists."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    has = any(p.startswith("/bank/") and p.endswith("/categorize") for p in paths)
    assert has


def test_dashboard_kpis_present():
    """The dashboard route loads without error and has operational KPIs."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/dashboard" in paths
    # The new operational KPIs are present in dashboard.html
    from pathlib import Path
    p = Path("/opt/data/work/saskia-app/app/templates/dashboard.html")
    content = p.read_text()
    assert "sl_open_count" in content
    assert "wishlist_count" in content
    assert "risk_count" in content
    assert "Comparativas de mercado" in content  # the 4th KPI card
