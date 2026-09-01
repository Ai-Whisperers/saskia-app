"""app/services/r2_backup.py — encrypt SQLite snapshot + upload to R2.

Per dev plan §9 Task 7 + v2 §7 (R2 encrypted backups).

What this module does:
1. Read a SQLite snapshot file (or any blob) from disk.
2. Encrypt it with Fernet (AES-128-CBC + HMAC-SHA256, authenticated).
3. Upload the ciphertext to an S3-compatible bucket (Cloudflare R2 by default).
4. Provide a `download_and_decrypt()` reverse path for restore.

What it deliberately does NOT do:
- Key management beyond reading the key from disk/env. (Operator is
  responsible for storing the key securely — passphrase + key file.)
- Streaming encryption. (DBs are <100MB; whole-file is fine.)
- Server-side encryption. The bucket is configured at-rest by R2; we
  encrypt client-side too for the defense-in-depth property that no
  plaintext ever leaves the machine.

Storage abstraction:
- We define a small `Storage` protocol with `put(key, bytes)` and
  `get(key) -> bytes`. Real R2 uses boto3; tests use `InMemoryStorage`.
- This keeps us from depending on moto (heavy) for unit tests.

Config:
- All settings come from `app.rms.config` + the optional R2 TOML config file.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

from app.rms.config import R2_CONFIG_PATH


class StorageError(Exception):
    """Raised on any R2 / S3 upload-download failure."""


class DecryptionError(Exception):
    """Raised when downloaded ciphertext can't be decrypted."""


class Storage(Protocol):
    """Minimal S3-like storage interface. boto3 clients satisfy this."""

    def put(self, key: str, data: bytes) -> None:
        """Upload data under key. Overwrites if exists."""
        ...

    def get(self, key: str) -> bytes:
        """Download data by key. Raises KeyError if not found."""
        ...


@dataclass
class R2Settings:
    """R2 connection settings. Loaded from r2.toml or env vars."""

    endpoint_url: str
    bucket: str
    access_key_id: str
    secret_access_key: str


def _read_r2_config(path: Path) -> R2Settings | None:
    """Read R2 settings from TOML. Returns None if file doesn't exist.

    Expected format:
        [r2]
        endpoint_url = "https://<account>.r2.cloudflarestorage.com"
        bucket = "saskia-backups"
        access_key_id = "..."
        secret_access_key = "..."
    """
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise StorageError(f"Could not read R2 config at {path}: {exc}") from exc
    r2 = data.get("r2", {})
    required = ("endpoint_url", "bucket", "access_key_id", "secret_access_key")
    missing = [k for k in required if not r2.get(k)]
    if missing:
        raise StorageError(f"R2 config at {path} is missing required keys: {', '.join(missing)}")
    return R2Settings(
        endpoint_url=r2["endpoint_url"],
        bucket=r2["bucket"],
        access_key_id=r2["access_key_id"],
        secret_access_key=r2["secret_access_key"],
    )


def load_r2_settings() -> R2Settings | None:
    """Return R2 settings from disk, or None if no config exists.

    The app treats None as "R2 not configured" — backup continues with
    local-only exports and no error.
    """
    return _read_r2_config(R2_CONFIG_PATH)


def make_boto3_client(settings: R2Settings) -> "object":
    """Create a boto3 S3 client configured for Cloudflare R2.

    Imported lazily so tests don't need boto3 imported.
    """
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name="auto",  # R2 ignores region but boto3 requires it
    )


class Boto3Storage:
    """Storage adapter that wraps a boto3 S3 client + bucket name."""

    def __init__(self, client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, key: str, data: bytes) -> None:
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        except Exception as exc:
            raise StorageError(f"S3 put failed for {key}: {exc}") from exc

    def get(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:
            if "NoSuchKey" in str(exc) or "404" in str(exc):
                raise KeyError(key) from exc
            raise StorageError(f"S3 get failed for {key}: {exc}") from exc


class InMemoryStorage:
    """In-process dict-backed Storage. Useful for tests.

    Stores raw ciphertext — never decrypts. Mirrors the Boto3Storage interface.
    """

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self._data[key] = data

    def get(self, key: str) -> bytes:
        if key not in self._data:
            raise KeyError(key)
        return self._data[key]

    def keys(self) -> list[str]:
        return list(self._data.keys())


def load_or_create_key(key_file: Path) -> bytes:
    """Load a Fernet key from file, or generate + save one if missing.

    The key file is operator-managed. If the file doesn't exist, we generate
    a new key and write it. This makes first-run zero-config.

    Returns the raw Fernet key bytes (urlsafe-base64-encoded 32-byte key).
    """
    if key_file.exists():
        return key_file.read_bytes()
    new_key = Fernet.generate_key()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(new_key)
    try:
        key_file.chmod(0o600)  # owner read/write only
    except OSError:
        pass  # Windows doesn't support chmod semantics here
    return new_key


def encrypt_bytes(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt with Fernet. Returns ciphertext (urlsafe-base64 token)."""
    return Fernet(key).encrypt(plaintext)


def decrypt_bytes(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt Fernet ciphertext. Raises DecryptionError on auth failure."""
    try:
        return Fernet(key).decrypt(ciphertext)
    except InvalidToken as exc:
        raise DecryptionError(f"Invalid Fernet token: {exc}") from exc


def encrypt_and_upload(
    storage: Storage,
    key: bytes,
    remote_key: str,
    plaintext: bytes,
) -> bytes:
    """Encrypt `plaintext` and upload to `storage[remote_key]`.

    Returns the ciphertext bytes (also stored remotely).
    """
    ciphertext = encrypt_bytes(plaintext, key)
    storage.put(remote_key, ciphertext)
    return ciphertext


def download_and_decrypt(
    storage: Storage,
    key: bytes,
    remote_key: str,
) -> bytes:
    """Download ciphertext from `storage[remote_key]` and decrypt.

    Raises KeyError if remote_key is missing.
    Raises DecryptionError if the ciphertext is corrupt or wrong key.
    """
    ciphertext = storage.get(remote_key)
    return decrypt_bytes(ciphertext, key)


__all__ = [
    "Storage",
    "StorageError",
    "DecryptionError",
    "R2Settings",
    "load_r2_settings",
    "make_boto3_client",
    "Boto3Storage",
    "InMemoryStorage",
    "load_or_create_key",
    "encrypt_bytes",
    "decrypt_bytes",
    "encrypt_and_upload",
    "download_and_decrypt",
]
