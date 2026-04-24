from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.exchanges.okx import OkxGateway


class TestOkxFetchKlines:
    """Tests for OkxGateway.fetch_klines method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.gateway = OkxGateway()

    def test_fetch_klines_passes_interval_as_bar_and_limit_as_count(self) -> None:
        """fetch_klines should pass interval as bar and count as limit."""
        with patch.object(self.gateway, "_public_get_data", return_value=[]) as mock_get:
            self.gateway.fetch_klines("BTC-USDT-SWAP", "1m", 100)

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})

            assert "bar" in params
            assert "limit" in params
            assert params["bar"] == "1m"
            assert params["limit"] == 100

    def test_fetch_klines_clamps_limit_to_max(self) -> None:
        """Limit should be clamped to maximum of 300."""
        with patch.object(self.gateway, "_public_get_data", return_value=[]) as mock_get:
            self.gateway.fetch_klines("BTC-USDT-SWAP", "1m", 500)

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})

            assert params["bar"] == "1m"
            assert params["limit"] == 300

    def test_fetch_klines_clamps_limit_to_min(self) -> None:
        """Limit should be clamped to minimum of 1."""
        with patch.object(self.gateway, "_public_get_data", return_value=[]) as mock_get:
            self.gateway.fetch_klines("BTC-USDT-SWAP", "1m", 0)

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})

            assert params["bar"] == "1m"
            assert params["limit"] == 1

    def test_fetch_klines_passes_instId(self) -> None:
        """fetch_klines should pass normalized symbol as instId."""
        with patch.object(self.gateway, "_public_get_data", return_value=[]) as mock_get:
            self.gateway.fetch_klines("btc-usdt-swap", "1m", 50)

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})

            assert params["instId"] == "BTC-USDT-SWAP"

    def test_fetch_klines_invalid_interval_raises(self) -> None:
        """Invalid interval should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported OKX kline interval"):
            self.gateway.fetch_klines("BTC-USDT-SWAP", "invalid", 100)
