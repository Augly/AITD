from __future__ import annotations

import time
from typing import Any

import pytest

from backend.exchanges.binance import BinanceGateway, EXCHANGE_INFO_CACHE_TTL_SECONDS


class TestBinanceSymbolInfoCache:
    """Tests for _symbol_info memory-level caching."""

    @pytest.fixture
    def gateway(self) -> BinanceGateway:
        return BinanceGateway()

    @pytest.fixture
    def mock_exchange_info(self) -> dict[str, Any]:
        return {
            "symbols": [
                {"symbol": "BTCUSDT", "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001"}]},
                {"symbol": "ETHUSDT", "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.01"}]},
            ]
        }

    def test_symbol_info_populates_cache_on_first_call(self, gateway: BinanceGateway, mock_exchange_info: dict[str, Any], monkeypatch: Any) -> None:
        """First call to _symbol_info triggers cache population."""
        call_count = 0

        def fake_exchange_info(_config: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return mock_exchange_info

        monkeypatch.setattr(gateway, "_exchange_info", fake_exchange_info)

        result = gateway._symbol_info({}, "BTCUSDT")

        assert result["symbol"] == "BTCUSDT"
        assert call_count == 1
        assert "BTCUSDT" in gateway._symbol_info_cache
        assert "ETHUSDT" in gateway._symbol_info_cache

    def test_symbol_info_reads_from_cache_on_subsequent_calls(self, gateway: BinanceGateway, mock_exchange_info: dict[str, Any], monkeypatch: Any) -> None:
        """Subsequent calls for the same or different symbols use cache."""
        call_count = 0

        def fake_exchange_info(_config: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return mock_exchange_info

        monkeypatch.setattr(gateway, "_exchange_info", fake_exchange_info)

        gateway._symbol_info({}, "BTCUSDT")
        gateway._symbol_info({}, "ETHUSDT")
        gateway._symbol_info({}, "btcusdt")

        assert call_count == 1

    def test_cache_expires_after_ttl(self, gateway: BinanceGateway, mock_exchange_info: dict[str, Any], monkeypatch: Any) -> None:
        """Cache refreshes after TTL expires."""
        call_count = 0

        def fake_exchange_info(_config: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return mock_exchange_info

        monkeypatch.setattr(gateway, "_exchange_info", fake_exchange_info)

        gateway._symbol_info({}, "BTCUSDT")
        assert call_count == 1

        gateway._symbol_info_cache_expiry = 0.0
        gateway._symbol_info({}, "ETHUSDT")

        assert call_count == 2

    def test_clear_symbol_cache_removes_all_entries(self, gateway: BinanceGateway, mock_exchange_info: dict[str, Any], monkeypatch: Any) -> None:
        """_clear_symbol_cache empties the cache and resets expiry."""
        monkeypatch.setattr(gateway, "_exchange_info", lambda _c: mock_exchange_info)

        gateway._symbol_info({}, "BTCUSDT")
        assert gateway._symbol_info_cache
        assert gateway._symbol_info_cache_expiry > 0
        assert gateway._symbol_info_cache_base_url == gateway.public_base_url

        gateway._clear_symbol_cache()

        assert gateway._symbol_info_cache == {}
        assert gateway._symbol_info_cache_expiry == 0.0
        assert gateway._symbol_info_cache_base_url is None

    def test_symbol_info_raises_on_unknown_symbol(self, gateway: BinanceGateway, monkeypatch: Any) -> None:
        """_symbol_info raises ValueError when symbol is not found."""
        monkeypatch.setattr(gateway, "_exchange_info", lambda _c: {"symbols": []})

        with pytest.raises(ValueError, match="Binance symbol not found: UNKNOWN"):
            gateway._symbol_info({}, "UNKNOWN")

    def test_validate_symbol_uses_cache(self, gateway: BinanceGateway, mock_exchange_info: dict[str, Any], monkeypatch: Any) -> None:
        """validate_symbol leverages the memory cache when available."""
        call_count = 0

        def fake_exchange_info(_config: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return mock_exchange_info

        monkeypatch.setattr(gateway, "_exchange_info", fake_exchange_info)

        assert gateway.validate_symbol("BTCUSDT") is True
        assert gateway.validate_symbol("ETHUSDT") is True
        assert gateway.validate_symbol("DOGEUSDT") is False

        assert call_count == 1

    def test_validate_symbol_returns_true_when_cache_refresh_fails(self, gateway: BinanceGateway, monkeypatch: Any) -> None:
        """validate_symbol preserves the existing fail-open behavior on refresh errors."""
        monkeypatch.setattr(gateway, "_symbol_info_cache_refresh", lambda _config=None: (_ for _ in ()).throw(RuntimeError("boom")))

        assert gateway.validate_symbol("DOGEUSDT") is True

    def test_symbol_info_cache_isolated_by_base_url(self, gateway: BinanceGateway, monkeypatch: Any) -> None:
        """Cache entries refresh when the exchange base URL changes."""
        responses = {
            "https://a.example": {"symbols": [{"symbol": "BTCUSDT"}]},
            "https://b.example": {"symbols": [{"symbol": "ETHUSDT"}]},
        }

        def fake_exchange_info(config: dict[str, Any]) -> dict[str, Any]:
            return responses[str(config.get("baseUrl"))]

        monkeypatch.setattr(gateway, "_exchange_info", fake_exchange_info)

        assert gateway._symbol_info({"baseUrl": "https://a.example"}, "BTCUSDT")["symbol"] == "BTCUSDT"
        assert gateway._symbol_info({"baseUrl": "https://b.example"}, "ETHUSDT")["symbol"] == "ETHUSDT"

    def test_validate_symbol_pattern_mismatch(self, gateway: BinanceGateway) -> None:
        """validate_symbol returns False for symbols not matching the pattern."""
        assert gateway.validate_symbol("INVALID") is False

    def test_cache_ttl_matches_file_cache(self, gateway: BinanceGateway, monkeypatch: Any) -> None:
        """Memory cache TTL is 6 hours, matching the file cache TTL."""
        assert gateway._symbol_info_cache_expiry == 0.0

        fixed_now = 1_700_000_000.0
        monkeypatch.setattr(time, "time", lambda: fixed_now)
        monkeypatch.setattr(gateway, "_exchange_info", lambda _c: {"symbols": [{"symbol": "BTCUSDT"}]})
        gateway._symbol_info_cache_refresh({})

        assert gateway._symbol_info_cache_expiry == fixed_now + EXCHANGE_INFO_CACHE_TTL_SECONDS

    def test_symbol_info_cache_refresh_uses_live_config_base_url(self, monkeypatch: Any) -> None:
        """validate_symbol should refresh cache against the configured live base URL."""
        live_config = {"baseUrl": "https://custom.example"}
        gateway = BinanceGateway(config_provider=lambda: live_config)
        seen_configs: list[dict[str, Any]] = []

        def fake_exchange_info(config: dict[str, Any]) -> dict[str, Any]:
            seen_configs.append(dict(config))
            return {"symbols": [{"symbol": "BTCUSDT"}]}

        monkeypatch.setattr(gateway, "_exchange_info", fake_exchange_info)

        assert gateway.validate_symbol("BTCUSDT") is True
        assert seen_configs == [live_config]
        assert gateway._symbol_info_cache_base_url == "https://custom.example"
