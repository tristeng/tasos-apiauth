#
# Copyright Tristen Georgiou 2023
#
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncEngine

from tasos.apiauth.api.base import add_base_endpoints_to_app
from tasos.apiauth.api.user import add_user_endpoints_to_app
from .test_base import db_engine, TEST_URL  # noqa

app = FastAPI()
add_base_endpoints_to_app(app)
add_user_endpoints_to_app(app)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_users(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(transport=ASGITransport(app=app), base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # get the list of users
        url = "/admin/users"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert data["items"][0]["id"] == 1
        assert data["items"][0]["email"] == "not@active.com"
        assert len(data["items"][0]["groups"]) == 1
        assert data["items"][0]["groups"][0]["name"] == "group1"
        assert len(data["items"][0]["groups"][0]["permissions"]) == 2

        assert data["items"][1]["id"] == 2
        assert data["items"][1]["email"] == "me@admin.com"
        assert len(data["items"][1]["groups"]) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(transport=ASGITransport(app=app), base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # get a user by ID
        url = "/admin/users/1"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["email"] == "not@active.com"
        assert len(data["groups"]) == 1
        assert data["groups"][0]["name"] == "group1"
        assert len(data["groups"][0]["permissions"]) == 2

        # get a user by email
        url = "/admin/users/me@admin.com"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 2
        assert data["email"] == "me@admin.com"
        assert len(data["groups"]) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_modify_user(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(transport=ASGITransport(app=app), base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # modify a user by ID - make them admin, activate them and clear out their groups
        url = "/admin/users/1"
        response = await ac.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": True, "is_admin": True, "groups": []},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["is_active"] is True
        assert data["is_admin"] is True
        assert len(data["groups"]) == 0

        # modify a user by email - remove admin access but leave them active and add them to group2
        url = "/admin/users/not@active.com"
        response = await ac.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"is_admin": False, "groups": ["group2"]},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["is_active"] is True
        assert data["is_admin"] is False
        assert len(data["groups"]) == 1
        assert data["groups"][0]["name"] == "group2"
        assert len(data["groups"][0]["permissions"]) == 1

        # login as the non-admin user who is now active, and make sure they can't modify the other user
        url = "/auth/token"
        response = await ac.post(url, data={"username": "not@active.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        url = "/admin/users/me@admin.com"
        response = await ac.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )
        assert response.status_code == 401
