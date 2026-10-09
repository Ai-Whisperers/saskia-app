# Test Plan Quick-Start — Pick Up Where We Left Off

**Date:** 2026-10-04
**Branch:** `feat/phase-3-ci-cleanup` (91 commits ahead of main)
**Coverage:** 35% → target 80% (10 weeks)

This is a 5-minute primer for a future session (you, future-Ivan, a
teammate) to know exactly what's done, what's next, and where to start.

---

## The 5 sister docs (read in this order)

1. **`docs/operations/2026-10-04-test-execution-plan.md`** — full plan with phase breakdown, hat assignments, dependency map, risks
2. **`docs/operations/2026-10-04-qa-hats-playbook.md`** — 12 hats × wishlists
3. **`docs/operations/2026-10-04-test-infrastructure-upgrade.md`** — 4 pillars (Phase 1-4 detailed)
4. **`docs/operations/2026-10-04-test-infra-one-pager.md`** — the same in 1 page
5. **`docs/TEST_ARCHITECTURE.md`** — 5 levels × 8 domains (the WHAT)
6. **`state/test-coverage-2026-10-04.json`** — snapshot of current state

If you only read ONE doc, read the execution-plan doc.

---

## What's already done (Phase 1 partial)

| Task | Commit | Status |
|---|---|---|
| Expand `tests/_lib/invariants.py` (4 new helpers) | 95d1619 | ✅ |
| `scripts/inventory_seed_helpers.py` (seed audit) | 95d1619 | ✅ |
| `--dist=loadscope` in CI | 95d1619 | ✅ |
| QA Hats Playbook doc | 16399fa | ✅ |

## What's next (Phase 1 remaining — 11 tasks, ~35h)

Top of the list, in priority order:

### 1. `scripts/gen_route_smoke.py` (4h, QA Engineer)

The biggest single win. Builds a script that introspects FastAPI routers and produces a parametrized test for each `@router.{get,post,put,delete,patch}`.

**Where to start:**
```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work

# 1. Find the un-tested routes
for f in $(find app/routers -name "*.py"); do
    bn=$(basename "$f" .py)
    eps=$(grep -cE "^@router\.(get|post|put|delete|patch)" "$f")
    tests=$(grep -rl "from app.routers.${bn}" --include="*.py" tests/ | wc -l)
    if [ "$tests" -eq 0 ] && [ "$eps" -gt 0 ]; then
        echo "UNCOVERED: $bn ($eps endpoints)"
    fi
done

# 2. Look at an existing parametrized test for inspiration
head -50 tests/test_smoke_all_routes.py

# 3. Write the generator
cat > scripts/gen_route_smoke.py <<'EOF'
"""..."""
EOF
```

**Output:** `tests/test_route_smoke_generated.py` with 50+ parametrized cases.

### 2. Migrate the top 5 `_seed_*` helpers (3h, Code Quality)

Use the inventory from `scripts/inventory_seed_helpers.py`. Top offenders:
- `_seed_sale` (5 copies): `_seed_basic` (3), `_seed_product` (3), `_seed_customer` (2), `_seed_pedido` (2)

**Where to start:**
```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work
python3 scripts/inventory_seed_helpers.py
# Pick the top 5, find a qseed scenario that matches, replace
```

### 3. Promote `flows.py` helpers to fixtures (3h, QA Engineer)

**Top 3 helpers to promote:**
- `create_pedido` — used by pedidos tests
- `void_sale` — used by sales tests
- `restock` — used by inventory tests

**Where to start:**
```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work
head -50 tests/flows.py  # see what's there
grep -rl "from tests.flows" --include="*.py" tests/  # see what's used
```

### 4. Test deploy script (3h, Operator)

`scripts/deploy.sh` has no test. Build `tests/test_deploy_dry_run.py` with sandbox mode.

**Where to start:**
```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work
ls scripts/deploy.sh 2>/dev/null || find . -name "deploy.sh" 2>/dev/null
# Build the dry-run mode in the script first, then test
```

### 5. Backup restore drill (4h, SRE)

`tests/test_r2_backup.py` tests artifacts. No test boots app against restored DB.

**Where to start:**
```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work
head -30 tests/test_r2_backup.py
# Add a test that takes backup, wipes DB, restores, asserts app starts
```

### 6. Audit copy + add `test_copy_voz.py` (2h, Localization)

AGENTS.md rule 5: "Paraguayan Spanish only". AGENTS.md rule 6: "vos form".

**Where to start:**
```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work
cat app/docs/copy-vos.md | head -50  # see the canonical strings
grep -rE 'salvá|podés|tenés|vos sos' app/templates/ | head -10  # forbidden patterns
```

### 7. WCAG AA compliance audit (4h, A11y)

`tests/test_wcag_aa_compliance.py` exists. Run it; collect violations.

### 8. Profile `app/rms/analytics.py` (4h, Performance)

Use `py-spy` or `cProfile` to find top 5 N+1 queries.

### 9. Audit csrf.py against OWASP (2h, Security)

Add 4 new csrf tests: token-after-logout, after-rotation, double-submit, after-timeout.

### 10. Migration cross-dialect rewrite (4h, Migration)

9 manual if/else branches remaining (39, 41, 42, 45-49, 51). Use the `_serial_pk_type` helper.

---

## How to do the work

For each task, follow this pattern:

```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work

# 1. Create a topic branch (or stay on feat/phase-3-ci-cleanup)
git checkout feat/phase-3-ci-cleanup
git fetch origin  # check sibling
git log --oneline origin/main..HEAD | head -5  # see your commits

# 2. Do the work
# (edit files, add tests)

# 3. Verify
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/test_<area>.py -v  # quick subset

# 4. Commit with rationale
git add -A
git -c user.name="Ivan" -c user.email="ivan@aiwhisperers.com" commit -m "..."

# 5. Push
git push origin feat/phase-3-ci-cleanup

# 6. Update the state file
# (only at end of phase: update state/test-coverage-2026-10-04.json with new coverage %)
```

---

## How to measure progress

Every PR should answer:
1. **Which TEST_ARCHITECTURE.md gap from §5 does this close?** (G1, G2, M1, etc.)
2. **What's the coverage delta?** (run before + after for affected module)
3. **What's the LOC delta?** (smaller is better; we want to delete code)

At end of each phase, update `state/test-coverage-2026-10-04.json` with:
- new coverage %
- new test_runtime_min
- which tasks completed

---

## Coordination rules (PR coord matters)

1. **Always `git fetch origin` before pushing** — sibling sessions are common.
2. **Always `uv run ruff check` and `uv run ruff format --check`** — keep PR #46 green.
3. **If sibling landed large merge, rebase before continuing** — `git pull --rebase origin feat/phase-3-ci-cleanup`.
4. **If your task is a generator, validate on small subset first** — 30 routes, then expand.

---

## When in doubt

- Read `docs/operations/2026-10-04-test-execution-plan.md` (the master plan)
- Read `docs/operations/2026-10-04-qa-hats-playbook.md` (who owns what)
- Read `docs/TEST_ARCHITECTURE.md` (the gaps)
- Run `python3 scripts/inventory_seed_helpers.py` (current state)
- Run `uv run pytest --cov=app --cov-report=term-missing | tail -30` (live coverage)
- Ask Ivan (the operator) for prioritization

---

## TL;DR for the next session

> 91 commits shipped, 35h of Phase 1 quick wins remaining. Start with `scripts/gen_route_smoke.py` — that's the single biggest win. Migration, seed, and flows tasks are parallel. After Phase 1, coverage bumps from 35% → 40%. Then 50%, 65%, 80% over the next 9 weeks. Total: 142.5h, 10 weeks, all 12 hats.

That's it. Have fun.