# Reference — Full Rules (extracted from AGENTS.md)

> **Purpose**: Houses the detailed rules moved out of root `AGENTS.md` per progressive-disclosure documentation standard. AGENTS.md is the table-of-contents; this file is the detail.

**Last updated**: 2026-09-23 (extracted from AGENTS.md)

---

## 📋 Verification commands (canonical baseline)

For Python projects in this org (most agents and scripts):
```bash
cd /opt/data/agents && bash tests/run-all.sh
```

Expected output:
- `=== Lint PROMPTs ===` (passes)
- `=== Validate state ===` (passes)
- `=== Run unit tests ===` (e.g. `210 passed`)
- `Total failures: 0`

For Python module changes specifically:
```bash
cd /opt/data/agents && /opt/data/.venv/bin/python3 -m pytest tests/<changed_module>.py -v
```

For Hermes skill/plugin changes:
```bash
/opt/hermes/bin/hermes skills list        # confirm enabled
/opt/hermes/bin/hermes plugins list       # confirm enabled
```

For enterprise-framework catalogue conformance (AIW-10):
```bash
python3 scripts/validate-enterprise-framework.py --root . --format text
python3 -m pytest tests/test_enterprise_framework_conformance.py -v
```

CI gate for `validate-enterprise-framework.py` is **not** wired into `.github/workflows/ci.yml` until the repository baseline (`pytest tests/ -m 'not slow'`) is green on `main`/`master`.

**If the verification command changes, update this section in the same commit.**

---

## ✅ Converge gate

A ticket/PR is `done` only when ALL of the following pass at HEAD, **after the last commit**, **twice consecutively**:

- full pytest suite (`-m 'not slow'`) — 0 failures
- `scripts/readme-counts.py --check` — exit 0
- `scripts/lint-prompts.py` — 0 issues
- `scripts/restore-prompt-bodies.py --verify` — 0 SHORT

**Rationale**: Spec-Kit converge pattern (repeat implement↔verify until stable); single passing runs hide nondeterminism. Local verification ALWAYS precedes any merge — GitHub Actions is confirmation, not the first line of defense.

---

## 🏗️ Architecture Decision Records (ADR)

- **Any "why this change" decision** for architecture / approach / schema changes goes in `docs/adr/`.
- Format: see `docs/adr/0000-template.md`.
- **Decisions only in chat = decisions that didn't happen.** Write them down.

---

## 🏛️ Enterprise framework governance

Framework models, terminology, and review gates follow [`docs/enterprise-framework/GOVERNANCE.md`](enterprise-framework/GOVERNANCE.md). Canonical gate index: [`docs/enterprise-framework/APPROVALS.md`](enterprise-framework/APPROVALS.md).

**Before changing core entities:**
1. **Terminology-first** — add or update terms in `docs/terminology/TERMS.md` before schemas, prompts, or tickets.
2. **ADR for breaking changes** — entity, relationship, or enumeration changes that break consumers require an ADR in `docs/adr/`.
3. **Migration notes** — when an approved schema version changes, document what consumers must update.
4. **Human authority** — changes to approvers or sign-off rules need a dated review gate, not a silent edit.

**Forbidden:** Calling a model `locked`, `complete`, or `approved` while its gate in APPROVALS.md is still `proposed`. AI-generated approval summaries are not evidence of human sign-off.

---

## 📦 Git discipline

- **Forbidden: `git add -A`** — use `git add -u` or per-file `git add <path>`. New files must be explicitly added.
- Before commit, `git diff --stat` to verify no surprise changes to `Dockerfile`, `nginx.conf`, `docker-compose.yml`, etc. Infrastructure files in separate commits.
- Small commits. One commit = one change. One task = one branch.
- Branch names: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`. No special chars.

---

## 🚫 Anti-patterns (forbidden)

- ❌ Putting critical context in vendor-private directories (`.claude/`, `.cursor/`, `.codex/`)
- ❌ Relying on conversation summaries / context compression to pass state between sessions
- ❌ Stacking new features on a red test baseline
- ❌ Tackling tasks larger than "can be explained in half a day" before handoff
- ❌ Claiming "Done!" or "All tests pass" without FRESH verification evidence in the same response
- ❌ Trusting agent success reports without independent VCS diff verification
- ❌ Leaving uncommitted work at session end

**The "no duplication" rule**: If a fact appears in two locations, it WILL drift. Pick the canonical location and link from everywhere else. The `agents/schemas/` folder is canonical; `schemas/` was deleted. `constitution/` is canonical for org docs; root-level duplicates deleted.

---

## 🧱 Engineering principles

- **Don't preserve backward compat:** delete obsolete paths, don't add compat shims, fallbacks, or migration code.
- **Choose the simplest implementation that fully meets current needs.** Avoid speculative abstractions, config, and indirection layers.
- **Layered evolution:** start with a working end-to-end minimum, then layer new capabilities on top. Never replace a working product with half-finished complexity.
- **Modular components, clear separation of concerns.**
- **Prefer mature, well-maintained libraries** (when they reduce overall complexity or improve reliability). Don't reinvent common functionality without a reason.
- **Use existing project dependencies first.** Don't assume a library lacks a capability — check docs and types first.
- **Architecture decisions are long-term.** No "works now, definitely replace later" temporary solutions.
- **Conflict resolution:** architectural boundaries follow long-term design; implementation within boundaries follows current simplest.

---

## 🤝 Handoff boundary integrity (ADR-0003)

**Every handoff between agents MUST:**
- Include an explicit `Audience:` header listing who can read it
- Include an explicit `Visibility:` scope (`internal` | `dept-scoped:<id>` | `agent-scoped:<id>` | `public`)
- Be full-text — **NEVER auto-summarize** handoff artifacts. Compressed handoffs lose boundary metadata at 73% leakage rate (per arXiv 2026).
- Go through `pre_dispatch_check` validation before writing

**Rationale:** "Facts Without Rules: Boundary Metadata Collapse in Multi-Agent LLM Handoffs" (arXiv 2026) measured 73% privacy leakage when handoffs are compressed to ≤25 words. AIW's full-text markdown outbox preserves boundaries; this rule prevents future contributors from accidentally introducing compression. See [`docs/adr/0003-handoff-boundary-integrity.md`](adr/0003-handoff-boundary-integrity.md).

---

## 🚨 Safety red lines

- **NEVER commit secrets, credentials, IDs, or customer PII.** If you find existing secrets in a repo, **report and stop — do not silently fix.**
- **NEVER push to a remote without explicit authorization** (this org uses `github-push-from-bws` wrapper; raw `git push` blocked by safety hook).
- **NEVER print token-shaped strings to chat** (token-leak failure mode). If a token appears in chat, treat as compromised, rotate in BWS.
- **NEVER modify `state/coord.json` directly** — go through the AIW agent that owns that signal.
- **NEVER add a new cron job without an entry in `/opt/data/agents/ORCHESTRATION.md`** explaining its purpose and SLA.

---

## 📜 Provenance

This document was extracted from the root `AGENTS.md` on 2026-09-23 as part of the professional-docs restructure. The original full document was adapted from `iPythoning/b2b-sdr-agent-template/AGENTS.md` (the closest peer-project AGENTS.md we found) and merged with AIW-specific safety red lines and verification commands. See:
- `/opt/data/profiles/ivan/plans/2026-09-01-aiw-research-round-3-communities.md`
- `/opt/data/profiles/ivan/plans/2026-09-01-aiw-research-round-4-upgrades-templates.md`
