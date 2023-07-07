#
# Copyright Tristen Georgiou 2023
#
# test app
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tasos.apiauth.api import add_base_endpoints_to_app, add_permission_endpoints_to_app
from .test_base import TEST_URL

# re-use the db_engine fixture from the group tests
from .test_group import db_engine  # noqa

app = FastAPI()
add_base_endpoints_to_app(app)
add_permission_endpoints_to_app(app)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_permissions(db_engine: AsyncGenerator) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # get the list of permissions
        url = "/admin/permissions"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert data["items"][0]["name"] == "permission1"
        assert data["items"][1]["name"] == "permission2"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_permission(db_engine: AsyncGenerator) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # get a single permission
        url = "/admin/permissions/1"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "permission1"

        # test getting a single permission by name
        url = "/admin/permissions/permission2"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 2
        assert data["name"] == "permission2"
