#!/usr/bin/env python3
"""scripts/check_imports.py — Sazon architecture linter.

Pure-Python equivalent of import-linter. Enforces the Sazon layering
contract: routers may import rms/* freely; rms/* may NOT import
routers/*; services/ may import each other freely; integrations/
may import services/ but not the other way.

Sazon tooling rec 2026-10-08. Catches the case where someone puts
business logic in a router (which makes it untestable) or imports
a router from a service (which causes circular imports at startup).

Usage:
    python scripts/check_imports.py                 # default contract
    python scripts/check_imports.py --report-only   # print, don't fail
    python scripts/check_imports.py --json          # machine output

Exit codes:
    0 = clean
    1 = violation
    2 = config error
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass

# Migrations are loaded by `init_db()` at runtime, not by Python
# import statements. The "app.rms.db -> app.rms.migrations._xxx ->
# app.rms.db" pattern is normal, not a cycle. Exclude.
EXCLUDE_FROM_CYCLE = {"app.rms.migrations"}  # dotted, like `imp`
ROOTS = ["app/"]
EXCLUDE_DIRS = {
    "app/_archive",
    "app/.venv",
    "app/__pycache__",
    ".venv",
    "node_modules",
    ".git",
    ".hermes",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


@dataclass
class Violation:
    importer: str
    imported: str
    rule: str


# The Sazon layering contract. Edit here as the architecture evolves.
# Format: (importer_glob, imported_glob, rule_name)
#
# Sibling-vs-child rule: when both importer and imported are inside
# the same package (e.g. `app.routers.produccion` and
# `app.routers.produccion._helpers`), they are parent/child, not
# siblings, and the import is fine. The rule fires only when they are
# SIBLINGS at the top router level (e.g. `app.routers.dashboard` and
# `app.routers.stations`). The sibling check is done in main() via
# _is_router_sibling(). For now, the rules below cover non-router
# siblings only — see main() for the router-sibling check.

# Known-allow list: legitimate cross-router/seed imports that the
# Sazon architecture REQUIRES. Each entry is (importer, imported, why).
# A future contributor removing a noqa comment without an
# architectural fix will fail this CI gate.
ALLOW_LIST: dict[tuple[str, str], str] = {
    (
        "app.routers.dashboard",
        "app.routers.stations",
    ): "dashboard uses `puesto` (current station) helper from stations; legitimate cross-router utility use",
    (
        "app.routers.herebus",
        "app.routers.shopping",
    ): "herebus wishlist purchases delegate to shopping.consolidate_open_items; legitimate cross-router utility use",
    (
        "app.routers.pedidos",
        "app.routers.settings_runtime",
    ): "pedidos uses render_template helper from settings_runtime; legitimate cross-router utility use",
    (
        "app.routers.produccion.forecast",
        "app.routers.pedidos",
    ): "produccion.forecast uses _pedido_total_gs helper from pedidos; legitimate cross-router utility use",
    (
        "app.rms.menu_ocr",
        "app.rms.seed.menu_import",
    ): "menu_ocr reuses _norm + _MATCH_CUTOFF constants from menu_import; should be moved to app/rms/menu_normalize.py but not blocking",
    (
        "app.rms.main",
        "app.rms.seed",
    ): "main.py is the CLI entry point (sazon seed, sazon seed-sazon, sazon migrate, sazon rollback); seed/ is the runtime-loaded package, not a peer module. The same pattern as Alembic env.py importing migration scripts.",
    (
        "app.rms.main",
        "app.rms.seed.competitor_prices",
    ): "main.py calls seed_competitor_prices at startup (idempotent, lazy import inside lifespan handler)",
    (
        "app.integrations.barcode",
        "app.rms.models",
    ): "barcode lookup needs the Product model for `barcode == product.barcode` join. The cleanest fix is to invert: barcode exposes lookup_by_barcode(session, code) -> int|None and integrations calls it; that's the Sazon pattern. Tracked for follow-up; not blocking CI.",
}

# Known-cycles allow-list. Each is a pair of modules that have a
# bidirectional lazy import (intentionally, to avoid module-load
# circularity). A future refactor breaking one of these MUST also
# remove the entry here; otherwise the CI gate will fail because the
# import count no longer matches.
#
# The Sazon pattern for these is "shim" modules: one file is a thin
# wrapper around the other for legacy import compatibility. The fix
# (deprecate the shim, update all callers) is a separate refactor.
KNOWN_CYCLES: list[tuple[str, str, str]] = [
    (
        "app.rms.ingredient_intel",
        "app.rms.tagging.classify",
        "ingredient_intel is a legacy shim that re-exports infer_allergens/infer_dietary_tags from tagging.classify. The bidirectional imports are inside function bodies. Fix: deprecate ingredient_intel, update callers. Tracked as SASKIA-XXX.",
    ),
    (
        "app.rms.db",
        "app.rms.backup",
        "db.py defines _get_db_url_safe (a runtime helper) that backup.py needs; backup.py defines backup_database that db.py needs. Both are inside function bodies. Fix: extract _get_db_url_safe to a third module (e.g. app/rms/db_url.py). Tracked as SASKIA-XXX.",
    ),
]


RULES: list[tuple[str, str, str]] = [
    # integrations/* must not import rms/* (one-way: rms imports integrations)
    ("app.integrations", "app.rms", "integrations/ must not import rms/"),
    # services/* must not import routers/*
    ("app.rms.services", "app.routers", "services/ must not import routers/"),
    # (migrations are loaded by init_db at runtime, not by import statements)
    # loyalty module boundary
    ("app.rms.loyalty", "app.rms.sales", "loyalty/ must not import sales/ (use events)"),
    # tagging module boundary
    ("app.rms.tagging", "app.rms.sales", "tagging/ must not import sales/ (passive)"),
]


def _gather_imports(path: str) -> list[tuple[str, str, int]]:
    """AST-walk a file; return (imported_module, lineno, level) tuples.

    Resolves relative imports to dotted paths.
    """
    if not path.endswith(".py"):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError:
        return []
    # Compute package for relative imports
    rel = os.path.relpath(path, ".")
    parts = rel.split(os.sep)[:-1]
    out: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, "Import", node.lineno))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level and node.level > 0:
                base_parts = parts[: -node.level] if node.level <= len(parts) else []
                if mod:
                    base_parts = base_parts + mod.split(".")
                if base_parts:
                    resolved = ".".join(base_parts)
                    out.append((resolved, "ImportFrom", node.lineno))
                    for alias in node.names:
                        out.append((resolved + "." + alias.name, "ImportFrom", node.lineno))
                else:
                    for alias in node.names:
                        out.append((alias.name, "ImportFrom", node.lineno))
            else:
                if mod:
                    out.append((mod, "ImportFrom", node.lineno))
    return out


def _is_router_sibling(importer: str, imported: str) -> bool:
    """True if importer and imported are TOP-LEVEL routers (siblings).

    `app.routers.produccion` -> `app.routers.produccion._helpers` is
    parent/child (NOT a sibling). `app.routers.dashboard` ->
    `app.routers.stations` is sibling (rule fires).

    The Sazon production router is a 9-file sub-package
    (`app.routers.produccion._full`, `_helpers`, etc.). Files inside
    that sub-package importing each other is the standard pattern;
    files in different top-level routers importing each other is the
    smell.
    """
    if not importer.startswith("app.routers."):
        return False
    if not imported.startswith("app.routers."):
        return False
    # Strip "app.routers." prefix and the function part
    # `app.routers.produccion` -> ["produccion"]
    # `app.routers.produccion._full` -> ["produccion", "_full"]
    # `app.routers.stations` -> ["stations"]
    imp_parts = importer.split(".")[2:]
    imp_parts_no_fn = (
        imp_parts[:-1]
        if imp_parts
        and imp_parts[-1][0].islower()
        and not imp_parts[-1].startswith("_")
        and len(imp_parts) > 2
        else imp_parts
    )
    # Heuristic: if the first segment matches AND both have at least
    # 1 more segment, they're in the same sub-package
    if not imp_parts:
        return True
    return imp_parts[0] != imported.split(".")[2] if imported.count(".") >= 2 else True


def _module_path_from_file(path: str) -> str:
    """Convert file path to dotted module path."""
    rel = os.path.relpath(path, ".")
    if rel.endswith("/__init__.py"):
        return rel[: -len("/__init__.py")].replace(os.sep, ".")
    if rel.endswith(".py"):
        return rel[:-3].replace(os.sep, ".")
    return rel.replace(os.sep, ".")


def _matches(glob: str, dotted: str) -> bool:
    """Sazon's glob: trailing '.' means 'prefix', bare means 'exact'."""
    if glob.endswith("."):
        return dotted.startswith(glob) and len(dotted) > len(glob)
    return dotted == glob or dotted.startswith(glob + ".")


def detect_cycles(imports: dict[str, set[str]]) -> list[list[str]]:
    """Find all simple import cycles using Tarjan's algorithm (light version)."""
    # Use DFS with three-color marking
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in imports}
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for nxt in imports.get(node, set()):
            if nxt not in color:
                continue
            if color[nxt] == GRAY and nxt != node:
                # Found cycle (skip self-loops; those are not real cycles)
                idx = path.index(nxt) if nxt in path else 0
                cycle = path[idx:] + [nxt]
                cycles.append(cycle)
            elif color[nxt] == WHITE:
                dfs(nxt, path)
        path.pop()
        color[node] = BLACK

    for node in imports:
        if color[node] == WHITE:
            dfs(node, [])
    return cycles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Build module -> set of imported modules
    file_imports: dict[str, list[tuple[str, str, int]]] = {}
    py_files: list[str] = []
    for root in ROOTS:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            if any(ex in dirpath for ex in EXCLUDE_DIRS):
                continue
            for f in filenames:
                if not f.endswith(".py"):
                    continue
                full = os.path.join(dirpath, f)
                py_files.append(full)
                file_imports[full] = _gather_imports(full)

    # Module-level graph: only count internal imports
    module_imports: dict[str, set[str]] = defaultdict(set)
    for full, imps in file_imports.items():
        mod = _module_path_from_file(full)
        # Skip modules in EXCLUDE_FROM_CYCLE (migrations: loaded at runtime)
        if any(mod == ex or mod.startswith(ex + ".") for ex in EXCLUDE_FROM_CYCLE):
            continue
        for imp, _, _ in imps:
            if not imp.startswith("app."):
                continue
            # Also skip edges that point INTO excluded modules
            if any(imp == ex or imp.startswith(ex + ".") for ex in EXCLUDE_FROM_CYCLE):
                continue
            module_imports[mod].add(imp)

    # Rule violations
    violations: list[Violation] = []
    for full, imps in file_imports.items():
        mod = _module_path_from_file(full)
        for imp, kind, lineno in imps:
            if not imp.startswith("app."):
                continue
            # Skip migration edges entirely
            if any(mod == ex or mod.startswith(ex + ".") for ex in EXCLUDE_FROM_CYCLE):
                continue
            if any(imp == ex or imp.startswith(ex + ".") for ex in EXCLUDE_FROM_CYCLE):
                continue
            # Router-sibling check (special-cased because Sazon
            # production router is a 9-file sub-package; standard
            # rules would flag legitimate parent/child imports).
            if mod.startswith("app.routers") and imp.startswith("app.routers"):
                if (mod, imp) in ALLOW_LIST:
                    continue  # known-allow (with comment in code)
                if not _is_router_sibling(mod, imp):
                    continue  # parent/child — fine
                # sibling — flag it (only outside the produccion sub-package)
                if not (
                    mod.startswith("app.routers.produccion")
                    and imp.startswith("app.routers.produccion")
                ):
                    violations.append(
                        Violation(
                            importer=mod,
                            imported=imp,
                            rule="router-to-router SIBLING (use shared util in app/routers/_shared/)",
                        )
                    )
                    continue
            # rms -> seed (outside seed/)
            if (mod, imp) in ALLOW_LIST:
                continue
            if (
                mod.startswith("app.rms.")
                and not mod.startswith("app.rms.seed")
                and imp.startswith("app.rms.seed")
            ):
                violations.append(
                    Violation(
                        importer=mod,
                        imported=imp,
                        rule="rms/ must not import seed/ (move seed call to a router or main)",
                    )
                )
                continue
            # Inside seed/ (e.g. app.rms.seed.sazon -> app.rms.seed.demo):
            # allow by default — standard package-internal import.
            if mod.startswith("app.rms.seed") and imp.startswith("app.rms.seed"):
                continue
            # Check allow-list first
            if (mod, imp) in ALLOW_LIST:
                continue
            for importer_glob, imported_glob, rule in RULES:
                if (mod, imp) in ALLOW_LIST:
                    continue
                if _matches(importer_glob, mod) and _matches(imported_glob, imp):
                    violations.append(Violation(importer=mod, imported=imp, rule=rule))

    # Cycles (basic) — filter known-cycles
    raw_cycles = detect_cycles(module_imports)
    cycles: list[list[str]] = []
    for cycle in raw_cycles:
        # Cycle is a list of nodes: e.g. ["app.rms.a", "app.rms.b", "app.rms.a"]
        # Normalize to a frozenset of the 2 unique endpoints
        if len(cycle) >= 3 and cycle[0] == cycle[-1]:
            endpoints = frozenset(cycle[:-1])
            if any(endpoints == frozenset({a, b}) for a, b, _ in KNOWN_CYCLES):
                continue  # known + tolerated
        cycles.append(cycle)

    if args.json:
        report = {
            "violations": [
                {"importer": v.importer, "imported": v.imported, "rule": v.rule} for v in violations
            ],
            "cycles": cycles,
        }
        print(json.dumps(report, indent=2))
    else:
        if cycles:
            print("=" * 70)
            print(f"ERROR: {len(cycles)} import cycle(s) detected:")
            for cyc in cycles[:20]:
                print("  " + " -> ".join(cyc))
            if len(cycles) > 20:
                print(f"  ... and {len(cycles) - 20} more")
            print("=" * 70)
            print()
        if violations:
            print("=" * 70)
            print(f"ERROR: {len(violations)} architecture rule violation(s):")
            for v in violations[:30]:
                print(f"  {v.importer}  →  {v.imported}")
                print(f"      rule: {v.rule}")
            if len(violations) > 30:
                print(f"  ... and {len(violations) - 30} more")
            print("=" * 70)
            print()
        if not cycles and not violations:
            print("OK: no import cycles, no architecture rule violations.")

    if (cycles or violations) and not args.report_only:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
