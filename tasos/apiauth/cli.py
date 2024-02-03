#
# Copyright Tristen Georgiou 2023
#
import argparse
import asyncio
import getpass

from sqlalchemy import select, asc, or_

from tasos.apiauth.helpers import get_objects_by_name
from tasos.apiauth.auth import get_user_by_email, hash_password
from tasos.apiauth.db import get_sessionmaker
from tasos.apiauth.model import UserOrm, User, Group, Permission, Registration, PermissionOrm, GroupOrm


async def _create_user(userargs: argparse.Namespace) -> None:
    """The async version of create_user

    :param userargs: the arguments
    :raises ValueError: if the user already exists or the password is invalid
    """
    # get the password
    password = getpass.getpass("Password: ")
    password_confirm = getpass.getpass("Confirm password: ")

    # check if the passwords match
    if password != password_confirm:
        raise ValueError("Passwords do not match")

    # validate the email and password using the pydantic models - throws a ValueError if invalid
    registration = Registration.parse_obj(
        {"email": userargs.email, "password": password, "password_confirm": password_confirm}
    )

    # connect to the database and create the user
    async_session = get_sessionmaker()
    async with async_session() as db:
        # check if the user already exists
        user = await get_user_by_email(userargs.email, db)
        if user:
            raise ValueError("A user with this email is already registered")

        user = UserOrm(
            email=registration.email,
            hashed_pw=hash_password(registration.password.get_secret_value()),
            is_active=userargs.inactive,
            is_admin=userargs.admin,
        )
        db.add(user)
        await db.commit()

        print(f"User created successfully: {User.model_validate(user)}")


async def _edit_user(userargs: argparse.Namespace) -> None:
    """The async version of edit_user

    :param userargs: the arguments
    :raises ValueError: if the user does not exist
    """
    async_session = get_sessionmaker()
    async with async_session() as db:
        # check if the user already exists
        user = await get_user_by_email(userargs.email, db)
        if not user:
            raise ValueError("A user with this email does not exist")

        # update the user
        if userargs.admin is not None:  # pragma: no cover
            user.is_admin = userargs.admin
        if userargs.active is not None:  # pragma: no cover
            user.is_active = userargs.active
        if userargs.groups:
            # special case to clear user's groups
            if len(userargs.groups) == 1 and userargs.groups[0] == "[]":
                user.groups = []
            else:
                # make sure the groups exist
                groups = await get_objects_by_name(set(userargs.groups), db, "Group", GroupOrm)
                if len(groups) != len(userargs.groups):
                    msg = ", ".join([group.name for group in groups])
                    raise ValueError(f"One or more groups were not found. Found = {msg}")
                user.groups = list(groups)

        db.add(user)
        await db.commit()

        print(f"User updated successfully: {User.model_validate(user)}")


async def _list_users(userargs: argparse.Namespace) -> None:
    """The async version of list_users

    :param userargs: the arguments
    """
    async_session = get_sessionmaker()
    async with async_session() as db:
        stmt = select(UserOrm)
        where_clauses = []
        if userargs.filter:  # pragma: no cover
            where_clauses = [UserOrm.email == fil for fil in userargs.filter]
        if userargs.admin is not None:  # pragma: no cover
            where_clauses.append(UserOrm.is_admin == userargs.admin)
        if userargs.active is not None:  # pragma: no cover
            where_clauses.append(UserOrm.is_active == userargs.active)
        if where_clauses:  # pragma: no cover
            stmt = stmt.where(or_(*where_clauses))
        stmt = stmt.order_by(asc(UserOrm.id))
        stmt = stmt.limit(userargs.limit).offset(userargs.offset)

        users = await db.execute(stmt)
        print("Users:")
        for user in users.scalars():  # pragma: no cover
            print(f"  {User.model_validate(user)}")
            if user.groups:
                print("    Groups:")
                for group in user.groups:
                    print(f"      {Group.model_validate(group)}")


async def _list_permissions(permargs: argparse.Namespace) -> None:
    """The async version of list_permissions

    :param permargs: the arguments
    """
    async_session = get_sessionmaker()
    async with async_session() as db:
        stmt = select(PermissionOrm)
        if permargs.filter:  # pragma: no cover
            where_clauses = [PermissionOrm.name.ilike(f"%{fil}%") for fil in permargs.filter]
            stmt = stmt.where(or_(*where_clauses))
        stmt = stmt.order_by(asc(PermissionOrm.id))

        permissions = await db.execute(stmt)
        print("Permissions:")
        for permission in permissions.scalars():  # pragma: no cover
            print(f"  {Permission.model_validate(permission)}")


async def _list_groups(groupargs: argparse.Namespace) -> None:
    """The async version of list_groups

    :param groupargs: the arguments
    """
    async_session = get_sessionmaker()
    async with async_session() as db:
        stmt = select(GroupOrm)
        if groupargs.filter:  # pragma: no cover
            where_clauses = [GroupOrm.name.ilike(f"%{fil}%") for fil in groupargs.filter]
            stmt = stmt.where(or_(*where_clauses))
        stmt = stmt.order_by(asc(GroupOrm.id))

        groups = await db.execute(stmt)
        print("Groups:")
        for group in groups.scalars():  # pragma: no cover
            print(f"  {Group.model_validate(group)}")


async def _create_group(groupargs: argparse.Namespace) -> None:
    """The async version of create_group

    :param groupargs: the arguments
    """
    async_session = get_sessionmaker()
    async with async_session() as db:
        # make sure the group name doesn't already exist
        result = await db.execute(select(GroupOrm).filter(GroupOrm.name == groupargs.name.lower()))
        if result.scalars().first() is not None:
            raise ValueError("A group with this name already exists")

        # make sure the permissions are valid and fetch them from the database
        permissions = await get_objects_by_name(set(groupargs.permissions), db, "Permission", PermissionOrm)

        # create the group
        group = GroupOrm(name=groupargs.name, permissions=permissions)
        db.add(group)
        await db.commit()
        await db.refresh(group)  # refresh the group to get the permissions

        print(f"Group created successfully: {Group.model_validate(group)}")


async def _edit_group(groupargs: argparse.Namespace) -> None:
    """The async version of edit_group

    :param groupargs: the arguments
    """
    async_session = get_sessionmaker()
    async with async_session() as db:
        # fetch the group by its name
        result = await db.execute(select(GroupOrm).filter(GroupOrm.name == groupargs.name))
        group = result.scalars().first()
        if group is None:
            raise ValueError(f"No group with name {groupargs.name} exists")

        # edit the group
        if groupargs.newname and groupargs.newname != groupargs.name:  # pragma: no cover
            # make sure the new name doesn't already exist
            result = await db.execute(select(GroupOrm).filter(GroupOrm.name == groupargs.newname))
            if result.scalars().first() is not None:
                raise ValueError("A group with this name already exists")
            group.name = groupargs.newname
        if groupargs.permissions:
            permissions = await get_objects_by_name(set(groupargs.permissions), db, "Permission", PermissionOrm)
            group.permissions = permissions
        else:
            # clears out the permissions for this group
            group.permissions = []

        db.add(group)
        await db.commit()

        print(f"Group updated successfully: {Group.model_validate(group)}")


def create_user(userargs: argparse.Namespace) -> None:  # pragma: no cover
    """Creates a new user

    :param userargs: the arguments
    """
    asyncio.run(_create_user(userargs))


def edit_user(userargs: argparse.Namespace) -> None:  # pragma: no cover
    """Edits an existing user

    :param userargs: the arguments
    """
    asyncio.run(_edit_user(userargs))


def list_users(userargs: argparse.Namespace) -> None:  # pragma: no cover
    """Lists the users

    :param userargs: the arguments
    """
    asyncio.run(_list_users(userargs))


def list_permissions(permargs: argparse.Namespace) -> None:  # pragma: no cover
    """Lists the permissions of available int the database

    :param permargs: the arguments
    """
    asyncio.run(_list_permissions(permargs))


def list_groups(groupargs: argparse.Namespace) -> None:  # pragma: no cover
    """Lists the groups of available int the database

    :param groupargs: the arguments
    """
    asyncio.run(_list_groups(groupargs))


def create_group(groupargs: argparse.Namespace) -> None:  # pragma: no cover
    """Creates a new group

    :param groupargs: the arguments
    """
    asyncio.run(_create_group(groupargs))


def edit_group(groupargs: argparse.Namespace) -> None:  # pragma: no cover
    """Modifies an existing group

    :param groupargs: the arguments
    """
    asyncio.run(_edit_group(groupargs))


def get_parser() -> argparse.ArgumentParser:  # pragma: no cover
    """
    Creates the argument parser for the admin commands

    :return: the argument parser
    """
    parser = argparse.ArgumentParser(
        description="Administrative commands for the API", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    subparsers = parser.add_subparsers(required=True)

    # create a new user
    parser_create_user = subparsers.add_parser("newuser", help="creates a new user")
    parser_create_user.add_argument("email", help="the email of the user")
    parser_create_user.add_argument("-a", "--admin", action="store_true", help="use this flag if the user is an admin")
    parser_create_user.add_argument(
        "-i", "--inactive", action="store_false", help="use this flag to create the user as inactive"
    )
    parser_create_user.set_defaults(func=create_user)

    # edit an existing user
    parser_edit_user = subparsers.add_parser("edituser", help="edits an existing user")
    parser_edit_user.add_argument("email", help="the email of an existing user")
    parser_edit_user.add_argument("--admin", action=argparse.BooleanOptionalAction, help="admin status toggle")
    parser_edit_user.add_argument("--active", action=argparse.BooleanOptionalAction, help="active status toggle")
    parser_edit_user.add_argument(
        "--groups", action="extend", nargs="+", type=str, help="groups to set for the user (exact names) or [] to clear"
    )
    parser_edit_user.set_defaults(func=edit_user)

    # list the users
    parser_list_users = subparsers.add_parser("listusers", help="lists the users")
    parser_list_users.add_argument(
        "--filter", action="extend", nargs="+", type=str, help="filter the users by 1+ emails"
    )
    parser_list_users.add_argument("--admin", action=argparse.BooleanOptionalAction, help="admin status toggle")
    parser_list_users.add_argument("--active", action=argparse.BooleanOptionalAction, help="active status toggle")
    parser_list_users.add_argument("--limit", type=int, default=50, help="the maximum number of users to return")
    parser_list_users.add_argument("--offset", type=int, default=0, help="the number of users to skip")
    parser_list_users.set_defaults(func=list_users)

    # list the permissions
    parser_list_permissions = subparsers.add_parser("listpermissions", help="lists the permissions")
    parser_list_permissions.add_argument(
        "--filter", action="extend", nargs="+", type=str, help="filter the permissions by 1+ names"
    )
    parser_list_permissions.set_defaults(func=list_permissions)

    # list the groups
    parser_list_groups = subparsers.add_parser("listgroups", help="lists the groups")
    parser_list_groups.add_argument(
        "--filter", action="extend", nargs="+", type=str, help="filter the groups by 1+ names"
    )
    parser_list_groups.set_defaults(func=list_groups)

    # create new group
    parser_create_group = subparsers.add_parser("newgroup", help="creates a new group")
    parser_create_group.add_argument("name", help="the name of the group")
    parser_create_group.add_argument(
        "--permissions", action="extend", nargs="+", type=str, help="permissions to set to the group (exact names)"
    )
    parser_create_group.set_defaults(func=create_group)

    # edit an existing group
    parser_edit_group = subparsers.add_parser("editgroup", help="edits an existing group")
    parser_edit_group.add_argument("name", help="the name of the group to edit")
    parser_edit_group.add_argument("--newname", help="the updated name of the group", type=str)
    parser_edit_group.add_argument(
        "--permissions", action="extend", nargs="+", type=str, help="permissions to set to the group (exact names)"
    )
    parser_edit_group.set_defaults(func=edit_group)

    return parser


if __name__ == "__main__":  # pragma: no cover
    argparser = get_parser()
    args = argparser.parse_args()
    args.func(args)
