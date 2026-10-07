"""TDD test for white-on-white bug audit (2026-10-06c).

The previous polish fixes used `color: var(--color-text, #111827)` to
ensure dark text on light callouts. But CSS variable fallbacks are only
applied when the variable is UNDEFINED — when --color-text IS defined
(as it is in :root[data-theme="dark"] = #f3f4f6 / gray-100), the
fallback is ignored and the text becomes near-white on the light
callout. Result: invisible body text on every soft-bg card I added.

This test now does a smarter scan: it only flags combinations where
the SAME element uses a light color (white / near-white) AND a light
background (soft-* / surface-subtle / cream). When the color and bg
are both theme-aware via var(--color-*) and they swap together (light
bg → dark text, dark bg → light text), it's correct. When they're
hardcoded to disagree with the theme (e.g., #fff on --color-text-muted
which is light gray in dark), it's a bug.

The previous version of this test was too aggressive — it flagged
`color: white` on `background: var(--color-danger)` as a bug, but in
dark mode --color-danger is #dc2626 (red) and white text on red is
fine.
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"


# Light backgrounds — colors that are white-ish in both themes.
LIGHT_BACKGROUND_PATTERNS = [
    r"--color-info-soft",
    r"--color-warn-soft",
    r"--color-success-soft",
    r"--color-danger-soft",
    r"--color-surface-subtle",
    r"--color-surface",
    r"--color-bg",
    r"--cream",
    r"#dbeafe\b",
    r"#fef3c7\b",
    r"#dcfce7\b",
    r"#fee2e2\b",
]

# Near-white text colors that would be invisible on a light bg.
LIGHT_TEXT_PATTERNS = [
    r"color:\s*var\(--color-text\)\b",
    r"color:\s*var\(--color-text,\s*#\d+\)",  # CSS fallback is ignored when var is defined
    r"color:\s*#fff\b",
    r"color:\s*white\b",
    r"color:\s*var\(--gray-100\)",
    r"color:\s*#f3f4f6\b",
    r"color:\s*#d1d5db\b",
    r"color:\s*#e5e7eb\b",
]


def _attr_on_same_element(html: str, color_attr: str, bg_attr: str) -> list[tuple[int, str]]:
    """Find elements where both attributes are on the SAME tag.

    Naive: walk the HTML and look at every <tag ... > opening, then
    check if it contains both a color regex match and a bg regex match.
    """
    results = []
    tag_re = re.compile(r"<([\w-]+)([^>]*?)/?>", re.DOTALL)
    for m in tag_re.finditer(html):
        attrs = m.group(2)
        line_no = html.count("\n", 0, m.start()) + 1
        for color_pat in LIGHT_TEXT_PATTERNS:
            if re.search(color_pat, attrs):
                for bg_pat in LIGHT_BACKGROUND_PATTERNS:
                    if re.search(bg_pat, attrs):
                        snippet = m.group(0).strip()[:120]
                        results.append((line_no, snippet))
                        break
                break
    return results


def _scan_style_blocks(html: str) -> list[tuple[int, str]]:
    """Find CSS rules where the same selector block has light text + light bg.

    Walks every `<style>...</style>` block (inline style sheets are
    common in templates). For each rule like `selector { color: X;
    background: Y }`, checks if X is light and Y is light.
    """
    results = []
    style_re = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL)
    rule_re = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
    for style_m in style_re.finditer(html):
        css_body = style_m.group(1)
        css_start = style_m.start(1)
        for rule_m in rule_re.finditer(css_body):
            selector = rule_m.group(1).strip()
            body = rule_m.group(2)
            # Check that BOTH are in the SAME rule body
            light_color = any(re.search(p, body) for p in LIGHT_TEXT_PATTERNS)
            light_bg = any(re.search(p, body) for p in LIGHT_BACKGROUND_PATTERNS)
            if light_color and light_bg:
                # Approximate line number
                line_no = html.count("\n", 0, css_start + rule_m.start()) + 1
                results.append((line_no, f"{selector} {{ ... }}"))
    return results


class TestWhiteOnWhiteAudit:
    """Audit every soft-bg template for white-on-white text."""

    SOFT_BG_TEMPLATES = [
        "produccion.html",
        "produccion_haccp.html",
        "_components/tags.html",
        "cliente_editar.html",
        "receta_form.html",
    ]

    def test_no_white_text_on_light_backgrounds(self):
        """Every template must NOT have any element where light text
        color is paired with a light background — that combination
        is unreadable."""
        offenders: list[str] = []
        for name in self.SOFT_BG_TEMPLATES:
            path = TEMPLATE_DIR / name
            if not path.exists():
                continue
            html = path.read_text()
            # Scan inline-styled elements
            for lineno, snippet in _attr_on_same_element(html, "color", "background"):
                offenders.append(f"{name}:{lineno}: inline elem/attr: {snippet}")
            # Scan <style> blocks
            for lineno, snippet in _scan_style_blocks(html):
                offenders.append(f"{name}:{lineno}: css rule: {snippet}")
        assert not offenders, "white-on-white bugs found:\n" + "\n".join(offenders)

    def test_soft_callouts_use_hard_dark_color(self):
        """Specifically: the 3 elements I patched in f2e3c18 + e9b89d9
        must use a HARD dark color (e.g., #111827), not var(--color-text).
        The original bug: var(--color-text, #111827) — CSS fallback is
        ignored when the var is defined."""
        text = (TEMPLATE_DIR / "produccion.html").read_text()
        for keyword in [
            "Sin producción planificada",
            "Cómo se calcula",
            "Verificá que haya ventas registradas",
        ]:
            idx = text.find(keyword)
            assert idx != -1, f"missing element: {keyword}"
            snippet = text[max(0, idx - 700) : idx]
            # The surrounding div must NOT use var(--color-text)
            for pattern in LIGHT_TEXT_PATTERNS:
                matches = re.findall(pattern, snippet)
                assert not matches, (
                    f"white-on-white in {keyword}: pattern={pattern}\n"
                    f"matches: {matches}\n"
                    f"snippet tail: {snippet[-300:]}"
                )

    def test_soft_callouts_visible_in_dark_theme(self):
        """Simulate dark theme: --color-text = #f3f4f6. The 3 patched
        callouts must NOT inherit or use that color directly (because
        it would be white on the soft blue tint)."""
        # We can't easily run a real browser in unit tests, but we
        # can check that the inline styles use hard #111827 instead
        # of var(--color-text).
        text = (TEMPLATE_DIR / "produccion.html").read_text()
        for keyword in [
            "Sin producción planificada",
            "Cómo se calcula",
            "Verificá que haya ventas registradas",
        ]:
            idx = text.find(keyword)
            assert idx != -1, f"missing element: {keyword}"
            # Look for "color: #111827" in the surrounding 700 chars
            snippet = text[max(0, idx - 700) : idx]
            assert "color: #111827" in snippet, (
                f"{keyword} must use hard #111827, not var(--color-text). "
                f"Snippet tail:\n{snippet[-400:]}"
            )


class TestTemplateCount:
    """Verify the audit scanned the right files (smoke test)."""

    def test_templates_exist(self):
        names = TestWhiteOnWhiteAudit.SOFT_BG_TEMPLATES
        for name in names:
            assert (TEMPLATE_DIR / name).exists(), f"missing: {name}"
