"""Хелперы для тестов пакета `ng_parser` — построение тестовых объектов."""

from ng_parser import Command, ParseResult, Repository


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


def make_test_client(transport):
    """Тестовый HttpxClient с минимальными обязательными параметрами."""
    from ng_parser.client import HttpxClient

    return HttpxClient(
        headers={},
        timeout=5.0,
        http2=False,
        follow_redirects=False,
        transport=transport,
    )


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


def make_async_coroutine_parser(client, *, workers=1, repository=None):
    """AsyncCoroutineParser с дефолтным ListRepository, если тесту не нужен реальный репозиторий."""
    from ng_parser.algorithm import AsyncCoroutineParser

    return AsyncCoroutineParser(
        max_workers=workers,
        client=client,
        repository=repository or ListRepository(),
    )
