"""tests/test_pedido_status_enum.py — verify PedidoStateMachine contract.

Phase 2A ticket #17: replace PEDIDO_TRANSITIONS dict + scattered
if/elif status checks with a PedidoStatus enum + PedidoStateMachine class.

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md OC-2, the current
pattern requires editing 5 places to add a new status. With the enum,
the central state machine owns the rule and call sites ask the machine
"can I transition from X to Y?" instead of comparing strings.

This test pins the BEHAVIOR (which transitions are valid) before the
refactor, so we can ship the enum with confidence the state machine
matches the dict's semantics.
"""
from __future__ import annotations

import pytest


# ─── Behavior locks — must hold both before and after refactor ──────────────


@pytest.mark.parametrize("from_status,to_status,allowed", [
    # From pending: can confirm or cancel
    ("pending", "confirmed", True),
    ("pending", "cancelled", True),
    ("pending", "ready", False),  # must go through confirmed
    ("pending", "fulfilled", False),
    # From confirmed: can mark ready or cancel
    ("confirmed", "ready", True),
    ("confirmed", "cancelled", True),
    ("confirmed", "pending", False),  # no backward
    ("confirmed", "fulfilled", False),  # must go through ready
    # From ready: can fulfill or cancel
    ("ready", "fulfilled", True),
    ("ready", "cancelled", True),
    ("ready", "confirmed", False),  # no backward
    ("ready", "pending", False),
    # fulfilled: terminal
    ("fulfilled", "pending", False),
    ("fulfilled", "cancelled", False),
    ("fulfilled", "ready", False),
    # cancelled: terminal
    ("cancelled", "pending", False),
    ("cancelled", "fulfilled", False),
])
def test_transition_table(from_status, to_status, allowed):
    """Each (from, to) pair must produce the expected allow/deny."""
    from app.routers.pedidos import PEDIDO_TRANSITIONS

    actual = to_status in PEDIDO_TRANSITIONS[from_status]
    assert actual is allowed, (
        f"{from_status} → {to_status}: expected allowed={allowed}, got {actual}"
    )


def test_all_statuses_have_transition_entry():
    """Every status in PEDIDO_STATUSES has a transitions entry."""
    from app.routers.pedidos import PEDIDO_STATUSES, PEDIDO_TRANSITIONS

    for status in PEDIDO_STATUSES:
        assert status in PEDIDO_TRANSITIONS, f"missing transitions for {status!r}"


def test_terminal_statuses_have_empty_transitions():
    """fulfilled and cancelled are terminal (no outgoing edges)."""
    from app.routers.pedidos import PEDIDO_TRANSITIONS

    assert len(PEDIDO_TRANSITIONS["fulfilled"]) == 0
    assert len(PEDIDO_TRANSITIONS["cancelled"]) == 0


def test_unknown_status_key_returns_keyerror():
    """Asking PEDIDO_TRANSITIONS for an unknown status raises."""
    from app.routers.pedidos import PEDIDO_TRANSITIONS

    with pytest.raises(KeyError):
        PEDIDO_TRANSITIONS["nonsense"]
