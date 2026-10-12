# AGENTS.md — AIW Org (aiw-org)

> **The single authoritative collaboration rulebook for all coding agents working in this org.**
> Applies to: Claude Code, Codex, Cursor, Gemini CLI, Windsurf, Kimi, OpenClaw, Hermes, and any other vendor.
> Vendor-specific files (`CLAUDE.md`, `AGENTS.md` per repo) are pointers to this doc.
> **Conflicts are resolved in favor of this file.**

---

## 🚦 Mandatory workflow — three steps before, three before done

**Before starting:**
1. Read `README*` → this file → `docs/HANDOFF.md` → `docs/adr/` → `git log -10 --oneline`
2. Run the [verification commands](docs/REFERENCE.md#verification)
3. Restate the task and acceptance criteria, confirm alignment with HANDOFF

**Before declaring done:**
1. Run the FULL verification command, confirm all green
2. Pass the [converge gate](docs/REFERENCE.md#converge-gate) — twice consecutively
3. Update `docs/HANDOFF.md` + commit with Conventional Commits (explain WHY)

**Stabilization window (DEMIURGE-157):** after infrastructure-affecting PRs merge, no new workstream for 24h.

---

## 🗂️ Repo structure (table of contents)

| Topic | File / location |
|---|---|
| **Workflow rules** (verification, converge gate, stabilization) | [`docs/REFERENCE.md`](docs/REFERENCE.md) |
| **Git discipline** (commits, branches, infra files) | [`docs/REFERENCE.md#git-discipline`](docs/REFERENCE.md#git-discipline) |
| **ADRs** (architectural decision records) | [`docs/adr/`](docs/adr/) |
| **Anti-patterns** + **Engineering principles** | [`docs/REFERENCE.md#anti-patterns`](docs/REFERENCE.md#anti-patterns) |
| **Handoff integrity** (ADR-0003, full-text not summarized) | [`docs/REFERENCE.md#handoff-integrity`](docs/REFERENCE.md#handoff-integrity) |
| **Safety red lines** (no secrets, no raw git push, etc.) | [`docs/REFERENCE.md#safety-red-lines`](docs/REFERENCE.md#safety-red-lines) |
| **Enterprise framework governance** | [`docs/enterprise-framework/GOVERNANCE.md`](docs/enterprise-framework/GOVERNANCE.md) |
| **Canonical schemas** | [`agents/schemas/`](agents/schemas/) |
| **Constitution** (deferred agents/roles) | [`constitution/`](constitution/) |
| **Org agents + prompts** | [`ORG-AGENTS.md`](ORG-AGENTS.md) + [`agents-prompts/`](agents-prompts/) |
| **Department index** | [`department-index.md`](department-index.md) |
| **Operations runbook** | [`OPERATIONS.md`](OPERATIONS.md) |
| **Orchestration spec** | [`ORCHESTRATION.md`](ORCHESTRATION.md) |

---

## ⏰ Cron domain discipline (Decision C1, 2026-09-25)

Two scheduler domains exist: **Domain A** = `/opt/data/cron/` (org-wide scripts fleet, default profile) and **Domain B** = `/opt/data/profiles/ivan/cron/` (ivan-profile jobs: LLM canaries, coaches, thesis ticks).

1. **R1 Ownership** — org-wide script jobs live ONLY in A; profile jobs ONLY in B. No job may be enabled in both.
2. **R2 Session-writes** — a profile session's `hermes cron` mutations land in B. To mutate A, prefix `HERMES_HOME=/opt/data`.
3. **R3 Do-not-revive** — never resume `*-monitor-30min` twins or any name in `state/cron-do-not-revive.json` (restoration zombies).
4. **R4 Preflight** — before ANY `cron resume/edit` on a shared name, run `python3 scripts/cron_domain_preflight.py <job> --action <action>`; exit 1 = STOP.
5. **R5 Canonical counts** — agent/cron numbers come from the `aiw-dashboard-refresh` job output, cited with its run date. Do not hand-maintain counts in docs.

Full rationale: [`docs/CRON-TOPOLOGY-CONSOLIDATION-2026-09-25.md`](docs/CRON-TOPOLOGY-CONSOLIDATION-2026-09-25.md).

---

## 🔥 The 3 hard rules (everywhere)

1. **No duplication.** If the same fact lives in two places, it will drift. Pick the canonical location and link from elsewhere. See `docs/REFERENCE.md#anti-patterns`.
2. **No vendor-private context.** Critical rules live in this repo, not in `.claude/`, `.cursor/`, `.codex/`, or chat.
3. **No claims without evidence.** "Done" requires fresh verification output in the same response, and a green test baseline.

---

## 🔗 Quick links

- Operations runbook: [`OPERATIONS.md`](OPERATIONS.md)
- Orchestration spec: [`ORCHESTRATION.md`](ORCHESTRATION.md)
- Org structure: [`ORG-AGENTS.md`](ORG-AGENTS.md)
- Department index: [`department-index.md`](department-index.md)
- ADRs: [`docs/adr/`](docs/adr/)
- Current state: `docs/HANDOFF.md`
- Reference (full rules): [`docs/REFERENCE.md`](docs/REFERENCE.md)
- BWS credential skill: `~/.hermes/skills/aiw-bws-credential-quirks/SKILL.md`

---

**Maintainer:** AIW org (Ivan Weiss Van Der Pol)
**Last updated:** 2026-09-23 (restructured to 70-line table-of-contents per professional docs standards)
