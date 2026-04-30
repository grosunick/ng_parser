"""
Conftest для тестов пакета `ng_parser`.

Настраивает sys.path и реэкспортит фикстуры из fixture.py — pytest подбирает
autouse-фикстуры только из conftest.py (или зарегистрированных плагинов).
Утилитные хелперы лежат в utils.py — тесты импортируют их напрямую.
"""

import sys
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_TEST_DIR = Path(__file__).parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))


from fixture import _no_command_sleep  # noqa: F401,E402
