"""Tests for some_module."""

import pytest
from src.some_module import some_function


def test_some_function():
    """Test that some_function returns the expected string with input."""
    result = some_function("test")
    expected = "This is a function from some_module with input: test"
    assert result == expected
    assert isinstance(result, str)


def test_some_function_not_empty():
    """Test that some_function does not return an empty string."""
    result = some_function("hello")
    assert result != ""
    assert len(result) > 0


def test_some_function_includes_input():
    """Test that some_function includes the input parameter in output."""
    test_input = "world"
    result = some_function(test_input)
    assert test_input in result


class TestSomeFunction:
    """Group of tests for some_function using a test class."""

    def test_return_type(self):
        """Test that some_function returns a string type."""
        result = some_function("example")
        assert isinstance(result, str)

    def test_return_value(self):
        """Test the exact return value of some_function."""
        expected = "This is a function from some_module with input: foo"
        assert some_function("foo") == expected

    def test_with_empty_string(self):
        """Test some_function with empty string input."""
        result = some_function("")
        assert result == "This is a function from some_module with input: "

    def test_with_special_characters(self):
        """Test some_function with special characters."""
        special_input = "!@#$%"
        result = some_function(special_input)
        assert special_input in result
