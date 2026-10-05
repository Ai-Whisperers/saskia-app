#!/usr/bin/env python3
"""Inventory every _seed_* helper across the test suite.

Output format:
  function_name  file1.py file2.py ...  suggested_qseed_scenario

Maps duplicated private helpers to either existing qseed scenarios
or new ones that need to be created.

Usage:
    python3 scripts/inventory_seed_helpers.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

TESTS_DIR = Path(__file__).parent.parent / "tests"


def main() -> int:
    # Walk all test files and collect (function_name, file_path) pairs
    seed_helpers: dict[str, set[str]] = defaultdict(set)
    for py_file in sorted(TESTS_DIR.rglob("*.py")):
        text = py_file.read_text()
        # Find function definitions like `def _seed_basic(...)`
        for match in re.finditer(r"def (_seed_\w+)\s*\(", text):
            name = match.group(1)
            seed_helpers[name].add(str(py_file.relative_to(TESTS_DIR.parent)))

    # Print inventory, sorted by usage count
    print("# Seed Helper Migration Map")
    print()
    print(f"{'Helper':<25} {'Files':<8} Suggested qseed scenario")
    print("-" * 80)
    by_count = sorted(seed_helpers.items(), key=lambda kv: -len(kv[1]))
    for name, files in by_count:
        count = len(files)
        # Suggest a qseed scenario based on naming convention
        suggestion = suggest_scenario(name)
        print(f"{name:<25} {count:<8} qseed({suggestion!r})")
    print()
    print(f"Total unique seed helpers: {len(seed_helpers)}")
    print(f"Total duplicate occurrences: {sum(len(f) for f in seed_helpers.values())}")
    print(f"Files touched: {len(set().union(*seed_helpers.values()))}")

    # Print detailed mapping
    print()
    print("# Files per helper (for migration planning)")
    last_count = 0
    for name, files in by_count:
        count = len(files)
        last_count = count
        if count >= 2:  # Only show duplicated ones
            print(f"\n## {name} ({count} files)")
            for f in sorted(files):
                print(f"  - {f}")
    _ = last_count

    return 0


def suggest_scenario(name: str) -> str:
    """Map a _seed_X helper name to a qseed scenario."""
    mapping = {
        "basic": "basic",
        "kyrian": "with_kyrian_full",
        "kyrian_full": "with_kyrian_full",
        "customer": "with_customer",
        "sale": "with_sale",
        "voided_sale": "with_voided_sale",
        "pedido": "with_pending_pedido",
        "pending_pedido": "with_pending_pedido",
        "low_stock": "with_low_stock",
        "waste": "with_waste",
        "complex_recipe": "with_complex_recipe",
        "audit_log": "with_audit_log",
        "supplier": "with_supplier",
    }
    # Extract the suffix after _seed_
    suffix = name.replace("_seed_", "", 1).replace("_seed", "")
    return mapping.get(suffix, f'"with_{suffix}"')  # suggested as new scenario


if __name__ == "__main__":
    sys.exit(main())
