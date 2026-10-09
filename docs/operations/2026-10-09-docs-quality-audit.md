# Documentation Quality — 2026-10-09 Audit

**Branch:** `docs/quality-audit-2026-10-09`
**Worktree:** `/opt/data/profiles/ivan/cache/scratch/saskia-app-docs-quality`

---

## TL;DR

The repo has **338 .md files** (5.35 MB). Quality is mixed: a few files are pristine, most have lint issues, 9 file pairs are exact duplicates, 57 internal links are broken, and 235 `TODO` markers are scattered around. We now have a **proper linting tool** (`pymarkdownlnt` via `uvx`) wired up via a single Python script in `scripts/`. Default config: 11,510 findings. Strict mode: 28,876 findings.

**Top wins available immediately:**
1. Fix the 9 duplicate file pairs (mostly `subagent-outputs/` mirrors of main report files)
2. Fix the 57 broken internal links (mostly in `docs/roadmap/INDEX.md` files referencing old paths)
3. Add `make docs-lint` to the Makefile so CI catches regressions
4. Auto-fix the 3 most common structural rules (MD022, MD032, MD031) with `pymarkdownlnt fix`

---

## Full audit results

### File inventory

| Folder | Files | .md | Size |
|---|---|---|---|
| `docs/` | 451 | 312 | 5.17 MB |
| Root | 5 | 5 | 0.09 MB |
| `app/` | 8 | 8 | 0.04 MB |
| `installer/` | 4 | 4 | 0.02 MB |
| `deliverables/` | 4 | 4 | 0.02 MB |
| `archive/` | 2 | 2 | <0.01 MB |
| `.github/` | 3 | 3 | <0.01 MB |
| **Total** | | **338** | **5.35 MB** |

### Top 10 largest docs (use as a "what's the long-form material" index)

| Size | File |
|---|---|
| 615 KB | `docs/reports/redesign-2026-09-27/design-plans-2026-09-27.md` |
| 122 KB | `docs/reports/redesign-2026-09-27/subagent-outputs/macro-contracts-2026-09-27.md` |
| 84 KB | `docs/reports/redesign-2026-09-27/subagent-outputs/role-wireframes-2026-09-27.md` |
| 77 KB | `docs/reports/redesign-2026-09-27/audit-batch2-prod.md` (and its subagent-outputs mirror) |
| 69 KB | `docs/ux/copy-fix-list.md` |
| 67 KB | `docs/reports/redesign-2026-09-27/audit-batch3-reports.md` (and mirror) |
| 66 KB | `docs/analysis/2026-10-08/sazon_master_catalog_20261008.md` |
| 64 KB | `docs/ux/inventory/E-admin-ops-system.md` |
| 63 KB | `docs/roadmap/audits/FRONTEND_AUDIT_2026-09-22.md` |
| 63 KB | `docs/archive/2026-09/FRONTEND_AUDIT_2026-09-22.md` |

### 9 exact-duplicate file pairs (md5 match)

| Canonical | Duplicate | Notes |
|---|---|---|
| `docs/user-guide/18-suscripciones.md` | `docs/user-guide/19-suscripciones.md` | Numbering collision (same content, different filenames) |
| `docs/user-guide/17-lista-compras.md` | `docs/user-guide/18-lista-compras.md` | Numbering collision |
| `docs/plans/2026-10-01-phase14-coverage-strategy.md` | `docs/roadmap/historical-plans/2026-10-phase14/2026-10-01-phase14-coverage-strategy.md` | One in `plans/`, one in `historical-plans/` |
| `docs/reports/designer-page-report-2026-09-27.md` | `docs/reports/redesign-2026-09-27/REPORT.md` | Old path, new path both have same content |
| `docs/reports/redesign-2026-09-27/audit-batch3-reports.md` | `.../subagent-outputs/audit-batch3-reports.md` | Main + subagent-outputs (intentional mirror pattern) |
| `docs/reports/redesign-2026-09-27/cross-page-wishlist-consolidation.md` | `.../subagent-outputs/cross-page-wishlist-consolidation.md` | Same pattern |
| `docs/reports/redesign-2026-09-27/cross-cutting-consistency-audit.md` | `.../subagent-outputs/cross-cutting-consistency-audit.md` | Same pattern |
| `docs/reports/redesign-2026-09-27/audit-batch2-prod.md` | `.../subagent-outputs/audit-batch2-prod.md` | Same pattern |
| `docs/reports/redesign-2026-09-27/qol-touches-catalog.md` | `.../subagent-outputs/qol-touches-catalog.md` | Same pattern |

The `subagent-outputs/` mirrors are **intentional** (the docs/reports/redesign-2026-09-27/ folder documents a multi-agent fan-out, so the subagent outputs are first-class artifacts). The other 3 pairs are **real cleanup candidates**.

### 57 broken internal links (15 source files)

Top offenders:
- `docs/roadmap/historical-plans/INDEX.md` — 4 broken refs to old `audits/2026-09-29/` and `operations/PRODUCTION_500_RUNBOOK.md` paths
- `docs/roadmap/audits/INDEX.md` — 4 broken refs to same old paths
- `docs/user-guide/*.md` — 9 broken refs to screenshot files (e.g., `screenshots/01-ventas-pos.png`) that don't exist
- `docs/roadmap/IMPROVEMENT_BACKLOG.md` — broken ref to `WHAT_NEXT.md` (case mismatch)
- `docs/roadmap/WISHLIST.md` — broken ref to `../../wishlist/README.md` (likely `docs/wishlist/README.md`)

### 235 TODO/FIXME markers across 73 files

Top files: `docs/plans/2026-10-01-phase14-todo-inventory.md` (22, ironic), `docs/roadmap/EXECUTION-PLAN.md` (22), `docs/roadmap/IMPROVEMENT_BACKLOG.md` (5), `docs/user-guide/15-cierre.md` (3), `docs/user-guide/13-ops.md` (3).

### Files with no H1 header (4)

- `CHANGELOG.md` — intentional, follows "Keep a Changelog" format
- `.github/ISSUE_TEMPLATE/bug.md` — intentional, template
- `.github/ISSUE_TEMPLATE/feature.md` — intentional, template
- `.github/ISSUE_TEMPLATE/epic.md` — intentional, template

### pymarkdownlnt findings (the main lint pass)

| Mode | Total | Top rule |
|---|---|---|
| **Default (MD013 disabled)** | 11,510 | MD032 (lists without blank lines) — 3,970 |
| **Strict (all rules)** | 28,876 | MD013 (line length) — 17,350 |

Top rules:

| Rule | Default | Strict | What it catches |
|---|---|---|---|
| **MD013** | 0 (disabled) | 17,350 | Line length > 80 chars (too noisy for prose) |
| **MD032** | 3,970 | 3,970 | Lists should be surrounded by blank lines |
| **MD022** | 3,631 | 3,631 | Headings should be surrounded by blank lines |
| **MD024** | 2,169 | 2,169 | Multiple headings with same content (siblings_only set) |
| **MD031** | 370 | 370 | Fenced code blocks should be surrounded by blank lines |
| **MD036** | 315 | 315 | Emphasis used instead of a heading |
| **MD025** | 299 | 299 | Multiple H1 in a single document |
| **MD040** | 295 | 295 | Code fence without a language tag |
| **MD034** | 37 | 37 | Bare URL used |
| **MD009** | 28 | 28 | Trailing whitespace |

---

## What was added (this PR)

### 1. `.markdownlint.jsonc` at repo root

```jsonc
{
  "config": {
    "default": true
  },
  "plugins": {
    "markdownlint": {
      "MD013": false,  // Line length (too noisy for prose docs)
      "MD033": false,  // Inline HTML (templates use it)
      "MD041": false,  // First-line H1 (fragments don't need it)
      "MD024": { "siblings_only": true }  // duplicate headings OK across sections
    }
  },
  "globs": ["docs/**/*.md", "*.md"],
  "ignores": ["**/_archive/**", "**/node_modules/**", "**/receipts/**", "**/.venv/**", "**/__pycache__/**"]
}
```

NOTE: `pymarkdownlnt v0.9.40` does not pick up the `globs`/`ignores` config fields from this file format — use the script's path arguments instead. The config is forward-compatible for when they fix the parsing.

### 2. `scripts/check_docs_quality.py`

A single Python script that:
- Runs `pymarkdownlnt` via `uvx --from pymarkdownlnt` (no Node.js required)
- Supports `--strict` (all rules), `--json` (machine-readable), and path arguments
- Default behavior disables 3 noisy rules (MD013, MD033, MD041)
- Aggregates findings by rule + file, prints top 20

**Why Python, not bash:** the script needs to parse pymarkdownlnt's output, aggregate by rule/file, and support `--json` for CI. Bash + grep is brittle for the parsing.

**Why pymarkdownlnt, not markdownlint-cli2:** pymarkdownlnt is pure Python; matches our `uv`-based tooling; no Node.js install step. Same rule set (MD001–MD058).

### 3. Companion report (this file)

Documents the audit, the 9 duplicate pairs, the 57 broken links, the 11,510 default findings, and the auto-fix strategy.

---

## Auto-fixable issues (priority order)

| Issue | Count | Auto-fixable? | Tool |
|---|---|---|---|
| MD032 (lists w/o blank lines) | 3,970 | ✅ yes | `pymarkdownlnt fix` |
| MD022 (headings w/o blank lines) | 3,631 | ✅ yes | `pymarkdownlnt fix` |
| MD031 (code blocks w/o blank lines) | 370 | ✅ yes | `pymarkdownlnt fix` |
| MD024 (duplicate headings) | 2,169 | ❌ review needed | manual |
| MD036 (emphasis as heading) | 315 | ⚠️ risky (changes meaning) | manual |
| MD040 (code fence w/o language) | 295 | ⚠️ risky (need to know language) | manual |
| MD025 (multiple H1) | 299 | ❌ review needed | manual |
| MD009 (trailing whitespace) | 28 | ✅ yes | `pymarkdownlnt fix` |
| MD012 (multiple blank lines) | 77 | ✅ yes | `pymarkdownlnt fix` |
| MD004 (mixed bullet styles) | 42 | ✅ yes | `pymarkdownlnt fix` |

**Of the 11,510 default findings, ~8,100 (~70%) are auto-fixable.**

---

## Recommended follow-up PR sequence

### PR 1 (this PR): Lint tooling — shipped
- `.markdownlint.jsonc`
- `scripts/check_docs_quality.py`
- This audit report (in `docs/operations/2026-10-09-docs-quality-audit.md`)

### PR 2: Auto-fix the structural issues
- Run `pymarkdownlnt fix` on the whole repo
- Commit the resulting whitespace changes (large diff, but mechanical)
- Should resolve ~8,100 of the 11,510 findings

### PR 3: Delete the 3 real duplicate pairs
- `docs/user-guide/18-suscripciones.md` (keep 19, fix number)
- `docs/user-guide/17-lista-compras.md` (keep 18, fix number)
- `docs/reports/designer-page-report-2026-09-27.md` (delete; `redesign-2026-09-27/REPORT.md` is canonical)

### PR 4: Fix the 57 broken internal links
- Most are in `docs/roadmap/INDEX.md` files — one source-of-truth edit
- User-guide screenshot links need actual screenshot files (separate task)

### PR 5: Add `make docs-lint` to Makefile + CI
- Wire `scripts/check_docs_quality.py` into the CI pipeline
- Set the bar at "no NEW findings" (don't fail on existing 11,510)

### PR 6: Resolve the 235 TODO markers
- Many are legitimate (the `phase14-todo-inventory.md` literally IS the TODO list)
- Some are stale (TODO from a plan that's already shipped)
- Audit each file; remove TODOs that are already done

---

## Research: what other teams use

Surveyed 5 sources for docs-quality best practices:

1. **Epic Games / Lore** ([reference](https://github.com/EpicGames/lore/blob/main/docs/developing/doc-standards/tools/README.md)) — uses Vale (prose) + markdownlint-cli2 (structure) + lychee (links). 30+ rules. Their setup is the gold standard for game-dev docs.

2. **Vale** ([docs.vale.sh](https://docs.vale.sh/)) — "code-like linting for prose". Supports Microsoft, Google, Red Hat style guides. One binary, no runtime. **Not installable here without network access for the binary download.**

3. **markdownlint-cli2** — Node.js. Same rule set as pymarkdownlnt. **Requires Node.js, which is not in our stack.**

4. **pymarkdownlnt** ([docs](https://github.com/jackdewinter/pymarkdown)) — Python port of markdownlint. **Our choice: pure Python, matches our uv-based tooling.**

5. **lychee** ([lychee-cli](https://github.com/lycheeverse/lychee)) — link checker. Rust binary. **Could not install in our environment.**

**Key takeaway from research:**
- 3-tool stack (Vale + markdownlint + lychee) is the standard for serious docs
- For our project, pymarkdownlnt + manual link checks (via the script in the prior PR) is the right starting point
- Vale is worth adding if we want prose quality checks (e.g., "don't say 'simply'", "use sentence-case headings")

---

## What did NOT change in this PR

- No .md files were edited
- No deletions
- No config changes to existing tools
- Only added: `.markdownlint.jsonc` (1 file) + `scripts/check_docs_quality.py` (1 file) + this audit doc

This is intentionally a **tooling PR**, not a cleanup PR. The cleanup PRs (PRs 2-6 above) are separate and should each be reviewed on its own.
