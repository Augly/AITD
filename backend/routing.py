from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from typing import Any, Callable


HandlerFunc = Callable[[BaseHTTPRequestHandler], Any]


class RouteRegistry:
    """Registry for HTTP route handlers keyed by (method, path)."""

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], HandlerFunc] = {}

    def register(self, method: str, path: str, handler: HandlerFunc) -> None:
        """Register a handler for the given HTTP method and path."""
        key = (method.upper(), path)
        self._routes[key] = handler

    def lookup(self, method: str, path: str) -> HandlerFunc | None:
        """Return the registered handler for (method, path), or None."""
        key = (method.upper(), path)
        return self._routes.get(key)

    def __contains__(self, key: tuple[str, str]) -> bool:
        """Allow ``(method, path) in registry`` checks."""
        return (key[0].upper(), key[1]) in self._routes

    def __len__(self) -> int:
        """Return the number of registered routes."""
        return len(self._routes)


# Global registry instance used by the @route decorator.
_default_registry: RouteRegistry | None = None


def get_default_registry() -> RouteRegistry:
    """Return the global default registry, creating it if necessary."""
    global _default_registry
    if _default_registry is None:
        _default_registry = RouteRegistry()
    return _default_registry


def route(method: str, path: str) -> Callable[[HandlerFunc], HandlerFunc]:
    """Decorator that registers a function as a handler for *method* + *path*.

    Usage::

        @route("GET", "/api/latest")
        def handle_api_latest(handler: BaseHTTPRequestHandler) -> None:
            ...
    """
    registry = get_default_registry()

    def decorator(func: HandlerFunc) -> HandlerFunc:
        registry.register(method, path, func)
        return func

    return decorator
