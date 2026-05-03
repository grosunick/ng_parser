"""Описание прокси-сервера."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HttpProxy:
    """Прокси-сервер. Тип определяется по схеме URL: http://, https://, socks5://, socks4://, ..."""

    url: str
    label: str = ""  # опционально, для логов

    @property
    def scheme(self) -> str:
        """Схема URL в нижнем регистре (http, https, socks5, socks4, socks5h, ...)."""
        if "://" not in self.url:
            return ""
        return self.url.split("://", 1)[0].lower()

    @property
    def is_socks(self) -> bool:
        """SOCKS-прокси (socks4/socks5/socks5h)."""
        return self.scheme.startswith("socks")

    @property
    def is_http(self) -> bool:
        """HTTP- или HTTPS-прокси."""
        return self.scheme in ("http", "https")
