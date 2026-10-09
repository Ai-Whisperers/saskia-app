#!/usr/bin/env python3
"""Render deploy/docker-stack.template.yml into a per-env stack file.

The template uses {{PLACEHOLDER}} substitution against the env row in
deploy/envs.yaml. The CSP, hostname, volume, middleware, and image tag
are all env-specific. The rendered output is byte-for-byte deterministic
given the same envs.yaml + template + Python version — important for
diffing what changed between deploys.

Secrets are NOT embedded in the rendered file. The template uses
`env_file: {{ENV_FILE}}` and the VPS-side deploy/write_env_file.py
populates /etc/sazon/.env.<env> from Bitwarden Secrets at deploy time.

Usage:
    python deploy/render_stack.py --env=prod > /tmp/docker-stack.prod.yml
    python deploy/render_stack.py --env=test
    python deploy/render_stack.py --env=dev --output=/tmp/docker-stack.dev.yml
"""

from __future__ import annotations

import argparse
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required. Install with: uv pip install pyyaml", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENVS_FILE = REPO_ROOT / "deploy" / "envs.yaml"
TEMPLATE_FILE = REPO_ROOT / "deploy" / "docker-stack.template.yml"

# Whitelist of envs. Adding a new env requires (a) a row in envs.yaml,
# (b) a Cloudflare CNAME, (c) a BWS secret set, (d) updating this list.
ALLOWED_ENVS = ("prod", "test", "dev")


def load_envs() -> dict:
    with open(ENVS_FILE) as f:
        return yaml.safe_load(f)


def render(env: str) -> str:
    if env not in ALLOWED_ENVS:
        print(f"ERROR: env must be one of {ALLOWED_ENVS}, got '{env}'", file=sys.stderr)
        sys.exit(2)
    envs = load_envs()
    row = envs[env]
    template = TEMPLATE_FILE.read_text()

    # Substitutions. The keys MUST exist in the env row or the template
    # will render an unfilled {{...}} and Docker will reject the stack.
    subs = {
        "ENV": env,
        "HOSTNAME": row["hostname"],
        "IMAGE_TAG_BASE": row["image_tag_base"],
        "STACK_NAME": row["stack_name"],
        "SERVICE_NAME": row["service_name"],
        "DATA_VOLUME": row["data_volume"],
        "LOGS_VOLUME": row["logs_volume"],
        "ROUTER_NAME": row["router_name"],
        "MIDDLEWARE_NAME": row["middleware_name"],
        "SERVICE_LB_NAME": row["service_lb_name"],
        "ENV_FILE": row["env_file"],
        "CSP": row["csp"],
        "FRAME_DENY": row["frame_deny"],
        "CPU_LIMIT": row["cpu_limit"],
        "MEMORY_LIMIT": row["memory_limit"],
        "CPU_RESERVATION": row["cpu_reservation"],
        "MEMORY_RESERVATION": row["memory_reservation"],
        # Per-env extra container env lines (optional). Rendered as
        # indented list items; empty when the env row has no extra_env.
        "EXTRA_ENV": "".join(
            f"      - {line}\n" for line in row.get("extra_env", [])
        ).rstrip("\n"),
    }

    # Sanity: every {{...}} in the template must be in the substitution
    # map. If we miss one, the rendered file will be syntactically
    # invalid YAML and docker will reject it with a confusing error.
    import re

    placeholders = set(re.findall(r"\{\{(\w+)\}\}", template))
    missing = placeholders - subs.keys()
    if missing:
        print(
            f"ERROR: template references placeholders not in envs.yaml: {sorted(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    rendered = template
    for k, v in subs.items():
        rendered = rendered.replace("{{" + k + "}}", v)
    return rendered


def main() -> int:
    p = argparse.ArgumentParser(description="Render a per-env stack file from the template.")
    p.add_argument("--env", required=True, choices=ALLOWED_ENVS, help="Target environment")
    p.add_argument("--output", help="Write to this file instead of stdout")
    p.add_argument(
        "--validate",
        action="store_true",
        help="Run docker-compose config to validate the rendered file (requires docker)",
    )
    args = p.parse_args()

    rendered = render(args.env)

    if args.output:
        pathlib.Path(args.output).write_text(rendered)
        print(f"wrote {args.output} ({len(rendered)} bytes)", file=sys.stderr)
    else:
        print(rendered)

    if args.validate:
        import subprocess

        r = subprocess.run(
            ["docker", "compose", "-f", args.output or "/dev/stdin", "config"],
            input=rendered if not args.output else None,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            print(f"docker compose config FAILED:\n{r.stderr}", file=sys.stderr)
            return r.returncode
        print("docker compose config: OK", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
