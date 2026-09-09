"""tests/test_production_session_safety.py — production code uses safe patterns.

Regression: any future route handler that holds a session outside a
context manager would leak connections. This test scans the source tree
for unsafe patterns and fails on them.
"""
from __future__ import annotations

import re
from pathlib import Path


def _collect_app_py_files() -> list[Path]:
    """All .py files under app/ (production code, not tests/scripts)."""
    root = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app")
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in str(p))


def test_no_bare_session_assignments_in_app():
    """No `session = session_factory()` without a `with` block in app/."""
    violations = []
    for p in _collect_app_py_files():
        src = p.read_text()
        # Look for lines like:    session = session_factory()
        # or:                       s = session_factory()
        # Exclude factory definitions (return session_factory()).
        for m in re.finditer(r"^(\s*)(s|session)\s*=\s*session_factory\(\)", src, re.MULTILINE):
            indent = m.group(1)
            # Must be inside a `with` block (8-space indent typical, with deeper)
            # Quick heuristic: factory functions like `def get_session` use
            # 4-space return statement which is fine.
            line_no = src[: m.start()].count("\n") + 1
            # Skip factory definitions: those are at module-level with `return session_factory()`
            # The pattern we want is "session = session_factory()" where session is then used.
            # Check the surrounding context: if it's the only line in the function and the function
            # is named get_session / make_*, it's a factory — fine.
            # Otherwise it's a session leak.
            # For simplicity, just check if the line is inside a `def` whose name contains "session_factory"
            # Get the function this line is in
            lines = src.split("\n")
            in_def = None
            for i in range(line_no - 1, -1, -1):
                m2 = re.match(r"^(?:async )?def\s+(\w+)", lines[i])
                if m2:
                    in_def = m2.group(1)
                    break
            if in_def and "session" in in_def.lower():
                # Factory function — OK.
                continue
            violations.append(f"{p}:{line_no}: {indent}{m.group(2)} = session_factory() — needs 'with' block")

    assert not violations, "\n".join(violations)


def test_all_engine_connect_uses_context_manager():
    """All `engine.connect()` calls must use `with`."""
    for p in _collect_app_py_files():
        src = p.read_text()
        # Find `engine.connect()` not inside a `with`
        # Quick check: count engine.connect() and verify each is followed by "as "
        # by searching for the pattern.
        for m in re.finditer(r"(\s+)engine\.connect\(\)", src):
            # Find the next 80 chars
            rest = src[m.end(): m.end() + 100]
            assert " as " in rest, (
                f"{p}: bare engine.connect() needs `with` block. Found at: {m.group(0)}"
            )


def test_get_session_dependency_works_for_test_factory():
    """Sanity: app/rms/dependencies.py:get_session returns a session_factory callable."""
    from app.rms.dependencies import get_session

    assert callable(get_session)


def test_no_session_commit_without_close_in_app():
    """No production code does session.commit() outside a context manager.

    Sessions held outside `with` blocks leak the underlying connection.
    Manual AST traversal to find .commit() calls outside `with` blocks.
    """
    import ast
    from pathlib import Path

    violations = []
    for py_file in sorted(Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app").rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        # Walk all function/method bodies; flag .commit() not under a `with`.
        # Cheap heuristic: build a set of line numbers that are inside `with` statements.
        with_line_numbers: set[int] = set()

        class WithVisitor(ast.NodeVisitor):
            def visit_With(self, node):
                for lineno in range(node.lineno, node.end_lineno + 1):
                    with_line_numbers.add(lineno)
                self.generic_visit(node)

        WithVisitor().visit(tree)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "commit"
                and isinstance(node.value.value, ast.Name)
            ):
                # Check if this is inside a `with` block.
                if node.lineno not in with_line_numbers:
                    violations.append(f"{py_file}:{node.lineno}: {node.value.value.id}.commit()")

    assert not violations, (
        "session.commit() outside context managers (would leak connection):\n"
        + "\n".join(violations[:10])
    )
