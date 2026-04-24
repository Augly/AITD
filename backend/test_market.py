from __future__ import annotations

import importlib

class _StubGateway:
    exchange_id = "binance"

    def validate_symbol(self, symbol: str) -> bool:
        return symbol in {"BTCUSDT", "ETHUSDT"}

    def candidate_symbol_hint(self) -> str:
        return "symbols"


def test_resolve_candidate_symbols_runs_dynamic_source_in_sandbox(monkeypatch) -> None:
    market = importlib.import_module("backend.market")

    universe = {
        "symbols": ["BTCUSDT", "BADPAIR"],
        "dynamicSource": {
            "enabled": True,
            "functionName": "load_candidate_symbols",
        },
    }

    monkeypatch.setattr(market, "get_active_exchange_gateway", lambda exchange_id=None: _StubGateway())
    monkeypatch.setattr(market, "read_network_settings", lambda: {"proxyEnabled": False})
    monkeypatch.setattr(market, "current_run_date", lambda: "2026-04-24")
    monkeypatch.setattr(market, "now_iso", lambda: "2026-04-24T12:00:00Z")

    source = (
        "def load_candidate_symbols(context):\n"
        "    print(context['scan_path'])\n"
        "    return {\n"
        "        'symbols': context['manual_symbols'],\n"
        "        'note': context['active_exchange'],\n"
        "    }\n"
    )

    resolved = market.resolve_candidate_symbols(
        universe=universe,
        code_override=source,
        exchange_id="binance",
    )

    assert resolved["mode"] == "python_function"
    assert resolved["enabled"] is True
    assert resolved["symbols"] == ["BTCUSDT"]
    assert resolved["invalidSymbols"] == ["BADPAIR"]
    assert resolved["note"] == "binance"
    assert resolved["stdout"].endswith("latest.json")
