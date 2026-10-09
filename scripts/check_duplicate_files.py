#!/usr/bin/env python3
"""scripts/check_duplicate_files.py — catch duplicate-name and dead modules.

Sazon tooling rec 2026-10-08. Catches:
1. **Duplicate-stem files** (e.g. `settings.py` + `settings_original.py`) — these
   usually indicate a half-completed refactor.
2. **Forbidden legacy modules** (deleted files that should not come back) —
   currently `settings_original.py` and `production_scheduler.py`.
3. **Possibly-unused modules** — files that no other module imports (the
   heuristic catches legitimately-unused code; manual review required).

Usage:
    python scripts/check_duplicate_files.py             # check + report
    python scripts/check_duplicate_files.py --strict    # fail on dead modules
    python scripts/check_duplicate_files.py --json      # machine-readable output

Exit codes:
    0 = clean
    1 = duplicate-stem files found
    2 = possibly-unused modules (only with --strict)
    3 = forbidden legacy modules found
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

# Configurable. Adjust to match Sazon's actual layout.
ROOTS = ["app/", "scripts/"]
EXCLUDE_DIRS = {
    "app/templates",  # Jinja templates, not Python
    "app/_archive",
    "app/.venv",
    "app/__pycache__",
    "scripts/__pycache__",
    ".venv",
    "node_modules",
    ".git",
    ".hermes",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}

# Files that were deleted in the 2026-10-08 tooling sweep and must
# not be re-added without explicit re-justification.
FORBIDDEN_LEGACY = {
    "app/rms/settings_original.py",
    "app/rms/production_scheduler.py",
}

# Modules that exist and are imported by the rest of the app, so we
# don't flag them as "possibly unused". Edit this when the canonical
# set changes (e.g. entry points, decorators-only files).
KNOWN_ENTRY_POINTS = {
    "app/rms/main.py",  # FastAPI app entry
    "app/rms/__init__.py",  # package init
    "app/rms/AGENTS.md",  # not py, but keep the check happy
    "app/rms/migrations/__init__.py",  # migration registry
    "app/rms/seed/__init__.py",  # seed package
    "app/rms/seed/sazon.py",  # referenced via `from app.rms.seed import sazon`
    "app/rms/seed/packs.py",  # referenced via `from app.rms.seed import packs`
    "app/rms/seed/demo.py",  # same
    "app/rms/seed/competitor_seed.py",
    "app/rms/seed/competitor_prices.py",
    "app/rms/seed/competitor_shoppings.py",
    "app/rms/seed/pack_demo.py",
    "app/rms/seed/menu_import.py",
    "app/rms/seed/onboard.py",
    "app/rms/services/__init__.py",
    "app/rms/services/closures.py",  # referenced by routers
    "app/rms/services/expenses.py",
    "app/rms/services/common.py",
    "app/rms/sales/__init__.py",
    "app/rms/sales/lifecycle.py",
    "app/rms/sales/pre_sale_check.py",
    "app/rms/sales/pre_sale_check_cart.py",
    "app/rms/loyalty/__init__.py",
    "app/rms/loyalty/ledger.py",
    "app/rms/loyalty/tiers.py",
    "app/rms/loyalty/suggestions.py",
    "app/rms/tagging/__init__.py",
    "app/rms/tagging/audit.py",
    "app/rms/tagging/audit_repair.py",
    "app/rms/tagging/cache.py",
    "app/rms/tagging/classify.py",
    "app/rms/tagging/derive.py",
    "app/rms/tagging/ensure.py",
    "app/rms/tagging/filters.py",
    "app/rms/tagging/model.py",
    "app/rms/tagging/vocabulary.py",
    "app/rms/models/__init__.py",  # re-exports
    "app/rms/models/audit.py",  # mixin
    "app/rms/models/auth.py",  # User, etc.
    "app/rms/models/catalogs_restored.py",
    "app/rms/models/channels.py",
    "app/rms/models/closure.py",
    "app/rms/models/common.py",
    "app/rms/models/core.py",  # Base
    "app/rms/models/delivery.py",
    "app/rms/models/herbus_drive.py",
    "app/rms/models/inventory.py",
    "app/rms/models/orders.py",
    "app/rms/models/procurement.py",
    "app/rms/models/production.py",
    "app/rms/models/sales.py",
    "app/rms/models/sales/__init__.py",
    "app/rms/models/sales/core.py",
    "app/rms/profitability/__init__.py",
    "app/rms/profitability/cost.py",
    "app/seed/__init__.py",
    "app/services/__init__.py",
    "app/routers/__init__.py",
    "app/routers/produccion/__init__.py",
    "app/integrations/__init__.py",
    "app/observability/__init__.py",
}


def _stem_variants(name: str) -> set[str]:
    """Return the set of normalized stems a file could match.

    e.g. settings_original.py and settings.py both normalize to 'settings'.
    """
    base = name[:-3] if name.endswith(".py") else name
    stem = re.sub(
        r"(_original|_backup|_legacy|_deprecated|_old|_v\d+|_new|_copy|_v2|_v3)$",
        "",
        base,
    )
    return {base, stem}


def find_duplicate_stems(root: str) -> dict[str, list[str]]:
    """Find groups of files in `root` whose stems collide.

    Sazon's intentional MVC pattern is `app/routers/X.py` +
    `app/rms/X.py` + `app/rms/models/X.py`. Those stems are EXPECTED
    to collide. We filter out:

    1. `__init__.py` (one per package — always a collision)
    2. The standard (router + service) or (router + service + model)
       pattern: when files in different standard layers share a stem,
       that is by design.

    We still report if the SAME LAYER has 2+ files with the same stem
    (e.g. two routers, two services, two seed files). Those are the
    real smells.
    """
    by_stem: dict[str, list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if any(ex in dirpath for ex in EXCLUDE_DIRS):
            continue
        for f in filenames:
            if not f.endswith(".py"):
                continue
            if f == "__init__.py":
                continue
            full = os.path.join(dirpath, f)
            for s in _stem_variants(f):
                by_stem.setdefault(s, []).append(full)
    out: dict[str, list[str]] = {}
    for stem, paths in by_stem.items():
        unique = sorted(set(paths))
        if len(unique) <= 1:
            continue
        # Determine the "layer" of each path
        layers = [_layer(full) for full in unique]
        # If every file is in a DIFFERENT layer, this is the standard
        # Sazon MVC pattern — not a smell.
        if len(set(layers)) == len(unique):
            continue
        # Else: at least one layer has 2+ files with this stem. Real
        # smell — flag it.
        out[stem] = unique
    return out


# Sazon standard layers, ordered from "outer" to "inner".
_LAYERS = [
    "app/integrations",
    "app/observability",
    "app/seed",
    "app/services",
    "app/routers",  # thin HTTP handlers
    "app/rms/seed",  # seed scripts (Sazon convention)
    "app/rms/sales",  # sub-domain packages
    "app/rms/models/sales",  # sub-domain model package
    "app/rms/loyalty",
    "app/rms/tagging",
    "app/rms/profitability",
    "app/rms/migrations",
    "app/rms/models",  # SQLAlchemy models
    "app/rms/services",  # business logic
    "app/rms",  # top-level rms package (root modules)
]


def _layer(path: str) -> str:
    """Return the Sazon layer a file lives in. Longest-prefix wins."""
    # Normalize to use / not os.sep for cross-platform robustness
    norm = path.replace(os.sep, "/")
    best = ""
    for L in _LAYERS:
        if norm.startswith(L + "/") or norm == L:
            if len(L) > len(best):
                best = L
    # Catch-all for the Sazon root
    if not best:
        if norm.startswith("app/"):
            return "app"
    return best or "unknown"


def find_forbidden_legacy() -> list[str]:
    """Return paths of any forbidden legacy files that exist on disk."""
    return [p for p in FORBIDDEN_LEGACY if os.path.isfile(p)]


def _is_app_import(imp: str) -> bool:
    """True if this is an internal app import (not a stdlib/third-party)."""
    return imp.startswith("app.") or imp.startswith(".")


def _gather_imports(path: str) -> set[str]:
    """AST-walk a file and return its set of internal `app.*` imports.

    Resolves relative imports to absolute (assuming `path` lives under
    the project root). Returns a set of dotted module paths.
    """
    if not os.path.isfile(path):
        return set()
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, UnicodeDecodeError):
        return set()
    imports: set[str] = set()
    # Compute package path (for relative import resolution)
    rel = os.path.relpath(path, ".")
    parts = rel.split(os.sep)[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_app_import(alias.name):
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level and node.level > 0:
                # Relative import
                base_parts = parts[: -node.level] if node.level <= len(parts) else []
                if mod:
                    base_parts = base_parts + mod.split(".")
                else:
                    # `from . import x` — just the package
                    pass
                if base_parts:
                    resolved = ".".join(base_parts)
                    if _is_app_import(resolved) or resolved.startswith("app."):
                        imports.add(resolved)
                    # Also track the specific name imported (for `from . import x`)
                    for alias in node.names:
                        imports.add(resolved + "." + alias.name if resolved else alias.name)
            else:
                if _is_app_import(mod):
                    imports.add(mod)
    return imports


def find_possibly_unused(root: str) -> list[str]:
    """Find modules that nothing else imports.

    Heuristic — not perfect. False positives include:
    - Module is loaded dynamically (importlib.import_module(...))
    - Module is loaded by entry point (FastAPI app, CLI)
    - Module is a plugin/extension

    Manual review required.
    """
    # Gather all import targets from the codebase
    all_imports: set[str] = set()
    py_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if any(ex in dirpath for ex in EXCLUDE_DIRS):
            continue
        for f in filenames:
            if f.endswith(".py"):
                full = os.path.join(dirpath, f)
                py_files.append(full)
                all_imports |= _gather_imports(full)

    unused: list[str] = []
    for path in py_files:
        rel = os.path.relpath(path, ".")
        # Build the dotted module path
        if rel.endswith("/__init__.py"):
            mod = rel[: -len("/__init__.py")].replace(os.sep, ".")
        else:
            mod = rel[:-3].replace(os.sep, ".")
        # If anyone imports this module (exact or as parent), it's used
        if mod in all_imports:
            continue
        if any(imp == mod or imp.startswith(mod + ".") for imp in all_imports):
            continue
        if rel in KNOWN_ENTRY_POINTS:
            continue
        # If a __init__.py in the same package does `from .X import *`
        # we already counted that.
        unused.append(rel)
    return sorted(unused)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on possibly-unused modules too (default: warn only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable report",
    )
    args = parser.parse_args()

    report: dict = {
        "duplicate_stems": {},
        "forbidden_legacy": [],
        "possibly_unused": [],
    }
    exit_code = 0

    for root in ROOTS:
        report["duplicate_stems"].update(find_duplicate_stems(root))

    report["forbidden_legacy"] = find_forbidden_legacy()

    all_unused: list[str] = []
    for root in ROOTS:
        all_unused.extend(find_possibly_unused(root))
    report["possibly_unused"] = all_unused

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if report["forbidden_legacy"]:
            print("=" * 70)
            print("ERROR: forbidden legacy files present (should be deleted):")
            for p in report["forbidden_legacy"]:
                print(f"  - {p}")
            print("  See docs/operations/2026-10-08-tooling-hardening.md")
            print("=" * 70)
            print()
            exit_code = max(exit_code, 3)

        if report["duplicate_stems"]:
            print("=" * 70)
            print("WARN: duplicate-stem files (likely half-completed refactor):")
            for stem, paths in sorted(report["duplicate_stems"].items()):
                print(f"  stem='{stem}':")
                for p in paths:
                    print(f"    - {p}")
            print("=" * 70)
            print()
            exit_code = max(exit_code, 1)

        if report["possibly_unused"]:
            if args.strict:
                print("=" * 70)
                print(f"ERROR: {len(report['possibly_unused'])} possibly-unused module(s):")
                for p in report["possibly_unused"]:
                    print(f"  - {p}")
                print("  Manual review required. False positives OK if dynamic import.")
                print("=" * 70)
                print()
                exit_code = max(exit_code, 2)
            else:
                print(
                    f"INFO: {len(report['possibly_unused'])} possibly-unused module(s) "
                    f"(use --strict to fail). Sample:"
                )
                for p in report["possibly_unused"][:5]:
                    print(f"  - {p}")
                if len(report["possibly_unused"]) > 5:
                    print(f"  ... and {len(report['possibly_unused']) - 5} more")
                print()

        if exit_code == 0:
            print("OK: no duplicate-stem files, no forbidden legacy, no unused modules.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
