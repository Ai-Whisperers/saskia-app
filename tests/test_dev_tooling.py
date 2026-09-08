"""tests/test_dev_tooling.py — sanity checks for E24 dev tooling.

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E24.

Covers:
- Makefile exists and contains all 13 documented targets
- CONTRIBUTING.md exists and references 'make' workflow
- docker-compose.dev.yml is valid YAML
- .github/CODEOWNERS has routing rules
- .github/dependabot.yml has uv ecosystem enabled
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_makefile_exists():
    assert (ROOT / "Makefile").exists()


def test_makefile_has_help_target():
    content = (ROOT / "Makefile").read_text()
    assert ".PHONY: help" in content
    assert "help:" in content


def test_makefile_has_all_targets():
    """The 13 expected targets must exist."""
    content = (ROOT / "Makefile").read_text()
    expected = [
        "install", "test", "test-verbose", "test-coverage",
        "lint", "lint-fix", "format", "check",
        "serve", "migrate", "seed", "seed-reset",
        "backup", "fixtures", "clean", "ci-smoke",
        "pre-commit", "stats",
    ]
    for t in expected:
        assert f"\n{t}:" in content or f"\n.PHONY: {t}" in content, f"Missing target: {t}"


def test_makefile_uses_uv():
    content = (ROOT / "Makefile").read_text()
    assert "uv run pytest" in content
    assert "uv run ruff" in content


def test_contributing_md_exists():
    p = ROOT / "CONTRIBUTING.md"
    assert p.exists()
    content = p.read_text()
    assert "make install" in content
    assert "make migrate" in content
    assert "make seed" in content
    assert "Saskia-eng-NNN" in content


def test_docker_compose_dev_yml_is_valid_yaml():
    p = ROOT / "docker-compose.dev.yml"
    assert p.exists()
    data = yaml.safe_load(p.read_text())
    assert "services" in data
    assert "postgres" in data["services"]
    assert data["services"]["postgres"]["image"] == "postgres:16-alpine"


def test_docker_compose_exposes_5432():
    p = ROOT / "docker-compose.dev.yml"
    data = yaml.safe_load(p.read_text())
    ports = data["services"]["postgres"]["ports"]
    assert "5432:5432" in ports


def test_dependabot_yml_is_valid_yaml():
    p = ROOT / ".github" / "dependabot.yml"
    assert p.exists()
    data = yaml.safe_load(p.read_text())
    updates = data["updates"]
    assert len(updates) >= 1
    assert updates[0]["package-ecosystem"] == "uv"


def test_codeowners_has_default_owner():
    p = ROOT / ".github" / "CODEOWNERS"
    assert p.exists()
    content = p.read_text()
    assert "@Ai-Whisperers" in content
    # Specific routes
    assert "audit.py" in content
    assert "security_headers.py" in content
    assert "rate_limit.py" in content
    assert "db.py" in content
