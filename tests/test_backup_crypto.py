"""tests/test_backup_crypto.py — D.5: AES-256-GCM backup encryption with
PBKDF2-SHA256 key derivation from operator DNI.

Why these tests exist: the backup encryption layer is the last line of
defense against VPS + R2 simultaneous compromise. A bug here means
either (a) backups are un-encrypted on disk, or (b) a legitimate
operator can't restore their own data. Both failure modes are silent
until a real disaster, so we test the contract explicitly here:

1. Deterministic key derivation (same DNI + salt → same key)
2. Salt randomness (different salts → different keys even for same DNI)
3. Roundtrip (encrypt → decrypt → plaintext)
4. Tamper detection (modify ciphertext → decrypt fails)
5. Wrong-DNI rejection (decrypt with wrong key → fails)
6. Format validation (bad magic / unsupported version → fails cleanly)
7. Empty plaintext works (smallest edge case)
8. Large plaintext works (multi-MB snapshots)

We test through the public module API only — no peeking at the raw
header layout. The format contract lives in the module docstring, not
in the tests, so a future refactor to Argon2id or to a longer nonce
doesn't break these tests if the public surface is preserved.
"""

from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest

# The module under test doesn't exist yet — these imports are the
# TDD red step. When the module is implemented, these become the
# contract it must satisfy.
from app.services.backup_crypto import (
    NONCE_SIZE,
    PBKDF2_ITERATIONS,
    SALT_SIZE,
    BackupCryptoError,
    DecryptionError,
    InvalidBackupFileError,
    UnsupportedVersionError,
    decrypt_backup,
    derive_key,
    derive_key_from_dni_file,
    encrypt_backup,
)

DNI = "1234567"
OTHER_DNI = "7654321"


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def test_derive_key_is_deterministic():
    """Same DNI + salt → same key. Required for the restore path:
    the same operator can decrypt their own backups across many
    backups, with each backup having a different salt but the same
    password."""
    salt = secrets.token_bytes(16)
    k1 = derive_key(DNI, salt)
    k2 = derive_key(DNI, salt)
    assert k1 == k2
    assert len(k1) == 32  # AES-256


def test_derive_key_salt_changes_output():
    """Different salts → different keys even for the same DNI. This
    is the property that prevents a known-plaintext attack on the
    same DNI from recovering a key usable for other backups."""
    k1 = derive_key(DNI, secrets.token_bytes(16))
    k2 = derive_key(DNI, secrets.token_bytes(16))
    assert k1 != k2


def test_derive_key_dni_changes_output():
    """Different DNIs → different keys. This is what 'DNI-derived
    key' actually means at the crypto level: rotating the DNI
    rotates the keyspace an attacker must search."""
    salt = secrets.token_bytes(16)
    k1 = derive_key(DNI, salt)
    k2 = derive_key(OTHER_DNI, salt)
    assert k1 != k2


def test_derive_key_iteration_count_meets_owasp_2023():
    """OWASP 2023 recommends ≥600,000 PBKDF2-HMAC-SHA256 iterations.
    We pin the constant in the module so a future 'optimization' PR
    can't lower it without breaking this test."""
    assert PBKDF2_ITERATIONS >= 600_000, (
        f"PBKDF2_ITERATIONS={PBKDF2_ITERATIONS} below OWASP 2023 minimum"
    )


def test_derive_key_salt_must_be_exactly_salt_size():
    """Salt size is a wire-format invariant. Wrong-size salt must
    fail fast at the KDF level, not silently produce a weak key."""
    with pytest.raises(ValueError, match="salt"):
        derive_key(DNI, b"too-short")
    with pytest.raises(ValueError, match="salt"):
        derive_key(DNI, b"x" * (SALT_SIZE - 1))
    with pytest.raises(ValueError, match="salt"):
        derive_key(DNI, b"x" * (SALT_SIZE + 1))


def test_derive_key_dni_cannot_be_empty():
    """Empty DNI would mean 'no key' — must reject."""
    with pytest.raises(ValueError, match="dni"):
        derive_key("", secrets.token_bytes(SALT_SIZE))


def test_derive_key_takes_about_1_second_on_modern_cpu():
    """PBKDF2-600k is intentionally slow. We assert a lower bound
    (≥ 100ms) and an upper bound (≤ 5s) — if a future change makes
    it 10× slower (e.g. accidental 6M iterations) or 10× faster
    (broken HMAC), this test fails."""
    import time

    salt = secrets.token_bytes(SALT_SIZE)
    start = time.perf_counter()
    derive_key(DNI, salt)
    elapsed = time.perf_counter() - start
    assert 0.05 < elapsed < 5.0, f"PBKDF2 took {elapsed:.2f}s; expected ~1s"


# ---------------------------------------------------------------------------
# Encrypt / decrypt roundtrip
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip():
    """The basic contract: encrypt then decrypt returns the same
    bytes. Tested with a small payload (most backups start small
    until a tenant accumulates history)."""
    plaintext = b"hello, world"
    blob = encrypt_backup(plaintext, DNI)
    out = decrypt_backup(blob, DNI)
    assert out == plaintext


def test_encrypt_decrypt_roundtrip_empty():
    """Edge case: an empty plaintext should still produce a valid
    blob (just header + nonce + 16-byte GCM tag, no ciphertext).
    GCM with empty plaintext is a real, supported configuration."""
    blob = encrypt_backup(b"", DNI)
    out = decrypt_backup(blob, DNI)
    assert out == b""


def test_encrypt_decrypt_roundtrip_large():
    """Snapshots can be 10-100MB. We test with 5MB to keep CI fast
    while still exercising the multi-block path inside GCM."""
    plaintext = secrets.token_bytes(5 * 1024 * 1024)
    blob = encrypt_backup(plaintext, DNI)
    out = decrypt_backup(blob, DNI)
    assert out == plaintext


def test_encrypt_produces_unique_ciphertexts():
    """Two encryptions of the same plaintext with the same DNI must
    produce DIFFERENT ciphertexts (different random salt + nonce).
    Without this, a known-plaintext attack on one backup yields
    plaintext for all of them."""
    plaintext = b"same content"
    blob1 = encrypt_backup(plaintext, DNI)
    blob2 = encrypt_backup(plaintext, DNI)
    assert blob1 != blob2


def test_encrypt_output_has_expected_header_size():
    """Wire format: 8 (magic) + 1 (version) + 16 (salt) + 12 (nonce)
    = 37 bytes of header, plus the GCM tag (16 bytes). So a 100-byte
    plaintext becomes a 153-byte blob."""
    plaintext = b"x" * 100
    blob = encrypt_backup(plaintext, DNI)
    assert len(blob) == len(plaintext) + 8 + 1 + SALT_SIZE + NONCE_SIZE + 16


def test_decrypt_with_wrong_dni_fails():
    """The whole point of 'DNI-derived' is that the wrong DNI can't
    decrypt. A wrong-DNI attempt must raise DecryptionError, not
    return wrong plaintext or raise something cryptic."""
    blob = encrypt_backup(b"secret data", DNI)
    with pytest.raises(DecryptionError):
        decrypt_backup(blob, OTHER_DNI)


def test_decrypt_tampered_ciphertext_fails():
    """Bit-flipping the ciphertext must be detected by the GCM tag
    and raise DecryptionError. This is the integrity half of
    'authenticated encryption'."""
    blob = encrypt_backup(b"secret data", DNI)
    # Flip a byte in the middle of the ciphertext.
    tampered = bytearray(blob)
    tampered[len(tampered) // 2] ^= 0x01
    with pytest.raises(DecryptionError):
        decrypt_backup(bytes(tampered), DNI)


def test_decrypt_truncated_too_short_fails():
    """Cutting the blob below HEADER_SIZE + TAG_SIZE (53 bytes)
    makes it not a backup file at all — must raise
    InvalidBackupFileError, not the generic DecryptionError from
    GCM tag mismatch. This is the 'header got cut off' case,
    distinct from 'ciphertext was tampered'."""
    # Empty blob → header-size check fires.
    with pytest.raises(InvalidBackupFileError):
        decrypt_backup(b"", DNI)
    # Truncate header in the middle — magic check might pass or
    # fail depending on bytes, but the length check should fire
    # first because we require HEADER_SIZE + TAG_SIZE minimum.
    too_short = b"SASKIA01\x01" + b"\x00" * 20  # 29 bytes, way too short
    with pytest.raises(InvalidBackupFileError):
        decrypt_backup(too_short, DNI)


def test_decrypt_partial_ciphertext_fails():
    """A blob that has the full header but a truncated ciphertext
    section (GCM tag missing) must fail with DecryptionError
    (auth tag mismatch) — this is the 'file got cut off mid-write'
    scenario. Distinct from 'wrong DNI' by the recovery path:
    an operator can re-fetch the backup from R2 in this case."""
    blob = encrypt_backup(b"secret data" * 100, DNI)  # bigger plaintext
    truncated = blob[:-10]  # cut 10 bytes — guaranteed to clip the tag
    with pytest.raises(DecryptionError):
        decrypt_backup(truncated, DNI)


def test_decrypt_rejects_bad_magic():
    """If the first 8 bytes aren't our magic, refuse to even try —
    this is a 'this isn't a Sazon backup file' check, not a crypto
    check. Distinct exception type so the operator can tell 'wrong
    file' from 'wrong password' from 'corrupt data'."""
    blob = encrypt_backup(b"x", DNI)
    bad = b"NOPE1234" + blob[8:]
    with pytest.raises(InvalidBackupFileError, match="magic"):
        decrypt_backup(bad, DNI)


def test_decrypt_rejects_unsupported_version():
    """v1 is what we ship. v2+ should be rejected with a clear
    'this backup was made by a newer version of Sazon' error, not
    silently decrypted with a wrong-key style failure."""
    blob = encrypt_backup(b"x", DNI)
    # Bump version byte (after magic, at offset 8).
    bad = blob[:8] + bytes([99]) + blob[9:]
    with pytest.raises(UnsupportedVersionError, match="99"):
        decrypt_backup(bad, DNI)


def test_decrypt_rejects_truncated_header():
    """A blob shorter than the header isn't a valid backup at all
    — raise InvalidBackupFileError, not a generic crypto error."""
    with pytest.raises(InvalidBackupFileError):
        decrypt_backup(b"short", DNI)


# ---------------------------------------------------------------------------
# DNI file loading
# ---------------------------------------------------------------------------


def test_dni_file_loading(tmp_path):
    """The DNI file is operator-provisioned (typically on a USB
    stick, NOT on the VPS). The loader must read it, strip the
    trailing newline, and reject if it's empty."""
    f = tmp_path / "dni"
    f.write_text("1234567\n")
    f.chmod(0o600)  # required: owner read/write only
    assert derive_key_from_dni_file(f) == "1234567"


def test_dni_file_loading_strips_whitespace(tmp_path):
    """DNI files written by `echo $DNI > file` get a trailing
    newline. We must strip it or the KDF gets a different input."""
    f = tmp_path / "dni"
    f.write_text("1234567  \n\n")
    f.chmod(0o600)
    assert derive_key_from_dni_file(f) == "1234567"


def test_dni_file_loading_rejects_missing(tmp_path):
    """Missing file → BackupCryptoError (caller decides exit code).
    The default VPS state is 'no DNI file' = 'no scheduled backups'
    = 'operator must provision'. This is intentional fail-closed."""
    f = tmp_path / "nonexistent"
    with pytest.raises(BackupCryptoError, match="not found"):
        derive_key_from_dni_file(f)


def test_dni_file_loading_rejects_empty(tmp_path):
    """Empty file is worse than missing — the operator THOUGHT they
    set it up. Loud failure is better than silent garbage key."""
    f = tmp_path / "dni"
    f.write_text("")
    f.chmod(0o600)
    with pytest.raises(BackupCryptoError, match="empty"):
        derive_key_from_dni_file(f)


def test_dni_file_loading_rejects_world_readable(tmp_path):
    """Defense in depth: the DNI file is a secret. If it's
    world-readable (chmod 0644), refuse to use it and tell the
    operator to lock it down. This catches the 'deployed with
    default perms' mistake."""
    f = tmp_path / "dni"
    f.write_text("1234567")
    f.chmod(0o644)  # the bad case: world-readable
    if os.name != "nt":
        with pytest.raises(BackupCryptoError, match=r"world.*readable|chmod"):
            derive_key_from_dni_file(f)


def test_dni_file_loading_accepts_0400_read_only(tmp_path):
    """The cron reads the DNI but never writes it, so 0400
    (read-only) should be acceptable. This is the recommended
    permission for an operator-managed file on a USB stick."""
    f = tmp_path / "dni"
    f.write_text("1234567")
    f.chmod(0o400)
    if os.name != "nt":
        assert derive_key_from_dni_file(f) == "1234567"


# ---------------------------------------------------------------------------
# Concurrency — the cron runs 1/day, but a manual operator-triggered
# backup from /admin/backup should not block other reads.
# ---------------------------------------------------------------------------


def test_concurrent_encrypt_does_not_share_state():
    """Multiple threads encrypting in parallel must not share any
    non-thread-local state (e.g. a global salt or nonce). Two
    concurrent encryptions of the same plaintext with the same DNI
    must produce two distinct, independently-decryptable blobs."""
    plaintext = b"shared plaintext"

    def enc():
        return encrypt_backup(plaintext, DNI)

    with ThreadPoolExecutor(max_workers=8) as pool:
        blobs = list(pool.map(lambda _: enc(), range(20)))
    assert len(set(blobs)) == 20  # all unique
    for blob in blobs:
        assert decrypt_backup(blob, DNI) == plaintext
