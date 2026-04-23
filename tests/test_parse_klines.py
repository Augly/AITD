from __future__ import annotations

from typing import Any

import pytest

from backend.utils import parse_klines


class TestParseKlinesBinance:
    """Binance-style klines: no reverse, closeTime at index 6, quoteVolume at index 7."""

    def test_basic_parsing(self) -> None:
        rows = [
            [1000, "1.0", "2.0", "0.5", "1.5", "100", 2000, "150"],
            [3000, "1.5", "2.5", "1.0", "2.0", "200", 4000, "300"],
        ]
        result = parse_klines(rows)

        assert len(result) == 2
        assert result[0]["openTime"] == 1000
        assert result[0]["open"] == 1.0
        assert result[0]["high"] == 2.0
        assert result[0]["low"] == 0.5
        assert result[0]["close"] == 1.5
        assert result[0]["volume"] == 100.0
        assert result[0]["closeTime"] == 2000
        assert result[0]["quoteVolume"] == 150.0

    def test_returns_chronological_order(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "1.5", "100", 2000, "150"],
            [3000, "1.5", "2.5", "1.0", "2.0", "200", 4000, "300"],
        ]
        result = parse_klines(rows)

        assert result[0]["openTime"] == 1000
        assert result[1]["openTime"] == 3000

    def test_skips_row_with_none_close(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", None, "100", 2000, "150"],
            [3000, "1.5", "2.5", "1.0", "2.0", "200", 4000, "300"],
        ]
        result = parse_klines(rows)

        assert len(result) == 1
        assert result[0]["openTime"] == 3000

    def test_skips_row_too_short(self) -> None:
        rows = [
            [1000, "1", "2", "0.5"],
            [3000, "1.5", "2.5", "1.0", "2.0", "200", 4000, "300"],
        ]
        result = parse_klines(rows)

        assert len(result) == 1
        assert result[0]["openTime"] == 3000

    def test_empty_input(self) -> None:
        assert parse_klines([]) == []
        assert parse_klines(None) == []

    def test_open_time_int_conversion(self) -> None:
        rows = [
            ["1000", "1", "2", "0.5", "1.5", "100", 2000, "150"],
        ]
        result = parse_klines(rows)

        assert result[0]["openTime"] == 1000


class TestParseKlinesBybit:
    """Bybit-style klines: reversed, closeTime falls back to openTime, quoteVolume at index 6."""

    def test_reversed_order(self) -> None:
        rows = [
            [3000, "1.5", "2.5", "1.0", "2.0", "200", "300"],
            [1000, "1.0", "2.0", "0.5", "1.5", "100", "150"],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=6,
            close_time_index=None,
            min_length=7,
        )

        assert len(result) == 2
        assert result[0]["openTime"] == 1000
        assert result[1]["openTime"] == 3000

    def test_close_time_fallback_to_open_time(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "1.5", "100", "150"],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=6,
            close_time_index=None,
            min_length=7,
        )

        assert result[0]["closeTime"] == 1000

    def test_quote_volume_at_index_6(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "1.5", "100", "150"],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=6,
            close_time_index=None,
            min_length=7,
        )

        assert result[0]["quoteVolume"] == 150.0

    def test_min_length_7_skips_short_rows(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "1.5", "100"],
            [2000, "1", "2", "0.5", "1.5", "100", "150"],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=6,
            close_time_index=None,
            min_length=7,
        )

        assert len(result) == 1
        assert result[0]["openTime"] == 2000


class TestParseKlinesOkx:
    """OKX-style klines: reversed, closeTime falls back to openTime, quoteVolume at 7 with fallback to 6."""

    def test_reversed_order(self) -> None:
        rows = [
            [3000, "1.5", "2.5", "1.0", "2.0", "200", "250", "300"],
            [1000, "1.0", "2.0", "0.5", "1.5", "100", "120", "150"],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=7,
            close_time_index=None,
            min_length=8,
        )

        assert len(result) == 2
        assert result[0]["openTime"] == 1000
        assert result[1]["openTime"] == 3000

    def test_quote_volume_primary_index_7(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "1.5", "100", "120", "150"],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=7,
            close_time_index=None,
            min_length=8,
        )

        assert result[0]["quoteVolume"] == 150.0

    def test_quote_volume_fallback_to_index_6(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "1.5", "100", "120", None],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=7,
            close_time_index=None,
            min_length=8,
        )

        assert result[0]["quoteVolume"] == 120.0

    def test_min_length_8_skips_short_rows(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "1.5", "100", "120"],
            [2000, "1", "2", "0.5", "1.5", "100", "120", "150"],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=7,
            close_time_index=None,
            min_length=8,
        )

        assert len(result) == 1
        assert result[0]["openTime"] == 2000

    def test_close_time_fallback_to_open_time(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "1.5", "100", "120", "150"],
        ]
        result = parse_klines(
            rows,
            reverse=True,
            quote_volume_index=7,
            close_time_index=None,
            min_length=8,
        )

        assert result[0]["closeTime"] == 1000


class TestParseKlinesEdgeCases:
    """Edge cases and boundary conditions."""

    def test_none_rows_input(self) -> None:
        assert parse_klines(None) == []

    def test_empty_rows_list(self) -> None:
        assert parse_klines([]) == []

    def test_all_rows_skipped(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", None, "100", 2000, "150"],
            [3000, "1.5", "2.5", "1.0", None, "200", 4000, "300"],
        ]
        assert parse_klines(rows) == []

    def test_close_value_zero_is_valid(self) -> None:
        rows = [
            [1000, "1", "2", "0.5", "0", "100", 2000, "150"],
        ]
        result = parse_klines(rows)

        assert len(result) == 1
        assert result[0]["close"] == 0.0

    def test_non_list_row_skipped(self) -> None:
        rows: list[Any] = [
            {"not": "a list"},
            [1000, "1", "2", "0.5", "1.5", "100", 2000, "150"],
        ]
        result = parse_klines(rows)

        assert len(result) == 1
        assert result[0]["openTime"] == 1000

    def test_string_numeric_values(self) -> None:
        rows = [
            ["1000", "1.0", "2.0", "0.5", "1.5", "100", "2000", "150"],
        ]
        result = parse_klines(rows)

        assert result[0]["openTime"] == 1000
        assert result[0]["close"] == 1.5
        assert result[0]["quoteVolume"] == 150.0
