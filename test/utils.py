"""Хелперы для тестов пакета `ng_parser` — построение тестовых объектов."""

import httpx

from ng_parser import Command, ParseResult, Repository
from ng_parser.client import HttpxClient
from ng_parser.proxy import Proxy


class UrlCommand(Command):
    """Тривиальная команда для тестов: скачать URL, parse() — no-op."""

    async def parse(self, html: str) -> ParseResult:
        return ParseResult()


class ListRepository(Repository):
    """In-memory репозиторий для тестов: накапливает строки в .rows."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, row: dict) -> None:
        self.rows.append(row)


class _MockTransportHttpxClient(HttpxClient):
    """HttpxClient с подменённым httpx.AsyncBaseTransport — для MockTransport-тестов.
    Только для тестов: подменяет _build_client(), чтобы не ходить в сеть."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport,
        headers: dict | None = None,
        timeout: float = 5.0,
        http2: bool = False,
        follow_redirects: bool = False,
    ):
        self._mock_transport = transport
        super().__init__(
            headers=headers,
            timeout=timeout,
            http2=http2,
            follow_redirects=follow_redirects,
        )

    def _build_client(
        self,
        *,
        headers: dict,
        timeout: float,
        http2: bool,
        follow_redirects: bool,
        proxy: Proxy | None,
    ) -> httpx.AsyncClient:
        # transport переопределяет proxy — MockTransport ловит всё.
        return httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            http2=http2,
            follow_redirects=follow_redirects,
            transport=self._mock_transport,
        )


def make_test_client(transport):
    """Тестовый HttpxClient с MockTransport."""
    return _MockTransportHttpxClient(transport=transport)


def make_queue_with(*commands):
    """Свежая AsyncQueue с уже положенными в неё командами."""
    from ng_parser.queue import AsyncQueue

    queue = AsyncQueue()
    for cmd in commands:
        queue.put(cmd)
    return queue


def make_async_parser(client, *, workers=1, repository=None):
    """AsyncParser с дефолтным ListRepository, если тесту не нужен реальный репозиторий."""
    from ng_parser.algorithm import AsyncParser

    return AsyncParser(
        max_workers=workers,
        client=client,
        repository=repository or ListRepository(),
    )
