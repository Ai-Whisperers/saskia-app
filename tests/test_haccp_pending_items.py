"""Tests for the expanded HACCP pending-lectures banner.

Sazon-Improvement v2 (2026-10-06) Phase E step 6: the /produccion
top banner now expands the missing items as inline chips
(e.g. "⚠️ 3 HACCP pendientes: Freezer1 AM · Freezer2 AM · Freezer1 PM")
so the cook doesn't have to click through to see which ones they
owe. Click still goes to /produccion/haccp for the form.

The helper lives in app.routers.produccion.analytics:
  expand_missing_items(missing: list[dict]) -> list[HaccpPendingItem]
where HaccpPendingItem = (location, weight) and weight is:
  - "AM" / "PM" — light chips (one shift missing)
  - "BOTH" — bold (location X is missing both shifts, urgent)

This is a pure refactor of the data + a small template change.
"""

from __future__ import annotations

from app.routers.produccion.analytics import (
    HaccpPendingItem,
    expand_missing_items,
)


def test_expand_missing_items_returns_list():
    """expand_missing_items takes the simple list and produces HaccpPendingItem."""
    items = expand_missing_items(
        missing=[{"location": "Freezer1", "shift": "AM"}],
    )
    assert isinstance(items, list)
    assert isinstance(items[0], HaccpPendingItem)


def test_single_shift_returns_normal_weight():
    """A single (location, shift) returns weight='AM' or 'PM'."""
    items = expand_missing_items(
        missing=[
            {"location": "Freezer1", "shift": "AM"},
            {"location": "Freezer2", "shift": "PM"},
        ]
    )
    assert items[0].weight == "AM"
    assert items[1].weight == "PM"


def test_both_shifts_for_location_returns_BOTH_weight():
    """If both AM and PM for the same location are missing,
    they merge into a single 'BOTH' chip."""
    items = expand_missing_items(
        missing=[
            {"location": "Freezer1", "shift": "AM"},
            {"location": "Freezer1", "shift": "PM"},
        ]
    )
    assert len(items) == 1
    assert items[0].weight == "BOTH"
    assert items[0].location == "Freezer1"


def test_one_location_BOTH_others_single():
    """Mixed: Freezer1 has both shifts, Freezer2 only AM."""
    items = expand_missing_items(
        missing=[
            {"location": "Freezer1", "shift": "AM"},
            {"location": "Freezer1", "shift": "PM"},
            {"location": "Freezer2", "shift": "AM"},
        ]
    )
    assert len(items) == 2
    # Order: BOTH comes first (most urgent), then single
    assert items[0].location == "Freezer1"
    assert items[0].weight == "BOTH"
    assert items[1].location == "Freezer2"
    assert items[1].weight == "AM"


def test_empty_missing_returns_empty_list():
    """No missing items → empty list."""
    items = expand_missing_items(missing=[])
    assert items == []


def test_HaccpPendingItem_dataclass():
    """The dataclass has the expected fields."""
    item = HaccpPendingItem(location="Freezer1", weight="BOTH")
    assert item.location == "Freezer1"
    assert item.weight == "BOTH"
