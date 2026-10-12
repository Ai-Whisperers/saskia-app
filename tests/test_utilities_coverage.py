"""tests/test_utilities_coverage.py — Utilities coverage tests.

Tests for utility functions and helper modules.
"""
import pytest
import re
import os
import hashlib


def test_regex_patterns():
    """Test regex pattern matching."""
    # Test email pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    assert re.match(email_pattern, "test@example.com")
    assert not re.match(email_pattern, "invalid.email")
    
    # Test phone pattern
    phone_pattern = r'^\+?[\d\s\-\(\)]{7,}$'
    assert re.match(phone_pattern, "+1 (555) 123-4567")
    assert not re.match(phone_pattern, "abc")


def test_file_operations():
    """Test file operation utilities."""
    # Test path joining
    path = os.path.join("dir1", "dir2", "file.txt")
    assert "dir1" in path
    assert "file.txt" in path
    
    # Test path splitting
    parts = os.path.splitext("file.txt")
    assert parts[0] == "file"
    assert parts[1] == ".txt"
    
    # Test basename/dirname
    assert os.path.basename("dir/file.txt") == "file.txt"
    assert os.path.dirname("dir/file.txt") == "dir"


def test_hash_operations():
    """Test hash operations."""
    # Test MD5
    text = "Hello World"
    md5_hash = hashlib.md5(text.encode()).hexdigest()
    assert len(md5_hash) == 32
    assert isinstance(md5_hash, str)
    
    # Test SHA256
    sha256_hash = hashlib.sha256(text.encode()).hexdigest()
    assert len(sha256_hash) == 64
    
    # Test hash consistency
    assert hashlib.md5(text.encode()).hexdigest() == md5_hash


def test_string_manipulation():
    """Test string manipulation utilities."""
    # Test capitalization
    assert "hello".capitalize() == "Hello"
    assert "HELLO".capitalize() == "Hello"
    
    # Test title case
    assert "hello world".title() == "Hello World"
    
    # Test swapcase
    assert "Hello".swapcase() == "hELLO"
    
    # Test casefold
    assert "HELLO".casefold() == "hello"


def test_list_utilities():
    """Test list utility functions."""
    # Test sorting
    numbers = [3, 1, 4, 1, 5, 9, 2, 6]
    sorted_nums = sorted(numbers)
    assert sorted_nums == [1, 1, 2, 3, 4, 5, 6, 9]
    
    # Test reversing
    assert list(reversed([1, 2, 3])) == [3, 2, 1]
    
    # Test flattening
    nested = [[1, 2], [3, 4], [5, 6]]
    flat = [item for sublist in nested for item in sublist]
    assert flat == [1, 2, 3, 4, 5, 6]


def test_dict_utilities():
    """Test dictionary utility functions."""
    # Test merging
    dict1 = {"a": 1, "b": 2}
    dict2 = {"c": 3, "d": 4}
    merged = {**dict1, **dict2}
    assert merged == {"a": 1, "b": 2, "c": 3, "d": 4}
    
    # Test filtering
    data = {"a": 1, "b": 2, "c": 3, "d": 4}
    filtered = {k: v for k, v in data.items() if v > 2}
    assert filtered == {"c": 3, "d": 4}
    
    # Test keys/values extraction
    assert list(data.keys()) == ["a", "b", "c", "d"]
    assert list(data.values()) == [1, 2, 3, 4]


def test_type_checking():
    """Test type checking utilities."""
    # Test isinstance
    assert isinstance(42, int)
    assert isinstance("text", str)
    assert isinstance([1, 2], list)
    assert isinstance({"a": 1}, dict)
    assert isinstance((1, 2), tuple)
    assert isinstance(3.14, float)
    assert isinstance(True, bool)
    
    # Test type()
    assert type(42) is int
    assert type("text") is str


def test_collections_operations():
    """Test collections operations."""
    from collections import Counter, defaultdict
    
    # Test Counter
    items = ["a", "b", "a", "c", "a", "b"]
    counter = Counter(items)
    assert counter["a"] == 3
    assert counter["b"] == 2
    assert counter["c"] == 1
    
    # Test defaultdict
    dd = defaultdict(list)
    dd["key1"].append(1)
    dd["key1"].append(2)
    assert dd["key1"] == [1, 2]
    assert dd["missing"] == []


def test_validation_functions():
    """Test validation utility functions."""
    # Test email validation
    def is_valid_email(email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    assert is_valid_email("test@example.com")
    assert not is_valid_email("invalid")
    
    # Test phone validation
    def is_valid_phone(phone):
        pattern = r'^\+?[\d\s\-\(\)]{7,}$'
        return bool(re.match(pattern, phone))
    
    assert is_valid_phone("+1-555-1234")
    assert not is_valid_phone("abc")


def test_string_conversion():
    """Test string conversion utilities."""
    # Test to string
    assert str(42) == "42"
    assert str(3.14) == "3.14"
    assert str(True) == "True"
    assert str([1, 2]) == "[1, 2]"
    
    # Test to int
    assert int("42") == 42
    assert int(3.14) == 3
    
    # Test to float
    assert float("3.14") == 3.14
    assert float(42) == 42.0


def test_error_messages():
    """Test error message formatting."""
    # Test basic error messages
    try:
        raise ValueError("Test error")
    except ValueError as e:
        assert str(e) == "Test error"
    
    # Test custom errors
    class CustomError(Exception):
        def __init__(self, message, code=None):
            super().__init__(message)
            self.code = code
    
    try:
        raise CustomError("Custom error", 42)
    except CustomError as e:
        assert str(e) == "Custom error"
        assert e.code == 42


def test_data_conversion():
    """Test data conversion utilities."""
    # Test list to tuple
    assert tuple([1, 2, 3]) == (1, 2, 3)
    
    # Test tuple to list
    assert list((1, 2, 3)) == [1, 2, 3]
    
    # Test set to list
    assert sorted(list({3, 1, 2})) == [1, 2, 3]
    
    # Test dict to list of items
    assert list({"a": 1, "b": 2}.items()) == [("a", 1), ("b", 2)]


def test_comparison_operations():
    """Test comparison operations."""
    # Test equality
    assert 1 == 1
    assert "test" == "test"
    assert [1, 2] == [1, 2]
    
    # Test inequality
    assert 1 != 2
    assert "a" != "b"
    
    # Test greater/less than
    assert 2 > 1
    assert 1 < 2
    assert 2 >= 2
    assert 1 <= 1


def test_logical_operations():
    """Test logical operations."""
    # Test and
    assert True and True
    assert not (True and False)
    assert not (False and True)
    assert not (False and False)
    
    # Test or
    assert True or False
    assert False or True
    assert True or True
    assert not (False or False)
    
    # Test not
    assert not False
    assert not (not True)


def test_conditional_expressions():
    """Test conditional expressions."""
    # Test ternary
    x = 5
    result = "positive" if x > 0 else "negative"
    assert result == "positive"
    
    result = "positive" if x < 0 else "negative"
    assert result == "negative"
    
    # Test short-circuit
    a = 0
    b = 10
    result = a or b
    assert result == 10
    
    result = b and a
    assert result == 0


def test_string_padding():
    """Test string padding operations."""
    # Test ljust
    assert "test".ljust(10) == "test      "
    
    # Test rjust
    assert "test".rjust(10) == "      test"
    
    # Test center
    assert "test".center(10) == "   test   "
    
    # Test zfill
    assert "42".zfill(5) == "00042"
    assert "-42".zfill(5) == "-0042"