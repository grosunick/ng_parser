"""AsyncQueue — реализация Queue поверх asyncio.Queue."""

from __future__ import annotations

import asyncio

from ng_parser.command import Command
from ng_parser.task_queue import Queue


class AsyncQueue(Queue):
    """Unbounded FIFO поверх asyncio.Queue."""

    def __init__(self) -> None:
        self._q: asyncio.Queue[Command] = asyncio.Queue()

    def put(self, command: Command) -> None:
        self._q.put_nowait(command)

    async def get(self) -> Command:
        return await self._q.get()

    def empty(self) -> bool:
        return self._q.empty()
