# AGENTS.md — Sazón app repo (build instructions)

Read this BEFORE writing code in this repo.

## What this repo is

**`Ai-Whisperers/sazon-app`** is the source code for the RMS fase 1 app —
the restaurant management system. Supports **two deployment modes**:

- **Local-first** (legacy): single-user install on the operator's PC, binds to
  `127.0.0.1`, SQLite, no third-party SaaS.
- **Hosted** (since 2026-09-24): VPS at paragu-ai (ServaRica), Docker
  Swarm + Traefik + Cloudflare DNS-01. Active URL:
  https://sazon-vps.paragu-ai.com. Render.com was the prior hosted
  target (2026-09-02 → 2026-09-23) but is now DEPRECATED — see
  `docs/operations/2026-09-24-deployment.md` and `render.yaml` header.

The dev plan is at `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`. The build
specs are at `docs/operations/2026-09-fase-1-specs.md`. Read both before
writing any code.

## Who reads this

**Kiki** (or whoever builds) reads this to write code.
**Operator (Ivan)** reads the docs to verify build progress.
**the operator** does NOT read this. She uses the installed app.

## Build brief

When the clock starts (signed quote + first cuota + Drive + PC named),
follow the dev plan Tasks 1-10 in order. Each task has a demo; don't start
the next task until the current task's demo passes.

Read these BEFORE Task 1:
1. `docs/plans/2026-08-31-rms-fase-1-dev-plan.md` — the locked plan
2. `docs/operations/2026-09-fase-1-specs.md` — 8 implementation specs
3. `docs/operations/import-mapper.md` — v1 catalog column spec (Task 6)
4. `docs/operations/herbus-discovery-prompt.md` — operator-install spec

## Tech stack (locked)

Per `docs/operations/2026-09-tech-stack-review.md`:

- **Python 3.13**, **FastAPI 0.115**, **uvicorn[standard]**, **SQLAlchemy 2.0 sync**,
  **openpyxl 3.1**, **jinja2 3.1**, **pydantic 2.9**, **loguru**.
- Dev: pytest 8, pytest-cov, hypothesis 6 (property-based tests), ruff 0.7.
- Install: **`uv sync`** (NOT pip).
- Pin all deps in `pyproject.toml`; use `uv.lock` for reproducibility.
- **No `async def`** in route handlers. Sync mode.
- **No Alembic**. Hand-rolled versioned migrations in `app/rms/db.py`.
- **No Docker, no Tailwind, no React/Vue.** Server-rendered HTML only.

## Hard rules (read before opening any PR)

1. **No new dependencies without explicit operator OK.** If you think you need
   pandas / numpy / pint / py-moneyed / SQLModel / anything not in
   `pyproject.toml`, **ask first**. Each new dep is a security review.
2. **Decimal for money, never float.** Even one `.00` display bug is a bug.
3. **Round half-up at persistence sites only.** Intermediate calculations
   in `Decimal`; round to `int` only when writing to the DB.
4. **Integer Gs. in the DB.** Money columns are `int`, not `Decimal`.
5. **Paraguayan Spanish only.** All UI strings from `app/docs/copy-vos.md`
   (or `sazon-context/docs/operations/copy-vos-request.md`). No Argentine,
   no Mexican, no English-only.
6. **Spanish (vos) form for verb conjugations.** "Guardá", not "Salvá".
7. **Bind to `127.0.0.1` for local; `0.0.0.0` allowed for hosted.**
   `app/rms/main.py` has an assertion that refuses to start on any other
   host. Hosted (Render/Fly) uses `0.0.0.0` because TLS is terminated by
   Cloudflare Tunnel and the port is not reachable from the public internet.
8. **WAL mode + secure_delete = ON.** Set in `app/rms/db.py` event listener.
9. **No live customer PII.** The app doesn't have a customer table;
   if you add one, follow AGENTS.md rule #4 of `sazon-context`.
10. **No silent overwrite.** Every mass-write (import, re-import) requires
    explicit user confirmation; auto-backup before destructive ops.
11. **Never commit credentials.** Pre-commit hook `check-no-secrets` blocks
    any staged file containing GitHub PAT shapes (`ghp_*`, `ghs_*`, `gho_*`,
    `ghu_*`, `github_pat_*`), `x-access-token:` URLs, AWS access keys, JWTs,
    or long `key=value` strings. Use BWS for secrets. See
    `scripts/check_no_secrets.py` and the `credential-redacted-grep` skill.
    **If you find a leaked credential: rotate first, then scrub the transcript
    with `scripts/redact_key.py`, then fix the leak path.**

## Testing

- Pytest with `uv run pytest`.
- Coverage gate: 80% (CI fails below). Current gate is 35%; Phase 1-4
  plan bumps it in 4 stages. See `state/test-coverage-2026-10-04.json`.
- Property-based tests for money (`test_money.py`); unit tests for unit
  coercion (`test_units.py`); roundtrip tests for import.
- **No Selenium / Playwright** in fase 1. Backend tests only.
- **Test strategy + roadmap**: see
  `docs/operations/2026-10-04-test-execution-plan.md` (the master
  plan). Pairs with `docs/TEST_ARCHITECTURE.md` (5 levels × 8 domains),
  `docs/operations/2026-10-04-qa-hats-playbook.md` (12 hats ×
  wishlists), and `docs/operations/2026-10-04-test-infra-one-pager.md`
  (condensed).

## CI

GitHub Actions runs on every PR to `main`:
- `ruff check .`
- `ruff format --check .`
- `pytest --cov=app` (80% coverage gate)
- Typer check (informational; not blocking yet)
- `sazon migrate` smoke test (fresh SQLite)
- CHANGELOG discipline check (fails PR if `app/`, `scripts/`, `tests/`, or
  `.github/` changed but `app/CHANGELOG.md` did not)

See `.github/workflows/ci.yml`.

## Issue templates

When filing an issue, pick the right template:

- **Bug report** (`.github/ISSUE_TEMPLATE/bug.md`) — defect in deployed code.
- **Feature request** (`.github/ISSUE_TEMPLATE/feature.md`) — proposal for
  a new feature. **Check `docs/wishlist/raw/` first** — the idea may already
  be there. If so, link rather than duplicate.
- **Epic / story** (`.github/ISSUE_TEMPLATE/epic.md`) — multi-PR initiative
  with several stories. Use for any work scoped across multiple PRs.

## Locked hotfixes (DO NOT REVERT without understanding)

The commits on `main` below address real production incidents from
2026-09-04. Each is locked in by a fail-closed test in
`tests/test_hotfix_regressions.py`. If a refactor breaks one of those
tests, the right answer is almost always to update the code to match the
test, NOT to relax the test.

- `f1af406` — HEAD /healthz for UptimeRobot
- `c093a75` — SUPABASE_SECRET_KEY / SUPABASE_PUBLISHABLE_KEY aliases
- `99b37c6` — supabase SDK in Dockerfile pip list
- `bb21eff` — /healthz/deps env fingerprint (debug-only, never leaks values)
- `501bcff` — `row_counts_json` ORM type matches Postgres JSONB

## Ticket convention

Tickets use the format `SASKIA-NNN` (e.g. `SASKIA-001`). 5-character
codes like `E1.S2` are for epic+story (e.g. `E3.S1` = Epic 3, Story 1).
File naming: `SASKIA-NNN-<short-slug>.md`.

The full epic plan (25 epics, 6 phases, ~268h) lives at
`docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md`. Pick from
there.

Ticket template:

```markdown
# SASKIA-NNN: <short title>

**Date:** YYYY-MM-DD
**Epic / Story:** E#.S#
**Owner:** Iván
**Estimate:** Xh
**Status:** in_progress | shipped | blocked | cancelled

## What

<description>

## Why

<business outcome>

## Tasks

- [ ] Task 1
- [ ] Task 2

## Acceptance

<definition of done>
```

## Cross-references

| Repo | What | When to read |
|---|---|---|
| `Ai-Whisperers/sazon-context` | the operator's data + engagement | When you need OPSEC context, who she is, what she asked for |
| `Ai-Whisperers/saskia` (legacy, archived) | Original engagement | Historical reference only; new work doesn't go here |

## When in doubt

- Read the locked dev plan (§9 has the full task breakdown).
- Check the spec docs first — they're the build brief.
- Ask the operator. Don't decide on scope, price, or OPSEC questions silently.
