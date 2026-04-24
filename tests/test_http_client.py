from __future__ import annotations

from typing import Any

from backend import http_client


class DummyClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.closed = False

    def close(self) -> None:
        self.closed = True


class DummyHttpx:
    def __init__(self) -> None:
        self.created_clients: list[DummyClient] = []

    @staticmethod
    def Limits(*, max_connections: int, max_keepalive_connections: int) -> dict[str, int]:
        return {
            "max_connections": max_connections,
            "max_keepalive_connections": max_keepalive_connections,
        }

    @staticmethod
    def Timeout(timeout: float) -> float:
        return timeout

    def Client(self, **kwargs: Any) -> DummyClient:
        client = DummyClient(**kwargs)
        self.created_clients.append(client)
        return client


class TestHttpClientPooling:
    def setup_method(self) -> None:
        http_client._close_http_clients()

    def teardown_method(self) -> None:
        http_client._close_http_clients()

    def test_reuses_client_for_same_effective_proxy_settings(self, monkeypatch) -> None:
        fake_httpx = DummyHttpx()
        monkeypatch.setattr(http_client, "_load_httpx", lambda: fake_httpx)

        client1 = http_client._get_http_client({"proxyEnabled": False})
        client2 = http_client._get_http_client({})

        assert client1 is client2
        assert len(fake_httpx.created_clients) == 1
        assert client1.kwargs["limits"] == {
            "max_connections": 100,
            "max_keepalive_connections": 20,
        }

    def test_creates_distinct_clients_per_proxy_configuration(self, monkeypatch) -> None:
        fake_httpx = DummyHttpx()
        monkeypatch.setattr(http_client, "_load_httpx", lambda: fake_httpx)

        direct_client = http_client._get_http_client({"proxyEnabled": False})
        proxy_client = http_client._get_http_client(
            {"proxyEnabled": True, "proxyUrl": "http://127.0.0.1:8080"}
        )
        same_proxy_client = http_client._get_http_client(
            {"proxyEnabled": True, "proxyUrl": "http://127.0.0.1:8080"}
        )

        assert direct_client is not proxy_client
        assert proxy_client is same_proxy_client
        assert len(fake_httpx.created_clients) == 2
        assert proxy_client.kwargs["proxy"] == "http://127.0.0.1:8080"

    def test_request_text_uses_direct_client_for_no_proxy_hosts(self, monkeypatch) -> None:
        called_with: list[dict[str, Any]] = []

        class RequestClient(DummyClient):
            def request(self, *args: Any, **kwargs: Any) -> Any:
                return type(
                    "Response",
                    (),
                    {
                        "text": "ok",
                        "raise_for_status": staticmethod(lambda: None),
                    },
                )()

        def fake_get_http_client(network_settings: dict[str, Any] | None = None) -> RequestClient:
            called_with.append(network_settings or {})
            return RequestClient()

        monkeypatch.setattr(http_client, "_get_http_client", fake_get_http_client)

        result = http_client.request_text(
            "GET",
            "https://api.binance.com/api/v3/time",
            network_settings={
                "proxyEnabled": True,
                "proxyUrl": "http://127.0.0.1:8080",
                "noProxy": ["binance.com"],
            },
        )

        assert result == "ok"
        assert called_with == [
            {
                "proxyEnabled": False,
                "proxyUrl": "http://127.0.0.1:8080",
                "noProxy": ["binance.com"],
            }
        ]

    def test_close_http_clients_closes_all_cached_clients(self, monkeypatch) -> None:
        fake_httpx = DummyHttpx()
        monkeypatch.setattr(http_client, "_load_httpx", lambda: fake_httpx)

        direct_client = http_client._get_http_client({"proxyEnabled": False})
        proxy_client = http_client._get_http_client(
            {"proxyEnabled": True, "proxyUrl": "http://127.0.0.1:8080"}
        )

        http_client._close_http_clients()

        assert direct_client.closed is True
        assert proxy_client.closed is True
        assert http_client._http_clients == {}
