# AIW-Org Corrective Action Plan — 2026-09-04

> **Audited commit**: `9e5a644` (2026-09-03 16:49 UTC) — corrective review by external auditor.
> **Current master**: `f008058` (2 commits past audit, locally green at 552 passed/3 skipped/0 failed).
> **Plan author**: Hermes Agent (prepared for Ivan + Kyrian)
> **Evidence basis**: Live local verification on 2026-09-04 — actual test runs, file counts, and code inspection at current HEAD.

---

## 0. What was verified vs. what the audit claimed

| Audit claim | Live state at `f008058` | Classification |
|---|---|---|
| Master CI is red (125 failed) | Local: 552 passed, 0 failed, 3 skipped. GitHub Actions may differ (CI creates `/opt/data` symlinks). | **Partially resolved** — local green, CI hermeticity still broken |
| 432 passed / 125 failed | 552 passed / 0 failed (local, with `/opt/data/.venv`) | **Improved** — the 125 failures were host-dependency tests; many fixed in PRs #28-#30 |
| 126/140 scripts contain `/opt/data` | 106/117 `.py` + 17/20 `.sh` = 123/137 still contain it | **Still critical** — 90% of scripts still have hardcoded paths |
| 22 scripts reference `AIW_ROOT`/`_paths` | 45 scripts reference it | **Improved** — doubled (22→45) |
| README claims 168 cron jobs, actual different | `readme-counts.py --check` fails: claims 168, actual 129 | **Still broken** — README count mismatch |
| Zero of 49 agents invoke enforcement wrapper | Global hard-stop enforcer deleted (PR #30) — correct disposition | **Resolved** (dead code deleted) |
| 188 cron registry, 140 enabled, 79 broken | 192 total, 129 enabled (10 broken disabled by PR #28) | **Partially addressed** — 10 broken crons disabled, 119 still need disposition |
| No `pyproject.toml` / `requirements.txt` / `uv.lock` | Still missing | **Still missing** |
| CI creates `/opt/data` symlinks | Still does (see `.github/workflows/ci.yml`) | **Still not hermetic** |
| `instinct_generator.py` doesn't emit `patch`/`agent_target` | Confirmed — still missing | **Still broken** |
| `homunculus.py` defaults missing eval to `1.0` (fail-open) | Confirmed — `load_eval_pass_rate` returns `1.0` on missing data | **Still broken** |
| No `kernel/` directory or `bootstrap-instance.sh` | Confirmed absent | **Still missing** (by design — premature) |
| Product Owner unresolved (DD-O1/O2/O3) | Confirmed still OPEN | **Still open** |

---

## 1. Epic structure

The audit identified 15+ distinct failure areas. These group into **6 epics**, each with a clear definition of done. Epics are ordered by the audit's own priority: Critical engineering failures first, then High operational, then Product/Org, then Research/Evidence, then Process.

| Epic | Title | Audit sections | Priority | Timeline |
|---|---|---|---|---|
| **E-CI** | CI Green + Hermetic Test Suite | §4.1, §4.2, §4.3 | Critical | First 48h |
| **E-PORT** | Path Portability + Deployment Contract | §4.3, §4.4, §5.8 | Critical/High | First week |
| **E-SAFE** | Enforced Safety + Self-Improvement Truth | §4.5, §4.6, §4.7 | Critical | First week |
| **E-OBS** | Observability over Self-Improvement | §4.6, §4.7, §5.1, §8.4 | Critical | Week 1–2 |
| **E-CRON** | Cron Fleet Reliability + Cost Truth | §5.1–§5.6 | High | First 2 weeks |
| **E-PROD** | Product Ownership + Org Discipline | §6.1–§6.6, §5.7, §5.10 | High | First 2 weeks |
| **E-EVID** | Evidence Maturity + Process Reset | §7, §8 | Medium | Weeks 3–4 |

### Epic E-OBS: Observability over Self-Improvement (added 2026-09-04, per Iván)

> **Definition of Done**: Every self-modifying script emits structured traces. Cron fleet carries per-job last-success + failure streaks. Bulk transformers use reusable fail-safe primitives. A generated dashboard answers "is self-improvement net-positive?" with measured deltas.
> **Rationale**: the final goal is agents that write prompts + Python. Prerequisites in order: observability → stability → predictability → hermetic environments → only then autonomous self-modification.

| Story | Ticket | Audit ref | Status | Owner | Acceptance criteria (abridged) |
|---|---|---|---|---|---|
| S-OBS-1: Trace-emission standard for self-modifying scripts | DEMIURGE-159 (new) | §4.6 | **NEW** | AI | JSONL traces {ts, actor, action, target, diff_sha256, dry_run, outcome} to `state/agent-traces.jsonl`; schema in CI; instinct_generator consumes enriched traces |
| S-OBS-2: Cron execution ledger + failure streaks + canary heartbeats | DEMIURGE-160 (new) | §5.1, §5.2 | **NEW** | AI | `schemas/cron-slo-registry.json` per-job: owner/purpose/last_success/consecutive_failures/duration/output_consumer/retirement_criterion; streak>N auto-flags; heartbeat-of-heartbeats |
| S-OBS-3: Fail-safe mechanics kit (dry-run, canary, atomic writes, invariant halts) | DEMIURGE-161 (new) | §4.7 | **NEW** | AI | `scripts/failsafe/` package; every bulk transformer calls it; tests prove dry-run/canary/atomic/hash-halt; truncation-incident regression test passes |
| S-OBS-4: Predictability dashboard (prompt-change history + eval trend + cron SLO burn) | DEMIURGE-162 (new) | §4.6, §8.4 | **NEW** | AI | `scripts/generate-dashboard.py` → `dashboards/autonomy.md`; per-agent pre/post eval deltas; answers net-positive question with measurements |

**Dependency**: E-OBS executes after E-CI is green and E-SAFE 140/141 land. E-OBS is the prerequisite for ever allowing autonomous prompt/code writes.

---

## 2a. Execution-tracking upgrade: DEMIURGE ↔ Hermes kanban bridge (added 2026-09-04, per Iván)

Per industry research (`/opt/data/profiles/ivan/research/agent-work-tracking-2026-09-04-synthesis.md`): Spec Kit (⭐133k), vibe-kanban (⭐28k), 12-factor-agents (⭐25.7k) converge on spec-layer + execution-layer + truth-layer separation. Hermes ships a native kanban (42 subcommands, SQLite, CAS atomic claims, run lifecycle `running|done|blocked|crashed|timed_out|failed|released`, `specify`/`decompose`/`swarm`).

**The bridge** (two-layer tracking, markdown stays the spec; kanban is execution truth):

```
DEMIURGE-XXX (spec: tickets/DEMIURGE-XXX/plan.md)
   └── kanban task on board "aiw-corrective" [claim → run → verify → release]
          └── PR with conventional commit + local-verified evidence
progress.md receives one sync line per kanban run outcome.
```

**Converge gate (new Definition of Done)**: a ticket is `done` only when, at HEAD, after the last commit: full pytest suite green AND `readme-counts.py --check` green AND `lint-prompts.py` green AND `restore-prompt-bodies.py --verify` green — passing **twice consecutively** (Spec-Kit repeat-until-Converged, adapted).

**Epic dependency order**: E-CI (truth) → E-SAFE (fail-closed) → E-OBS (eyes) → E-PORT (freedom) → E-CRON (fleet) → E-PROD (humans) → E-EVID (proof).

---

## 2. Epic details: stories, tickets, and status

### Epic E-CI: CI Green + Hermetic Test Suite

> **Definition of Done**: Three consecutive green GitHub Actions runs from clean runners. No `/opt/data` symlinks in CI. Test suite passes from `/tmp/<random>/` with `AIW_ROOT` set.

| Story | Ticket | Audit ref | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|
| S-CI-1: Fix `readme-counts.py --check` mismatch | DEMIURGE-126 (new) | §5.6, §5.5 | **NEW** | AI | `readme-counts.py --check` exits 0; README cron count matches live registry (129 enabled, not 168) |
| S-CI-2: Remove CI `/opt/data` symlink emulation | DEMIURGE-127 (new) | §4.2 | **NEW** | AI | CI step "Setup hermetic AIW_ROOT fixture" replaced with `AIW_ROOT=/tmp/<random>` env var; no `mkdir -p /opt/data`; no symlinks |
| S-CI-3: Run tests under random temporary root | DEMIURGE-099 (existing, pending) | §4.2 | PENDING | AI | `AIW_ROOT=/tmp/test-$$ python -m pytest tests/ -m 'not slow'` passes; no test creates or modifies anything under `/opt/data` |
| S-CI-4: Replace hardcoded `run-all.sh` interpreter | DEMIURGE-128 (new) | §4.2 | **NEW** | AI | `tests/run-all.sh` uses `python3 -m pytest` or `$PYTHON -m pytest`, not `/opt/data/.venv/bin/python3` |
| S-CI-5: Add CI check for `/opt/data` literals | DEMIURGE-129 (new) | §4.2 | **NEW** | AI | CI step `grep -rn '/opt/data' scripts/ --include='*.py'` fails unless file is in allowlist (`_paths.py`, `__init__.py`) |
| S-CI-6: Add root `pyproject.toml` | DEMIURGE-130 (new) | §4.3 | **NEW** | AI | `pyproject.toml` exists with `[project]` name, version, `requires-python = ">=3.11"`, dependencies: `pyyaml`, `croniter`, `pytest` |
| S-CI-7: Verify 3 consecutive green CI runs | DEMIURGE-131 (new) | §4.1 | **NEW** | AI | Three consecutive `push` triggers on `master` all green; all gates execute (not skipped) |

**Current state**: Local tests pass (552/0/3), but CI `readme-counts.py --check` fails because README says 168 cron jobs while live registry has 129. The CI fixture creates `/opt/data` symlinks, which is the opposite of hermetic.

---

### Epic E-PORT: Path Portability + Deployment Contract

> **Definition of Done**: Every script derives paths from `_paths.py`/`AIW_ROOT`. No manual script copies under `/opt/data/scripts/`. One deployment contract document exists.

| Story | Ticket | Audit ref | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|
| S-PORT-1: Thread remaining 72 Python scripts via `_paths.py` | DEMIURGE-098 (existing) + DEMIURGE-132–134 (new, batched) | §4.3 | IN PROGRESS (45/117 done) | AI | 0 Python scripts in `scripts/` contain literal `/opt/data` outside `_paths.py`; `grep -rn '/opt/data' scripts/ --include='*.py'` returns only `_paths.py` |
| S-PORT-2: Thread remaining shell scripts via `AIW_ROOT` env | DEMIURGE-135 (new) | §4.3 | **NEW** | AI | 0 shell scripts in `scripts/` contain literal `/opt/data` except a documented allowlist |
| S-PORT-3: Define source-to-deployment contract | DEMIURGE-136 (new) | §4.4, §5.8 | **NEW** | Ivan + AI | Document at `docs/DEPLOYMENT-CONTRACT.md`: either (a) crons execute repo entry points directly, or (b) `scripts/deploy.sh <version>` installs to `/opt/data/scripts/`; no manual copies |
| S-PORT-4: Remove duplicate scripts | DEMIURGE-137 (new) | §5.8 | **NEW** | AI | CI check: `scripts/dedupe-check.py` finds zero content-identical script pairs (or they're in an allowlist with explanation) |
| S-PORT-5: Remove `/opt/data/scripts/` copies or sync them | DEMIURGE-138 (new) | §4.4 | **NEW** | Ivan | Either deploy contract covers them (S-PORT-3) or they're deleted with a migration record |

**Current state**: 45/117 Python scripts use `AIW_ROOT`/`_paths`. 72 still hardcode `/opt/data`. 14 scripts were copied to `/opt/data/scripts/` (commit `9e5a644`) — these are the deployment drift source.

---

### Epic E-SAFE: Enforced Safety + Self-Improvement Truth

> **Definition of Done**: Self-improvement pipeline renamed to "curated improvement proposal pipeline". All fail-open paths fixed. One real action path has enforced hard stops with tested denial cases.

| Story | Ticket | Audit ref | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|
| S-SAFE-1: Rename "self-improving" to "curated improvement proposal pipeline" | DEMIURGE-139 (new) | §4.6 | **NEW** | AI | `AIW-SELF-IMPROVING-CAPABILITIES.md` → `AIW-CURATED-IMPROVEMENT-PIPELINE.md`; all references updated; no document says "self-improving" without qualification |
| S-SAFE-2: Fix `instinct_generator.py` to emit `patch` + `agent_target` | DEMIURGE-140 (new) | §4.6 | **NEW** | AI | Generator output includes `patch` and `agent_target` fields; downstream `curator-evolver.py` reads them; test verifies non-empty on synthetic data |
| S-SAFE-3: Fix `homunculus.py` fail-open eval default | DEMIURGE-141 (new) | §4.6 | **NEW** | AI | `load_eval_pass_rate()` returns `0.0` (deny) on missing/malformed/unknown-agent data, not `1.0`; test covers missing-eval, malformed-eval, and unknown-agent cases |
| S-SAFE-4: Implement sandbox application for proposals | DEMIURGE-142 (new) | §4.6 | **NEW** | AI | Approved proposals apply to a copy in `state/curation-sandbox/`, not the live `PROMPT.md`; a pre/post eval suite runs against the sandbox |
| S-SAFE-5: Implement automatic rollback on regression | DEMIURGE-143 (new) | §4.6 | **NEW** | AI | If post-application eval score < pre-application score, sandbox is reverted; test verifies rollback fires on synthetic regression |
| S-SAFE-6: Add enforced hard-stop to one real action path | DEMIURGE-115 (existing, pending) | §4.5 | PENDING (Ivan-gated) | Ivan | One real action (email, payment, or public post) has an authorization check in the action path; test covers: denial, timeout, replay, forged approval, missing approval, stale approval |

**Current state**: `instinct_generator.py` hardcodes `/opt/data`, doesn't emit `patch`/`agent_target`. `homunculus.py` `load_eval_pass_rate()` returns `1.0` on missing data — fail-open. No sandbox. No rollback. The old enforcer was correctly deleted (dead code).

---

### Epic E-CRON: Cron Fleet Reliability + Cost Truth

> **Definition of Done**: Every enabled cron has an owner, SLO, output consumer, and retirement criterion. No enabled cron has an empty prompt. Cost claims include source, coverage, timestamp, and confidence.

| Story | Ticket | Audit ref | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|
| S-CRON-1: Per-job SLO + owner + consumer registry | DEMIURGE-144 (new) | §5.1, §5.10 | **NEW** | AI | `schemas/cron-slo-registry.json` exists; each enabled job has: `owner`, `purpose`, `last_success`, `consecutive_failures`, `output_consumer`, `retirement_criterion`; CI validates schema |
| S-CRON-2: Repair or retire top-10 highest-value broken crons | DEMIURGE-113 (existing, pending) | §5.1, §5.2 | PENDING (Ivan-gated) | Ivan | 10 highest-value jobs either (a) run successfully once or (b) are retired with a record; each has one of: retired/replaced/blocked-with-deadline/repaired |
| S-CRON-3: Fix empty-prompt cron jobs | DEMIURGE-121 (existing, done) | §5.1 | DONE | AI | 4 fully-orphan jobs identified and dispositioned (done in DEMIURGE-121) |
| S-CRON-4: Add provenance tags to cost events | DEMIURGE-145 (new) | §5.3 | **NEW** | AI | Every cost event in `state/token-ledger.json` has `source` (measured/estimated/synthetic/unknown), `coverage`, `timestamp`, `pricing_version`, `confidence` |
| S-CRON-5: Separate no-agent jobs from LLM jobs | DEMIURGE-146 (new) | §5.4 | **NEW** | AI | Cron registry entries have `agent_required: bool`; no-agent jobs don't carry model fields; CI validates |
| S-CRON-6: Provider capability matrix + preflight test | DEMIURGE-147 (new) | §5.4 | **NEW** | AI | `docs/PROVIDER-CAPABILITY-MATRIX.md` exists; `scripts/provider-preflight.py` tests all providers before fleet migration; canary 10 jobs before full switch |

**Current state**: 192 total crons, 129 enabled. 10 broken ones disabled (PR #28). 4 orphan jobs identified (DEMIURGE-121). Cost claims corrected from $93.61/day to ~$0.18/day for crons. But cost events don't carry provenance metadata.

---

### Epic E-PROD: Product Ownership + Org Discipline

> **Definition of Done**: Human Product Owner named. One-page product boundary written. Every agent/monitor has a named consumer or is parked. No new departments.

| Story | Ticket | Audit ref | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|
| S-PROD-1: Name human Product Owner (DD-O1) | DEMIURGE-148 (new) | §6.1 | **NEW (Ivan-gated)** | Ivan | DECISIONS.md DD-O1 status changes from OPEN to LOCKED with a named human (Ivan, Kyrian, or split) |
| S-PROD-2: Write one-page product boundary (DD-O3) | DEMIURGE-149 (new) | §6.1 | **NEW (Ivan-gated)** | Ivan | `docs/PRODUCT-BOUNDARY.md` exists: audience, problem, deliverable, exclusions, price, promises |
| S-PROD-3: Decide Athena vs thin PO agent (DD-O2) | DEMIURGE-150 (new) | §6.1 | **NEW (Ivan-gated)** | Ivan | DD-O2 changes from OPEN to LOCKED; if adding PO agent, it maintains evidence + backlog, doesn't decide strategy |
| S-PROD-4: Audit every agent/monitor for consumer | DEMIURGE-151 (new) | §5.7, §5.10 | **NEW** | AI | `scripts/consumer-audit.py` outputs: per-agent, named consumer, last-read timestamp, decision informed; agents with no consumer are marked `dormant` |
| S-PROD-5: Park or activate `people-hr` | DEMIURGE-152 (new) | §6.3 | **NEW (Ivan-gated)** | Ivan | `06-people-culture/people-hr` either (a) has one weekly useful output contract or (b) is marked `dormant` in department-index.md |
| S-PROD-6: WIP limits per person + agent | DEMIURGE-153 (new) | §5.7 | **NEW** | AI | `tickets/INDEX.md` shows per-owner WIP count; CI warns when WIP limit exceeded; no new ticket without owner |
| S-PROD-7: Consolidate duplicate agent names | DEMIURGE-154 (new) | §5.8 | **NEW** | AI | 5 duplicate directory names (ai-ops-coordinator, bizops-tracker, business-analyst, compliance-monitor, management-coordinator) have declared aliases or are merged |

**Current state**: 76 prompts, 71 monitors, 140 scripts — far more artifacts than the ~2 humans can consume. Product Owner is still OPEN. `people-hr` has 1 prompt and no evidence of ever running.

---

### Epic E-EVID: Evidence Maturity + Process Reset

> **Definition of Done**: Every "complete" claim has a maturity level. Inventories generated from tree. Operational drills run. Merge velocity controlled.

| Story | Ticket | Audit ref | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|
| S-EVID-1: Adopt maturity ladder labels | DEMIURGE-108 (existing, pending) | §7.3 | PENDING | AI | No document uses "complete" without a maturity level from: proposed, designed, implemented, unit-tested, integration-tested, deployed, operated, outcome-validated, independently-reviewed |
| S-EVID-2: Generate `inventory.json` from tree | DEMIURGE-155 (new) | §5.5 | **NEW** | AI | `scripts/generate-inventory.py` outputs `inventory.json` with: prompt count, monitor count, script count, test count, ticket count — all from actual `find`/`grep`, not hand-maintained |
| S-EVID-3: Fix `readme-counts.py` to cover all claims | DEMIURGE-096 (existing, pending) | §5.6 | PENDING | AI | Every numeric claim in README.md is checked by `readme-counts.py --check`; script reports which claims are checked, skipped, or not understood |
| S-EVID-4: Run first controlled chaos drill | DEMIURGE-156 (new) | §8.4 | **NEW** | AI | One of: state-corruption recovery, provider outage, stale approval, missing dependency, malformed agent output, restore-from-backup — with recorded detection time, response time, data loss, false alarms |
| S-EVID-5: Stabilization window after infrastructure PRs | DEMIURGE-157 (new) | §8.1 | **NEW** | Ivan | After any WS-3/portability/cron PR, no new workstream starts for 24h; deployed behavior verified before next batch |
| S-EVID-6: Reassess sales-funnel deferral with evidence | DEMIURGE-158 (new) | §6.4 | **NEW (Ivan-gated)** | Ivan | DD-08 reassessed with: active customers, conversion, retained usage, revenue, product readiness blockers, founder capacity — or a small manual sales experiment is run |

**Current state**: Maturity labels are inconsistent. Multiple documents cite incompatible totals. `readme-counts.py` only checks some claims. No chaos drill has been run. The David Ondrej analysis is used only for content strategy (correct).

---

## 3. What's already DONE (audit findings that are resolved or partially resolved)

| Audit finding | Resolution | Evidence |
|---|---|---|
| Zero of 49 agents invoke enforcement wrapper | **RESOLVED** — dead code deleted (PR #30, ADR-0006) | `scripts/global-hard-stop-enforcer.py` no longer exists |
| 79 broken cron jobs | **PARTIALLY RESOLVED** — 10 disabled (PR #28), 4 orphans identified (DEMIURGE-121) | `disable_or_fix_broken_crons.py` |
| $93.61/day cost estimate was wrong | **RESOLVED** — corrected to ~$0.18/day for crons (TOKEN-AUDIT-SYNTHESIS) | `analysis/TOKEN-AUDIT-SYNTHESIS-2026-09-03.md` |
| Skills inventory said 126, actual is 43 | **RESOLVED** — corrected (PR #24) | `analysis/SKILLS-INVENTORY-2026-09-03.md` |
| Prompt truncation incident (65/76 prompts) | **RESOLVED** — prompts restored, 7 stubs marked, trust-window audited | `analysis/STATE-WRITE-TRUST-WINDOW-2026-09-01.md` |
| Six-department freeze | **MAINTAINED** — DD-02 still LOCKED | `meetings/department-design/DECISIONS.md` |
| Caching of /opt/data path | **PARTIALLY RESOLVED** — 45/117 scripts threaded (was 22) | `scripts/_paths.py` + 45 references |
| CI infrastructure exists | **MAINTAINED** — workflow exists, lint passes, but fast pytest stage may fail on GitHub runners | `.github/workflows/ci.yml` |
| Test count: 566 collected | **IMPROVED** — 552 passed, 3 skipped, 0 failed (local) | `/opt/data/.venv/bin/python3 -m pytest tests/ -m 'not slow'` |
| Cron empty-prompt audit | **DONE** — DEMIURGE-121 completed | `analysis/CRON-EMPTY-PROMPT-AUDIT-2026-09-02.md` |
| Hard-stop ADR disposition | **DONE** — ADR-0006 documents 3 options, default = delete | `docs/adr/0006-hard-stop-enforcer-disposition.md` |

---

## 4. What's NOT done (genuinely missing — needs new work)

| Gap | Audit section | Epic | New ticket(s) |
|---|---|---|---|
| CI not hermetic (symlinks `/opt/data`) | §4.2 | E-CI | DEMIURGE-127, 128, 129 |
| `readme-counts.py --check` fails (168 vs 129) | §5.5/5.6 | E-CI | DEMIURGE-126 |
| No root `pyproject.toml` / dependency manifest | §4.3 | E-CI | DEMIURGE-130 |
| 72 Python scripts still hardcode `/opt/data` | §4.3 | E-PORT | DEMIURGE-132–135 |
| 17 shell scripts still hardcode `/opt/data` | §4.3 | E-PORT | DEMIURGE-135 |
| No deployment contract (scripts copied manually) | §4.4 | E-PORT | DEMIURGE-136, 138 |
| Duplicate script contents exist | §5.8 | E-PORT | DEMIURGE-137 |
| `instinct_generator.py` missing `patch`/`agent_target` | §4.6 | E-SAFE | DEMIURGE-140 |
| `homunculus.py` fail-open on missing eval | §4.6 | E-SAFE | DEMIURGE-141 |
| No sandbox application for proposals | §4.6 | E-SAFE | DEMIURGE-142 |
| No automatic rollback on regression | §4.6 | E-SAFE | DEMIURGE-143 |
| No enforced hard-stop on any real action | §4.5 | E-SAFE | DEMIURGE-115 |
| Per-job SLO/owner/consumer/retirement registry | §5.1 | E-CRON | DEMIURGE-144 |
| Cost events lack provenance metadata | §5.3 | E-CRON | DEMIURGE-145 |
| No provider capability matrix | §5.4 | E-CRON | DEMIURGE-146, 147 |
| Product Owner unresolved (DD-O1/O2/O3) | §6.1 | E-PROD | DEMIURGE-148–150 |
| `people-hr` has no consumer | §6.3 | E-PROD | DEMIURGE-152 |
| No WIP limits | §5.7 | E-PROD | DEMIURGE-153 |
| Duplicate agent directory names | §5.8 | E-PROD | DEMIURGE-154 |
| No `inventory.json` generated from tree | §5.5 | E-EVID | DEMIURGE-155 |
| No chaos drill run | §8.4 | E-EVID | DEMIURGE-156 |
| No stabilization window | §8.1 | E-EVID | DEMIURGE-157 |
| Sales-funnel deferral not evidence-based | §6.4 | E-EVID | DEMIURGE-158 |
| "Self-improving" label overstated | §4.6 | E-SAFE | DEMIURGE-139 |
| Maturity labels not adopted | §7.3 | E-EVID | DEMIURGE-108 |
| `run-all.sh` hardcodes host venv path | §4.2 | E-CI | DEMIURGE-128 |

---

## 5. Recommended execution order

### Phase 1 — First 48 hours (Critical engineering)

> **Freeze**: No new agents, departments, monitors, tickets, or kernel work.

1. **S-CI-1** (DEMIURGE-126): Fix `readme-counts.py --check` — README says 168 cron jobs, actual is 129. Update README or the count checker.
2. **S-CI-4** (DEMIURGE-128): Fix `tests/run-all.sh` to use `python3 -m pytest` instead of `/opt/data/.venv/bin/python3`.
3. **S-CI-6** (DEMIURGE-130): Add root `pyproject.toml` with declared dependencies.
4. **S-CI-2** (DEMIURGE-127): Remove CI `/opt/data` symlink emulation — replace with `AIW_ROOT=/tmp/<random>`.
5. **S-CI-3** (DEMIURGE-099): Verify tests pass from random temp root.
6. **S-CI-5** (DEMIURGE-129): Add CI gate that rejects new `/opt/data` literals.
7. **S-CI-7** (DEMIURGE-131): Verify 3 consecutive green CI runs.

**Exit gate**: Three green CI runs. No symlinks. No `/opt/data` in CI.

### Phase 2 — First week (Portability + Safety truth)

8. **S-PORT-1** (DEMIURGE-098 + 132–134): Thread remaining 72 scripts through `_paths.py` in batches of ~15.
9. **S-PORT-2** (DEMIURGE-135): Thread shell scripts through `AIW_ROOT` env var.
10. **S-SAFE-1** (DEMIURGE-139): Rename "self-improving" → "curated improvement proposal pipeline".
11. **S-SAFE-2** (DEMIURGE-140): Fix `instinct_generator.py` to emit `patch` + `agent_target`.
12. **S-SAFE-3** (DEMIURGE-141): Fix `homunculus.py` fail-open → fail-closed.
13. **S-CRON-1** (DEMIURGE-144): Build per-job SLO/owner/consumer registry.
14. **S-CRON-4** (DEMIURGE-145): Add provenance tags to cost events.

**Exit gate**: `grep -rn '/opt/data' scripts/ --include='*.py'` returns only `_paths.py`. Self-improvement pipeline renamed. Eval defaults to deny.

### Phase 3 — Second week (Product + Org + Enforcement)

15. **S-PROD-1** (DEMIURGE-148): **Ivan** — name human Product Owner.
16. **S-PROD-2** (DEMIURGE-149): **Ivan** — write one-page product boundary.
17. **S-PROD-3** (DEMIURGE-150): **Ivan** — decide Athena vs thin PO agent.
18. **S-PROD-4** (DEMIURGE-151): Audit every agent/monitor for consumer.
19. **S-PROD-5** (DEMIURGE-152): **Ivan** — park or activate `people-hr`.
20. **S-SAFE-4** (DEMIURGE-142): Implement sandbox application.
21. **S-SAFE-5** (DEMIURGE-143): Implement automatic rollback.
22. **S-SAFE-6** (DEMIURGE-115): **Ivan** — add enforced hard-stop to one real action.
23. **S-EVID-4** (DEMIURGE-156): Run first controlled chaos drill.

**Exit gate**: Product Owner named. One safety gate denies the wrong action. One chaos drill completed.

### Phase 4 — Weeks 3–4 (Evidence + Operation)

24. **S-EVID-1** (DEMIURGE-108): Adopt maturity ladder labels across all docs.
25. **S-EVID-2** (DEMIURGE-155): Generate `inventory.json` from tree.
26. **S-EVID-3** (DEMIURGE-096): Fix `readme-counts.py` to cover all numeric claims.
27. **S-CRON-2** (DEMIURGE-113): **Ivan** — repair or retire top-10 broken crons.
28. **S-CRON-5** (DEMIURGE-146): Separate no-agent jobs from LLM jobs.
29. **S-CRON-6** (DEMIURGE-147): Provider capability matrix + preflight.
30. **S-PORT-3** (DEMIURGE-136): **Ivan** — define deployment contract.
31. **S-PORT-4** (DEMIURGE-137): Remove duplicate scripts.
32. **S-PORT-5** (DEMIURGE-138): Remove `/opt/data/scripts/` copies.
33. **S-PROD-6** (DEMIURGE-153): WIP limits.
34. **S-PROD-7** (DEMIURGE-154): Consolidate duplicate agent names.
35. **S-EVID-5** (DEMIURGE-157): **Ivan** — stabilization window.
36. **S-EVID-6** (DEMIURGE-158): **Ivan** — reassess sales-funnel deferral.

**Exit gate**: Four weeks of successful useful scheduled runs. Inventories generated, not hand-maintained. Every "complete" has a maturity level.

---

## 6. Operating rules (adopted from audit §12)

1. **No green baseline, no feature merge.**
2. **No consumer, no agent or monitor.**
3. **No measured source, no precise cost claim.**
4. **No executable gate, no safety claim.**
5. **No closed feedback loop, no self-improvement claim.**
6. **No clean-root test, no portability claim.**
7. **No direct approval, no requirements attributed to another person.**
8. **No human owner, no strategic agent delegation.**
9. **No repeated successful operation, no "complete."**
10. **No deployment contract, no copied runtime script.**
11. **No generated inventory, no hand-maintained headline count.**
12. **No WIP limit, no new workstream.**
13. **No dated evidence, no timeless operational fact.**
14. **No pre/post evaluation, no retained automated prompt change.**
15. **No explicit retirement condition, no recurring job.**

---

## 7. What NOT to change (from audit §9)

- ✅ Keep the six-department freeze (DD-02)
- ✅ Keep separating aiw-org, growth-coaching, coach-agents, state-versioned
- ✅ Keep using ADRs and explicit locked/open decisions
- ✅ Keep auditing downstream damage after incidents
- ✅ Keep closing bad branches rather than merging for activity credit
- ✅ Keep reverting changes when evidence disproves them
- ✅ Keep deleting unwired code that creates false confidence
- ✅ Keep distinguishing internal human-in-the-loop from future client-grade autonomy
- ✅ Keep the David Ondrej analysis bounded to content strategy (not engineering validation)
- ✅ Keep the Saskia design as a disposable hypothesis (do not implement without consent)
- ✅ Keep the kernel as a future direction (do not build until a second instance proves the need)

---

## 8. Ticket summary

| ID range | Epic | Count | Owner | Timeline |
|---|---|---|---|---|
| DEMIURGE-126–131 | E-CI | 6 (+ DEMIURGE-099 existing) | AI + Ivan | 48h |
| DEMIURGE-132–138 | E-PORT | 7 (+ DEMIURGE-098 existing) | AI + Ivan | Week 1–2 |
| DEMIURGE-139–143 | E-SAFE | 5 (+ DEMIURGE-115 existing) | AI + Ivan | Week 1–2 |
| DEMIURGE-144–147 | E-CRON | 4 (+ DEMIURGE-113, 121 existing) | AI + Ivan | Weeks 1–3 |
| DEMIURGE-148–154 | E-PROD | 7 | Ivan + AI | Weeks 2–3 |
| DEMIURGE-155–158 | E-EVID | 4 (+ DEMIURGE-096, 108 existing) | AI + Ivan | Weeks 3–4 |
| **Total new** | | **33** | | **4 weeks** |

**Ivan-gated decisions** (cannot be done by agents): DEMIURGE-115, 136, 148, 149, 150, 152, 157, 158 (8 items)

---

*Plan authored: 2026-09-04*
*Next review: after Phase 1 exit gate (three green CI runs)*
