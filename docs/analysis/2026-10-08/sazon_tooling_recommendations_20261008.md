# SAZON — Code Quality, Duplication & Tooling Recommendations
## Verified against the Sazon codebase 2026-10-08

This document is the **tooling + quality** companion to the master catalog. It covers:

1. **The "4 settings versions" question** — verified, with the actual picture
2. **Other duplication patterns** found in Sazon (settings isn't the only one)
3. **Linters already in place** — what works today
4. **Gaps** — what should be added
5. **Recommended tooling** with effort estimates
6. **Concrete issues to fix** (the "things to run and implement")

---

# PART 1 — THE SETTINGS STORY (verified)

You were right that there are multiple settings files. Verified on disk:

```
/opt/data/work/saskia-app/app/routers/settings_runtime.py    [router]
/opt/data/work/saskia-app/app/routers/settings.py            [router]
/opt/data/work/saskia-app/app/rms/settings_original.py      [⚠️ legacy kept]
/opt/data/work/saskia-app/app/rms/settings_runtime.py       [new helpers]
/opt/data/work/saskia-app/app/rms/settings.py               [canonical]
```

**5 files**, not 4. The intended state per memory is:
- `settings.py` (538 lines) — the **canonical** 42-key SettingsKV registry
- `settings_runtime.py` (192 lines) — runtime helpers (`get_pricing_markup`, `settings_get`, etc.)
- `settings_original.py` (411 lines) — **legacy, kept for back-compat, should be DELETED but wasn't**

Per memory "Sprint 2.1 (bee5eb9e): settings.py+settings_original.py DELETED; 42-key registry
now app/rms/settings_registry.py (same API, SettingsKV-backed)." This is **wrong on disk**:
- `settings_registry.py` does NOT exist; the registry is in `settings.py`
- `settings_original.py` is **kept** (411 lines), not deleted

So the situation is: **one canonical file (settings.py) + one runtime helper (settings_runtime.py) + one legacy file (settings_original.py) that should have been deleted but wasn't**. Sprint 2.1 was incomplete.

This is the **highest-value cleanup**: `git rm app/rms/settings_original.py` + verify nothing imports it. (Likely no one does, since it's a back-compat shim.)

---

# PART 2 — OTHER DUPLICATION PATTERNS FOUND

I walked every `.py` file in `app/` looking for duplicate-stem names. Found **20** — but **most are the standard Sazon MVC pattern** (intentional, not duplicate):

| Pattern | Status | Reason |
|---|---|---|
| `routers/X.py` + `rms/X.py` + `rms/models/X.py` | ✅ **Intentional** | Thin HTTP handler + service + model. Sazon convention. **Not duplication.** |
| `routers/auth.py` + `auth.py` + `rms/models/auth.py` | ✅ Intentional | Same MVC pattern |
| `rms/audit.py` + `rms/models/audit.py` + `rms/tagging/audit.py` | ✅ Intentional | Different scopes (domain log, model mixin, tagging audit) |
| `rms/models/sales/core.py` + `rms/models/sales/__init__.py` | ✅ Intentional | Subpackage |

**The only REAL outliers** (multiple files in same dir with same purpose):

### 2.1 `settings*.py` triple-stack (already covered above)

### 2.2 `production_scheduler.py` (deprecated but kept)

`app/rms/production_scheduler.py` is 21 lines, **deprecated 2026-10-05** per docstring
("port to production.py helpers"). Should be deleted; verify no one still imports it.

### 2.3 `_archive/2026-10-07-p44-legacy-cleanup/` (already archived)

Already properly archived by P44 cleanup. Good. No action.

### 2.4 Hardcoded `"mostrador"` strings: **57 occurrences**

`grep -rn 'mostrador' app/ --include='*.py'` returns **57 hits**. Some are legitimate
(channel enum values, migration CHECK constraints), but many are likely
`channel="mostrador"` literals that should use `Channel.MOSTRADOR` enum instead.

The 1 active TODO in the code is exactly this:
```
app/rms/models/channels.py:79: # TODO: Remove these once all code is updated to use Channel enum
```

**Effort to fix:** 🟡 M (1 day). Add a ruff rule or simple script: flag `channel="mostrador"`
literals (or any string in the channel allow-list) and suggest `Channel.MOSTRADOR.value`.

### 2.5 `analytics.py` exists in TWO different scopes (intentional but worth noting)

```
app/routers/produccion/analytics.py    [production sub-router]
app/rms/analytics.py                  [979 lines — big stats module]
```

**Intentional** (one is a router, one is service) but the name overlap is confusing.
Document it; consider renaming `rms/analytics.py` → `rms/stats.py` to disambiguate.

### 2.6 Money formatters: probably duplicated

I didn't dig deep, but `notifications.py:74` defines `_money()` and `display.py:135`
defines money formatters. Likely overlap; verify.

---

# PART 3 — LINTERS ALREADY IN PLACE (verified)

## 3.1 ruff (in `.venv/bin/ruff`)

**Configured in `pyproject.toml`** with a rich rule set:

```toml
[tool.ruff]
line-length = 100
target-version = "py313"
extend-exclude = [".github", "app/_archive", ".hermes/plans"]

[tool.ruff.lint]
select = [
    "E", "F", "W", "I",        # pycodestyle + pyflakes + isort (baseline)
    "BLE", "PERF",              # blind-except, perf
    "ANN", "S", "DTZ",          # annotations, bandit, datetimez
    "B", "PIE", "RUF", "ASYNC", # bugbear, pie, ruff-specific, async
    "BLE001", "F401", "F821", "ANN401",
]
```

**Family-by-family what ruff catches today:**

| Family | Catches |
|---|---|
| E/F/W/I | Unused imports, undefined names, style, import order |
| BLE | Blind `except:` (BACKLOG #53 guard) |
| PERF | List/dict comprehension performance, slow loops |
| ANN | Missing type annotations (P0 #1) |
| S | Bandit — SQL injection (S608), hardcoded secrets (S105/S106) |
| DTZ | `datetime.utcnow()` ban, TZ enforcement (P0 #3) |
| B | Bugbear — default-arg gotchas, duplicate excepts |
| PIE | Misc correctness — unused-noqa, redundant comments |
| RUF | Ruff-specific — mutable class attrs, implicit Optional |
| ASYNC | Async correctness — blocking IO in async def |

## 3.2 Pre-commit (4 hooks)

`/opt/data/work/saskia-app/.pre-commit-config.yaml`:

| Hook | What it does |
|---|---|
| `ruff` | `ruff --fix --exit-non-zero-on-fix` |
| `ruff-format` | Auto-format |
| `pytest-smoke` | `uv run pytest -x -q --no-cov tests/test_money.py tests/test_units.py` |
| `forbid-secret-files` | Blocks .env / credentials / id_rsa / secrets.yaml |
| `file-size-sanity` | Blocks accidental > 1 MB commits |

## 3.3 Custom scripts (in `scripts/`)

| Script | Purpose |
|---|---|
| `check_no_secrets.py` | Pattern-shapes scan (GitHub PAT, AWS, JWT) |
| `lint_tier1.py` | Enforces UI conventions (no `.kpi-card`, use `ui.metric_card`) |
| `check_warnings.py` | Fails if test suite emits > N warnings |
| `check_currency_drift.sh` | Currency drift check |
| `check_bank_schema.py` | Bank schema consistency |
| `lint_tier1.py` | UI template conventions |
| `smoke_test_deploy_shape.py` | Deploy-shape smoke test |

## 3.4 Makefile targets

15+ targets including: `test`, `test-fast`, `test-coverage`, `lint`, `lint-fix`,
`format`, `serve`, `migrate`, `seed`, `smoke`, `check-warnings`, `check-secrets`,
`pre-commit`, `ci-smoke`, `ci`.

---

# PART 4 — GAPS (what's missing)

| Gap | What would catch | Effort |
|---|---|---|
| **No duplicate-function detection** | Two functions doing the same thing with different names | 🟢 S |
| **No dead-code detection beyond ruff** | Imported-but-never-used modules (like `settings_original.py` if nothing imports it) | 🟢 S |
| **No import-cycle detection** | A imports B imports A (slow startup, brittle refactor) | 🟢 S |
| **No architecture-rule enforcement** | e.g. "routers/X.py must not import from another routers/Y.py" (cross-handler calls = spaghetti) | 🟡 M |
| **No docstring-coverage check** (interrogate) | Public functions without docstrings | 🟢 S |
| **No complexity check** (radon / xenon) | Cyclomatic complexity > 10 = refactor signal | 🟢 S |
| **No type-checker** (mypy/pyright) | Even with `ANN` ruff, no real type-check pass | 🟡 M |
| **No security scanner** (bandit) | S rules in ruff are partial | 🟢 S |
| **No dependency-vuln check** (pip-audit / safety) | CVEs in deps | 🟢 S |
| **No license check** (reuse) | Wrong license headers | 🟢 S |
| **No CHANGELOG enforcement** | Conventional-commits / release-please | 🟡 M |
| **No "settings_original" detector** | Specifically catches "kept for back-compat" files | 🟢 S |

---

# PART 5 — RECOMMENDED TOOLING

Sorted by ROI. All in pyproject.toml `[dependency-groups].dev`.

## 5.1 High-value, low-effort (add this week)

| Tool | What it does | Why Sazon needs it | Effort | Risk |
|---|---|---|---|---|
| **vulture** | Find dead code (unused functions, classes, variables) | Catch `settings_original.py`-style leftovers | 🟢 S | 🟢 low |
| **pip-audit** | Scan `uv.lock` for CVEs in dependencies | Already in `pre-commit`-style; `sazon` runs on VPS so CVE = exploit | 🟢 S | 🟢 low |
| **bandit** | Security linter (SQL injection, hardcoded creds, weak crypto) | Ruff S rules are partial; bandit has more | 🟢 S | 🟢 low |
| **reuse** | License-header compliance (SPDX) | The repo has MIT in pyproject.toml but no per-file headers | 🟢 S | 🟢 low |
| **radon** | Cyclomatic complexity + raw metrics | Sazon has files like `db.py` (4,844 lines) and `models_legacy.py` (2,943) — know where to refactor | 🟢 S | 🟢 low |
| **xenon** | Enforce complexity ceiling (CI fail if CC > 10) | Same as radon but CI-enforceable | 🟢 S | 🟢 low |

## 5.2 Duplicate-detection (the answer to "settings had 4 versions")

| Tool | What it does | Why Sazon needs it | Effort | Risk |
|---|---|---|---|---|
| **jscpd** | Copy-paste detector across all files (Python, HTML, JS, YAML) | Catches settings.py + settings_original.py duplication. Catches `routers/X.py` + `rms/X.py` over-merge. Catches the 57 hardcoded `"mostrador"`. | 🟢 S | 🟢 low |
| **pylint --disable=all --enable=W0611,W0401** | W0611 unused imports, W0401 wildcard imports | Quick win alongside ruff | 🟢 S | 🟢 low |
| **autoflake** | Auto-remove unused imports + unused variables | Pairs with ruff format | 🟢 S | 🟢 low |

## 5.3 Architecture enforcement (medium effort)

| Tool | What it does | Why Sazon needs it | Effort | Risk |
|---|---|---|---|---|
| **import-linter** | Define + enforce architectural rules (e.g. "routers/X.py must not import another routers/Y.py") | Sazon's MVC layering is good but undocumented; lint it | 🟡 M | 🟢 low |
| **pydeps** | Visualize import graph | One-time to find cycle risks | 🟢 S | 🟢 low |
| **grimp** | Programmatic import-graph queries | Sazon's `app/rms/sales/` + `app/routers/sales.py` could be a cycle — verify | 🟡 M | 🟡 med |

## 5.4 Type checking (medium effort)

| Tool | What it does | Why Sazon needs it | Effort | Risk |
|---|---|---|---|---|
| **mypy** | Static type checker (PEP 484) | `app/rms/` has few type hints despite `from __future__ import annotations` everywhere | 🟠 L | 🟡 med |
| **pyright** (Microsoft) | Faster mypy alt, used by VSCode Pylance | Same | 🟠 L | 🟡 med |

**Recommendation:** Start with **mypy on `app/rms/money.py` + `app/rms/units.py`** (the money/quantity layer) since money bugs are the most expensive. Then expand.

## 5.5 Specialized (defer until needed)

| Tool | What it does | When to add |
|---|---|---|
| **safety** | PyUp.io vulnerability DB (alternative to pip-audit) | If pip-audit has gaps |
| **detect-secrets** | Yelp's secret scanner (alt to check_no_secrets.py) | If you want a richer scanner |
| **deptry** | Find unused + missing dependencies in pyproject.toml | When bumping deps |
| **syrupy** | Snapshot testing | When refactoring analytics pages |
| **hypothesis** | Property-based testing (already in pyproject) | When adding calculation paths |
| **mutmut** | Mutation testing | When you want to verify test quality |
| **cove** | Coverage visualization | When growing coverage from 35% → 80% |

---

# PART 6 — CONCRETE THINGS TO RUN (the actionable list)

## 6.1 Things to run ONCE now (no install, just script)

```bash
# 1. Detect dead/duplicate files in app/
# (no install needed; uses Python stdlib)
cd /opt/data/work/saskia-app

# Find files with the same stem (settings, audit, customers, etc.)
python3 -c "
import os, re
seen = {}
for root, dirs, files in os.walk('app'):
    if '_archive' in root: continue
    for f in files:
        if f.endswith('.py'):
            stem = re.sub(r'(_original|_backup|_legacy|_deprecated|_old|_v\d+|_new|_copy)$', '', f.replace('.py',''))
            seen.setdefault(stem, []).append(os.path.join(root, f))
for k, v in sorted(seen.items()):
    if len(v) > 1:
        print(f'{k}:')
        for p in v: print(f'  {p}')
"
```

```bash
# 2. Find all hardcoded channel strings (the 57 'mostrador' issue)
grep -rn '"mostrador"\|'"'"'mostrador'"'"'' app/ --include='*.py' | wc -l
# Then open the file, identify the legitimate ones (in migrations, enum)
# vs the ones that should be Channel.MOSTRADOR.value
```

```bash
# 3. Find unused imports (catches settings_original.py if no one imports it)
grep -rn 'settings_original' app/ --include='*.py' | grep -v 'settings_original.py'
# If empty → safe to git rm
```

```bash
# 4. Check for cycles in the sales/ lifecycle split
python3 -c "
import ast, os
graph = {}
for root, dirs, files in os.walk('app/rms/sales'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path) as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
                    if mod and mod.startswith('app.'):
                        graph.setdefault(path, set()).add(mod)
# Print the edges
for src, dsts in graph.items():
    for d in dsts:
        if d.endswith('.sales') or 'sales' in d:
            print(f'{src} -> {d}')
"
```

## 6.2 Things to install + run (one-time setup)

```bash
# 1. vulture — dead code
uv add --dev vulture
uv run vulture app/ --min-confidence 80

# 2. pip-audit — CVE scan
uv add --dev pip-audit
uv run pip-audit

# 3. bandit — security
uv add --dev bandit
uv run bandit -r app/ -ll

# 4. radon — complexity
uv add --dev radon
uv run radon cc app/ -a -s

# 5. jscpd — copy-paste
# jscpd is a Node tool; install separately
npx jscpd app/ --min-tokens 50 --reporters html
# Will find settings.py ↔ settings_original.py duplication

# 6. reuse — license headers
uv add --dev reuse
uv run reuse lint

# 7. import-linter — architecture rules
uv add --dev import-linter
# Then add .import-linter.ini with rules:
#   - rms must not import routers
#   - models must not import rms.X (only sqlalchemy)
#   - routers must not import other routers
```

## 6.3 Things to add to pre-commit (long-term)

```yaml
# .pre-commit-config.yaml — additions
repos:
  # ... existing ruff + ruff-format ...
  
  - repo: local
    hooks:
      - id: vulture
        name: dead-code scan
        entry: uv run vulture app/ --min-confidence 80
        language: system
        pass_filenames: false
        types: [python]
        
      - id: pip-audit
        name: dependency CVE scan
        entry: uv run pip-audit
        language: system
        pass_filenames: false
        
      - id: bandit
        name: security scan
        entry: uv run bandit -r app/ -ll
        language: system
        pass_filenames: false
        
      - id: radon
        name: complexity ceiling
        entry: uv run radon cc app/ -a -s -n C
        language: system
        pass_filenames: false
        
      - id: no-settings-original
        name: forbid settings_original.py from being committed again
        entry: bash -c 'if git diff --cached --name-only | grep -q "settings_original.py"; then echo "settings_original.py was deleted in Sprint 2.1; re-add only if you really need back-compat"; exit 1; fi'
        language: system
        pass_filenames: false
```

## 6.4 Things to add to CI (`.github/workflows/ci.yml`)

```yaml
# Add to existing CI workflow
- name: Dead code scan
  run: uv run vulture app/ --min-confidence 80

- name: Dependency CVE scan
  run: uv run pip-audit

- name: Security scan
  run: uv run bandit -r app/ -ll

- name: Complexity ceiling
  run: uv run radon cc app/ -a -s -n C

- name: License check
  run: uv run reuse lint
```

---

# PART 7 — IMMEDIATE ACTION ITEMS (start today)

Sorted by ROI. Each takes < 1 day.

| # | Action | Effort | Risk | Tool needed |
|---|---|---|---|---|
| 1 | **Verify `settings_original.py` has no importers; if zero, `git rm`** | 🟢 S | 🟢 low | grep |
| 2 | **Verify `production_scheduler.py` (deprecated) has no callers** | 🟢 S | 🟢 low | grep |
| 3 | **Run `vulture` to find all dead code** | 🟢 S | 🟢 low | vulture |
| 4 | **Run `bandit` to find security issues** | 🟢 S | 🟢 low | bandit |
| 5 | **Run `radon cc` to find complex files** | 🟢 S | 🟢 low | radon |
| 6 | **Run `pip-audit` for CVEs** | 🟢 S | 🟢 low | pip-audit |
| 7 | **Fix 57 hardcoded `"mostrador"` strings** (replace with `Channel.MOSTRADOR.value`) | 🟡 M | 🟡 med | ruff custom rule + manual |
| 8 | **Add `import-linter` rules** to enforce MVC layering | 🟡 M | 🟡 med | import-linter |
| 9 | **Run `jscpd` to find all copy-paste** including the 5 settings files | 🟢 S | 🟢 low | jscpd (Node) |
| 10 | **Set up `reuse` for SPDX license headers** | 🟢 S | 🟢 low | reuse |

---

# PART 8 — LONG-TERM RECOMMENDATIONS (for the next 3 months)

## 8.1 Tooling maturity model

| Stage | Tools | When |
|---|---|---|
| **Stage 1 (now)** | ruff + ruff-format + pre-commit + check_no_secrets + lint_tier1 | Already in place ✅ |
| **Stage 2 (this week)** | vulture + bandit + radon + pip-audit | 🟢 add |
| **Stage 3 (this month)** | jscpd + reuse + import-linter | 🟡 add |
| **Stage 4 (this quarter)** | mypy/pyright on critical paths (money, units) | 🟠 add |
| **Stage 5 (next quarter)** | mutation testing (mutmut) + property-based (hypothesis expansion) | 🔵 defer |

## 8.2 Pre-commit hook ordering (when adding new hooks)

Order matters for fast feedback:
1. **forbid-secret-files** (no install) — instant
2. **file-size-sanity** (no install) — instant
3. **ruff --fix** — fast (~1s)
4. **ruff-format** — fast (~1s)
5. **vulture** — fast (~2s)
6. **bandit** — medium (~5s)
7. **radon** — medium (~5s)
8. **pytest-smoke** — slow (~30s)
9. **pip-audit** — slow (~30s, network)
10. **reuse** — fast (~1s)

## 8.3 CI matrix (.github/workflows/ci.yml)

Currently: 1 job, 1 Python version. Recommended:

```yaml
strategy:
  matrix:
    python-version: ["3.13.5"]
    test-tier: [smoke, full]
    include:
      - test-tier: smoke
        cmd: uv run pytest -x -q --no-cov -m smoke
      - test-tier: full
        cmd: uv run pytest --cov=app --cov-fail-under=35
```

---

# PART 9 — CONCRETE FIXES (the "things to do")

## 9.1 Sprint-day fixes (do this week)

### Fix 1: Delete `settings_original.py`

```bash
# Verify no importers
cd /opt/data/work/saskia-app
grep -rn 'settings_original' app/ --include='*.py' | grep -v 'settings_original.py'
# If empty, delete:
git rm app/rms/settings_original.py
```

### Fix 2: Delete `production_scheduler.py` (deprecated)

```bash
grep -rn 'production_scheduler' app/ --include='*.py' | grep -v 'production_scheduler.py'
# If empty, delete:
git rm app/rms/production_scheduler.py
```

### Fix 3: Add `[tool.ruff.lint.per-file-ignores]` for tests

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN", "DTZ"]  # tests can assert + skip annotations
"app/_archive/**" = ["ALL"]           # archived code exempt
"app/r2_backup.py" = ["ALL"]
```

### Fix 4: Add vulture to pyproject

```toml
[tool.vulture]
min_confidence = 80
paths = ["app/"]
exclude = ["app/_archive/", "tests/"]
```

## 9.2 Sprint-week fixes (this month)

### Fix 5: Add `import-linter` rules

```ini
# .import-linter.ini
[importlinter:contract:no-rms-in-routers]
type = forbidden
source_modules = app.routers
forbidden_modules = app.rms.profitability, app.rms.audit
```

### Fix 6: Replace 57 `"mostrador"` strings with `Channel.MOSTRADOR.value`

Each location:
```python
# Before
sale.channel = "mostrador"
# After
from app.rms.models.channels import Channel

sale.channel = Channel.MOSTRADOR.value
```

This is a **search-and-replace** task with verification. Effort: 1 day.

### Fix 7: Add `mypy` to `app/rms/money.py` only

```bash
uv add --dev mypy
cat > mypy.ini <<EOF
[mypy]
files = app/rms/money.py,app/rms/units.py
strict = True
EOF
uv run mypy app/rms/money.py
```

---

# PART 10 — WHAT NOT TO DO (avoid the rabbit holes)

| Tool | Why skip for now |
|---|---|
| **SonarQube** | Heavy; not for a 1-dev shop; ruff + bandit + radon covers it |
| **CodeQL** | Free for OSS, expensive infra otherwise; ruff S rules are enough |
| **Pylint** | ruff is faster + cleaner; pylint is redundant |
| **Black** | ruff-format replaced it |
| **isort** | ruff I rules replaced it |
| **Sphinx** | 99 templates don't need auto-API docs |
| **Mypy on whole project** | Sazon has 30K+ LOC with little type hints; whole-project mypy = weeks of churn. **Just do money.py + units.py first.** |
| **Pre-commit on every push** | Only on commits; CI on push |

---

# PART 11 — SUGGESTED ADDITIONS TO AGENTS.md

Once the new tools are in, add to `app/rms/AGENTS.md`:

```markdown
## Rule 27: No duplicate-name files in the same directory

If `app/rms/<feature>.py` exists, `app/rms/<feature>_original.py` is forbidden.
Use git history, not file copies, to preserve old code.

## Rule 28: No hardcoded channel strings

Use `Channel.MOSTRADOR.value` from `app/rms/models/channels.py`. No `channel="mostrador"` literals.

## Rule 29: Cyclomatic complexity < 10 per function

Enforced by `radon cc -n C` in CI. Refactor if CC > 10.

## Rule 30: No new deps without CVE scan

Run `uv run pip-audit` before adding any new dependency.
```

---

# PART 12 — SUMMARY

## The "4 settings versions" question
- Verified: **5 files** (not 4), with **1 dead** (`settings_original.py` 411 lines)
- **Sprint 2.1 was incomplete** — the deletion didn't actually happen
- Fix: `git rm app/rms/settings_original.py` (1 minute, if no importers)

## What to run NOW (no install, just script)
1. `grep -rn 'settings_original' app/` — verify safe to delete
2. `grep -rn 'production_scheduler' app/` — verify safe to delete
3. `grep -rn '"mostrador"' app/` — find 57 hardcoded strings

## What to install THIS WEEK
1. **vulture** — catch dead code
2. **bandit** — catch security issues
3. **radon** — measure complexity
4. **pip-audit** — catch CVEs

## What to install THIS MONTH
1. **jscpd** — catch copy-paste duplication
2. **import-linter** — enforce MVC layering
3. **reuse** — license header compliance

## What to add to pre-commit
1. vulture + bandit + radon + reuse (after the vulture baseline is clean)

## What to add to CI
1. pip-audit
2. radon CC ceiling
3. bandit

## What to add to AGENTS.md
1. Rule 27: no duplicate-name files
2. Rule 28: no hardcoded channel strings
3. Rule 29: CC < 10
4. Rule 30: no new deps without CVE scan

## File path
- This doc: `/opt/data/profiles/ivan/cache/scratch/sazon_tooling_recommendations_20261008.md`
