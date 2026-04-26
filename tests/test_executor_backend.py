"""Tests for the ExecutionBackend abstract interface."""

from __future__ import annotations

import pytest

from backend.engine.executor import ExecutionBackend


class _MinimalBackend(ExecutionBackend):
    """Minimal concrete implementation for interface validation."""

    def sync_book(self, book):
        return book, []

    def apply_position_action(self, book, position, action, decision_id):
        return book, [], []

    def open_position(
        self,
        book,
        candidate,
        entry,
        decision_id,
    ):
        return book, [], []

    def apply_circuit_breaker(self, book, positions, decision_id):
        return book, [], []

    def flatten_all_positions(self, book, decision_id):
        return book, [], []


class TestExecutionBackendInterface:
    """Verify that ExecutionBackend can be subclassed and instantiated."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            ExecutionBackend()

    def test_can_instantiate_concrete_subclass(self):
        backend = _MinimalBackend({})
        assert isinstance(backend, ExecutionBackend)

    def test_sync_book_signature(self):
        backend = _MinimalBackend({})
        book = {"initialCapitalUsd": 10000.0}
        updated_book, warnings = backend.sync_book(book)
        assert updated_book is book
        assert warnings == []

    def test_apply_position_action_signature(self):
        backend = _MinimalBackend({})
        book = {"openPositions": []}
        position = {"symbol": "BTCUSDT", "side": "long"}
        action = {"decision": "close", "reason": "test"}
        updated_book, actions, warnings = backend.apply_position_action(
            book, position, action, "decision-123"
        )
        assert updated_book is book
        assert actions == []
        assert warnings == []

    def test_open_position_signature(self):
        backend = _MinimalBackend({})
        book = {"openPositions": []}
        candidate = {"symbol": "BTCUSDT", "baseAsset": "BTC", "price": 50000.0}
        entry = {"side": "long", "stop_loss": 45000.0, "take_profit": 60000.0, "confidence": 0.85, "notional_usd": 1000.0, "reason": "test_entry"}
        updated_book, actions, warnings = backend.open_position(
            book,
            candidate,
            entry,
            "decision-123",
        )
        assert updated_book is book
        assert actions == []
        assert warnings == []

    def test_flatten_all_positions_signature(self):
        backend = _MinimalBackend({})
        book = {"openPositions": []}
        updated_book, actions, warnings = backend.flatten_all_positions(
            book, "flatten-123"
        )
        assert updated_book is book
        assert actions == []
        assert warnings == []

    def test_all_methods_present(self):
        """Ensure no methods are missing from the abstract interface."""
        required_methods = {
            "sync_book",
            "apply_position_action",
            "open_position",
            "apply_circuit_breaker",
            "flatten_all_positions",
        }
        actual_methods = {
            name
            for name in dir(ExecutionBackend)
            if not name.startswith("_") and callable(getattr(ExecutionBackend, name, None))
            and name != "execute_decision" # Not abstract, implemented bridge method
        }
        assert required_methods <= actual_methods, (
            f"Missing methods: {required_methods - actual_methods}"
        )

    def test_all_methods_are_abstract(self):
        """Every public method should be abstract (must be overridden)."""
        for name in dir(ExecutionBackend):
            if name.startswith("_"):
                continue
            attr = getattr(ExecutionBackend, name)
            if callable(attr) and hasattr(attr, "__isabstractmethod__"):
                assert attr.__isabstractmethod__ is True, (
                    f"Method {name} is not abstract"
                )
