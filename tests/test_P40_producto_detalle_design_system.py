"""P-40: /productos/{id} should use the design-system classes, not Tailwind.

Audit: producto_detalle.html uses Tailwind-style classes
('flex flex-col md:flex-row', 'grid grid-cols-1 md:grid-cols-4',
'max-w-6xl', etc.) that aren't in the rest of the app's design system.

Fix: replace Tailwind classes with the design-system equivalents.

Acceptance:
  - No 'flex flex-col' / 'flex flex-row' (Tailwind flex) on /productos/{id}.
  - No 'grid grid-cols-N' (Tailwind grid) on /productos/{id}.
  - The metric-card markup is still present (we shouldn't break the
    existing functionality).
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import sessionmaker

from tests.factories import make_product


def test_producto_detalle_no_tailwind_classes(client, session_factory):
    """P-40: /productos/{id} uses design-system classes, not Tailwind."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        prod = make_product(s, name=f"ds-{uuid.uuid4().hex[:8]}")
        s.commit()
        product_id = prod.id
    finally:
        s.close()

    r = client.get(f"/productos/{product_id}")
    assert r.status_code == 200
    body = r.text

    # Tailwind flex patterns: "flex flex-col", "flex flex-row".
    tailwind_flex = re.findall(r'class="[^"]*\bflex flex-(?:col|row)\b[^"]*"', body)
    assert not tailwind_flex, f"found Tailwind flex patterns: {tailwind_flex[:3]}"

    # Tailwind grid: "grid grid-cols-N".
    tailwind_grid = re.findall(r'class="[^"]*\bgrid grid-cols-\d+\b[^"]*"', body)
    assert not tailwind_grid, f"found Tailwind grid patterns: {tailwind_grid[:3]}"

    # The metric-card class must still be present.
    assert "metric-card" in body, "metric-card markup missing (regression)"
