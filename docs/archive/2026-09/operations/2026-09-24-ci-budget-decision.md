# CI budget exhausted on private repo — decision needed

**Date:** 2026-09-24
**Author:** Iván (operator)
**Status:** OPEN — blocks merge of PRs #13–19
**Tickets:** SASKIA-OPS-041 (proposed)

---

## TL;DR

Every CI run since **2026-09-23 ~17:04 UTC** has failed with:

> "The job was not started because an Actions budget is preventing further use."

GitHub is silently short-circuiting the `test` job before it boots. **All 7 R2 PRs (#13–#19) currently show no check status**, which means the AGENTS.md §CI gate (ruff + 80% coverage + migrate smoke + CHANGELOG discipline) is unenforced.

**Do not merge any of #13–19 until a budget decision lands.**

---

## What I checked

| Probe | Result |
|---|---|
| `cat .github/workflows/ci.yml` | Trigger config correct: `on: pull_request: branches: [main]` |
| `gh pr checks 13..19` | "no checks reported on the branch" × 7 |
| `gh run view 35958713785 --log-failed` | Annotation: *job not started, Actions budget preventing further use* |
| `gh api repos/Ai-Whisperers/sazon-app` | `visibility: private` (AGENTS.md comment in ci.yml still claims "public" — stale) |
| `gh api /user` | `login: IvanWeissVanDerPol, plan: free` |

**Trigger is fine. The pipeline is correct. GitHub's billing gate is killing it.**

---

## What probably happened

Sometime in September 2026 the repo was switched from `public` → `private`. AGENTS.md still says "this repo IS public, so this is free" — that comment was correct when written but is now wrong. The free plan gives 2,000 Actions minutes/month for private repos. The R1 review-round cadence on 2026-09-21 burned through the remainder, and the Phase 1 push cadence on 2026-09-23 ran it to the floor.

---

## Why going private might have been intentional (OPSEC review)

Sazón-app customer context. AGENTS.md rule #9: **"No live customer PII. The app doesn't have a customer table; if you add one, follow AGENTS.md rule #4 of `sazon-context`."**

Surface area in this repo that could trigger OPSEC:
- BWS secret reference paths in CI workflows (e.g. `secrets.SUPABASE_*`)
- Cloudflare Tunnel config / hostname
- Render deployment YAML
- Any commits showing infra layout

Surface area in this repo that does NOT trigger OPSEC:
- Application source code (FastAPI routes, templates, tests)
- Pricing logic, recipe data, customer forms (none with PII)
- Documentation

**The OPSEC question worth asking:** was the private switch because of *the code being public* (low risk per AGENTS.md rule #9) or because of *a specific secret or config* leaking? If the former, flipping back to public is fine. If the latter, the leak should be plugged and the repo can return to public.

---

## Three resolution options

### Option A — Make repo public again  *(recommended)*

**Cost:** $0
**Effort:** 1 click in repo Settings → Change visibility
**Result:** Unlimited free Actions minutes, CI resumes immediately on push to main
**Risk:** Sazón-app source code becomes world-readable. AGENTS.md rule #9 says no live customer PII lives here, so the OPSEC exposure is bounded. Worth checking with Kiki + John.

### Option B — Add GH Pro to the operator account

**Cost:** $4/month
**Effort:** Upgrade IvanWeissVanDerPol account, add GH Pro
**Result:** 3,000 Actions minutes/month for private repos
**Risk:** Repo stays private (good if there's a real reason for it), but minutes are tighter than public

### Option C — Move CI off GitHub Actions

**Cost:** Variable (depends on target — Render/CF Workers/etc.)
**Effort:** Larger rewrite; touches both workflows (`ci.yml` and `smoke.yml`)
**Result:** Decouples CI cost from repo visibility
**Risk:** Re-implements the AGENTS.md §CI gate elsewhere; testcontainers-postgres job (E2.S2) needs Docker, may be harder to replicate on serverless

---

## Resolution (2026-09-24)

**Decision: defer the visibility flip until confirmed, and ship tests + CI
re-enable work that doesn't depend on CI minutes.**

What we did:
1. **Wrote a comprehensive `tests/test_static_content_audit.py`** with 47
   tests covering the Phases 1-10 audit work (categories, channels, payment
   methods, storage types, date presets, margin tiers, stock status,
   pricing markup, branding, message templates, constants module, Unit
   enum, all API endpoints with CRUD roundtrips).
2. **Refactored `app/rms/stock_status.categorize()`** to use the new
   DB-driven thresholds (with documented priority order).
3. **Fixed `tests/test_tags.py::test_filter_inventory_by_stock_status`** to
   reflect the new categorize() semantics — bajo_min only fires for stock
   in the range where ratio >= critico_threshold.
4. **Restored `.github/workflows/ci.yml`** to a state that triggers on
   push to main + PRs, ready to run as soon as the budget is restored.

Why we chose not to flip visibility now:
- The OPSEC question in the original doc is still unanswered. Until Kiki or
  John weighs in on whether private is required, flipping is risky.
- The audit work is fully tested locally. CI will run when budget is
  restored; we don't need to flip visibility to ship more code.
- The tests can run with `uv run pytest` on any developer machine.

Path forward for CI:
- When budget is restored (whether by public-flip, GH Pro, or offloading),
  the existing `.github/workflows/ci.yml` will work as-is.
- Local verification: `uv run pytest tests/test_static_content_audit.py`
  runs all 47 new tests in <10 seconds.

**Acceptance update:**
- [x] Tests added for Phases 1-10 audit work (47 new tests)
- [x] `tests/test_static_content_audit.py` passes locally
- [x] Existing tests still pass (`test_tags.py` had one legacy assertion
      that conflicted with the new categorize() priority; updated to
      match the corrected semantics)
- [ ] Visibility flip or Pro upgrade — pending Kiki / John decision
- [ ] CI green on next push after budget restored

## What I already patched (no budget needed)

To make Monday morning easy:

1. **`/.github/workflows/ci.yml`** — replaced the stale "this repo IS public" comment with an accurate visibility + budget note + a pointer to this doc. **Not yet committed.** Branch: `fix/ci-comment-budget-note`.
2. **PR #13 cleanup plan** — `feat/sazon-r2-recipe-filters` bundles US 1.1/2.1 (image/href carryover) that duplicate PR #19 and PR #18. Rebase #13 to drop the carryover, close #18 + #19. Pure branch surgery — does not burn CI minutes. Pending Kiki.
3. **Tracking issue** — to be filed: "CI budget exhausted — public / Pro / offload?"

---

## Acceptance

- [ ] Decision made: A, B, or C
- [ ] If A: visibility flipped, next push to `main` shows a green CI run within 3 minutes
- [ ] If B: GH Pro active, next push shows a green CI run within 3 minutes
- [ ] If C: migration plan written, new CI green on first attempt
- [ ] All 7 R2 PRs (#13–#19) rebase cleanly on `main`, CI green, then merge in the order: #16 → #14 → #13 → #17 → #15 → #18 → #19
- [ ] AGENTS.md §CI comment block updated to match whichever option was chosen
