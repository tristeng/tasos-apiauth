#
# Copyright Tristen Georgiou 2023
#
from fastapi import FastAPI

from .base import add_base_endpoints_to_app
from .permission import add_permission_endpoints_to_app
from .user import add_user_endpoints_to_app
from .group import add_group_endpoints_to_app


def add_all_endpoints_to_app(app: FastAPI, auth_path: str = "/auth", admin_path: str = "/admin") -> None:
    """
    Adds all the endpoints to the given app - auth endpoints prefixed by /auth and admin endpoints prefixed by /admin

    :param app: The app to add the endpoints to
    :param auth_path: The path to add the authentication endpoints to
    :param admin_path: The path to add the admin endpoints to
    """

    add_base_endpoints_to_app(app, auth_path)
    add_user_endpoints_to_app(app, admin_path)
    add_group_endpoints_to_app(app, admin_path)
    add_permission_endpoints_to_app(app, admin_path)
