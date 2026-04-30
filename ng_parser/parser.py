"""Абстрактный `Parser` — интерфейс параллельного выполнения команд."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task_queue import Queue


class Parser(ABC):
    """
    Конкретная реализация задаёт стратегию конкаррентности.
    run() принимает очередь со стартовыми командами и обрабатывает её
    до исчерпания.
    """

    @abstractmethod
    async def run(self, queue: "Queue") -> None:
        """Обработать все команды в очереди.

        Очередь должна содержать как минимум одну команду на входе.
        После завершения может содержать sentinel-ы (None) от close() —
        переиспользование требует свежей очереди.

        Исключения из execute() логируются и не валят обход — раннер
        продолжает тянуть следующие задания. Если команде нужна
        спецреакция на конкретную ошибку, она реализует её сама.
        """
        ...

    async def __aenter__(self) -> "Parser":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass
