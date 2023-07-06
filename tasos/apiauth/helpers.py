#
# Copyright Tristen Georgiou 2023
#
from enum import Enum
from typing import TypeVar, Generic, Type

from fastapi import HTTPException
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel
from sqlalchemy import select, func, asc, desc
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import OperatorExpression
from starlette import status

from tasos.apiauth.model import Base

T = TypeVar("T")


class BaseFilterQueryParams(BaseModel):
    """
    The base filter parameters for a database query
    """

    limit: int = Field(default=10, ge=1, le=100, description="The number of items to return")
    offset: int = Field(default=0, ge=0, description="The offset to start from")


class Paginated(GenericModel, Generic[T]):
    """
    A generic paginated response model
    """

    total: int
    items: list[T]


class OrderDirection(Enum):
    """
    The order direction for a query result set
    """

    asc = "asc"
    desc = "desc"


class BaseOrderQueryParams(BaseModel):
    """
    The base order by query parameters for the group model
    """

    order_by: Enum
    order_dir: OrderDirection = OrderDirection.asc


def validate_path(path: str) -> str:
    """
    Validates the given path and returns it if successful

    :param path: The path to validate
    :raises AssertionError: If the path is invalid
    """
    assert path == "" or path.startswith("/"), "Path must start with '/'"

    # remove any trailing slashes from the path
    return path.rstrip("/")


async def get_paginated_results(
    where_clauses: list[OperatorExpression],
    query: BaseFilterQueryParams,
    order: BaseOrderQueryParams,
    model: Type[Base],
    db: AsyncSession,
) -> Paginated:
    """
    Gets the paginated results for the given query

    :param where_clauses: The where clauses to filter the query by
    :param query: The query parameters
    :param order: The order by query parameters
    :param model: The model to query against
    :param db: The database session
    :returns: The paginated results
    """
    # query for the count that matches the query
    count = await db.execute(select(func.count(model.id)).where(*where_clauses))

    # fetch the items filtered by the query
    order_clause = asc(order.order_by.value) if order.order_dir == OrderDirection.asc else desc(order.order_by.value)

    items = await db.execute(
        select(model).where(*where_clauses).limit(query.limit).offset(query.offset).order_by(order_clause)
    )

    return Paginated(total=count.scalar(), items=[item for item in items.scalars()])


async def get_object_from_db_by_id_or_name(id_or_name: int | str, db: AsyncSession, name: str, orm: Type[Base]) -> Base:
    """
    Get the given object by its database id or name

    :param id_or_name: The id or name
    :param db: The database session
    :param name: The name of the object, e.g. Group, Permission, etc.
    :param orm: The ORM model to query against
    :return: The object that matches the given id or name
    :raises HTTPException: If the object is not found or multiple objects are found
    """
    if isinstance(id_or_name, int):
        results = await db.execute(select(orm).where(orm.id == id_or_name))
        not_found_msg = f"{name} with ID {id_or_name} not found"
    elif hasattr(orm, "name"):
        results = await db.execute(select(orm).where(orm.name == id_or_name))  # exact match, not like
        not_found_msg = f"{name} with name '{id_or_name}' not found"
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Can only query {name} with an integer ID"
        )

    try:
        return results.scalar_one()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_msg)
    except MultipleResultsFound:  # should only be possible for models where the name is not unique
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Multiple {name}s found for name '{id_or_name}'"
        )
