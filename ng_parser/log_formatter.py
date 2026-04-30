"""LogFormatter и get_logger — единая точка настройки логирования.

LogFormatter красит WARNING/ERROR/CRITICAL красным, если stderr — TTY:
в файл/Docker-stdout/CI пишутся чистые строки без ANSI-эскейпов, в
интерактивном терминале — выделенные цветом важные сообщения.
"""

from __future__ import annotations

import logging
import sys


class LogFormatter(logging.Formatter):
    """Formatter с TTY-aware подсветкой WARNING+ уровней красным."""

    _RED = "\033[31m"
    _RESET = "\033[0m"
    _COLORED_LEVELS = frozenset({logging.WARNING, logging.ERROR, logging.CRITICAL})

    def __init__(self, fmt: str | None = None, datefmt: str | None = None):
        super().__init__(fmt, datefmt)
        self._is_tty = sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if self._is_tty and record.levelno in self._COLORED_LEVELS:
            return f"{self._RED}{text}{self._RESET}"
        return text


def get_logger(name: str, *, verbose: bool = False) -> logging.Logger:
    """Настраивает глобальный logging (LogFormatter + StreamHandler) и возвращает именованный логгер.

    Идемпотентен: повторные вызовы logging.basicConfig игнорируются stdlib-ом,
    если root-логгер уже сконфигурирован. Безопасно звать из main() с разными verbose.
    """
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(LogFormatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logging.basicConfig(level=level, handlers=[handler])
    return logging.getLogger(name)
