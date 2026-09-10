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
