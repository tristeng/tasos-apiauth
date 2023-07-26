#
# Copyright Tristen Georgiou 2023
#
from collections.abc import Iterator
from datetime import datetime
from typing import Type
from unittest.mock import AsyncMock, MagicMock

import pytest

from tasos.apiauth.model import UserOrm, PermissionOrm, GroupOrm, Base
from tasos.apiauth.cli import (
    get_parser,
    _create_user,  # noqa
    _edit_user,  # noqa
    _list_permissions,  # noqa
    _list_groups,  # noqa
    _list_users,  # noqa
    _create_group,  # noqa
    _edit_group,  # noqa
)


@pytest.fixture
def mock_getpass_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_getpass(prompt: str) -> str:  # noqa
        return "Abcdef123!"

    monkeypatch.setattr("getpass.getpass", mock_getpass)


@pytest.fixture
def mock_getpass_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_getpass(prompt: str) -> Iterator[str]:  # noqa
        yield "Abcdef123!"
        yield "abcdef123!"

    monkeypatch.setattr("getpass.getpass", mock_getpass)


@pytest.fixture
def mock_database(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock_db = AsyncMock()
    mock_db.add = MagicMock()  # add is an sync method
    mock_db.execute = AsyncMock(return_value=MagicMock())  # execute is an async method, but the return value is sync

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_db
    mock_session_maker = MagicMock(return_value=mock_cm)

    def mock_get_sessionmaker() -> MagicMock:
        return mock_session_maker

    monkeypatch.setattr("tasos.apiauth.cli.get_sessionmaker", mock_get_sessionmaker)

    return mock_db


@pytest.fixture
def mock_user_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_user_from_orm(user: UserOrm) -> str:  # noqa
        return "user info"

    monkeypatch.setattr("tasos.apiauth.cli.User.from_orm", mock_user_from_orm)


@pytest.fixture
def mock_hash_password(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_hash_password(plain: str) -> str:  # noqa
        return plain

    monkeypatch.setattr("tasos.apiauth.cli.hash_password", mock_hash_password)


@pytest.fixture
def mock_get_user_not_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_get_user_by_email(email: str, session: AsyncMock) -> None:  # noqa
        # return None to signify the user hasn't been registered yet
        return None

    monkeypatch.setattr("tasos.apiauth.cli.get_user_by_email", mock_get_user_by_email)


@pytest.fixture
def mock_get_user_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_get_user_by_email(email: str, session: AsyncMock) -> UserOrm:  # noqa
        # return a user to signify this email has already been registered
        return UserOrm(
            id=4,
            email="test@test.com",
            hashed_pw="Abcdef123!",
            is_active=True,
            is_admin=False,
            groups=[
                GroupOrm(id=1, name="group1", created=datetime.now()),
                GroupOrm(id=2, name="group2", created=datetime.now()),
            ],
        )

    monkeypatch.setattr("tasos.apiauth.cli.get_user_by_email", mock_get_user_by_email)


@pytest.fixture
def mock_get_permissions(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_get_objects_by_name(
        names: set[str], db: AsyncMock, model_name: str, orm: Type[Base]  # noqa
    ) -> list[Base]:
        return [
            PermissionOrm(id=1, name="read", created=datetime.now()),
            PermissionOrm(id=2, name="write", created=datetime.now()),
        ]

    monkeypatch.setattr("tasos.apiauth.cli.get_objects_by_name", mock_get_objects_by_name)


def create_user_assertions(mock_database: AsyncMock, expected: UserOrm) -> None:
    mock_database.add.assert_called_once()
    actual = mock_database.add.call_args.args[0]
    assert actual.email == expected.email
    assert actual.hashed_pw == expected.hashed_pw
    assert actual.is_active == expected.is_active
    assert actual.is_admin == expected.is_admin
    mock_database.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_user(
    mock_getpass_valid: None,
    mock_database: AsyncMock,
    mock_user_model: None,
    mock_hash_password: None,
    mock_get_user_not_exists: None,
) -> None:
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
    mock_getpass_valid: None,
    mock_database: AsyncMock,
    mock_user_model: None,
    mock_hash_password: None,
    mock_get_user_not_exists: None,
) -> None:
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
async def test_create_user_no_matching_password(mock_getpass_no_match: None) -> None:
    parser = get_parser()
    args = parser.parse_args("newuser test@test.com".split())

    with pytest.raises(ValueError, match="Passwords do not match"):
        await _create_user(args)


@pytest.mark.asyncio
async def test_create_user_already_exists(
    mock_getpass_valid: None, mock_database: AsyncMock, mock_get_user_exists: None
) -> None:
    parser = get_parser()
    args = parser.parse_args("newuser test@test.com".split())

    with pytest.raises(ValueError, match="A user with this email is already registered"):
        await _create_user(args)


@pytest.mark.asyncio
async def test_edit_user(mock_database: AsyncMock, mock_get_user_exists: None, mock_user_model: None) -> None:
    parser = get_parser()

    # test setting a user to admin and deactivating them
    args = parser.parse_args("edituser test@test.com --admin --no-active".split())
    await _edit_user(args)

    mock_database.add.assert_called_once()
    actual = mock_database.add.call_args.args[0]
    assert actual.email == "test@test.com"
    assert actual.is_active is False
    assert actual.is_admin is True
    mock_database.commit.assert_called_once()


@pytest.mark.asyncio
async def test_edit_user_not_exists(
    mock_database: AsyncMock, mock_get_user_not_exists: None, mock_user_model: None
) -> None:
    parser = get_parser()

    # test setting a user to admin and deactivating them
    args = parser.parse_args("edituser who@isthis.com --admin".split())
    with pytest.raises(ValueError, match="A user with this email does not exist"):
        await _edit_user(args)


@pytest.mark.asyncio
async def test_list_users(mock_database: AsyncMock) -> None:
    parser = get_parser()

    # test listing the permissions
    args = parser.parse_args("listusers --filter abc@def.com --no-admin --active --limit 5 --offset 25".split())

    await _list_users(args)
    mock_database.execute.assert_called_once()
    actual = mock_database.execute.call_args.args[0]

    # convert the actual statement into a SQL string and ensure the sql contains the correct clauses
    sql = str(actual.compile(compile_kwargs={"literal_binds": True}))
    assert "\"user\".email = 'abc@def.com'" in sql
    assert '"user".is_admin = false' in sql
    assert '"user".is_active = true' in sql
    assert "LIMIT 5" in sql
    assert "OFFSET 25" in sql


@pytest.mark.asyncio
async def test_list_permissions(mock_database: AsyncMock) -> None:
    parser = get_parser()

    # test listing the permissions
    args = parser.parse_args("listpermissions --filter abc def".split())

    await _list_permissions(args)
    mock_database.execute.assert_called_once()
    actual = mock_database.execute.call_args.args[0]

    # convert the actual statement into a SQL string and ensure the sql contains the correct clauses
    sql = str(actual.compile(compile_kwargs={"literal_binds": True}))
    assert "lower(permission.name) LIKE lower('%abc%')" in sql
    assert "lower(permission.name) LIKE lower('%def%')" in sql
    assert " OR " in sql


@pytest.mark.asyncio
async def test_list_groups(mock_database: AsyncMock) -> None:
    parser = get_parser()

    # test listing the groups
    args = parser.parse_args("listgroups --filter abc def".split())

    await _list_groups(args)
    mock_database.execute.assert_called_once()
    actual = mock_database.execute.call_args.args[0]

    # convert the actual statement into a SQL string and ensure the sql contains the correct clauses
    sql = str(actual.compile(compile_kwargs={"literal_binds": True}))
    assert "lower(\"group\".name) LIKE lower('%abc%')" in sql
    assert "lower(\"group\".name) LIKE lower('%def%')" in sql
    assert " OR " in sql


@pytest.mark.asyncio
async def test_create_group(mock_database: AsyncMock, mock_get_permissions: None) -> None:
    result = MagicMock()
    result.scalars().first = MagicMock(return_value=None)  # return None to signify the group doesn't exist
    mock_database.execute = AsyncMock(return_value=result)

    def mock_add(group: GroupOrm) -> None:
        group.id = 1
        group.created = datetime.now()

    mock_database.add = mock_add

    parser = get_parser()

    # test group creation
    args = parser.parse_args("newgroup TestGroup --permissions read write".split())

    await _create_group(args)
    mock_database.execute.assert_called_once()
    actual = mock_database.execute.call_args.args[0]

    # convert the actual statement into a SQL string and ensure the sql contains the correct clauses
    sql = str(actual.compile(compile_kwargs={"literal_binds": True}))
    assert "\"group\".name = 'testgroup'" in sql  # should be lowercase

    mock_database.commit.assert_called_once()
    mock_database.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_create_group_already_exists(mock_database: AsyncMock, mock_get_permissions: None) -> None:
    result = MagicMock()
    result.scalars().first = MagicMock(return_value=GroupOrm(id=1, name="testgroup", created=datetime.now()))
    mock_database.execute = AsyncMock(return_value=result)

    parser = get_parser()

    # test group creation
    args = parser.parse_args("newgroup TestGroup --permissions read write".split())

    with pytest.raises(ValueError, match="A group with this name already exists"):
        await _create_group(args)


@pytest.mark.asyncio
async def test_edit_group(mock_database: AsyncMock, mock_get_permissions: None) -> None:
    result = MagicMock()

    # first result is to get the group to modify, second call is to ensure a group with the new name doesn't exist
    result.scalars().first = MagicMock(side_effect=[GroupOrm(id=1, name="testgroup", created=datetime.now()), None])
    mock_database.execute = AsyncMock(return_value=result)  # group must exist for edit

    parser = get_parser()

    # test group edit, new name and permissions
    args = parser.parse_args("editgroup TestGroup --newname grouptest --permissions read write".split())

    await _edit_group(args)

    mock_database.add.assert_called_once()
    actual = mock_database.add.call_args.args[0]

    assert actual.name == "grouptest"
    assert len(actual.permissions) == 2
    assert actual.permissions[0].name == "read"
    assert actual.permissions[1].name == "write"


@pytest.mark.asyncio
async def test_edit_group_newname_exists(mock_database: AsyncMock, mock_get_permissions: None) -> None:
    result = MagicMock()

    # first result is to get the group to modify, second call is to ensure a group with the new name doesn't exist
    result.scalars().first = MagicMock(
        side_effect=[
            GroupOrm(id=1, name="testgroup", created=datetime.now()),
            GroupOrm(id=2, name="grouptest", created=datetime.now()),
        ]
    )
    mock_database.execute = AsyncMock(return_value=result)

    parser = get_parser()

    # test group edit
    args = parser.parse_args("editgroup TestGroup --newname grouptest".split())

    with pytest.raises(ValueError, match="A group with this name already exists"):
        await _edit_group(args)


@pytest.mark.asyncio
async def test_edit_group_not_exists(mock_database: AsyncMock, mock_get_permissions: None) -> None:
    result = MagicMock()

    # first result is to get the group to modify, second call is to ensure a group with the new name doesn't exist
    result.scalars().first = MagicMock(return_value=None)
    mock_database.execute = AsyncMock(return_value=result)

    parser = get_parser()

    # test group edit
    args = parser.parse_args("editgroup TestGroup --newname grouptest".split())

    with pytest.raises(ValueError, match="No group with name TestGroup exists"):
        await _edit_group(args)


@pytest.mark.asyncio
async def test_edit_group_no_permissions(mock_database: AsyncMock, mock_get_permissions: None) -> None:
    result = MagicMock()

    # first result is to get the group to modify, second call is to ensure a group with the new name doesn't exist
    result.scalars().first = MagicMock(side_effect=[GroupOrm(id=1, name="testgroup", created=datetime.now()), None])
    mock_database.execute = AsyncMock(return_value=result)  # group must exist for edit

    parser = get_parser()

    # test group edit, new name and permissions
    args = parser.parse_args("editgroup TestGroup --newname grouptest".split())

    await _edit_group(args)

    mock_database.add.assert_called_once()
    actual = mock_database.add.call_args.args[0]

    assert actual.name == "grouptest"
    assert len(actual.permissions) == 0
