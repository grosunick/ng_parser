"""AsyncQueue — реализация Queue поверх asyncio.Queue."""

from __future__ import annotations

import asyncio

from ng_parser.command import Command
from ng_parser.task_queue import Queue


class AsyncQueue(Queue):
    """FIFO-очередь поверх asyncio.Queue с sentinel-завершением.

    Очередь не bounded (maxsize=0) — put_nowait никогда не бросает.
    Завершение работы — через close(n), который кладёт N None-ов; воркер,
    получивший None, должен выйти из своего цикла.
    """

    def __init__(self) -> None:
        self._q: asyncio.Queue[Command | None] = asyncio.Queue()

    def put(self, command: Command) -> None:
        self._q.put_nowait(command)

    async def get(self) -> Command | None:
        return await self._q.get()

    def empty(self) -> bool:
        return self._q.empty()

    def close(self, n_sentinels: int) -> None:
        for _ in range(n_sentinels):
            self._q.put_nowait(None)
