from __future__ import annotations

from typing import Any

import pytest

from backend.exchanges.base import ConfigProvider, ExchangeGateway, NetworkSettingsProvider


class DummyGateway(ExchangeGateway):
    """Concrete implementation for testing the base class."""

    exchange_id = "dummy"
    display_name = "Dummy"
    market_label = "Test"
    default_backdrop_symbol = "TESTUSD"

    def validate_symbol(self, symbol: str) -> bool:
        return True

    def base_asset_from_symbol(self, symbol: str) -> str:
        return symbol

    def fetch_all_tickers_24h(self) -> list[dict[str, Any]]:
        return []

    def fetch_all_premium_index(self) -> list[dict[str, Any]]:
        return []

    def fetch_ticker_24h(self, symbol: str) -> dict[str, Any]:
        return {}

    def fetch_premium(self, symbol: str) -> dict[str, Any]:
        return {}

    def fetch_klines(self, symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
        return []

    def resolved_base_url(self, config: dict[str, Any]) -> str:
        return "https://dummy.exchange"

    def live_execution_status(
        self,
        live_config: dict[str, Any] | None = None,
        trading_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {}

    def fetch_account_snapshot(self, config: dict[str, Any], session_started_at: str | None = None) -> dict[str, Any]:
        return {}

    def normalize_quantity(
        self,
        config: dict[str, Any],
        symbol: str,
        *,
        reference_price: float | None = None,
        quantity: float | None = None,
        notional_usd: float | None = None,
    ) -> float:
        return 0.0

    def normalize_price(self, config: dict[str, Any], symbol: str, price: float) -> float:
        return price

    def apply_symbol_settings(self, config: dict[str, Any], symbol: str) -> None:
        pass

    def cancel_all_open_orders(self, config: dict[str, Any], symbol: str) -> Any:
        return None

    def place_market_order(
        self,
        config: dict[str, Any],
        *,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        return {}

    def place_protection_orders(
        self,
        config: dict[str, Any],
        *,
        symbol: str,
        position_side: str,
        stop_loss: float | None,
        take_profit: float | None,
    ) -> list[dict[str, Any]]:
        return []


class TestExchangeGatewayBase:
    """Tests for ExchangeGateway base class constructor injection."""

    def test_default_initialization(self) -> None:
        """Gateway initializes with no providers by default."""
        gateway = DummyGateway()

        assert gateway._config_provider is None
        assert gateway._network_settings_provider is None
        assert gateway._get_live_config() == {}
        assert gateway._get_network_settings() == {}

    def test_config_provider_injection(self) -> None:
        """Config provider is injected and callable."""
        expected_config = {"apiKey": "test-key", "enabled": True}

        def mock_config_provider() -> dict[str, Any]:
            return expected_config

        gateway = DummyGateway(config_provider=mock_config_provider)

        assert gateway._config_provider is mock_config_provider
        assert gateway._get_live_config() == expected_config

    def test_network_settings_provider_injection(self) -> None:
        """Network settings provider is injected and callable."""
        expected_settings = {"timeout": 30, "retries": 3}

        def mock_network_provider() -> dict[str, Any]:
            return expected_settings

        gateway = DummyGateway(network_settings_provider=mock_network_provider)

        assert gateway._network_settings_provider is mock_network_provider
        assert gateway._get_network_settings() == expected_settings

    def test_both_providers_injected(self) -> None:
        """Both providers can be injected simultaneously."""
        config = {"exchange": "dummy"}
        network = {"proxy": "http://proxy"}

        gateway = DummyGateway(
            config_provider=lambda: config,
            network_settings_provider=lambda: network,
        )

        assert gateway._get_live_config() == config
        assert gateway._get_network_settings() == network

    def test_class_attributes_preserved(self) -> None:
        """Class-level attributes remain accessible."""
        gateway = DummyGateway()

        assert gateway.exchange_id == "dummy"
        assert gateway.display_name == "Dummy"
        assert gateway.market_label == "Test"
        assert gateway.default_backdrop_symbol == "TESTUSD"

    def test_candidate_symbol_hint(self) -> None:
        """candidate_symbol_hint uses display_name and market_label."""
        gateway = DummyGateway()

        assert gateway.candidate_symbol_hint() == "Dummy Test symbols"

    def test_normalize_symbol(self) -> None:
        """normalize_symbol uppercases and strips input."""
        gateway = DummyGateway()

        assert gateway.normalize_symbol(" btcusdt ") == "BTCUSDT"
        assert gateway.normalize_symbol("") == ""


class TestProtocolTypes:
    """Tests for ConfigProvider and NetworkSettingsProvider Protocols."""

    def test_config_provider_protocol(self) -> None:
        """A callable returning dict satisfies ConfigProvider Protocol."""

        def provider() -> dict[str, Any]:
            return {"key": "value"}

        # Protocol is structural — no explicit inheritance needed
        assert callable(provider)
        result = provider()
        assert isinstance(result, dict)

    def test_network_settings_provider_protocol(self) -> None:
        """A callable returning dict satisfies NetworkSettingsProvider Protocol."""

        def provider() -> dict[str, Any]:
            return {"timeout": 10}

        assert callable(provider)
        result = provider()
        assert isinstance(result, dict)

    def test_lambda_satisfies_protocol(self) -> None:
        """Lambdas also satisfy the Protocol."""
        provider: ConfigProvider = lambda: {"apiKey": "secret"}

        assert provider() == {"apiKey": "secret"}

    def test_partial_satisfies_protocol(self) -> None:
        """functools.partial can be used to bind arguments."""
        from functools import partial

        def provider(defaults: dict[str, Any]) -> dict[str, Any]:
            return defaults

        bound = partial(provider, {"timeout": 45})
        result = bound()
        assert result == {"timeout": 45}


class TestBackwardCompatibility:
    """Ensure existing abstract method signatures remain unchanged."""

    def test_all_abstract_methods_exist(self) -> None:
        """All expected abstract methods are still defined on the base class."""
        abstract_methods = {
            "validate_symbol",
            "base_asset_from_symbol",
            "fetch_all_tickers_24h",
            "fetch_all_premium_index",
            "fetch_ticker_24h",
            "fetch_premium",
            "fetch_klines",
            "resolved_base_url",
            "live_execution_status",
            "fetch_account_snapshot",
            "normalize_quantity",
            "normalize_price",
            "apply_symbol_settings",
            "cancel_all_open_orders",
            "place_market_order",
            "place_protection_orders",
        }

        actual_methods = {
            name
            for name in dir(ExchangeGateway)
            if getattr(getattr(ExchangeGateway, name), "__isabstractmethod__", False)
        }

        assert actual_methods == abstract_methods

    def test_no_config_import_in_base(self) -> None:
        """base.py must not import from the config module."""
        import backend.exchanges.base as base_module

        # Check that no attribute from config module is imported
        assert not hasattr(base_module, "read_live_trading_config")
        assert not hasattr(base_module, "read_network_settings")
        assert not hasattr(base_module, "read_trading_settings")
