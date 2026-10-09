---
name: Epic / story template
about: Track a multi-PR initiative (audit log, Fase 2 migration, etc.)
title: "[EPIC] "
labels: ["epic"]
assignees: []
---

## Goal

One-paragraph statement of the outcome we want.

## Stories

A bullet list of stories, each independently shippable as a PR. Per the
2026-09-04 critical-path plan, each story should be 2-8 hours of work.

- [ ] **Story 1** — `<short name>` (XXh, owner?)
  - Acceptance: ...
- [ ] **Story 2** — `<short name>` (XXh, owner?)
  - Acceptance: ...

## Dependencies

What must land first? (Link to epics / stories.)

## Out of scope

What we're explicitly NOT doing in this epic.

## Definition of done

- [ ] All stories merged to main
- [ ] CI green at all points
- [ ] CHANGELOG.md `[Unreleased]` updated to a release tag
- [ ] Tests at or above 80% coverage
- [ ] `docs/wishlist/` entries that spawned this epic are moved to `triaged/` with a link
