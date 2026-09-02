# AGENTS.md — Saskia RMS app repo (build instructions)

Read this BEFORE writing code in this repo.

## What this repo is

**`Ai-Whisperers/saskia-app`** is the source code for the RMS fase 1 app —
the restaurant management system. Supports **two deployment modes**:

- **Local-first** (legacy): single-user install on Saskia's PC, binds to
  `127.0.0.1`, SQLite, no third-party SaaS.
- **Hosted** (recommended since 2026-09-02): Neon Postgres + Render + Cloudflare
  Tunnel + Supabase Auth. Saskia just opens a URL. See
  `docs/operations/2026-09-02-saskia-decision-hosted-pivot.md`.

The dev plan is at `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`. The build
specs are at `docs/operations/2026-09-fase-1-specs.md`. Read both before
writing any code.

## Who reads this

**Kiki** (or whoever builds) reads this to write code.
**Operator (Ivan)** reads the docs to verify build progress.
**Saskia** does NOT read this. She uses the installed app.

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
   (or `saskia-context/docs/operations/copy-vos-request.md`). No Argentine,
   no Mexican, no English-only.
6. **Spanish (vos) form for verb conjugations.** "Guardá", not "Salvá".
7. **Bind to `127.0.0.1` for local; `0.0.0.0` allowed for hosted.**
   `app/rms/main.py` has an assertion that refuses to start on any other
   host. Hosted (Render/Fly) uses `0.0.0.0` because TLS is terminated by
   Cloudflare Tunnel and the port is not reachable from the public internet.
8. **WAL mode + secure_delete = ON.** Set in `app/rms/db.py` event listener.
9. **No live customer PII.** The app doesn't have a customer table;
   if you add one, follow AGENTS.md rule #4 of `saskia-context`.
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
- Coverage gate: 80% (CI fails below).
- Property-based tests for money (`test_money.py`); unit tests for unit
  coercion (`test_units.py`); roundtrip tests for import.
- **No Selenium / Playwright** in fase 1. Backend tests only.

## CI

GitHub Actions runs on every PR to `main`:
- `ruff check .`
- `ruff format --check .`
- `pytest --cov=app`
- Typer check (informational; not blocking yet)

See `.github/workflows/ci.yml`.

## Cross-references

| Repo | What | When to read |
|---|---|---|
| `Ai-Whisperers/saskia-context` | Saskia's data + engagement | When you need OPSEC context, who she is, what she asked for |
| `Ai-Whisperers/saskia` (legacy, archived) | Original engagement | Historical reference only; new work doesn't go here |

## When in doubt

- Read the locked dev plan (§9 has the full task breakdown).
- Check the spec docs first — they're the build brief.
- Ask the operator. Don't decide on scope, price, or OPSEC questions silently.
