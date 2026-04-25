from __future__ import annotations

import json
import time

from copy import deepcopy
from typing import Any, Callable


class AccountSummaryCache:
    """Cache for summarize_account results, invalidated when book state changes."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] | None = None
        self._key: str | None = None

    def _compute_key(self, book: dict[str, Any], settings: dict[str, Any]) -> str:
        """Build a cache key from book mutable state and relevant settings."""
        open_positions = book.get("openPositions", [])
        closed_trades = book.get("closedTrades", [])
        open_orders = book.get("openOrders", [])
        exchange_closed_trades = book.get("exchangeClosedTrades", [])

        # Use lengths as a fast fingerprint; include key scalar fields
        # that affect summarize_account output.
        parts = [
            str(len(open_positions)),
            str(len(closed_trades)),
            str(len(open_orders)),
            str(len(exchange_closed_trades)),
            str(book.get("highWatermarkEquity")),
            str(book.get("exchangeEquityUsd")),
            str(book.get("circuitBreakerTripped")),
            str(book.get("lastDecisionAt")),
            str(book.get("exchangeWalletBalanceUsd")),
            str(book.get("exchangeUnrealizedPnlUsd")),
            str(book.get("exchangeNetCashflowUsd")),
            str(book.get("exchangeIncomeRealizedPnlUsd")),
            str(book.get("exchangeFundingFeeUsd")),
            str(book.get("exchangeCommissionUsd")),
            str(book.get("exchangeOtherIncomeUsd")),
            str(book.get("exchangeAccountingUpdatedAt")),
            str(settings.get("initialCapitalUsd")),
            str(settings.get("maxGrossExposurePct")),
            str(settings.get("maxAccountDrawdownPct")),
            str(settings.get("mode")),
        ]

        # Include position IDs and quantities for fine-grained change detection
        # (positions may change size without length changing)
        for pos in open_positions:
            parts.append(str(pos.get("id")))
            parts.append(str(pos.get("quantity")))
            parts.append(str(pos.get("entryPrice")))
            parts.append(str(pos.get("notionalUsd")))
            parts.append(str(pos.get("lastMarkPrice")))

        for trade in closed_trades:
            parts.append(str(trade.get("id")))
            parts.append(str(trade.get("realizedPnl")))

        return "|".join(parts)

    def get_or_compute(
        self,
        book: dict[str, Any],
        settings: dict[str, Any],
        compute_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Return cached summary if book state hasn't changed; otherwise compute and cache."""
        key = self._compute_key(book, settings)
        if self._key == key and self._cache is not None:
            return self._cache
        self._cache = compute_fn(book, settings)
        self._key = key
        return self._cache

    def invalidate(self) -> None:
        """Explicitly clear the cache."""
        self._cache = None
        self._key = None

from .config import (
    read_fixed_universe,
    read_live_trading_config,
    read_llm_provider,
    read_prompt_settings,
    read_trading_settings,
)
from .engine.state import (
    archive_decision,
    derive_session_started_at,
    empty_trading_account,
    normalize_decision,
    normalize_exchange_closed_trade,
    normalize_order,
    normalize_position,
    normalize_trade,
    read_trading_state,
    write_trading_state,
)
from .exchanges import get_active_exchange_gateway
from .live_trading import (
    apply_symbol_settings,
    cancel_all_open_orders,
    fetch_account_snapshot,
    live_execution_status,
    normalize_quantity,
    place_market_order,
    place_protection_orders,
)
from .llm import generate_trading_decision, provider_status
from .market import (
    build_candidate_snapshot,
    candidate_universe_from_scan,
    fetch_candidate_live_context,
    fetch_candidates_live_context,
    fetch_market_backdrop,
    read_latest_scan,
    refresh_candidate_pool,
)
from .utils import clamp, now_iso, num, one_line, safe_last
import time


def clean_mode(value: Any) -> str:
    return "live" if str(value or "paper").strip().lower() == "live" else "paper"


def account_key_for_mode(value: Any) -> str:
    return "live" if clean_mode(value) == "live" else "paper"


def enabled_modes(settings: dict[str, Any]) -> list[str]:
    modes: list[str] = []
    if settings.get("paperTrading", {}).get("enabled"):
        modes.append("paper")
    if settings.get("liveTrading", {}).get("enabled"):
        modes.append("live")
    return modes


def position_pnl(position: dict[str, Any], mark_price: float | None) -> float | None:
    entry_price = num(position.get("entryPrice"))
    quantity = num(position.get("quantity"))
    mark = num(mark_price)
    if entry_price is None or quantity is None or mark is None:
        return None
    multiplier = -1 if position.get("side") == "short" else 1
    return (mark - entry_price) * quantity * multiplier


def enrich_position(position: dict[str, Any]) -> dict[str, Any]:
    mark_price = num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0
    unrealized_pnl = position_pnl(position, mark_price) or 0
    notional_usd = num(position.get("notionalUsd")) or (mark_price * (num(position.get("quantity")) or 0))
    pnl_pct = (unrealized_pnl / notional_usd) * 100 if notional_usd else None
    enriched = dict(position)
    enriched["markPrice"] = mark_price
    enriched["unrealizedPnl"] = unrealized_pnl
    enriched["pnlPct"] = pnl_pct
    return enriched


def summarize_account(book: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    open_positions = [enrich_position(item) for item in book.get("openPositions", [])]
    open_orders = [normalize_order(item) for item in book.get("openOrders", [])]
    exchange_closed_trades = [normalize_exchange_closed_trade(item) for item in book.get("exchangeClosedTrades", [])]
    local_estimated_realized_pnl = sum(num(item.get("realizedPnl")) or 0 for item in book.get("closedTrades", []))
    unrealized_pnl = sum(num(item.get("unrealizedPnl")) or 0 for item in open_positions)
    initial_capital = num(book.get("initialCapitalUsd")) or settings["initialCapitalUsd"]
    account_source = book.get("accountSource") or "paper"
    equity_usd = (num(book.get("exchangeEquityUsd")) if account_source == "exchange" else None)
    if equity_usd is None:
        equity_usd = initial_capital + local_estimated_realized_pnl + unrealized_pnl
    has_local_history = bool(book.get("decisions") or book.get("closedTrades"))
    if account_source == "exchange" and not has_local_history and equity_usd is not None:
        initial_capital = equity_usd
    exchange_wallet_balance = num(book.get("exchangeWalletBalanceUsd"))
    exchange_unrealized_pnl = num(book.get("exchangeUnrealizedPnlUsd"))
    exchange_net_cashflow_usd = num(book.get("exchangeNetCashflowUsd"))
    exchange_realized_pnl_usd = None
    if account_source == "exchange":
        exchange_realized_pnl_usd = sum(num(item.get("realizedPnl")) or 0 for item in exchange_closed_trades)
    realized_pnl_usd = exchange_realized_pnl_usd if account_source == "exchange" and exchange_realized_pnl_usd is not None else local_estimated_realized_pnl
    gross_exposure = sum(abs((num(item.get("markPrice")) or 0) * (num(item.get("quantity")) or 0)) for item in open_positions)
    max_gross_exposure = equity_usd * (settings["maxGrossExposurePct"] / 100)
    available_exposure = max(0.0, max_gross_exposure - gross_exposure)
    if account_source == "exchange" and not has_local_history and equity_usd is not None:
        high_watermark = equity_usd
    else:
        high_watermark = max(num(book.get("highWatermarkEquity")) or initial_capital, equity_usd)
    drawdown_pct = ((high_watermark - equity_usd) / high_watermark) * 100 if high_watermark else 0
    return {
        "baselineCapitalUsd": initial_capital,
        "initialCapitalUsd": initial_capital,
        "equityUsd": equity_usd,
        "realizedPnlUsd": realized_pnl_usd,
        "localEstimatedRealizedPnlUsd": local_estimated_realized_pnl,
        "exchangeRealizedPnlUsd": exchange_realized_pnl_usd,
        "exchangeNetCashflowUsd": exchange_net_cashflow_usd,
        "exchangeIncomeRealizedPnlUsd": num(book.get("exchangeIncomeRealizedPnlUsd")),
        "exchangeFundingFeeUsd": num(book.get("exchangeFundingFeeUsd")),
        "exchangeCommissionUsd": num(book.get("exchangeCommissionUsd")),
        "exchangeOtherIncomeUsd": num(book.get("exchangeOtherIncomeUsd")),
        "exchangeAccountingUpdatedAt": book.get("exchangeAccountingUpdatedAt"),
        "exchangeAccountingNote": book.get("exchangeAccountingNote"),
        "unrealizedPnlUsd": unrealized_pnl,
        "highWatermarkEquity": high_watermark,
        "drawdownPct": drawdown_pct,
        "grossExposureUsd": gross_exposure,
        "maxGrossExposureUsd": max_gross_exposure,
        "availableExposureUsd": available_exposure,
        "exchangeWalletBalanceUsd": exchange_wallet_balance,
        "exchangeAvailableBalanceUsd": num(book.get("exchangeAvailableBalanceUsd")),
        "exchangeUnrealizedPnlUsd": exchange_unrealized_pnl,
        "exchangeClosedTradesCount": len(exchange_closed_trades),
        "openPositions": open_positions,
        "openOrdersCount": len(open_orders),
        "closedTradesCount": len(book.get("closedTrades", [])),
        "decisionsCount": len(book.get("decisions", [])),
        "circuitBreakerTripped": book.get("circuitBreakerTripped") is True,
        "circuitBreakerReason": book.get("circuitBreakerReason"),
        "accountSource": account_source,
    }


def action_label(action_type: str, symbol: str | None = None, side: str | None = None) -> str:
    symbol = symbol or "MARKET"
    if action_type == "open":
        return f"{(side or '').upper()} {symbol}".strip()
    if action_type == "close":
        return f"Close {symbol}"
    if action_type == "reduce":
        return f"Reduce {symbol}"
    if action_type == "update":
        return f"Update risk {symbol}"
    if action_type == "circuit_breaker":
        return "Circuit breaker"
    return action_type


def serialize_candidate_for_history(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": candidate.get("symbol"),
        "baseAsset": candidate.get("baseAsset"),
        "price": candidate.get("price"),
    }


def serialize_candidate_for_prompt(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        **serialize_candidate_for_history(candidate),
        "priceChangePct": candidate.get("priceChangePct"),
        "quoteVolume": candidate.get("quoteVolume"),
        "fundingPct": candidate.get("fundingPct"),
        "klineFeeds": candidate.get("klineFeeds"),
        "klinesByInterval": candidate.get("klinesByInterval"),
    }


def close_position(book: dict[str, Any], position: dict[str, Any], exit_price: float, decision_id: str, reason: str) -> tuple[dict[str, Any], dict[str, Any]]:
    trade = normalize_trade(
        {
            "id": f"{position['id']}-close-{int(time.time() * 1000)}",
            "positionId": position["id"],
            "symbol": position["symbol"],
            "baseAsset": position["baseAsset"],
            "side": position["side"],
            "quantity": position["quantity"],
            "entryPrice": position["entryPrice"],
            "exitPrice": exit_price,
            "notionalUsd": position.get("notionalUsd"),
            "realizedPnl": position_pnl(position, exit_price) or 0,
            "openedAt": position.get("openedAt"),
            "closedAt": now_iso(),
            "exitReason": reason,
            "decisionId": decision_id,
        }
    )
    book["openPositions"] = [item for item in book.get("openPositions", []) if item["id"] != position["id"]]
    book.setdefault("closedTrades", []).append(trade)
    action = {
        "type": "close",
        "symbol": position["symbol"],
        "side": position["side"],
        "realizedPnlUsd": trade["realizedPnl"],
        "reason": reason,
        "label": action_label("close", position["symbol"]),
    }
    return book, action


def reduce_position(book: dict[str, Any], position: dict[str, Any], exit_price: float, reduce_fraction: float, decision_id: str, reason: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    total_qty = num(position.get("quantity")) or 0
    fraction = clamp(reduce_fraction, 0.05, 0.95)
    close_qty = total_qty * fraction
    remaining_qty = total_qty - close_qty
    if remaining_qty <= 1e-9:
        return close_position(book, position, exit_price, decision_id, reason)
    partial_position = dict(position)
    partial_position["quantity"] = close_qty
    trade = normalize_trade(
        {
            "id": f"{position['id']}-reduce-{int(time.time() * 1000)}",
            "positionId": position["id"],
            "symbol": position["symbol"],
            "baseAsset": position["baseAsset"],
            "side": position["side"],
            "quantity": close_qty,
            "entryPrice": position["entryPrice"],
            "exitPrice": exit_price,
            "notionalUsd": (num(position.get("notionalUsd")) or 0) * fraction,
            "realizedPnl": position_pnl(partial_position, exit_price) or 0,
            "openedAt": position.get("openedAt"),
            "closedAt": now_iso(),
            "exitReason": reason,
            "decisionId": decision_id,
        }
    )
    for index, current in enumerate(book.get("openPositions", [])):
        if current["id"] != position["id"]:
            continue
        updated = dict(current)
        updated["quantity"] = remaining_qty
        updated["notionalUsd"] = (num(current.get("notionalUsd")) or 0) * (remaining_qty / total_qty)
        updated["updatedAt"] = now_iso()
        book["openPositions"][index] = normalize_position(updated)
        break
    book.setdefault("closedTrades", []).append(trade)
    action = {
        "type": "reduce",
        "symbol": position["symbol"],
        "side": position["side"],
        "reduceFraction": fraction,
        "realizedPnlUsd": trade["realizedPnl"],
        "reason": reason,
        "label": action_label("reduce", position["symbol"]),
    }
    return book, action


def build_prompt(
    *,
    settings: dict[str, Any],
    prompt_settings: dict[str, Any],
    provider: dict[str, Any],
    market_backdrop: dict[str, Any],
    account_summary: dict[str, Any],
    open_positions: list[dict[str, Any]],
    open_orders: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> str:
    # We ignore the massive market_data dump now.
    
    # Create a lean snapshot
    snapshot = f"Mode: {settings.get('mode', 'paper')}\n"
    snapshot += f"Total Equity: {account_summary.get('equityUsd', 0)}\n"
    snapshot += f"Available Margin: {account_summary.get('availableExposureUsd', 0)}\n"
    
    if open_positions:
        snapshot += "Open Positions:\n"
        for pos in open_positions:
            snapshot += f"  - {pos.get('symbol')}: {pos.get('side')} {pos.get('quantity')} @ {pos.get('entryPrice')}\n"
    else:
        snapshot += "Open Positions: None\n"
        
    snapshot += "\nCandidate Universe:\n"
    for cand in candidates:
        # Just give the symbol, the agent must use get_klines to get price data
        snapshot += f"  - {cand.get('symbol')}\n"
        
    custom_prompt = prompt_settings.get("decision_logic", "")
    
    system_instruction = f"""You are an autonomous quantitative trading AI Agent.
Your goal is to maximize PnL while strictly managing risk.
{custom_prompt}

CURRENT ACCOUNT SNAPSHOT:
{snapshot}

INSTRUCTIONS:
1. You have a set of tools available. You MUST use them to gather information.
2. If you want to analyze a symbol's raw data, use the `get_kline_data` tool.
3. CRITICAL: If you want to use classical trading strategies (MACD, RSI), Chanlun (缠论 - Chaos Theory/Fractals), or SMC (Smart Money Concepts like FVG, VWAP, Divergence), use the `analyze_market_technicals` tool. It provides ready-to-use indicator values and fractal analysis.
4. To get a top-down view (15m, 1h, 4h), use `analyze_multi_timeframe`.
5. CRITICAL: Before placing an order, you MUST use `calculate_position_size` to determine the exact `qty` based on your stop loss and max 2% account risk.
6. If you want to review your past mistakes or successes, use `get_recent_decisions`.
7. When you are ready to act, use `place_order` to execute a trade, or `pass_turn` if no action is needed.
8. Think step-by-step before calling a tool.
"""
    return system_instruction


def default_model_decision(open_positions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "summary": "Fallback decision because model output was unavailable.",
        "position_actions": [
            {
                "symbol": position["symbol"],
                "decision": "hold",
                "reason": "Fallback hold because model output was unavailable.",
            }
            for position in open_positions
        ],
        "entry_actions": [],
        "watchlist": [],
    }


def normalize_model_decision(
    parsed: dict[str, Any],
    *,
    open_positions: list[dict[str, Any]],
    candidates_by_symbol: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        raise ValueError("Model response must be a JSON object.")
    position_actions_raw = parsed.get("position_actions") if isinstance(parsed.get("position_actions"), list) else []
    entry_actions_raw = parsed.get("entry_actions") if isinstance(parsed.get("entry_actions"), list) else []
    watchlist_raw = parsed.get("watchlist") if isinstance(parsed.get("watchlist"), list) else []
    positions_by_symbol = {item["symbol"]: item for item in open_positions}
    normalized_positions: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for item in position_actions_raw:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper()
        if symbol not in positions_by_symbol or symbol in seen_symbols:
            continue
        decision = str(item.get("decision") or "hold").strip().lower()
        if decision not in {"hold", "close", "reduce", "update"}:
            decision = "hold"
        normalized_positions.append(
            {
                "symbol": symbol,
                "decision": decision,
                "reason": str(item.get("reason") or ""),
                "reduceFraction": clamp(item.get("reduceFraction"), 0.05, 0.95),
                "stopLoss": num(item.get("stopLoss")),
                "takeProfit": num(item.get("takeProfit")),
            }
        )
        seen_symbols.add(symbol)
    for symbol in positions_by_symbol:
        if symbol not in seen_symbols:
            normalized_positions.append(
                {
                    "symbol": symbol,
                    "decision": "hold",
                    "reason": "No explicit model instruction; defaulting to hold.",
                    "reduceFraction": 0.25,
                    "stopLoss": None,
                    "takeProfit": None,
                }
            )
    normalized_entries: list[dict[str, Any]] = []
    for item in entry_actions_raw:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper()
        candidate = candidates_by_symbol.get(symbol)
        if not candidate:
            continue
        action = str(item.get("action") or "open").strip().lower()
        if action != "open":
            continue
        side = str(item.get("side") or candidate.get("defaultSide") or "").strip().lower()
        if side not in {"long", "short"}:
            continue
        normalized_entries.append(
            {
                "symbol": symbol,
                "action": "open",
                "side": side,
                "confidence": clamp(item.get("confidence") or candidate.get("confidenceScore"), 1, 100),
                "reason": str(item.get("reason") or candidate.get("topStrategy") or ""),
                "stopLoss": num(item.get("stopLoss")) or num(candidate.get("defaultStopLoss")),
                "takeProfit": num(item.get("takeProfit")) or num(candidate.get("defaultTakeProfit")),
            }
        )
    normalized_watchlist = []
    for item in watchlist_raw:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper()
        if not symbol:
            continue
        normalized_watchlist.append(
            {
                "symbol": symbol,
                "reason": str(item.get("reason") or ""),
            }
        )
    return {
        "summary": str(parsed.get("summary") or ""),
        "position_actions": normalized_positions,
        "entry_actions": normalized_entries,
        "watchlist": normalized_watchlist,
    }


def mark_to_market(book: dict[str, Any], live_by_symbol: dict[str, dict[str, Any]]) -> None:
    for position in book.get("openPositions", []):
        live = live_by_symbol.get(position["symbol"])
        if not live:
            continue
        mark_price = num(live["premium"].get("markPrice")) or num(live["ticker24h"].get("lastPrice")) or num(position.get("entryPrice")) or 0
        position["lastMarkPrice"] = mark_price
        position["lastMarkTime"] = now_iso()
        position["updatedAt"] = now_iso()


def _risk_valid_for_side(side: str, mark_price: float, stop_loss: float | None, take_profit: float | None) -> bool:
    if side == "long":
        if stop_loss is not None and stop_loss >= mark_price:
            return False
        if take_profit is not None and take_profit <= mark_price:
            return False
    else:
        if stop_loss is not None and stop_loss <= mark_price:
            return False
        if take_profit is not None and take_profit >= mark_price:
            return False
    return True


def apply_protection_hits(book: dict[str, Any], decision_id: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for position in list(book.get("openPositions", [])):
        mark_price = num(position.get("lastMarkPrice"))
        if mark_price is None:
            continue
        stop_loss = num(position.get("stopLoss"))
        take_profit = num(position.get("takeProfit"))
        if position["side"] == "long":
            if stop_loss is not None and mark_price <= stop_loss:
                book, action = close_position(book, position, mark_price, decision_id, "stop_loss_hit")
                actions.append(action)
                continue
            if take_profit is not None and mark_price >= take_profit:
                book, action = close_position(book, position, mark_price, decision_id, "take_profit_hit")
                actions.append(action)
                continue
        else:
            if stop_loss is not None and mark_price >= stop_loss:
                book, action = close_position(book, position, mark_price, decision_id, "stop_loss_hit")
                actions.append(action)
                continue
            if take_profit is not None and mark_price <= take_profit:
                book, action = close_position(book, position, mark_price, decision_id, "take_profit_hit")
                actions.append(action)
                continue
    return actions


def position_notional_from_risk(
    account_summary: dict[str, Any],
    *,
    entry_price: float,
    stop_loss: float,
    settings: dict[str, Any],
) -> float:
    stop_pct = abs(((entry_price - stop_loss) / entry_price))
    if stop_pct <= 0:
        return 0
    risk_budget = account_summary["equityUsd"] * (settings["riskPerTradePct"] / 100)
    risk_sized_notional = risk_budget / stop_pct
    return min(
        settings["maxPositionNotionalUsd"],
        account_summary["availableExposureUsd"],
        risk_sized_notional,
    )


def cap_live_notional_by_margin(
    requested_notional_usd: float,
    *,
    account_summary: dict[str, Any],
    live_config: dict[str, Any],
) -> float:
    available_balance = num(account_summary.get("exchangeAvailableBalanceUsd"))
    leverage = int(clamp(live_config.get("defaultLeverage"), 1, 125))
    if available_balance is None or available_balance <= 0:
        return requested_notional_usd
    max_margin_notional = max(0.0, available_balance * leverage * 0.92)
    return min(requested_notional_usd, max_margin_notional)


def open_paper_position(
    book: dict[str, Any],
    *,
    candidate: dict[str, Any],
    side: str,
    stop_loss: float,
    take_profit: float | None,
    confidence: float,
    notional_usd: float,
    reason: str,
    decision_id: str,
) -> dict[str, Any]:
    entry_price = num(candidate.get("price")) or 0
    quantity = notional_usd / entry_price if entry_price else 0
    position = normalize_position(
        {
            "id": f"{candidate['symbol']}-{int(time.time() * 1000)}",
            "symbol": candidate["symbol"],
            "baseAsset": candidate["baseAsset"],
            "side": side,
            "quantity": quantity,
            "initialQuantity": quantity,
            "entryPrice": entry_price,
            "notionalUsd": notional_usd,
            "initialNotionalUsd": notional_usd,
            "stopLoss": stop_loss,
            "takeProfit": take_profit,
            "lastMarkPrice": entry_price,
            "lastMarkTime": now_iso(),
            "leverage": 1,
            "openedAt": now_iso(),
            "updatedAt": now_iso(),
            "source": "paper",
            "entryReason": reason,
            "decisionId": decision_id,
            "confidenceScore": confidence,
        }
    )
    book.setdefault("openPositions", []).append(position)
    return position


def sync_live_book(
    book: dict[str, Any],
    settings: dict[str, Any],
) -> tuple[dict[str, Any], list[str], dict[str, Any], dict[str, Any] | None]:
    live_config = read_live_trading_config()
    status = live_execution_status(live_config, settings)
    warnings: list[str] = []
    if not status["canSync"]:
        warnings.extend(status["issues"])
        return book, warnings, status, live_config
    session_started_at = book.get("sessionStartedAt") or derive_session_started_at(book)
    if session_started_at:
        book["sessionStartedAt"] = session_started_at
    snapshot = fetch_account_snapshot(live_config, session_started_at=session_started_at)
    accounting_note = str(snapshot.get("accountingNote") or "").strip()
    if accounting_note:
        warnings.append(accounting_note)
    prior_positions = {item["symbol"]: item for item in book.get("openPositions", [])}
    merged_positions = []
    for position in snapshot["openPositions"]:
        prior = prior_positions.get(position["symbol"], {})
        merged = normalize_position(
            {
                **position,
                "stopLoss": prior.get("stopLoss"),
                "takeProfit": prior.get("takeProfit"),
                "openedAt": prior.get("openedAt") or now_iso(),
                "entryReason": prior.get("entryReason") or "synced_from_exchange",
                "decisionId": prior.get("decisionId"),
            }
        )
        merged_positions.append(merged)
    merged_orders = [normalize_order(item) for item in snapshot.get("openOrders", [])]
    exchange_closed_trades = [normalize_exchange_closed_trade(item) for item in snapshot.get("exchangeClosedTrades", [])]
    should_seed_equity_baseline = not book.get("decisions") and not book.get("closedTrades")
    snapshot_equity = num(snapshot.get("equityUsd"))
    book.update(
        {
            "accountSource": "exchange",
            "exchangeWalletBalanceUsd": snapshot["walletBalanceUsd"],
            "exchangeEquityUsd": snapshot["equityUsd"],
            "exchangeAvailableBalanceUsd": snapshot["availableBalanceUsd"],
            "exchangeUnrealizedPnlUsd": snapshot["unrealizedPnlUsd"],
            "exchangeNetCashflowUsd": num(snapshot.get("netCashflowUsd")),
            "exchangeIncomeRealizedPnlUsd": num(snapshot.get("incomeRealizedPnlUsd")),
            "exchangeFundingFeeUsd": num(snapshot.get("fundingFeeUsd")),
            "exchangeCommissionUsd": num(snapshot.get("commissionUsd")),
            "exchangeOtherIncomeUsd": num(snapshot.get("otherIncomeUsd")),
            "exchangeAccountingUpdatedAt": snapshot.get("accountingUpdatedAt"),
            "exchangeAccountingNote": snapshot.get("accountingNote"),
            "openPositions": merged_positions,
            "openOrders": merged_orders,
            "exchangeClosedTrades": exchange_closed_trades,
        }
    )
    if snapshot_equity is not None:
        current_initial = num(book.get("initialCapitalUsd"))
        current_high_watermark = num(book.get("highWatermarkEquity"))
        if current_initial is None or current_initial <= 0:
            book["initialCapitalUsd"] = snapshot_equity
        if should_seed_equity_baseline or current_high_watermark is None or current_high_watermark <= 0:
            book["highWatermarkEquity"] = snapshot_equity
    return book, warnings, status, live_config


def refresh_account_state_after_settings_save(*, reset_live_session: bool = False) -> dict[str, Any]:
    settings = read_trading_settings()
    state = read_trading_state(settings)

    paper_has_history = bool(state["paper"].get("decisions") or state["paper"].get("closedTrades"))
    if not paper_has_history:
        state["paper"]["initialCapitalUsd"] = settings["initialCapitalUsd"]
        if not state["paper"].get("openPositions"):
            state["paper"]["highWatermarkEquity"] = settings["initialCapitalUsd"]

    live_has_history = bool(state["live"].get("decisions") or state["live"].get("closedTrades"))
    if not live_has_history:
        state["live"]["initialCapitalUsd"] = settings["initialCapitalUsd"]
        if not state["live"].get("openPositions"):
            state["live"]["highWatermarkEquity"] = settings["initialCapitalUsd"]
    if reset_live_session:
        state["live"]["sessionStartedAt"] = now_iso()
        state["live"]["exchangeClosedTrades"] = []
    elif settings.get("liveTrading", {}).get("enabled") and not state["live"].get("sessionStartedAt"):
        state["live"]["sessionStartedAt"] = now_iso()

    live_sync_warnings: list[str] = []
    live_status_payload: dict[str, Any] | None = None
    live_config: dict[str, Any] | None = None
    try:
        state["live"], live_sync_warnings, live_status_payload, live_config = sync_live_book(state["live"], settings)
    except Exception as error:
        live_sync_warnings = [f"Live account sync after settings save failed: {error}"]

    write_trading_state(state)
    return {
        "state": state,
        "liveSyncWarnings": live_sync_warnings,
        "liveStatus": live_status_payload,
        "liveConfig": live_config,
    }


def apply_live_position_action(
    book: dict[str, Any],
    position: dict[str, Any],
    action: dict[str, Any],
    decision_id: str,
    status: dict[str, Any],
    live_config: dict[str, Any],
    settings: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    decision = action["decision"]
    mark_price = num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0
    if decision in {"close", "reduce"} and not status["canExecute"]:
        warnings.append(f"Live execution skipped for {position['symbol']}: real execution is not enabled.")
        return book, actions, warnings
    if decision == "close":
        cancel_all_open_orders(live_config, position["symbol"])
        order_side = "SELL" if position["side"] == "long" else "BUY"
        place_market_order(live_config, symbol=position["symbol"], side=order_side, quantity=position["quantity"], reduce_only=True)
        book, recorded = close_position(book, position, mark_price, decision_id, action["reason"] or "model_close")
        recorded["exchange"] = True
        actions.append(recorded)
        return book, actions, warnings
    if decision == "reduce":
        close_qty = (num(position.get("quantity")) or 0) * action["reduceFraction"]
        normalized_qty = normalize_quantity(live_config, position["symbol"], quantity=close_qty, reference_price=mark_price)
        order_side = "SELL" if position["side"] == "long" else "BUY"
        place_market_order(live_config, symbol=position["symbol"], side=order_side, quantity=normalized_qty, reduce_only=True)
        book, recorded = reduce_position(book, position, mark_price, action["reduceFraction"], decision_id, action["reason"] or "model_reduce")
        if recorded:
            recorded["exchange"] = True
            actions.append(recorded)
        return book, actions, warnings
    if decision in {"hold", "update"}:
        stop_loss = action.get("stopLoss")
        take_profit = action.get("takeProfit")
        if stop_loss is None and take_profit is None:
            return book, actions, warnings
        if not _risk_valid_for_side(position["side"], mark_price, stop_loss, take_profit):
            warnings.append(f"Ignored invalid live protection update for {position['symbol']}.")
            return book, actions, warnings
        for current in book.get("openPositions", []):
            if current["id"] != position["id"]:
                continue
            current["stopLoss"] = stop_loss
            current["takeProfit"] = take_profit
            current["updatedAt"] = now_iso()
            break
        if status["canExecute"] and settings["liveExecution"]["useExchangeProtectionOrders"]:
            try:
                cancel_all_open_orders(live_config, position["symbol"])
                place_protection_orders(
                    live_config,
                    symbol=position["symbol"],
                    position_side=position["side"],
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
            except Exception as error:
                warnings.append(f"Exchange protection order update failed for {position['symbol']}: {error}")
        actions.append(
            {
                "type": "update",
                "symbol": position["symbol"],
                "side": position["side"],
                "stopLoss": stop_loss,
                "takeProfit": take_profit,
                "reason": action["reason"] or "model_update",
                "label": action_label("update", position["symbol"]),
            }
        )
    return book, actions, warnings


def apply_paper_position_action(
    book: dict[str, Any],
    position: dict[str, Any],
    action: dict[str, Any],
    decision_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    mark_price = num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0
    decision = action["decision"]
    if decision == "close":
        book, recorded = close_position(book, position, mark_price, decision_id, action["reason"] or "model_close")
        actions.append(recorded)
        return book, actions, warnings
    if decision == "reduce":
        book, recorded = reduce_position(book, position, mark_price, action["reduceFraction"], decision_id, action["reason"] or "model_reduce")
        if recorded:
            actions.append(recorded)
        return book, actions, warnings
    stop_loss = action.get("stopLoss")
    take_profit = action.get("takeProfit")
    if decision in {"hold", "update"} and (stop_loss is not None or take_profit is not None):
        if not _risk_valid_for_side(position["side"], mark_price, stop_loss, take_profit):
            warnings.append(f"Ignored invalid risk update for {position['symbol']}.")
            return book, actions, warnings
        for current in book.get("openPositions", []):
            if current["id"] != position["id"]:
                continue
            current["stopLoss"] = stop_loss
            current["takeProfit"] = take_profit
            current["updatedAt"] = now_iso()
            break
        actions.append(
            {
                "type": "update",
                "symbol": position["symbol"],
                "side": position["side"],
                "stopLoss": stop_loss,
                "takeProfit": take_profit,
                "reason": action["reason"] or "model_update",
                "label": action_label("update", position["symbol"]),
            }
        )
    return book, actions, warnings


def apply_account_circuit_breaker(
    book: dict[str, Any],
    settings: dict[str, Any],
    decision_id: str,
    *,
    live_mode: bool,
    live_status_payload: dict[str, Any] | None = None,
    live_config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    account = summarize_account(book, settings)
    if account["drawdownPct"] < settings["maxAccountDrawdownPct"]:
        book["circuitBreakerTripped"] = False
        book["circuitBreakerReason"] = None
        return book, [], []
    book["circuitBreakerTripped"] = True
    book["circuitBreakerReason"] = f"Drawdown {account['drawdownPct']:.2f}% breached max {settings['maxAccountDrawdownPct']:.2f}%."
    actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    for position in list(book.get("openPositions", [])):
        if live_mode:
            if not live_status_payload or not live_status_payload.get("canExecute"):
                warnings.append(f"Circuit breaker could not close live {position['symbol']} because real execution is not enabled.")
                continue
            cancel_all_open_orders(live_config, position["symbol"])
            order_side = "SELL" if position["side"] == "long" else "BUY"
            place_market_order(live_config, symbol=position["symbol"], side=order_side, quantity=position["quantity"], reduce_only=True)
        book, recorded = close_position(
            book,
            position,
            num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0,
            decision_id,
            "circuit_breaker",
        )
        recorded["type"] = "circuit_breaker"
        recorded["label"] = action_label("circuit_breaker")
        actions.append(recorded)
    return book, actions, warnings


def _fetch_live_contexts(symbols: list[str], prompt_kline_feeds: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    return _fetch_live_contexts_for_exchange(symbols, prompt_kline_feeds)


def _fetch_live_contexts_for_exchange(
    symbols: list[str],
    prompt_kline_feeds: dict[str, Any],
    exchange_id: str | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    try:
        live_by_symbol = fetch_candidates_live_context(symbols, prompt_kline_feeds, exchange_id)
    except Exception as error:
        return {}, [str(error)]
    warnings: list[str] = []
    for symbol in symbols:
        if symbol not in live_by_symbol:
            warnings.append(f"{symbol}: missing live context")
    return live_by_symbol, warnings


def run_trading_cycle(reason: str = "manual", mode_override: str | None = None) -> dict[str, Any]:
    from .engine.agent_loop import ReActAgent
    from .engine.models import AgentMemory, Decision, Trade
    from .engine.db import init_db
    from .engine.llm_client import LLMClientFactory
    from .config import read_llm_provider
    import time
    
    # Initialize DB
    Session = init_db()
    
    provider_config = read_llm_provider()
    # provider_config usually has 'preset' (e.g. 'anthropic' or 'openai') and 'apiKey'
    preset = provider_config.get("preset", "anthropic").lower()
    api_key = provider_config.get("apiKey", "")
    
    llm_client = LLMClientFactory.create(preset, api_key)
    
    def llm_caller(history, tools):
        tool_schemas = []
        for tool_name in tools.keys():
            schema = {
                "name": tool_name,
                "description": f"Call {tool_name}",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
            if tool_name == "place_order":
                schema["input_schema"]["properties"] = {
                    "symbol": {"type": "string", "description": "e.g. BTCUSDT"},
                    "side": {"type": "string", "description": "BUY or SELL"},
                    "qty": {"type": "number", "description": "Amount to trade"}
                }
                schema["input_schema"]["required"] = ["symbol", "side", "qty"]
            elif tool_name in ["get_kline_data", "get_position", "close_position", "analyze_market_technicals"]:
                schema["input_schema"]["properties"] = {
                    "symbol": {"type": "string", "description": "e.g. BTCUSDT"}
                }
                schema["input_schema"]["required"] = ["symbol"]
            elif tool_name == "get_recent_decisions":
                schema["input_schema"]["properties"] = {
                    "limit": {"type": "integer", "description": "Number of decisions to fetch"}
                }
                schema["input_schema"]["required"] = ["limit"]
            elif tool_name == "analyze_multi_timeframe":
                schema["input_schema"]["properties"] = {"symbol": {"type": "string"}}
                schema["input_schema"]["required"] = ["symbol"]
            elif tool_name == "calculate_position_size":
                schema["input_schema"]["properties"] = {
                    "account_equity": {"type": "number"},
                    "risk_pct": {"type": "number", "description": "e.g. 1.0 for 1%"},
                    "entry_price": {"type": "number"},
                    "stop_loss": {"type": "number"}
                }
                schema["input_schema"]["required"] = ["account_equity", "risk_pct", "entry_price", "stop_loss"]
                
            tool_schemas.append(schema)
            
        return llm_client.call(history, tool_schemas)
        
    agent = ReActAgent(llm_caller=llm_caller)
    
    with Session() as session:
        # Load latest memory
        latest_memory = session.query(AgentMemory).order_by(AgentMemory.timestamp.desc()).first()
        context = latest_memory.reasoning if latest_memory else "Initial state."
        
    # Start reasoning loop based on trigger event
    trigger_event = reason
    instruction = f"Event: {trigger_event}. Context: {context}. Analyze market and manage positions."
    
    agent_result = agent.run(instruction)
    
    # Extract the final decision from the agent loop history
    final_text = ""
    tool_calls = []
    if isinstance(agent_result, list) and len(agent_result) > 0:
        final_msg = agent_result[-1]
        
        if isinstance(final_msg, dict):
            # The agent loop appends {"role": "tool", "content": ...}
            # We actually want the last assistant message before the tools, 
            # OR we modify agent_loop.py to return the final assistant msg.
            # Assuming agent_result is the history, let's find the last assistant message.
            for msg in reversed(agent_result):
                if msg.get("role") == "assistant" or "tool_calls" in msg:
                    final_text = msg.get("text", msg.get("content", ""))
                    tool_calls = msg.get("tool_calls", [])
                    break
    elif isinstance(agent_result, dict):
        final_text = agent_result.get("content", "")
        tool_calls = agent_result.get("tool_calls", [])
        
    if isinstance(final_text, list): # if it's a list of blocks
        text_blocks = [b["text"] for b in final_text if b.get("type") == "text"]
        final_text = "\n".join(text_blocks)
    elif isinstance(final_text, str):
        pass
            
    with Session() as session:
        # Save reasoning
        decision = Decision(
            timestamp=int(time.time()),
            symbol="ALL",
            action="EVALUATED",
            reasoning=str(final_text)
        )
        session.add(decision)
        
        # Route execution based on tool calls
        from .engine.executor import PaperBackend, LiveBackend
        from .config import read_account_configs
        
        # Initialize the proper backend
        accounts = read_account_configs()
        account_config = accounts.get(mode_override or "paper", {})
        
        if (mode_override or "paper") == "live":
            # Provide real api keys if live, handled in executor
            backend_executor = LiveBackend(api_key=account_config.get("apiKey", ""), api_secret=account_config.get("apiSecret", ""))
        else:
            backend_executor = PaperBackend()
            
        for tc in tool_calls:
            if tc["name"] == "place_order":
                args = tc.get("arguments", {})
                symbol = args.get("symbol", "UNKNOWN")
                side = args.get("side", "BUY")
                qty = float(args.get("qty", 0.0))
                
                # Execute through the robust backend which handles risk checks
                try:
                    exec_result = backend_executor.execute_decision(symbol, side, qty)
                    if exec_result and exec_result.get("status") == "success":
                        trade = Trade(
                            timestamp=int(time.time()),
                            symbol=symbol,
                            side=side,
                            quantity=qty,
                            price=exec_result.get("price", 0.0)
                        )
                        session.add(trade)
                        decision.action = f"ORDER_{side}_{symbol}_SUCCESS"
                    else:
                        decision.action = f"ORDER_{side}_{symbol}_FAILED"
                except Exception as e:
                    decision.action = f"ORDER_{side}_{symbol}_ERROR_{str(e)}"
            elif tc["name"] == "close_position":
                args = tc.get("arguments", {})
                symbol = args.get("symbol", "UNKNOWN")
                
                try:
                    # In our simplified execute_decision, sending opposite side closes the position
                    # We can fetch the current position side and send the opposite
                    from .engine.state import read_trading_state
                    book = read_trading_state(accounts.get(mode_override or "paper", {}))[mode_override or "paper"]
                    pos = next((p for p in book.get("openPositions", []) if p["symbol"] == symbol), None)
                    if pos:
                        opposite_side = "SELL" if pos["side"].lower() == "long" else "BUY"
                        exec_result = backend_executor.execute_decision(symbol, opposite_side, float(pos["quantity"]))
                        if exec_result and exec_result.get("status") == "success":
                            decision.action = f"CLOSE_{symbol}_SUCCESS"
                        else:
                            decision.action = f"CLOSE_{symbol}_FAILED"
                    else:
                        decision.action = f"CLOSE_{symbol}_NOT_FOUND"
                except Exception as e:
                    decision.action = f"CLOSE_{symbol}_ERROR_{str(e)}"
                
        session.commit()
    
    return {
        "ok": True,
        "mode": mode_override or "paper",
        "agent_result": final_text,
        "tool_calls": tool_calls
    }

def run_trading_cycle_batch(reason: str = "manual", modes: list[str] | None = None) -> dict[str, Any]:
    settings = read_trading_settings()
    requested_modes = [clean_mode(item) for item in (modes or enabled_modes(settings))]
    unique_modes: list[str] = []
    for mode in requested_modes:
        if mode not in unique_modes:
            unique_modes.append(mode)
    results = []
    for mode in unique_modes:
        result = run_trading_cycle(reason=reason, mode_override=mode)
        results.append(
            {
                "ok": True,
                "mode": mode,
                "result": result,
            }
        )
    return {
        "settings": settings,
        "modes": unique_modes,
        "activeMode": unique_modes[0] if unique_modes else "paper",
        "results": results,
        "primaryResult": results[0]["result"] if results else None,
    }


def preview_trading_prompt_decision(mode_override: str | None = None, prompt_override: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = read_trading_settings()
    settings["mode"] = clean_mode(mode_override or settings["mode"])
    universe = read_fixed_universe()
    account_key = account_key_for_mode(settings["mode"])
    cycle_exchange_id = str(settings.get("activeExchange") or "binance").strip().lower() or "binance"
    if account_key == "live":
        live_config = read_live_trading_config()
        cycle_exchange_id = str(live_config.get("exchange") or cycle_exchange_id).strip().lower() or cycle_exchange_id
    scan = read_latest_scan(cycle_exchange_id)
    if universe.get("dynamicSource", {}).get("enabled") or not scan["opportunities"] or str(scan.get("exchange") or "").strip().lower() != cycle_exchange_id:
        scan = refresh_candidate_pool(cycle_exchange_id)
    state = read_trading_state(settings)
    book = deepcopy(state[account_key])
    warnings: list[str] = []
    if account_key == "live":
        book, live_warnings, _, _ = sync_live_book(book, settings)
        warnings.extend(live_warnings)
    prompt_settings = prompt_override or read_prompt_settings()
    prompt_kline_feeds = prompt_settings.get("klineFeeds") if isinstance(prompt_settings.get("klineFeeds"), dict) else {}
    raw_candidates = candidate_universe_from_scan(scan)
    symbols = []
    for item in raw_candidates:
        symbol = str(item.get("symbol") or "").upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    for position in book.get("openPositions", []):
        if position["symbol"] not in symbols:
            symbols.append(position["symbol"])
    live_by_symbol, live_context_warnings = _fetch_live_contexts_for_exchange(symbols, prompt_kline_feeds, cycle_exchange_id)
    warnings.extend(live_context_warnings)
    mark_to_market(book, live_by_symbol)
    gateway = get_active_exchange_gateway(cycle_exchange_id)
    market_backdrop = fetch_market_backdrop(prompt_kline_feeds, cycle_exchange_id) if gateway.default_backdrop_symbol in symbols else {}
    candidate_snapshots = []
    for opportunity in raw_candidates:
        symbol = str(opportunity.get("symbol") or "").upper()
        live = live_by_symbol.get(symbol)
        if not live:
            continue
        candidate_snapshots.append(build_candidate_snapshot(opportunity, live, settings, cycle_exchange_id))
    candidates_by_symbol = {item["symbol"]: item for item in candidate_snapshots}
    account_summary = summarize_account(book, settings)
    provider = read_llm_provider()
    prompt = build_prompt(
        settings=settings,
        prompt_settings=prompt_settings,
        provider=provider,
        market_backdrop=market_backdrop,
        account_summary=account_summary,
        open_positions=account_summary["openPositions"],
        open_orders=[normalize_order(item) for item in book.get("openOrders", [])],
        candidates=candidate_snapshots,
    )
    model_result = generate_trading_decision(prompt, provider)
    parsed_model = normalize_model_decision(
        model_result["parsed"],
        open_positions=account_summary["openPositions"],
        candidates_by_symbol=candidates_by_symbol,
    )
    return {
        "mode": settings["mode"],
        "promptName": prompt_settings.get("name") or "default_trading_logic",
        "candidateCount": len(candidate_snapshots),
        "account": account_summary,
        "warnings": warnings,
        "prompt": prompt,
        "rawText": model_result["rawText"],
        "parsed": parsed_model,
        "provider": model_result["provider"],
    }


def summarize_book_history(book: dict[str, Any]) -> dict[str, Any]:
    recent_decisions = list(book.get("decisions", []))[-8:]
    decision_timeline = [
        {
            "id": item["id"],
            "startedAt": item["startedAt"],
            "finishedAt": item["finishedAt"],
            "actions": item["actions"],
        }
        for item in book.get("decisions", [])[-240:]
    ]
    return {
        "sessionStartedAt": book.get("sessionStartedAt"),
        "lastDecisionAt": book.get("lastDecisionAt"),
        "decisions": recent_decisions,
        "decisionTimeline": decision_timeline,
        "exchangeClosedTrades": list(book.get("exchangeClosedTrades", [])),
        "closedTrades": list(book.get("closedTrades", [])),
    }


def compact_latest_decision(decision: dict[str, Any] | None) -> dict[str, Any] | None:
    if not decision:
        return None
    return {
        "id": decision["id"],
        "startedAt": decision["startedAt"],
        "finishedAt": decision["finishedAt"],
        "runnerReason": decision["runnerReason"],
        "mode": decision["mode"],
        "promptSummary": decision["promptSummary"],
        "actionsCount": len(decision.get("actions", [])),
    }


def summarize_trading_state() -> dict[str, Any]:
    settings = read_trading_settings()
    state = read_trading_state(settings)
    live_status_payload = live_execution_status(read_live_trading_config(), settings)
    scan = read_latest_scan(settings.get("activeExchange"))
    active_mode = settings["mode"]
    active_key = account_key_for_mode(active_mode)
    active_book = state[active_key]
    paper_account = summarize_account(state["paper"], {**settings, "mode": "paper"})
    live_account = summarize_account(state["live"], {**settings, "mode": "live"})
    active_account = summarize_account(active_book, settings)
    return {
        "settings": settings,
        "activeMode": active_mode,
        "paperTradingEnabled": settings.get("paperTrading", {}).get("enabled") is True,
        "liveTradingEnabled": settings.get("liveTrading", {}).get("enabled") is True,
        "scan": {
            "runDate": scan.get("runDate"),
            "fetchedAt": scan.get("fetchedAt"),
            "candidateUniverseSize": len(scan.get("opportunities", [])),
        },
        "account": active_account,
        "paperAccount": paper_account,
        "liveAccount": live_account,
        "adaptive": state.get("adaptive"),
        "latestDecision": compact_latest_decision(safe_last(active_book.get("decisions", []))),
        "latestPaperDecision": compact_latest_decision(safe_last(state["paper"].get("decisions", []))),
        "latestLiveDecision": compact_latest_decision(safe_last(state["live"].get("decisions", []))),
        "paperBook": state["paper"],
        "liveBook": state["live"],
        "activeBook": active_book,
        "paperHistory": summarize_book_history(state["paper"]),
        "liveHistory": summarize_book_history(state["live"]),
        "liveExecutionStatus": live_status_payload,
        "providerStatus": provider_status(),
    }


def flatten_active_account(reason: str = "manual_flatten", mode_override: str | None = None) -> dict[str, Any]:
    settings = read_trading_settings()
    target_mode = clean_mode(mode_override or settings["mode"])
    state = read_trading_state(settings)
    account_key = account_key_for_mode(target_mode)
    book = state[account_key]
    decision_id = f"flatten-{int(time.time() * 1000)}"
    actions = []
    warnings: list[str] = []
    if account_key == "live":
        book, live_warnings, live_status_payload, live_config = sync_live_book(book, settings)
        warnings.extend(live_warnings)
        if not live_status_payload["canExecute"]:
            raise RuntimeError("Live flatten requires real execution to be enabled.")
        for position in list(book.get("openPositions", [])):
            cancel_all_open_orders(live_config, position["symbol"])
            side = "SELL" if position["side"] == "long" else "BUY"
            place_market_order(live_config, symbol=position["symbol"], side=side, quantity=position["quantity"], reduce_only=True)
            book, action = close_position(book, position, num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0, decision_id, reason)
            actions.append(action)
        book, live_warnings, _, _ = sync_live_book(book, settings)
        warnings.extend(live_warnings)
    else:
        for position in list(book.get("openPositions", [])):
            book, action = close_position(book, position, num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0, decision_id, reason)
            actions.append(action)
    decision = normalize_decision(
        {
            "id": decision_id,
            "startedAt": now_iso(),
            "finishedAt": now_iso(),
            "runnerReason": "manual",
            "mode": target_mode,
            "prompt": f"Flatten all open {target_mode} positions because: {reason}",
            "promptSummary": f"Flattened {len(actions)} open {target_mode} positions.",
            "actions": actions,
            "warnings": warnings,
            "output": {"actions": actions},
            "candidateUniverse": [],
            "accountBefore": {},
            "accountAfter": summarize_account(book, {**settings, "mode": target_mode}),
        }
    )
    book.setdefault("decisions", []).append(decision)
    book["lastDecisionAt"] = now_iso()
    write_trading_state(state)
    archive_decision(decision)
    return state


def reset_paper_account(mode: str = "full") -> dict[str, Any]:
    settings = read_trading_settings()
    state = read_trading_state(settings)
    if str(mode) == "equity_only":
        state["paper"]["initialCapitalUsd"] = settings["initialCapitalUsd"]
        state["paper"]["highWatermarkEquity"] = settings["initialCapitalUsd"]
        state["paper"]["openPositions"] = []
        state["paper"]["circuitBreakerTripped"] = False
        state["paper"]["circuitBreakerReason"] = None
    else:
        state["paper"] = empty_trading_account(settings["initialCapitalUsd"], "paper")
    state["adaptive"] = {
        "updatedAt": now_iso(),
        "notes": [
            "Paper account was reset in the Python build.",
            "The trade-logic fields, provider config, and proxy config were preserved.",
        ],
    }
    return write_trading_state(state)


def reset_trading_account(mode: str = "paper") -> dict[str, Any]:
    reset_mode = str(mode or "paper").strip().lower()
    if reset_mode in {"paper", "full", "equity_only"}:
        return reset_paper_account(reset_mode if reset_mode == "equity_only" else "full")

    if reset_mode != "live":
        raise ValueError(f"Unsupported reset mode: {mode}")

    settings = read_trading_settings()
    state = read_trading_state(settings)
    book = state["live"]
    book, warnings, live_status_payload, live_config = sync_live_book(book, settings)
    state["live"] = book
    if not live_status_payload["canSync"]:
        state["live"] = empty_trading_account(settings["initialCapitalUsd"], "exchange")
        state["adaptive"] = {
            "updatedAt": now_iso(),
            "notes": [
                "Live account local state was reset without exchange sync.",
                "No valid live API configuration was available, so only local live decisions, positions, and drawdown baseline were cleared.",
            ],
        }
        return write_trading_state(state)
    if book.get("openPositions"):
        if not live_status_payload["canExecute"]:
            raise RuntimeError("实盘重置发现当前仍有持仓。请先启用实盘并关闭模拟下单，或先手动全部平仓。")
        for position in list(book.get("openPositions", [])):
            cancel_all_open_orders(live_config, position["symbol"])
            side = "SELL" if position["side"] == "long" else "BUY"
            place_market_order(
                live_config,
                symbol=position["symbol"],
                side=side,
                quantity=position["quantity"],
                reduce_only=True,
            )
    fresh_book = empty_trading_account(num(book.get("exchangeEquityUsd")) or settings["initialCapitalUsd"], "exchange")
    fresh_book, sync_warnings, _, _ = sync_live_book(fresh_book, settings)
    warnings.extend(sync_warnings)
    state["live"] = fresh_book
    state["adaptive"] = {
        "updatedAt": now_iso(),
        "notes": [
            "Live account was reset in the Python build.",
            "Live decisions, local estimated realized PnL, drawdown baseline, and synced positions were cleared.",
        ] + ([f"Reset warnings: {'; '.join(warnings[:3])}"] if warnings else []),
    }
    return write_trading_state(state)
