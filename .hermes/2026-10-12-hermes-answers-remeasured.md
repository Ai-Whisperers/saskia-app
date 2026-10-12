# HERMES-ANSWERS re-measured — 2026-10-12 live VPS verification

**Source doc:** `/opt/data/aiw-org-work/docs/HERMES-ANSWERS-2026-09-02.md` (142 questions, measured 2026-09-02 against `3471e2a`)
**This pass:** 2026-10-12, live probes against `/opt/data` (host HEAD `555cc58` 2026-10-07; fresh clone `bc6faf5`; stale clone `66b5485` 2026-09-02)
**Method:** every file/registry/script answer below was re-read from the live system this session. No inference without a probe.

---

## 0. The 5 findings that changed since 2026-09-02 (read this first)

| # | Was (09-02) | Now (10-12, measured) | Verdict |
|---|---|---|---|
| 1 | Truncation incident: live PROMPT.md at 17 lines [BLOCKING] | **FIXED.** security-watchdog-30min = 245 lines live, 195 in clone. Fleet-wide: 46/46 PROMPT.md ≥123 lines, zero under 40 | Resolved |
| 2 | 47% of fleet broken (79/168) | **FIXED-ish.** 163 jobs, 105 enabled, only **6 errors (5.7%)**. The litellm/`primary` provider fields were stripped entirely — jobs now run agent-side | Resolved |
| 3 | Cron registry at `/opt/data/.hermes/cron/jobs.json` | **MOVED to `/opt/data/cron/jobs.json`** — and the move **broke 3 scripts** that still hardcode the old path (see §2, BUG-1) | **NEW BUG** |
| 4 | decisions_for_ivan: 424 items (saturation) | **25 items**, oldest 2026-09-21. Queue was cleaned (clean_decision_queue.py exists on host) | Resolved |
| 5 | token-ledger.json inert (2 events), token-cap fake-fires | **token-ledger.json DELETED** from /opt/data/state. token-cap.py still exists (host + 2 clones, 3 divergent copies — see DUP-3) | Half-fixed, now duplicated |

---

## 1. Question-by-question re-answers (only where state changed or doc was wrong)

### Section 1 — truncation incident
- **Q1 (paths):** Both trees still exist, but roles changed: `/opt/data/agents` = live+newest (HEAD 2026-10-07); `/opt/data/agents-v2/aiw-org-clone` = **stale, 40 days behind** (HEAD 2026-09-02, same day the doc was written); `/opt/data/aiw-org-work/aiw-org` = fresh second clone (2026-10-07). → see DUP-1: three clones of one repo.
- **Q2 (live truncation):** NO longer truncated. 245 lines live vs 195 in the stale clone — the live tree is now the LONGER one. Incident fully remediated.
- **Q5 (regression test):** `restore-prompt-bodies.py --verify` now exists in all 3 clones (it's in the converge gate per REFERENCE.md). Whether a min-line-count test exists: the lint still doesn't check body length — **recommendation stands: add `assert len(lines) >= 40` to lint-prompts.py.**
- **Q7 (bulk frontmatter scripts):** all 4 still present in all 3 copies. The body-preserving fix (`restore-prompt-bodies.py`) landed. Risk class documented but the buggy scripts were never quarantined — they can re-fire.

### Section 2 — runtime mechanics
- **Q12 (prompt caching):** `prompt_caching.py` now lives at `/opt/data/hermes-agent-latest/agent/` and `/opt/data/hermes-agent/agent/` (hermes-fixed is gone). Still **no `cache_control` in the cron path** — the biggest input-token optimization remains open.
- **Q13 (port 8787):** Nothing listens on 8787 anymore. Listening now: **22, 53, 443, 8090, 8642, 9119, 37470**. The gateway topology changed; docs citing 8787 are stale.
- **Q11 (parent_spec):** still on **46/46** live PROMPT.md files. The ~10k-token ORG-AGENTS.md load per invocation is still the top cost driver — link-by-ID recommendation still open.

### Section 3 — cron fleet
- **Q21/Q22:** 163 total / 105 enabled (was 184/168). Fleet was actively pruned — contradicts the old "nothing is ever deleted" claim; deletion/disabling happened ~24%.
- **Q23-25:** provider breakdown now: `(empty)/(empty)` = 100, `no-llm/no-llm` = 5. The litellm/primary/fast/reasoning model fields were **removed wholesale** (there's a `clean-script-model-fields.py` and `migrate-litellm-to-minimax.py` on host). Status of enabled: **98 ok / 6 error / 1 None.**
- **Q29 (alert_sent):** still 0 unalerted errors. Good.
- **Q30 (sunday stack):** confirmed gone — no sunday jobs remain.
- **Q31 (people-hr):** `aiw-people-hr-monitor-30min` exists, **disabled**, last status ok (2026-09-03). Parked, matching the E-PROD-5 disposition.
- **Q33 (signal-indexer):** **now `ok`** — it was fixed (there's a `fix_signal_indexer_path.py` on host). Doc's "remove or fix" → fixed.
- **Q35 (deletions):** fleet went 184→163. At least 21 jobs removed or merged. The "never deleted anything" era is over.

### Section 4 — providers/cost
- **Q37-39 (litellm aliases):** `llm.paragu-ai.com/v1` now returns **401 auth error for all three aliases** (with and without the MINIMAX_API_KEY from .env — the proxy rejects the key: "Invalid proxy server token"). The litellm route is **fully dead**, consistent with the fleet's wholesale migration off litellm. Kill the aliases in docs; they're history.
- **Q42 (GLM):** unreachable via the dead proxy. GLM only lives as the direct zai provider (2 profile-registry jobs use `zai/glm-4.5-flash`, both ok).
- **Q44 (cost):** cost-tracker.json is **fresh again** (2026-10-12 today, 2 KB). cost-per-cron.json 2026-10-05. agent-traces.jsonl went stale **2026-09-25** (129 events) — tracing decayed after the fleet migration. Re-measure before trusting any daily number.
- **Q46-48 (token ledger/cap):** `/opt/data/state/token-ledger.json` **deleted** (fake-fire source gone). But `token-cap-daily` cron still exists (disabled, error state) and the scripts remain in 3 divergent copies (DUP-3). Either wire the ledger properly or delete the whole toolchain.

### Section 5 — state layer
- **Q53:** /opt/data/state exploded to ~80+ files. Notables: coord.json now **13.6 KB** (was 357 KB — compaction landed via coord-compact.py), agent-parent-spec-cache.json exists (partial Q11 mitigation), build-pipeline-dispatch.ndjson = **16 MB** and growing, auto-eval-log.jsonl + **11 rolling .bak files** (~21 MB total) — see CLEAN-1.
- **Q55:** still two different `state/` meanings (repo docs vs runtime). Still undocumented in README. Flagged.
- **Q57/Q61:** no `.pre-sqlite.bak` found; orphan coord.json.* files gone (compaction cleaned them).
- **Q52:** `aiw-state-auto-commit` (hourly) + `aiw-state-snapshot-6h` both enabled and ok; state-snapshots/ has the 2026-10-11 weekly snapshot. Working.

### Section 6 — host ↔ repo divergence
- **Q63:** host scripts vs stale clone: 52 host-only / 1 repo-only (global-hard-stop-enforcer.py — the deleted dead code, correctly absent from host, still in stale clone). Host vs fresh work-clone: 28 host-only / 35 work-only. **Divergence continues; no deployment contract exists yet** (DEMIURGE-136 still open).
- **Q65 (token-ledger/token-cap location):** now token-ledger.py exists on host AND in work-clone (different sizes: 5,295 vs 3,278 — **divergent copies**), token-cap.py in all 3 (1,945 / 1,945 / 5,163 — two versions). DUP-3.
- **Q67:** /opt/data/agents has **224 dirty entries** (124 modified, 99 untracked) — the live repo is heavily diverged from its own HEAD. This is the deployment-contract gap made visible.
- **Q70 (repos):** confirmed ~8 org repos; saskia-app, aiw-org, growth-coaching all real.
- **Q71:** agents-v2/aiw-org-clone is now a **40-day-stale third wheel**. Candidate for deletion after diffing (DUP-1).
- **Q72 (libsodium blob):** **gone** from all repo roots. Cleaned.

### Section 7 — secrets/security
- **Q75:** all 4 credential files now **chmod 600** ✅ (was world-readable). sudo still not installed (fine for single-admin VPS).
- **Q77/Q78:** pre-commit hook installed on `/opt/data/agents` and globally at `/opt/data/.git-hooks/` (core.hooksPath). Missing on both clones — low risk (clones are read-mostly) but install for consistency.
- **Q80/Q84-adjacent:** static grep found PAT *prefix patterns* in 5 scripts (audit-fresh.py, red-team-scenarios.py, cron-secret-sentinel.py, pii-redact.py + pycache) — these are detectors/scanners, not embedded secrets (they grep FOR tokens). Spot-checked class: legitimate. No live secret literals found in scripts/.
- **Q82:** vault.bitwarden.com → **HTTP 200**. BWS reachable.
- **Q73/Q74/Q76 (revocations):** still operator-only. The burned `github_pat_11AZQFZ...` from this week's chat leak belongs on that list — rotate.

### Section 8 — safety
- **Q85/Q136 (hard-stop enforcement):** **hermes-fixed is gone entirely** (replaced by hermes-agent-latest). No `hardstop_check`/`hard-stop-wrapper` references anywhere in the current runtime tree. The wrapper concept did not survive the runtime migration — **safety posture now rests on Hermes-native ToolGuardrails + prompt-level hard_stops text.** MAA-2's "declared but not enforced" is now structural: update THREAT-MODEL Addendum A accordingly.
- **Q87:** no scheduler.py to grep at the old path; the question needs re-asking against `/opt/data/hermes-agent-latest/`.
- **Q89:** decisions_for_ivan = **25** (was 424). Oldest 2026-09-21, all from cron-fleet-monitor. Saturation resolved; cadence now manageable.

### Section 9 — tests/CI
- **Q93:** pytest via `/opt/data/.venv/bin/python3` collects **772 tests** in the fresh clone (doc recorded 397 passed on 09-02 — suite nearly doubled). Full run not executed this pass (time-boxed); run before next merge per converge gate.
- **Q96/Q97:** **CI now exists** — `.github/workflows/ci.yml` (+qa_ci.yml, qa-gates.yml) in the live repo and clone. The "no automated gate has ever blocked a commit" claim is obsolete.

### Section 10-12 — operator-only
- Q102-122 (saskia-app model, people, governance): still operator questions; not measurable from host. Unchanged except: saskia-app now has 3 environment configs and its own registry entries (saskia-uptime-watch, saskia-prod-login-watch, saskia-backup-pull — the last one **erroring**, see BUG-2).

---

## 2. NEW bugs found this pass (not in the doc)

**BUG-1 — Path-migration breakage (3 jobs + 1 config):**
The `.hermes/cron/` → `cron/` move (and `.hermes/config.yaml` → `config.yaml`) left hardcoded paths behind:
- `aiw-config-sync` → ERROR: `canonical missing: /opt/data/.hermes/config.yaml` (canonical is now `/opt/data/config.yaml`)
- `aiw-cost-per-cron-daily` → ERROR: `jobs file not found: /opt/data/.hermes/cron/jobs.json` (now `/opt/data/cron/jobs.json`)
- `cron-sync` → ERROR: same missing-jobs.json path
- `aiw-dept-cost-dashboard-daily` → ERROR: traceback in build-dept-cost-dashboard.py (likely same class)
Fix: one sed pass over `/opt/data/scripts/` for the two old paths, or better: route through a `_paths.py`-style constant (this is exactly E-PORT/DEMIURGE-132-135, still unlearned).

**BUG-2 — saskia-backup-pull failing since at least today:**
`scp: /var/backups/saskia/rms-2026-10-12.sqlite.gz: No such file or directory` — the remote (Saskia VPS) backup file wasn't there at pull time. Either the upstream backup job failed or the filename/date drifted. **This is prod-client data protection — P1.** Check the Saskia VPS's local backup job.

**BUG-3 — seals-snapshot-daily erroring:**
`seals-snapshot-daily` exit 3: "include root missing: /opt/data/Projects" + "skipping over-cap file (774 MB)". Its include list references a nonexistent dir and something is dumping a 774 MB file into scope. Both need a one-line fix each.

**BUG-4 — build-pipeline-dispatch.ndjson at 16 MB and auto-eval-log rolling .baks at ~21 MB in /opt/data/state:** unbounded growth, no retention. Add to the nightly cleanup rotation.

---

## 3. DUPLICATIONS flagged (dedup targets)

**DUP-1 — Three clones of aiw-org on one host:**
| Clone | HEAD | State |
|---|---|---|
| `/opt/data/agents` | 555cc58 (10-07) | live runtime, 224 dirty entries |
| `/opt/data/aiw-org-work/aiw-org` | bc6faf5 (10-07) | fresh sibling-session clone |
| `/opt/data/agents-v2/aiw-org-clone` | 66b5485 (09-02) | **40 days stale** |
Dedup: diff stale clone vs live for anything unique (its 2 session scripts were re-added elsewhere), then **delete agents-v2/aiw-org-clone**. Keep exactly 2: live runtime + one work clone, with the work clone pulled before use.

**DUP-2 — Two cron registries with 39 duplicated names:**
`/opt/data/cron/jobs.json` (163) and `/opt/data/profiles/ivan/cron/jobs.json` (111) share 39 job names. Good news: **0 enabled in both** (no double-firing). But 36 names are disabled in BOTH registries = dead entries maintained twice. Dedup: delete the 36 dead duplicates from the profile registry (or main, whichever is canonical per name), and document which registry owns what (main = org fleet, profile = Ivan's personal + saskia/prod watchers).

**DUP-3 — token-ledger.py / token-cap.py in 3 divergent copies:**
host 5,295 B, work-clone 3,278 B, stale-clone 5,163 B — two different generations of the same script, all alive on disk, plus a disabled erroring cron (`aiw-token-cap-daily`). The ledger JSON itself was deleted. Dedup: pick one home (repo), delete the others, and either wire it or drop the cron.

**DUP-4 — Nonsense job name:** `aiw-devops-monitor-30min-monitor-30min` (monitor-of-monitor). Also `aiw-ai-safety-engineer-30min-monitor-30min` in the overlap set. These are monitors OF monitors with mangled suffix names — rename or retire.

**DUP-5 — ~35 audit/probe/temp scripts accumulated at /opt/data root** (probe1-3.py, _scan*.py, _q2.py, audit-*.py/md, cron-probe.py, mgmt/ops probes, 22 MB visual-audit zip, .spawn-ledger tmp). This is exactly the class the repo's own anti-pattern rules forbid ("relying on session leftovers"). Dedup: move keepers into `/opt/data/scripts/` (or repo), delete the rest. ~35 files + 22 MB.

**DUP-6 — Monitors-of-monitors pattern generally:** the tick-doctrine skills in Hermes reference `*-monitor-30min-monitor-30min` style jobs across the fleet. Each monitor that watches a monitor should have a named consumer and retirement criterion (per operating rule #15) — right now several are just stacked.

---

## 4. THINGS THAT DON'T MAKE SENSE (flagged for operator)

1. **THREAT-MODEL.md Addendum A still describes hermes-fixed + hard-stops-wrapper** — that runtime no longer exists. The doc's HIGH-risk MAA-2 finding is unanswerable in the current architecture. Rewrite Addendum A against `hermes-agent-latest`.
2. **REFERENCE.md converge gate requires `readme-counts.py --check`** but README counts (agents 47? 49? crons 156? 105?) have drifted again across 4 docs (README, OPERATIONS, ORG-AGENTS, REVIEW). One generated inventory (DEMIURGE-155, still open) would end this class of contradiction.
3. **litellm aliases (primary/fast/reasoning) still documented in token-plan and tooling docs** as live routing — the proxy 401s on everything. Docs must mark them historical.
4. **Port 8787 in ORCHESTRATION.md** — nothing listens there. Same doc-freshness class.
5. **cron-fleet-audit-report.md (2026-09-18) sits at /opt/data root** describing the OLD registry path and OLD totals (179/81) — superseded twice over. Archive into the repo or delete (DUP-5).
6. **`cost-per-cron.json` (2026-10-05) still being written by a job whose sibling dashboard already errors** on the old path. Half the cost toolchain is broken, half runs — pick: fix all 4 path-broken jobs (BUG-1) or retire the cost dashboard line entirely.
7. **Converge gate says "local verification ALWAYS precedes merge"** but the live runtime repo carries 124 modified + 99 untracked files vs HEAD — the live tree IS the divergence the gate exists to prevent. Root cause: no deployment contract (DEMIURGE-136, 6+ weeks open). This is the single highest-leverage open item in the whole doc set.

---

## 5. Best-practice scorecard (what's now aligned vs still off)

| Practice | Status now |
|---|---|
| Secrets out of chat, files 600 | ✅ done (this session's PAT burn notwithstanding — rotate it) |
| Truncation regression guard | ⚠️ partial (restore-verifier exists; lint still lacks min-length) |
| Registry single-source | ❌ two registries, 36 dupes (DUP-2) |
| Path constants / no hardcoded roots | ❌ BUG-1 proves the E-PORT epic never closed |
| Deployment contract host↔repo | ❌ open, 224 dirty files (item 7 above) |
| Generated inventory for counts | ❌ open (DEMIURGE-155) |
| Cron SLO/owner/retirement registry | ❌ not built; monitor-of-monitor names show why it's needed |
| Token/cost measurement | ⚠️ half-broken (BUG-1 + DUP-3) |
| CI gate | ✅ exists now (ci.yml + qa gates) |
| Decision queue hygiene | ✅ 424→25 |
| Prompt-body preservation | ✅ incident fixed + restore tooling |
| parent_spec 10k-token load | ❌ still every prompt; cache file appeared but not link-by-ID |

**Priority order for fixes (my recommendation):**
1. BUG-2 saskia-backup-pull (client prod backups — today)
2. BUG-1 path migration sed-pass (4 jobs, 30 min)
3. DUP-1 delete stale clone (after diff, 1 h)
4. BUG-3/BUG-4 + DUP-5 cleanup rotation (1 h)
5. DUP-2 registry dedup + ownership doc (2 h)
6. DEMIURGE-136 deployment contract (the big one, 1-2 days)
7. Rewrite THREAT-MODEL Addendum A for hermes-agent-latest (2 h)

---

*All numbers above re-measured 2026-10-12 from live probes; commands preserved in session log. Questions not listed = unchanged since the 09-02 doc or operator-only.*
