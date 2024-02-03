#
# Copyright Tristen Georgiou 2023
#
# mostly implemented according to https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt
from datetime import datetime, timedelta, UTC
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tasos.apiauth.config import get_apiauth_settings
from tasos.apiauth.db import DatabaseDepends
from tasos.apiauth.model import UserOrm

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# blowfish cryptography hashing algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password passed in as plain text against a hashed password (e.g. from the DB)

    :param plain_password: the input plain text password to check
    :param hashed_password: the stored hashed password to check against
    :return: True if they are equivalent, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(plain_password: str) -> str:
    """Returns the equivalent hashed password from an input plain text password

    :param plain_password: the input plain text password
    :return: the equivalent hashed version of the password
    """
    return pwd_context.hash(plain_password)


def create_access_token(data: dict[str, Any]) -> str:
    """Creates a JWT access token

    :param data: the input data used to create the token
    :return: a JWT string
    """
    auth_settings = get_apiauth_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=auth_settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, auth_settings.secret_key, algorithm=auth_settings.algorithm)
    return encoded_jwt


async def get_user_by_email(email: str, db: AsyncSession) -> UserOrm | None:
    """Gets a user from the database using their email

    :param email: the user's email
    :param db: the database session
    :return: the user object or None if the user doesn't exist
    """
    # load the groups at the same time
    result = await db.execute(select(UserOrm).filter(UserOrm.email == email))
    return result.scalars().first()


async def authenticate_user(email: str, password: str, db: AsyncSession) -> UserOrm:
    """Authenticates a user by their email and password

    :param email: the user's email
    :param password: the user's password
    :param db: the database session
    :return: the user object if the user exists and the password is correct, False otherwise
    :raises ValueError: if the email or password is invalid
    """
    user = await get_user_by_email(email, db)
    if not user or not verify_password(password, user.hashed_pw):
        raise ValueError("Invalid email or password")

    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DatabaseDepends) -> UserOrm:
    """Gets the current user from the database using their JWT token

    :param token: the JWT token
    :param db: the database session
    :return: the user object
    :raises HTTPException: if the token is invalid or the user doesn't exist
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        auth_settings = get_apiauth_settings()
        payload = jwt.decode(token, auth_settings.secret_key, algorithms=[auth_settings.algorithm])
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception

    except JWTError:  # pragma: no cover
        raise credentials_exception

    # shouldn't be possible for this to be None, but just in case
    user = await get_user_by_email(email, db)
    if user is None:  # pragma: no cover
        raise credentials_exception

    return user


async def get_current_active_user(user: Annotated[UserOrm, Depends(get_current_user)]) -> UserOrm:
    """Checks if the current user is active

    :param user: the user object as returned by the get_current_user dependency
    :return: the user object
    :raises HTTPException: if the user is not active
    """
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    return user


async def get_current_admin_user(user: Annotated[UserOrm, Depends(get_current_user)]) -> UserOrm:
    """Checks if the current user is an admin

    :param user: the user object as returned by the get_current_user dependency
    :return: the user object
    :raises HTTPException: if the user is not an admin
    """
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not admin")

    return user
