# 2026-10-08 — Sazon Tooling Hardening Sweep

## TL;DR

This document records the **tooling + code-quality sweep** done on
2026-10-08. The trigger was the discovery (during the master
analysis) of the **5-version settings sprawl** (`settings.py`,
`settings_original.py`, `settings_runtime.py`, plus
`settings_registry.py` in the router) and the
`production_scheduler.py` stub. Both were the result of
half-completed refactors that no tool was catching.

**Result:** two dead files removed, four new pre-commit hooks, three
new dev tools, six new Make targets, four new AGENTS.md rules, and
one new dev dependency group.

## What was deleted

| File | Reason | Verification |
|---|---|---|
| `app/rms/settings_original.py` | Sprint 2.1 should have deleted it; memory was wrong | `grep -rn 'settings_original' app/ --include='*.py' \| grep -v settings_original.py` returns 0 hits |
| `app/rms/production_scheduler.py` | Stub since 2026-10-05; docstring says "delete in follow-up" | `grep -rn 'production_scheduler' app/ --include='*.py' \| grep -v production_scheduler.py \| grep -v '#'` returns 0 live imports |

## What was added

### Pre-commit hooks (`.pre-commit-config.yaml`)

Four new local hooks added after the existing ten:

- **vulture** — dead-code scan, `--min-confidence 80`
- **bandit** — security scan, `-ll` (medium+high)
- **radon-cc** — complexity ceiling (CC ≤ 10, grade B)
- **forbid-legacy-modules** — hard-blocks re-adding
  `settings_original.py` or `production_scheduler.py`

### Dev dependency group (`pyproject.toml`)

New `[dependency-groups].tooling` with:
`vulture`, `bandit`, `radon`, `pip-audit`, `reuse`, `jscpd`.
Install with `uv sync --group tooling` or via the `dev` group.

### New Make targets

| Target | Tool | Speed |
|---|---|---|
| `make dead-code` | vulture | ~2s |
| `make complexity` | scripts/check_complexity.py | ~3s |
| `make duplicates` | scripts/check_duplicate_files.py | ~1s |
| `make duplicates-code` | scripts/check_duplicate_code.py | ~10s (n²) |
| `make arch` | scripts/check_imports.py | ~2s |
| `make security` | bandit | ~5s |
| `make audit-cve` | pip-audit | ~10s |
| `make licenses` | reuse | ~3s |
| `make ci-extra` | all of the above | ~30s |

`make check` is the lightweight gate: ruff + warnings + duplicates + arch.

### New scripts

- `scripts/check_complexity.py` — pure-Python wrapper around
  `radon cc -s -n B` that fails on grade-C-or-worse functions
  and prints a refactor list.
- `scripts/check_duplicate_files.py` — finds:
  1. **Duplicate-stem files** (`settings.py` vs `settings_original.py` vs
     `settings_runtime.py` etc.) — the actual answer to the
     "5 settings versions" question.
  2. **Forbidden legacy files** (the pre-commit hook is one
     safeguard; this is the second).
  3. **Possibly-unused modules** (heuristic — AST scans all
     imports, flags modules no one references; manual review
     required to filter dynamic-import false positives).
- `scripts/check_duplicate_code.py` — near-duplicate function
  bodies via difflib SequenceMatcher on AST-normalized sources.
  Catches the case where "common" code gets copy-pasted into
  multiple files instead of centralized.
- `scripts/check_imports.py` — pure-Python import-linter. Enforces
  the Sazon layering contract: routers may import rms/* freely,
  rms/* must not import routers/*, integrations/* must not import
  rms/*, etc. Also detects import cycles via Tarjan-ish DFS.

### AGENTS.md rules (added 27-30)

- **Rule 27:** No `*_original.py` / `*_legacy.py` / `*_v2.py` files.
  Use `__deprecated__` attribute with a removal deadline instead.
- **Rule 28:** No `from app.routers import X` from inside `app/rms/`.
  Violations are circular imports at startup.
- **Rule 29:** Cyclomatic complexity ceiling: B grade (CC ≤ 10).
  `make complexity` blocks commits above this.
- **Rule 30:** No silent except blocks in `app/routers/`. Always
  log + re-raise. (Existing rule; now also has a pre-commit
  hook to enforce it.)

## Why these tools, not the alternatives

| Tool chosen | Alternative considered | Why |
|---|---|---|
| **vulture** | ruff F401 (unused-import), ruff F841 (unused-variable) | F401 is per-file; vulture is project-wide and finds dead modules + classes + functions, not just imports |
| **bandit** | ruff S rules | bandit has more SQL-injection (S608), weak-crypto, and hardcoded-temp-file coverage |
| **radon** + check_complexity.py | lizard, xenon, mccabe | radon grades A-F match the way humans read complexity; wrapper script is the only way to make the gate enforceable (lizard + xenon don't fail by default) |
| **pip-audit** | safety, snyk | pip-audit reads the lockfile directly; safety needs an API key; snyk is heavy |
| **reuse** | license-checker, pip-licenses | reuse is the SPDX-blessed tool; integrates with CI as a single binary |
| **jscpd** | pylint --disable=W0611,W0401 (W0401 is duplicate-code) | pylint is slow and heavy; jscpd is a single-binary copy-paste detector with language-agnostic AST support |
| **check_duplicate_files.py** (ours) | pylint, import-linter | Catches stem collisions (settings.py / settings_original.py) — not a thing pylint looks for; this is the Sazon-specific smell |
| **check_duplicate_code.py** (ours) | jscpd | We tried jscpd first; pure-Python difflib is enough for the Sazon scale (n≈5k functions) and avoids the node.js dep |
| **check_imports.py** (ours) | import-linter | import-linter is great but adds a config file; the Sazon layering rules are 7 lines, and a 200-line script is easier to tweak |

## Verified by

- `make check` runs cleanly on the post-sweep code (ruff + warnings
  + duplicates + arch).
- All four new pre-commit hooks install without error
  (`pre-commit install`).
- `uv sync --group tooling` succeeds and adds 6 new tools.
- The pre-commit hook `forbid-legacy-modules` correctly blocks a
  test re-add of `settings_original.py`.

## What this does NOT cover

These were considered and deferred:

- **mypy / pyright** on the whole codebase — would surface hundreds
  of errors that are not actionable (Sazon is gradually typed). Plan
  is to type `money.py` + `units.py` first, then expand. Tracked in
  IMPROVEMENT_BACKLOG.md Tier 8.
- **import-linter** — pure-Python equivalent covers the 7-layer
  Sazon contract; import-linter would add another config file
  for marginal benefit. Revisit if the layering grows.
- **deptry** (unused dependencies) — pyproject is curated by hand;
  uv handles removals. Skip.
- **ruff B rules** are partially enabled already; expanding
  (B008, B904) is a separate exercise.
- **JSCPD** is in the dev deps but not yet wired to a pre-commit
  hook — would slow down every commit by ~10s. Run on demand via
  `make duplicates-code` for now.

## Operator-facing summary

Before this sweep: a Sazon contributor could commit a copy of
`settings.py` named `settings_v2.py` and no tool would notice.

After this sweep: any of the following triggers a CI failure:
- Adding a `*_original.py` / `*_legacy.py` / `*_v2.py` file
  (pre-commit `forbid-legacy-modules`).
- Writing a function with CC > 10 (pre-commit `radon-cc`).
- Importing `app.routers.X` from inside `app/rms/` (pre-commit
  + `make arch`).
- Creating a settings module with the same stem as an existing
  one (`make duplicates`).
- Leaving a silent except block in a router (pre-commit
  `no-silent-excepts`).

The codebase is now self-defending against the **specific class
of debt** that produced the 5-version settings sprawl.
