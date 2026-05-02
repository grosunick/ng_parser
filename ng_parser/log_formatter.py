"""LogFormatter и get_logger — настройка логирования с TTY-aware подсветкой."""

from __future__ import annotations

import logging
import sys


class LogFormatter(logging.Formatter):
    """Красит WARNING/ERROR/CRITICAL красным, если stderr — TTY."""

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
    """Идемпотентен: stdlib игнорирует повторный basicConfig, если root уже сконфигурирован."""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(LogFormatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logging.basicConfig(level=level, handlers=[handler])
    return logging.getLogger(name)
