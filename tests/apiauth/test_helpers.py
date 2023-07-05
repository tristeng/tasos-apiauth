#
# Copyright Tristen Georgiou 2023
#
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import Result
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from tasos.apiauth.api.permission import PermissionQueryParams, PermissionOrderQueryParams, PermissionOrderColumns
from tasos.apiauth.helpers import validate_path, get_paginated_results, get_object_from_db_by_id_or_name, OrderDirection
from tasos.apiauth.model import PermissionOrm, GroupOrm, Group, UserOrm


@pytest.fixture
def mock_db() -> AsyncMock:
    count_result = MagicMock(Result)
    count_result.scalar.return_value = 3

    item_result = MagicMock(Result)
    item_result.scalars.return_value = [
        PermissionOrm(id=1, name="permission1", group_id=1),
        PermissionOrm(id=2, name="permission2", group_id=1),
        PermissionOrm(id=3, name="permission3", group_id=2),
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
    item_result.scalar_one.side_effect = NoResultFound

    mock_db = AsyncMock(AsyncSession)
    mock_db.execute.return_value = item_result
    return mock_db


def test_validate_path():
    assert validate_path("/admin/") == "/admin"
    assert validate_path("/admin//") == "/admin"
    assert validate_path("/admin") == "/admin"
    assert validate_path("") == ""

    with pytest.raises(AssertionError, match="Path must start with '/'"):
        validate_path("admin")


@pytest.mark.asyncio
async def test_get_paginated_results(mock_db: AsyncMock):
    where_clauses = [PermissionOrm.name.like("some_permission_name"), PermissionOrm.group_id == 7]
    query = PermissionQueryParams(limit=10, offset=10)
    order = PermissionOrderQueryParams(order_by=PermissionOrderColumns.name, order_dir=OrderDirection.desc)

    actual = await get_paginated_results(where_clauses, query, order, PermissionOrm, mock_db)
    assert actual.total == 3
    assert len(actual.items) == 3
    assert actual.items[0].id == 1
    assert actual.items[0].name == "permission1"
    assert actual.items[0].group_id == 1
    assert actual.items[1].id == 2
    assert actual.items[1].name == "permission2"
    assert actual.items[1].group_id == 1
    assert actual.items[2].id == 3
    assert actual.items[2].name == "permission3"
    assert actual.items[2].group_id == 2


@pytest.mark.asyncio
async def test_get_object_from_db_by_id_or_name(mock_db_get_object: AsyncMock):
    # test get by integer id
    actual = await get_object_from_db_by_id_or_name(1, mock_db_get_object, "Group", GroupOrm)
    actual = Group.from_orm(actual)
    assert actual.id == 1
    assert actual.name == "group1"

    # test get by string name
    actual = await get_object_from_db_by_id_or_name("group2", mock_db_get_object, "Group", GroupOrm)
    actual = Group.from_orm(actual)
    assert actual.id == 2
    assert actual.name == "group2"


@pytest.mark.asyncio
async def test_get_object_from_db_by_id_or_name_not_exists(mock_db_get_object_not_exists: AsyncMock):
    with pytest.raises(HTTPException) as exc:
        await get_object_from_db_by_id_or_name(12, mock_db_get_object_not_exists, "Group", GroupOrm)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Group with ID 12 not found"


@pytest.mark.asyncio
async def test_get_object_from_db_by_id_or_name_invalid_model():
    # test case where the input ORM model doesn't have the name attribute
    with pytest.raises(HTTPException) as exc:
        await get_object_from_db_by_id_or_name("this won't work!", AsyncMock(AsyncSession), "User", UserOrm)

    assert exc.value.status_code == 500
    assert exc.value.detail == "Can only query User with an integer ID"
