#
# Copyright Tristen Georgiou 2023
#
from unittest.mock import AsyncMock, MagicMock
from typing import Any

import pytest
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from tasos.apiauth.auth import (
    pwd_context,
    verify_password,
    hash_password,
    create_access_token,
    get_user_by_email,
    authenticate_user,
    get_current_user,
    get_current_active_user,
    get_current_admin_user,
)
from tasos.apiauth.model import UserOrm


@pytest.fixture
def mock_pwd_context(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_verify(plain: str, hashed: str) -> bool:
        # override the verify to check string equivalence
        return plain == hashed

    monkeypatch.setattr(pwd_context, "verify", mock_verify)

    def mock_hash(plain: str) -> str:
        return plain

    monkeypatch.setattr(pwd_context, "hash", mock_hash)


@pytest.fixture
def mock_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_encode(claims: dict[str, Any], key: str, algorithm: str) -> str:  # noqa
        return "abc.def.ghi"

    monkeypatch.setattr(jwt, "encode", mock_encode)

    def mock_decode(token: str, key: str, algorithms: str) -> dict[str, str]:  # noqa
        return {"sub": "test@test.com"}

    monkeypatch.setattr(jwt, "decode", mock_decode)


@pytest.fixture
def mock_jwt_decode_missing_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_decode(token: str, key: str, algorithms: list[str]) -> dict[str, str]:  # noqa
        return {"wrong": "should fail"}

    monkeypatch.setattr(jwt, "decode", mock_decode)


@pytest.fixture
def mock_get_user_by_email(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_get_user_by_email(email: str, db: AsyncSession) -> UserOrm | None:  # noqa
        return UserOrm(id=1, email=email, hashed_pw="mypass", is_active=True)

    monkeypatch.setattr("tasos.apiauth.auth.get_user_by_email", mock_get_user_by_email)


@pytest.fixture
def mock_get_user_by_email_user_not_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_get_user_by_email(email: str, db: AsyncSession) -> UserOrm | None:  # noqa
        return None

    monkeypatch.setattr("tasos.apiauth.auth.get_user_by_email", mock_get_user_by_email)


def test_verify_password(mock_pwd_context: None) -> None:
    # doesn't test much other than to just cover the code
    assert verify_password("mypass", "mypass")
    assert not verify_password("mypass", "wrongpass")


def test_hash_password(mock_pwd_context: None) -> None:
    # doesn't test much other than to just cover the code
    assert hash_password("mysecret") == "mysecret"


def test_create_access_token(mock_jwt: None) -> None:
    # doesn't test much other than to just cover the code
    assert create_access_token({"sub": "username"}) == "abc.def.ghi"


@pytest.mark.asyncio
async def test_get_user_by_email() -> None:
    mock_db = AsyncMock(AsyncSession)
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result

    await get_user_by_email("test@test.com", mock_db)

    mock_db.execute.assert_called_once()
    stmt: Select[Any] = mock_db.execute.call_args[0][0]
    assert stmt.whereclause is not None
    assert "test@test.com" == stmt.whereclause.expression.right.expression.value

    mock_result.scalars().first.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_user(mock_pwd_context: None, mock_get_user_by_email: None) -> None:
    mock_db = AsyncMock(AsyncSession)
    user = await authenticate_user("test@test.com", "mypass", mock_db)
    assert user.id == 1 and user.email == "test@test.com"

    # test when password is wrong
    with pytest.raises(ValueError, match="Invalid email or password"):
        await authenticate_user("test@test.com", "wrongpass", mock_db)


@pytest.mark.asyncio
async def test_authenticate_user_not_exists(
    mock_pwd_context: None, mock_get_user_by_email_user_not_exists: None
) -> None:
    mock_db = AsyncMock(AsyncSession)
    with pytest.raises(ValueError, match="Invalid email or password"):
        await authenticate_user("test@test.com", "mypass", mock_db)


@pytest.mark.asyncio
async def test_get_current_user(mock_jwt: None, mock_get_user_by_email: None) -> None:
    mock_token = "some.fake.token"
    mock_db = AsyncMock(AsyncSession)
    user = await get_current_user(mock_token, mock_db)
    assert user.id == 1 and user.email == "test@test.com"


@pytest.mark.asyncio
async def test_get_current_user_decode_fails(mock_jwt_decode_missing_sub: None, mock_get_user_by_email: None) -> None:
    mock_token = "some.fake.token"
    mock_db = AsyncMock(AsyncSession)

    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(mock_token, mock_db)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Could not validate credentials"


@pytest.mark.asyncio
async def test_get_current_active_user() -> None:
    active_user = UserOrm(id=1, email="test@test.com", hashed_pw="mypass", is_active=True)
    user = await get_current_active_user(active_user)
    assert user == active_user

    inactive_user = UserOrm(id=1, email="test@test.com", hashed_pw="mypass", is_active=False)

    with pytest.raises(HTTPException) as excinfo:
        await get_current_active_user(inactive_user)

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Inactive user"


@pytest.mark.asyncio
async def test_get_current_admin_user() -> None:
    admin_user = UserOrm(id=1, email="test@test.com", hashed_pw="mypass", is_active=True, is_admin=True)
    user = await get_current_admin_user(admin_user)
    assert user == admin_user

    non_admin_user = UserOrm(id=1, email="test@test.com", hashed_pw="mypass", is_active=True, is_admin=False)
    with pytest.raises(HTTPException) as excinfo:
        await get_current_admin_user(non_admin_user)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "User is not admin"
