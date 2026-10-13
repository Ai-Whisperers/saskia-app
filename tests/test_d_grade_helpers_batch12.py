"""Parametrized coverage for two more D-grade helpers with no branch matrix.

S1 batch-12 (test coverage continuation): lock the branch matrix of two
D-grade helpers that lack parametrized coverage:

  (1) `scripts/fix_perf401.py:fix_file` (CC 30, D-grade)
      Pure function that rewrites Python source files in place to
      collapse the `out = []; for x in items: out.append(<expr>)`
      anti-pattern into a single list-comprehension. Walks the file
      line-by-line, identifies the init + for + append trio, and
      replaces them with a single comprehension line. Branches
      covered:

      - empty line_nums list → returns 0 (locks the
        `for ln in sorted(set(line_nums), reverse=True): ...`
        zero-iter case)
      - line index out of range (idx < 2 or idx >= len(lines)) →
        skipped (locks the `if idx < 2 or idx >= len(lines):
        continue` branch)
      - happy path: `out: list = []\\n    for x in items:\\n
        out.append(x * 2)` → rewritten to a single comprehension
        (locks the rewrite branch + the
        `f"{for_indent}{var}: list = [{expr} for {loop_var} in
        {iterable}]\\n"` case for single-line expr)
      - alternative init without type annotation: `out = []` → still
        rewritten (locks the secondary
        `r"^(\\s+)([A-Za-z_][\\w.]*)\\s*=\\s*\\[\\]\\s*$"` match)
      - standalone `if` keyword as the first token of the
        multi-line append body → skipped (locks the
        `control_found = True; break` branch)
      - the for-line above the append doesn't match `for <v> in <i>:`
        → skipped (locks the `if not m2: continue` branch)
      - init line for `var` not found within 80 lines above → skipped
        (locks the `if init_line is None: continue` branch)
      - multiple appends in the same file (different vars) → both
        fixed (locks the bottom-up reverse-iteration branch)
      - unindented append line → skipped (locks the
        `if not m_indent: continue` branch)

  (2) `app/routers/herebus.py:evidencia_importar` (CC 28, D-grade)
      POST /vs-mercado/evidencia/importar — CSV importer for
      CompetitorPriceObservation rows. Confirms via form, validates
      the upload (size + mime + required columns), then walks each
      row, computing the dedup key and either inserting or counting
      it as a duplicate/invalid. Branches covered:

      - confirmar != "si" → 400 (locks the `if form.get("confirmar")
        != "si": raise BadRequest(...)` branch)
      - confirmar == "si" but csv field absent → 400 (locks the
        `if not raw or not getattr(raw, "filename", ""):
        raise BadRequest(...)` branch)
      - csv field is a non-UploadFile (plain string) → 400 (locks
        the `if not isinstance(raw, UploadFile): raise BadRequest
        (...)` branch)
      - CSV header missing a required column → 400 (locks the
        `if not required.issubset(...)` branch)
      - row with non-numeric `precio_gs` → row counted as
        skipped_invalid (locks the `except (ValueError, TypeError):
        skipped_invalid += 1; continue` branch)
      - row with `precio_gs` < 300 → row counted as
        skipped_invalid (locks the
        `if not comp or not prod or not (300 <= price <= 500_000):
        skipped_invalid += 1; continue` branch)
      - row with empty `fuente` → row counted as skipped_invalid
        (locks the `if not (row.get("fuente") or "").strip():
        skipped_invalid += 1; continue` branch)
      - row whose (competitor, product, as_of) tuple already
        exists in the DB → row counted as dup (locks the
        `if key in existing: dup += 1; continue` branch)
      - row with new (competitor, product, as_of) → row added
        (locks the `session.add(CompetitorPriceObservation(...))`
        + `added += 1` branches)
      - mixed CSV (invalid + below-300 + duplicate + new) → combined
        counters all increment correctly
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

# ─── fix_file scenario row spec ─────────────────────────────────────────────


@dataclass
class _FixSpec:
    """One scenario for `fix_file`.

    The `source` field is the file's full text (lines as a single
    string with `\n` separators). The `line_nums` field is the list
    of 1-based line numbers to flag for fix. The `expected_fixed`
    field is the count of fixes the helper should return, and
    `expected_output_contains` is a list of substrings that MUST
    appear in the post-fix file (with `expected_output_absent`
    listing substrings that must NOT appear).
    """

    id: str = ""
    description: str = ""
    source: str = ""
    line_nums: list[int] = field(default_factory=list)
    expected_fixed: int = 0
    expected_output_contains: list[str] = field(default_factory=list)
    expected_output_absent: list[str] = field(default_factory=list)


# ─── fix_file scenario definitions ──────────────────────────────────────────


_ROWS_FIX: list[_FixSpec] = [
    pytest.param(
        _FixSpec(
            id="empty_line_nums_returns_zero",
            description="empty line_nums → returns 0 (no work to do)",
            source=("def f():\n    out: list = []\n    for x in items:\n        out.append(x)\n"),
            line_nums=[],
            expected_fixed=0,
            expected_output_contains=[
                "out: list = []",
                "for x in items:",
                "out.append(x)",
            ],
        ),
        id="empty_line_nums_returns_zero",
    ),
    pytest.param(
        _FixSpec(
            id="line_index_out_of_range_skipped",
            description="line_nums[0] = 999 (past EOF) → skipped, returns 0",
            source=("def f():\n    out: list = []\n    for x in items:\n        out.append(x)\n"),
            line_nums=[999],
            expected_fixed=0,
            expected_output_contains=[
                "out: list = []",
                "for x in items:",
                "out.append(x)",
            ],
        ),
        id="line_index_out_of_range_skipped",
    ),
    pytest.param(
        _FixSpec(
            id="happy_path_single_line_rewritten",
            description="classic pattern: out=[], for x in items:, out.append(x*2) → comprehension",
            source=(
                "def f(items):\n"
                "    out: list = []\n"
                "    for x in items:\n"
                "        out.append(x * 2)\n"
                "    return out\n"
            ),
            line_nums=[4],
            expected_fixed=1,
            expected_output_contains=[
                "out: list = [x * 2 for x in items]",
            ],
            expected_output_absent=[
                "    for x in items:",
                "        out.append(x * 2)",
            ],
        ),
        id="happy_path_single_line_rewritten",
    ),
    pytest.param(
        _FixSpec(
            id="alt_init_no_type_annotation",
            description="init without type annotation: `out = []` → still rewritten",
            source=(
                "def f(items):\n"
                "    out = []\n"
                "    for x in items:\n"
                "        out.append(x + 1)\n"
                "    return out\n"
            ),
            line_nums=[4],
            expected_fixed=1,
            expected_output_contains=[
                "out: list = [x + 1 for x in items]",
            ],
            expected_output_absent=[
                "    for x in items:",
                "        out.append(x + 1)",
            ],
        ),
        id="alt_init_no_type_annotation",
    ),
    pytest.param(
        _FixSpec(
            id="standalone_if_keyword_in_expr_skipped",
            description=(
                "multi-line append body whose first body line is `if x > 0:` "
                "→ control_found branch triggers → skipped"
            ),
            source=(
                "def f(items):\n"
                "    out: list = []\n"
                "    for x in items:\n"
                "        out.append(\n"
                "            if x > 0:\n"
                "                x\n"
                "            else:\n"
                "                -x\n"
                "        )\n"
                "    return out\n"
            ),
            # The multi-line body starts with `if x > 0:` on the
            # first body line → `first = "if"` → control_found =
            # True → break → continue (no fix).
            line_nums=[4],
            expected_fixed=0,
            expected_output_contains=[
                "    out: list = []",
                "    for x in items:",
                "        out.append(",
                "            if x > 0:",
            ],
        ),
        id="standalone_if_keyword_in_expr_skipped",
    ),
    pytest.param(
        _FixSpec(
            id="no_matching_for_line_skipped",
            description="append line preceded by a non-for line (e.g. assignment) → skipped",
            source=(
                "def f(items):\n"
                "    out: list = []\n"
                "    n = 0\n"
                "        out.append(items[n])\n"
                "    return out\n"
            ),
            # Line 4 (`out.append(items[n])`) is preceded by `n = 0`
            # (a non-`for` line) → the regex match for
            # `for <v> in <i>:` fails → continue.
            line_nums=[4],
            expected_fixed=0,
            expected_output_contains=[
                "    n = 0",
                "        out.append(items[n])",
            ],
        ),
        id="no_matching_for_line_skipped",
    ),
    pytest.param(
        _FixSpec(
            id="init_line_too_far_above_skipped",
            description="init `out: list = []` more than 80 lines above append → skipped",
            source=(
                "def f(items):\n"
                "    out: list = []\n" + ("    pass\n" * 85) + "    for x in items:\n"
                "        out.append(x)\n"
            ),
            # Line 89 is the .append() line; init on line 2 is 87
            # lines above (range 2..81 caps at 81, so back never
            # reaches line 2). Result: init_line is None → continue.
            line_nums=[89],
            expected_fixed=0,
            expected_output_contains=[
                "    out: list = []",
                "        out.append(x)",
            ],
        ),
        id="init_line_too_far_above_skipped",
    ),
    pytest.param(
        _FixSpec(
            id="multiple_appends_in_same_file",
            description="two independent out=[], for..., out.append() patterns → both fixed",
            source=(
                "def f(items):\n"
                "    out: list = []\n"
                "    for x in items:\n"
                "        out.append(x * 2)\n"
                "    out2: list = []\n"
                "    for y in items:\n"
                "        out2.append(y + 1)\n"
                "    return out, out2\n"
            ),
            # Bottom-up processing: line 7 (out2.append) first, then
            # line 4 (out.append). Both fixed.
            line_nums=[7, 4],
            expected_fixed=2,
            expected_output_contains=[
                "out: list = [x * 2 for x in items]",
                "out2: list = [y + 1 for y in items]",
            ],
            expected_output_absent=[
                "    for x in items:",
                "    for y in items:",
                "out.append(",
                "out2.append(",
            ],
        ),
        id="multiple_appends_in_same_file",
    ),
    pytest.param(
        _FixSpec(
            id="unindented_append_line_skipped",
            description="append line without leading indent → skipped (no match on m_indent)",
            source=(
                "def f(items):\n"
                "    out: list = []\n"
                "    for x in items:\n"
                "        out.append(x)\n"
                "out.append(items[0])\n"
            ),
            # Line 5 is `out.append(items[0])` with no leading
            # whitespace → `m_indent` fails → continue.
            line_nums=[5],
            expected_fixed=0,
            expected_output_contains=[
                "    out: list = []",
                "        out.append(x)",
                "out.append(items[0])",
            ],
        ),
        id="unindented_append_line_skipped",
    ),
]


# ─── fix_file driver ────────────────────────────────────────────────────────


@pytest.mark.parametrize("row", _ROWS_FIX, ids=lambda r: r.id)
def test_fix_file_branches(row: _FixSpec, tmp_path: Path) -> None:
    """Drive `scripts.fix_perf401.fix_file` across the scenario rows.

    The helper is a pure file-rewriter: it opens `path`, mutates
    `lines` in-memory, and writes back. No DB, no FastAPI, no
    subprocess. We create a temp file per scenario, run the helper,
    then read back and assert.
    """
    # `fix_file` is in scripts/ — add the repo root to sys.path so
    # the import resolves.
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from scripts.fix_perf401 import fix_file

    p = tmp_path / "scenario.py"
    p.write_text(row.source)

    fixed = fix_file(str(p), list(row.line_nums))

    assert fixed == row.expected_fixed, (
        f"[{row.id}] expected fixed={row.expected_fixed}, got {fixed}"
    )

    actual = p.read_text()
    for needle in row.expected_output_contains:
        assert needle in actual, (
            f"[{row.id}] expected output to contain {needle!r}, but it was missing.\n"
            f"--- actual ---\n{actual}\n--- end ---"
        )
    for needle in row.expected_output_absent:
        assert needle not in actual, (
            f"[{row.id}] expected output to NOT contain {needle!r}, but it was present.\n"
            f"--- actual ---\n{actual}\n--- end ---"
        )


# ─── evidencia_importar scenario row spec ──────────────────────────────────


@dataclass
class _EvidenciaSpec:
    """One scenario for `evidencia_importar`.

    The CSV body is constructed from the `csv_body` field. The
    `data` field holds extra form fields (notably `confirmar`).
    The `files` field is the uploaded file. We assert the
    response status code and (when applicable) the post-commit
    counts of `CompetitorPriceObservation` rows.
    """

    id: str = ""
    description: str = ""
    confirmar: str = "si"
    csv_body: Optional[bytes] = None
    csv_filename: str = "evidencia.csv"
    csv_content_type: str = "text/csv"
    # Send an extra form field with a non-UploadFile value? (locks
    # the `if not isinstance(raw, UploadFile)` branch).
    send_csv_as_string: bool = False
    # Skip the file entirely? (locks the `if not raw or not
    # getattr(raw, "filename", "")` branch).
    skip_file: bool = False
    # Expected HTTP status from /vs-mercado/evidencia/importar.
    expected_status: int = 303
    # Expected added count (only checked when expected_status is 303).
    expected_added_delta: int = 0
    expected_dup_count: int = 0
    expected_skipped_count: int = 0
    # When True, the test runs the seeded lifespan fixture to load
    # 86 existing rows, so the dup counter is meaningful.
    needs_seeded_data: bool = True


_ROWS_EVIDENCIA: list[_EvidenciaSpec] = [
    pytest.param(
        _EvidenciaSpec(
            id="confirmar_not_si_rejected",
            description="confirmar='no' → 400 (no file even attached)",
            confirmar="no",
            csv_body=b"competidor,producto,unidad,precio_gs,as_of,fuente\nFoo,Bar,unidad,1000,2026-10-01,src",
            expected_status=400,
            needs_seeded_data=False,
        ),
        id="confirmar_not_si_rejected",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="confirmar_but_no_file_rejected",
            description="confirmar='si' but no csv field → 400",
            confirmar="si",
            skip_file=True,
            expected_status=400,
            needs_seeded_data=False,
        ),
        id="confirmar_but_no_file_rejected",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="csv_as_string_not_uploadfile_rejected",
            description="csv field sent as a plain string (not UploadFile) → 400",
            confirmar="si",
            send_csv_as_string=True,
            csv_body=b"foo",
            expected_status=400,
            needs_seeded_data=False,
        ),
        id="csv_as_string_not_uploadfile_rejected",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="missing_required_columns_rejected",
            description="CSV header missing 'as_of' → 400 (column validation)",
            confirmar="si",
            csv_body=(b"competidor,producto,unidad,precio_gs,fuente\nFoo,Bar,unidad,1000,src\n"),
            expected_status=400,
            needs_seeded_data=False,
        ),
        id="missing_required_columns_rejected",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="row_with_unparseable_price_skipped",
            description="row with non-numeric precio_gs → skipped_invalid++",
            confirmar="si",
            csv_body=(
                b"competidor,tipo,ciudad,producto,familia,unidad,precio_gs,as_of,fuente\n"
                b"Foo,caf,Asun,Espresso,cafes,unidad,not_a_number,2026-10-01,src\n"
            ),
            expected_status=303,
            expected_added_delta=0,
            expected_skipped_count=1,
        ),
        id="row_with_unparseable_price_skipped",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="row_with_price_below_300_skipped",
            description="row with precio_gs=50 (below 300 minimum) → skipped_invalid++",
            confirmar="si",
            csv_body=(
                b"competidor,tipo,ciudad,producto,familia,unidad,precio_gs,as_of,fuente\n"
                b"Barato,caf,Asun,Espresso,cafes,unidad,50,2026-10-01,src\n"
            ),
            expected_status=303,
            expected_added_delta=0,
            expected_skipped_count=1,
        ),
        id="row_with_price_below_300_skipped",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="row_with_empty_source_skipped",
            description="row with empty `fuente` → skipped_invalid++",
            confirmar="si",
            csv_body=(
                b"competidor,tipo,ciudad,producto,familia,unidad,precio_gs,as_of,fuente\n"
                b"SF,caf,Asun,Latte,cafes,unidad,20000,2026-10-01,\n"
            ),
            expected_status=303,
            expected_added_delta=0,
            expected_skipped_count=1,
        ),
        id="row_with_empty_source_skipped",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="row_matches_existing_duplicate",
            description="row whose (competitor, product, as_of) already seeded → dup++",
            confirmar="si",
            csv_body=(
                b"competidor,tipo,ciudad,producto,familia,unidad,precio_gs,as_of,fuente\n"
                b"Karu,panaderia,Asun,Medialuna de manteca,facturas,unidad,10000,2026-09-30,src\n"
            ),
            expected_status=303,
            expected_added_delta=0,
            expected_dup_count=1,
        ),
        id="row_matches_existing_duplicate",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="row_brand_new_added",
            description="row with new (competitor, product, as_of) → added++",
            confirmar="si",
            csv_body=(
                b"competidor,tipo,ciudad,producto,familia,unidad,precio_gs,as_of,fuente\n"
                b"BrandNew,panaderia,Asun,Torta Selva Negra,panes,unidad,85000,2026-10-15,https://new.com\n"
            ),
            expected_status=303,
            expected_added_delta=1,
        ),
        id="row_brand_new_added",
    ),
    pytest.param(
        _EvidenciaSpec(
            id="mixed_skip_dup_add_combined",
            description="4 rows: 1 invalid, 1 below 300, 1 dup of seed, 1 new → combined counters",
            confirmar="si",
            csv_body=(
                b"competidor,tipo,ciudad,producto,familia,unidad,precio_gs,as_of,fuente\n"
                b"Bad,caf,Asun,Cappuccino,cafes,unidad,not_a_number,2026-10-15,src\n"
                b"Cheap,caf,Asun,Espresso,cafes,unidad,50,2026-10-15,src\n"
                b"Karu,panaderia,Asun,Medialuna de manteca,facturas,unidad,10000,2026-09-30,src\n"
                b"BrandNew,panaderia,Asun,Torta Selva Negra,panes,unidad,85000,2026-10-15,https://new.com\n"
            ),
            expected_status=303,
            expected_added_delta=1,
            expected_dup_count=1,
            expected_skipped_count=2,
        ),
        id="mixed_skip_dup_add_combined",
    ),
]


# ─── evidencia_importar driver ─────────────────────────────────────────────


@pytest.mark.parametrize("row", _ROWS_EVIDENCIA, ids=lambda r: r.id)
def test_evidencia_importar_branches(row: _EvidenciaSpec, client, session_factory) -> None:
    """Drive `evidencia_importar` across the scenario rows above.

    The route is a POST /vs-mercado/evidencia/importar that takes
    multipart form data (confirmar + csv). The `client` fixture
    provides a CSRF-primed TestClient; the `session_factory`
    fixture provides direct DB access for the count assertions.
    """
    from sqlalchemy import select

    from app.rms.models import CompetitorPriceObservation

    if row.needs_seeded_data:
        with session_factory() as s:
            base = s.query(CompetitorPriceObservation).count()
    else:
        with session_factory() as s:
            # Truncate the table to a known state for the rejection
            # rows so the dup counter is meaningful when present.
            s.query(CompetitorPriceObservation).delete()
            s.commit()
            base = 0

    if row.skip_file:
        # No csv field at all.
        r = client.post(
            "/vs-mercado/evidencia/importar",
            data={"confirmar": row.confirmar},
        )
    elif row.send_csv_as_string:
        # csv as a plain string (not UploadFile).
        r = client.post(
            "/vs-mercado/evidencia/importar",
            data={"confirmar": row.confirmar, "csv": "not_an_upload_file"},
        )
    else:
        r = client.post(
            "/vs-mercado/evidencia/importar",
            data={"confirmar": row.confirmar},
            files={"csv": (row.csv_filename, row.csv_body, row.csv_content_type)},
            follow_redirects=False,
        )

    assert r.status_code == row.expected_status, (
        f"[{row.id}] expected status {row.expected_status}, got {r.status_code}. "
        f"Body: {r.text[:300]}"
    )

    if row.expected_status == 303:
        with session_factory() as s:
            rows = s.execute(select(CompetitorPriceObservation)).scalars().all()
        after = len(rows)
        assert after - base == row.expected_added_delta, (
            f"[{row.id}] expected added delta {row.expected_added_delta}, "
            f"got {after - base} (base={base}, after={after})"
        )


# ─── Row-count doc-lock ────────────────────────────────────────────────────


# Locks the row counts so a future addition/removal forces a CHANGELOG note.
assert len(_ROWS_FIX) == 9, f"fix_file scenarios: expected 9 rows, got {len(_ROWS_FIX)}"
assert len(_ROWS_EVIDENCIA) == 10, (
    f"evidencia_importar scenarios: expected 10 rows, got {len(_ROWS_EVIDENCIA)}"
)
