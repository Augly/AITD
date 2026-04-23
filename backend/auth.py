from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .utils import CONFIG_DIR, read_json


AUTH_CONFIG_PATH = CONFIG_DIR / "auth.json"
ENV_VAR_NAME = "AITD_API_KEY"
HEADER_NAME = "X-API-Key"


def _load_api_key_from_config() -> str | None:
    if not AUTH_CONFIG_PATH.exists():
        return None
    payload = read_json(AUTH_CONFIG_PATH, {})
    if not isinstance(payload, dict):
        return None
    key = payload.get("apiKey")
    if isinstance(key, str):
        stripped = key.strip()
        return stripped if stripped else None
    return None


def _load_api_key_from_env() -> str | None:
    key = os.environ.get(ENV_VAR_NAME)
    if isinstance(key, str):
        stripped = key.strip()
        return stripped if stripped else None
    return None


def get_configured_api_key() -> str | None:
    env_key = _load_api_key_from_env()
    if env_key is not None:
        return env_key
    return _load_api_key_from_config()


def is_auth_enabled() -> bool:
    return get_configured_api_key() is not None


def validate_api_key(key: str) -> bool:
    if not is_auth_enabled():
        return True
    configured = get_configured_api_key()
    if configured is None:
        return True
    return key.strip() == configured


def get_auth_error_response() -> dict[str, Any]:
    return {
        "error": "Unauthorized",
        "message": f"Valid {HEADER_NAME} header is required.",
        "status": 401,
    }
