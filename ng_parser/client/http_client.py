"""Абстрактный HTTP-клиент."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class HttpClientError(Exception):
    pass


class HttpTransportError(HttpClientError):
    """Сетевая ошибка: таймаут, обрыв, DNS и т.п."""


class HttpStatusError(HttpClientError):
    """4xx/5xx HTTP-статус. Бросается из HttpResponse.raise_for_status()."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    text: str
    url: str

    def raise_for_status(self) -> None:
        if 400 <= self.status_code < 600:
            raise HttpStatusError(
                f"HTTP {self.status_code} on {self.url}",
                status_code=self.status_code,
            )


class HttpClient(ABC):
    """Сессионный HTTP-клиент: cookies/настройки живут между get() (нужно для warmup)."""

    @abstractmethod
    async def get(self, url: str, *, headers: dict | None = None) -> HttpResponse:
        """GET. На 4xx/5xx не бросает — вызывающий код решает сам."""
        ...

    @abstractmethod
    async def close(self) -> None: ...

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
