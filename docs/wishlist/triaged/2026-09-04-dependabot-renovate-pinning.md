# Dependabot / Renovate for runtime + dev deps

**Date:** 2026-09-04
**Author:** operator (Iván) — observed during pyproject.toml audit
**Cost guess:** S
**Phase guess:** 1.5
**Source:** `pyproject.toml` has 13 runtime + 5 dev deps, all `<`-pinned

## What

Enable Dependabot (or Renovate) on the repo. Weekly PR cadence. Group minor/patch updates; require human review for major version bumps.

## Why now

Repo is public. Zero automation means manual updates forever, and CVE patches lag by months.


## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `.github/dependabot.yml` (uv ecosystem, weekly schedule, groups runtime-patch + dev-patch; majors require human review). Verified by `tests/test_dev_tooling.test_dependabot_exists`. Commit 928f08d.
