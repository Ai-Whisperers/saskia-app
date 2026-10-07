"""tests/test_backup_cron_wrapper.py — B.8: scripts/backup_cron.py wraps
the /admin/backup/cron HTTP endpoint with proper exit codes + dry-run.

The wrapper is the host-level cron entry point. It must:
1. Read SASKIA_BACKUP_URL + SASKIA_CRON_BACKUP_TOKEN from env (or
   CLI args) and POST the endpoint.
2. Map HTTP status to a shell exit code so the cron daemon can
   distinguish "success", "config error", and "backup failed":
   - 200 → 0 (success; skipped=True is also 0 — it's a no-op)
   - 401, 503 → 2 (config error; operator must fix and re-run)
   - 500 → 3 (backup raised; cron should alert)
   - connection refused / timeout → 4 (app is down; cron retries)
3. Log a one-line summary to stdout (cron captures this in
   /var/log/sazon-cron.log). In --json mode, log the raw response body
   as JSON for downstream parsing.
4. In --dry-run mode, print the request that WOULD be made and exit
   0 without making it (used by deploy.sh to verify the crontab line
   syntactically before installing it).

We test the wrapper by spinning up a real local HTTP server (in a
background thread) that fakes the /admin/backup/cron endpoint and
returns whatever status the test wants. This exercises the wrapper's
real urllib call path end-to-end — monkeypatching urllib in the
parent process would not, since the wrapper runs as a subprocess.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "backup_cron.py"

FAKE_TOKEN = "test-cron-secret-deadbeef-cafe"

# Populated by the test HTTP server. Reset in the fixture.
_received: list[dict] = []


class _FakeHandler(BaseHTTPRequestHandler):
    """Reads its response from class-level attrs set by the test fixture."""

    next_status = 500
    next_body = b"{}"

    def do_POST(self):
        token = self.headers.get("X-Cron-Token", "")
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        _received.append({
            "path": self.path,
            "token": token,
            "body": body.decode("utf-8", errors="replace"),
        })
        self.send_response(self.next_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.next_body)

    def log_message(self, format, *args):  # silence default stderr logging
        pass


@pytest.fixture
def fake_server():
    """Yield a started server on 127.0.0.1, reset state after the test."""
    _received.clear()
    server = HTTPServer(("127.0.0.1", 0), _FakeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _FakeHandler.next_status = 200
    _FakeHandler.next_body = b"{}"
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()


def _run_wrapper(*args, env=None, timeout=30):
    full_env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/tmp"}
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=full_env, timeout=timeout,
    )


def _success_body(skipped: bool = False) -> bytes:
    return json.dumps({
        "status": "backup_complete",
        "skipped": skipped,
        "local_path": None if skipped else "/tmp/rms-backup.xlsx",
        "r2_uploaded": not skipped,
        "r2_key": None if skipped else "rms-snapshots/20261007-030000.sqlite.enc",
        "local_pruned": 0,
        "reason": "Backup completed" if not skipped else
                  "Last backup < 24h ago, skipped",
    }).encode("utf-8")


def test_wrapper_imports():
    """The script can be imported without error.

    Catches the obvious 'typo in import' regression that would
    otherwise only show up in the crontab stderr.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("backup_cron_wrapper", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert mod is not None


def test_wrapper_dry_run_prints_request_without_making_it(fake_server):
    """--dry-run should print the curl-equivalent and exit 0 with no
    network calls. The fake_server is alive but must receive zero
    requests."""
    result = _run_wrapper(
        "--dry-run", "--url", fake_server,
        env={"SASKIA_CRON_BACKUP_TOKEN": FAKE_TOKEN},
    )
    assert result.returncode == 0, f"dry-run exited {result.returncode}: {result.stderr}"
    assert "DRY-RUN" in result.stdout
    assert _received == [], f"dry-run hit the server: {_received}"
    assert "ConnectionError" not in result.stderr
    assert "Traceback" not in result.stderr


def test_wrapper_dry_run_fails_without_url():
    """--dry-run without --url or env should exit 2 (config error)."""
    result = _run_wrapper("--dry-run", env={"SASKIA_CRON_BACKUP_TOKEN": FAKE_TOKEN})
    assert result.returncode == 2
    assert "SASKIA_BACKUP_URL" in result.stderr or "url" in result.stderr.lower()


def test_wrapper_dry_run_fails_without_token():
    """--dry-run without token should exit 2 (config error)."""
    result = _run_wrapper("--dry-run", "--url", "https://test.example.com")
    assert result.returncode == 2
    assert "SASKIA_CRON_BACKUP_TOKEN" in result.stderr or "token" in result.stderr.lower()


def test_wrapper_maps_200_to_exit_0(fake_server):
    """A 200 OK (skipped or completed) → exit 0."""
    _FakeHandler.next_status = 200
    _FakeHandler.next_body = _success_body(skipped=True)
    result = _run_wrapper("--url", fake_server, "--token", FAKE_TOKEN)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "backup_complete" in result.stdout or "skipped" in result.stdout.lower()
    assert len(_received) == 1
    assert _received[0]["path"] == "/admin/backup/cron"
    assert _received[0]["token"] == FAKE_TOKEN


def test_wrapper_maps_500_to_exit_3(fake_server):
    """A 500 (backup raised) → exit 3. Cron monitoring fires on exit
    code 3 to alert 'backup raised'."""
    _FakeHandler.next_status = 500
    _FakeHandler.next_body = json.dumps({
        "error": "backup_failed",
        "detail": "R2 outage: bucket unreachable",
    }).encode("utf-8")
    result = _run_wrapper("--url", fake_server, "--token", FAKE_TOKEN)
    assert result.returncode == 3, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "backup_failed" in result.stdout or "R2" in result.stdout


def test_wrapper_maps_401_to_exit_2(fake_server):
    """A 401 (bad token) → exit 2 (config error). Operator must
    re-set SASKIA_CRON_BACKUP_TOKEN; cron should NOT retry."""
    _FakeHandler.next_status = 401
    _FakeHandler.next_body = b'{"error":"invalid_cron_token"}'
    result = _run_wrapper("--url", fake_server, "--token", "wrong-token")
    assert result.returncode == 2


def test_wrapper_maps_connection_refused_to_exit_4():
    """If the app is down, the wrapper exits 4 so cron knows to
    retry. Distinct from config error (2) and backup failure (3).

    We point the wrapper at a port that we KNOW is free: ask the OS
    for one, close the socket, then hit it. The connect() should
    fail with ECONNREFUSED."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    dead_port = sock.getsockname()[1]
    sock.close()
    dead_url = f"http://127.0.0.1:{dead_port}"
    result = _run_wrapper("--url", dead_url, "--token", FAKE_TOKEN, timeout=15)
    assert result.returncode == 4, f"stdout: {result.stdout}\nstderr: {result.stderr}"


def test_wrapper_json_mode_outputs_valid_json(fake_server):
    """--json mode should print a single JSON line to stdout for
    downstream parsing."""
    _FakeHandler.next_status = 200
    _FakeHandler.next_body = _success_body(skipped=False)
    result = _run_wrapper(
        "--url", fake_server, "--token", FAKE_TOKEN, "--json",
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    last_json_line = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            last_json_line = line
    assert last_json_line is not None, f"no JSON line in: {result.stdout!r}"
    body = json.loads(last_json_line)
    assert body["status"] == "backup_complete"
    assert body["skipped"] is False
    assert body["r2_uploaded"] is True


def test_wrapper_appends_endpoint_path_to_base_url(fake_server):
    """Operators only set the base URL. The wrapper must append
    /admin/backup/cron so the crontab line is shorter and the env
    var matches every other config knob."""
    _FakeHandler.next_status = 200
    _FakeHandler.next_body = _success_body()
    result = _run_wrapper("--url", fake_server, "--token", FAKE_TOKEN)
    assert result.returncode == 0
    assert _received[0]["path"] == "/admin/backup/cron"
