"""Tests for AccountSummaryCache."""

from __future__ import annotations

import pytest

from backend.engine_core import AccountSummaryCache


def _make_book(**overrides):
    """Build a minimal book dict for cache key testing."""
    return {
        "initialCapitalUsd": 10000.0,
        "accountSource": "paper",
        "highWatermarkEquity": 10000.0,
        "sessionStartedAt": None,
        "lastDecisionAt": None,
        "circuitBreakerTripped": False,
        "circuitBreakerReason": None,
        "exchangeWalletBalanceUsd": None,
        "exchangeEquityUsd": None,
        "exchangeAvailableBalanceUsd": None,
        "exchangeUnrealizedPnlUsd": None,
        "exchangeNetCashflowUsd": None,
        "exchangeIncomeRealizedPnlUsd": None,
        "exchangeFundingFeeUsd": None,
        "exchangeCommissionUsd": None,
        "exchangeOtherIncomeUsd": None,
        "exchangeAccountingUpdatedAt": None,
        "exchangeAccountingNote": None,
        "openPositions": [],
        "openOrders": [],
        "exchangeClosedTrades": [],
        "closedTrades": [],
        "decisions": [],
        **overrides,
    }


def _make_settings(**overrides):
    return {
        "initialCapitalUsd": 10000.0,
        "maxGrossExposurePct": 100.0,
        "maxAccountDrawdownPct": 20.0,
        "mode": "paper",
        **overrides,
    }


def _fake_summarize(book, settings):
    return {"equityUsd": book["initialCapitalUsd"], "computed": True}


class TestAccountSummaryCache:
    def test_cache_miss_on_first_call(self):
        cache = AccountSummaryCache()
        book = _make_book()
        settings = _make_settings()
        result = cache.get_or_compute(book, settings, _fake_summarize)
        assert result == {"equityUsd": 10000.0, "computed": True}

    def test_cache_hit_on_identical_state(self):
        cache = AccountSummaryCache()
        book = _make_book()
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is result2

    def test_cache_invalidated_when_position_added(self):
        cache = AccountSummaryCache()
        book = _make_book()
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)

        book["openPositions"].append(
            {
                "id": "pos-1",
                "symbol": "BTCUSDT",
                "side": "long",
                "quantity": 1.0,
                "entryPrice": 50000.0,
                "notionalUsd": 50000.0,
                "lastMarkPrice": 51000.0,
            }
        )
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2

    def test_cache_invalidated_when_position_quantity_changes(self):
        cache = AccountSummaryCache()
        book = _make_book(
            openPositions=[
                {
                    "id": "pos-1",
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "quantity": 1.0,
                    "entryPrice": 50000.0,
                    "notionalUsd": 50000.0,
                    "lastMarkPrice": 51000.0,
                }
            ]
        )
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)

        book["openPositions"][0]["quantity"] = 2.0
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2

    def test_cache_invalidated_when_closed_trade_added(self):
        cache = AccountSummaryCache()
        book = _make_book()
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)

        book["closedTrades"].append(
            {"id": "trade-1", "symbol": "BTCUSDT", "realizedPnl": 100.0}
        )
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2

    def test_cache_invalidated_when_settings_change(self):
        cache = AccountSummaryCache()
        book = _make_book()
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)

        settings["maxGrossExposurePct"] = 50.0
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2

    def test_cache_hit_after_invalidate(self):
        cache = AccountSummaryCache()
        book = _make_book()
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)
        cache.invalidate()
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2
        result3 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result2 is result3

    def test_cache_invalidated_when_high_watermark_changes(self):
        cache = AccountSummaryCache()
        book = _make_book()
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)

        book["highWatermarkEquity"] = 12000.0
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2

    def test_cache_invalidated_when_circuit_breaker_trips(self):
        cache = AccountSummaryCache()
        book = _make_book()
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)

        book["circuitBreakerTripped"] = True
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2

    def test_cache_invalidated_when_exchange_equity_changes(self):
        cache = AccountSummaryCache()
        book = _make_book(accountSource="exchange")
        settings = _make_settings(mode="live")
        result1 = cache.get_or_compute(book, settings, _fake_summarize)

        book["exchangeEquityUsd"] = 9500.0
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2

    def test_compute_fn_receives_correct_args(self):
        cache = AccountSummaryCache()
        received = {}

        def capture(book, settings):
            received["book"] = book
            received["settings"] = settings
            return {"captured": True}

        book = _make_book()
        settings = _make_settings()
        cache.get_or_compute(book, settings, capture)
        assert received["book"] is book
        assert received["settings"] is settings

    def test_cache_hit_with_multiple_positions(self):
        cache = AccountSummaryCache()
        book = _make_book(
            openPositions=[
                {
                    "id": "pos-1",
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "quantity": 1.0,
                    "entryPrice": 50000.0,
                    "notionalUsd": 50000.0,
                    "lastMarkPrice": 51000.0,
                },
                {
                    "id": "pos-2",
                    "symbol": "ETHUSDT",
                    "side": "short",
                    "quantity": 2.0,
                    "entryPrice": 3000.0,
                    "notionalUsd": 6000.0,
                    "lastMarkPrice": 2900.0,
                },
            ]
        )
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is result2

    def test_cache_invalidated_when_position_mark_price_changes(self):
        cache = AccountSummaryCache()
        book = _make_book(
            openPositions=[
                {
                    "id": "pos-1",
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "quantity": 1.0,
                    "entryPrice": 50000.0,
                    "notionalUsd": 50000.0,
                    "lastMarkPrice": 51000.0,
                }
            ]
        )
        settings = _make_settings()
        result1 = cache.get_or_compute(book, settings, _fake_summarize)

        book["openPositions"][0]["lastMarkPrice"] = 52000.0
        result2 = cache.get_or_compute(book, settings, _fake_summarize)
        assert result1 is not result2
