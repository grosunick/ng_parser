"""AsyncParser — пул воркеров вокруг очереди, переданной в run()."""

from __future__ import annotations

import asyncio
import logging

from ng_parser.client import HttpClient
from ng_parser.parser import Parser
from ng_parser.repository import Repository
from ng_parser.task_queue import Queue

log = logging.getLogger(__name__)


class AsyncParser(Parser):
    """
    Пул из max_workers воркеров вокруг переданной в run() очереди.

    Контракт команды: Command.execute() возвращает ParseResult(rows, children).
    Раннер — единственная точка, знающая про Repository и Queue: записывает
    rows в repository и кладёт children в очередь. Сама команда про эти
    концепции ничего не знает.

    AsyncParser не знает конкретную реализацию Queue (DIP). Любое исключение
    из cmd.execute() ловится воркером и логируется — обход очереди продолжается.
    Если команде нужна спецреакция на конкретную ошибку, она делает её сама
    (например, AutoRuCommand ловит AntiBotBlocked в собственном execute()).

    Завершение — через sentinel: queue.close(N) кладёт N None-ов; каждый
    воркер, получивший None, выходит. close(N) вызывает последний воркер,
    закончивший работу при пустой очереди.
    """

    def __init__(self, max_workers: int, client: HttpClient, repository: Repository):
        if max_workers <= 0:
            raise ValueError(f"max_workers должен быть >= 1, получили {max_workers}")
        self._client = client
        self._repository = repository
        self._max_workers = max_workers

    async def run(self, queue: Queue) -> None:
        if queue.empty():
            raise ValueError("run() ожидает непустую очередь")

        active = 0
        active_lock = asyncio.Lock()

        async def worker() -> None:
            nonlocal active
            while True:
                cmd = await queue.get()
                if cmd is None:
                    return

                async with active_lock:
                    active += 1

                log.info("воркер начал задание: url=%s", cmd.url)
                try:
                    result = await cmd.execute(self._client)
                    for row in result.rows:
                        self._repository.add(row)
                    for child in result.children:
                        queue.put(child)
                except Exception as e:
                    # Команды отвечают за свои ошибки сами; раннер только логирует
                    # и продолжает обход — одна упавшая команда не валит всю очередь.
                    log.exception("команда %s упала: %s", cmd.url, e)
                finally:
                    async with active_lock:
                        active -= 1
                        if active == 0 and queue.empty():
                            queue.close(self._max_workers)

        async with asyncio.TaskGroup() as tg:
            for _ in range(self._max_workers):
                tg.create_task(worker())
