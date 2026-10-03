"""Phase 22 — Shortcut help modal verification.

base.html now includes a full keyboard shortcuts modal triggered by '?',
with navigation shortcuts, command palette, help self-reference, and Esc close.
"""
from __future__ import annotations

from pathlib import Path


BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_shortcut_help_modal_in_base_html():
    """The modal should be pre-rendered in base.html."""
    text = BASE_HTML.read_text()
    assert 'id="shortcut-help-modal"' in text
    assert 'Atajos de teclado' in text
    assert 'Ir a Inicio' in text
    assert 'Ir a Ventas' in text
    assert 'Paleta de comandos' in text


def test_shortcut_help_modal_has_proper_structure():
    """Should be a modal with dialog, header, and body."""
    text = BASE_HTML.read_text()
    assert 'role="dialog"' in text
    assert 'aria-modal="true"' in text
    assert 'aria-labelledby="shortcut-help-title"' in text


def test_shortcut_help_lists_all_main_shortcuts():
    """Should list all g+letter navigation, Cmd+K, ?, Esc."""
    text = BASE_HTML.read_text()
    # Check main navigation (note: in the HTML it's 'g + e' with spaces)
    assert '<kbd>g</kbd> + <kbd>i</kbd>' in text and 'Ir a Inicio' in text
    assert '<kbd>g</kbd> + <kbd>v</kbd>' in text and 'Ir a Ventas' in text
    assert '<kbd>g</kbd> + <kbd>p</kbd>' in text and 'Ir a Productos' in text
    assert '<kbd>g</kbd> + <kbd>r</kbd>' in text and 'Ir a Recetas' in text
    assert '<kbd>g</kbd> + <kbd>n</kbd>' in text and 'Ir a Inventario' in text
    assert '<kbd>g</kbd> + <kbd>e</kbd>' in text and 'Ir a Cierre' in text
    assert '<kbd>g</kbd> + <kbd>m</kbd>' in text and 'Ir a Merma' in text
    assert '<kbd>g</kbd> + <kbd>s</kbd>' in text and 'Ir a Configuración' in text
    # Check global shortcuts
    assert 'Cmd</kbd>/<kbd>Ctrl</kbd> + <kbd>K</kbd>' in text or 'Cmd/Ctrl+K' in text
    assert '<kbd>?</kbd></td>' in text and 'Muestra este panel' in text
    assert '<kbd>Esc</kbd></td>' in text and 'Cerrar modales' in text


def test_shortcut_help_special_pos_shortcuts():
    """Should mention F2/F4 for POS screen."""
    text = BASE_HTML.read_text()
    assert '<kbd>F2</kbd>' in text, "F2 should be in the modal"
    assert '<kbd>F4</kbd>' in text, "F4 should be in the modal"
    assert 'En la pantalla de ventas' in text, "POS explanation should be present"


def test_shortcut_help_has_close_button():
    """Should have a close button with proper label."""
    text = BASE_HTML.read_text()
    assert 'aria-label="Cerrar"' in text
    assert 'close-shortcuts' in text


def test_shortcut_help_uses_existing_modal_backdrop():
    """Should reuse the modal-backdrop and modal-dialog classes."""
    text = BASE_HTML.read_text()
    assert 'class="modal-backdrop"' in text
    assert 'class="modal-dialog"' in text


def test_shortcut_help_keyboard_notation():
    """Should use <kbd> tags for keyboard shortcuts."""
    text = BASE_HTML.read_text()
    kbd_count = text.count('<kbd>')
    assert kbd_count >= 10, f"Expected >=10 <kbd> tags, found {kbd_count}"


def test_shortcut_help_is_hidden_by_default():
    """Should be hidden until user presses ?."""
    text = BASE_HTML.read_text()
    assert 'hidden' in text


def test_shortcut_help_has_accessible_heading():
    """Should have a heading with proper ID for label."""
    text = BASE_HTML.read_text()
    assert 'id="shortcut-help-title"' in text
    assert 'Atajos de teclado' in text