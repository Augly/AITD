from __future__ import annotations

import threading

import pytest

from backend.exchanges.binance import BinanceGateway
from backend.exchanges.binance import EXCHANGE_INFO_TTL_MS
from backend.exchanges.binance import EXCHANGE_INFO_TTL_SECONDS


class TestExchangeInfoCache:
    def test_uses_memory_cache_on_second_call(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}
        call_count = 0

        def fake_cached_get_json(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return {"symbols": [{"symbol": "BTCUSDT"}]}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)

        result1 = gateway._exchange_info(config)
        result2 = gateway._exchange_info(config)

        assert call_count == 1
        assert result1 == result2 == {"symbols": [{"symbol": "BTCUSDT"}]}
        cache_key = "https://test.binance.com/fapi/v1/exchangeInfo"
        cached_entry = gateway._exchange_info_cache[cache_key]
        assert cached_entry["payload"] == {"symbols": [{"symbol": "BTCUSDT"}]}
        assert cached_entry["expires_at_ms"] > 0

    def test_refreshes_after_ttl_expires(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}
        call_count = 0

        def fake_cached_get_json(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return {"symbols": [{"symbol": f"CALL{call_count}"}]}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)

        result1 = gateway._exchange_info(config)
        cache_key = "https://test.binance.com/fapi/v1/exchangeInfo"
        gateway._exchange_info_cache[cache_key]["expires_at_ms"] = 0
        result2 = gateway._exchange_info(config)

        assert call_count == 2
        assert result1 == {"symbols": [{"symbol": "CALL1"}]}
        assert result2 == {"symbols": [{"symbol": "CALL2"}]}

    def test_thread_safe_concurrent_access(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}
        call_count = 0
        lock = threading.Lock()
        release_fetch = threading.Event()
        entered_fetch = threading.Event()

        def slow_cached_get_json(*_args, **_kwargs):
            nonlocal call_count
            with lock:
                call_count += 1
            entered_fetch.set()
            release_fetch.wait(timeout=1)
            return {"symbols": [{"symbol": "BTCUSDT"}]}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", slow_cached_get_json)

        results: list[dict] = []
        result_lock = threading.Lock()
        start_barrier = threading.Barrier(11)

        def worker() -> None:
            start_barrier.wait()
            result = gateway._exchange_info(config)
            with result_lock:
                results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        start_barrier.wait()
        assert entered_fetch.wait(timeout=1)
        release_fetch.set()
        for t in threads:
            t.join()

        assert call_count == 1
        assert len(results) == 10
        assert all(r == {"symbols": [{"symbol": "BTCUSDT"}]} for r in results)

    def test_empty_payload_returns_empty_dict(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}

        monkeypatch.setattr(
            "backend.exchanges.binance.cached_get_json", lambda *_args, **_kwargs: None
        )

        result = gateway._exchange_info(config)

        assert result == {}
        cache_key = "https://test.binance.com/fapi/v1/exchangeInfo"
        assert gateway._exchange_info_cache[cache_key]["payload"] == {}

    def test_symbol_info_uses_cached_exchange_info(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}
        exchange_info_calls = 0

        def fake_cached_get_json(*_args, **_kwargs):
            nonlocal exchange_info_calls
            exchange_info_calls += 1
            return {"symbols": [{"symbol": "ETHUSDT", "filters": []}]}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)

        info1 = gateway._symbol_info(config, "ETHUSDT")
        info2 = gateway._symbol_info(config, "ETHUSDT")

        assert exchange_info_calls == 1
        assert info1 == info2

    def test_cache_is_scoped_by_base_url(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        urls: list[str] = []

        def fake_cached_get_json(url, *_args, **_kwargs):
            urls.append(url)
            if "testnet" in url:
                return {"symbols": [{"symbol": "BTCUSDT"}]}
            return {"symbols": [{"symbol": "ETHUSDT"}]}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)

        testnet_result = gateway._exchange_info({"baseUrl": "https://testnet.binance.com"})
        prod_result = gateway._exchange_info({"baseUrl": "https://fapi.binance.com"})

        assert testnet_result == {"symbols": [{"symbol": "BTCUSDT"}]}
        assert prod_result == {"symbols": [{"symbol": "ETHUSDT"}]}
        assert urls == [
            "https://testnet.binance.com/fapi/v1/exchangeInfo",
            "https://fapi.binance.com/fapi/v1/exchangeInfo",
        ]

    def test_symbol_info_index_is_scoped_by_base_url(self, monkeypatch) -> None:
        gateway = BinanceGateway()

        def fake_cached_get_json(url, *_args, **_kwargs):
            if "testnet" in url:
                return {"symbols": [{"symbol": "BTCUSDT", "filters": [{"stepSize": "0.001"}]}]}
            return {"symbols": [{"symbol": "ETHUSDT", "filters": [{"stepSize": "0.01"}]}]}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)

        testnet_info = gateway._symbol_info({"baseUrl": "https://testnet.binance.com"}, "BTCUSDT")
        prod_info = gateway._symbol_info({"baseUrl": "https://fapi.binance.com"}, "ETHUSDT")

        assert testnet_info["symbol"] == "BTCUSDT"
        assert prod_info["symbol"] == "ETHUSDT"

        with pytest.raises(ValueError, match="symbol not found: ETHUSDT"):
            gateway._symbol_info({"baseUrl": "https://testnet.binance.com"}, "ETHUSDT")

    def test_cache_ttl_matches_file_cache_policy(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}
        captured_kwargs: dict[str, int] = {}
        fixed_time = 1_700_000_000.0

        def fake_cached_get_json(*_args, **kwargs):
            captured_kwargs["ttl_seconds"] = kwargs["ttl_seconds"]
            return {"symbols": []}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)
        monkeypatch.setattr("time.time", lambda: fixed_time)

        gateway._exchange_info(config)

        cache_key = "https://test.binance.com/fapi/v1/exchangeInfo"
        cached_entry = gateway._exchange_info_cache[cache_key]
        now_ms = int(fixed_time * 1000)
        assert captured_kwargs["ttl_seconds"] == EXCHANGE_INFO_TTL_SECONDS
        assert cached_entry["expires_at_ms"] - now_ms == EXCHANGE_INFO_TTL_MS

    def test_symbol_info_uses_o1_index_lookup(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}
        call_count = 0

        def fake_cached_get_json(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "symbols": [
                    {"symbol": "BTCUSDT", "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001"}]},
                    {"symbol": "ETHUSDT", "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.01"}]},
                    {"symbol": "SOLUSDT", "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.1"}]},
                ]
            }

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)

        # First call builds the index
        info1 = gateway._symbol_info(config, "ETHUSDT")
        assert info1["symbol"] == "ETHUSDT"
        assert call_count == 1

        # Second call hits the O(1) index directly without calling _exchange_info
        info2 = gateway._symbol_info(config, "BTCUSDT")
        assert info2["symbol"] == "BTCUSDT"
        assert call_count == 1  # No additional fetch

        info3 = gateway._symbol_info(config, "SOLUSDT")
        assert info3["symbol"] == "SOLUSDT"
        assert call_count == 1  # Still no additional fetch

    def test_symbol_info_index_is_built_on_cache_refresh(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}
        call_count = 0

        def fake_cached_get_json(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"symbols": [{"symbol": "BTCUSDT", "filters": []}]}
            return {"symbols": [{"symbol": "ETHUSDT", "filters": []}]}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)

        # First fetch
        gateway._symbol_info(config, "BTCUSDT")
        assert gateway._symbol_index == {
            "https://test.binance.com/fapi/v1/exchangeInfo": {
                "BTCUSDT": {"symbol": "BTCUSDT", "filters": []}
            }
        }

        # Expire cache and trigger refresh
        cache_key = "https://test.binance.com/fapi/v1/exchangeInfo"
        gateway._exchange_info_cache[cache_key]["expires_at_ms"] = 0

        gateway._symbol_info(config, "ETHUSDT")
        assert gateway._symbol_index == {
            "https://test.binance.com/fapi/v1/exchangeInfo": {
                "ETHUSDT": {"symbol": "ETHUSDT", "filters": []}
            }
        }
        assert call_count == 2

    def test_symbol_info_refreshes_same_symbol_after_ttl_expires(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}
        call_count = 0

        def fake_cached_get_json(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"symbols": [{"symbol": "BTCUSDT", "filters": [{"stepSize": "0.001"}]}]}
            return {"symbols": [{"symbol": "BTCUSDT", "filters": [{"stepSize": "0.1"}]}]}

        monkeypatch.setattr("backend.exchanges.binance.cached_get_json", fake_cached_get_json)

        first = gateway._symbol_info(config, "BTCUSDT")
        cache_key = "https://test.binance.com/fapi/v1/exchangeInfo"
        gateway._exchange_info_cache[cache_key]["expires_at_ms"] = 0

        refreshed = gateway._symbol_info(config, "BTCUSDT")

        assert first["filters"][0]["stepSize"] == "0.001"
        assert refreshed["filters"][0]["stepSize"] == "0.1"
        assert call_count == 2

    def test_symbol_info_raises_for_unknown_symbol(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}

        monkeypatch.setattr(
            "backend.exchanges.binance.cached_get_json",
            lambda *_args, **_kwargs: {"symbols": [{"symbol": "BTCUSDT"}]},
        )

        gateway._symbol_info(config, "BTCUSDT")

        with pytest.raises(ValueError, match="symbol not found: UNKNOWN"):
            gateway._symbol_info(config, "UNKNOWN")

    def test_symbol_index_skips_invalid_entries(self, monkeypatch) -> None:
        gateway = BinanceGateway()
        config = {"baseUrl": "https://test.binance.com"}

        monkeypatch.setattr(
            "backend.exchanges.binance.cached_get_json",
            lambda *_args, **_kwargs: {
                "symbols": [
                    {"symbol": "BTCUSDT"},
                    {"symbol": None},
                    {"symbol": ""},
                    "not_a_dict",
                    {"filters": []},
                ]
            },
        )

        gateway._exchange_info(config)
        assert gateway._symbol_index == {
            "https://test.binance.com/fapi/v1/exchangeInfo": {
                "BTCUSDT": {"symbol": "BTCUSDT"}
            }
        }
