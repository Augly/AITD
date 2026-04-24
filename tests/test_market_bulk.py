from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.market import fetch_candidates_live_context, normalize_prompt_kline_feeds


class TestFetchCandidatesLiveContext:
    @pytest.fixture
    def mock_gateway(self) -> MagicMock:
        gateway = MagicMock()
        gateway.exchange_id = "binance"
        gateway.fetch_all_tickers_24h.return_value = [
            {"symbol": "BTCUSDT", "lastPrice": "50000", "priceChangePercent": "2.5"},
            {"symbol": "ETHUSDT", "lastPrice": "3000", "priceChangePercent": "-1.2"},
        ]
        gateway.fetch_all_premium_index.return_value = [
            {"symbol": "BTCUSDT", "markPrice": "50010", "lastFundingRate": "0.0001"},
            {"symbol": "ETHUSDT", "markPrice": "3005", "lastFundingRate": "-0.0002"},
        ]
        return gateway

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_returns_context_for_all_symbols(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}
        symbols = ["BTCUSDT", "ETHUSDT"]

        result = fetch_candidates_live_context(symbols)

        assert set(result.keys()) == set(symbols)
        mock_gateway.fetch_all_tickers_24h.assert_called_once()
        mock_gateway.fetch_all_premium_index.assert_called_once()

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_each_symbol_has_expected_structure(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}
        symbols = ["BTCUSDT"]

        result = fetch_candidates_live_context(symbols)

        ctx = result["BTCUSDT"]
        assert ctx["symbol"] == "BTCUSDT"
        assert "ticker24h" in ctx
        assert "premium" in ctx
        assert "promptKlineFeeds" in ctx
        assert "klinesByInterval" in ctx

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_ticker_data_mapped_correctly(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}
        symbols = ["BTCUSDT", "ETHUSDT"]

        result = fetch_candidates_live_context(symbols)

        assert result["BTCUSDT"]["ticker24h"]["lastPrice"] == "50000"
        assert result["ETHUSDT"]["ticker24h"]["lastPrice"] == "3000"

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_premium_data_mapped_correctly(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}
        symbols = ["BTCUSDT", "ETHUSDT"]

        result = fetch_candidates_live_context(symbols)

        assert result["BTCUSDT"]["premium"]["markPrice"] == "50010"
        assert result["ETHUSDT"]["premium"]["markPrice"] == "3005"

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_missing_symbol_returns_empty_dict(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}
        symbols = ["BTCUSDT", "MISSING"]

        result = fetch_candidates_live_context(symbols)

        assert result["MISSING"]["ticker24h"] == {}
        assert result["MISSING"]["premium"] == {}

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_symbol_case_insensitive_lookup(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}
        symbols = ["btcusdt"]

        result = fetch_candidates_live_context(symbols)

        assert result["btcusdt"]["ticker24h"]["lastPrice"] == "50000"
        assert result["btcusdt"]["symbol"] == "BTCUSDT"

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_klines_fetched_per_symbol(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": [{"close": 100}]}
        symbols = ["BTCUSDT", "ETHUSDT"]

        result = fetch_candidates_live_context(symbols)

        assert mock_fetch_klines.call_count == 2
        assert result["BTCUSDT"]["klinesByInterval"] == {"15m": [{"close": 100}]}

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_empty_symbols_returns_empty_dict(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}

        result = fetch_candidates_live_context([])

        assert result == {}
        mock_gateway.fetch_all_tickers_24h.assert_called_once()
        mock_gateway.fetch_all_premium_index.assert_called_once()

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_prompt_kline_feeds_passed_through(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}
        feeds = {"15m": {"enabled": True, "limit": 50}}
        symbols = ["BTCUSDT"]

        result = fetch_candidates_live_context(symbols, feeds)

        assert result["BTCUSDT"]["promptKlineFeeds"] == normalize_prompt_kline_feeds(feeds)

    @patch("backend.market.get_active_exchange_gateway")
    @patch("backend.market._fetch_prompt_kline_map")
    def test_exchange_id_passed_to_gateway(
        self,
        mock_fetch_klines: MagicMock,
        mock_get_gateway: MagicMock,
        mock_gateway: MagicMock,
    ) -> None:
        mock_get_gateway.return_value = mock_gateway
        mock_fetch_klines.return_value = {"15m": []}
        symbols = ["BTCUSDT"]

        fetch_candidates_live_context(symbols, exchange_id="bybit")

        mock_get_gateway.assert_called_once_with("bybit")
