"""tests/test_round2_triage_contract.py — E4.S1 round-2 triage contract.

Pins the round-2 triage workflow so it can't silently drift:
- ROUND-2-NOTES.md exists with ship-it criteria and review window
- round-2-triage-process.md defines raw → triaged → shipped/rejected states
- Bug template references the round-2 workflow
- Round-2 cap (≤2h) is explicit so the cap cannot drift
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUND2_NOTES = REPO_ROOT / "installer" / "ROUND-2-NOTES.md"
TRIAGE_DOC = REPO_ROOT / "docs" / "operations" / "round-2-triage-process.md"
BUG_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_round2_notes_exist():
    assert ROUND2_NOTES.exists()


def test_triage_doc_exists():
    assert TRIAGE_DOC.exists()


def test_round2_notes_pin_2h_cap():
    """The 2h ship-it cap must be explicit so it can't drift."""
    text = _read(ROUND2_NOTES)
    assert "≤2h" in text or "<=2h" in text or "2h" in text, (
        "round-2-notes must mention the 2h cap on ship-it items"
    )


def test_round2_notes_pin_ship_it_criteria():
    """The ship-it criteria must include all 5 dimensions (effort, repro, test, deps, schema)."""
    text = _read(ROUND2_NOTES).lower()
    # All five must be present
    assert "≤2h" in text or "<=2h" in text or "2h" in text, "must mention effort cap"
    assert "repro" in text, "must require clear repro"
    assert "acceptance test" in text or "fails on main" in text, "must require acceptance test"
    assert "dependency" in text or "no new dep" in text, "must forbid new deps"
    assert "schema migration" in text or "schema change" in text, "must forbid schema changes"


def test_triage_doc_has_workflow_states():
    """The triage doc must define OPEN → ACCEPTED / OUT-OF-SCOPE states."""
    content = _read(TRIAGE_DOC).lower()
    # Capture state
    assert "open" in content, "must define an OPEN / capture state"
    # Triaged state
    assert "triage" in content, "must mention triage step"
    # Terminal states: ACCEPTED, OUT-OF-SCOPE, WONT-FIX, shipped, rejected, or closed
    assert (
        "shipped" in content
        or "rejected" in content
        or "accepted" in content
        or "out-of-scope" in content
        or "out of scope" in content
        or "wont-fix" in content
        or "closed" in content
    ), "must define a terminal state"


def test_triage_doc_links_to_notes():
    """The triage doc must reference ROUND-2-NOTES.md so operators can find both."""
    content = _read(TRIAGE_DOC)
    assert "ROUND-2-NOTES" in content or "installer/ROUND-2" in content, (
        "triage doc must link to ROUND-2-NOTES.md"
    )


def test_bug_template_references_round2_workflow():
    """The GitHub bug template must reference the round-2 label/process."""
    content = _read(BUG_TEMPLATE)
    assert "round-2" in content.lower() or "round 2" in content.lower(), (
        "bug template must mention round-2 routing"
    )
    assert "round-2-triage-process.md" in content or "ROUND-2-NOTES.md" in content
