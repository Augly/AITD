from __future__ import annotations

import time

from abc import ABC, abstractmethod
from typing import Any

from .common import (
    action_label,
    close_position,
    reduce_position,
    _risk_valid_for_side,
)
from .state import normalize_position, now_iso
from ..config import read_live_trading_config
from ..live_trading import (
    apply_symbol_settings,
    cancel_all_open_orders,
    live_execution_status,
    normalize_quantity,
    place_market_order,
    place_protection_orders,
)
from ..utils import num


class ExecutionBackend(ABC):
    """Abstract interface for trade execution backends.

    Implementations encapsulate the differences between paper trading
    (local simulation) and live trading (exchange execution).  The
    caller creates a backend instance once per trading cycle and
    delegates all execution operations to it.
    """

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings

    @abstractmethod
    def sync_book(
        self,
        book: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """Synchronise the trading book with the backend.

        Returns the updated book and any warnings produced during sync.
        """

    @abstractmethod
    def apply_position_action(
        self,
        book: dict[str, Any],
        position: dict[str, Any],
        action: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Apply a position-level action (close / reduce / update / hold).

        Returns the updated book, recorded actions, and warnings.
        """

    @abstractmethod
    def open_position(
        self,
        book: dict[str, Any],
        candidate: dict[str, Any],
        entry: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Open a new position for the given candidate and entry action.

        Returns the updated book, recorded actions, and warnings.
        """

    @abstractmethod
    def apply_circuit_breaker(
        self,
        book: dict[str, Any],
        positions: list[dict[str, Any]],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Close all positions when the circuit breaker trips.

        Returns the updated book, recorded actions, and warnings.
        """

    @abstractmethod
    def flatten_all_positions(
        self,
        book: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Close every open position (manual flatten).

        Returns the updated book, recorded actions, and warnings.
        """

    def execute_decision(self, symbol: str, side: str, qty: float, stop_loss: float = None, take_profit: float = None) -> dict[str, Any]:
        """A simplified bridge method for the ReAct agent tool calls.
        It reads the current JSON state, applies the execution logic (open or close),
        and writes the state back to ensure the frontend Dashboard stays synced.
        """
        from .state import read_trading_state, write_trading_state
        import time
        
        # Determine mode based on instance type
        mode = "live" if "LiveBackend" in self.__class__.__name__ else "paper"
        state = read_trading_state(self.settings)
        book = state[mode]
        decision_id = f"decision-{int(time.time() * 1000)}"
        
        book, warnings = self.sync_book(book)
        
        # Look for existing position
        existing_pos = next((p for p in book.get("openPositions", []) if p["symbol"] == symbol), None)
        
        actions = []
        if existing_pos:
            if existing_pos["side"].lower() != side.lower():
                # Opposite side means close the position
                action = {"decision": "close", "reason": "Agent executed opposite side order"}
                book, acts, warns = self.apply_position_action(book, existing_pos, action, decision_id)
                actions.extend(acts)
            else:
                # Update risk if same side
                if stop_loss is not None or take_profit is not None:
                    action = {"decision": "update", "stopLoss": stop_loss, "takeProfit": take_profit, "reason": "Agent updated risk"}
                    book, acts, warns = self.apply_position_action(book, existing_pos, action, decision_id)
                    actions.extend(acts)
        else:
            # Open new position
            price = 0.0
            try:
                from .db import init_db
                from .models import KLineCache
                Session = init_db()
                with Session() as session:
                    latest_kline = session.query(KLineCache).filter(KLineCache.symbol == symbol).order_by(KLineCache.timestamp.desc()).first()
                    if latest_kline:
                        price = latest_kline.close
            except Exception:
                pass
                
            notional_usd = qty * price if price > 0 else qty
            candidate = {"symbol": symbol, "defaultSide": side, "price": price, "baseAsset": symbol.replace("USDT", "")}
            
            entry = {
                "action": "open", 
                "side": side, 
                "quantity": qty, 
                "confidence": 100, 
                "reason": "Agent placed order",
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "notional_usd": notional_usd
            }
            book, acts, warns = self.open_position(book, candidate, entry, decision_id)
            actions.extend(acts)
            
        state[mode] = book
        write_trading_state(state)
        
        # Return success if we executed actions or decided to hold
        return {"status": "success", "price": price if price > 0 else 0.0}


class PaperBackend(ExecutionBackend):
    """Paper-trading backend: all execution is simulated locally."""

    def sync_book(
        self,
        book: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        book["initialCapitalUsd"] = self.settings["initialCapitalUsd"]
        return book, []

    def apply_position_action(
        self,
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
            book, recorded = reduce_position(book, position, mark_price, action["reduceFraction"], decision_id, action["reason"] or "model_reduce")  # type: ignore[assignment]
            if recorded is not None:
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

    def open_position(
        self,
        book: dict[str, Any],
        candidate: dict[str, Any],
        entry: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        entry_price = num(candidate.get("price")) or 0
        notional_usd = entry["notional_usd"]
        quantity = entry.get("quantity") or (notional_usd / entry_price if entry_price else 0)
        position = normalize_position(
            {
                "id": f"{candidate['symbol']}-{int(time.time() * 1000)}",
                "symbol": candidate["symbol"],
                "baseAsset": candidate["baseAsset"],
                "side": entry["side"],
                "quantity": quantity,
                "initialQuantity": quantity,
                "entryPrice": entry_price,
                "notionalUsd": notional_usd,
                "initialNotionalUsd": notional_usd,
                "stopLoss": entry["stop_loss"],
                "takeProfit": entry["take_profit"],
                "lastMarkPrice": entry_price,
                "lastMarkTime": now_iso(),
                "leverage": 1,
                "openedAt": now_iso(),
                "updatedAt": now_iso(),
                "source": "paper",
                "entryReason": entry["reason"],
                "decisionId": decision_id,
                "confidenceScore": entry["confidence"],
            }
        )
        book.setdefault("openPositions", []).append(position)
        action = {
            "type": "open",
            "symbol": candidate["symbol"],
            "side": entry["side"],
            "confidence": entry["confidence"],
            "notionalUsd": notional_usd,
            "stopLoss": entry["stop_loss"],
            "takeProfit": entry["take_profit"],
            "reason": entry["reason"],
            "label": action_label("open", candidate["symbol"], entry["side"]),
        }
        return book, [action], []

    def apply_circuit_breaker(
        self,
        book: dict[str, Any],
        positions: list[dict[str, Any]],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        actions: list[dict[str, Any]] = []
        for position in positions:
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
        return book, actions, []

    def flatten_all_positions(
        self,
        book: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        actions: list[dict[str, Any]] = []
        for position in list(book.get("openPositions", [])):
            book, action = close_position(
                book,
                position,
                num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0,
                decision_id,
                "manual_flatten",
            )
            actions.append(action)
        return book, actions, []


class LiveBackend(ExecutionBackend):
    """Live-trading backend: executes orders on the configured exchange."""

    def __init__(self, settings: dict[str, Any]) -> None:
        super().__init__(settings)
        self.live_config: dict[str, Any] | None = None
        self.live_status: dict[str, Any] | None = None

    def _ensure_config(self) -> dict[str, Any]:
        if self.live_config is None:
            self.live_config = read_live_trading_config()
        return self.live_config

    def _ensure_status(self) -> dict[str, Any]:
        if self.live_status is None:
            self.live_status = live_execution_status(self._ensure_config(), self.settings)
        return self.live_status

    def sync_book(
        self,
        book: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        from ..engine_core import sync_live_book

        book, warnings, self.live_status, live_config = sync_live_book(book, self.settings)
        self.live_config = live_config or self._ensure_config()
        return book, warnings

    def apply_position_action(
        self,
        book: dict[str, Any],
        position: dict[str, Any],
        action: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        actions: list[dict[str, Any]] = []
        warnings: list[str] = []
        mark_price = num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0
        decision = action["decision"]
        status = self.live_status or {"canExecute": False}
        config = self._ensure_config()

        if decision in {"close", "reduce"} and not status["canExecute"]:
            warnings.append(f"Live execution skipped for {position['symbol']}: real execution is not enabled.")
            return book, actions, warnings

        if decision == "close":
            cancel_all_open_orders(config, position["symbol"])
            order_side = "SELL" if position["side"] == "long" else "BUY"
            place_market_order(config, symbol=position["symbol"], side=order_side, quantity=position["quantity"], reduce_only=True)
            book, recorded = close_position(book, position, mark_price, decision_id, action["reason"] or "model_close")
            recorded["exchange"] = True
            actions.append(recorded)
            return book, actions, warnings

        if decision == "reduce":
            close_qty = (num(position.get("quantity")) or 0) * action["reduceFraction"]
            normalized_qty = normalize_quantity(config, position["symbol"], quantity=close_qty, reference_price=mark_price)
            order_side = "SELL" if position["side"] == "long" else "BUY"
            place_market_order(config, symbol=position["symbol"], side=order_side, quantity=normalized_qty, reduce_only=True)
            book, recorded = reduce_position(book, position, mark_price, action["reduceFraction"], decision_id, action["reason"] or "model_reduce")  # type: ignore[assignment]
            if recorded is not None:
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
            if status["canExecute"] and self._use_exchange_protection():
                try:
                    cancel_all_open_orders(config, position["symbol"])
                    place_protection_orders(
                        config,
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

    def open_position(
        self,
        book: dict[str, Any],
        candidate: dict[str, Any],
        entry: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Open a live position.

        Live positions are NOT appended to ``book["openPositions"]`` here.
        The position is placed on the exchange and will be picked up during
        the next ``sync_book`` call, which is the authoritative source of
        truth for live open positions.
        """
        actions: list[dict[str, Any]] = []
        warnings: list[str] = []
        status = self.live_status or {"canExecute": False}

        if not status["canExecute"]:
            warnings.append(f"Skipped live entry {candidate['symbol']}: real execution is not enabled.")
            return book, actions, warnings

        config = self._ensure_config()
        side = entry["side"]
        entry_price = num(candidate.get("price")) or 0
        notional_usd = entry["notional_usd"]
        stop_loss = entry["stop_loss"]
        take_profit = entry["take_profit"]

        # Apply margin cap for live trading
        from ..engine_core import cap_live_notional_by_margin, summarize_account

        account_summary = summarize_account(book, {})
        notional_usd = cap_live_notional_by_margin(
            notional_usd,
            account_summary=account_summary,
            live_config=config,
        )
        if notional_usd < 20:
            warnings.append(f"Skipped live entry {candidate['symbol']}: available margin is too small after leverage cap.")
            return book, actions, warnings

        try:
            apply_symbol_settings(config, candidate["symbol"])
        except Exception as error:
            warnings.append(f"Live symbol settings update skipped for {candidate['symbol']}: {error}")

        quantity = normalize_quantity(config, candidate["symbol"], notional_usd=notional_usd, reference_price=entry_price)
        order_side = "BUY" if side == "long" else "SELL"
        place_market_order(config, symbol=candidate["symbol"], side=order_side, quantity=quantity)

        if entry.get("use_exchange_protection", False):
            try:
                cancel_all_open_orders(config, candidate["symbol"])
                place_protection_orders(
                    config,
                    symbol=candidate["symbol"],
                    position_side=side,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
            except Exception as error:
                warnings.append(f"Exchange protection order placement failed for {candidate['symbol']}: {error}")

        action = {
            "type": "open",
            "symbol": candidate["symbol"],
            "side": side,
            "confidence": entry["confidence"],
            "notionalUsd": notional_usd,
            "stopLoss": stop_loss,
            "takeProfit": take_profit,
            "reason": entry["reason"],
            "label": action_label("open", candidate["symbol"], side),
        }
        return book, [action], warnings

    def apply_circuit_breaker(
        self,
        book: dict[str, Any],
        positions: list[dict[str, Any]],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        actions: list[dict[str, Any]] = []
        warnings: list[str] = []
        status = self.live_status or {"canExecute": False}
        config = self._ensure_config()

        for position in positions:
            if not status.get("canExecute"):
                warnings.append(f"Circuit breaker could not close live {position['symbol']} because real execution is not enabled.")
                continue
            cancel_all_open_orders(config, position["symbol"])
            order_side = "SELL" if position["side"] == "long" else "BUY"
            place_market_order(config, symbol=position["symbol"], side=order_side, quantity=position["quantity"], reduce_only=True)
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

    def flatten_all_positions(
        self,
        book: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Close every open position (manual flatten).

        Unlike ``apply_circuit_breaker``, this method raises if live
        execution is not enabled.  Flatten is an explicit user action
        and should fail fast rather than silently skip orders.
        """
        actions: list[dict[str, Any]] = []
        warnings: list[str] = []
        status = self.live_status or {"canExecute": False}
        config = self._ensure_config()

        if not status["canExecute"]:
            raise RuntimeError("Live flatten requires real execution to be enabled.")

        for position in list(book.get("openPositions", [])):
            cancel_all_open_orders(config, position["symbol"])
            side = "SELL" if position["side"] == "long" else "BUY"
            place_market_order(config, symbol=position["symbol"], side=side, quantity=position["quantity"], reduce_only=True)
            book, action = close_position(
                book,
                position,
                num(position.get("lastMarkPrice")) or num(position.get("entryPrice")) or 0,
                decision_id,
                "manual_flatten",
            )
            actions.append(action)
        return book, actions, warnings

    def _use_exchange_protection(self) -> bool:
        live_exec = self.settings.get("liveExecution")
        if isinstance(live_exec, dict):
            return bool(live_exec.get("useExchangeProtectionOrders"))
        return False
