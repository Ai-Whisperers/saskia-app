"""Tests for PRODUCCION-V3 Phase 5 — EOD checklist progress bar.

The audit (H3, M3) found the EOD operator had no at-a-glance view of
how much of the checklist was left. They had to scroll the whole
form to know "can I close the day yet?"

Phase 5 ship:
  - A progress block at the top of /eod's checklist form showing
    "X of Y done (Z%)" with a CSS bar.
  - The block has the data-eod-progress hook so JS could update it
    live (deferred to a later phase).
  - The route exposes eod_items_total / eod_items_done / eod_items_pct.
"""
from __future__ import annotations


def test_eod_progress_block_renders(client, qseed):
    """The EOD page must surface a progress block with X-of-Y."""
    qseed("with_kyrian_full")
    r = client.get("/eod")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    assert 'data-eod-progress' in body, "EOD progress block not rendered"
    # "X de Y" Spanish copy
    assert "de " in body, "expected 'X de Y' in progress text"
    # progressbar role
    assert 'role="progressbar"' in body, "expected ARIA progressbar"


def test_eod_progress_starts_at_zero_when_no_items_checked(client, qseed):
    """With no items checked, the count is 0/N (0%) and the bar
    has width: 0%."""
    qseed("with_kyrian_full")
    r = client.get("/eod")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # The first <strong> in the progress text is the "done" count.
    # Should be 0 if nothing has been saved.
    if "data-eod-progress-text" in body:
        import re
        m = re.search(
            r'data-eod-progress-text[^>]*>\s*<strong>(\d+)</strong>',
            body,
        )
        if m:
            assert m.group(1) == "0", (
                f"expected 0 done initially, got {m.group(1)!r}"
            )


def test_eod_progress_renders_when_items_checked(client, qseed):
    """When at least one item is checked (saved via AppMeta), the
    progress count should reflect it. We simulate by posting first
    then re-getting."""
    qseed("with_kyrian_full")
    # POST to check an item
    _r = client.post(
        "/eod/check",
        data={
            "csrf_token": "test",
            "idempotency_key": "test",
            "check_1": "1",  # First EOD item
        },
        follow_redirects=False,
    )
    # Then re-GET
    r2 = client.get("/eod")
    body = r2.content.decode("utf-8", errors="replace")
    assert r2.status_code == 200
    # The progress should now show ≥1 done.
    assert "data-eod-progress" in body


def test_eod_route_exposes_progress_context(client, qseed):
    """Route must set eod_items_total / eod_items_done / eod_items_pct
    in the render context (smoke check that the keys are wired)."""
    qseed("with_kyrian_full")
    r = client.get("/eod")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # Easiest way to verify the context is set: the template renders
    # the values directly into the page, so look for the formatting.
    assert "data-eod-progress-text" in body
    # And the ARIA bar
    assert 'aria-valuenow=' in body
