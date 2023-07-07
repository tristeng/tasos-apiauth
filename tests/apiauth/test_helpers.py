#
# Copyright Tristen Georgiou 2023
#
from datetime import datetime
from enum import StrEnum
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import Result
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession

from tasos.apiauth.api.permission import PermissionQueryParams, PermissionOrderQueryParams, PermissionOrderColumns
from tasos.apiauth.helpers import (
    validate_path,
    get_paginated_results,
    get_object_from_db_by_id_or_name,
    OrderDirection,
    UserHasPermissions,
)
from tasos.apiauth.model import PermissionOrm, GroupOrm, Group, UserOrm


class CustomPermissions(StrEnum):
    """
    Some custom permissions for testing
    """

    permission1 = "permission1"
    permission2 = "permission2"
    permission3 = "permission3"
    permission4 = "permission4"
    permission5 = "permission5"


@pytest.fixture
def mock_db() -> AsyncMock:
    count_result = MagicMock(Result)
    count_result.scalar_one.return_value = 3

    item_result = MagicMock(Result)
    item_result.scalars.return_value = [
        PermissionOrm(id=1, name=CustomPermissions.permission1),
        PermissionOrm(id=2, name=CustomPermissions.permission2),
        PermissionOrm(id=3, name=CustomPermissions.permission3),
    ]

    mock_db = AsyncMock(AsyncSession)
    mock_db.execute.side_effect = [count_result, item_result]
    return mock_db


@pytest.fixture
def mock_db_get_object() -> AsyncMock:
    item_result = MagicMock(Result)
    item_result.scalar_one.side_effect = [
        GroupOrm(id=1, name="group1", created=datetime.now(), permissions=[]),
        GroupOrm(id=2, name="group2", created=datetime.now(), permissions=[]),
    ]

    mock_db = AsyncMock(AsyncSession)
    mock_db.execute.return_value = item_result
    return mock_db


@pytest.fixture
def mock_db_get_object_not_exists() -> AsyncMock:
    item_result = MagicMock(Result)
    item_result.scalar_one.side_effect = [NoResultFound, MultipleResultsFound]

    mock_db = AsyncMock(AsyncSession)
    mock_db.execute.return_value = item_result
    return mock_db


@pytest.fixture
def mock_current_active_user() -> UserOrm:
    # a user that belongs to a single group with 3 permissions
    perm1 = PermissionOrm(id=1, name=CustomPermissions.permission1)
    perm2 = PermissionOrm(id=2, name=CustomPermissions.permission2)
    perm3 = PermissionOrm(id=3, name=CustomPermissions.permission3)

    group1 = GroupOrm(id=1, name="group1", created=datetime.now(), permissions=[perm1, perm2, perm3])

    user = UserOrm(id=1, email="someuser@test.com", hashed_pw="somehashedpassword", is_active=True, groups=[group1])
    return user


def test_validate_path() -> None:
    assert validate_path("/admin/") == "/admin"
    assert validate_path("/admin//") == "/admin"
    assert validate_path("/admin") == "/admin"
    assert validate_path("") == ""

    with pytest.raises(AssertionError, match="Path must start with '/'"):
        validate_path("admin")


@pytest.mark.asyncio
async def test_get_paginated_results(mock_db: AsyncMock) -> None:
    where_clauses = [PermissionOrm.name.like("some_permission_name")]
    query = PermissionQueryParams(limit=10, offset=10)
    order = PermissionOrderQueryParams(order_by=PermissionOrderColumns.name, order_dir=OrderDirection.desc)

    actual = await get_paginated_results(where_clauses, query, order, PermissionOrm, mock_db)
    assert actual.total == 3
    assert len(actual.items) == 3
    assert actual.items[0].id == 1
    assert actual.items[0].name == "permission1"
    assert actual.items[1].id == 2
    assert actual.items[1].name == "permission2"
    assert actual.items[2].id == 3
    assert actual.items[2].name == "permission3"


@pytest.mark.asyncio
async def test_get_object_from_db_by_id_or_name(mock_db_get_object: AsyncMock) -> None:
    # test get by integer id
    actual = Group.from_orm(await get_object_from_db_by_id_or_name(1, mock_db_get_object, "Group", GroupOrm))
    assert actual.id == 1
    assert actual.name == "group1"

    # test get by string name
    actual = Group.from_orm(await get_object_from_db_by_id_or_name("group2", mock_db_get_object, "Group", GroupOrm))
    assert actual.id == 2
    assert actual.name == "group2"


@pytest.mark.asyncio
async def test_get_object_from_db_by_id_or_name_invalid(mock_db_get_object_not_exists: AsyncMock) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_object_from_db_by_id_or_name(12, mock_db_get_object_not_exists, "Group", GroupOrm)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Group with ID 12 not found"

    with pytest.raises(HTTPException) as exc:
        await get_object_from_db_by_id_or_name("too many results", mock_db_get_object_not_exists, "Group", GroupOrm)

    assert exc.value.status_code == 422
    assert exc.value.detail == "Multiple Groups found for name 'too many results'"


@pytest.mark.asyncio
async def test_get_object_from_db_by_id_or_name_invalid_model() -> None:
    # test case where the input ORM model doesn't have the name attribute
    with pytest.raises(HTTPException) as exc:
        await get_object_from_db_by_id_or_name("this won't work!", AsyncMock(AsyncSession), "User", UserOrm)

    assert exc.value.status_code == 500
    assert exc.value.detail == "Can only query User with an integer ID"


@pytest.mark.asyncio
async def test_user_has_permissions_dep(mock_current_active_user: UserOrm) -> None:
    # these checks should pass - the user has all 3 permissions
    checker_valid1 = UserHasPermissions(CustomPermissions.permission1)
    checker_valid2 = UserHasPermissions(CustomPermissions.permission1, CustomPermissions.permission2)
    checker_valid3 = UserHasPermissions(
        CustomPermissions.permission1, CustomPermissions.permission2, CustomPermissions.permission3
    )

    # test valid permissions
    await checker_valid1(mock_current_active_user)
    await checker_valid2(mock_current_active_user)
    await checker_valid3(mock_current_active_user)

    # test invalid permissions
    checker_invalid = UserHasPermissions(CustomPermissions.permission1, CustomPermissions.permission4)
    with pytest.raises(HTTPException) as exc:
        await checker_invalid(mock_current_active_user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "User does not have required permissions"

    # but if the user is admin, we should be able to pass any permission check
    mock_current_active_user.is_admin = True
    await checker_invalid(mock_current_active_user)
