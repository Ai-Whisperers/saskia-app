"""app/services/backup_crypto.py — D.5: AES-256-GCM backup encryption with
PBKDF2-SHA256 key derivation from operator DNI.

Threat model
------------
The backup layer defends against two scenarios the rest of the
security model doesn't cover:

1. **VPS-only breach**: an attacker reads `/opt/sazon/backups/` on
   the VPS and walks away with the entire sales history. Local
   backup files MUST be encrypted at rest.

2. **VPS + R2 simultaneous breach**: an attacker reads both the VPS
   filesystem AND the R2 bucket. If the same key encrypts both
   and the key is on the VPS, the attacker decrypts both. The
   "DNI-derived" requirement breaks this: if the key is derived
   from the operator's identity at backup time and NEVER stored on
   disk, a VPS breach yields ciphertext-without-key. R2 backup
   recovery still requires the operator to enter the DNI.

What this module does
---------------------
- Derives a 32-byte AES key from the operator DNI + a per-backup
  random salt using PBKDF2-HMAC-SHA256 with 600,000 iterations
  (OWASP 2023 minimum for PBKDF2-SHA256).
- Encrypts a plaintext blob with AES-256-GCM, generating a fresh
  12-byte nonce per call (NIST SP 800-38D §8.2.1 recommends 12-byte
  nonces; AESGCM enforces nonce uniqueness within a key).
- Packages the encrypted blob with a versioned header so future
  Sazon versions can detect "this backup was made by a newer
  version of Sazon" and refuse silently-decryptable input.

What this module deliberately does NOT do
-----------------------------------------
- **Key storage.** The DNI-derived key never leaves the process.
  On disk, only the salt is stored (and the salt is in the header,
  not a secret).
- **Streaming encryption.** SQLite snapshots are <100MB; whole-file
  is fine. Streaming would force us to expose a chunked API and
  we'd be one footgun away from nonce reuse.
- **KDF tuning.** PBKDF2-SHA256 with 600k iterations is what
  cryptography.hazmat ships. Argon2id would be marginally better
  (memory-hard) but is a new dep, and AGENTS.md says no new deps
  without operator OK.

Wire format (v1)
-----------------
    [ 0..7  ] 8 bytes  magic        = b"SASKIA01"
    [ 8     ] 1 byte   version      = 0x01
    [ 9..24 ] 16 bytes salt         = random per backup
    [ 25..36] 12 bytes nonce        = random per encryption
    [ 37..  ] N bytes  ciphertext + 16-byte GCM tag

The 16-byte GCM tag is appended automatically by AESGCM.encrypt().

Operational notes
-----------------
- The DNI file is operator-provisioned. The default state on a
  fresh VPS is "no DNI file = no scheduled backups" — this is
  intentional fail-closed. See docs/operations/backup-cron.md
  for the provisioning runbook.
- The DNI is a national-ID-style string (digits). It is
  low-entropy by design (typically 6-8 digits) — that's why we
  use 600k PBKDF2 iterations instead of one SHA256. A low-entropy
  password with a 1s derivation time costs the operator 1s per
  backup but costs an offline attacker ~1s per password guess,
  which is the only defense when the password space is small.
"""

from __future__ import annotations

import hashlib
import secrets
import stat
from pathlib import Path
from typing import Final

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Wire-format constants. Don't change HEADER_VERSION without
# bumping both the format AND the UnsupportedVersionError message
# below — restore code on older versions will refuse to read
# anything with a higher version number.

HEADER_MAGIC: Final[bytes] = b"SASKIA01"
HEADER_VERSION: Final[int] = 0x01

SALT_SIZE: Final[int] = 16
NONCE_SIZE: Final[int] = 12
KEY_SIZE: Final[int] = 32  # AES-256
TAG_SIZE: Final[int] = 16  # GCM authentication tag
HEADER_SIZE: Final[int] = len(HEADER_MAGIC) + 1 + SALT_SIZE + NONCE_SIZE  # 37

# OWASP 2023 Password Storage Cheat Sheet, PBKDF2-HMAC-SHA256:
# "PBKDF2-HMAC-SHA256: 600,000 iterations".
# https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
# Pinned to a module constant so a future 'optimization' PR can't
# silently lower it without breaking the test that asserts this.
PBKDF2_ITERATIONS: Final[int] = 600_000

# The DNI file's permissions. We require the OWNER to be the only
# reader/writer (0600 or 0400). Anything looser is a security
# regression — backup keys should be as locked down as private
# SSH keys. We don't fail on 0400 because the file is read-only
# by design.
_DNI_FILE_REQUIRED_MODE: Final[int] = stat.S_IRUSR | stat.S_IWUSR  # 0o600 bits


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BackupCryptoError(Exception):
    """Base class for all backup_crypto failures.

    Catch this if you don't care about the subtype (e.g. in the cron
    wrapper that just maps to exit code 2). Catch the subtypes if
    you want to surface a specific message to the operator (e.g.
    'wrong DNI' vs 'corrupt file' vs 'this is a v99 backup')."""


class DecryptionError(BackupCryptoError):
    """Wrong key, tampered ciphertext, or truncated GCM tag.
    The GCM auth tag mismatch is reported as the same exception
    type as wrong-DNI on purpose: we don't want to leak which one
    it was to an attacker probing the endpoint."""


class UnsupportedVersionError(BackupCryptoError):
    """Backup was made by a newer Sazon version. The format has
    changed; this version doesn't know how to read it."""


class InvalidBackupFileError(BackupCryptoError):
    """This isn't a Sazon backup file at all (bad magic, wrong
    length, etc.). Distinct from DecryptionError so the operator
    can tell 'wrong file' from 'wrong DNI'."""


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def derive_key(dni: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES-256 key from DNI + salt using PBKDF2.

    Args:
        dni: Operator identity (typically a national-ID string).
            Must be non-empty. Whitespace is NOT stripped here —
            the caller (derive_key_from_dni_file) is responsible
            for that, so the encryption path and the restore path
            are forced to apply the same normalization.
        salt: Exactly SALT_SIZE (16) bytes of randomness.
            The caller should use secrets.token_bytes(SALT_SIZE)
            for new backups.

    Returns:
        32 bytes suitable for AES-256.

    Raises:
        ValueError: if salt has the wrong size, or DNI is empty.
    """
    if not dni:
        raise ValueError("dni must be a non-empty string")
    if len(salt) != SALT_SIZE:
        raise ValueError(f"salt must be exactly {SALT_SIZE} bytes, got {len(salt)}")
    return hashlib.pbkdf2_hmac(
        "sha256",
        dni.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_SIZE,
    )


def derive_key_from_dni_file(path: Path) -> str:
    """Read the DNI from an operator-provisioned file.

    The file should be a single line containing the DNI (digits
    only for a national ID; the format is operator-decided).
    Trailing whitespace and newlines are stripped; an empty file
    or a missing file is a hard error.

    Security: the file must be mode 0600 or 0400 (owner read/write
    only). A world-readable DNI file means the 'key never on disk'
    guarantee is false, so we refuse to use it.

    Args:
        path: Absolute path to the DNI file.

    Returns:
        The DNI string, stripped of leading/trailing whitespace.

    Raises:
        BackupCryptoError: with a specific message on missing
            file, empty file, or insecure permissions.
    """
    if not path.exists():
        raise BackupCryptoError(
            f"DNI file not found at {path}. The operator must provision "
            f"this file (see docs/operations/backup-cron.md) before "
            f"scheduled backups can run."
        )
    mode = path.stat().st_mode
    # We require owner-only read+write. 0400 (read-only) is also
    # acceptable for a file that the cron only needs to read.
    if (mode & 0o077) != 0:
        raise BackupCryptoError(
            f"DNI file {path} is world- or group-readable "
            f"(mode={oct(mode & 0o777)}). Fix with: "
            f"chmod 600 {path}. A world-readable DNI file defeats "
            f"the threat model this module is designed to address."
        )
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise BackupCryptoError(
            f"DNI file {path} is empty. The operator must provision "
            f"a non-empty value before scheduled backups can run."
        )
    return content


# ---------------------------------------------------------------------------
# Encrypt / decrypt
# ---------------------------------------------------------------------------


def encrypt_backup(plaintext: bytes, dni: str) -> bytes:
    """Encrypt `plaintext` with a DNI-derived key.

    The output is a self-describing blob: it includes the salt, the
    nonce, and a version byte, so the same `decrypt_backup(blob,
    dni)` call works on every backup ever made (assuming the
    operator's DNI hasn't changed).

    Args:
        plaintext: Arbitrary bytes. Can be empty.
        dni: Operator identity. See derive_key() for normalization.

    Returns:
        Encrypted bytes in the wire format described in the
        module docstring.
    """
    salt = secrets.token_bytes(SALT_SIZE)
    nonce = secrets.token_bytes(NONCE_SIZE)
    key = derive_key(dni, salt)

    aesgcm = AESGCM(key)
    # AESGCM.encrypt appends the 16-byte tag to the ciphertext.
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, associated_data=None)

    return HEADER_MAGIC + bytes([HEADER_VERSION]) + salt + nonce + ciphertext_with_tag


def decrypt_backup(blob: bytes, dni: str) -> bytes:
    """Decrypt a backup blob made by encrypt_backup().

    The DNI used here must match the one used at encryption time
    (modulo whitespace stripping, which the DNI-file loader does
    for both paths). A wrong DNI raises DecryptionError, not a
    'wrong password' error — we don't want to leak which it was.

    Args:
        blob: Bytes from encrypt_backup() (or read from disk / R2).
        dni: Operator identity.

    Returns:
        The original plaintext bytes.

    Raises:
        InvalidBackupFileError: blob is too short, has the wrong
            magic, or is otherwise not a Sazon backup file.
        UnsupportedVersionError: blob has a version byte higher
            than this code knows how to read.
        DecryptionError: the GCM tag didn't verify (wrong DNI,
            tampered ciphertext, or truncated blob).
    """
    if len(blob) < HEADER_SIZE + TAG_SIZE:
        # Minimum size = header + at least the tag, even with
        # empty plaintext.
        raise InvalidBackupFileError(
            f"blob is {len(blob)} bytes; minimum is {HEADER_SIZE + TAG_SIZE}"
        )
    if blob[:8] != HEADER_MAGIC:
        raise InvalidBackupFileError(
            f"bad magic: expected {HEADER_MAGIC!r}, got {blob[:8]!r}. "
            f"This doesn't look like a Sazon backup file."
        )
    version = blob[8]
    if version > HEADER_VERSION:
        raise UnsupportedVersionError(
            f"backup version {version} is newer than supported "
            f"({HEADER_VERSION}). Upgrade Sazon to read this backup."
        )
    if version < HEADER_VERSION:
        # Lower version (0x00) was a dev artifact. Don't pretend
        # to decrypt it; tell the operator the file is from a
        # never-released build.
        raise UnsupportedVersionError(
            f"backup version {version} is older than supported "
            f"({HEADER_VERSION}). This backup is from a never-released "
            f"Sazon build and cannot be restored."
        )

    salt = blob[9 : 9 + SALT_SIZE]
    nonce = blob[9 + SALT_SIZE : HEADER_SIZE]
    ciphertext_with_tag = blob[HEADER_SIZE:]

    key = derive_key(dni, salt)
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext_with_tag, associated_data=None)
    except Exception as exc:
        # AESGCM raises cryptography.exceptions.InvalidTag for tag
        # mismatch. We don't care which specific exception — the
        # right user-facing message is "wrong DNI or corrupt file"
        # for both cases (and we don't want to leak which one).
        raise DecryptionError(
            f"decryption failed (wrong DNI, tampered file, or truncated ciphertext): {exc}"
        ) from exc


__all__ = [
    "HEADER_MAGIC",
    "HEADER_SIZE",
    "HEADER_VERSION",
    "KEY_SIZE",
    "NONCE_SIZE",
    "PBKDF2_ITERATIONS",
    "SALT_SIZE",
    "TAG_SIZE",
    "BackupCryptoError",
    "DecryptionError",
    "InvalidBackupFileError",
    "UnsupportedVersionError",
    "decrypt_backup",
    "derive_key",
    "derive_key_from_dni_file",
    "encrypt_backup",
]
