"""Абстрактный класс `Repository` — слой доступа к данным."""

from abc import ABC, abstractmethod


class Repository(ABC):
    """
    Абстрактное хранилище распаршенных объявлений.
    """

    @abstractmethod
    def add(self, row: dict) -> None:
        ...
