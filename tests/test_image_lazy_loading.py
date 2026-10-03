"""Phase 22 — Image lazy-loading verification.

The 4 templates that previously had <img> without loading="lazy":
- login.html (logo = eager, hero = lazy)
- producto_form.html
- receta_form.html
- recetas.html

All <img> tags in template files should have a loading attribute
(either 'eager' for above-the-fold or 'lazy' for below-the-fold).
"""
from __future__ import annotations

import re
from pathlib import Path


TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates"


def test_login_logo_loading_eager():
    """The logo is above-the-fold, so it should be eager."""
    text = (TEMPLATES_DIR / "login.html").read_text()
    # Find the logo <img> tag
    m = re.search(r'<img[^>]*logo\.svg[^>]*>', text)
    assert m
    assert 'loading="eager"' in m.group(0)


def test_login_hero_loading_lazy():
    """The hero illustration is below-the-fold, so it should be lazy."""
    text = (TEMPLATES_DIR / "login.html").read_text()
    m = re.search(r'<img[^>]*login-hero[^>]*>', text)
    assert m
    assert 'loading="lazy"' in m.group(0)
    assert 'decoding="async"' in m.group(0)


def test_producto_form_image_loading_lazy():
    text = (TEMPLATES_DIR / "producto_form.html").read_text()
    for m in re.finditer(r'<img[^>]*image-preview-img[^>]*>', text):
        assert 'loading="lazy"' in m.group(0), f"Image missing lazy: {m.group(0)[:200]}"


def test_receta_form_image_loading_lazy():
    text = (TEMPLATES_DIR / "receta_form.html").read_text()
    for m in re.finditer(r'<img[^>]*recipe\.image_url[^>]*>', text):
        assert 'loading="lazy"' in m.group(0), f"Image missing lazy: {m.group(0)[:200]}"


def test_recetas_list_image_loading_lazy():
    text = (TEMPLATES_DIR / "recetas.html").read_text()
    # First img in list
    for m in re.finditer(r'<img[^>]*r\.image_url[^>]*>', text):
        assert 'loading="lazy"' in m.group(0)


def test_recetas_modal_image_loading_lazy():
    text = (TEMPLATES_DIR / "recetas.html").read_text()
    m = re.search(r'<img id="recipe-photo-img"[^>]*>', text)
    assert m
    assert 'loading="lazy"' in m.group(0)


def test_all_template_images_have_loading_attr():
    """No <img> tag in any template should be without loading="..." attribute."""
    template_files = list(TEMPLATES_DIR.glob("*.html"))
    failures = []
    for tf in template_files:
        text = tf.read_text()
        for m in re.finditer(r'<img[^>]+>', text):
            tag = m.group(0)
            if "loading=" not in tag:
                failures.append(f"{tf.name}: {tag[:120]}")
    assert not failures, "Images without loading attr:\n  " + "\n  ".join(failures)


def test_lazy_images_also_have_decoding_async():
    """Images with loading=lazy should also have decoding=async for best perf."""
    template_files = list(TEMPLATES_DIR.glob("*.html"))
    failures = []
    for tf in template_files:
        text = tf.read_text()
        for m in re.finditer(r'<img[^>]+>', text):
            tag = m.group(0)
            if 'loading="lazy"' in tag and "decoding=" not in tag:
                failures.append(f"{tf.name}: {tag[:120]}")
    assert not failures, "Lazy images without decoding=async:\n  " + "\n  ".join(failures)