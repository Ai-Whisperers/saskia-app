"""P-34.1: /clientes/{id} must show LTV headline in the page HEADER.

The page already shows lifetime Gs. deep in the body (line 313), but the
HEADER (around the H1) is missing the most important number. A cashier
who lands here from a call needs LTV visible without scrolling.

Fix: add a subheader line under the H1 with:
  - "Cliente desde YYYY-MM-DD"
  - "LTV Gs. 1.234.567"
  - "Tier (Bronce: 0–3 visitas)" — short helper text

Acceptance:
  - The H1's enclosing <div> contains a lifetime-Gs. formatted number
    (Gs. 0 minimum, even for a new customer with no sales).
  - The header area contains a tier explanation phrase
    (visitas / Gastó / lifetime / compró).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from app.rms.models import Customer


def test_cliente_detalle_ltv_in_header(client, session_factory):
    """P-34.1: LTV appears in the page header (within first 1500 chars after H1)."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        unique = f"cl-{uuid.uuid4().hex[:8]}"
        cust = Customer(
            name=unique,
            phone="+595 9XX",
            created_at=datetime.now(timezone.utc),
        )
        s.add(cust)
        s.commit()
        customer_id = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{customer_id}")
    assert r.status_code == 200
    body = r.text

    # Find the H1. The LTV must appear in the surrounding header block.
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.DOTALL)
    assert h1_match, "no <h1> in /clientes/{id}"
    h1_pos = h1_match.start()

    # The header is the next 2500 chars (covers the title row + sub-line area).
    header_section = body[h1_pos : h1_pos + 2500]

    # LTV (Gs. number) must appear in this header section.
    ltv_matches = re.findall(r"Gs\.\s*[\d.]+", header_section)
    assert ltv_matches, (
        f"LTV (Gs. <num>) not found in page header (first 2.5k chars after H1).\n"
        f"Header content: {header_section[:500]}"
    )

    # Tier explanation phrase in the same header.
    has_tier_help = any(
        phrase in header_section.lower()
        for phrase in ("visitas", "gastó", "lifetime", "ltv", "cliente desde")
    )
    assert has_tier_help, f"no tier explanation in header. Header content: {header_section[:500]}"
