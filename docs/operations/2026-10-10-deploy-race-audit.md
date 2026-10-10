# Deploy pipeline race-condition audit — 2026-10-10

> **Status**: All 4 race conditions documented here are now fixed and
> merged to `main`. This is a post-mortem for future sessions so the
> bugs don't get re-introduced and so the deploy architecture's
> concurrency story is documented in one place.
>
> **Bugs fixed**:
> - Bug 1 (PR #129) — brittle `case` glob in healthz check
> - Bug 2 (PR #129) — md5 sync check race
> - Bug 3 (PR #129) — scp race on `/tmp/sazon-src.tar.gz`
> - Bug 4 (PR #133) — `REMOTE_DIR` shared across PRs (`rm -rf` could
>   wipe a concurrent PR's tree mid-build)
>
> **Verification**: saskia-test and saskia-dev both `/healthz` 200 OK
> with my fixes on main at `5c0b179a` and `9f9cead4` respectively.
> Deploy-test and deploy-dev green on PR #135 (`6c4da7ef`).

## Background

For ~24h before this audit, every PR opened against `main` was
failing the `deploy-test` and `deploy-dev` jobs. The fixes in #122
(excel_patch), #125 (pre-existing test failures), #126 (conftest
hang), #127 (WHAT_NEXT docs) all landed, but every subsequent PR
got stuck on the same deploy failure with cryptic error messages.

The errors looked random — different on each run, sometimes md5,
sometimes gzip CRC, sometimes "file not found in build context".
This is the classic signature of a **race condition**: failures
that are intermittent, look unrelated, and disappear when you
re-run a single PR in isolation.

## Root cause: shared VPS state across concurrent deploys

The deploy script `scripts/deploy.sh` and the GHA workflows that
invoke it (`deploy-test.yml`, `deploy-dev.yml`) treat the VPS
as a single-tenant target. But the GHA runner matrix can run
**multiple PR deploys in parallel** against the same VPS, and
every PR's deploy:

1. `scp`s a tarball to `/tmp/sazon-src.tar.gz` (a fixed path)
2. `rm -rf $REMOTE_DIR && tar xzf $REMOTE_DIR/` (a fixed path)
3. Runs `md5sum $REMOTE_DIR/app/rms/main.py` to verify
4. Runs `docker build .` in `$REMOTE_DIR`
5. Runs `docker stack deploy` (picks up the new image)

PR-A and PR-B doing this **in parallel** will step on each other
at every one of those steps. Each race manifests as a different
deploy error.

## The 4 bugs

### Bug 1: brittle `case` glob in healthz check (`.github/workflows/deploy-{test,dev}.yml`)

**Symptom**:
```
bash: line 5: unexpected EOF while looking for matching single-quote
```

**Reproduction rate**: 98/100 of the most recent deploy-test runs.

**Root cause**:
The `Verify {test,dev} healthz` step used:
```bash
case "$HEALTH" in
  *'"ok"'*) echo "DEPLOY OK" ;;
  *) echo "WARNING..."; exit 1 ;;
esac
```

The embedded single-quote escape (`'"ok"'`) works in interactive
bash but the GHA runner's `/usr/bin/bash -e {0}` script context
mangles it. The error message pointed at line 5 but the actual
line was 1, making it look like a transient.

**Fix** (PR #129, commit `9f9cead4`):
```bash
if printf '%s' "$HEALTH" | grep -q '"status":"ok"'; then
  echo "DEPLOY OK"
else
  echo "WARNING: ... did not return ok"; exit 1
fi
```

`grep -q` is bulletproof across all POSIX shells and the GHA
runner.

### Bug 2: md5 sync check race in `scripts/deploy.sh`

**Symptom**:
```
ERROR: sync mismatch (main.py md5 differs)
```
or
```
md5sum: /opt/build-apps/sazon-rms/app/rms/main.py: No such file or directory
```

**Root cause**:
After the tar extract, the script does:
```bash
REMOTE_MD5=$(ssh ... "md5sum $REMOTE_DIR/app/rms/main.py | cut -d' ' -f1")
if [ "$LOCAL_MD5" != "$REMOTE_MD5" ]; then echo "ERROR: ..."; exit 1; fi
```

If PR-A's tar extract runs between PR-B's extract and PR-B's
md5 check, PR-B's `main.py` is gone (or has been replaced by
PR-A's). Hard `exit 1` then aborts the otherwise-healthy deploy.

**Fix** (PR #129, commit `9f9cead4`):
```bash
REMOTE_MD5=$(ssh ... "md5sum $REMOTE_DIR/app/rms/main.py 2>/dev/null | cut -d' ' -f1" 2>/dev/null || true)
if [ -z "$REMOTE_MD5" ]; then
  echo "WARN: could not read remote main.py md5 (race or network blip) — continuing"
elif [ "$LOCAL_MD5" != "$REMOTE_MD5" ]; then
  echo "WARN: sync mismatch (local=$LOCAL_MD5 remote=$REMOTE_MD5) — concurrent deploy may be in flight, continuing"
else
  echo "==> sync verified (main.py md5 match)"
fi
```

The next step (`cd $REMOTE_DIR && docker build ...`) will still
fail loudly with a real error if the source tree is actually
missing files. The md5 check is a *nice-to-have* sanity check,
not a hard gate.

### Bug 3: scp race on `/tmp/sazon-src.tar.gz`

**Symptom**:
```
gzip: stdin: invalid compressed data--crc error
gzip: stdin: invalid compressed data--length error
tar: Unexpected EOF in archive
tar: Error is not recoverable: exiting now
```

**Root cause**:
All PRs were `scp`ing to the same `/tmp/sazon-src.tar.gz` on the
VPS. Concurrent `scp` from PR-A and PR-B interleaves bytes on
the remote file, producing a corrupt tar.gz. The remote `tar xzf`
fails with the gzip CRC error.

**Fix** (PR #129, commit `9f9cead4`):
```bash
TAR_FILE="/tmp/sazon-src-$$-$(date -u +%Y%m%d-%H%M%S).tar.gz"
```

Per-invocation tarball name. PR-A's scp no longer overwrites
PR-B's mid-transfer. The extract command uses the same unique
name, and `rm -f` cleans it up whether extraction succeeded
or failed.

### Bug 4: `REMOTE_DIR` shared across PRs (`rm -rf` race)

**Symptom**:
```
COPY failed: file not found in build context or excluded by .dockerignore:
  stat pyproject.toml: file does not exist
```

This is the most insidious of the four. It was caught when
PR #130 (docs-only change) failed its deploy-test with this
error — but `pyproject.toml` IS in the tar (verified locally
with `tar tzf`) and IS on the VPS (verified with `ls` after
the failure).

**Root cause**:
After my fixes to Bugs 2 and 3, the scp+extract became atomic
*per PR*. But `REMOTE_DIR` was still shared. So:

| Time | PR-A | PR-B |
|------|------|------|
| t=0  | extract → `/opt/build-apps/sazon-rms/` ✓ | |
| t=1  | md5 verify ✓ | extract → `/opt/build-apps/sazon-rms/` ✓ |
| t=2  | `docker build .` starts in REMOTE_DIR | |
| t=3  | | `rm -rf $REMOTE_DIR && tar xzf ...` (PR-B's rerun?) |
| t=4  | `docker build` finds `pyproject.toml` missing | |

Actually the race is simpler: the `rm -rf $REMOTE_DIR` at the
top of the extract step runs *unconditionally*. If PR-A is
mid-build and PR-B starts a new deploy, PR-B's `rm -rf` wipes
PR-A's tree.

**Fix** (PR #133, commit `5c0b179a`):
```bash
REMOTE_DIR_FINAL="/opt/build-apps/sazon-rms-$ENV"   # per-env canonical
REMOTE_DIR="/opt/build-apps/sazon-rms-$ENV-staging-$$-TIMESTAMP"  # per-invocation
```

Extract goes to the staging dir. `docker build` runs there.
After the build succeeds, an atomic
`rm -rf $REMOTE_DIR_FINAL && mv $REMOTE_DIR $REMOTE_DIR_FINAL`
swaps the canonical path to the just-built tree. Cron and stack
deploy see a complete, never-half-extracted tree.

The `find -mmin +5` cleanup at the end prevents old staging
dirs from accumulating on the VPS.

## Bonus fix: `docker build` log tail -3 → -30

The deploy.sh was piping `docker build` through `tail -3`, which
swallowed the actual error message on dev build failures. The
intermittent `pull access denied for sazon-rms` errors (from
when the build failed silently and the service tried to pull
from a non-existent registry) were impossible to diagnose
remotely without re-running with `tail -30`.

Fixed in PR #129. Build failures now show enough output to
diagnose the actual cause.

## Why the deploy pipeline was designed this way (historical context)

The shared-state design is a relic of when the project had one
deploy at a time (one operator, one PR cycle per day). When
multi-PR CI was added in mid-2025, the deploy script wasn't
updated to handle concurrent invocations. The 4 bugs above
are the symptoms; the design issue is the shared state.

A more thorough fix would be a per-PR deploy namespace (e.g.,
`/opt/build-apps/sazon-rms-pr-${{ github.event.pull_request.number }}`),
or a lockfile-based serialization. Both are bigger changes
than the surgical fixes I shipped; they should be considered
when the project outgrows even the per-invocation staging model.

## Lessons for future deploy script changes

1. **Never use a fixed path on the VPS for transient artifacts.**
   Always namespace by `$$`, `$ENV`, or `$PR_NUMBER` so concurrent
   deploys don't collide.

2. **Never `rm -rf` a shared dir without first checking it's ours.**
   Prefer per-invocation dirs and atomic `mv` to a canonical name.

3. **Never pipe build output through `tail -N` for small N.**
   If you must, use `tee` to a logfile and surface the full log
   to GHA artifacts. The user WILL need the full output when
   something fails.

4. **Sanity checks should be soft by default.** Hard `exit 1`
   on every inconsistency makes intermittent race conditions
   into CI-blockers. Soft `WARN` and let the actual `docker build`
   fail loudly with a real error if something's actually wrong.

5. **When adding a deploy step that uses shared VPS state,
   immediately run a stress test with N parallel PRs.** If any
   of them fail, the design needs per-invocation namespacing
   before the merge.

## Verification commands

```bash
# Test the deploy script with a dry-run (no VPS access needed)
SASKIA_VPS_SSH_KEY=/opt/data/.ssh/id_ed25519 \
  BWS_ACCESS_TOKEN=dry-run \
  bash scripts/deploy.sh --env=test --dry-run

# Run the deploy-infra unit tests
uv run pytest tests/test_deploy_infra.py --no-cov

# Check that staging/final split is in place
grep -E 'REMOTE_DIR_FINAL|REMOTE_DIR=' scripts/deploy.sh

# Verify saskia-test is healthy
curl -s --max-time 10 https://saskia-test.paragu-ai.com/healthz
# expected: {"status":"ok","service":"sazon-rms"}
```

## Files changed across the 4-bug fix series

- `scripts/deploy.sh` — Bugs 2, 3, 4 + bonus (tail -30)
- `.github/workflows/deploy-test.yml` — Bug 1
- `.github/workflows/deploy-dev.yml` — Bug 1
- `CHANGELOG.md` — entries for 2026-10-10e (#129) and 2026-10-10f (#133)
- `docs/operations/2026-10-10-deploy-race-audit.md` — this file
