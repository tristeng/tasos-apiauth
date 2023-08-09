#
# Copyright Tristen Georgiou 2023
#
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tasos.apiauth.api.base import add_base_endpoints_to_app
from tasos.apiauth.api.group import add_group_endpoints_to_app
from tasos.apiauth.auth import hash_password
from tasos.apiauth.db import get_engine, get_sessionmaker
from tasos.apiauth.model import Base, UserOrm, GroupOrm, PermissionOrm
from tests.apiauth.api.test_base import TEST_URL

# test app
app = FastAPI()
add_base_endpoints_to_app(app)
add_group_endpoints_to_app(app)


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    # create the database and tables
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # create a deactivated user and an admin user
    session_maker = get_sessionmaker()
    async with session_maker() as conn:
        # add some permissions
        perm1 = PermissionOrm(name="permission1")
        perm2 = PermissionOrm(name="permission2")
        conn.add(perm1)
        conn.add(perm2)

        # add some groups
        group1 = GroupOrm(name="group1", permissions=[perm1, perm2])
        conn.add(group1)

        group2 = GroupOrm(name="group2", permissions=[perm2])
        conn.add(group2)

        # add an admin user
        admin_user = UserOrm(
            email="me@admin.com",
            hashed_pw=hash_password("Abcdef123!"),
            is_active=True,
            is_admin=True,
        )
        conn.add(admin_user)

        # add a non-admin user and add them to the group
        user = UserOrm(
            email="notadmin@test.com",
            hashed_pw=hash_password("Abcdef123!"),
            is_active=True,
            is_admin=False,
            groups=[group1],
        )
        conn.add(user)

        await conn.commit()

    yield engine  # run the tests

    # drop the database and tables
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_groups(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # get the list of groups
        url = "/admin/groups"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert data["items"][0]["name"] == "group1"
        assert len(data["items"][0]["permissions"]) == 2
        assert data["items"][0]["permissions"][0]["name"] == "permission1"
        assert data["items"][0]["permissions"][1]["name"] == "permission2"
        assert data["items"][1]["name"] == "group2"
        assert len(data["items"][1]["permissions"]) == 1
        assert data["items"][1]["permissions"][0]["name"] == "permission2"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_group(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # get the list of groups
        url = "/admin/groups/1"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "group1"
        assert len(data["permissions"]) == 2
        assert data["permissions"][0]["name"] == "permission1"
        assert data["permissions"][1]["name"] == "permission2"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_group(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # create a new group
        url = "/admin/groups"
        response = await ac.post(url, headers={"Authorization": f"Bearer {token}"}, json={"name": "group3"})
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 3
        assert data["name"] == "group3"
        assert len(data["permissions"]) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_group_name_exists(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # create a new group
        url = "/admin/groups"
        response = await ac.post(url, headers={"Authorization": f"Bearer {token}"}, json={"name": "group1"})
        assert response.status_code == 409

        data = response.json()
        assert data["detail"] == "A group with this name already exists"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_group_with_permissions(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # create a new group
        url = "/admin/groups"
        response = await ac.post(
            url, headers={"Authorization": f"Bearer {token}"}, json={"name": "group3", "permissions": ["permission1"]}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 3
        assert data["name"] == "group3"
        assert len(data["permissions"]) == 1
        assert data["permissions"][0]["name"] == "permission1"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_group_with_unknown_permission(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # create a new group
        url = "/admin/groups"
        response = await ac.post(
            url, headers={"Authorization": f"Bearer {token}"}, json={"name": "group3", "permissions": ["permission3"]}
        )
        assert response.status_code == 404

        data = response.json()
        assert data["detail"] == "One or more Permissions were not found. Found = "


@pytest.mark.asyncio
@pytest.mark.integration
async def test_modify_group(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # modify the group
        url = "/admin/groups/1"
        response = await ac.put(
            url, headers={"Authorization": f"Bearer {token}"}, json={"name": "group1", "permissions": ["permission1"]}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "group1"
        assert len(data["permissions"]) == 1
        assert data["permissions"][0]["name"] == "permission1"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_modify_group_name_exists(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # modify the group
        url = "/admin/groups/1"
        response = await ac.put(
            url, headers={"Authorization": f"Bearer {token}"}, json={"name": "group2", "permissions": ["permission1"]}
        )
        assert response.status_code == 409

        data = response.json()
        assert data["detail"] == "A group with this name already exists"
