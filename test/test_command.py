"""Тесты для ng_parser.command: Command, ParseResult и UrlCommand."""

import asyncio
import logging

import httpx
import pytest

from ng_parser import Command, ParseResult
from utils import (
    ListRepository,
    UrlCommand,
    make_async_parser,
    make_queue_with,
    make_test_client,
)


def _make_ok_transport(text: str = "<html>ok</html>") -> httpx.MockTransport:
    return httpx.MockTransport(lambda req: httpx.Response(200, text=text))


def test_command_is_abstract():
    with pytest.raises(TypeError, match="abstract"):
        Command("https://example.com/")  # type: ignore[abstract]


def test_command_subclass_without_parse_is_still_abstract():
    class Incomplete(Command):
        pass

    with pytest.raises(TypeError, match="abstract"):
        Incomplete("https://example.com/")  # type: ignore[abstract]


def test_command_subclass_with_parse_can_be_instantiated():
    class OK(Command):
        async def parse(self, html: str) -> ParseResult:
            return ParseResult()

    cmd = OK("https://example.com/")
    assert cmd.url == "https://example.com/"


def test_url_command_is_concrete():
    cmd = UrlCommand("https://example.com/")
    assert cmd.url == "https://example.com/"


def test_url_command_parse_returns_empty_result():
    cmd = UrlCommand("https://example.com/")
    result = asyncio.run(cmd.parse("<html>hello</html>"))
    assert list(result.rows) == []
    assert list(result.children) == []


def test_async_parser_rejects_empty_queue():
    client = make_test_client(_make_ok_transport())

    async def _():
        async with make_async_parser(client, workers=2) as parser:
            await parser.run(make_queue_with())

    with pytest.raises(ValueError, match="непустую"):
        asyncio.run(_())
    asyncio.run(client.close())


def test_command_parse_is_called_with_html():
    class Captor(Command):
        received_html: str | None = None

        async def parse(self, html: str) -> ParseResult:
            self.received_html = html
            return ParseResult()

    client = make_test_client(_make_ok_transport("<html>payload</html>"))
    cmd = Captor("https://example.com/")

    async def _():
        async with make_async_parser(client) as parser:
            await parser.run(make_queue_with(cmd))

    asyncio.run(_())
    assert cmd.received_html == "<html>payload</html>"
    asyncio.run(client.close())


def test_parse_can_return_children_for_runner_to_enqueue():
    """parse() возвращает ParseResult(children=...) — раннер кладёт детей в очередь."""
    visited: list[str] = []

    class LeafCmd(Command):
        async def parse(self, html: str) -> ParseResult:
            visited.append(self.url)
            return ParseResult()

    class RootCmd(Command):
        async def parse(self, html: str) -> ParseResult:
            visited.append(self.url)
            return ParseResult(children=[
                LeafCmd(f"https://example.com/leaf/{i}") for i in range(3)
            ])

    def handler(request):
        return httpx.Response(200, text=f"body-{request.url.path}")

    client = make_test_client(httpx.MockTransport(handler))

    async def _():
        async with make_async_parser(client, workers=4) as parser:
            await parser.run(make_queue_with(RootCmd("https://example.com/root")))

    asyncio.run(_())
    asyncio.run(client.close())

    assert "https://example.com/root" in visited
    for i in range(3):
        assert f"https://example.com/leaf/{i}" in visited
    assert len(visited) == 4


def test_parse_can_return_rows_for_runner_to_persist():
    """parse() возвращает ParseResult(rows=...) — раннер пишет в repository."""

    class WithRows(Command):
        async def parse(self, html: str) -> ParseResult:
            return ParseResult(rows=[{"url": "a"}, {"url": "b"}])

    repo = ListRepository()
    client = make_test_client(_make_ok_transport())

    async def _():
        async with make_async_parser(client, repository=repo) as parser:
            await parser.run(make_queue_with(WithRows("https://example.com/")))

    asyncio.run(_())
    asyncio.run(client.close())

    assert [r["url"] for r in repo.rows] == ["a", "b"]


def test_command_parse_exception_is_swallowed_by_runner(caplog):
    """Исключение в parse() глушится раннером и не валит обход."""
    class Buggy(Command):
        async def parse(self, html: str) -> ParseResult:
            raise ValueError("ошибка в parse")

    client = make_test_client(_make_ok_transport())

    async def _():
        async with make_async_parser(client) as parser:
            await parser.run(make_queue_with(Buggy("https://example.com/")))

    with caplog.at_level(logging.ERROR, logger="ng_parser.algorithm.async_parser"):
        asyncio.run(_())
    asyncio.run(client.close())

    assert any("упала" in rec.message for rec in caplog.records)


def test_command_fetch_can_be_overridden():
    seen_headers: dict = {}

    def handler(request):
        seen_headers.update(request.headers)
        return httpx.Response(200, text="ok")

    class CustomFetch(Command):
        async def fetch(self, client):
            response = await client.get(self.url, headers={"X-Custom": "hello"})
            response.raise_for_status()
            return response.text

        async def parse(self, html: str) -> ParseResult:
            return ParseResult()

    client = make_test_client(httpx.MockTransport(handler))

    async def _():
        async with make_async_parser(client) as parser:
            await parser.run(make_queue_with(CustomFetch("https://example.com/")))

    asyncio.run(_())
    asyncio.run(client.close())
    assert seen_headers.get("x-custom") == "hello"


def test_parse_returning_none_is_treated_as_empty_result():
    """execute() толерантен к parse(), который возвращает None — удобно для тестовых subclass-ов."""

    class NoneParse(Command):
        async def parse(self, html: str):
            return None

    client = make_test_client(_make_ok_transport())
    cmd = NoneParse("https://example.com/")

    result = asyncio.run(cmd.execute(client))
    assert isinstance(result, ParseResult)
    assert list(result.rows) == []
    assert list(result.children) == []
    asyncio.run(client.close())


# ============================================================================
# Command.execute() retry
# ============================================================================


def test_execute_retries_until_success():
    """3 попытки: первые 2 падают, третья успешна."""
    attempts = {"n": 0}

    class Flaky(Command):
        RETRY_ATTEMPTS = 3
        RETRY_INITIAL_DELAY_SEC = 0.01

        async def fetch(self, client):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RuntimeError(f"fail #{attempts['n']}")
            return "ok-html"

        async def parse(self, html):
            return ParseResult()

    client = make_test_client(_make_ok_transport())
    cmd = Flaky("https://example.com/")

    async def _():
        async with make_async_parser(client) as parser:
            await parser.run(make_queue_with(cmd))

    asyncio.run(_())
    assert attempts["n"] == 3
    asyncio.run(client.close())


def test_execute_propagates_after_all_retries_exhausted():
    """Тест юнит-уровня: Command.execute() сам по себе пробрасывает исключение
    наверх после исчерпания попыток. Раннер уже отдельно решит, глушить его
    или нет — здесь нас это не волнует."""
    attempts = {"n": 0}

    class AlwaysFails(Command):
        RETRY_ATTEMPTS = 3
        RETRY_INITIAL_DELAY_SEC = 0.01

        async def fetch(self, client):
            attempts["n"] += 1
            raise RuntimeError(f"fail #{attempts['n']}")

        async def parse(self, html):
            return ParseResult()

    client = make_test_client(_make_ok_transport())
    cmd = AlwaysFails("https://example.com/")

    with pytest.raises(RuntimeError, match="fail #3"):
        asyncio.run(cmd.execute(client))
    assert attempts["n"] == 3
    asyncio.run(client.close())


def test_execute_uses_exponential_backoff(monkeypatch):
    """Задержки между попытками удваиваются: initial × 2^(attempt-1)."""
    sleeps: list[float] = []

    async def mock_sleep(s):
        sleeps.append(s)
        return None

    monkeypatch.setattr("ng_parser.command._retry_sleep", mock_sleep)

    class Flaky(Command):
        RETRY_ATTEMPTS = 4
        RETRY_INITIAL_DELAY_SEC = 1.0

        async def fetch(self, client):
            raise RuntimeError("nope")

        async def parse(self, html):
            return ParseResult()

    client = make_test_client(_make_ok_transport())
    cmd = Flaky("https://example.com/")

    with pytest.raises(RuntimeError):
        asyncio.run(cmd.execute(client))
    asyncio.run(client.close())

    # 4 попытки → 3 задержки: 1, 2, 4.
    assert sleeps == [1.0, 2.0, 4.0]


def test_execute_retries_on_parse_exception():
    """Ошибка в parse() тоже триггерит retry."""
    parse_calls = {"n": 0}

    class ParseFails(Command):
        RETRY_ATTEMPTS = 3
        RETRY_INITIAL_DELAY_SEC = 0.01

        async def parse(self, html):
            parse_calls["n"] += 1
            if parse_calls["n"] < 2:
                raise ValueError("bad html")
            return ParseResult()

    client = make_test_client(_make_ok_transport("<html>x</html>"))
    cmd = ParseFails("https://example.com/")

    async def _():
        async with make_async_parser(client) as parser:
            await parser.run(make_queue_with(cmd))

    asyncio.run(_())
    assert parse_calls["n"] == 2
    asyncio.run(client.close())


def test_execute_does_not_retry_on_non_retriable():
    """_NON_RETRIABLE_EXCEPTIONS пробрасывается сразу."""

    class StopError(Exception):
        pass

    attempts = {"n": 0}

    class NonRetriable(Command):
        RETRY_ATTEMPTS = 5
        RETRY_INITIAL_DELAY_SEC = 0.01
        _NON_RETRIABLE_EXCEPTIONS = (StopError,)

        async def fetch(self, client):
            attempts["n"] += 1
            raise StopError("bail")

        async def parse(self, html):
            return ParseResult()

    client = make_test_client(_make_ok_transport())
    cmd = NonRetriable("https://example.com/")

    with pytest.raises(StopError):
        asyncio.run(cmd.execute(client))
    assert attempts["n"] == 1
    asyncio.run(client.close())


def test_execute_no_retry_when_attempts_is_1(monkeypatch):
    """RETRY_ATTEMPTS=1 — без повторов и задержек."""
    attempts = {"n": 0}
    sleeps: list[float] = []

    async def mock_sleep(s):
        sleeps.append(s)
        return None

    monkeypatch.setattr("ng_parser.command._retry_sleep", mock_sleep)

    class OneShot(Command):
        RETRY_ATTEMPTS = 1
        RETRY_INITIAL_DELAY_SEC = 1.0

        async def fetch(self, client):
            attempts["n"] += 1
            raise RuntimeError("nope")

        async def parse(self, html):
            return ParseResult()

    client = make_test_client(_make_ok_transport())
    cmd = OneShot("https://example.com/")

    with pytest.raises(RuntimeError):
        asyncio.run(cmd.execute(client))
    asyncio.run(client.close())

    assert attempts["n"] == 1
    assert sleeps == []


# ============================================================================
# Command.execute() с ProxyService
# ============================================================================


class _FakeProxyService:
    """Мок ProxyService: при каждом acquire() отдаёт следующий клиент по списку,
    собирает все вызовы report_bad для проверок."""

    def __init__(self, clients):
        self._clients = list(clients)
        self._idx = 0
        self.acquire_calls = 0
        self.bad_reports: list[tuple[object, Exception]] = []
        self.closed = False

    async def acquire(self):
        client = self._clients[self._idx % len(self._clients)]
        self._idx += 1
        self.acquire_calls += 1
        return client

    async def report_bad(self, client, reason):
        self.bad_reports.append((client, reason))

    async def close(self):
        self.closed = True


def test_execute_uses_proxy_service_acquire_per_attempt():
    """proxy_service.acquire() вызывается перед каждой попыткой."""
    client = make_test_client(_make_ok_transport())
    svc = _FakeProxyService([client])

    class OK(Command):
        async def parse(self, html):
            return ParseResult()

    cmd = OK("https://example.com/")
    asyncio.run(cmd.execute(client, svc))
    asyncio.run(client.close())

    assert svc.acquire_calls == 1
    assert svc.bad_reports == []


def test_execute_calls_report_bad_on_retriable_failure():
    """retry-эксепшен → report_bad(client, e) вызван для соответствующего клиента."""
    c1 = make_test_client(_make_ok_transport())
    c2 = make_test_client(_make_ok_transport())
    svc = _FakeProxyService([c1, c2])

    class FailsTwiceThenOk(Command):
        RETRY_ATTEMPTS = 3
        RETRY_INITIAL_DELAY_SEC = 0.0
        n = 0

        async def fetch(self, client):
            FailsTwiceThenOk.n += 1
            if FailsTwiceThenOk.n < 3:
                raise RuntimeError("transport down")
            return "ok"

        async def parse(self, html):
            return ParseResult()

    cmd = FailsTwiceThenOk("https://example.com/")
    asyncio.run(cmd.execute(c1, svc))

    assert svc.acquire_calls == 3
    # 2 неудачи → 2 report_bad; третья попытка успешна → report_bad не вызывается.
    assert len(svc.bad_reports) == 2
    # acquire поочерёдно отдаёт c1, c2, c1 — первые два упали, третий успех.
    assert [reported_client for reported_client, _ in svc.bad_reports] == [c1, c2]
    assert all(isinstance(reason, RuntimeError) for _, reason in svc.bad_reports)

    asyncio.run(c1.close())
    asyncio.run(c2.close())


def test_execute_does_not_call_report_bad_on_non_retriable():
    """_NON_RETRIABLE_EXCEPTIONS пробрасывается без report_bad."""

    class StopError(Exception):
        pass

    client = make_test_client(_make_ok_transport())
    svc = _FakeProxyService([client])

    class NonRetriable(Command):
        RETRY_ATTEMPTS = 5
        _NON_RETRIABLE_EXCEPTIONS = (StopError,)

        async def fetch(self, client):
            raise StopError("bail")

        async def parse(self, html):
            return ParseResult()

    cmd = NonRetriable("https://example.com/")
    with pytest.raises(StopError):
        asyncio.run(cmd.execute(client, svc))

    assert svc.acquire_calls == 1
    assert svc.bad_reports == []
    asyncio.run(client.close())


def test_execute_without_proxy_service_uses_base_client():
    """proxy_service=None — клиент берётся напрямую (как раньше), acquire не дёргается."""
    seen: list[object] = []

    class Captor(Command):
        async def fetch(self, client):
            seen.append(client)
            return "ok"

        async def parse(self, html):
            return ParseResult()

    client = make_test_client(_make_ok_transport())
    cmd = Captor("https://example.com/")
    asyncio.run(cmd.execute(client))
    asyncio.run(client.close())

    assert seen == [client]


def test_async_parser_passes_proxy_service_to_execute():
    """AsyncParser прокидывает proxy_service в Command.execute()."""
    client = make_test_client(_make_ok_transport())
    svc = _FakeProxyService([client])

    class OK(Command):
        async def parse(self, html):
            return ParseResult()

    async def _():
        from ng_parser.algorithm import AsyncParser

        parser = AsyncParser(
            max_workers=1, client=client, repository=ListRepository(), proxy_service=svc
        )
        async with parser:
            await parser.run(make_queue_with(OK("https://example.com/")))

    asyncio.run(_())
    asyncio.run(client.close())

    assert svc.acquire_calls == 1
    assert svc.bad_reports == []
