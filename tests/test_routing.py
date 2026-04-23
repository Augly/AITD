from __future__ import annotations

import pytest
from http.server import BaseHTTPRequestHandler
from unittest.mock import MagicMock

from backend.routing import RouteRegistry, route, get_default_registry


class TestRouteRegistry:
    def test_register_and_lookup(self) -> None:
        registry = RouteRegistry()

        def handler(handler: BaseHTTPRequestHandler) -> str:
            return "ok"

        registry.register("GET", "/api/latest", handler)
        assert registry.lookup("GET", "/api/latest") is handler

    def test_lookup_unregistered_returns_none(self) -> None:
        registry = RouteRegistry()
        assert registry.lookup("GET", "/api/not-found") is None

    def test_lookup_case_insensitive_method(self) -> None:
        registry = RouteRegistry()

        def handler(handler: BaseHTTPRequestHandler) -> str:
            return "ok"

        registry.register("POST", "/api/settings", handler)
        assert registry.lookup("post", "/api/settings") is handler
        assert registry.lookup("POST", "/api/settings") is handler

    def test_contains(self) -> None:
        registry = RouteRegistry()

        def handler(handler: BaseHTTPRequestHandler) -> str:
            return "ok"

        registry.register("GET", "/api/latest", handler)
        assert ("GET", "/api/latest") in registry
        assert ("get", "/api/latest") in registry
        assert ("GET", "/api/other") not in registry

    def test_len(self) -> None:
        registry = RouteRegistry()
        assert len(registry) == 0

        def handler_a(handler: BaseHTTPRequestHandler) -> str:
            return "a"

        def handler_b(handler: BaseHTTPRequestHandler) -> str:
            return "b"

        registry.register("GET", "/a", handler_a)
        registry.register("POST", "/b", handler_b)
        assert len(registry) == 2

    def test_overwrite_existing_route(self) -> None:
        registry = RouteRegistry()

        def handler_a(handler: BaseHTTPRequestHandler) -> str:
            return "a"

        def handler_b(handler: BaseHTTPRequestHandler) -> str:
            return "b"

        registry.register("GET", "/api/latest", handler_a)
        registry.register("GET", "/api/latest", handler_b)
        assert registry.lookup("GET", "/api/latest") is handler_b

    def test_handler_invocation(self) -> None:
        registry = RouteRegistry()
        mock_handler = MagicMock(spec=BaseHTTPRequestHandler)

        def handle_latest(h: BaseHTTPRequestHandler) -> dict[str, str]:
            return {"status": "ok"}

        registry.register("GET", "/api/latest", handle_latest)
        fn = registry.lookup("GET", "/api/latest")
        assert fn is not None
        result = fn(mock_handler)
        assert result == {"status": "ok"}


class TestRouteDecorator:
    def test_route_decorator_registers(self) -> None:
        registry = RouteRegistry()

        @route("GET", "/api/test")
        def handle_test(handler: BaseHTTPRequestHandler) -> str:
            return "test"

        default_registry = get_default_registry()
        assert default_registry.lookup("GET", "/api/test") is handle_test

    def test_route_decorator_preserves_function(self) -> None:
        @route("POST", "/api/settings")
        def handle_settings(handler: BaseHTTPRequestHandler) -> str:
            return "settings"

        assert handle_settings.__name__ == "handle_settings"

    def test_multiple_routes(self) -> None:
        @route("GET", "/api/a")
        def handle_a(handler: BaseHTTPRequestHandler) -> str:
            return "a"

        @route("POST", "/api/b")
        def handle_b(handler: BaseHTTPRequestHandler) -> str:
            return "b"

        registry = get_default_registry()
        assert registry.lookup("GET", "/api/a") is handle_a
        assert registry.lookup("POST", "/api/b") is handle_b
        assert len(registry) >= 2
