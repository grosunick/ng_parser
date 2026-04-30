"""Абстрактный класс `Command` — единица задания для `Parser`."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterable, NamedTuple

# Локальная ссылка на asyncio.sleep — чтобы тесты могли занулить именно
# retry-backoff в Command, не задевая asyncio.sleep в других местах
# (например, в handler-ах MockTransport).
_retry_sleep = asyncio.sleep

if TYPE_CHECKING:
    from ng_parser.client import HttpClient


log = logging.getLogger(__name__)


class ParseResult(NamedTuple):
    """
    Результат разбора страницы:
    - rows: строки для записи в Repository (раннер сам зальёт)
    - children: дочерние команды для постановки в очередь (раннер сам положит)

    Запись/постановка происходят атомарно после успешного parse() — если parse
    или fetch упал и retry-цикл вызвал parse повторно, частичных записей нет.
    """

    rows: Iterable[dict] = ()
    children: Iterable["Command"] = ()


class Command(ABC):
    """
    Абстрактная команда парсинга одного URL.

    Наследник реализует parse(html) и возвращает ParseResult — раннер
    сам обрабатывает rows (пишет в Repository) и children (кладёт в очередь).
    Сама Command не знает ни про Queue, ни про Repository.

    Retry: execute() оборачивает fetch+parse в цикл с exponential backoff.
    Параметры берутся из class attributes — конкретный пакет (например, commands/)
    переопределяет их на этапе импорта значениями из конфига.
    """

    # Дефолты — без retry. Переопределяются на уровне пакета (commands/__init__.py).
    RETRY_ATTEMPTS: int = 1
    RETRY_INITIAL_DELAY_SEC: float = 0.0
    # Исключения, которые НЕ ретраятся (например, AntiBotBlocked: смена IP/браузера —
    # внешняя задача, retry бесполезен). Список наполняется наследниками-пакетами.
    _NON_RETRIABLE_EXCEPTIONS: tuple = ()

    def __init__(self, url: str):
        self.url = url

    async def execute(self, client: HttpClient) -> ParseResult:
        """
        Выполняет fetch+parse с retry на любые исключения, кроме
        _NON_RETRIABLE_EXCEPTIONS. Между попытками — exponential backoff.
        После исчерпания попыток пробрасывает последнее исключение.
        """
        attempts = max(1, self.RETRY_ATTEMPTS)
        delay = self.RETRY_INITIAL_DELAY_SEC

        last_exc: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                html = await self.fetch(client)
                result = await self.parse(html)
                return result if result is not None else ParseResult()
            except self._NON_RETRIABLE_EXCEPTIONS:
                # Эти ошибки бессмысленно повторять — отдаём наверх как есть.
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
                    # Exponential backoff: следующая задержка вдвое больше.
                    delay = delay * 2 if delay > 0 else 0.0
                else:
                    log.error(
                        "парсинг %s не удался после %d попыток: %s",
                        self.url,
                        attempts,
                        e,
                    )

        # Все попытки исчерпаны — пробрасываем последнее исключение.
        assert last_exc is not None
        raise last_exc

    async def fetch(self, client: HttpClient) -> str:
        """GET по self.url. Наследник может переопределить (Referer, POST, ...)."""
        response = await client.get(self.url)
        response.raise_for_status()
        return response.text

    @abstractmethod
    async def parse(self, html: str) -> ParseResult:
        """Обрабатывает HTML; возвращает (rows, children) — обработка на раннере."""
        ...
