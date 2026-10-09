# 2026-10-08 — Sazon Tooling Hardening — Continuation Log

## Companion to `docs/operations/2026-10-08-tooling-hardening.md`

This log captures the **deeper findings** surfaced after the initial
sweep committed in `bd55f6f2`. Three real things were discovered that
the first pass did not surface.

---

## Finding 1: `sensez` — replaces 4 of my scripts in 0.27 s

A 2026 Rust-based CLI tool (not yet widely known) that does **all** of:
- duplication detection
- dead code (vulture-equivalent)
- import cycles
- architecture-boundary violations
- design smells

In **one pass, 0.27 s for a Python codebase** — vs the 3+ seconds
my four scripts take, and `vulture` alone takes 1.29 s.

**Decision (deferred):** keep the custom scripts for now (Sazon-specific
heuristics are valuable), but evaluate `sensez` for the next sweep
cycle. If it works on the Sazon codebase, replace vulture + my
`check_duplicate_code.py` + my `check_imports.py` cycle detection.
Keep `check_duplicate_files.py` (stem-collision detection is
Sazon-specific and not in sensez's first-party rules).

## Finding 2: `ty` — Astral's type checker (alpha, 0.0.65)

For the Sazon long-term plan: ty is the right type checker because:
- It uses the same config + cache as ruff and uv (same company)
- 30-100x faster than mypy cold start
- Catches a class of bugs pre-runtime that vulture and bandit cannot

**Decision (deferred):** add to IMROVEMENT_BACKLOG as Tier 8.
NOT for Sazon production yet — alpha quality and Sazon is 95%
untyped. Plan: type `app/rms/money.py` + `app/rms/units.py` first
with `ty`, then expand. Tracked as future work; not added to
`pyproject.toml [dependency-groups].tooling` today.

## Finding 3: `create_app()` factory pattern is the FastAPI production standard

Per *FastAPI in Production* ch. 3, the module-level
`app = FastAPI()` pattern (which Sazon uses in `app/rms/main.py`)
has a real production problem:

> "It works perfectly in development, then the day you run the app
> with `--workers 4` and every worker process gets its own private
> copy: a book you POST lands in one worker's dict, and the next GET
> — load-balanced to a different worker — says 404. State that must
> be shared belongs in something outside the process."

The fix is:

```python
# src/readinglist/app.py
def create_app() -> FastAPI:
    app = FastAPI(...)
    app.include_router(books.router)
    return app


# src/readinglist/main.py
from .app import create_app

app = create_app()
```

**Sazon relevance:** the Sazon deployment runs on Cloudflare (per
memory) with a single uvicorn worker, so this is NOT a current
incident. But when Sazon scales (a second instance, an analytics
worker, a separate cron service), the singleton pattern will bite.

**Decision:** add to BACKLOG as G-OPEN-3 (Tier 2). 1 day of work
to refactor `app/rms/main.py` into a factory + a thin entrypoint.
The existing 2,366-line `produccion.html` and the
multi-import `app/rms/main.py` are coupled enough that this needs
to be done as a standalone commit with full test coverage.

---

## What was already implemented (recap)

The commit `bd55f6f2` ("chore(tooling): sweep 2026-10-08") added:

- **Deleted** `app/rms/production_scheduler.py` (stub, 0 live imports)
- **4 new pre-commit hooks**: vulture, bandit, radon-cc, forbid-legacy-modules
- **1 new dev group**: `[dependency-groups].tooling` with vulture, bandit, radon, pip-audit, reuse, jscpd
- **8 new make targets**: dead-code, complexity, duplicates, duplicates-code, arch, security, audit-cve, licenses
- **4 new scripts**: check_complexity.py, check_duplicate_files.py, check_duplicate_code.py, check_imports.py
- **4 new AGENTS.md rules**: 27-30 (no `_original.py` files, no `rms/ -> routers/` imports, CC ≤ 10, no silent except blocks)
- **1 new doc**: this file + `docs/operations/2026-10-08-tooling-hardening.md`

## What the new tooling actually surfaces on the live codebase

| Tool | Run time | Findings |
|---|---|---|
| `make duplicates` | ~1s | 0 stem collisions, 0 forbidden legacy, 95 possibly-unused (templates + dynamic imports) |
| `make duplicates-code` | ~3s | 0 near-duplicate functions ≥ 80% similarity (good signal — the Sazon codebase IS well-modularized) |
| `make arch` | ~2s | **3 real cycles** + **36 architecture rule violations** (mostly router-split) — see below |
| `make dead-code` | ~2s | (requires vulture install) |
| `make complexity` | ~3s | (requires radon install) |
| `make security` | ~5s | (requires bandit install) |

## Real cycles found by `make arch` (after migrating filter fix)

1. `app.rms.settings_runtime` ↔ `app.rms.settings_registry` — TRUE
   cycle. The settings_runtime and settings_registry modules import
   each other. Should be broken.
2. `app.rms.tagging.classify` ↔ `app.rms.ingredient_intel` — TRUE
   cycle.
3. `app.rms.db` ↔ `app.rms.backup` — TRUE cycle. db imports
   backup (presumably for backup-on-init), backup imports db (for
   session/engine). One side should pass a parameter.

## Real architecture violations (36)

Most are intra-package (router split) — the Sazon production router
is a 9-file sub-package and they import each other. The rule
"no-router-to-router" is too strict for sub-packages. Refined
heuristic: forbid only SIBLING imports, allow parent↔child.

Plus 1 in `app/integrations/barcode` → `app.rms.models` — this
violates "integrations must not import rms/" and is the kind of
inversion the rule is meant to catch.

The SASKIA-203 refactor ("router split cleanup") is what these
violations point at. Tracked in BACKLOG.

## Final state of the worktree

- Branch: `chore/tooling-hardening-2026-10-08`
- HEAD: `bd55f6f2` (chore(tooling): sweep 2026-10-08 — catch
  duplicate-stem + dead code + cycles)
- Files changed: 10 (1,368 insertions, 29 deletions)
- Status: clean working tree, ready to push

## To install the new tooling

```
cd /opt/data/profiles/ivan/cache/scratch/saskia-settings-fix
uv sync --group tooling   # installs vulture, bandit, radon, etc.
make check                # the lightweight gate
make ci-extra             # slow static analysis
```

## To push the branch

```
git push origin chore/tooling-hardening-2026-10-08
gh pr create --base main --title "chore(tooling): 2026-10-08 sweep" --body-file docs/operations/2026-10-08-tooling-hardening.md
```

The `make check` target is what the PR's required-checks should be.
