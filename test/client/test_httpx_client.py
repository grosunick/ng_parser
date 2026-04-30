"""Тесты для ng_parser.client.httpx_client: реализация HttpxClient поверх httpx.AsyncClient."""

import asyncio

import httpx
import pytest

from utils import make_test_client
from ng_parser.client import (
    HttpResponse,
    HttpTransportError,
    HttpxClient,
)


def test_httpx_client_get_returns_http_response():
    """GET возвращает наш HttpResponse, а не httpx.Response."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text="hi"))
    async def _():
        async with make_test_client(transport) as client:
            resp = await client.get("https://example.com/")
            assert isinstance(resp, HttpResponse)
            assert resp.status_code == 200
            assert resp.text == "hi"
            assert resp.url == "https://example.com/"
    asyncio.run(_())


def test_httpx_client_get_passes_extra_headers():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, text="ok")

    async def _():
        async with make_test_client(httpx.MockTransport(handler)) as client:
            await client.get("https://example.com/", headers={"X-Custom": "value"})
    asyncio.run(_())
    assert seen.get("x-custom") == "value"


def test_httpx_client_session_headers_persist():
    seen: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.headers))
        return httpx.Response(200, text="ok")

    async def _():
        async with HttpxClient(
            headers={"X-Session": "session-token"},
            timeout=5.0,
            http2=False,
            follow_redirects=False,
            transport=httpx.MockTransport(handler),
        ) as client:
            await client.get("https://a/")
            await client.get("https://b/")
    asyncio.run(_())
    assert all(h.get("x-session") == "session-token" for h in seen)


def test_httpx_client_does_not_raise_on_4xx_5xx():
    transport = httpx.MockTransport(lambda req: httpx.Response(503, text="busy"))
    async def _():
        async with make_test_client(transport) as client:
            resp = await client.get("https://example.com/")
            assert resp.status_code == 503
    asyncio.run(_())


def test_httpx_client_get_wraps_connect_error():
    """httpx.ConnectError → HttpTransportError."""

    def handler(req):
        raise httpx.ConnectError("обрыв")

    async def _():
        async with make_test_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpTransportError):
                await client.get("https://example.com/")
    asyncio.run(_())


def test_httpx_client_get_wraps_timeout_exception():
    """httpx.TimeoutException → HttpTransportError."""

    def handler(req):
        raise httpx.ReadTimeout("медленный сервер")

    async def _():
        async with make_test_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpTransportError):
                await client.get("https://example.com/")
    asyncio.run(_())


def test_httpx_client_close_closes_underlying_session():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text="ok"))
    async def _():
        client = make_test_client(transport)
        await client.close()
        with pytest.raises(Exception):
            await client.get("https://example.com/")
    asyncio.run(_())
