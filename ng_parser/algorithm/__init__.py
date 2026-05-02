"""Имплементации абстрактного `Parser`."""

from .async_coroutine_parser import AsyncCoroutineParser
from .async_parser import AsyncParser

__all__ = ["AsyncCoroutineParser", "AsyncParser"]
