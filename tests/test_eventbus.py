"""Tests for the EventBus and trading-cycle event types."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from backend.engine.events import (
    ALL_EVENT_TYPES,
    EventBus,
    candidates_refreshed,
    circuit_breaker_tripped,
    cycle_completed,
    cycle_failed,
    cycle_started,
    decision_made,
    live_contexts_fetched,
    live_sync_completed,
    live_sync_failed,
    mark_to_market_applied,
    market_backdrop_fetched,
    model_decision_failed,
    model_decision_requested,
    model_decision_succeeded,
    position_action_applied,
    position_opened,
    protection_hit_applied,
    state_loaded,
    state_written,
)


class TestEventTypeConstants:
    """Verify all 16 trading-cycle event type constants are defined."""

    def test_all_event_types_present(self):
        expected = {
            "cycle.started",
            "cycle.completed",
            "cycle.failed",
            "state.loaded",
            "candidates.refreshed",
            "live.sync.completed",
            "live.sync.failed",
            "mark_to_market.applied",
            "live.contexts.fetched",
            "market.backdrop.fetched",
            "model.decision.requested",
            "model.decision.succeeded",
            "model.decision.failed",
            "decision.made",
            "position.action.applied",
            "protection.hit.applied",
            "circuit.breaker.tripped",
            "position.opened",
            "state.written",
        }
        assert ALL_EVENT_TYPES == expected

    def test_individual_constants(self):
        assert cycle_started == "cycle.started"
        assert cycle_completed == "cycle.completed"
        assert cycle_failed == "cycle.failed"
        assert state_loaded == "state.loaded"
        assert candidates_refreshed == "candidates.refreshed"
        assert live_sync_completed == "live.sync.completed"
        assert live_sync_failed == "live.sync.failed"
        assert mark_to_market_applied == "mark_to_market.applied"
        assert live_contexts_fetched == "live.contexts.fetched"
        assert market_backdrop_fetched == "market.backdrop.fetched"
        assert model_decision_requested == "model.decision.requested"
        assert model_decision_succeeded == "model.decision.succeeded"
        assert model_decision_failed == "model.decision.failed"
        assert decision_made == "decision.made"
        assert position_action_applied == "position.action.applied"
        assert protection_hit_applied == "protection.hit.applied"
        assert circuit_breaker_tripped == "circuit.breaker.tripped"
        assert position_opened == "position.opened"
        assert state_written == "state.written"


class TestEventBusSubscribePublish:
    """Verify basic subscribe → publish → receive flow."""

    def test_single_subscriber_receives_event(self):
        bus = EventBus()
        received: list[tuple[str, Any]] = []

        def handler(event_type: str, payload: Any) -> None:
            received.append((event_type, payload))

        bus.on(cycle_started, handler)
        bus.emit(cycle_started, {"mode": "paper"})

        assert len(received) == 1
        assert received[0][0] == cycle_started
        assert received[0][1] == {"mode": "paper"}

    def test_multiple_subscribers_all_receive(self):
        bus = EventBus()
        received_a: list[str] = []
        received_b: list[str] = []

        def handler_a(event_type: str, payload: Any) -> None:
            received_a.append("a")

        def handler_b(event_type: str, payload: Any) -> None:
            received_b.append("b")

        bus.on(cycle_started, handler_a)
        bus.on(cycle_started, handler_b)
        bus.emit(cycle_started)

        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_subscriber_only_receives_subscribed_event(self):
        bus = EventBus()
        received: list[str] = []

        def handler(event_type: str, payload: Any) -> None:
            received.append(event_type)

        bus.on(cycle_started, handler)
        bus.emit(cycle_completed)

        assert len(received) == 0

    def test_payload_defaults_to_none(self):
        bus = EventBus()
        received: list[Any] = []

        def handler(event_type: str, payload: Any) -> None:
            received.append(payload)

        bus.on(state_loaded, handler)
        bus.emit(state_loaded)

        assert len(received) == 1
        assert received[0] is None


class TestEventBusUnsubscribe:
    """Verify off() removes subscriptions correctly."""

    def test_off_removes_handler(self):
        bus = EventBus()
        received: list[str] = []

        def handler(event_type: str, payload: Any) -> None:
            received.append(event_type)

        bus.on(cycle_started, handler)
        bus.off(cycle_started, handler)
        bus.emit(cycle_started)

        assert len(received) == 0

    def test_off_only_removes_first_occurrence(self):
        bus = EventBus()
        received: list[int] = []

        def handler(event_type: str, payload: Any) -> None:
            received.append(1)

        bus.on(cycle_started, handler)
        bus.on(cycle_started, handler)
        bus.off(cycle_started, handler)
        bus.emit(cycle_started)

        assert len(received) == 1

    def test_off_unknown_event_is_noop(self):
        bus = EventBus()

        def handler(event_type: str, payload: Any) -> None:
            pass

        bus.off("unknown.event", handler)

    def test_off_unregistered_handler_is_noop(self):
        bus = EventBus()

        def handler_a(event_type: str, payload: Any) -> None:
            pass

        def handler_b(event_type: str, payload: Any) -> None:
            pass

        bus.on(cycle_started, handler_a)
        bus.off(cycle_started, handler_b)
        assert bus.listener_count(cycle_started) == 1


class TestEventBusThreadSafety:
    """Verify EventBus behaves correctly under concurrent access."""

    def test_concurrent_subscribe_and_emit(self):
        bus = EventBus()
        received = []
        lock = threading.Lock()

        def handler(event_type: str, payload: Any) -> None:
            with lock:
                received.append(payload)

        threads: list[threading.Thread] = []
        for i in range(50):
            t = threading.Thread(target=bus.on, args=(cycle_started, handler))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        bus.emit(cycle_started, "payload")

        assert len(received) == 50

    def test_concurrent_emit(self):
        bus = EventBus()
        received = []
        lock = threading.Lock()

        def handler(event_type: str, payload: Any) -> None:
            with lock:
                received.append(payload)

        for _ in range(10):
            bus.on(cycle_started, handler)

        threads: list[threading.Thread] = []
        for i in range(20):
            t = threading.Thread(target=bus.emit, args=(cycle_started, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(received) == 200  # 10 handlers × 20 emits

    def test_concurrent_off_and_emit(self):
        bus = EventBus()
        received = []
        lock = threading.Lock()

        def handler(event_type: str, payload: Any) -> None:
            with lock:
                received.append(payload)

        for _ in range(10):
            bus.on(cycle_started, handler)

        threads: list[threading.Thread] = []
        for _ in range(5):
            t = threading.Thread(target=bus.off, args=(cycle_started, handler))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        bus.emit(cycle_started, "x")

        assert len(received) == 5  # 10 - 5 removals


class TestEventBusErrorHandling:
    """Verify one failing handler does not break the bus."""

    def test_exception_in_handler_does_not_stop_others(self):
        bus = EventBus()
        received: list[str] = []

        def bad_handler(event_type: str, payload: Any) -> None:
            raise RuntimeError("boom")

        def good_handler(event_type: str, payload: Any) -> None:
            received.append("ok")

        bus.on(cycle_started, bad_handler)
        bus.on(cycle_started, good_handler)
        bus.emit(cycle_started)

        assert len(received) == 1
        assert received[0] == "ok"

    def test_exception_in_handler_allows_future_emits(self):
        bus = EventBus()
        received: list[str] = []

        def bad_handler(event_type: str, payload: Any) -> None:
            raise RuntimeError("boom")

        def good_handler(event_type: str, payload: Any) -> None:
            received.append("ok")

        bus.on(cycle_started, bad_handler)
        bus.on(cycle_started, good_handler)
        bus.emit(cycle_started)
        bus.emit(cycle_started)

        assert len(received) == 2


class TestEventBusIntrospection:
    """Verify listener_count and has_listener helpers."""

    def test_listener_count_empty(self):
        bus = EventBus()
        assert bus.listener_count(cycle_started) == 0

    def test_listener_count_with_subscribers(self):
        bus = EventBus()

        def handler(event_type: str, payload: Any) -> None:
            pass

        bus.on(cycle_started, handler)
        bus.on(cycle_started, handler)
        assert bus.listener_count(cycle_started) == 2

    def test_has_listener_false_when_empty(self):
        bus = EventBus()
        assert bus.has_listener(cycle_started) is False

    def test_has_listener_true_when_subscribed(self):
        bus = EventBus()

        def handler(event_type: str, payload: Any) -> None:
            pass

        bus.on(cycle_started, handler)
        assert bus.has_listener(cycle_started) is True

    def test_has_listener_false_after_off(self):
        bus = EventBus()

        def handler(event_type: str, payload: Any) -> None:
            pass

        bus.on(cycle_started, handler)
        bus.off(cycle_started, handler)
        assert bus.has_listener(cycle_started) is False


class TestEventBusClear:
    """Verify clear() removes all handlers."""

    def test_clear_removes_all(self):
        bus = EventBus()

        def handler(event_type: str, payload: Any) -> None:
            pass

        bus.on(cycle_started, handler)
        bus.on(cycle_completed, handler)
        bus.clear()

        assert bus.listener_count(cycle_started) == 0
        assert bus.listener_count(cycle_completed) == 0

    def test_clear_allows_reuse(self):
        bus = EventBus()
        received: list[str] = []

        def handler(event_type: str, payload: Any) -> None:
            received.append(event_type)

        bus.on(cycle_started, handler)
        bus.clear()
        bus.on(cycle_started, handler)
        bus.emit(cycle_started)

        assert len(received) == 1
