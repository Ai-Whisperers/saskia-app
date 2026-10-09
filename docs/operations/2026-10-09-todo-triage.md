# TODO Triage (PR 6 of the docs-quality plan)

**Date:** 2026-10-09
**Scope:** Resolves the 235-marker TODO noise from the docs-quality audit
(`docs/operations/2026-10-09-docs-quality-audit.md` PR 6).

## TL;DR

A `grep TODO` repo-wide finds 253 matches, but **only 2 are actionable
code comments**. The rest are false positives in three classes:
Spanish prose ("todo de un proveedor"), audit/test references to closed
TODOs, and sprint tables in archived plans. PR 6 ships:

1. A code-comment-only scanner (`scripts/check_active_todos.py`) that
   returns the real 2.
2. This triage doc.
3. Two GitHub issues (SASKIA-2xx) — one per real TODO — so each has a
   ticket = an actionable home.

## Triage policy (post-PR-6)

When a future PR adds a new `# TODO:` comment, the scanner will show
`N+1` results. The expected workflow is:

1. If the TODO is **immediate work** (a known next step), file a
   `SASKIA-NNN` ticket inline in the same PR and link it from the
   comment (`# TODO(SASKIA-NNN): ...`).
2. If the TODO is **deferred** (a real "we'll get to this later"),
   either:
   - Move it to a planning doc (`docs/plans/2026-10-01-phase14-todo-inventory.md`),
     referencing the code location, OR
   - Resolve it now if the work is small.
3. If the TODO is **obsolete** (the work was done elsewhere or the
   context is gone), delete it.

The scanner is run by `make todos` (Makefile target in this PR). It is
**not** a CI gate — the real count is too small and too judgement-heavy
to be a binary check.

## The 2 real code TODOs

### TODO-1: `app/rms/models/channels.py:79`

```
# Legacy constants for backward compatibility (deprecated)
# TODO: Remove these once all code is updated to use Channel enum
ALLOWED_CHANNELS = Channel.allowed_values()
CHANNELS_DISPLAY = Channel.display_order()
CHANNEL_DEFAULT = Channel.default()
```

**Context:** Migration from ad-hoc string constants to a `Channel` enum.
The four legacy constants above (and their imports across the app)
exist for back-compat while a search/replace refactor is in progress.

**Resolution path:** Grep for `from app.rms.models.channels import
ALLOWED_CHANNELS, CHANNELS_DISPLAY, CHANNEL_DEFAULT` and replace each
usage with the enum method. Estimate: 1-2h for a careful refactor +
tests. SASKIA-2xx issue filed.

### TODO-2: `tests/test_dashboard_kpis_end_to_to_end.py:115`

```python
# KNOWN BUG: this endpoint raises ValueError("Unknown period: custom")
# when called without start/end. Currently returns 500.
# This test documents the behavior; should be fixed to fall back to "today".
r = client.get("/?period=custom")
# Acceptable: 200/303/422/500
# TODO: Fix _period_window to fall back to "today" when period="custom" but no dates.
```

**Context:** Dashboard period selector with `?period=custom` but no
date params raises 500 instead of falling back to "today". Test
documents the buggy behavior rather than enforcing the fix.

**Resolution path:** Update `_period_window()` to treat missing
`start`/`end` with `period=custom` as "today" (or 422 if the UX
wants the user to be explicit). Add a regression test asserting 200.
Estimate: 30 min. SASKIA-2xx issue filed.

## The 251 false positives, by class

### Spanish prose (62 matches)

`todo` lowercase is Spanish for "all" / "everything". Examples:

- `docs/user-guide/17-lista-compras.md:49` — "si comprás TODO de un proveedor"
- Many similar uses in user-guide prose.

The scanner excludes these by requiring uppercase `TODO` and matching
only comment-style lines (`#`, `//`, `<!-- -->`).

### Audit / test references to closed TODOs (29 matches)

Phase-14 tests reference closed TODOs by line number:

- `tests/test_riesgos_new_route.py:3` — `Closes Phase-14 TODO #nav:11`
- `tests/test_clientes_nuevo_route.py:3` — `Closes Phase-14 TODO #nav:217`

These are historical "this test closes a previously-noted gap"
references; not actual pending work. Don't grep-resolve them.

### Sprint status tables in archived plans (24 matches)

`docs/archive/2026-09/COMPLETE_PLAN.md` has rows like:

```
| Sprint 7 (production blockers) | ~4h | ~10 | 🔴 TODO |
```

The 🔴 emoji + `TODO` indicates "not done" status. Since the file is
archived (and superseded by the IDEATION_PLAN), these are frozen
historical state, not current work.

### Audit docs quoting other projects (138 matches)

`docs/analysis/2026-10-08/all_competitors_deep_audit_20261008.md` has
a `TODO Subscriptions` column and 100+ other references to other
products' TODO lists. These are research notes, not our work.

## How to run

```bash
# Show the current real TODO inventory
./scripts/check_active_todos.py

# Just stats
./scripts/check_active_todos.py --stats

# JSON for tooling
./scripts/check_active_todos.py --json

# Via Make
make todos
```

## Future maintenance

If the scanner reports `N+1` after a PR, the PR author should either
file a ticket and add the `SASKIA-NNN` reference to the comment, or
delete the TODO as part of the same PR. No "I'll do it later" allowed
without a ticket.
