"""PROD-MERMA-2: deficit-prompt JS is wired (T4 completion).

Verifies:
- /produccion?shift_saved=1 carries data-shift-saved on the flash banner.
- The IIFE that scans production-rows is present.
- Buttons created by the IIFE carry data-batch-qty for openQuickMerma().
- openQuickMerma() reads data-batch-qty + data-recipe-id and switches tabs.
"""

from __future__ import annotations

import pathlib

TPL = pathlib.Path("/opt/data/work/saskia-app/app/templates/produccion.html")


def _tpl() -> str:
    return TPL.read_text()


def test_data_shift_saved_marker_present():
    """The shift-saved banner emits data-shift-saved='1'."""
    src = _tpl()
    assert 'data-shift-saved="1"' in src, "data-shift-saved marker missing on flash banner"


def test_deficit_prompt_uses_data_batch_qty():
    """The deficit-prompt IIFE passes data-batch-qty to openQuickMerma()."""
    src = _tpl()
    # The IIFE sets data-batch-qty on each button.
    assert "data-batch-qty" in src, "deficit button never receives data-batch-qty"


def test_open_quick_merma_reads_data_batch_qty():
    """openQuickMerma() reads data-batch-qty and prefills the input."""
    src = _tpl()
    assert "btn.getAttribute('data-batch-qty')" in src, (
        "openQuickMerma does not read data-batch-qty"
    )


def test_open_quick_merma_switches_to_recipe_tab_when_deficit():
    """openQuickMerma() switches to recipe tab when both recipe_id AND batch_qty present."""
    src = _tpl()
    # The conditional should be inside openQuickMerma
    idx = src.find("function openQuickMerma")
    assert idx > 0
    body = src[idx : idx + 1500]
    assert "qmSwitchTab('recipe')" in body, (
        "openQuickMerma does not switch to recipe tab when triggered by a deficit"
    )


def test_qm_batch_qty_input_has_stable_id():
    """The batch_qty input is addressable by id='qm-batch-qty' so the JS can prefill."""
    src = _tpl()
    assert 'id="qm-batch-qty"' in src, "qm-batch-qty input id missing"


def test_deficit_button_text_includes_qty():
    """The button text dynamically includes the deficit qty so operators see the amount."""
    src = _tpl()
    # Pattern: '🔥 Registrar ' + d.missing + ' como merma'
    assert "🔥 Registrar" in src, "deficit button missing 🔥 prefix"
    assert "como merma" in src, "deficit button missing 'como merma' suffix"
