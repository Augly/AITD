from __future__ import annotations

import pytest

from backend.utils import parse_klines


class TestParseKlines:
    def test_basic_parsing(self) -> None:
        rows = [
            [1000, "1.0", "2.0", "0.5", "1.5", "100"],
            [2000, "1.5", "2.5", "1.0", "2.0", "200"],
        ]
        result = parse_klines(rows)
        assert len(result) == 2
        assert result[0]["openTime"] == 1000
        assert result[0]["closeTime"] == 1000
        assert result[0]["open"] == 1.0
        assert result[0]["high"] == 2.0
        assert result[0]["low"] == 0.5
        assert result[0]["close"] == 1.5
        assert result[0]["volume"] == 100.0

    def test_empty_rows(self) -> None:
        assert parse_klines([]) == []
        assert parse_klines(None) == []

    def test_reverse(self) -> None:
        rows = [
            [1000, "1.0", "2.0", "0.5", "1.5", "100"],
            [2000, "1.5", "2.5", "1.0", "2.0", "200"],
        ]
        result = parse_klines(rows, reverse=True)
        assert result[0]["openTime"] == 2000
        assert result[1]["openTime"] == 1000

    def test_close_time_from_index(self) -> None:
        rows = [
            [1000, "1.0", "2.0", "0.5", "1.5", "100", 1999],
        ]
        result = parse_klines(rows, close_time_index=6)
        assert result[0]["closeTime"] == 1999

    def test_close_time_with_interval_ms(self) -> None:
        rows = [
            [1000, "1.0", "2.0", "0.5", "1.5", "100"],
        ]
        result = parse_klines(rows, close_time_index=None, interval_ms=60000)
        assert result[0]["closeTime"] == 61000

    def test_close_time_index_takes_priority_over_interval_ms(self) -> None:
        rows = [
            [1000, "1.0", "2.0", "0.5", "1.5", "100", 1999],
        ]
        result = parse_klines(rows, close_time_index=6, interval_ms=60000)
        assert result[0]["closeTime"] == 1999

    def test_close_time_fallback_to_open_time(self) -> None:
        rows = [
            [1000, "1.0", "2.0", "0.5", "1.5", "100"],
        ]
        result = parse_klines(rows, close_time_index=None, interval_ms=None)
        assert result[0]["closeTime"] == 1000

    def test_quote_volume(self) -> None:
        rows = [
            [1000, "1.0", "2.0", "0.5", "1.5", "100", "200"],
        ]
        result = parse_klines(rows, quote_volume_index=6)
        assert result[0]["quoteVolume"] == 200.0

    def test_min_length_filter(self) -> None:
        rows = [
            [1000, "1.0", "2.0"],
            [2000, "1.5", "2.5", "1.0", "2.0", "200"],
        ]
        result = parse_klines(rows, min_length=5)
        assert len(result) == 1
        assert result[0]["openTime"] == 2000

    def test_interval_ms_with_bybit_1m(self) -> None:
        rows = [
            [1609459200000, "29000.0", "29500.0", "28800.0", "29200.0", "100.5"],
        ]
        result = parse_klines(rows, close_time_index=None, interval_ms=60000)
        assert result[0]["openTime"] == 1609459200000
        assert result[0]["closeTime"] == 1609459260000

    def test_interval_ms_with_bybit_1h(self) -> None:
        rows = [
            [1609459200000, "29000.0", "29500.0", "28800.0", "29200.0", "100.5"],
        ]
        result = parse_klines(rows, close_time_index=None, interval_ms=3600000)
        assert result[0]["closeTime"] == 1609462800000
