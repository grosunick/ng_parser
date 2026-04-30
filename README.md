# ng_parser

Библиотека для построения асинхронных парсеров по паттерну **Command + очередь**.

## Установка

### Как git submodule (рекомендуется для приложений)

```bash
git submodule add https://github.com/grosunick/ng_parser.git lib/ng_parser
```

В `requirements.txt`:
```
-e ./lib/ng_parser
```

### Напрямую из GitHub

```
ng_parser @ git+https://github.com/grosunick/ng_parser.git@main
```

## Основные примитивы

| Класс | Импорт | Роль |
|---|---|---|
| `Command` / `ParseResult` | `from ng_parser import Command, ParseResult` | Единица работы: `fetch()` → `parse(html)` → `ParseResult(rows, children)` |
| `Parser` / `AsyncParser` | `from ng_parser.algorithm import AsyncParser` | Раннер: пул воркеров, пишет rows в Repository, children — в Queue |
| `Queue` / `AsyncQueue` | `from ng_parser.queue import AsyncQueue` | FIFO с sentinel-завершением |
| `Repository` | `from ng_parser import Repository` | Абстрактный sink: `add(row)` |
| `HttpClient` / `HttpxClient` | `from ng_parser.client import HttpxClient` | Асинхронный HTTP-клиент поверх httpx |
| `LogFormatter` / `get_logger` | `from ng_parser import get_logger` | TTY-aware логирование |

## Пример

```python
import asyncio
from ng_parser import Command, ParseResult, Repository
from ng_parser.algorithm import AsyncParser
from ng_parser.queue import AsyncQueue
from ng_parser.client import HttpxClient


class MyRepository(Repository):
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, row: dict) -> None:
        self.rows.append(row)


class PageCommand(Command):
    async def parse(self, html: str) -> ParseResult:
        # разбор HTML, возврат строк и дочерних команд
        return ParseResult(rows=[{"url": self.url, "html_len": len(html)}])


async def main():
    repo = MyRepository()

    async with HttpxClient(http2=True) as client:
        parser = AsyncParser(max_workers=4, client=client, repository=repo)
        queue = AsyncQueue()
        queue.put(PageCommand("https://example.com/"))
        await parser.run(queue)

    print(repo.rows)


asyncio.run(main())
```

## Разработка

```bash
make install   # создать .venv и установить зависимости
make test      # запустить тесты
```
