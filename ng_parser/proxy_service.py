"""Источник HTTP-клиентов с прокси."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .client import HttpClient


class ProxyService(ABC):
    """Источник HTTP-клиентов, привязанных к прокси.

    Владеет lifecycle клиентов (создание, кеш, закрытие). Логика ротации/cooldown/blacklist —
    на усмотрение реализации. Команды получают только готовый HttpClient и про Proxy не знают.
    """

    @abstractmethod
    async def acquire(self) -> HttpClient:
        """Клиент для следующей попытки (может быть direct, без прокси)."""
        ...

    @abstractmethod
    async def report_bad(self, client: HttpClient, reason: Exception) -> None:
        """Сигнал, что запросы через этот клиент провалились. Реализация сама знает,
        какой Proxy с ним связан, и решает — пометить, выкинуть, поставить в cooldown."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Закрыть все созданные клиенты."""
        ...
