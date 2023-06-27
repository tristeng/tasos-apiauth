#
# Copyright Tristen Georgiou 2023
#
from datetime import datetime

from pydantic import BaseModel, EmailStr, SecretStr, validator
from sqlalchemy import String, Boolean, DateTime, ForeignKey, func, Table, Column
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from tasos.apiauth.config import get_apiauth_settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


# this is the table for the many-to-many group-permission relationship
# https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#many-to-many
# "note for a Core table, we use the sqlalchemy.Column construct, not sqlalchemy.orm.mapped_column"
usergroup_table = Table(
    "usergroup",
    Base.metadata,
    Column("user_id", ForeignKey("user.id")),
    Column("group_id", ForeignKey("group.id")),
)


class UserOrm(Base):
    """
    The User ORM model
    """

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True, unique=True)
    hashed_pw: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name="is_active_bool"))
    is_admin: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name="is_admin_bool"), insert_default=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(), index=True, nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(), index=True, insert_default=func.now())

    # relationships
    groups: Mapped[list["GroupOrm"]] = relationship(secondary=usergroup_table)


class User(BaseModel):
    """
    The user info FastAPI model - for public display
    """

    id: int
    email: EmailStr
    is_active: bool
    is_admin: bool
    last_login: datetime | None
    created: datetime

    class Config:
        orm_mode = True


class UserInternal(User):
    """
    The user internal FastAPI model - the model that mirrors the ORM model
    """

    hashed_pw: SecretStr

    groups: list["Group"]


class GroupOrm(Base):
    """
    The Group ORM model
    """

    __tablename__ = "group"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    created: Mapped[datetime] = mapped_column(DateTime(), index=True, insert_default=func.now())

    # relationships
    permissions: Mapped[list["PermissionOrm"]] = relationship(back_populates="group")


class Group(BaseModel):
    """
    The group FastAPI model
    """

    id: int
    name: str
    created: datetime
    permissions: list["Permission"]

    class Config:
        orm_mode = True


class PermissionOrm(Base):
    """
    The Permission ORM model
    """

    __tablename__ = "permission"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    group_id = mapped_column(ForeignKey("group.id"))
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    created: Mapped[datetime] = mapped_column(DateTime(), index=True, insert_default=func.now())

    # relationships
    group: Mapped[GroupOrm] = relationship(back_populates="permissions")


class Permission(BaseModel):
    """
    The permission FastAPI model
    """

    id: int
    group: Group
    name: str
    created: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    """
    The token model
    """

    access_token: str
    token_type: str = "bearer"


class Password(BaseModel):
    """
    The model to either create or change a password
    """

    password: SecretStr
    password_confirm: SecretStr

    @validator("password")
    def password_strength(cls, v: SecretStr) -> SecretStr:
        auth_settings = get_apiauth_settings()
        if not auth_settings.password_regex.match(v.get_secret_value()):
            raise ValueError(auth_settings.password_help)
        return v

    @validator("password_confirm")
    def passwords_match(cls, v: SecretStr, values: dict[str, SecretStr]) -> SecretStr:
        if "password" in values and v.get_secret_value() != values["password"].get_secret_value():
            raise ValueError("Passwords do not match")
        return v


class Registration(Password):
    """
    The registration model
    """

    email: EmailStr


class ChangePassword(Password):
    """
    The change password model
    """

    current_password: SecretStr

    @validator("current_password")
    def current_password_matches_new(cls, v: SecretStr, values: dict[str, SecretStr]) -> SecretStr:
        if "password" in values and v.get_secret_value() == values["password"].get_secret_value():
            raise ValueError("You cannot use your current password as your new password")
        return v


# update forward refs for ORM models
UserInternal.update_forward_refs()
Group.update_forward_refs()
