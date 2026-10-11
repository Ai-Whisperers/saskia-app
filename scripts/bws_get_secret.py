#!/usr/bin/env python3
"""bws_get_secret.py — BWS secret fetching with 429 retry logic.

This script implements the 3-attempt exponential backoff for BWS 429 errors
as specified in Plan 5.1.

Usage:
    python scripts/bws_get_secret.py SECRET_NAME

Exit codes:
    0   secret found and printed to stdout
    1   bws CLI missing or other error
    2   secret not found after retries
"""
import json
import os
import pathlib
import subprocess
import sys
import time

BWS_BIN = "/usr/local/bin/bws"
BWS_TOKEN_FILE = pathlib.Path("/etc/sazon/bws-token")

def bws_get_secret_with_retry(secret_name: str) -> str:
    """Fetch a secret with 3-attempt exponential backoff for 429 errors."""
    if not pathlib.Path(BWS_BIN).exists():
        print(f"ERROR: bws CLI not at {BWS_BIN}", file=sys.stderr)
        return None
    
    token = BWS_TOKEN_FILE.read_text().strip()
    
    for attempt in range(1, 4):  # 3 attempts
        r = subprocess.run(
            [BWS_BIN, "secret", "get", secret_name],
            env={**os.environ, "BWS_ACCESS_TOKEN": token},
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if r.returncode == 0:
            # Success - return the secret value
            return r.stdout.strip()
        
        # Check for 429 (Too Many Requests) error
        if "429" in r.stderr or "Too Many Requests" in r.stderr:
            if attempt < 3:  # Not the last attempt
                sleep_time = attempt * 5  # 5s, 10s, 15s
                print(f"BWS 429 error on attempt {attempt}, retrying in {sleep_time}s...", file=sys.stderr)
                time.sleep(sleep_time)
                continue
            else:
                print(f"BWS 429 error persisted after 3 attempts", file=sys.stderr)
                return None
        else:
            # Non-429 error - fail immediately
            print(f"BWS secret get FAILED: {r.stderr}", file=sys.stderr)
            return None
    
    return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} SECRET_NAME", file=sys.stderr)
        sys.exit(1)
    
    secret_name = sys.argv[1]
    secret_value = bws_get_secret_with_retry(secret_name)
    
    if secret_value is None:
        print(f"ERROR: Secret '{secret_name}' not found after retries", file=sys.stderr)
        sys.exit(2)
    
    print(secret_value)