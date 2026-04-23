from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from backend.utils import read_json_locked, write_json_locked


class TestReadJsonLocked:
    def test_reads_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"key": "value"}), encoding="utf-8")

        result = read_json_locked(path)

        assert result == {"key": "value"}

    def test_returns_default_when_file_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.json"

        result = read_json_locked(path, default={"default": True})

        assert result == {"default": True}

    def test_returns_none_default_when_file_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.json"

        result = read_json_locked(path)

        assert result is None

    def test_returns_default_on_malformed_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")

        result = read_json_locked(path, default={})

        assert result == {}

    def test_creates_lock_file(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text("{}", encoding="utf-8")
        lock_path = tmp_path / "state.json.lock"

        read_json_locked(path)

        assert lock_path.exists()


class TestWriteJsonLocked:
    def test_writes_json_file(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        payload = {"key": "value", "number": 42}

        write_json_locked(path, payload)

        assert path.exists()
        content = json.loads(path.read_text(encoding="utf-8"))
        assert content == payload

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / "state.json"
        payload = {"data": True}

        write_json_locked(path, payload)

        assert path.exists()

    def test_creates_lock_file(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        lock_path = tmp_path / "state.json.lock"

        write_json_locked(path, {"data": True})

        assert lock_path.exists()

    def test_sensitive_file_gets_600_permission(self, tmp_path: Path) -> None:
        path = tmp_path / "live_trading.json"

        write_json_locked(path, {"apiKey": "secret"})

        mode = os.stat(path).st_mode & 0o777
        assert mode == 0o600

    def test_non_sensitive_file_uses_default_permissions(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        _umask = os.umask(0o022)
        os.umask(_umask)

        write_json_locked(path, {"key": "value"})

        mode = os.stat(path).st_mode & 0o777
        assert mode == (0o666 & ~_umask)

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"old": True}), encoding="utf-8")

        write_json_locked(path, {"new": True})

        content = json.loads(path.read_text(encoding="utf-8"))
        assert content == {"new": True}

    def test_atomic_write_no_partial_file_on_crash(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"

        class WriteCrash(Exception):
            pass

        try:
            write_json_locked(path, {"data": True})
            raise WriteCrash("simulated")
        except WriteCrash:
            pass

        assert path.exists()
        content = json.loads(path.read_text(encoding="utf-8"))
        assert content == {"data": True}

    def test_file_not_corrupted_during_concurrent_writes(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        iterations = 100
        errors: list[Exception] = []

        def writer(value: int) -> None:
            for _ in range(iterations):
                try:
                    write_json_locked(path, {"writer": value})
                except Exception as e:
                    errors.append(e)

        t1 = threading.Thread(target=writer, args=(1,))
        t2 = threading.Thread(target=writer, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0

        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["writer"] in (1, 2)

    def test_no_tmp_files_left_after_write(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"

        write_json_locked(path, {"data": True})

        tmp_files = list(tmp_path.glob("*.tmp*"))
        assert len(tmp_files) == 0


class TestLockExclusion:
    def test_read_blocks_during_write(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        write_json_locked(path, {"version": 1})
        results: list[dict | None] = []

        def slow_writer() -> None:
            write_json_locked(path, {"version": 2})

        def reader() -> None:
            results.append(read_json_locked(path))

        t1 = threading.Thread(target=slow_writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 1
        assert results[0] is not None
        assert "version" in results[0]

    def test_concurrent_reads_are_safe(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        write_json_locked(path, {"data": "initial"})
        results: list[dict | None] = []
        errors: list[Exception] = []

        def reader() -> None:
            try:
                results.append(read_json_locked(path))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 4
        for r in results:
            assert r is not None
            assert r["data"] == "initial"
