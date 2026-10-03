"""Final cleaner: place pytestmark correctly.

Strategy: scan each file. If it has `pytestmark = pytest.mark.X` somewhere
(valid or not), remove ALL of those lines. Then insert a single
`pytestmark = pytest.mark.X` line at the top of the file (after the
docstring + __future__ imports), followed by a blank line.

Also ensures `import pytest` exists.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tests"

TAG_FOR = {
    "test_smoke_all_routes.py": "smoke",
    "test_smoke_review_user_stories.py": "smoke",
    "test_smoke_all_pdf_endpoints.py": "smoke",
    "test_smoke_all_csv_exports.py": "smoke",
    "test_reportes_pages_load.py": "smoke",
    "test_dashboard_visual.py": "smoke",
    "test_dashboard_kpis_end_to_end.py": "smoke",
    "test_dashboard_deltas.py": "smoke",
    "test_reliability.py": "smoke",
    "test_hierarchy_endpoints.py": "smoke",
    "test_clientes_crud_roundtrip.py": "crud",
    "test_clientes_filter.py": "crud",
    "test_customers.py": "crud",
    "test_suppliers_crud_roundtrip.py": "crud",
    "test_products_crud_roundtrip.py": "crud",
    "test_recipes_polymorphic_roundtrip.py": "crud",
    "test_settings_roundtrip.py": "crud",
    "test_settings_seed_demo.py": "crud",
    "test_qseed_quick.py": "crud",
    "test_pedidos.py": "crud",
    "test_audit_log.py": "security",
    "test_csrf.py": "security",
    "test_csrf_local_dev.py": "security",
    "test_csrf_on_forms.py": "security",
    "test_security_headers.py": "security",
    "test_rate_limit.py": "security",
    "test_auth_login_logout.py": "auth",
    "test_auth.py": "auth",
    "test_auth_gate.py": "auth",
    "test_auth_integration.py": "auth",
    "test_auth_supabase.py": "auth",
    "test_analytics.py": "analytics",
    "test_costing.py": "analytics",
    "test_accounting.py": "analytics",
    "test_dashboard_analytics_sections.py": "analytics",
    "test_food_cost.py": "analytics",
    "test_dashboard_perf.py": "perf",
    "test_no_legacy_warnings.py": "manual",
    "test_demo_reset_safety.py": "manual",
}


def normalize(path: Path, marker: str) -> bool:
    text = path.read_text()
    # 1. Strip ALL existing pytestmark lines.
    text = re.sub(r"^pytestmark = pytest\.mark\.\w+\n", "", text, flags=re.MULTILINE)
    # Also strip blank-line doubles that were left behind.
    # 2. Ensure `import pytest` is present.
    if "import pytest" not in text:
        # Place it after `from __future__ import annotations` if present.
        lines = text.splitlines(keepends=True)
        out = []
        inserted = False
        for line in lines:
            out.append(line)
            if not inserted and line.strip() == "from __future__ import annotations":
                out.append("\nimport pytest\n")
                inserted = True
        if not inserted:
            # Place at top after the docstring.
            pattern = re.compile(r'^\s*""".*?"""\s*\n', re.DOTALL | re.MULTILINE)
            m = pattern.search(text)
            if m:
                # Insert just before m.end()
                insert_at = m.end()
                text = text[:insert_at] + "import pytest\n\n" + text[insert_at:]
            else:
                text = "import pytest\n" + text
        text = "".join(out)
    # 3. Insert `pytestmark = pytest.mark.X` once, immediately after the
    # `import pytest` line (or after __future__).
    lines = text.splitlines(keepends=True)
    out = []
    inserted = False
    for i, line in enumerate(lines):
        out.append(line)
        if not inserted and line.strip().startswith("import pytest"):
            out.append(f"\npytestmark = pytest.mark.{marker}\n")
            inserted = True
    if not inserted:
        # Fallback: insert at top of file (shouldn't happen)
        text = f"import pytest\npytestmark = pytest.mark.{marker}\n" + text
    else:
        text = "".join(out)
    path.write_text(text)
    return True


def main() -> None:
    for fname, marker in TAG_FOR.items():
        p = ROOT / fname
        if not p.exists():
            continue
        normalize(p, marker)
        print(f"Normalized: {fname}")


if __name__ == "__main__":
    main()
