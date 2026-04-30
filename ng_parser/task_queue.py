"""Абстрактная FIFO-очередь заданий парсинга.

put() — синхронный, очередь не bounded, вызовы из parse() не блокируются.
get() — асинхронный, блокирует до появления элемента или sentinel-а (None).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .command import Command


class Queue(ABC):
    """Очередь заданий с sentinel-завершением."""

    @abstractmethod
    def put(self, command: "Command") -> None:
        """Положить команду в конец очереди. Без ожидания."""
        ...

    @abstractmethod
    async def get(self) -> "Command | None":
        """Извлечь команду из начала очереди.

        Блокирует event loop до появления элемента. Возвращает None, если
        был положен sentinel завершения через close(n).
        """
        ...

    @abstractmethod
    def empty(self) -> bool:
        """True, если в очереди нет элементов."""
        ...

    @abstractmethod
    def close(self, n_sentinels: int) -> None:
        """Положить N sentinel-ов (None) — все ждущие воркеры проснутся и выйдут."""
        ...
