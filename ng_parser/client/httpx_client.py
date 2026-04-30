"""HttpxClient — реализация HttpClient поверх httpx.AsyncClient."""

from __future__ import annotations

import httpx

from .http_client import HttpClient, HttpResponse, HttpTransportError


class HttpxClient(HttpClient):
    def __init__(
        self,
        *,
        headers: dict | None = None,
        timeout: float = 20.0,
        http2: bool = True,
        follow_redirects: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        # httpx.AsyncClient(headers=None) бросает — подставляем пустой dict.
        self._client = httpx.AsyncClient(
            headers=headers or {},
            timeout=timeout,
            http2=http2,
            follow_redirects=follow_redirects,
            transport=transport,
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
