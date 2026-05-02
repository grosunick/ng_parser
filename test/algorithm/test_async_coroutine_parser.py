"""Тесты для ng_parser.algorithm.AsyncCoroutineParser."""

import asyncio
import logging
import time
import threading

import httpx
import pytest

from utils import (
    ListRepository,
    UrlCommand,
    make_async_coroutine_parser,
    make_queue_with,
    make_test_client,
)
from ng_parser import Command, ParseResult
from ng_parser.algorithm import AsyncCoroutineParser


def _ok_transport(body: str = "<html>ok</html>") -> httpx.MockTransport:
    return httpx.MockTransport(lambda req: httpx.Response(200, text=body))


def _counting_transport(hold_seconds: float = 0.1):
    """Считает пиковое число одновременных запросов."""
    counter = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    def handler(req: httpx.Request) -> httpx.Response:
        with lock:
            counter["active"] += 1
            counter["max_active"] = max(counter["max_active"], counter["active"])
        time.sleep(hold_seconds)
        with lock:
            counter["active"] -= 1
        return httpx.Response(200, text=str(req.url))

    return httpx.MockTransport(handler), counter


# ── базовый run ──────────────────────────────────────────────────────────────

def test_run_uses_passed_url():
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return httpx.Response(200, text="ok")

    client = make_test_client(httpx.MockTransport(handler))

    async def _():
        parser = make_async_coroutine_parser(client)
        await parser.run(make_queue_with(UrlCommand("https://example.com/page1")))
        await parser.run(make_queue_with(UrlCommand("https://example.com/page2")))

    asyncio.run(_())
    asyncio.run(client.close())
    assert seen == ["https://example.com/page1", "https://example.com/page2"]


def test_run_rejects_empty_queue():
    client = make_test_client(_ok_transport())

    async def _():
        async with make_async_coroutine_parser(client) as parser:
            await parser.run(make_queue_with())

    with pytest.raises(ValueError, match="непустую"):
        asyncio.run(_())
    asyncio.run(client.close())


# ── ошибки ────────────────────────────────────────────────────────────────────

def test_run_swallows_http_error_and_continues(caplog):
    """HTTP-статус-ошибка ловится раннером, логируется и не валит обход."""
    client = make_test_client(
        httpx.MockTransport(lambda req: httpx.Response(500, text="oops"))
    )
    async def _():
        async with make_async_coroutine_parser(client, workers=2) as parser:
            await parser.run(make_queue_with(UrlCommand("https://example.com/")))

    with caplog.at_level(logging.ERROR, logger="ng_parser.algorithm.async_coroutine_parser"):
        asyncio.run(_())
    asyncio.run(client.close())

    assert any("упала" in rec.message for rec in caplog.records)


def test_run_swallows_transport_error_and_continues(caplog):
    """Сетевая ошибка ловится раннером, логируется и не валит обход."""
    def handler(req):
        raise httpx.ConnectError("обрыв")

    client = make_test_client(httpx.MockTransport(handler))

    async def _():
        async with make_async_coroutine_parser(client) as parser:
            await parser.run(make_queue_with(UrlCommand("https://example.com/")))

    with caplog.at_level(logging.ERROR, logger="ng_parser.algorithm.async_coroutine_parser"):
        asyncio.run(_())
    asyncio.run(client.close())

    assert any("упала" in rec.message for rec in caplog.records)


def test_failing_command_does_not_abort_siblings():
    """Команда с исключением не валит соседей — раннер сам глушит ошибки."""
    collected: list[str] = []

    class OkChild(Command):
        async def parse(self, html: str) -> ParseResult:
            collected.append("ok")
            return ParseResult()

    class BadChild(Command):
        async def fetch(self, client):
            raise RuntimeError("плохая страница")

        async def parse(self, html: str) -> ParseResult:
            return ParseResult()

    class Root(Command):
        async def parse(self, html: str) -> ParseResult:
            return ParseResult(children=[
                OkChild("https://example.com/ok"),
                BadChild("https://example.com/bad"),
            ])

    client = make_test_client(_ok_transport())

    async def _():
        async with make_async_coroutine_parser(client, workers=2) as parser:
            await parser.run(make_queue_with(Root("https://example.com/root")))

    asyncio.run(_())
    asyncio.run(client.close())
    assert "ok" in collected


# ── ограничение параллельности ────────────────────────────────────────────────

def test_max_workers_limit_is_enforced():
    """10 команд в одной очереди при max_workers=3 → одновременно не более 3.

    Лимит — per-run(): несколько параллельных run() на одном инстансе
    делят лимит независимо, поэтому проверяем в рамках одного run().
    """
    transport, counter = _counting_transport(hold_seconds=0.05)
    client = make_test_client(transport)

    async def _():
        parser = make_async_coroutine_parser(client, workers=3)
        urls = [UrlCommand(f"https://example.com/{i}") for i in range(10)]
        await parser.run(make_queue_with(*urls))

    asyncio.run(_())
    asyncio.run(client.close())
    assert counter["max_active"] <= 3


def test_max_workers_1_is_strictly_serial():
    transport, counter = _counting_transport(hold_seconds=0.03)
    client = make_test_client(transport)

    async def _():
        parser = make_async_coroutine_parser(client)
        for i in range(5):
            await parser.run(make_queue_with(UrlCommand(f"https://example.com/{i}")))

    asyncio.run(_())
    asyncio.run(client.close())
    assert counter["max_active"] == 1


# ── конструктор ───────────────────────────────────────────────────────────────

def test_zero_max_workers_raises():
    client = make_test_client(_ok_transport())
    repo = ListRepository()
    with pytest.raises(ValueError):
        AsyncCoroutineParser(max_workers=0, client=client, repository=repo)
    asyncio.run(client.close())


def test_negative_max_workers_raises():
    client = make_test_client(_ok_transport())
    repo = ListRepository()
    with pytest.raises(ValueError):
        AsyncCoroutineParser(max_workers=-1, client=client, repository=repo)
    asyncio.run(client.close())


def test_constructor_requires_client():
    with pytest.raises(TypeError, match="client"):
        AsyncCoroutineParser(max_workers=1, repository=ListRepository())  # type: ignore[call-arg]


def test_constructor_requires_repository():
    client = make_test_client(_ok_transport())
    with pytest.raises(TypeError, match="repository"):
        AsyncCoroutineParser(max_workers=1, client=client)  # type: ignore[call-arg]
    asyncio.run(client.close())


# ── context manager ───────────────────────────────────────────────────────────

def test_context_manager_works():
    client = make_test_client(_ok_transport())

    async def _():
        async with make_async_coroutine_parser(client) as parser:
            await parser.run(make_queue_with(UrlCommand("https://example.com/")))

    asyncio.run(_())
    asyncio.run(client.close())


# ── spawn из parse() (через ParseResult.children) ─────────────────────────────

def test_child_commands_complete_before_run_returns():
    """Дочерние команды, вернутые в ParseResult.children, завершаются до возврата run()."""
    collected: list[str] = []

    class Child(Command):
        async def parse(self, html: str) -> ParseResult:
            collected.append(self.url)
            return ParseResult()

    class Parent(Command):
        async def parse(self, html: str) -> ParseResult:
            return ParseResult(children=[Child("https://example.com/child")])

    client = make_test_client(_ok_transport())

    async def _():
        async with make_async_coroutine_parser(client, workers=2) as parser:
            await parser.run(make_queue_with(Parent("https://example.com/parent")))

    asyncio.run(_())
    asyncio.run(client.close())
    assert collected == ["https://example.com/child"]


def test_deep_spawn_chain_completes():
    """Глубина 3: parent → child → grandchild — всё завершается."""
    depth_log: list[str] = []

    class GrandChild(Command):
        async def parse(self, html: str) -> ParseResult:
            depth_log.append("grandchild")
            return ParseResult()

    class Child(Command):
        async def parse(self, html: str) -> ParseResult:
            depth_log.append("child")
            return ParseResult(children=[GrandChild("https://example.com/grandchild")])

    class Parent(Command):
        async def parse(self, html: str) -> ParseResult:
            depth_log.append("parent")
            return ParseResult(children=[Child("https://example.com/child")])

    client = make_test_client(_ok_transport())

    async def _():
        async with make_async_coroutine_parser(client, workers=2) as parser:
            await parser.run(make_queue_with(Parent("https://example.com/parent")))

    asyncio.run(_())
    asyncio.run(client.close())
    assert set(depth_log) == {"parent", "child", "grandchild"}


def test_end_to_end_batch_all_urls_fetched():
    """20 параллельных run() — каждый URL запрошен ровно один раз."""
    seen: list[str] = []
    lock = threading.Lock()

    def handler(req: httpx.Request) -> httpx.Response:
        with lock:
            seen.append(str(req.url))
        return httpx.Response(200, text="ok")

    client = make_test_client(httpx.MockTransport(handler))
    urls = [f"https://example.com/p{i}" for i in range(20)]

    async def _():
        parser = make_async_coroutine_parser(client, workers=5)
        await asyncio.gather(*[parser.run(make_queue_with(UrlCommand(url))) for url in urls])

    asyncio.run(_())
    asyncio.run(client.close())

    assert sorted(seen) == sorted(urls)
