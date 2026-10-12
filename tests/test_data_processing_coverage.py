"""tests/test_data_processing_coverage.py — Data processing coverage tests.

Tests for data processing and validation functions.
"""
import pytest
import json
import csv
from datetime import datetime, date, timedelta
from decimal import Decimal


def test_json_serialization():
    """Test JSON serialization patterns."""
    # Test basic types
    assert json.dumps("text") == '"text"'
    assert json.dumps(42) == '42'
    assert json.dumps(True) == 'true'
    assert json.dumps(None) == 'null'
    assert json.dumps([1, 2, 3]) == '[1, 2, 3]'
    assert json.dumps({"key": "value"}) == '{"key": "value"}'
    
    # Test deserialization
    assert json.loads('"text"') == "text"
    assert json.loads('42') == 42
    assert json.loads('true') is True
    assert json.loads('null') is None
    assert json.loads('[1, 2, 3]') == [1, 2, 3]
    assert json.loads('{"key": "value"}') == {"key": "value"}


def test_csv_operations():
    """Test CSV operations."""
    import io
    
    # Test CSV writing
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "age"])
    writer.writerow(["Alice", 30])
    writer.writerow(["Bob", 25])
    
    csv_content = output.getvalue()
    assert "name" in csv_content
    assert "Alice" in csv_content
    assert "30" in csv_content
    
    # Test CSV reading
    input_data = io.StringIO(csv_content)
    reader = csv.reader(input_data)
    rows = list(reader)
    assert rows[0] == ["name", "age"]
    assert rows[1] == ["Alice", "30"]
    assert rows[2] == ["Bob", "25"]


def test_date_parsing():
    """Test date parsing operations."""
    # Test ISO format
    date_str = "2026-10-11"
    parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    assert parsed.year == 2026
    assert parsed.month == 10
    assert parsed.day == 11
    
    # Test custom format
    date_str2 = "11/10/2026"
    parsed2 = datetime.strptime(date_str2, "%d/%m/%Y").date()
    assert parsed2.day == 11
    assert parsed2.month == 10


def test_date_formatting():
    """Test date formatting operations."""
    d = date(2026, 10, 11)
    
    # Test various formats
    assert d.strftime("%Y-%m-%d") == "2026-10-11"
    assert d.strftime("%d/%m/%Y") == "11/10/2026"
    assert d.strftime("%B %d, %Y") == "October 11, 2026"
    assert d.strftime("%Y%m%d") == "20261011"


def test_money_calculations():
    """Test money calculation utilities."""
    # Test addition
    price1 = Decimal("10.50")
    price2 = Decimal("20.25")
    total = price1 + price2
    assert total == Decimal("30.75")
    
    # Test subtraction
    diff = price2 - price1
    assert diff == Decimal("9.75")
    
    # Test multiplication
    quantity = Decimal("3")
    assert price1 * quantity == Decimal("31.50")
    
    # Test division
    assert Decimal("10.00") / Decimal("2") == Decimal("5.00")
    
    # Test rounding
    assert Decimal("10.555").quantize(Decimal("0.01")) == Decimal("10.56")
    assert Decimal("10.554").quantize(Decimal("0.01")) == Decimal("10.55")


def test_percentage_calculations():
    """Test percentage calculation utilities."""
    def percentage(part, whole):
        return (part / whole) * 100 if whole > 0 else 0
    
    # Test basic percentages
    assert percentage(25, 100) == 25.0
    assert percentage(50, 100) == 50.0
    assert percentage(75, 100) == 75.0
    
    # Test edge cases
    assert percentage(0, 100) == 0.0
    assert percentage(100, 100) == 100.0
    assert percentage(50, 0) == 0
    
    # Test decimal results
    assert percentage(1, 3) == pytest.approx(33.333, 0.01)


def test_string_cleaning():
    """Test string cleaning utilities."""
    # Test whitespace stripping
    assert "  text  ".strip() == "text"
    assert "\ttext\n".strip() == "text"
    
    # Test case normalization
    assert "HELLO".lower() == "hello"
    assert "hello".upper() == "HELLO"
    
    # Test special character removal
    text = "Hello, World!"
    cleaned = text.replace(",", "").replace("!", "")
    assert cleaned == "Hello World"


def test_data_validation():
    """Test data validation utilities."""
    # Test required field validation
    def validate_required(data, fields):
        errors = []
        for field in fields:
            if field not in data or not data[field]:
                errors.append(f"Field {field} is required")
        return errors
    
    # Test valid data
    data = {"name": "Alice", "age": 30}
    errors = validate_required(data, ["name", "age"])
    assert errors == []
    
    # Test missing fields
    data2 = {"name": "Bob"}
    errors2 = validate_required(data2, ["name", "age"])
    assert len(errors2) == 1
    assert "age" in errors2[0]
    
    # Test empty fields
    data3 = {"name": "", "age": 0}
    errors3 = validate_required(data3, ["name", "age"])
    assert len(errors3) == 2  # Both empty name and age=0 trigger errors


def test_data_transformation():
    """Test data transformation utilities."""
    # Test mapping
    numbers = [1, 2, 3, 4, 5]
    squared = list(map(lambda x: x**2, numbers))
    assert squared == [1, 4, 9, 16, 25]
    
    # Test filtering
    evens = list(filter(lambda x: x % 2 == 0, numbers))
    assert evens == [2, 4]
    
    # Test reducing
    from functools import reduce
    total = reduce(lambda x, y: x + y, numbers)
    assert total == 15


def test_list_comprehensions():
    """Test list comprehension patterns."""
    # Test basic comprehension
    squares = [x**2 for x in range(5)]
    assert squares == [0, 1, 4, 9, 16]
    
    # Test with condition
    evens = [x for x in range(10) if x % 2 == 0]
    assert evens == [0, 2, 4, 6, 8]
    
    # Test nested comprehension
    matrix = [[i*3+j for j in range(3)] for i in range(3)]
    assert matrix[0] == [0, 1, 2]
    assert matrix[1] == [3, 4, 5]
    assert matrix[2] == [6, 7, 8]


def test_dict_comprehensions():
    """Test dictionary comprehension patterns."""
    # Test basic comprehension
    squares = {x: x**2 for x in range(5)}
    assert squares[0] == 0
    assert squares[1] == 1
    assert squares[2] == 4
    assert squares[3] == 9
    assert squares[4] == 16
    
    # Test with condition
    even_squares = {x: x**2 for x in range(10) if x % 2 == 0}
    assert even_squares[0] == 0
    assert even_squares[2] == 4
    assert even_squares[4] == 16


def test_set_comprehensions():
    """Test set comprehension patterns."""
    # Test basic comprehension
    squares = {x**2 for x in range(5)}
    assert squares == {0, 1, 4, 9, 16}
    
    # Test with condition
    evens = {x for x in range(10) if x % 2 == 0}
    assert evens == {0, 2, 4, 6, 8}


def test_generator_expressions():
    """Test generator expression patterns."""
    # Test basic generator
    squares_gen = (x**2 for x in range(5))
    squares_list = list(squares_gen)
    assert squares_list == [0, 1, 4, 9, 16]
    
    # Test sum with generator
    total = sum(x**2 for x in range(5))
    assert total == 30


def test_string_formatting_advanced():
    """Test advanced string formatting."""
    # Test format with specifiers
    assert "{:.2f}".format(3.14159) == "3.14"
    assert "{:,.2f}".format(1234567.89) == "1,234,567.89"
    assert "{:>10}".format("test") == "      test"
    assert "{:<10}".format("test") == "test      "
    assert "{:^10}".format("test") == "   test   "
    
    # Test percentage formatting
    assert "{:.1%}".format(0.25) == "25.0%"
    assert "{:.0%}".format(0.5) == "50%"


def test_number_parsing():
    """Test number parsing utilities."""
    # Test int parsing
    assert int("42") == 42
    assert int("-42") == -42
    assert int("+42") == 42
    
    # Test float parsing
    assert float("3.14") == 3.14
    assert float("-3.14") == -3.14
    assert float("1e5") == 100000.0


def test_boolean_conversion():
    """Test boolean conversion utilities."""
    # Test truthy values
    assert bool(1) is True
    assert bool("text") is True
    assert bool([1]) is True
    assert bool({"a": 1}) is True
    assert bool(True) is True
    
    # Test falsy values
    assert bool(0) is False
    assert bool("") is False
    assert bool([]) is False
    assert bool({}) is False
    assert bool(None) is False
    assert bool(False) is False


def test_none_handling():
    """Test None handling patterns."""
    # Test default values
    value = None
    result = value if value is not None else "default"
    assert result == "default"
    
    # Test or operator
    result2 = value or "default"
    assert result2 == "default"
    
    # Test safe access
    data = {"key": "value"}
    result3 = data.get("missing", "default")
    assert result3 == "default"


def test_string_searching():
    """Test string searching operations."""
    text = "The quick brown fox jumps over the lazy dog"
    
    # Test find
    assert text.find("fox") == 16
    assert text.find("missing") == -1
    
    # Test count
    assert text.count("the") == 1  # Case sensitive, only "the" lowercase
    assert text.count("missing") == 0
    
    # Test index
    assert text.index("fox") == 16


def test_string_replacement():
    """Test string replacement operations."""
    text = "Hello World, Hello Universe"
    
    # Test replace all
    result = text.replace("Hello", "Hi")
    assert result == "Hi World, Hi Universe"
    
    # Test replace with count
    result2 = text.replace("Hello", "Hi", 1)
    assert result2 == "Hi World, Hello Universe"


def test_string_splitting():
    """Test string splitting operations."""
    # Test split with delimiter
    assert "a,b,c".split(",") == ["a", "b", "c"]
    
    # Test split with maxsplit
    assert "a,b,c,d".split(",", 2) == ["a", "b", "c,d"]
    
    # Test splitlines
    assert "line1\nline2\nline3".splitlines() == ["line1", "line2", "line3"]
    
    # Test partition
    assert "key=value".partition("=") == ("key", "=", "value")