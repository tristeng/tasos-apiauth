#
# Copyright Tristen Georgiou 2023
#
import argparse
import asyncio
import getpass

from tasos.apiauth.auth import get_user_by_email, hash_password
from tasos.apiauth.db import get_sessionmaker
from tasos.apiauth.model import UserOrm, UserInfo, Registration


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

        print(f"User created successfully: {UserInfo.from_orm(user)}")


def create_user(userargs: argparse.Namespace) -> None:  # pragma: no cover
    """Creates a new user

    :param userargs: the arguments
    """
    asyncio.run(_create_user(userargs))


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
    parser_user = subparsers.add_parser("newuser", help="creates a new user")
    parser_user.add_argument("email", help="the email of the user")
    parser_user.add_argument("-a", "--admin", action="store_true", help="use this flag if the user is an admin")
    parser_user.add_argument(
        "-i", "--inactive", action="store_false", help="use this flag to create the user as inactive"
    )
    parser_user.set_defaults(func=create_user)

    return parser


if __name__ == "__main__":  # pragma: no cover
    argparser = get_parser()
    args = argparser.parse_args()
    args.func(args)
