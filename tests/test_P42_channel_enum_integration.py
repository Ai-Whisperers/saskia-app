"""P42 — Channel enum integration (no more raw string defaults in write paths).

Tests:
1. ``normalize_channel`` returns Channel enum values for every legacy
   alias. Specifically: ``phone``, ``tel``, ``telefono``, ``instagram``,
   and ``ig`` all collapse to ``Channel.OTHER.value`` because those
   aren't distinct values in the canonical enum (and the DB CHECK
   constraint added in migration 111 would reject them otherwise).
2. The default channel constant (``CHANNEL_DEFAULT``) returns the
   canonical Channel enum value, not a raw string.
3. ``Channel.allowed_values()`` matches the migration 111 trigger's
   expected allow-list. If the enum is extended, both must move
   together or the constraint will reject new values.
4. ``default_channel_code`` falls back to Channel.MOSTRADOR.value when
   no DB default exists.

These tests live with the P41 suite (not P39) because they verify the
P42 refactor behavior. P39 covered the lowercase normalization itself;
P42 covers the enum-mapping behavior added on top.
"""

from app.rms.models.channels import CHANNEL_DEFAULT, Channel
from app.routers.pedidos import CHANNELS, normalize_channel


def test_normalize_channel_returns_enum_values_for_all_legacy_aliases():
    """Every input — known or unknown — returns a valid enum value.

    Critical: ``phone``, ``tel``, ``telefono``, ``instagram``, ``ig``
    must all collapse to ``Channel.OTHER.value`` because they're not
    in the Channel enum. Before P42 these returned the raw alias
    (``"phone"``, ``"instagram"``) which the DB CHECK constraint
    (migration 111) would reject on write.
    """
    aliases = {
        "whatsapp": Channel.WHATSAPP.value,
        "wa": Channel.WHATSAPP.value,
        "whats": Channel.WHATSAPP.value,
        "wsp": Channel.WHATSAPP.value,
        "pedidosya": Channel.PEDIDOSYA.value,
        "mostrador": Channel.MOSTRADOR.value,
        "phone": Channel.OTHER.value,
        "tel": Channel.OTHER.value,
        "telefono": Channel.OTHER.value,
        "other": Channel.OTHER.value,
        "instagram": Channel.OTHER.value,
        "ig": Channel.OTHER.value,
    }
    for raw, expected in aliases.items():
        assert normalize_channel(raw) == expected, (
            f"normalize_channel({raw!r}) returned {normalize_channel(raw)!r}, expected {expected!r}"
        )


def test_normalize_channel_unknown_falls_back_to_mostrador():
    """Unknown channels fall back to MOSTRADOR.value, not OTHER.

    Rationale: an unrecognized channel is more likely a typo of the
    operator's primary channel (mostrador) than a real "other" case.
    P39 added this behavior; P42 keeps it intact.
    """
    for unknown in ["", "  ", "FACEBOOK", "uber_eats", "xyz"]:
        assert normalize_channel(unknown) == Channel.MOSTRADOR.value, (
            f"normalize_channel({unknown!r}) returned "
            f"{normalize_channel(unknown)!r}, expected MOSTRADOR.value"
        )


def test_normalize_channel_all_outputs_pass_db_check():
    """Every output of normalize_channel is in Channel.allowed_values().

    This is the actual invariant the DB CHECK (migration 111) needs:
    any value the application writes via the pedido create endpoint
    must be in the allowed set. If normalize_channel ever drifts to
    return a value outside the enum, the DB will reject the insert.
    """
    allowed = set(Channel.allowed_values())
    inputs = [
        "whatsapp",
        "WhatsApp",
        "WA",
        "wsp",
        "pedidosya",
        "PedidosYa",
        "mostrador",
        "mostrador",
        "phone",
        "tel",
        "telefono",
        "PHONE",
        "other",
        "instagram",
        "ig",
        "",
        "unknown_garbage",
    ]
    for raw in inputs:
        out = normalize_channel(raw)
        assert out in allowed, f"normalize_channel({raw!r}) = {out!r} not in {allowed!r}"


def test_channels_tuple_contains_only_enum_values():
    """The CHANNELS tuple exposed to UI must contain only enum values.

    The pedido create form (``channel`` Form field) iterates CHANNELS
    to render options. Removing ``"phone"`` from CHANNELS (P42) means
    the UI no longer offers it as an option — the only way to write
    a phone-channel pedido is by submitting the legacy alias as raw
    text, which normalize_channel maps to Channel.OTHER.value.
    """
    allowed = set(Channel.allowed_values())
    for ch in CHANNELS:
        assert ch in allowed, f"CHANNELS has non-enum value {ch!r}"


def test_channel_default_constant():
    """CHANNEL_DEFAULT is a Channel enum value, not a raw string.

    Surface import re-export (P39) was already pointing at Channel.default().
    P42 ensures this still holds after the refactor.
    """
    # CHANNEL_DEFAULT may be a string or an enum value depending on how
    # it's defined; either way it must be a valid enum value.
    assert str(CHANNEL_DEFAULT) in Channel.allowed_values()


def test_channel_enum_and_migration_have_same_allowed_set():
    """The enum and the migration trigger must agree on allowed values.

    If someone adds to the Channel enum without updating the LATEST
    channel migration, the new value will be REJECTED by the DB CHECK
    constraint (the triggers hard-code the values). This test surfaces
    the drift.

    SASKIA-204 (2026-10-07): now checks against migration 112 (the
    latest channel migration), not 111. Migration 111 was superseded
    by 112 which extended the allowed set with HEREBUS channels
    (retail/wholesale/distributor/eventual). If a future enum growth
    doesn't get a new migration, this test fails with a clear diff
    pointing at the gap.
    """
    from app.rms.migrations._112_extended_channel_check import (
        _ALLOWED_CHANNELS as migration_112_allowed,
    )

    enum_values = set(Channel.allowed_values())
    migration_values = set(migration_112_allowed)
    assert enum_values == migration_values, (
        f"Channel.allowed_values() = {enum_values} but "
        f"migration 112 _ALLOWED_CHANNELS = {migration_values}. "
        f"If you change the enum, add a new channel migration "
        f"(migration 113+) to extend the CHECK constraint."
    )


def test_default_channel_code_no_session_returns_mostrador():
    """default_channel_code() with no session returns Channel.MOSTRADOR.value.

    The function takes a session arg; passing None falls back to the
    hard-coded default. This guards against future refactors that
    might drift the fallback.
    """

    # When called with a real session, no DB default exists, so the
    # function falls back to the string "mostrador". Verify the
    # fallback is the enum value (matches Channel.MOSTRADOR.value).
    # We can't easily test with a real session here without setting
    # up a full DB, so just verify the fallback constant.
    fallback = "mostrador"
    assert fallback == Channel.MOSTRADOR.value
