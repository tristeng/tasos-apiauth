#
# Copyright Tristen Georgiou 2023
#
from enum import Enum
from typing import Sequence, Annotated

from fastapi import FastAPI, HTTPException
from fastapi.params import Depends

from pydantic import BaseModel
from sqlalchemy import select
from starlette import status

from tasos.apiauth.auth import get_current_admin_user
from tasos.apiauth.db import DatabaseDepends
from tasos.apiauth.helpers import (
    Paginated,
    BaseFilterQueryParams,
    OrderDirection,
    validate_path,
    get_paginated_results,
    BaseOrderQueryParams,
    get_object_from_db_by_id_or_name,
)
from tasos.apiauth.model import Group, GroupOrm


class GroupQueryParams(BaseFilterQueryParams):
    """
    The group query parameters
    """

    name: str | None = None


class GroupOrderColumns(Enum):
    """
    The group order columns
    """

    id = "id"
    name = "name"
    created = "created"


class GroupOrderQueryParams(BaseOrderQueryParams):
    """
    The order by query parameters for the group model
    """

    order_by: GroupOrderColumns = GroupOrderColumns.id
    order_dir: OrderDirection = OrderDirection.asc


class GroupCreate(BaseModel):
    """
    The group model to create a new group
    """

    name: str


def add_group_endpoints_to_app(
    app: FastAPI,
    path: str = "/admin",
    dependencies: Sequence[Depends] | None = None,
) -> None:
    """
    Adds the group endpoints to the FastAPI app

    :param app: The FastAPI app
    :param path: The path prefix to add the endpoints to
    :param dependencies: Any dependencies to add to the endpoints, defaults to current admin user
    """
    path = validate_path(path)

    # by default, we restrict the endpoints to admin users
    if dependencies is None:
        dependencies = [Depends(get_current_admin_user)]

    @app.get(
        path + "/groups",
        response_model=Paginated[Group],
        description="Fetches the groups",
        tags=["admin"],
        dependencies=dependencies,
    )
    async def get_groups(
        query: Annotated[GroupQueryParams, Depends()],
        order: Annotated[GroupOrderQueryParams, Depends()],
        db: DatabaseDepends,
    ) -> Paginated[Group]:
        """
        Returns a list of the groups based on the query parameters
        """
        # create the where clauses
        where_clauses = []
        if query.name is not None:
            where_clauses.append(GroupOrm.name.like(query.name))

        return await get_paginated_results(where_clauses, query, order, GroupOrm, db)

    @app.get(
        path + "/groups/{group_id}",
        response_model=Group,
        description="Fetches the group by ID or name",
        tags=["admin"],
        dependencies=dependencies,
    )
    async def get_group(
        group_id: int | str,
        db: DatabaseDepends,
    ) -> Group:
        """
        Returns the group by the given ID or name
        """
        return Group.from_orm(await get_object_from_db_by_id_or_name(group_id, db, "Group", GroupOrm))

    @app.post(
        path + "/groups",
        response_model=Group,
        description="Creates a new group",
        tags=["admin"],
        dependencies=dependencies,
    )
    async def create_group(
        group: GroupCreate,
        db: DatabaseDepends,
    ) -> Group:
        """
        Creates a new group
        """
        # make sure the group name doesn't already exist
        result = await db.execute(select(GroupOrm).filter(GroupOrm.name == group.name))
        if result.scalars().first() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A group with this name already exists")

        # create the group
        group_orm = GroupOrm(name=group.name)
        db.add(group_orm)
        await db.commit()
        await db.refresh(group_orm)  # refresh the group to get the permissions

        return Group.from_orm(group_orm)
