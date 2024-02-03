#
# Copyright Tristen Georgiou 2023
#
from collections.abc import AsyncGenerator
from functools import cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from tasos.apiauth.config import get_apiauth_settings

# global engine variable
_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Gets the engine for the database

    :return: the sqlalchemy database engine
    """
    global _engine
    if _engine is None:
        auth_settings = get_apiauth_settings()
        _engine = create_async_engine(auth_settings.database_url)
    return _engine


def clear_engine() -> None:
    """
    Clears the global engine variable - only used for testing
    """
    global _engine
    _engine = None


@cache
def get_sessionmaker(autoflush: bool = True, expire_on_commit: bool = False) -> async_sessionmaker[AsyncSession]:
    """Gets a new session maker for the database

    :param autoflush: whether to autoflush the session
    :param expire_on_commit: whether to expire the session on commit - "should normally be set to False when using
        asyncio"
    :return: the sqlalchemy database session maker
    """
    return async_sessionmaker(get_engine(), autoflush=autoflush, expire_on_commit=expire_on_commit)


async def get_db() -> AsyncGenerator[AsyncSession, None]:  # pragma: no cover
    """Gets a new database session and automatically closes it when the context is exited

    :return: sqlalchemy database session
    """
    async_session = get_sessionmaker()
    async with async_session() as session:
        yield session


DatabaseDepends = Annotated[AsyncSession, Depends(get_db)]
