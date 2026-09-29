"""Verify all destructive POST forms have js-confirm-form + CSRF token.

Catches regressions if a developer adds a new form without protection.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DESTRUCTIVE_PATTERNS = [
    r'/eliminar',
    r'/delete',
    r'/anular',
    r'/borrar',
    r'/cancel',
    r'/bulk-cancel',
]

EXEMPT_TEMPLATES = {
    # /login is CSRF-exempt per app/rms/csrf.py
    'app/templates/login.html',
}


def find_destructive_forms():
    forms = []
    for html in REPO.glob('app/templates/**/*.html'):
        if str(html.relative_to(REPO)) in EXEMPT_TEMPLATES:
            continue
        text = html.read_text(encoding='utf-8')
        for pattern in DESTRUCTIVE_PATTERNS:
            for m in re.finditer(rf'<form[^>]*action="[^"]*{pattern}[^"]*"', text):
                forms.append((str(html.relative_to(REPO)), m.group(0)))
    return forms


def test_all_destructive_forms_have_confirm():
    """Every destructive POST form must have js-confirm-form class."""
    forms = find_destructive_forms()
    missing = []
    for path, form_html in forms:
        text = (REPO / path).read_text(encoding='utf-8')
        idx = text.find(form_html)
        end = text.find('>', idx)
        form_open = text[idx:end + 1]
        if 'js-confirm-form' not in form_open:
            missing.append((path, form_open[:120]))
    assert not missing, "Forms without js-confirm-form:\n" + '\n'.join(f"  {p}: {f}" for p, f in missing)


def test_all_post_forms_have_csrf():
    """Every <form method="post"> (except login) must have csrf_token field."""
    missing = []
    for html in REPO.glob('app/templates/**/*.html'):
        if str(html.relative_to(REPO)) in EXEMPT_TEMPLATES:
            continue
        text = html.read_text(encoding='utf-8')
        if 'method="post"' not in text:
            continue
        if 'name="csrf_token"' not in text:
            if re.search(r'<form[^>]*method="post"', text):
                missing.append(str(html.relative_to(REPO)))
    assert not missing, "Templates with POST form but no csrf_token:\n" + '\n'.join(f"  {m}" for m in missing)


def test_no_legacy_confirm_javascript_remains():
    """Old confirm('...') JS pattern must be replaced with data-confirm-*."""
    legacy = []
    for html in REPO.glob('app/templates/**/*.html'):
        text = html.read_text(encoding='utf-8')
        if 'onclick="if (confirm(' in text or 'onclick="return confirm(' in text:
            legacy.append(str(html.relative_to(REPO)))
    assert not legacy, "Legacy confirm() JS found:\n" + '\n'.join(f"  {l}" for l in legacy)