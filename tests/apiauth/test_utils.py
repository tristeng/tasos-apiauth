#
# Copyright Tristen Georgiou 2023
#
from unittest.mock import AsyncMock, MagicMock

import pytest

from tasos.apiauth.model import UserOrm
from tasos.apiauth.utils import _create_user, get_parser  # noqa


@pytest.fixture
def mock_getpass_valid(monkeypatch):
    def mock_getpass(prompt):  # noqa
        return "Abcdef123!"

    monkeypatch.setattr("getpass.getpass", mock_getpass)


@pytest.fixture
def mock_getpass_no_match(monkeypatch):
    def mock_getpass(prompt):  # noqa
        yield "Abcdef123!"
        yield "abcdef123!"

    monkeypatch.setattr("getpass.getpass", mock_getpass)


@pytest.fixture
def mock_database(monkeypatch):
    mock_db = AsyncMock()
    mock_db.add = MagicMock()  # add is an sync method

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_db
    mock_session_maker = MagicMock(return_value=mock_cm)

    def mock_get_sessionmaker():
        return mock_session_maker

    monkeypatch.setattr("tasos.apiauth.utils.get_sessionmaker", mock_get_sessionmaker)

    return mock_db


@pytest.fixture
def mock_user_info_from_orm(monkeypatch):
    def mock_user_info_from_orm(user):  # noqa
        return "user info"

    monkeypatch.setattr("tasos.apiauth.utils.UserInfo.from_orm", mock_user_info_from_orm)


@pytest.fixture
def mock_hash_password(monkeypatch):
    def mock_hash_password(plain):  # noqa
        return plain

    monkeypatch.setattr("tasos.apiauth.utils.hash_password", mock_hash_password)


@pytest.fixture
def mock_get_user_not_exists(monkeypatch):
    async def mock_get_user_by_email(email, session):  # noqa
        # return None to signify the user hasn't been registered yet
        return None

    monkeypatch.setattr("tasos.apiauth.utils.get_user_by_email", mock_get_user_by_email)


@pytest.fixture
def mock_get_user_exists(monkeypatch):
    async def mock_get_user_by_email(email, session):  # noqa
        # return a user to signify this email has already been registered
        return UserOrm(
            email="test@test.com",
            hashed_pw="Abcdef123!",
            is_active=True,
            is_admin=False,
        )

    monkeypatch.setattr("tasos.apiauth.utils.get_user_by_email", mock_get_user_by_email)


def create_user_assertions(mock_database, expected):
    mock_database.add.assert_called_once()
    actual = mock_database.add.call_args.args[0]
    assert actual.email == expected.email
    assert actual.hashed_pw == expected.hashed_pw
    assert actual.is_active == expected.is_active
    assert actual.is_admin == expected.is_admin
    mock_database.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_user(
    mock_getpass_valid, mock_database, mock_user_info_from_orm, mock_hash_password, mock_get_user_not_exists
):
    # the happy case with defaults
    parser = get_parser()
    args = parser.parse_args("newuser test@test.com".split())
    await _create_user(args)

    expected = UserOrm(
        email="test@test.com",
        hashed_pw="Abcdef123!",
        is_active=True,
        is_admin=False,
    )

    create_user_assertions(mock_database, expected)


@pytest.mark.asyncio
async def test_create_user_admin_inactive(
    mock_getpass_valid, mock_database, mock_user_info_from_orm, mock_hash_password, mock_get_user_not_exists
):
    # the happy case with all flags
    parser = get_parser()
    args = parser.parse_args("newuser test@test.com --admin --inactive".split())
    await _create_user(args)

    expected = UserOrm(
        email="test@test.com",
        hashed_pw="Abcdef123!",
        is_active=False,
        is_admin=True,
    )

    create_user_assertions(mock_database, expected)


@pytest.mark.asyncio
async def test_create_user_no_matching_password(mock_getpass_no_match):
    parser = get_parser()
    args = parser.parse_args("newuser test@test.com".split())

    with pytest.raises(ValueError, match="Passwords do not match"):
        await _create_user(args)


@pytest.mark.asyncio
async def test_create_user_already_exists(mock_getpass_valid, mock_database, mock_get_user_exists):
    parser = get_parser()
    args = parser.parse_args("newuser test@test.com".split())

    with pytest.raises(ValueError, match="A user with this email is already registered"):
        await _create_user(args)
