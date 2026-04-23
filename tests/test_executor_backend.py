"""Tests for the ExecutionBackend abstract interface."""

from __future__ import annotations

import pytest

from backend.engine.executor import ExecutionBackend


class _MinimalBackend(ExecutionBackend):
    """Minimal concrete implementation for interface validation."""

    def sync_book(self, book, settings):
        return book, [], None, None

    def apply_position_action(self, book, position, action, decision_id):
        return book, [], []

    def open_position(
        self,
        book,
        *,
        candidate,
        side,
        stop_loss,
        take_profit,
        confidence,
        notional_usd,
        reason,
        decision_id,
    ):
        return {}

    def flatten_positions(self, book, settings, decision_id):
        return book, [], []

    def reset_account(self, book, settings):
        return book, []

    def can_execute(self):
        return True


class TestExecutionBackendInterface:
    """Verify that ExecutionBackend can be subclassed and instantiated."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            ExecutionBackend()

    def test_can_instantiate_concrete_subclass(self):
        backend = _MinimalBackend()
        assert isinstance(backend, ExecutionBackend)

    def test_sync_book_signature(self):
        backend = _MinimalBackend()
        book = {"initialCapitalUsd": 10000.0}
        settings = {"mode": "paper"}
        updated_book, warnings, live_status, live_config = backend.sync_book(book, settings)
        assert updated_book is book
        assert warnings == []
        assert live_status is None
        assert live_config is None

    def test_apply_position_action_signature(self):
        backend = _MinimalBackend()
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
        backend = _MinimalBackend()
        book = {"openPositions": []}
        candidate = {"symbol": "BTCUSDT", "baseAsset": "BTC", "price": 50000.0}
        position = backend.open_position(
            book,
            candidate=candidate,
            side="long",
            stop_loss=45000.0,
            take_profit=60000.0,
            confidence=0.85,
            notional_usd=1000.0,
            reason="test_entry",
            decision_id="decision-123",
        )
        assert isinstance(position, dict)

    def test_flatten_positions_signature(self):
        backend = _MinimalBackend()
        book = {"openPositions": []}
        settings = {"mode": "paper"}
        updated_book, actions, warnings = backend.flatten_positions(
            book, settings, "flatten-123"
        )
        assert updated_book is book
        assert actions == []
        assert warnings == []

    def test_reset_account_signature(self):
        backend = _MinimalBackend()
        book = {"initialCapitalUsd": 10000.0}
        settings = {"mode": "paper"}
        reset_book, warnings = backend.reset_account(book, settings)
        assert reset_book is book
        assert warnings == []

    def test_can_execute_signature(self):
        backend = _MinimalBackend()
        assert backend.can_execute() is True


class TestExecutionBackendMethodCoverage:
    """Verify the interface covers all required Paper/Live operations."""

    def test_all_methods_present(self):
        """Ensure no methods are missing from the abstract interface."""
        required_methods = {
            "sync_book",
            "apply_position_action",
            "open_position",
            "flatten_positions",
            "reset_account",
            "can_execute",
        }
        actual_methods = {
            name
            for name in dir(ExecutionBackend)
            if not name.startswith("_") and callable(getattr(ExecutionBackend, name, None))
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
