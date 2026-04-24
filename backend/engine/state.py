from __future__ import annotations

import datetime
import time
from copy import deepcopy
from typing import Any

from ..config import read_trading_settings
from ..exchanges import base_asset_for_symbol
from ..utils import DATA_DIR, current_run_date, now_iso, num, read_json, write_json


STATE_PATH = DATA_DIR / "trading_agent_state.json"
DECISIONS_DIR = DATA_DIR / "trading-agent" / "decisions"


def clean_mode(value: Any) -> str:
    return "live" if str(value or "paper").strip().lower() == "live" else "paper"


def empty_trading_account(initial_capital_usd: float, source: str) -> dict[str, Any]:
    return {
        "initialCapitalUsd": initial_capital_usd,
        "accountSource": source,
        "highWatermarkEquity": initial_capital_usd,
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
    }


def default_state(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or read_trading_settings()
    return {
        "version": 2,
        "updatedAt": now_iso(),
        "paper": empty_trading_account(settings["initialCapitalUsd"], "paper"),
        "live": empty_trading_account(settings["initialCapitalUsd"], "exchange"),
        "adaptive": {
            "updatedAt": None,
            "notes": [
                "The Python build keeps execution logic local and uses the editable trade-logic fields only for trade judgment.",
                "Paper mode and live mode can be started independently from the dashboard.",
            ],
        },
    }


def normalize_position(position: dict[str, Any]) -> dict[str, Any]:
    side = "short" if str(position.get("side") or "long").lower() == "short" else "long"
    symbol = str(position.get("symbol") or "").upper()
    exchange_id = str(position.get("source") or "binance").strip().lower() or "binance"
    quantity = num(position.get("quantity")) or 0
    entry_price = num(position.get("entryPrice")) or 0
    notional = num(position.get("notionalUsd")) or quantity * entry_price
    return {
        "id": str(position.get("id") or f"{symbol}-{int(time.time() * 1000)}"),
        "symbol": symbol,
        "baseAsset": str(position.get("baseAsset") or base_asset_for_symbol(symbol, exchange_id)),
        "side": side,
        "quantity": quantity,
        "initialQuantity": num(position.get("initialQuantity")) or quantity,
        "entryPrice": entry_price,
        "notionalUsd": notional,
        "initialNotionalUsd": num(position.get("initialNotionalUsd")) or notional,
        "stopLoss": num(position.get("stopLoss")),
        "takeProfit": num(position.get("takeProfit")),
        "lastMarkPrice": num(position.get("lastMarkPrice")) or entry_price,
        "lastMarkTime": position.get("lastMarkTime") or now_iso(),
        "leverage": num(position.get("leverage")) or 1,
        "status": "open",
        "openedAt": position.get("openedAt"),
        "updatedAt": position.get("updatedAt") or now_iso(),
        "source": position.get("source") or "trading_agent",
        "entryReason": position.get("entryReason") or "",
        "decisionId": position.get("decisionId"),
        "confidenceScore": num(position.get("confidenceScore")),
    }


def normalize_trade(trade: dict[str, Any]) -> dict[str, Any]:
    symbol = str(trade.get("symbol") or "").upper()
    exchange_id = str(trade.get("source") or "binance").strip().lower() or "binance"
    return {
        "id": str(trade.get("id") or f"trade-{int(time.time() * 1000)}"),
        "positionId": trade.get("positionId"),
        "symbol": symbol,
        "baseAsset": str(trade.get("baseAsset") or base_asset_for_symbol(symbol, exchange_id)),
        "side": "short" if str(trade.get("side") or "long").lower() == "short" else "long",
        "quantity": num(trade.get("quantity")) or 0,
        "entryPrice": num(trade.get("entryPrice")) or 0,
        "exitPrice": num(trade.get("exitPrice")) or 0,
        "notionalUsd": num(trade.get("notionalUsd")) or 0,
        "realizedPnl": num(trade.get("realizedPnl")) or 0,
        "openedAt": trade.get("openedAt"),
        "closedAt": trade.get("closedAt") or now_iso(),
        "exitReason": trade.get("exitReason") or "manual",
        "decisionId": trade.get("decisionId"),
    }


def normalize_exchange_closed_trade(trade: dict[str, Any]) -> dict[str, Any]:
    symbol = str(trade.get("symbol") or "").upper()
    exchange_id = str(trade.get("source") or "binance").strip().lower() or "binance"
    return {
        "id": str(trade.get("id") or f"exchange-close-{int(time.time() * 1000)}"),
        "symbol": symbol,
        "baseAsset": str(trade.get("baseAsset") or base_asset_for_symbol(symbol, exchange_id)),
        "realizedPnl": num(trade.get("realizedPnl")) or 0,
        "asset": str(trade.get("asset") or "USDT").strip().upper() or "USDT",
        "closedAt": trade.get("closedAt") or now_iso(),
        "info": str(trade.get("info") or "").strip(),
        "source": str(trade.get("source") or exchange_id),
    }


def normalize_order(order: dict[str, Any]) -> dict[str, Any]:
    symbol = str(order.get("symbol") or "").upper()
    exchange_id = str(order.get("source") or "binance").strip().lower() or "binance"
    return {
        "id": str(order.get("id") or f"order-{int(time.time() * 1000)}"),
        "symbol": symbol,
        "baseAsset": str(order.get("baseAsset") or base_asset_for_symbol(symbol, exchange_id)),
        "side": str(order.get("side") or "").upper(),
        "positionSide": str(order.get("positionSide") or "").upper(),
        "type": str(order.get("type") or "").upper(),
        "status": str(order.get("status") or "").upper(),
        "price": num(order.get("price")),
        "triggerPrice": num(order.get("triggerPrice")),
        "quantity": num(order.get("quantity")),
        "reduceOnly": order.get("reduceOnly") is True,
        "closePosition": order.get("closePosition") is True,
        "workingType": str(order.get("workingType") or "").upper(),
        "source": str(order.get("source") or exchange_id),
        "updatedAt": order.get("updatedAt") or now_iso(),
    }


def derive_session_started_at(book: dict[str, Any]) -> str | None:
    candidates: list[str] = []
    if book.get("sessionStartedAt"):
        candidates.append(str(book.get("sessionStartedAt")))
    if book.get("lastDecisionAt"):
        candidates.append(str(book.get("lastDecisionAt")))
    for decision in book.get("decisions", []):
        if isinstance(decision, dict):
            if decision.get("startedAt"):
                candidates.append(str(decision.get("startedAt")))
            if decision.get("finishedAt"):
                candidates.append(str(decision.get("finishedAt")))
    for trade in book.get("closedTrades", []):
        if isinstance(trade, dict):
            if trade.get("openedAt"):
                candidates.append(str(trade.get("openedAt")))
            if trade.get("closedAt"):
                candidates.append(str(trade.get("closedAt")))
    for position in book.get("openPositions", []):
        if isinstance(position, dict) and position.get("openedAt"):
            candidates.append(str(position.get("openedAt")))

    parsed: list[tuple[float, str]] = []
    for value in candidates:
        try:
            dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            continue
        parsed.append((dt.timestamp(), value))
    if not parsed:
        return None
    parsed.sort(key=lambda item: item[0])
    return parsed[0][1]


def normalize_decision(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(decision.get("id") or f"decision-{int(time.time() * 1000)}"),
        "startedAt": decision.get("startedAt") or now_iso(),
        "finishedAt": decision.get("finishedAt") or now_iso(),
        "runnerReason": decision.get("runnerReason") or "manual",
        "mode": clean_mode(decision.get("mode")),
        "prompt": str(decision.get("prompt") or ""),
        "promptSummary": str(decision.get("promptSummary") or ""),
        "output": decision.get("output") if isinstance(decision.get("output"), dict) else {},
        "rawModelResponse": decision.get("rawModelResponse") if isinstance(decision.get("rawModelResponse"), dict) else {},
        "actions": decision.get("actions") if isinstance(decision.get("actions"), list) else [],
        "warnings": decision.get("warnings") if isinstance(decision.get("warnings"), list) else [],
        "candidateUniverse": decision.get("candidateUniverse") if isinstance(decision.get("candidateUniverse"), list) else [],
        "accountBefore": decision.get("accountBefore") if isinstance(decision.get("accountBefore"), dict) else {},
        "accountAfter": decision.get("accountAfter") if isinstance(decision.get("accountAfter"), dict) else {},
    }


def read_trading_state(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or read_trading_settings()
    saved = read_json(STATE_PATH, {})
    state = default_state(settings)
    for key in ("paper", "live"):
        source = "exchange" if key == "live" else "paper"
        seed = saved.get(key) if isinstance(saved.get(key), dict) else {}
        normalized = {
            **empty_trading_account(settings["initialCapitalUsd"], source),
            **seed,
            "initialCapitalUsd": num(seed.get("initialCapitalUsd")) or settings["initialCapitalUsd"],
            "accountSource": seed.get("accountSource") or source,
            "highWatermarkEquity": num(seed.get("highWatermarkEquity")) or settings["initialCapitalUsd"],
            "exchangeWalletBalanceUsd": num(seed.get("exchangeWalletBalanceUsd")),
            "exchangeEquityUsd": num(seed.get("exchangeEquityUsd")),
            "exchangeAvailableBalanceUsd": num(seed.get("exchangeAvailableBalanceUsd")),
            "exchangeUnrealizedPnlUsd": num(seed.get("exchangeUnrealizedPnlUsd")),
            "exchangeNetCashflowUsd": num(seed.get("exchangeNetCashflowUsd")),
            "exchangeIncomeRealizedPnlUsd": num(seed.get("exchangeIncomeRealizedPnlUsd")),
            "exchangeFundingFeeUsd": num(seed.get("exchangeFundingFeeUsd")),
            "exchangeCommissionUsd": num(seed.get("exchangeCommissionUsd")),
            "exchangeOtherIncomeUsd": num(seed.get("exchangeOtherIncomeUsd")),
            "exchangeAccountingUpdatedAt": seed.get("exchangeAccountingUpdatedAt"),
            "exchangeAccountingNote": seed.get("exchangeAccountingNote"),
            "openPositions": [normalize_position(item) for item in seed.get("openPositions", [])],
            "openOrders": [normalize_order(item) for item in seed.get("openOrders", [])],
            "exchangeClosedTrades": [normalize_exchange_closed_trade(item) for item in seed.get("exchangeClosedTrades", [])],
            "closedTrades": [normalize_trade(item) for item in seed.get("closedTrades", [])],
            "decisions": [normalize_decision(item) for item in seed.get("decisions", [])],
        }
        state[key] = normalized
    adaptive = saved.get("adaptive") if isinstance(saved.get("adaptive"), dict) else {}
    state["adaptive"] = {
        "updatedAt": adaptive.get("updatedAt"),
        "notes": adaptive.get("notes") if isinstance(adaptive.get("notes"), list) else state["adaptive"]["notes"],
    }
    state["updatedAt"] = saved.get("updatedAt") or state["updatedAt"]
    return state


def write_trading_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(state)
    for key in ("paper", "live"):
        payload[key]["openPositions"] = [normalize_position(item) for item in payload[key].get("openPositions", [])]
        payload[key]["openOrders"] = [normalize_order(item) for item in payload[key].get("openOrders", [])][-80:]
        payload[key]["exchangeClosedTrades"] = [normalize_exchange_closed_trade(item) for item in payload[key].get("exchangeClosedTrades", [])][-400:]
        payload[key]["closedTrades"] = [normalize_trade(item) for item in payload[key].get("closedTrades", [])][-400:]
        payload[key]["decisions"] = [normalize_decision(item) for item in payload[key].get("decisions", [])][-40:]
    payload["updatedAt"] = now_iso()
    write_json(STATE_PATH, payload)
    return payload


def archive_decision(decision: dict[str, Any]) -> None:
    run_date = current_run_date()
    path = DECISIONS_DIR / run_date / f"{decision['id']}.json"
    write_json(path, decision)
