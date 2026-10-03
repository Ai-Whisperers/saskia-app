"""Index of all Phase 22 tests (frontend/UX/UI polish)."""
from pathlib import Path

PHASE_22_TESTS = [
    "test_a11y_sweep.py",              # 7 tests
    "test_flex_utilities.py",          # 12 tests
    "test_design_system_atoms.py",     # 8 tests
    "test_insight_export_buttons.py",  # 5 tests
    "test_keyboard_shortcuts.py",      # 12 tests
    "test_image_lazy_loading.py",      # 8 tests
    "test_skeleton_loader.py",         # 14 tests
    "test_back_to_top.py",             # 17 tests
    "test_form_dirty.py",              # 10 tests
    "test_confirm_dialogs.py",         # 8 tests
    "test_saskia_toast.py",            # 6 tests
    "test_dark_mode.py",               # 10 tests
    # from earlier phases
    "test_breadcrumbs_nav.py",         # 10 tests
    "test_days_filter_chip.py",        # 8 tests
]


def test_phase22_test_files_exist():
    tests_dir = Path(__file__).parent
    missing = [f for f in PHASE_22_TESTS if not (tests_dir / f).exists()]
    assert not missing, f"Missing Phase 22 test files: {missing}"


def test_phase22_test_count_meets_target():
    """Phase 22 added 100+ tests across the surface."""
    tests_dir = Path(__file__).parent
    total = 0
    for f in PHASE_22_TESTS:
        path = tests_dir / f
        if path.exists():
            # Count test functions
            content = path.read_text()
            total += content.count("def test_")
    assert total >= 100, f"Phase 22 has only {total} tests; want >= 100"