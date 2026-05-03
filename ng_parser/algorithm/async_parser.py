"""AsyncParser — корутина-на-задачу с лимитом per-run."""

from __future__ import annotations

import asyncio
import logging

from ng_parser.client import HttpClient, ProxyService
from ng_parser.command import Command
from ng_parser.parser import Parser
from ng_parser.repository import Repository
from ng_parser.task_queue import Queue

log = logging.getLogger(__name__)


class AsyncParser(Parser):
    """На каждую команду — отдельная корутина; одновременно не более max_workers."""

    def __init__(
        self,
        max_workers: int,
        client: HttpClient,
        repository: Repository,
        proxy_service: ProxyService | None = None,
    ):
        if max_workers <= 0:
            raise ValueError(f"max_workers должен быть >= 1, получили {max_workers}")
        self._client = client
        self._repository = repository
        self._max_workers = max_workers
        self._proxy_service = proxy_service

    async def run(self, queue: Queue) -> None:
        if queue.empty():
            raise ValueError("run() ожидает непустую очередь")

        pending: set[asyncio.Task] = set()
        while not queue.empty() or pending:
            while not queue.empty() and len(pending) < self._max_workers:
                cmd = await queue.get()
                pending.add(asyncio.create_task(self._handle(cmd, queue)))
            _, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

    async def _handle(self, cmd: Command, queue: Queue) -> None:
        log.info("корутина начала задание: url=%s", cmd.url)
        try:
            result = await cmd.execute(self._client, self._proxy_service)
        except Exception as e:
            log.exception("команда %s упала: %s", cmd.url, e)
            return
        for row in result.rows:
            self._repository.add(row)
        for child in result.children:
            queue.put(child)
