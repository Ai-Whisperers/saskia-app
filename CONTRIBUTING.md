# Contributing to Sazón

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E24.S2.

## Quick start

```bash
git clone https://github.com/Ai-Whisperers/sazon-app
cd sazon-app
make install          # uv sync --dev
make migrate          # apply schema migrations
make seed             # populate demo data
make serve            # run on http://127.0.0.1:8765
```

`make` alone shows the full command list.

## Development workflow

1. Create a branch off `main` named `eng/<NNN>-<slug>` or `fix/<slug>`.
2. Make changes; **all PRs touching `app/`, `scripts/`, `tests/`, or `.github/` MUST also touch `app/CHANGELOG.md`** — CI rejects otherwise.
3. Run `make check` locally (ruff + tests).
4. Commit with a clear message referencing the issue / epic.
5. Open a PR against `main`.

## Commit message convention

```
<type>(<scope>): <subject>

<body — what + why, not how>

Refs: ENG-NNN
```

**Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `ci`
**Scope**: epic ID (`E13`), module (`seed`), or area (`ci`).

## Branch convention

```
eng/E6-realistic-seed          # new feature tied to epic
fix/audit-log-timezone          # bug fix
chore/deps-bump-openpyxl        # housekeeping
docs/plan-v3-25-epics           # documentation
```

## Testing

- `make test` — full suite (~70s)
- `make test-coverage` — with HTML report
- `make test-verbose PATH=tests/test_seed.py` — single file

Target: 80%+ coverage. New code must come with tests.

## Database

- Schema is hand-rolled; **do not use Alembic**. Migrations live in `app/rms/db.py` as `_migration_NNN_*` functions.
- Bump `CURRENT_SCHEMA_VERSION` in `app/rms/config.py` after adding a migration.
- Always include `app/rms/models.py` updates for new tables/columns.
- Run `make migrate` after pulling to apply pending migrations.

## Settings

- 30 operator-facing settings live in `app/rms/settings.py`.
- New settings go in the `SETTINGS` list with a default + validator + group.
- Settings are stored in `app_meta` (key-value table).
- The settings UI groups them by `SettingGroup`.

## Tags

- Tags are polymorphic M:N (`Tag` + `TagLink`).
- Use `app/rms/tags.py` helpers — never insert tags directly.
- Starter tags (31) live in `STARTER_TAGS`. Add new ones there.

## Style

- Python: ruff enforces everything. `make lint-fix` to clean.
- Type hints required on all new functions.
- Avoid `Any`; prefer specific types.
- Pure-Python helpers go in `app/rms/<module>.py`; routers in `app/routers/<resource>.py`.
- Tests in `tests/test_<module>.py`.

## Release process

This is a "gem project" for the operator. No formal releases — commits go to `main` via PR, CI must be green, and a `STATUS.html` is auto-refreshed by `make ci-smoke`.

## Reporting issues

Use the GitHub issue templates:
- `.github/ISSUE_TEMPLATE/bug.md`
- `.github/ISSUE_TEMPLATE/feature.md`
- `.github/ISSUE_TEMPLATE/epic.md`

For security issues: contact maintainers directly — do **not** open a public issue.

## Code of conduct

Be kind. We're a small team and we're building something that has to work for a real bakery. No bikeshedding; ship it and iterate.
