from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from backend.utils import read_json, write_json


class TestWriteJsonPermissions(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_live_trading_json_gets_600_permission(self) -> None:
        path = self.tmp_path / "live_trading.json"
        write_json(path, {"apiKey": "secret123", "enabled": True})

        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_llm_provider_json_gets_600_permission(self) -> None:
        path = self.tmp_path / "llm_provider.json"
        write_json(path, {"apiKey": "sk-test", "model": "gpt-4"})

        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_dashboard_settings_json_no_special_permission(self) -> None:
        path = self.tmp_path / "dashboard_settings.json"
        write_json(path, {"timezone": "UTC", "pageAutoRefreshSeconds": 30})

        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertNotEqual(mode, 0o600)

    def test_trading_agent_json_no_special_permission(self) -> None:
        path = self.tmp_path / "trading_agent.json"
        write_json(path, {"mode": "paper"})

        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertNotEqual(mode, 0o600)

    def test_existing_file_permission_corrected_to_600(self) -> None:
        path = self.tmp_path / "live_trading.json"
        path.write_text("{}", encoding="utf-8")
        os.chmod(path, 0o644)

        write_json(path, {"apiKey": "new-secret", "enabled": False})

        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_existing_llm_provider_permission_corrected_to_600(self) -> None:
        path = self.tmp_path / "llm_provider.json"
        path.write_text("{}", encoding="utf-8")
        os.chmod(path, 0o755)

        write_json(path, {"apiKey": "new-key"})

        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_read_json_corrects_permissive_live_trading(self) -> None:
        path = self.tmp_path / "live_trading.json"
        path.write_text('{"apiKey": "secret"}', encoding="utf-8")
        os.chmod(path, 0o644)

        result = read_json(path, {})

        self.assertEqual(result.get("apiKey"), "secret")
        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_read_json_corrects_permissive_llm_provider(self) -> None:
        path = self.tmp_path / "llm_provider.json"
        path.write_text('{"apiKey": "sk-test"}', encoding="utf-8")
        os.chmod(path, 0o755)

        result = read_json(path, {})

        self.assertEqual(result.get("apiKey"), "sk-test")
        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_read_json_does_not_touch_non_sensitive_files(self) -> None:
        path = self.tmp_path / "dashboard_settings.json"
        path.write_text('{"timezone": "UTC"}', encoding="utf-8")
        os.chmod(path, 0o644)

        result = read_json(path, {})

        self.assertEqual(result.get("timezone"), "UTC")
        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o644)

    def test_read_json_returns_default_when_file_missing(self) -> None:
        path = self.tmp_path / "live_trading.json"

        result = read_json(path, {"default": True})

        self.assertEqual(result, {"default": True})


if __name__ == "__main__":
    unittest.main()
