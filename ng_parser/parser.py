"""Абстрактный Parser."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task_queue import Queue


class Parser(ABC):
    """Реализация задаёт стратегию конкаррентности."""

    @abstractmethod
    async def run(self, queue: "Queue") -> None:
        """Обработать все команды в очереди.

        Исключения из execute() логируются и не валят обход.
        """
        ...

    async def __aenter__(self) -> "Parser":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass
