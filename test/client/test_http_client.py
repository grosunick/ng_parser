"""Тесты для ng_parser.client.http_client: абстракции HttpClient/HttpResponse и иерархия ошибок."""

import asyncio

import pytest

from ng_parser.client import (
    HttpClient,
    HttpClientError,
    HttpResponse,
    HttpStatusError,
    HttpTransportError,
)


def test_http_client_is_abstract():
    with pytest.raises(TypeError, match="abstract"):
        HttpClient()  # type: ignore[abstract]


def test_http_client_subclass_must_implement_get_and_close():
    class IncompleteClient(HttpClient):
        pass

    with pytest.raises(TypeError, match="abstract"):
        IncompleteClient()  # type: ignore[abstract]


def test_http_client_minimal_subclass_works():
    class FakeClient(HttpClient):
        def get(self, url, *, headers=None):
            return HttpResponse(status_code=200, text="ok", url=url)

        def close(self):
            pass

    client = FakeClient()
    response = client.get("https://example.com/")
    assert response.status_code == 200

def test_http_client_context_manager_calls_close():
    closed = []

    class TrackingClient(HttpClient):
        async def get(self, url, *, headers=None):
            return HttpResponse(200, "", url)

        async def close(self):
            closed.append(True)

    async def _():
        async with TrackingClient():
            pass

    asyncio.run(_())
    assert closed == [True]


def test_http_response_is_frozen_dataclass():
    resp = HttpResponse(status_code=200, text="ok", url="https://x")
    with pytest.raises((AttributeError, Exception)):
        resp.status_code = 500  # type: ignore[misc]


@pytest.mark.parametrize("status", [200, 201, 204, 301, 302, 304, 399])
def test_raise_for_status_no_op_below_400(status):
    HttpResponse(status, "", "https://x").raise_for_status()


@pytest.mark.parametrize("status", [400, 403, 404, 429, 500, 502, 503, 599])
def test_raise_for_status_throws_for_4xx_5xx(status):
    resp = HttpResponse(status, "", "https://x")
    with pytest.raises(HttpStatusError) as exc_info:
        resp.raise_for_status()
    assert exc_info.value.status_code == status


def test_http_status_error_subclass_of_http_client_error():
    err = HttpStatusError("...", status_code=500)
    assert isinstance(err, HttpClientError)


def test_http_transport_error_subclass_of_http_client_error():
    assert issubclass(HttpTransportError, HttpClientError)
