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
    return (mark - entry_price) * quantity * multiplier


def close_position(
    book: dict[str, Any],
    position: dict[str, Any],
    exit_price: float,
    decision_id: str,
    reason: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
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
