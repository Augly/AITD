from __future__ import annotations

from pathlib import Path

from backend.exchanges.binance import BinanceGateway


def test_binance_gateway_does_not_use_deprecated_utcfromtimestamp() -> None:
    source = Path("backend/exchanges/binance.py").read_text(encoding="utf-8")

    assert "utcfromtimestamp(" not in source


def test_exchange_closed_trades_formats_closed_at_as_utc_zulu(monkeypatch) -> None:
    gateway = BinanceGateway()
    config = {"apiKey": "key", "apiSecret": "secret"}

    monkeypatch.setattr(gateway, "_signed_request_json", lambda *_args, **_kwargs: [
        {
            "income": "12.5",
            "symbol": "btcusdt",
            "time": 1713916800123,
            "asset": "usdt",
            "info": "realized",
            "tranId": 7,
        }
    ])

    closed_trades = gateway._exchange_closed_trades(config, "2026-04-24T00:00:00Z")

    assert len(closed_trades) == 1
    assert closed_trades[0]["closedAt"] == "2024-04-24T00:00:00Z"
    assert closed_trades[0]["asset"] == "USDT"
    assert closed_trades[0]["symbol"] == "BTCUSDT"
