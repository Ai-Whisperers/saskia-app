# 2026-10-09 — Tier 2 Followups: Vale prose lint + tool evaluations

**Branch:** `tooling/tier2-followups-2026-10-09`
**Predecessors:** PR #95 (Tier 2 adoption), PR #96 (SHA-pinning + safeguard)
**Scope:** the remaining deferred items from `docs/operations/2026-10-09-tier2-adoption.md` "Tier 3 deferred" + followups #3-#5.

---

## TL;DR

| Item | Decision | Evidence |
|---|---|---|
| **Vale prose lint** | **ADOPTED** — `make docs-prose`, vendored styles, 0 findings after 7 typo fixes | 36k → 0 findings via rule curation; corpus runs in ~35s |
| **ast-grep** | **PARTIAL** — Python rules work; HTML rules can't replace `lint_tier1.py` | lint_tier1 finds 3 violations ast-grep misses (script blocks + attribute order) |
| **Semgrep CE** | **REJECTED** — ruff+bandit+ast-grep already cover the surface; Semgrep adds registry/network dependency + CI runtime | evaluation below |
| **umbra-scan** | **REJECTED** — no shadow APIs: single FastAPI app, no drift surface | app has one process + nginx; nothing to shadow |
| **factory_boy audit** | **RESOLVED: N/A** — factory_boy isn't a dep and has zero usage | `grep factory pyproject.toml uv.lock tests/` = empty |

---

## 1. Vale (ADOPTED)

**Was blocked on:** network (binary download). Now unblocked — `uvx --from=vale vale` works.

**What shipped:**
- `.vale.ini` — curated config. Philosophy: *only rules that catch objectively-wrong prose*. 
- `styles/` — vendored `Microsoft` + `write-good` packs (PROVENANCE.txt records source URLs; `scripts/vendor_vale_styles.sh` re-fetches).
- `scripts/docs_prose.sh` — deterministic file list via `find` (Vale's multi-`--glob` exclusion proved inconsistent: archive + PNG/tar.gz binary files leaked through with several glob flags combined).
- `make docs-prose` + added to `ci-extra`.

**The curation journey (why the config looks like it does):**
- Full Microsoft style: **8,470 findings** (Quotes 2708, We 2043, TooWordy 1037, Auto 640, UIVerbs 434...). Corporate style fights a bilingual ops-log repo.
- After disabling house-style conflicts: **520** (Adverbs 430 = stylistic noise).
- After disabling stylistic remnants: **45** real findings.
- Triage of the 45: DateFormat (10) + Percentages (12) were **quoted Spanish UI strings** ("26 sep 2026" is literally what the app displays — "fixing" them would falsify citations); BiasFree/Illusions were real typos.
- **7 real typo fixes** shipped: "the the" ×2, "in in", "sanity check" → "quick check" ×3, "hangs" → "stalls".
- Final: **0 findings, rc=0** on the whole corpus.

**Rule roster (kept):** BiasFree, Illusions, Cliches, Passive, TooManyNegatives, ThereIs + Microsoft hygiene rules not in conflict. Full disable-list documented inline in `.vale.ini` with finding counts.

---

## 2. ast-grep (PARTIAL — Python only)

**Hypothesis (from research):** replace `scripts/lint_tier1.py` (substring linter for template conventions).

**Test results:**
- HTML pattern rules **parse** Jinja templates fine (`<input $$$>` matches).
- But: regex/pattern rules **cannot see inside `<script>` blocks** — `ventas.html:1247` `confirm('¿...')` (a real lint_tier1 violation) is invisible to ast-grep.
- And: `<input type="date">` patterns miss when attributes are reordered (`<input id="x" type="date">`).
- Python rules **work correctly**: planted-violation test (`datetime.now() == $X`) matched; the real app is clean of that pitfall.

**Decision:** `lint_tier1.py` stays the template gate. `.ast-grep/rules.yml` ships with 3 structural Python rules (datetime equality, `int(Decimal)` via to_int_gs) as a manual tool with room to grow. Not a CI gate — zero enforcement value today.

---

## 3. Semgrep CE (REJECTED)

- Coverage overlap: ruff (lint+format), bandit (security), vulture (dead code), deptry (deps), pyright (types) already run per-PR.
- Semgrep's value is the registry — a **network dependency in CI** we just eliminated everywhere else (vendored Vale styles, uv.lock).
- CI runtime cost: ~2-4 min/job for meaningful rule sets; the tooling gate is currently 34s.
- Revisit trigger: a security incident class that bandit misses, or a compliance requirement naming Semgrep.

## 4. umbra-scan (REJECTED)

Shadow-API detection needs an API surface with drift between spec and implementation. Sazón is a single FastAPI process + nginx; OpenAPI is generated from the code itself (no independent spec to drift). **No drift surface exists.**

## 5. factory_boy audit (RESOLVED: N/A)

`factory_boy` is not in `pyproject.toml`, `uv.lock`, or imported anywhere in `tests/`. The research item was written against an assumed state. Nothing to audit.

---

## Makefile dedup (drive-by fix)

`make docs-prose` surfaced warnings: `jscpd`, `deadcode-code`, `docs-lint`, `docs-lint-strict`, `tool-matrix` were each defined **twice** (once pre-#94, once in #94's tooling wave). Make silently used the last definition. Deduplicated keeping the #94 (correct) versions — `make -n` on all targets now emits zero warnings.

---

## Files

- `.vale.ini` — Vale config (curated)
- `styles/` — Microsoft + write-good vendored + PROVENANCE.txt
- `scripts/vendor_vale_styles.sh` — re-vendor script
- `scripts/docs_prose.sh` — corpus runner (deterministic find-based list)
- `.ast-grep/rules.yml` — 3 structural Python rules (manual, not gated)
- `Makefile` — `docs-prose` target + `ci-extra` + dedup
- 7 doc typo fixes across docs/

## Verification

- `make docs-prose` → rc=0, 0 findings (35s)
- `make -n` on all touched targets → zero duplicate-definition warnings
- ast-grep scan on app/ → 0 findings
- Rule curation documented with finding counts in `.vale.ini` comments
