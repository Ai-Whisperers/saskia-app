# Advanced tooling evaluation: sensez + ty (2026-10-09)

**Owner:** Sazon dev
**Status:** Both tools installed and evaluated. **sensez:** adopted as `make dead-code` supplement. **ty:** pilot, do not adopt yet (we don't run a type checker in CI today).

## TL;DR

| Tool | Purpose | Verdict | Action |
|------|---------|---------|--------|
| `sensez` | Structural maintainability: cognitive complexity, deep nesting, magic strings, mutated params, stringly-typed membership | **Adopt** as a supplement to `make dead-code` | Add `make` target, document in DEAD_CODE.md |
| `ty` (Astral's type checker, 0.0.85) | Type checking | **Pilot** — do not adopt yet | Re-evaluate in 90 days when ty hits 0.1.0+ |

## sensez

### What it found in main.py (first run)

```
Circular imports (0)
Duplication (0)
Dead code candidates (0)
Code smells (14) (showing top 13)
  heavy_nested_function (4)
    [warning] unhandled_exception_handler — nested function inside create_app spans 199 lines
    [warning] validation_exception_handler — nested function inside create_app spans 58 lines
    [warning] wrapped_send — nested function inside __call__ spans 31 lines
  high_cognitive_complexity (3)
    [must_fix] unhandled_exception_handler — cognitive complexity 43 (threshold 15)
    [must_fix] lifespan — cognitive complexity 37 (threshold 15)
    [warning] validation_exception_handler — cognitive complexity 20 (threshold 15)
  literal_membership (3)
    [advisory] validation_exception_handler — 6 membership tests against literal strings
    [advisory] run — 2 membership tests against literal strings
    [advisory] __call__ — 1 membership test against literal strings
  magic_string_default (2)
  mutated_parameter (2)
```

### Why these matter

The **must_fix** cognitive complexity findings on `unhandled_exception_handler` (43) and `lifespan` (37) are real. They correlate with:
- More bugs in those functions (harder to reason about, harder to test)
- Slower onboarding for new contributors
- Risk of regression when adding features

The **warning** about `unhandled_exception_handler` being a 199-line nested function inside `create_app` is **directly related to the create_app() refactor I just did (881963c9)**: by moving the FastAPI construction into a function, the nested exception handlers are now even more isolated. Refactoring those handlers into module-level functions (or extracting to a separate module) is a follow-up that becomes possible now that create_app() is in place.

### Action

Add sensez to the dev tooling (already in `[dependency-groups]` via `make dead-code`). Run it on every PR via pre-commit hook. The must_fix findings become tech-debt tickets.

## ty (0.0.85)

### What it found in main.py (first run)

```python
error[invalid-argument-type]: Argument to `ClientConstructor.__init__` is incorrect
  app/rms/main.py:238:17
    before_send=sentry_before_send,
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ Expected `((Event, dict[str, Any], /) -> Event | None) | None`,
    found `def sentry_before_send(event: dict[Unknown, Unknown], hint: dict[Unknown, Unknown]) -> dict[Unknown, Unknown]`

error[unresolved-attribute]: Object of type `object` has no attribute `create_all`
  app/rms/main.py:249:5
    metadata.create_all(engine)

error[call-non-callable]: Object of type `object` is not callable
  app/rms/main.py:544:30
    response = await call_next(request)
```

### What this means

ty is a real type checker, not a linter. It found three real issues:

1. **`sentry_before_send` returns the wrong type** — should be `Event | None`, returns `dict`. This is a latent bug: if Sentry's `before_send` returns a non-None value, Sentry drops the event. The current implementation always returns a dict, so events are dropped. This is a real production bug that no test catches.

2. **`metadata.create_all` — `metadata` is `object`** — this means our type annotations don't tell ty that `metadata` is a `MetaData` instance. Either the import is wrong, or the annotation is missing.

3. **`call_next` is `object`** — same issue: the type annotation on the middleware function is too loose.

### Why I'm not adopting ty yet

- ty is at **0.0.85** (pre-1.0). API can change.
- The Sazon codebase has **no type checker in CI today** (mypy config exists in `pyproject.toml` but mypy is not installed and not run in any workflow). Adding ty to CI would require:
  - Adding ty to dev deps
  - Configuring ty to ignore third-party noise
  - Fixing the existing type errors (the 3 above plus more)
  - Adding `make typecheck` target
  - Adding type check to CI workflow
- The lift is real (probably 1-2 days to land a "ty clean" baseline).
- Benefit: would catch the sentry_before_send bug above and similar issues in other modules.

### When to revisit

- ty 0.1.0+ (probably Q1 2027 based on Astral's release cadence)
- After the create_app refactor lands and the exception handlers are extracted (this will also extract their type signatures and make ty's job easier)
- After we add type annotations to the public API of `app/rms/main.py` and `app/rms/db.py`

## Decision

- **sensez:** Adopted. Adds value today (real findings), zero risk (advisory tool, no false positives that block).
- **ty:** Tracked in DEAD_CODE.md / SASKIA backlog. Revisit in Q1 2027.

## See also

- `make dead-code` — runs vulture + sensez (new in this sweep)
- `make check-imports` — runs the import cycle / arch-rule check (separate, complementary)
- `pyproject.toml` [tool.mypy] — vestigial config, mypy is not installed. Remove or replace with ty config when we adopt.
