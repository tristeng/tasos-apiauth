#
# Copyright Tristen Georgiou 2023
#
from datetime import datetime, UTC
from typing import Annotated, Callable, Awaitable

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from tasos.apiauth.auth import (
    authenticate_user,
    create_access_token,
    get_user_by_email,
    hash_password,
    get_current_active_user,
)
from tasos.apiauth.db import DatabaseDepends
from tasos.apiauth.model import Token, Registration, UserOrm, User, ChangePassword


post_registration_hooks: list[Callable[[AsyncSession, UserOrm], Awaitable[None]]] = []


def add_base_endpoints_to_app(app: FastAPI, path: str = "/auth") -> None:
    """
    Adds the base endpoints to the given app

    :param app: The app to add the endpoints to
    :param path: The path to add the endpoints to
    """

    assert path == "" or path.startswith("/"), "Path must start with '/'"

    # remove any trailing slashes from the path
    path = path.rstrip("/")

    @app.post(
        path + "/register",
        status_code=status.HTTP_201_CREATED,
        response_model=User,
        description="Registers a new user",
        tags=["auth"],
    )
    async def register(form_data: Registration, db: DatabaseDepends, background_tasks: BackgroundTasks) -> UserOrm:
        """
        Registers a new user with the given email and password
        """
        # check if the user exists in the database
        user = await get_user_by_email(form_data.email, db)
        if user:
            # if the user exists, raise an exception
            raise HTTPException(status.HTTP_409_CONFLICT, detail="A user with this email is already registered")

        # otherwise create the user in the database
        user = UserOrm(
            email=form_data.email, hashed_pw=hash_password(form_data.password.get_secret_value()), is_active=True
        )
        db.add(user)
        await db.commit()

        # call any post registration hooks - for example to send a welcome email
        if post_registration_hooks:
            for hook in post_registration_hooks:
                background_tasks.add_task(hook, db, user)

        return user

    @app.post(
        path + "/token", response_model=Token, description="Authenticates a user and returns a JWT token", tags=["auth"]
    )
    async def login_for_access_token(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DatabaseDepends
    ) -> Token:
        """
        Attempts to login a user from email and password and returns the JWT token if successful
        """
        try:
            user = await authenticate_user(form_data.username, form_data.password, db)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # check if the user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is not active - please contact an administrator",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # update the last login time
        user.last_login = datetime.now(UTC)
        await db.commit()

        return Token(access_token=create_access_token(data={"sub": user.email}))

    @app.get(
        path + "/whoami", response_model=User, description="Returns information about the current user", tags=["auth"]
    )
    async def current_user_info(current_user: Annotated[UserOrm, Depends(get_current_active_user)]) -> UserOrm:
        """
        Returns information about the current user
        """
        return current_user

    @app.put(
        path + "/password",
        status_code=status.HTTP_204_NO_CONTENT,
        description="Changes the current user's password",
        tags=["auth"],
    )
    async def change_password(
        form_data: ChangePassword,
        current_user: Annotated[UserOrm, Depends(get_current_active_user)],
        db: DatabaseDepends,
    ) -> None:
        """
        Changes the current user's password
        """
        # check if the old password is correct
        try:
            user = await authenticate_user(current_user.email, form_data.current_password.get_secret_value(), db)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Existing password is incorrect")

        # update the password
        user.hashed_pw = hash_password(form_data.password.get_secret_value())
        db.add(user)
        await db.commit()
