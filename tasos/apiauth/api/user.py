#
# Copyright Tristen Georgiou 2023
#
from enum import Enum
from typing import Annotated, Sequence

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, asc, desc
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from tasos.apiauth.auth import get_current_admin_user
from tasos.apiauth.db import DatabaseDepends
from tasos.apiauth.model import User, UserOrm
from tasos.apiauth.helpers import Paginated, BaseFilterQueryParams, OrderDirection


class UserQueryParams(BaseFilterQueryParams):
    """
    The user query parameters
    """

    is_active: bool | None = None
    is_admin: bool | None = None


class UserOrderColumns(Enum):
    """
    The user order columns
    """

    id = "id"
    last_login = "last_login"
    created = "created"


class UserOrderQueryParams(BaseModel):
    """
    The order by query parameters for the user model
    """

    order_by: UserOrderColumns = UserOrderColumns.id
    order_dir: OrderDirection = OrderDirection.asc


class UserModify(BaseModel):
    """
    The user model to modify an existing user
    """

    is_active: bool | None = None
    is_admin: bool | None = None


async def get_user_from_db_by_id_or_email(user_id: int | EmailStr, db: AsyncSession) -> UserOrm:
    """
    Attempts to get the user by ID or email from the database

    :param user_id: The user ID or email
    :param db: The database session
    :return: The user (or None if user doesn't exist) and an appropriate error message if the user doesn't exist
    :raises HTTPException: If the user doesn't exist
    """
    if isinstance(user_id, int):
        user = await db.execute(select(UserOrm).where(UserOrm.id == user_id))
        not_found_msg = f"User with ID {user_id} not found"
    else:
        user = await db.execute(select(UserOrm).where(UserOrm.email == user_id))
        not_found_msg = f"User with email '{user_id}' not found"

    try:
        user = user.scalar_one()
    except NoResultFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=not_found_msg)

    return user


def add_user_endpoints_to_app(
    app: FastAPI,
    path: str = "/admin",
    dependencies: Sequence[Depends] | None = None,
) -> None:
    """
    Adds the user endpoints to the FastAPI app

    :param app: The FastAPI app
    :param path: The path prefix to add the endpoints to
    :param dependencies: Any dependencies to add to the encpoints, defaults to current admin user
    """
    assert path == "" or path.startswith("/"), "Path must start with '/'"

    # remove any trailing slashes from the path
    path = path.rstrip("/")

    # by default, we restrict the endpoints to admin users
    if dependencies is None:
        dependencies = [Depends(get_current_admin_user)]

    @app.get(
        path + "/users/",
        response_model=Paginated[User],
        description="Fetches the users",
        tags=["admin"],
        dependencies=dependencies,
    )
    async def get_users(
        query: Annotated[UserQueryParams, Depends()],
        order: Annotated[UserOrderQueryParams, Depends()],
        db: DatabaseDepends,
    ) -> Paginated[User]:
        """
        Returns a list of the users based on the query parameters
        """
        # create the where clauses
        where_clauses = []
        if query.is_active is not None:
            where_clauses.append(UserOrm.is_active == query.is_active)
        if query.is_admin is not None:
            where_clauses.append(UserOrm.is_admin == query.is_admin)

        # query for the count that matches the query
        count = await db.execute(select(func.count(UserOrm.id)).where(*where_clauses))

        # fetch the items filtered by the query
        order_clause = (
            asc(order.order_by.value) if order.order_dir == OrderDirection.asc else desc(order.order_by.value)
        )

        items = await db.execute(
            select(UserOrm).where(*where_clauses).limit(query.limit).offset(query.offset).order_by(order_clause)
        )

        return Paginated(total=count.scalar(), items=[item for item in items.scalars()])

    @app.get(
        path + "/users/{user_id}",
        response_model=User,
        description="Fetches a user by ID",
        tags=["admin"],
        dependencies=dependencies,
    )
    async def get_user_by_id_or_email(
        user_id: int | EmailStr,
        db: DatabaseDepends,
    ) -> UserOrm:
        """
        Fetches a user by ID or email
        """
        return await get_user_from_db_by_id_or_email(user_id, db)

    @app.put(
        path + "/users/{user_id}",
        response_model=User,
        description="Updates a user by ID",
        tags=["admin"],
        dependencies=dependencies,
    )
    async def modify_user_by_id_or_email(
        user_modify: UserModify,
        user_id: int | EmailStr,
        db: DatabaseDepends,
    ) -> UserOrm:
        """
        Modifies an existing user
        """
        user = await get_user_from_db_by_id_or_email(user_id, db)

        if user_modify.is_active is not None:
            user.is_active = user_modify.is_active

        if user_modify.is_admin is not None:
            user.is_admin = user_modify.is_admin

        db.add(user)
        await db.commit()

        return user