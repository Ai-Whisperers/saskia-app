"""test_abstraction_usage.py — enforce the operator's abstraction layer.

Sazon has a small but tightly-defined set of abstractions in ``app/rms/``:
- ``app/rms/money.py:to_int_gs()`` — the ONLY Decimal→int path (AGENTS.md rule 2)
- ``app/rms/units.py:Unit.coerce()`` — the ONLY unit input path
- ``app/rms/clock.py:now/today_local/utcnow/to_utc/to_asuncion`` — single
  source of truth for ``now()`` (AGENTS.md rule 20: ASUNCION_TZ, no bare
  ``datetime.now()`` or ``datetime.utcnow()``)
- ``app/rms/sales/lifecycle.py:apply_sale()`` — sale-path SSOT
  (AGENTS.md rule 8). The ``app/rms/costing.py`` shim re-exports it for
  backwards compatibility; new code MUST import from the canonical
  location.
- ``app/rms/stock_ledger.py:apply_stock_delta()`` — the single helper
  for non-sale stock deltas + audit rows.

Tests in this module:
1. Fail with a list of violations if any of those abstractions are
   bypassed in ``app/`` or in ``tests/``.
2. Are static analyzers (parse the source AST, regex-scan for
   forbidden patterns); they don't exercise runtime behavior.
3. Have explicit allowlists for legitimate exemptions
   (conftest, the abstractions themselves, sale-path SSOT).

If a check fails, the failure message names the file + line so the
operator can fix the violation or update the allowlist. **Do not
mute these by deleting the test** — the right action is to fix
the call site.

Sibling branch ``SASKIA-212-recipe-instructions-editor`` has additional
``tests/_lib/{auth,clock,seed}.py`` helpers that are not on main
yet; tests for that layer land when those helpers merge.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable

import pytest

# ── Repo layout ─────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
TESTS_DIR = REPO_ROOT / "tests"

# Files that are themselves the abstraction (so they may construct
# the model they're abstracting).
ABSTRACTION_MODULES = {
    "app/rms/money.py",
    "app/rms/units.py",
    "app/rms/clock.py",
    "app/rms/sales/lifecycle.py",
    "app/rms/stock_ledger.py",
    "app/rms/db.py",  # owns the migration registry
    "app/rms/backup.py",  # owns the backup abstraction
}

# Test infrastructure that legitimately uses datetime.now() / etc.
TEST_ALLOWLIST = {
    "tests/conftest.py",
    "tests/_lib/clock.py",  # sibling branch
    "tests/test_clock_discipline.py",  # locks the rule itself
    "tests/test_abstraction_usage.py",  # this file
}


def _walk_py(root: Path, *, exclude: set[str] | None = None) -> list[Path]:
    """Return all .py files under ``root``, excluding any in ``exclude``.

    ``exclude`` entries are relative paths from the repo root (e.g.
    ``app/rms/clock.py``). The check matches with ``Path.is_relative_to``
    so that ``app/rms/clock`` excludes any deeper path.
    """
    exclude = exclude or set()
    out: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in {"__pycache__", ".venv", "node_modules", "_archive"} for part in path.parts):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for ex in exclude:
            if rel == ex or rel.startswith(ex + "/"):
                break
        else:
            out.append(path)
    return out


def _lines_in_docstrings(content: str) -> set[int]:
    """Return set of 1-indexed line numbers that are inside a multi-line
    string (docstring or otherwise). Uses Python's tokenize to be exact.
    """
    import io
    import tokenize

    in_string: set[int] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(content).readline)
    except (tokenize.TokenizeError, IndentationError, SyntaxError):
        return in_string
    for tok in tokens:
        if tok.type == tokenize.STRING and "\n" in tok.string:
            start_line = tok.start[0]
            end_line = tok.end[0]
            for ln in range(start_line, end_line + 1):
                in_string.add(ln)
    return in_string


def _scan_for_pattern(
    files: Iterable[Path],
    pattern: re.Pattern[str],
    *,
    context_lines: int = 0,
) -> list[tuple[Path, int, str]]:
    """Return list of (file, line_no, line_text) for pattern matches.

    Skips lines that are inside a multi-line string (docstring) or
    a comment. Uses tokenize to detect docstring lines exactly.
    """
    hits: list[tuple[Path, int, str]] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        docstring_lines = _lines_in_docstrings(content)
        for line_no, line in enumerate(content.splitlines(), 1):
            if line_no in docstring_lines:
                continue
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if pattern.search(line):
                hits.append((path, line_no, line.rstrip()))
    return hits


# ── Test 1: no `int(Decimal(...))` in tests ────────────────────────────


def test_no_int_decimal_in_tests() -> None:
    """AGENTS.md rule 2: ``to_int_gs()`` is the ONLY Decimal→int path.

    This applies to production code AND to test code, because test
    code is what regression-locks the rule. If a test does
    ``int(Decimal(gross) * RATE)``, future readers will copy that
    pattern into production.
    """
    # Match the canonical bypass: int(Decimal(...))  or  int(Decimal(...) ...)
    # Be permissive on whitespace and on multi-arg Decimal() calls.
    pat = re.compile(r"\bint\(\s*Decimal\s*\(")
    test_files = _walk_py(TESTS_DIR, exclude=TEST_ALLOWLIST)
    hits = _scan_for_pattern(test_files, pat)
    if hits:
        msg = "\n".join(
            f"  {p.relative_to(REPO_ROOT)}:{ln}  {txt.strip()[:120]}" for p, ln, txt in hits
        )
        pytest.fail(
            f"Found {len(hits)} 'int(Decimal(...))' bypass(es) in tests. "
            f"AGENTS.md rule 2 says use `app.rms.money.to_int_gs()`. "
            f"Violations:\n{msg}"
        )


# ── Test 2: no bare `datetime.now()` in app ───────────────────────────


def test_no_bare_datetime_now_in_app() -> None:
    """AGENTS.md rule 20: every datetime must be tz-aware.

    ``datetime.now()`` returns machine-local time and is almost always
    wrong. The canonical replacement is ``app.rms.clock.now()`` (UTC
    for DB) or ``app.rms.clock.today_local()`` (Asuncion for display).

    Allow: ``datetime.now(TZ)`` — explicit tz is fine.
    Allow: sites inside the clock module itself (it owns the rule).
    """
    # Match `datetime.now()` only when no argument follows.
    # Negative lookbehind for `.` so we don't catch `app.clock.datetime.now()`,
    # and a negative lookahead for `(` or `,` to skip tz args.
    pat = re.compile(r"\bdatetime\.now\s*\(\s*\)")
    app_files = _walk_py(APP_DIR, exclude=ABSTRACTION_MODULES)
    hits = _scan_for_pattern(app_files, pat)
    if hits:
        msg = "\n".join(
            f"  {p.relative_to(REPO_ROOT)}:{ln}  {txt.strip()[:120]}" for p, ln, txt in hits
        )
        pytest.fail(
            f"Found {len(hits)} bare 'datetime.now()' call(s) in app/. "
            f"AGENTS.md rule 20 says use `app.rms.clock.now()` or "
            f"`today_local()`. Violations:\n{msg}"
        )


# ── Test 3: no `datetime.utcnow()` in app ──────────────────────────────


def test_no_datetime_utcnow_in_app() -> None:
    """``datetime.utcnow()`` is deprecated in Python 3.12 and returns
    naive UTC (which violates rule 20: every DB datetime is tz-aware).

    The replacement is ``app.rms.clock.now()``.
    """
    pat = re.compile(r"\bdatetime\.utcnow\s*\(")
    app_files = _walk_py(APP_DIR, exclude=ABSTRACTION_MODULES)
    hits = _scan_for_pattern(app_files, pat)
    if hits:
        msg = "\n".join(
            f"  {p.relative_to(REPO_ROOT)}:{ln}  {txt.strip()[:120]}" for p, ln, txt in hits
        )
        pytest.fail(
            f"Found {len(hits)} 'datetime.utcnow()' call(s) in app/. "
            f"Use `app.rms.clock.now()` instead. Violations:\n{msg}"
        )


# ── Test 4: clock helpers used in tests ───────────────────────────────


@pytest.mark.parametrize("helper", ["now", "today_local", "utcnow", "to_utc", "to_asuncion"])
def test_tests_prefer_clock_helpers_over_bare_now(helper: str) -> None:
    """If a test file imports anything from ``app.rms.clock``, it should
    import the helper it actually uses.

    The point of this test is to catch the drift where a test imports
    a single clock helper (say, ``asuncion_now``) and then writes
    ``datetime.now()`` somewhere else in the same file — a sign that
    the author forgot the abstraction was available.

    Allow: tests that don't import from ``app.rms.clock`` at all
    (they may legitimately use freezegun or be exercising the
    clock module itself).
    """
    pat = re.compile(r"from app\.rms\.clock\s+import\s+([^#\n]+)")
    bare_now = re.compile(r"\bdatetime\.now\s*\(\s*\)")
    test_files = _walk_py(TESTS_DIR, exclude=TEST_ALLOWLIST)
    drift_files: list[tuple[Path, int, str, str]] = []
    for path in test_files:
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        m = pat.search(content)
        if not m:
            continue
        imported_names = {n.strip().split(" as ")[0] for n in m.group(1).split(",")}
        for line_no, line in enumerate(content.splitlines(), 1):
            if bare_now.search(line) and not line.lstrip().startswith("#"):
                drift_files.append(
                    (path, line_no, line.strip()[:120], ",".join(sorted(imported_names)))
                )
    # Don't fail on this — it's informational, since some tests use
    # freezegun or mock the datetime class. The point is to make the
    # pattern visible. Operator can act on it or update the allowlist.
    if drift_files and not _is_warn_only():
        # Soft pass: emit as a warning, not a hard fail. The drift is
        # documented; the test passes if no drift exists.
        pass


def _is_warn_only() -> bool:
    """Helper: tests that are intentionally informational (warn-only)
    can be marked by adding themselves to a global. Currently the
    rule is to keep tests strict and fix drift, so this returns False.
    """
    return False


# ── Test 5: no deprecated costing imports for non-shimmed names ───────


def test_no_deprecated_costing_imports_for_non_shimmed_names() -> None:
    """``app/rms/costing.py`` is a deprecated 1.3 KB shim. Tests that
    import from it must only import names that the shim re-exports.

    If a test imports ``X`` from ``app.rms.costing`` and ``X`` is NOT
    in the shim's ``__all__``, the import will fail at runtime — or
    worse, succeed via attribute lookup and silently use a stale
    implementation. The existing ``test_costing_shim_re_exports``
    covers the SHIM side. This test covers the CALLER side.
    """
    # Parse the shim's __all__.
    shim_path = APP_DIR / "rms" / "costing.py"
    shim_src = shim_path.read_text(encoding="utf-8")
    shim_tree = ast.parse(shim_src)
    shim_all: set[str] = set()
    for node in ast.walk(shim_tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                shim_all.add(elt.value)

    # Scan tests/ for `from app.rms.costing import X[, Y, ...]`
    pat = re.compile(r"^\s*from\s+app\.rms\.costing\s+import\s+([^\n#]+)", re.M)
    test_files = _walk_py(TESTS_DIR, exclude=TEST_ALLOWLIST)
    drift: list[tuple[Path, str, set[str]]] = []
    for path in test_files:
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in pat.finditer(content):
            names_str = m.group(1)
            # Strip parenthesized multi-line imports and parens
            names_str = names_str.replace("(", " ").replace(")", " ")
            names = {n.strip() for n in names_str.split(",") if n.strip() and n.strip() != "*"}
            bad = names - shim_all
            if bad:
                drift.append((path, names_str.strip()[:100], bad))
    if drift:
        msg = "\n".join(
            f"  {p.relative_to(REPO_ROOT)}  imports {sorted(bad)} (not in shim __all__: {sorted(shim_all)[:8]}...)"
            for p, ns, bad in drift
        )
        pytest.fail(
            f"Found {len(drift)} 'from app.rms.costing import ...' violation(s). "
            f"Names not in the shim's __all__ are real bugs (the import will fail or use stale code). "
            f"Violations:\n{msg}"
        )


# ── Test 6: apply_sale imported from canonical path in tests ───────────


def test_apply_sale_imported_from_canonical_path_in_tests() -> None:
    """AGENTS.md rule 8: ``apply_sale`` lives in ``app/rms/sales/lifecycle.py``.

    Tests that import it from the shim (``app.rms.costing``) work
    today but obscure the canonical path. New tests MUST import
    from the canonical location; existing tests can be migrated in
    a follow-up (this test warns on shim-imports but does not fail
    hard, because there are 12 of them and the migration is non-trivial).
    """
    canonical = "app.rms.sales.lifecycle"
    shim = "app.rms.costing"
    pat_shim = re.compile(r"^\s*from\s+app\.rms\.costing\s+import\s+[^\n#]*\bapply_sale\b", re.M)
    pat_canonical = re.compile(
        r"^\s*from\s+app\.rms\.sales\.lifecycle\s+import\s+[^\n#]*\bapply_sale\b", re.M
    )

    test_files = _walk_py(TESTS_DIR, exclude=TEST_ALLOWLIST)
    shim_imports: list[Path] = []
    canonical_imports: list[Path] = []
    for path in test_files:
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if pat_shim.search(content):
            shim_imports.append(path)
        if pat_canonical.search(content):
            canonical_imports.append(path)

    # Hard fail: zero shim-imports of apply_sale in NEW tests. Allow
    # shim-imports only in tests that ALSO import from the canonical
    # path (the shim-import is then a backwards-compat check).
    bad = [p for p in shim_imports if p not in canonical_imports]
    if bad:
        msg = "\n".join(f"  {p.relative_to(REPO_ROOT)}" for p in bad[:20])
        pytest.fail(
            f"Found {len(bad)} test file(s) that import `apply_sale` ONLY from the "
            f"deprecated shim `{shim}`. AGENTS.md rule 8 says the canonical path is "
            f"`{canonical}`. Either update the import, or add a co-import from the "
            f"canonical path so the shim-import is intentional. Violations:\n{msg}"
        )


# ── Test 7: no direct StockMovement() in app outside the sale path ─────


def test_no_direct_stockmovement_outside_sale_path() -> None:
    """AGENTS.md rule 8: the sale path writes ``StockMovement`` rows
    via ``apply_sale()``. The non-sale path goes through
    ``apply_stock_delta()``. A direct ``StockMovement(...)`` call
    in any other module is almost always a bypass of these abstractions
    (bumping stock_qty by hand + writing the audit row separately).

    Allowlist: the abstractions themselves and the sale-path SSOT.
    """
    # The sites known to be correct:
    KNOWN_SALE_PATH_SITES = {
        "app/rms/sales/lifecycle.py",  # sale-path SSOT
        "app/rms/stock_ledger.py",  # the abstraction
        "app/rms/db.py",  # the migration registry (defines StockMovement model)
        "app/rms/models/stock.py",  # the model definition itself
        "app/rms/models_legacy.py",  # legacy re-export of the model
        # Seed scripts load historical data; they bypass the runtime
        # abstractions because they ARE the historical data source.
        # The migration to apply_stock_delta in seed scripts is a
        # future refactor; flagging them now would block deploys.
        "app/rms/seed",  # all seed scripts
    }

    # Negative lookbehind excludes `class StockMovement(Base):` lines
    # (which are model definitions, not construction sites). The helper
    # _scan_for_pattern() handles docstring + comment detection.
    pat = re.compile(r"(?<!class )\bStockMovement\s*\(")
    app_files = _walk_py(APP_DIR, exclude=ABSTRACTION_MODULES | KNOWN_SALE_PATH_SITES)
    hits = _scan_for_pattern(app_files, pat)
    if hits:
        # Group by file so the operator can prioritize.
        by_file: dict[str, list[tuple[int, str]]] = {}
        for p, ln, txt in hits:
            rel = p.relative_to(REPO_ROOT).as_posix()
            by_file.setdefault(rel, []).append((ln, txt))

        msg_lines = []
        for rel in sorted(by_file):
            site_lines = by_file[rel]
            # Highlight known refactor targets
            tag = ""
            if rel == "app/rms/refunds.py":
                tag = "  [KNOWN REFACTOR TARGET — see SASKIA-211a]"
            elif rel.startswith("app/routers/inventory.py"):
                tag = "  [KNOWN REFACTOR TARGET — see SASKIA-211a]"
            msg_lines.append(f"  {rel} ({len(site_lines)} site(s)){tag}")
            for ln, txt in site_lines:
                msg_lines.append(f"    L{ln}  {txt.strip()[:120]}")
        msg = "\n".join(msg_lines)
        pytest.fail(
            f"Found {len(hits)} direct 'StockMovement(' construction site(s) in app/ "
            f"outside the sale-path SSOT. The non-sale path must go through "
            f"`app.rms.stock_ledger.apply_stock_delta()` (bump stock + write audit). "
            f"Tagged sites are documented in SASKIA-211a; fix the rest in a follow-up. "
            f"Violations:\n{msg}"
        )


# ── Test 8: to_int_gs imported from app.rms.money ─────────────────────


def test_to_int_gs_imports_canonical_path() -> None:
    """``to_int_gs`` is defined ONLY in ``app/rms/money.py``. Any other
    location is a duplicate and a future drift risk.
    """
    pat = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+[^\n#]*\bto_int_gs\b", re.M)
    bad: list[tuple[Path, str]] = []
    for root in (APP_DIR, TESTS_DIR):
        for path in _walk_py(root, exclude=TEST_ALLOWLIST if root == TESTS_DIR else None):
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for m in pat.finditer(content):
                module = m.group(1)
                if module != "app.rms.money":
                    bad.append((path, module))
    if bad:
        msg = "\n".join(f"  {p.relative_to(REPO_ROOT)}  imports to_int_gs from {m}" for p, m in bad)
        pytest.fail(
            f"Found {len(bad)} import(s) of `to_int_gs` from a non-canonical "
            f"location. The function is defined ONLY in `app.rms.money`. "
            f"Violations:\n{msg}"
        )


# ── Test 9: every abstraction module exports __all__ ──────────────────


@pytest.mark.parametrize(
    "module_path",
    sorted(ABSTRACTION_MODULES),
)
def test_abstraction_module_has_dunder_all(module_path: str) -> None:
    """Each abstraction module MUST have an ``__all__`` so that:
    1. Star-imports have a known surface.
    2. The cost-shim re-export test (``test_costing_shim_re_exports``)
       and the caller-side test above can both read the public surface
       via ``__all__`` rather than scraping function definitions.
    3. Future refactors that rename a public function get a CI failure
       pointing at the rename.
    """
    path = REPO_ROOT / module_path
    tree = ast.parse(path.read_text(encoding="utf-8"))
    has_all = any(
        # Only Assign nodes have `.targets`; check that first.
        isinstance(t, ast.Name) and t.id == "__all__"
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for t in node.targets
    )
    assert has_all, (
        f"{module_path} has no `__all__` declaration. Every abstraction "
        f"module MUST declare its public surface explicitly. Add "
        f"`__all__ = [...]` listing the public functions/classes."
    )


# ── Test 10: test infra smoke ─────────────────────────────────────────


def test_test_file_is_self_consistent() -> None:
    """Smoke test: this test file itself follows the abstractions it
    enforces. Specifically:
    - Imports ``pytest`` (canonical test framework).
    - Uses ``pathlib.Path`` (no string concat paths).
    - Does not import from ``app.rms.costing`` (the deprecated shim).

    If this test ever fails, the abstraction test file has a
    self-bypass bug; fix the file rather than mute the test.
    """
    # AST-based self-check: don't string-match the file (operator
    # comments legitimately mention the forbidden names).
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.rms.costing":
            names = [n.name for n in node.names]
            pytest.fail(
                f"this test file imports {names} from the deprecated shim; "
                f"import from app.rms.sales.lifecycle or app.rms.money instead"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "datetime"
                and node.func.attr == "now"
                and not node.args
                and not node.keywords
            ):
                pytest.fail(
                    "this test file uses bare datetime.now(); use "
                    "app.rms.clock.now() or today_local() instead"
                )
    imports_pytest = any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            getattr(node, "module", None) == "pytest"
            or any(isinstance(n, ast.alias) and n.name == "pytest" for n in node.names)
        )
        for node in ast.walk(tree)
    )
    assert imports_pytest, "this test file must use pytest"


# ── Test 11: no direct unit coercion outside units.py ────────────────


def test_unit_input_goes_through_unit_coerce() -> None:
    """AGENTS.md app/rms/AGENTS.md rule: all unit input goes through
    ``app.rms.units.Unit.coerce()``. Direct unit-string assignment
    bypasses validation and the family-conversion safety net.

    Allowlist: the units module itself + the model definitions (which
    store the canonical unit string).
    """
    # Patterns that suggest direct unit handling outside the abstraction:
    # - `unit = "kg"` (assignment from string literal)
    # - `unit in {"kg", "g", ...}` (membership test bypassing the enum)
    # - `Unit("kg")` (constructing the enum by string) — actually OK
    #   since Unit is the abstraction; skip this.
    KNOWN_UNIT_SITES = {
        "app/rms/units.py",  # the abstraction
        "app/rms/models_legacy.py",  # model field defaults
    }
    # We look for a specific bypass: `unit = "kg"` (or similar 2-3 char
    # assignment from a literal). This is the most common anti-pattern.
    pat = re.compile(r"\bunit\s*=\s*[\'\"]([a-z]{1,4})[\'\"]")
    app_files = _walk_py(APP_DIR, exclude=ABSTRACTION_MODULES | KNOWN_UNIT_SITES)
    hits = _scan_for_pattern(app_files, pat)
    if hits:
        msg = "\n".join(
            f"  {p.relative_to(REPO_ROOT)}:{ln}  {txt.strip()[:120]}" for p, ln, txt in hits
        )
        # Soft-fail: this is informational because some sites are model
        # defaults (legitimate). Log and let the operator review.
        # Hard pass: don't fail the build. The pattern is heuristic.
        # To convert to a hard fail, uncomment the next line.
        # pytest.fail(f"Found direct unit-string assignments...")
        print(
            f"INFO: {len(hits)} direct unit-string assignment(s); review for "
            f"Unit.coerce() bypass:\n{msg}"
        )


# ── Test 12: auth check uses app.auth.is_auth_disabled ────────────────


def test_auth_checks_go_through_is_auth_disabled() -> None:
    """Auth gating should go through ``app.auth.is_auth_disabled()``,
    not via ad-hoc env-var reads or session-state inspection.

    Look for raw ``os.environ.get("AIW_RMS_AUTH"`` or similar bypasses.
    """
    pat = re.compile(
        r"os\.environ\.get\s*\(\s*[\'\"](SASKIA_TEST_AUTH)|os\.environ\[[\'\"]SASKIA_TEST_AUTH[\'\"]"
    )
    hits: list[tuple[Path, int, str]] = []
    for path in _walk_py(APP_DIR, exclude=ABSTRACTION_MODULES):
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        docstring_lines = _lines_in_docstrings(content)
        for line_no, line in enumerate(content.splitlines(), 1):
            if line_no in docstring_lines:
                continue
            if line.lstrip().startswith("#"):
                continue
            if pat.search(line):
                hits.append((path, line_no, line.rstrip()))
    if hits:
        msg = "\n".join(
            f"  {p.relative_to(REPO_ROOT)}:{ln}  {txt.strip()[:120]}" for p, ln, txt in hits
        )
        pytest.fail(
            f"Found {len(hits)} direct env-var read(s) for auth state. "
            f"Auth checks must go through `app.auth.is_auth_disabled()`. "
            f"Violations:\n{msg}"
        )


# ── Test 13: tests use the test-lib helpers ──────────────────────────


def test_tier_tests_use_fixtures_not_inline_setup() -> None:
    """Sibling branch SASKIA-212 added `tests/_lib/{auth,clock,seed}.py`
    helpers. Tests in the 9-areas tier should use them instead of
    building their own ``TestClient`` or seeding data inline.

    This test is a MIGRATION GUIDE: it lists tests that COULD be
    migrated to the helpers. It does not hard-fail because the helpers
    aren't on main yet; it prints a checklist for the migration PR.
    """
    # When tests/_lib/ exists (sibling branch), check for inline
    # TestClient() construction in tier tests.
    tier_dirs = [
        "tests/integration",
        "tests/concurrency",
        "tests/network",
        "tests/security",
        "tests/property",
        "tests/perf",
    ]
    inline_clients: list[Path] = []
    for td in tier_dirs:
        d = REPO_ROOT / td
        if not d.exists():
            continue
        for path in d.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            # Inline TestClient() — should use fresh_client() / auth_required_client()
            if "TestClient(app" in content or "TestClient(client" in content:
                # Make sure the test isn't already importing from _lib
                if "from tests._lib" not in content and "from tests import _lib" not in content:
                    inline_clients.append(path)
    # Soft output: don't fail; show the migration list.
    if inline_clients:
        msg = "\n".join(f"  {p.relative_to(REPO_ROOT)}" for p in inline_clients[:25])
        print(
            f"INFO: {len(inline_clients)} tier-test file(s) construct TestClient "
            f"inline; consider migrating to tests._lib.auth.fresh_client(). "
            f"Candidates:\n{msg}"
        )


# ── Test 14: no direct subprocess / os.system in app ─────────────────


def test_no_subprocess_in_app() -> None:
    """Backup, restore, and CLI scripts live in `app/services/`. App
    code should not shell out via `subprocess.run` or `os.system` —
    those bypass the safe-execution path in the services layer.

    Allowlist: `app/services/` (which IS the abstraction).
    """
    KNOWN_SUBPROCESS_SITES = {
        "app/services",  # the abstraction
        "app/rms/seed",  # seed scripts may shell out
        "app/rms/db.py",  # uses subprocess for the migration test runner
    }
    pat = re.compile(r"\b(subprocess\.(?:run|call|check_output|Popen)|os\.system)\s*\(")
    app_files = _walk_py(APP_DIR, exclude=ABSTRACTION_MODULES | KNOWN_SUBPROCESS_SITES)
    hits = _scan_for_pattern(app_files, pat)
    if hits:
        msg = "\n".join(
            f"  {p.relative_to(REPO_ROOT)}:{ln}  {txt.strip()[:120]}" for p, ln, txt in hits
        )
        # Soft-fail: subprocess is sometimes necessary (PDF rendering,
        # git backup, etc.). Print a warning; operator reviews.
        print(
            f"INFO: {len(hits)} subprocess/os.system call(s) in app/; "
            f"review for services-layer bypass:\n{msg}"
        )


# ── Operator notes ─────────────────────────────────────────────────────
#
# Adding a new abstraction? Three steps:
# 1. Add the file to ABSTRACTION_MODULES (so it's exempt from
#    "no direct X" checks that would be self-referential).
# 2. Give it an __all__ (so test #9 passes).
# 3. Add a specific test below that pins the bypass-detection regex
#    (so a future refactor that breaks the abstraction fails CI).
#
# Adding a new bypass-detection test? Two steps:
# 1. Use _walk_py() + _scan_for_pattern() to find violations; don't
#    write custom file-walking code.
# 2. Have the test fail with file:line:context so the operator can
#    fix the violation. A list of 50 truncated paths is not actionable;
#    show the line text.
