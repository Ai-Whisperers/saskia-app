# AGENTS.md analysis — does the current docs still make sense?

**Author:** Hermes (this session, `ivan/20261008_231844_c3f34c`)
**Date:** 2026-10-08 (last reviewed: pre-2026-10-07, pre-SASKIA-210, pre-sibling-side SASKIA-211/212/213/215)
**Sources of truth:** `AGENTS.md` (repo root), `app/rms/AGENTS.md`, live repo state
**Verdict:** the docs are **mostly accurate but fact-rotated in 11 specific places**, and they're missing **4 new rules** that emerged from Sprint 2.x work. Both are fixable in a single follow-up PR (SASKIA-211e). No write yet.

---

## 0. TL;DR

| File | Verdict | Action |
|---|---|---|
| `AGENTS.md` | 9 factually-stale claims, 3 missing rules, 1 stale file reference | SASKIA-211e — single PR with proposed edits |
| `app/rms/AGENTS.md` | 2 factually-stale claims (money rules), 1 missing abstraction registry reference, 1 wrong file path | same PR, smaller scope |

A single SASKIA-211e PR with proposed diffs is in §6 below. **Nothing is written yet** — this doc is a research artifact for the operator to read.

---

## 1. What "make sense" means here

For each hard rule in AGENTS.md I asked four questions:

1. **Does the rule still hold at the code level?** (i.e. is the codebase honoring it?)
2. **Is the rule still enforceable at the CI level?** (i.e. is `tests/test_*.py` actually catching violations?)
3. **Are the cited tests, files, and SHAs still accurate?**
4. **Is there a NEW rule that emerged since the doc was last touched that we should add?**

If any of 1-3 is "no" or 4 is "yes", the doc needs an update.

---

## 2. `AGENTS.md` (root) — line-by-line audit

### 2.1 Stale factual claims (need fixing)

| Line(s) | Claim | Actual state | Severity |
|---|---|---|---|
| L13 (`Personas`) | "AI agents (Kiki, this assistant, future agents) — read this to understand the build brief and hard rules" | Per L170 ("Build brief"), the "Kiki" engagement model is historical; current code is owned by Iván directly. The "Kiki" framing pre-dates this clarity. | low — historical tour |
| L18 (`Hard rules` count) | "117 migrations, no gaps" | **118 migrations** (`CURRENT_SCHEMA_VERSION = 118` per `app/rms/config.py:92`), range 1-118, **0 gaps** still. So the count is off by one; "no gaps" still true | medium — version drift |
| L46 (rule 8) | "delegates to `apply_sale()` in `app/rms/costing.py`" | **`apply_sale()` now lives in `app/rms/sales/lifecycle.py`**; `app/rms/costing.py` is a 1.3 KB deprecated shim (verified — file content). Per shim's docstring: "Sprint 2.3 of the 2026-10-02 backend overhaul" | medium — wrong file path |
| L53 (rule 12) | "No Alembic. Hand-rolled versioned migrations in `app/rms/db.py` (117 migrations, no gaps)" | same as L18 — 117→118 | medium |
| L109 (anti-rule #2) | "Sazon has 251 app/ python files, 45 tables, 117 migrations" | **290 app/ .py files** (verified), **89 model classes across legacy + new + domain packages** (not 45), **118 migrations** | medium — count drift on three numbers |
| L182 (Testing) | "Coverage gate: 80%" and "Current gate is 35%" | Verified `pyproject.toml:69` addopts `fail-under=35 -m 'not (browser or e2e or pg or manual)'`. So 35% is current; phase ramp is dormant | low — staleness on phase ramp claim |
| L184-185 (Testing) | "Property-based tests for money (`test_money.py`); unit tests for unit coercion (`test_units.py`)" | `tests/test_money.py` and `tests/test_units.py` exist and are 4.6 KB / 7.0 KB. Also: `app/rms/AGENTS.md` adds coverage gates 95% money / 90% costing that aren't cited in the root doc | low — root doc less strict than rms/AGENTS.md |
| L210 (CI) | "Anti-rule enforcement (13 of 20 anti-rules enforced via grep in CI; see `.github/workflows/ci.yml` and `tests/test_ci_anti_rules.py`)" | `test_ci_anti_rules.py` has **14 test methods** (was 13?). The "13 of 20" claim was accurate at one point; today's count is unclear without running the test | low — count may have grown to 14+ |
| L240-258 (Locked hotfixes) | 5 SHAs (f1af406, c093a75, 99b37c6, bb21eff, 501bcff) | **All 5 SHAs verified present** in git object DB. No drift | none — section is correct |
| L268 (Ticket convention) | "Sazon tickets use `SASKIA-NNN`" | Live branches: SASKIA-211b, 211-clean, 211-cocina-pages-audit, 212, 213, 215. All use the format. OK | none |

### 2.2 Stale references / dead links

| Reference | Issue | Fix |
|---|---|---|
| `render.yaml` (referenced as "historical only, do not deploy to Render") | **File does NOT exist** in repo root. Either removed in SASKIA-211 hardening or never existed. | Remove the reference |
| `state/test-coverage-2026-10-04.json` (Testing §) | Likely stale filename; coverage work has been merged into other artifacts | Verify path, update or remove |
| `IMPROVEMENT_BACKLOG.md`, `WHAT_NEXT.md` | Referenced twice; are they still authoritative? | Verify they exist & are current |

### 2.3 Missing rules the doc has not yet captured

The audit on 2026-10-07 and the abstraction-gate work this session surfaced rules that **should be in AGENTS.md but aren't**:

1. **"No direct `StockMovement(...)` outside `app/rms/stock_ledger.py`, `app/rms/sales/lifecycle.py`, `app/rms/costing.py`, and ORM models."** (per audit doc + this session's bypass probe showing 9 violations, of which 5 belong in lifecycle.py allow-list and 4 in routers/inventory.py are still true bypasses)

2. **"All money persistence goes through `app.rms.money.to_int_gs()` — no other integer-cast for money, ever."** This rule already lives in `app/rms/AGENTS.md` (rule #3) but should be promoted to root AGENTS.md since it affects `app/routers/*` files (not just `app/rms/*`). Currently 4 sites violated this rule (now fixed in this session's 211a).

3. **"Reuse abstractions over copy-pasting the audit row."** Pattern: when a router needs to bump stock + write a `StockMovement` row, it MUST call `apply_stock_delta()` (sale paths: `apply_sale()`). This is the audit's primary finding, and AGENTS.md doesn't have it.

4. **"Cross-session writes go to `.hermes/`. Don't coordinate in chat."** This is per `docs/operations/2026-10-04-sibling-session-coordination.md` (read this session). The root AGENTS.md L264-265 does mention sibling coordination but doesn't cite the protocol of "write plans to .hermes/plans/".

### 2.4 Things that should be REMOVED or DOWNPLAYED

- L11 ("AI agents (Kiki, this assistant, future agents)") — the doc's own L170 contradicts this; consolidating would be cleaner.
- L170-176 (Build brief — "Tasks 1-10 from `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`") — Phase 1 dev plan is done per the SASKIA-211/212/213 ship cadence. Demoting or removing the phase-1 tasks reference would be correct.

---

## 3. `app/rms/AGENTS.md` audit

### 3.1 Stale factual claims

| Line(s) | Claim | Actual state | Severity |
|---|---|---|---|
| L41-42 (Stock rule 4) | "`sale_stock_move.affected_recipe_id` is for audit, not for re-walking" | **Migration 092 dropped `sale_stock_move` entirely** per comments in `app/rms/sales/lifecycle.py:172-176`. The whole table is gone. Rule #4 is outdated. | medium — refers to non-existent table |
| L29 (Recipe rule — recipe_line line_kind) | Not verified stale but worth a check against current model schema | low risk |
| L41-42 (Stock rule 4) | (above) | medium |
| L47 (Testing rule 3) | "Costing tests are in `tests/test_costing.py`" | Need to verify. If tests moved to `tests/test_SASKIA-***`, the path is outdated. | low — may have moved |

### 3.2 Module is well-structured

The 30 rules across 6 sections (Money / Unit / Time / Recipe / Stock / Testing) are well-organized and largely correct. The "Things to NOT do" and "Tooling rules" (27-30) sections are recent (2026-10-08), accurate, and add real value.

### 3.3 Missing rules specific to `app/rms/`

1. **`Unit.coerce()` is the only way to read user-supplied units** — this is rule #1 but could be more explicit about where to find it (`app/rms/units.py`).
2. **`apply_stock_delta()` is the only helper for stock changes outside sale paths** — analogous to the rule about `to_int_gs()`. Missing.
3. **`app/rms/costing.py` is a deprecated shim; use `app.rms.profitability.cost` + `app.rms.sales.lifecycle` directly** — needs to be in the migration-rules or "things NOT to do" section.

---

## 4. What is still correct (no change needed)

These I checked and the doc is accurate:

- AGENTS.md L36-41 money rules (Decimal / to_int_gs-only / property tests / display rounding / CSV import / boundary rounding)
- AGENTS.md L46 (sale-path SSOT — the principle, just the file path is wrong; see §2.1)
- AGENTS.md L58 (pre-migration auto-backup, fail-closed)
- AGENTS.md L59 (`app_meta` is the schema-version source)
- AGENTS.md L60-62 (the two fail-closed rules)
- AGENTS.md L66-67 (timezones)
- AGENTS.md L72-76 (UI strings in vos / English code identifiers)
- AGENTS.md L80-83 (security: no new deps / no committed creds / no live PII)
- AGENTS.md L96 (CHANGELOG discipline — CI enforced)
- AGENTS.md L97 (single-developer bus factor)
- AGENTS.md L100-105 (anti-rule §1 React/Vue + the multi-tenant-with-≥2-clients caveat)
- All 20 anti-rules themselves (each was verified against the current state on 2026-10-07 per the doc; I haven't re-verified — that belongs in a separate sprint)
- All 5 locked hotfix SHAs

---

## 5. What should be ADDED (new rules, not fixes)

If we're improving "all the practices we prepared," here are 4 new rules the codebase now follows but the docs don't capture:

1. **`apply_stock_delta()` is the only path for non-sale stock changes.** Mirror AGENTS.md rule 8 (apply_sale-only-for-sales). Cite SASKIA-207. Cross-link `app/rms/stock_ledger.py`.

2. **`app/rms/costing.py` is a deprecated shim.** List the new SSOT paths: `app.rms.profitability.cost` for read-side cost, `app.rms.sales.lifecycle` for sale/void.

3. **Cross-session writes go to `.hermes/plans/` and `.hermes/lessons/`**; do not coordinate in chat. Cite `docs/operations/2026-10-04-sibling-session-coordination.md`.

4. **Every abstraction named in `app/rms/_abstraction_registry.py` (NEW in 211d) has an AST gate; the gate is run by `scripts/check_abstractions.py` and exit code MUST be 0 in CI.** Cite SASKIA-211.

---

## 6. Proposed SASKIA-211e PR (one PR; minimal-surface edits)

**Branch:** `docs/211-agents-md-freshen` off `main`. **Touches:** `AGENTS.md`, `app/rms/AGENTS.md`, no other files. **CHANGELOG entry required.**

### 6.1 Edits to `AGENTS.md`

| Section | Edit |
|---|---|
| Personas | Replace "Kiki" framing with current reality; line 11 becomes "AI agents reading this repo should ground their work in AGENTS.md, never assume operator context from elsewhere." |
| Hard rule 8 | Change "delegates to `apply_sale()` in `app/rms/costing.py`" → "delegates to `apply_sale()` in `app/rms/sales/lifecycle.py` (re-exported via the deprecated `app/rms/costing.py` shim for back-compat)" |
| Hard rule 12 | "117 migrations" → "118 migrations (verified via `grep _migration_ app/rms/db.py | sort -u` on 2026-10-08; no gaps in 1..118)" |
| After rule 11 (data integrity) | New rule **8a**: "All non-sale stock changes go through `apply_stock_delta()` in `app/rms/stock_ledger.py`. Sale/void paths stay in `apply_sale()` / `void_sale()` in `app/rms/sales/lifecycle.py`. Refund routes that are NOT sale/void reverse (e.g. cancellation that restores stock without a sale event) also use `apply_stock_delta()`." |
| After rule 6 (money) | New rule **6a**: "No integer-cast for money other than `to_int_gs()`. Use `to_int_gs(Decimal(...))` — never `int(Decimal(...))`." |
| Anti-rule 2 | Update counts: "Sazon has ~290 app/ python files, ~89 model classes across legacy + new + domain packages, 118 migrations" |
| Build brief | Demote "Tasks 1-10 of phase-1 dev plan" — done. Reference current work: pick from `IMPROVEMENT_BACKLOG.md` / `WHAT_NEXT.md` / the active SASKIA-ticket. |
| CI | Update anti-rule count: "13→14 of 20 enforced; remaining 6 are intentional forward-leverage (anti-rules §3, §12, §20 are not enforceable as gates, only as behavior tests)." |
| Render.com | Remove the line about `render.yaml`. The file is no longer in the repo. Add: "Render.com history lives in `docs/operations/2026-09-24-deployment.md`." |
| Add new top-level section "Cross-session protocol" | One paragraph + a pointer to `docs/operations/2026-10-04-sibling-session-coordination.md`. Cite SASKIA-211e. |

### 6.2 Edits to `app/rms/AGENTS.md`

| Section | Edit |
|---|---|
| Stock rule 4 | Remove. The `sale_stock_move` table was dropped in migration 092 (see `app/rms/sales/lifecycle.py:172-176`). The remaining StockMovement table's `affected_recipe_id` follows a different docstring. Replace with: "**Sale stock moves are atomic with sale creation.** The audit row's `affected_recipe_id` lets you re-walk the historical recipe tree for audit-only purposes, but the runtime walk during void uses current state." |
| Module structure | Add: "`app/rms/costing.py` is a deprecated shim — re-exports from `profitability.cost` and `sales.lifecycle`. New code should import from those modules directly." |
| After "Money rules" | New rule **6**: "Stock deltas outside sale paths MUST go through `apply_stock_delta()` in `app/rms/stock_ledger.py`. The bump + audit-row pattern is locked by `tests/test_SASKIA-207_stock_ledger.py`." |
| Migration rules | Add: "Migration 092 dropped `sale_stock_move` — the StockMovement audit row in `stock_movement` table is the only ledger. Code that referenced `sale_stock_move` must be updated to `StockMovement` directly (refund paths, sale paths)." |
| Tooling cheat sheet | Add: "211e: SASKIA-211 abstraction-gates track (`scripts/check_abstractions.py` + `app/rms/_abstraction_registry.py`)" |

---

## 7. Things in the doc that DON'T make sense (should be REMOVED, not fixed)

- L11 ("AI agents (Kiki, this assistant, future agents)") — contradicts L170. Pick one.
- L173-175 ("locked dev plan Tasks 1-10 in `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`") — Phase 1 dev plan is done per the live branch cadence (211/212/213/215). Remove or demote to historical.
- The entire Personas section could be tightened to two lines.

---

## 8. Risk of editing AGENTS.md

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Breaking references that other tools depend on (the COUNT of migrations in the doc, etc.) | Medium | Low | Verified via `grep _migration_`; counts always numeric |
| Operator disagreement with what counts as "missing rule" | Medium | Low | This analysis doc; §6 lists what to add |
| Sibling is editing AGENTS.md in parallel | Low | Medium | Check with reflog before commit; sibling owns `SASKIA-213-vaquita-seed-data-update` branch, would be separate commit |
| Doc churn interrupts other work | Low | Low | Single PR, scoped to two files |

**Edit surface:** 2 files, ~30 line changes in total. ~45 min PR including CHANGELOG.

---

## 9. Suggested process

1. Operator reads this analysis (5 min).
2. Operator approves, rejects, or modifies the proposed edits in §6.
3. Branch `docs/211-agents-md-freshen` from `main`.
4. Apply the agreed edits.
5. `uv run ruff check . && uv run ruff format --check .` (no logic changes, should be clean).
6. `uv run pytest tests/test_ci_anti_rules.py tests/test_SASKIA-207_stock_ledger.py tests/test_money.py` smoke (no test changes, should be green).
7. Commit with `chore(docs): SASKIA-211e refresh AGENTS.md against 2026-10-08 repo state`.
8. CHANGELOG entry per AGENTS rule 35.

**No code changes. No CI changes. No schema.** This is documentation-only and reversible by revert.

---

## 10. Sources & verification

- `git log --oneline -15` for sibling state, sibling commits `4e8fd6ab`, `dd08969e`.
- `grep _migration_ app/rms/db.py | sort -u` (Python equivalent) for migration count.
- Direct read of `app/rms/costing.py` (1.3 KB, deprecated shim).
- Direct read of `app/rms/sales/lifecycle.py:172-176` (migration 092 comment).
- Direct read of `app/rms/config.py:92` (`CURRENT_SCHEMA_VERSION = 118`).
- Direct read of `app/auth.py` (current_operator, current_user_id — NOT `app/rms/auth.py`).
- Direct read of `app/rms/stock_ledger.py` (apply_stock_delta + qty_to_stock_unit signatures).
- `pyproject.toml:69` for `fail-under=35` coverage gate.
- All 5 hotfix SHAs verified present via `git show`.
