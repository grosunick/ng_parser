"""Тесты для ng_parser.repository: абстракция Repository."""

import pytest

from ng_parser import Repository


def test_repository_is_abstract():
    with pytest.raises(TypeError, match="abstract"):
        Repository()  # type: ignore[abstract]


def test_repository_subclass_must_implement_add():
    class IncompleteRepo(Repository):
        pass

    with pytest.raises(TypeError, match="abstract"):
        IncompleteRepo()  # type: ignore[abstract]


def test_repository_minimal_subclass_works():
    class ListRepo(Repository):
        def __init__(self):
            self.rows = []

        def add(self, row):
            self.rows.append(row)

        @property
        def count(self) -> int:
            return len(self.rows)

    repo = ListRepo()
    repo.add({"url": "x"})
    assert repo.rows == [{"url": "x"}]
    assert repo.count == 1