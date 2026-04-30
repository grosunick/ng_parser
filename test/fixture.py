"""Pytest-фикстуры для тестов пакета `ng_parser`."""

import pytest


@pytest.fixture(autouse=True)
def _no_command_sleep(monkeypatch):
    """
    Зануляет retry-backoff в Command — иначе тесты на ошибки растягиваются
    на секунды exponential backoff. Патчим только локальную ссылку
    Command._retry_sleep, не глобальный asyncio.sleep — иначе ломаем
    concurrency-тесты с `await asyncio.sleep(...)` в handler-ах MockTransport.
    """
    async def noop_sleep(_s):
        return None
    monkeypatch.setattr("ng_parser.command._retry_sleep", noop_sleep)