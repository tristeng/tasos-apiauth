#
# Copyright Tristen Georgiou 2023
#
import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tasos.apiauth.api.base import add_base_endpoints_to_app, post_registration_hooks
from tasos.apiauth.auth import hash_password
from tasos.apiauth.db import get_engine, get_sessionmaker
from tasos.apiauth.model import Base, UserOrm


# test app
app = FastAPI()
add_base_endpoints_to_app(app)


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    # create the database and tables
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # create a deactivated user and an admin user
    session_maker = get_sessionmaker()
    async with session_maker() as conn:
        d_user = UserOrm(email="not@active.com", hashed_pw=hash_password("Abcdef123!"), is_active=False, is_admin=False)
        admin = UserOrm(email="me@admin.com", hashed_pw=hash_password("Abcdef123!"), is_active=True, is_admin=True)

        conn.add(d_user)
        conn.add(admin)
        await conn.commit()

    yield engine  # run the tests

    # drop the database and tables
    await engine.dispose()


@pytest.fixture
def register_payload() -> dict[str, str]:
    return {
        "email": "test@test.com",
        "password": "Abcdef123!",
        "password_confirm": "Abcdef123!",
    }


TEST_URL = "http://test"
HOOK_CALLED = False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_register(db_engine: AsyncEngine, register_payload: dict[str, str]) -> None:  # noqa
    # test a post registration hook
    async def hook(db: AsyncSession, user: UserOrm) -> None:  # noqa
        global HOOK_CALLED
        HOOK_CALLED = True

    # add the task to the list of hooks
    post_registration_hooks.append(hook)

    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        url = "/auth/register"
        response = await ac.post(url, json=register_payload)

    assert response.status_code == 201
    resp = response.json()

    assert resp["id"] is not None
    assert resp["email"] == "test@test.com"
    assert resp["is_active"] is True
    assert resp["is_admin"] is False
    assert resp["last_login"] is None

    # test that the post registration hook was called
    await asyncio.sleep(0.5)  # wait for the background task to finish
    assert HOOK_CALLED is True

    # try to register the same user again
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        response = await ac.post(url, json=register_payload)

    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.integration
async def test_login_for_access_token(db_engine: AsyncEngine, register_payload: dict[str, str]) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # test login with valid credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})

        assert response.status_code == 200
        resp = response.json()
        assert resp["access_token"] is not None
        assert resp["token_type"] == "bearer"

        # test login with invalid credentials
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Incorrect123!"})
        resp = response.json()
        assert response.status_code == 401
        assert resp["detail"] == "Incorrect email or password"

        # try to login with a non-existent user
        response = await ac.post(url, data={"username": "not@real.com", "password": "WhoamI?123!"})
        resp = response.json()
        assert response.status_code == 401
        assert resp["detail"] == "Incorrect email or password"

        # try to login with a deactivated user
        response = await ac.post(url, data={"username": "not@active.com", "password": "Abcdef123!"})
        resp = response.json()
        assert response.status_code == 403
        assert resp["detail"] == "This account is not active - please contact an administrator"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_current_user_info(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # test getting current user info
        url = "/auth/whoami"
        response = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        resp = response.json()
        assert resp["email"] == "me@admin.com"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_change_password(db_engine: AsyncEngine) -> None:  # noqa
    async with AsyncClient(app=app, base_url=TEST_URL) as ac:
        # login to get credentials
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        # test changing password with invalid current password
        url = "/auth/password"
        response = await ac.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "ThisIsWrong1234!", "password": "Abcdef1234!", "password_confirm": "Abcdef1234!"},
        )
        assert response.status_code == 400
        resp = response.json()
        assert resp["detail"] == "Existing password is incorrect"

        # test changing password successfully
        response = await ac.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "Abcdef123!", "password": "Abcdef1234!", "password_confirm": "Abcdef1234!"},
        )
        assert response.status_code == 204
        assert response.text == ""

        # test logging in with the new password
        url = "/auth/token"
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef1234!"})
        assert response.status_code == 200

        # test logging in with the old password
        response = await ac.post(url, data={"username": "me@admin.com", "password": "Abcdef123!"})
        assert response.status_code == 401
        resp = response.json()
        assert resp["detail"] == "Incorrect email or password"
