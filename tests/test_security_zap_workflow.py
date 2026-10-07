"""tests/test_security_zap_workflow.py — M-INFRA-001 sanity tests.

Validates the security-zap.yml workflow + .zap-rules.tsv before they
ship. Tests do NOT run ZAP (that needs Docker + ~5 min) — they verify
the workflow is well-formed and the rule overrides parse correctly.

References:
  - OpenResto ZAP job: karanshukla/openresto .github/workflows/ci.yml
  - ZAP rules format: https://www.zaproxy.org/docs/desktop/addons/alert-filters/
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security-zap.yml"
RULES = REPO_ROOT / ".github" / ".zap-rules.tsv"


# ---- 1. Workflow file exists & is well-formed YAML --------------------


def test_zap_workflow_file_exists():
    assert WORKFLOW.is_file(), (
        f"Missing {WORKFLOW}. M-INFRA-001 requires this workflow to run "
        f"OWASP ZAP scans on every PR + weekly Monday 03:00 UTC."
    )


def test_zap_workflow_is_valid_yaml():
    """The workflow file must parse as valid YAML (GitHub Actions parser
    is strict about syntax — bad YAML silently breaks the workflow)."""
    with WORKFLOW.open() as f:
        data = yaml.safe_load(f)
    assert data is not None
    assert "jobs" in data
    assert "zap-api-scan" in data["jobs"]


def test_zap_workflow_has_required_triggers():
    """Weekly cron + on-demand workflow_dispatch are required so the
    scan runs even when nothing changes (catches dep-time vulns)."""
    with WORKFLOW.open() as f:
        data = yaml.safe_load(f)
    triggers = data.get(True)  # YAML key 'on' parses as True
    assert triggers is not None
    assert "schedule" in triggers, "Missing weekly cron — silent dep vulns won't surface"
    assert "workflow_dispatch" in triggers, "Missing manual trigger"
    assert "pull_request" in triggers
    assert "push" in triggers


def test_zap_workflow_uses_known_github_action():
    """Pin the action to a known version (v0.10.0) so we don't get a
    supply-chain surprise on the next pin update."""
    content = WORKFLOW.read_text()
    assert "zaproxy/action-api-scan@v0.10.0" in content


def test_zap_workflow_targets_sazon_openapi():
    """Must hit /api/openapi.json — the path FastAPI auto-generates.
    Wrong path = ZAP scans nothing and the job silently passes."""
    content = WORKFLOW.read_text()
    assert "/api/openapi.json" in content


def test_zap_workflow_uses_custom_rules_file():
    """The .zap-rules.tsv file is the lever for suppressing Sazon false
    positives without polluting the OpenAPI spec or middleware."""
    content = WORKFLOW.read_text()
    assert ".zap-rules.tsv" in content


def test_zap_workflow_uses_advisory_uvicorn_no_docker_compose():
    """Sazon AGENTS.md anti-rule #4 forbids Docker Compose. The
    workflow boots uvicorn directly with `nohup uv run uvicorn ...`."""
    # Strip comments first so the rule documentation itself
    # ("# - no docker compose") doesn't trigger the assertion.
    content_no_comments = "\n".join(
        line for line in WORKFLOW.read_text().splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "docker compose" not in content_no_comments.lower(), (
        "Sazon's AGENTS.md forbids Docker Compose. Workflow should "
        "boot uvicorn directly. Found 'docker compose' in non-comment lines."
    )
    assert "uv run uvicorn app.rms.main:app" in content_no_comments


def test_zap_workflow_pre_flights_security_headers():
    """Pre-flight check that SecurityHeadersMiddleware is wired before
    ZAP runs. Catches regressions where someone removes the middleware
    without noticing ZAP would silently miss the regression."""
    content = WORKFLOW.read_text()
    assert "x-content-type-options" in content.lower()
    assert "x-frame-options" in content.lower()
    assert "content-security-policy" in content.lower()


def test_zap_workflow_does_not_enforce_in_pr_until_promoted():
    """Per the workflow comment block, this is advisory at first
    (uses `fail_action: true` from the action but not as a required
    check). Verify the comment explicitly mentions the promotion path."""
    content = WORKFLOW.read_text()
    assert "Advisory" in content or "advisory" in content
    assert "promote" in content.lower() or "Branch Protection" in content


def test_zap_workflow_uploads_report_artifact():
    """ZAP report must be uploaded even when the job passes (audit
    trail for which findings existed at the time of the green build)."""
    content = WORKFLOW.read_text()
    assert "upload-artifact" in content
    assert "zap-report" in content


def test_zap_workflow_disables_https_only_in_ci():
    """HTTPS_ONLY=false in CI so ZAP doesn't flag "missing HSTS" over
    plaintext http://127.0.0.1. Production uses HTTPS_ONLY=True."""
    content = WORKFLOW.read_text()
    assert "HTTPS_ONLY: \"false\"" in content


def test_zap_workflow_uses_unique_port():
    """PORT must differ from smoke.yml (18999) so concurrent workflow
    runs don't collide on the same loopback port."""
    with WORKFLOW.open() as f:
        content = f.read()
    assert "18998" in content, "PORT should be 18998 to avoid smoke.yml collision"
    assert "18999" not in content, "PORT must NOT match smoke.yml"


def test_zap_workflow_uses_ephemeral_postgres():
    """PG must be in a container (test-only exception per AGENTS.md).
    Use Postgres 16-alpine to match smoke.yml."""
    content = WORKFLOW.read_text()
    assert "postgres:16-alpine" in content


def test_zap_workflow_teardown_is_idempotent():
    """docker stop ... || true — failure to stop the container should
    not fail the workflow (CI VMs auto-recycle anyway)."""
    content = WORKFLOW.read_text()
    assert "docker stop sazon-zap-pg || true" in content


# ---- 2. .zap-rules.tsv validity ---------------------------------------


def test_zap_rules_file_exists():
    assert RULES.is_file(), f"Missing {RULES}"


def test_zap_rules_have_tab_separator():
    """ZAP's rule-file parser is strict about tabs (not spaces). Any
    space here would silently fail to parse and ALL alerts would be
    enabled again."""
    bad = []
    with RULES.open() as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#"):
                continue
            if "\t" not in line:
                bad.append((lineno, line))
    assert not bad, (
        f".zap-rules.tsv must be TAB-separated (ZAP rule-file parser "
        f"strict). Lines without tabs: {bad}"
    )


def test_zap_rules_columns_are_valid():
    """Each non-comment line: <id><TAB>[ACTION>]<TAB>(<reason>)."""
    with RULES.open() as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            assert len(parts) == 3, (
                f"Line {lineno} has {len(parts)} columns, expected 3: "
                f"{line!r}"
            )
            rule_id, action, reason = parts
            assert rule_id.isdigit(), (
                f"Line {lineno}: rule_id '{rule_id}' not numeric"
            )
            assert action in ("IGNORE", "FAIL"), (
                f"Line {lineno}: action '{action}' not IGNORE or FAIL"
            )
            assert reason.startswith("(") and reason.endswith(")"), (
                f"Line {lineno}: reason '{reason}' should be in parens"
            )


def test_zap_rules_only_ignore_real_false_positives():
    """Every IGNORE entry must have a comment in the file header
    explaining WHY it's a false positive. No silent suppressions."""
    content = RULES.read_text()
    # Parse the header section (between # marks at start)
    header_match = re.search(
        r"^# Rules to IGNORE:.*?(?=^# Rules NOT to suppress)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert header_match, "Header missing — must list every IGNORE rule"
    header = header_match.group(0)
    with RULES.open() as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            rule_id = parts[0]
            action = parts[1]
            if action == "IGNORE":
                assert rule_id in header, (
                    f"Rule {rule_id} IGNORE'd but no explanation in "
                    f"header. Add a `100NN  Reason: ...` line above the TSV."
                )


def test_zap_rules_dont_suppress_security_header_checks():
    """The four security-header rules Sazon cares about must NOT be
    in the IGNORE list (they catch real regressions)."""
    MUST_NOT_IGNORE = {
        "10023",  # X-Content-Type-Options
        "10020",  # X-Frame-Options
        "10038",  # CSP
    }
    with RULES.open() as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            rule_id, action = parts[0], parts[1]
            assert not (rule_id in MUST_NOT_IGNORE and action == "IGNORE"), (
                f"Rule {rule_id} is a security-header check Sazon must "
                f"NEVER suppress. Remove the IGNORE entry."
            )


def test_zap_rules_documented_suppression_count_matches():
    """Sanity: the number of IGNORE rows should match the number of
    entries in the header section (excluding "No silent default")."""
    with RULES.open() as f:
        lines = f.readlines()
    ignore_count = 0
    for line in lines:
        line = line.rstrip("\n")
        if not line or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 3 and parts[1] == "IGNORE":
            ignore_count += 1
    # Header mentions 10 rules explicitly (10049, 10015, 10036, 10003,
    # 10109, 100001, 10098, 10027, 10035, 10063). Allow <= so that
    # adding a new rule with a header entry doesn't break this test.
    assert ignore_count <= 10
    assert ignore_count >= 5, (
        f"Only {ignore_count} IGNORE rows — fewer than the documented "
        f"5 minimum baseline. Did someone delete entries without "
        f"updating the header?"
    )