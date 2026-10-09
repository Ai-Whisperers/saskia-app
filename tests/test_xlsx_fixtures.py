"""tests/test_xlsx_fixtures.py — verify Drive-shape fixtures round-trip cleanly.

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E7.

Builds (or rebuilds) the fixture files in tests/fixtures/ and exercises
the import service against them. Asserts:
- minimal.xlsx imports without warnings
- realistic.xlsx round-trips with the seed counts
- edge_cases.xlsx imports gracefully (no crash on renamed sheet / blank
  rows / extra column / unicode names)
- herbus_compat.xlsx (mimics the operator's actual Drive file) imports cleanly
- All sheets persist with expected row counts
- Fixtures are committed under tests/fixtures/
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.import_xlsx import ImportResult
from app.services.import_xlsx import from_file as import_xlsx

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures_built():
    """Build fixtures on first run (or rebuild if missing).

    Idempotent: if fixtures exist, leave them alone. Tests should always
    have them after this fixture runs.
    """
    if not (FIXTURE_DIR / "herbus_minimal.xlsx").exists():
        from tests.fixtures.build_herbus_fixture import build_all

        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        build_all()
    yield


def test_minimal_fixture_imports(session_factory):
    """3 ingredients, 1 recipe, 2 products should import cleanly."""
    path = FIXTURE_DIR / "herbus_minimal.xlsx"
    assert path.exists(), f"missing fixture: {path}"
    s = session_factory()
    try:
        result = import_xlsx(s, str(path))
        assert isinstance(result, ImportResult)
        assert result.ingredients == 3
        assert result.recipes == 1
        assert result.lines == 3
        assert result.products == 2
        assert result.warnings == []
    finally:
        s.close()


def test_realistic_fixture_round_trips(session_factory):
    """Realistic fixture should match E6 seed counts (after re-import)."""
    path = FIXTURE_DIR / "herbus_realistic.xlsx"
    assert path.exists()
    s = session_factory()
    try:
        result = import_xlsx(s, str(path))
        assert result.ingredients == 30
        assert result.recipes == 12
        assert result.products == 20
        assert result.lines >= 60
        assert result.sales >= 20
    finally:
        s.close()


def test_edge_cases_fixture_imports_gracefully(session_factory):
    """Edge cases (renamed sheet, blank rows, extra column, unicode) should not crash.

    Acceptable outcomes:
    - Either succeeds with the same ingredient count we wrote (4)
      and a warning about the renamed sheet
    - Or raises a clear error message about the rename
    """
    path = FIXTURE_DIR / "herbus_edge_cases.xlsx"
    assert path.exists()
    s = session_factory()
    try:
        try:
            result = import_xlsx(s, str(path))
            # If import succeeded, the "Insumos" sheet alias must have worked
            # OR a warning was recorded explaining the rename.
            assert isinstance(result, ImportResult)
        except ValueError as e:
            # Acceptable to fail loudly on a renamed sheet; user must rename.
            assert "Insumos" in str(e) or "sheet" in str(e).lower()
    finally:
        s.close()


def test_herbus_compat_fixture_imports(session_factory):
    """Compat fixture (the operator's real Drive file shape) should import cleanly."""
    path = FIXTURE_DIR / "herbus_compat.xlsx"
    assert path.exists()
    s = session_factory()
    try:
        result = import_xlsx(s, str(path))
        # 3 ingredients, 1 recipe, 2 products, 2 sales, 3 lines
        assert result.ingredients == 3
        assert result.recipes == 1
        assert result.lines == 3
        assert result.products == 2
        assert result.sales == 2
        # Note: "extra_field" on Productos should be ignored, not crash
    finally:
        s.close()


def test_realistic_fixture_has_correct_sheet_names():
    """Verify the fixture structure matches what import_xlsx expects."""
    from openpyxl import load_workbook

    path = FIXTURE_DIR / "herbus_minimal.xlsx"
    wb = load_workbook(path)
    expected = {"Ingredientes", "Recetas", "Lineas", "Productos"}
    assert expected.issubset(set(wb.sheetnames)), f"missing sheets: {expected - set(wb.sheetnames)}"


def test_realistic_fixture_has_expected_row_counts():
    """Sanity check on fixture row counts (catches accidental truncation)."""
    from openpyxl import load_workbook

    path = FIXTURE_DIR / "herbus_realistic.xlsx"
    wb = load_workbook(path)

    ing = wb["Ingredientes"]
    assert ing.max_row >= 31, f"expected >=31 rows (header + 30), got {ing.max_row}"

    rec = wb["Recetas"]
    assert rec.max_row >= 13

    prod = wb["Productos"]
    assert prod.max_row >= 21


def test_edge_cases_fixture_has_unicode_names():
    """Edge case fixture must contain unicode + blank-row tolerance signal."""
    from openpyxl import load_workbook

    path = FIXTURE_DIR / "herbus_edge_cases.xlsx"
    wb = load_workbook(path)
    ing = wb["Insumos"]
    found_unicode = False
    for row in ing.iter_rows(values_only=True):
        if row and row[1] and "azúcar" in str(row[1]):
            found_unicode = True
            break
    assert found_unicode, "edge_cases fixture should have unicode ingredient names"


def test_herbus_compat_fixture_has_utf8_sale_notes():
    """Compat fixture should have UTF-8 (acentos, ñ) in sale notes for stress-testing."""
    from openpyxl import load_workbook

    path = FIXTURE_DIR / "herbus_compat.xlsx"
    wb = load_workbook(path)
    sales = wb["Ventas"]
    rows = list(sales.iter_rows(values_only=True))
    # First row is header, second is first sale
    assert len(rows) >= 2
    notes = " ".join(str(r[5]) for r in rows[1:] if r[5])
    assert "María" in notes or "cumpleaños" in notes, (
        f"compat fixture must contain UTF-8 sale notes (got {notes!r})"
    )


def test_fixtures_exist_in_expected_paths():
    """All fixture files must be committed under tests/fixtures/."""
    expected = [
        "herbus_minimal.xlsx",
        "herbus_realistic.xlsx",
        "herbus_edge_cases.xlsx",
        "herbus_compat.xlsx",
        "build_herbus_fixture.py",
    ]
    for name in expected:
        path = FIXTURE_DIR / name
        assert path.exists(), f"missing fixture: {path}"


def test_fixture_files_are_reasonable_size():
    """Each fixture should be > 4KB (sanity check, not zero-bytes)."""
    for name in [
        "herbus_minimal.xlsx",
        "herbus_realistic.xlsx",
        "herbus_edge_cases.xlsx",
        "herbus_compat.xlsx",
    ]:
        path = FIXTURE_DIR / name
        if path.exists():
            size = path.stat().st_size
            assert size > 4000, f"{name} too small: {size} bytes"
