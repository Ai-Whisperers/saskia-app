# Dependabot — Sazon RMS

**Last updated:** 2026-10-09
**Owner:** Ivan (operator)
**Source config:** `.github/dependabot.yml`

## What's already configured

The repo has Dependabot enabled for two ecosystems:

| Ecosystem | Schedule | What's covered | Auto-merge? |
|---|---|---|---|
| **uv** (Python deps via `pyproject.toml` + `uv.lock`) | Weekly Monday 09:00 | runtime + dev deps, patches + minors grouped, majors skipped | No (manual review) |
| **github-actions** | Weekly Monday | GH Actions versions (`actions/checkout`, `astral-sh/setup-uv`, etc.) | No (manual review) |

The Dependabot PRs land as `deps:` (uv) or `ci:` (actions) prefix commits, with the `dependencies` and `automated` labels.

## What's NOT yet covered

| Ecosystem | Could add? | Why we haven't |
|---|---|---|
| **Docker** (`Dockerfile`) | Yes | One Dockerfile; rarely changes base image |
| **postgres** (image version in `smoke.yml`, `security-zap.yml`) | Yes | We pin to `16-alpine` deliberately; major bump is a sprint decision |
| **pre-commit** (`.pre-commit-config.yaml`) | Yes | Pre-commit has its own auto-update; Dependabot config would conflict |

## Policy for Dependabot PRs

The repo follows **pin-minor, bump-major** (see `docs/ci/toolchain-versions.md` §"Version policy"):

- **Patch + minor** — auto-grouped into 1 PR per ecosystem. **Merge within 1 week** of the PR opening, after:
  1. CI passes (all 4 required checks per `branch-protection.md`)
  2. The changelog of the bumped dep is skimmed (look for deprecations)
  3. `uv run pytest -n 2 --dist=loadscope` runs clean locally
- **Major** — Dependabot is configured to **skip** major version bumps (see `ignore:` block in `dependabot.yml`). Major bumps are a sprint decision: create a manual PR, run a full audit.

## What to do when a Dependabot PR is opened

1. **Look at the changelog** of the bumped dep. Common ones:
   - **fastapi**: deprecate `@app.on_event("startup")` in favor of `lifespan` context manager (already done in Sazon)
   - **sqlalchemy**: 2.0 → 2.1 (current is 2.0.x; lock to <2.2)
   - **pydantic**: 2.9 → 2.10 is safe; 2.x → 3.x would be a sprint
2. **Run the local suite** (the GH Actions suite is the same, but local is faster):
   ```bash
   uv run pytest -n 2 --dist=loadscope --no-cov
   ```
3. **If CI is red**, investigate. Common causes:
   - Test fixture uses an old API (`pytest-asyncio` mode change, etc.)
   - Deprecation warning became an error (typical in sqlalchemy 2.x)
   - The bump is part of a series; need to take 2 minor bumps in sequence
4. **If local + CI both green**, merge.

## When to disable Dependabot

Don't. Even in a small repo, the 1-2 hours/month saved by automated patches is worth more than the 5 minutes/month of reviewing PRs.

If a Dependabot PR keeps failing because the dep has a known regression that the maintainers haven't fixed, the action is:
1. Add a `pin` to the previous version in `pyproject.toml` with a comment explaining why
2. Add the dep to the `ignore:` block in `dependabot.yml` with a `version-update:semver-minor` filter
3. Open a manual tracking issue

## Alternatives we considered and rejected

| Tool | Why not |
|---|---|
| **Renovate** | More powerful (grouping, scheduling, auto-merge) but requires self-hosting or a SaaS sub. Dependabot is free. |
| **Snyk** | Adds vuln intel, but the free tier caps scans; the Sazon budget doesn't cover it. |
| **GitHub-native Dependabot security alerts** | Already enabled (the dependency graph workflow in the audit shows it green). Different from Dependabot version PRs. |

## References

- `.github/dependabot.yml` (the config)
- `docs/ci/toolchain-versions.md` (the version policy)
- https://docs.github.com/en/code-security/dependabot/dependabot-version-updates
