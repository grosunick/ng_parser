"""Абстрактный Repository."""

from abc import ABC, abstractmethod


class Repository(ABC):
    @abstractmethod
    def add(self, row: dict) -> None: ...
