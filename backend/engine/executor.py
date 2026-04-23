from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ExecutionBackend(ABC):
    """Abstract interface for trade execution backends.

    Provides a unified contract for both paper (simulated) and live (real exchange)
    trading operations. Implementations must handle mode-specific concerns such as
    exchange API calls, margin checks, and order placement internally.
    """

    @abstractmethod
    def sync_book(
        self,
        book: dict[str, Any],
        settings: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str], dict[str, Any] | None, dict[str, Any] | None]:
        """Synchronize the account book with the backend's source of truth.

        For paper trading this typically sets initial capital and resets
        derived fields. For live trading this fetches the latest account
        snapshot from the exchange and merges it with local state.

        Args:
            book: The current account book dictionary.
            settings: Trading settings dictionary.

        Returns:
            A tuple of (updated_book, warnings, live_status_payload, live_config).
            Live backends populate the live_status_payload and live_config; paper backends
            return None for those fields.
        """

    @abstractmethod
    def apply_position_action(
        self,
        book: dict[str, Any],
        position: dict[str, Any],
        action: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Apply a position action (close, reduce, or update protection).

        Args:
            book: The current account book dictionary.
            position: The target position dictionary.
            action: The action specification with keys such as ``decision``,
                ``reason``, ``reduceFraction``, ``stopLoss``, ``takeProfit``.
            decision_id: The unique identifier for the current decision cycle.

        Returns:
            A tuple of (updated_book, recorded_actions, warnings).
        """

    @abstractmethod
    def open_position(
        self,
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
        """Open a new position for the given candidate.

        Args:
            book: The current account book dictionary.
            candidate: The candidate opportunity dictionary (must contain
                ``symbol``, ``baseAsset``, ``price``).
            side: Position side - ``"long"`` or ``"short"``.
            stop_loss: Stop-loss price.
            take_profit: Optional take-profit price.
            confidence: Model confidence score (0-1).
            notional_usd: Target notional value in USD.
            reason: Entry reason string.
            decision_id: The unique identifier for the current decision cycle.

        Returns:
            The newly created position dictionary.
        """

    @abstractmethod
    def flatten_positions(
        self,
        book: dict[str, Any],
        settings: dict[str, Any],
        decision_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Close all open positions (flatten the account).

        Args:
            book: The current account book dictionary.
            settings: Trading settings dictionary.
            decision_id: The unique identifier for the flatten operation.

        Returns:
            A tuple of (updated_book, recorded_actions, warnings).
        """

    @abstractmethod
    def reset_account(
        self,
        book: dict[str, Any],
        settings: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """Reset the account to its initial empty state.

        For paper trading this returns a fresh empty account. For live trading
        this may first flatten existing positions on the exchange before
        resetting local state.

        Args:
            book: The current account book dictionary.
            settings: Trading settings dictionary.

        Returns:
            A tuple of (reset_book, warnings).
        """

    @abstractmethod
    def can_execute(self) -> bool:
        """Return whether this backend is currently able to execute trades.

        Paper backends typically always return ``True``. Live backends return
        ``True`` only when API credentials are valid and real execution is
        explicitly enabled.
        """
