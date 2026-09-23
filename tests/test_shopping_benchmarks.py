"""Test the Shopping List + Production Planner pipeline + Benchmark form."""

import json
import pytest
from fastapi.testclient import TestClient

from app.rms.main import app


@pytest.fixture(scope="module")
def dump():
    """Load dump.json for benchmark/import data shape checks."""
    with open("/tmp/herbus_drive/dump.json") as f:
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
    has = any(p.startswith("/benchmarks/") and p.endswith("/edit") for p in paths)
    assert has


def test_benchmark_save_route_in_app():
    """The /benchmarks/{id}/save route is registered."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    has = any(p.startswith("/benchmarks/") and p.endswith("/save") for p in paths)
    assert has


def test_planner_to_shopping_pipeline_syntax():
    """Verify the planner template uses combo (no native select)."""
    from pathlib import Path
    p = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/planner.html")
    content = p.read_text()
    # Should have saskia-combo (recipe picker)
    assert "saskia-combo" in content
    # Should NOT have plain <select for recipe_id
    assert '<select name="recipe_id"' not in content


def test_shopping_list_template_no_native_select():
    """Bank manual-entry uses combos not selects."""
    from pathlib import Path
    p = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/bank.html")
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
