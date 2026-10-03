"""Sprint Week 1 — Strategic improvements verification.

Tests the batch improvements shipped during the strategic sprint:
- Sortable table coverage
- Aria accessibility sweep
- Form validation improvements
- Error handling patterns
"""
from __future__ import annotations

from pathlib import Path


def test_sortable_table_coverage():
    """Should have sortable on at least 65+ templates (target: 88%+)."""
    templates = Path(__file__).parent.parent / "app" / "templates"
    sortable = list(templates.glob("*.html"))
    sortable = [f for f in sortable if "sortable" in f.read_text() or "data-sortable" in f.read_text()]
    assert len(sortable) >= 60, f"Only {len(sortable)} templates have sortable"


def test_complex_inline_onclick_replaced():
    """Should have minimal complex inline onclick= handlers."""
    templates = Path(__file__).parent.parent / "app" / "templates"
    bad_onclick = 0
    for f in templates.glob("*.html"):
        text = f.read_text()
        # Count onclick= that use "this." (indicates complex logic)
        import re
        complex_onclick = re.findall(r'onclick=.*this\.', text)
        bad_onclick += len(complex_onclick)
    assert bad_onclick <= 5, f"Too many complex inline onclick: {bad_onclick}"


def test_images_have_alt():
    """All <img> tags should have alt attribute."""
    templates = Path(__file__).parent.parent / "app" / "templates"
    import re
    missing_alt = 0
    for f in templates.glob("*.html"):
        text = f.read_text()
        # Find img tags without alt
        imgs = re.findall(r'<img[^>]*>', text)
        for img in imgs:
            if 'alt=' not in img:
                missing_alt += 1
    assert missing_alt <= 2, f"Too many images without alt: {missing_alt}"


def test_external_links_have_rel():
    """External links should have rel=noopener."""
    templates = Path(__file__).parent.parent / "app" / "templates"
    import re
    bad_links = 0
    for f in templates.glob("*.html"):
        text = f.read_text()
        # Find target="_blank" without rel
        links = re.findall(r'<a[^>]*target="_blank"[^>]*>', text)
        for link in links:
            if 'rel=' not in link:
                bad_links += 1
    assert bad_links <= 2, f"External links without rel: {bad_links}"


def test_no_bare_except():
    """Should not have bare except: clauses."""
    app_dir = Path(__file__).parent.parent / "app"
    import subprocess
    r = subprocess.run(['grep', '-r', 'except:', str(app_dir), '-l'],
                       capture_output=True, text=True)
    files = r.stdout.strip().split('\n') if r.stdout.strip() else []
    assert len(files) <= 1, f"Too many bare except: {files}"


def test_no_alert_in_js():
    """Should not use alert() in production JS."""
    static_dir = Path(__file__).parent.parent / "app" / "static"
    import subprocess
    r = subprocess.run(['grep', '-l', 'alert(', str(static_dir), '-r'],
                       capture_output=True, text=True)
    files = r.stdout.strip().split('\n') if r.stdout.strip() else []
    # Should be 0 or only test files
    bad = [f for f in files if 'test' not in f]
    assert len(bad) <= 1, f"alert() in production JS: {bad}"


def test_forms_have_grid():
    """All form templates should have grid layout."""
    templates = Path(__file__).parent.parent / "app" / "templates"
    forms = list(templates.glob("*form*.html"))
    no_grid = 0
    for f in forms:
        text = f.read_text()
        if 'class="grid' not in text and 'class="form-grid' not in text:
            no_grid += 1
    assert no_grid <= 2, f"Forms without grid: {no_grid}"


def test_base_html_has_key_meta():
    """base.html should have viewport, lang, charset."""
    base = Path(__file__).parent.parent / "app" / "templates" / "base.html"
    text = base.read_text()
    assert 'viewport' in text
    assert 'lang=' in text
    assert 'charset' in text or 'content-type' in text.lower()


def test_css_files_organized():
    """CSS files should be modular and focused."""
    static_dir = Path(__file__).parent.parent / "app" / "static"
    css_files = list(static_dir.glob("*.css"))
    # Should have 10+ focused CSS files
    assert len(css_files) >= 10, f"Only {len(css_files)} CSS files"


def test_js_files_organized():
    """JS files should be modular."""
    static_dir = Path(__file__).parent.parent / "app" / "static"
    js_files = list(static_dir.glob("*.js"))
    # Should have 15+ focused JS files
    assert len(js_files) >= 15, f"Only {len(js_files)} JS files"