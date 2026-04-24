from __future__ import annotations

import json
import logging
import os
import sys
import threading
from unittest.mock import patch

import pytest

from backend.logging_config import (
    JSONFormatter,
    _MemoryLogBuffer,
    configure_logging,
    get_logger,
    get_memory_entries,
)


class TestJSONFormatter:
    def test_basic_format(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0, msg="hello", args=(), exc_info=None
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "hello"
        assert "timestamp" in parsed

    def test_format_with_exception(self) -> None:
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except Exception:
            import sys

            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="error occurred",
                args=(),
                exc_info=exc_info,
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "ERROR"
        assert parsed["message"] == "error occurred"
        assert "exc_info" in parsed
        assert "ValueError" in parsed["exc_info"]

    def test_format_non_ascii(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0, msg="你好", args=(), exc_info=None
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "你好"


class TestMemoryLogBuffer:
    def test_capacity_limit(self) -> None:
        buf = _MemoryLogBuffer(capacity=3)
        logger = logging.getLogger("test_capacity")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []
        logger.addHandler(buf)

        logger.info("msg1")
        logger.info("msg2")
        logger.info("msg3")
        logger.info("msg4")

        entries = buf.get_entries()
        assert len(entries) == 3
        assert entries[0]["message"] == "msg2"
        assert entries[2]["message"] == "msg4"

    def test_thread_safety(self) -> None:
        buf = _MemoryLogBuffer(capacity=100)
        logger = logging.getLogger("test_thread")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []
        logger.addHandler(buf)

        errors: list[Exception] = []

        def worker() -> None:
            try:
                for i in range(50):
                    logger.info("thread msg %d", i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        entries = buf.get_entries()
        assert len(entries) == 100  # capped at capacity

    def test_entry_structure(self) -> None:
        buf = _MemoryLogBuffer(capacity=10)
        logger = logging.getLogger("test_structure")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []
        logger.addHandler(buf)

        logger.warning("warn test")
        entries = buf.get_entries()
        assert len(entries) == 1
        entry = entries[0]
        assert set(entry.keys()) == {"at", "level", "message", "line"}
        assert entry["level"] == "WARNING"
        assert entry["message"] == "warn test"
        assert entry["at"].endswith("Z")


class TestConfigureLogging:
    def test_default_level(self) -> None:
        # Reset internal state
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            mem = configure_logging()
            root = logging.getLogger()
            assert root.level == logging.INFO
            assert mem is not None
            # Clean up
            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)

    def test_explicit_level(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            configure_logging(level=logging.DEBUG)
            root = logging.getLogger()
            assert root.level == logging.DEBUG
            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)

    def test_env_level(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            with patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}):
                configure_logging()
                root = logging.getLogger()
                assert root.level == logging.ERROR
                for h in list(root.handlers):
                    if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                        root.removeHandler(h)

    def test_reconfigure_avoids_duplicate_handlers(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            configure_logging()
            root = logging.getLogger()
            stream_count = sum(
                1 for h in root.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, _MemoryLogBuffer)
            )
            assert stream_count == 1

            configure_logging()
            stream_count = sum(
                1 for h in root.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, _MemoryLogBuffer)
            )
            assert stream_count == 1

            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)

    def test_stream_handler_uses_stdout(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            configure_logging()
            root = logging.getLogger()
            stream_handlers = [
                h for h in root.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, _MemoryLogBuffer)
            ]
            assert len(stream_handlers) == 1
            assert stream_handlers[0].stream is sys.stdout

            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)


class TestGetLogger:
    def test_returns_named_logger(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            logger = get_logger("my_module")
            assert logger.name == "my_module"
            assert isinstance(logger, logging.Logger)
            root = logging.getLogger()
            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)

    def test_auto_configures(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            logger = get_logger("auto_config")
            root = logging.getLogger()
            has_stream = any(
                isinstance(h, logging.StreamHandler) and not isinstance(h, _MemoryLogBuffer)
                for h in root.handlers
            )
            assert has_stream
            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)


class TestGetMemoryEntries:
    def test_empty_when_not_configured(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_memory_handler", None):
            assert get_memory_entries() == []

    def test_returns_entries(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            configure_logging()
            logger = get_logger("memory_test")
            logger.info("entry one")
            logger.warning("entry two")

            entries = get_memory_entries()
            assert len(entries) == 2
            assert entries[0]["message"] == "entry one"
            assert entries[1]["message"] == "entry two"
            assert entries[0]["level"] == "INFO"
            assert entries[1]["level"] == "WARNING"

            root = logging.getLogger()
            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)


class TestIntegration:
    def test_log_levels_filtering(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            configure_logging(level=logging.WARNING)
            logger = get_logger("level_test")

            logger.debug("debug msg")
            logger.info("info msg")
            logger.warning("warn msg")
            logger.error("error msg")

            entries = get_memory_entries()
            messages = [e["message"] for e in entries]
            assert "debug msg" not in messages
            assert "info msg" not in messages
            assert "warn msg" in messages
            assert "error msg" in messages

            root = logging.getLogger()
            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)

    def test_json_output_format(self) -> None:
        import backend.logging_config as lc

        with patch.object(lc, "_root_configured", False), patch.object(lc, "_memory_handler", None):
            configure_logging()
            logger = get_logger("json_test")
            logger.info("json msg")

            entries = get_memory_entries()
            assert len(entries) == 1
            line = entries[0]["line"]
            parsed = json.loads(line)
            assert parsed["level"] == "INFO"
            assert parsed["message"] == "json msg"
            assert "timestamp" in parsed

            root = logging.getLogger()
            for h in list(root.handlers):
                if isinstance(h, (logging.StreamHandler, _MemoryLogBuffer)):
                    root.removeHandler(h)
