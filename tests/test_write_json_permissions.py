from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from backend.utils import write_json


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


if __name__ == "__main__":
    unittest.main()
