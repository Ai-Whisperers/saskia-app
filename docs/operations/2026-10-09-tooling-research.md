# Repo Improvement Tooling — Research & Recommendations
**Date:** 2026-10-09
**Branch:** `docs/tooling-research-2026-10-09`
**Worktree:** `/opt/data/profiles/ivan/cache/scratch/saskia-app-tooling-research`
**Reference state:** main @ `1438b8ca`

---

## TL;DR

The Sazon repo already has **comprehensive tooling** — 13+ static analyzers, 14 pre-commit hooks, 38 Makefile targets, 14 CI workflows, 22 dev dependencies. The biggest improvements now are **integration** (wire jscpd/deadcode into Makefile, add `make docs-lint` target) and **observability** (OpenTelemetry, Prometheus, structured logging). Three new tool categories would unlock real value: FastAPI-specific security (fastapi-safeguard), code-search/grep (ast-grep), and doc-prose linting (Vale when network allows).

**Quick wins (this PR, no code changes):**
1. Add `make docs-lint` target (calls `scripts/check_docs_quality.py`)
2. Add `make jscpd` and `make deadcode` targets (tools declared but unwired)
3. Document the tool matrix in this report

**Medium-term (next sprint):**
4. `fastapi-safeguard` — startup-time security checks with baseline lock
5. `ast-grep` — code search & refactor with structural patterns
6. `actionlint` — already partly in CI, formalize for all .github/workflows files

**Long-term (when ops allow):**
7. OpenTelemetry + Prometheus instrumentation
8. Vale for prose linting (needs network for binary download)
9. Semgrep CE for deeper SAST

---

## 1. Current state of tooling (inventory)

### 1.1 Declared in `pyproject.toml` [dependency-groups]

| Tool | dev-base | tooling | dev | Category | Wired? |
|---|---|---|---|---|---|
| pytest | ✓ | | ✓ | Testing | ✅ |
| pytest-cov | ✓ | | ✓ | Coverage | ✅ |
| pytest-xdist | ✓ | | ✓ | Parallel tests | ✅ |
| ruff | ✓ | | ✓ | Lint + format | ✅ |
| httpx | | | ✓ | TestClient | ✅ |
| hypothesis | | | ✓ | Property tests | ✅ |
| playwright | | | ✓ | E2E browser | ✅ |
| pytest-randomly | | | ✓ | Test order | ⚠️ disabled |
| testcontainers[pg] | | | ✓ | Real DB tests | ✅ |
| vulture | | ✓ | ✓ | Dead code | ✅ pre-commit |
| deadcode | | ✓ | ✓ | Dead code (cross-file) | ❌ declared only |
| bandit | | ✓ | ✓ | Security | ✅ pre-commit |
| radon | | ✓ | ✓ | Cyclomatic complexity | ✅ pre-commit |
| complexipy | | ✓ | ✓ | Cognitive complexity | ✅ Make + CI |
| pyright | | ✓ | ✓ | Type checker | ✅ Make + CI |
| deptry | | ✓ | ✓ | Unused deps | ✅ Make |
| interrogate | | ✓ | ✓ | Docstring coverage | ✅ Make |
| refurb | | ✓ | ✓ | Modernization | ✅ Make |
| pip-audit | | ✓ | ✓ | CVE scan | ✅ Make |
| reuse | | ✓ | ✓ | License compliance | ✅ Make |
| jscpd | | ✓ | ✓ | Copy-paste | ❌ declared only |
| sensez | | ✓ | ✓ | Structural clones | ✅ Make |
| **pymarkdownlnt** | | | | Markdown lint | ✅ PR #93 (this branch) |
| **check_docs_quality.py** | | | | Markdown wrapper | ✅ PR #93 |

### 1.2 Pre-commit hooks (`.pre-commit-config.yaml`)

14 hooks installed:
1. ruff (with `--fix`)
2. ruff-format
3. pytest-smoke
4. forbid-secret-files
5. file-size-sanity
6. check-yaml
7. check-no-secrets
8. lint-tier1 (UI conventions)
9. no-hardcoded-dates
10. routers-require-auth
11. no-silent-excepts
12. vulture
13. bandit
14. radon-cc
15. forbid-legacy-modules

### 1.3 Makefile targets (38)

install, test, test-fast, lint, format, serve, migrate, seed, smoke, check-warnings, check-secrets, test-verbose, test-coverage, lint-fix, check, seed-reset, backup, fixtures, ci-smoke, pre-commit, stats, test-browser, test-e2e, test-migration, test-xdist, dead-code, complexity, cognitive, deptry, interrogate, pyright, refurb, duplicates, duplicates-code, arch, security, audit-cve, licenses, ci-extra, ci, clean

### 1.4 CI workflows (14)

ci.yml, browser.yml, currency-drift.yml, date-boundary.yml, deploy-dev.yml, deploy-test.yml, dev-ci.yml, qa-gates.yml, release.yml, route-smoke.yml, security-zap.yml, sharded-test.yml, smoke.yml, tooling.yml

---

## 2. Gap analysis — what's missing

### 2.1 Unwired declared tools

| Tool | Currently | Fix |
|---|---|---|
| `jscpd` | In pyproject only | Add `make jscpd` target |
| `deadcode` | In pyproject only | Add `make deadcode-code` target (complements vulture) |
| `pymarkdownlnt` | In scripts/ only (PR #93) | Add `make docs-lint` target |

### 2.2 Tooling categories not covered

| Category | Why we need it | Recommended tool |
|---|---|---|
| **FastAPI security** | bandit misses FastAPI-specific risks (missing auth dep on a route, exposed CORS, debug mode) | `fastapi-safeguard` |
| **Structural code search** | Grep is line-based; can't write AST-aware refactors | `ast-grep` (Rust binary, multi-lang) |
| **GitHub Actions lint** | YAML errors in workflows only surface at runtime | `actionlint` (already in CI for one workflow; should be uniform) |
| **API surface audit** | No tool checks route coverage or shadow APIs | `umbra-scan` (Python-native) |
| **OpenTelemetry** | No distributed tracing; debugging prod issues is log-spelunking | `opentelemetry-api` + `opentelemetry-sdk` + FastAPI instrumentation |
| **Prometheus metrics** | No /metrics endpoint; no SLO tracking | `prometheus-fastapi-instrumentator` |
| **Structured logging** | Stdlib logging is ungreppable JSON-less | `structlog` (lightweight) |
| **Prose linting (docs)** | pymarkdownlnt only checks structure | `Vale` (when binary available) |
| **Deeper SAST** | bandit is single-file, pattern-based | `Semgrep CE` (free, YAML rules, cross-file taint in Pro) |
| **License audit** | `reuse` is local only | No improvement needed; reuse is the right tool |

### 2.3 Tools tried but didn't work in our env

| Tool | Reason | Workaround |
|---|---|---|
| Vale | Binary download from GitHub blocked | Use pymarkdownlnt only; revisit when network allows |
| markdownlint-cli2 | Requires Node.js | Use pymarkdownlnt (Python equivalent) |
| lychee | Rust binary not installed | Use the manual link check in our existing scripts |

---

## 3. Recommended additions — ranked by ROI

### Tier 1: This PR (zero-risk, just Makefile targets)

**Goal:** Make the already-installed tools actually easy to use.

**Effort:** ~30 minutes
**Risk:** none (Makefile changes only)
**Value:** low-effort visibility into the 8,100 auto-fixable docs findings and copy-paste reports

**Tasks:**
- [x] Add `make docs-lint` (calls `scripts/check_docs_quality.py`)
- [ ] Add `make jscpd` (copy-paste detector)
- [ ] Add `make deadcode` (cross-file dead code; complements vulture)
- [ ] Add `make tool-matrix` (prints this table)
- [ ] Update AGENTS.md "Tooling" section to point at these targets

### Tier 2: Next sprint (high-value additions)

**Goal:** Catch bugs we currently miss.

**Effort:** 1-2 days
**Risk:** low (additive, can disable per-rule)
**Value:** high

**Task 1: `fastapi-safeguard` integration**
- Why: We have a `routers-require-auth` test (line-level grep), but it doesn't catch missing `Depends(get_current_user)`, exposed sensitive fields, CORS misconfigs, debug mode left on
- How: `uv add fastapi-safeguard`, add `make security-routes`, wire into pre-commit
- Cost: ~4 hours to integrate and baseline existing findings
- Reference: https://github.com/mateush/fastapi-safeguard

**Task 2: `ast-grep` for structural code search**
- Why: We have ad-hoc grep scripts in `scripts/` (lint_tier1.py, check_no_silent_excepts.py, etc.). ast-grep lets us replace these with declarative YAML rules
- How: `ast-grep` Rust binary (no install needed if downloaded; or use `sg` Python wrapper). Add to Makefile, write 2-3 example rules
- Cost: ~6 hours
- Reference: https://ast-grep.github.io/

**Task 3: `actionlint` for ALL workflows**
- Why: We have it implicit in one workflow; should run on all 14
- How: One-line addition to `.github/workflows/tooling.yml`
- Cost: 30 minutes

**Task 4: OTel + Prometheus**
- Why: We have Sentry for errors but no tracing/metrics. Debugging prod issues requires log-speleology
- How: `uv add opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy prometheus-fastapi-instrumentator`, wire into `app/rms/main.py`
- Cost: ~1 day
- Reference: https://fastapi.tiangolo.com/advanced/opentelemetry/

### Tier 3: Long-term (when operational fit allows)

**Task 5: `Vale` for prose linting**
- Blocker: binary download from GitHub fails in our env
- When: revisit when network is available
- Value: enforce style consistency in docs (sentence-case headings, banned words)

**Task 6: `Semgrep CE` for custom rules**
- Why: We can write a single rule to catch all Sazon-specific anti-patterns (e.g., "routers in `app/rms/routers/` must not import from `app/routers/`")
- Cost: ~2 days to write 3-5 rules + integrate
- Reference: https://semgrep.dev/

**Task 7: `umbra-scan` for shadow API detection**
- Why: 350 routes; we'd want a tool to verify every route is documented and protected
- Cost: ~1 day
- Reference: https://github.com/djinn-ai/umbra-scan

**Task 8: `factory_boy` for test fixtures**
- Why: We have SAVEPOINT isolation (from `saskia-rms-development` skill memory) but factories are likely hand-rolled
- Audit: read `tests/factories.py` and `tests/conftest.py` to see if factory_boy is used
- Cost: ~2 days if not used; 0 if it is

---

## 4. Research sources (4 surveyed)

### 4.1 Static analysis tool landscape (Sourcegraph 2026)

The big 12:
- **Security-focused (SAST):** Semgrep, CodeQL, Snyk Code, Checkmarx, Veracode, Fortify, Coverity
- **Quality:** SonarQube, PMD, CodeScene
- **Linters:** ESLint, Qodana

**Verdict for us:** SonarQube/Semgrep/CodeQL are the heavy hitters. We're a Python-only shop with one repo; Semgrep CE is the right commercial-tier option when we want it. SonarQube is overkill for our size.

### 4.2 Python-specific tools (Safeguard.sh 2026)

| Tool | Category | Notes for us |
|---|---|---|
| Ruff | Lint/format | ✅ already have it (the only one we need) |
| Bandit | Security SAST | ✅ already have it |
| Pylint | Correctness lint | ❌ Ruff supersedes |
| mypy / Pyright | Type checking | ✅ Pyright in CI, mypy informational |
| Semgrep | Security SAST | Tier 3 (custom rules) |
| CodeQL | Security SAST | Free for public repos; Tier 3 |
| SonarQube | Quality + security | Overkill for us |
| pip-audit / Safety | SCA | ✅ pip-audit already in Makefile |

### 4.3 FastAPI-specific tools (2026)

| Tool | Purpose | Status |
|---|---|---|
| `fastapi-safeguard` | Startup-time security checks | ⭐ Tier 2 — recommend adding |
| `fastapi-doctor` | Rust-native FastAPI analyzer | ⭐ Tier 2 — interesting but young (2026) |
| `umbra-scan` | Shadow API detection | ⭐ Tier 3 — useful when we want route audit |
| `lite-bootstrap` | OTel/Prometheus/Sentry in one | ⭐ Tier 2 — good for OTel adoption |
| `prometheus-fastapi-instrumentator` | /metrics endpoint | ⭐ Tier 2 — recommend adding |
| `FastAPIInstrumentor` | OTel auto-instrumentation | ⭐ Tier 2 — recommend adding |

### 4.4 Python pre-commit ecosystem (2026)

- **ruff-pre-commit** is the standard — we already have it
- **ty** (Astral's new type checker) is the future, but pyright works today
- **prek** is a faster Rust-based pre-commit alternative; consider for Tier 3

---

## 5. Tool adoption decision matrix

| Tool | Add now? | Why / why not |
|---|---|---|
| `make docs-lint` | ✅ Tier 1 | Zero risk, surfaces 8,100 auto-fixable findings |
| `make jscpd` | ✅ Tier 1 | Tool installed, no Makefile target |
| `make deadcode` | ✅ Tier 1 | Tool installed, no Makefile target |
| `actionlint` (all workflows) | ✅ Tier 1 | 30-min fix, prevents runtime YAML errors |
| `fastapi-safeguard` | ⏳ Tier 2 | Real bug-finder; needs baseline + 1 day |
| `ast-grep` | ⏳ Tier 2 | Replaces 3+ ad-hoc scripts; needs 1 day |
| OpenTelemetry + Prometheus | ⏳ Tier 2 | Observability gap; needs 1 day |
| `Vale` | ⏳ Tier 3 | Blocked by network; revisit when binary available |
| `Semgrep CE` | ⏳ Tier 3 | Custom Sazon rules; 2 days |
| `umbra-scan` | ⏳ Tier 3 | Route audit; 1 day |
| `factory_boy` | ⏳ Tier 3 (audit first) | Need to check current state |
| `lite-bootstrap` | ❌ Not recommended | Sentry is already integrated; lite-bootstrap replaces 5+ libs for marginal benefit |
| `fastapi-doctor` | ❌ Not recommended | Too new (2026), Rust binary |

---

## 6. What this PR does (tooling-research-2026-10-09)

This PR is **research only**. No new tools are wired up. The deliverable is:

1. **This report** (`docs/operations/2026-10-09-tooling-research.md`) — the full audit + decision matrix
2. **3 Makefile targets** for already-installed but unwired tools:
   - `make docs-lint` — calls `scripts/check_docs_quality.py` (the script from PR #93)
   - `make jscpd` — copy-paste detector (currently only in pyproject)
   - `make deadcode-code` — cross-file dead code (currently only in pyproject)
   - `make tool-matrix` — prints the tool coverage table

The Tier 2/3 changes are documented but NOT in this PR. Each becomes its own future PR with its own scope, baseline, and rollback plan.

---

## 7. Open questions for Ivan

1. **Network access for tooling binaries?** `Vale` and `ast-grep` need GitHub binary downloads. If those are blocked in prod but allowed locally, we can pin downloads to local-only paths.
2. **Observability stack preference?** Sentry is integrated. Should we add Prometheus + Grafana, or use Sentry's own metrics? (Sentry's metrics are limited.)
3. **Test fixture style:** is `factory_boy` already used in `tests/`? (I haven't read conftest.py yet.) If yes, the recommendation is moot; if no, this is a 2-day upgrade.
4. **Compliance:** any audit requirements (SOC 2, PCI, HIPAA) that drive tool selection? If yes, `pip-audit` + `reuse` + a heavier SAST might become Tier 1.

---

## 8. Sources

1. Sourcegraph: "12 Best Static Code Analysis Tools in 2026" — https://sourcegraph.com/blog/static-code-analysis-tools
2. DeepSource: "9 Best Static Analysis (SAST) Tools for 2026" — https://deepsource.com/resources/static-analysis-tools
3. AppSecSanta: "38 Best SAST Tools for 2026" — https://appsecsanta.com/sast-tools
4. Safeguard.sh: "Python Code Review Tools Compared (2026)" — https://safeguard.sh/resources/blog/python-code-review-tools
5. Subhranshu Pati: "Setting Up a Modern Python + FastAPI Environment" — https://subhranshu.com/blog/setting-up-modern-fastapi-environment
6. FastAPI docs: OpenTelemetry integration — https://fastapi.tiangolo.com/advanced/opentelemetry/
7. fastapi-safeguard — https://github.com/mateush/fastapi-safeguard
8. fastapi-doctor — https://github.com/s-smits/fastapi-doctor
9. umbra-scan — https://github.com/djinn-ai/umbra-scan
10. lite-bootstrap — https://github.com/modern-python/lite-bootstrap
11. fastapi/fastapi .pre-commit-config.yaml — https://github.com/fastapi/fastapi/blob/master/.pre-commit-config.yaml
12. PyDevtools: pre-commit setup — https://pydevtools.com/handbook/how-to/how-to-set-up-pre-commit-hooks-for-a-python-project/
