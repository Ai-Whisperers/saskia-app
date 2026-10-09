# 2026-10-09 — Tier 2 Tooling Adoption

**Branch:** `tooling/adopt-tier2-2026-10-09`
**Worktree:** `/opt/data/profiles/ivan/cache/scratch/saskia-app-tooling-adopt`
**Predecessor:** `docs/tooling-research-2026-10-09` (PR #94) — research only

---

## TL;DR

This PR adopts the 4 Tier 2 tooling wins from the 2026-10-09 research (PR #94). The deliverable is **infrastructure, not full integration**:

1. **zizmor** for GitHub Actions security — wired into Makefile + new CI workflow. 15 high-severity findings surfaced.
2. **OpenTelemetry + Prometheus** — opt-in via env var, no breaking changes. New `app/rms/otel.py` module.
3. **fastapi-safeguard** — added to `tooling-tier2` dep group; not yet wired into `create_app()` (needs baseline).
4. **Actionlint** — superseded by zizmor (zizmor does the same checks plus more). No separate actionlint integration needed.

**Not in this PR** (deferred to followups):
- SHA-pinning the 35 unpinned-uses findings (cross-cutting, 14 files)
- Wiring fastapi-safeguard into main.py (needs baseline; not safe to land without it)
- ast-grep (would replace `lint_tier1.py`; needs learning curve + value validation)

---

## What this PR ships

### 1. zizmor for GitHub Actions security

**Files added:**
- `.github/zizmor.yml` — config (8 rules promoted to high, 2 downgraded to informational)
- `.github/workflows/workflows-lint.yml` — CI workflow that runs zizmor on every PR

**Files modified:**
- `Makefile` — 6 new targets: `workflows-lint`, `workflows-lint-all`, `docs-lint`, `docs-lint-strict`, `jscpd`, `deadcode-code`, `tool-matrix`
- `ci-extra` — extended to include `workflows-lint`

**Findings (zizmor 1.30.1 against all 14 workflows):**

| Severity | Count | Rules |
|---|---|---|
| HIGH (blocks PR) | **15** | excessive-permissions (8), template-injection (6), cache-poisoning (1) |
| INFORMATIONAL (visible) | **49** | unpinned-uses (35), artipacked (14) |
| **Total** | **64** | |

**Why "informational" for unpinned-uses/artipacked:**
- The 35 unpinned-uses findings are a separate SHA-pinning PR (14 files, 35+ lines of diff). The config downgrades them to informational until that PR ships.
- The 14 artipacked findings require adding `persist-credentials: false` to every checkout. Also a separate cross-cutting PR.
- Both are tracked as TODOs in the config file.

**Why a separate workflow, not part of `tooling.yml`:**
- zizmor is a Rust binary installed via `uvx`, not `uv sync`
- The 15 high-severity findings would block the existing tooling gate
- Independent concurrency + clear ownership

### 2. OpenTelemetry + Prometheus (opt-in)

**Files added:**
- `app/rms/otel.py` — `init_observability(app)` function with env-gated activation

**Files modified:**
- `app/rms/main.py` — calls `init_observability(app)` from the Sentry init block in `lifespan`
- `pyproject.toml` — new `[dependency-groups].tooling-tier2` with OTel + Prometheus + fastapi-safeguard

**Activation (off by default):**

| Env var | Effect |
|---|---|
| `OTEL_ENABLED=true` + `OTEL_EXPORTER_OTLP_ENDPOINT=http://...` | OTel tracing enabled |
| `OTEL_ENABLED=true` (no endpoint) | Warns; creates spans but doesn't export |
| `PROMETHEUS_ENABLED=true` | Exposes `/metrics` endpoint |
| (unset) | no-op, no overhead |

**Install:**
```bash
uv sync --group tooling-tier2
```

**Why env-gated, not always-on:**
- The OTel SDK is ~6 MB; bundling it always-on adds weight to dev installs
- Tests don't need real OTel; the module's try/except makes the import safe
- Sazon is a one-bakery app; operator chooses when to flip the switch
- Pattern matches the existing Sentry activation (same env-gated style)

### 3. fastapi-safeguard (added to deps, not wired)

**File modified:**
- `pyproject.toml` — `fastapi-safeguard>=0.2` added to `tooling-tier2`

**Why not wired into `create_app()`:**
- `fastapi-safeguard` requires a baseline lock file (`security_baseline.json`) before activation
- Without a baseline, it would fail on the first run with all 350+ routes flagged
- Building the baseline requires running against the live app once, capturing all findings, then committing the baseline
- This needs operator review (decide which routes are intentionally public)

**Followup PR:** Wire `fastapi-safeguard` into `create_app()` with baseline = `docs/security/2026-10-09-fastapi-baseline.json` (to be generated).

### 4. (Not done) actionlint

zizmor covers everything actionlint would (and more). No separate integration needed.

### 5. (Not done) ast-grep

`scripts/lint_tier1.py` already covers the Sazon-specific UI patterns. ast-grep would replace it but:
- It's a Rust binary (different install path than current Python-only tooling)
- The patterns in lint_tier1.py are Jinja-template-specific (not pure Python AST)
- Replacement would be marginal value

**Decision:** Keep `lint_tier1.py` for now. Revisit when we have more Sazon-specific patterns to express.

---

## Verification

| Check | Result |
|---|---|
| `make workflows-lint` | rc=0 (uses `|| true` for info); 15 HIGH findings logged |
| `uvx zizmor` on our new workflow | rc=0, "No findings to report" |
| `uv lock --dry-run` | rc=0, 146 packages resolved |
| `pytest tests/test_money.py tests/test_units.py` | rc=0, 115 tests pass |
| `python3 -c "import ast; ast.parse(open('app/rms/main.py').read())"` | rc=0 |
| `python3 -c "import ast; ast.parse(open('app/rms/otel.py').read())"` | rc=0 |
| `make docs-lint` | rc=1, 11,510 findings (per PR #93) |
| `make jscpd` | rc=0, 303 clone groups |
| `make deadcode-code` | rc=0, 30+ dead functions |

---

## The 15 high-severity zizmor findings (operator review needed)

**excessive-permissions (8)** — these are jobs without a `permissions:` block. Fix by adding explicit `permissions:` per job. Suggested starting point:

```yaml
permissions:
  contents: read
```

| Workflow | Job |
|---|---|
| `browser.yml` | browser |
| `ci.yml` | test |
| `currency-drift.yml` | currency-drift |
| `date-boundary.yml` | date-boundary |
| `dev-ci.yml` | gate |
| `release.yml` | release |
| `route-smoke.yml` | route-smoke |
| `smoke.yml` | smoke |

**template-injection (6)** — `${{ github.event.* }}` expansions in unquoted shell contexts. Mostly in `release.yml` (workflow_dispatch inputs). Fix: pass through env vars (not direct interpolation).

**cache-poisoning (1)** — `release.yml:34` has an `on:push:tags:` trigger that uses a wildcard pattern; can be exploited to inject cache keys. Fix: pin to a specific format.

---

## Tier 3 deferred (for completeness)

These are documented in the research report but **not** in this PR:

- **Vale** for prose linting (blocked by network — binary download fails)
- **Semgrep CE** for custom Sazon-specific rules
- **umbra-scan** for shadow API detection
- **`factory_boy` audit** — needs to check `tests/conftest.py` current state

Each will become its own future PR with a clear scope.

---

## Sources

1. zizmor docs: https://docs.zizmor.sh/
2. FastAPI OTel integration: https://fastapi.tiangolo.com/advanced/opentelemetry/
3. prometheus-fastapi-instrumentator: https://github.com/trallnag/prometheus-fastapi-instrumentator
4. fastapi-safeguard: https://github.com/mateush/fastapi-safeguard
5. Predecessor: `docs/operations/2026-10-09-tooling-research.md` (PR #94)

---

## Changelog entry (auto-applied)

```markdown
## [Unreleased] — Tooling Tier 2

### Added
- zizmor for GitHub Actions security (`.github/zizmor.yml`, `.github/workflows/workflows-lint.yml`)
- `app/rms/otel.py` — opt-in OTel + Prometheus via `OTEL_ENABLED` / `PROMETHEUS_ENABLED` env vars
- `tooling-tier2` dependency group with fastapi-safeguard, OpenTelemetry, and prometheus-fastapi-instrumentator

### Makefile
- `make workflows-lint` (zizmor HIGH only)
- `make workflows-lint-all` (all severities)
- `make docs-lint` (pymarkdownlnt)
- `make docs-lint-strict` (all markdown rules)
- `make jscpd` (copy-paste detector)
- `make deadcode-code` (cross-file dead code)
- `make tool-matrix` (print coverage table)
```
