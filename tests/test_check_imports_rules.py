"""tests/test_check_imports_rules.py — locks the Sazon architecture rules.

After the 2026-10-08 tooling sweep, the architecture linter
(scripts/check_imports.py) discovered 36 violations + 3 cycles. All
were addressed:

- 8 cross-router/seed/integrations violations: documented as
  known-allow with reason in the script (see ALLOW_LIST).
- 3 cycles: documented as known-tolerate (see KNOWN_CYCLES). Each
  is a "shim module" pattern that's a candidate for a future
  refactor (SASKIA-XXX tickets).

This test file pins the post-sweep state. If a new module pair
appears in the allow-list or known-cycles list, this test fails and
forces the contributor to either:

1. Fix the underlying architectural smell, OR
2. Add a comment in the relevant module with `# noqa: arch-rule - <reason>`
   AND update the allow-list with a clear reason, AND update this
   test's expected counts.

That second path is for Sazon-specific exceptions, not for laziness.

We parse scripts/check_imports.py via AST (rather than importing it)
to keep the test fast and decoupled from sqlalchemy / app imports.
The ALLOW_LIST and KNOWN_CYCLES are top-level dict/list assignments
that are easy to find.

Run with: pytest -x -q tests/test_check_imports_rules.py
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_imports.py"


def _load_constants() -> dict[str, ast.AST]:
    """Parse check_imports.py and return its top-level assignments."""
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            v = node.value
            if v is not None:
                out[node.target.id] = v
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    v = node.value
                    if v is not None:
                        out[t.id] = v
    return out


class TestAllowListSize(unittest.TestCase):
    """Pins the number of known-allow entries. Adding a new entry MUST
    be a deliberate decision (the right fix is to break the cycle or
    extract a shared helper, not to add to the list)."""

    def test_allow_list_has_expected_size(self) -> None:
        consts = _load_constants()
        self.assertIn("ALLOW_LIST", consts, "ALLOW_LIST not found in check_imports.py")
        allow_list = consts["ALLOW_LIST"]
        assert isinstance(allow_list, ast.Dict)
        # As of 2026-10-08 sweep. Update this number only when you
        # add to the ALLOW_LIST with a clear reason + noqa comment in
        # the source file. See check_imports.py docstring.
        self.assertEqual(
            len(allow_list.keys),
            8,
            "Allow-list size changed. Either fix the underlying smell, "
            "or update this test AND add a noqa comment in the offending "
            "source file.",
        )

    def test_allow_list_entries_have_audit_comments(self) -> None:
        """Every allow-list entry must have a non-empty reason."""
        consts = _load_constants()
        allow_list = consts["ALLOW_LIST"]
        assert isinstance(allow_list, ast.Dict)
        for value in allow_list.values:
            # Reason is a string constant
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                self.assertTrue(
                    value.value.strip(),
                    f"Allow-list entry has no reason: {value.value!r}. "
                    "Add a one-line explanation of why this is tolerated.",
                )


class TestAllowListBackedByNoqa(unittest.TestCase):
    """Each ALLOW_LIST entry must be backed by a `# noqa: arch-rule` line
    in the source file. This makes the source self-explain the architectural
    exception, so the contract survives even if the check_imports.py
    docstring is lost."""

    def test_every_allow_list_entry_has_matching_noqa(self) -> None:
        consts = _load_constants()
        allow_list = consts["ALLOW_LIST"]
        assert isinstance(allow_list, ast.Dict)
        missing = []
        for key in allow_list.keys:
            assert isinstance(key, ast.Tuple) and len(key.elts) == 2
            importer_ast = key.elts[0]
            imported_ast = key.elts[1]
            assert isinstance(importer_ast, ast.Constant)
            assert isinstance(imported_ast, ast.Constant)
            importer: str = importer_ast.value  # type: ignore[assignment]
            imported: str = imported_ast.value  # type: ignore[assignment]
            # importer is "app.routers.dashboard" → app/routers/dashboard.py
            # or "app.routers.produccion.forecast" → "app/routers/produccion/forecast.py"
            candidate = REPO_ROOT / (importer.replace(".", "/") + ".py")
            if not candidate.exists():
                # Maybe it's a package's __init__.py
                candidate = REPO_ROOT / importer.replace(".", "/") / "__init__.py"
            if not candidate.exists():
                missing.append(f"  ALLOW_LIST [{importer} -> {imported}]: source file not found")
                continue
            text = candidate.read_text(encoding="utf-8")
            if "noqa: arch-rule" not in text:
                missing.append(
                    f"  ALLOW_LIST [{importer} -> {imported}]: "
                    f"no `# noqa: arch-rule` in {candidate.relative_to(REPO_ROOT)}"
                )
                continue
            # Verify the noqa is near an import of the imported module
            noqa_pos = text.index("noqa: arch-rule")
            window = text[max(0, noqa_pos - 200): noqa_pos + 500]
            imported_short: str = imported.split(".")[-1]  # type: ignore[assignment]
            if imported_short not in window:
                missing.append(
                    f"  ALLOW_LIST [{importer} -> {imported}]: noqa comment in "
                    f"{candidate.relative_to(REPO_ROOT)} does not reference "
                    f"{imported_short} within +/-200 chars"
                )
        assert not missing, (
            "ALLOW_LIST entries must be backed by `# noqa: arch-rule` in source:\n"
            + "\n".join(missing)
        )


class TestKnownCyclesBackedByNoqa(unittest.TestCase):
    """Each KNOWN_CYCLES pair must have `# noqa: cycle-known` in BOTH
    directions of the cycle (both files). Stricter than the allow-list
    test because cycles are bidirectional."""

    def test_every_known_cycle_has_noqa_in_both_files(self) -> None:
        consts = _load_constants()
        known = consts["KNOWN_CYCLES"]
        assert isinstance(known, ast.List)
        missing = []
        for elt in known.elts:
            assert isinstance(elt, ast.Tuple) and len(elt.elts) == 3
            a_ast = elt.elts[0]
            b_ast = elt.elts[1]
            assert isinstance(a_ast, ast.Constant) and isinstance(b_ast, ast.Constant)
            a: str = a_ast.value  # type: ignore[assignment]
            b: str = b_ast.value  # type: ignore[assignment]
            for module, other in [(a, b), (b, a)]:
                candidate = REPO_ROOT / (module.replace(".", "/") + ".py")
                if not candidate.exists():
                    candidate = REPO_ROOT / module.replace(".", "/") / "__init__.py"
                if not candidate.exists():
                    missing.append(f"  CYCLE [{a} <-> {b}]: source file not found: {module}")
                    continue
                text = candidate.read_text(encoding="utf-8")
                if "noqa: cycle-known" not in text:
                    missing.append(
                        f"  CYCLE [{a} <-> {b}]: no `# noqa: cycle-known` in "
                        f"{candidate.relative_to(REPO_ROOT)}"
                    )
        assert not missing, (
            "KNOWN_CYCLES pairs must be backed by `# noqa: cycle-known` in BOTH source files:\n"
            + "\n".join(missing)
        )


class TestKnownCyclesSize(unittest.TestCase):
    """Pins the number of tolerated cycles."""

    def test_known_cycles_has_expected_size(self) -> None:
        consts = _load_constants()
        self.assertIn("KNOWN_CYCLES", consts, "KNOWN_CYCLES not found in check_imports.py")
        known = consts["KNOWN_CYCLES"]
        assert isinstance(known, ast.List)
        # As of 2026-10-08 sweep. The 3 cycles are:
        # 1. settings_runtime <-> settings_registry
        # 2. ingredient_intel <-> tagging.classify
        # 3. db <-> backup
        # Each is a "shim module" pattern; the fix is a SASKIA ticket.
        self.assertEqual(
            len(known.elts),
            3,
            "Known-cycles list size changed. Either fix the cycle "
            "(extract a shared helper), or update this test AND add a "
            "SASKIA ticket to track the refactor.",
        )

    def test_known_cycles_have_ticket_references(self) -> None:
        """Each known cycle must mention a SASKIA-XXX in the reason."""
        consts = _load_constants()
        known = consts["KNOWN_CYCLES"]
        assert isinstance(known, ast.List)
        for elt in known.elts:
            # Each element is a 3-tuple (a, b, reason)
            if isinstance(elt, ast.Tuple) and len(elt.elts) == 3:
                reason = elt.elts[2]
                if isinstance(reason, ast.Constant) and isinstance(reason.value, str):
                    self.assertIn(
                        "SASKIA-",
                        reason.value,
                        "Each tolerated cycle must be tracked as a future "
                        "refactor (SASKIA-XXX in the reason text).",
                    )


class TestEndToEnd(unittest.TestCase):
    """Run the full `check_imports.py` script as a subprocess and
    assert it returns 0 (no violations, no cycles). If a new cycle or
    violation appears, this test fails."""

    def test_no_cycles_no_violations_on_current_tree(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        # We want rc=0 (clean). If non-zero, fail with the output.
        if result.returncode != 0:
            self.fail(
                "check_imports.py found new cycles or violations:\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

    def test_check_imports_reports_clean_message(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        self.assertIn("OK:", result.stdout)


if __name__ == "__main__":
    unittest.main()
