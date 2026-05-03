"""HttpxClient — реализация HttpClient поверх httpx.AsyncClient."""

from __future__ import annotations

import httpx

from .http_client import HttpClient, HttpResponse, HttpTransportError
from .http_proxy import HttpProxy


class HttpxClient(HttpClient):
    """HttpClient на httpx.AsyncClient. Прокси задаётся в конструкторе.

    Кеш клиентов под разные прокси и lifecycle — забота ProxyService.
    """

    def __init__(
        self,
        *,
        headers: dict | None = None,
        timeout: float = 20.0,
        http2: bool = True,
        follow_redirects: bool = True,
        proxy: HttpProxy | None = None,
    ):
        # httpx.AsyncClient(headers=None) бросает — подставляем пустой dict.
        self._client = self._build_client(
            headers=headers or {},
            timeout=timeout,
            http2=http2,
            follow_redirects=follow_redirects,
            proxy=proxy,
        )

    def _build_client(
        self,
        *,
        headers: dict,
        timeout: float,
        http2: bool,
        follow_redirects: bool,
        proxy: HttpProxy | None,
    ) -> httpx.AsyncClient:
        """Factory-метод httpx.AsyncClient. Точка расширения для наследников."""
        tr = _make_proxy_transport(proxy) if proxy is not None else None
        return httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            http2=http2,
            follow_redirects=follow_redirects,
            transport=tr,
        )

    async def get(self, url: str, *, headers: dict | None = None) -> HttpResponse:
        try:
            response = await self._client.get(url, headers=headers or {})
        except (httpx.TransportError, httpx.TimeoutException) as e:
            raise HttpTransportError(str(e)) from e

        return HttpResponse(
            status_code=response.status_code,
            text=response.text,
            url=str(response.url),
        )

    async def close(self) -> None:
        await self._client.aclose()


def _make_proxy_transport(proxy: HttpProxy) -> httpx.AsyncBaseTransport:
    """Транспорт под прокси: SOCKS — через httpx-socks, HTTP(S) — нативный httpx."""
    if proxy.is_socks:
        try:
            from httpx_socks import AsyncProxyTransport
        except ImportError as e:
            raise RuntimeError(
                f"для SOCKS-прокси нужен httpx-socks: pip install ng_parser[socks] "
                f"(прокси: {proxy.url})"
            ) from e
        return AsyncProxyTransport.from_url(proxy.url)
    return httpx.AsyncHTTPTransport(proxy=proxy.url)
