#
# Copyright Tristen Georgiou 2023
#
import pytest

from fastapi import FastAPI, Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncEngine

from tasos.apiauth.api.base import add_base_endpoints_to_app
from tasos.apiauth.api.permission import add_permission_endpoints_to_app
from tasos.apiauth.helpers import UserHasAllPermissions, UserHasAnyPermission
from .test_base import TEST_URL

# re-use the db_engine fixture from the group tests
from .test_group import db_engine  # noqa

# re-use the permissions from the helpers tests
from ..test_helpers import CustomPermissions  # noqa

app = FastAPI()
add_base_endpoints_to_app(app)
add_permission_endpoints_to_app(app)


# the default user only has permission1 and permission2
checker_valid1 = UserHasAllPermissions(CustomPermissions.permission1)
checker_valid2 = UserHasAllPermissions(CustomPermissions.permission2)
checker_valid3 = UserHasAllPermissions(CustomPermissions.permission1, CustomPermissions.permission2)

checker_invalid1 = UserHasAllPermissions(CustomPermissions.permission4)
checker_invalid2 = UserHasAllPermissions(CustomPermissions.permission5)
checker_invalid3 = UserHasAllPermissions(CustomPermissions.permission4, CustomPermissions.permission5)

# the default user only has permission1 and permission2 - but this permission checker should pass
checker_any = UserHasAnyPermission(CustomPermissions.permission1, CustomPermissions.permission5)


# add some custom endpoints to test permission checking
@app.get("/some/endpoint1", dependencies=[Depends(checker_valid1)])
async def some_endpoint1() -> dict[str, str]:
    return {}


@app.get("/some/endpoint2", dependencies=[Depends(checker_valid2)])
async def some_endpoint2() -> dict[str, str]:
    return {}


@app.get("/some/endpoint3", dependencies=[Depends(checker_valid3)])
async def some_endpoint3() -> dict[str, str]:
    return {}


@app.get("/some/endpoint4", dependencies=[Depends(checker_invalid1)])
async def some_endpoint4() -> dict[str, str]:
    return {}


@app.get("/some/endpoint5", dependencies=[Depends(checker_invalid2)])
async def some_endpoint5() -> dict[str, str]:
    return {}


@app.get("/some/endpoint6", dependencies=[Depends(checker_invalid3)])
async def some_endpoint6() -> dict[str, str]:
    return {}


@app.get("/some/endpoint7", dependencies=[Depends(checker_any)])
async def some_endpoint7() -> dict[str, str]:
    return {}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_permissions(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(transport=ASGITransport(app=app), base_url=TEST_URL) as ac:
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
async def test_get_permission(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(transport=ASGITransport(app=app), base_url=TEST_URL) as ac:
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_permissions_checkers(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(transport=ASGITransport(app=app), base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "notadmin@test.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # test valid permissions
        for x in range(1, 4):
            url = f"/some/endpoint{x}"
            response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200

        # check the any permission checker
        url = "/some/endpoint7"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        # test invalid permissions
        for x in range(4, 7):
            url = f"/some/endpoint{x}"
            response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 403
            assert "User does not have required permissions" in response.text

        # login is admin and verify that this user gets a successful response to all endpoints
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        for x in range(1, 7):
            url = f"/some/endpoint{x}"
            response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
