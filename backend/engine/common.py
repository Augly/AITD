from __future__ import annotations

import time
from typing import Any

from .state import normalize_position, normalize_trade, now_iso
from ..utils import num


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


def position_pnl(position: dict[str, Any], mark_price: float | None) -> float | None:
    entry_price = num(position.get("entryPrice"))
    quantity = num(position.get("quantity"))
    mark = num(mark_price)
    if entry_price is None or quantity is None or mark is None:
        return None
    multiplier = -1 if position.get("side") == "short" else 1
    
    # We already deducted the open fee and slippage when the position was opened (via notional reduction).
    # We also deduct the close fee and exit slippage during the close/reduce operation.
    # For unrealized PnL, we just want to show the current raw PnL minus an estimated closing fee
    # to be conservative, so the user knows what they'd get if they closed right now.
    if position.get("source") == "paper":
        fee_rate = 0.001 # 0.1% estimated exit fee
        slippage_rate = 0.0005
        exit_price = mark * (1 - slippage_rate) if position.get("side") == "long" else mark * (1 + slippage_rate)
        fee_cost = (exit_price * quantity * fee_rate)
        
        # Recalculate pnl using exit_price instead of mark
        raw_pnl = (exit_price - entry_price) * quantity * multiplier - fee_cost
    else:
        raw_pnl = (mark - entry_price) * quantity * multiplier
        
    return raw_pnl


def close_position(
    book: dict[str, Any],
    position: dict[str, Any],
    exit_price: float,
    decision_id: str,
    reason: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    # Apply a 0.05% slippage on exit for paper trading
    if position.get("source") == "paper":
        slippage_rate = 0.0005
        fee_rate = 0.001
        if position["side"] == "long":
            exit_price = exit_price * (1 - slippage_rate)
        else:
            exit_price = exit_price * (1 + slippage_rate)
            
        # Deduct 0.1% closing fee from realized PnL
        fee_cost = (exit_price * position["quantity"]) * fee_rate
    else:
        fee_cost = 0.0

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
            "realizedPnl": (position_pnl(position, exit_price) or 0) - fee_cost,
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


def reduce_position(
    book: dict[str, Any],
    position: dict[str, Any],
    exit_price: float,
    reduce_fraction: float,
    decision_id: str,
    reason: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from ..utils import clamp

    total_qty = num(position.get("quantity")) or 0
    fraction = clamp(reduce_fraction, 0.05, 0.95)
    close_qty = total_qty * fraction
    remaining_qty = total_qty - close_qty
    if remaining_qty <= 1e-9:
        return close_position(book, position, exit_price, decision_id, reason)
    partial_position = dict(position)
    partial_position["quantity"] = close_qty

    if position.get("source") == "paper":
        slippage_rate = 0.0005
        fee_rate = 0.001
        if position["side"] == "long":
            exit_price = exit_price * (1 - slippage_rate)
        else:
            exit_price = exit_price * (1 + slippage_rate)
            
        # Deduct 0.1% closing fee from realized PnL
        fee_cost = (exit_price * close_qty) * fee_rate
    else:
        fee_cost = 0.0

    # Avoid passing the partial_position dict back into position_pnl which causes dict side effects
    entry_price = num(partial_position.get("entryPrice")) or 0
    multiplier = -1 if partial_position.get("side") == "short" else 1
    raw_pnl = (exit_price - entry_price) * close_qty * multiplier - fee_cost

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
            "realizedPnl": raw_pnl,
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


def _risk_valid_for_side(
    side: str,
    mark_price: float,
    stop_loss: float | None,
    take_profit: float | None,
) -> bool:
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
