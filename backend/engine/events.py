"""EventBus — thread-safe pub/sub for trading-cycle observability.

This module provides a lightweight, zero-dependency event bus that
decouples the trading loop into discrete, observable phases.
"""

from __future__ import annotations

import threading
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Event-type constants — 16 phases of the trading cycle
# ---------------------------------------------------------------------------

# Cycle lifecycle
cycle_started = "cycle.started"
cycle_completed = "cycle.completed"
cycle_failed = "cycle.failed"

# State & data loading
state_loaded = "state.loaded"
candidates_refreshed = "candidates.refreshed"
live_sync_completed = "live.sync.completed"
live_sync_failed = "live.sync.failed"

# Market data & analysis
mark_to_market_applied = "mark_to_market.applied"
live_contexts_fetched = "live.contexts.fetched"
market_backdrop_fetched = "market.backdrop.fetched"

# Decision & model
model_decision_requested = "model.decision.requested"
model_decision_succeeded = "model.decision.succeeded"
model_decision_failed = "model.decision.failed"

# Position management
decision_made = "decision.made"
position_action_applied = "position.action.applied"
protection_hit_applied = "protection.hit.applied"

# Account & risk
circuit_breaker_tripped = "circuit.breaker.tripped"
position_opened = "position.opened"
state_written = "state.written"

# All event types for validation / introspection
ALL_EVENT_TYPES: frozenset[str] = frozenset(
    {
        cycle_started,
        cycle_completed,
        cycle_failed,
        state_loaded,
        candidates_refreshed,
        live_sync_completed,
        live_sync_failed,
        mark_to_market_applied,
        live_contexts_fetched,
        market_backdrop_fetched,
        model_decision_requested,
        model_decision_succeeded,
        model_decision_failed,
        decision_made,
        position_action_applied,
        protection_hit_applied,
        circuit_breaker_tripped,
        position_opened,
        state_written,
    }
)

# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

Handler = Callable[[str, Any], None]


class EventBus:
    """Thread-safe in-memory event bus.

    Supports multiple subscribers per event type, synchronous dispatch,
    and dynamic subscription / unsubscription.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: dict[str, list[Handler]] = {}

    def on(self, event_type: str, handler: Handler) -> None:
        """Subscribe *handler* to *event_type*.

        Duplicate subscriptions are allowed (handler called multiple times).
        """
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def off(self, event_type: str, handler: Handler) -> None:
        """Unsubscribe *handler* from *event_type*.

        If *handler* was subscribed multiple times, only the first
        occurrence is removed.
        """
        with self._lock:
            handlers = self._handlers.get(event_type)
            if not handlers:
                return
            try:
                handlers.remove(handler)
            except ValueError:
                return
            if not handlers:
                del self._handlers[event_type]

    def emit(self, event_type: str, payload: Any = None) -> None:
        """Dispatch *event_type* to all subscribed handlers.

        Handlers are invoked synchronously in subscription order.
        Exceptions raised by a handler are caught and logged to stderr
        so that one failing listener does not break the bus.
        """
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        for handler in handlers:
            try:
                handler(event_type, payload)
            except Exception:
                import sys
                import traceback

                traceback.print_exc(file=sys.stderr)

    def clear(self) -> None:
        """Remove all handlers from all event types."""
        with self._lock:
            self._handlers.clear()

    def listener_count(self, event_type: str) -> int:
        """Return the number of active listeners for *event_type*."""
        with self._lock:
            return len(self._handlers.get(event_type, []))

    def has_listener(self, event_type: str) -> bool:
        """Return ``True`` if at least one listener is registered."""
        with self._lock:
            return event_type in self._handlers and bool(self._handlers[event_type])
