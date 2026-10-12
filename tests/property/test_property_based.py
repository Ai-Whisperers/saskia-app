"""tests/property/test_property_based.py — Phase 1 refactored."""
import pytest
from hypothesis import given, strategies as st


pytestmark = [pytest.mark.property, pytest.mark.slow]


text_strategy = st.text(
    min_size=0, max_size=50,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "P", "Zs"),
        max_codepoint=127,
    ),
)

small_int_strategy = st.integers(min_value=0, max_value=10_000)


def test_hypothesis_imports():
    """hypothesis should be importable."""
    from hypothesis import given, strategies as st
    assert given is not None
    assert st is not None


@given(text=text_strategy)
def test_md_to_html_returns_string(text):
    """_md_to_html should always return a string for any text."""
    try:
        from app.routers.help import _md_to_html
        result = _md_to_html(text)
        assert isinstance(result, str)
    except ImportError:
        pytest.skip("help router not available")


@given(value=small_int_strategy)
def test_format_gs_never_crashes(value):
    """format_gs should handle any non-negative integer."""
    from app.rms.money import format_gs
    result = format_gs(value)
    assert isinstance(result, str)


@given(a=st.lists(st.integers(min_value=0, max_value=1000), min_size=0, max_size=20))
def test_sparkline_handles_any_list(a):
    """sparkline should handle any list of numbers."""
    from app.rms.charts import sparkline
    result = sparkline(a)
    assert isinstance(result, str)


@given(
    a=st.sets(st.integers(min_value=0, max_value=100), max_size=20),
    b=st.sets(st.integers(min_value=0, max_value=100), max_size=20),
)
def test_jaccard_similarity_in_range(a, b):
    """jaccard_similarity should return 0-1 for any two sets."""
    from app.rms.product_similarity import jaccard_similarity
    result = jaccard_similarity(a, b)
    assert 0.0 <= result <= 1.0


@given(
    a=st.text(
        min_size=0, max_size=100,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll"), max_codepoint=127),
    ),
)
def test_slugify_no_spaces(a):
    """slugify should never have spaces in output."""
    from app.rms.validation import slugify
    result = slugify(a)
    assert " " not in result


@given(value=st.integers(min_value=0, max_value=1_000_000).map(str))
def test_parse_gs_numeric_strings(value):
    """parse_gs should accept integer strings."""
    from app.rms.money import parse_gs
    result = parse_gs(value)
    assert isinstance(result, (int, type(None)))


@given(
    a=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Nd",), max_codepoint=57)),
)
def test_parse_gs_digit_strings(a):
    """parse_gs should accept digit strings."""
    from app.rms.money import parse_gs
    result = parse_gs(a)
    assert isinstance(result, (int, type(None)))


@given(value=st.integers(min_value=0, max_value=1_000_000_000))
def test_to_int_gs_idempotent(value):
    """to_int_gs should be idempotent on integers."""
    from app.rms.money import to_int_gs
    once = to_int_gs(value)
    twice = to_int_gs(once)
    assert once == twice
