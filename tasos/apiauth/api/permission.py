#
# Copyright Tristen Georgiou 2023
#
from enum import Enum
from typing import Sequence, Annotated

from fastapi import FastAPI, Depends

from tasos.apiauth.auth import get_current_admin_user
from tasos.apiauth.db import DatabaseDepends
from tasos.apiauth.helpers import (
    validate_path,
    Paginated,
    BaseFilterQueryParams,
    get_paginated_results,
    OrderDirection,
    BaseOrderQueryParams,
    get_object_from_db_by_id_or_name,
)
from tasos.apiauth.model import Permission, PermissionOrm


class PermissionQueryParams(BaseFilterQueryParams):
    """
    The permission query parameters
    """

    name: str | None = None
    group_id: int | None = None


class PermissionOrderColumns(Enum):
    """
    The permission order columns
    """

    id = "id"
    name = "name"
    group_id = "group_id"
    created = "created"


class PermissionOrderQueryParams(BaseOrderQueryParams):
    """
    The order by query parameters for the permission model - defaults to group id ascending
    """

    order_by: PermissionOrderColumns = PermissionOrderColumns.group_id
    order_dir: OrderDirection = OrderDirection.asc


def add_permission_endpoints_to_app(
    app: FastAPI,
    path: str = "/admin",
    dependencies: Sequence[Depends] | None = None,
) -> None:
    """
    Add the permission endpoints to the app

    :param app: The FastAPI app
    :param path: The path prefix to add the endpoints to
    :param dependencies: Any dependencies to add to the endpoints, defaults to current admin user
    """
    path = validate_path(path)

    # by default, we restrict the endpoints to admin users
    if dependencies is None:
        dependencies = [Depends(get_current_admin_user)]

    @app.get(
        path + "/permissions",
        response_model=Paginated[Permission],
        description="Fetches the permissions",
        tags=["admin"],
        dependencies=dependencies,
    )
    async def get_permissions(
        query: Annotated[PermissionQueryParams, Depends()],
        order: Annotated[PermissionOrderQueryParams, Depends()],
        db: DatabaseDepends,
    ) -> Paginated[Permission]:
        """
        Returns a list of the groups based on the query parameters
        """
        # create the where clauses
        where_clauses = []
        if query.name is not None:
            where_clauses.append(PermissionOrm.name.like(query.name))
        if query.group_id is not None:
            where_clauses.append(PermissionOrm.group_id == query.group_id)

        return await get_paginated_results(where_clauses, query, order, PermissionOrm, db)

    @app.get(
        path + "/permissions/{permission_id}",
        response_model=Permission,
        description="Fetches the permission by ID or name",
        tags=["admin"],
        dependencies=dependencies,
    )
    async def get_permission(
        permission_id: int | str,
        db: DatabaseDepends,
    ) -> Permission:
        """
        Returns the permission by the given ID or name
        """
        return Permission.from_orm(
            await get_object_from_db_by_id_or_name(permission_id, db, "Permission", PermissionOrm)
        )
