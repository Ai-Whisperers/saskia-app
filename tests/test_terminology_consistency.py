"""tests/test_terminology_consistency.py — SASKIA-310 CI gate.

Greps every template for the "don't use" English loan-word patterns
defined in `app/docs/glossary.md`. Fails CI on any new violation.

Run with: uv run pytest tests/test_terminology_consistency.py -v

Each rule is (regex, file_glob, allowed_substrings):
    regex:               the loan-word pattern (case-sensitive)
    file_glob:           match path against this glob; * matches everything
    allowed_substrings:  list of substrings; if ANY is on the same line, the
                         rule does NOT trigger (escape hatch for legit uses)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"

# (description, regex, file_glob, allowed_substrings)
# A rule fires when:
#   1. the file path matches file_glob
#   2. the regex matches somewhere on a line in that file
#   3. NO allowed_substring is present on that same line
RULES: list[tuple[str, str, str, list[str]]] = [
    # ---- Headers / labels (UI text) ----
    (
        "Header '<th>Diff</th>' — must be 'Diferencia'",
        r"<th[^>]*>\s*Diff\s*</",
        "*.html",
        [],
    ),
    (
        "Header '<th>Accuracy</th>' — must be 'Precisión'",
        r"<th[^>]*>\s*Accuracy\s*</",
        "*.html",
        [],
    ),
    (
        "Header '<th>Qty</th>' — must be 'Cantidad'",
        r"<th[^>]*>\s*Qty\s*</",
        "*.html",
        [],
    ),
    (
        "Header '<th>Status</th>' — must be 'Estado'",
        r"<th[^>]*>\s*Status\s*</",
        "*.html",
        [],
    ),
    (
        "Header '<th>Owner</th>' — must be 'Responsable'",
        r"<th[^>]*>\s*Owner\s*</",
        "*.html",
        [],
    ),
    (
        "Header '<th>Endpoint</th>' — must be 'Ruta'",
        r"<th[^>]*>\s*Endpoint\s*</",
        "*.html",
        [],
    ),
    (
        "Header '<th>COGS</th>' — must be 'Costo de Mercadería Vendida'",
        r"<th[^>]*>\s*COGS\s*</",
        "*.html",
        [],
    ),
    (
        "Header '<th>Revenue</th>' — must be 'Ingresos'",
        r"<th[^>]*>\s*Revenue\s*</",
        "*.html",
        [],
    ),
    # ---- User-visible labels in <span>, <label>, <h1>, <h2>, <p> ----
    (
        "Label '>Loyalty<' — must be 'Fidelización'",
        r">\s*Loyalty\s*<",
        "*.html",
        [],
    ),
    (
        "Label '>Batches<' — must be 'Tandas'",
        r">\s*Batches\s*<",
        "*.html",
        [],
    ),
    (
        "Label '>Forecast<' — must be 'Pronóstico'",
        r">\s*Forecast\s*<",
        "*.html",
        [],
    ),
    (
        "Label '>Override<' — must be 'Ajuste manual'",
        r">\s*Override\s*<",
        "*.html",
        [],
    ),
    (
        "Label '>Counterparty<' — must be 'Contraparte'",
        r">\s*Counterparty\s*<",
        "*.html",
        [],
    ),
    (
        "Label '>Reorder rate<' — must be 'Tasa de reposición'",
        r">\s*Reorder\s+rate",
        "*.html",
        [],
    ),
    (
        "Login 'Login OK' — must be 'Login exitoso'",
        r"Login\s+OK",
        "*.html",
        [],
    ),
    (
        "Login 'Login FAIL' — must be 'Login fallido'",
        r"Login\s+FAIL",
        "*.html",
        [],
    ),
]


def _all_template_files() -> list[Path]:
    return sorted(TEMPLATES_DIR.rglob("*.html"))


def _glob_match(path: Path, pattern: str) -> bool:
    """Simple glob match — pattern is matched against the file's basename
    (so '*.html' matches any .html regardless of subdir)."""
    return path.match(pattern) or path.name == pattern


def _scan_violations() -> list[str]:
    """Walk all templates, find every rule violation, return human-readable
    list of 'file:line:rule: snippet' strings."""
    out: list[str] = []
    files = _all_template_files()
    for fpath in files:
        try:
            text = fpath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for desc, regex, glob_pat, allowed in RULES:
            if not _glob_match(fpath, glob_pat):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not re.search(regex, line):
                    continue
                # escape hatch
                if any(a in line for a in allowed):
                    continue
                # Strip whitespace for the snippet
                snippet = line.strip()[:100]
                rel = fpath.relative_to(TEMPLATES_DIR)
                out.append(f"{rel}:{lineno}: {desc}\n    {snippet}")
    return out


def test_terminology_consistency_no_violations() -> None:
    """No template may contain any of the loan-word patterns from the
    glossary. This locks the SASKIA-301..308 program against regression.

    If you're adding a new column/label and need to use one of these
    terms, fix the GLOSSARY (the wrong answer is to weaken this test).
    Use Spanish per `app/docs/glossary.md`.
    """
    violations = _scan_violations()
    if violations:
        msg = (
            f"\n{len(violations)} terminology violations found in templates.\n"
            "Use Spanish terms from app/docs/glossary.md.\n"
            "If a pattern is legitimate, add an allowed_substring entry "
            "in this test with justification.\n\n" + "\n".join(violations)
        )
        pytest.fail(msg)


def test_glossary_doc_exists() -> None:
    """Glossary doc must be present and well-formed."""
    p = Path(__file__).resolve().parents[1] / "app" / "docs" / "glossary.md"
    assert p.exists(), f"Glossary doc missing: {p}"
    text = p.read_text(encoding="utf-8")
    # Required sections (cheap schema check)
    for needle in (
        "# Sazón — Terminology Glossary",
        "## Canonical terms",
        "## Currency rules",
        "## Date rules",
        "## Register rules",
    ):
        assert needle in text, f"glossary.md missing required section: {needle!r}"


def test_copy_vos_doc_still_exists() -> None:
    """Companion string-level copy bank must not be deleted."""
    p = Path(__file__).resolve().parents[1] / "app" / "docs" / "copy-vos.md"
    assert p.exists(), f"copy-vos.md missing: {p}"


def test_dashboard_titles_use_spanish_labels() -> None:
    """Dashboard widget titles — from the SASKIA-307 sweep — must remain
    in Spanish (not English loans). Locks the canonical Spanish labels."""
    expected_substrings = [
        # KPI card labels on inicio.html (each passed as label="...")
        'label="Ventas de hoy"',
        'label="Ventas"',
        'label="Margen estimado"',
        # Section headers
        "Ranking de productos",
        "Avisos",
    ]
    candidates = list(TEMPLATES_DIR.rglob("inicio.html")) + list(
        TEMPLATES_DIR.rglob("dashboard*.html")
    )
    if not candidates:
        pytest.skip("no inicio/dashboard template found")
    text = "\n".join(p.read_text(encoding="utf-8") for p in candidates)
    missing = [s for s in expected_substrings if s not in text]
    assert not missing, f"Missing Spanish dashboard titles: {missing}"
