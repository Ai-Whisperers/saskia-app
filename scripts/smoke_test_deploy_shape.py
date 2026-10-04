#!/usr/bin/env python3
"""scripts/smoke_test_deploy_shape.py — boot the deploy-shape env and run health probes.

Used by CI to catch migration drift before deploy. Runs:
1. Boot ephemeral Postgres in Docker.
2. Build the app's Docker image (or use a slim Python image).
3. Run uvicorn with DATABASE_URL pointing at the ephemeral PG.
4. Probe /healthz, /healthz/db, /healthz/schema, /healthz/deps.
5. Verify the schema_version drift detector says drift=0.
6. Tear everything down.

This is the "deploy-shape env" smoke test: same Dockerfile, same DB
dialect (Postgres), same env-var expectations as production.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wait_for_port(host: str, port: int, *, timeout_s: int = 30) -> bool:
    """Wait until TCP accepts a connection."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=1):
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    return False


def main() -> int | None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        type=int,
        default=18000,
        help="Local port to bind uvicorn (default: 18000).",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker setup; assume Postgres is already running on localhost:5432.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip Docker build; run uvicorn directly with the local venv.",
    )
    args = parser.parse_args()

    pg_container = None
    app_process = None
    try:
        if not args.skip_docker:
            print("[smoke] starting ephemeral postgres…")
            r = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "--name",
                    "saskia-smoke-pg",
                    "-e",
                    "POSTGRES_USER=saskia",
                    "-e",
                    "POSTGRES_PASSWORD=saskia",
                    "-e",
                    "POSTGRES_DB=saskia",
                    "-p",
                    "5433:5432",
                    "postgres:16-alpine",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if r.returncode != 0:
                print(f"docker run failed: {r.stderr}")
                return 1
            pg_container = r.stdout.strip()
            # Wait for pg_isready
            for _ in range(30):
                rr = subprocess.run(
                    ["docker", "exec", pg_container, "pg_isready", "-U", "saskia"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if rr.returncode == 0:
                    print("[smoke] postgres is ready")
                    break
                time.sleep(1)
            else:
                print("postgres never became ready")
                return 1
            db_url = "postgresql+psycopg://saskia:saskia@localhost:5433/saskia"
        else:
            db_url = "postgresql+psycopg://saskia:saskia@localhost:5432/saskia"

        if args.skip_build:
            print(f"[smoke] starting uvicorn on :{args.port} (venv)…")
            env = os.environ.copy()
            env["DATABASE_URL"] = db_url
            # Only run migrations if the caller hasn't already done so
            # (e.g., a pre-provision step that called create_all and
            # seeded app_meta with the head version).
            env.setdefault("AIW_SASKIA_RUN_MIGRATIONS", "1")
            env["PORT"] = str(args.port)
            env["BIND_HOST"] = "127.0.0.1"
            app_process = subprocess.Popen(
                [
                    "uv",
                    "run",
                    "uvicorn",
                    "app.rms.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.port),
                ],
                env=env,
                cwd=str(ROOT),
            )
        else:
            print("[smoke] building docker image…")
            r = subprocess.run(
                ["docker", "build", "-t", "saskia-rms:smoke", str(ROOT)],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if r.returncode != 0:
                print(f"docker build failed:\n{r.stderr}")
                return 1
            print(f"[smoke] starting container on :{args.port}…")
            app_process = subprocess.Popen(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "--name",
                    "saskia-smoke-app",
                    "-p",
                    f"{args.port}:8000",
                    "-e",
                    f"DATABASE_URL={db_url}",
                    "-e",
                    "AIW_SASKIA_RUN_MIGRATIONS=1",
                    "-e",
                    "PORT=8000",
                    "-e",
                    "BIND_HOST=0.0.0.0",
                    "saskia-rms:smoke",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            time.sleep(2)

        if not wait_for_port("127.0.0.1", args.port, timeout_s=60):
            print(f"uvicorn never became ready on :{args.port}")
            return 1
        print(f"[smoke] uvicorn is ready on :{args.port}")

        # Probe health endpoints.
        for path in ("/healthz", "/healthz/db", "/healthz/deps", "/healthz/schema"):
            url = f"http://127.0.0.1:{args.port}{path}"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    body = r.read().decode()
                    status = r.status
            except urllib.error.HTTPError as e:
                status = e.code
                body = e.read().decode()
            except urllib.error.URLError as e:
                print(f"FAIL {path}: {e}")
                return 1
            print(f"[smoke] {path}: HTTP {status} body={body[:120]}")
            # /healthz/schema may return 500 if drift > 0 (test fails).
            if status >= 500:
                print(f"FAIL {path}: server error")
                return 1

        # Probe /healthz/deps for schema drift.
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{args.port}/healthz/schema", timeout=5
            ) as r:
                schema_body = r.read().decode()
            if '"drift":0' not in schema_body:
                print(f"FAIL /healthz/schema: drift != 0: {schema_body}")
                return 1
            print("[smoke] schema_version drift=0 ✓")
        except urllib.error.HTTPError as e:
            if e.code == 500:
                print("FAIL /healthz/schema: drift detected")
                return 1
            raise

        print("[smoke] OK ✓")
        return 0
    finally:
        if app_process:
            if isinstance(app_process, subprocess.Popen):
                app_process.terminate()
                try:
                    app_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    app_process.kill()
            else:
                # Docker container name
                subprocess.run(
                    ["docker", "stop", app_process.stdout.strip()],
                    capture_output=True,
                    timeout=30,
                )
        if pg_container:
            subprocess.run(
                ["docker", "stop", pg_container],
                capture_output=True,
                timeout=30,
            )


if __name__ == "__main__":
    sys.exit(main())
