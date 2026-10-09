# app/_archive — legacy code archive

This directory holds source files that were removed from the active
codebase during cleanup passes. Files here are **NOT imported** by
anything in `app/` or `tests/`. They're preserved in case a future
feature needs to resurrect one (e.g., a follow-up to a Phase-2B redo).

To find what's been archived and why:
- `git log --follow app/_archive/<date>/<file>` shows the commit that
  moved it and the rationale.
- `docs/backlog/<date>-p44-legacy-cleanup.md` has the full audit.

If you need to restore a file: `git mv` it back to its original
location, update imports, and add a test.

Do NOT import from `app/_archive/` in new code — these files are
frozen at their last-known-good state and will not receive fixes.
