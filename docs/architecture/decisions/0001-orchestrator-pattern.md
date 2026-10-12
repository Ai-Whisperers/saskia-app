# ADR-0001 — Orchestrator pattern for cyclomatic-complexity refactors

**Status**: Accepted (2026-10-12)

**Context**: AGENTS.md rule 40 enforces CC ≤ 10 per function (`make complexity` gate). The codebase had 209 functions over CC>10 (verified 2026-10-12 via `scripts/check_complexity.py` after its parser fix). Prior refactors (104 commits, e.g. `3957cc54 refactor(produccion): reduce produccion_prep complexity 26→2`) followed the orchestrator pattern: thin coordinator + single-purpose `_helpers`.

**Decision**: When refactoring any function over CC>10 in `app/`:

1. **Extract by concern**, not by line count. One helper per logical concern (e.g. one for "effective threshold", one for "fallback value", one for "label mapping"). Helpers stay small enough that each is grade A or B on its own.
2. **Helpers are private** (`_name`), live in the same file as the orchestrator, and are not exported via `__all__`. The orchestrator is the only public surface.
3. **Behavior is preserved character-for-character** — input/output shapes, sort keys, `'or X'` guards, `finally` restore blocks, rounding, all unchanged. The commit message records the specific preservations (which fields, which fallback, which threshold).
4. **Tests stay green BEFORE commit**. Run the function's existing dedicated tests; if none exist, add a smoke test covering the orchestrator's external contract. The orchestrator must not gain new public surface that bypasses the test suite.
5. **Session is passed explicitly** to extracted helpers when they touch the DB. Never via module-level globals, thread-locals, or FastAPI `Depends()` injection in a helper (helpers are pure functions, not route handlers).
6. **Imports stay function-local** in modules whose tests purge `sys.modules` between cases (re-import cost is low; state-import side-effects break tests).
7. **No `*_legacy.py` / `*_v2.py` files** (rule 38). Split a function, not a module. The pre-commit hook `forbid-legacy-modules` enforces `settings_original.py` + `production_scheduler.py`; same spirit applies to function refactors.

**Trade-offs accepted**:

- A function split into 5 helpers is harder to read top-to-bottom than a single 60-line function — but CC is the gate, and helpers are individually testable.
- Helpers are not reusable across modules unless we later want to. YAGNI: when reusability becomes a need, promote to a shared module then, not now.
- Some helpers duplicate logic across modules (e.g. `_target_max_qty` here vs `restock_forecast.py:208`). When 2+ modules share identical helpers, that becomes a "single-path" refactor on its own (separate ADR-0002 candidate).

**Anti-patterns explicitly rejected**:

- Splitting by line count (e.g. "lines 1-30 → helper_a, lines 31-60 → helper_b"). The split points are arbitrary; concerns get re-tangled.
- Creating a class to "share state" between helpers. They take explicit args; state is the caller's job.
- Using `match`/`switch` as a complexity trick. Each branch is still a branch; radon counts them.
- Hiding complexity behind `**kwargs` / `dict` config. CC measures call sites; this just moves the noise.

**Examples shipped**:

- `app/rms/reorder.py::compute_reorder_list` (CC 13 → 4) — split into `_effective_min`, `_target_max_qty`, `_urgency_ratio`, `_urgency_label`, `_build_reorder_item`. 43 tests pass.

**Future ADRs queued**:

- ADR-0002: Single-path refactor for the `effective_min * 2` / `display_stock / min_stock_qty` pattern that appears in `app/rms/reorder.py`, `app/rms/restock_forecast.py`, `app/rms/stock_status.py`, and several seed files.
- ADR-0003: Dead-code archival protocol for `app/_archive/<date>-<ticket>/` moves (verification: zero importers via grep AND zero recent activity via `git log --since='6 months ago'`).

**References**:

- AGENTS.md rule 36 (ADRs), rule 38 (no legacy shims), rule 40 (CC ≤ 10)
- `scripts/check_complexity.py` — gate (parser bug fixed 2026-10-12)
- `docs/operations/2026-10-08-tooling-hardening.md` — tooling rec that introduced the gate
- Prior campaigns: `3957cc54` (produccion), `b27d916c` (pedidos), `ae6b7282` (sales_intel)