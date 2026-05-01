# CLAUDE.md — ng_parser

Инструкция для Claude Code по этому репозиторию. Комментарии и docstring-и в коде — на русском.

## Команды

- `make install` — `.venv` (Python 3.12) + зависимости из `pyproject.toml`
- `make test` — тесты пакета (`test/`)
- `make clean` — удалить `.venv` и кэши

Один тест: `.venv/bin/python -m pytest test/<путь>::test_name -v`.

## Архитектура

Паттерн **Command + асинхронная очередь**. Каждый шаг — `Command`, его `parse()` возвращает `ParseResult(rows, children)`; раннер пишет `rows` в `Repository`, `children` — в очередь.

| Сущность | Файл | Роль |
|---|---|---|
| `Command` / `ParseResult` | `ng_parser/command.py` | Контракт: `fetch()` → `parse(html)` → `ParseResult`. Retry с backoff в `execute()`. Хранит **только URL**. |
| `Parser` / `AsyncParser` | `ng_parser/{parser,algorithm/async_parser}.py` | Раннер. `run(queue)` поднимает N воркеров, пишет `rows` в repository, `children` — в queue. **Только раннер знает про Repository и Queue.** |
| `Queue` / `AsyncQueue` | `ng_parser/{task_queue,queue/async_queue}.py` | Unbounded FIFO. `put` синхронный, `get` async, `close(n)` — sentinel. |
| `Repository` | `ng_parser/repository.py` | Sink: `add(row)`. Без дедупликации. |
| `HttpClient` / `HttpxClient` | `ng_parser/client/` | `get()` **не бросает** на 4xx/5xx — `raise_for_status()` руками. |
| `LogFormatter` / `get_logger` | `ng_parser/log_formatter.py` | Красный для WARNING+ только если `stderr.isatty()`. |

## Refactoring Workflow

- After any refactor, run the full test suite and report pass/fail counts before committing.
- When renaming symbols, never use blind replace_all; verify each call site (especially test function names like `test_*`).
- Prefer minimal, targeted changes over architectural rewrites; do NOT introduce new dataclasses, state objects, or exit codes unless explicitly requested.


## Инварианты

- **Retry — на `Command.execute()`**, не внутри `fetch()`/`parse()`.
- **Команды не знают про Repository/Queue.** `parse()` — pure функция HTML→`ParseResult`.
- **Запись per-page атомарна.** Если `parse()` упал — частичных записей нет.
- **Завершение через sentinel**, не `queue.join()`. Когда `active==0 and queue.empty()`, последний воркер делает `queue.close(N)`.
- **Раннер глушит ВСЕ исключения команд** и идёт дальше.
- **`HttpClient.get()` не бросает на 4xx/5xx** намеренно.
- **Никаких `\033[...]` в коде** — цвет накручивает `LogFormatter` только для TTY.

## Тесты

Дерево `test/` — на уровне обёртки рядом с `pyproject.toml`. Структура зеркалит `ng_parser/`:
- `test/test_command.py` → `ng_parser/command.py`
- `test/test_log_formatter.py` → `ng_parser/log_formatter.py`
- `test/test_repository.py` → `ng_parser/repository.py`
- `test/algorithm/test_async_parser.py` → `ng_parser/algorithm/async_parser.py`
- `test/client/test_http_client.py` → `ng_parser/client/http_client.py`
- `test/client/test_httpx_client.py` → `ng_parser/client/httpx_client.py`

Хелперы — `test/utils.py` (`UrlCommand`, `ListRepository`, `make_test_client`, `make_async_parser`, `make_queue_with`). Фикстуры — `test/fixture.py` + `test/conftest.py`.

Тонкости:
- **`_no_command_sleep`** (autouse) патчит **локальный** `ng_parser.command._retry_sleep`, не глобальный `asyncio.sleep`.
- Реальную сеть в тесты не вводи — только `httpx.MockTransport`.

## Коммиты

- Русский текст, без `Co-Authored-By: Claude ...`.
- Запускай тесты перед коммитом, указывай счётчик в теле коммита при рефакторинге.
