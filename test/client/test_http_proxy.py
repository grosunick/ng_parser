"""Тесты для ng_parser.client.http_proxy: dataclass HttpProxy и его properties."""

import pytest

from ng_parser.client.http_proxy import HttpProxy


@pytest.mark.parametrize(
    "url,expected_scheme",
    [
        ("http://host:8080", "http"),
        ("HTTPS://host:443", "https"),
        ("socks5://host:1080", "socks5"),
        ("socks4://host:1080", "socks4"),
        ("socks5h://host:1080", "socks5h"),
        ("Socks5://HOST", "socks5"),
        ("user:pass@host:8080", ""),  # без схемы
        ("", ""),
    ],
)
def test_proxy_scheme(url, expected_scheme):
    assert HttpProxy(url=url).scheme == expected_scheme


@pytest.mark.parametrize(
    "url,is_socks",
    [
        ("socks5://host", True),
        ("socks4://host", True),
        ("socks5h://host", True),
        ("SOCKS5://host", True),
        ("http://host", False),
        ("https://host", False),
        ("", False),
    ],
)
def test_proxy_is_socks(url, is_socks):
    assert HttpProxy(url=url).is_socks is is_socks


@pytest.mark.parametrize(
    "url,is_http",
    [
        ("http://host", True),
        ("https://host", True),
        ("HTTP://host", True),
        ("socks5://host", False),
        ("", False),
    ],
)
def test_proxy_is_http(url, is_http):
    assert HttpProxy(url=url).is_http is is_http


def test_proxy_is_frozen():
    p = HttpProxy(url="http://host", label="primary")
    with pytest.raises(Exception):
        p.url = "http://other"  # type: ignore[misc]


def test_proxy_label_default_empty():
    assert HttpProxy(url="http://host").label == ""


def test_proxy_equality_includes_label():
    """label — часть identity, два прокси с одним url, но разными label не равны."""
    assert HttpProxy(url="http://host", label="a") != HttpProxy(url="http://host", label="b")
    assert HttpProxy(url="http://host") == HttpProxy(url="http://host")
