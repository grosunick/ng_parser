"""AsyncCoroutineParser — корутина-на-задачу с лимитом через Semaphore."""

from __future__ import annotations

import asyncio
import logging

from ng_parser.client import HttpClient
from ng_parser.command import Command
from ng_parser.parser import Parser
from ng_parser.repository import Repository
from ng_parser.task_queue import Queue

log = logging.getLogger(__name__)


class AsyncCoroutineParser(Parser):
    """
    На каждую команду — отдельная корутина (`asyncio.create_task`).
    Конкурентность ограничена `asyncio.Semaphore(max_workers)`: семафор
    держится на время `cmd.execute()`, спавн дочерних — без удержания.

    Без sentinel-механики, без TaskGroup. Главный цикл вычерпывает
    очередь, дожидается завершения хотя бы одной корутины и проверяет
    очередь снова — туда могли попасть дочерние команды от завершившихся
    корутин.
    """

    def __init__(self, max_workers: int, client: HttpClient, repository: Repository):
        if max_workers <= 0:
            raise ValueError(f"max_workers должен быть >= 1, получили {max_workers}")
        self._client = client
        self._repository = repository
        self._semaphore = asyncio.Semaphore(max_workers)

    async def run(self, queue: Queue) -> None:
        if queue.empty():
            raise ValueError("run() ожидает непустую очередь")

        pending: set[asyncio.Task] = set()
        while not queue.empty() or pending:
            while not queue.empty():
                cmd = await queue.get()
                pending.add(asyncio.create_task(self._handle(cmd, queue)))
            _, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

    async def _handle(self, cmd: Command, queue: Queue) -> None:
        async with self._semaphore:
            log.info("корутина начала задание: url=%s", cmd.url)
            try:
                result = await cmd.execute(self._client)
            except Exception as e:
                log.exception("команда %s упала: %s", cmd.url, e)
                return
        for row in result.rows:
            self._repository.add(row)
        for child in result.children:
            queue.put(child)