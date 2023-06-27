#
# Copyright Tristen Georgiou 2023
#
import argparse
import asyncio
import getpass

from tasos.apiauth.auth import get_user_by_email, hash_password
from tasos.apiauth.db import get_sessionmaker
from tasos.apiauth.model import UserOrm, User, Registration


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

        print(f"User created successfully: {User.from_orm(user)}")


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
        if userargs.admin is not None:
            user.is_admin = userargs.admin
        if userargs.active is not None:
            user.is_active = userargs.active

        db.add(user)
        await db.commit()

        print(f"User updated successfully: {User.from_orm(user)}")


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
    parser_edit_user.set_defaults(func=edit_user)

    return parser


if __name__ == "__main__":  # pragma: no cover
    argparser = get_parser()
    args = argparser.parse_args()
    args.func(args)
