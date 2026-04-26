from __future__ import annotations

import atexit
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .utils import DATA_DIR, now_iso, read_json, sha1_hex, write_json

CACHE_DIR = DATA_DIR / "cache" / "http"


class HttpRequestError(RuntimeError):
    pass


# Module-level pooled httpx clients for connection reuse.
# Initialized lazily on first request to avoid import-time side effects.
_http_clients: dict[str | None, Any] = {}


def _load_httpx() -> Any:
    try:
        import httpx
    except ImportError:
        raise HttpRequestError(
            "httpx is required for HTTP requests. Install it with: pip install httpx>=0.27.0"
        ) from None
    return httpx


def _build_http_client(proxy_url: str | None) -> Any:
    httpx = _load_httpx()

    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    client_kwargs: dict[str, Any] = {"limits": limits, "timeout": httpx.Timeout(45.0)}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
    return httpx.Client(**client_kwargs)


def _get_http_client(network_settings: dict[str, Any] | None = None) -> Any:
    proxy_url = _resolve_proxy_url(network_settings or {})
    client = _http_clients.get(proxy_url)
    if client is not None:
        return client

    client = _build_http_client(proxy_url)
    _http_clients[proxy_url] = client
    return client


def _close_http_clients() -> None:
    for client in list(_http_clients.values()):
        try:
            client.close()
        except Exception:
            pass
    _http_clients.clear()


def _resolve_proxy_url(network_settings: dict[str, Any]) -> str | None:
    if not network_settings.get("proxyEnabled") or not network_settings.get("proxyUrl"):
        return None
    return str(network_settings.get("proxyUrl") or "").strip() or None


def _should_bypass_proxy(hostname: str, network_settings: dict[str, Any]) -> bool:
    no_proxy = [item.lower() for item in network_settings.get("noProxy", [])]
    host = (hostname or "").lower()
    return any(host == item or host.endswith(f".{item}") for item in no_proxy)


def _cache_path(namespace: str, url: str) -> Path:
    return CACHE_DIR / namespace / f"{sha1_hex(url)}.json"


def _cache_payload(path: Path, payload: Any, ttl_seconds: int, max_stale_seconds: int) -> None:
    now_ms = int(time.time() * 1000)
    write_json(
        path,
        {
            "fetchedAt": now_iso(),
            "fetchedAtMs": now_ms,
            "expiresAtMs": now_ms + max(1, ttl_seconds) * 1000,
            "staleUntilMs": now_ms + max(ttl_seconds, max_stale_seconds) * 1000,
            "payload": payload,
        },
    )


def _cache_is_fresh(cache: dict[str, Any] | None) -> bool:
    if not cache:
        return False
    return int(cache.get("expiresAtMs") or 0) > int(time.time() * 1000)


def _cache_is_usable(cache: dict[str, Any] | None) -> bool:
    if not cache:
        return False
    return int(cache.get("staleUntilMs") or 0) > int(time.time() * 1000)


def request_text(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: Any = None,
    timeout_seconds: int = 45,
    network_settings: dict[str, Any] | None = None,
) -> str:
    import httpx
    ns = network_settings or {}
    parsed = urlparse(url)
    if _should_bypass_proxy(parsed.hostname or "", ns):
        ns = {**ns, "proxyEnabled": False}

    client = _get_http_client(ns)

    body: bytes | str | None
    if payload is None:
        body = None
    elif isinstance(payload, (bytes, bytearray)):
        body = bytes(payload)
    elif isinstance(payload, str):
        body = payload
    else:
        body = json.dumps(payload)

    merged_headers = {
        "accept": "application/json",
        "user-agent": "python-trading-agent/1.0",
    }
    if body is not None and "content-type" not in {key.lower() for key in (headers or {})}:
        merged_headers["content-type"] = "application/json"
    merged_headers.update(headers or {})

    try:
        response = client.request(
            method.upper(),
            url,
            content=body,
            headers=merged_headers,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        return response.text
    except httpx.TimeoutException as error:
        raise HttpRequestError(f"Request timed out for {url}: {error}") from error
    except httpx.RequestError as error:
        # Catch connection reset by peer, network failures, etc.
        raise HttpRequestError(f"Network error for {url}: {error}") from error
    except Exception as error:
        response_obj = getattr(error, "response", None)
        status_code = getattr(response_obj, "status_code", None) if response_obj is not None else None
        if status_code is not None:
            detail = getattr(response_obj, "text", "") or ""
            raise HttpRequestError(f"{status_code} {error}: {detail}") from error
        raise HttpRequestError(str(error)) from error


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: Any = None,
    timeout_seconds: int = 45,
    network_settings: dict[str, Any] | None = None,
) -> Any:
    text = request_text(
        method,
        url,
        headers=headers,
        payload=payload,
        timeout_seconds=timeout_seconds,
        network_settings=network_settings,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        snippet = text[:220].replace("\n", " ").strip()
        if len(text) > 220:
            snippet += "..."
        message = f"invalid JSON response from {url}: {error}"
        if snippet:
            message += f" | response starts with: {snippet}"
        raise HttpRequestError(message) from error


def cached_get_json(
    url: str,
    *,
    namespace: str = "generic",
    ttl_seconds: int = 60,
    max_stale_seconds: int = 3600,
    timeout_seconds: int = 45,
    headers: dict[str, str] | None = None,
    network_settings: dict[str, Any] | None = None,
) -> Any:
    path = _cache_path(namespace, url)
    cache = read_json(path, {})
    if _cache_is_fresh(cache):
        return cache.get("payload")
    try:
        payload = request_json(
            "GET",
            url,
            headers=headers,
            timeout_seconds=timeout_seconds,
            network_settings=network_settings,
        )
        _cache_payload(path, payload, ttl_seconds, max_stale_seconds)
        return payload
    except Exception:
        if _cache_is_usable(cache):
            return cache.get("payload")
        raise


atexit.register(_close_http_clients)
