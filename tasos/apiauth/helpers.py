#
# Copyright Tristen Georgiou 2023
#
from enum import StrEnum
from typing import TypeVar, Generic, Type, Any, Annotated

from fastapi import HTTPException, Depends
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel
from sqlalchemy import select, func, asc, desc
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import UnaryExpression
from starlette import status

from tasos.apiauth.auth import get_current_active_user
from tasos.apiauth.model import Base, UserOrm, PermissionOrm

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


class OrderDirection(StrEnum):
    """
    The order direction for a query result set
    """

    asc = "asc"
    desc = "desc"


class BaseOrderQueryParams(BaseModel):
    """
    The base order by query parameters for the group model
    """

    order_by: StrEnum
    order_dir: OrderDirection = OrderDirection.asc


class UserHasPermissions:
    """
    A dependency that checks if the current user has the given permissions
    """

    def __init__(self, *permissions: StrEnum) -> None:
        """
        Initializes a new instance of the UserHasPermissions class

        :param permissions: The required permissions
        """
        self.permissions = [perm for perm in permissions]

    async def __call__(self, user: Annotated[UserOrm, Depends(get_current_active_user)]) -> None:
        """
        Checks if the current user has the required permissions

        :param user: The current user
        :raises HTTPException: If the user does not have the required permissions
        """
        # check if the user is an admin and if so, they have all permissions
        if user.is_admin:
            return

        # assemble the user's permissions
        permissions = set()
        for group in user.groups:
            permissions.update({perm.name for perm in group.permissions})

        # check if the user has all the required permissions
        if not permissions.issuperset(self.permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not have required permissions")


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
    where_clauses: list[Any],
    query: BaseFilterQueryParams,
    order: BaseOrderQueryParams,
    model: Type[Base],
    db: AsyncSession,
) -> Paginated[Any]:
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
    order_clause: UnaryExpression[Any] = (
        asc(order.order_by) if order.order_dir == OrderDirection.asc else desc(order.order_by)
    )

    items = await db.execute(
        select(model).where(*where_clauses).limit(query.limit).offset(query.offset).order_by(order_clause)
    )

    return Paginated(total=count.scalar_one(), items=[item for item in items.scalars()])


async def get_object_from_db_by_id_or_name(
    id_or_name: int | str, db: AsyncSession, name: str, orm: Type[Base]
) -> Type[BaseModel] | Base:
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


async def get_permissions_by_name(permissions: set[str], db: AsyncSession) -> list[PermissionOrm]:
    """
    Fetches permissions from the database by name

    :param permissions: The permissions - a set of exact permission names
    :param db: The database session
    :return: The permissions or an empty list if none were specified
    :raises ValueError: if one or more permissions were not found
    """
    results = []
    if permissions is not None:
        perm_results = await db.execute(select(PermissionOrm).where(PermissionOrm.name.in_(permissions)))
        results = perm_results.scalars().all()

        # make sure all the permissions were found
        if len(results) != len(permissions):
            msg = ", ".join([perm.name for perm in results])
            raise ValueError(f"One or more permissions were not found. Found = {msg}")

    return results
