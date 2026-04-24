from __future__ import annotations

import json
import logging
import os
import sys
import threading
from collections import deque
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class _MemoryLogBuffer(logging.Handler):
    """Thread-safe in-memory handler that keeps the last N log entries."""

    def __init__(self, capacity: int = 400) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._entries: deque[dict[str, Any]] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "at": self._iso_now(),
            "level": record.levelname,
            "message": record.getMessage(),
            "line": self.format(record),
        }
        with self._lock:
            self._entries.append(entry)

    def get_entries(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries)

    @staticmethod
    def _iso_now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# Module-level singleton so that all loggers share the same memory buffer.
_memory_handler: _MemoryLogBuffer | None = None
_root_configured = False
_lock = threading.Lock()


def configure_logging(
    level: int | str | None = None,
    capacity: int = 400,
) -> _MemoryLogBuffer:
    """Configure root logger with JSON output to stdout and a memory buffer.

    Args:
        level: Log level (defaults to env LOG_LEVEL or INFO).
        capacity: Maximum number of entries to keep in the memory buffer.

    Returns:
        The memory buffer handler for querying recent log entries.
    """
    global _memory_handler, _root_configured

    with _lock:
        if _root_configured:
            if _memory_handler is not None:
                return _memory_handler

        if level is None:
            level = os.environ.get("LOG_LEVEL", "INFO").upper()
        if isinstance(level, str):
            level = getattr(logging, level, logging.INFO)

        formatter = JSONFormatter()

        # Stream handler -> stdout
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        # Memory buffer handler
        mem_handler = _MemoryLogBuffer(capacity=capacity)
        mem_handler.setFormatter(formatter)

        root = logging.getLogger()
        root.setLevel(level)

        # Avoid duplicate handlers on re-configuration
        for h in list(root.handlers):
            if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                root.removeHandler(h)

        root.addHandler(stream_handler)
        root.addHandler(mem_handler)

        _memory_handler = mem_handler
        _root_configured = True
        return mem_handler


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Configures root logging if not already done."""
    if not _root_configured:
        configure_logging()
    return logging.getLogger(name)


def get_memory_entries() -> list[dict[str, Any]]:
    """Return the current entries from the memory log buffer."""
    if _memory_handler is None:
        return []
    return _memory_handler.get_entries()
