"""Абстрактная FIFO-очередь заданий парсинга."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .command import Command


class Queue(ABC):
    """Очередь заданий: put синхронный, get асинхронный."""

    @abstractmethod
    def put(self, command: "Command") -> None: ...

    @abstractmethod
    async def get(self) -> "Command": ...

    @abstractmethod
    def empty(self) -> bool: ...
