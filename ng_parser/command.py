"""Абстрактный Command — единица задания для Parser."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterable, NamedTuple

# Локальная ссылка — чтобы тесты патчили retry-backoff, не задевая asyncio.sleep
# в других местах (например, в handler-ах MockTransport).
_retry_sleep = asyncio.sleep

if TYPE_CHECKING:
    from ng_parser.client import HttpClient


log = logging.getLogger(__name__)


class ParseResult(NamedTuple):
    """rows → Repository, children → Queue. Раннер делает запись/постановку атомарно после успешного parse()."""

    rows: Iterable[dict] = ()
    children: Iterable["Command"] = ()


class Command(ABC):
    """Команда парсинга одного URL. Наследник реализует parse(html)."""

    # Дефолты — без retry. Переопределяются на уровне пакета (commands/__init__.py).
    RETRY_ATTEMPTS: int = 1
    RETRY_INITIAL_DELAY_SEC: float = 0.0
    # Исключения, которые не имеет смысла ретраить (нужно внешнее вмешательство).
    _NON_RETRIABLE_EXCEPTIONS: tuple = ()

    def __init__(self, url: str):
        self.url = url

    async def execute(self, client: HttpClient) -> ParseResult:
        """fetch+parse с exponential backoff, кроме _NON_RETRIABLE_EXCEPTIONS."""
        attempts = max(1, self.RETRY_ATTEMPTS)
        delay = self.RETRY_INITIAL_DELAY_SEC

        last_exc: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                html = await self.fetch(client)
                result = await self.parse(html)
                return result if result is not None else ParseResult()
            except self._NON_RETRIABLE_EXCEPTIONS:
                raise
            except Exception as e:
                last_exc = e
                if attempt < attempts:
                    log.warning(
                        "ошибка парсинга %s (попытка %d/%d): %s — повтор через %.1fs",
                        self.url,
                        attempt,
                        attempts,
                        e,
                        delay,
                    )
                    if delay > 0:
                        await _retry_sleep(delay)
                    delay = delay * 2 if delay > 0 else 0.0
                else:
                    log.error(
                        "парсинг %s не удался после %d попыток: %s",
                        self.url,
                        attempts,
                        e,
                    )

        assert last_exc is not None
        raise last_exc

    async def fetch(self, client: HttpClient) -> str:
        """GET по self.url. Наследник может переопределить (Referer, POST, ...)."""
        response = await client.get(self.url)
        response.raise_for_status()
        return response.text

    @abstractmethod
    async def parse(self, html: str) -> ParseResult: ...
