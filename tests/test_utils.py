from __future__ import annotations

import math
from typing import Any

import pytest

from backend.utils import (
    clean_bool,
    clamp,
    num,
    one_line,
    parse_json_loose,
    safe_last,
    sha1_hex,
)


class TestNum:
    def test_normal_numeric_values(self) -> None:
        assert num(42) == 42.0
        assert num(3.14) == 3.14
        assert num("123") == 123.0
        assert num("-5.5") == -5.5
        assert num("0") == 0.0

    def test_none_returns_none(self) -> None:
        assert num(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert num("") is None

    def test_false_returns_none(self) -> None:
        assert num(False) is None

    def test_nan_returns_none(self) -> None:
        assert num(float("nan")) is None

    def test_inf_returns_none(self) -> None:
        assert num(float("inf")) is None
        assert num(float("-inf")) is None

    def test_non_numeric_string_returns_none(self) -> None:
        assert num("abc") is None
        assert num("12.34.56") is None
        assert num("") is None

    def test_list_returns_none(self) -> None:
        assert num([1, 2, 3]) is None

    def test_dict_returns_none(self) -> None:
        assert num({"a": 1}) is None

    def test_zero_string_is_valid(self) -> None:
        assert num("0") == 0.0

    def test_numeric_zero_treated_as_falsy(self) -> None:
        # Note: Python's bool is a subclass of int, so False == 0 == 0.0.
        # The current implementation treats all falsy numeric zeros as None.
        # This is a known quirk of the existing code.
        assert num(0) is None
        assert num(0.0) is None


class TestClamp:
    def test_value_within_range(self) -> None:
        assert clamp(50, 0, 100) == 50.0
        assert clamp(3.14, 0, 10) == 3.14

    def test_value_below_minimum(self) -> None:
        assert clamp(-10, 0, 100) == 0.0

    def test_value_above_maximum(self) -> None:
        assert clamp(200, 0, 100) == 100.0

    def test_none_returns_minimum(self) -> None:
        assert clamp(None, 10, 20) == 10.0

    def test_empty_string_returns_minimum(self) -> None:
        assert clamp("", 10, 20) == 10.0

    def test_string_numeric(self) -> None:
        assert clamp("50", 0, 100) == 50.0
        assert clamp("-10", 0, 100) == 0.0
        assert clamp("200", 0, 100) == 100.0

    def test_at_boundaries(self) -> None:
        assert clamp(0, 0, 100) == 0.0
        assert clamp(100, 0, 100) == 100.0


class TestCleanBool:
    def test_true_returns_true(self) -> None:
        assert clean_bool(True) is True

    def test_false_returns_false(self) -> None:
        assert clean_bool(False) is False

    def test_non_bool_returns_fallback(self) -> None:
        assert clean_bool("yes") is False
        assert clean_bool(1) is False
        assert clean_bool(0) is False
        assert clean_bool(None) is False
        assert clean_bool([]) is False

    def test_custom_fallback(self) -> None:
        assert clean_bool("yes", fallback=True) is True
        assert clean_bool(1, fallback=True) is True
        assert clean_bool(None, fallback=True) is True


class TestOneLine:
    def test_basic_whitespace_compression(self) -> None:
        assert one_line("hello   world") == "hello world"
        assert one_line("  leading trailing  ") == "leading trailing"

    def test_multiline_compression(self) -> None:
        assert one_line("line1\nline2\nline3") == "line1 line2 line3"
        assert one_line("a\t\t\tb") == "a b"

    def test_truncation(self) -> None:
        long_text = "a" * 250
        result = one_line(long_text)
        assert result.endswith("...")
        assert len(result) == 220

    def test_none_input(self) -> None:
        assert one_line(None) == ""

    def test_empty_string(self) -> None:
        assert one_line("") == ""

    def test_within_limit_no_truncation(self) -> None:
        text = "a" * 220
        assert one_line(text) == text

    def test_custom_limit(self) -> None:
        assert one_line("hello world", limit=5) == "he..."

    def test_exactly_at_limit(self) -> None:
        text = "a" * 219
        assert one_line(text) == text

    def test_number_input(self) -> None:
        assert one_line(42) == "42"


class TestSafeLast:
    def test_empty_list_returns_none(self) -> None:
        assert safe_last([]) is None

    def test_none_input_returns_none(self) -> None:
        assert safe_last(None) is None

    def test_normal_list(self) -> None:
        assert safe_last([1, 2, 3]) == 3
        assert safe_last(["a"]) == "a"

    def test_mixed_types(self) -> None:
        assert safe_last([1, "two", 3.0]) == 3.0


class TestSha1Hex:
    def test_deterministic_output(self) -> None:
        result1 = sha1_hex("hello")
        result2 = sha1_hex("hello")
        assert result1 == result2
        assert len(result1) == 40

    def test_different_inputs_different_outputs(self) -> None:
        assert sha1_hex("hello") != sha1_hex("world")

    def test_known_hash(self) -> None:
        result = sha1_hex("hello")
        assert result == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"

    def test_empty_string(self) -> None:
        result = sha1_hex("")
        assert len(result) == 40
        assert result == "da39a3ee5e6b4b0d3255bfef95601890afd80709"


class TestParseJsonLoose:
    def test_valid_json(self) -> None:
        assert parse_json_loose('{"key": "value"}') == {"key": "value"}
        assert parse_json_loose('[1, 2, 3]') == [1, 2, 3]

    def test_markdown_fence(self) -> None:
        text = '```json\n{"a": 1}\n```'
        assert parse_json_loose(text) == {"a": 1}

    def test_markdown_fence_without_json_label(self) -> None:
        text = '```\n{"b": 2}\n```'
        assert parse_json_loose(text) == {"b": 2}

    def test_bare_object_in_text(self) -> None:
        text = 'Some text {"c": 3} more text'
        assert parse_json_loose(text) == {"c": 3}

    def test_bare_array_in_text(self) -> None:
        text = 'Here is [1, 2, 3] the array'
        assert parse_json_loose(text) == [1, 2, 3]

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="empty JSON payload"):
            parse_json_loose("")

    def test_none_input_raises(self) -> None:
        with pytest.raises(ValueError, match="empty JSON payload"):
            parse_json_loose(None)  # type: ignore[arg-type]

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty JSON payload"):
            parse_json_loose("   \n\t  ")

    def test_invalid_json_no_object_raises(self) -> None:
        with pytest.raises(ValueError, match="could not find JSON object"):
            parse_json_loose("just plain text without any json")

    def test_nested_json_in_fence(self) -> None:
        text = '```json\n{"outer": {"inner": 42}}\n```'
        assert parse_json_loose(text) == {"outer": {"inner": 42}}
