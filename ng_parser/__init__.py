"""ng_parser: базовые абстракции и готовые парсеры."""

from .client import HttpProxy, ProxyService
from .command import Command, ParseResult
from .log_formatter import LogFormatter, get_logger
from .parser import Parser
from .repository import Repository
from .task_queue import Queue

__all__ = [
    "Command",
    "HttpProxy",
    "LogFormatter",
    "ParseResult",
    "Parser",
    "ProxyService",
    "Queue",
    "Repository",
    "get_logger",
]
