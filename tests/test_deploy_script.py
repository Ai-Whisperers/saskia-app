"""tests/test_deploy_script.py — A14 (Phase 14, 2026-10-01).

Tests scripts/deploy.sh in --dry-run mode. The script touches the
real VPS (ssh + scp + docker service update), so without --dry-run
there is nothing to test that wouldn't be the deploy itself. The
dry-run prints every step without network calls, which we assert on.

What's covered:
1. --dry-run on a clean main exits 0 and includes all expected steps
2. --dry-run + --repo=DIR works against any worktree
3. Wrong branch → exits 1 with a clear "not on main" error
4. Uncommitted changes in app/ → exits 1 with a clear error
5. --help prints usage
7. Unknown flag → exits 2 (usage error)

NOTE: This file is in the saskia-app test suite but executes against
the deploy script in the WORKTREE the test runner is started in.
Both /opt/data/work/saskia-app and /opt/data/profiles/ivan/scratch/
saskia-app-work have the same deploy.sh; the test points at the one
shipped in the parent dir of the current worktree.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# Resolve the deploy.sh path: it's always at <worktree>/scripts/deploy.sh
DEPLOY_SH = Path(__file__).parent.parent / "scripts" / "deploy.sh"


def _run(args: list[str], repo: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run deploy.sh with optional --repo override. Returns CompletedProcess."""
    cmd = [str(DEPLOY_SH)]
    cmd.extend(args)
    if repo is not None:
        cmd.append(f"--repo={repo}")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,  # we want to assert on exit codes
    )


def test_help_exits_zero() -> None:
    """--help prints usage and exits 0."""
    if not DEPLOY_SH.exists():
        pytest.skip(f"deploy.sh not at {DEPLOY_SH}")
    result = _run(["--help"])
    assert result.returncode == 0
    assert "deploy.sh" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_unknown_flag_exits_2() -> None:
    """Unknown flag → usage error (exit 2)."""
    if not DEPLOY_SH.exists():
        pytest.skip(f"deploy.sh not at {DEPLOY_SH}")
    result = _run(["--bogus"])
    assert result.returncode == 2
    assert "unknown flag" in result.stdout.lower()


def test_dry_run_clean_main_repo(monkeypatch, tmp_path) -> None:
    """When main is clean and on main branch, --dry-run exits 0 and prints
    the expected sequence of steps without touching the network.
    """
    if not DEPLOY_SH.exists():
        pytest.skip(f"deploy.sh not at {DEPLOY_SH}")
    # Use the worktree this test is run from (parent of tests/).
    worktree = DEPLOY_SH.parent.parent
    # Skip if the worktree isn't on main (test environment).
    branch_proc = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if branch_proc.stdout.strip() != "main":
        pytest.skip(f"worktree is on '{branch_proc.stdout.strip()}', not 'main'")
    # Make sure no uncommitted changes in app/ or app/static/
    status_proc = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain", "--", "app", "app/static"],
        capture_output=True, text=True, check=False,
    )
    if status_proc.stdout.strip():
        pytest.skip("worktree has uncommitted changes in app/ or app/static/")
    # Now run dry-run.
    result = _run(["--dry-run"], repo=worktree)
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    # All expected steps must appear in output.
    assert "DRY: scp" in result.stdout, "expected scp step"
    assert "DRY: ssh" in result.stdout, "expected ssh step"
    assert "tar" in result.stdout, "expected tar step"
    assert "DRY-RESULT" in result.stdout, "expected dry-run result marker"
    assert "DRY: would curl" in result.stdout, "expected healthz verification (dry)"


def test_dry_run_wrong_branch_exits_1(monkeypatch, tmp_path) -> None:
    """When --repo points at a worktree on a non-main branch, exits 1
    with a clear error.
    """
    if not DEPLOY_SH.exists():
        pytest.skip(f"deploy.sh not at {DEPLOY_SH}")
    # Create a tiny fake repo on a non-main branch.
    fake = tmp_path / "fake_repo"
    fake.mkdir()
    subprocess.run(["git", "-C", str(fake), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(fake), "config", "user.email", "test@test"], check=True)
    subprocess.run(["git", "-C", str(fake), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(fake), "checkout", "-b", "feat/temp"], check=True)
    # Create a minimal file so the repo isn't empty.
    (fake / "README.md").write_text("test\n")
    subprocess.run(["git", "-C", str(fake), "add", "."], check=True)
    subprocess.run(["git", "-C", str(fake), "commit", "-q", "-m", "init"], check=True)
    # Run deploy.sh --dry-run --repo=fake. Should fail at branch check.
    result = _run(["--dry-run"], repo=fake)
    assert result.returncode == 1
    assert "not on main" in result.stdout.lower() or "not on main" in result.stderr.lower()


def test_dry_run_uncommitted_changes_exits_1(monkeypatch, tmp_path) -> None:
    """When --repo points at a main-branch worktree with uncommitted changes
    in app/, exits 1 with a clear error.

    We build this with a real-ish worktree: git init on main + an uncommitted
    app/foo.py file.
    """
    if not DEPLOY_SH.exists():
        pytest.skip(f"deploy.sh not at {DEPLOY_SH}")
    fake = tmp_path / "fake_repo_uncommit"
    fake.mkdir()
    subprocess.run(["git", "-C", str(fake), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(fake), "config", "user.email", "test@test"], check=True)
    subprocess.run(["git", "-C", str(fake), "config", "user.name", "Test"], check=True)
    # Stay on default branch (main/master).
    (fake / "README.md").write_text("test\n")
    subprocess.run(["git", "-C", str(fake), "add", "."], check=True)
    subprocess.run(["git", "-C", str(fake), "commit", "-q", "-m", "init"], check=True)
    # Create app/ subdir with an untracked file.
    (fake / "app").mkdir()
    (fake / "app" / "foo.py").write_text("# uncommitted\n")
    # Run dry-run. Should fail at the uncommitted-changes check.
    result = _run(["--dry-run"], repo=fake)
    assert result.returncode == 1
    out = result.stdout + result.stderr
    assert "uncommitted changes" in out.lower() or "commit first" in out.lower()


def test_dry_run_does_not_touch_network(monkeypatch) -> None:
    """Verify --dry-run doesn't actually invoke scp/ssh/curl/network.
    We do this by overriding PATH to a sandbox that contains only
    /bin/cat and /bin/echo. If deploy.sh tries to invoke scp/ssh/curl,
    subprocess.run in those tools will fail with "No such file or directory",
    surfacing a real problem.

    This test only runs on Unix and skips on platforms without /bin.
    """
    if not DEPLOY_SH.exists():
        pytest.skip(f"deploy.sh not at {DEPLOY_SH}")
    if not shutil.which("bash"):
        pytest.skip("no bash on PATH")
    # Use the worktree this test is run from.
    worktree = DEPLOY_SH.parent.parent
    branch_proc = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if branch_proc.stdout.strip() != "main":
        pytest.skip(f"worktree is on '{branch_proc.stdout.strip()}', not 'main'")
    status_proc = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain", "--", "app", "app/static"],
        capture_output=True, text=True, check=False,
    )
    if status_proc.stdout.strip():
        pytest.skip("worktree has uncommitted changes in app/ or app/static/")
    # Build a minimal PATH containing only bash + coreutils so scp/ssh/curl
    # are unfindable. This proves --dry-run never tries to invoke them.
    sandbox = tmp_path / "sandbox_bin"
    sys_path = sandbox / "bin"
    sys_path.mkdir(parents=True)
    for tool in ("bash", "sh", "cat", "echo", "md5sum", "git", "grep", "tar"):
        src = shutil.which(tool)
        if src:
            dst = sys_path / tool
            try:
                os.symlink(src, dst)
            except OSError:
                shutil.copy(src, dst)
    # Now run deploy.sh with this PATH. --dry-run must succeed; scp/ssh/curl
    # must not be invoked.
    env = os.environ.copy()
    env["PATH"] = str(sys_path)
    result = subprocess.run(
        [str(DEPLOY_SH), "--dry-run", f"--repo={worktree}"],
        capture_output=True, text=True, env=env, check=False,
    )
    assert result.returncode == 0, (
        f"--dry-run touched the network or a missing tool. "
        f"exit={result.returncode} stderr={result.stderr!r}"
    )
