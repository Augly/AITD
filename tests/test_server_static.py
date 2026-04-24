from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.server import TradingAgentHandler


class TestServeStatic(unittest.TestCase):
    def setUp(self):
        self.runtime = MagicMock()
        TradingAgentHandler.runtime = self.runtime

    def _create_handler(self):
        handler = MagicMock(spec=TradingAgentHandler)
        handler.runtime = self.runtime
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = MagicMock()
        return handler

    def _call_serve_static(self, handler, path):
        TradingAgentHandler._serve_static(handler, path)

    def test_normal_file_served(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_dir = Path(tmpdir)
            (dashboard_dir / "test.txt").write_text("hello")

            with patch("backend.server.DASHBOARD_DIR", dashboard_dir):
                handler = self._create_handler()
                self._call_serve_static(handler, "/test.txt")

            handler.send_response.assert_called_once_with(200)

    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_root = Path(tmpdir)
            dashboard_dir = sandbox_root / "dashboard"
            dashboard_dir.mkdir()
            outside_root = sandbox_root / "outside-root"
            outside_root.mkdir()
            (outside_root / "secret.txt").write_text("secret")

            with patch("backend.server.DASHBOARD_DIR", dashboard_dir):
                handler = self._create_handler()
                self._call_serve_static(handler, "../outside-root/secret.txt")

            handler.send_response.assert_called_once_with(403)

    def test_symlink_file_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_root = Path(tmpdir)
            dashboard_dir = sandbox_root / "dashboard"
            dashboard_dir.mkdir()
            outside_root = sandbox_root / "outside-root"
            outside_root.mkdir()
            target_file = outside_root / "target.txt"
            target_file.write_text("target")
            (dashboard_dir / "link.txt").symlink_to(target_file)

            with patch("backend.server.DASHBOARD_DIR", dashboard_dir):
                handler = self._create_handler()
                self._call_serve_static(handler, "/link.txt")

            handler.send_response.assert_called_once_with(403)

    def test_symlink_parent_directory_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_root = Path(tmpdir)
            dashboard_dir = sandbox_root / "dashboard"
            dashboard_dir.mkdir()
            outside_root = sandbox_root / "outside-root"
            outside_root.mkdir()
            target_dir = outside_root / "nested"
            target_dir.mkdir()
            (target_dir / "file.txt").write_text("content")
            (dashboard_dir / "linked_dir").symlink_to(target_dir)

            with patch("backend.server.DASHBOARD_DIR", dashboard_dir):
                handler = self._create_handler()
                self._call_serve_static(handler, "/linked_dir/file.txt")

            handler.send_response.assert_called_once_with(403)

    def test_symlink_to_internal_path_still_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_dir = Path(tmpdir)
            real_dir = dashboard_dir / "real"
            real_dir.mkdir()
            (real_dir / "file.txt").write_text("content")
            (dashboard_dir / "alias").symlink_to(real_dir)

            with patch("backend.server.DASHBOARD_DIR", dashboard_dir):
                handler = self._create_handler()
                self._call_serve_static(handler, "/alias/file.txt")

            handler.send_response.assert_called_once_with(403)

    def test_commonpath_validation_blocks_escape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_dir = Path(tmpdir)

            with patch("backend.server.DASHBOARD_DIR", dashboard_dir):
                handler = self._create_handler()
                self._call_serve_static(handler, "../../../etc/passwd")

            handler.send_response.assert_called_once_with(403)

    def test_nonexistent_file_returns_404(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_dir = Path(tmpdir)

            with patch("backend.server.DASHBOARD_DIR", dashboard_dir):
                handler = self._create_handler()
                self._call_serve_static(handler, "/nonexistent.txt")

            handler.send_response.assert_called_once_with(404)

    def test_root_path_serves_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_dir = Path(tmpdir)
            (dashboard_dir / "index.html").write_text("<html></html>")

            with patch("backend.server.DASHBOARD_DIR", dashboard_dir):
                handler = self._create_handler()
                self._call_serve_static(handler, "/")

            handler.send_response.assert_called_once_with(200)


if __name__ == "__main__":
    unittest.main()
