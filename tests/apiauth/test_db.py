#
# Copyright Tristen Georgiou 2023
#
import pytest

from tasos.apiauth.db import get_engine, get_sessionmaker, clear_engine


@pytest.fixture
def mock_sqlachelmy(monkeypatch):
    def mock_create_async_engine(database_url):
        return database_url

    monkeypatch.setattr("tasos.apiauth.db.create_async_engine", mock_create_async_engine)

    def mock_async_sessionmaker(engine, autoflush, expire_on_commit):
        return engine, autoflush, expire_on_commit

    monkeypatch.setattr("tasos.apiauth.db.async_sessionmaker", mock_async_sessionmaker)


def test_get_engine(mock_sqlachelmy):
    # clears the caching that may occur from the api client tests
    clear_engine()

    # environment variables read by pytest are set in the pyproject.toml file
    # doesn't test much other than to just cover the code
    assert get_engine() == "sqlite+aiosqlite://?check_same_thread=false"


def test_get_sessionmaker(mock_sqlachelmy):
    # clears the caching that may occur from the api client tests
    clear_engine()
    get_sessionmaker.cache_clear()

    # doesn't test much other than to just cover the code
    assert get_sessionmaker() == ("sqlite+aiosqlite://?check_same_thread=false", True, False)
    assert get_sessionmaker(False, True) == ("sqlite+aiosqlite://?check_same_thread=false", False, True)
