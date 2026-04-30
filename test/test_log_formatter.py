"""Тесты для ng_parser.log_formatter: LogFormatter и get_logger."""

import io
import logging
import sys

import pytest

from ng_parser import LogFormatter, get_logger


# ── LogFormatter ─────────────────────────────────────────────────────────────


class _FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class _FakeNonTTY(io.StringIO):
    def isatty(self) -> bool:
        return False


def _make_record(level: int, msg: str = "msg") -> logging.LogRecord:
    return logging.LogRecord(
        name="x", level=level, pathname="p", lineno=1, msg=msg, args=(), exc_info=None
    )


def test_log_formatter_no_color_when_stderr_not_tty(monkeypatch):
    monkeypatch.setattr(sys, "stderr", _FakeNonTTY())
    fmt = LogFormatter("%(levelname)s %(message)s")

    out = fmt.format(_make_record(logging.ERROR))
    assert out == "ERROR msg"
    assert "\033" not in out


def test_log_formatter_colors_warning_when_stderr_is_tty(monkeypatch):
    monkeypatch.setattr(sys, "stderr", _FakeTTY())
    fmt = LogFormatter("%(levelname)s %(message)s")

    out = fmt.format(_make_record(logging.WARNING))
    assert out.startswith("\033[31m")
    assert out.endswith("\033[0m")
    assert "WARNING msg" in out


@pytest.mark.parametrize("level", [logging.WARNING, logging.ERROR, logging.CRITICAL])
def test_log_formatter_colors_warning_error_critical(monkeypatch, level):
    monkeypatch.setattr(sys, "stderr", _FakeTTY())
    fmt = LogFormatter("%(message)s")

    out = fmt.format(_make_record(level))
    assert out.startswith("\033[31m")
    assert out.endswith("\033[0m")


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_log_formatter_does_not_color_debug_info(monkeypatch, level):
    monkeypatch.setattr(sys, "stderr", _FakeTTY())
    fmt = LogFormatter("%(message)s")

    out = fmt.format(_make_record(level))
    assert "\033[31m" not in out


def test_log_formatter_uses_passed_format_string(monkeypatch):
    monkeypatch.setattr(sys, "stderr", _FakeNonTTY())
    fmt = LogFormatter("[%(name)s] %(message)s")

    record = _make_record(logging.INFO, "hello")
    record.name = "myapp"
    assert fmt.format(record) == "[myapp] hello"


# ── get_logger ───────────────────────────────────────────────────────────────


@pytest.fixture
def captured_basic_config(monkeypatch):
    """Перехватывает logging.basicConfig — pytest сам управляет root-логгером,
    поэтому проверять через root.level/handlers ненадёжно. Мокаем напрямую."""
    captured: dict = {}

    def fake_basic_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)
    return captured


def test_get_logger_returns_named_logger():
    log = get_logger("test.ng_parser.demo")
    assert isinstance(log, logging.Logger)
    assert log.name == "test.ng_parser.demo"


def test_get_logger_same_name_returns_singleton():
    a = get_logger("test.ng_parser.singleton")
    b = get_logger("test.ng_parser.singleton")
    assert a is b


def test_get_logger_verbose_true_configures_debug_level(captured_basic_config):
    get_logger("test.ng_parser.debug", verbose=True)
    assert captured_basic_config["level"] == logging.DEBUG


def test_get_logger_verbose_false_configures_info_level(captured_basic_config):
    get_logger("test.ng_parser.info", verbose=False)
    assert captured_basic_config["level"] == logging.INFO


def test_get_logger_default_verbose_is_false(captured_basic_config):
    get_logger("test.ng_parser.default")
    assert captured_basic_config["level"] == logging.INFO


def test_get_logger_attaches_log_formatter_to_handler(captured_basic_config):
    get_logger("test.ng_parser.fmt")
    handlers = captured_basic_config["handlers"]
    assert any(isinstance(h.formatter, LogFormatter) for h in handlers), (
        "LogFormatter должен быть навешен хотя бы на один handler"
    )


def test_get_logger_attaches_stream_handler(captured_basic_config):
    get_logger("test.ng_parser.stream")
    handlers = captured_basic_config["handlers"]
    assert any(isinstance(h, logging.StreamHandler) for h in handlers)