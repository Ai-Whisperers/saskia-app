# Pull Request

<!--
  s4-tooling PR template (2026-10-12).
  Use this for any PR that touches app/, scripts/, tests/, or .github/.
  Lightweight: keep it short. CI gates the rest.
-->

## Summary

<!-- One paragraph: what this PR does and why. -->

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Refactor (no functional change)
- [ ] Tooling / CI / docs only
- [ ] Breaking change (fix or feature that would cause existing functionality to change)

## Closes gap:

<!--
  Per AGENTS.md rule 35 + the 2026-10-12 level-up campaign decision.
  Link the audit / ledger / plan entry that surfaced this gap.
  Format: docs/operations/<date>-<lane>-<scope>.md §<section>
  or: INBOX/s5-org/from-<lane>.md item <#>
  If there's no audit — say so and explain why this PR exists.
-->

Closes gap:

## Measured delta:

<!--
  Per campaign decision 2026-10-12: every PR records its measured impact.
  Pick the ones that apply.
  - LOC: N added / M removed
  - Coverage: before X% / after Y% (NEVER raise the gate per rule 12)
  - Cyclomatic complexity: <function> from CC=N to CC=M
  - Test count: N new tests, M modified
  - Workflow runtime: <workflow> from Nmin to Mmin
  - Dead code removed: <file> via vulture
  - CVE count: N vulns found / M resolved
  - Other:
-->

| Metric | Before | After |
|--------|--------|-------|
|        |        |       |

## Checklist

- [ ] I updated root `CHANGELOG.md` (rule 35 — required when touching `app/`, `scripts/`, `tests/`, or `.github/`)
- [ ] I did NOT raise `--cov-fail-under` above 35% measured reality (rule 12)
- [ ] I did NOT introduce any `*_legacy.py` / `*_v2.py` / `*_original.py` file (rule 38)
- [ ] I ran `make lint` locally — passes
- [ ] I ran `make test-fast` locally — passes (or explained why it can't)
- [ ] If I touched `pyproject.toml [tool.ruff]`, I coordinated with s4-tooling lane
- [ ] If I touched `pyproject.toml [tool.pytest]`, I coordinated with s1-tests lane
- [ ] If I touched any `app/**` file, I coordinated with s3-complexity lane (ruff must stay clean)
- [ ] If I added a new test file, I coordinated with s1-tests lane for pattern conformance

## Notes for reviewer

<!-- Anything the reviewer should know: known limitations, followups, blocked-by. -->