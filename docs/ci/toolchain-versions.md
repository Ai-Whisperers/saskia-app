# Toolchain versions — Sazon RMS

**Last updated:** 2026-10-09 (post-CI-recovery)
**Owner:** Ivan (AIW)
**Audience:** anyone bumping a tool, debugging a CI failure, or onboarding a new session.

## Quick reference

| Tool | Version | Pinned where | Upgrade policy |
|---|---|---|---|
| **Python** | 3.13 (Hermes runtime = 3.13.5) | `pyproject.toml` `requires-python`, all `uv python install 3.13` in workflows, `Dockerfile` | Bump once per 6 months after GA; never in the same week as a uv bump |
| **uv** | 0.5.x (current 0.5.11) | `astral-sh/setup-uv@v7` with `version: "0.5.x"` in all `.github/workflows/*.yml` | Pin to minor; bump after 1 week of test runs with no regressions |
| **ruff** | latest stable (matches uv 0.5.x) | `pyproject.toml` `[tool.ruff]` + pre-commit hook | Auto-updated by uv; verify in `uv.lock` |
| **pytest** | 8.x (latest) | `pyproject.toml` `[tool.pytest.ini_options]` + pre-commit + dev-base group | Auto-updated by uv; lock for stability |
| **pytest-cov** | latest | dev-base group | Auto |
| **pytest-xdist** | latest (used in ci.yml `-n 2 --dist=loadscope`) | dev group | Auto |
| **playwright** | latest (browser tests excluded from dev-base) | dev group, separate `browser.yml` workflow | Bump with 1-week test |
| **Postgres** | 16-alpine | `smoke.yml`, `security-zap.yml` ephemeral containers | Bump to latest GA (16→17) only after a sprint of stability |
| **Docker** | (swarm mode, not compose) | VPS-side; per AGENTS.md anti-rule #4 | N/A — Swarm only |
| **GH Actions runners** | ubuntu-latest | all workflows `runs-on: ubuntu-latest` | Auto |
| **actions/checkout** | v7 | all workflows | Bump in lockstep across all workflows |
| **astral-sh/setup-uv** | v7 | all workflows | Same |
| **actions/upload-artifact** | v7 | `security-zap.yml`, future sharded tests | Same |
| **zaproxy/action-api-scan** | v0.10.0 | `security-zap.yml` | Bump + rerun weekly scan; check for new `-l` levels in the changelog |
| **pre-commit** | latest stable | `.pre-commit-config.yaml` (14 hooks) | Auto; verify in CI after bump |
| **Git** | 2.x (host-side) | VPS + operator machine | N/A |
| **uvloop** | latest (Linux only) | `app[uvloop]` extras | Auto |

## Version policy

The repo follows a **pin-minor-bump-major** policy:

- **Patches** (X.Y.Z+1) — auto-bumped by uv; commit the lockfile change; CI validates.
- **Minors** (X.Y+1) — explicit PR; bump one tool at a time; let it run on 5-10 CI cycles before the next bump.
- **Majors** (X+1) — manual decision; needs a sprint to plan migrations (deprecations, breaking changes).

**Never two majors in the same week.** A Python 3.13 → 3.14 + uv 0.5 → 0.7 + ruff 0.5 → 0.6 triple-bump is the fastest path to "nothing works, can't tell why". One at a time.

## Upgrade procedure

### Python minor bump (3.13 → 3.14)

1. Update `pyproject.toml` `requires-python = ">=3.14,<3.15"`.
2. Update `uv python install 3.14` in all `.github/workflows/*.yml`.
3. Update `Dockerfile` `FROM python:3.14-slim` (if it exists).
4. Run `uv lock` to regenerate `uv.lock`.
5. `uv run python -c "import sys; assert sys.version_info[:2] == (3, 14)"` — sanity check.
6. Run `uv run pytest -n 2 --dist=loadscope` locally — full suite.
7. Push; let CI cycle for 1 week before bumping anything else.

### uv bump (0.5.x → 0.6.x)

1. Update `version: "0.5.x"` → `version: "0.6.x"` in every workflow file. (`grep -rn "0.5.x" .github/workflows/`).
2. Run `uv self update` (Hermes runtime).
3. `uv sync --all-extras` to refresh lockfile.
4. `uv run pytest -n 2 --dist=loadscope` — full suite.
5. Push; verify all 11 GH Actions workflows still pass.

### GH Actions version bump (v7 → v8)

1. Update all `actions/checkout@v7` → `@v8` (or whatever the new SHA-pinned major is).
2. Update `astral-sh/setup-uv@v7` → `@v8` similarly.
3. `git grep -l "actions/checkout@v7" .github/` — confirm zero hits.
4. Push; verify all workflows still trigger.

## Failure mode: uv 0.5 → 0.7 (hypothetical)

This is a what-would-break list, not a thing that happened. (uv 0.5 → 0.7 would be 2 minor bumps; in practice we'd do one at a time.)

**What would break:**

1. **`uv sync --only-group dev-base` flag semantics.** Newer uv versions sometimes deprecate `--only-group` in favor of `--group` + `--no-default-groups`. Workflows that use the old flag silently drop dependencies → 90% of tests fail with `ModuleNotFoundError`.
2. **`.venv` cache key changes.** `astral-sh/setup-uv@v7` with `enable-cache: true` uses `pyproject.toml` + `uv.lock` as the cache key. If the cache key includes the uv version, a uv bump invalidates ALL caches → next CI run is 3-4 min slower (cold download).
3. **Python 3.13 → 3.14 in `uv python install`.** If the version is hardcoded, a 3.14 GA + old `uv python install 3.13` will start failing once the host image drops 3.13. (Hermes currently ships 3.13.5; bump there first.)
4. **The `actions/upload-artifact@v7` breaking change.** v8 deprecates the old `actions/upload-artifact@v3` and the artifact name format. The ZAP workflow uses `name: zap-report` — that should keep working, but the new v8 has stricter input validation (no special chars in `name`).

**Mitigation:**

- Pin uv to `0.5.x`, not the latest. The `x` is intentional — it lets patch updates through but stops minors.
- Run `uv self update` + `uv sync --all-extras` locally before pushing any workflow change.
- Always run `uv run pytest -n 2 --dist=loadscope` locally before pushing CI changes.

## History of toolchain changes

| Date | Change | Why | Verifier |
|---|---|---|---|
| 2026-09-XX | `actions/checkout@v4` → `@v7` | GH Actions runner security; v4 was deprecated 2026-Q2 | `git grep "actions/checkout"` returns only `@v7` |
| 2026-10-09 | uv pinned to `0.5.x` across all workflows | Stop the "uv 0.5 → 0.7 broke things" scenario from PR #88 audit | grep -rn "0.5.x" .github/workflows/ = 11 hits (one per workflow) |
| 2026-10-09 | `astral-sh/setup-uv` pinned to `@v7` | same | grep -rn "setup-uv" .github/workflows/ returns only `@v7` |
| 2026-10-09 | `zaproxy/action-api-scan` pinned to `@v0.10.0` | Newer versions changed `-l` flag behavior; would need a separate audit | grep "action-api-scan" .github/workflows/security-zap.yml = `@v0.10.0` |

## Verification checklist (run before AND after any toolchain bump)

```bash
# 1. Lint
uv run ruff check .
uv run ruff format --check .

# 2. Static analysis
uv run python -m compileall app/

# 3. Full test suite
uv run pytest -n 2 --dist=loadscope --no-cov

# 4. Migration smoke
uv run python scripts/smoke_test_deploy_shape.py

# 5. Pre-commit
pre-commit run --all-files

# 6. Build the Docker image (VPS-side)
ssh root@38.9.96.179 'cd /opt/build-apps/sazon-rms && docker build -t sazon-rms:toolchain-test .'

# 7. Smoke deploy (dev)
bash scripts/deploy.sh --env=dev

# 8. Verify all 11 GH Actions workflows pass on the bump PR
gh pr checks <PR-number>
```

If any step fails, the toolchain bump is not safe. Roll back the version pin and try a smaller increment.

## References

- `pyproject.toml` — the single source of truth for Python deps + tool config
- `uv.lock` — the lockfile (commit changes; don't `.gitignore` it)
- `.pre-commit-config.yaml` — the 14 hooks
- `scripts/smoke_test_deploy_shape.py` — the migration + boot smoke test
- `docs/operations/2026-10-09-three-env-deploy.md` — how the deploy flow uses these tools
- `docs/operations/2026-10-09-ci-recovery.md` — what was broken and why we pin now
- [astral-sh/uv changelog](https://github.com/astral-sh/uv/blob/main/CHANGELOG.md) — read before bumping uv
- [GitHub Actions runners](https://github.com/actions/runner-images) — what's on `ubuntu-latest` at any time
