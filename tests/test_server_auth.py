from __future__ import annotations

import json
import os
import unittest
from http.cookies import SimpleCookie
from io import BytesIO
from unittest.mock import MagicMock, patch

from backend.server import _check_api_auth, _is_api_path, TradingAgentHandler
from backend.auth import HEADER_NAME


class TestServerAuthHelpers(unittest.TestCase):
    def test_is_api_path_with_api_path(self):
        self.assertTrue(_is_api_path("/api/latest"))
        self.assertTrue(_is_api_path("/api/settings"))
        self.assertTrue(_is_api_path("/api/trading/state"))

    def test_is_api_path_with_non_api_path(self):
        self.assertFalse(_is_api_path("/"))
        self.assertFalse(_is_api_path("/trader.html"))
        self.assertFalse(_is_api_path("/css/style.css"))
        self.assertFalse(_is_api_path("/js/app.js"))

    @patch("backend.server.is_auth_enabled")
    @patch("backend.server.validate_api_key")
    def test_check_api_auth_disabled_always_true(self, mock_validate, mock_enabled):
        mock_enabled.return_value = False
        handler = MagicMock()
        handler.headers = {}
        self.assertTrue(_check_api_auth(handler))
        mock_validate.assert_not_called()

    @patch("backend.server.is_auth_enabled")
    @patch("backend.server.validate_api_key")
    def test_check_api_auth_enabled_valid_key(self, mock_validate, mock_enabled):
        mock_enabled.return_value = True
        mock_validate.return_value = True
        handler = MagicMock()
        handler.headers = {HEADER_NAME: "valid-key"}
        self.assertTrue(_check_api_auth(handler))
        mock_validate.assert_called_once_with("valid-key")

    @patch("backend.server.is_auth_enabled")
    @patch("backend.server.validate_api_key")
    def test_check_api_auth_enabled_invalid_key(self, mock_validate, mock_enabled):
        mock_enabled.return_value = True
        mock_validate.return_value = False
        handler = MagicMock()
        handler.headers = {HEADER_NAME: "invalid-key"}
        self.assertFalse(_check_api_auth(handler))
        mock_validate.assert_called_once_with("invalid-key")

    @patch("backend.server.is_auth_enabled")
    @patch("backend.server.validate_api_key")
    def test_check_api_auth_enabled_missing_key(self, mock_validate, mock_enabled):
        mock_enabled.return_value = True
        mock_validate.return_value = False
        handler = MagicMock()
        handler.headers = {}
        self.assertFalse(_check_api_auth(handler))
        mock_validate.assert_called_once_with("")


class TestServerAuthIntegration(unittest.TestCase):
    def setUp(self):
        self.runtime = MagicMock()
        TradingAgentHandler.runtime = self.runtime

    def _create_mock_handler(self, path, method="GET", headers=None, body=None):
        handler = MagicMock(spec=TradingAgentHandler)
        handler.path = path
        handler.headers = headers or {}
        handler.runtime = TradingAgentHandler.runtime
        if body is not None:
            handler.rfile = BytesIO(json.dumps(body).encode("utf-8"))
            handler.headers["Content-Length"] = str(len(json.dumps(body)))
        else:
            handler.rfile = BytesIO(b"")
        handler.wfile = BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler._serve_static = MagicMock()
        return handler

    def _handle_with_method(self, handler, method):
        TradingAgentHandler._handle(handler, method)

    @patch("backend.server.is_auth_enabled")
    def test_auth_status_endpoint_when_disabled(self, mock_enabled):
        mock_enabled.return_value = False
        handler = self._create_mock_handler("/api/auth/status", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(200)

    @patch("backend.server.is_auth_enabled")
    def test_auth_status_endpoint_when_enabled(self, mock_enabled):
        mock_enabled.return_value = True
        handler = self._create_mock_handler("/api/auth/status", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(200)

    @patch("backend.server.is_auth_enabled", return_value=False)
    @patch("backend.server.read_latest_scan", return_value={})
    def test_api_access_allowed_when_auth_disabled(self, mock_read, mock_enabled):
        handler = self._create_mock_handler("/api/opportunities", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(200)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled", return_value=True)
    def test_api_access_denied_without_key_when_enabled(self, mock_enabled, mock_get_key):
        handler = self._create_mock_handler("/api/opportunities", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(401)
        handler.send_header.assert_any_call("WWW-Authenticate", HEADER_NAME)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled", return_value=True)
    @patch("backend.server.validate_api_key", return_value=True)
    @patch("backend.server.read_latest_scan", return_value={})
    def test_api_access_allowed_with_valid_key(self, mock_read, mock_validate, mock_enabled, mock_get_key):
        handler = self._create_mock_handler("/api/opportunities", method="GET", headers={HEADER_NAME: "valid-key"})
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(200)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled", return_value=True)
    @patch("backend.server.validate_api_key", return_value=False)
    def test_api_access_denied_with_invalid_key(self, mock_validate, mock_enabled, mock_get_key):
        handler = self._create_mock_handler("/api/opportunities", method="GET", headers={HEADER_NAME: "invalid-key"})
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(401)

    @patch("backend.server.is_auth_enabled", return_value=True)
    def test_static_files_no_auth_required(self, mock_enabled):
        handler = self._create_mock_handler("/trader.html", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_not_called()

    @patch("backend.server.is_auth_enabled", return_value=True)
    def test_root_path_no_auth_required(self, mock_enabled):
        handler = self._create_mock_handler("/", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_not_called()

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled", return_value=True)
    def test_post_api_access_denied_without_key_when_enabled(self, mock_enabled, mock_get_key):
        handler = self._create_mock_handler("/api/settings", method="POST", body={"pageAutoRefreshSeconds": 5})
        self._handle_with_method(handler, "POST")
        handler.send_response.assert_called_once_with(401)
        handler.send_header.assert_any_call("WWW-Authenticate", HEADER_NAME)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled", return_value=True)
    @patch("backend.server.validate_api_key", return_value=True)
    @patch("backend.server.write_dashboard_settings", return_value={"pageAutoRefreshSeconds": 5})
    def test_post_api_access_allowed_with_valid_key(self, mock_write, mock_validate, mock_enabled, mock_get_key):
        handler = self._create_mock_handler("/api/settings", method="POST", headers={HEADER_NAME: "valid-key"}, body={"pageAutoRefreshSeconds": 5})
        self._handle_with_method(handler, "POST")
        handler.send_response.assert_called_once_with(200)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled", return_value=True)
    @patch("backend.server.validate_api_key", return_value=False)
    def test_post_api_access_denied_with_invalid_key(self, mock_validate, mock_enabled, mock_get_key):
        handler = self._create_mock_handler("/api/settings", method="POST", headers={HEADER_NAME: "invalid-key"}, body={"pageAutoRefreshSeconds": 5})
        self._handle_with_method(handler, "POST")
        handler.send_response.assert_called_once_with(401)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled", return_value=True)
    def test_api_logs_get_denied_without_key_when_enabled(self, mock_enabled, mock_get_key):
        handler = self._create_mock_handler("/api/logs", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(401)
        handler.send_header.assert_any_call("WWW-Authenticate", HEADER_NAME)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled", return_value=True)
    @patch("backend.server.validate_api_key", return_value=True)
    def test_api_logs_get_allowed_with_valid_key(self, mock_validate, mock_enabled, mock_get_key):
        TradingAgentHandler.runtime.api_logs = MagicMock(return_value={})
        handler = self._create_mock_handler("/api/logs", method="GET", headers={HEADER_NAME: "valid-key"})
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(200)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled")
    def test_auth_state_toggle_disabled_to_enabled_requires_auth(self, mock_enabled, mock_get_key):
        mock_enabled.return_value = False
        handler = self._create_mock_handler("/api/opportunities", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(200)

        mock_enabled.return_value = True
        handler2 = self._create_mock_handler("/api/opportunities", method="GET")
        self._handle_with_method(handler2, "GET")
        handler2.send_response.assert_called_once_with(401)

    @patch("backend.auth.get_configured_api_key", return_value="secret-key")
    @patch("backend.server.is_auth_enabled")
    @patch("backend.server.read_latest_scan", return_value={})
    def test_auth_state_toggle_enabled_to_disabled_allows_access(self, mock_read, mock_enabled, mock_get_key):
        mock_enabled.return_value = True
        handler = self._create_mock_handler("/api/opportunities", method="GET")
        self._handle_with_method(handler, "GET")
        handler.send_response.assert_called_once_with(401)

        mock_enabled.return_value = False
        handler2 = self._create_mock_handler("/api/opportunities", method="GET")
        self._handle_with_method(handler2, "GET")
        handler2.send_response.assert_called_once_with(200)


if __name__ == "__main__":
    unittest.main()
