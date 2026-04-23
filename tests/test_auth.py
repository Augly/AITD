from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.auth import (
    AUTH_CONFIG_PATH,
    ENV_VAR_NAME,
    HEADER_NAME,
    get_auth_error_response,
    get_configured_api_key,
    is_auth_enabled,
    validate_api_key,
)
from backend.utils import write_json


class TestAuthNoConfiguration(unittest.TestCase):
    def setUp(self) -> None:
        self._clear_env_and_config()

    def tearDown(self) -> None:
        self._clear_env_and_config()

    def _clear_env_and_config(self) -> None:
        os.environ.pop(ENV_VAR_NAME, None)
        if AUTH_CONFIG_PATH.exists():
            AUTH_CONFIG_PATH.unlink()

    def test_get_configured_api_key_returns_none(self) -> None:
        self.assertIsNone(get_configured_api_key())

    def test_is_auth_enabled_returns_false(self) -> None:
        self.assertFalse(is_auth_enabled())

    def test_validate_api_key_returns_true_when_no_key_configured(self) -> None:
        self.assertTrue(validate_api_key("any-key"))
        self.assertTrue(validate_api_key(""))
        self.assertTrue(validate_api_key("   "))

    def test_get_auth_error_response_format(self) -> None:
        response = get_auth_error_response()
        self.assertEqual(response["error"], "Unauthorized")
        self.assertIn(HEADER_NAME, response["message"])
        self.assertEqual(response["status"], 401)


class TestAuthWithEnvVar(unittest.TestCase):
    def setUp(self) -> None:
        self._clear_env_and_config()
        os.environ[ENV_VAR_NAME] = "test-env-key-123"

    def tearDown(self) -> None:
        self._clear_env_and_config()

    def _clear_env_and_config(self) -> None:
        os.environ.pop(ENV_VAR_NAME, None)
        if AUTH_CONFIG_PATH.exists():
            AUTH_CONFIG_PATH.unlink()

    def test_get_configured_api_key_from_env(self) -> None:
        self.assertEqual(get_configured_api_key(), "test-env-key-123")

    def test_is_auth_enabled_returns_true(self) -> None:
        self.assertTrue(is_auth_enabled())

    def test_validate_api_key_with_correct_key(self) -> None:
        self.assertTrue(validate_api_key("test-env-key-123"))

    def test_validate_api_key_with_wrong_key(self) -> None:
        self.assertFalse(validate_api_key("wrong-key"))

    def test_validate_api_key_is_case_sensitive(self) -> None:
        self.assertFalse(validate_api_key("TEST-ENV-KEY-123"))

    def test_validate_api_key_strips_whitespace(self) -> None:
        self.assertTrue(validate_api_key("  test-env-key-123  "))

    def test_env_var_takes_priority_over_config_file(self) -> None:
        write_json(AUTH_CONFIG_PATH, {"apiKey": "config-file-key"})
        self.assertEqual(get_configured_api_key(), "test-env-key-123")


class TestAuthWithConfigFile(unittest.TestCase):
    def setUp(self) -> None:
        self._clear_env_and_config()
        write_json(AUTH_CONFIG_PATH, {"apiKey": "test-config-key-456"})

    def tearDown(self) -> None:
        self._clear_env_and_config()

    def _clear_env_and_config(self) -> None:
        os.environ.pop(ENV_VAR_NAME, None)
        if AUTH_CONFIG_PATH.exists():
            AUTH_CONFIG_PATH.unlink()

    def test_get_configured_api_key_from_config(self) -> None:
        self.assertEqual(get_configured_api_key(), "test-config-key-456")

    def test_is_auth_enabled_returns_true(self) -> None:
        self.assertTrue(is_auth_enabled())

    def test_validate_api_key_with_correct_key(self) -> None:
        self.assertTrue(validate_api_key("test-config-key-456"))

    def test_validate_api_key_with_wrong_key(self) -> None:
        self.assertFalse(validate_api_key("wrong-key"))

    def test_config_file_whitespace_key_treated_as_empty(self) -> None:
        write_json(AUTH_CONFIG_PATH, {"apiKey": "   "})
        self.assertIsNone(get_configured_api_key())
        self.assertFalse(is_auth_enabled())


class TestAuthEdgeCases(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(ENV_VAR_NAME, None)
        if AUTH_CONFIG_PATH.exists():
            AUTH_CONFIG_PATH.unlink()

    def test_empty_env_var_treated_as_unconfigured(self) -> None:
        os.environ[ENV_VAR_NAME] = ""
        self.assertIsNone(get_configured_api_key())
        self.assertFalse(is_auth_enabled())

    def test_whitespace_only_env_var_treated_as_unconfigured(self) -> None:
        os.environ[ENV_VAR_NAME] = "   "
        self.assertIsNone(get_configured_api_key())
        self.assertFalse(is_auth_enabled())

    def test_missing_config_file_returns_none(self) -> None:
        self.assertFalse(AUTH_CONFIG_PATH.exists())
        self.assertIsNone(get_configured_api_key())

    def test_invalid_config_file_format_returns_none(self) -> None:
        AUTH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUTH_CONFIG_PATH.write_text("not json", encoding="utf-8")
        self.assertIsNone(get_configured_api_key())

    def test_config_file_without_api_key_field_returns_none(self) -> None:
        write_json(AUTH_CONFIG_PATH, {"otherField": "value"})
        self.assertIsNone(get_configured_api_key())

    def test_config_file_with_non_string_api_key_returns_none(self) -> None:
        write_json(AUTH_CONFIG_PATH, {"apiKey": 12345})
        self.assertIsNone(get_configured_api_key())


if __name__ == "__main__":
    unittest.main()
